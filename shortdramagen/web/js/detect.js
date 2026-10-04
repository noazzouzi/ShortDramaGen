// Détection locale et instantanée de ce qui est tapé ou collé (mêmes règles que inputs.py et providers/*.py).
// Le serveur refait l'analyse : ceci ne sert qu'à choisir le bon comportement de l'interface.

const RAW_ID = /^\s*(\d{8,14})\s*$/;
const PREFIXED = /^\s*([a-z][a-z0-9]*):(\d{1,20})\s*$/;
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

// GoodShort : /drama/{slug}-{id}, /episodes/{slug}-{id}, /episode/{slug}-{id}/{NNN}-{chapitre},
// et (cdn-)goodshort.dramafren.org/index.php?page=detail&id={id} (page=watch&…&ep={index}, 0 pour l'épisode 1)
const GS_PATH = /^\/(?:[a-z]{2}(?:-[a-z]{2,4})?\/)?(?:drama|episodes|episode)\/(?:[^/]*?-)?(\d{8,14})(?:\/(\d{1,4})-\d+)?\/?$/i;
const GS_DRAMAFREN = ["goodshort.dramafren.org", "cdn-goodshort.dramafren.org"];

function parseGoodShort(url) {
  if (GS_DRAMAFREN.includes(url.hostname.toLowerCase())) {
    const id = url.searchParams.get("id");
    const ep = url.searchParams.get("ep");
    return id && /^\d{8,14}$/.test(id) ? { bookId: id, lang: null, episode: ep && /^\d+$/.test(ep) ? Number(ep) + 1 : null } : null;
  }
  const m = url.pathname.match(GS_PATH);
  return m ? { bookId: m[1], lang: null, episode: m[2] ? Number(m[2]) : null } : null;
}

// FlickReels : (cdn-)flickreels.dramafren.org/index.php?page=detail&id={id} (page=watch&…&ep={n}, 1 pour l'épisode 1),
// flickreels.net/{langue}/episodes-list/{slug}-{id}, /movie/{slug}-{id}, /playlist/{slug}/{id}/episode-{n}
const FR_PATH = /^\/(?:[a-z]{2}(?:-[a-z]{2,4})?\/)?(?:(?:episodes-list|movie)\/(?:[^/]*-)?(\d{1,9})|playlist\/[^/]+\/(\d{1,9})(?:\/(?:episode-(\d{1,4})|full-movie))?)\/?$/i;
const FR_DRAMAFREN = ["flickreels.dramafren.org", "cdn-flickreels.dramafren.org"];

// Lecteurs copiés de dramafren (FlickReels, ShortMax, NetShort) : index.php?page=detail&id={id} (page=watch&…&ep={n}, 1 pour l'épisode 1)
function parsePlayerLink(url, idPattern = /^\d{1,9}$/) {
  const id = url.searchParams.get("id");
  const ep = Number(url.searchParams.get("ep")) || null;
  return id && idPattern.test(id) ? { bookId: id, lang: null, episode: ep } : null;
}

function parseFlickReels(url) {
  if (FR_DRAMAFREN.includes(url.hostname.toLowerCase())) return parsePlayerLink(url);
  const m = url.pathname.match(FR_PATH);
  return m ? { bookId: m[1] || m[2], lang: null, episode: m[3] ? Number(m[3]) : null } : null;
}

// ShortMax : shortmax.ngeshorts.fun (ou shortmax.dramafren.org)/index.php?page=detail&id={id},
// shorttv.live (ex-shortmax.com)/{langue}/drama/{slug}-{id}, /{langue}/episode/{slug}-{id}-{n}
const SM_PATH = /^\/(?:[a-z]{2}(?:-[a-z]{2,4})?\/)?(?:drama\/(?:[^/]*-)?(\d{1,9})|episode\/(?:[^/]*-)?(\d{1,9})-(\d{1,4}))\/?$/i;
const SM_PLAYER = ["shortmax.ngeshorts.fun", "shortmax.dramafren.org"];

function parseShortMax(url) {
  if (SM_PLAYER.includes(url.hostname.toLowerCase())) return parsePlayerLink(url);
  const m = url.pathname.match(SM_PATH);
  return m ? { bookId: m[1] || m[2], lang: null, episode: m[3] ? Number(m[3]) : null } : null;
}

// NetShort : netshort.com/{langue}/episode/{slug}-{id} (…-ep-{n}), /full-episodes/{slug}-{id}, /hotseries/{slug}-{id},
// (cdn-)netshort.dramafren.org/index.php?page=detail&id={id}
const NS_PATH = /^\/(?:[a-z]{2}(?:-[a-z]{2,4})?\/)?(?:episode|full-episodes|hotseries)\/(?:[^/]*-)?(\d{15,20})(?:-ep-(\d{1,4}))?\/?$/i;
const NS_DRAMAFREN = ["netshort.dramafren.org", "cdn-netshort.dramafren.org"];

function parseNetShort(url) {
  if (NS_DRAMAFREN.includes(url.hostname.toLowerCase())) return parsePlayerLink(url, /^\d{15,20}$/);
  const m = url.pathname.match(NS_PATH);
  return m ? { bookId: m[1], lang: null, episode: m[2] ? Number(m[2]) : null } : null;
}

export const PROVIDERS = [
  { name: "dramabox", label: "DramaBox", hosts: ["dramaboxdb.com", "dramabox.com", "dramaboxapp.com", "dramafren.org"], parse: parseDramaBox },
  { name: "goodshort", label: "GoodShort", hosts: ["goodshort.com", ...GS_DRAMAFREN], parse: parseGoodShort },
  { name: "flickreels", label: "FlickReels", hosts: ["flickreels.net", ...FR_DRAMAFREN], parse: parseFlickReels },
  { name: "shortmax", label: "ShortMax", hosts: ["shorttv.live", "shortmax.com", ...SM_PLAYER], parse: parseShortMax },
  { name: "netshort", label: "NetShort", hosts: ["netshort.com", ...NS_DRAMAFREN], parse: parseNetShort },
];

// Longueur de l'hôte revendiqué le plus précis (0 : aucun) ; goodshort.dramafren.org l'emporte sur dramafren.org.
function claim(provider, host) {
  return Math.max(0, ...provider.hosts.filter((h) => host === h || host.endsWith(`.${h}`)).map((h) => h.length));
}
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
  const best = PROVIDERS.reduce((a, b) => (claim(b, host) > claim(a, host) ? b : a));
  const provider = claim(best, host) ? best : DEFAULT;
  const match = provider.parse(url);
  return match ? found(provider, "link", match) : { kind: "invalid" };
}

// « Lien GoodShort · série 31000662271 · FR »
export function linkLabel(d) {
  return `Lien ${d.label} · série ${d.bookId}${d.lang ? ` · ${d.lang.toUpperCase()}` : ""}`;
}

export const ACCEPTED =
  "Liens acceptés : DramaBox (dramaboxdb.com, dramabox.com, lien de partage de l'app, dramafren), GoodShort (goodshort.com, dramafren), FlickReels (flickreels.net, dramafren), ShortMax (shorttv.live, shortmax.ngeshorts.fun), NetShort (netshort.com, dramafren), le n° de série DramaBox (ex. 41000105199) ou plateforme:n° (ex. goodshort:31000662271, flickreels:9561, shortmax:24403, netshort:2103009231354593281).";

export const EXAMPLE_URL = "https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever";
