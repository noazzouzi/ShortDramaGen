# 01 — Étude technique

> Constats vérifiés le **2026-09-26** sur la série *One Night to Forever*
> (`bookId = 41000105199`, 62 épisodes). Tout ce qui est marqué ✅ a été testé ;
> ce qui est marqué ❓ reste à confirmer. Les captures HAR fournies ont permis
> de trouver l'API décrite au §2.2.

## 1. Les trois acteurs

| Acteur | Rôle pour nous | Protection |
|---|---|---|
| **API dramafren** `cdn-dramabox.dramafren.org` | URL vidéo signée pour **tous** les épisodes, en 540p, 720p et 1080p | **Aucune** (ni challenge, ni cookie) |
| Pages dramafren `dramabox.dramafren.org` | Interface web (inutile pour nous) | Cloudflare *Managed Challenge* / Turnstile |
| **www.dramaboxdb.com** (site officiel) | Métadonnées complètes + MP4 des **10 premiers** épisodes | Aucune (Next.js statique) |
| **CDN vidéo `*.dramaboxdb.com`** | Sert les fichiers MP4 / HLS | URL signée avec expiration, rien d'autre |

---

## 2. dramafren

### 2.1 Les pages HTML (`dramabox.dramafren.org`)

- Site PHP : `index.php?page=detail&id={bookId}&lang={lang}` et
  `index.php?page=watch&id={bookId}&ep={n}&lang={lang}&slug={slug}&sv={1|2|3}`.
  Le paramètre `id` **est le `bookId` DramaBox**.
- ✅ **Protégé par Cloudflare** (`cf-mitigated: challenge`, `cType: 'interactive'`) :
  - `curl` → `403` + page « Just a moment… ».
  - Chromium headless (Playwright) depuis une IP de datacenter → bloqué
    indéfiniment sur la case « Vérifiez que vous êtes humain ».
  - Depuis ton Chrome (IP résidentielle, vrai profil) → ça passe.
- Le menu liste 20+ plateformes (GoodShort, ReelShort, ShortMax, NetShort,
  FlickReels…) sur des sous-domaines du même modèle.

### 2.2 L'API vidéo (trouvée grâce aux captures HAR) ✅

La page `watch` ne contient pas l'URL : son JavaScript appelle une API JSON
**sur un autre sous-domaine, qui n'est pas derrière le challenge Cloudflare** :

```
GET https://cdn-dramabox.dramafren.org/index.php?action=get_video&id={bookId}&ep={n}&lang={lang}&sv=1
    (le site essaie ensuite https://cdn-dramaboxv2.dramafren.org/... en secours, timeout 10 s)
```

```jsonc
{
  "ok": true,
  "videoUrl": "https://hwztakavideoto.dramaboxdb.com/f940aa0c…/6ad5b861/36/…/577159363.720p.narrowv3.mp4",
  "qualities": [
    { "quality": "Server 1 720p",  "url": "…/577159363.720p.narrowv3.mp4" },
    { "quality": "Server 1 1080p", "url": "…/577159363.1080p.nav2.mp4" },   // 10,1 Mo au lieu de 6,9
    { "quality": "Server 1 540p",  "url": "…/577159363.540p.narrowv2.mp4" }
  ],
  "subtitles": [], "isHls": false, "activeVideoServer": 1
}
```

- ✅ **Aucun cookie** ni jeton : la requête du navigateur (HAR) n'en envoie pas,
  et `curl` seul obtient la même réponse. `Access-Control-Allow-Origin: *`,
  cache de 5 min côté Cloudflare.
- ✅ **Trois qualités** : 540p, 720p (celle lue par défaut) et **1080p**.
- ✅ **`lang` n'a aucun effet** sur la vidéo : `en`, `fr` et `es` renvoient le
  même fichier (la VO). Les versions doublées ont **leur propre `bookId`**,
  qu'on passe directement dans `id` (§5) :
  `id=41000111625` renvoie bien les fichiers de la VF (`52611100014/586357960…`).
- ✅ `sv=2` et `sv=3` → `{"ok": false, "error": "Video unavailable"}` pour
  DramaBox. Seul `sv=1` fonctionne.
- ✅ Épisode hors limites (`ep=63`) → même réponse `ok: false`.
- Le jeton Akamai des URLs a la **même expiration pour tous les épisodes**
  (`6ad5b861` = 2026-10-19). dramafren semble donc les générer par lots.

## 3. Le CDN vidéo (l'URL que tu as capturée)

```
https://hwztakavideoto.dramaboxdb.com/f940aa0c163471fa5ae4deac10afef0d/6ad5b861/36/9x9/99x1/991x5/99150100014/577159363_1/577159363.720p.narrowv3.mp4
                                     └──────── signature MD5 ───────┘ └expire┘ └──────────────────── chemin ───────────────────────────────┘
```

- ✅ **Akamai devant S3** (en-têtes `Akamai-Mon-*`, `Server: AmazonS3`).
- ✅ **Jeton dans le chemin** : `/{md5}/{expiration en hexadécimal}/…`.
  `0x6ad5b861` = **2026-10-19 06:27:45 UTC**, soit une validité d'environ 3
  semaines après génération.
- ✅ **Aucune autre protection** : pas de `Referer`, cookie ni User-Agent
  requis, `Access-Control-Allow-Origin: *`.
- ✅ **Range supporté** (`206 Partial Content`) : reprise sur coupure et
  téléchargement parallèle possibles.
- ✅ **MP4 « faststart »** (`ftyp` → `moov` → `mdat`), 720p, 6,9 Mo pour 79 s.
  Débit mesuré depuis le sandbox : ~9,7 Mo/s.
- ✅ **Durée du fichier = durée des métadonnées officielles** : 79,134 s dans
  `mvhd` contre `duration: 79134` (ms) sur le site officiel. On obtient un
  **contrôle d'intégrité gratuit et exact**.

Ordre de grandeur : ~6-7 Mo par minute, soit **~450 Mo pour une série de 62
épisodes**.

## 4. Le chemin CDN est déterministe ✅

À partir du `bookId` et du `chapterId` (ID d'épisode), le chemin se calcule :

```
r   = reverse(bookId)             # 41000105199 -> 99150100014
cid = chapterId                   # 577159363
seg = reverse(cid[-2:])           # "63" -> "36"

{seg}/{r[0]}x{r[1]}/{r[:2]}x{r[2]}/{r[:3]}x{r[3]}/{r}/{cid}_1/{cid}.720p.narrowv3.mp4
= 36/9x9/99x1/991x5/99150100014/577159363_1/577159363.720p.narrowv3.mp4   ✔
```

Formule vérifiée sur **144 URLs sans exception** : covers et MP4 des 62
épisodes, en VO (`41000105199`) et en VF (`41000111625`), plus l'URL
dramafren. Les URLs HLS ajoutent seulement un segment `/m3u8/` avant le nom
du fichier.

**Ce qu'on ne peut pas calculer, c'est la signature** (MD5 + expiration côté
Akamai, `Signature`/`Key-Pair-Id` côté CloudFront) : il faut toujours une
source autorisée (un « resolver ») pour obtenir une URL valide. La formule
sert à **vérifier qu'une URL capturée correspond bien à l'épisode attendu**,
pour éviter qu'un épisode 28 se retrouve enregistré sous le nom de l'épisode 27.

## 5. Le site officiel `www.dramaboxdb.com` ✅

Next.js en génération statique (`gsp: true`), **sans challenge Cloudflare**.

### URLs

| Page | Format |
|---|---|
| Série | `/{locale?}/movie/{bookId}/{slug}` (le slug est corrigé par redirection) |
| Épisode | `/{locale?}/ep/{bookId}_{slug}/{chapterId}_Episode-{n}` |
| **JSON brut** | `/_next/data/{buildId}/{locale?}/movie/{bookId}/{slug}.json` |

`buildId` se lit dans `__NEXT_DATA__` de n'importe quelle page (actuellement
`dramaboxdb_prod_20260908`). Il change à chaque déploiement : il faut le relire
à chaque exécution, ou à défaut parser `__NEXT_DATA__` dans le HTML.

### Contenu de `pageProps` (page série)

```jsonc
{
  "bookInfo": { "bookId": "41000105199", "bookName": "One Night to Forever",
                "introduction": "...", "cover": "...", "chapterCount": 62,
                "tags": [...], "language": "ENGLISH", "performerList": [...] },
  "chapterList": [            // les 62 épisodes, dans un seul appel
    { "id": "577159336", "index": 0, "indexStr": "001", "duration": 153118,
      "unlock": true,         // true pour les épisodes 1 à 10 uniquement
      "mp4": "https://hwvideoseo.dramaboxdb.com/…720p.narrowv3.mp4?Expires=…&Signature=…&Key-Pair-Id=…",
      "m3u8Url": "https://hwzthls.dramaboxdb.com/…/m3u8/577159336.720p.m3u8?Expires=…",
      "cover": "…" },
    { "id": "577159363", "index": 27, "unlock": false, "duration": 79134, "cover": "…" }  // pas d'URL
  ],
  "languages": ["ko","th","in","ja","en","fr","es"],
  "sourceBookId": "41000105199",   // "41000111625" sur /fr/ : version doublée
  "tabData": ["1-50", "51-62"]
}
```

- ✅ **Épisodes 1 à 10** : MP4 et HLS fournis. Signature CloudFront valable
  ~24 h. Le HLS n'est **pas chiffré** (pas de `#EXT-X-KEY`).
- ✅ **Épisodes 11 et suivants** : la page épisode ne donne qu'un `freeSource` =
  aperçu de **15 secondes** (`….720p.nav2.15s.mp4`).
- ✅ **Langues** : `/fr/movie/41000105199/…` renvoie la **version doublée**
  (« Qui Est la Véritable Mme Lafont ? »), avec un autre livre source
  (`41000111625`) et d'autres IDs vidéo (`586357933…`). Les `id` de
  `chapterList` restent ceux de la VO.

- ✅ Une langue non proposée (ex. `/de/`) renvoie la VO (`sourceBookId` =
  `bookId`). Autre version doublée vérifiée : `/es/` → `41000106297`
  (« Una Noche Para Siempre »).
- ✅ Série inexistante → `404` (page Next.js `/404` sans `bookInfo`).

**Conclusion** : le site officiel est la **source de vérité pour les
métadonnées** (titre, synopsis, nombre d'épisodes, IDs, durées) et donne
le `bookId` de chaque version doublée. L'API dramafren fournit les URLs de
**tous** les épisodes. Le site officiel sert de secours pour les 10 premiers.

## 6. Formats d'URL d'entrée à accepter

| Source | Exemple | Statut |
|---|---|---|
| Site officiel (série) | `https://www.dramaboxdb.com/fr/movie/41000105199/one-night-to-forever` | ✅ |
| Site officiel (épisode) | `https://www.dramaboxdb.com/ep/41000105199_one-night-to-forever/577159363_Episode-28` | ✅ |
| dramabox.com | `https://www.dramabox.com/drama/41000105199/One-Night-to-Forever` | ✅ 200 |
| Lien de partage de l'app | domaine `dramaboxapp.com` | ❓ format exact à confirmer avec un vrai lien |
| dramafren | `https://dramabox.dramafren.org/index.php?page=detail&id=41000105199&lang=fr` | ✅ |
| ID brut | `41000105199` | ✅ |

Tous se ramènent à un **`bookId` de 11 chiffres** (préfixes `41…` ou `42…`
observés), plus éventuellement une langue.

## 7. Cadre légal (à garder en tête)

- Le contenu appartient à DramaBox (STORYMATRIX PTE. LTD.). Dans l'app, les
  épisodes au-delà des 10 premiers sont payants ; dramafren est un site non
  officiel qui les « déverrouille ».
- Télécharger pour un usage personnel reste une zone grise. **Republier** ces
  vidéos (YouTube, TikTok…) expose à des réclamations Content ID, des
  avertissements et des retraits DMCA : DramaBox publie ses propres extraits
  sur ses chaînes officielles et surveille ces plateformes.
- Si l'objectif final de *ShortDramaGen* est de publier, la voie propre passe
  par un accord : le site officiel liste un contact
  `partnerships@dramabox.com` (licences IP / partenariats) sur
  `/business`.
- Choix de conception qui en découle : **on ne forge pas de signatures CDN et on
  ne rétro-ingénie pas l'API privée de l'app**. Le projet automatise uniquement
  ce que fait le lecteur dramafren dans ton navigateur (un appel `get_video`
  par épisode, espacés de 0,3 s).
- Usage déclaré : défi technique personnel, sans republication.
