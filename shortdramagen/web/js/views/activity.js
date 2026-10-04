// Tiroir Activité (spec E5) : en cours, en file, en pause, terminés récemment, journal.

import { append, clear, copyText, h, icon } from "../dom.js";
import { bytes, duration, plural, ranges, shortWhen, versionShort, when } from "../format.js";

const PHASES = {
  metadata: "Lecture des infos…",
  probing: "Recherche des épisodes à la source…",
  downloading: "Téléchargement",
  finishing: "Vérifications finales…",
  merging: "Création du film…",
  rendering: "Montage des épisodes…",
};

function eta(seconds) {
  if (seconds === null || seconds === undefined) return null;
  return seconds < 60 ? "moins d'une minute" : `≈ ${duration(seconds)}`;
}

function versionLabel(ctx, job) {
  const found = job.series_key && ctx.versionOf(job.series_key);
  if (found) return versionShort(found.version);
  return job.lang ? job.lang.toUpperCase() : "VO";
}

function cover(job) {
  const box = h("div", { class: "job-cover" });
  if (job.cover_url) {
    const img = h("img", { src: job.cover_url, alt: "" });
    img.addEventListener("error", () => img.remove());
    box.append(img);
  }
  if (job.kind === "film") box.append(h("span", { class: "job-kind" }, icon("film", { size: 14 })));
  return box;
}

function bar(fraction, tone = "active") {
  const fill = h("span", { class: `bar-fill is-${tone}` });
  fill.style.setProperty("--p", Math.max(0, Math.min(1, fraction || 0)).toFixed(4));
  return h("div", { class: "bar", "aria-hidden": "true" }, fill);
}

// Ruban d'avancement d'un téléchargement : un segment par épisode sélectionné.
function ribbon(ctx, job) {
  const detail = ctx.state.details.get(job.series_key)?.data;
  if (!detail || !job.selected?.length || job.selected.length > 150) return null;
  const byN = new Map(detail.episodes.map((e) => [e.n, e.status]));
  const tone = { done: "rs-ok", done_unverified: "rs-ok", downloading: "rs-act", failed: "rs-fail", unavailable: "rs-fail", partial: "rs-warn", missing: "rs-warn" };
  return h("div", { class: "ribbon ribbon-eq", "aria-hidden": "true" }, job.selected.map((n) => h("span", { class: tone[byN.get(n)] || "rs-todo" })));
}

function jobRow(ctx, job, confirmCancel, setConfirm) {
  const p = ctx.state.progress[job.id] || job.progress;
  const title = `${job.title || job.book_id || "Série"} · ${versionLabel(ctx, job)}`;
  const lines = [];
  let fraction = 0;
  let tone = "active";
  if (job.kind === "film") {
    fraction = p?.seconds_total ? p.seconds_done / p.seconds_total : 0;
    const what = job.phase === "rendering" ? "Montage des épisodes" : "Création du film";
    lines.push(p?.seconds_total ? `${what} · ${Math.round(fraction * 100)} %` : PHASES[job.phase] || PHASES.merging);
    if (p?.eta_s !== undefined && p?.eta_s !== null) lines.push(eta(p.eta_s));
  } else if (job.status === "running" && p?.episodes && job.phase === "downloading") {
    const e = p.episodes;
    fraction = p.bytes_total ? p.bytes_done / p.bytes_total : 0;
    lines.push(`${e.done + e.skipped}/${e.total} vérifiés · ${bytes(p.bytes_done)} / ${p.total_is_estimate ? "≈ " : ""}${bytes(p.bytes_total)}`);
    const speed = p.speed_bps ? `${bytes(p.speed_bps)}/s` : null;
    lines.push([speed, eta(p.eta_s)].filter(Boolean).join(" · ") || "Mesure du débit…");
    if (e.failed) lines.push(plural(e.failed, "échec", "échecs"));
  } else if (job.status === "running") {
    lines.push(job.phase === "probing" && p?.probed ? `${PHASES.probing} ${p.probed} trouvés` : PHASES[job.phase] || "Démarrage…");
  } else if (job.status === "pausing") {
    lines.push("Mise en pause…");
  } else if (job.status === "cancelling") {
    lines.push("Annulation…");
  }
  const busy = job.status === "pausing" || job.status === "cancelling";
  const firstDone = ctx.firstPlayable(job.series_key);
  const actions = confirmCancel === job.id
    ? cancelConfirm(ctx, job, setConfirm)
    : h(
        "div",
        { class: "btn-row" },
        h("button", { class: "btn btn-sm btn-secondary", type: "button", disabled: busy || null, onclick: () => ctx.act.jobCommand(job, "pause") }, icon("pause", { size: 14 }), "Pause"),
        h("button", { class: "btn btn-sm btn-ghost", type: "button", disabled: busy || null, onclick: () => setConfirm(job.id), text: "Annuler" }),
        firstDone && job.kind === "fetch" ? h("a", { class: "btn btn-sm btn-ghost", href: ctx.theaterHrefFor(job.series_key, firstDone) }, icon("play", { size: 14 }), `Ép. ${firstDone}`) : null,
        job.series_key ? h("a", { class: "btn btn-sm btn-ghost", href: ctx.seriesHrefFor(job.series_key) || "#/", text: "Voir la fiche" }) : null,
      );
  const progressText = lines.join(" · ");
  return h(
    "li",
    { class: "job-row" },
    cover(job),
    h(
      "div",
      { class: "job-body" },
      h("p", { class: "job-title", text: title }),
      bar(fraction, tone),
      h("p", { class: "job-meta num", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(fraction * 100)), "aria-valuetext": progressText, text: progressText }),
      job.kind === "fetch" ? ribbon(ctx, job) : null,
      actions,
    ),
  );
}

function cancelConfirm(ctx, job, setConfirm) {
  const p = ctx.state.progress[job.id];
  const done = p?.episodes ? p.episodes.done + p.episodes.skipped : null;
  const keep = h("input", { type: "checkbox", checked: true });
  return h(
    "div",
    { class: "inline-confirm" },
    h("p", { text: done ? `Arrêter ? Les ${plural(done, "épisode vérifié reste", "épisodes vérifiés restent")}.` : "Arrêter ce téléchargement ? Les épisodes déjà vérifiés restent." }),
    h("label", { class: "check-inline" }, keep, "Garder les fichiers partiels pour reprendre plus tard"),
    h(
      "div",
      { class: "btn-row" },
      h("button", { class: "btn btn-sm btn-danger", type: "button", onclick: () => { setConfirm(null); ctx.act.jobCommand(job, "cancel", { delete_parts: !keep.checked }); }, text: "Arrêter" }),
      h("button", { class: "btn btn-sm btn-secondary", type: "button", "data-autofocus": true, onclick: () => setConfirm(null), text: "Continuer" }),
    ),
  );
}

function waitingRow(ctx, job) {
  const title = `${job.title || job.book_id || "Série"} · ${versionLabel(ctx, job)}`;
  let text;
  let buttons;
  if (job.status === "queued") {
    text = job.position ? `En file · ${job.position}e` : "En file";
    buttons = [
      h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.jobCommand(job, "pause"), text: "Pause" }),
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => ctx.act.jobCommand(job, "cancel", { delete_parts: false }), text: "Retirer" }),
    ];
  } else {
    const r = job.result || {};
    const got = r.done ? r.done.length + (r.skipped || []).length : null;
    const when_ = job.finished_at ? ` · ${when(job.finished_at)}` : "";
    text = job.reason === "offline"
      ? "Hors ligne. Reprise automatique au retour de la connexion."
      : job.status === "interrupted"
        ? `Interrompu${when_}`
        : `En pause par toi${got !== null ? ` · ${got} déjà vérifiés` : ""}`;
    buttons = [
      h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.jobCommand(job, "resume") }, icon("play", { size: 14 }), job.reason === "offline" ? "Réessayer maintenant" : "Reprendre"),
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => ctx.act.jobCommand(job, "cancel", { delete_parts: false }), text: "Annuler" }),
    ];
  }
  return h("li", { class: "job-row is-compact" }, cover(job), h("div", { class: "job-body" }, h("p", { class: "job-title", text: title }), h("p", { class: "job-meta", text }), h("div", { class: "btn-row" }, buttons)));
}

function historyRow(ctx, job) {
  const title = job.kind === "film" ? `Film · ${job.result?.file || job.title || ""}` : `${job.title || job.book_id} · ${versionLabel(ctx, job)}`;
  const r = job.result || {};
  let text;
  const buttons = [];
  const took = job.started_at && job.finished_at ? ` · ${duration((Date.parse(job.finished_at) - Date.parse(job.started_at)) / 1000)}` : "";
  if (job.status === "failed") {
    text = job.error?.message || "Échec.";
    buttons.push(h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.jobCommand(job, "resume"), text: "Réessayer" }));
  } else if (job.status === "cancelled") {
    text = "Annulé";
  } else if (job.kind === "film") {
    text = `${r.reused ? "Déjà à jour" : "Prêt"} · ${duration(r.duration_s)} · ${bytes(r.bytes)}${took}`;
    if (job.series_key) buttons.push(h("a", { class: "btn btn-sm btn-ghost", href: ctx.theaterHrefFor(job.series_key, "film") }, icon("play", { size: 14 }), "Regarder"));
  } else {
    const failed = Object.keys(r.failed || {}).map(Number);
    const got = (r.done || []).length + (r.skipped || []).length;
    text = failed.length ? `Terminé avec ${plural(failed.length, "problème", "problèmes")} (${ranges(failed)})${took}` : `${got} vérifiés${took}`;
    if (failed.length && job.series_key) buttons.push(h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: () => ctx.act.retry(job.series_key), text: "Réparer" }));
    else if (job.series_key && ctx.firstPlayable(job.series_key)) buttons.push(h("a", { class: "btn btn-sm btn-ghost", href: ctx.theaterHrefFor(job.series_key, ctx.firstPlayable(job.series_key)) }, icon("play", { size: 14 }), "Regarder"));
  }
  return h(
    "li",
    { class: "job-row is-compact is-history" },
    h("span", { class: "job-when num", text: shortWhen(job.finished_at) }),
    h("div", { class: "job-body" }, h("p", { class: "job-title", text: title }), h("p", { class: `job-meta${job.status === "failed" ? " is-danger" : ""}`, text }), buttons.length ? h("div", { class: "btn-row" }, buttons) : null),
  );
}

function section(title, count, items, tools) {
  if (!items.length) return null;
  return h(
    "section",
    { class: "drawer-section" },
    h("div", { class: "drawer-section-head" }, h("h3", { class: "overline", text: count ? `${title} · ${count}` : title }), tools || null),
    h("ul", { class: "job-list" }, items),
  );
}

// Rend le contenu du tiroir ; ui : { confirmCancel, setConfirm, logOpen, setLogOpen }.
export function renderActivity(container, ctx, ui) {
  clear(container);
  const { active, history } = ctx.state.jobs;
  const running = active.filter((j) => ["running", "pausing", "cancelling"].includes(j.status));
  const queued = active.filter((j) => j.status === "queued").sort((a, b) => (a.position || 0) - (b.position || 0));
  const waiting = active.filter((j) => j.status === "paused" || j.status === "interrupted");
  const recent = history.slice(0, 10);
  const pauseAll = active.some((j) => ["running", "queued"].includes(j.status))
    ? h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => active.filter((j) => ["running", "queued"].includes(j.status)).forEach((j) => ctx.act.jobCommand(j, "pause")) }, icon("pause", { size: 14 }), "Tout mettre en pause")
    : null;

  const logs = ctx.state.logs;
  const logList = h("ol", { class: "log" }, logs.slice(-150).map((l) => h("li", { class: `log-${l.level}` }, h("span", { class: "num", text: (l.at || "").slice(11, 19) }), " ", l.message)));
  const logBox = logs.length
    ? h(
        "details",
        { class: "drawer-section log-box", open: ui.logOpen || null, ontoggle: (e) => ui.setLogOpen(e.target.open) },
        h("summary", { class: "overline", text: "Journal" }),
        logList,
        h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: (e) => copyText(logs.map((l) => `${(l.at || "").slice(11, 19)} ${l.message}`).join("\n"), e.currentTarget) }, icon("copy", { size: 14 }), "Copier"),
      )
    : null;

  const empty = !running.length && !queued.length && !waiting.length;
  append(container, [
    pauseAll ? h("div", { class: "drawer-tools" }, pauseAll) : null,
    empty
      ? h(
          "div",
          { class: "drawer-empty" },
          h("p", { text: "Rien en cours." }),
          recent[0] ? h("p", { class: "muted", text: `Dernière activité : ${recent[0].title || recent[0].result?.file || ""}, ${when(recent[0].finished_at)}.` }) : null,
          h("button", { class: "btn btn-secondary", type: "button", onclick: () => ctx.openAdd() }, icon("download", { size: 16 }), "Coller un lien"),
        )
      : null,
    section("En cours", 0, running.map((j) => jobRow(ctx, j, ui.confirmCancel, ui.setConfirm))),
    section("En file", queued.length, queued.map((j) => waitingRow(ctx, j))),
    section("En pause ou interrompus", waiting.length, waiting.map((j) => waitingRow(ctx, j))),
    section("Terminés récemment", 0, recent.map((j) => historyRow(ctx, j)),
      recent.length ? h("button", { class: "link-btn", type: "button", onclick: () => history.forEach((j) => ctx.act.removeJob(j)), text: "Effacer la liste (tes fichiers restent)" }) : null),
    logBox,
  ]);
  if (logBox && ui.logOpen) logList.scrollTop = logList.scrollHeight;
  container.querySelector("[data-autofocus]")?.focus();
}
