// Théâtre (spec E6) : lecteur vertical 9:16 pour un épisode ou le film, avec chapitres.

import { h, icon, clear, announce, append } from "../dom.js";
import { clock, duration, versionShort } from "../format.js";
import { EPISODE } from "../status.js";

const AUTONEXT_KEY = "sdg.autonext";

function readAutoNext() {
  try {
    return localStorage.getItem(AUTONEXT_KEY) !== "0";
  } catch {
    return true;
  }
}

function writeAutoNext(value) {
  try {
    localStorage.setItem(AUTONEXT_KEY, value ? "1" : "0");
  } catch {
    /* stockage indisponible : réglage gardé pour cette page seulement */
  }
}

export function parseVtt(text) {
  const cues = [];
  const toSeconds = (t) => {
    const parts = t.trim().split(":").map(Number);
    return parts.reduce((acc, v) => acc * 60 + v, 0);
  };
  for (const block of text.replace(/\r/g, "").split(/\n\n+/)) {
    const lines = block.split("\n");
    const i = lines.findIndex((l) => l.includes("-->"));
    if (i < 0) continue;
    const [start, end] = lines[i].split("-->").map((s) => toSeconds(s.split(" ").filter(Boolean)[0] || s));
    cues.push({ start, end, title: lines.slice(i + 1).join(" ").trim() });
  }
  return cues;
}

// target : numéro d'épisode ou "film". navigate(target) change d'épisode, close() ferme.
export function openTheater({ group, detail, target, navigate, close, openExternal, retry }) {
  const isFilm = target === "film";
  const playable = detail.episodes.filter((e) => e.media_url);
  const n = isFilm ? null : Number(target);
  const ep = isFilm ? null : detail.episodes.find((e) => e.n === n);
  const index = ep ? playable.findIndex((e) => e.n === ep.n) : -1;
  const prev = index > 0 ? playable[index - 1] : ep ? [...playable].reverse().find((e) => e.n < ep.n) : null;
  const next = index >= 0 ? playable[index + 1] : ep ? playable.find((e) => e.n > ep.n) : null;
  let autoNext = readAutoNext();
  let countdownTimer = null;
  let chapters = [];

  const titleId = "theatre-titre";
  const video = h("video", { controls: true, autoplay: true, playsinline: true, preload: "metadata" });
  const veil = h("div", { class: "veil", hidden: true });
  const countdown = h("div", { class: "countdown", hidden: true, role: "status" });
  const box = h("div", { class: "video-box" }, video, veil, countdown);

  const showVeil = (...children) => {
    clear(veil);
    append(veil, children);
    veil.hidden = false;
  };

  if (isFilm) {
    if (detail.film?.media_url) video.src = detail.film.media_url;
    else showVeil(h("p", { text: "Ce film n'est pas lisible ici." }));
  } else if (ep?.media_url) {
    video.src = ep.media_url;
  } else if (ep) {
    const status = EPISODE[ep.status]?.label || ep.status;
    const skip = next ? h("button", { class: "btn btn-secondary", type: "button", onclick: () => navigate(next.n), text: `Passer à l'épisode ${next.n}` }) : null;
    if (ep.status === "downloading" || ep.status === "queued") {
      showVeil(h("p", { text: `L'épisode ${ep.n} est encore en téléchargement. Il sera lisible dès qu'il sera vérifié.` }), skip);
    } else if (ep.status === "missing" || ep.status === "removed") {
      showVeil(h("p", { text: `Le fichier de l'épisode ${ep.n} n'est plus dans le dossier.` }),
        retry ? h("button", { class: "btn btn-primary", type: "button", onclick: () => retry(ep.n), text: "Retélécharger l'épisode" }) : null, skip);
    } else {
      showVeil(h("p", { text: `Épisode ${ep.n} : ${status.toLowerCase()}. Il n'y a pas de fichier à lire.` }),
        retry && ep.status !== "not_requested" ? h("button", { class: "btn btn-primary", type: "button", onclick: () => retry(ep.n), text: "Réessayer" }) : null, skip);
    }
  } else {
    showVeil(h("p", { text: `L'épisode ${target} n'existe pas dans cette version.` }));
  }

  video.addEventListener("error", () => {
    const url = isFilm ? detail.film?.media_url : ep?.media_url;
    showVeil(
      h("p", { text: "Ton navigateur n'arrive pas à lire cette vidéo." }),
      openExternal ? h("button", { class: "btn btn-primary", type: "button", onclick: () => openExternal(isFilm ? "film" : ep.n), text: "Ouvrir dans le lecteur par défaut" }) : null,
      url ? h("a", { class: "btn btn-secondary", href: `${url}?download=1`, download: "" }, icon("download"), "Enregistrer le fichier pour l'ouvrir dans ton lecteur") : null,
    );
  });

  const cancelCountdown = () => {
    clearInterval(countdownTimer);
    countdownTimer = null;
    countdown.hidden = true;
  };
  video.addEventListener("ended", () => {
    if (isFilm || !next || !autoNext) return;
    let left = 5;
    const render = () => {
      clear(countdown);
      countdown.append(h("span", { text: `Épisode ${next.n} dans ${left} s` }), h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: cancelCountdown, text: "Annuler" }));
    };
    render();
    countdown.hidden = false;
    countdownTimer = setInterval(() => {
      left -= 1;
      if (left <= 0) {
        cancelCountdown();
        navigate(next.n);
      } else render();
    }, 1000);
  });

  const navButton = (item, dir) =>
    h(
      "button",
      {
        class: "btn btn-secondary nav-btn", type: "button", disabled: !item,
        "aria-label": item ? `Épisode ${item.n}` : dir === "prev" ? "Pas d'épisode précédent" : "Pas d'épisode suivant",
        onclick: () => item && navigate(item.n),
      },
      dir === "prev" ? icon("prev") : null,
      item ? `Épisode ${item.n}` : "—",
      dir === "next" ? icon("next") : null,
    );

  // Panneau droit : grille des épisodes, ou chapitres du film.
  const panel = h("aside", { class: "t-panel", "aria-label": isFilm ? "Chapitres" : "Épisodes" });
  if (isFilm) {
    const list = h("div", { class: "chapters" });
    panel.append(h("h3", { text: "Chapitres" }), list);
    if (detail.film?.chapters_url) {
      fetch(detail.film.chapters_url, { credentials: "same-origin" })
        .then((r) => (r.ok ? r.text() : ""))
        .then((text) => {
          chapters = parseVtt(text);
          list.append(
            ...chapters.map((c, i) =>
              h("button", { class: "chap-row", type: "button", dataset: { i }, onclick: () => { video.currentTime = c.start + 0.01; video.play().catch(() => {}); } }, h("span", { text: c.title }), h("span", { class: "chap-time", text: clock(c.start) })),
            ),
          );
        })
        .catch(() => list.append(h("p", { class: "t-note", text: "Chapitres indisponibles." })));
    } else {
      list.append(h("p", { class: "t-note", text: "Ce film n'a pas de chapitres." }));
    }
    video.addEventListener("timeupdate", () => {
      const t = video.currentTime;
      const current = chapters.findIndex((c) => t >= c.start && t < c.end);
      for (const row of list.querySelectorAll(".chap-row")) row.classList.toggle("is-current", Number(row.dataset.i) === current);
    });
  } else {
    const tiles = detail.episodes.map((e) => {
      const info = EPISODE[e.status] || { label: e.status };
      return h(
        "button",
        {
          class: `tile${e.n === n ? " is-playing" : ""}`, type: "button", dataset: { status: e.status, n: e.n },
          "aria-label": `Épisode ${e.n} · ${info.label}`, title: `Épisode ${e.n} · ${info.label}`,
          "aria-current": e.n === n ? "true" : null, disabled: !e.media_url && e.n !== n,
          onclick: () => e.media_url && navigate(e.n),
        },
        String(e.n),
      );
    });
    const toggle = h("button", {
      class: "switch", type: "button", role: "switch", "aria-checked": String(autoNext), "aria-labelledby": "enchainement",
      onclick: (evt) => {
        autoNext = !autoNext;
        writeAutoNext(autoNext);
        evt.currentTarget.setAttribute("aria-checked", String(autoNext));
        if (!autoNext) cancelCountdown();
      },
    });
    panel.append(
      h("h3", { text: `Épisodes · ${n}/${detail.counts.total}` }),
      h("div", { class: "t-tiles" }, tiles),
      h("div", { class: "switch-row" }, h("span", { id: "enchainement", text: "Enchaînement automatique" }), toggle),
      h("p", { class: "t-note", text: "Sous-titres non fournis par la source." }),
    );
  }

  const where = isFilm
    ? `Film${detail.film?.duration_s ? ` · ${duration(detail.film.duration_s)}` : ""}`
    : `Épisode ${n} sur ${detail.counts.total}`;
  const closeButton = h("button", { class: "btn-icon", type: "button", "aria-label": "Fermer (Échap)", title: "Fermer (Échap)", onclick: close }, icon("close", { size: 20 }));
  const el = h(
    "div",
    { class: "theater", role: "dialog", "aria-modal": "true", "aria-labelledby": titleId },
    h("div", { class: "theater-bar" }, h("h2", { id: titleId, text: `${detail.title} · ${versionShort(detail)}` }), h("span", { class: "where", text: where }),
      openExternal && (isFilm ? detail.film?.media_url : ep?.media_url)
        ? h("button", { class: "btn btn-sm btn-ghost theater-external", type: "button", title: "Ouvrir dans le lecteur par défaut (VLC, Films et TV…)", onclick: () => { video.pause(); openExternal(isFilm ? "film" : ep.n); } }, icon("external", { size: 14 }), "Lecteur par défaut")
        : null,
      closeButton),
    h("div", { class: "theater-body" }, h("div", { class: "stage" }, isFilm ? null : navButton(prev, "prev"), box, isFilm ? null : navButton(next, "next")), panel),
  );

  const jumpChapter = (dir) => {
    const t = video.currentTime;
    let i = chapters.findIndex((c) => t >= c.start && t < c.end);
    if (dir < 0 && i >= 0 && t - chapters[i].start > 3) i += 1; // revenir au début du chapitre en cours
    const target = chapters[Math.min(Math.max(i + dir, 0), chapters.length - 1)];
    if (target) video.currentTime = target.start + 0.01;
  };
  const onKey = (e) => {
    if (e.defaultPrevented || e.ctrlKey || e.altKey || e.metaKey) return;
    const onControl = e.target instanceof HTMLElement && e.target.closest("button, a, input, select");
    const onVideo = e.target === video;
    if (e.key === "Escape") {
      e.preventDefault();
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      else close();
    } else if (e.shiftKey && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      e.preventDefault();
      const dir = e.key === "ArrowLeft" ? -1 : 1;
      if (isFilm) jumpChapter(dir);
      else if (dir < 0 && prev) navigate(prev.n);
      else if (dir > 0 && next) navigate(next.n);
    } else if (onVideo || onControl) {
      return; // la vidéo et les boutons gèrent eux-mêmes Espace et les flèches
    } else if (e.key === " " || e.key === "k" || e.key === "K") {
      e.preventDefault();
      if (video.paused) video.play().catch(() => {});
      else video.pause();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      video.currentTime = Math.max(0, video.currentTime + (e.key === "ArrowLeft" ? -5 : 5));
    } else if (e.key === "f" || e.key === "F") {
      e.preventDefault();
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      else video.requestFullscreen?.().catch(() => {});
    } else if (e.key === "m" || e.key === "M") {
      e.preventDefault();
      video.muted = !video.muted;
    }
  };
  el.addEventListener("keydown", onKey);

  announce(isFilm ? `Lecture du film ${detail.title}.` : `Lecture de l'épisode ${n}.`);
  return {
    el,
    focus: () => (video.src ? video : closeButton).focus(),
    destroy() {
      cancelCountdown();
      el.removeEventListener("keydown", onKey);
      video.pause();
      video.removeAttribute("src"); // libère le fichier (Windows ne supprime pas un fichier ouvert)
      video.load();
      el.remove();
    },
  };
}
