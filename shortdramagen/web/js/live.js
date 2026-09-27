// Temps réel : flux SSE /api/events (reconnexion et rejeu gérés par EventSource)
// et pilule d'activité de l'en-tête (spec E0).

import { h, icon, clear } from "./dom.js";
import { duration } from "./format.js";

const TYPES = ["snapshot", "job", "progress", "episode", "log", "library", "health", "settings", "server"];

// on : { open, lost, snapshot, job, progress, … } ; renvoie une fonction de fermeture.
export function connectEvents(on) {
  let source = null;
  let failures = 0;
  let retry = null;
  const open = () => {
    source = new EventSource("/api/events");
    source.addEventListener("open", () => {
      failures = 0;
      on.open?.();
    });
    source.addEventListener("error", () => {
      failures += 1;
      if (failures >= 2) on.lost?.();
      if (source.readyState === EventSource.CLOSED) {
        clearTimeout(retry);
        retry = setTimeout(open, 5000); // le serveur a refusé : on retente plus tard
      }
    });
    for (const type of TYPES) {
      source.addEventListener(type, (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        on[type]?.(data);
      });
    }
  };
  open();
  return () => {
    clearTimeout(retry);
    source?.close();
  };
}

// Jobs : { active: [...], history: [...] } tenus à jour à partir des événements `job`.
export function applyJobEvent(jobs, { op, job }) {
  const drop = (list) => list.filter((j) => j.id !== job.id);
  const active = drop(jobs.active);
  const history = drop(jobs.history);
  if (op !== "removed") {
    const terminal = ["done", "failed", "cancelled"].includes(job.status);
    (terminal ? history : active).push(job);
  }
  history.sort((a, b) => (b.finished_at || "").localeCompare(a.finished_at || ""));
  return { active, history };
}

function eta(seconds) {
  if (seconds === null || seconds === undefined) return null;
  return seconds < 60 ? "moins d'une minute" : `≈ ${duration(seconds)}`;
}

// Ce que dit la pilule : { tone, text, fraction, job } ou null au repos.
export function activity(jobs, progress) {
  const active = jobs.active;
  const running = active.find((j) => j.status === "running");
  const queued = active.filter((j) => j.status === "queued").length;
  const more = queued ? ` · +${queued} en file` : "";
  if (running) {
    const p = progress[running.id] || running.progress;
    if (running.kind === "film") {
      const fraction = p && p.seconds_total ? p.seconds_done / p.seconds_total : 0;
      const parts = [`Film · ${Math.round(fraction * 100)} %`, eta(p?.eta_s)].filter(Boolean);
      return { tone: "active", text: parts.join(" · ") + more, fraction, job: running };
    }
    if (!p || running.phase === "metadata") return { tone: "active", text: `Lecture des infos…${more}`, fraction: 0, job: running };
    if (running.phase === "probing") return { tone: "active", text: `Recherche des épisodes… ${p.probed || 0} trouvés${more}`, fraction: 0, job: running };
    const e = p.episodes || {};
    const done = (e.done || 0) + (e.skipped || 0);
    const fraction = p.bytes_total ? p.bytes_done / p.bytes_total : 0;
    const parts = [`↓ ${done}/${e.total || 0}`, eta(p.eta_s)].filter(Boolean);
    return { tone: "active", text: parts.join(" · ") + more, fraction, job: running };
  }
  const stopping = active.find((j) => j.status === "pausing" || j.status === "cancelling");
  if (stopping) return { tone: "active", text: stopping.status === "pausing" ? "Mise en pause…" : "Annulation…", fraction: 0, job: stopping };
  const offline = active.find((j) => j.status === "interrupted" && j.reason === "offline");
  if (offline) return { tone: "warning", text: "En pause · hors ligne", fraction: 0, job: offline };
  if (queued) return { tone: "active", text: `${queued} en file`, fraction: 0, job: active.find((j) => j.status === "queued") };
  const paused = active.filter((j) => j.status === "paused" || j.status === "interrupted");
  if (paused.length) return { tone: "neutral", text: `‖ ${paused.length} en pause`, fraction: 0, job: paused[0] };
  return null;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function ring(fraction) {
  const c = 2 * Math.PI * 6;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("class", "ring");
  svg.setAttribute("aria-hidden", "true");
  const track = document.createElementNS(SVG_NS, "circle");
  const bar = document.createElementNS(SVG_NS, "circle");
  for (const [el, cls] of [[track, "ring-track"], [bar, "ring-bar"]]) {
    el.setAttribute("cx", "8");
    el.setAttribute("cy", "8");
    el.setAttribute("r", "6");
    el.setAttribute("class", cls);
    svg.append(el);
  }
  bar.setAttribute("stroke-dasharray", `${Math.max(0, Math.min(1, fraction)) * c} ${c}`);
  bar.setAttribute("transform", "rotate(-90 8 8)");
  return svg;
}

// Pilule dans l'en-tête ; href(job) donne le lien de la fiche concernée.
export function renderPill(el, info, href) {
  clear(el);
  if (!info) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.className = `pill is-${info.tone}`;
  const link = info.job && href(info.job);
  if (link) el.setAttribute("href", link);
  else el.removeAttribute("href");
  const title = info.job?.title ? `${info.job.title} · ${info.text}` : info.text;
  el.title = title;
  el.setAttribute("aria-label", `Activité : ${title}`);
  el.append(info.tone === "warning" ? icon("pause", { size: 14 }) : ring(info.fraction), h("span", { class: "num", text: info.text }));
}
