// Mise en forme fr-FR : « 684 Mo », « 1 h 32 », « 2 min 05 », « aujourd'hui à 18:52 ».

const n1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const n0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

export function bytes(value) {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return `${value} o`;
  if (value < 1e6) return `${n0.format(value / 1e3)} Ko`;
  if (value < 1e9) return `${(value < 1e8 ? n1 : n0).format(value / 1e6)} Mo`;
  return `${n1.format(value / 1e9)} Go`;
}

export function duration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h) return `${h} h ${String(m).padStart(2, "0")}`;
  if (m) return `${m} min ${String(r).padStart(2, "0")}`;
  return `${r} s`;
}

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${r}` : `${m}:${r}`;
}

const timeFmt = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const fullFmt = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" });

export function when(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const today = new Date();
  const start = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(today) - start(date)) / 86400000);
  if (days === 0) return `aujourd'hui à ${timeFmt.format(date)}`;
  if (days === 1) return `hier à ${timeFmt.format(date)}`;
  return `le ${dayFmt.format(date)} à ${timeFmt.format(date)}`;
}

export function fullDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : fullFmt.format(date);
}

export function plural(count, one, many) {
  return `${n0.format(count)} ${count > 1 ? many : one}`;
}

export function ranges(numbers) {
  const sorted = [...numbers].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < sorted.length; i++) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    out.push(i === j ? `${sorted[i]}` : `${sorted[i]}-${sorted[j]}`);
    i = j;
  }
  return out.join(", ");
}

// DramaBox utilise « in » pour l'indonésien (ISO : « id »).
const LANGS = {
  en: "anglais", fr: "français", es: "espagnol", pt: "portugais", de: "allemand", it: "italien",
  ko: "coréen", ja: "japonais", zh: "chinois", th: "thaï", in: "indonésien", id: "indonésien",
  ar: "arabe", tr: "turc", ru: "russe", vi: "vietnamien", hi: "hindi", tl: "tagalog", pl: "polonais",
};

export function langName(code) {
  return LANGS[code] || code || "langue inconnue";
}

export function htmlLang(code) {
  if (code === "in") return "id";
  return /^[a-z]{2,3}$/.test(code || "") ? code : undefined;
}

const SHORT = { fr: "VF", es: "VE" };

export function versionShort(version) {
  if (version.is_original) return "VO";
  return SHORT[version.lang] || (version.lang || "?").toUpperCase();
}

export function versionLong(version) {
  const name = langName(version.lang);
  if (version.is_original) return version.lang ? `VO (${name})` : "VO";
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function versionSlug(version) {
  return version.is_original ? "vo" : version.lang;
}

export function capitalize(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

const hourFmt = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
const weekdayFmt = new Intl.DateTimeFormat("fr-FR", { weekday: "long" });

// « 18:52 » aujourd'hui, « hier », puis le jour de la semaine ou la date.
export function shortWhen(iso) {
  const date = new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return "";
  const start = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(new Date()) - start(date)) / 86400000);
  if (days === 0) return hourFmt.format(date);
  if (days === 1) return "hier";
  if (days < 7) return weekdayFmt.format(date);
  return dayFmt.format(date);
}
