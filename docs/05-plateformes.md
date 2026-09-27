# 05 — Plateformes

> État au 27/09/2026. Le fonctionnement commun (interface `Provider`,
> références `plateforme:n°`, HLS, « gratuits seulement ») est décrit dans
> [02 — Architecture §7](02-architecture.md#7-plateformes-providers).

## Principe retenu

Chaque plateforme ajoutée est lue **depuis son site officiel** : métadonnées,
et vidéos des épisodes que le site sert gratuitement. Les épisodes payants
restent dans l'application de la plateforme. On n'utilise pas de site tiers
qui débloque les épisodes payants pour ces plateformes.

## Vue d'ensemble

| Plateforme | Site officiel | État |
|---|---|---|
| DramaBox | dramaboxdb.com | Intégrée (voir [01 — Étude technique](01-etude-technique.md)) |
| GoodShort | www.goodshort.com | **Intégrée** : épisodes gratuits, HLS (ci-dessous) |
| NetShort | netshort.com | Étude interrompue (voir « Étude en pause ») |
| FlickReels | www.flickreels.net | Site joignable, pas étudié |
| ShortMax | www.shortmax.com → redirige vers www.shorttv.live | Site joignable, pas étudié |
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
chiffres commençant par 31.

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

**Vidéo.** `m3u8Path` est une URL signée
(`…/origin1/{nom}.m3u8?expiredTime={unix}&tul={jeton}`), valable environ deux
semaines. Sans signature, la playlist répond 403. C'est une playlist média
directe (une seule qualité, `#EXT-X-PLAYLIST-TYPE:VOD`), faite de segments
MPEG-TS de 5 s, **non chiffrés** et **accessibles sans signature**. La somme
des `EXTINF` vaut `playTime` à moins d'une seconde près (118,28 s pour 118).
La tolérance de durée est donc de 1,5 s pour GoodShort.

**Intégration** (`providers/goodshort.py`).
- **Liste des épisodes** : `chapterCount` donne la liste complète ; les
  épisodes au-delà de la liste embarquée n'ont ni durée ni vidéo.
- **Sources** : l'URL gratuite est une source `hls` ; elle est relue sur la
  fiche si elle expire dans moins de 5 minutes.
- **Épisodes payants** : ils répondent `ep_unavailable`.

**Non vérifié** (à confirmer avant de s'y fier) :
- **Fiche sans slug** : `sdg fetch goodshort:31000662271` tente
  `/drama/31000662271`. La page contient un `redirectObj` qui laisse penser
  que le site redirige vers l'URL canonique, mais ce n'est pas testé. Coller
  le lien complet évite la question.
- **Épisodes gratuits au-delà des 11 listés** : ils ne seraient pas vus. Les
  pages d'épisode (`/episode/…`) les exposent peut-être.
- **Versions dans d'autres langues** : non cherchées.

## Étude en pause

En récupérant la page d'une série NetShort (Next.js, données dans
`self.__next_f`), la requête a été bloquée par le classifieur de sécurité du
mode automatique de Claude Code (motif : « Third-Party Attack »). L'étude des
plateformes restantes est suspendue en attendant une décision sur ce blocage. Pour chacune, il
reste à établir, sur le site officiel, ce qui a été établi pour GoodShort :
- les formats de lien ;
- où sont les métadonnées ;
- quels épisodes sont gratuits ;
- le format vidéo (MP4, HLS, chiffré ou non) ;
- ce qui est signé et pour combien de temps.
