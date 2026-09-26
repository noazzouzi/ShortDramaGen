# 01 — Étude technique

> Constats vérifiés le **2026-09-26** sur la série *One Night to Forever*
> (`bookId = 41000105199`, 62 épisodes). Tout ce qui est marqué ✅ a été testé ;
> ce qui est marqué ❓ reste à confirmer.

## 1. Les trois acteurs

| Acteur | Rôle pour nous | Protection |
|---|---|---|
| **dramabox.dramafren.org** | Fournit une URL vidéo pour **tous** les épisodes | Cloudflare *Managed Challenge* / Turnstile |
| **www.dramaboxdb.com** (site officiel) | Métadonnées complètes + MP4 des **10 premiers** épisodes | Aucune (Next.js statique) |
| **CDN vidéo `*.dramaboxdb.com`** | Sert les fichiers MP4 / HLS | URL signée avec expiration, rien d'autre |

---

## 2. dramafren (`dramabox.dramafren.org`)

- Site PHP : `index.php?page=detail&id={bookId}&lang={lang}`. Le paramètre `id`
  **est le `bookId` DramaBox** : pas besoin de mapping.
- ✅ **Protégé par Cloudflare** (`cf-mitigated: challenge`, `cType: 'interactive'`) :
  - `curl` → `403` + page « Just a moment… ».
  - Chromium headless (Playwright) depuis une IP de datacenter → bloqué
    indéfiniment sur la case « Vérifiez que vous êtes humain ».
  - Depuis ton Chrome (IP résidentielle, vrai profil) → ça passe.
- ❓ **Mécanisme interne inconnu** : comment un clic sur « Ep 28 » produit l'URL
  MP4 (page `watch`, appel XHR/`fetch` vers une API JSON, URL déjà présente dans
  le HTML…). Impossible à observer depuis un serveur à cause de Cloudflare : il
  faut une capture HAR depuis ton navigateur (voir
  [03 — Brainstorm, §5](03-brainstorm-et-roadmap.md#5-action-demandée--capture-har)).
- Le menu liste 20+ plateformes (GoodShort, ReelShort, ShortMax, NetShort,
  FlickReels…) sur des sous-domaines du même modèle → l'architecture doit
  prévoir **plusieurs plateformes**, même si on commence par DramaBox.
- ❓ `lang=fr` sur dramafren a renvoyé la vidéo de la **version originale**
  (chemin `99150100014`, voir §4), pas la version doublée française. Le paramètre
  semble ne concerner que l'interface ou les sous-titres.

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

**Conclusion** : le site officiel est la **source de vérité pour les
métadonnées** (titre, synopsis, cover, nombre d'épisodes, IDs, durées) et
suffit pour les 10 premiers épisodes. dramafren n'est nécessaire que pour
**résoudre les URLs des épisodes 11+**.

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
  ce que tu fais déjà à la main dans ton navigateur.
