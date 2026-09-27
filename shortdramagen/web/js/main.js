// Point d'entrée : coquille, routeur par hash, état partagé, temps réel, raccourcis.
//
// Routes (spec §4.1) :
//   #/                                   Bibliothèque   (?f=filtre&q=recherche&tri=…&vue=liste)
//   #/serie/<ref>/<vo|fr|es…>             Fiche d'une version (ref : n° DramaBox ou plateforme:n°)
//   #/serie/<ref>/<v>/lire/<n|film>       Théâtre par-dessus la fiche
//   #/reglages/<section>                  Réglages
//   #/activite                            Tiroir Activité (page sur mobile)

import { makeActions } from "./actions.js";
import { get } from "./api.js";
import { detect, linkLabel } from "./detect.js";
import { append, clear, announce, h, icon } from "./dom.js";
import { versionShort } from "./format.js";
import { activity, applyJobEvent, connectEvents, renderPill } from "./live.js";
import { openDialog, toast, closeLayer } from "./ui.js";
import { renderActivity } from "./views/activity.js";
import { openAddDialog } from "./views/add.js";
import { firstPlayable, openDeleteDialog, runPrimary } from "./views/common.js";
import { filteredGroups, mainVersion, renderLibrary, seriesHref } from "./views/library.js";
import { renderMissing, renderSeries, seriesUi, theaterHref } from "./views/series.js";
import { renderSettings } from "./views/settings.js";
import { openTheater } from "./views/theater.js";
import { primaryAction } from "./status.js";

const FALLBACK_POLL_MS = 15000; // seulement si le flux d'événements est coupé
const HEALTH_MS = 60000;

const state = {
  health: null,
  settings: null,
  library: null,
  libraryEtag: null,
  details: new Map(), // series_key -> { data, version }
  jobs: { active: [], history: [] },
  progress: {}, // job_id -> dernier événement progress
  logs: [], // derniers messages du moteur
  live: false,
  unreachable: false,
  query: "",
  selection: new Set(), // ref des séries sélectionnées dans la bibliothèque
  selectionAnchor: null,
  seriesUi: new Map(), // series_key -> état d'interface de la fiche
};

let view = { name: null, key: null };
let theater = null; // { target, key, handle }
let baseTitle = "ShortDramaGen";
const scrolls = new Map();
const main = document.getElementById("contenu");
const drawerUi = { confirmCancel: null, logOpen: false, setConfirm: null, setLogOpen: null };
const milestones = new Map(); // job_id -> dernier palier annoncé

// --- routeur -------------------------------------------------------------------------------------

function parseRoute() {
  const raw = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query);
  if (parts[0] === "serie" && parts[1]) {
    return { name: "series", bookId: parts[1], v: parts[2] || "vo", play: parts[3] === "lire" ? parts[4] || null : null, params };
  }
  if (parts[0] === "reglages") return { name: "settings", section: parts[1] || "general", params };
  if (parts[0] === "activite") return { name: "activity", params };
  return { name: "library", params };
}

function findVersion(bookId, v) {
  const group = state.library?.groups.find((g) => g.ref === bookId);
  if (!group) return {};
  const version = v === "vo"
    ? group.versions.find((x) => x.is_original) || group.versions[0]
    : group.versions.find((x) => !x.is_original && x.lang === v) || group.versions.find((x) => x.lang === v);
  return { group, version };
}

function versionOf(key) {
  for (const group of state.library?.groups || []) {
    const version = group.versions.find((v) => v.series_key === key);
    if (version) return { group, version };
  }
  return null;
}

// --- contexte partagé par les vues --------------------------------------------------------------

const ctx = {
  state,
  go(hash) {
    location.hash = hash;
  },
  goSeries(key, play, anchor) {
    const found = versionOf(key);
    if (!found) return;
    const base = seriesHref(found.group, found.version);
    location.hash = play ? `${base}/lire/${play}` : base;
    if (anchor) setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" }), 400);
  },
  async watch(version) {
    let detail = state.details.get(version.series_key)?.data;
    if (!detail) detail = await loadDetail(version.series_key).catch(() => null);
    const n = firstPlayable(detail);
    if (n) ctx.goSeries(version.series_key, n);
    else ctx.goSeries(version.series_key);
  },
  openAdd(input = "", { lang = null } = {}) {
    closeLayer();
    return openAddDialog(ctx, { input, lang });
  },
  afterAdd() {
    const omni = document.getElementById("recherche");
    if (omni) {
      omni.value = "";
      renderOmniChip();
      omni.focus();
    }
  },
  openDrawer: () => setDrawer(true),
  closeDrawer: () => setDrawer(false),
  openHelp,
  refresh: (force) => refresh(force),
  rerender: () => render(true),
  setParams: setLibraryParams,
  toggleSelect(bookId, shift) {
    const route = parseRoute();
    const { shown } = filteredGroups(state.library, route.params, state.query);
    const ids = shown.map((g) => g.ref);
    if (shift && state.selectionAnchor && ids.includes(state.selectionAnchor)) {
      const [a, b] = [ids.indexOf(state.selectionAnchor), ids.indexOf(bookId)].sort((x, y) => x - y);
      ids.slice(a, b + 1).forEach((id) => state.selection.add(id));
    } else if (state.selection.has(bookId)) {
      state.selection.delete(bookId);
    } else {
      state.selection.add(bookId);
    }
    state.selectionAnchor = bookId;
    render(true);
  },
  clearSelection() {
    state.selection.clear();
    render(true);
  },
  onJob(job) {
    state.jobs = applyJobEvent(state.jobs, { op: job.removed ? "removed" : "updated", job });
    updateActivity();
    renderDrawer();
    scheduleRefresh();
  },
  onSettings(settings) {
    state.settings = settings;
    applyTheme();
    scheduleRefresh();
    if (view.name === "settings") render(true);
  },
  onHealth(health) {
    state.health = { ...(state.health || {}), ...health };
    renderHealthDot();
    updateBanner();
    if (view.name === "settings") render(true);
  },
  versionOf,
  seriesHrefFor(key) {
    const found = versionOf(key);
    return found ? seriesHref(found.group, found.version) : null;
  },
  theaterHrefFor(key, target) {
    const found = versionOf(key);
    return found ? theaterHref(found.group, found.version, target) : "#/";
  },
  firstPlayable(key) {
    return firstPlayable(state.details.get(key)?.data);
  },
  stopPlayer: () => closeTheater(),
  quit() {
    openDialog({
      title: "Quitter ShortDramaGen ?",
      size: "sm",
      content: () => h("p", { text: "Le serveur s'arrête. Les téléchargements en cours reprendront au prochain lancement de sdg ui." }),
      footer: (d) => [
        h("button", { class: "btn btn-secondary", type: "button", "data-autofocus": true, onclick: () => d.close(), text: "Annuler" }),
        h("button", { class: "btn btn-danger", type: "button", onclick: async () => { d.close(); await ctx.act.shutdown(); }, text: "Quitter" }),
      ],
    });
  },
};
ctx.act = makeActions(ctx);

// --- données --------------------------------------------------------------------------------------

async function loadLibrary() {
  try {
    const res = await get("/api/library", { etag: state.libraryEtag });
    setReachable(true);
    if (res.status === 304) return false;
    state.library = res.data;
    state.libraryEtag = res.etag;
    const known = new Set(res.data.groups.map((g) => g.ref));
    for (const id of [...state.selection]) if (!known.has(id)) state.selection.delete(id);
    return true;
  } catch (err) {
    if (err.code === "unreachable") setReachable(false);
    return false;
  }
}

async function loadDetail(key, force = false) {
  const cached = state.details.get(key);
  if (cached && !force && cached.version === state.libraryEtag) return cached.data;
  const res = await get(`/api/series/${encodeURIComponent(key)}`);
  state.details.set(key, { data: res.data, version: state.libraryEtag });
  return res.data;
}

async function loadHealth() {
  try {
    const [health, settings] = await Promise.all([get("/api/health"), get("/api/settings")]);
    state.health = health.data;
    state.settings = settings.data;
    applyTheme();
    renderHealthDot();
    updateBanner();
    setReachable(true);
  } catch (err) {
    if (err.code === "unreachable") setReachable(false);
  }
}

let polling = false;
async function refresh(force = false) {
  if (polling) {
    scheduleRefresh();
    return;
  }
  polling = true;
  try {
    const changed = await loadLibrary();
    if (changed || force) {
      state.details.clear();
      if (!theater) await render(true);
      renderDrawer();
    }
  } finally {
    polling = false;
  }
}

let refreshTimer = null;
function scheduleRefresh(delay = 300) {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refresh(), delay);
}

// --- coquille ---------------------------------------------------------------------------------------

function applyTheme() {
  const theme = state.settings?.theme || "dark";
  const dark = theme === "system" ? matchMedia("(prefers-color-scheme: dark)").matches : theme !== "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function renderOmniChip() {
  const omni = document.getElementById("recherche");
  const chip = document.getElementById("omni-chip");
  const d = detect(omni.value);
  const link = d.kind === "id" || d.kind === "link" || d.kind === "batch";
  chip.hidden = !link;
  if (d.kind === "batch") chip.textContent = `${d.links.filter((l) => l.kind === "id" || l.kind === "link").length} liens · Entrée`;
  else if (link) chip.textContent = `${linkLabel(d)} · Entrée`;
  omni.closest(".field").classList.toggle("is-error", d.kind === "invalid");
  document.getElementById("omni-aide").textContent = d.kind === "invalid" ? "Ce lien n'est pas reconnu : colle le lien d'une série (DramaBox, GoodShort) ou un n° de série." : "";
  return d;
}

function buildShell() {
  const bar = document.getElementById("topbar");
  const omni = h("input", {
    id: "recherche", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder: "Chercher une série ou coller un lien", "aria-label": "Chercher une série ou coller le lien d'une série",
    "aria-keyshortcuts": "Control+K", "aria-describedby": "omni-aide",
  });
  omni.addEventListener("input", () => {
    const d = renderOmniChip();
    if (d.kind === "text" || d.kind === "empty") {
      if (parseRoute().name !== "library") history.pushState(null, "", "#/");
      setLibraryParams({ q: omni.value });
      omni.focus();
    }
  });
  omni.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const d = detect(omni.value);
      if (d.kind === "id" || d.kind === "link" || d.kind === "batch") {
        e.preventDefault(); // sinon l'appui atteint le bouton ciblé du dialogue et le ferme aussitôt
        ctx.openAdd(omni.value);
      }
    } else if (e.key === "Escape" && omni.value) {
      e.stopPropagation();
      omni.value = "";
      renderOmniChip();
      setLibraryParams({ q: "" });
    }
  });
  omni.addEventListener("paste", () => setTimeout(() => {
    const d = renderOmniChip();
    if (d.kind === "id" || d.kind === "link" || d.kind === "batch") ctx.openAdd(omni.value);
  }, 0));

  const addButton = h("button", { class: "btn btn-secondary add-btn", type: "button", title: "Ajouter une série (A)", onclick: () => ctx.openAdd() }, icon("plus"), h("span", { text: "Ajouter" }));
  const activityButton = h("button", { class: "btn-icon", type: "button", id: "activite-btn", "aria-label": "Activité (T)", title: "Activité (T)", "aria-expanded": "false", "aria-controls": "tiroir", onclick: () => setDrawer() }, icon("health", { size: 20 }), h("span", { class: "activity-dot", id: "activite-dot", hidden: true }));
  const pill = h("button", { class: "pill", id: "activite", type: "button", hidden: true, "aria-controls": "tiroir", onclick: () => setDrawer() });
  const settingsLink = h("a", { class: "btn-icon", href: "#/reglages/general", id: "reglages-btn", "aria-label": "Réglages", title: "Réglages" }, icon("settings", { size: 20 }), h("span", { class: "health-dot", id: "sante-dot", hidden: true }));
  append(bar, [
    h("a", { class: "logo", href: "#/" }, h("img", { src: "/icon.svg", alt: "" }), h("span", { text: "ShortDramaGen" })),
    h("div", { class: "omni" },
      h("label", { class: "field" }, icon("search"), omni, h("span", { class: "detect-chip", id: "omni-chip", hidden: true }), h("kbd", { class: "kbd omni-kbd", text: "Ctrl K" })),
      h("p", { class: "omni-help", id: "omni-aide", "aria-live": "polite" })),
    addButton,
    h("div", { class: "topbar-end" }, pill, activityButton, settingsLink),
  ]);

  // Tiroir Activité
  const drawer = h("aside", { class: "drawer", id: "tiroir", hidden: true, "aria-labelledby": "titre-activite" },
    h("div", { class: "drawer-head" },
      h("h2", { id: "titre-activite", text: "Activité" }),
      h("button", { class: "btn-icon btn-icon-sm", type: "button", id: "tiroir-epingle", "aria-pressed": "false", title: "Épingler le tiroir", "aria-label": "Épingler le tiroir", onclick: togglePin }, icon("pin")),
      h("button", { class: "btn-icon btn-icon-sm", type: "button", "aria-label": "Fermer (Échap)", title: "Fermer (Échap)", onclick: () => setDrawer(false) }, icon("close"))),
    h("div", { class: "drawer-body", id: "tiroir-contenu" }));
  document.body.append(drawer);

  // Mobile : barre du bas et mini-barre d'activité
  const nav = h("nav", { class: "bottom-nav", "aria-label": "Navigation principale" },
    h("a", { href: "#/", class: "bottom-item", id: "nav-bibli" }, icon("home", { size: 24 }), h("span", { text: "Bibliothèque" })),
    h("button", { class: "bottom-item", type: "button", onclick: () => ctx.openAdd() }, icon("plus", { size: 24 }), h("span", { text: "Ajouter" })),
    h("button", { class: "bottom-item", type: "button", id: "nav-activite", onclick: () => setDrawer() }, icon("health", { size: 24 }), h("span", { text: "Activité" }), h("span", { class: "bottom-badge", id: "nav-badge", hidden: true })),
    h("a", { href: "#/reglages/general", class: "bottom-item", id: "nav-reglages" }, icon("settings", { size: 24 }), h("span", { text: "Réglages" })));
  const mini = h("button", { class: "mini-bar", type: "button", id: "mini-barre", hidden: true, onclick: () => setDrawer(true) });
  document.body.append(mini, nav);
}

function renderHealthDot() {
  const hl = state.health;
  const dot = document.getElementById("sante-dot");
  if (!hl || !dot) return;
  const problem = !hl.downloads_dir_ok ? "danger" : hl.ffmpeg && !hl.ffmpeg.found ? "warning" : hl.online === false ? "warning" : null;
  dot.hidden = !problem;
  dot.className = `health-dot${problem ? ` is-${problem}` : ""}`;
}

// --- bandeaux (un seul à la fois, par priorité) -------------------------------------------------------

let otherTab = false;
let bannerDismissed = new Set();

function updateBanner() {
  const zone = document.getElementById("banners");
  clear(zone);
  const banner = (tone, text, actions = [], id = null) => {
    if (id && bannerDismissed.has(id)) return false;
    zone.append(h("div", { class: `banner banner-${tone}`, role: tone === "danger" ? "alert" : "status" },
      icon(tone === "danger" ? "alert" : tone === "warning" ? "alert" : "info", { size: 20 }), h("span", { text }),
      h("div", { class: "btn-row" }, actions, id ? h("button", { class: "btn-icon btn-icon-sm", type: "button", "aria-label": "Masquer", onclick: () => { bannerDismissed.add(id); updateBanner(); } }, icon("close")) : null)));
    return true;
  };
  if (state.unreachable) {
    banner("danger", state.stopped ? "ShortDramaGen s'est arrêté. Relance sdg ui pour continuer ; les téléchargements reprendront là où ils en étaient." : "Le moteur ne répond plus : la fenêtre de sdg ui a peut-être été fermée. On essaie de se reconnecter…",
      [h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => refresh(true), text: "Réessayer maintenant" })]);
    return;
  }
  const disk = [...state.jobs.active, ...state.jobs.history.slice(0, 3)].find((j) => j.error?.code === "disk_space" && j.status === "failed");
  if (disk && banner("danger", "Téléchargements arrêtés : disque plein. Libère de la place puis reprends.", [
    h("a", { class: "btn btn-sm btn-secondary", href: "#/reglages/stockage", text: "Voir le stockage" }),
    h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.jobCommand(disk, "resume"), text: "Reprendre" }),
  ], `disk-${disk.id}`)) return;
  const started = state.health?.started_at;
  const resumed = started ? state.jobs.active.filter((j) => j.kind === "fetch" && ["running", "queued"].includes(j.status) && j.created_at < started) : [];
  if (resumed.length && banner("info", `Reprise de ${resumed.length} téléchargement${resumed.length > 1 ? "s" : ""} interrompu${resumed.length > 1 ? "s" : ""}.`, [
    h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => resumed.forEach((j) => ctx.act.jobCommand(j, "pause")), text: "Mettre en pause" }),
    h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => setDrawer(true), text: "Voir" }),
  ], `resume-${started}`)) return;
  if (state.health?.online === false && banner("info", "Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls.")) return;
  if (otherTab) banner("info", "ShortDramaGen est déjà ouvert dans un autre onglet.", [], "tab");
}

function setReachable(ok) {
  if (ok === !state.unreachable) return;
  state.unreachable = !ok;
  if (ok) {
    state.stopped = false;
    announce("Moteur de nouveau joignable.");
  }
  updateBanner();
}

// --- tiroir Activité -----------------------------------------------------------------------------------------

function isMobile() {
  return matchMedia("(max-width: 599px)").matches;
}

function setDrawer(open) {
  const drawer = document.getElementById("tiroir");
  const next = open === undefined ? drawer.hidden : open;
  if (next === !drawer.hidden) {
    if (next) drawer.querySelector("button")?.focus();
    return;
  }
  drawer.hidden = !next;
  document.body.classList.toggle("has-drawer", next);
  for (const id of ["activite-btn", "activite"]) document.getElementById(id)?.setAttribute("aria-expanded", String(next));
  if (next) {
    renderDrawer();
    drawer.querySelector(".drawer-head button")?.focus();
    for (const job of state.jobs.active) if (job.series_key && !state.details.has(job.series_key)) loadDetail(job.series_key).then(renderDrawer).catch(() => {});
  } else {
    document.getElementById("activite-btn")?.focus();
    if (parseRoute().name === "activity") history.replaceState(null, "", "#/");
  }
}

function togglePin() {
  const pinned = document.body.classList.toggle("drawer-pinned");
  document.getElementById("tiroir-epingle").setAttribute("aria-pressed", String(pinned));
  try {
    localStorage.setItem("sdg.tiroir.epingle", pinned ? "1" : "0");
  } catch {
    /* confort seulement */
  }
}

let drawerFrame = null;
function renderDrawer() {
  const drawer = document.getElementById("tiroir");
  if (!drawer || drawer.hidden || drawerFrame) return;
  drawerFrame = requestAnimationFrame(() => {
    drawerFrame = null;
    const body = document.getElementById("tiroir-contenu");
    const focusId = document.activeElement && body.contains(document.activeElement) ? document.activeElement.textContent : null;
    renderActivity(body, ctx, drawerUi);
    if (focusId) [...body.querySelectorAll("button, a")].find((b) => b.textContent === focusId)?.focus();
  });
}
drawerUi.setConfirm = (id) => {
  drawerUi.confirmCancel = id;
  renderDrawer();
};
drawerUi.setLogOpen = (open) => {
  drawerUi.logOpen = open;
};

// --- activité : pilule, titre de l'onglet, mini-barre, annonces ---------------------------------------------------

function setTitle(title) {
  baseTitle = title;
  updateActivity();
}

function updateActivity() {
  const info = activity(state.jobs, state.progress);
  const pill = document.getElementById("activite");
  const button = document.getElementById("activite-btn");
  if (pill) {
    renderPill(pill, info, () => null);
    if (button) button.hidden = Boolean(info);
  }
  const running = info && info.job?.status === "running" && info.job.kind === "fetch" && state.progress[info.job.id];
  const e = running?.episodes;
  document.title = e ? `(${(e.done || 0) + (e.skipped || 0)}/${e.total}) ${baseTitle}` : baseTitle;

  const unhandled = state.jobs.history.filter((j) => j.status === "failed" || Object.keys(j.result?.failed || {}).length).length;
  const dot = document.getElementById("activite-dot");
  if (dot) dot.hidden = !unhandled;
  const badge = document.getElementById("nav-badge");
  const count = state.jobs.active.filter((j) => ["running", "queued"].includes(j.status)).length;
  if (badge) {
    badge.hidden = !count;
    badge.textContent = String(count);
  }
  const mini = document.getElementById("mini-barre");
  if (mini) {
    mini.hidden = !info || !info.job;
    clear(mini);
    if (info?.job) {
      append(mini, [
        h("span", { class: "mini-cover" }, info.job.cover_url ? h("img", { src: info.job.cover_url, alt: "" }) : null),
        h("span", { class: "mini-text num", text: `${info.job.title || ""} · ${info.text}` }),
      ]);
    }
  }
  announceMilestones();
}

function announceMilestones() {
  const mode = state.settings?.sr_announcements || "milestones";
  if (mode !== "milestones") return;
  for (const job of state.jobs.active) {
    const p = state.progress[job.id];
    if (!p?.bytes_total || job.kind !== "fetch") continue;
    const pct = (p.bytes_done / p.bytes_total) * 100;
    const step = [75, 50, 25].find((s) => pct >= s) || 0;
    if (step > (milestones.get(job.id) || 0)) {
      milestones.set(job.id, step);
      announce(`${job.title || "Téléchargement"} : ${step} %.`);
    }
  }
}

// Tuiles et affiches en cours : mises à jour sans reconstruire la page.
function updateLive(progress) {
  const job = state.jobs.active.find((j) => j.id === progress.job_id);
  if (!job) return;
  if (view.name === "series" && job.series_key === view.key && progress.episodes?.active) {
    const active = new Set(progress.episodes.active.map((a) => a.n));
    for (const tile of main.querySelectorAll(".tile[data-live]")) {
      if (!active.has(Number(tile.dataset.n))) {
        tile.dataset.status = tile.dataset.was;
        delete tile.dataset.live;
      }
    }
    for (const { n, bytes: done, total } of progress.episodes.active) {
      const tile = main.querySelector(`.tile[data-n="${n}"]`);
      if (!tile) continue;
      if (!tile.dataset.live) {
        tile.dataset.was = tile.dataset.status === "downloading" ? "queued" : tile.dataset.status;
        tile.dataset.live = "1";
      }
      tile.dataset.status = "downloading";
      tile.style.setProperty("--p", total ? Math.min(1, done / total).toFixed(3) : "0");
    }
  }
  if (view.name === "series" && job.series_key === view.key && job.kind === "film") render(true);
  if (view.name === "library" && job.ref && progress.episodes) {
    const cover = main.querySelector(`.poster[data-book="${CSS.escape(job.ref)}"] .poster-cover.is-coloring`);
    const e = progress.episodes;
    if (cover && e.total) cover.style.setProperty("--p", ((e.done + e.skipped) / e.total).toFixed(3));
  }
}

// --- temps réel (SSE) -----------------------------------------------------------------------------------------------

function startEvents() {
  connectEvents({
    open() {
      state.live = true;
      setReachable(true);
    },
    lost() {
      state.live = false;
      setReachable(false);
    },
    snapshot(data) {
      state.jobs = data.jobs;
      state.health = data.health;
      renderHealthDot();
      updateActivity();
      updateBanner();
      renderDrawer();
      if (data.library_version !== state.library?.version) scheduleRefresh(0);
    },
    job(data) {
      const before = [...state.jobs.active, ...state.jobs.history].find((j) => j.id === data.job.id);
      state.jobs = applyJobEvent(state.jobs, data);
      if (!["running", "queued"].includes(data.job.status)) delete state.progress[data.job.id];
      if (before && before.status !== data.job.status) jobFinished(before, data.job);
      updateActivity();
      updateBanner();
      renderDrawer();
      scheduleRefresh();
    },
    progress(data) {
      state.progress[data.job_id] = data;
      updateActivity();
      updateLive(data);
      renderDrawer();
    },
    // Un épisode vient d'aboutir : sa tuile change tout de suite, le reste suit au prochain rafraîchissement.
    episode(data) {
      if (view.name !== "series" || view.key !== data.series_key || !["done", "failed", "unavailable"].includes(data.status)) return;
      const tile = main.querySelector(`.tile[data-n="${data.n}"]`);
      if (!tile) return;
      delete tile.dataset.live;
      tile.dataset.status = data.status;
      tile.style.removeProperty("--p");
    },
    log(data) {
      state.logs.push(data);
      if (state.logs.length > 300) state.logs.splice(0, state.logs.length - 300);
      renderDrawer();
    },
    library: () => scheduleRefresh(),
    health(data) {
      ctx.onHealth(data);
    },
    settings(data) {
      state.settings = data.settings;
      applyTheme();
      scheduleRefresh();
    },
    server(data) {
      if (data.op === "shutdown") {
        state.stopped = true;
        setReachable(false);
      }
    },
  });
}

function jobFinished(before, job) {
  const drawerOpen = !document.getElementById("tiroir").hidden;
  const onPage = view.name === "series" && view.key === job.series_key;
  const name = job.kind === "film" ? `Film · ${job.result?.file || job.title}` : `${job.title || "Série"}`;
  if (job.status === "done") {
    const failed = Object.keys(job.result?.failed || {});
    const text = job.kind === "film" ? `${name} : prêt.` : failed.length ? `${name} : terminé avec ${failed.length} problème${failed.length > 1 ? "s" : ""}.` : `${name} : terminé.`;
    announce(text);
    if (!drawerOpen && !onPage) {
      toast({ tone: failed.length ? "warning" : "success", text, actions: job.series_key ? [{ label: failed.length ? "Réparer" : "Voir", onClick: () => (failed.length ? ctx.act.retry(job.series_key) : ctx.goSeries(job.series_key)) }] : [] });
    }
  } else if (job.status === "failed") {
    toast({ tone: "error", text: `${name} : ${job.error?.message || "échec."}`, actions: [{ label: "Voir", onClick: () => setDrawer(true) }] });
  } else if (job.status === "interrupted" && job.reason === "offline") {
    announce("Hors ligne : les téléchargements reprendront au retour de la connexion.");
  }
}

// --- rendu ------------------------------------------------------------------------------------------------------------

function focusHeading() {
  const target = main.querySelector("[data-autofocus]");
  (target || main).focus({ preventScroll: true });
}

// Garde l'élément ciblé à travers un nouveau rendu (même rôle, même série ou même épisode).
function focusKey() {
  const el = document.activeElement;
  if (!el || !main.contains(el) || el === main) return null;
  const tile = el.closest(".tile");
  if (tile) return `.tile[data-n="${tile.dataset.n}"]`;
  const poster = el.closest(".poster");
  if (poster) return `.poster[data-book="${CSS.escape(poster.dataset.book)}"] ${el.classList.contains("poster-link") ? ".poster-link" : el.classList.contains("poster-main") ? ".poster-main" : el.classList.contains("poster-more") ? ".poster-more" : ".poster-link"}`;
  if (el.id) return `#${CSS.escape(el.id)}`;
  return null;
}

async function render(soft = false) {
  const route = parseRoute();
  if (view.name === "library") scrolls.set("library", scrollY);
  closeLayer();
  const keep = soft ? focusKey() : null;
  const restore = () => {
    if (keep) main.querySelector(keep)?.focus({ preventScroll: true });
  };

  if (route.name === "activity") {
    setDrawer(true);
    if (view.name) return;
  }
  if (route.name === "library" || route.name === "activity") {
    closeTheater();
    const same = view.name === "library";
    const y = scrollY;
    clear(main);
    renderLibrary(main, ctx, { ...route, params: route.name === "activity" ? new URLSearchParams() : route.params });
    view = { name: "library", key: null };
    setTitle("Bibliothèque · ShortDramaGen");
    if (!same) {
      scrollTo(0, scrolls.get("library") || 0);
      if (!soft) focusHeading();
    } else {
      scrollTo(0, y);
      restore();
    }
    return;
  }
  if (route.name === "settings") {
    closeTheater();
    const y = scrollY;
    const same = view.name === "settings" && view.key === route.section;
    clear(main);
    renderSettings(main, ctx, route.section);
    view = { name: "settings", key: route.section };
    setTitle("Réglages · ShortDramaGen");
    if (same) {
      scrollTo(0, y);
      restore();
    } else {
      scrollTo(0, 0);
      focusHeading();
    }
    return;
  }

  // Fiche série (+ Théâtre éventuel)
  if (!state.library) {
    clear(main);
    renderLibrary(main, ctx, { name: "library", params: new URLSearchParams() });
    return;
  }
  const { group, version } = findVersion(route.bookId, route.v);
  if (!group || !version) {
    closeTheater();
    clear(main);
    renderMissing(main, "Cette série n'est pas (ou plus) dans ta bibliothèque.");
    view = { name: "missing", key: null };
    focusHeading();
    return;
  }
  let detail;
  try {
    detail = await loadDetail(version.series_key);
  } catch (err) {
    clear(main);
    renderMissing(main, err.message);
    view = { name: "missing", key: null };
    return;
  }
  if (parseRoute().name !== "series") return; // l'utilisateur est reparti entre-temps

  const sameView = view.name === "series" && view.key === version.series_key;
  const rerender = !sameView || soft === true || (!route.play && !theater);
  if (rerender) {
    const y = sameView ? scrollY : 0;
    if (!state.seriesUi.has(version.series_key)) state.seriesUi.set(version.series_key, seriesUi(ctx, version.series_key));
    clear(main);
    renderSeries(main, ctx, { group, detail, ui: state.seriesUi.get(version.series_key) });
    scrollTo(0, y);
    if (!sameView) {
      view = { name: "series", key: version.series_key };
      setTitle(`${detail.title} · ShortDramaGen`);
      if (!route.play) focusHeading();
    } else {
      restore();
    }
  }
  if (route.play) showTheater(group, version, detail, route.play);
  else closeTheater(true);
}

function showTheater(group, version, detail, target) {
  if (theater && theater.target === target && theater.key === version.series_key) return;
  closeTheater();
  const back = seriesHref(group, version);
  const handle = openTheater({
    group,
    detail,
    target,
    navigate: (n) => location.replace(`${back}/lire/${n}`),
    close: () => { location.hash = back; },
    openExternal: (what) => ctx.act.open(version.series_key, what === "film" ? "film" : "episode", what === "film" ? { play: true } : { episode: Number(what), play: true }),
    retry: (n) => ctx.act.retry(version.series_key, { episodes: [n] }, `Épisode ${n} relancé`),
  });
  document.body.append(handle.el);
  main.inert = true;
  document.getElementById("topbar").inert = true;
  theater = { target, key: version.series_key, handle };
  setTitle(`${target === "film" ? "Film" : `Épisode ${target}`} · ${detail.title}`);
  handle.focus();
}

function closeTheater(restoreFocus = false) {
  if (!theater) return;
  const { target } = theater;
  theater.handle.destroy();
  theater = null;
  main.inert = false;
  document.getElementById("topbar").inert = false;
  if (restoreFocus) {
    const tile = target !== "film" && main.querySelector(`.tile[data-n="${CSS.escape(String(target))}"]`);
    (tile || main.querySelector("[data-autofocus]") || main).focus({ preventScroll: Boolean(tile) });
  }
}

function setLibraryParams(changes) {
  const route = parseRoute();
  const params = new URLSearchParams(route.name === "library" ? route.params : undefined);
  for (const [key, value] of Object.entries(changes)) {
    if (key === "q") {
      state.query = value || "";
      const omni = document.getElementById("recherche");
      if (omni && omni.value !== state.query && document.activeElement !== omni) omni.value = state.query;
    }
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  history.replaceState(null, "", `#/${query ? `?${query}` : ""}`);
  render(true);
}

// --- raccourcis, collage, glisser-déposer ------------------------------------------------------------------------------

const SHORTCUTS = [
  ["Global", "Ctrl+K ou /", "Chercher, ou coller un lien"],
  ["Global", "Ctrl+V", "Ajouter la série du lien copié (hors d'un champ)"],
  ["Global", "A", "Ajouter une série"],
  ["Global", "T", "Ouvrir ou fermer l'activité"],
  ["Global", "?", "Cette aide"],
  ["Global", "Échap", "Fermer, ou revenir à la bibliothèque"],
  ["Carte ciblée", "Entrée", "Ouvrir la fiche"],
  ["Carte ciblée", "L · O · P · Suppr", "Regarder · Dossier · Pause/reprise · Supprimer"],
  ["Bibliothèque", "Ctrl+A", "Tout sélectionner (dans le résultat filtré)"],
  ["Épisodes", "Flèches · Début · Fin", "Se déplacer dans la grille"],
  ["Épisodes", "Espace · Maj+flèches · Ctrl+clic", "Sélectionner, étendre"],
  ["Dialogue d'ajout", "Entrée · Ctrl+Entrée", "Télécharger · Télécharger puis créer le film"],
  ["Théâtre", "Espace ou K · ←/→ · Maj+←/→", "Lecture · ±5 s · épisode ou chapitre"],
  ["Théâtre", "F · M · Échap", "Plein écran · muet · fermer"],
];

function openHelp() {
  openDialog({
    title: "Raccourcis clavier",
    size: "md",
    content: () => h("table", { class: "table shortcuts" },
      h("thead", {}, h("tr", {}, h("th", { text: "Où" }), h("th", { text: "Touche" }), h("th", { text: "Action" }))),
      h("tbody", {}, SHORTCUTS.map(([where, key, what]) => h("tr", {}, h("td", { text: where }), h("td", { class: "keys" }, key.split(" · ").map((k) => h("kbd", { class: "kbd", text: k }))), h("td", { text: what }))))),
    footer: (d) => [h("a", { class: "btn btn-ghost", href: "#/reglages/clavier", onclick: () => d.close(), text: "Réglages du clavier" }), h("button", { class: "btn btn-secondary", type: "button", "data-autofocus": true, onclick: () => d.close(), text: "Fermer" })],
  });
}

function typing(target) {
  return target instanceof HTMLElement && (target.closest("input, textarea, select, [contenteditable]") !== null);
}

function shortcuts() {
  document.addEventListener("keydown", (e) => {
    if (theater || document.querySelector("dialog[open]")) return;
    const nav = state.settings?.nav_shortcuts !== false;
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      document.getElementById("recherche")?.focus();
      return;
    }
    if (e.key === "Escape") {
      if (!document.getElementById("tiroir").hidden && !document.body.classList.contains("drawer-pinned")) setDrawer(false);
      else if (state.selection.size) ctx.clearSelection();
      else if (view.name === "series" && state.seriesUi.get(view.key)?.selection.size) state.seriesUi.get(view.key).select([], true);
      else if ((view.name === "series" || view.name === "settings") && !typing(e.target)) location.hash = "#/";
      return;
    }
    if (typing(e.target) || e.ctrlKey && e.key !== "a" || e.altKey || e.metaKey) return;
    if ((e.ctrlKey && e.key === "a") && view.name === "library") {
      e.preventDefault();
      const { shown } = filteredGroups(state.library, parseRoute().params, state.query);
      shown.forEach((g) => state.selection.add(g.ref));
      render(true);
      return;
    }
    const poster = e.target instanceof HTMLElement ? e.target.closest(".poster") : null;
    if (poster) {
      const group = state.library?.groups.find((g) => g.ref === poster.dataset.book);
      const version = group && mainVersion(group);
      if (version) {
        const key = e.key.toLowerCase();
        if (key === "l") return void ctx.watch(version);
        if (key === "o") return void ctx.act.open(version.series_key, "folder");
        if (key === "p" && version.job) return void ctx.act.jobCommand(version.job, ["paused", "interrupted"].includes(version.job.status) ? "resume" : "pause");
        if (e.key === "Delete") return void openDeleteDialog(ctx, [version]);
        if (state.settings?.action_shortcuts) {
          const action = primaryAction(version);
          if ((key === "r" && action.id === "repair") || (key === "c" && action.id === "complete") || (key === "f" && action.id === "film")) return void runPrimary(ctx, version, action);
        }
      }
    }
    if (!nav) return;
    if (e.key === "/") {
      e.preventDefault();
      document.getElementById("recherche")?.focus();
    } else if (e.key === "a" || e.key === "A") {
      e.preventDefault();
      ctx.openAdd();
    } else if (e.key === "t" || e.key === "T") {
      e.preventDefault();
      setDrawer();
    } else if (e.key === "?") {
      e.preventDefault();
      openHelp();
    }
  });

  // Ctrl+V n'importe où (hors d'un champ) : un lien de série ouvre directement l'aperçu.
  document.addEventListener("paste", (e) => {
    if (typing(e.target) || document.querySelector("dialog[open]")) return;
    const text = e.clipboardData?.getData("text") || "";
    const d = detect(text);
    if (d.kind === "id" || d.kind === "link" || d.kind === "batch") {
      e.preventDefault();
      ctx.openAdd(text);
    }
  });

  // Glisser-déposer d'un lien depuis une autre page.
  document.addEventListener("dragover", (e) => {
    if ([...(e.dataTransfer?.types || [])].some((t) => t === "text/uri-list" || t === "text/plain")) e.preventDefault();
  });
  document.addEventListener("drop", (e) => {
    const text = e.dataTransfer?.getData("text/uri-list") || e.dataTransfer?.getData("text/plain") || "";
    const d = detect(text);
    if (d.kind === "id" || d.kind === "link" || d.kind === "batch") {
      e.preventDefault();
      ctx.openAdd(text.trim());
    }
  });
}

// Un seul onglet à la fois est conseillé (limite de connexions du navigateur).
function watchOtherTabs() {
  if (!("BroadcastChannel" in window)) return;
  const channel = new BroadcastChannel("shortdramagen");
  channel.onmessage = (e) => {
    if (e.data === "hello") channel.postMessage("here");
    if (e.data === "here" || e.data === "hello") {
      otherTab = true;
      updateBanner();
    }
  };
  channel.postMessage("hello");
}

// --- démarrage ------------------------------------------------------------------------------------------------------------

async function start() {
  buildShell();
  shortcuts();
  try {
    if (localStorage.getItem("sdg.tiroir.epingle") === "1") {
      document.body.classList.add("drawer-pinned");
      document.getElementById("tiroir-epingle").setAttribute("aria-pressed", "true");
    }
  } catch {
    /* confort seulement */
  }
  state.query = parseRoute().params.get("q") || "";
  document.getElementById("recherche").value = state.query;
  render();
  await Promise.all([loadHealth(), loadLibrary()]);
  await render(parseRoute().name === "library");
  const count = state.library?.stats?.groups ?? 0;
  if (state.library) announce(`Bibliothèque chargée : ${count} série${count > 1 ? "s" : ""}.`);
  addEventListener("hashchange", () => render());
  startEvents();
  setInterval(() => { if (!state.live && document.visibilityState === "visible") refresh(); }, FALLBACK_POLL_MS);
  setInterval(() => { if (document.visibilityState === "visible") loadHealth(); }, HEALTH_MS);
  addEventListener("focus", () => refresh());
  watchOtherTabs();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  if (isMobile()) document.body.classList.add("is-mobile");
}

start();

// Utilitaires exposés aux vues qui n'importent pas main.js directement.
export { versionShort };
