// Fiche série (spec E3, E4 en lecture) : héros, versions, santé, grille d'épisodes, film, stockage.

import { h, icon, codeBox, clear } from "../dom.js";
import { bytes, capitalize, duration, fullDate, htmlLang, langName, plural, ranges, versionLong, versionSlug, when } from "../format.js";
import { EPISODE, ERRORS, counts } from "../status.js";

export function theaterHref(group, version, target) {
  return `#/serie/${group.book_id}/${versionSlug(version)}/lire/${target}`;
}

function majorityQuality(detail) {
  return Object.keys(detail.qualities || {})[0] || null;
}

function fetchCommand(detail, extra = "") {
  const lang = detail.is_original ? "" : ` --lang ${detail.lang}`;
  const quality = detail.requested?.quality && detail.requested.quality !== "best" ? ` -q ${detail.requested.quality}` : "";
  return `python -m shortdramagen fetch ${detail.book_id}${lang}${quality}${extra}`;
}

function filmCommand(detail, replace = false) {
  return `python -m shortdramagen film "${detail.path}"${replace ? " --replace" : ""}`;
}

// --- héros et versions --------------------------------------------------------------

function hero(group, detail) {
  const coverUrl = detail.cover_url || group.cover_url;
  const title = h("h1", { tabindex: "-1", "data-autofocus": true, lang: htmlLang(detail.lang), text: detail.title });
  const meta = [
    plural(detail.counts.total, "épisode", "épisodes"),
    detail.duration_s ? duration(detail.duration_s) : null,
    detail.bytes ? bytes(detail.bytes) : null,
    qualityLine(detail),
  ].filter(Boolean);
  const syn = detail.introduction ? h("p", { class: "syn", lang: htmlLang(detail.lang), text: detail.introduction }) : null;
  const more = syn
    ? h("button", {
        class: "link-btn", type: "button", "aria-expanded": "false",
        onclick: (e) => {
          const open = syn.classList.toggle("is-open");
          e.currentTarget.textContent = open ? "Réduire" : "Lire plus";
          e.currentTarget.setAttribute("aria-expanded", String(open));
        },
        text: "Lire plus",
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
      Object.assign(title, { id: "titre-serie" }),
      detail.title_vo && detail.title_vo !== detail.title ? h("p", { class: "hero-vo", lang: "en", text: `${detail.title_vo} · titre original` }) : null,
      h("div", { class: "hero-meta num" }, meta.map((m) => h("span", { text: m }))),
      syn,
      more && syn.textContent.length > 220 ? more : null,
      tabs(group, detail),
    ),
  );
}

function qualityLine(detail) {
  const q = Object.entries(detail.qualities || {});
  if (!q.length) return null;
  const [main, ...others] = q;
  if (!others.length) return main[0];
  const n = others.reduce((s, [, c]) => s + c, 0);
  return `${main[0]} (${plural(n, "ép.", "ép.")} en ${others.map(([k]) => k).join(", ")})`;
}

function tabs(group, detail) {
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
  const have = new Set(group.versions.map((v) => v.lang));
  const others = (group.languages_available || []).filter((l) => !have.has(l));
  if (others.length) {
    items.push(h("span", { class: "tab is-other", title: "Téléchargement d'une autre langue : bientôt depuis l'interface" }, `Aussi en : ${others.map(langName).join(", ")}`));
  }
  return h("nav", { class: "tabs", "aria-label": "Versions" }, items);
}

// --- barre de santé ---------------------------------------------------------------------

function healthBar(group, detail) {
  const c = detail.counts;
  const k = counts(detail);
  const byStatus = (s) => detail.episodes.filter((e) => e.status === s).map((e) => e.n);
  const parts = [];
  let tone = "ok";
  let glyph = "check";
  if (detail.state === "complete") {
    parts.push(`${k.present}/${k.total} téléchargés${detail.from_official ? " et vérifiés" : ""}`);
    if (detail.duration_s) parts.push(duration(detail.duration_s));
    parts.push(bytes(detail.episodes_bytes));
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
    tone = tone === "ok" ? "info" : tone;
    parts.push("durées non vérifiées : série absente du site officiel");
  }

  const actions = [];
  const film = detail.film;
  if (film && ["ready", "partial", "stale"].includes(film.state)) {
    actions.push(h("a", { class: "btn btn-primary", href: theaterHref(group, detail, "film") }, icon("play"), film.state === "ready" ? "Regarder le film" : `Regarder le film (ép. ${film.episodes})`));
  }
  const first = detail.episodes.find((e) => e.media_url);
  if (first) {
    actions.push(h("a", { class: `btn ${actions.length ? "btn-secondary" : "btn-primary"}`, href: theaterHref(group, detail, first.n) }, icon("play"), `Épisode ${first.n}`));
  }
  return h(
    "section",
    { class: "health", "aria-label": "État de la version" },
    h("p", { class: `health-text is-${tone}` }, icon(glyph), h("span", { text: capitalize(parts.join(" · ")) })),
    h("div", { class: "btn-row" }, actions),
  );
}

// --- épisodes -------------------------------------------------------------------------

function tile(ep, main, onActivate, onFocus) {
  const info = EPISODE[ep.status] || { label: ep.status };
  const odd = ep.media_url && ep.quality && main && ep.quality !== main;
  const label = [`Épisode ${ep.n}`, info.label, ep.duration_s ? duration(ep.duration_s) : null, odd ? ep.quality : null].filter(Boolean).join(" · ");
  const button = h(
    "button",
    { class: `tile${odd ? " has-q" : ""}${ep.suspect ? " is-suspect" : ""}`, type: "button", "aria-label": label, title: label, dataset: { status: ep.status, n: ep.n } },
    h("span", { text: ep.n }),
    info.glyph ? h("span", { class: "glyph" }, icon(info.glyph)) : null,
    odd ? h("span", { class: "q-badge", "aria-hidden": "true", text: ep.quality.replace("p", "") }) : null,
  );
  button.addEventListener("click", () => onActivate(ep));
  button.addEventListener("focus", () => onFocus(ep));
  return button;
}

function episodesSection(detail, onActivate, onFocus) {
  const main = majorityQuality(detail);
  const legendItems = [
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
    .map(([status, cls, label]) => [detail.counts[status], cls, label])
    .filter(([n]) => n)
    .map(([n, cls, label]) => h("span", { class: `badge ${cls}` }, `${label} `, h("span", { class: "num", text: n })));

  const rows = new Map();
  for (const ep of detail.episodes) {
    const row = Math.floor((ep.n - 1) / 10);
    if (!rows.has(row)) rows.set(row, []);
    rows.get(row).push(ep);
  }
  const grid = h(
    "div",
    { class: "grid", role: "group", "aria-label": "Épisodes" },
    [...rows.entries()].map(([row, eps]) =>
      h(
        "div",
        { class: "grid-row" },
        h("span", { class: "row-label", "aria-hidden": "true", text: `${row * 10 + 1}–${row * 10 + 10}` }),
        h("div", { class: "tiles" }, eps.map((ep) => tile(ep, main, onActivate, onFocus))),
      ),
    ),
  );
  return h(
    "section",
    { "aria-labelledby": "titre-episodes" },
    h("h2", { class: "section-title", id: "titre-episodes", text: "Épisodes" }),
    legend.length ? h("div", { class: "legend" }, legend) : null,
    grid,
    h("p", { class: "note", text: "Clique sur un épisode téléchargé pour le regarder ; les autres affichent leur détail dans le volet." }),
  );
}

// --- volet contextuel ---------------------------------------------------------------

function sideSummary(detail) {
  const k = counts(detail);
  const last = detail.episodes.map((e) => e.finished_at).filter(Boolean).sort().pop();
  const origins = [...new Set(detail.episodes.filter((e) => e.origin).map((e) => e.origin))];
  return [
    h("h2", { text: `Résumé · ${versionLong(detail)}` }),
    h(
      "dl",
      {},
      kv("Présents", `${k.present}/${k.total}`),
      kv("Taille", bytes(detail.episodes_bytes)),
      qualityLine(detail) ? kv("Qualité", qualityLine(detail)) : null,
      origins.length ? kv("Source", origins.map((o) => (o === "official" ? "site officiel" : o)).join(", ")) : null,
      last ? kv("Dernier téléchargement", when(last)) : null,
    ),
    h("p", { text: "Sélectionne un épisode (Tab ou clic) pour voir son détail." }),
  ];
}

function kv(label, value) {
  return h("div", { class: "kv" }, h("dt", { text: label }), h("dd", { text: value }));
}

function sideEpisode(group, detail, ep) {
  const info = EPISODE[ep.status] || { label: ep.status };
  const main = majorityQuality(detail);
  const out = [h("h2", { text: `Épisode ${ep.n}${ep.duration_s ? ` · ${duration(ep.duration_s)}` : ""} · ${info.label}` })];
  const say = (text) => out.push(h("p", { text }));
  switch (ep.status) {
    case "done":
      if (ep.quality_requested && ep.quality_requested !== ep.quality) say(`Téléchargé et vérifié en ${ep.quality} : le ${ep.quality_requested} n'était pas disponible.`);
      else say(`Téléchargé et vérifié${ep.quality ? ` · ${ep.quality}` : ""} · ${bytes(ep.bytes)}.`);
      if (ep.quality && main && ep.quality !== main) say(`Le reste de la version est en ${main} : pour créer le film sans ré-encodage, il faudra le retélécharger en ${main}.`);
      break;
    case "done_unverified":
      say(detail.from_official ? "Présent sur le disque, pas encore vérifié : le prochain téléchargement le confirmera." : "Téléchargé, mais sa durée n'a pas pu être vérifiée (série absente du site officiel).");
      break;
    case "missing":
      say(`Le fichier E${String(ep.n).padStart(3, "0")}.mp4 n'est plus dans le dossier (supprimé en dehors de l'appli ?).`);
      break;
    case "failed":
    case "unavailable":
      say(ERRORS[ep.error_code] || ERRORS.unknown);
      if (ep.attempts) out.push(h("p", { class: "note", text: `${plural(ep.attempts, "tentative", "tentatives")}.` }));
      break;
    case "partial":
      say(`Interrompu · ${bytes(ep.part_bytes)} déjà reçus : le téléchargement reprendra là où il s'était arrêté.`);
      break;
    case "not_requested":
      say("Hors de la sélection demandée lors du téléchargement.");
      break;
    case "removed":
      say("Retiré pour libérer de la place ; le film le contient toujours.");
      break;
    default:
      say("Pas encore téléchargé.");
  }
  if (ep.suspect) out.push(h("p", { class: "note", text: "Attention : la taille du fichier a changé depuis sa vérification." }));
  if (ep.media_url) {
    out.push(
      h(
        "div",
        { class: "btn-row" },
        h("a", { class: "btn btn-primary", href: theaterHref(group, detail, ep.n) }, icon("play"), "Regarder"),
        h("a", { class: "btn btn-secondary", href: `${ep.media_url}?download=1`, download: "" }, icon("download"), "Enregistrer"),
      ),
    );
  } else if (ep.status !== "removed") {
    out.push(h("p", { class: "note", text: "Pour le (re)télécharger, en attendant les actions dans l'interface :" }));
    out.push(codeBox(fetchCommand(detail, ` -e ${ep.n}`), "Copier la commande"));
  }
  if (ep.error) {
    out.push(h("details", {}, h("summary", { class: "note", text: "Détails techniques" }), h("p", { class: "note mono", text: ep.error })));
  }
  return out;
}

// --- film, stockage, détails -----------------------------------------------------------

function filmSection(group, detail) {
  const film = detail.film;
  const card = h("section", { class: "card", "aria-labelledby": "titre-film" });
  const title = h("h2", { class: "section-title", id: "titre-film" }, "Film");
  card.append(title);
  const k = counts(detail);
  if (!film) {
    title.append(h("span", { class: "badge badge-dashed", text: "Pas encore créé" }));
    if (k.present === k.total && k.total) {
      card.append(h("p", { class: "film-state", text: `Réunis les ${k.total} épisodes en un seul fichier${detail.duration_s ? ` (${duration(detail.duration_s)})` : ""}, un chapitre par épisode, en quelques secondes.` }));
    } else {
      card.append(h("p", { class: "film-state", text: `Il manque ${plural(k.total - k.present, "épisode", "épisodes")} pour un film complet.` }));
    }
    card.append(h("p", { class: "note", text: "Création depuis l'interface : bientôt. En attendant, dans un terminal :" }), codeBox(filmCommand(detail) + (k.present < k.total ? " --allow-missing" : ""), "Copier la commande"));
    return card;
  }
  const badge = {
    ready: ["badge-success", "Prêt"],
    partial: ["badge-warning", "Partiel"],
    stale: ["badge-warning", "Obsolète"],
    missing_file: ["badge-danger", "Fichier disparu"],
    outside: ["badge-info", "Hors bibliothèque"],
  }[film.state] || ["badge", film.state];
  title.append(h("span", { class: `badge ${badge[0]}`, text: badge[1] }));
  const facts = [film.duration_s ? duration(film.duration_s) : null, film.bytes ? bytes(film.bytes) : null, film.chapters ? plural(film.chapters, "chapitre", "chapitres") : null].filter(Boolean).join(" · ");
  const play = () =>
    h(
      "div",
      { class: "btn-row" },
      h("a", { class: "btn btn-primary", href: theaterHref(group, detail, "film") }, icon("play"), "Regarder le film"),
      h("a", { class: "btn btn-secondary", href: `${film.media_url}?download=1`, download: "" }, icon("download"), "Enregistrer"),
    );
  switch (film.state) {
    case "ready":
      card.append(h("p", { class: "film-state" }, "Film prêt : ", h("strong", { text: film.file }), facts ? ` · ${facts}` : ""), play());
      break;
    case "partial":
      card.append(h("p", { class: "film-state" }, `Film partiel (épisodes ${film.episodes}) : `, h("strong", { text: film.file }), facts ? ` · ${facts}` : ""), play());
      break;
    case "stale": {
      const added = film.added_since || [];
      const why = added.length ? `${plural(added.length, "épisode ajouté", "épisodes ajoutés")} depuis (${ranges(added)})` : "des épisodes ont changé depuis sa création";
      card.append(h("p", { class: "film-state", text: `Film obsolète (épisodes ${film.episodes}) : ${why}.` }), play());
      card.append(h("p", { class: "note", text: "Pour le recréer avec tous les épisodes présents :" }), codeBox(filmCommand(detail, true) + (k.present < k.total ? " --allow-missing" : ""), "Copier la commande"));
      break;
    }
    case "missing_file":
      card.append(h("p", { class: "film-state", text: `Le film « ${film.file} » n'est plus dans le dossier.` }), codeBox(filmCommand(detail), "Copier la commande"));
      break;
    case "outside":
      card.append(h("p", { class: "film-state", text: `Ce film (${film.file}) a été créé en dehors du dossier de la série : il n'est pas lisible ici.` }));
      break;
    default:
      break;
  }
  return card;
}

function storageSection(detail) {
  return h(
    "section",
    { class: "card", "aria-labelledby": "titre-stockage" },
    h("h2", { class: "section-title", id: "titre-stockage", text: "Stockage" }),
    h(
      "dl",
      {},
      kv("Épisodes", bytes(detail.episodes_bytes)),
      kv("Film", detail.film?.bytes ? bytes(detail.film.bytes) : "—"),
      kv("Fichiers partiels", bytes(detail.parts_bytes)),
    ),
    codeBox(detail.path, "Copier le chemin du dossier"),
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
    h(
      "div",
      {},
      h(
        "dl",
        {},
        kv("N° de série", detail.book_id),
        kv("N° vidéo de la version", detail.source_book_id),
        kv("Langue", detail.lang ? `${langName(detail.lang)} (${detail.lang})` : "—"),
        kv("Dossier", detail.series_key),
        detail.requested?.at ? kv("Dernière demande", when(detail.requested.at)) : null,
        detail.url_expires_at_min ? kv("Liens de la source valables jusqu'au", fullDate(detail.url_expires_at_min)) : null,
      ),
      Object.keys(origins).length
        ? h(
            "table",
            { class: "table" },
            h("thead", {}, h("tr", {}, h("th", { text: "Origine" }), h("th", { text: "Qualité" }), h("th", { text: "Épisodes" }))),
            h("tbody", {}, Object.entries(origins).map(([key, list]) => {
              const [origin, quality] = key.split("|");
              return h("tr", {}, h("td", { text: origin }), h("td", { text: quality }), h("td", { text: ranges(list) }));
            })),
          )
        : null,
      h("p", { class: "note", text: "Commande équivalente :" }),
      codeBox(fetchCommand(detail), "Copier la commande"),
    ),
  );
}

// --- page ---------------------------------------------------------------------------------

export function renderSeries(main, { group, detail, selected, onSelect, openEpisode }) {
  const side = h("aside", { class: "side", "aria-label": "Détail", "aria-live": "polite" });
  const showSide = (ep) => {
    clear(side);
    side.append(...(ep ? sideEpisode(group, detail, ep) : sideSummary(detail)));
  };
  const activate = (ep) => {
    if (ep.media_url) openEpisode(ep.n);
    else {
      onSelect(ep.n);
      showSide(ep);
    }
  };
  const focus = (ep) => {
    onSelect(ep.n);
    showSide(ep);
  };
  showSide(detail.episodes.find((e) => e.n === selected) || null);

  const page = h(
    "div",
    { class: "page" },
    h("a", { class: "back", href: "#/" }, icon("back"), "Bibliothèque"),
    hero(group, detail),
    healthBar(group, detail),
    h(
      "div",
      { class: "cols" },
      h("div", { class: "col-main" }, episodesSection(detail, activate, focus), filmSection(group, detail), storageSection(detail), techSection(detail)),
      side,
    ),
  );
  main.append(page);
}

export function renderMissing(main, text) {
  main.append(
    h(
      "div",
      { class: "page" },
      h("a", { class: "back", href: "#/" }, icon("back"), "Bibliothèque"),
      h("section", { class: "empty", role: "alert" }, h("h2", { tabindex: "-1", "data-autofocus": true, text: "Série introuvable" }), h("p", { text })),
    ),
  );
}
