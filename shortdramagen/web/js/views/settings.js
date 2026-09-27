// Réglages et santé (spec E7) : enregistrement automatique, erreur sous le champ concerné.

import { ApiError, get } from "../api.js";
import { append, codeBox, h, icon } from "../dom.js";
import { bytes, capitalize, langName, when } from "../format.js";

const SECTIONS = [
  ["general", "Général"],
  ["telechargement", "Téléchargement"],
  ["film", "Film"],
  ["stockage", "Stockage"],
  ["affichage", "Affichage"],
  ["clavier", "Clavier"],
  ["accessibilite", "Accessibilité"],
  ["sante", "Santé"],
  ["apropos", "À propos"],
];

function status(el, text, tone = "ok") {
  el.textContent = text;
  el.className = `save-status is-${tone}`;
  if (tone === "ok") setTimeout(() => { if (el.textContent === text) el.textContent = ""; }, 2000);
}

// Un champ de réglage : control + message d'état ; save(value) envoie { field: value }.
function row(ctx, field, label, control, help) {
  const msg = h("span", { class: "save-status", role: "status", id: `msg-${field}` });
  control.setAttribute("aria-describedby", `msg-${field}${help ? ` aide-${field}` : ""}`);
  const save = async (value) => {
    try {
      await ctx.act.settings({ [field]: value });
      status(msg, "Enregistré.");
    } catch (err) {
      status(msg, err instanceof ApiError ? err.message : "Réglage non enregistré.", "error");
    }
  };
  return {
    save,
    el: h("div", { class: "setting" },
      h("label", { class: "setting-label", for: control.id || null, text: label }),
      h("div", { class: "setting-control" }, control, msg, help ? h("p", { class: "field-help", id: `aide-${field}`, text: help }) : null)),
  };
}

function switchRow(ctx, s, field, label, help) {
  const input = h("button", { class: "switch", type: "button", role: "switch", id: `set-${field}`, "aria-checked": String(Boolean(s[field])) });
  const r = row(ctx, field, label, input, help);
  input.addEventListener("click", () => {
    const next = input.getAttribute("aria-checked") !== "true";
    input.setAttribute("aria-checked", String(next));
    r.save(next);
  });
  return r.el;
}

function selectRow(ctx, s, field, label, options, help, map = (v) => v, toValue = (v) => v) {
  const select = h("select", { id: `set-${field}` }, options.map(([value, text]) => h("option", { value, selected: String(map(s[field]) ?? "") === value, text })));
  const r = row(ctx, field, label, h("span", { class: "select select-md" }, select), help);
  select.addEventListener("change", () => r.save(toValue(select.value)));
  return r.el;
}

function numberRow(ctx, s, field, label, min, max, help, suffix = "") {
  const input = h("input", { class: "text-field num-field", type: "number", id: `set-${field}`, min, max, value: s[field] });
  const r = row(ctx, field, label, h("span", { class: "inline-field" }, input, suffix ? h("span", { class: "muted", text: suffix }) : null), help);
  input.addEventListener("change", () => r.save(Number(input.value)));
  return r.el;
}

function textRow(ctx, s, field, label, help, placeholder = "") {
  const input = h("input", { class: "text-field mono", type: "text", id: `set-${field}`, value: s[field] || "", placeholder, spellcheck: "false" });
  const button = h("button", { class: "btn btn-secondary", type: "button", text: "Enregistrer" });
  const r = row(ctx, field, label, h("span", { class: "inline-field" }, input, button), help);
  const go = () => r.save(input.value.trim() || null);
  button.addEventListener("click", go);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } });
  return r.el;
}

function healthBlock(ctx, health) {
  const ok = (v) => (v === null || v === undefined ? "info" : v ? "ok" : "danger");
  const line = (state, label, text) => h("li", { class: `prevol-row is-${state}` }, icon(state === "ok" ? "check" : state === "info" ? "info" : "alert", { size: 20 }), h("span", { class: "prevol-label", text: label }), h("span", { class: "prevol-detail", text }));
  const ff = health.ffmpeg || {};
  const checked = health.checked_at ? ` (vérifié ${when(health.checked_at)})` : "";
  const recheck = h("button", { class: "btn btn-secondary", type: "button" }, icon("refresh"), "Tout revérifier");
  recheck.addEventListener("click", async () => {
    recheck.disabled = true;
    try {
      ctx.onHealth((await get("/api/health?check=1")).data);
    } finally {
      recheck.disabled = false;
    }
  });
  return h("section", { class: "card health-card", "aria-labelledby": "titre-sante" },
    h("h2", { class: "section-title", id: "titre-sante", text: "Santé" }),
    h("ul", { class: "prevol" },
      line(ff.found ? "ok" : "warning", "ffmpeg", ff.found ? `prêt · ${ff.path} (${ff.source === "PATH" ? "via PATH" : ff.source})` : "absent : nécessaire seulement pour créer des films"),
      line(ok(health.downloads_dir_ok), "Dossier", health.downloads_dir_ok ? "accessible" : "introuvable ou inaccessible"),
      line(health.free_bytes === null ? "info" : health.free_bytes > 2e9 ? "ok" : "warning", "Espace libre", health.free_bytes === null ? "—" : bytes(health.free_bytes)),
      line(ok(health.official_reachable), "Site officiel", health.official_reachable === null ? "pas encore vérifié" : health.official_reachable ? `joignable${checked}` : `injoignable${checked}`),
      line(ok(health.source_reachable), "Source", health.source_reachable === null ? "pas encore vérifiée" : health.source_reachable ? `joignable${checked}` : `injoignable${checked}`)),
    recheck);
}

function ffmpegHelp() {
  return h("div", { class: "notice is-info" }, icon("info", { size: 20 }),
    h("div", {}, h("p", { text: "Pour créer des films, installe ffmpeg d'une de ces façons, puis clique sur « Tout revérifier » :" }),
      codeBox("winget install Gyan.FFmpeg", "Copier"), codeBox("pip install imageio-ffmpeg", "Copier")));
}

export function renderSettings(main, ctx, section) {
  const s = ctx.state.settings;
  const health = ctx.state.health || {};
  const current = SECTIONS.some(([id]) => id === section) ? section : "general";
  const nav = h("nav", { class: "settings-nav", "aria-label": "Sections des réglages" },
    SECTIONS.map(([id, label]) => h("a", { href: `#/reglages/${id}`, "aria-current": id === current ? "page" : null, text: label })));
  const content = h("div", { class: "settings-content" });
  const page = h("div", { class: "page" },
    h("a", { class: "back", href: "#/" }, icon("back"), "Bibliothèque"),
    h("h1", { class: "page-title", tabindex: "-1", "data-autofocus": true, text: "Réglages" }),
    h("div", { class: "settings" }, nav, content));
  if (!s) {
    content.append(h("p", { class: "note", text: "Chargement des réglages…" }));
    main.append(page);
    return;
  }
  const problems = !health.downloads_dir_ok || (health.ffmpeg && !health.ffmpeg.found) || health.online === false;
  const title = SECTIONS.find(([id]) => id === current)[1];
  const langs = new Set();
  for (const g of ctx.state.library?.groups || []) (g.languages_available || []).forEach((l) => langs.add(l));
  ["fr", "en", "es"].forEach((l) => langs.add(l));

  const blocks = {
    general: () => [
      textRow(ctx, s, "downloads_dir", "Dossier de la bibliothèque", "Chemin complet. Il sera créé s'il n'existe pas. Impossible de le changer pendant un téléchargement."),
      h("div", { class: "setting" }, h("span", { class: "setting-label" }), h("div", { class: "setting-control" },
        h("button", { class: "btn btn-ghost", type: "button", onclick: () => ctx.act.openLibrary() }, icon("folder"), "Afficher dans l'explorateur"))),
      selectRow(ctx, s, "preferred_langs", "Version préférée", [["", "Version originale (VO)"], ...[...langs].sort().map((l) => [l, `${capitalize(langName(l))} si disponible, sinon VO`])],
        "Choisie par défaut dans le dialogue d'ajout.", (v) => (Array.isArray(v) ? v[0] || "" : v), (v) => (v ? [v] : [])),
      selectRow(ctx, s, "default_quality", "Qualité", [["best", "Meilleure (1080p)"], ["1080p", "1080p"], ["720p", "720p"], ["540p", "540p"]]),
      switchRow(ctx, s, "film_after_download", "Créer le film après chaque téléchargement", "Seulement si aucun épisode n'a échoué."),
      switchRow(ctx, s, "resume_on_start", "Reprendre automatiquement au démarrage", "Les téléchargements interrompus (fenêtre fermée, coupure) repartent tout seuls."),
    ],
    telechargement: () => [
      numberRow(ctx, s, "parallel_downloads", "Téléchargements simultanés", 1, 6, "3 recommandé. Au-delà, la source risque de te bloquer temporairement.", "épisodes à la fois"),
      numberRow(ctx, s, "concurrent_series", "Séries en même temps", 1, 2, "1 recommandé : la première série est prête plus tôt.", "série(s)"),
    ],
    film: () => [
      h("p", { class: "setting-intro", text: health.ffmpeg?.found ? `ffmpeg est prêt (${health.ffmpeg.source === "PATH" ? "via PATH" : health.ffmpeg.source}).` : "ffmpeg n'est pas installé : il ne sert qu'à créer des films." }),
      health.ffmpeg?.found ? null : ffmpegHelp(),
      textRow(ctx, s, "ffmpeg_path", "Chemin de ffmpeg (optionnel)", "Laisse vide pour le trouver automatiquement (PATH, puis imageio-ffmpeg).", "C:\\ffmpeg\\bin\\ffmpeg.exe"),
    ],
    stockage: () => {
      const st = ctx.state.library?.stats || {};
      const withParts = (ctx.state.library?.groups || []).flatMap((g) => g.versions).filter((v) => v.parts_bytes && !v.job);
      return [
        h("dl", { class: "card" },
          h("div", { class: "kv" }, h("dt", { text: "Bibliothèque" }), h("dd", { text: bytes(st.bytes) })),
          h("div", { class: "kv" }, h("dt", { text: "Épisodes" }), h("dd", { text: bytes(st.episodes_bytes) })),
          h("div", { class: "kv" }, h("dt", { text: "Films" }), h("dd", { text: bytes(st.films_bytes) })),
          h("div", { class: "kv" }, h("dt", { text: "Fichiers partiels" }), h("dd", { text: bytes(st.parts_bytes) })),
          h("div", { class: "kv" }, h("dt", { text: "Libérable (épisodes déjà dans un film)" }), h("dd", { text: bytes(st.freeable_bytes) })),
          h("div", { class: "kv" }, h("dt", { text: "Espace libre" }), h("dd", { text: bytes(st.free_bytes) }))),
        h("div", { class: "btn-row" },
          st.freeable_bytes ? h("a", { class: "btn btn-secondary", href: "#/?f=film", text: "Voir les séries libérables" }) : null,
          withParts.length ? h("button", { class: "btn btn-secondary", type: "button", onclick: () => withParts.forEach((v) => ctx.act.deleteSeries(v, "parts")) }, `Nettoyer les fichiers partiels · ${bytes(withParts.reduce((a, v) => a + v.parts_bytes, 0))}`) : null),
        numberRow(ctx, s, "trash_minutes", "Délai d'annulation d'une suppression", 1, 1440, "Les fichiers supprimés restent récupérables pendant ce délai.", "minutes"),
      ];
    },
    affichage: () => [
      selectRow(ctx, s, "theme", "Thème", [["dark", "Sombre"], ["light", "Clair"], ["system", "Comme le système"]]),
      selectRow(ctx, s, "title_lang", "Titres affichés", [["preferred", "Dans la langue préférée quand elle existe"], ["original", "Titre original"]]),
    ],
    clavier: () => [
      switchRow(ctx, s, "nav_shortcuts", "Raccourcis de navigation", "A (ajouter), T (activité), ? (aide), / (chercher)."),
      switchRow(ctx, s, "action_shortcuts", "Raccourcis d'action rapide", "L (regarder), O (dossier), P (pause), Suppr (supprimer) sur la carte ciblée."),
      h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.openHelp() }, icon("keyboard"), "Voir tous les raccourcis"),
    ],
    accessibilite: () => [
      selectRow(ctx, s, "sr_announcements", "Annonces pour lecteur d'écran", [["milestones", "Paliers (25, 50, 75 %) et fin"], ["all", "Fin de chaque série et échecs"], ["off", "Aucune"]]),
    ],
    sante: () => [healthBlock(ctx, health)],
    apropos: () => [
      h("dl", { class: "card" },
        h("div", { class: "kv" }, h("dt", { text: "Version" }), h("dd", { text: health.version || "—" })),
        h("div", { class: "kv" }, h("dt", { text: "Adresse" }), h("dd", { class: "mono", text: location.origin })),
        h("div", { class: "kv" }, h("dt", { text: "Démarré" }), h("dd", { text: health.started_at ? when(health.started_at) : "—" }))),
      numberRow(ctx, s, "auto_shutdown_minutes", "Arrêt automatique", 0, 1440, "Sans onglet ouvert ni téléchargement ; 0 pour ne jamais s'arrêter.", "minutes"),
      h("div", { class: "btn-row" },
        h("button", { class: "btn btn-danger-ghost", type: "button", onclick: () => ctx.quit() }, "Quitter ShortDramaGen"),
        h("span", { class: "note", text: "Les téléchargements en cours reprendront au prochain lancement." })),
    ],
  };
  append(content, [
    h("h2", { class: "section-title", text: title }),
    problems && current !== "sante" ? healthBlock(ctx, health) : null,
    blocks[current](),
  ]);
  main.append(page);
}
