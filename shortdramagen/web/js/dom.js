// Construction du DOM sans innerHTML (données jamais interprétées comme du HTML)
// et sans attribut style (CSP) : seules des variables CSS sont posées, via le CSSOM.

const SVG_NS = "http://www.w3.org/2000/svg";

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key === "vars") for (const [name, v] of Object.entries(value)) el.style.setProperty(name, String(v));
      else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
      else if (key === "text") el.textContent = value;
      else if (value === true) el.setAttribute(key, "");
      else el.setAttribute(key, String(value));
    }
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

// Pictogrammes au trait de 1,75 (dessinés pour ce projet), 24 × 24.
const ICONS = {
  play: [["path", { d: "M7 4.5v15l12-7.5z" }]],
  pause: [["path", { d: "M8 5v14M16 5v14" }]],
  back: [["path", { d: "M19 12H5M12 19l-7-7 7-7" }]],
  prev: [["path", { d: "M15 18l-6-6 6-6" }]],
  next: [["path", { d: "M9 18l6-6-6-6" }]],
  close: [["path", { d: "M18 6L6 18M6 6l12 12" }]],
  check: [["path", { d: "M20 6L9 17l-5-5" }]],
  alert: [["circle", { cx: 12, cy: 12, r: 9 }], ["path", { d: "M12 7.5v5.5M12 16.5v.01" }]],
  bang: [["path", { d: "M12 5v9M12 18.5v.01" }]],
  dash: [["path", { d: "M7 12h10" }]],
  question: [["path", { d: "M9 9a3 3 0 1 1 4.5 2.6c-1 .6-1.5 1.2-1.5 2.4M12 18v.01" }]],
  approx: [["path", { d: "M5 10c2-2 4-2 7 0s5 2 7 0M5 15c2-2 4-2 7 0s5 2 7 0" }]],
  film: [["rect", { x: 3, y: 3, width: 18, height: 18, rx: 2 }], ["path", { d: "M7 3v18M17 3v18M3 12h18M3 7.5h4M3 16.5h4M17 7.5h4M17 16.5h4" }]],
  folder: [["path", { d: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" }]],
  download: [["path", { d: "M12 4v11M7 10l5 5 5-5M5 20h14" }]],
  copy: [["rect", { x: 9, y: 9, width: 12, height: 12, rx: 2 }], ["path", { d: "M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" }]],
  search: [["circle", { cx: 11, cy: 11, r: 7 }], ["path", { d: "M20.5 20.5L16 16" }]],
  clock: [["circle", { cx: 12, cy: 12, r: 9 }], ["path", { d: "M12 7v5l3 2" }]],
  arrowDown: [["path", { d: "M12 4v15M6 13l6 6 6-6" }]],
  health: [["path", { d: "M3 12h4l3-7 4 14 3-7h4" }]],
  info: [["circle", { cx: 12, cy: 12, r: 9 }], ["path", { d: "M12 11v6M12 7.5v.01" }]],
  refresh: [["path", { d: "M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" }]],
  trash: [["path", { d: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" }]],
  plus: [["path", { d: "M12 5v14M5 12h14" }]],
  more: [["circle", { cx: 5, cy: 12, r: 1.2 }], ["circle", { cx: 12, cy: 12, r: 1.2 }], ["circle", { cx: 19, cy: 12, r: 1.2 }]],
  settings: [["circle", { cx: 12, cy: 12, r: 3 }], ["path", { d: "M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" }]],
  keyboard: [["rect", { x: 2.5, y: 6, width: 19, height: 12, rx: 2 }], ["path", { d: "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" }]],
  grid: [["rect", { x: 4, y: 4, width: 7, height: 7, rx: 1 }], ["rect", { x: 13, y: 4, width: 7, height: 7, rx: 1 }], ["rect", { x: 4, y: 13, width: 7, height: 7, rx: 1 }], ["rect", { x: 13, y: 13, width: 7, height: 7, rx: 1 }]],
  list: [["path", { d: "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01" }]],
  external: [["path", { d: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" }]],
  pin: [["path", { d: "M9 4h6l-1 6 3 3v2H7v-2l3-3zM12 15v6" }]],
  wifiOff: [["path", { d: "M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 13a10 10 0 0 1 5-2.7M19 13a10 10 0 0 0-2.4-1.8M12 20h.01" }]],
  home: [["path", { d: "M4 11l8-7 8 7M6 10v10h12V10" }]],
};
const SOLID = new Set(["play"]);

export function icon(name, { size, label } = {}) {
  const el = document.createElementNS(SVG_NS, "svg");
  el.setAttribute("viewBox", "0 0 24 24");
  el.setAttribute("class", SOLID.has(name) ? "icon is-solid" : "icon");
  if (size) el.style.setProperty("--icon-size", `${size}px`);
  if (label) {
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", label);
  } else {
    el.setAttribute("aria-hidden", "true");
  }
  for (const [tag, attrs] of ICONS[name] || []) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    el.append(node);
  }
  return el;
}

let announceTimer;
export function announce(text) {
  const region = document.getElementById("annonces");
  if (!region) return;
  clearTimeout(announceTimer);
  region.textContent = "";
  announceTimer = setTimeout(() => { region.textContent = text; }, 50);
}

export async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    announce("Copié dans le presse-papiers.");
    if (button) {
      const previous = button.getAttribute("aria-label");
      button.setAttribute("aria-label", "Copié");
      button.title = "Copié";
      setTimeout(() => { button.setAttribute("aria-label", previous || "Copier"); button.title = previous || "Copier"; }, 1500);
    }
  } catch {
    announce("Copie impossible : sélectionne le texte à la main.");
  }
}

export function codeBox(text, label = "Copier") {
  const button = h("button", { class: "btn-icon btn-icon-sm", type: "button", "aria-label": label, title: label });
  button.append(icon("copy"));
  button.addEventListener("click", () => copyText(text, button));
  return h("div", { class: "code-box" }, h("code", { text }), button);
}
