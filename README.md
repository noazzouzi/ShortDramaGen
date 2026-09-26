# ShortDramaGen

Récupérer automatiquement **tous les épisodes** d'une série de short drama
(DramaBox pour commencer) à partir d'une simple URL.

```bash
sdg fetch https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever
# -> downloads/41000105199-one-night-to-forever/E001.mp4 … E062.mp4 + manifest.json
```

> **Statut : phase d'étude.** Aucun code pour l'instant, seulement l'analyse
> technique et l'architecture cible.

## Documentation

| Doc | Contenu |
|---|---|
| [01 — Étude technique](docs/01-etude-technique.md) | Constats vérifiés : dramafren, CDN, site officiel, formats d'URL, cadre légal |
| [02 — Architecture](docs/02-architecture.md) | Composants, flux, modèle de données, stack, arborescence |
| [03 — Brainstorm & roadmap](docs/03-brainstorm-et-roadmap.md) | Approches comparées, risques, questions ouvertes, phases, capture HAR |

## En bref

- Le **site officiel** `dramaboxdb.com` donne en JSON, sans protection, la
  liste complète des épisodes (IDs, durées) et les MP4 des **10 premiers**.
- **dramafren** donne une URL pour **tous** les épisodes, mais il est protégé
  par Cloudflare Turnstile. Il faut donc piloter un navigateur **sur ta
  machine**, avec une session humaine.
- Les fichiers viennent d'un **CDN à URL signée** (validité ~3 semaines),
  sans autre protection. Le téléchargement direct est reprenable et
  parallélisable.
- Le chemin CDN est **déterministe** (`bookId` inversé + `chapterId`). On s'en
  sert pour vérifier chaque URL, et la durée officielle permet de contrôler
  chaque fichier.
