# 03 — Brainstorm, risques et roadmap

## 1. Approches envisagées

| # | Approche | + | − | Verdict |
|---|---|---|---|---|
| **H** | **Métadonnées officielles + API `get_video` de dramafren en HTTP simple** | Pas de navigateur, marche partout, rapide (62 ép. en ~1 min 40), jusqu'au 1080p | Dépend d'une API non documentée | ✅ **Implémentée (V1)** |
| B | Hybride avec navigateur piloté (Playwright, profil persistant) pour passer Cloudflare | Imite parfaitement l'humain | Lourd, lent, uniquement sur ta machine | 🅿️ **Plan B** si l'API se ferme |
| C | Userscript dans ton navigateur → `links.json` → downloader | Aucun souci de détection | Une action manuelle par série | 🅿️ Plan C |
| A | Tout scraper sur les pages HTML dramafren | — | Derrière Cloudflare, fragile | ❌ |
| D | Rétro-ingénierie de l'API privée de l'app DramaBox | Indépendant de dramafren | Contournement direct du paywall, clés à extraire de l'APK | ❌ Écartée |
| E | Services de résolution de CAPTCHA / FlareSolverr | — | Inutile depuis la découverte de l'API ; fragile, contraire aux CGU | ❌ |
| F | Forger les URLs CDN (le chemin est calculable) | — | Impossible sans la clé de signature | ❌ |

## 2. Risques et parades

| Risque | Probabilité | Parade en place / prévue |
|---|---|---|
| dramafren protège ou modifie `get_video` | Moyenne | Module isolé (`dramafren.py`) ; secours `cdn-dramaboxv2` ; plan B (navigateur) documenté |
| dramafren renvoie l'URL d'un autre épisode | Faible | ✅ `cdn.matches_episode` rejette l'URL |
| Fichier tronqué ou mauvais contenu | Faible | ✅ Taille = `Content-Length`, durée MP4 = durée officielle ±1 s |
| Coupure réseau en plein téléchargement | Moyenne | ✅ `.part` par variante + reprise `Range` ; relancer la commande suffit |
| URL signée expirée | Faible (~3 semaines) | ✅ `403` → source suivante puis nouvelle résolution ; expiration dans le manifest |
| Série absente du site officiel | Faible | ✅ Mode sonde via dramafren (sans contrôle de durée) |
| Le site officiel change sa structure | Moyenne | Échec explicite (`SeriesNotFound`) + mode sonde ; fixtures pour détecter la casse |
| Blocage IP pour abus | Faible | ✅ Appels API espacés de 0,3 s ; 3 téléchargements CDN en parallèle maximum par défaut |

## 3. Réponses aux questions ouvertes

1. **Finalité** : défi technique personnel. Pas de republication, donc pas de
   post-traitement orienté diffusion.
2. **Où tourne l'outil ?** N'importe où : l'API n'est pas derrière Cloudflare
   (testé depuis un serveur cloud).
3. **Langue** : peu importe. Par défaut on prend la VO (celle de l'URL), sinon
   `--lang fr|es|…` pour une version doublée si elle existe (vérifié : VF et
   VE de la série de test).
4. **Qualité** : 540p, 720p et 1080p disponibles. Par défaut la meilleure
   (`-q best`).
5. **Plateformes** : DramaBox uniquement en V1.

## 4. Roadmap

| Phase | Contenu | Statut |
|---|---|---|
| 0 — Recon | Étude, HAR, découverte de l'API `get_video` | ✅ Fait |
| 1 — Métadonnées | `inputs`, `official`, `cdn`, mode sonde | ✅ Fait |
| 2 — Résolution | `dramafren.get_video` + secours officiel | ✅ Fait |
| 3 — Téléchargement fiable | Parallélisme, reprise, contrôle de durée, manifest, source suivante sur échec | ✅ Fait — validé : 62/62 en VF 1080p, 684 Mo, 1 min 38 s |
| 4 — Confort | `sdg verify`, `sdg concat` (un seul fichier « film »), barre de progression globale, file de plusieurs séries | À faire |
| 5 — Multi-plateformes | Vérifier les API `cdn-<plateforme>.dramafren.org` (ReelShort, ShortMax…) | À explorer |
| 6 — Plan B | Resolver navigateur (Playwright) si l'API se ferme | Seulement si besoin |

## 5. Idées pour la suite du défi

- **Film complet** : concaténation sans ré-encodage (`ffmpeg -f concat -c copy`)
  avec un chapitre par épisode.
- **Veille** : relancer périodiquement sur une liste de séries et ne
  télécharger que les nouveaux épisodes. Le manifest le permet déjà.
- **Catalogue local** : index des séries téléchargées (tags, acteurs, durées).
- **Statistiques** : débit moyen, taille par qualité, temps par série.
- **Sous-titres** : `subtitles` est vide pour DramaBox aujourd'hui. À
  surveiller dans la réponse `get_video`.
