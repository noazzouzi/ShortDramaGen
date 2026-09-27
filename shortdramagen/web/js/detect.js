// Détection locale et instantanée de ce qui est tapé ou collé (mêmes règles que inputs.py et providers/*.py).
// Le serveur refait l'analyse : ceci ne sert qu'à choisir le bon comportement de l'interface.

const RAW_ID = /^\s*(\d{8,14})\s*$/;
const PREFIXED = /^\s*([a-z][a-z0-9]*):(\d{8,14})\s*$/;
const LOOKS_LIKE_URL = /^(https?:\/\/|www\.)|^[\w-]+(\.[\w-]+)+\//i;

// DramaBox : dramaboxdb.com, dramabox.com, lien de partage, dramafren… et tout hôte qu'aucune autre plateforme ne revendique.
const DB_PATH_ID = /\/(?:([a-z]{2}(?:-[a-z]{2})?)\/)?(?:movie|drama|video|book|series)\/(\d{8,14})/i;
const DB_EP_PATH = /\/(?:([a-z]{2}(?:-[a-z]{2})?)\/)?(?:ep|episode)\/(\d{8,14})/i;
const DB_EP_NUMBER = /_Episode-(\d+)/i;
const DB_QUERY_KEYS = ["bookId", "book_id", "bid", "id"];
const DB_ANY_ID = /(?<!\d)(4[12]\d{9})(?!\d)/;

function parseDramaBox(url) {
  const official = url.hostname.includes("dramaboxdb");
  for (const regex of [DB_EP_PATH, DB_PATH_ID]) {
    const m = url.pathname.match(regex);
    if (m) {
      const ep = regex === DB_EP_PATH ? url.pathname.match(DB_EP_NUMBER) : null;
      return { bookId: m[2], lang: official && m[1] ? m[1].toLowerCase() : null, episode: ep ? Number(ep[1]) : null };
    }
  }
  const episode = Number(url.searchParams.get("ep")) || null;
  for (const key of DB_QUERY_KEYS) {
    const v = url.searchParams.get(key);
    if (v && /^\d{8,14}$/.test(v)) return { bookId: v, lang: null, episode };
  }
  const any = (url.pathname + url.search).match(DB_ANY_ID);
  return any ? { bookId: any[1], lang: null, episode: null } : null;
}

// GoodShort : /drama/{slug}-{id}, /episodes/{slug}-{id}, /episode/{slug}-{id}/{NNN}-{chapitre}
const GS_PATH = /^\/(?:[a-z]{2}(?:-[a-z]{2,4})?\/)?(?:drama|episodes|episode)\/(?:[^/]*?-)?(\d{8,14})(?:\/(\d{1,4})-\d+)?\/?$/i;

function parseGoodShort(url) {
  const m = url.pathname.match(GS_PATH);
  return m ? { bookId: m[1], lang: null, episode: m[2] ? Number(m[2]) : null } : null;
}

export const PROVIDERS = [
  { name: "dramabox", label: "DramaBox", hosts: ["dramaboxdb.com", "dramabox.com", "dramaboxapp.com", "dramafren.org"], parse: parseDramaBox },
  { name: "goodshort", label: "GoodShort", hosts: ["goodshort.com"], parse: parseGoodShort },
];
const DEFAULT = PROVIDERS[0];

export function refKey(provider, bookId) {
  return !provider || provider === DEFAULT.name ? bookId : `${provider}:${bookId}`;
}

function found(provider, kind, match) {
  return { kind, provider: provider.name, label: provider.label, ref: refKey(provider.name, match.bookId), ...match };
}

// → { kind: "id" | "link" | "invalid" | "batch" | "text" | "empty", provider, label, ref, bookId, lang, episode, links }
export function detect(text) {
  const value = (text || "").trim();
  if (!value) return { kind: "empty" };
  const lines = value.split(/\s*\n\s*/).filter(Boolean);
  if (lines.length > 1) {
    const links = lines.map((line) => ({ line, ...detect(line) }));
    if (links.some((l) => l.kind === "id" || l.kind === "link")) return { kind: "batch", links };
  }
  const raw = value.match(RAW_ID);
  if (raw) return found(DEFAULT, "id", { bookId: raw[1], lang: null, episode: null });
  const prefixed = value.match(PREFIXED);
  const named = prefixed && PROVIDERS.find((p) => p.name === prefixed[1]);
  if (named) return found(named, "id", { bookId: prefixed[2], lang: null, episode: null });
  if (!LOOKS_LIKE_URL.test(value)) return { kind: "text" };
  let url;
  try {
    url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
  } catch {
    return { kind: "invalid" };
  }
  const host = url.hostname.toLowerCase();
  const provider = PROVIDERS.find((p) => p.hosts.some((h) => host === h || host.endsWith(`.${h}`))) || DEFAULT;
  const match = provider.parse(url);
  return match ? found(provider, "link", match) : { kind: "invalid" };
}

// « Lien GoodShort · série 31000662271 · FR »
export function linkLabel(d) {
  return `Lien ${d.label} · série ${d.bookId}${d.lang ? ` · ${d.lang.toUpperCase()}` : ""}`;
}

export const ACCEPTED =
  "Liens acceptés : DramaBox (dramaboxdb.com, dramabox.com, lien de partage de l'app, dramafren), GoodShort (goodshort.com), le n° de série DramaBox (ex. 41000105199) ou plateforme:n° (ex. goodshort:31000662271).";

export const EXAMPLE_URL = "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever";
