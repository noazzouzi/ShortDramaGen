// Bibliothèque (spec E1) : mur d'affiches, stats, filtres, recherche et tri côté client.

import { h, icon, codeBox, append } from "../dom.js";
import { bytes, htmlLang, plural, versionShort, versionSlug } from "../format.js";
import { FILTERS, counts, filmReady, groupProblem, matchFilter, versionMeta } from "../status.js";

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
  return `#/serie/${group.book_id}/${versionSlug(version)}`;
}

function cover(url, title) {
  const box = h("div", { class: "poster-cover" });
  if (url) {
    const img = h("img", { src: url, alt: "", loading: "lazy", decoding: "async" });
    img.addEventListener("error", () => img.replaceWith(h("div", { class: "cover-fallback", text: title })));
    box.append(img);
  } else {
    box.append(h("div", { class: "cover-fallback", text: title }));
  }
  return box;
}

function ribbon(version) {
  const k = counts(version);
  const seg = (cls, n) => (n > 0 ? h("span", { class: cls, vars: { "--n": n } }) : null);
  return h(
    "div",
    { class: "ribbon", role: "img", "aria-label": `${k.present} épisodes sur ${k.total} présents` },
    seg("rs-ok", k.present),
    seg("rs-warn", k.partial),
    seg("rs-fail", k.repair),
    seg("rs-todo", k.todo),
  );
}

function card(group) {
  const version = mainVersion(group);
  const problem = groupProblem(group);
  const badges = [];
  if (group.versions.length > 1) badges.push(group.versions.map(versionShort).join(" · "));
  else if (!version.is_original) badges.push(versionShort(version));
  if (group.versions.some(filmReady)) badges.push("Film");
  const unverified = group.versions.some((v) => !v.from_official);

  const band = problem || unverified
    ? h(
        "div",
        { class: "poster-band" },
        problem && h("div", { class: `poster-status is-${problem.tone}` }, problem.icon && icon(problem.icon, { size: 12 }), problem.text),
        h(
          "div",
          { class: "poster-badges" },
          badges.slice(0, 2).map((b) => h("span", { class: "badge", text: b })),
          unverified && h("span", { class: "badge badge-info", text: "Non vérifiée" }),
        ),
      )
    : badges.length
      ? h("div", { class: "poster-band is-nominal" }, h("div", { class: "poster-badges" }, badges.map((b) => h("span", { class: "badge", text: b }))))
      : null;

  const coverBox = cover(group.cover_url, group.display_title);
  if (band) coverBox.append(band);
  const incomplete = version.state !== "complete";
  return h(
    "a",
    { class: "poster", href: seriesHref(group, version), dataset: { book: group.book_id } },
    coverBox,
    h(
      "div",
      { class: "poster-body" },
      incomplete && ribbon(version),
      h("h2", { class: "poster-title", lang: htmlLang(version.lang), title: group.display_title, text: group.display_title }),
      h("div", { class: "poster-meta" }, versionMeta(version)),
    ),
  );
}

function stats(library) {
  const s = library.stats;
  const parts = [plural(s.groups, "série", "séries")];
  if (s.versions !== s.groups) parts.push(plural(s.versions, "version", "versions"));
  parts.push(bytes(s.bytes));
  if (s.free_bytes !== null && s.free_bytes !== undefined) parts.push(`${bytes(s.free_bytes)} libres`);
  return parts.join(" · ");
}

function emptyState(library) {
  return h(
    "section",
    { class: "empty" },
    h("h2", { tabindex: "-1", "data-autofocus": true, text: "Ta bibliothèque est vide" }),
    h("p", { text: "Pour l'instant, les séries se téléchargent depuis un terminal. Elles apparaissent ici automatiquement." }),
    codeBox("python -m shortdramagen fetch <lien de la série>", "Copier la commande"),
    h("p", { class: "note" }, "Dossier lu : ", h("span", { class: "mono", text: library.root })),
  );
}

function rootError(library, onRetry) {
  const button = h("button", { class: "btn btn-secondary", type: "button", onclick: onRetry }, icon("refresh"), "Réessayer");
  return h(
    "section",
    { class: "empty", role: "alert" },
    h("h2", { tabindex: "-1", "data-autofocus": true, text: "Impossible d'ouvrir ton dossier de séries" }),
    h("p", {}, h("span", { class: "mono", text: library.root }), " : il a peut-être été déplacé, ou le disque est débranché."),
    h("p", { class: "note", text: "Pour lire un autre dossier : relance avec sdg ui -o <dossier>." }),
    button,
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

// params : URLSearchParams du hash (f = filtre, q = recherche, tri).
export function renderLibrary(main, { library, query, params, setParams, onRetry }) {
  const page = h("div", { class: "page" });
  if (!library) {
    page.append(
      h("div", { class: "lib-head" }, h("h1", { text: "Bibliothèque" }), h("span", { class: "lib-stats", text: "Lecture de ta bibliothèque…" })),
      h("div", { class: "wall", "aria-hidden": "true" }, Array.from({ length: 7 }, () => h("div", {}, h("div", { class: "skeleton poster-cover" }), h("div", { class: "skeleton skeleton-line" })))),
    );
    main.append(page);
    return;
  }
  if (library.root_error) {
    page.append(rootError(library, onRetry));
    main.append(page);
    return;
  }

  const filterId = params.get("f") || "";
  const sortId = params.get("tri") || "recent";
  const filter = FILTERS.find((f) => f.id === filterId) || FILTERS[0];
  const needle = normalize(query);
  const groups = library.groups;
  let shown = groups.filter((g) => matchFilter(g, filter) && (!needle || groupText(g).includes(needle)));
  if (sortId === "title") shown = [...shown].sort((a, b) => a.display_title.localeCompare(b.display_title, "fr"));
  else if (sortId === "size") shown = [...shown].sort((a, b) => groupBytes(b) - groupBytes(a));

  const sortSelect = h(
    "select",
    { "aria-label": "Tri", onchange: (e) => setParams({ tri: e.target.value === "recent" ? "" : e.target.value }) },
    SORTS.map((s) => h("option", { value: s.id, selected: s.id === sortId, text: `Tri : ${s.label}` })),
  );
  page.append(
    h(
      "div",
      { class: "lib-head" },
      h("h1", { tabindex: "-1", "data-autofocus": true, text: "Bibliothèque" }),
      h("span", { class: "lib-stats num", text: stats(library) }),
      groups.length ? h("div", { class: "lib-tools" }, h("label", { class: "select" }, sortSelect)) : null,
    ),
  );
  append(page, [problemsBox(library.problems || [])]);
  if (!groups.length) {
    page.append(emptyState(library));
    main.append(page);
    return;
  }

  const chips = FILTERS.map((f) => {
    const count = groups.filter((g) => matchFilter(g, f)).length;
    if (f.id && !count && f.id !== filterId) return null;
    return h(
      "button",
      { class: "chip", type: "button", "aria-pressed": String(f.id === filter.id), onclick: () => setParams({ f: f.id === filter.id ? "" : f.id }) },
      f.id === filter.id && f.id ? icon("check", { size: 14 }) : null,
      f.label,
      h("span", { class: "chip-count", text: count }),
    );
  });
  const filtered = filter.id || needle;
  page.append(
    h(
      "div",
      { class: "lib-filters" },
      h("div", { class: "chips", role: "group", "aria-label": "Filtres" }, chips),
      filtered
        ? h(
            "span",
            { class: "lib-result" },
            `${shown.length} sur ${plural(groups.length, "série", "séries")} `,
            h("button", { class: "link-btn", type: "button", onclick: () => setParams({ f: "", q: "" }, true), text: "Effacer les filtres" }),
          )
        : null,
    ),
  );
  if (!shown.length) {
    page.append(h("p", { class: "empty", role: "status", text: needle ? `Aucune série ne correspond à « ${query} ».` : `Aucune série « ${filter.label} ».` }));
  } else {
    page.append(h("div", { class: "wall" }, shown.map(card)));
  }
  main.append(page);
}
