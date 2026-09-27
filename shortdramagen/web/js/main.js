// Point d'entrée : coquille, routeur par hash, état partagé, rafraîchissement.
//
// Routes (spec §4.1) :
//   #/                                 Bibliothèque   (?f=filtre&q=recherche&tri=…)
//   #/serie/<bookId>/<vo|fr|es…>        Fiche d'une version
//   #/serie/<bookId>/<v>/lire/<n|film>  Théâtre par-dessus la fiche

import { get } from "./api.js";
import { h, icon, clear, announce, codeBox } from "./dom.js";
import { bytes } from "./format.js";
import { activity, applyJobEvent, connectEvents, renderPill } from "./live.js";
import { renderLibrary, seriesHref, mainVersion } from "./views/library.js";
import { renderSeries, renderMissing } from "./views/series.js";
import { openTheater } from "./views/theater.js";

const FALLBACK_POLL_MS = 15000; // seulement si le flux d'événements est coupé
const HEALTH_MS = 60000;

const state = {
  health: null,
  settings: null,
  library: null,
  libraryEtag: null,
  details: new Map(), // series_key -> { data, version }
  unreachable: false,
  query: "",
  selected: new Map(), // series_key -> épisode affiché dans le volet
  jobs: { active: [], history: [] },
  progress: {}, // job_id -> dernier événement progress
  live: false, // flux SSE ouvert
};
let baseTitle = "ShortDramaGen";

let view = { name: null, key: null }; // ce qui est affiché dans <main>
let theater = null; // { target, key, handle }
const scrolls = new Map();
const main = document.getElementById("contenu");

// --- routeur -------------------------------------------------------------------------

function parseRoute() {
  const raw = decodeURIComponent(location.hash.replace(/^#/, "")) || "/";
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query);
  if (parts[0] === "serie" && parts[1]) {
    return { name: "series", bookId: parts[1], v: parts[2] || "vo", play: parts[3] === "lire" ? parts[4] || null : null, params };
  }
  return { name: "library", params };
}

function setLibraryParams(changes, focusSearch = false) {
  const route = parseRoute();
  const params = new URLSearchParams(route.params);
  for (const [key, value] of Object.entries(changes)) {
    if (key === "q") {
      state.query = value || "";
      const search = document.getElementById("recherche");
      if (search && search.value !== state.query) search.value = state.query;
    }
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const query = params.toString();
  history.replaceState(null, "", `#/${query ? `?${query}` : ""}`);
  render(true);
  if (focusSearch) document.getElementById("recherche")?.focus();
}

function findVersion(route) {
  const group = state.library?.groups.find((g) => g.book_id === route.bookId);
  if (!group) return {};
  const version =
    route.v === "vo"
      ? group.versions.find((v) => v.is_original) || group.versions[0]
      : group.versions.find((v) => !v.is_original && v.lang === route.v) || group.versions.find((v) => v.lang === route.v);
  return { group, version };
}

// --- données ---------------------------------------------------------------------------

async function loadLibrary() {
  try {
    const res = await get("/api/library", { etag: state.libraryEtag });
    setReachable(true);
    if (res.status === 304) return false;
    state.library = res.data;
    state.libraryEtag = res.etag;
    return true;
  } catch (err) {
    if (err.code === "unreachable") setReachable(false);
    else showBanner("danger", err.message);
    return false;
  }
}

async function loadDetail(key, force = false) {
  const cached = state.details.get(key);
  if (cached && !force && cached.version === state.library?.version) return cached.data;
  const res = await get(`/api/series/${encodeURIComponent(key)}`);
  state.details.set(key, { data: res.data, version: state.library?.version });
  return res.data;
}

async function loadHealth() {
  try {
    const [health, settings] = await Promise.all([get("/api/health"), get("/api/settings")]);
    state.health = health.data;
    state.settings = settings.data;
    applyTheme();
    renderHealth();
    setReachable(true);
  } catch (err) {
    if (err.code === "unreachable") setReachable(false);
  }
}

// --- coquille --------------------------------------------------------------------------

function applyTheme() {
  const theme = state.settings?.theme || "dark";
  const dark = theme === "system" ? matchMedia("(prefers-color-scheme: dark)").matches : theme !== "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

function buildTopbar() {
  const bar = document.getElementById("topbar");
  const search = h("input", {
    id: "recherche", type: "search", placeholder: "Chercher dans ta bibliothèque", autocomplete: "off", spellcheck: "false",
    "aria-label": "Chercher dans ta bibliothèque", "aria-keyshortcuts": "Control+K",
  });
  search.addEventListener("input", () => {
    if (parseRoute().name !== "library") history.pushState(null, "", "#/");
    setLibraryParams({ q: search.value });
    search.focus();
  });
  const healthButton = h("button", { class: "btn-icon", type: "button", id: "sante-btn", "aria-label": "Santé et dossier", title: "Santé et dossier", "aria-expanded": "false", "aria-controls": "sante" }, icon("health", { size: 20 }), h("span", { class: "health-dot", id: "sante-dot" }));
  const popover = h("div", { class: "popover", id: "sante", hidden: true, role: "dialog", "aria-label": "Santé" });
  healthButton.addEventListener("click", () => {
    popover.hidden = !popover.hidden;
    healthButton.setAttribute("aria-expanded", String(!popover.hidden));
    if (!popover.hidden) loadHealth();
  });
  document.addEventListener("click", (e) => {
    if (!popover.hidden && !popover.contains(e.target) && !healthButton.contains(e.target)) {
      popover.hidden = true;
      healthButton.setAttribute("aria-expanded", "false");
    }
  });
  bar.append(
    h("a", { class: "logo", href: "#/" }, h("img", { src: "/icon.svg", alt: "" }), h("span", { text: "ShortDramaGen" })),
    h("label", { class: "field" }, icon("search"), search),
    h("div", { class: "topbar-end" }, h("a", { class: "pill", id: "activite", hidden: true }), healthButton),
    popover,
  );
}

function renderHealth() {
  const hl = state.health;
  const popover = document.getElementById("sante");
  const dot = document.getElementById("sante-dot");
  if (!hl || !popover) return;
  const ffmpeg = hl.ffmpeg || {};
  const problems = !hl.downloads_dir_ok ? "danger" : !ffmpeg.found ? "warning" : null;
  dot.className = `health-dot${problems ? ` is-${problems}` : ""}`;
  clear(popover);
  const row = (ok, label, value) => h("div", { class: "kv" }, h("dt", {}, ok === null ? "" : icon(ok ? "check" : "alert", { size: 14 }), ` ${label}`), h("dd", { text: value }));
  popover.append(
    h("h2", { class: "overline", text: "Santé" }),
    h(
      "dl",
      {},
      row(hl.downloads_dir_ok, "Dossier", hl.downloads_dir_ok ? "accessible" : "introuvable"),
      row(null, "Espace libre", hl.free_bytes === null ? "—" : bytes(hl.free_bytes)),
      row(ffmpeg.found, "ffmpeg", ffmpeg.found ? `prêt (${ffmpeg.source})` : "absent : nécessaire pour créer un film"),
      row(hl.online === null || hl.online === undefined ? null : hl.online, "Connexion", hl.online === false ? "hors ligne" : hl.online ? "en ligne" : "vérification…"),
      row(null, "Tâches", hl.jobs ? `${hl.jobs.running} en cours · ${hl.jobs.queued} en file` : "—"),
      row(null, "Version", `${hl.version}`),
    ),
    codeBox(hl.downloads_dir, "Copier le chemin du dossier"),
  );
}

let bannerTimer = null;
function showBanner(tone, text, action) {
  const zone = document.getElementById("banners");
  clear(zone);
  if (!text) return;
  zone.append(h("div", { class: `banner banner-${tone}`, role: tone === "danger" ? "alert" : "status" }, icon(tone === "danger" ? "alert" : "info", { size: 20 }), h("span", { text }), action || null));
  clearTimeout(bannerTimer);
}

function setReachable(ok) {
  if (ok && state.unreachable) {
    state.unreachable = false;
    showBanner(null, null);
    announce("Moteur de nouveau joignable.");
  } else if (!ok && !state.unreachable) {
    state.unreachable = true;
    showBanner(
      "danger",
      "Le moteur ne répond plus : la fenêtre de sdg ui a peut-être été fermée. On essaie de se reconnecter…",
      h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => refresh(true), text: "Réessayer maintenant" }),
    );
  }
}

// --- rendu ---------------------------------------------------------------------------------

function focusHeading() {
  const target = main.querySelector("[data-autofocus]");
  (target || main).focus({ preventScroll: true });
}

async function render(soft = false) {
  const route = parseRoute();
  if (view.name === "library") scrolls.set("library", scrollY);

  if (route.name === "library") {
    closeTheater();
    const same = view.name === "library";
    clear(main);
    renderLibrary(main, {
      library: state.library,
      query: state.query,
      params: route.params,
      setParams: setLibraryParams,
      onRetry: () => refresh(true),
    });
    view = { name: "library", key: null };
    setTitle("Bibliothèque · ShortDramaGen");
    if (!same) {
      scrollTo(0, scrolls.get("library") || 0);
      if (!soft) focusHeading();
    }
    return;
  }

  // Fiche série (+ Théâtre éventuel)
  if (!state.library) {
    clear(main);
    renderLibrary(main, { library: null });
    return;
  }
  const { group, version } = findVersion(route);
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
  // Ouvrir, changer ou fermer le Théâtre ne reconstruit pas la fiche (défilement et focus gardés).
  const rerender = !sameView || soft === true || (!route.play && !theater);
  if (rerender) {
    const y = sameView ? scrollY : 0;
    clear(main);
    renderSeries(main, {
      group,
      detail,
      selected: state.selected.get(version.series_key),
      onSelect: (n) => state.selected.set(version.series_key, n),
      openEpisode: (n) => { location.hash = `${seriesHref(group, version)}/lire/${n}`; },
    });
    scrollTo(0, y);
    if (!sameView) {
      view = { name: "series", key: version.series_key };
      setTitle(`${detail.title} · ShortDramaGen`);
      if (!route.play) focusHeading();
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
    navigate: (n) => { location.replace(`${back}/lire/${n}`); },
    close: () => { location.hash = back; },
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

// --- temps réel ---------------------------------------------------------------------------

function setTitle(title) {
  baseTitle = title;
  updateActivity();
}

function jobHref(job) {
  for (const group of state.library?.groups || []) {
    const version = group.versions.find((v) => v.series_key === job.series_key);
    if (version) return seriesHref(group, version);
  }
  return null;
}

function updateActivity() {
  const info = activity(state.jobs, state.progress);
  const pill = document.getElementById("activite");
  if (pill) renderPill(pill, info, jobHref);
  const running = info && info.job?.status === "running" && info.job.kind === "fetch" && state.progress[info.job.id];
  const e = running?.episodes;
  document.title = e ? `(${(e.done || 0) + (e.skipped || 0)}/${e.total}) ${baseTitle}` : baseTitle;
}

// Tuiles des épisodes en cours : barre de progression sans reconstruire la fiche.
function updateTiles(progress) {
  if (view.name !== "series" || !progress.episodes?.active) return;
  const job = state.jobs.active.find((j) => j.id === progress.job_id);
  if (!job || job.series_key !== view.key) return;
  const active = new Set(progress.episodes.active.map((a) => a.n));
  for (const tile of main.querySelectorAll(".tile[data-live]")) {
    if (!active.has(Number(tile.dataset.n))) {
      tile.dataset.status = tile.dataset.was; // fini ou arrêté : la fiche se met à jour juste après
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

let refreshTimer = null;
function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refresh(), 300);
}

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
      renderHealth();
      updateActivity();
      if (data.library_version !== state.library?.version) scheduleRefresh();
    },
    job(data) {
      const before = state.jobs.active.find((j) => j.id === data.job.id);
      state.jobs = applyJobEvent(state.jobs, data);
      if (data.op !== "updated" || !["running", "queued"].includes(data.job.status)) delete state.progress[data.job.id];
      if (before && data.job.status === "done") announce(`Terminé : ${data.job.title || "tâche"}.`);
      updateActivity();
      scheduleRefresh();
    },
    progress(data) {
      state.progress[data.job_id] = data;
      updateActivity();
      updateTiles(data);
    },
    library: scheduleRefresh,
    health(data) {
      state.health = { ...(state.health || {}), ...data };
      renderHealth();
      if (data.online === false) showBanner("info", "Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls.");
      else if (data.online === true && !state.unreachable) showBanner(null, null);
    },
    settings(data) {
      state.settings = data.settings;
      applyTheme();
      scheduleRefresh();
    },
    server(data) {
      if (data.op === "shutdown") {
        state.unreachable = true;
        showBanner("danger", "ShortDramaGen s'est arrêté. Relance sdg ui pour continuer ; les téléchargements reprendront là où ils en étaient.");
      }
    },
  });
}

// --- rafraîchissement ---------------------------------------------------------------------

let polling = false;
async function refresh(force = false) {
  if (polling) return;
  polling = true;
  try {
    const changed = await loadLibrary();
    if (changed || force) {
      state.details.clear();
      if (!theater) await render(true);
    }
  } finally {
    polling = false;
  }
}

function startPolling() {
  setInterval(() => { if (!state.live && document.visibilityState === "visible") refresh(); }, FALLBACK_POLL_MS);
  setInterval(() => { if (document.visibilityState === "visible") loadHealth(); }, HEALTH_MS);
  addEventListener("focus", () => refresh());
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refresh(); });
}

function shortcuts() {
  document.addEventListener("keydown", (e) => {
    if (theater) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      document.getElementById("recherche")?.focus();
    } else if (e.key === "Escape") {
      const popover = document.getElementById("sante");
      if (popover && !popover.hidden) {
        popover.hidden = true;
        document.getElementById("sante-btn")?.focus();
      } else if (parseRoute().name === "series" && !(e.target instanceof HTMLInputElement)) {
        location.hash = "#/";
      }
    }
  });
}

async function start() {
  buildTopbar();
  shortcuts();
  state.query = parseRoute().params.get("q") || "";
  document.getElementById("recherche").value = state.query;
  render();
  await Promise.all([loadHealth(), loadLibrary()]);
  const count = state.library?.stats?.groups ?? 0;
  await render(parseRoute().name === "library");
  if (state.library) announce(`Bibliothèque chargée : ${count} série${count > 1 ? "s" : ""}.`);
  addEventListener("hashchange", () => render());
  startEvents();
  startPolling();
}

start();
