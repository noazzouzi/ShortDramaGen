# 05 — Plateformes

> État au 03/10/2026. Le fonctionnement commun (interface `Provider`,
> références `plateforme:n°`, HLS, « gratuits seulement ») est décrit dans
> [02 — Architecture §7](02-architecture.md#7-plateformes-providers).

## Principe retenu

Les **métadonnées** viennent du site officiel de chaque plateforme (titre,
liste des épisodes, durées, pour vérifier chaque fichier), quand il les donne
sans signature à forger. Les **vidéos** viennent de dramafren quand il sert la
plateforme (DramaBox, GoodShort, FlickReels, ShortMax, NetShort : tous les
épisodes, jusqu'en 1080p) ; les vidéos gratuites du site officiel restent en
dernier recours, sauf pour NetShort où elles sont meilleures (720p contre
540p) et passent donc en premier. FlickReels et ShortMax font exception pour les métadonnées : l'API
officielle de FlickReels signe chaque appel, et le site de ShortMax ne publie
pas les durées ; tout vient donc du lecteur (voir plus bas).

## Vue d'ensemble

| Plateforme | Site officiel | État |
|---|---|---|
| DramaBox | dramaboxdb.com | Intégrée (voir [01 — Étude technique](01-etude-technique.md)) |
| GoodShort | www.goodshort.com | **Intégrée** : tous les épisodes via dramafren, HLS jusqu'en 1080p (ci-dessous) |
| NetShort | netshort.com | **Intégrée** : tous les épisodes via l'API `resolve_watch` de dramafren (MP4 540p), gratuits en 720p depuis le site officiel, sous-titres WebVTT à part (ci-dessous) |
| FlickReels | www.flickreels.net | **Intégrée** : tout via dramafren, HLS du CDN officiel en 1080p (ci-dessous) |
| ShortMax | www.shortmax.com → redirige vers www.shorttv.live | **Intégrée** : lecteur shortmax.ngeshorts.fun, HLS du CDN officiel en 1080p (ci-dessous) |
| DramaWave | www.mydramawave.com | Site joignable (page de 9 Ko : rendu côté navigateur), pas étudié |
| StardustTV | www.stardusttv.net | Site joignable, pas étudié |
| RadReel | radreel.tv | Site joignable (page de 1,8 Ko), pas étudié |
| Vigloo (« Viglo ») | www.vigloo.com/en/discovery | Site joignable, pas étudié ; le site annonce le 1er épisode gratuit de chaque titre |

Domaines trouvés par recherche web (fiches des stores et sites des éditeurs)
puis vérifiés par une requête HTTP. Les domaines `stardusttv.com`,
`radreel.com` et `dramawave.com` ne sont pas ceux des plateformes (à vendre
ou injoignables).

## GoodShort

Constats du 27/09/2026 sur la série *Perfect Love* (`31000662271`, 56 épisodes).

**Liens.** `/drama/{slug}-{id}` (fiche), `/episodes/{slug}-{id}` (liste),
`/episode/{slug}-{id}/{NNN}-{chapterId}` (épisode NNN). Identifiant de 11
chiffres commençant par 31. Le slug peut contenir des accents
(`engagée-à-un-milliardaire-bâtard-31000835255`) : il est décodé à la lecture
du lien et réencodé pour la requête ; le dossier en garde une version ASCII
(`goodshort-31000835255-engagee-a-un-milliardaire-batard`).

Liens dramafren acceptés en entrée :
`goodshort.dramafren.org/index.php?page=detail&id={id}&lang=…&slug=…&sv=1`
(et `page=watch&…&ep={index}`). `id` est l'identifiant GoodShort ; `slug` est
celui de dramafren (`engag-e-un-milliardaire-b-tard`), pas celui du site, et
`lang` ne change rien (chaque version a son propre identifiant). `ep` est
l'**index** du chapitre, compté à partir de 0 : `ep=0` est l'épisode 1.

**Données de page.** Le HTML contient `window.__INITIAL_STATE__={…};` suivi,
sur la même ligne, d'un script qui se retire lui-même : on lit l'objet JSON
avec `json.JSONDecoder().raw_decode` à partir du `=`.

- `BookInfoModule.book` : `bookId`, `bookName`, `cover` (JPEG),
  `introduction`, `language` (`ENGLISH`…), `chapterCount`,
  `bookResourceUrl` (`perfect-love-31000662271`).
- `BookInfoModule.chapterVoList` : les **11 premiers** chapitres seulement
  (sur la fiche comme sur `/episodes/`). Par chapitre : `id`, `index`
  (0-based), `playTime` (durée en secondes entières), `price` (0 = gratuit)
  et, pour les gratuits seulement, `m3u8Path`.
- Sur cette série, les épisodes 1 à 7 sont gratuits.

**API des pages** (constat du 27/09/2026). La fiche répond **404 si le slug
n'est pas exactement celui du site** (`/drama/{id}`, `/drama/x-{id}` et le slug
dramafren échouent). Le JavaScript du site appelle
`POST /hwycreels/book/detail` avec `{"bookId": "…"}` (JSON seulement : un
formulaire répond 415), sans cookie ni jeton. La réponse
`{"status": 0, "data": {…}}` contient le même `book` (mêmes clés) et le même
`chapterVoList` (11 chapitres, `m3u8Path` signés) que l'état de la page. Un
identifiant inconnu répond aussi `status` 0, avec seulement
`data.seo404Vo`. Vérifié sur *Engagée à un Milliardaire Bâtard*
(`31000835255`, `FRENCH`, 61 épisodes, 1 à 5 gratuits).

**Tous les chapitres.** `POST /hwycreels/chapter/page` avec
`{"bookId", "pageNo", "pageSize"}` renvoie
`{"status": 0, "data": {"total", "pages", "records": […]}}` : chaque chapitre
avec les mêmes clés que `chapterVoList` (`m3u8Path` pour les gratuits). Sans
`pageSize`, 15 par page ; `pageSize` 500 renvoie les 61 chapitres de
`31000835255` d'un coup. Un identifiant inconnu répond `status` 12000
(« Book not exists. »). Les noms de chapitre ne suivent pas toujours l'index :
sur `31000835255`, l'index 0 s'appelle « 002 » (sur *Perfect Love*, « 001 »).
L'outil numérote par l'index (épisode = index + 1), comme dramafren.

**Vidéo officielle (gratuits).** `m3u8Path` est une URL signée
(`…/origin1/{nom}.m3u8?expiredTime={unix}&tul={jeton}`), valable environ deux
semaines. Sans signature, la playlist répond 403. C'est une playlist média
directe (une seule qualité, `#EXT-X-PLAYLIST-TYPE:VOD`), faite de segments
MPEG-TS de 5 s, **non chiffrés** et **accessibles sans signature**. La somme
des `EXTINF` vaut `playTime` à moins d'une seconde près (118,28 s pour 118).
La tolérance de durée est donc de 1,5 s pour GoodShort. Résolution mesurée :
720×1280 (mêmes segments, octet pour octet, que le 720p de dramafren).

### Vidéos via dramafren

Constats du 27/09/2026 sur `31000835255`.

- **Pages** `goodshort.dramafren.org` : derrière le challenge Cloudflare (403
  « Just a moment… »), comme celles de DramaBox. Le même site PHP répond
  **sans challenge** sur `cdn-goodshort.dramafren.org` (page `watch` de 62 Ko
  en 45 s au premier appel).
- **La page `watch`** contient `chapterIds` (les identifiants officiels des
  chapitres, dans l'ordre des index) et appelle
  `index.php?action=get_video_url&id={bookId}&chap_id={chapterId}&sv={1|2|3}&lang={lang}`.
- **Réponse** : `{"status": "success", "video_url": …, "qualities":
  [{"quality": "720P", "url": …}, {"quality": "540P", …}, {"quality": "1080P", …}]}`.
  Chaque URL est `https://cdn-goodshort.dramafren.org/proxy?token=v2.…` : une
  playlist HLS (une seule qualité, `#EXT-X-PLAYLIST-TYPE:VOD`) dont les
  segments passent aussi par le proxy. Segments MPEG-TS **non chiffrés**
  (octet 0x47). 1080P mesuré en 1080×1920, H.264 + AAC. Les `EXTINF` valent
  tous 5,000000, dernier segment compris : la durée vérifiée est `playTime`.
- **Épisodes payants** : servis comme les gratuits (vérifié sur les index 0,
  40 à 42 et 59).
- `lang` et `sv=2` ne changent rien à la réponse ; un `chap_id` inconnu répond
  `{"status": "error", "video_url": "", "qualities": []}`.
- **Jetons** : encore valables 15 min après (playlist identique). Durée de vie
  réelle non mesurée ; l'outil redemande l'URL à chaque tentative.
- **Lenteur** : l'API répond en 2 à 5 s, mais 30 à 67 s au premier appel
  d'une série (délai d'attente de 60 s, puis nouvel essai). `sv=3` et un appel
  répété sont restés une fois sans réponse pendant 120 s. Un segment met de
  0,6 s à 85 s, contre 50 ms pour la playlist officielle. Mesures du
  27/09/2026 : 6 segments à la suite en 171 s (28 s chacun en moyenne) ;
  8 segments, 4 à la fois, en 70 s (9 s chacun). Le temps vient de la latence
  de chaque requête, pas du débit : les requêtes en parallèle avancent.
- **Test réel** (`sdg fetch … -e 1,60`, 27/09/2026) : épisodes 1 (gratuit) et
  60 (payant) en 1080×1920, 89,5 s et 103,0 s pour `playTime` 89 et 102, en
  15 min au total.

**Intégration** (`providers/goodshort.py`, `dramafren.get_goodshort_video`).
- **Métadonnées** : la fiche si le lien donne un slug ; sinon (`goodshort:n°`,
  lien dramafren), ou si la fiche répond 404, l'API `book/detail`. Puis
  `chapter/page` pour les identifiants et durées de **tous** les chapitres.
- **Sources** : dramafren (1080p, 720p, 540p, `hls`), puis, pour un épisode
  gratuit, la playlist officielle (qualité non annoncée, donc essayée en
  dernier ; relue par `chapter/page` si elle expire dans moins de 5 minutes).
  « Refus » d'un serveur : le suivant est essayé (1, 2, puis 3). Erreur réseau :
  pas d'autre serveur, puisqu'ils sont tous derrière le même hôte.
- **Reprise** : toutes les playlists dramafren s'appellent `/proxy` ; les
  `.part` portent donc la qualité (`E060.proxy.1080p.ts.part`), pour ne jamais
  reprendre un épisode dans une autre qualité.
- **Disponibilité** : dramafren est interrogé sur le dernier épisode.

**Non vérifié** :
- **Versions dans d'autres langues** : non cherchées.
- **Séries sans liste de chapitres** : si `chapter/page` ne répond plus, le
  chargement échoue (erreur réseau) au lieu de retomber sur les 11 chapitres
  de la fiche.

## FlickReels

Constats du 27/09/2026 sur *SSS : Le Dieu de la Foudre* (`9561`, 61 épisodes).

**Liens.** Identifiants courts (4 ou 5 chiffres : `9561`, `11860`), les mêmes
sur dramafren et sur le site officiel. Formats acceptés :
- dramafren : `flickreels.dramafren.org/index.php?page=detail&id={id}&lang=…`
  et `page=watch&id={id}&ep={n}` (**`ep` compté à partir de 1**, contrairement à
  GoodShort) ; même chose sur `cdn-flickreels.dramafren.org` ;
- officiel : `www.flickreels.net/{langue}/episodes-list/{slug}-{id}`,
  `/movie/{slug}-{id}`, `/playlist/{slug}/{id}/episode-{n}` et
  `/playlist/{slug}/{id}/full-movie` ;
- `flickreels:9561`.

Les dossiers s'appellent `flickreels-9561-sss-le-dieu-de-la-foudre` : la
bibliothèque (`library.KEY_RE`), la route de l'affiche d'aperçu et la
détection côté web acceptent maintenant des n° courts pour les plateformes
préfixées (DramaBox garde 6 chiffres au moins).

**Site officiel.** Nuxt ; la page `/episodes-list/{slug}-{id}` répond 404 si
le slug n'est pas exact. Elle embarque 20 chapitres par page (`chapter_id`,
`chapter_num`, `is_lock`, `duration`). Son JavaScript appelle
`https://apiweb.flickreels.net/web/playlet/chapterList` (et `play`,
`chapterCollection`) avec un en-tête `sign` : MD5 des paramètres triés suivis
d'un sel écrit dans le JavaScript. **Non utilisé** : le projet ne forge pas de
signatures (voir [01 §7](01-etude-technique.md#7-cadre-légal-à-garder-en-tête)).

**dramafren.** `flickreels.dramafren.org` est derrière le challenge
Cloudflare ; `cdn-flickreels.dramafren.org` sert le même site sans challenge,
en 1 s environ.
- **Fiche** (`page=detail&id=…`) : titre (`<h1>`), affiche (`og:image`, JPEG du
  CDN officiel), synopsis, « Total: 61 Eps » et les liens des épisodes. Un
  identifiant inconnu renvoie la page d'accueil du lecteur.
- **Page `watch`** : le script contient
  `var availableQualities = [{"quality": "Default Auto", "url": …}]` et
  `initialVideoUrl` : l'URL HLS du **CDN officiel**
  (`zshipricf.farsunpteltd.com` ou `.net`,
  `/playlet-hls/{nom}.m3u8?verify={unix}-{signature}`), valable environ 2 h
  (même échéance pour tous les épisodes). La playlist est une playlist média :
  segments MPEG-TS de 10 s, **non chiffrés** et **sans signature**. Mesuré en
  1080×1920, H.264 + AAC. Au-delà du dernier épisode, la liste est vide.
- `lang` ne change ni le titre ni la vidéo (chaque version a son identifiant).
- Le secours du lecteur (`action=proxy_m3u8`) répond « CDN Error: 403 » ;
  « Server 2 » (`action=server2_stream`) répond « stream unavailable ». Ni
  l'un ni l'autre n'est utilisé.

**Intégration** (`providers/flickreels.py`).
- **Métadonnées** : la fiche dramafren. Pas de durée par épisode ni de
  langue : chaque fichier est vérifié contre la durée de sa propre playlist
  (somme des `EXTINF`, à 0,1 s près sur les épisodes mesurés).
- **Qualité** : une seule, non annoncée (`Default Auto`) : `info` et
  l'interface n'en proposent pas le choix.
- **Disponibilité** : la page `watch` du dernier épisode.
- **Test réel** (`sdg fetch … -e 1,61`) : 2 épisodes, 59 Mo, en 4 s.

**Non vérifié** : séries où dramafren proposerait plusieurs qualités (le code
les lirait, mais le cas n'a pas été vu).

## ShortMax

Constats du 27/09/2026 sur *[Doublé]Protégée par le Seigneur Serpent*
(`24403`, 67 épisodes, VF).

**Liens.** Identifiants courts (`24403`), les mêmes sur le lecteur et sur le
site officiel. Formats acceptés :
- lecteur : `shortmax.ngeshorts.fun/index.php?page=detail&id={id}&lang=…` et
  `page=watch&id={id}&ep={n}` (`ep` compté à partir de 1) ; les liens
  `shortmax.dramafren.org` (même format) sont acceptés mais non vérifiés : ce
  site est derrière le challenge Cloudflare ;
- officiel : `www.shorttv.live/{langue}/drama/{slug}-{id}` et
  `/{langue}/episode/{slug}-{id}-{n}` (`www.shortmax.com` redirige vers
  `www.shorttv.live`) ;
- `shortmax:24403`.

**Site officiel.** Nuxt. `/drama/x-24403` répond 404, mais
`/fr/drama/x-24403` répond (le slug n'y est pas vérifié). Ses données
(`__NUXT_DATA__`) ne contiennent **aucune durée** d'épisode : il n'est pas
utilisé.

**Lecteur** `shortmax.ngeshorts.fun` : copie du lecteur de dramafren, sans
challenge. Fiche identique à celle de FlickReels (titre, affiche du CDN
officiel, synopsis, « Total: 67 Eps »), lue par le même code
(`providers/player.py`). La page `watch` ne contient pas la vidéo : son script
appelle
`index.php?action=video_server&server={server1|server2}&id={id}&ep={n}&lang=…&stale=1`
sur `videoServerEndpoints` (`cdn-shortmaxv3.dramafren.org`, puis
`cdn-shortmaxv5.dramafren.org`), puis sur le lecteur lui-même (8 s, contre
0,2 s pour v3). Réponse (en-tête `Access-Control-Allow-Origin: *`, cache d'un
jour) :

```jsonc
{"ok": true, "server": {"key": "server1", "playUrl": "…_720/main.m3u8?auth_key=…",
  "proxyUrl": "https://cdn-shortmaxv2.dramafren.org/index.php?action=proxy_video&url=…",
  "qualities": [{"quality": "720p", "url": …}, {"quality": "1080p", …}, {"quality": "480p", …}]}}
```

- Les URL `url` pointent sur le **CDN officiel**
  (`akamai-static.shorttv.live/hls/{uuid}_{hauteur}/main.m3u8?auth_key={unix}-0-0-{md5}`).
  La playlist répond aussi sans `auth_key`, et sans User-Agent. Playlist média,
  segments `main/segment-{i}.ts` de 10 s, MPEG-TS **non chiffrés** et **sans
  signature**. Mesuré en 1080×1920 ; 17 segments en 17 s. Somme des `EXTINF`
  164,68 s pour un fichier de 164,84 s.
- `lang` ne change rien ; sans `lang`, même réponse.
- Épisode au-delà du dernier ou identifiant inconnu :
  `{"ok": false, "message": "Server unavailable"}`. `server2` a répondu la même
  chose pour l'épisode 30.

**Intégration** (`providers/shortmax.py`).
- **Métadonnées** : la fiche du lecteur (pas de durée ni de langue : chaque
  fichier est vérifié contre sa playlist, comme pour FlickReels).
- **Sources** : `qualities` (1080p, 720p, 480p ; jamais le `proxyUrl` de
  dramafren). Pour chaque serveur (`server1`, puis `server2`), les points
  d'accès sont essayés dans l'ordre : une erreur réseau passe au suivant, un
  refus passe au serveur suivant (les points d'accès partagent les mêmes
  données).
- **Reprise** : toutes les playlists s'appellent `main.m3u8` ; les `.part`
  portent la qualité (`E001.main.1080p.ts.part`).
- **Test réel** (`sdg fetch shortmax:24403 -e 1,67`) : 2 épisodes en 1080p,
  43 Mo, en 23 s.

**Constat du 02/10/2026** : la fiche du lecteur `shortmax.ngeshorts.fun`
répond 403 (challenge Cloudflare), y compris avec le client de l'outil ;
l'API `video_server` de `cdn-shortmaxv3.dramafren.org` répond toujours.
Charger une série ShortMax échoue donc tant que la fiche reste bloquée.

## NetShort

Constats du 02/10/2026 sur *Naked Tide* (`2103009231354593281`, VO anglaise)
et sa version française *Mon rival, mon demi-frère* (`2103009231497199618`) :
50 épisodes, 1 à 7 gratuits. API dramafren : constats du 03/10/2026.

**Liens.** Identifiants de 19 chiffres, les mêmes sur le site officiel et sur
dramafren. Formats acceptés :
- officiel : `netshort.com/{langue}/episode/{slug}-{id}` (épisode 1),
  `/episode/{slug}-{id}-ep-{n}`, `/full-episodes/{slug}-{id}` et
  `/hotseries/{slug}-{id}` (avis) ; le préfixe de langue (`/fr/`) ne change
  que l'interface, pas la version ;
- dramafren : `netshort.dramafren.org/index.php?page=detail&id={id}` et
  `page=watch&id={id}&ep={n}` (`ep` compté à partir de 1), même chose sur
  `cdn-netshort.dramafren.org` ;
- `netshort:2103009231354593281`.

Les pages `/drama/{genre}-{id}` sont des genres, pas des séries : refusées.

**dramafren.** `netshort.dramafren.org` (et `netshortv2`) est derrière le
challenge Cloudflare (403 « Just a moment… »). `cdn-netshort.dramafren.org`
répond 404 (corps vide) aux pages du lecteur (`page=detail`, `page=watch`) et
aux actions inconnues (`get_video`, `get_video_url`, `video_server`…) ;
`cdn-netshortv2` répond 404 à tout. Les pages archivées par la Wayback Machine
(janvier à mai 2026) montraient l'URL MP4 de **tout** épisode dans la page
`watch` (CDN officiel `awscdn.netshort.com`, signé).

La page `watch` actuelle ne contient plus la vidéo : son script appelle
`index.php?action=resolve_watch&id={id}&ep={n}&server={1|2}&_={horodatage}`
sur `watchActionEndpoints` (`["index.php"]`, donc le lecteur lui-même), et
`cdn-netshort.dramafren.org` sert cette action **sans challenge** (en-tête
`Access-Control-Allow-Origin: *`, `no-store`) :

```jsonc
{"ok": true, "server": 1, "videoUrl": "https://ns-aws-cdn.netshort.com/{nom}?…&auth_key=…",
  "qualities": [{"quality": "Default", "url": …}],  // la même URL
  "subtitles": [{"subtitleLanguage": "fr_FR", "url": …}],
  "source": "Primary"}  // ou "Stale Cache Fallback"
```

- **Tous les épisodes**, payants compris : MP4 du **CDN officiel**
  (`ns-aws-cdn.netshort.com`), signé `auth_key={expiration}-…` à environ
  4 jours, avec `Range`. Mesuré : **540×960**, H.264 + AAC 44,1 kHz,
  ~0,8 Mbit/s (11,3 Mo pour 114 s), contre 720×1280 pour la vidéo officielle
  d'un épisode gratuit. Durées identiques à celles du site officiel au
  millième (114,289 s pour l'épisode 10, 156,92 s pour l'épisode 1).
- **Sous-titres** : seulement ceux de la langue de la version (`fr_FR` pour
  la VF, `en_US` pour *Heiresses on My Tail*, aucun pour *Naked Tide*, dont
  les sous-titres sont incrustés), en WebVTT sur le même CDN.
- **Refus** : HTTP 404 avec `{"ok": false, "status": 404, "message": "Video
  URL is unavailable for this episode."}` (épisode au-delà du dernier,
  identifiant inconnu) ; `ep=0` : 400 « Invalid watch request. ». `server=2`
  a toujours refusé (épisodes 3, 10 et 53 de trois séries) ; `server=3`
  répond comme `server=1`.
- **Lenteur** : 0,1 à 1 s en général, jusqu'à 16 s quand la réponse vient
  de `Stale Cache Fallback` (URL alors encore valable 3 jours et demi).

L'action `proxy_sub` (sous-titres) répond aussi sur cet hôte ; elle n'est pas
utilisée, les URL de sous-titres étant lues directement sur le CDN.

**Site officiel** (Next.js, sans challenge). Chaque épisode a sa page,
rendue côté serveur (~330 Ko) : `/episode/{slug}-{id}` pour l'épisode 1,
`/episode/{slug}-{id}-ep-{n}` pour les suivants. Un mauvais slug est redirigé
(301) vers le bon, donc `/episode/x-{id}` suffit ; sans slug
(`/episode/{id}`) ou avec un identifiant inconnu, 404. Les données sont dans
les `self.__next_f.push([1, "…"])` (chaînes JSON à concaténer) :
- `shortPlayDetailVo` : `shortPlayId`, `shortPlayName`, `shortPlayUrl`
  (`/episode/naked-tide-2103009231354593281`), `shortPlayCover` (PNG
  d'origine de 2,5 Mo ; l'`og:image` du site est la variante
  `~tplv-vod-rs:540:720.webp`, 53 Ko ; le chemin contient « 3比4 », à encoder),
  `shotIntroduce`, `language` (`fr_FR`), `isDelisted`,
  `languageDetail` (chemin et identifiant de chaque autre version) et
  `videoEpisodeInfos` : `episodeId`, `episodeNo`, `isLock` de **tous** les
  épisodes ;
- `initialCurrentEpisodeInfo` : l'épisode affiché, avec `duration` (secondes,
  au millième : 85,24 pour un fichier de 85,240 s), et pour un épisode
  gratuit `playVoucher` et `subtitleList`. Un épisode payant a sa durée mais
  `playVoucher: null`.

L'API appelée par le navigateur pour changer d'épisode passe par une
connexion visiteur (`/web/auth/visitor_login`) : non utilisée, les pages
suffisent.

**Vidéo.** `playVoucher` : MP4 sur `cfcdn.netshort.com`, signé
`auth_key={expiration}-{aléa}-0-{md5}` (expiration à 10 jours de la création
de l'URL ; les pages renvoient une URL déjà vieille de quelques jours). Répond
sans User-Agent ni Referer, avec `Range`. Mesuré : 720×1280, H.264 + AAC
44,1 kHz, ~0,9 Mbit/s (9,9 Mo pour 85 s).

**Sous-titres.** Chaque version a son identifiant (`languageDetail`) et sa
vidéo, sous-titrée ou non :
- *Naked Tide* (VO anglaise) : sous-titres anglais **incrustés**,
  `subtitleList: null` ;
- sa version française : vidéo **sans** sous-titres (audio anglais) et
  `subtitleList` en WebVTT pour 13 langues (`subtitleLanguage`: `fr_FR`…) ;
- *Heiresses on My Tail* (`2047614438592217090`, `en_US`) : vidéo sans
  sous-titres, `subtitleList` avec `en_US`.

Le lecteur du site affiche le fichier de `subtitleList` dont la langue est
celle de la version (`language`) : l'outil fait de même.

**Intégration** (`providers/netshort.py`).
- **Métadonnées** : la page de l'épisode 1 (`/episode/x-{id}`) : titre,
  affiche (variante WebP), synopsis, langue, liste des épisodes et
  gratuits (`isLock: false`, aucun si `isDelisted`). Tous les épisodes sont
  téléchargeables (plus de `Series.free_only`).
- **Sources**, au téléchargement de chaque épisode :
  1. la page de l'épisode sur le site officiel : sa durée (qui sert au
     contrôle, payants compris) et, s'il est gratuit, `playVoucher` (720p,
     qualité non annoncée) et ses sous-titres ;
  2. `resolve_watch` (`server=1`, puis `server=2` après un refus) : le MP4
     540p et les sous-titres de la langue de la série. Une erreur réseau
     n'essaie pas l'autre serveur (même hôte).

  Les deux sources sont sans qualité annoncée : l'ordre (officiel d'abord)
  décide, et le pipeline passe à dramafren si le fichier officiel est
  refusé. Si la page officielle ne répond pas ou montre un autre épisode,
  seul dramafren reste, et son fichier n'est contrôlé que comme MP4 (pas de
  durée attendue). Un épisode que dramafren refuse et que le site officiel
  ne sert pas échoue en `ep_unavailable`.
- **Sous-titres** : `VideoSource.subtitles`, enregistré avant la vidéo en
  `E001.fr.vtt` (langue de la série), contrôlé (en-tête `WEBVTT`, sinon
  `subtitles_unreadable`). Les lecteurs comme VLC le chargent tout seuls ;
  le lecteur de `sdg ui`, la fusion en film et le montage ne l'utilisent pas
  encore.
- **Disponibilité** : `resolve_watch` sur le dernier épisode.
- **Test réel** (`sdg fetch netshort:2103009231497199618 -e 7,8,10,50`,
  03/10/2026) : l'épisode 7 (gratuit) en 720×1280 depuis le site officiel,
  8, 10 et 50 (payants) en 540×960 depuis dramafren, tous avec leurs
  sous-titres français, 41,6 Mo en 4 s.

**Non vérifié** : séries en VO non anglaise ; épisodes gratuits au-delà du
début (seuls 1 à 7 et 1 à 9 ont été vus) ; `server=2` qui répondrait ;
séries que le site officiel ne connaîtrait pas (non gérées : les métadonnées
en viennent toujours).

## Plateformes restantes

Pour chacune, il reste à établir, sur le site officiel, ce qui a été établi
pour GoodShort :
- les formats de lien ;
- où sont les métadonnées ;
- quels épisodes sont gratuits ;
- le format vidéo (MP4, HLS, chiffré ou non) ;
- ce qui est signé et pour combien de temps.
