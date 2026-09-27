// Composants de base partagés : toasts, dialogues modaux, menus et popovers.
// Aucune donnée n'est insérée en HTML ; les positions passent par le CSSOM (CSP).

import { h, icon, clear, append, announce } from "./dom.js";

// --- toasts (spec §7.9) ------------------------------------------------------------------

const MAX_TOASTS = 3;

function toastRegion() {
  let region = document.getElementById("toasts");
  if (!region) {
    region = h("div", { id: "toasts", class: "toasts", "aria-live": "polite" });
    document.body.append(region);
  }
  return region;
}

// tone : success | info | error | warning ; actions : [{ label, onClick }] ; timeout en ms (0 = reste affiché).
export function toast({ tone = "info", text, actions = [], timeout }) {
  const region = toastRegion();
  const glyph = { success: "check", error: "alert", warning: "alert", info: "info" }[tone] || "info";
  const duration = timeout ?? (tone === "error" ? 0 : actions.length ? 10000 : 5000);
  const el = h("div", { class: `toast is-${tone}`, role: tone === "error" ? "alert" : "status" });
  let timer = null;
  const close = () => {
    clearTimeout(timer);
    el.remove();
  };
  const arm = () => {
    clearTimeout(timer);
    if (duration) timer = setTimeout(close, duration);
  };
  append(el, [
    icon(glyph, { size: 20 }),
    h("p", { class: "toast-text", text }),
    h(
      "div",
      { class: "toast-actions" },
      actions.map((a) => h("button", { class: "btn btn-sm btn-ghost", type: "button", onclick: () => { close(); a.onClick(); }, text: a.label })),
      h("button", { class: "btn-icon btn-icon-sm", type: "button", "aria-label": "Fermer", onclick: close }, icon("close")),
    ),
  ]);
  // Il reste affiché tant qu'on le survole ou qu'il a le focus.
  el.addEventListener("mouseenter", () => clearTimeout(timer));
  el.addEventListener("mouseleave", arm);
  el.addEventListener("focusin", () => clearTimeout(timer));
  el.addEventListener("focusout", arm);
  region.append(el);
  while (region.children.length > MAX_TOASTS) region.firstElementChild.remove();
  arm();
  return close;
}

// --- dialogues (spec §7.8, §7.10) -----------------------------------------------------------

// content(close) renvoie les nœuds du corps ; footer(close) ceux du pied (optionnel).
export function openDialog({ title, content, footer, size = "md", onClose, className = "" }) {
  const titleId = `dlg-${Math.random().toString(36).slice(2, 8)}`;
  const dialog = h("dialog", { class: `dialog dialog-${size} ${className}`, "aria-labelledby": titleId });
  const opener = document.activeElement;
  let closed = false;
  const close = (result) => {
    if (closed) return;
    closed = true;
    dialog.close();
    dialog.remove();
    onClose?.(result);
    if (opener && opener.isConnected && typeof opener.focus === "function") opener.focus();
  };
  const body = h("div", { class: "dialog-body" });
  const foot = h("div", { class: "dialog-foot" });
  dialog.append(
    h(
      "div",
      { class: "dialog-head" },
      h("h2", { id: titleId, text: title }),
      h("button", { class: "btn-icon", type: "button", "aria-label": "Fermer (Échap)", title: "Fermer (Échap)", onclick: () => close() }, icon("close", { size: 20 })),
    ),
    body,
    foot,
  );
  dialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    close();
  });
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) close(); // clic sur le voile
  });
  const api = {
    el: dialog,
    body,
    foot,
    close,
    setTitle: (text) => { dialog.querySelector(`#${titleId}`).textContent = text; },
    render() {
      clear(body);
      append(body, [content(api)]);
      clear(foot);
      if (footer) append(foot, [footer(api)]);
      foot.hidden = !foot.firstChild;
    },
  };
  document.body.append(dialog);
  api.render();
  dialog.showModal();
  // Sans cible désignée, le focus va au titre et non au bouton Fermer (un Entrée égaré le fermerait).
  const first = dialog.querySelector("[autofocus], [data-autofocus]") || dialog.querySelector(`#${titleId}`);
  if (!first.matches("[autofocus], [data-autofocus]")) first.tabIndex = -1;
  first.focus();
  return api;
}

// --- menus et popovers (spec §7.8) -------------------------------------------------------------

let openLayer = null;

function closeLayer() {
  if (!openLayer) return;
  const { el, anchor, onKey, onDown } = openLayer;
  openLayer = null;
  el.remove();
  document.removeEventListener("keydown", onKey, true);
  document.removeEventListener("pointerdown", onDown, true);
  anchor?.setAttribute("aria-expanded", "false");
}

function place(el, anchor, align = "end") {
  const r = anchor.getBoundingClientRect();
  el.style.position = "fixed";
  el.style.top = `${Math.min(r.bottom + 6, innerHeight - 16)}px`;
  document.body.append(el);
  const w = el.offsetWidth;
  const left = align === "end" ? r.right - w : r.left;
  el.style.left = `${Math.max(8, Math.min(left, innerWidth - w - 8))}px`;
  const hgt = el.offsetHeight;
  if (r.bottom + 6 + hgt > innerHeight - 8 && r.top - 6 - hgt > 8) el.style.top = `${r.top - 6 - hgt}px`;
}

function layer(anchor, el, { align, onEscape } = {}) {
  closeLayer();
  place(el, anchor, align);
  anchor.setAttribute("aria-expanded", "true");
  const onKey = (e) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      e.preventDefault();
      closeLayer();
      anchor.focus();
      onEscape?.();
    }
  };
  const onDown = (e) => {
    if (!el.contains(e.target) && !anchor.contains(e.target)) closeLayer();
  };
  document.addEventListener("keydown", onKey, true);
  document.addEventListener("pointerdown", onDown, true);
  openLayer = { el, anchor, onKey, onDown };
  return closeLayer;
}

// items : [{ label, icon, onClick, danger, disabled, reason, key }] ou "sep".
export function openMenu(anchor, items, { label = "Actions" } = {}) {
  const buttons = [];
  const el = h("div", { class: "menu", role: "menu", "aria-label": label });
  for (const item of items) {
    if (item === "sep") {
      el.append(h("div", { class: "menu-sep", role: "separator" }));
      continue;
    }
    if (!item) continue;
    const button = h(
      "button",
      {
        class: `menu-item${item.danger ? " is-danger" : ""}`, type: "button", role: "menuitem",
        "aria-disabled": item.disabled ? "true" : null, title: item.disabled ? item.reason : null,
        onclick: () => {
          if (item.disabled) return;
          closeLayer();
          item.onClick();
        },
      },
      item.icon ? icon(item.icon) : null,
      h("span", { text: item.label }),
      item.key ? h("span", { class: "menu-key", text: item.key }) : null,
    );
    buttons.push(button);
    el.append(button);
  }
  el.addEventListener("keydown", (e) => {
    const i = buttons.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = (i + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next].focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      buttons[e.key === "Home" ? 0 : buttons.length - 1].focus();
    } else if (e.key === "Tab") {
      closeLayer();
    }
  });
  layer(anchor, el);
  buttons[0]?.focus();
}

// Popover libre (ex. confirmation de « Tout réparer ») : content(close) renvoie ses nœuds.
export function openPopover(anchor, content, { align = "end", label } = {}) {
  const el = h("div", { class: "popover-layer", role: "dialog", "aria-label": label });
  const close = () => {
    closeLayer();
    anchor.focus();
  };
  append(el, [content(close)]);
  layer(anchor, el, { align });
  (el.querySelector("[data-autofocus]") || el.querySelector("button"))?.focus();
  return close;
}

export { closeLayer, announce };
