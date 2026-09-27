// Commandes de l'interface : appel à l'API, puis toast de résultat (ou d'erreur).
// Chaque fonction renvoie la réponse, ou null si la commande a échoué (l'erreur a déjà été dite).

import { ApiError, del, post, patch } from "./api.js";
import { toast } from "./ui.js";
import { bytes, plural, versionShort } from "./format.js";

export function makeActions(ctx) {
  const fail = (err, fallback) => {
    if (err instanceof ApiError && err.code === "unreachable") {
      toast({ tone: "error", text: "Le moteur ne répond pas. Vérifie que sdg ui est toujours lancé." });
    } else if (err instanceof ApiError && err.code === "duplicate_job") {
      toast({ tone: "info", text: "C'est déjà dans la file.", actions: [{ label: "Voir", onClick: () => ctx.openDrawer() }] });
    } else if (err instanceof ApiError && err.code === "series_busy") {
      toast({ tone: "warning", text: err.message || "Un téléchargement est en cours sur cette série.", actions: [{ label: "Voir", onClick: () => ctx.openDrawer() }] });
    } else {
      toast({ tone: "error", text: err.message || fallback || "Quelque chose s'est mal passé." });
    }
    return null;
  };

  const queued = (job, what) => {
    const position = job.position && job.position > 1 ? ` · ${job.position}e` : "";
    toast({ tone: "success", text: `${what} · ${job.title || "série"}${position}`, actions: [{ label: "Voir", onClick: () => ctx.openDrawer() }] });
    ctx.onJob(job);
    return job;
  };

  return {
    async addFetch(body, what = "Ajouté à la file") {
      try {
        return queued((await post("/api/jobs", { kind: "fetch", ...body })).data.job, what);
      } catch (err) {
        return fail(err);
      }
    },

    async retry(key, body = {}, what = "Réparation lancée") {
      try {
        return queued((await post(`/api/series/${encodeURIComponent(key)}/retry`, body)).data.job, what);
      } catch (err) {
        if (err instanceof ApiError && err.code === "nothing_to_do") {
          toast({ tone: "info", text: err.message });
          return null;
        }
        return fail(err);
      }
    },

    async redownload(key, episodes, quality) {
      try {
        const job = (await post(`/api/series/${encodeURIComponent(key)}/redownload`, { episodes, quality })).data.job;
        return queued(job, `${plural(episodes.length, "épisode", "épisodes")} à retélécharger en ${quality}`);
      } catch (err) {
        return fail(err);
      }
    },

    async repairAll(dryRun) {
      try {
        const res = await post("/api/repair", { dry_run: dryRun });
        if (!dryRun) {
          const n = res.data.jobs.length;
          toast({ tone: "success", text: n ? `Réparation lancée pour ${plural(n, "série", "séries")}.` : "Rien à réparer.", actions: n ? [{ label: "Voir", onClick: () => ctx.openDrawer() }] : [] });
          res.data.jobs.forEach(ctx.onJob);
        }
        return res.data;
      } catch (err) {
        return fail(err);
      }
    },

    async jobCommand(job, command, body) {
      try {
        const res = await post(`/api/jobs/${encodeURIComponent(job.id)}/${command}`, body);
        ctx.onJob(res.data.job);
        return res.data.job;
      } catch (err) {
        return fail(err);
      }
    },

    async removeJob(job) {
      try {
        await del(`/api/jobs/${encodeURIComponent(job.id)}`);
        ctx.onJob({ ...job, removed: true });
        return true;
      } catch (err) {
        return fail(err);
      }
    },

    // Création du film : les erreurs de pré-vol (ffmpeg absent, épisodes manquants…) remontent à l'appelant.
    async createFilm(key, options = {}) {
      try {
        const res = await post(`/api/series/${encodeURIComponent(key)}/film`, options);
        if (res.data.reused) {
          toast({ tone: "success", text: `Le film est déjà à jour : ${res.data.film.file}.` });
          return res.data;
        }
        return queued(res.data.job, "Création du film");
      } catch (err) {
        if (err instanceof ApiError && ["film_exists", "film_missing_episodes", "film_mixed_formats", "ffmpeg_missing", "no_episodes"].includes(err.code)) {
          throw err;
        }
        return fail(err);
      }
    },

    async deleteSeries(version, scope) {
      const key = version.series_key;
      try {
        const res = await del(`/api/series/${encodeURIComponent(key)}?scope=${scope}`);
        ctx.refresh();
        const what = { all: `${version.title} (${versionShort(version)}) supprimée`, episodes: "Épisodes supprimés, le film reste", film: "Film supprimé", parts: "Fichiers partiels supprimés" }[scope];
        const freed = res.data.freed_bytes ? ` · ${bytes(res.data.freed_bytes)} libérés` : "";
        toast({
          tone: "success",
          text: `${what}${freed}`,
          actions: res.data.trash_id ? [{ label: "Annuler", onClick: () => this.restore(res.data.trash_id) }] : [],
          timeout: res.data.trash_id ? 10000 : 5000,
        });
        return res.data;
      } catch (err) {
        if (err instanceof ApiError && err.code === "file_locked") {
          toast({ tone: "error", text: `${err.message}${err.details?.files ? ` (${err.details.files.slice(0, 3).join(", ")})` : ""}` });
          ctx.refresh();
          return null;
        }
        return fail(err);
      }
    },

    async restore(trashId) {
      try {
        await post(`/api/trash/${encodeURIComponent(trashId)}/restore`);
        toast({ tone: "success", text: "Suppression annulée." });
        ctx.refresh();
        return true;
      } catch (err) {
        return fail(err);
      }
    },

    async open(key, target = "folder", extra = {}) {
      try {
        await post(`/api/series/${encodeURIComponent(key)}/open`, { target, ...extra });
        return true;
      } catch (err) {
        return fail(err, "Impossible d'ouvrir ce fichier.");
      }
    },

    async openLibrary() {
      try {
        await post("/api/library/open");
        return true;
      } catch (err) {
        return fail(err, "Impossible d'ouvrir le dossier.");
      }
    },

    async ignore(key, problem, ignored = true) {
      try {
        const res = await post(`/api/series/${encodeURIComponent(key)}/ignore`, { problem, ignored });
        toast({
          tone: "info",
          text: ignored ? "Problème masqué dans « À traiter »." : "Problème de nouveau signalé.",
          actions: ignored ? [{ label: "Annuler", onClick: () => this.ignore(key, problem, false) }] : [],
        });
        ctx.refresh();
        return res.data;
      } catch (err) {
        return fail(err);
      }
    },

    // Réglages : l'erreur de validation remonte au champ concerné.
    async settings(changes) {
      const res = await patch("/api/settings", changes);
      ctx.onSettings(res.data);
      return res.data;
    },

    async shutdown() {
      try {
        await post("/api/shutdown");
        return true;
      } catch (err) {
        return fail(err);
      }
    },

    fail,
  };
}
