# ShortDramaGen

Récupère automatiquement **tous les épisodes** d'une série DramaBox à partir
d'une simple URL : jusqu'en 1080p, avec reprise sur coupure et vérification
de chaque fichier. L'outil peut ensuite les **fusionner en un seul film** avec
un chapitre par épisode.

```text
$ python -m shortdramagen fetch "https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr" --lang fr
« Qui Est la Véritable Mme Lafont ? » : 62 épisodes -> downloads/41000105199-one-night-to-forever-fr
[ 1/62] E001 1080p   21.2 Mo  OK
[ 2/62] E002 1080p   13.0 Mo  OK
…
[62/62] E062 1080p   13.9 Mo  OK

Terminé : 62 épisode(s) OK (62 téléchargé(s), 0 déjà présent(s)), 0 échec(s).
```

## Installation

Pour télécharger, il faut seulement **Python ≥ 3.10** : aucune dépendance,
aucun navigateur.

```bash
git clone https://github.com/noazzouzi/ShortDramaGen.git
cd ShortDramaGen
python -m shortdramagen --help        # utilisable tel quel
pip install -e .                      # optionnel : ajoute la commande « sdg »
```

Pour la **fusion en film**, il faut aussi ffmpeg. Le plus simple est
`pip install imageio-ffmpeg` (ou `pip install -e ".[ffmpeg]"`), qui fournit
ffmpeg sans installation système. Sinon : `winget install Gyan.FFmpeg`
(Windows), `brew install ffmpeg` (macOS) ou `apt install ffmpeg` (Linux).

Sous Windows, remplace `python` par `py` si besoin.

## Utilisation

```bash
# Infos de la série (titre, nb d'épisodes, langues, qualités dispo), sans téléchargement
python -m shortdramagen info https://www.dramaboxdb.com/movie/41000105199/one-night-to-forever

# Tout télécharger (meilleure qualité, dans ./downloads)
python -m shortdramagen fetch 41000105199

# Version doublée, en 720p, seulement certains épisodes, 4 en parallèle
python -m shortdramagen fetch 41000105199 --lang fr -q 720p -e 1-10,28,50- -j 4

# Juste les URLs (pour aria2c, IDM…) ; --json pour un export complet
python -m shortdramagen links 41000105199 -q 1080p > liens.txt

# Télécharger puis fusionner en un seul film (un chapitre par épisode)
python -m shortdramagen fetch 41000105199 --lang fr --film

# Fusionner une série déjà téléchargée (identifiant, URL ou dossier)
python -m shortdramagen film 41000105199 --lang fr
python -m shortdramagen film "downloads/41000105199-one-night-to-forever" -f "C:/Films/One Night.mp4"
```

### Fusion en film

- **Sans ré-encodage** : les épisodes d'une même qualité ont exactement les
  mêmes paramètres (vérifié avant la fusion). Le film se crée en quelques
  secondes, sans perte de qualité : 62 épisodes → 1 h 32, 717 Mo, **6 s**.
- **Chapitres** « Épisode 1 », « Épisode 2 »… pour naviguer dans VLC, mpv,
  MPC-HC, etc. (`--no-chapters` pour les désactiver).
- **Contrôles** : durée finale vérifiée. Synchro audio/vidéo mesurée à moins de
  1 ms d'écart par rapport aux épisodes d'origine, sans dérive sur 62 épisodes.
- **Qualités mélangées** (ex. un épisode en 720p dans une série en 1080p) :
  l'outil refuse et explique pourquoi. Deux solutions :
  - retélécharger ces épisodes dans la même qualité ;
  - `--reencode`, qui ré-encode tout (H.264/AAC) à la résolution majoritaire.
    C'est beaucoup plus lent.
- **Épisodes manquants** : refus par défaut ; `--allow-missing` fusionne ce
  qui est là. Un film partiel est nommé `Titre (épisodes 1-10).mp4`.
- Avec `fetch -e … --film`, le film contient exactement les épisodes demandés.

**Entrées acceptées** : URL `dramaboxdb.com` (série ou épisode, avec ou sans
`/fr/`), `dramabox.com/drama/…`, lien de partage de l'app, URL dramafren
(`detail` ou `watch`), ou l'identifiant seul (`41000105199`).

**Langue** : par défaut, la version de l'URL (VO en général). `--lang fr`,
`es`, `ko`… prend la version doublée si elle existe. Sinon l'outil prévient et
garde la VO (`info` liste les langues disponibles).

**Relancer la même commande** ne fait que ce qui manque. C'est aussi comme ça
qu'on reprend après une coupure ou un Ctrl+C.

### Résultat

```text
downloads/41000105199-one-night-to-forever-fr/
├── E001.mp4 … E062.mp4
├── Qui Est la Véritable Mme Lafont.mp4   # avec --film ou « sdg film »
└── manifest.json      # titre, épisodes, statut, qualité, URL et expiration, taille, film
```

## Comment ça marche

1. **Métadonnées** depuis le site officiel `dramaboxdb.com` : liste des
   épisodes, durées exactes, identifiant de la version doublée.
2. **URLs signées** depuis l'API `get_video` de dramafren (découverte grâce
   aux captures HAR). Elle n'est pas protégée par Cloudflare et fournit du
   540p, du 720p et du 1080p. Les MP4 gratuits du site officiel servent de
   secours pour les épisodes 1 à 10.
3. **Téléchargement** direct depuis le CDN (3 en parallèle, reprise par
   `Range`), puis **vérifications** :
   - l'URL doit pointer vers le bon épisode (le chemin CDN est déterministe) ;
   - la durée du MP4 doit égaler la durée officielle à ±1 s.
4. **Fusion** (option) : ffmpeg concatène les épisodes sans ré-encodage, avec
   une durée imposée pour chacun et des chapitres calculés sur ces mêmes
   durées (voir [architecture §3.9](docs/02-architecture.md#39-filmpy--fusion-en-un-seul-film)).

## Documentation

| Doc | Contenu |
|---|---|
| [01 — Étude technique](docs/01-etude-technique.md) | Constats vérifiés : API dramafren, CDN, site officiel, formats d'URL, cadre légal |
| [02 — Architecture](docs/02-architecture.md) | Composants, flux, manifest, choix techniques |
| [03 — Brainstorm & roadmap](docs/03-brainstorm-et-roadmap.md) | Approches comparées, risques, plans B, suite |

## Tests

```bash
python -m unittest discover -s tests      # 42 tests, hors ligne, < 1 s
# (3 tests de fusion utilisent un vrai ffmpeg ; ils sont ignorés s'il est absent)
```

## Avertissement

Projet personnel, à but d'apprentissage. Le contenu appartient à DramaBox
(STORYMATRIX). Ne republie pas les vidéos téléchargées : voir
[étude §7](docs/01-etude-technique.md#7-cadre-légal-à-garder-en-tête).
