# 06 — Montage des épisodes et du film

> **MVP implémenté le 27/09/2026** (`shortdramagen/montage.py`, CLI
> `sdg montage`, carte « Montage » de `sdg ui`). La section 0 dit ce qui a été
> fait et en quoi cela diffère de la proposition (sections 1 à 9, gardées
> telles quelles), selon les choix de l'utilisateur. Les mesures sont en annexe.

## 0. État et décisions

**Choix de l'utilisateur** (27/09/2026) :
1. Le film brut n'est pas gardé : le film monté prend son nom et le remplace.
2. Les épisodes montés sont gardés (`<série>/montage/`), pour des retouches rapides.
3. Pas d'import de sous-titres : chaque épisode a déjà ses **sous-titres
   incrustés**. Il faut qu'ils restent lisibles après le miroir (voir plus bas).
4. Encodeur AMF par défaut quand il marche (`auto`), sinon x264.
5. La coupe du début et de la fin s'applique à **tous** les épisodes, sans
   exception pour le premier et le dernier.

**Sous-titres incrustés gardés lisibles avec le miroir.** Plutôt qu'un OCR
(dépendance lourde, erreurs sur les accents, police différente), le texte
d'origine est récupéré **en image**, dans la même passe ffmpeg :
- **Bande** des sous-titres mesurée une fois par série : sur 18 images de 3
  épisodes, les pixels « texte » sont comptés par ligne, et le bloc le plus
  dense entre 30 % et 95 % de la hauteur est retenu, avec une marge de 2 %
  (`detect_band`). Elle est gardée dans `montage/index.json` et peut être
  forcée (`--band 74-84`).
  Mesuré : GoodShort 74-84 %.
- **Masque du texte**, en demi-résolution : pixels clairs (Y > 200), peu
  colorés (U et V à ±14 de 128), à moins de 3 px d'un pixel sombre (Y < 90,
  le contour ou l'ombre des lettres), puis agrandi de 2 px.
  Un pull blanc dans la bande n'est pas pris pour du texte (vérifié).
- **Image retournée** : dans la bande, le texte miroir est remplacé par une
  version floue de l'image (le masque miroir sert de canal alpha). Le texte
  d'origine, non retourné, est ensuite recollé par-dessus.
- **Coût** : 6,7× le temps réel avec x264 (4,5 s pour 30 s), contre 9,3× pour
  un miroir seul. Le masque en pleine résolution coûtait 3,2× et donnait des
  bords moins nets.
- **Limites** : un titre coloré (le carton orange de ShortMax) est retourné
  comme le reste de l'image ; un léger halo flou peut rester autour des
  lettres.

**Ce qui est livré.**
- **Recette** : `montage.json`, validée strictement, avec erreurs par champ.
  Contenu : miroir, sous-titres gardés, bande, coupe début/fin, vitesse
  globale, look (aucun, vif, doux, nb, avec luminosité, contraste et
  saturation), encodeur et qualité. Par épisode : coupe propre et passages
  accélérés ou coupés.
- **Rendu** : un ffmpeg par épisode vers `montage/E017.mp4`. Coupe par `-ss/-to`
  avant `-i`, parties coupées sur l'horloge commune, `fps` et taille de la
  série, `format=yuv420p` en dernier. Durée contrôlée pour chaque épisode.
  Cache par empreinte : profil, recette de l'épisode, taille et date de la
  source.
- **Film** : assemblé en copie depuis `montage/`, avec chapitres. Le manifest
  garde `film.edit = {fp, summary}`. Un film monté remplace notre film brut
  sans `--replace`, mais l'inverse est refusé, pour ne pas perdre un montage.
- **Aperçu** : 8 s d'un épisode, en environ 1 s.
- **CLI** : `sdg montage show|set|reset|preview|render`, `sdg film --montage`,
  `sdg fetch --film --montage`.
- **Web** : carte « Montage » sur la fiche, enregistrement automatique,
  passages par épisode, aperçu en lecture et « Créer le film monté ». Le job
  « film » reçoit `montage: true` et **fige la recette** : la modifier pendant
  le rendu ne change rien au job en cours. Il passe par les phases
  `rendering` puis `merging`.
- **Correctif du code existant** : `film --reencode` sur une très longue série
  utilisait `-filter_complex_script`, que ffmpeg 9 refuse. Il utilise
  maintenant `-/filter_complex` à partir de ffmpeg 7 (`film.filter_script_args`).

**Pas encore fait** (V2 de la proposition) : marquer les passages dans le
lecteur, plusieurs rendus en parallèle, volume et fondus, préréglages de
l'utilisateur.

### 0.1 Effets activés par défaut (04/10/2026)

**Demande de l'utilisateur** : avant le rendu du film, une série d'effets de
montage, **activés par défaut** : hauteur du son, fond sonore discret,
tempo, égaliseur, zoom, miroir, étalonnage, grain et découpe rapide. Le
miroir existait déjà : il est maintenant actif par défaut, avec les
sous-titres incrustés gardés lisibles.

| Effet | Recette (défaut) | Réalisation ffmpeg | Coupé par |
|---|---|---|---|
| Hauteur du son | `audio.pitch` : +0,5 demi-ton (−3 à 3) | `asetrate` à 44 100 × 2^(p/12), `aresample`, puis `atempo` inverse : la durée ne change pas | `0` |
| Fond sonore | `audio.bed` : `vent` (`blanc`, `basse`), `audio.bed_level` : −40 dB (−60 à −20) | `anoisesrc` (bruit blanc ; bruit brun filtré à 500 Hz et modulé lentement pour le vent) ou `aevalsrc` (55 et 82,5 Hz filtrés à 200 Hz pour la basse), ramené à son niveau RMS, puis `amerge` + `pan` sous le son | `aucun` |
| Tempo | `stretch` : +3 % (−10 à 10) | multiplie la vitesse de chaque partie (globale et passages) : `setpts` et `atempo`, son compris | `0` |
| Égaliseur | `audio.eq` : `shelf` (`notch`) | shelf : −8 dB sous 120 Hz et au-dessus de 7 kHz (`bass`, `treble`) ; notch : −18 dB à 950 Hz et 2,9 kHz (`equalizer`, Q 4) | `aucun` |
| Zoom | `zoom` : 4 % (0 à 15) | `crop` centré, tailles paires, puis `scale` à la taille de la série | `0` |
| Miroir | `mirror` : oui | inchangé (voir plus haut) | `--no-mirror` |
| Étalonnage | `grade.temperature` : +30 (−100 bleu à 100 orange), `grade.curve` : `douce` (`contraste`) | un seul `lutyuv` : U − t/10 et V + t/10 (vers l'orange), courbe de luma (douce : noirs relevés, blancs adoucis ; contraste : courbe en S) | `0`, `aucune` |
| Grain | `grain` : 4 (0 à 20) | `noise=c0s=4:c0f=t` : bruit temporel sur la luma seule | `0` |
| Découpe rapide | `staccato.transition` : `zoom` (`flash`, `noir`), segments de `min` 1 à `max` 2 s | voir ci-dessous | `aucune` |

**Découpe rapide.** Une série reste une histoire : rien n'est retiré. Chaque
épisode est découpé en segments de 1 à 2 s de sortie, tirés par un
générateur initialisé avec le numéro de l'épisode (les mêmes coupes à chaque
rendu, et dans l'aperçu). À chaque coupe :
- `zoom` (défaut) : un segment sur deux est montré 8 % plus près (copie
  zoomée posée par `overlay` avec `enable`). C'est l'effet de coupe des
  formats courts, sans flash.
- `flash` : 2 images éclaircies (`lutyuv` avec `enable`).
- `noir` : 2 images noires (`drawbox` avec `enable`).

Les « inserts d'autres contenus » ne sont pas faits : il n'y a pas d'autre
contenu à insérer.

**Ordre des étapes.** Son : tempo (par partie) → hauteur → égaliseur →
fond. Image : miroir (et sous-titres recollés) → zoom et découpe → look `eq` →
étalonnage → grain → flash ou noir → `format=yuv420p`. Le zoom vient après
le miroir : la bande des sous-titres reste mesurée sur l'image d'origine.

**Recettes existantes.** Une clé absente prend sa valeur par défaut : une
recette enregistrée avant ces effets les reçoit, et chaque épisode est
refait une fois (l'empreinte inclut les effets et les coupes). Pour revenir
au montage d'avant : `sdg montage set <série> --no-effects` (ou « Couper tous
les effets » dans la carte). `grade`, `staccato` et `audio` se complètent clé
par clé : `{"audio": {"bed": "aucun"}}` garde la hauteur et l'égaliseur.

**Sans recette.** `sdg film --montage`, `sdg montage render` et le bouton
« Créer le film monté » appliquent le montage par défaut quand la série n'a
pas de `montage.json`. Le film brut (`sdg film`, bouton « Créer le film »)
reste une simple fusion sans ré-encodage.

**Graphes longs.** Un épisode long avec la découpe en flash peut dépasser
16 Kio de graphe : il passe alors par un fichier (`film.filter_script_args`).

**Mesures** (épisode 1 de « Qui Est la Véritable Mme Lafont ? », 30 s en
1080x1920, x264 veryfast, 4 cœurs lents) :

| Recette | Temps | Taille |
|---|---|---|
| Ré-encodage seul | 13,4 s | 7,7 Mo |
| Miroir + sous-titres (montage d'avant) | 22,3 s | 8,6 Mo |
| Défaut (miroir + effets) | 29,9 s | 9,0 Mo |
| Défaut sans grain | 28,4 s | 8,9 Mo |
| Défaut sans découpe rapide | 26,6 s | 8,7 Mo |
| Défaut sans effets sur le son | 30,4 s | 9,0 Mo |

Les effets coûtent donc environ un tiers de temps en plus que le miroir
seul, surtout pour la découpe (une seconde mise à l'échelle par image) ; ceux
du son ne se mesurent pas (écart dans le bruit de la mesure). Le
grain grossit vite les fichiers au-delà de 5 : sur 30 s, +3 % à 4, ×2 à 6,
×6 à 8. Film réel de 2 épisodes (263 s de source) : 4 min 15 s en sortie
(tempo +3 %), 92 Mo, sous-titres repérés entre 61 et 72 % de la hauteur.
Hauteur vérifiée sur une sinusoïde : 440 Hz → 452,8 Hz (attendu 452,9).

**Limites.** Comme pour le miroir seul, un carton de titre coloré ou
vertical est retourné. Le zoom de la découpe (12 % au total) peut rogner la
première et la dernière lettre d'un sous-titre très large. Ces effets ne
changent rien au statut des vidéos : l'avertissement du README vaut toujours.

## 1. Résumé de la recommandation (proposition d'origine)

- **Recette par série**, stockée dans `<série>/montage.json`, hors du manifest. Les fichiers `E###.mp4` ne sont jamais modifiés.
- **Rendu par épisode** dans `<série>/montage/E017.mp4`, en une passe ffmpeg par épisode :
  - coupe exacte par recherche avant `-i` ;
  - passages accélérés ou coupés, miroir, look, sous-titres incrustés ;
  - sortie normalisée : taille de la série, 25 i/s, bt709, SAR 1, yuv420p, AAC 44,1 kHz stéréo, un seul encodeur.
- **Cache par empreinte** : si tu modifies l'épisode 17, seul le 17 est recalculé. Pause, reprise et redémarrage repartent des épisodes déjà rendus.
- **Film en copie** avec le chemin actuel de `film.py` : quelques secondes. Chapitres, durée attendue et progression sont justes sans code nouveau.
- **Pas de nouveau kind de job** : le kind `film` reçoit `params.montage`, avec la recette figée à la création.
- **Encodeur** : AMF automatique s'il passe le test de 3 images (≈ 2× x264), sinon x264.
- **Aperçu fidèle de 8 s** en 1 à 3 s.

**Alternatives écartées**
- **Une seule passe au moment du film** (« film-pass ») : toute modification refait le film entier (16 à 37 min), une pause repart de zéro, 65 décodeurs sont ouverts en même temps (mémoire jamais mesurée), et les filtres tournent sur des images que l'accélération supprime ensuite. J'en garde la recette hors du manifest, la recette figée dans le job et le passage du graphe par `-/filter_complex`.
- **Plusieurs montages nommés avec un kind `montage`** (« episode-variants ») : le coût d'intégration est le plus élevé (jobs, bibliothèque, corbeille, routes, 4 fichiers côté client) pour un besoin avancé. J'en garde la coupe par `-ss/-to` avant `-i`, le contrôle de `format_key` et de la durée de chaque épisode rendu, la priorité basse et le refus de tout filtre ffmpeg libre.

## 2. La recette (`montage.json`, `v: 1`)

```jsonc
{
  "v": 1,
  "mirror": true,
  "trim": {"start": 5, "end": 10,              // s retirées au début / à la fin
           "except_first": true, "except_last": true},
  "look": {"preset": "vif",                    // aucun | vif | doux | nb | retro
           "brightness": 0.02, "contrast": 1.06, "saturation": 1.12,
           "hue": 0, "sharpen": 0, "vignette": false},
  "speed": 1.0,                                // hors passages, 0,5–3
  "subtitles": {"mode": "burn", "position": "top", "size": 64, "margin": 260, "box": false},
  "render": {"encoder": "auto", "quality": "standard"},
  "episodes": {
    "3":  {"trim": {"start": 12.5}},           // récap plus long sur cet épisode
    "17": {"ranges": [
      {"from": 40, "to": 55, "speed": 1.5},    // temps de l'épisode source
      {"from": 80, "to": 92, "cut": true}
    ]}
  }
}
```

**Règles**
- Tous les temps sont en secondes de l'épisode **source**, comme dans le lecteur brut. Un passage reste donc valable si la coupe change.
- `episodes[n]` complète la recette de la série clé par clé. `ranges` n'existe qu'au niveau d'un épisode.
- La vitesse d'un passage est absolue : elle ne se multiplie pas par `speed`.
- **Validation stricte** : une clé inconnue est refusée. `RecipeError(field)` donne `422 invalid_input` avec le chemin exact (`episodes.17.ranges.0.speed`), sur le modèle de `SettingsError`.
  - Coupe entre 0 et 120 s, et au moins 5 s gardées ; sinon `montage_empty_episode`.
  - Passages triés, sans chevauchement, ramenés dans la partie gardée.
- **Préréglages intégrés** (constantes) : « Miroir », « Sans récap ni générique » (5 s / 10 s), « Couleurs vives », « Noir et blanc », « Rétro » (curves vintage), « Rythme ×1,25 ».
- **Pourquoi hors du manifest** : un fetch garde un `Manifest` en mémoire et réécrit tout le fichier à chaque `update`. Une recette posée entre-temps serait effacée.
- **Extensibilité (le « etc. »)** : chaque clé correspond à une ligne de la table `OPS` (`validate`, `stage`, `vf(ctx)`, `af(ctx)`, `timeline(ctx)`). L'ordre des étapes est fixe :

  `temps → géométrie → miroir → couleur YUV → RGB → incrustation → normalisation`

  Volume, fondus, cadrage ou débruitage s'ajoutent chacun par une ligne et un contrôle de formulaire.
- **Hors périmètre** : champ de filtre ffmpeg libre (`movie=` lit n'importe quel fichier), variations aléatoires d'un épisode à l'autre, retrait de logos ou de filigranes.

## 3. Réalisation ffmpeg

### Commande pour un épisode

ffmpeg est lancé avec le répertoire courant `montage/`, les drapeaux `CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS` (lus par `getattr`) et l'entrée en chemin absolu (`resolve()`).

```
ffmpeg -hide_banner -nostdin -y -loglevel error -progress pipe:1 -nostats
  -ss 5 -to 130 -i C:\…\<série>\E017.mp4
  -filter_complex "<graphe>" -map [v] -map [a] -map_metadata -1 -map_chapters -1
  <encodeur> -c:a aac -b:a 128k -ar 44100 -ac 2 -movflags +faststart -f mp4 .rendu-017.part
```

- **Coupe** : la fin vaut `D − M`, où `D` est la durée de présentation donnée par `mp4.probe`. `-ss` et `-to` avant `-i`, avec ré-encodage, donnent une coupe **exacte à l'image** (labo : 187,00 / 186,963 s) et évitent de décoder la partie retirée.
- **Couper sans ré-encoder est interdit** : au concat, le pré-roll réapparaît (9530 images décodées au lieu de 9356).

### Graphe de E017 (source de 140 s)

Après la recherche, les temps sont décalés de 5 s. On obtient les segments [0,35]×1, [35,50]×1,5, [50,75]×1 et [87,125]×1, soit 108 s en sortie.

```
[0:v]split=4[s0][s1][s2][s3];[0:a]asplit=4[t0][t1][t2][t3];
[s0]trim=0:35[v0];                          [t0]atrim=0:35[a0];
[s1]trim=35:50,setpts=(PTS-35/TB)/1.5[v1];  [t1]atrim=35:50,asetpts=PTS-35/TB,atempo=1.5[a1];
[s2]trim=50:75,setpts=PTS-50/TB[v2];        [t2]atrim=50:75,asetpts=PTS-50/TB[a2];
[s3]trim=87:125,setpts=PTS-87/TB[v3];       [t3]atrim=87:125,asetpts=PTS-87/TB[a3];
[v0][a0][v1][a1][v2][a2][v3][a3]concat=n=4:v=1:a=1[vc][ac];
[vc]fps=25,hflip,scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2,setsar=1,
 eq=brightness=0.02:contrast=1.06:saturation=1.12,subtitles=f=.sub-017.ass,
 setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=yuv420p[v];
[ac]aformat=sample_rates=44100:channel_layouts=stereo[a]
```

**Synchro**
- Variante B du labo : coupe sur l'horloge commune (`PTS-a/TB`), **jamais `PTS-STARTPTS`** (la vidéo de ShortMax commence à 0,16 s), puis `fps=25` après le concat. Écart mesuré : 13 ms au plus.
- Vitesse globale : `setpts=PTS/f` et `atempo=f`. Décalage constant de −15 ms.
- Au-delà de ×2, `atempo` est enchaîné. C'est inutile avec ffmpeg 7.1 ou 9.0.1, mais sans risque avec un ffmpeg ancien fourni par l'utilisateur.

**Normalisation**
- `W×H` = taille du format principal de la série (`main_format`) : 1080x1920, ou 720x1280 pour une série téléchargée en 720p.
- `scale` + `pad` + `setsar=1` corrige le SAR 1088:1089 de ShortMax et les tailles mélangées. `aformat` convertit le 48 kHz de FlickReels.
- Épisode sans audio : `anullsrc=r=44100:cl=stereo`, coupé à la durée de sortie, comme `reencode_filter`.

**Ordre des filtres**
- Tous les filtres viennent après `fps`, donc seulement sur les images gardées : 20 % d'images en moins à ×1,25.
- `hflip` passe avant `subtitles`, sinon le texte ajouté est lui aussi en miroir.
- Les filtres RGB (`curves`, puis `vignette` avec `dither=0`) passent avant l'incrustation.
- `format=yuv420p` toujours en dernier : sans lui, x264 produit du High 4:4:4, illisible dans le navigateur.
- Sans passage, pas de `split`.

**Sous-titres incrustés**
- Python lit `sous-titres/E017.srt` ou `.vtt` (`utf-8-sig`, repli sur `cp1252`, CRLF accepté).
- Les temps sont recalés par `TimeMap.map` : une réplique dans une coupe est supprimée, une réplique à cheval est tronquée, et dans un passage accéléré les temps sont divisés par la vitesse.
- Le fichier écrit est `.sub-017.ass`, en PlayRes `W×H` : Arial 64 px (proportionnel en 720p), Outline 4, Alignment 8 (en haut), MarginV 260, BorderStyle 3 si `box`.
- Chemin relatif : pas d'échappement `C\:` à gérer.
- Coût négligeable (9,95x pour miroir + ASS).
- libass est vérifié dans `ffmpeg -filters` ; s'il manque, erreur `subtitles_unsupported`.

**Graphes longs**
- Le graphe d'un épisode fait moins de 3 Ko et passe en ligne.
- Correctif de `film.reencode_args:419` : `-filter_complex_script` est **refusé par ffmpeg 9.0.1**. Un helper `filter_args` passe à `-/filter_complex fichier` à partir de la version 7 (validé sur 7.1 et 9.0.1).

### Encodeur

| Qualité | x264 veryfast | AMF (`-quality balanced -rc vbr_peak`) |
|---|---|---|
| standard | CRF 23 : ≈ 1,5× la source, SSIM 0,992, 9,3x | `-b:v 2500k -maxrate 4M` : ≈ 1,36×, SSIM 0,990, 18,5x |
| compacte | CRF 26 : ≈ 1,1×, SSIM 0,989 | `-b:v 1800k -maxrate 3M` (à calibrer) |

- **Mode `auto`** : test de 3 images (`-f lavfi -i color=s=1080x1920 -frames:v 3 -c:v h264_amf -f null -`, 0,2 s). Le résultat est gardé en cache par chemin et mtime de ffmpeg. NVENC et QSV échouent sur cette machine.
- AMF n'est jamais laissé à ses réglages par défaut : il sortirait du 20 Mb/s.
- **Encodeur épinglé** dans le profil de `montage/index.json`. Les en-têtes avcC d'AMF et de x264 diffèrent : les deux ne se mélangent jamais dans un film. Si AMF disparaît, l'erreur `montage_encoder_unavailable` propose de tout refaire en x264.

### Durées, chapitres et contrôles

- `TimeMap` : `out = Σ(b−a)/r`, et `map(t)` renvoie le temps de sortie, ou None si le passage est coupé. Il sert au recalage des sous-titres, au total de progression (`out_time` est un temps de sortie), à l'estimation et au contrôle.
- **Contrôle de chaque épisode rendu, avant sa mise en place** :
  - la durée probée doit valoir `out` à 0,1 s + 0,04 s par segment près (labo : 13 à 18 ms) ;
  - le `format_key` doit être celui du profil.

  Sinon, erreur `montage_format_mismatch` ou `montage_duration`, avec le correctif « refaire les épisodes 12, 30 ».
- **Film** : `plan_film(episodes_dir=montage/)` en copie. `segment()` lit la durée mvhd des fichiers montés : chapitres, tolérance (1 s + 0,05 s par épisode) et progression suivent. `chapter_times` est toujours enregistré.
- Le décalage de +23 ms dû à l'amorce AAC touche les deux flux pareil : aucune dérive, vérifié au labo sur 3 plateformes.

## 4. Intégration dans le code

### Nouveaux modules

- **`montage.py`** : `Recipe` (lecture, validation, fusion, empreinte), `OPS`, `TimeMap`, `episode_graph`, `episode_args`, `render_episode(series_dir, n, rec, ctx, on_progress, stop)`, `render_series` (saute les épisodes à jour) et `preview(series_dir, n, at, seconds, recipe)` (TimeMap restreinte à la fenêtre).
- **`subtitles.py`** : lecture SRT/VTT, normalisation, recalage, écriture ASS (VTT en V2), association nom de fichier → numéro (« E03.srt », « 03.srt », « Episode 3.vtt »).
- **`encoders.py`** : `probe_encoders`, `has_libass`, `ffmpeg_version`, `encoder_args(encoder, quality)`.

### `film.py`

- `_run_ffmpeg(args, cwd=None, low_priority=False)`, avec `CREATE_NO_WINDOW`.
- `filter_args` (le correctif ci-dessus) et `plan_film(..., episodes_dir=None)`.
- `make_film(..., montage=None)` : `render_series`, puis assemblage en copie.
- `up_to_date_film` compare `edit.fp` (None pour un film brut) : un film brut n'est plus jamais jugé « à jour » à la place d'un film monté, ni l'inverse.
- `_record_in_manifest` ajoute `edit: {fp, summary, encoder, quality}`.
- Nom par défaut : `<titre> (montage).mp4`.
- `plan_summary(montage=True)` ajoute un bloc `montage` : encodeur, libass, couverture des sous-titres, épisodes à rendre ou en cache, `estimate_s`, octets estimés, avertissements.

### Jobs (`jobs.py`, `server/actions.py`)

- **Création** : `film_job` avec `montage: true` valide la recette, résout `auto` en encodeur réel, puis **fige** `params.montage = {recipe, encoder, quality}` (quelques Kio dans `jobs.json`). Modifier `montage.json` pendant le rendu ne change rien au job en cours ; le film passe ensuite « obsolète ».
- **Phases** : `rendering`, puis `merging`. `FilmProgress` gagne `episode`, `episodes_done` et `episodes_total` ; `seconds_total` = Σ des durées de sortie des épisodes à rendre.
- **Pause et redémarrage** : ffmpeg est tué et le `.rendu-NNN.part` supprimé. À la reprise, les épisodes en cache sont sautés.
- **Annulation** : supprime seulement `montage/.rendu-*.part` et `.sub-*.ass`. **`_delete_parts` est réservé au kind `fetch`** : aujourd'hui, il efface les `E*.part` d'un fetch en échec qu'on pouvait encore reprendre.
- **Fin** : `_summary` écrit « Film monté prêt ». Côté client, il suffit d'un libellé pour la phase `rendering`.

### Stockage et nommage

```
<série>/E001.mp4…              jamais modifiés
<série>/montage.json           recette (fsutil.write_text → le mtime du dossier change)
<série>/sous-titres/E017.srt   fichiers normalisés en UTF-8
<série>/montage/index.json     {engine, profile{encoder,quality,W,H,format_key},
                                episodes{"17":{key,out_s,bytes}}}
<série>/montage/E017.mp4       .rendu-017.part  .sub-017.ass  .apercu-a|b.mp4
<série>/<titre> (montage).mp4
```

- **Aucune collision avec les épisodes** : `scan_dir`, `download.finish`, `_delete_parts` et la corbeille en portée `parts` ne descendent pas dans les sous-dossiers, et tous les fichiers temporaires commencent par un point.
- **Clé d'un épisode** : `sha256` de `ENGINE` + profil + recette résolue de l'épisode + taille et `mtime_ns` de la source + sha1 du sous-titre et de son style.
- **Empreinte du film** : hash des couples (n, clé).
- **Invalidation** : un épisode périmé est réécrit à sa place (`.part` puis `fsutil.replace`). Si le lecteur garde le fichier verrouillé, l'épisode reste périmé avec `file_locked` et il est réessayé en fin de job.

### Bibliothèque

- **Cache** : l'empreinte `stamp` (library.py:468) inclut aussi le `stat` de `montage/index.json` et le mtime de `sous-titres/`. Sans cela, les rendus sont invisibles.
- **`describe_montage`** : `{summary, rendered, stale, bytes, subtitles: {found, missing}}`. Le film passe `stale` avec la raison `montage_changed`.
- **« Libérer la place des épisodes »** (:549) : avertissement « Sans les épisodes, tu ne pourras plus modifier le montage. »

### Réglages, erreurs, corbeille

- **`settings.py`** : `montage_encoder` (`_choice` auto/x264/amf) et `montage_quality` (`_choice` standard/compacte).
- **`errors.py`** : `montage_invalid`, `montage_empty_episode`, `montage_encoder_unavailable`, `montage_format_mismatch`, `montage_duration`, `subtitles_unsupported`, `subtitles_invalid`. À reporter dans `_FILM_STATUS` et dans la liste d'actions.js:103.
- **`trash.py`** : portée `montage`. Elle déplace `montage/` et garde la recette et les sous-titres.
- **Aperçus** : deux noms fixes utilisés en alternance, pour éviter le verrou du lecteur, purgés au démarrage du serveur.

## 5. Interface

### CLI

```
sdg montage show    <série>              # recette, 42/65 rendus, 3 obsolètes, 5,1 Go
sdg montage set     <série> [--preset NOM] [--mirror/--no-mirror] [--look vif|doux|nb|retro]
                    [--trim-start 5] [--trim-end 10] [--keep-edges/--no-keep-edges]
                    [--speed 1.25] [--subs top|bottom|off]
sdg montage set     <série> -e 17 --range 0:40-0:55x1.5 --cut 1:20-1:32 --trim-start 12.5
sdg montage reset   <série> [-e 17]
sdg montage subs    <série> <fichiers|dossier>
sdg montage preview <série> -e 17 --at 0:40 [--seconds 8] [--open]
sdg montage render  <série> [-e 1-10] [--force]
sdg film <série> --montage
```

Affichage pendant le rendu : `Montage E017/65 · 38 % · ≈ 12 min`, puis `Assemblage…`.

### API

- `GET` et `PUT /api/series/<k>/montage` : 64 Kio au plus, validation stricte, écriture atomique.
- `GET film/plan?montage=1` ; `POST /api/jobs {kind:"film", montage:true}`.
- `POST …/montage/preview {n, at, seconds≤10, recipe}` : appel synchrone (ThreadingHTTPServer). Il renvoie `media_url` vers `/media/series/<k>/montage/preview/<a|b>`, résolu par une fonction à noms fixes, jamais à partir d'un chemin client.

### Web, carte « Montage » après `filmSection` (series.js:670)

- **En-tête** : pastilles « Miroir · −5/−10 s · Vif · Sous-titres 62/65 » et « 42/65 rendus ».
- **Préréglage** : liste déroulante.
- **Volets** :
  - Image : miroir, look et 4 curseurs ;
  - Découpe : début, fin, « sauf l'épisode 1 », « sauf le dernier » ;
  - Vitesse : ×1, ×1,1, ×1,25, ×1,5 ;
  - Sous-titres : couverture (« manquent : 4, 9, 51 »), haut ou bas, taille ;
  - Rendu : « Auto · AMF détecté », qualité.
- **Avertissements** : pour un miroir sur GoodShort ou ShortMax, « les sous-titres incrustés par la plateforme seront à l'envers ». Pour nos sous-titres placés en bas sur ces plateformes, risque de chevauchement.
- **Pied de carte** : « ≈ 7 min (AMF) · +5,5 Go », boutons « Aperçu 8 s » et « Créer le film monté », commande CLI à copier.
- **Enregistrement automatique** (PUT après 500 ms sans saisie) : sans risque, puisque la recette est hors du manifest et figée dans le job.
- **Carte « Film »** : « Montage 17/65 · 38 % · ≈ 12 min », Pause et Annuler. Quand le montage a changé : « Obsolète : 3 épisodes à refaire, ≈ 25 s ».

## 6. Performances sur cette machine

Série de 65 épisodes, 9000 s de source. Coupe de 5 s au début et 10 s à la fin, sauf au début du premier épisode et à la fin du dernier : ≈ 8040 s en sortie.

| Recette | x264 veryfast | AMF |
|---|---|---|
| Miroir seul (9000 s) | 9,3x → ≈ 16 min | 18,5x → ≈ 8 min |
| Légère : miroir, coupes, look eq/hue, sous-titres | 8,1x → ≈ 16,5 min | 17,8x → ≈ 7,5 min |
| Miroir + ×1,25 partout (7200 s) | ≈ 13 min | ≈ 6,5 min (estimé) |
| Lourde : + netteté, vignette, curves | 3,65x → ≈ 37 min | 4,4x → ≈ 30 min |
| Lourde, 2 à 3 rendus en parallèle (V3) | 4,8x → ≈ 28 min | 7,1x → ≈ 19 min |
| Un épisode modifié (138 s, légère) | ≈ 17 s + assemblage | ≈ 8 s + assemblage |
| Assemblage en copie | < 30 s (≈ 3 Go écrits) | idem |
| Aperçu de 8 s | 1 à 3 s | idem |

- **Disque** : la source fait ≈ 2,2 Go. Les épisodes montés font ≈ 2,9 Go (x264) ou 2,7 Go (AMF), et le film autant : **≈ +5,5 Go**, ou ≈ +4 Go en qualité compacte.
- **Rendu en série** dans le MVP : un seul x264 occupe déjà les 16 threads (9,6x à 4 en parallèle, contre 9,3x seul).

## 7. Risques et parades

| Risque | Parade |
|---|---|
| Copie refusée (avcC différents) | normalisation complète, encodeur épinglé, `format_key` contrôlé par épisode, correctif ciblé |
| Mise à jour de pilote ou de ffmpeg | même contrôle ; `ENGINE` n'augmente que si le graphe change |
| Dérive son/image | horloge commune, `fps` final, test réel flash + bip |
| Une coupe globale mange l'histoire | aperçu, exceptions par épisode, premier et dernier épisodes épargnés |
| Miroir sur des sous-titres incrustés | avertissement ; nos sous-titres après `hflip`, en haut |
| libass ou AMF absents | sondage, message au pré-vol, repli sur x264 |
| Machine saturée | priorité basse ; l'aperçu reste en priorité normale |
| Disque | pré-vol en octets, portée de corbeille `montage` |
| SRT en CP1252 | normalisation en Python |
| Image d'une seule frame perdue en accéléré | accepté, mentionné dans l'aide |
| Modification pendant le rendu | recette figée dans le job, film marqué obsolète ensuite |

## 8. Plan

### MVP, en une session

- **Nouveaux fichiers** : `montage.py`, `subtitles.py`, `encoders.py`.
- **Fichiers modifiés** :
  - `film.py` : correctif `-/filter_complex`, `CREATE_NO_WINDOW`, `episodes_dir`, `edit.fp`, pré-vol ;
  - `jobs.py` : `params.montage`, phase `rendering`, `_delete_parts` limité au fetch ;
  - `library.py` (stamp, `describe_montage`, obsolescence), `trash.py` (portée `montage`), `settings.py`, `errors.py` ;
  - `cli.py`, `server/api.py`, `server/actions.py` ;
  - `web/js/views/series.js`, `web/js/actions.js`, libellé de phase dans `status.js` et `live.js` ;
  - docs : 02 (§3.9, §3.12), 04, README.
- **Périmètre** : miroir, coupes avec exceptions, looks et curseurs, vitesse globale, passages accélérés ou coupés (moteur et CLI), sous-titres incrustés depuis `sous-titres/`, AMF automatique, deux qualités, cache, aperçu 8 s.
- **Tests hors ligne** :
  - `test_montage.py` : un test par champ refusé, fusion, empreinte stable qui change avec le mtime, les sous-titres ou l'encodeur, `TimeMap` ; graphes de référence (`hflip` avant `subtitles`, `yuv420p` en dernier, jamais `STARTPTS`, `-ss/-to` avant `-i`, `anullsrc`) ;
  - `test_subtitles.py` : cp1252, BOM, CRLF, recalage, réplique dans une coupe, association nom → numéro ;
  - film : plan en copie depuis `montage/`, `chapter_times`, `up_to_date_film` et empreinte, correctif `-/filter_complex` ;
  - jobs (`LiveTest`, avec un faux `render_episode`) : reprise sur le cache, recette figée, annulation qui épargne `E*.part` ;
  - bibliothèque : `montage/` et `.rendu-*.part` ne changent ni les épisodes ni `parts_bytes` ; état obsolète ;
  - API : 422 avec le champ en cause.
- **Tests avec un vrai ffmpeg** (sautés s'il est absent) :
  - clips `testsrc` de 6 s en 108x192, flash et bip, vidéo décalée de 0,16 s : miroir (pixel échantillonné), coupe à ±0,05 s, synchro dans un passage ×2 à ±40 ms ;
  - trois sources (SAR 1088:1089, 48 kHz) : même `format_key`, film en copie ;
  - incrustation si libass est présent, sortie yuv420p après `curves`.

### V2

- **Lecteur** : mode montage (frise, touches I/O, [ ], V pour accélérer, X pour couper), bascule Brut / Monté, routes médias des épisodes montés.
- **Sous-titres** : envoi depuis l'interface, un fichier par requête sous 64 Kio (sans toucher MAX_BODY) ; mode piste (mov_text, `-map 0:s?`) avec VTT web.
- **Préréglages de l'utilisateur** dans `<downloads>/.sdg/montage-presets.json`.
- `fetch --film --montage`.

### V3

- 2 à 3 rendus en parallèle (AMF ou filtres lourds).
- Cadrage (zoom), volume et `loudnorm`, fondus.
- Un seul SRT pour le film entier.
- Suggestions de coupe par `blackdetect`.
- Film brut et film monté côte à côte.

## 9. Questions pour toi

1. **Garder le film brut à côté du film monté ?** Par défaut : non. L'ancien part à la corbeille, et le brut se refait en quelques secondes.
2. **Garder les épisodes montés après le film (≈ +2,7 Go) ?** Par défaut : oui, c'est ce qui rend les retouches rapides. Portée de corbeille « montage » pour les libérer.
3. **Tes sous-titres : un fichier par épisode ?** Par défaut : oui, le numéro dans le nom, incrustés en haut.
4. **AMF par défaut quand il est détecté ?** Par défaut : oui, ≈ 2× plus rapide, SSIM 0,990 contre 0,992.
5. **La coupe épargne-t-elle le début de l'épisode 1 et la fin du dernier ?** Par défaut : oui.

## Annexe : mesures du labo ffmpeg (27/09/2026)

Machine : Ryzen 7 5700X (8 cœurs, 16 threads), Radeon RX 7800 XT, ffmpeg 9.0.1.

**Profil des sources, mesuré avec ffprobe.** Toutes sont en 1080x1920, H.264 High, 25 i/s, yuv420p, bt709.
- **Intervalle entre images clés :** 1 s chez GoodShort, 10 s chez FlickReels et ShortMax.
- **Décalage vidéo/audio :** la vidéo commence à 0,04 s, et à 0,16 s chez ShortMax. L'audio commence à 0.
- **Pixels non carrés :** ShortMax E001 a un rapport de pixel de 1088:1089 ; les autres sont en 1:1.
- **Audio :** 44,1 kHz, sauf FlickReels en 48 kHz.
- **Sous-titres déjà incrustés :** GoodShort et ShortMax ont des sous-titres français incrustés dans l'image, vers y≈1270–1570 px. ShortMax affiche aussi des cartons de noms.

**Méthode pour la synchro son/image :** un clip synthétique de 1080x1920 avec un flash d'une image et un bip de 40 ms toutes les 5 s. Sa vidéo démarre à 0,16 s, comme ShortMax. Après chaque traitement, les flashs sont repérés avec `signalstats` et les bips avec `silencedetect`, puis comparés.

### 1. Miroir (hflip) et encodeurs

```
ffmpeg -hide_banner -y -i E001.mp4 -vf hflip -c:v libx264 -preset veryfast -crf 23 -c:a copy -movflags +faststart out.mp4
```

FlickReels E001 : 206 s, source de 50,7 Mo. Le SSIM est mesuré contre la source miroitée.

| Encodeur / réglage | Temps | Vitesse | Taille | SSIM |
|---|---|---|---|---|
| x264 veryfast crf20 | 23,7 s | 8,7x | 109 Mo | 0,9936 |
| x264 veryfast crf23 | 22,2 s | 9,3x | 78 Mo | 0,9918 |
| x264 veryfast crf26 | 21,4 s | 9,6x | 57 Mo | 0,9891 |
| x264 medium crf20 | 55,2 s | 3,7x | 117 Mo | – |
| x264 ultrafast crf23 | 10,5 s | 19,6x | 189 Mo | – |
| `h264_amf -quality balanced -rc vbr_peak -b:v 2500k -maxrate 4M` | 10,2 s | 20,2x | 69 Mo | 0,9896 |
| h264_amf cqp 24/26/28 | 10,4 s | 19,8x | 92 Mo | 0,9907 |
| hevc_amf cqp | 10,7 s | 19,3x | 64 Mo | 0,9898 |
| h264_amf qvbr (quality) | 84 s | 2,4x | 54 Mo | 0,982 |

- **NVENC :** ne marche pas (« Cannot load nvcuda.dll »).
- **QSV :** ne marche pas (« MFX session -9 »).
- **AMF :** fonctionne, en h264, hevc et av1. Pour savoir si un encodeur est utilisable, il suffit d'un test de 3 images (`-f lavfi -i color=s=1080x1920 -frames:v 3 -c:v X -f null -`) : 0,2 s, et un code de retour non nul signifie inutilisable.
- **Le décodage n'est pas le goulot :** décoder seul va à 76x ; c'est l'encodeur qui limite.
- **Pièges :**
  - Réglé par défaut, AMF sort du 20 Mb/s (25 Mo pour 10 s). Il faut fixer le contrôle de débit.
  - Avec `qvbr`, plus `qvbr_quality_level` est haut, meilleure est la qualité.
  - `qvbr` exige la pré-analyse : avec `-preanalysis 0`, l'encodeur refuse de s'ouvrir.
  - AMF produit du profil Main.
  - Un ré-encodage agrandit les fichiers : CRF 23 donne 1,5 fois la taille de la source, CRF 26 environ 1,1 fois.

### 2. Couper les N premières et M dernières secondes

Exemple : FlickReels E001, N=7 et M=12, donc une cible de 186,963 s.

| Méthode | Vidéo / audio obtenus |
|---|---|
| `-ss 7 -to 193.963 -i in -c copy` (recherche avant `-i`) | 187,16 / 186,98. 174 images de pré-roll (depuis l'image clé à 0,04 s) sont stockées et masquées par une liste de montage. |
| `-i in -ss 7 -to … -c copy` (recherche après `-i`) | La vidéo ne commence qu'à 3,04 s : 3 s de son sans image. |
| Ré-encodage `-ss 7 -to 193.963 -i in -c:v libx264 … -c:a aac` | 187,00 / 186,963, précis à l'image. 19,6 s de calcul (9,5x). |
| GoodShort (images clés toutes les 1 s), copie | 70,73 pour une cible de 70,467 |

- **Piège majeur :** un fichier coupé sans ré-encodage, passé au concat demuxer (la méthode de film.py), donne 210 avertissements « Non-monotonic DTS » et 9530 images décodées au lieu de 9356. Le pré-roll réapparaît dans le film.
- **Conclusion :** couper précisément impose un ré-encodage. Sans ré-encodage, la coupe ne tombe que sur une image clé : ±1 s chez GoodShort, ±10 s chez FlickReels et ShortMax.
- **Pour les M dernières secondes :** calculer la fin (durée du conteneur − M) puis passer `-ss N -to FIN` avant `-i`.

### 3. Accélérer des passages

Le graphe retenu est dans `e3_B_fps.txt` (x1,5 de 10 à 20 s, x2 de 40 à 50 s). On le passe par fichier avec `ffmpeg -i in.mp4 -/filter_complex speed.txt -map "[v]" -map "[a]" …`. Les segments sont affichés sur plusieurs lignes pour la lecture ; le fichier les enchaîne après une ligne `split=5` / `asplit=5` :

```
[s1]trim=10:20,setpts=(PTS-10/TB)/1.5[v1];[t1]atrim=10:20,asetpts=PTS-10/TB,atempo=1.5[a1];
... concat=n=5:v=1:a=1[vc][a];[vc]fps=25[v]
```

Variantes testées sur le clip synthétique :
- **B, avec `PTS-T0` et `fps=25` après le concat (retenue) :** écart son/image de 13 ms au plus, audio exact à la milliseconde.
- **A, avec `PTS-STARTPTS` :** la vidéo du premier segment est décalée de 160 ms, à cause du départ à 0,16 s de ShortMax.
- **C, avec `setpts` par morceaux et `asendcmd`/`atempo` :** l'audio dérive jusqu'à −100 ms. Rejetée.
- **B avec `-r 25` au lieu du filtre `fps` :** retard de 53 ms et images perdues aux jonctions. `-fps_mode vfr` fait pire.

Sur un vrai épisode (ShortMax E001, 144,2 s) :
- **Passages accélérés :** 13,0 s de calcul. Audio de 135,881 s pour 135,863 en théorie ; la vidéo finit à 135,96 pour 135,947 en théorie.
- **x1,25 sur tout l'épisode** (`[0:v]setpts=PTS/1.25,fps=25[v];[0:a]atempo=1.25[a]`) : 11,8 s de calcul, 115,370 s pour 115,357 en théorie. Sur le clip synthétique, l'audio garde un décalage constant de −15 ms.

Pièges :
- En accéléré, des images sont supprimées : un événement d'une seule image peut disparaître.
- Dans `-progress`, `out_time` est le temps de sortie : le pourcentage doit se calculer sur la durée attendue en sortie.
- Mettre les segments dans l'ordre croissant, sinon ffmpeg met les images en mémoire.

### 4. Filtres d'image

Coût du filtre seul sur 30 s (le décodage seul prend 0,5 s) :

| Filtre | Temps |
|---|---|
| hflip | 0,6 s |
| eq | 0,6 s |
| crop + scale | 0,7 s |
| hue | 0,8 s |
| curves | 1,0 s |
| colorchannelmixer | 1,4 s |
| gblur | 1,6 s |
| unsharp | 1,8 s |
| vignette | 5,7 s (2,3 s avec `dither=0`) |

Chaîne validée en une seule passe, avec la coupe et le miroir (`e4_chain.txt`) :

```
hflip,crop=trunc(iw/1.08/2)*2:trunc(ih/1.08/2)*2,scale=1080:1920:flags=lanczos,setsar=1,eq=brightness=0.02:contrast=1.06:saturation=1.12,hue=h=4,unsharp=5:5:0.6,vignette=PI/5:dither=0,curves=preset=vintage,format=yuv420p
```

- **Chaîne complète** (187 s après coupe) : x264 50,8 s (3,7x), AMF 42,4 s (4,4x). Le CPU consommé par les filtres limite la vitesse.
- **Chaîne légère** (miroir, zoom, eq, hue, sous-titres) : x264 23,1 s (8,1x), AMF 10,5 s (17,8x).
- **Piège `curves` :** il ne travaille qu'en RGB, donc ffmpeg convertit l'image vers rgb24 puis vers yuv444p. Sans `format=yuv420p` final, x264 a produit du « High 4:4:4 Predictive », que les navigateurs ne lisent pas, et environ deux fois plus lentement. Mettre les filtres RGB en fin de chaîne et toujours finir par `format=yuv420p`.
- **Piège crop + scale :** sans `setsar=1`, le rapport de pixel devient 8000:8001.

### 5. Sous-titres

**(a) Incrustés dans l'image**
- **Chemin Windows :** il faut écrire `subtitles='C\:/Users/.../sub.ass'`, avec les deux-points du lecteur échappés et des barres obliques. Avec des antislashs ou des deux-points non échappés, ffmpeg répond « Unable to parse original_size ». Plus simple : lancer ffmpeg avec le dossier du fichier comme répertoire courant et écrire `subtitles=sub.ass`.
- **Ordre :** `hflip` doit venir avant `subtitles`, sinon le texte ajouté est lui aussi en miroir (vérifié en image). Le miroir inverse aussi les sous-titres déjà incrustés dans la source.
- **Le SRT se prête mal au format vertical.** Il est rendu dans un espace virtuel de 384x288. Par défaut, la police fait environ 107 px de haut et une réplique tient sur 5 lignes. Avec `force_style` (par exemple `Alignment=8`), le résultat est mal centré.
- **Solution :** générer un ASS avec `PlayResX: 1080` et `PlayResY: 1920`. Les tailles sont alors en pixels (Fontsize 64, Outline 4, Alignment 8, MarginV 260 ; BorderStyle 3 pour un fond en boîte). Le rendu est correct : accents, « », œ, apostrophes et italique passent. libass et fontconfig sont inclus dans ce build et Arial est trouvé.
- **Placement :** en bas, ils chevauchent les sous-titres déjà incrustés de GoodShort et ShortMax. Mettre les nôtres en haut par défaut, ou rendre la marge réglable.
- **Coût :** négligeable, 9,95x pour miroir plus ASS sur un épisode complet.
- **Encodage des fichiers :**
  - Un SRT en CP1252 provoque « Invalid UTF-8 » : les répliques sont perdues au multiplexage et l'incrustation échoue.
  - Ça fonctionne avec `-sub_charenc CP1252` ou `charenc=CP1252`.
  - L'UTF-8 avec BOM et les fins de ligne CRLF passent.
  - Le plus sûr : normaliser le fichier en Python (lecture en utf-8-sig, repli sur cp1252).

**(b) Pistes de sous-titres dans le fichier, sans ré-encodage (0,1 s)**
- **MP4 :**
  ```
  ffmpeg -i ep.mp4 -i sub.srt -map 0:v -map 0:a -map 1:s -c:v copy -c:a copy -c:s mov_text -metadata:s:s:0 language=fre -movflags +faststart out.mp4
  ```
- **MKV :** `-c:s srt`, ou `-c:s ass` pour garder les styles. Le texte ressort intact.
- **ASS vers mov_text :** les balises `<font size="64">` sont conservées. Il faut donner du SRT à mov_text.
- **Compatibilité (connue, non testée ici) :** Chrome, Edge et Firefox ignorent la piste mov_text dans une balise `<video>`. Pour l'interface web, il faut un fichier WebVTT séparé via `<track>`, que `ffmpeg -i sub.srt sub.vtt` produit (l'italique est gardé). VLC et mpv lisent tout. Les navigateurs ne lisent pas le MKV.

**(c) Dans le film**
- Le concat demuxer avec `-map 0` garde les pistes mov_text et décale correctement les répliques : la première de l'épisode 2 tombe à 137,303 = 136,28 + 1 + 0,023.
- Mais film.py ne mappe que `0:v:0` et `0:a:0` : les sous-titres disparaissent. Il faudrait ajouter `-map 0:s?`.
- Pour un fichier SRT ou VTT du film entier, décaler chaque épisode de la somme des durées précédentes, comme `chapter_marks`.

### 6. Interaction avec le film

- **Premier essai :** les épisodes retouchés avec les mêmes réglages étaient jugés incompatibles par film.py, qui compare la configuration du décodeur (`format_key` = avcC). x264 recopie dans son en-tête (SPS) le rapport de pixel de la source (1088:1089 contre 1:1 chez ShortMax) et ses balises de couleur. Les options de sortie `-color_primaries`, `-color_trc`, etc. sont ignorées.
- **Correctif :** mettre `setsar=1,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709` dans la chaîne, `fps=25` ou `-r 25`, et `-ar 44100 -ac 2` pour l'audio. On obtient alors une configuration identique pour GoodShort, FlickReels (rééchantillonné de 48 kHz) et ShortMax.
- **AMF :** sa configuration est stable d'un épisode à l'autre mais différente de x264. Il faut un seul encodeur par film.
- **Assemblage sans ré-encodage** (méthode de film.py, liste ffconcat avec `duration` = durée du conteneur), sur 4 épisodes de 3 plateformes :
  - 0,3 s de calcul ;
  - vidéo de 369,48 s, égale à la somme des épisodes ; audio de 369,466 s ;
  - un avertissement DTS par jonction, sans conséquence (amorce AAC) ;
  - le décodage du film ne signale aucune erreur.
- **Synchro sur le clip synthétique** (3 fois 52 s) : flashs et bips alignés à la milliseconde dans les 3 parties. Le décalage uniforme de +23 ms (amorce AAC) touche les deux flux pareil, donc aucune dérive.
- **Retouche pendant l'assemblage** (filtre concat, 4 entrées, un seul encodage) : 39,4 s, contre 41,0 s épisode par épisode en série et 39,9 s avec 4 en parallèle. Aucun gain, et on perd la mise en cache, la reprise et la progression par épisode.

### 7. Projection pour 65 épisodes (environ 9000 s)

| Traitement | x264 veryfast | AMF |
|---|---|---|
| Miroir seul | 9,3x, environ 16 min (9,6x avec 4 en parallèle) | 18,5x, environ 8 min ; 25x avec 4 en parallèle, environ 6 min |
| Réglages légers (miroir, coupe, zoom, eq, hue, sous-titres) | 8,1x, environ 19 min | 17,8x, environ 8,5 min |
| Réglages lourds (unsharp, vignette, curves) | 3,65x en série, environ 41 min ; 4,8x en parallèle, environ 31 min | 4,4x en série, environ 34 min ; 7,1x en parallèle, environ 21 min |
| Assemblage du film sans ré-encodage | quelques secondes | quelques secondes |

Un seul x264 occupe déjà les 16 threads. Lancer plusieurs traitements en parallèle ne sert que si les filtres sont lourds ou avec AMF. Une concurrence de 2 à 3 semble le bon réglage.

### Ce qu'un concepteur doit savoir

1. Toute retouche (coupe précise, miroir, filtre, vitesse, incrustation) impose un ré-encodage. Seules les pistes de sous-titres s'ajoutent sans ré-encoder.
2. Couper sans ré-encoder, puis assembler, fait réapparaître des images supprimées. À ne jamais proposer.
3. Produire des épisodes retouchés normalisés (`setsar=1`, `setparams` bt709, `fps=25`, `format=yuv420p`, AAC 44,1 kHz stéréo, un seul encodeur). Le film se fait alors en copie : quelques secondes, sans dérive.
4. Ne pas remettre chaque flux à zéro séparément (`PTS-STARTPTS`) : ShortMax décale sa vidéo de 0,16 s. Couper sur l'horloge commune et finir par `fps=25`.
5. AMF est le seul encodeur matériel utilisable ici : environ 2 fois plus rapide que x264 veryfast, mais il faut fixer le débit. NVENC et QSV sont listés mais ne marchent pas. Il faut détecter les encodeurs utilisables par un test de 3 images.
6. Les filtres RGB (`curves`) et `vignette` coûtent cher et peuvent faire sortir du 4:4:4 : il faut toujours finir par `format=yuv420p`.
7. Pour les sous-titres, générer de l'ASS avec PlayRes 1080x1920, placé en haut par défaut, appliqué après le miroir, en UTF-8 normalisé. Le miroir rend illisibles les sous-titres déjà incrustés chez GoodShort et ShortMax.
8. Le navigateur n'affiche pas la piste de sous-titres d'un MP4 : il faut un fichier WebVTT séparé. film.py doit ajouter `-map 0:s?` pour garder les sous-titres.
9. Passer les graphes longs par `-/filter_complex fichier` (`-filter_complex_script` est obsolète), à cause de la limite de 32 767 caractères de la ligne de commande Windows. La progression doit se calculer sur la durée de sortie.
10. Il faut rappeler la hausse de taille des fichiers : CRF 23 donne environ 1,5 fois la source, CRF 26 environ 1,1 fois.
