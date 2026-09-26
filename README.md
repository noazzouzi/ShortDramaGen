# ShortDramaGen

Récupère automatiquement **tous les épisodes** d'une série DramaBox à partir
d'une simple URL : jusqu'en 1080p, avec reprise sur coupure et vérification
de chaque fichier.

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

Il faut seulement **Python ≥ 3.10**. Aucune dépendance, aucun navigateur,
aucun ffmpeg.

```bash
git clone https://github.com/noazzouzi/ShortDramaGen.git
cd ShortDramaGen
python -m shortdramagen --help        # utilisable tel quel
pip install -e .                      # optionnel : ajoute la commande « sdg »
```

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
```

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
└── manifest.json      # titre, épisodes, statut, qualité, URL et expiration, taille
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

## Documentation

| Doc | Contenu |
|---|---|
| [01 — Étude technique](docs/01-etude-technique.md) | Constats vérifiés : API dramafren, CDN, site officiel, formats d'URL, cadre légal |
| [02 — Architecture](docs/02-architecture.md) | Composants, flux, manifest, choix techniques |
| [03 — Brainstorm & roadmap](docs/03-brainstorm-et-roadmap.md) | Approches comparées, risques, plans B, suite |

## Tests

```bash
python -m unittest discover -s tests      # 25 tests, hors ligne, ~30 ms
```

## Avertissement

Projet personnel, à but d'apprentissage. Le contenu appartient à DramaBox
(STORYMATRIX). Ne republie pas les vidéos téléchargées : voir
[étude §7](docs/01-etude-technique.md#7-cadre-légal-à-garder-en-tête).
