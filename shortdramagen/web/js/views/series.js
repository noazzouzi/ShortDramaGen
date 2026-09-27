// Fiche série (spec E3, E4) : héros, versions, santé et action principale, grille d'épisodes
// avec sélection, volet de détail, film (pré-vol, remèdes, création), stockage, détails.

import { ApiError, get } from "../api.js";
import { append, clear, codeBox, copyText, h, icon } from "../dom.js";
import { bytes, capitalize, duration, fullDate, htmlLang, langName, plural, ranges, versionLong, versionShort, versionSlug, when } from "../format.js";
import { EPISODE, ERRORS, counts, primaryAction } from "../status.js";
import { openMenu } from "../ui.js";
import { parseRanges } from "./add.js";
import { fetchCommand, firstPlayable, menuItems, openDeleteDialog, runPrimary } from "./common.js";

export function theaterHref(group, version, target) {
  return `#/serie/${group.book_id}/${versionSlug(version)}/lire/${target}`;
}

function majorityQuality(detail) {
  return Object.keys(detail.qualities || {})[0] || null;
}

function kv(label, value) {
  return h("div", { class: "kv" }, h("dt", { text: label }), h("dd", { text: value }));
}

function qualityLine(detail) {
  const q = Object.entries(detail.qualities || {});
  if (!q.length) return null;
  const [main, ...others] = q;
  if (!others.length) return main[0];
  const n = others.reduce((s, [, c]) => s + c, 0);
  return `${main[0]} (${plural(n, "ép.", "ép.")} en ${others.map(([k]) => k).join(", ")})`;
}

// --- héros et versions --------------------------------------------------------------------------------

function hero(ctx, group, detail) {
  const coverUrl = detail.cover_url || group.cover_url;
  const meta = [plural(detail.counts.total, "épisode", "épisodes"), detail.duration_s ? duration(detail.duration_s) : null, detail.bytes ? bytes(detail.bytes) : null, qualityLine(detail)].filter(Boolean);
  const syn = detail.introduction ? h("p", { class: "syn", lang: htmlLang(detail.lang), text: detail.introduction }) : null;
  const more = syn && detail.introduction.length > 220
    ? h("button", {
        class: "link-btn", type: "button", "aria-expanded": "false", text: "Lire plus",
        onclick: (e) => {
          const open = syn.classList.toggle("is-open");
          e.currentTarget.textContent = open ? "Réduire" : "Lire plus";
          e.currentTarget.setAttribute("aria-expanded", String(open));
        },
      })
    : null;
  const coverBox = h("div", { class: "hero-cover" });
  coverBox.append(coverUrl ? h("img", { src: coverUrl, alt: "" }) : h("div", { class: "cover-fallback" }, icon("film", { size: 32 })));
  return h(
    "section",
    { class: "hero", "aria-labelledby": "titre-serie" },
    coverUrl ? h("img", { class: "hero-bg", src: coverUrl, alt: "", "aria-hidden": "true" }) : null,
    coverBox,
    h(
      "div",
      { class: "hero-info" },
      h("div", { class: "overline", text: group.versions.length > 1 ? `Série · ${group.versions.length} versions` : "Série" }),
      h("h1", { id: "titre-serie", tabindex: "-1", "data-autofocus": true, lang: htmlLang(detail.lang), text: detail.title }),
      detail.title_vo && detail.title_vo !== detail.title ? h("p", { class: "hero-vo", lang: "en", text: `${detail.title_vo} · titre original` }) : null,
      h("div", { class: "hero-meta num" }, meta.map((m) => h("span", { text: m }))),
      syn,
      more,
      tabs(ctx, group, detail),
    ),
  );
}

function tabs(ctx, group, detail) {
  const items = group.versions.map((v) => {
    const k = counts(v);
    const ok = v.state === "complete";
    const problem = v.state === "failed" || v.state === "interrupted";
    return h(
      "a",
      { class: "tab", href: `#/serie/${group.book_id}/${versionSlug(v)}`, "aria-current": v.series_key === detail.series_key ? "page" : null, title: v.title },
      versionLong(v),
      h("span", { class: `tab-status num ${ok ? "is-ok" : problem ? "is-problem" : ""}` }, ok ? icon("check", { size: 12 }) : null, `${k.present}/${k.total}`, problem ? " !" : ""),
    );
  });
  const have = new Set(group.versions.map((v) => (v.is_original ? null : v.lang)));
  const vo = group.versions.find((v) => v.is_original);
  const others = (group.languages_available || []).filter((l) => !have.has(l) && l !== vo?.lang);
  for (const l of others.slice(0, 3)) {
    items.push(h("button", { class: "tab is-add", type: "button", title: `Ajouter la version ${langName(l)}`, onclick: () => ctx.openAdd(group.book_id, { lang: l }) }, icon("plus", { size: 14 }), capitalize(langName(l))));
  }
  if (others.length > 3) {
    const more = h("button", { class: "tab is-add", type: "button", "aria-haspopup": "menu" }, "+ Autres ▾");
    more.addEventListener("click", () => openMenu(more, others.slice(3).map((l) => ({ label: capitalize(langName(l)), onClick: () => ctx.openAdd(group.book_id, { lang: l }) })), { label: "Autres langues" }));
    items.push(more);
  }
  return h("nav", { class: "tabs", "aria-label": "Versions" }, items);
}

// --- barre de santé ------------------------------------------------------------------------------------------

function healthSentence(detail) {
  const c = detail.counts;
  const k = counts(detail);
  const byStatus = (s) => detail.episodes.filter((e) => e.status === s).map((e) => e.n);
  const parts = [];
  let tone = "ok";
  let glyph = "check";
  const job = detail.job;
  if (job && job.kind === "fetch" && ["active", "queued", "paused", "interrupted"].includes(detail.state)) {
    tone = detail.state === "active" ? "active" : detail.state === "queued" ? "info" : "warning";
    glyph = { active: "arrowDown", queued: "clock" }[detail.state] || "pause";
    const label = { active: "Téléchargement en cours", queued: job.position ? `En file · ${job.position}e` : "En file", paused: "En pause", interrupted: "Interrompu" }[detail.state];
    parts.push(`${label} · ${k.present}/${k.total}`);
    if (c.downloading) parts.push(`${c.downloading} en cours`);
    if (c.queued) parts.push(`${c.queued} en attente`);
  } else if (job && job.kind === "film") {
    tone = "active";
    glyph = "film";
    parts.push(job.status === "running" ? "Création du film en cours" : "Film en file");
  } else if (detail.state === "complete") {
    parts.push(`${k.present}/${k.total} téléchargés${detail.from_official ? " et vérifiés" : ""}`);
    if (detail.duration_s) parts.push(duration(detail.duration_s));
    parts.push(bytes(detail.episodes_bytes));
    if (detail.film?.state === "ready") parts.push("Film prêt");
  } else {
    tone = detail.state === "failed" ? "danger" : "warning";
    glyph = detail.state === "failed" ? "alert" : detail.state === "interrupted" ? "pause" : "info";
    parts.push(`${k.present}/${k.total} présents`);
    const add = (status, one, many) => {
      const list = byStatus(status);
      if (list.length) parts.push(`${plural(list.length, one, many)} (${ranges(list)})`);
    };
    add("failed", "échec", "échecs");
    add("unavailable", "indisponible", "indisponibles");
    add("missing", "fichier manquant", "fichiers manquants");
    add("partial", "interrompu", "interrompus");
    add("pending", "à télécharger", "à télécharger");
    add("not_requested", "non demandé", "non demandés");
  }
  const main = majorityQuality(detail);
  const odd = detail.episodes.filter((e) => e.media_url && e.quality && e.quality !== main);
  if (odd.length) parts.push(`${plural(odd.length, "épisode", "épisodes")} en ${[...new Set(odd.map((e) => e.quality))].join(", ")} (${ranges(odd.map((e) => e.n))})`);
  if (c.suspect) parts.push(`${plural(c.suspect, "fichier modifié", "fichiers modifiés")} depuis la vérification`);
  if (!detail.from_official) {
    if (tone === "ok") tone = "info";
    parts.push("durées non vérifiées : série absente du site officiel");
  }
  return { tone, glyph, text: capitalize(parts.join(" · ")) };
}

function healthBar(ctx, group, detail) {
  const sentence = healthSentence(detail);
  const action = primaryAction(detail);
  const playable = firstPlayable(detail);
  const buttons = [];
  if (action.id !== "open") {
    buttons.push(h("button", { class: "btn btn-primary", type: "button", onclick: () => runPrimary(ctx, detail, action) }, action.icon ? icon(action.icon) : null, action.label.replace(/ · (\d+)$/, (_, n) => ` · ${plural(Number(n), "épisode", "épisodes")}`)));
  }
  if (detail.job && detail.job.kind === "fetch" && ["running", "queued"].includes(detail.job.status)) {
    buttons.push(h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.openDrawer(), text: "Voir l'activité" }));
  }
  if (playable && action.id !== "watch_film") {
    buttons.push(h("a", { class: "btn btn-secondary", href: theaterHref(group, detail, playable) }, icon("play"), `Regarder · ép. ${playable}`));
  }
  buttons.push(h("button", { class: "btn btn-ghost", type: "button", onclick: () => ctx.act.open(detail.series_key, "folder") }, icon("folder"), "Dossier"));
  const more = h("button", { class: "btn-icon", type: "button", "aria-label": "Autres actions", "aria-haspopup": "menu" }, icon("more", { size: 20 }));
  more.addEventListener("click", () => openMenu(more, [
    ...menuItems(ctx, detail, detail).filter((i) => i === "sep" || (i && !["Ouvrir la fiche", "Ouvrir le dossier"].includes(i.label))),
  ], { label: "Autres actions" }));
  buttons.push(more);
  return h(
    "section",
    { class: "health", "aria-label": "État de la version" },
    h("p", { class: `health-text is-${sentence.tone}` }, icon(sentence.glyph), h("span", { text: sentence.text })),
    h("div", { class: "btn-row" }, buttons),
  );
}

// --- épisodes : grille, sélection -------------------------------------------------------------------------------

const REPAIRABLE = ["failed", "unavailable", "missing", "partial"];

function episodesSection(ctx, group, detail, ui) {
  const main = majorityQuality(detail);
  const sel = ui.selection;
  const selecting = sel.size > 0;
  const legendItems = [
    ["downloading", "badge-active", "En cours"],
    ["queued", "badge", "En file"],
    ["done", "badge-success", "Téléchargés"],
    ["done_unverified", "badge-success", "Non vérifiés"],
    ["partial", "badge-warning", "Interrompus"],
    ["failed", "badge-danger", "Échecs"],
    ["unavailable", "badge-dashed", "Indisponibles"],
    ["missing", "badge-warning", "Manquants"],
    ["pending", "badge-dashed", "À télécharger"],
    ["not_requested", "badge-dashed", "Non demandés"],
    ["removed", "badge", "Retirés"],
  ];
  const legend = legendItems
    .filter(([status]) => detail.counts[status])
    .map(([status, cls, label]) =>
      h("button", {
        class: `badge badge-btn ${cls}`, type: "button", title: `Sélectionner : ${label.toLowerCase()}`,
        onclick: () => ui.select(detail.episodes.filter((e) => e.status === status).map((e) => e.n)),
      }, `${label} `, h("span", { class: "num", text: detail.counts[status] })));
  const odd = detail.episodes.filter((e) => e.media_url && e.quality && main && e.quality !== main);
  if (odd.length) legend.push(h("button", { class: "badge badge-btn badge-warning", type: "button", onclick: () => ui.select(odd.map((e) => e.n)) }, `${odd[0].quality} `, h("span", { class: "num", text: odd.length })));

  const rangeField = h("input", { class: "mono range-field", type: "text", placeholder: "1-10, 28, 50-", value: selecting ? ranges([...sel]) : "", "aria-label": "Sélection par plages", "aria-describedby": "plages-fiche" });
  const rangeHelp = h("p", { class: "field-help", id: "plages-fiche" });
  rangeField.addEventListener("change", () => {
    try {
      ui.select([...parseRanges(rangeField.value, detail.counts.total)], true);
    } catch (err) {
      rangeHelp.textContent = err.message;
      rangeField.classList.add("is-error");
    }
  });
  const tool = (label, list) => h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => ui.select(list, true), text: label });
  const all = detail.episodes.map((e) => e.n);
  const tools = h(
    "div",
    { class: "grid-tools" },
    h("span", { class: "muted", text: "Sélection :" }),
    tool("Tous", all),
    tool("Aucun", []),
    tool("Manquants", detail.episodes.filter((e) => !e.media_url && e.status !== "removed").map((e) => e.n)),
    tool("Échecs", detail.episodes.filter((e) => REPAIRABLE.includes(e.status)).map((e) => e.n)),
    h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => ui.select(all.filter((n) => !sel.has(n)), true), text: "Inverser" }),
    rangeField,
  );

  const selectedEps = detail.episodes.filter((e) => sel.has(e.n));
  const selSize = selectedEps.reduce((s, e) => s + (e.bytes || (e.duration_s ? e.duration_s * 124000 : 0)), 0);
  const selbar = selecting
    ? h("div", { class: "selmode", role: "status" },
        h("span", { class: "num", text: `${plural(sel.size, "sélectionné", "sélectionnés")} · ≈ ${bytes(selSize)} · Échap pour quitter` }),
        h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => ui.select([], true), text: "Quitter" }))
    : null;

  // Grille décimale avec un seul arrêt de tabulation (roving tabindex).
  const rows = new Map();
  for (const ep of detail.episodes) {
    const row = Math.floor((ep.n - 1) / 10);
    if (!rows.has(row)) rows.set(row, []);
    rows.get(row).push(ep);
  }
  const current = ui.focusN && detail.episodes.some((e) => e.n === ui.focusN) ? ui.focusN : detail.episodes[0]?.n;
  const grid = h(
    "div",
    { class: `grid${selecting ? " is-selecting" : ""}`, role: "grid", "aria-label": "Épisodes", "aria-multiselectable": "true" },
    [...rows.entries()].map(([row, eps]) =>
      h("div", { class: "grid-row", role: "row" },
        h("span", { class: "row-label", "aria-hidden": "true", text: `${row * 10 + 1}–${row * 10 + 10}` }),
        h("div", { class: "tiles" }, eps.map((ep) => tile(ep, main, sel.has(ep.n), ep.n === current))))),
  );
  grid.addEventListener("click", (e) => {
    const t = e.target.closest(".tile");
    if (!t) return;
    const ep = detail.episodes.find((x) => x.n === Number(t.dataset.n));
    ui.focusN = ep.n;
    if (e.shiftKey && ui.anchor) ui.extend(ep.n);
    else if (e.ctrlKey || e.metaKey || selecting) ui.toggle(ep.n);
    else if (ep.media_url) ctx.go(theaterHref(group, detail, ep.n));
    else ui.show(ep.n);
  });
  grid.addEventListener("focusin", (e) => {
    const t = e.target.closest(".tile");
    if (t && !selecting) ui.show(Number(t.dataset.n), false);
  });
  grid.addEventListener("keydown", (e) => {
    const t = e.target.closest(".tile");
    if (!t) return;
    const n = Number(t.dataset.n);
    const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 10, ArrowUp: -10 };
    let next = null;
    if (moves[e.key] !== undefined) next = n + moves[e.key];
    else if (e.key === "Home") next = all[0];
    else if (e.key === "End") next = all[all.length - 1];
    else if (e.key === " ") {
      e.preventDefault();
      ui.focusN = n;
      ui.toggle(n);
      return;
    } else if (e.key === "Enter") {
      return; // le clic du bouton fait le reste
    }
    if (next === null) return;
    e.preventDefault();
    const target = grid.querySelector(`.tile[data-n="${Math.max(all[0], Math.min(all[all.length - 1], next))}"]`);
    if (!target) return;
    t.tabIndex = -1;
    target.tabIndex = 0;
    target.focus();
    ui.focusN = Number(target.dataset.n);
    if (e.shiftKey) ui.extend(ui.focusN);
  });
  return h(
    "section",
    { "aria-labelledby": "titre-episodes" },
    h("h2", { class: "section-title", id: "titre-episodes", text: "Épisodes" }),
    legend.length ? h("div", { class: "legend" }, legend) : null,
    tools,
    rangeHelp,
    selbar,
    grid,
    h("p", { class: "note", text: "Clic : regarder un épisode téléchargé, ou voir le détail des autres. Ctrl+clic ou Espace : sélectionner ; Maj : étendre." }),
  );
}

function tile(ep, main, selected, focusable) {
  const info = EPISODE[ep.status] || { label: ep.status };
  const odd = ep.media_url && ep.quality && main && ep.quality !== main;
  const label = [`Épisode ${ep.n}`, ep.duration_s ? duration(ep.duration_s) : null, info.label.toLowerCase(), ep.bytes ? bytes(ep.bytes) : null, ep.quality].filter(Boolean).join(", ");
  const button = h(
    "button",
    {
      class: `tile${odd ? " has-q" : ""}${ep.suspect ? " is-suspect" : ""}${selected ? " is-sel" : ""}`, type: "button", role: "gridcell",
      "aria-label": label, "aria-selected": String(selected), title: label, tabindex: focusable ? "0" : "-1", dataset: { status: ep.status, n: ep.n },
    },
    h("span", { text: ep.n }),
    info.glyph ? h("span", { class: "glyph" }, icon(info.glyph)) : null,
    odd ? h("span", { class: "q-badge", "aria-hidden": "true", text: ep.quality.replace("p", "") }) : null,
    selected ? h("span", { class: "tile-pick", "aria-hidden": "true" }, icon("check", { size: 12 })) : null,
  );
  return button;
}

// --- volet contextuel -------------------------------------------------------------------------------------------

function sideSummary(detail) {
  const k = counts(detail);
  const last = detail.episodes.map((e) => e.finished_at).filter(Boolean).sort().pop();
  const origins = [...new Set(detail.episodes.filter((e) => e.origin).map((e) => e.origin))];
  return [
    h("h2", { text: `Résumé · ${versionLong(detail)}` }),
    h("dl", {},
      kv("Présents", `${k.present}/${k.total}`),
      kv("Taille", bytes(detail.episodes_bytes)),
      qualityLine(detail) ? kv("Qualité", qualityLine(detail)) : null,
      origins.length ? kv("Source", origins.map((o) => (o === "official" ? "site officiel" : o)).join(", ")) : null,
      last ? kv("Dernier téléchargement", when(last)) : null),
    h("p", { text: "Clique sur un épisode pour voir son détail ; Ctrl+clic pour en sélectionner plusieurs." }),
  ];
}

function sideEpisode(ctx, group, detail, ep) {
  const info = EPISODE[ep.status] || { label: ep.status };
  const main = majorityQuality(detail);
  const key = detail.series_key;
  const out = [h("h2", { text: `Épisode ${ep.n}${ep.duration_s ? ` · ${duration(ep.duration_s)}` : ""} · ${info.label}` })];
  const say = (text) => out.push(h("p", { text }));
  const actions = [];
  const retry = (label) => actions.push(h("button", { class: "btn btn-primary", type: "button", onclick: () => ctx.act.retry(key, { episodes: [ep.n] }, `Épisode ${ep.n} relancé`) }, icon("refresh"), label));
  switch (ep.status) {
    case "done":
    case "done_unverified":
      if (ep.status === "done_unverified") say(detail.from_official ? "Présent sur le disque, pas encore vérifié : le prochain téléchargement le confirmera." : "Téléchargé, mais sa durée n'a pas pu être vérifiée (série absente du site officiel).");
      else if (ep.quality_requested && ep.quality_requested !== ep.quality) say(`Téléchargé et vérifié en ${ep.quality} : le ${ep.quality_requested} n'était pas disponible.`);
      else say(`Téléchargé et vérifié${ep.quality ? ` · ${ep.quality}` : ""} · ${bytes(ep.bytes)}.`);
      actions.push(h("a", { class: "btn btn-primary", href: theaterHref(group, detail, ep.n) }, icon("play"), "Regarder"));
      if (ep.quality && main && ep.quality !== main) {
        say(`Le reste de la version est en ${main}. Pour un film sans ré-encodage, retélécharge-le en ${main}.`);
        actions.push(h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.act.redownload(key, [ep.n], main) }, icon("refresh"), `Retélécharger en ${main}`));
      }
      actions.push(h("button", { class: "btn btn-ghost", type: "button", onclick: () => ctx.act.open(key, "episode", { episode: ep.n }) }, icon("folder"), "Afficher dans le dossier"));
      actions.push(h("a", { class: "btn btn-ghost", href: `${ep.media_url}?download=1`, download: "" }, icon("download"), "Enregistrer"));
      break;
    case "missing":
      say(`Le fichier E${String(ep.n).padStart(3, "0")}.mp4 n'est plus dans le dossier (supprimé en dehors de l'appli ?).`);
      retry("Retélécharger");
      break;
    case "failed":
    case "unavailable":
      say(ERRORS[ep.error_code] || ERRORS.unknown);
      if (ep.status === "unavailable") say("On ne réessaie pas en boucle.");
      if (ep.attempts) out.push(h("p", { class: "note", text: `${plural(ep.attempts, "tentative", "tentatives")}.` }));
      retry(ep.status === "unavailable" ? "Réessayer maintenant" : "Réessayer");
      break;
    case "partial":
      say(`Interrompu · ${bytes(ep.part_bytes)} déjà reçus : le téléchargement reprendra là où il s'était arrêté.`);
      retry("Reprendre");
      break;
    case "downloading":
      say("En cours de téléchargement : il sera lisible dès qu'il sera vérifié.");
      break;
    case "queued":
      say("En file : il sera téléchargé dans la série en cours.");
      break;
    case "not_requested":
      say("Hors de la sélection demandée lors du téléchargement.");
      retry("Télécharger cet épisode");
      break;
    case "removed":
      say("Retiré pour libérer de la place ; le film le contient toujours.");
      retry("Retélécharger");
      break;
    default:
      say("Pas encore téléchargé.");
      retry("Télécharger");
  }
  if (ep.suspect) out.push(h("p", { class: "note", text: "Attention : la taille du fichier a changé depuis sa vérification." }));
  if (actions.length) out.push(h("div", { class: "btn-col" }, actions));
  if (ep.error) {
    out.push(h("details", {}, h("summary", { class: "note", text: "Détails techniques" }),
      h("p", { class: "note mono", text: ep.error }),
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: (e) => copyText(`Épisode ${ep.n} (${detail.series_key}) : ${ep.error_code} · ${ep.error}`, e.currentTarget) }, icon("copy", { size: 14 }), "Copier")));
  }
  return out;
}

function sideSelection(ctx, detail, sel) {
  const eps = detail.episodes.filter((e) => sel.has(e.n));
  const main = majorityQuality(detail) || "1080p";
  const toFetch = eps.filter((e) => !e.media_url).map((e) => e.n);
  const present = eps.filter((e) => e.media_url).map((e) => e.n);
  const size = eps.reduce((s, e) => s + (e.bytes || (e.duration_s ? e.duration_s * 124000 : 0)), 0);
  const redo = h("button", { class: "btn btn-secondary", type: "button", disabled: !present.length || null, "aria-haspopup": "menu" }, icon("refresh"), "Retélécharger en ▾");
  redo.addEventListener("click", () => openMenu(redo, ["1080p", "720p", "540p"].map((q) => ({ label: `${q}${q === main ? " (comme le reste)" : ""}`, onClick: () => ctx.act.redownload(detail.series_key, present, q) })), { label: "Qualité" }));
  return [
    h("h2", { text: `${plural(eps.length, "épisode", "épisodes")} · ≈ ${bytes(size)}` }),
    h("p", { text: ranges([...sel]) }),
    h("div", { class: "btn-col" },
      h("button", { class: "btn btn-primary", type: "button", disabled: !toFetch.length || null, onclick: () => ctx.act.retry(detail.series_key, { episodes: toFetch }, `${plural(toFetch.length, "épisode", "épisodes")} relancés`) },
        icon("download"), toFetch.length ? `Télécharger ou réessayer · ${toFetch.length}` : "Rien à télécharger"),
      redo),
  ];
}

// --- film ------------------------------------------------------------------------------------------------------------

function preflightRow(ok, label, detailText, warn = false) {
  const glyph = ok === null ? "info" : ok ? "check" : warn ? "alert" : "close";
  const tone = ok === null ? "info" : ok ? "ok" : warn ? "warning" : "danger";
  return h("li", { class: `prevol-row is-${tone}` }, icon(glyph, { size: 20 }), h("span", { class: "prevol-label", text: label }), h("span", { class: "prevol-detail", text: detailText }));
}

function formatText(plan) {
  const groups = plan.checks.format?.groups || [];
  if (groups.length <= 1) return groups[0] ? `Tous en ${groups[0].quality}` : "—";
  const sorted = [...groups].sort((a, b) => b.count - a.count);
  const [first, ...others] = sorted;
  return others.map((g) => `${g.count > 1 ? "Les épisodes" : "L'épisode"} ${g.episodes} ${g.count > 1 ? "sont" : "est"} en ${g.quality}`).join(" ; ") + `, les autres en ${first.quality}.`;
}

function filmSection(ctx, group, detail, ui) {
  const card = h("section", { class: "card film-card", id: "film", "aria-labelledby": "titre-film" });
  const title = h("h2", { class: "section-title", id: "titre-film" }, "Film");
  card.append(title);
  const film = detail.film;
  const key = detail.series_key;
  const k = counts(detail);
  const filmJob = ctx.state.jobs.active.find((j) => j.kind === "film" && j.series_key === key);
  const fetchJob = detail.job && detail.job.kind === "fetch" ? detail.job : null;

  if (filmJob) {
    const p = ctx.state.progress[filmJob.id];
    const pct = p?.seconds_total ? Math.round((p.seconds_done / p.seconds_total) * 100) : 0;
    title.append(h("span", { class: "badge badge-active", text: filmJob.status === "queued" ? "En file" : "En cours" }));
    const btn = h("div", { class: "btn btn-lg btn-primary btn-progress", role: "progressbar", "aria-valuenow": String(pct), "aria-valuemin": "0", "aria-valuemax": "100" },
      h("span", { text: filmJob.status === "queued" ? "En attente…" : `Assemblage… ${pct} %${p?.eta_s ? ` · ≈ ${duration(p.eta_s)}` : ""}` }));
    btn.style.setProperty("--p", (pct / 100).toFixed(3));
    card.append(h("div", { class: "btn-row" }, btn, h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.act.jobCommand(filmJob, "cancel"), text: "Annuler" })));
    return card;
  }

  if (film && ["ready", "partial", "stale"].includes(film.state)) {
    const badge = { ready: ["badge-success", "Prêt"], partial: ["badge-dashed", "Partiel"], stale: ["badge-warning", "Obsolète"] }[film.state];
    title.append(h("span", { class: `badge ${badge[0]}`, text: badge[1] }));
    const facts = [film.duration_s ? duration(film.duration_s) : null, film.bytes ? bytes(film.bytes) : null, film.chapters ? plural(film.chapters, "chapitre", "chapitres") : null].filter(Boolean).join(" · ");
    const sentence = film.state === "ready"
      ? `Film prêt : ${film.file}${facts ? ` · ${facts}` : ""}`
      : film.state === "partial"
        ? `Film partiel (épisodes ${film.episodes}) : ${film.file}${facts ? ` · ${facts}` : ""}`
        : `Film obsolète (épisodes ${film.episodes}) : ${film.added_since?.length ? `${plural(film.added_since.length, "épisode ajouté", "épisodes ajoutés")} depuis (${ranges(film.added_since)})` : "des épisodes ont changé depuis sa création"}.`;
    card.append(
      h("p", { class: "film-state", text: sentence }),
      h("div", { class: "btn-row" },
        h("a", { class: "btn btn-primary", href: theaterHref(group, detail, "film") }, icon("play"), "Regarder le film"),
        h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.act.open(key, "film") }, icon("folder"), "Afficher dans le dossier"),
        h("a", { class: "btn btn-ghost", href: `${film.media_url}?download=1`, download: "" }, icon("download"), "Enregistrer")),
    );
    if (film.state === "ready" && detail.episodes_bytes && !ui.dismissedFree()) {
      card.append(h("div", { class: "notice is-info" }, icon("info", { size: 20 }),
        h("p", { text: `Libérer ${bytes(detail.episodes_bytes)} en supprimant les épisodes ? Le film reste.` }),
        h("div", { class: "btn-row" },
          h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.deleteSeries(detail, "episodes"), text: "Libérer" }),
          h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => { ui.dismissFree(); ctx.rerender(); }, text: "Non merci" }))));
    }
    if (film.state === "ready") return card;
    card.append(h("h3", { class: "overline", text: "Recréer le film complet" }));
  } else if (film && film.state === "missing_file") {
    title.append(h("span", { class: "badge badge-danger", text: "Fichier disparu" }));
    card.append(h("p", { class: "film-state", text: `Le film « ${film.file} » n'est plus dans le dossier.` }));
  } else if (film && film.state === "outside") {
    title.append(h("span", { class: "badge badge-info", text: "Hors bibliothèque" }));
    card.append(h("p", { class: "film-state", text: "Ce film a été créé en dehors du dossier de la série." }),
      h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.act.open(key, "folder") }, icon("folder"), "Ouvrir le dossier"));
    return card;
  } else if (!k.present) {
    card.append(h("p", { class: "film-state", text: "Le film se crée une fois les épisodes téléchargés." }));
    return card;
  }
  if (fetchJob) {
    card.append(h("p", { class: "note", text: fetchJob.film_after
      ? "Le film sera créé automatiquement à la fin du téléchargement."
      : "Un téléchargement est en cours sur cette série : le film pourra être créé ici une fois terminé." }));
    return card;
  }

  // Pré-vol, calculé par le serveur sans réseau ni ffmpeg (lecture des boîtes MP4).
  const plan = ui.plan;
  if (!plan) {
    card.append(h("p", { class: "note", role: "status", text: "Vérification des épisodes…" }));
    ui.loadPlan();
    return card;
  }
  if (plan.error) {
    card.append(h("p", { class: "film-state", text: plan.error.message }));
    return card;
  }
  const c = plan.checks;
  const opts = ui.filmOptions;
  const outputName = opts.output_name || c.output.name;
  // Un film obsolète ou partiel sous le même nom est remplacé sans case à cocher.
  const implicitReplace = ["stale", "partial"].includes(film?.state) && outputName === film.file;
  const missing = c.episodes.missing || [];
  const nameEdit = h("input", { class: "text-field", type: "text", value: opts.output_name || c.output.name, "aria-label": "Nom du film", hidden: !ui.editName || null });
  nameEdit.addEventListener("change", () => { opts.output_name = nameEdit.value.trim() || null; ui.reloadPlan(); });
  const rows = [
    preflightRow(c.episodes.ok, "Épisodes", c.episodes.ok ? `${c.episodes.present} présents` : `${plural(missing.length, "absent", "absents")} : ${ranges(missing)}`),
    preflightRow(c.format.ok || opts.reencode, "Format", c.format.ok ? formatText(plan) : `${formatText(plan)}${opts.reencode ? " (ré-encodage choisi)" : ""}`),
    preflightRow(c.ffmpeg.ok, "ffmpeg", c.ffmpeg.ok ? `prêt (${c.ffmpeg.source === "PATH" ? "via PATH" : c.ffmpeg.source})` : "absent"),
    preflightRow(c.disk.ok, "Espace", `≈ ${bytes(c.disk.needed_bytes)} nécessaires · ${bytes(c.disk.free_bytes)} libres`),
    h("li", { class: `prevol-row is-${c.output.exists && !implicitReplace ? "warning" : "info"}` }, icon(c.output.exists && !implicitReplace ? "alert" : "film", { size: 20 }), h("span", { class: "prevol-label", text: "Nom" }),
      h("span", { class: "prevol-detail" }, c.output.exists ? `${implicitReplace ? "Remplace le film actuel" : "Un film porte déjà ce nom"} : ${outputName}` : outputName, " ",
        h("button", { class: "link-btn", type: "button", onclick: () => { ui.editName = !ui.editName; ctx.rerender(); }, text: ui.editName ? "Fermer" : "Modifier" }), nameEdit)),
    preflightRow(opts.chapters ? true : null, "Chapitres", opts.chapters ? `${plural(c.chapters, "chapitre", "chapitres")} « Épisode N »` : "sans chapitres"),
  ];
  card.append(h("ul", { class: "prevol" }, rows));
  const replaceBox = c.output.exists && !implicitReplace
    ? h("label", { class: "check-inline" }, h("input", { type: "checkbox", checked: opts.replace || null, onchange: (e) => { opts.replace = e.target.checked; ctx.rerender(); } }), "Remplacer le film existant")
    : null;
  if (replaceBox) card.append(replaceBox);
  if (!c.ffmpeg.ok) {
    card.append(h("div", { class: "notice is-warning" }, icon("alert", { size: 20 }),
      h("div", {}, h("p", { text: "Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans." }),
        codeBox("winget install Gyan.FFmpeg", "Copier"), codeBox("pip install imageio-ffmpeg", "Copier"),
        h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ui.reloadPlan(), text: "Vérifier à nouveau" }))));
  }
  if (ui.filmError) card.append(h("div", { class: "notice is-danger", role: "alert" }, icon("alert", { size: 20 }), h("p", { text: ui.filmError })));

  const create = async (extra = {}) => {
    ui.filmError = null;
    try {
      await ctx.act.createFilm(key, { chapters: opts.chapters, output_name: opts.output_name, reencode: opts.reencode, allow_missing: opts.allow_missing, replace: opts.replace || implicitReplace, ...extra });
    } catch (err) {
      ui.filmError = err instanceof ApiError ? err.message : String(err);
    }
    ctx.rerender();
  };
  const remedies = h("div", { class: "remedies" });
  const blockedByName = c.output.exists && !opts.replace && !(film && ["stale", "partial"].includes(film.state));
  if (plan.can_build && c.ffmpeg.ok) {
    remedies.append(h("div", { class: "remedy" },
      h("button", { class: "btn btn-lg btn-primary", type: "button", disabled: blockedByName || null, onclick: () => create() }, icon("film"), film ? "Recréer le film complet" : "Créer le film"),
      blockedByName ? h("span", { class: "remedy-note", text: "Coche « Remplacer » ou change le nom." }) : h("span", { class: "remedy-note", text: `Réunit ${plural(c.episodes.present, "épisode", "épisodes")} en un seul fichier${plan.duration_s ? ` (${duration(plan.duration_s)})` : ""}, en quelques secondes.` })));
  }
  for (const fix of plan.fixes || []) {
    if (fix.action === "repair_then_film") {
      const parts = [];
      if (fix.download?.length) parts.push(`télécharge ${ranges(fix.download)}`);
      if (fix.redownload?.length) parts.push(`retélécharge ${ranges(fix.redownload)} en ${fix.quality}`);
      remedies.append(h("div", { class: "remedy" },
        h("button", { class: "btn btn-lg btn-primary", type: "button", onclick: () => ctx.act.retry(key, { episodes: fix.download?.length ? fix.download : null, redownload: fix.redownload, quality: fix.quality, film_after: true }, "Réparation puis film") },
          icon("refresh"), fix.label),
        h("span", { class: "remedy-note", text: `${capitalize(parts.join(", "))}, puis crée le film.` })));
    } else if (fix.action === "allow_missing") {
      remedies.append(h("div", { class: "remedy" },
        h("button", { class: "btn btn-secondary", type: "button", disabled: !c.ffmpeg.ok || null, onclick: () => create({ allow_missing: true, replace: true }) }, fix.label),
        h("span", { class: "remedy-note", text: fix.output_name })));
    } else if (fix.action === "reencode") {
      remedies.append(h("div", { class: "remedy" },
        h("button", { class: "btn btn-secondary", type: "button", disabled: !fix.enabled || !c.ffmpeg.ok || null, "aria-describedby": fix.reason ? `raison-${fix.action}` : null, onclick: () => create({ reencode: true }) }, fix.label),
        fix.reason ? h("span", { class: "remedy-note", id: `raison-${fix.action}`, text: fix.reason }) : null));
    }
  }
  card.append(remedies);

  const options = h("details", { class: "film-options", open: ui.optionsOpen || null, ontoggle: (e) => { ui.optionsOpen = e.target.open; } },
    h("summary", { text: "Options du film" }),
    h("label", { class: "check-inline" }, h("input", { type: "checkbox", checked: opts.chapters, onchange: (e) => { opts.chapters = e.target.checked; ctx.rerender(); } }), "Un chapitre par épisode"),
    h("label", { class: "check-inline" }, h("input", { type: "checkbox", checked: opts.reencode || null, onchange: (e) => { opts.reencode = e.target.checked; ui.reloadPlan(); } }), "Ré-encoder (plus lent : nécessaire si les qualités sont mélangées)"),
    h("label", { class: "check-inline" }, h("input", { type: "checkbox", checked: opts.allow_missing || null, onchange: (e) => { opts.allow_missing = e.target.checked; ui.reloadPlan(); } }), "Autoriser un film partiel"),
    codeBox(`python -m shortdramagen film "${detail.path}"${opts.reencode ? " --reencode" : ""}${opts.allow_missing ? " --allow-missing" : ""}${opts.chapters ? "" : " --no-chapters"}`, "Copier la commande"));
  card.append(options);
  return card;
}

// --- stockage et détails ---------------------------------------------------------------------------------------------------

function storageSection(ctx, detail) {
  const filmReady = detail.film?.state === "ready";
  return h(
    "section",
    { class: "card", "aria-labelledby": "titre-stockage" },
    h("h2", { class: "section-title", id: "titre-stockage", text: "Stockage" }),
    h("dl", {}, kv("Épisodes", bytes(detail.episodes_bytes)), kv("Film", detail.film?.bytes ? bytes(detail.film.bytes) : "—"), kv("Fichiers partiels", bytes(detail.parts_bytes))),
    codeBox(detail.path, "Copier le chemin du dossier"),
    h("div", { class: "btn-row" },
      h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.act.open(detail.series_key, "folder") }, icon("folder"), "Ouvrir le dossier"),
      filmReady && detail.episodes_bytes ? h("button", { class: "btn btn-secondary", type: "button", onclick: () => openDeleteDialog(ctx, [detail]) }, `Libérer ${bytes(detail.episodes_bytes)} (garder le film)`) : null,
      detail.parts_bytes && !detail.job ? h("button", { class: "btn btn-ghost", type: "button", onclick: () => ctx.act.deleteSeries(detail, "parts") }, `Supprimer les fichiers partiels · ${bytes(detail.parts_bytes)}`) : null,
      h("button", { class: "btn btn-danger-ghost", type: "button", onclick: () => openDeleteDialog(ctx, [detail]) }, icon("trash"), "Supprimer…")),
  );
}

function techSection(detail) {
  const origins = {};
  for (const e of detail.episodes) {
    if (!e.media_url) continue;
    const key = `${e.origin === "official" ? "site officiel" : e.origin || "?"}|${e.quality || "?"}`;
    origins[key] = (origins[key] || []).concat(e.n);
  }
  return h(
    "details",
    { class: "tech" },
    h("summary", { text: "Détails techniques" }),
    h("div", {},
      h("dl", {},
        kv("N° de série", detail.book_id),
        kv("N° vidéo de la version", detail.source_book_id),
        kv("Langue", detail.lang ? `${langName(detail.lang)} (${detail.lang})` : "—"),
        kv("Dossier", detail.series_key),
        detail.requested?.at ? kv("Dernière demande", when(detail.requested.at)) : null,
        detail.url_expires_at_min ? kv("Liens de la source valables jusqu'au", fullDate(detail.url_expires_at_min)) : null),
      Object.keys(origins).length
        ? h("table", { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { text: "Origine" }), h("th", { text: "Qualité" }), h("th", { text: "Épisodes" }))),
            h("tbody", {}, Object.entries(origins).map(([key, list]) => {
              const [origin, quality] = key.split("|");
              return h("tr", {}, h("td", { text: origin }), h("td", { text: quality }), h("td", { text: ranges(list) }));
            })))
        : null,
      h("p", { class: "note", text: "Commande équivalente :" }),
      codeBox(fetchCommand(detail), "Copier la commande")),
  );
}

// --- page ------------------------------------------------------------------------------------------------------------------------

export function renderSeries(main, ctx, { group, detail, ui }) {
  const side = h("aside", { class: "side", "aria-label": "Détail", "aria-live": "polite" });
  const fillSide = () => {
    clear(side);
    if (ui.selection.size) append(side, sideSelection(ctx, detail, ui.selection));
    else {
      const ep = detail.episodes.find((e) => e.n === ui.shown);
      append(side, ep ? sideEpisode(ctx, group, detail, ep) : sideSummary(detail));
    }
  };
  ui.bind(detail, fillSide);
  fillSide();
  main.append(h(
    "div",
    { class: "page" },
    h("a", { class: "back", href: "#/" }, icon("back"), "Bibliothèque"),
    hero(ctx, group, detail),
    healthBar(ctx, group, detail),
    h("div", { class: "cols" },
      h("div", { class: "col-main" }, episodesSection(ctx, group, detail, ui), filmSection(ctx, group, detail, ui), storageSection(ctx, detail), techSection(detail)),
      side),
  ));
}

// État d'interface d'une fiche (sélection, épisode montré, options du film), gardé entre deux rendus.
export function seriesUi(ctx, key) {
  const ui = {
    key,
    selection: new Set(),
    shown: null,
    focusN: null,
    anchor: null,
    plan: null,
    planVersion: null,
    filmOptions: { chapters: true, reencode: false, allow_missing: false, replace: false, output_name: null },
    filmError: null,
    editName: false,
    optionsOpen: false,
    detail: null,
    fillSide: null,
    bind(detail, fillSide) {
      this.detail = detail;
      this.fillSide = fillSide;
      const version = ctx.state.library?.version;
      if (this.planVersion !== version) {
        this.plan = null;
        this.planVersion = version;
      }
    },
    show(n, rerender = true) {
      this.shown = n;
      if (rerender || this.fillSide) this.fillSide?.();
    },
    select(list, replace = true) {
      this.selection = replace ? new Set(list) : new Set([...this.selection, ...list]);
      this.anchor = list.length ? list[list.length - 1] : null;
      ctx.rerender();
    },
    toggle(n) {
      this.selection.has(n) ? this.selection.delete(n) : this.selection.add(n);
      this.anchor = n;
      ctx.rerender();
    },
    extend(n) {
      const a = Math.min(this.anchor ?? n, n);
      const b = Math.max(this.anchor ?? n, n);
      for (let i = a; i <= b; i++) if (this.detail.episodes.some((e) => e.n === i)) this.selection.add(i);
      ctx.rerender();
    },
    async loadPlan() {
      if (this.loadingPlan) return;
      this.loadingPlan = true;
      const o = this.filmOptions;
      try {
        const res = await get(`/api/series/${encodeURIComponent(key)}/film/plan?reencode=${o.reencode ? 1 : 0}&allow_missing=${o.allow_missing ? 1 : 0}`);
        this.plan = res.data.error ? { error: res.data.error } : res.data;
      } catch (err) {
        this.plan = { error: { message: err.message } };
      }
      this.loadingPlan = false;
      ctx.rerender();
    },
    reloadPlan() {
      this.plan = null;
      ctx.rerender();
    },
    dismissedFree() {
      try {
        return localStorage.getItem(`sdg.libérer.${key}`) === "1";
      } catch {
        return false;
      }
    },
    dismissFree() {
      try {
        localStorage.setItem(`sdg.libérer.${key}`, "1");
      } catch {
        /* réglage de confort : pas grave s'il n'est pas gardé */
      }
    },
  };
  return ui;
}

export function renderMissing(main, text) {
  main.append(
    h("div", { class: "page" },
      h("a", { class: "back", href: "#/" }, icon("back"), "Bibliothèque"),
      h("section", { class: "empty", role: "alert" }, h("h2", { tabindex: "-1", "data-autofocus": true, text: "Série introuvable" }), h("p", { text }))),
  );
}
