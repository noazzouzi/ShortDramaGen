// Détection locale et instantanée de ce qui est tapé ou collé (mêmes règles que inputs.py).
// Le serveur refait l'analyse : ceci ne sert qu'à choisir le bon comportement de l'interface.

const RAW_ID = /^\s*(\d{8,14})\s*$/;
const PATH_ID = /\/(?:([a-z]{2}(?:-[a-z]{2})?)\/)?(?:movie|drama|video|book|series)\/(\d{8,14})/i;
const EP_PATH = /\/(?:([a-z]{2}(?:-[a-z]{2})?)\/)?(?:ep|episode)\/(\d{8,14})/i;
const EP_NUMBER = /_Episode-(\d+)/i;
const QUERY_KEYS = ["bookId", "book_id", "bid", "id"];
const ANY_ID = /(?<!\d)(4[12]\d{9})(?!\d)/;
const LOOKS_LIKE_URL = /^(https?:\/\/|www\.)|^[\w-]+(\.[\w-]+)+\//i;

// → { kind: "id" | "link" | "invalid" | "batch" | "text" | "empty", bookId, lang, episode, links }
export function detect(text) {
  const value = (text || "").trim();
  if (!value) return { kind: "empty" };
  const lines = value.split(/\s*\n\s*/).filter(Boolean);
  if (lines.length > 1) {
    const links = lines.map((line) => ({ line, ...detect(line) }));
    if (links.some((l) => l.kind === "id" || l.kind === "link")) return { kind: "batch", links };
  }
  const raw = value.match(RAW_ID);
  if (raw) return { kind: "id", bookId: raw[1], lang: null, episode: null };
  if (!LOOKS_LIKE_URL.test(value)) return { kind: "text" };
  let url;
  try {
    url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
  } catch {
    return { kind: "invalid" };
  }
  const official = url.hostname.includes("dramaboxdb");
  for (const regex of [EP_PATH, PATH_ID]) {
    const m = url.pathname.match(regex);
    if (m) {
      const ep = regex === EP_PATH ? url.pathname.match(EP_NUMBER) : null;
      return { kind: "link", bookId: m[2], lang: official && m[1] ? m[1].toLowerCase() : null, episode: ep ? Number(ep[1]) : null };
    }
  }
  const episode = Number(url.searchParams.get("ep")) || null;
  for (const key of QUERY_KEYS) {
    const v = url.searchParams.get(key);
    if (v && /^\d{8,14}$/.test(v)) return { kind: "link", bookId: v, lang: null, episode };
  }
  const any = (url.pathname + url.search).match(ANY_ID);
  if (any) return { kind: "link", bookId: any[1], lang: null, episode: null };
  return { kind: "invalid" };
}

export const ACCEPTED =
  "Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199).";

export const EXAMPLE_URL = "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever";
