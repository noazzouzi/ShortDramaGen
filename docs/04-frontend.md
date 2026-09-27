# 04 — Frontend : plan, brainstorm et maquette

> **Maquette haute fidélité** : [canevas « Maquette ShortDramaGen »](https://claude.ai/artifact/7aFKCrXeMqch89v37XBH4G).
> Elle compte 10 écrans cliquables (8 desktop, 2 mobile), construits sur de vraies séries. Le lien est privé tant que tu ne le partages pas.
>
> **Spécification complète** : [frontend/spec-v1.md](frontend/spec-v1.md) · **Système visuel** : [frontend/design-system.md](frontend/design-system.md) · **Données de la maquette** : [frontend/jeu-de-donnees-maquette.md](frontend/jeu-de-donnees-maquette.md) · **Brainstorm** : [frontend/brainstorm/](frontend/brainstorm/)

## 1. La demande

Visualiser et gérer tout ce que fait le moteur, depuis une interface soignée côté UX/UI :
- **donner une URL** et **télécharger tous les épisodes disponibles** ;
- **gérer l'ensemble des séries** possédées ;
- partir d'une maquette optimisée.

## 2. Méthode

Le travail s'est fait en plusieurs passes indépendantes, avec une confrontation des points de vue avant chaque décision.

| Étape | Qui | Livrable |
|---|---|---|
| Recherche | 4 analyses en parallèle | [Capacités du moteur](frontend/brainstorm/1-recherche-capacites-du-moteur.md) (lues dans le code, avec les écarts trouvés) · [Benchmark UX](frontend/brainstorm/2-recherche-benchmark-ux.md) (Sonarr/Radarr, Plex/Jellyfin, qBittorrent, JDownloader, Tube Archivist, apps de short dramas…) · [Parcours et états](frontend/brainstorm/3-recherche-parcours-et-etats.md) · [Architecture](frontend/brainstorm/4-recherche-architecture.md) |
| Concepts | 3 directeurs UX, chacun avec un angle imposé | [A « Bibliothèque d'abord »](frontend/brainstorm/5-concept-A.md) · [B « Flux d'abord »](frontend/brainstorm/5-concept-B.md) · [C « Poste de pilotage »](frontend/brainstorm/5-concept-C.md) |
| Jury | 3 juges indépendants (heuristiques · efficacité · visuel, accessibilité et faisabilité) | [Notes et verdicts](frontend/brainstorm/6-jury.md) |
| Synthèse | Lead designer | [Spec v1](frontend/spec-v1.md) + [système visuel](frontend/design-system.md) + plan des écrans |
| Maquette | 10 écrans construits, validés automatiquement (format), puis revus sous 5 angles et corrigés | Canevas publié |

## 3. Décision : « Bibliothèque d'abord », en version hybride

**Scores cumulés du jury : A = 148 · B = 140 · C = 134.** Le concept A arrive premier chez les trois juges.

- **L'accueil, c'est la collection** : un mur d'affiches. Une série = une carte ; les langues sont des **versions** de la même série, alors que le moteur crée un dossier par langue.
- **La tâche principale reste en 2 gestes** : Ctrl+V n'importe où, puis Entrée. Un aperçu s'ouvre dans un dialogue (titre, épisodes, versions, taille, temps estimé), et « Télécharger » lance tout.
- **Idées reprises de B et C** :
  - pilule d'activité en texte dans l'en-tête (« ↓ 21/82 · ≈ 1 min 10 s · +1 en file ») et tiroir Activité ;
  - couleur « en cours » dédiée (lavande), distincte de l'accent bleu ;
  - « Regarder l'ép. 1 » pendant que la suite arrive ;
  - pré-vol du film (épisodes, format, ffmpeg, espace, nom) où chaque refus devient un choix ;
  - « Tout réparer » limité aux actions sûres ;
  - raccourcis adaptés à Windows et à l'AZERTY.
- **Écartés** :
  - flux d'activité en page d'accueil (les jobs durent environ 1 min) ;
  - poste à 4 zones (trop chargé pour un seul utilisateur) ;
  - grilles de 12 épisodes par ligne : on garde la **grille décimale de 10**, héritée de dramafren, où l'épisode 28 est en rangée 3, colonne 8 ;
  - recherche par titre (le moteur ne sait pas la faire).

## 4. Principes UX

1. **Une URL, un geste.** Des valeurs par défaut mémorisées et des options repliées.
2. **La série, pas le fichier.** Dossiers, manifest et liens signés n'apparaissent que dans « Détails techniques ».
3. **La confiance se prouve.** « Vérifié » seulement si la durée est conforme ; « 62/62 » visible partout.
4. **Le système répare, l'utilisateur décide.** Nouveaux essais et liens expirés se gèrent seuls ; on ne dérange l'utilisateur que pour une décision, toujours avec le bouton de réparation.
5. **Calme en arrière-plan.** La progression se lit en périphérie (titre d'onglet, pilule, notification) ; aucune modale pour attendre.
6. **Le vertical d'abord.** Lecteur 9:16 ; la place libre sert au contexte (épisodes, chapitres).
7. **Rien ne se perd.** Corbeille avec [Annuler] et reprise idempotente.
8. **Parité avec la CLI.** Tout ce que font `info`, `fetch`, `links` et `film` se fait aussi dans l'interface, et la commande équivalente reste copiable.

## 5. Architecture de l'information

```
En-tête permanent : logo · « Chercher ou coller » (Ctrl K) · [+ Ajouter] · pilule Activité · Réglages
├── #/                          Bibliothèque : filtres, étagère « À traiter », mur d'affiches | liste
├── #/serie/<id>/<version>      Fiche : héros + onglets de version, barre de santé, grille d'épisodes, Film, Stockage
│   └── …/lire/<n|film>         Théâtre : lecteur vertical 9:16 + épisodes et chapitres
├── #/activite                  Tiroir sur desktop, page sur mobile
└── #/reglages/<section>        Réglages et santé (ffmpeg, disque, connectivité)
Couches : dialogue d'ajout (aperçu) · Supprimer · menus · toasts
```

La profondeur maximale est de 2 niveaux, plus le Théâtre en surcouche.

## 6. Les écrans de la maquette

| Écran | Ce qu'il montre |
|---|---|
| **Bibliothèque** (accueil) | Mur de 12 vraies séries aux états variés, filtres avec compteurs, étagère « À traiter · 3 », pilule d'activité, champ qui détecte un lien collé, sélection multiple, menus, toasts |
| **Ajout par URL** | Dialogue d'aperçu : lien reconnu, squelette, puis fiche d'aperçu, choix de la version (VO, VF, VE), qualité, choix d'épisodes par plages (« 1-10 »), coût (taille, temps, espace), « Copier la commande » |
| **Fiche série** | VF de « Qui Est la Véritable Mme Lafont ? » avec des statuts mixtes réels (vérifiés, 720p, échec, indisponible, fichier manquant), barre de santé avec une seule action principale, volet de détail, section Film bloquée avec remèdes |
| **Film** | Pré-vol ; réparation puis fusion, avec la progression dans le bouton ; film prêt ; variantes (manquants, formats mélangés, nom déjà pris…) |
| **Activité** | Tiroir : job en cours (vitesse, ETA, ruban d'épisodes), file, interrompus, terminés, journal ; pause et annulation avec confirmation |
| **Théâtre** | Lecteur vertical, navigation entre épisodes, grille latérale, enchaînement automatique, chapitres du film |
| **États** | Premier lancement au calme, moteur injoignable, hors ligne, disque plein, lien invalide, série introuvable, mode sonde, ffmpeg absent |
| **Réglages** | Santé (ffmpeg, dossier, disque, connectivité), dossier, version préférée, qualité, parallélisme, stockage « libérable », thème, raccourcis |
| **Mobile · Bibliothèque** | Mur de 3 colonnes avec action visible sans survol, mini-barre d'activité, ajout en feuille avec [Coller] |
| **Mobile · Fiche** | Série en cours de téléchargement : grille de 5 par ligne qui se remplit en direct, action principale collée en bas |

## 7. Système visuel (résumé)

- **Direction** : « Salle de projection bleu nuit », dans la continuité de dramafren. L'interface est sobre et désaturée ; ce sont les **affiches qui apportent la couleur**.
- **Couleurs** :
  - fond `#0B1220` et surfaces `#131C2E` / `#1B2640` / `#243150` ;
  - texte `#E8ECF4` / `#A7B2C8` / `#8E9BB4` ;
  - accent `#5B9BFF` (action, lien, sélection) et lavande `#C4B5FF` réservée à « en cours » ;
  - succès `#3DD68C`, avertissement `#F5B544`, danger `#FF6B6B`, info `#56C8E8` ;
  - tous les ratios de contraste sont vérifiés (texte ≥ 4,5:1).
- **Typographie** : IBM Plex Sans et IBM Plex Mono, chiffres tabulaires partout où ça bouge.
- **Statuts d'épisode** : jamais portés par la seule couleur. Chaque statut combine un palier de luminance, un bord (plein ou tirets), un glyphe et un nom accessible. Téléchargé = vert moyen avec coche ; échec = rouge vif avec « ! » ; en cours = lavande avec barre ; manquant = tirets ambre avec « ? ».
- **Interdits** : dégradés décoratifs, emoji, bordures gauches colorées, ombres sur les éléments posés.

Détails complets : [frontend/design-system.md](frontend/design-system.md).

## 8. Architecture technique retenue

| Sujet | Décision |
|---|---|
| Lancement | `sdg ui` : serveur de la **bibliothèque standard** (`ThreadingHTTPServer`) sur `127.0.0.1:8765` qui ouvre le navigateur (ou `--window` pour une fenêtre Edge en mode app). Philosophie « zéro dépendance » conservée. |
| Temps réel | REST/JSON pour les commandes, **SSE** (`/api/events`) pour la progression, avec rejeu. |
| Client | HTML, CSS et JS natifs, modules ES, Custom Elements, routeur par hash. **Pas de npm ni de build.** Polices et icônes auto-hébergées. |
| Jobs | File persistée (`downloads/.sdg/jobs.json`), 1 série à la fois × 3 épisodes, pause, reprise et annulation propres, reprise au redémarrage. |
| Bibliothèque | Scan des `manifest.json`, réconciliation avec le disque (fichier supprimé = « manquant », `.part` = « interrompu »), regroupement des versions par série. |
| Médias | Lecture dans le navigateur via `/media/…` avec `Range` (les épisodes sont en faststart). |
| Sécurité | Écoute locale uniquement, jeton anti-CSRF, contrôle `Host`/`Origin`, CSP stricte, **aucun chemin fourni par le client**, aucune URL signée exposée. |

Contrat d'API complet (routes, charges utiles, événements SSE) : [spec-v1.md §11](frontend/spec-v1.md#11-contrat-dapi-v1).

## 9. Plan d'implémentation

| Étape | Contenu | Estimation |
|---|---|---|
| **0. Moteur pilotable** | Annulation injectable, événements de progression (octets, épisodes), codes d'erreur stables, option `force`, aperçu sans téléchargement, `make_film` réutilisable. La CLI reste identique et les tests existants passent. | 1,5 j |
| **1. Serveur en lecture seule** | `sdg ui`, bibliothèque, fiches, lecture des médias | 1,5 j |
| **2. Jobs et temps réel** | File, SSE, pause, reprise, réparation, film, corbeille, réglages | 2 j |
| **3. Client MVP** | Tous les écrans de la maquette | 4 à 5 j |
| V1.1 | Catalogue des langues, « Continuer à regarder », nouveaux épisodes, notifications Windows, zip portable | 2 j |
| V2 | Accès depuis le téléphone (réseau local authentifié), `.exe`, 2 séries en parallèle | — |

La recherche sur le code a trouvé des écarts à corriger à l'étape 0 :
- après un Ctrl+C, des épisodes restent en `downloading` dans le manifest ;
- `fetch --film` ne transmet ni `reencode` ni `allow_missing` ;
- un film existant est écrasé sans confirmation.

Détails : [brainstorm/1-recherche-capacites-du-moteur.md](frontend/brainstorm/1-recherche-capacites-du-moteur.md).

## 10. Questions ouvertes

1. L'affiche désaturée pendant le premier téléchargement est-elle lue comme « désactivée » ? À tester sur quelques cartes.
2. Les estimations de taille en 720p et 540p ne sont pas encore mesurées ; elles restent marquées « estimation ».
3. Les langues doublées autres que VF et VE ne sont pas vérifiées pour la série de test.
4. Faut-il un réglage « supprimer les épisodes après création du film » ? Recommandation : non, seulement une suggestion unique après la création.
