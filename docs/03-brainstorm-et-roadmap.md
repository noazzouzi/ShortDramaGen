# 03 — Brainstorm, risques et roadmap

## 1. Approches envisagées

| # | Approche | + | − | Verdict |
|---|---|---|---|---|
| **A** | Tout scraper sur dramafren (métadonnées + URLs) | Une seule source | Tout dépend du site le plus fragile ; lent ; pas de référence pour vérifier la complétude | ❌ |
| **B** | **Hybride** : métadonnées officielles, ép. 1-10 officiels, 11+ via dramafren | Source de vérité fiable ; dramafren sollicité au minimum ; contrôle d'intégrité exact | Deux sources à maintenir | ✅ **Retenue** |
| **C** | Userscript dans ton navigateur → `links.json` → downloader | Aucun souci Cloudflare ; très simple | Une action manuelle par série | ✅ En **repli** (mode C) |
| **D** | Rétro-ingénierie de l'API privée de l'app DramaBox (requêtes signées, comptes) | Indépendant de dramafren | Contournement direct du paywall (risque légal max) ; clés à extraire de l'APK, cassé à chaque mise à jour | ❌ Écartée |
| **E** | Services de résolution de CAPTCHA ou FlareSolverr pour passer Cloudflare depuis un serveur | Exécution 100 % serveur | Course aux armements, payant, contraire aux CGU, peu fiable sur Turnstile interactif | ❌ Écartée |
| **F** | Forger les URLs CDN (le chemin est calculable) | Pas de resolver | Impossible sans la clé de signature, et ce serait du contournement | ❌ Écartée |
| **G** | Enregistrement d'écran du lecteur | Marche partout | Qualité dégradée, temps réel, lourd | ❌ |

## 2. Risques et parades

| Risque | Probabilité | Parade |
|---|---|---|
| dramafren change son HTML ou son API | Élevée | Stratégie V1 par interception réseau, indépendante du DOM ; fixtures HAR + test de fumée |
| dramafren disparaît | Moyenne | Interface `Resolver` : brancher un autre miroir ou le mode C sans toucher au reste |
| Cloudflare durcit (cookie plus court, challenge à chaque page) | Moyenne | Profil persistant ou CDP sur ton vrai Chrome ; vitesse réduite |
| URLs signées expirées avant le téléchargement | Moyenne (CloudFront ~24 h) | Résolution juste avant le download, `expires_at` stocké, re-résolution auto sur 403 |
| Mauvais fichier associé à un épisode | Faible mais grave | `UrlValidator` (chapterId dans le chemin) + durée ffprobe = `duration_ms` |
| Le site officiel change `buildId` ou sa structure | Moyenne | Repli JSON → HTML `__NEXT_DATA__` ; validation pydantic qui échoue explicitement |
| Blocage IP côté dramafren (trop de requêtes) | Faible | 1 épisode à la fois, pauses aléatoires, cache des résolutions |
| Juridique (republication) | Dépend de l'usage | Voir [étude §7](01-etude-technique.md#7-cadre-légal-à-garder-en-tête) |

## 3. Questions ouvertes (à trancher ensemble)

1. **Finalité** : archive personnelle, ou matière première pour *générer* du
   contenu à publier (le nom « ShortDramaGen » le suggère) ? Cela change le
   post-traitement et le risque juridique.
2. **Où tourne l'outil ?** Sur ton PC (Windows, d'après les captures) : c'est
   compatible Cloudflare. Sur un serveur : dramafren bloquera, il faudra le
   mode C.
3. **Langue** : VO sous-titrée (ce que dramafren a renvoyé) ou version doublée
   (autre `bookId`, dispo sur le site officiel pour les 10 premiers
   épisodes) ? Les sous-titres sont-ils incrustés dans `narrowv3` ?
4. **Qualité** : seule la 720p a été observée. Existe-t-il du 1080p ? Le HAR
   le dira.
5. **Périmètre plateformes** : DramaBox seul pour la V1, ou d'emblée
   ReelShort, ShortMax, etc. ?

## 4. Roadmap proposée

| Phase | Contenu | Livrable | Dépend de |
|---|---|---|---|
| **0 — Recon** | Capture HAR dramafren (ci-dessous) | `research/` (non commité si cookies) | toi |
| **1 — POC officiel** | `InputParser`, `OfficialProvider`, `cdn.py`, `DownloadManager`, manifest ; télécharge les ép. 1-10 | `sdg info` / `sdg fetch --resolver official` | — (faisable tout de suite) |
| **2 — Resolver dramafren** | Mode A (Playwright persistant, interception réseau) puis V2 (endpoint direct) | `sdg fetch` complet 62/62 | Phase 0 |
| **3 — Robustesse** | Re-résolution sur 403, `verify`, reprise, logs, tests fixtures | Outil fiable en usage réel | 1, 2 |
| **4 — Confort** | Mode C (userscript), mode B (CDP), `concat`, export `links.json` | — | 2 |
| **5 — Gen** | Pistes ci-dessous | — | réponse Q1 |

## 5. Action demandée : capture HAR

Pour écrire le `DramaFrenResolver`, j'ai besoin de voir comment la page obtient
l'URL MP4 :

1. Chrome → ouvre `https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr`
   et passe le challenge Cloudflare.
2. `F12` → onglet **Network** → coche **Preserve log** et **Disable cache**,
   puis clique sur 🚫 (Clear).
3. Clique sur **Ep 1**, attends que la vidéo démarre, reviens en arrière,
   clique sur **Ep 28**.
4. Clic droit dans la liste → **Save all as HAR (sanitized)** (cette option
   retire les cookies ; sinon utilise « Save all as HAR » et ne le commite pas).
5. Onglet **Elements** : clic droit sur la grille d'épisodes → *Copy* →
   *Copy outerHTML*, puis colle-le dans un fichier `.html`.
6. Dépose les deux fichiers dans `research/` (ignoré par git) ou envoie-les-moi.

À chercher dans le HAR : la requête (Doc, Fetch/XHR) qui précède le chargement
du `.mp4` et qui contient l'URL `hwztakavideoto…` dans sa réponse.

## 6. Idées pour la suite (« Gen »)

- **Film complet** : concaténation sans ré-encodage (`ffmpeg -f concat -c copy`),
  avec chapitres par épisode.
- **Sous-titres** : transcription Whisper, puis traduction FR/EN et
  incrustation ou `.srt`.
- **Découpage intelligent** : détection de scènes (PySceneDetect) et repérage
  des cliffhangers en fin d'épisode.
- **Veille** : suivre des séries et télécharger automatiquement les nouveaux
  épisodes (comparaison `chapterCount`).
- **Catalogue local** : index SQLite des séries téléchargées (tags, acteurs,
  durées) et recherche.
- **UI web locale** : coller une URL, suivre la progression, visionner.
- **Recherche de niches** : croiser les tags et genres DramaBox avec des
  données de tendance YouTube pour choisir quoi traiter. Seulement dans un
  cadre de licence si publication (voir étude §7).
