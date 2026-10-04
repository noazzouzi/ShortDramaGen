# ShortDramaGen

Récupère automatiquement **tous les épisodes** d'une série DramaBox, GoodShort,
FlickReels, ShortMax ou NetShort à partir d'une simple URL : jusqu'en 1080p, avec reprise sur coupure et vérification de chaque
fichier. L'outil peut ensuite les **fusionner en un
seul film** avec un chapitre par épisode.

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

Pour la **fusion en film** et pour les plateformes servies en HLS
(GoodShort, FlickReels, ShortMax), il faut aussi ffmpeg. Le plus simple est
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
  `fetch --film` accepte les mêmes options que `film` ; si des épisodes ont
  échoué, le film n'est créé qu'avec `--allow-missing`.
- **Film existant** : jamais écrasé en silence. S'il est à jour (mêmes
  épisodes, aucun modifié depuis), il est simplement réutilisé ; sinon l'outil
  refuse. `--replace` le reconstruit, `-f` choisit un autre nom.

### Montage (retouches avant le film)

```bash
# Miroir (les sous-titres incrustés restent lisibles), 3 s coupées au début et 4 s à la fin de chaque épisode
python -m shortdramagen montage set goodshort:31000835255 --mirror --trim-start 3 --trim-end 4 --look vif
# Un épisode : passage accéléré, passage coupé
python -m shortdramagen montage set goodshort:31000835255 -e 17 --range 0:40-0:55x1.5 --cut 1:20-1:32
python -m shortdramagen montage preview goodshort:31000835255 -e 17 --at 0:38   # 8 s rendues pour juger
python -m shortdramagen film goodshort:31000835255 --montage                   # film monté
python -m shortdramagen montage show goodshort:31000835255
```

- Les épisodes téléchargés ne sont jamais modifiés. Chaque épisode est
  retouché une fois dans `<série>/montage/`, puis le film est assemblé sans
  ré-encodage. Modifier un épisode ne refait que lui.
- **Miroir** : les sous-titres incrustés par la plateforme sont recollés à
  l'endroit (`--no-keep-subs` pour tout retourner). Leur zone est repérée
  automatiquement ; `--band 74-84` la force.
- **Autres réglages** : looks `vif`, `doux`, `nb` (et `--brightness`,
  `--contrast`, `--saturation`), vitesse globale `--speed 1.25`. L'encodeur
  est AMD (AMF) s'il marche, sinon x264 (`--encoder`, `--quality compacte`).
- Le film monté **remplace** le film brut, qui se refait en quelques secondes.
- **Durée** : environ 5 à 7 fois plus vite que la lecture (60 épisodes :
  15 à 25 min), puis quelques secondes d'assemblage. Tout est aussi réglable
  dans la carte « Montage » de `sdg ui`. Détails :
  [06 — Montage](docs/06-montage.md).

### Interface web

```bash
python -m shortdramagen ui                       # ouvre http://127.0.0.1:8765/ dans le navigateur
python -m shortdramagen ui -o "D:/Séries"        # autre dossier (mémorisé pour la suite)
python -m shortdramagen ui --window              # fenêtre d'application Edge/Chrome, sans barre d'adresse
```

- **Ajouter** : colle un lien n'importe où dans la page (ou dans le champ du
  haut) ; un aperçu montre l'affiche, le nombre d'épisodes, la durée, les
  versions et la place nécessaire. On choisit la langue, la qualité, les
  épisodes, et si le film doit être créé à la fin.
- **Bibliothèque** : un mur d'affiches (ou une liste), avec l'état de chaque
  série (complète, à compléter, avec échecs, interrompue, film prêt), une
  recherche, des filtres, une étagère « À traiter » avec « Tout réparer » et
  la sélection multiple. Les versions d'une même série (VO, VF…) sont
  regroupées.
- **Fiche série** : tous les épisodes en grille, avec le détail de chaque
  problème (échec, indisponible, fichier supprimé, 720p isolé…) et un bouton
  pour chaque remède (Réparer, Reprendre, Compléter, Retélécharger), la carte
  Film (vérifications avant création, puis création en un clic), la place
  occupée et la suppression annulable.
- **Lecture** dans le navigateur, épisode par épisode (enchaînement
  automatique) ou le film avec ses chapitres.
- **En direct** : la progression s'affiche dans l'en-tête (« ↓ 21/80 · ≈ 1 min »)
  et dans le titre de l'onglet, les épisodes se colorent au fur et à mesure.
- **Le serveur télécharge lui-même** : file de téléchargements et de films
  (tiroir Activité), pause, reprise à l'octet près, annulation, réparation.
  Si tu fermes la fenêtre ou si Internet coupe, tout reprend tout seul
  ensuite. Tout a aussi son API ([architecture §3.12](docs/02-architecture.md#312-jobs-et-temps-réel-étape-2)).
- **Réglages** : dossier, langue préférée, qualité, téléchargements en
  parallèle, film automatique, thème sombre ou clair, raccourcis clavier
  (`?` pour la liste), santé (réseau, ffmpeg, disque).
- Tout reste **local** : le serveur n'écoute que sur `127.0.0.1` et refuse
  les requêtes des autres sites. Les liens signés de la source ne sont
  jamais affichés.

**Entrées acceptées** :
- **DramaBox** : URL `dramaboxdb.com` (série ou épisode, avec ou sans `/fr/`),
  `dramabox.com/drama/…`, lien de partage de l'app, URL dramafren (`detail` ou
  `watch`), ou l'identifiant seul (`41000105199`).
- **GoodShort** : URL dramafren
  (`goodshort.dramafren.org/index.php?page=detail&id=31000835255…`, ou
  `watch`), URL `goodshort.com/drama/…`, `/episodes/…` ou `/episode/…`, ou
  `goodshort:31000662271`. Tous les épisodes, payants compris, viennent de
  dramafren (HLS, donc ffmpeg requis).
- **FlickReels** : URL dramafren
  (`flickreels.dramafren.org/index.php?page=detail&id=9561…`, ou `watch`), URL
  `flickreels.net/…/episodes-list/…`, `/movie/…` ou `/playlist/…`, ou
  `flickreels:9561`. Tout vient de dramafren (HLS, donc ffmpeg requis).
- **ShortMax** : URL du lecteur
  (`shortmax.ngeshorts.fun/index.php?page=detail&id=24403…`, ou `watch`), URL
  `shorttv.live/…/drama/…` ou `/episode/…` (ex-`shortmax.com`), ou
  `shortmax:24403`. Tout vient du lecteur (HLS, donc ffmpeg requis).
- **NetShort** : URL `netshort.com/…/episode/…` (série ou épisode,
  `-ep-12`), `/full-episodes/…`, URL dramafren
  (`netshort.dramafren.org/index.php?page=detail&id=…`, ou `watch`), ou
  `netshort:2103009231354593281`. Tous les épisodes, en MP4 sans ffmpeg :
  540p depuis dramafren, 720p depuis le site officiel pour les gratuits (les
  7 à 9 premiers en général). Chaque version (VF…) a son propre lien ; ses
  sous-titres sont enregistrés à côté de l'épisode (`E001.fr.vtt`).

**Langue** : par défaut, la version de l'URL (VO en général). `--lang fr`,
`es`, `ko`… prend la version doublée si elle existe. Sinon l'outil prévient et
garde la VO (`info` liste les langues disponibles).

**Relancer la même commande** ne fait que ce qui manque. C'est aussi comme ça
qu'on reprend après une coupure ou un Ctrl+C : les épisodes interrompus
repartent de leur `.part`.

### Résultat

```text
downloads/41000105199-one-night-to-forever-fr/
├── E001.mp4 … E062.mp4
├── E001.fr.vtt …      # sous-titres à part (NetShort), lus par VLC
├── cover.jpg          # affiche de la série (pour l'interface)
├── Qui Est la Véritable Mme Lafont.mp4   # avec --film ou « sdg film »
└── manifest.json      # titre, épisodes, statut, qualité, URL et expiration, taille, code d'erreur, film
```

## Comment ça marche

Le moteur est commun à toutes les plateformes ; ce qui est propre à chacune
(liens, métadonnées, sources vidéo) vit dans `shortdramagen/providers/`
(voir [architecture §7](docs/02-architecture.md#7-plateformes-providers)). Pour DramaBox :

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

Pour GoodShort, les métadonnées viennent aussi du site officiel
(`goodshort.com`, liste complète des chapitres) et les vidéos de l'API
`get_video_url` de dramafren : des playlists HLS en 540p, 720p et 1080p,
passant par le proxy de dramafren, remuxées en MP4 par ffmpeg. Ce proxy est
**lent et irrégulier** : de 1 s à plus d'une minute par segment de 5 s. Le
27/09/2026, 2 épisodes (1 min 30 et 1 min 43) ont pris 15 min. Augmenter `-j`
aide, car l'attente vient de la latence de chaque requête (voir
[plateformes](docs/05-plateformes.md#vidéos-via-dramafren)).

Pour FlickReels, tout vient du lecteur de dramafren : titre, affiche et nombre
d'épisodes sur sa fiche, et pour chaque épisode l'URL HLS du CDN officiel
(1080p, rapide). L'API du site officiel signe ses appels : elle n'est pas
utilisée, donc pas de durée officielle. Chaque fichier est vérifié contre la
durée de sa playlist (voir [plateformes](docs/05-plateformes.md#flickreels)).
ShortMax fonctionne de même avec le lecteur `shortmax.ngeshorts.fun` et son
API `video_server` : 1080p, 720p ou 480p, depuis le CDN officiel (voir
[plateformes](docs/05-plateformes.md#shortmax)).

Pour NetShort, la page de chaque épisode sur le site officiel `netshort.com`
donne sa durée (pour le contrôle) et, pour un épisode gratuit, sa vidéo (MP4
720p) et ses sous-titres WebVTT. Les autres épisodes viennent de l'API
`resolve_watch` du lecteur dramafren, servie sans challenge par
`cdn-netshort.dramafren.org` (MP4 540p du CDN officiel, sous-titres) (voir
[plateformes](docs/05-plateformes.md#netshort)).

## Documentation

| Doc | Contenu |
|---|---|
| [01 — Étude technique](docs/01-etude-technique.md) | Constats vérifiés : API dramafren, CDN, site officiel, formats d'URL, cadre légal |
| [02 — Architecture](docs/02-architecture.md) | Composants, flux, manifest, moteur pilotable (événements, codes d'erreur), choix techniques |
| [03 — Brainstorm & roadmap](docs/03-brainstorm-et-roadmap.md) | Approches comparées, risques, plans B, suite |
| [04 — Frontend](docs/04-frontend.md) | Interface web : recherche, 3 concepts et jury, spec, système visuel, API, maquette, avancement (étapes 0 à 3 livrées) |
| [05 — Plateformes](docs/05-plateformes.md) | Plateformes au-delà de DramaBox : état de l'étude, constats GoodShort, FlickReels, ShortMax et NetShort, points non vérifiés |
| [06 — Montage](docs/06-montage.md) | Retouches avant le film : miroir avec sous-titres gardés, coupes, looks, passages accélérés ; mesures ffmpeg |

## Tests

```bash
python -m unittest discover -s tests      # 213 tests, hors ligne, environ 29 s
# (4 tests de fusion utilisent un vrai ffmpeg ; ils sont ignorés s'il est absent)
```

## Avertissement

Projet personnel, à but d'apprentissage. Le contenu appartient à DramaBox
(STORYMATRIX). Ne republie pas les vidéos téléchargées : voir
[étude §7](docs/01-etude-technique.md#7-cadre-légal-à-garder-en-tête).
