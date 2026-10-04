// Dialogue d'ajout (spec E2) : aperçu d'un lien, choix de la version, des épisodes
// et de la qualité, puis lancement. Aussi un mode « lot » pour plusieurs liens collés.

import { ApiError, post } from "../api.js";
import { announce, append, clear, codeBox, h, icon } from "../dom.js";
import { ACCEPTED, detect, linkLabel } from "../detect.js";
import { bytes, capitalize, duration, htmlLang, langName, plural, ranges } from "../format.js";
import { openDialog } from "../ui.js";

const QUALITY_FACTORS = { "1080p": 1, "720p": 0.55, "540p": 0.33 }; // 720p et 540p : estimations

// "1-10, 28, 50-" → Set de numéros (max = nombre d'épisodes) ; lève une Error lisible.
export function parseRanges(text, max) {
  const out = new Set();
  const cleaned = (text || "").replace(/[‒-―−]/g, "-");
  for (const part of cleaned.split(",").map((p) => p.trim()).filter(Boolean)) {
    const m = part.match(/^(\d+)\s*(?:-\s*(\d*))?$/);
    if (!m) throw new Error(`« ${part} » n'est pas une plage (ex. 1-10, 28, 50-).`);
    const a = Number(m[1]);
    const b = m[2] === undefined ? a : m[2] === "" ? max || a : Number(m[2]);
    if (a < 1 || b < a) throw new Error(`Plage à l'envers : ${part}.`);
    for (let n = a; n <= Math.min(b, max || b); n++) out.add(n);
  }
  return out;
}

// La source ne propose qu'une qualité, non annoncée (FlickReels) : rien à choisir.
function siteQuality(preview) {
  return preview.free_only || (preview.availability?.source === "ok" && !preview.availability.qualities?.length);
}

function estimateFor(preview, quality, count) {
  const full = preview.estimate?.["1080p"]?.bytes;
  if (!full || !preview.episode_count) return null;
  const factor = QUALITY_FACTORS[quality === "best" ? "1080p" : quality] ?? 1;
  return Math.round((full * factor * count) / preview.episode_count);
}

export function openAddDialog(ctx, { input = "", lang = null } = {}) {
  const settings = ctx.state.settings || {};
  const st = {
    input: input.trim(),
    detected: detect(input),
    lang: lang,
    explicitLang: Boolean(lang),
    preview: null,
    loading: false,
    slow: false,
    error: null,
    previewedInput: null,
    requestId: 0,
    quality: settings.default_quality || "best",
    mode: "all", // all | choose
    chosen: new Set(),
    rangeText: "",
    rangeError: null,
    filmAfter: Boolean(settings.film_after_download),
    expanded: false,
    notDubbed: new Set(),
    voLang: null,
    batch: null,
  };
  if (!st.lang && st.detected.lang) st.lang = st.detected.lang;
  if (!st.lang && settings.preferred_langs?.length) st.lang = settings.preferred_langs[0];

  const field = h("input", {
    class: "mono", type: "text", value: st.input, autocomplete: "off", spellcheck: "false",
    placeholder: "Colle le lien d'une série ou son numéro", "aria-label": "Lien de la série",
    "aria-describedby": "ajout-aide", "data-autofocus": !st.input || null,
  });
  const chip = h("span", { class: "detect-chip", hidden: true });
  const help = h("p", { class: "field-help", id: "ajout-aide" });
  const fieldBox = h("div", { class: "add-field" }, h("label", { class: "field" }, icon("download"), field, chip), help);
  const area = h("div", { class: "add-area", "aria-live": "polite" });
  let dialog;
  let debounce = null;

  field.addEventListener("input", () => {
    st.input = field.value.trim();
    st.detected = detect(field.value);
    renderField();
    clearTimeout(debounce);
    if (["id", "link", "batch"].includes(st.detected.kind)) debounce = setTimeout(load, 500);
  });
  field.addEventListener("paste", () => setTimeout(() => { st.input = field.value.trim(); st.detected = detect(field.value); renderField(); load(); }, 0));

  function renderField() {
    const d = st.detected;
    chip.hidden = !(d.kind === "id" || d.kind === "link" || d.kind === "batch");
    if (d.kind === "batch") chip.textContent = `${d.links.filter((l) => l.kind === "id" || l.kind === "link").length} liens reconnus sur ${d.links.length}`;
    else if (!chip.hidden) chip.textContent = linkLabel(d);
    const bad = d.kind === "invalid" || (d.kind === "text" && st.input.length > 0);
    fieldBox.querySelector(".field").classList.toggle("is-error", bad);
    help.textContent = bad ? `Ce lien n'est pas reconnu. ${ACCEPTED}` : "";
  }

  async function load() {
    const d = st.detected;
    if (d.kind === "batch") return loadBatch();
    st.batch = null;
    if (!(d.kind === "id" || d.kind === "link")) {
      st.preview = null;
      update();
      return;
    }
    const id = ++st.requestId;
    st.loading = true;
    st.error = null;
    st.slow = false;
    update();
    const slow = setTimeout(() => {
      if (id === st.requestId && st.loading) {
        st.slow = true;
        update();
      }
    }, 4000);
    try {
      const res = await post("/api/preview", { input: st.input, lang: st.lang });
      if (id !== st.requestId) return;
      const p = res.data;
      if (p.lang_source === "fallback" && st.lang) {
        st.notDubbed.add(st.lang);
        if (!st.explicitLang) st.lang = null; // langue préférée absente : la VO, sans insister
      }
      if (p.is_original && p.lang) st.voLang = p.lang;
      st.preview = p;
      st.previewedInput = st.input;
      if (p.episode_ref && st.mode === "all" && !st.chosen.size) st.episodeHint = p.episode_ref;
    } catch (err) {
      if (id !== st.requestId) return;
      st.error = err;
      st.preview = null;
    } finally {
      clearTimeout(slow);
      if (id === st.requestId) {
        st.loading = false;
        update();
        if (st.preview) {
          announce(`Aperçu prêt : ${st.preview.title}.`);
          dialog.foot.querySelector(".btn-primary:not([disabled])")?.focus();
        }
      }
    }
  }

  // --- rendu de l'aperçu -------------------------------------------------------------------

  function owned() {
    const p = st.preview;
    return (p?.local || []).find((v) => (p.is_original ? v.is_original : !v.is_original && v.lang === p.lang)) || null;
  }

  function versionChips() {
    const p = st.preview;
    const langs = (p.languages || []).filter((l) => l !== st.voLang);
    const local = p.local || [];
    const chips = [{ lang: null, label: st.voLang ? `VO · ${langName(st.voLang)}` : "VO" }];
    for (const l of langs) if (!st.notDubbed.has(l)) chips.push({ lang: l, label: capitalize(langName(l)) });
    const current = p.is_original ? null : p.lang;
    const group = h("div", { class: "version-chips", role: "radiogroup", "aria-label": "Version" });
    chips.forEach((c) => {
      const have = local.find((v) => (c.lang === null ? v.is_original : !v.is_original && v.lang === c.lang));
      const checked = c.lang === current;
      const button = h(
        "button",
        {
          class: "chip chip-lg", type: "button", role: "radio", "aria-checked": String(checked), tabindex: checked ? "0" : "-1",
          title: c.lang ? langName(c.lang) : "Version originale",
          onclick: () => {
            if (checked) return;
            st.lang = c.lang;
            st.explicitLang = true;
            load();
          },
        },
        checked ? icon("check", { size: 14 }) : null,
        c.label,
        have ? h("span", { class: "chip-count", text: have.done >= have.total ? `✓ ${have.done}/${have.total}` : `${have.done}/${have.total}` }) : null,
      );
      group.append(button);
    });
    group.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const items = [...group.querySelectorAll("[role=radio]")];
      const i = items.indexOf(document.activeElement);
      const next = items[(i + (e.key === "ArrowRight" ? 1 : -1) + items.length) % items.length];
      next?.focus();
      next?.click();
    });
    const titleOnly = [...st.notDubbed].map(langName);
    return [
      group,
      titleOnly.length ? h("p", { class: "field-help", text: `${capitalize(titleOnly.join(", "))} : titre traduit seulement, pas de version doublée.` }) : null,
    ];
  }

  function episodePicker(total) {
    const grid = h("div", { class: "mini-grid", role: "group", "aria-label": "Épisodes à télécharger" });
    const rangeField = h("input", { class: "mono range-field", type: "text", value: st.rangeText, placeholder: "1-10, 28, 50-", "aria-label": "Plages d'épisodes", "aria-describedby": "plages-aide" });
    const rangeHelp = h("p", { class: "field-help", id: "plages-aide", text: st.rangeError || "" });
    const sync = () => {
      for (const tile of grid.children) tile.setAttribute("aria-pressed", String(st.chosen.has(Number(tile.dataset.n))));
      st.rangeText = ranges([...st.chosen]);
      rangeField.value = st.rangeText;
      updateFooter();
    };
    for (let n = 1; n <= total; n++) {
      grid.append(h("button", {
        class: "mini-tile", type: "button", "aria-pressed": String(st.chosen.has(n)), dataset: { n },
        onclick: () => { st.chosen.has(n) ? st.chosen.delete(n) : st.chosen.add(n); st.rangeError = null; rangeHelp.textContent = ""; sync(); },
      }, String(n)));
    }
    rangeField.addEventListener("input", () => {
      try {
        st.chosen = parseRanges(rangeField.value, total);
        st.rangeError = null;
        st.rangeText = rangeField.value;
        for (const tile of grid.children) tile.setAttribute("aria-pressed", String(st.chosen.has(Number(tile.dataset.n))));
        updateFooter();
      } catch (err) {
        st.rangeError = err.message;
      }
      rangeHelp.textContent = st.rangeError || "";
      rangeField.classList.toggle("is-error", Boolean(st.rangeError));
    });
    const tools = h(
      "div",
      { class: "btn-row" },
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => { st.chosen = new Set(Array.from({ length: total }, (_, i) => i + 1)); sync(); }, text: "Tous" }),
      h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => { st.chosen = new Set(); sync(); }, text: "Aucun" }),
      rangeField,
    );
    return [tools, rangeHelp, total ? grid : h("p", { class: "note", text: "Le nombre d'épisodes n'est pas connu : indique des plages." })];
  }

  function options(p) {
    const qualities = p.availability?.qualities?.length ? p.availability.qualities : ["1080p", "720p", "540p"];
    const qualitySelect = h(
      "select",
      { "aria-label": "Qualité", onchange: (e) => { st.quality = e.target.value; updateFooter(); } },
      ["best", ...qualities].map((q) => {
        const est = estimateFor(p, q, p.episode_count || 0);
        const label = q === "best" ? `Meilleure (${qualities[0]})` : q;
        const suffix = est ? ` · ≈ ${bytes(est)}${q === "720p" || q === "540p" ? " (estimation)" : ""}` : "";
        return h("option", { value: q, selected: q === st.quality, text: label + suffix });
      }),
    );
    const modeRadio = (value, label) =>
      h("label", { class: "radio-inline" }, h("input", { type: "radio", name: "ajout-episodes", value, checked: st.mode === value, onchange: () => { st.mode = value; update(); } }), label);
    const command = ["python -m shortdramagen fetch", p.ref, p.is_original ? "" : `--lang ${p.lang}`, !siteQuality(p) && st.quality !== "best" ? `-q ${st.quality}` : "",
      st.mode === "choose" && st.chosen.size ? `-e ${ranges([...st.chosen]).replace(/ /g, "")}` : "", st.filmAfter ? "--film" : ""].filter(Boolean).join(" ");
    return h(
      "div",
      { class: "add-options" },
      siteQuality(p) ? null : h("label", { class: "form-row" }, h("span", { text: "Qualité" }), h("span", { class: "select" }, qualitySelect)),
      h("div", { class: "form-row" }, h("span", { text: "Épisodes" }), h("div", { class: "radio-row-inline" }, modeRadio("all", "Tous"), modeRadio("choose", "Choisir…"))),
      st.mode === "choose" ? h("div", { class: "picker" }, episodePicker(p.episode_count || 0)) : null,
      h("p", { class: "note" }, "Dossier : ", h("span", { class: "mono", text: ctx.state.health?.downloads_dir || "" }), " (modifiable dans les Réglages)"),
      codeBox(command, "Copier la commande"),
    );
  }

  function previewBlock(p) {
    const minMax = p.episode_duration_s ? ` · épisodes de ${duration(p.episode_duration_s.min)} à ${duration(p.episode_duration_s.max)}` : "";
    const meta = p.episode_count ? `${plural(p.episode_count, "épisode", "épisodes")}${p.duration_s ? ` · ${duration(p.duration_s)}` : ""}${minMax}` : "Nombre d'épisodes inconnu";
    const available = p.availability?.source === "ok";
    const syn = p.introduction ? h("p", { class: "syn syn-sm", lang: htmlLang(p.lang), text: p.introduction }) : null;
    const cover = h("div", { class: "add-cover" });
    cover.append(p.cover_url ? h("img", { src: p.cover_url, alt: "" }) : h("div", { class: "cover-fallback", text: p.title }));
    return h(
      "div",
      { class: "add-preview" },
      cover,
      h(
        "div",
        { class: "add-info" },
        h("h3", { class: "add-title", lang: htmlLang(p.lang), text: p.title }),
        p.title_vo && p.title_vo !== p.title ? h("p", { class: "muted", lang: "en", text: `${p.title_vo} · titre original` }) : null,
        h("p", { class: "muted num", text: meta }),
        syn,
        h(
          "p",
          { class: `source-pill ${available ? "is-ok" : "is-danger"}` },
          icon(available ? "check" : "alert", { size: 14 }),
          !available
            ? p.free_only ? `Aucun épisode gratuit sur le site ${p.provider_label}.` : "La source ne répond pas pour cette série : le téléchargement risque d'échouer."
            : p.free_only ? `Site officiel ${p.provider_label} · ${plural((p.free_episodes || []).length, "épisode gratuit", "épisodes gratuits")}`
            : p.availability.qualities?.length ? `Source disponible · ${p.availability.qualities.join(", ")}` : "Source disponible",
        ),
      ),
    );
  }

  function update() {
    clear(area);
    if (st.batch) {
      append(area, [batchBlock()]);
      updateFooter();
      return;
    }
    if (st.loading) {
      append(area, [
        h("div", { class: "add-preview", "aria-busy": "true" }, h("div", { class: "add-cover skeleton" }), h("div", { class: "add-info" }, h("div", { class: "skeleton skeleton-line" }), h("div", { class: "skeleton skeleton-line" }), h("div", { class: "skeleton skeleton-line" }))),
        h("p", { class: "note", role: "status", text: st.slow ? "Le site officiel met du temps à répondre…" : "Lien reconnu. Recherche de la série…" }),
      ]);
    } else if (st.error) {
      append(area, [errorBlock(st.error)]);
    } else if (st.preview) {
      const p = st.preview;
      const mine = owned();
      const localLabels = (p.local || []).map((v) => `${v.is_original ? "VO" : v.lang.toUpperCase()} ${v.done >= v.total ? `complète (${v.done}/${v.total})` : `${v.done}/${v.total}`}`);
      append(area, [
        previewBlock(p),
        p.from_official === false
          ? h("div", { class: "notice is-info" }, icon("info", { size: 20 }), h("p", {}, h("strong", { text: "Infos limitées. " }), "Cette série n'est pas sur le site officiel : titre, durées et affiche indisponibles. Les épisodes seront détectés pendant le téléchargement, sans contrôle de durée."))
          : null,
        p.free_only
          ? h("div", { class: "notice is-info" }, icon("info", { size: 20 }), h("p", {}, h("strong", { text: `${p.provider_label} : épisodes gratuits seulement. ` }),
              `Seuls les épisodes gratuits du site officiel sont téléchargés (${(p.free_episodes || []).length} sur ${p.episode_count || "?"}) ; les autres restent dans l'application ${p.provider_label}.`))
          : null,
        p.episode_ref && !mine
          ? h("div", { class: "notice is-info" }, icon("info", { size: 20 }), h("p", {}, `C'est le lien de l'épisode ${p.episode_ref} : on te propose toute la série. `,
              h("button", { class: "link-btn", type: "button", onclick: () => { st.mode = "choose"; st.chosen = new Set([p.episode_ref]); st.rangeText = String(p.episode_ref); st.expanded = true; update(); }, text: `Seulement l'épisode ${p.episode_ref}` })))
          : null,
        localLabels.length
          ? h("div", { class: "notice is-info" }, icon("info", { size: 20 }), h("p", { text: `Déjà dans ta bibliothèque : ${localLabels.join(" · ")}.${mine ? "" : " Cette version sera ajoutée à la même série."}` }))
          : null,
        p.from_official !== false ? h("div", { class: "add-section" }, h("h3", { class: "overline", text: "Version" }), versionChips()) : null,
        mine ? null : summaryLine(p),
        mine || !st.expanded ? null : options(p),
        mine ? null : costLine(p),
      ]);
    } else {
      append(area, [h("p", { class: "note", text: st.detected.kind === "empty" ? `Colle le lien d'une série. ${ACCEPTED}` : "" })]);
    }
    updateFooter();
  }

  function summaryLine(p) {
    const qualityLabel = siteQuality(p) ? "Qualité du site" : st.quality === "best" ? `Meilleure (${p.availability?.qualities?.[0] || "1080p"})` : st.quality;
    const episodes = st.mode === "choose" ? plural(st.chosen.size, "épisode choisi", "épisodes choisis") : "tous les épisodes";
    return h(
      "button",
      { class: "summary-line", type: "button", "aria-expanded": String(st.expanded), onclick: () => { st.expanded = !st.expanded; update(); } },
      h("span", { text: `${qualityLabel} · ${episodes} · ${st.filmAfter ? "film à la fin" : "sans film"}` }),
      h("span", { class: "link-btn", text: st.expanded ? "Masquer ▴" : "Modifier ▾" }),
    );
  }

  function selectedCount(p) {
    return st.mode === "choose" ? st.chosen.size : p.episode_count || 0;
  }

  function costLine(p) {
    const est = estimateFor(p, st.quality, selectedCount(p));
    const ahead = ctx.state.jobs.active.filter((j) => j.kind === "fetch" && ["running", "queued"].includes(j.status)).length;
    const parts = [];
    if (est) parts.push(`≈ ${bytes(est)}${st.quality === "720p" || st.quality === "540p" ? " (estimation)" : ""}`);
    if (p.disk?.free_bytes !== null && p.disk?.free_bytes !== undefined) parts.push(`${bytes(p.disk.free_bytes)} libres`);
    parts.push(ahead ? `démarre après ${plural(ahead, "série", "séries")}` : "démarre tout de suite");
    return h("p", { class: "cost num", text: parts.join(" · ") });
  }

  function errorBlock(err) {
    let text = err.message;
    let retry = true;
    if (err.code === "invalid_input") {
      text = `Ce lien n'est pas reconnu. ${ACCEPTED}`;
      retry = false;
    } else if (err.code === "series_not_found") {
      text = "On n'a trouvé cette série ni sur le site officiel ni à la source. Vérifie le lien ou essaie avec le n° de série (11 chiffres).";
      retry = false;
    } else if (err.code === "network") {
      text = "Impossible de joindre DramaBox. Vérifie ta connexion.";
    } else if (err.code === "unreachable") {
      text = "Le moteur ne répond pas : vérifie que sdg ui est toujours lancé.";
    }
    return h("div", { class: "notice is-danger", role: "alert" }, icon("alert", { size: 20 }), h("p", { text }), retry ? h("button", { class: "btn btn-sm btn-secondary", type: "button", onclick: load, text: "Réessayer" }) : null);
  }

  // --- pied : bouton principal selon le cas (spec E2) ------------------------------------------------

  function primary() {
    if (st.batch) {
      const rows = st.batch.filter((r) => r.checked && r.preview);
      const total = rows.reduce((s, r) => s + (estimateFor(r.preview, st.quality, r.preview.episode_count || 0) || 0), 0);
      return {
        label: `Tout télécharger · ${plural(rows.length, "série", "séries")}${total ? ` · ≈ ${bytes(total)}` : ""}`,
        disabled: !rows.length,
        run: async () => {
          let ok = 0;
          for (const r of rows) if (await ctx.act.addFetch({ input: r.line, lang: r.lang, quality: st.quality, film_after: st.filmAfter })) ok += 1;
          return ok > 0;
        },
      };
    }
    const p = st.preview;
    if (!p || st.loading) return { label: "Télécharger", disabled: true, reason: st.loading ? "Aperçu en cours…" : "Colle d'abord un lien." };
    if (st.input !== st.previewedInput) return { label: "Voir l'aperçu", run: () => { load(); return false; } };
    if (p.queued_job_id) return { label: "Voir dans l'activité", run: () => { ctx.openDrawer(); return true; } };
    const mine = owned();
    const vname = p.is_original ? "VO" : p.lang.toUpperCase();
    if (mine) {
      const key = mine.series_key;
      if (mine.state === "failed" || mine.state === "interrupted") {
        return { label: `Réparer la ${vname}`, run: async () => Boolean(await ctx.act.retry(key)), secondary: openSeries(key) };
      }
      if (mine.done < mine.total) {
        return { label: `Compléter · ${plural(mine.total - mine.done, "manquant", "manquants")}`, run: async () => Boolean(await ctx.act.retry(key, { include_pending: true, film_after: st.filmAfter }, "Téléchargement lancé")), secondary: openSeries(key) };
      }
      return { label: "Ouvrir la fiche", run: () => { ctx.goSeries(key); return true; }, secondary: mine.film === "ready" ? { label: "▶ Regarder le film", run: () => { ctx.goSeries(key, "film"); return true; } } : null };
    }
    const count = selectedCount(p);
    const est = estimateFor(p, st.quality, count);
    const enough = !p.disk || p.disk.enough !== false || !est || !p.disk.free_bytes || p.disk.free_bytes > est;
    if (!enough) return { label: "Télécharger", disabled: true, reason: `Il manque ≈ ${bytes(est - p.disk.free_bytes)} sur le disque.` };
    if (st.mode === "choose" && !count) return { label: "Télécharger", disabled: true, reason: "Choisis au moins un épisode." };
    let label;
    if (p.from_official === false) label = "Télécharger les épisodes trouvés";
    else if (st.mode === "choose") label = `Télécharger ${plural(count, "épisode", "épisodes")}${est ? ` · ≈ ${bytes(est)}` : ""}`;
    else if ((p.local || []).length) label = `Télécharger la ${vname} · ${plural(count, "épisode", "épisodes")}`;
    else label = `Tout télécharger · ${plural(count, "épisode", "épisodes")}`;
    return {
      label,
      run: async () => Boolean(await ctx.act.addFetch({
        input: st.input, lang: p.is_original ? null : p.lang, quality: siteQuality(p) ? "best" : st.quality,
        episodes: st.mode === "choose" ? [...st.chosen].sort((a, b) => a - b) : null, film_after: st.filmAfter,
      })),
      secondary: st.mode === "all" && p.episode_count ? { label: "Choisir les épisodes", run: () => { st.mode = "choose"; st.expanded = true; update(); return false; } } : null,
    };
  }

  function openSeries(key) {
    return { label: "Ouvrir la fiche", run: () => { ctx.goSeries(key); return true; } };
  }

  async function launch(action) {
    const done = await action.run();
    if (done) {
      dialog.close("launched");
      ctx.afterAdd();
    }
  }

  function updateFooter() {
    if (!dialog) return;
    clear(dialog.foot);
    const action = primary();
    const filmBox = h("label", { class: "check-inline", title: "Ctrl+Entrée" },
      h("input", { type: "checkbox", checked: st.filmAfter, onchange: (e) => { st.filmAfter = e.target.checked; if (st.expanded) update(); else updateFooter(); } }),
      "Créer le film à la fin");
    const main = h("button", { class: "btn btn-primary btn-lg", type: "button", disabled: action.disabled || null, "aria-describedby": action.reason ? "ajout-raison" : null, onclick: () => launch(action) }, action.label);
    append(dialog.foot, [
      st.preview && !owned() ? filmBox : h("span"),
      h(
        "div",
        { class: "btn-row" },
        action.reason ? h("span", { class: "field-help", id: "ajout-raison", text: action.reason }) : null,
        action.secondary ? h("button", { class: "btn btn-secondary btn-lg", type: "button", onclick: () => launch(action.secondary), text: action.secondary.label }) : null,
        main,
      ),
    ]);
    dialog.foot.hidden = false;
  }

  // --- lot ---------------------------------------------------------------------------------------------

  async function loadBatch() {
    const links = st.detected.links;
    st.preview = null;
    st.error = null;
    st.batch = links.map((l, i) => ({ ...l, index: i + 1, checked: l.kind === "id" || l.kind === "link", preview: null, error: null, loading: l.kind === "id" || l.kind === "link" }));
    update();
    for (const row of st.batch) {
      if (!row.loading) continue;
      try {
        row.preview = (await post("/api/preview", { input: row.line, lang: row.lang })).data;
        const complete = (row.preview.local || []).some((v) => v.done >= v.total && (row.preview.is_original ? v.is_original : v.lang === row.preview.lang));
        if (complete || row.preview.queued_job_id) row.checked = false;
      } catch (err) {
        row.error = err.message;
        row.checked = false;
      }
      row.loading = false;
      if (st.batch) update();
    }
  }

  function batchBlock() {
    return h(
      "ul",
      { class: "batch" },
      st.batch.map((row) => {
        const valid = row.kind === "id" || row.kind === "link";
        const p = row.preview;
        let detail;
        if (!valid) detail = `La ligne ${row.index} n'est pas un lien de série reconnu.`;
        else if (row.loading) detail = "Recherche de la série…";
        else if (row.error) detail = row.error;
        else {
          const est = estimateFor(p, st.quality, p.episode_count || 0);
          const done = (p.local || []).some((v) => v.done >= v.total) ? " · déjà complète" : p.queued_job_id ? " · déjà dans la file" : "";
          detail = `${p.episode_count ? plural(p.episode_count, "épisode", "épisodes") : "épisodes inconnus"}${est ? ` · ≈ ${bytes(est)}` : ""}${done}`;
        }
        return h(
          "li",
          { class: "batch-row" },
          h("input", { type: "checkbox", checked: row.checked, disabled: !p || null, "aria-label": p ? p.title : `Ligne ${row.index}`, onchange: (e) => { row.checked = e.target.checked; updateFooter(); } }),
          h("div", { class: "batch-cover" }, p?.cover_url ? h("img", { src: p.cover_url, alt: "" }) : null),
          h("div", { class: "batch-text" }, h("strong", { text: p ? p.title : row.line }), h("span", { class: "muted", text: detail })),
        );
      }),
    );
  }

  // --- ouverture ---------------------------------------------------------------------------------------

  dialog = openDialog({
    title: "Ajouter une série",
    size: "lg",
    className: "add-dialog",
    content: () => [fieldBox, area],
  });
  dialog.el.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.target.matches("button, select, textarea, .range-field")) return;
    e.preventDefault();
    if (e.ctrlKey || e.metaKey) st.filmAfter = true;
    const action = primary();
    if (!action.disabled) launch(action);
  });
  renderField();
  if (["id", "link", "batch"].includes(st.detected.kind)) load();
  else update();
  return dialog;
}
