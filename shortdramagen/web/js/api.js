// Appels à l'API locale. Le jeton de page est écrit dans index.html par le serveur.

const TOKEN = document.querySelector('meta[name="sdg-token"]')?.content || "";

export class ApiError extends Error {
  constructor(status, code, message, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details || {};
  }
}

async function call(method, path, { body, etag } = {}) {
  const headers = { "X-SDG-Token": TOKEN, Accept: "application/json" };
  if (etag) headers["If-None-Match"] = etag;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "unreachable", "Le moteur ne répond pas.");
  }
  if (response.status === 304) return { status: 304, data: null, etag };
  let data = null;
  if (response.status !== 204) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }
  if (!response.ok) {
    const err = data?.error || {};
    throw new ApiError(response.status, err.code || "internal", err.message || `Erreur ${response.status}`, err.details);
  }
  return { status: response.status, data, etag: response.headers.get("ETag") };
}

// Réponse : { status, data, etag }. 304 → data vaut null (rien n'a changé).
export const get = (path, options) => call("GET", path, options);
export const post = (path, body = {}) => call("POST", path, { body });
export const patch = (path, body) => call("PATCH", path, { body });
export const put = (path, body) => call("PUT", path, { body });
export const del = (path) => call("DELETE", path);
