// Appels à l'API locale. Le jeton de page est écrit dans index.html par le serveur.

const TOKEN = document.querySelector('meta[name="sdg-token"]')?.content || "";

export class ApiError extends Error {
  constructor(status, code, message, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Réponse : { status, data, etag }. 304 → data vaut null (rien n'a changé).
export async function get(path, { etag } = {}) {
  const headers = { "X-SDG-Token": TOKEN, Accept: "application/json" };
  if (etag) headers["If-None-Match"] = etag;
  let response;
  try {
    response = await fetch(path, { headers, cache: "no-store", credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "unreachable", "Le moteur ne répond pas.");
  }
  if (response.status === 304) return { status: 304, data: null, etag };
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const err = data?.error || {};
    throw new ApiError(response.status, err.code || "internal", err.message || `Erreur ${response.status}`, err.details);
  }
  return { status: response.status, data, etag: response.headers.get("ETag") };
}
