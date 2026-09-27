// Éléments partagés par la bibliothèque et la fiche : action principale, menu, dialogue Supprimer.

import { ApiError } from "../api.js";
import { append, h, icon } from "../dom.js";
import { bytes, plural, versionLong, versionShort } from "../format.js";
import { counts, primaryAction } from "../status.js";
import { openDialog, toast } from "../ui.js";

// La version qui compte pour une carte de série : celle qui a un job, puis la plus urgente.
export function focusVersion(group, fallback) {
  const rank = (v) => {
    if (v.job) return 0;
    if (v.state === "interrupted") return 1;
    if (v.state === "failed") return 2;
    if (counts(v).todo && v.counts.pending) return 3;
    return 9;
  };
  const sorted = [...group.versions].sort((a, b) => rank(a) - rank(b));
  return rank(sorted[0]) < 9 ? sorted[0] : fallback || group.versions[0];
}

export function firstPlayable(detail) {
  return detail?.episodes?.find((e) => e.media_url)?.n || null;
}

// Exécute l'action principale d'une version (carte, étagère, barre de santé).
export async function runPrimary(ctx, version, action) {
  const key = version.series_key;
  switch (action.id) {
    case "pause":
      return ctx.act.jobCommand(version.job, "pause");
    case "resume":
      return ctx.act.jobCommand(version.job, "resume");
    case "repair":
      return ctx.act.retry(key);
    case "complete":
      return ctx.act.retry(key, { include_pending: true }, "Téléchargement lancé");
    case "film":
      try {
        return await ctx.act.createFilm(key, { replace: Boolean(action.replace) });
      } catch (err) {
        if (err instanceof ApiError) {
          toast({ tone: "warning", text: err.message, actions: [{ label: "Voir le film", onClick: () => ctx.goSeries(key, null, "film") }] });
        }
        return null;
      }
    case "watch_film":
      return ctx.goSeries(key, "film");
    case "drawer":
      return ctx.openDrawer();
    default:
      return ctx.goSeries(key);
  }
}

export function menuItems(ctx, version, detail) {
  const film = version.film;
  const playable = detail ? firstPlayable(detail) : null;
  const rest = (version.counts.pending || 0) + (version.counts.not_requested || 0);
  return [
    { label: "Ouvrir la fiche", icon: "next", onClick: () => ctx.goSeries(version.series_key) },
    playable || counts(version).present ? { label: "Regarder", icon: "play", key: "L", onClick: () => ctx.watch(version) } : null,
    film && ["ready", "partial", "stale"].includes(film.state)
      ? { label: "Regarder le film", icon: "film", onClick: () => ctx.goSeries(version.series_key, "film") }
      : counts(version).present
        ? { label: "Créer le film", icon: "film", onClick: () => runPrimary(ctx, version, { id: "film" }) }
        : null,
    rest && primaryAction(version).id !== "complete"
      ? { label: `Télécharger le reste · ${plural(rest, "épisode", "épisodes")}`, icon: "download", onClick: () => runPrimary(ctx, version, { id: "complete" }) }
      : null,
    { label: "Ouvrir le dossier", icon: "folder", key: "O", onClick: () => ctx.act.open(version.series_key, "folder") },
    { label: "Copier la commande", icon: "copy", onClick: () => navigator.clipboard?.writeText(fetchCommand(version)).then(() => toast({ tone: "success", text: "Commande copiée." })) },
    "sep",
    { label: "Supprimer…", icon: "trash", danger: true, key: "Suppr", onClick: () => openDeleteDialog(ctx, [version]) },
  ];
}

export function fetchCommand(version, extra = "") {
  const lang = version.is_original ? "" : ` --lang ${version.lang}`;
  return `python -m shortdramagen fetch ${version.book_id}${lang}${extra}`;
}

// Dialogue Supprimer (spec E8), pour une version ou plusieurs (sélection).
export function openDeleteDialog(ctx, versions) {
  const single = versions.length === 1 ? versions[0] : null;
  const busy = versions.filter((v) => v.job && ["running", "pausing", "queued", "cancelling"].includes(v.job.status));
  const sizes = (v) => ({
    film: v.film?.bytes || 0,
    episodes: v.episodes_bytes || 0,
    all: (v.bytes || 0) + (v.film?.bytes || 0),
    parts: v.parts_bytes || 0,
  });
  const total = (scope) => versions.reduce((s, v) => s + sizes(v)[scope], 0);
  const hasFilm = versions.some((v) => v.film && v.film.bytes);
  const options = [
    { scope: "film", label: "Seulement le film", size: total("film"), disabled: !hasFilm, reason: "pas de film" },
    { scope: "episodes", label: hasFilm ? "Seulement les épisodes (le film reste)" : "Seulement les épisodes", size: total("episodes"), disabled: !total("episodes"), reason: "aucun épisode" },
    { scope: "all", label: "Tout : épisodes, film et dossier", size: total("all") },
    total("parts") ? { scope: "parts", label: "Fichiers partiels", size: total("parts") } : null,
  ].filter(Boolean);
  let chosen = hasFilm && total("episodes") ? "episodes" : null;
  const subtitle = single ? `${single.title} (${versionShort(single)})` : `${plural(versions.length, "version", "versions")} · ${bytes(total("all"))}`;

  const dialog = openDialog({
    title: "Que veux-tu supprimer ?",
    size: "sm",
    content: (d) => {
      if (busy.length) {
        return [
          h("p", { class: "muted", text: subtitle }),
          h("div", { class: "notice is-warning" }, icon("alert", { size: 20 }), h("p", { text: "Mets d'abord le téléchargement en pause." })),
        ];
      }
      const radios = h(
        "div",
        { class: "radio-list", role: "radiogroup", "aria-label": "Quoi supprimer" },
        options.map((o) =>
          h(
            "label",
            { class: `radio-row${o.disabled ? " is-off" : ""}` },
            h("input", { type: "radio", name: "portee", value: o.scope, disabled: o.disabled || null, checked: chosen === o.scope, onchange: () => { chosen = o.scope; d.render(); } }),
            h("span", { class: "radio-label", text: o.label }),
            h("span", { class: "num muted", text: o.disabled ? `— (${o.reason})` : bytes(o.size) }),
          ),
        ),
      );
      return [h("p", { class: "muted", text: subtitle }), radios, h("p", { class: "note", text: `Tu pourras annuler pendant ${ctx.state.settings?.trash_minutes || 5} minutes.` })];
    },
    footer: (d) => {
      if (busy.length) {
        return [
          h("button", { class: "btn btn-secondary", type: "button", onclick: () => d.close(), text: "Fermer" }),
          h("button", { class: "btn btn-primary", type: "button", onclick: () => { busy.forEach((v) => ctx.act.jobCommand(v.job, "pause")); d.close(); }, text: "Mettre en pause" }),
        ];
      }
      const option = options.find((o) => o.scope === chosen);
      return [
        h("button", { class: "btn btn-secondary", type: "button", "data-autofocus": true, onclick: () => d.close(), text: "Annuler" }),
        h(
          "button",
          {
            class: "btn btn-danger", type: "button", disabled: !option || null,
            onclick: async () => {
              d.close();
              ctx.stopPlayer?.();
              for (const v of versions) await ctx.act.deleteSeries(v, chosen);
            },
          },
          option ? `Supprimer ${bytes(option.size)}` : "Supprimer",
        ),
      ];
    },
  });
  dialog.foot.querySelector("[data-autofocus]")?.focus();
  return dialog;
}

export function versionName(version) {
  return versionLong(version);
}

export { append };
