// Bibliothèque (spec E1) : mur d'affiches ou liste, filtres, recherche, tri, étagère
// « À traiter », actions sur les cartes, sélection multiple.

import { append, codeBox, h, icon } from "../dom.js";
import { ACCEPTED, EXAMPLE_URL, detect } from "../detect.js";
import { bytes, duration, htmlLang, plural, shortWhen, versionShort, versionSlug } from "../format.js";
import { FILTERS, counts, filmReady, groupProblem, matchFilter, primaryAction, toTreat, versionMeta } from "../status.js";
import { openMenu, openPopover } from "../ui.js";
import { focusVersion, menuItems, openDeleteDialog, runPrimary } from "./common.js";

const SORTS = [
  { id: "recent", label: "Activité récente" },
  { id: "title", label: "Titre (A → Z)" },
  { id: "size", label: "Taille" },
];

export function normalize(text) {
  return (text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function groupText(group) {
  return normalize([group.display_title, group.title_vo, ...Object.values(group.titles || {}), group.book_id].join(" "));
}

function groupBytes(group) {
  return group.versions.reduce((sum, v) => sum + v.bytes + (v.film?.bytes || 0), 0);
}

// La version ouverte par la carte : celle dont le titre est affiché, sinon la première (la VO).
export function mainVersion(group) {
  return group.versions.find((v) => v.title === group.display_title) || group.versions[0];
}

export function seriesHref(group, version) {
  return `#/serie/${group.ref}/${versionSlug(version)}`;
}

function coverImage(url, cls = "") {
  const img = h("img", { class: cls, src: url, alt: "", loading: "lazy", decoding: "async" });
  img.addEventListener("error", () => img.remove());
  return img;
}

export function ribbon(version, { eq = false } = {}) {
  const k = counts(version);
  const seg = (cls, n) => (n > 0 ? h("span", { class: cls, vars: { "--n": n } }) : null);
  const c = version.counts;
  return h(
    "div",
    { class: "ribbon", role: "img", "aria-label": `${k.present} épisodes sur ${k.total} présents` },
    seg("rs-ok", k.present),
    seg("rs-act", c.downloading || 0),
    seg("rs-warn", k.partial),
    seg("rs-fail", k.repair),
    seg("rs-todo", k.todo + (c.queued || 0)),
  );
}

function accessibleName(group, problem, version) {
  const parts = [group.display_title];
  if (group.versions.length > 1) parts.push(plural(group.versions.length, "version", "versions"));
  if (problem) parts.push(problem.text);
  if (group.versions.some(filmReady)) parts.push("film prêt");
  if (!problem) parts.push(versionMeta(version));
  return parts.join(", ");
}

// --- carte affiche ------------------------------------------------------------------------------------

function card(ctx, group, selected) {
  const version = mainVersion(group);
  const focus = focusVersion(group, version);
  const problem = groupProblem(group);
  const prefix = group.versions.length > 1 ? `${versionShort(focus)} · ` : "";
  const action = primaryAction(focus, { prefix });
  const badges = [];
  if (group.versions.length > 1) badges.push(group.versions.map(versionShort).join(" · "));
  else if (!version.is_original) badges.push(versionShort(version));
  const film = group.versions.map((v) => v.film).find((f) => f && ["ready", "partial", "stale"].includes(f.state));
  if (film) badges.push(film.state === "ready" ? "Film" : film.state === "partial" ? "Film partiel" : "Film obsolète");
  const unverified = group.versions.some((v) => !v.from_official);
  const job = focus.job;
  const href = seriesHref(group, version);

  // Première arrivée : l'affiche se colore au rythme des épisodes vérifiés.
  const coloring = job && job.kind === "fetch" && group.versions.length === 1;
  const coverBox = h("div", { class: `poster-cover${coloring ? " is-coloring" : ""}` });
  if (group.cover_url) {
    if (coloring) {
      const k = counts(focus);
      coverBox.style.setProperty("--p", (k.total ? k.present / k.total : 0).toFixed(3));
      coverBox.append(coverImage(group.cover_url, "poster-gray"), coverImage(group.cover_url, "poster-color"));
    } else {
      coverBox.append(coverImage(group.cover_url));
    }
  } else {
    coverBox.append(h("div", { class: "cover-fallback", text: group.display_title }));
  }

  let status = problem;
  if (job && job.kind === "fetch") {
    const k = counts(focus);
    const live = ctx.state.progress[job.id];
    const done = live?.episodes ? live.episodes.done + live.episodes.skipped : k.present;
    const total = live?.episodes?.total || k.total;
    status = {
      tone: job.status === "queued" ? "neutral" : job.status === "paused" || job.status === "interrupted" ? "warning" : "active",
      icon: job.status === "queued" ? "clock" : job.status === "paused" || job.status === "interrupted" ? "pause" : "arrowDown",
      text: job.status === "queued" ? `En file${job.position ? ` · ${job.position}e` : ""}` : job.status === "paused" ? `En pause · ${done}/${total}` : job.status === "interrupted" ? `Interrompu · ${done}/${total}` : `${prefix}${done}/${total}`,
    };
  }
  const band = status || unverified
    ? h(
        "div",
        { class: "poster-band" },
        status && h("div", { class: `poster-status is-${status.tone}` }, status.icon && icon(status.icon, { size: 12 }), status.text),
        h("div", { class: "poster-badges" }, badges.slice(0, 2).map((b) => h("span", { class: "badge", text: b })), badges.length > 2 ? h("span", { class: "badge", text: `+${badges.length - 2}` }) : null,
          unverified && h("span", { class: "badge badge-info", text: "Non vérifiée" })),
      )
    : badges.length
      ? h("div", { class: "poster-band is-nominal" }, h("div", { class: "poster-badges" }, badges.map((b) => h("span", { class: "badge", text: b }))))
      : null;
  if (band) coverBox.append(band);

  const link = h("a", { class: "poster-link", href, "aria-label": accessibleName(group, status, version), dataset: { book: group.ref } });
  const check = h(
    "label",
    { class: "poster-check", title: "Sélectionner" },
    h("input", { type: "checkbox", checked: selected || null, "aria-label": `Sélectionner ${group.display_title}`, onclick: (e) => ctx.toggleSelect(group.ref, e.shiftKey) }),
  );
  const more = h("button", { class: "btn-icon btn-icon-sm poster-more btn-scrim", type: "button", "aria-label": `Actions pour ${group.display_title}`, "aria-haspopup": "menu", "aria-expanded": "false" }, icon("more"));
  more.addEventListener("click", () => openMenu(more, menuItems(ctx, focus, ctx.state.details.get(focus.series_key)?.data), { label: `Actions pour ${group.display_title}` }));
  const main = h("button", { class: "btn btn-sm btn-primary poster-main", type: "button", onclick: () => runPrimary(ctx, focus, action) }, action.icon ? icon(action.icon, { size: 14 }) : null, h("span", { text: action.label }));
  const play = counts(focus).present
    ? h("button", { class: "btn-icon btn-icon-sm btn-scrim", type: "button", "aria-label": `Regarder ${group.display_title}`, title: "Regarder (L)", onclick: () => ctx.watch(focus) }, icon("play"))
    : null;
  coverBox.append(link, check, more, h("div", { class: "poster-actions" }, main, play));

  const incomplete = focus.state !== "complete";
  return h(
    "article",
    { class: `poster${selected ? " is-selected" : ""}`, dataset: { book: group.ref } },
    coverBox,
    h(
      "div",
      { class: "poster-body" },
      incomplete && ribbon(focus),
      h("h2", { class: "poster-title", lang: htmlLang(version.lang), title: group.display_title }, h("a", { href, tabindex: "-1", text: group.display_title })),
      h("div", { class: "poster-meta" }, versionMeta(focus)),
    ),
  );
}

// --- vue liste -------------------------------------------------------------------------------------------

function listView(ctx, groups, selection) {
  const rows = groups.map((group) => {
    const version = mainVersion(group);
    const focus = focusVersion(group, version);
    const k = counts(focus);
    const problem = groupProblem(group);
    const film = group.versions.map((v) => v.film).find((f) => f && f.bytes);
    const qualities = Object.keys(focus.qualities || {}).join(", ");
    const selected = selection.has(group.ref);
    return h(
      "tr",
      { class: selected ? "is-selected" : "", dataset: { book: group.ref } },
      h("td", {}, h("input", { type: "checkbox", checked: selected || null, "aria-label": `Sélectionner ${group.display_title}`, onclick: (e) => ctx.toggleSelect(group.ref, e.shiftKey) })),
      h("td", {}, h("div", { class: "list-cover" }, group.cover_url ? coverImage(group.cover_url) : null)),
      h("td", { class: "list-title" }, h("a", { href: seriesHref(group, version), lang: htmlLang(version.lang), text: group.display_title }),
        group.title_vo && group.title_vo !== group.display_title ? h("span", { class: "muted", lang: "en", text: group.title_vo }) : null),
      h("td", { text: group.versions.map(versionShort).join(" · ") }),
      h("td", { class: "list-episodes" }, h("span", { class: "num", text: `${k.present}/${k.total}` }), ribbon(focus)),
      h("td", { class: "num", text: focus.duration_s ? duration(focus.duration_s) : "—" }),
      h("td", { class: "num", text: bytes(groupBytes(group)) }),
      h("td", { text: film ? { ready: "Prêt", partial: "Partiel", stale: "Obsolète" }[film.state] || "—" : "—" }),
      h("td", { text: qualities || "—" }),
      h("td", { class: "num", text: shortWhen(group.updated_at) }),
      h("td", {}, problem ? h("span", { class: `list-state is-${problem.tone}`, text: problem.text }) : h("span", { class: "muted", text: "Complète" })),
    );
  });
  return h(
    "div",
    { class: "list-wrap" },
    h(
      "table",
      { class: "list" },
      h("thead", {}, h("tr", {}, ["", "", "Titre", "Versions", "Épisodes", "Durée", "Taille", "Film", "Qualité", "Modifiée", "État"].map((t, i) => h("th", { scope: "col", text: t, "aria-label": i === 0 ? "Sélection" : i === 1 ? "Affiche" : null })))),
      h("tbody", {}, rows),
    ),
  );
}

// --- étagère « À traiter » -------------------------------------------------------------------------------

function shelf(ctx, groups) {
  const items = [];
  for (const group of groups) {
    for (const version of group.versions) {
      const issue = toTreat(version);
      if (issue) items.push({ group, version, issue });
    }
  }
  if (!items.length) return null;
  const repairable = items.filter((i) => i.issue.problem !== "incomplete");
  const repairAll = repairable.length
    ? h("button", { class: "btn btn-secondary", type: "button", "aria-haspopup": "dialog" }, icon("refresh", { size: 16 }), `Tout réparer · ${plural(new Set(repairable.map((i) => i.version.series_key)).size, "série", "séries")}`)
    : null;
  repairAll?.addEventListener("click", async () => {
    const plan = await ctx.act.repairAll(true);
    if (!plan) return;
    openPopover(repairAll, (close) => {
      const lines = plan.actions.map((a) => `${plural(a.retry.length, "épisode", "épisodes")} · ${a.title}`);
      return [
        h("p", { class: "popover-title", text: plan.actions.length ? "Tout réparer" : "Rien à réparer" }),
        plan.actions.length ? h("ul", { class: "plain-list" }, lines.map((l) => h("li", { text: l }))) : h("p", { class: "muted", text: "Les problèmes restants demandent un choix (compléter, harmoniser)." }),
        plan.bytes_estimate ? h("p", { class: "muted num", text: `≈ ${bytes(plan.bytes_estimate)} à télécharger.` }) : null,
        h("p", { class: "note", text: "Seulement des actions sûres : réessayer les échecs, reprendre les interruptions, retélécharger les fichiers disparus." }),
        h("div", { class: "btn-row" },
          plan.actions.length ? h("button", { class: "btn btn-primary btn-sm", type: "button", "data-autofocus": true, onclick: () => { close(); ctx.act.repairAll(false); }, text: "Tout réparer" }) : null,
          h("button", { class: "btn btn-secondary btn-sm", type: "button", onclick: close, text: "Annuler" })),
      ];
    }, { label: "Tout réparer" });
  });
  const cards = items.slice(0, 12).map(({ group, version, issue }) => {
    const action = primaryAction(version);
    const more = h("button", { class: "btn-icon btn-icon-sm compact-more", type: "button", "aria-label": `Autres actions pour ${version.title}`, "aria-haspopup": "menu" }, icon("more"));
    more.addEventListener("click", () => openMenu(more, [
      { label: "Voir la fiche", icon: "next", onClick: () => ctx.goSeries(version.series_key) },
      { label: "Ignorer ce problème", icon: "close", onClick: () => ctx.act.ignore(version.series_key, issue.problem) },
    ]));
    return h(
      "article",
      { class: "compact" },
      h("div", { class: "compact-cover" }, version.cover_url || group.cover_url ? coverImage(version.cover_url || group.cover_url) : null),
      h(
        "div",
        { class: "compact-body" },
        h("h3", { class: "compact-title", title: version.title }, h("a", { href: seriesHref(group, version), lang: htmlLang(version.lang), text: `${version.title}${group.versions.length > 1 ? ` · ${versionShort(version)}` : ""}` })),
        h("p", { class: "compact-problem", text: issue.text }),
        h("div", { class: "compact-actions" }, h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => runPrimary(ctx, version, action) }, action.label)),
      ),
      more,
    );
  });
  return h(
    "section",
    { class: "shelf", "aria-labelledby": "titre-a-traiter" },
    h("div", { class: "shelf-head" }, h("h2", { id: "titre-a-traiter", text: `À traiter · ${items.length}` }), repairAll),
    h("div", { class: "shelf-row" }, cards),
  );
}

// --- barre de sélection ------------------------------------------------------------------------------------

function selectionBar(ctx, groups, selection) {
  const chosen = groups.filter((g) => selection.has(g.ref));
  if (!chosen.length) return null;
  const versions = chosen.flatMap((g) => g.versions);
  const size = chosen.reduce((s, g) => s + groupBytes(g), 0);
  const toComplete = versions.filter((v) => !v.job && counts(v).todo);
  const toRetry = versions.filter((v) => !v.job && counts(v).repair + counts(v).partial);
  const filmable = versions.filter((v) => !v.job && counts(v).present === counts(v).total && counts(v).total && !(v.film && v.film.state === "ready"));
  const blocked = versions.filter((v) => !(v.film && v.film.state === "ready")).length - filmable.length;
  const freeable = versions.filter((v) => v.film?.state === "ready" && v.episodes_bytes);
  const freeBytes = freeable.reduce((s, v) => s + v.episodes_bytes, 0);
  const button = (label, list, run, cls = "btn-secondary") =>
    h("button", { class: `btn btn-sm ${cls}`, type: "button", disabled: !list.length || null, onclick: () => run(list) }, label);
  return h(
    "div",
    { class: "selbar", role: "region", "aria-label": "Sélection" },
    h("span", { class: "selbar-count num", text: `${plural(chosen.length, "série", "séries")} · ${bytes(size)}` }),
    button(`Compléter${toComplete.length ? ` · ${toComplete.length}` : ""}`, toComplete, (list) => list.forEach((v) => ctx.act.retry(v.series_key, { include_pending: true }, "Téléchargement lancé"))),
    button("Réessayer les échecs", toRetry, (list) => list.forEach((v) => ctx.act.retry(v.series_key))),
    button(`Créer les films${filmable.length || blocked ? ` · ${filmable.length} possible${filmable.length > 1 ? "s" : ""}` : ""}${blocked > 0 ? ` · ${blocked} bloqué${blocked > 1 ? "s" : ""}` : ""}`, filmable,
      (list) => list.forEach((v) => runPrimary(ctx, v, { id: "film" }))),
    button(`Libérer l'espace (garder les films)${freeBytes ? ` · ${bytes(freeBytes)}` : ""}`, freeable, (list) => openDeleteDialog(ctx, list)),
    button("Supprimer…", versions, (list) => openDeleteDialog(ctx, list), "btn-danger-ghost"),
    h("button", { class: "btn-icon btn-icon-sm", type: "button", "aria-label": "Vider la sélection (Échap)", title: "Vider la sélection (Échap)", onclick: () => ctx.clearSelection() }, icon("close")),
  );
}

// --- états vides --------------------------------------------------------------------------------------------

function emptyState(ctx, library) {
  const field = h("input", { class: "hero-input", type: "text", placeholder: "Colle le lien d'une série", "aria-label": "Lien d'une série", "data-autofocus": true, autocomplete: "off" });
  const go = () => {
    const d = detect(field.value);
    if (d.kind !== "empty") ctx.openAdd(field.value);
  };
  field.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
  field.addEventListener("paste", () => setTimeout(go, 0));
  const health = ctx.state.health || {};
  return h(
    "section",
    { class: "empty-hero" },
    h("h1", { tabindex: "-1", text: "Ta bibliothèque est vide" }),
    h("p", { class: "lead", text: "Colle le lien d'une série : on récupère ses épisodes, vérifiés." }),
    h("div", { class: "hero-field" }, icon("download", { size: 20 }), field),
    h("p", { class: "note", text: ACCEPTED }),
    h("button", { class: "btn btn-ghost", type: "button", onclick: () => { field.value = EXAMPLE_URL; field.focus(); }, text: "Essayer avec un exemple" }),
    h(
      "div",
      { class: "quick-settings" },
      h("span", {}, "Dossier : ", h("span", { class: "mono", text: library.root })),
      h("a", { href: "#/reglages/general", text: "Changer" }),
      h("span", { text: health.ffmpeg?.found ? "Films : ffmpeg prêt" : "Films : ffmpeg manquant" }),
      health.ffmpeg && !health.ffmpeg.found ? h("a", { href: "#/reglages/film", text: "Comment l'installer ?" }) : null,
    ),
    h("p", { class: "note", text: "Astuce : Ctrl+V fonctionne n'importe où · Ctrl+K pour chercher · ? pour les raccourcis." }),
  );
}

function rootError(library, onRetry) {
  return h(
    "section",
    { class: "empty", role: "alert" },
    h("h2", { tabindex: "-1", "data-autofocus": true, text: "Impossible d'ouvrir ton dossier de séries" }),
    h("p", {}, h("span", { class: "mono", text: library.root }), " : il a peut-être été déplacé, ou le disque est débranché."),
    h("div", { class: "btn-row" },
      h("a", { class: "btn btn-secondary", href: "#/reglages/general", text: "Choisir un autre dossier" }),
      h("button", { class: "btn btn-secondary", type: "button", onclick: onRetry }, icon("refresh"), "Réessayer")),
  );
}

function problemsBox(problems) {
  if (!problems.length) return null;
  return h(
    "details",
    { class: "problems banner banner-warning" },
    h("summary", {}, `${plural(problems.length, "dossier n'a pas pu être lu et est masqué", "dossiers n'ont pas pu être lus et sont masqués")}. Voir lesquels`),
    h("ul", {}, problems.map((p) => h("li", {}, h("span", { class: "mono", text: p.folder }), ` : ${p.message}`))),
  );
}

// --- page ------------------------------------------------------------------------------------------------------

export function filteredGroups(library, params, query) {
  const filter = FILTERS.find((f) => f.id === (params.get("f") || "")) || FILTERS[0];
  const needle = normalize(query);
  const sortId = params.get("tri") || "recent";
  let shown = library.groups.filter((g) => matchFilter(g, filter) && (!needle || groupText(g).includes(needle)));
  if (sortId === "title") shown = [...shown].sort((a, b) => a.display_title.localeCompare(b.display_title, "fr"));
  else if (sortId === "size") shown = [...shown].sort((a, b) => groupBytes(b) - groupBytes(a));
  return { shown, filter, needle, sortId };
}

export function renderLibrary(main, ctx, route) {
  const { library } = ctx.state;
  const params = route.params;
  const page = h("div", { class: "page" });
  if (!library) {
    append(page, [
      h("div", { class: "lib-head" }, h("h1", { text: "Bibliothèque" }), h("span", { class: "lib-stats", text: "Lecture de ta bibliothèque…" })),
      h("div", { class: "wall", "aria-hidden": "true" }, Array.from({ length: 7 }, () => h("div", {}, h("div", { class: "skeleton poster-cover" }), h("div", { class: "skeleton skeleton-line" })))),
    ]);
    main.append(page);
    return;
  }
  if (library.root_error) {
    page.append(rootError(library, () => ctx.refresh(true)));
    main.append(page);
    return;
  }
  if (!library.groups.length && !library.problems?.length) {
    page.append(emptyState(ctx, library));
    main.append(page);
    return;
  }

  const { shown, filter, needle, sortId } = filteredGroups(library, params, ctx.state.query);
  const view = params.get("vue") === "liste" ? "liste" : "affiches";
  const s = library.stats;
  const stats = [plural(s.groups, "série", "séries")];
  if (s.versions !== s.groups) stats.push(plural(s.versions, "version", "versions"));
  stats.push(bytes(s.bytes));
  if (s.free_bytes !== null && s.free_bytes !== undefined) stats.push(`${bytes(s.free_bytes)} libres`);

  const sortSelect = h(
    "select",
    { "aria-label": "Tri", onchange: (e) => ctx.setParams({ tri: e.target.value === "recent" ? "" : e.target.value }) },
    SORTS.map((o) => h("option", { value: o.id, selected: o.id === sortId, text: `Tri : ${o.label}` })),
  );
  const segmented = h(
    "div",
    { class: "segmented", role: "group", "aria-label": "Affichage" },
    [["affiches", "Affiches", "grid"], ["liste", "Liste", "list"]].map(([id, label, glyph]) =>
      h("button", { class: "segmented-btn", type: "button", "aria-pressed": String(view === id), onclick: () => ctx.setParams({ vue: id === "affiches" ? "" : id }) }, icon(glyph, { size: 14 }), label)),
  );
  append(page, [
    h("div", { class: "lib-head" },
      h("h1", { tabindex: "-1", "data-autofocus": true, text: "Bibliothèque" }),
      h("span", { class: "lib-stats num", text: stats.join(" · ") }),
      h("div", { class: "lib-tools" }, h("label", { class: "select" }, sortSelect), segmented)),
    problemsBox(library.problems || []),
  ]);

  const chips = FILTERS.map((f) => {
    const count = library.groups.filter((g) => matchFilter(g, f)).length;
    if (f.id && !count && f.id !== filter.id) return null;
    return h("button", { class: "chip", type: "button", "aria-pressed": String(f.id === filter.id), onclick: () => ctx.setParams({ f: f.id === filter.id ? "" : f.id }) },
      f.id === filter.id && f.id ? icon("check", { size: 14 }) : null, f.label, h("span", { class: "chip-count", text: count }));
  });
  const filtered = filter.id || needle;
  page.append(h("div", { class: "lib-filters" },
    h("div", { class: "chips", role: "group", "aria-label": "Filtres" }, chips),
    filtered ? h("span", { class: "lib-result" }, `${shown.length} sur ${plural(library.groups.length, "série", "séries")} `,
      h("button", { class: "link-btn", type: "button", onclick: () => ctx.setParams({ f: "", q: "" }), text: "Effacer les filtres" })) : null));

  if (!filtered) {
    const treat = shelf(ctx, library.groups);
    if (treat) page.append(treat);
  }

  if (!shown.length) {
    page.append(h("p", { class: "empty", role: "status" }, needle ? `Aucune série « ${ctx.state.query} » dans ta bibliothèque. Pour en ajouter une, colle son lien.` : `Aucune série « ${filter.label} ».`,
      " ", h("button", { class: "link-btn", type: "button", onclick: () => ctx.setParams({ f: "", q: "" }), text: "Effacer les filtres" })));
  } else if (view === "liste") {
    page.append(listView(ctx, shown, ctx.state.selection));
  } else {
    page.append(h("div", { class: "wall", role: "list", "aria-label": "Séries" }, shown.map((g) => {
      const c = card(ctx, g, ctx.state.selection.has(g.ref));
      c.setAttribute("role", "listitem");
      return c;
    })));
  }
  const bar = selectionBar(ctx, shown, ctx.state.selection);
  if (bar) page.append(bar);
  main.append(page);
}
