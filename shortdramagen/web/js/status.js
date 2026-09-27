// Vocabulaire des états (spec §4.2) : moteur → texte affiché, ton, pictogramme.

import { duration, plural, versionShort } from "./format.js";

export const EPISODE = {
  done: { label: "Téléchargé et vérifié", glyph: "check" },
  done_unverified: { label: "Téléchargé · non vérifié", glyph: "approx" },
  missing: { label: "Fichier manquant", glyph: "question" },
  failed: { label: "Échec", glyph: "bang" },
  unavailable: { label: "Indisponible à la source", glyph: "dash" },
  partial: { label: "Interrompu", glyph: "pause" },
  downloading: { label: "En cours", glyph: "arrowDown" },
  queued: { label: "En file", glyph: "clock" },
  pending: { label: "À télécharger", glyph: null },
  not_requested: { label: "Non demandé", glyph: null },
  removed: { label: "Retiré (film conservé)", glyph: "film" },
};

// Codes d'erreur stables du moteur (errors.py) → phrase pour l'utilisateur.
export const ERRORS = {
  ep_unavailable: "Cet épisode n'est pas disponible à la source pour le moment.",
  url_mismatch: "La source a renvoyé un autre épisode : il a été écarté.",
  url_rejected: "La source a refusé le lien (il avait peut-être expiré).",
  size_mismatch: "Le téléchargement a été coupé avant la fin.",
  mp4_unreadable: "Le fichier reçu était illisible : il a été écarté.",
  duration_mismatch: "Le fichier reçu n'avait pas la bonne durée : il a été écarté.",
  quality_unavailable: "La qualité demandée n'est pas proposée pour cet épisode.",
  network: "La connexion a échoué pendant le téléchargement.",
  disk_full: "Le disque était plein.",
  file_locked: "Le fichier était verrouillé (ouvert dans un lecteur ?).",
  unknown: "Échec inattendu.",
};

export function counts(version) {
  const c = version.counts;
  return {
    total: c.total,
    present: c.done + c.done_unverified,
    repair: c.failed + c.unavailable + c.missing,
    todo: c.pending + c.not_requested,
    partial: c.partial,
  };
}

const URGENCY = { interrupted: 3, failed: 2, incomplete: 1, complete: 0 };

// Ligne d'état d'une version, ou null si elle est complète (état nominal).
export function versionProblem(version) {
  const k = counts(version);
  switch (version.state) {
    case "interrupted":
      return { tone: "warning", icon: "pause", text: `Interrompu · ${k.present}/${k.total}` };
    case "failed":
      return { tone: "danger", icon: "bang", text: `${plural(k.repair, "à réparer", "à réparer")}` };
    case "incomplete":
      return { tone: "warning", icon: null, text: `${k.present}/${k.total} · ${plural(k.todo, "à télécharger", "à télécharger")}` };
    default:
      return null;
  }
}

// État d'une série (carte) : celui de sa version la plus urgente, préfixé par la version s'il y en a plusieurs.
export function groupProblem(group) {
  const worst = [...group.versions].sort((a, b) => (URGENCY[b.state] || 0) - (URGENCY[a.state] || 0))[0];
  const problem = worst && versionProblem(worst);
  if (!problem) return null;
  return group.versions.length > 1 ? { ...problem, text: `${versionShort(worst)} · ${problem.text}` } : problem;
}

export function filmReady(version) {
  return version.film && ["ready", "partial", "stale"].includes(version.film.state);
}

export function versionMeta(version) {
  const k = counts(version);
  if (version.state === "complete") return version.duration_s ? `${k.total} ép. · ${duration(version.duration_s)}` : `${k.total} ép.`;
  const parts = [`${k.present}/${k.total} ép.`];
  if (k.repair) parts.push(`${k.repair} à réparer`);
  else if (k.partial) parts.push(`${k.partial} interrompu${k.partial > 1 ? "s" : ""}`);
  else if (k.todo) parts.push(`${k.todo} à télécharger`);
  return parts.join(" · ");
}

// Filtres de la bibliothèque : une série passe si l'une de ses versions correspond.
export const FILTERS = [
  { id: "", label: "Toutes", test: () => true },
  { id: "incomplete", label: "À compléter", test: (v) => counts(v).todo > 0 },
  { id: "failed", label: "Avec échecs", test: (v) => counts(v).repair > 0 },
  { id: "interrupted", label: "Interrompues", test: (v) => counts(v).partial > 0 },
  { id: "film", label: "Film prêt", test: (v) => v.film?.state === "ready" },
  { id: "nofilm", label: "Sans film", group: (g) => !g.versions.some(filmReady) },
  { id: "unverified", label: "Non vérifiées", test: (v) => !v.from_official },
];

export function matchFilter(group, filter) {
  if (!filter || !filter.id) return true;
  if (filter.group) return filter.group(group);
  return group.versions.some(filter.test);
}
