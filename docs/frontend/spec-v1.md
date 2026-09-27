# ShortDramaGen : spécification du frontend (v1)

> Document de référence pour la maquette haute fidélité, puis pour le vrai frontend. Langue de l'interface : français, avec tutoiement. Cible : Windows 10/11, Edge ou Chrome, 1440 et 1280 px. Mise en page 390 px pour les fenêtres étroites, puis pour le téléphone en V2.
> Toutes les données viennent des faits vérifiés. Les séries autres que « One Night to Forever » sont des **titres d'exemple fictifs** (§3).

> **Mise à jour après la maquette** : les covers DramaBox réelles sont en **3:4** (540 × 720), pas en 9:16 ; seules les vidéos sont verticales en 9:16. Le jeu de données du §3 (titres fictifs) est remplacé par de vraies séries : voir [jeu-de-donnees-maquette.md](jeu-de-donnees-maquette.md).

---

## 0. En bref

- **Concept retenu : A « Bibliothèque d'abord », en version hybride.** Il obtient 148 points contre 140 pour B et 134 pour C, et il arrive premier chez les trois juges. L'accueil est la collection : un mur d'affiches 9:16. Un champ global sert à coller un lien ou à chercher, et l'aperçu d'ajout s'ouvre dans un dialogue. L'activité se suit dans une **pilule texte** en en-tête et dans un tiroir.
- **Idées reprises de B et C :**
  - pilule d'activité ;
  - couleur « en cours » dédiée (lavande), distincte de l'accent bleu ;
  - « Regarder l'ép. 1 » pendant le téléchargement ;
  - pré-vol du film complet, avec case « Remplacer » ;
  - carte des erreurs ;
  - « Tout réparer » limité aux actions sûres, et « Ignorer » ;
  - filtres « Libérable » et « Non vérifiées » ;
  - raccourcis clavier adaptés à Windows et à l'AZERTY ;
  - glisser-déposer d'un lien ;
  - détection des onglets multiples.
- **Technique :** la commande `sdg ui` lance un serveur de la bibliothèque standard sur `127.0.0.1:8765`. Les commandes passent en REST/JSON, le temps réel en SSE. Le client est en JS natif sans build (Custom Elements en light DOM) et les polices IBM Plex sont auto-hébergées.
- **Prérequis bloquant :** l'étape 0 « moteur pilotable » (§12) : annulation injectable, événements structurés, codes d'erreur, option `force`, index de bibliothèque.

---

## 1. Décision

### 1.1 Pourquoi A
1. **C'est lui qui répond le mieux à la demande « manager l'ensemble des séries ».** Sa page d'accueil est la collection elle-même. On reconnaît une série à sa cover même quand son titre change selon la langue (« Qui Est la Véritable Mme Lafont ? » et « One Night to Forever » partagent la même affiche).
2. **Un seul modèle mental :** une série = une carte, et les langues sont des **versions** de cette série. Le moteur crée un dossier par langue, mais l'interface les regroupe.
3. **La tâche principale reste aussi rapide qu'ailleurs :** Ctrl+V puis Entrée, soit 2 interactions au clavier.
4. **C'est le plus simple à construire en JS sans build.** L'affiche qui se colore tient dans une variable CSS, et la même grille d'épisodes sert partout.
5. **Ses faiblesses se corrigent à faible coût** avec des idées de B et C : file peu visible, accent qui servait aussi à la progression, couleur des tuiles trop peu contrastée.

### 1.2 Idées reprises de B et C

| Idée | Origine | Où | Pourquoi |
|---|---|---|---|
| Pilule d'activité en texte (« ↓ 21/80 · ≈ 1 min 10 s · +1 en file ») | B et C | En-tête, toutes les pages | Rend la file visible sans créer d'écran File |
| Couleur « en cours » dédiée (lavande `#C4B5FF`), distincte de l'accent | B et C | Tuiles, ruban, pilule, badges | La progression ne se confond plus avec le bouton principal ni avec le focus |
| « ▶ Regarder l'ép. 1 » dès le premier épisode vérifié | B (S7) | Carte, tiroir, fiche | Un téléchargement d'environ 1 min devient invisible, puisqu'on regarde déjà |
| Pré-vol du film : épisodes, format, ffmpeg, **espace**, **nom**, case « Remplacer le film existant » | C | Section Film | Le moteur écrase le film sans prévenir (`ffmpeg -y`, film.py:235 et 250) |
| Carte des erreurs : cas du moteur → lieu → message → action | C (§3.14) | §8 | Sert à la fois de contrat d'implémentation et de jeu de tests des états |
| « Tout réparer » limité aux actions sûres, avec un récapitulatif chiffré | C, et B pour le récapitulatif | Étagère « À traiter » | Réparer toute la collection en 1 à 2 interactions sans lancer 700 Mo par surprise |
| « Ignorer » mémorisé ; une sélection partielle volontaire ne déclenche jamais d'alerte | B | À traiter | Évite qu'« À traiter » devienne une liste de reproches |
| Filtres « Libérable (x Go) » et « Non vérifiées » ; actions de masse chiffrées avec la raison des blocages | C | Bibliothèque | Pour libérer de l'espace et comprendre pourquoi un film ne peut pas être créé |
| Ctrl+K comme raccourci principal, F6 d'une zone à l'autre, `event.key`, raccourci affiché sur chaque bouton, pas de Ctrl+J | C (§5.9) | Partout | Conventions Windows, clavier AZERTY, pas de conflit avec les raccourcis du navigateur |
| Glisser-déposer d'un lien ; message par ligne pour un collage en lot | B | Fenêtre, dialogue d'ajout | Un geste de plus, sans rien à apprendre |
| Détection d'un autre onglet ouvert (BroadcastChannel) avec [Utiliser ici] | B | Coquille | Chrome limite à 6 connexions HTTP/1.1 par hôte, et chaque onglet garde un flux SSE |
| Points de rupture pour Windows Snap (600 à 1023 px) | B | Responsive | Fenêtre en demi-écran à côté de l'Explorateur |
| Premier lancement « au calme » ; une zone sans données reste masquée plutôt qu'affichée fausse | C | Démarrage | Confiance |
| Toasts regroupés ; pas de toast quand la vue affiche déjà l'information | B et C | Toasts | Moins de bruit |
| Ctrl+Entrée dans l'aperçu = télécharger puis créer le film | C | Dialogue d'ajout | Parité avec `--film` en un geste |

### 1.3 Idées écartées

| Idée | Origine | Pourquoi on l'écarte |
|---|---|---|
| Flux comme page d'accueil | B | Avec des jobs d'environ 1 min, l'accueil deviendrait surtout un historique. B affichait aussi deux unités (la version dans le flux, la série dans la bibliothèque). |
| Poste à 4 zones (barre latérale, inspecteur, dock) | C | Trop chargé pour un seul utilisateur, et le plus coûteux à construire en JS sans build |
| Pellicule dont les segments sont proportionnels à la durée des épisodes | B | Elle contredit le compteur (« 34/62 » peut s'afficher à 45 % ou à 60 %) et réduit un épisode de 50 s à 5 px. On garde un ruban **à segments égaux**. |
| Grille à 12 épisodes par ligne | C | Casse le repère décimal (l'épisode 28 doit être en rangée 3, colonne 8). On garde **10 par ligne partout** sur desktop et 5 sur mobile. |
| Fiche série en « mode Aperçu » pour une série non possédée | A | Elle doublait le dialogue d'ajout. Il n'y a désormais **qu'une seule surface d'aperçu** : le dialogue d'ajout, qui contient aussi le sélecteur d'épisodes. |
| Préchargement de l'aperçu d'une langue au survol de « + Espagnol » | A | Envoie des requêtes réseau non demandées. L'aperçu ne se charge qu'au clic. |
| Collage express (téléchargement lancé sans confirmation) | B | Risque de lancer 700 Mo par erreur pour un gain d'une seule interaction |
| Mini-syntaxe `fr 720p 1-10 film` dans le champ | C | Reportée en V1.1, en option pour les utilisateurs avancés |
| Page Activité plein écran sur desktop, vues enregistrées, réordonnancement de la file | C | V2 : la file ne contient qu'une série à la fois, pendant environ 1 min |
| « Garder les deux » en cas d'écrasement du film | A | Demande un ajout au moteur pour un bénéfice faible. On le remplace par une case « Remplacer » obligatoire. |
| Onglet « Search Title » à la dramafren | — | Le moteur ne sait pas chercher par titre. On ne montre pas une fonction qui ne marche pas. |
| Drapeaux pour les langues | — | Ambigus (espagnol d'Espagne ou d'Amérique latine). On écrit les noms en toutes lettres, et `in` s'affiche « Indonésien ». |

### 1.4 Points tranchés là où les juges n'étaient pas d'accord

1. **Même action principale sur la carte et dans la fiche.**
   - Une seule règle de priorité : Mettre en pause > Réparer / Réessayer > Reprendre > Compléter > Recréer le film > Créer le film > ▶ Regarder le film.
   - « ▶ Regarder » (ou « ▶ Reprendre · ép. 14 ») est **toujours** présent en bouton secondaire à côté. Regarder reste donc à 1 interaction partout.
2. **Raccourcis à une touche.**
   - Actifs par défaut, parce qu'ils sont sans coût ou réversibles : `Entrée`, `L` (lire), `O` (dossier), `P` (pause/reprendre), `Espace` (cocher), `Suppr` (ouvre le dialogue, ne supprime rien directement), `T` (activité), `?`.
   - Désactivés par défaut, dans le réglage « Raccourcis d'action rapide » : `R` (réessayer), `C` (compléter), `F` (film), parce qu'ils peuvent lancer des centaines de Mo.
3. **L'affiche qui se colore** ne concerne que la **première arrivée** d'une série (aucune version complète) et les séries en file. Pour une nouvelle version d'une série déjà possédée, on affiche une barre lavande et une ligne d'état. L'effet est toujours accompagné d'un texte. Un test utilisateur est à prévoir (§13).
4. **L'aperçu est un vrai `<dialog>` modal** : focus piégé, arrière-plan `inert`, Échap pour fermer en gardant le texte collé. Ce n'est pas une attente : c'est un point de décision, donc il reste compatible avec le principe « aucune modale pour attendre ».
5. **Le film enchaîné après un téléchargement est construit sur toute la version**, et non sur la seule sélection du job. C'est volontairement différent de `fetch --film -e`, qui fait un film avec les seuls épisodes demandés.

---

## 2. Principes UX directeurs

1. **Une URL, un geste.** Ctrl+V n'importe où, puis Entrée. Les valeurs par défaut sont mémorisées : qualité Meilleure (1080p), version préférée si elle existe, tous les épisodes. Les options restent repliées.
2. **La série, pas le fichier.** Série, versions, film. Dossiers, n° de série, manifest et liens signés n'apparaissent que dans « Détails techniques ».
3. **La confiance se prouve.** « Vérifié » ne s'affiche que si la durée est conforme (±1 s). Un fichier non vérifié (mode sonde) ne ressemble jamais à un fichier vérifié. « 62/62 » est visible partout.
4. **Le système répare, l'utilisateur décide.** Nouveaux essais, liens expirés et reprise se font automatiquement et sans message. On ne dérange l'utilisateur que pour une décision (film partiel, ré-encodage, suppression), et toujours avec le bouton de réparation.
5. **Calme en arrière-plan.** La progression se lit en périphérie : titre d'onglet, favicon, pilule, notification Windows. Aucune modale pour attendre et aucun changement d'écran forcé. Quand tout va bien, le mur n'affiche aucun badge.
6. **Le vertical d'abord.** Affiches 9:16, lecteur vertical, grille décimale héritée de dramafren. La place libre en paysage sert au contexte (épisodes, chapitres), pas à étirer la vidéo.
7. **Rien ne se perd.** Les suppressions passent par une corbeille interne avec [Annuler]. La reprise est idempotente. Préférences et filtres sont conservés.
8. **Parité avec la CLI, sans l'imposer.** Tout ce que font `info`, `fetch`, `links` et `film` est faisable dans l'interface. La commande équivalente peut toujours être copiée.

---

## 3. Jeu de données de référence (maquette)

**Instantané commun à tous les écrans : samedi 26 septembre 2026, 19:05.** Débit mesuré : 9,7 Mo/s. Disque : 182 Go libres sur C:. Dossier : `C:\Users\…\Videos\ShortDramaGen`. Préférences : « Français si disponible, sinon VO », Meilleure (1080p), 3 téléchargements simultanés.

Le titre affiché est celui de la langue préférée quand le catalogue le connaît (titre localisé du site officiel), sinon celui de la VO.

| # | Titre affiché | Titre VO | n° de série | Versions possédées | Épisodes | Durée | Taille des épisodes | Film | État de la carte |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Qui Est la Véritable Mme Lafont ?** (réel) | One Night to Forever | 41000105199 | VO (anglais) 62/62 ✓ · VF 59/62 (vidéos 41000111625) | 62 | 1 h 32 | VO 702 Mo · VF 649 Mo | VO : prêt, 717 Mo, 62 chapitres | « ! VF · 3 à réparer » → [Réparer VF · 3] |
| 2 | La Revanche de l'héritière | The Heiress Strikes Back | 41000123401 | VO 21/80, **en cours** | 80 | 1 h 58 | 231 Mo / ≈ 880 Mo | — | Affiche colorée à 26 %, « ↓ 21/80 · ≈ 1 min 10 s » |
| 3 | Ma femme de substitution | My Substitute Wife | 41000125590 | VO 0/60, **en file (1er)** | 60 | 1 h 29 | ≈ 660 Mo | — | Affiche désaturée, « En file · 1er » |
| 4 | Série 41000999999 (mode sonde) | — | 41000999999 | VO 34/48, **interrompu** hier à 23:14 | 48 | inconnue | 370 Mo (+ 12 Mo en .part) | — | Affiche générée, « ‖ Interrompu · 34/48 », badge « Non vérifiée » |
| 5 | Le Contrat d'un an | One-Year Contract | 41000118822 | VO 58/62 (4 nouveaux épisodes : 59 à 62) | 62 | 1 h 35 | 660 Mo | — | « ◐ 58/62 · 4 manquants » |
| 6 | Mariée par erreur au PDG | Wrong Bride for the CEO | 41000097310 | VO 71/71 ✓ | 71 | 1 h 46 | 790 Mo | prêt, 805 Mo | nominal |
| 7 | L'Héritier caché | The Hidden Heir | 41000110457 | VO 64/64 ✓ · VF 64/64 ✓ | 64 | 1 h 36 | 712 + 709 Mo | VF : prêt, 725 Mo | nominal |
| 8 | Le Milliardaire amnésique | The Amnesiac Billionaire | 41000101268 | VO ✓ | 66 | 1 h 38 | 729 Mo | prêt, 745 Mo | nominal |
| 9 | Trois ans de silence | Three Years of Silence | 41000099843 | VO ✓ | 58 | 1 h 27 | 647 Mo | prêt, 660 Mo | nominal |
| 10 | La Fiancée du tigre | The Tiger's Fiancée | 41000108716 | VO ✓ | 70 | 1 h 44 | 774 Mo | prêt, 790 Mo | nominal |
| 11 | Le Dernier Rendez-vous | The Last Date | 41000103935 | VO ✓ | 63 | 1 h 33 | 692 Mo | prêt, 705 Mo | nominal |
| 12 | Le Pacte de minuit | The Midnight Pact | 41000112077 | VO ✓ | 68 | 1 h 41 | 751 Mo | prêt, 765 Mo | nominal |

**Totaux**
- 12 séries, 14 versions, **14,3 Go** (épisodes 8,4 Go + films 5,9 Go).
- **Libérable** (épisodes déjà fusionnés dans un film complet) : **5,8 Go**.
- Compteurs de filtres : Toutes 12 · En cours 1 · En file 1 · À compléter 1 · Avec échecs 1 · Interrompues 1 · Film prêt 8 · Sans film 4 · Non vérifiées 1 · Libérable 5,8 Go. Versions : VO 12 · VF 2.

**VF de la série n° 1** (sert à la fiche, au film et au lecteur)

| Épisodes | Statut | Détail |
|---|---|---|
| 1-2, 4-11, 13-39, 42-62 | Téléchargés et vérifiés, 1080p | ép. 1 : 2 min 33, 21,2 Mo ; ép. 14 : 2 min 05, 13,2 Mo |
| 3 | **Fichier manquant** | E003.mp4 supprimé dans l'Explorateur |
| 12 | Vérifié, en **720p** | 1 min 31, 7,3 Mo ; le 1080p n'était pas disponible |
| 40 | **Indisponible à la source** | 1 min 19 ; `Episode unavailable` |
| 41 | **Échec de vérification** | « 1 min 12 au lieu de 1 min 28 » ; brut : `dramafren 1080p : durée 72,3 s au lieu de 88,4 s (mauvais fichier ?)` |

Job terminé à 18:52 : 60/62, 1 min 41 s. Le fichier E003 a été supprimé ensuite.

**Job actif `j-7f3a2c`** (série n° 2)
- Démarré à 19:04:58. 21/80 vérifiés, épisodes 22, 23 et 24 en cours (64 %, 31 %, 8 %).
- 231 Mo sur ≈ 880 Mo, 9,7 Mo/s, ≈ 1 min 10 s restantes.
- Titre d'onglet : « (21/80) ShortDramaGen ».
- Pilule : « ↓ 21/80 · ≈ 1 min 10 s · +1 en file ».

**Historique récent**
- 18:52 : VF de la série n° 1, « Terminé avec 2 problèmes (40, 41) », 1 min 41 s.
- Mercredi : VO de la série n° 1, 62/62 vérifiés, 702 Mo, 1 min 38 s.
- Mercredi : film « One Night to Forever.mp4 », 1 h 32, 717 Mo, 6 s.

**Estimations d'aperçu** (VE « Una Noche Para Siempre », non possédée)
- Qualités : Meilleure (1080p) ≈ 690 Mo · 720p ≈ 380 Mo (estimation) · 540p ≈ 230 Mo (estimation).
- Durée : ≈ 1 min 10 s de téléchargement. Démarrage estimé après la file : ≈ 2 min 15 s.
- Synopsis : utiliser un texte neutre d'environ 400 caractères. Ne pas inventer d'intrigue.

---

## 4. Architecture de l'information et navigation

### 4.1 Arborescence et routes (routeur par hash)

```
ShortDramaGen (sdg ui → http://127.0.0.1:8765)
├── En-tête permanent : logo · champ « Chercher ou coller » (Ctrl K) · [+ Ajouter] · pilule/icône Activité (T) · Réglages (pastille santé)
├── #/                         Bibliothèque (accueil)   ?f=<filtre>&v=<vo|fr|…>&tri=<…>&vue=<affiches|liste>&q=<texte>
│   ├── Bandeau conditionnel (1 au plus)
│   ├── Barre de titre : stats · tri · vue
│   ├── Puces de filtre
│   ├── Étagère « À traiter » (si non vide et sans filtre ni recherche)
│   ├── [V1.1] Étagère « Continuer à regarder »
│   └── Mur d'affiches | Liste dense  (+ sélection multiple → barre d'actions)
├── #/serie/<bookId>/<vo|fr|es…>   Fiche série
│   ├── Héros (cover, titres, méta, synopsis) + onglets de version (+ langue)
│   ├── Barre de santé + action principale
│   ├── Colonne principale : Épisodes · Film · Stockage · Détails techniques
│   └── Volet contextuel (épisode ou sélection)
├── #/serie/<bookId>/<v>/lire/<n|film>   Théâtre (surcouche plein écran)
├── #/activite     Tiroir Activité sur desktop (la route ouvre le tiroir) ; page sur mobile
└── #/reglages/<general|telechargement|film|stockage|affichage|clavier|sante|apropos>

Couches : dialogue d'ajout (#/…?ajout=<url encodée>) · dialogue Supprimer · menu ⋯ · aide des raccourcis (?) · toasts
```

- **Profondeur maximale : 2 niveaux** (Bibliothèque → Fiche), plus le Théâtre en surcouche.
- Le bouton Retour du navigateur restaure les filtres, le tri, la vue et la position de défilement.

### 4.2 Vocabulaire (terme du moteur → terme affiché)

| Moteur | Interface |
|---|---|
| groupe de dossiers de même `book_id` | **Série** (une carte) |
| dossier `<bookId>-<slug>[-<lang>]` + manifest | **Version** : « VO (anglais) », « VF », « VE » ; nom complet au survol |
| `E014.mp4` | **Épisode 14** (tuile « 14 ») ; « E014 » seulement dans l'infobulle et les détails |
| `pending` sélectionné, sans job | **À télécharger** |
| `pending` hors de la sélection demandée | **Non demandé** |
| `pending` pendant un job actif | **En file** |
| `downloading` avec job | **En cours · 45 %** |
| `downloading` sans job, ou `.part` présent | **Interrompu · 40 %** |
| `done` avec durée vérifiée | **Téléchargé et vérifié** |
| `done` en mode sonde | **Téléchargé · non vérifié** |
| `done` dont le fichier a disparu | **Fichier manquant** |
| `failed` avec `error_code=ep_unavailable` | **Indisponible à la source** |
| `failed` pour une autre cause | **Échec** + raison courte |
| `removed` | **Retiré (film conservé)** |
| `film` | **Film** · `--allow-missing` = **Film partiel** · `--reencode` = **Ré-encoder (plus lent)** |
| `-q best` / `-j 3` | **Meilleure (1080p)** / **Téléchargements simultanés : 3** |
| CDN, Range, URL signée, dramafren | « la source » ; le reste uniquement dans « Détails techniques » |

**Statut d'une version** : un seul badge, par priorité **En cours > En file > Interrompu > Avec échecs > À compléter > Complète**. Complète n'a pas de badge. Film prêt, Film partiel et Film obsolète s'y ajoutent.

**Statut d'une série** (la carte) : celui de sa version la plus urgente, préfixé par la version dès que la série en a plus d'une (« ! VF · 3 à réparer »).

### 4.3 Navigation

| | Desktop ≥ 1366 (cible 1440) | Laptop 1024-1365 | Snap 600-1023 | Mobile < 600 (cible 390) |
|---|---|---|---|---|
| Principale | En-tête de 64 px ; pas de barre latérale (3 destinations seulement) | Idem | Idem, champ réduit à 320 px, libellé « + » seul | Barre d'app de 56 px + **barre du bas** : Bibliothèque · Ajouter · Activité · Réglages |
| Activité | Tiroir de 400 px à droite, épinglable | Tiroir en surimpression | Tiroir en surimpression | Page `#/activite` + mini-barre au-dessus de la barre du bas |
| Retour depuis la fiche | « ← Bibliothèque » | Idem | Idem | Flèche dans la barre d'app |
| Gouttières | 32 px | 24 px | 24 px | 16 px |

### 4.4 Clavier (Windows, AZERTY compatible)

Les raccourcis lisent `event.key`. Aucun ⌘ n'est affiché. Les raccourcis à une touche sont inactifs dans les champs et peuvent être désactivés (WCAG 2.1.4).

| Portée | Touche | Action |
|---|---|---|
| Global | **Ctrl+K** | Focus du champ « Chercher ou coller » avec ses commandes. `/` marche aussi (QWERTY, pavé numérique). |
| Global, hors champ | **Ctrl+V** | Ouvre le dialogue d'ajout avec le lien collé (événement `paste`, sans demande d'autorisation) |
| Global | F6 / Maj+F6 | Région suivante / précédente : en-tête → contenu → volet → tiroir |
| Global | `A` · `T` · `?` · Échap | Ajouter · Activité · Aide des raccourcis · Fermer ou remonter d'un niveau |
| Mur | Flèches · Début/Fin · Entrée · Espace · Maj+flèches · Ctrl+A | Naviguer (grille ARIA) · ouvrir la fiche · cocher · étendre · tout cocher dans le résultat filtré |
| Carte ou fiche ciblée | `L` · `O` · `P` · `Suppr` · Maj+F10 | Lire · Dossier · Pause ou reprise · Dialogue Supprimer · Menu |
| Idem, si le réglage est activé | `R` · `C` · `F` | Réessayer · Compléter · Créer le film |
| Dialogue d'ajout | Entrée · Ctrl+Entrée · ←/→ sur les puces | Télécharger · Télécharger puis créer le film · Changer de version |
| Grille d'épisodes | Flèches · Début/Fin · Entrée · Espace · Maj+flèches | Déplacer · action de la tuile · sélectionner · étendre |
| Théâtre | Espace/K · ←/→ · Maj+←/→ · F · M · Échap | Lecture · ±5 s · épisode ou chapitre · plein écran · muet · fermer |

Chaque bouton qui a un raccourci l'affiche dans son infobulle, avec un `kbd` de 12 px.

---

## 5. Écrans

Chaque écran suit le même plan : **But · Mise en page · Contenu · Actions · États · Microcopy**. Les dimensions sont données pour 1440 × 900 sauf mention contraire.

### E0. Coquille

- **But.** Garder l'ajout et l'activité à un seul geste, depuis n'importe quel écran.
- **Mise en page**, de haut en bas :
  1. **En-tête collant de 64 px**, fond `bg`, filet bas `border-subtle`. De gauche à droite, gouttière de 32 px :
     - logo (pictogramme de 24 px + « ShortDramaGen » en 16/600) ;
     - 40 px d'espace ;
     - **champ « Chercher ou coller »** de 560 × 40 ;
     - 12 px, puis bouton **[+ Ajouter]** (secondaire, 40) ;
     - aligné à droite : **pilule Activité** (32 de haut) ou icône Activité (40 × 40) ;
     - 8 px, puis icône **Réglages** (40 × 40) avec une pastille de santé de 8 px.
  2. **Zone de bandeau** (48 px minimum, pleine largeur, un bandeau au plus), par priorité : moteur injoignable > disque plein > reprise au démarrage > hors ligne.
  3. **Contenu.**
  4. **Toasts** en bas à gauche, à 24 px du bord, 360 de large, 3 empilés au maximum.
  5. **Tiroir Activité** à droite : 400 px, sous l'en-tête. Il n'assombrit pas la page et peut être épinglé (le contenu se décale alors de 400 px).
  6. **Une seule région `role="status"`** pour les annonces aux lecteurs d'écran.
- **Pilule Activité (états)**

| État | Rendu |
|---|---|
| Au repos | Icône Activité grise (40 × 40), sans texte |
| Téléchargement | Pilule : anneau lavande de 16 px + « ↓ 21/80 · ≈ 1 min 10 s · +1 en file » |
| Création de film | « Film · 38/62 · ≈ 3 s » |
| Mise en pause ou annulation | « Mise en pause… » / « Annulation… » (jusqu'à 30-45 s si le réseau est bloqué) |
| Terminé | « ✓ Terminé · 80/80 » pendant 5 s, puis retour à l'icône |
| Échecs non traités | Pastille rouge de 8 px sur l'icône ; titre d'onglet « (2 échecs) ShortDramaGen » |
| Hors ligne | « En pause · hors ligne » en ambre |

- **Signaux périphériques**
  - Titre d'onglet : « (21/80) ShortDramaGen », puis « Terminé · ShortDramaGen » pendant 5 s.
  - Favicon avec un anneau de progression.
  - Notification Windows **une fois par série**, seulement si l'onglet est masqué. La permission est demandée au **premier** téléchargement terminé.
- **États**

| État | Rendu et texte |
|---|---|
| Démarrage | Barre fine de 2 px sous l'en-tête (statique si reduced-motion) · « Lecture de ta bibliothèque… 9 séries trouvées » |
| Moteur injoignable | Bandeau danger, `role="alert"`. Toute l'interface passe en lecture seule avec le dernier état connu, et on retente toutes les 5 s. « Le moteur ne répond plus. Tes téléchargements sont peut-être arrêtés. On essaie de se reconnecter… » [Réessayer maintenant] · aide : « Si tu as fermé la fenêtre du moteur, relance ShortDramaGen. » |
| Hors ligne (mesuré par le moteur) | Bandeau info : « Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls. » · au retour, toast « De retour en ligne. Reprise des téléchargements. » |
| Disque plein | Bandeau danger : « Téléchargements arrêtés : il manque 312 Mo sur C:. Libère de la place puis reprends. » [Voir le stockage] [Reprendre] |
| Reprise au démarrage (reprise automatique activée) | Bandeau info : « Reprise de 2 téléchargements interrompus (34/48 et 0/60). » [Mettre en pause] [Voir] |
| Reprise au démarrage (reprise automatique désactivée) | « 2 téléchargements ont été interrompus (34/48 et 0/60). » [Tout reprendre] [Voir] · case « Reprendre automatiquement la prochaine fois » |
| Autre onglet ouvert | Bandeau info : « ShortDramaGen est déjà ouvert dans un autre onglet. » [Utiliser ici] |

### E1. Bibliothèque (accueil) : route `#/`

- **But.** Voir toute la collection, repérer ce qui demande de l'attention et agir depuis la carte.
- **Mise en page** (contenu sur 1376 px, gouttières de 32 px) :
  1. **Barre de titre, 56 px.** À gauche :
     - H1 « Bibliothèque » (24/32, 600) ;
     - 16 px, puis les stats en 13/18 texte secondaire : « 12 séries · 14 versions · 14,3 Go · 182 Go libres sur C: ».
     
     À droite : sélecteur « Tri : Activité récente ▾ » (40), 8 px, segmenté [Affiches | Liste] (32).
  2. **Puces de filtre, 40 px** (hauteur 32, espacement 8, défilement horizontal si ça déborde) : Toutes 12 · En cours 1 · En file 1 · À compléter 1 · Avec échecs 1 · Interrompues 1 · Film prêt 8 · Sans film 4 · Non vérifiées 1 · Libérable 5,8 Go · séparateur de 1 px · VO 12 · VF 2.
     - Les puces à 0 sont masquées.
     - Quand un filtre est actif : « 3 séries sur 12 » et [Effacer les filtres].
  3. **Étagère « À traiter »**, 24 px sous les puces :
     - titre « À traiter · 3 » (16/24, 600) ;
     - à droite, bouton secondaire **[Tout réparer · 2 séries]** ;
     - une rangée de **cartes compactes** de 344 × 104, espacées de 16.
  4. **Mur**, 32 px dessous : `repeat(auto-fill, minmax(164px, 1fr))` avec un espacement de 20, soit **7 colonnes de 180 px**.
  5. **Marge basse de 96 px**, pour que les toasts et la barre de sélection ne masquent jamais le dernier rang.
- **Ordre du mur (tri Activité récente)** : 2 La Revanche (en cours) · 3 Ma femme de substitution (en file) · 1 Qui Est la Véritable Mme Lafont ? · 4 Série 41000999999 · 5 Le Contrat d'un an · puis 6 à 12.
- **Anatomie d'une carte** (180 de large) :
  - **Cover 180 × 320**, rayon 10, `alt=""` (le titre est juste en dessous).
  - **Bande d'état** en bas de la cover (72 px, voile plein `rgba(11,18,32,.85)`, sans dégradé), **seulement si l'état n'est pas nominal** :
    - ligne d'état en 12/16 ;
    - jusqu'à 2 badges (versions « VO · VF », « Film ») ; au-delà, « +1 ».
  - Si la carte est nominale, seuls les badges s'affichent, dans le coin bas-gauche, sur un voile de 32 px.
  - **Sous la cover**, 8 px :
    - **ruban** (6 px, seulement si une version est incomplète) ;
    - titre en 14/18 600 sur 2 lignes (titre complet en infobulle), attribut `lang` ;
    - méta en 12/16 texte secondaire : « 62 ép. · 1 h 32 » ou « 58/62 ép. · 4 manquants ».
  - **Au survol et au focus** (jamais uniquement au survol) :
    - case à cocher de 24 dans le coin haut-gauche ;
    - bouton ⋯ de 32 dans le coin haut-droit ;
    - en bas de la cover, par-dessus la bande : **action principale** (bouton 32, pleine largeur moins 44) + bouton ▶ de 32.
  - **Coloration (première arrivée)** : deux couches, la cover en niveaux de gris assombrie à 60 % et la cover en couleur découpée par `clip-path: inset(calc((1 - var(--p)) * 100%) 0 0 0)`, avec `--p` = épisodes vérifiés / épisodes demandés. Une série en file est entièrement grise (`--p: 0`).

- **Contenu des cartes à 19:05**

| Carte | Bande d'état | Action principale | ▶ secondaire |
|---|---|---|---|
| La Revanche de l'héritière | « ↓ 21/80 · ≈ 1 min 10 s » | [Mettre en pause] | [▶ Ép. 1] |
| Ma femme de substitution | « En file · 1er » | [Mettre en pause] | — |
| Qui Est la Véritable Mme Lafont ? | « ! VF · 3 à réparer » + badges « VO · VF » « Film » | [Réparer VF · 3] | [▶ Regarder le film] |
| Série 41000999999 | « ‖ Interrompu · 34/48 » + « Non vérifiée » | [Reprendre] | [▶ Ép. 1] |
| Le Contrat d'un an | « ◐ 58/62 · 4 manquants » | [Compléter · 4] | [▶ Regarder] |
| 6 à 12 (nominales) | badges seulement (« VO », « Film », « VO · VF ») | [▶ Regarder le film] (ou [Créer le film]) | — |

- **Menu ⋯ d'une carte** : Ouvrir la fiche · Regarder · Créer le film · Ajouter une version › · Ouvrir le dossier · Vérifier les nouveaux épisodes · Copier la commande · Supprimer…
- **Carte compacte « À traiter »** (344 × 104, fond surface-1, rayon 10, filet `border-subtle`) :
  - cover de 48 × 85 ;
  - titre sur 1 ligne (14/20, 600) ;
  - problème en 13/18 ;
  - bouton sm en bas à droite ;
  - ⋯ (Ignorer · Voir la fiche).

  | Carte | Problème | Bouton |
  |---|---|---|
  | Qui Est la Véritable Mme Lafont ? · VF | « 1 échec · 1 indisponible · 1 fichier manquant » | [Réparer · 3] |
  | Série 41000999999 | « Interrompu hier à 23:14 · 34/48 » | [Reprendre · 14] |
  | Le Contrat d'un an · VO | « 4 nouveaux épisodes (59 à 62) » | [Compléter · 4] |

- **[Tout réparer]** n'enchaîne que des actions sûres : réessayer les échecs et les indisponibles, reprendre les interrompus, retélécharger les fichiers manquants. Il n'inclut **ni Compléter ni Harmoniser**.
  - Un popover de confirmation s'ouvre sous le bouton : « Réessayer 3 épisodes (VF de Qui Est la Véritable Mme Lafont ?) et reprendre 1 téléchargement (Série 41000999999) · ≈ 190 Mo. » [Tout réparer] [Annuler].
- **Vue Liste**
  - Lignes de 56 px, colonnes triables : Affiche 32 × 57 · Titre (titre VO en gris dessous) · Versions · Épisodes (x/y + ruban de 80 px) · Durée · Taille · Film · Qualité · Modifiée · État.
  - Navigation aux flèches (`role="grid"`).
- **Sélection multiple**
  - Case à cocher, Maj+clic, Ctrl+A.
  - Une barre flottante s'affiche en bas au centre (56 px, 880 de large, fond surface-2) : « 3 séries · 2,1 Go » · [Compléter] [Réessayer les échecs] [Créer les films · 1 possible · 2 bloqués] [Libérer l'espace (garder les films) · 1,4 Go] [Supprimer…] [×].
  - Le libellé « bloqués » est suivi d'un lien « pourquoi ? » qui ouvre un popover avec la raison par série.
- **États**

| État | Rendu et texte |
|---|---|
| Vide (premier lancement) | Voir E9 |
| Chargement | Affiches squelettes 9:16 en aplat surface-2, pulsation d'opacité (aucune si reduced-motion), et « Lecture de ta bibliothèque… » |
| Partiel | Bandeau info : « 2 dossiers n'ont pas pu être lus et sont masqués. » [Voir lesquels] (manifest corrompu, renvoie vers À traiter) |
| Erreur | Au centre : « Impossible d'ouvrir ton dossier de séries (C:\Users\…\Videos\ShortDramaGen). Il a peut-être été déplacé, ou le disque est débranché. » [Choisir un autre dossier] [Réessayer] |
| Filtre sans résultat | « Aucune série « À compléter · VF ». » [Effacer les filtres] |
| Hors ligne | Identique (covers en cache local). Les actions réseau restent affichées mais sont désactivées, avec la raison : « Au retour de la connexion » |
| Changement sur le disque | Relecture au retour du focus (ETag). Toast discret : « Mis à jour depuis le disque : 1 série ajoutée. » |

### E2. Champ « Chercher ou coller » et dialogue d'ajout

**Champ de l'en-tête** : 560 × 40, fond surface-1, bord `border-subtle`, icône loupe de 16, `kbd` « Ctrl K ».
- Placeholder : « Chercher une série ou coller un lien DramaBox ».
- La détection est locale et instantanée (mêmes règles que `inputs.py`) :

| Saisie | Mode | Comportement |
|---|---|---|
| Texte libre | Recherche | Liste déroulante (`role="combobox"`) sous le champ, 560 de large. Section « Dans ta bibliothèque » (5 séries au plus, terme surligné, « trouvé dans le titre VF »), puis section « Actions » (3 au plus, filtrées). Le mur filtre en direct derrière. |
| Lien ou n° de 8 à 14 chiffres | Lien | Puce dans le champ : « Lien DramaBox · série 41000105199 · ES ». Entrée ouvre le dialogue d'ajout ; un collage l'ouvre directement. Si le n° est déjà possédé, la liste propose d'abord « Ouvrir Qui Est la Véritable Mme Lafont ? », puis « Aperçu et ajout ». |
| Plusieurs lignes | Lot | « 3 liens reconnus sur 4 », puis dialogue en mode lot |
| Lien d'un autre site | Erreur | Bord danger, texte conservé, partie fautive soulignée. « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199). » |
| Aucun résultat | — | « Aucune série « xyz » dans ta bibliothèque. La recherche par titre sur DramaBox n'existe pas encore : colle le lien de la série. » |

- **Actions de la liste** : Tout réparer (2) · Tout reprendre · Tout mettre en pause · Créer le film de… · Ouvrir le dossier de la bibliothèque · Réglages · Raccourcis clavier.

**Dialogue d'ajout** : `<dialog>` modal de 760 px, à 88 px du haut, hauteur maximale de 100vh − 120 (défile à l'intérieur), rayon 14, fond surface-1, ombre e2, voile `rgba(5,8,15,.6)`.

- **Mise en page** (marges internes de 24) :
  1. **En-tête, 56 px** : titre « Ajouter une série » (20/28, 600) · bouton × de 40.
  2. **Champ du dialogue** (pleine largeur, 40), prérempli avec le lien et sa puce de détection, pour pouvoir le corriger sans fermer.
  3. **Bloc aperçu** (espacement de 24) :
     - **à gauche** : cover de 150 × 267 ;
     - **à droite** : titre dans la version choisie (22/28, 600, `lang`), titre VO en 14/20 secondaire (« One Night to Forever · titre original ») ;
     - méta : « 62 épisodes · 1 h 32 · épisodes de 50 s à 3 min 30 » ;
     - synopsis en 14/20 sur 3 lignes, lien [Lire plus] ;
     - pastille « ● Source disponible · 1080p, 720p, 540p ».
  4. **Encart « déjà possédée »** (fond info-subtle, 14/20), si besoin : « Déjà dans ta bibliothèque : VO complète (62/62) · VF 59/62. Cette version sera ajoutée à la même série. »
  5. **Versions** (puces radio de 36 px) :
     - `VO · anglais ✓` · `Français · 59/62` · `● Espagnol` ;
     - ligne d'aide : « Coréen, thaï, indonésien, japonais : titre traduit seulement ». Tant que le catalogue n'a pas répondu, ces langues sont en état « vérification… » et ne peuvent pas être choisies.
  6. **Réglages résumés**, sur une ligne cliquable : « Meilleure (1080p) · tous les épisodes · sans film » [Modifier ▾]. Déplié :
     - Qualité (select de 40, taille par option) ;
     - Épisodes : radio Tous · Seulement les manquants (si la version existe) · Choisir… (ouvre le **sélecteur de plages intégré**, §7.7, 10 tuiles de 44 × 36 par ligne) ;
     - case « Créer le film à la fin » ;
     - dossier en lecture seule (« Modifiable dans les Réglages ») ;
     - [Copier la commande] `sdg fetch 41000105199 --lang es -q 1080p`.
  7. **Coût** en 14/20 tabulaire : « ≈ 690 Mo · ≈ 1 min 10 s · 182 Go libres sur C: · démarre après 2 séries (≈ 2 min 15 s) ».
  8. **Pied** :
     - bouton principal lg **[Télécharger la VE · 62 épisodes]**, focalisé dès que l'aperçu est prêt, avec l'indice « Entrée » ;
     - bouton secondaire [Choisir les épisodes] ;
     - case « Créer le film à la fin », avec l'indice « Ctrl+Entrée ».

- **Libellé du bouton principal selon le cas**

| Cas | Bouton principal | Secondaire |
|---|---|---|
| Série nouvelle | Tout télécharger · 62 épisodes | Choisir les épisodes |
| Nouvelle version d'une série possédée | Télécharger la VE · 62 épisodes | Ouvrir la fiche |
| Version possédée, avec problèmes | Réparer la VF · 3 épisodes | Ouvrir la fiche |
| Version possédée et complète | Ouvrir la fiche | ▶ Regarder le film |
| Version incomplète | Compléter · 4 manquants | Ouvrir la fiche |
| Déjà en file ou en cours | Voir dans l'activité | — |
| Sélection partielle | Télécharger 23 épisodes · ≈ 270 Mo | Tous |
| Mode sonde | Télécharger les épisodes trouvés | — |
| Disque insuffisant | Désactivé, avec « Il manque ≈ 310 Mo sur C: » | [Voir le stockage] |

- **Après le lancement**
  - Le dialogue se ferme ; le focus revient sur le champ de l'en-tête, **vidé**, pour enchaîner un autre lien.
  - La carte apparaît dans le mur, grise (« En file · 2e ») ; la pilule affiche « +2 en file ».
  - Toast : « Ajouté à la file · Una Noche Para Siempre (VE) · 2e » [Voir].
- **États**

| État | Rendu et texte |
|---|---|
| Chargement | Squelette (affiche, 3 lignes, bouton inactif) · « Lien reconnu. Recherche de la série… » ; au-delà de 4 s : « Le site officiel met du temps à répondre… » |
| Lien d'épisode | « C'est le lien de l'épisode 14 : on te propose toute la série. » + lien [Seulement l'épisode 14] |
| Mode sonde | Affiche générée « Série 41000999999 » + étiquette info **« Infos limitées »** : « Cette série n'est pas sur le site officiel : titre, durées et cover indisponibles. Les épisodes seront détectés pendant le téléchargement, sans contrôle de durée. » |
| Source en panne | Pastille danger : « La source ne répond pas pour cette série : le téléchargement risque d'échouer. » (le bouton reste actif) |
| Introuvable | « On n'a trouvé cette série ni sur le site officiel ni à la source. Vérifie le lien ou essaie avec le n° de série (11 chiffres). » |
| Réseau | « Impossible de joindre DramaBox. Vérifie ta connexion. » [Réessayer] |
| Hors ligne | « Tu es hors ligne : l'aperçu a besoin d'Internet. » [Garder le lien pour plus tard] (le lien part dans l'activité, « En attente de connexion ») |
| Lot | Liste de lignes de 64 px (cover 36 × 64, titre, épisodes, taille, case cochée). Ligne invalide : « La ligne 2 n'est pas un lien DramaBox. » (décochée). Séries déjà complètes décochées. Bouton : [Tout télécharger · 3 séries · ≈ 2,1 Go] |

### E3. Fiche série : route `#/serie/41000105199/fr`

- **But.** Comprendre et agir sur une série : ses versions, ses épisodes, son film, ses fichiers.
- **Mise en page** (1440 de large, 1600 de haut, contenu sur 1376 px) :
  1. **Lien retour, 40 px** : « ← Bibliothèque » (restaure les filtres et le défilement).
  2. **Héros, 491 px**, rayon 14 :
     - fond : la même cover floutée (flou de 40 px) sous un voile plein `bg` à 80 %, sans dégradé ;
     - marges de 32 ;
     - **cover nette de 240 × 427** à gauche ;
     - colonne d'infos de 32 px, avec :
       - surtitre « Série · 2 versions » (12/16, 500, texte tertiaire) ;
       - **H1** « Qui Est la Véritable Mme Lafont ? » (28/36, 600, `lang="fr"`) ;
       - titre VO « One Night to Forever · titre original » (16/24, secondaire) ;
       - méta : « 62 épisodes · 1 h 32 · 649 Mo · 1080p (1 ép. en 720p) » ;
       - synopsis en 16/24 sur 3 lignes, [Lire plus] ;
       - en bas du héros, **onglets de version** (44 px) : `VO (anglais) ✓ 62/62` · `Français · 59/62 !` (actif, souligné de 2 px accent) · `+ Espagnol` · `+ Autres ▾`. « + Espagnol » ouvre le dialogue d'ajout en espagnol.
  3. **Barre de santé**, 24 px dessous, 72 px de haut, fond surface-1, rayon 10, marges de 16/20 :
     - icône d'état de 20 ;
     - phrase-bilan en 14/20 : « 59/62 présents · 1 échec (41) · 1 indisponible (40) · 1 fichier manquant (3) · 1 épisode en 720p (12) » ;
     - à droite : **[Réparer · 3 épisodes]** (principal, 40) · [▶ Regarder] (secondaire) · [Dossier] (fantôme) · ⋯ (Vérifier les nouveaux épisodes · Retélécharger la version dans une autre qualité · Copier la commande · Copier les liens pour aria2c/IDM · Supprimer…).
  4. **Deux colonnes**, 32 px dessous :
     - **colonne principale de 984 px** : Épisodes · Film · Stockage · Détails techniques ;
     - **volet contextuel de 360 px**, collant à 88 px du haut.

- **Action principale selon l'état** (même règle que sur la carte)

| État | Phrase-bilan | Action principale |
|---|---|---|
| En cours | « Téléchargement · 21/80 · ≈ 1 min 10 s » | Mettre en pause |
| En file | « En file · démarre après La Revanche de l'héritière » | Mettre en pause |
| Échecs, indisponibles ou manquants | « 59/62 présents · … » | Réparer · n épisodes (ou « Réessayer les n épisodes » s'il n'y a que des échecs) |
| Interrompue | « Interrompu · 34/48 · reprend là où il s'était arrêté » | Reprendre |
| Incomplète | « 58/62 · 4 à télécharger (59 à 62) » | Télécharger les 4 manquants |
| Film partiel ou obsolète | « Film partiel (épisodes 1-10) · 52 épisodes ajoutés depuis » | Recréer le film complet |
| Complète, sans film | « ✓ 62/62 téléchargés et vérifiés · 1 h 32 · 702 Mo » | Créer le film |
| Complète, avec film | « ✓ 62/62 · Film prêt » | ▶ Regarder le film (ou ▶ Reprendre · ép. 14) |
| Sonde | « Durées non vérifiées : série absente du site officiel » | selon l'état |

- **Section Épisodes** (colonne principale) :
  - Titre « Épisodes » (20/28, 600).
  - **Légende-compteurs** (puces de 32, cliquables, qui sélectionnent les épisodes concernés sans filtrer la grille) : `✓ Téléchargés 59` · `! Échec 1` · `– Indisponible 1` · `? Manquant 1` · `720p 1`. Les entrées à 0 sont masquées.
  - **Outils** : Sélection : Tous · Aucun · Manquants · Échecs · Inverser, et champ « Plages » de 200 × 40 en mono (placeholder « 1-10, 28, 50- »).
  - **Grille décimale** :
    - 10 tuiles de **56 × 48** par ligne, espacement de 12 ;
    - étiquettes de rangée « 1–10 », « 11–20 »… (44 px, 12/16 tabulaire, texte tertiaire) ;
    - largeur totale 724 px ; au-delà de 100 épisodes, onglets de centaine.
  - **Barre de mode sélection**, affichée seulement quand une sélection existe : « 3 sélectionnés · ≈ 36 Mo · Échap pour quitter ». Tant qu'elle est affichée, le clic coche.
- **Clic sur une tuile** (hors sélection) :

| Tuile | Effet |
|---|---|
| Téléchargée | Ouvre le Théâtre |
| Échec, indisponible, manquante, à télécharger ou interrompue | Affiche son détail et son action dans le volet |
| En cours | Volet : progression, qualité, « reprise à 64 % » |

  Clic droit, touche Menu ou Maj+F10 : Regarder · Réessayer · Retélécharger en… › · Afficher dans le dossier · Supprimer le fichier.

- **Volet contextuel (360 px, fond surface-1, rayon 10, marges de 20)**
  - **Par défaut** : « Résumé de la VF » : 59/62 présents, 649 Mo, qualité 1080p (1 × 720p), source principale « dramafren », dernier téléchargement « aujourd'hui à 18:52 », aide « Clique sur un épisode pour voir son détail ».
  - **Épisode 41** : « Épisode 41 · 1 min 28 · Échec » · « Le fichier reçu ne correspond pas : 1 min 12 au lieu de 1 min 28. Il a été écarté. » · [Réessayer] · ▸ Détails techniques (message brut copiable, sans URL).
  - **Épisode 40** : « Cet épisode n'est pas disponible à la source pour le moment. On ne réessaie pas en boucle. » · [Réessayer maintenant].
  - **Épisode 3** : « Le fichier E003.mp4 n'est plus dans le dossier (supprimé en dehors de l'appli ?). » · [Retélécharger].
  - **Épisode 12** : « Téléchargé et vérifié en 720p : le 1080p n'était pas disponible. Le reste de la série est en 1080p. » · [▶ Regarder] · [Retélécharger en 1080p].
  - **Épisode 14** : « Téléchargé et vérifié · 2 min 05 · 1080p · 13,2 Mo » · [▶ Regarder] · [Afficher dans le dossier].
  - **Sélection** : « 3 épisodes · ≈ 36 Mo » · [Réessayer] · [Retélécharger en ▾] · [Supprimer ces fichiers].
- **Section Stockage** :
  - « Épisodes 649 Mo · Film — · Fichiers partiels 0 Mo » ;
  - chemin en mono 13/20 : `C:\Users\…\Videos\ShortDramaGen\41000105199-one-night-to-forever-fr` ;
  - [Ouvrir le dossier] [Supprimer…] ;
  - quand un film complet existe : [Libérer 702 Mo (garder le film)].
- **Détails techniques** (replié) :
  - n° de série 41000105199 · n° vidéo de la version 41000111625 ;
  - origine et qualité par épisode (tableau), expiration des liens (**jamais l'URL**) ;
  - commande `sdg fetch 41000105199 --lang fr -q 1080p` [Copier] ;
  - [Copier les liens pour aria2c / IDM] · [Exporter en JSON] ;
  - journal de la dernière tâche.
- **États**

| État | Rendu et texte |
|---|---|
| Chargement | Squelettes du héros et de la grille · `role="status"` : « Chargement de la série… » |
| Vide (0 épisode) | « Aucun épisode téléchargé pour l'instant. » [Tout télécharger · 62 épisodes] |
| Dossier disparu | Bandeau danger : « Le dossier de cette version est introuvable (déplacé ou supprimé en dehors de l'appli). » [Le retrouver…] [Retélécharger] [Retirer de la bibliothèque] |
| Hors ligne | Actions réseau désactivées : « Disponible au retour de la connexion ». Regarder, Film et Dossier restent actifs. |
| Moteur injoignable | Lecture seule, dernier état connu |

### E4. Film (section de la fiche)

- **But.** Passer de 62 fichiers à un film chapitré en un clic, sans jamais tomber sur un refus sec.
- **Mise en page** : carte de 984 de large, fond surface-1, rayon 10, marges de 24.
  - Titre « Film » (20/28) + badge d'état.
  - Phrase d'état (16/24).
  - **Liste de pré-vol** : 6 lignes de 40 px (icône de 20 + libellé + détail), calculée sans réseau et sans ffmpeg (lecture des boîtes MP4).
  - Remèdes : boutons empilés, le recommandé en premier.
  - « Options du film ▸ » (replié).
- **Pré-vol, cas réel de la VF**

| Contrôle | Résultat |
|---|---|
| Épisodes | ✗ « 3 absents : 3, 40 et 41 » |
| Format | ✗ « L'épisode 12 est en 720p, les autres en 1080p » |
| ffmpeg | ✓ « prêt (via PATH) » |
| Espace | ✓ « ≈ 717 Mo nécessaires · 182 Go libres » |
| Nom | « Qui Est la Véritable Mme Lafont.mp4 » [Modifier] |
| Chapitres | ✓ « 62 chapitres « Épisode N » » |

- **Remèdes (cas réel)**
  - **[Réparer puis créer le film]**, avec le sous-titre « Réessaie 40 et 41, retélécharge 3, et 12 en 1080p · ≈ 50 Mo, puis crée le film ».
  - [Créer un film partiel] : « Qui Est la Véritable Mme Lafont (épisodes 1-2, 4-39, 42-62).mp4 ».
  - [Créer quand même (ré-encodage, plusieurs minutes)] : actif seulement si le seul blocage est le format.
- **Options du film** : Chapitres (activés) · Nom du fichier · Ré-encoder (plus lent) · Autoriser un film partiel. C'est la parité avec `sdg film`.
- **États**

| État | Texte | Actions |
|---|---|---|
| Prêt à créer | « Réunis les 62 épisodes en un seul fichier (1 h 32, un chapitre par épisode), en quelques secondes. » | **[Créer le film]** |
| Réparation en cours | « Réparation · 2/4 épisodes · puis création du film » | [Annuler] |
| Création | Progression **dans le bouton** : « Assemblage… 38/62 · ≈ 3 s », sans modale | [Annuler] |
| Prêt | « Film prêt : Qui Est la Véritable Mme Lafont.mp4 · 1 h 32 · 717 Mo · 62 chapitres » | **[▶ Regarder le film]** [Afficher dans le dossier]. Une seule fois : « Libérer 649 Mo en supprimant les épisodes ? Le film reste. » [Libérer] [Non merci] |
| Épisodes manquants (seulement) | « Il manque 2 épisodes (61 et 62). » | **[Les télécharger puis créer le film]** · [Créer un film partiel (épisodes 1-60)] |
| Formats mélangés (seulement) | « L'épisode 12 est en 720p, les autres en 1080p. Pour un film sans perte en quelques secondes, retélécharge-le en 1080p. » | **[Retélécharger l'épisode 12 en 1080p (≈ 13 Mo) puis créer]** · [Créer quand même (ré-encodage, plusieurs minutes)] |
| 1080p toujours indisponible | « Le 1080p n'est toujours pas disponible pour l'épisode 12. » | **[Créer avec ré-encodage]** · [Réessayer plus tard] |
| ffmpeg absent | « Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans. » | Encart avec `winget install Gyan.FFmpeg` et `pip install imageio-ffmpeg` ([Copier] sur chaque ligne) · [Vérifier à nouveau] |
| Un film porte déjà ce nom | Ligne de pré-vol ⚠ « Un film porte déjà ce nom (717 Mo). » + case **« Remplacer le film existant »** (obligatoire ; sinon le bouton reste désactivé avec « Coche « Remplacer » ou change le nom ») | — |
| Partiel ou obsolète | « Film partiel (épisodes 1-10). 52 épisodes ajoutés depuis. » | **[Recréer le film complet]** · l'ancien fichier est proposé à la suppression |
| Fichier disparu | « Le film n'est plus dans le dossier. » | [Recréer le film] |
| Durée incorrecte | « Le film créé n'a pas la durée attendue (1 h 29 au lieu de 1 h 32). » | [Réessayer] · Détails techniques |
| Hors bibliothèque (`-f` hors du dossier) | « Ce film a été créé en dehors du dossier de la série. » | [Ouvrir le dossier] seulement |

### E5. Activité (tiroir) : route `#/activite`

- **But.** Le détail pour qui le veut. L'essentiel est déjà visible dans la pilule et sur l'affiche.
- **Mise en page** :
  - tiroir de 400 px, de 64 px du haut jusqu'en bas, fond surface-1, filet gauche `border-subtle`, ombre e2 ;
  - en-tête de 56 px : « Activité » (16/24, 600) · [Épingler] · [×] ;
  - barre d'outils : [Tout mettre en pause] ;
  - sections avec titres en 12/16, 500, majuscules, texte tertiaire.
- **Sections (19:05)**
  1. **EN COURS**, ligne de job (marges de 16) :
     - cover de 40 × 71 · « La Revanche de l'héritière · VO » ;
     - barre de 6 px (lavande) · « 21/80 vérifiés · 231 / ≈ 880 Mo » ;
     - « 9,7 Mo/s · ≈ 1 min 10 s » ;
     - **ruban** de 80 segments (1-21 verts, 22-24 lavande, le reste en piste) ;
     - [Pause] [Annuler] [▶ Ép. 1] [Voir la fiche].
     - Phases visibles selon le cas : « Lecture des infos… », « Recherche des épisodes à la source… 23 trouvés » (sonde), « Téléchargement », « Création du film… ».
  2. **EN FILE · 1** : « Ma femme de substitution · VO · 60 ép. · ≈ 660 Mo · démarre dans ≈ 1 min 10 s » [Pause] [Retirer].
  3. **INTERROMPUS · 1** : « Série 41000999999 · 34/48 · interrompu hier à 23:14 » [Reprendre].
  4. **TERMINÉS RÉCEMMENT** [Effacer la liste (tes fichiers restent)] :
     - 18:52 : « Qui Est la Véritable Mme Lafont ? · VF · Terminé avec 2 problèmes (40, 41) · 1 min 41 s » [Réparer] ;
     - mercredi : « One Night to Forever · VO · 62/62 vérifiés · 702 Mo · 1 min 38 s » [▶ Regarder] ;
     - mercredi : « Film · One Night to Forever.mp4 · 1 h 32 · 717 Mo · 6 s » [▶ Regarder].
  5. **▸ Journal** (Plex Mono 12/16) :
     - 19:04:58 Infos officielles récupérées : 80 épisodes, version originale
     - 19:04:58 Téléchargement lancé : 80 épisodes, 1080p, 3 en parallèle
     - 19:05:01 Ép. 1 vérifié (1 min 52, 1080p, 14,1 Mo)
     - 19:05:27 Ép. 21 vérifié (1 min 31, 1080p, 11,4 Mo)
     
     [Copier]. Jamais d'URL signée.
- **Règles**
  - « Annuler » ne supprime **pas** les épisodes terminés. La confirmation se fait dans la ligne : « Arrêter ? Les 21 épisodes vérifiés restent. » avec la case « Garder les fichiers partiels pour reprendre plus tard » (cochée) · [Arrêter] [Continuer].
  - La barre ne recule jamais.
  - Le temps restant n'est publié qu'après 3 s de mesure, lissé et arrondi : « moins d'une minute », « ≈ 1 min 10 s ».
- **États**

| État | Texte |
|---|---|
| Vide | « Rien en cours. » + dernière activité · [Coller un lien] |
| Terminé avec échecs | « Terminé avec 2 problèmes (épisodes 40 et 41). » [Réparer] |
| Mise en pause / annulation | « Mise en pause… » / « Annulation… », boutons désactivés |
| En pause | « En pause par toi · 21/80 » [Reprendre] |
| Disque plein | « Arrêté : disque plein (il manque 312 Mo sur C:). Libère de la place puis reprends. » [Reprendre] |
| Hors ligne | « Hors ligne. Reprise automatique au retour de la connexion. Nouvel essai dans 12 s. » [Réessayer maintenant] ; aucun échec compté |
| Erreurs répétées | « Arrêté après plusieurs erreurs de suite. Vérifie ta connexion, puis reprends. » [Reprendre] [Détails techniques] |

### E6. Théâtre (lecteur vertical) : route `…/lire/14`

- **Mise en page**
  - Surcouche plein écran, fond `backdrop #05080F`, barre haute de 56 : titre « Qui Est la Véritable Mme Lafont ? · VF » · « Épisode 14 sur 62 » · [×] (Échap).
  - Vidéo 9:16 centrée dans la zone gauche (1080 px de large), hauteur = viewport − 56 − 72, soit **772 × 434 à 900 px de haut**.
  - Boutons [◀ Épisode 13] et [Épisode 15 ▶] (40) de part et d'autre, à 24 px de la vidéo.
  - Contrôles sous la vidéo (72 px) : lecture, barre de lecture (chapitres marqués pour le film), temps « 1:12 / 2:05 », volume, vitesse, plein écran, [Ouvrir dans le lecteur par défaut].
  - **Panneau droit de 360 px** (surface-1) :
    - « Épisodes · 14/62 » ;
    - grille de 5 colonnes de 48 × 40, espacement de 8 ;
    - états : vu (point de 4 px en bas), en cours de lecture (fond accent-subtle + bord accent), non lisible (même codage que la grille) ;
    - « Enchaînement automatique » (interrupteur, activé) ;
    - « Sous-titres non fournis par la source ».
    - Pour un film : liste « Chapitres » de « Épisode 1 » à « Épisode 62 », lignes de 36.
- **Comportements**
  - Fin d'épisode : « Épisode 15 dans 5 s » [Annuler]. Avec reduced-motion, le décompte s'affiche en texte seul.
  - Un épisode non lisible est sauté : « Épisode 40 indisponible : on passe au 42. »
  - Reprise : « Reprise à 1:12 » [Revenir au début].
  - À la fermeture, le focus revient sur la tuile d'origine.
- **États**

| État | Texte |
|---|---|
| Chargement | Cover en fond, `role="status"` : « Chargement de l'épisode 14… » |
| En cours de téléchargement | « Cet épisode est encore en téléchargement (45 %). Il sera lisible dès qu'il sera terminé. » |
| Fichier absent | « Ce fichier n'est plus dans le dossier. » [Retélécharger l'épisode] |
| Codec illisible (HEVC) | « Ton navigateur n'arrive pas à lire cette vidéo. » [Ouvrir dans le lecteur par défaut] |

### E7. Réglages et santé : route `#/reglages/general`

- **Mise en page** : navigation interne de 240 px à gauche (liens de 40), puis contenu de 720 px. Enregistrement automatique, avec « Enregistré. » affiché en ligne pendant 2 s.
- **Bloc Santé**, en tête de chaque section tant qu'un point est ✗, sinon dans la section Santé :
  - ffmpeg : « prêt · C:\ffmpeg\bin\ffmpeg.exe (via PATH) » ;
  - Dossier accessible en écriture ✓ ;
  - Espace libre : 182 Go sur C: ✓ ;
  - Site officiel joignable ✓ (vérifié à 19:04) ;
  - Source joignable ✓ ;
  - [Tout revérifier].
- **Sections**

| Section | Contenu |
|---|---|
| Général | Dossier de la bibliothèque `C:\Users\…\Videos\ShortDramaGen` [Changer] [Afficher dans l'Explorateur] · Version préférée « Français si disponible, sinon VO » · Qualité « Meilleure (1080p) » · Créer le film après chaque téléchargement (désactivé) · Reprendre automatiquement au démarrage (activé) |
| Téléchargement | Téléchargements simultanés : 3 (recommandé), curseur de 1 à 6. Au-delà de 3 : « Au-delà de 3, la source risque de te bloquer temporairement. » |
| Film | État de ffmpeg + commandes d'installation · chemin personnalisé · Chapitres par défaut (activés) |
| Stockage | Bibliothèque 14,3 Go (épisodes 8,4 Go · films 5,9 Go · fichiers partiels 12 Mo) · Libérable 5,8 Go [Voir] · [Nettoyer les fichiers partiels orphelins] · Corbeille d'annulation : 5 min |
| Affichage | Thème : Sombre / Clair / Système · Titres affichés : langue préférée / VO · Vue par défaut : Affiches |
| Clavier | Raccourcis de navigation (activés) · Raccourcis d'action rapide R, C, F (désactivés) · [Voir tous les raccourcis] |
| Notifications | Notifications Windows (activées) · Annonces pour lecteur d'écran : paliers / fin seulement / aucune |
| À propos | Version 0.2.0 · commande `sdg ui` · port 8765 · arrêt automatique après 10 min sans onglet ni téléchargement · [Ouvrir le journal du serveur] · [Quitter ShortDramaGen] (met les téléchargements en pause) |

- **Erreurs**
  - « Ce dossier n'est pas accessible en écriture. Choisis-en un autre. »
  - Pendant un job : « Tu pourras changer de dossier quand les téléchargements seront finis. »
  - « Vérification de ffmpeg… » pendant le contrôle.

### E8. Dialogues

**Supprimer…** (`<dialog>` de 520 px, focus piégé, **refusé pendant un job** : « Mets d'abord le téléchargement en pause. » [Mettre en pause])

- Titre : « Que veux-tu supprimer ? » + sous-titre « Qui Est la Véritable Mme Lafont ? (VF) ».
- Radios de 48 px :
  - ( ) Seulement le film · — (désactivé : « pas de film ») ;
  - (•) **Seulement les épisodes · 649 Mo** (présélectionné quand il y a un film ; sinon **aucune présélection**) ;
  - ( ) Tout : épisodes, film et dossier · 649 Mo ;
  - ( ) Fichiers partiels · 0 Mo (masqué s'il n'y en a pas).
- Note : « Tu pourras annuler pendant 5 minutes. »
- Boutons : [Annuler] (focus par défaut) · 8 px · [Supprimer 649 Mo] (danger). Le libellé suit le choix.
- Avant la suppression, l'interface coupe son propre lecteur.
- Toast : « Supprimé · 649 Mo libérés » [Annuler]. Il reste affiché tant qu'il a le focus ou qu'il est survolé.
- Erreur : « Impossible de supprimer E014.mp4 : il est ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. » [Réessayer]
- Partiel : « 60 fichiers supprimés sur 62. 2 sont ouverts dans un autre programme. » [Voir lesquels]
- En masse : récapitulatif chiffré « 5 séries · 3,4 Go ».

**Aide des raccourcis** (`?`) : dialogue de 640 px avec le tableau du §4.4, toujours au même endroit.

**Permission des notifications** (au premier téléchargement terminé, dans le toast) : « Te prévenir quand un téléchargement est fini, même si l'appli est en arrière-plan ? » [Oui, me prévenir] [Non merci].

### E9. Premier lancement et états vides

- **Bibliothèque vide**
  - Pas d'en-tête de stats ni de puces. Le **champ passe au centre** : 640 × 56, 20/28, **déjà focalisé**.
  - Titre (32/40, 600) : « Ta bibliothèque est vide »
  - Texte (16/24) : « Colle le lien d'une série DramaBox : on récupère tous les épisodes, vérifiés, jusqu'en 1080p. »
  - Formats acceptés en 13/18.
  - [Essayer avec un exemple] remplit l'URL de One Night to Forever **sans lancer**.
  - Carte « Réglages rapides » sur une ligne : « Dossier : C:\Users\…\Videos\ShortDramaGen [Changer] · Version préférée : Français si disponible [Changer] · Films : ffmpeg manquant [Comment l'installer ?] ».
  - Si des dossiers créés par la CLI existent : « 3 séries trouvées dans ton dossier, créées en ligne de commande. » [Les afficher] (en réalité déjà lues, puisque le mur reflète le disque).
  - Astuce : « Ctrl+V fonctionne n'importe où · Ctrl+K pour chercher · ? pour les raccourcis ».
- **Activité vide** : « Rien en cours. »
- **Recherche sans résultat** : voir E2.
- **À traiter vide** : l'étagère disparaît.

### E10. Mobile 390 (fenêtre étroite en V1, téléphone en V2)

- **Barre d'app de 56** : logo de 24 · titre de la vue (16/24, 600) · icônes Rechercher (44) et Filtres (44).
- **Barre du bas** : 64 + zone sûre ; 4 cibles de 97 × 64 : Bibliothèque · Ajouter · Activité (badge) · Réglages.
- **Mini-barre d'activité** de 56 au-dessus de la barre du bas : cover de 24 × 43 · « ↓ La Revanche de l'héritière · 21/80 · ≈ 1 min 10 s » · [⏸] de 44. Un appui ouvre `#/activite`.
- **Bibliothèque**
  - Puces sur une rangée défilante de 32 (la page ne défile jamais horizontalement).
  - « À traiter » : rangée défilante de cartes de 280 × 96.
  - Mur de 3 colonnes de 112 × 199, espacement de 10 ; titre sur 2 lignes (13/18).
  - **Sous le titre, une seule ligne d'état et, si l'état n'est pas nominal, l'action principale visible** (bouton de 112 × 44). Pas de survol.
- **Ajouter** : feuille plein écran avec un champ, un bouton **[Coller]** (lit le presse-papiers après un geste), l'aperçu empilé (cover de 120 × 213 en haut) et le bouton principal **collé en bas**.
- **Fiche**
  - En-tête compact : cover de 96 × 171 et titre sur 3 lignes à côté.
  - Onglets de version en puces défilantes.
  - Phrase-bilan.
  - Grille de **5 tuiles de 60 × 48 par ligne**, espacement de 12 (348 px).
  - Volet en feuille du bas.
  - **Action principale collée en bas** : 358 × 48, au-dessus de la mini-barre.
- **Masqué sur mobile** (et pas seulement désactivé) : Ouvrir le dossier · Ouvrir dans le lecteur par défaut · installation de ffmpeg · réglages avancés · vue Liste dense.

---

## 6. Parcours clés

Convention : 1 interaction = 1 clic ou appui, 1 raccourci ou 1 validation. Coller compte pour 1, taper une recherche aussi. Le défilement ne compte pas.

| Parcours | Chemin | Clavier | Souris | Mobile |
|---|---|---|---|---|
| **(a) URL → aperçu → tout télécharger** | Ctrl+V n'importe où → aperçu en moins de 2 s, bouton focalisé → Entrée | **2** | **3** (clic dans le champ, Ctrl+V, clic sur le bouton) | 3 (Ajouter, Coller, Télécharger) |
| (a) + film à la fin | Ctrl+V → Ctrl+Entrée | 2 | 4 | 4 |
| (a) autre version | + ← / → ou clic sur une puce | 3 | 4 | 4 |
| (a) choisir des épisodes | Ctrl+V → [Choisir les épisodes] → saisie de « 1-10 » → Entrée | 4 | 5 | 5 |
| (a) plusieurs liens | Coller N lignes → Entrée | 2 | 3 | 3 |
| **(b) Suivre la progression** | Titre d'onglet, favicon, pilule, affiche qui se colore, notification | **0** | 0 | 0 |
| (b) détail | T ou clic sur la pilule | 1 | 1 | 1 |
| **(c) Retrouver une série parmi 50 et plus** | Ctrl+K → « laf » (trouvé dans le titre VF) → Entrée | **3** | 3 (clic, saisie, clic) | 3 |
| (c) par état | Puce « Avec échecs » → carte | — | 2 | 2 |
| **(d) Réessayer les échecs d'une série** | Bouton de la carte « À traiter » ou action principale de la carte | 2 (flèches + Entrée) | **1** | 1 |
| (d) Tout réparer | [Tout réparer] → confirmer | 2 | **2** | 2 |
| (d) Compléter | Carte [Compléter · 4] | 2 | **1** | 1 |
| (d) Ajouter une langue | Fiche → « + Espagnol » → Entrée | 3 | 3 | 3 |
| (d) Créer le film (pré-vol vert) | Fiche → [Créer le film], ou `F` sur la carte ciblée si le réglage est activé | 2 (1 avec F) | 2 | 2 |
| (d) Réparer puis créer le film (qualités mélangées + manquants) | Fiche → [Réparer puis créer le film] | 2 | 2 | 2 |
| (d) Retélécharger un épisode en 1080p | Fiche → tuile → [Retélécharger en 1080p] | 3 | 3 | 3 |
| (d) Ouvrir le dossier | Carte ciblée → `O`, ou ⋯ → Ouvrir le dossier | 1 | 2 | — |
| (d) Supprimer | Fiche → [Supprimer…] → choix → [Supprimer] | 3 | 3 | 3 |
| (d) En masse | Puce « À compléter » → Ctrl+A → [Compléter] | 3 | 3 | — |
| **(e) Regarder** | Carte → [▶ Regarder le film] / [▶ Reprendre · ép. 14], ou tuile téléchargée dans la fiche | 1 (`L`) | **1** | 1 |
| (e) Pendant le téléchargement | [▶ Ép. 1] sur la carte ou dans le tiroir | 1 | 1 | 1 |
| **(f) Reprendre après fermeture** | Reprise automatique au démarrage + bandeau | **0** | 0 | 0 |
| (f) Coupure Internet | Pause « hors ligne », aucun échec compté, reprise à l'octet près | 0 | 0 | 0 |
| (f) Fichier supprimé dans l'Explorateur | Carte dans « À traiter » → [Réparer] | 1 | 1 | 1 |

---

## 7. Composants

Les mesures exactes sont dans le système de design. Chaque composant est un Custom Element en light DOM.

### 7.1 `sdg-series-card` (carte série)
- **Variantes** : affiche (desktop 180 × 320, mobile 112 × 199), compacte « À traiter » (344 × 104, mobile 280 × 96), ligne de liste (56).
- **États** :
  - nominale (badges seulement) ;
  - première arrivée : en file (grise) / en cours (se colore, `--p`) / interrompue (remplissage figé + ‖) ;
  - nouvelle version en cours (barre lavande + « ↓ VE · 34/62 ») ;
  - avec échecs ;
  - à compléter ;
  - non vérifiée ;
  - survol/focus (case, ⋯, action principale, ▶) ;
  - cochée (anneau accent + coche) ;
  - squelette ;
  - hors ligne (actions réseau désactivées).
- **Nom accessible** : « Qui Est la Véritable Mme Lafont ?, 2 versions, VF : 3 épisodes à réparer, film prêt ».

### 7.2 `sdg-episode-tile` (tuile d'épisode)
- Un `<button data-status data-quality style="--p:.42">`. Les statuts : à télécharger · non demandé · en file · en cours · interrompu · téléchargé et vérifié · non vérifié · échec · indisponible · manquant · retiré.
- Ce qui s'y ajoute : qualité différente (badge « 720 »), sélection, focus, « vu » (dans le Théâtre).
- Codage complet (fond, luminance, bord, glyphe) dans le système de design, §3.
- **Nom accessible** : « Épisode 14, 2 min 05, téléchargé et vérifié, 13,2 Mo, 1080p ».
- Infobulle : « E014 · 2 min 05 · 1080p · 13,2 Mo · Vérifié ».

### 7.3 `sdg-episode-grid` (grille d'épisodes)
- `role="grid"`, un seul arrêt de tabulation, déplacement aux flèches (roving tabindex).
- Tailles : 10 par ligne (56 × 48) dans la fiche ; 10 par ligne (44 × 36) dans le dialogue d'ajout ; 5 par ligne (48 × 40) dans le Théâtre ; 5 par ligne (60 × 48) sur mobile. Étiquettes de rangée sur desktop.
- Légende-compteurs cliquable ; mode sélection signalé par une barre ; champ de plages synchronisé (§7.7).
- Mise à jour en direct : seul `--p` des tuiles actives change, au plus 4 fois par seconde. Le rendu reste fluide jusqu'à 1000 tuiles.

### 7.4 `sdg-ribbon` (ruban de complétude) et barre de progression
- **Ruban** : un segment égal par épisode, 6 px de haut, 1 px d'espace jusqu'à 80 épisodes. Au-delà de 150, les épisodes sont regroupés par paquets, et c'est le plus mauvais statut qui l'emporte.
- **Forme des segments** : vérifié (plein) · en cours (plein lavande) · échec (10 px, dépasse la piste) · indisponible (hachuré) · interrompu, manquant ou 720p (3 px, centré) · à venir (piste seule).
- `aria-hidden="true"`, toujours doublé d'un texte (« 21/80 · 1 échec »).
- **Barre de progression** : 6 px (tiroir, fiche) ou 4 px (tuile, pilule), piste surface-3, remplissage lavande (en cours), vert (terminé) ou ambre (en pause).
  - `role="progressbar"` + `aria-valuetext` : « 21 épisodes sur 80, environ 1 minute 10 secondes restantes ».
  - La barre ne recule jamais. Si un épisode repart de zéro, il reste affiché à son maximum avec le repère « nouvel essai ».

### 7.5 `sdg-omnibar` + `sdg-add-dialog` (champ URL et aperçu)
- **États du champ** : vide · saisie (recherche) · lien détecté (puce) · lot · erreur (bord danger + message relié par `aria-describedby`) · hors ligne.
- **États du dialogue** : chargement (squelette) · aperçu · déjà possédée · lien d'épisode · sonde · source en panne · disque insuffisant · introuvable · réseau · hors ligne · lot.
- Focus : champ du dialogue → bouton principal quand l'aperçu est prêt (annoncé) → retour sur le champ de l'en-tête après le lancement.

### 7.6 Sélecteurs de langue (version) et de qualité
- **Puces de version** (`role="radiogroup"`, 36 de haut). Statuts :
  - possédée : « ✓ 62/62 » ou « 59/62 » ;
  - doublée disponible ;
  - « vérification… » (désactivée, `aria-disabled`, pulsation d'opacité) ;
  - titre traduit seulement : pas de puce, cité dans la ligne d'aide.
- Nom complet de la langue au survol et pour le lecteur d'écran (`in` = « Indonésien »). Jamais de drapeau.
- **Qualité** : `<select>` natif stylé, 40 de haut. Options :
  - « Meilleure (1080p) · ≈ 690 Mo » ;
  - « 720p · ≈ 380 Mo (estimation) » ;
  - « 540p · ≈ 230 Mo (estimation) ».
- La sélection d'épisodes est conservée quand on change de qualité.

### 7.7 `sdg-range-picker` (sélection d'épisodes par plages)
- Champ texte en mono, 200 × 40, **synchronisé dans les deux sens** avec la grille.
- Accepte « 1-10, 28, 50- », le tiret long « 1–10 », les espaces et « 50-62 ».
- Une saisie invalide affiche un message sous le champ (« Plage à l'envers : 10-3 ») sans modifier la grille.
- Raccourcis : Tous · Aucun · Manquants · Échecs · Inverser.
- Résumé en direct : « 23 épisodes · ≈ 270 Mo ».
- Gestes : Maj+clic ou glisser pour une plage, Ctrl+clic ou Espace pour un épisode seul.

### 7.8 `sdg-activity` : pilule, tiroir, ligne de job, mini-barre mobile
- **Pilule** : repos (icône) · en cours · film · pause/arrêt · terminé (5 s) · échecs · hors ligne.
- **Ligne de job** : en file · métadonnées · sonde (« 23 trouvés », barre indéterminée statique) · téléchargement · mise en pause · en pause · interrompu · annulation · terminé · terminé avec échecs · échec bloquant (série introuvable, disque plein, réseau) · film.
- **Tiroir** : épinglé ou flottant.

### 7.9 `sdg-toast`
- **Variantes** :
  - succès : disparaît après 5 s ;
  - info ;
  - erreur : reste affiché, avec une action ;
  - annulable : 10 s, avec [Annuler].
- 3 toasts au maximum, **regroupés par vague** (« 3 épisodes en échec »). Chaque toast est aussi consigné dans le journal de l'activité.
- Pas de toast de fin si la fiche de la série ou le tiroir est déjà visible.
- Les toasts ne masquent jamais l'élément qui a le focus.

### 7.10 `sdg-confirm` (dialogues de confirmation)
- Types : Supprimer (radios de portée) · Arrêter un job (en ligne) · Tout réparer (popover) · Remplacer le film (case dans le pré-vol).
- Règles :
  - le bouton destructif affiche la quantité (« Supprimer 649 Mo ») et se trouve à 8 px d'[Annuler] ;
  - le focus par défaut est sur l'option la moins destructive ;
  - pas de « Êtes-vous sûr ? » générique.

### 7.11 `sdg-player` (lecteur vertical)
- **États** : chargement · lecture · pause · fin d'épisode (décompte) · épisode sauté · en cours de téléchargement · fichier absent · codec illisible.
- **Modes** : épisode (grille) ou film (chapitres, `chapters.vtt`).
- La vidéo n'est jamais étirée. Position mémorisée (V1.1).

### 7.12 Composants de base
Bouton (principal, secondaire, fantôme, danger, icône) · champ · select · case, radio, interrupteur · puce de filtre · badge · contrôle segmenté · onglets · menu · infobulle · bandeau · squelette · `kbd`.

---

## 8. Carte des erreurs (cas du moteur → lieu → message → action)

| Cas | Lieu | Message | Action |
|---|---|---|---|
| URL invalide (`InputError`) | Sous le champ, texte conservé | « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199). » | Corriger |
| Série absente du site officiel (mode sonde) | Aperçu, puis phase du job | « Infos limitées… sans contrôle de durée » → « Recherche des épisodes à la source… 23 trouvés » | Continuer |
| Introuvable partout (`SeriesNotFound`) | Aperçu | « On n'a trouvé cette série ni sur le site officiel ni à la source. » | Vérifier le lien |
| Langue indisponible | **Évitée** : pas de puce | « Coréen, thaï… : titre traduit seulement » | Choisir une version doublée |
| Épisode indisponible (`ep_unavailable`) | Tuile hachurée « – », volet, À traiter | « Cet épisode n'est pas disponible à la source pour le moment. » | [Réessayer maintenant] (pas de boucle) |
| Mauvais épisode renvoyé (`url_mismatch`) | Silencieux si la source suivante marche ; sinon Échec | « La source a renvoyé une vidéo qui n'est pas cet épisode. » | [Réessayer] |
| URL signée expirée | Silencieux (nouvelle résolution) ; sinon Échec | « Lien de téléchargement expiré, et impossible d'en obtenir un nouveau pour l'instant. » | [Réessayer] |
| Durée incorrecte (`duration_mismatch`) | Tuile « ! », volet | « Le fichier reçu ne correspond pas : 1 min 12 au lieu de 1 min 28. Il a été écarté. » | [Réessayer] |
| Téléchargement incomplet / MP4 illisible | Idem | « Le fichier reçu est incomplet ou illisible. » | [Réessayer] |
| Réseau ponctuel | Silencieux pendant les nouveaux essais | — | — |
| Réseau persistant | Tiroir, À traiter | « Connexion perdue · 3 échecs » | [Réessayer les échecs] |
| Hors ligne | Bandeau, pilule, tiroir | « Hors ligne… Nouvel essai dans 12 s. » | [Réessayer maintenant] |
| Interruption (fermeture, Ctrl+C, veille) | Bandeau au démarrage, carte, À traiter | « Interrompu · 34/48. Reprend là où il s'était arrêté. » | [Reprendre] |
| Repli de qualité (`quality_fallback`) | Badge « 720 » sur la tuile | « Téléchargé en 720p : le 1080p n'était pas disponible. » | [Retélécharger en 1080p] |
| ffmpeg absent | Pastille sur Réglages + pré-vol du film | « Pour créer un film, il faut ffmpeg… » | Commandes à copier · [Vérifier à nouveau] |
| Qualités mélangées (`film_mixed_formats`) | Pré-vol | « L'épisode 12 est en 720p, les autres en 1080p. » | [Retélécharger en 1080p puis créer] · [Ré-encoder] |
| Épisodes manquants (`film_missing_episodes`) | Pré-vol | « Il manque 3 épisodes (3, 40 et 41). » | [Réparer puis créer] · [Film partiel] |
| Durée du film incorrecte | Section Film | « … 1 h 29 au lieu de 1 h 32. » | [Réessayer] |
| Écrasement du film | Pré-vol | « Un film porte déjà ce nom (717 Mo). » | Case « Remplacer » |
| Disque plein (`disk_space`) | Bandeau + tiroir + notification | « Arrêté : disque plein (il manque 312 Mo sur C:). » | [Voir le stockage] [Reprendre] |
| Fichier verrouillé (`file_locked`, WinError 32) | Dialogue | « … ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. » | [Réessayer] |
| Dossier déplacé | Fiche | « Le dossier de cette version est introuvable. » | [Le retrouver…] [Retélécharger] [Retirer] |
| Manifest corrompu | Bibliothèque (partiel) + À traiter | « 2 dossiers n'ont pas pu être lus. » | [Voir lesquels] |
| Moteur injoignable | Bandeau `role="alert"` | « Le moteur ne répond plus… » | [Réessayer maintenant] |
| Doublon de job (`duplicate_job`) | Dialogue d'ajout | « Cette série est déjà dans la file. » | [Voir dans l'activité] |
| Série occupée (`series_busy`) | Dialogue Supprimer, film | « Un téléchargement est en cours sur cette série. » | [Mettre en pause puis continuer] |
| Erreur interne | Toast d'erreur | « Quelque chose s'est mal passé. Le détail est dans le journal. » | [Copier le rapport] |

Chaque message a un lien « Détails techniques » qui déplie la cause brute (message du moteur, n° de série, épisode, horodatage), avec [Copier]. **Jamais d'URL signée.**

---

## 9. Accessibilité et responsive

### 9.1 Accessibilité (WCAG 2.2 AA)
- **Contraste**
  - Texte ≥ 4,5:1 sur toutes les surfaces où il est utilisé ; composants et bords ≥ 3:1 (ratios vérifiés dans le système de design).
  - Texte sur une cover : uniquement sur un voile plein à 85 %.
  - Pas de texte blanc sur l'accent : le bouton principal porte un texte `#0B1220` (6,76:1).
- **Jamais la couleur seule** : chaque statut combine un fond de luminance différente, une forme de bord, un glyphe et un nom accessible.
- Mode Contraste élevé de Windows (`forced-colors: active`) : bords et glyphes système ; barres et rubans avec contour.
- **Focus**
  - Anneau de 2 px `#8FC1FF`, décalé de 2 px (5 px sur une tuile cochée).
  - Jamais masqué par l'en-tête collant, le tiroir ou un toast (`scroll-padding-top: 80px`, marge basse de 96).
  - Lien d'évitement « Aller au contenu ».
- **Clavier**
  - Grilles (mur, épisodes, mini-grille du Théâtre) avec roving tabindex ; F6 d'une région à l'autre.
  - Dialogues avec focus piégé et focus rendu à l'élément d'origine.
  - Aucune action uniquement au survol.
  - Le glisser-déposer a toujours une alternative.
  - Raccourcis à une touche désactivables.
- **Cibles** : 44 × 44 minimum sur mobile, 32 minimum sur desktop (au-delà des 24 de 2.5.8). Tuiles de 56 × 48 sur desktop et 60 × 48 sur mobile. 8 px entre une cible destructive et ses voisines.
- **Lecteurs d'écran**
  - Une seule région `role="status"`. Annonces au lancement, à 25, 50 et 75 %, à la fin et pour chaque groupe d'échecs, avec au moins 10 s d'écart. **Jamais une annonce par épisode.** Réglage : paliers / fin seulement / aucune.
  - `role="alert"` réservé aux blocages (moteur injoignable, disque plein).
  - `lang` sur chaque titre étranger (`es`, `en`, `ko`…).
  - Covers : `alt=""` quand le titre est affiché à côté.
- **Mouvement**
  - `prefers-reduced-motion` : pas de pulsation, remplissages par paliers, pas de transition de tiroir, décomptes en texte.
  - Rien ne clignote plus de 3 fois par seconde. Aucune limite de temps imposée (le toast annulable se prolonge tant qu'il a le focus).
- **Zoom** : utilisable à 200 % et en reflow à 320 px CSS sans défilement horizontal (sauf la vidéo). Tailles en `rem`.
- **Saisie redondante** (3.3.7) : langue, qualité, film à la fin et dossier sont mémorisés.

### 9.2 Responsive

| Zone | 1440 | 1280 | 600-1023 (Snap) | 390 |
|---|---|---|---|---|
| Gouttières / colonnes | 32 / 12 col. espacées de 24 | 24 / 12 col. | 24 / 8 col. | 16 / 4 col. espacées de 16 |
| En-tête | 64, champ de 560 | 64, champ de 440 | 64, champ de 320 | Barre d'app de 56 + barre du bas de 64 |
| Mur | 7 × 180 | 6 × ≈ 188 | 4 × ≈ 150 | 3 × 112 |
| Fiche | Héros avec cover de 240 · colonne de 984 + volet de 360 | Cover de 200 · colonne principale + volet de 320 | Une colonne, volet en feuille | Une colonne, cover de 96, action collée en bas |
| Grille d'épisodes | 10 × 56 | 10 × 52 | 10 × 48 | 5 × 60 |
| Dialogue d'ajout | 760 | 720 | Pleine largeur − 48 | Feuille plein écran |
| Activité | Tiroir de 400, épinglable | Tiroir en surimpression | Tiroir en surimpression | Page + mini-barre |
| Théâtre | Vidéo + panneau de 360 | Idem, panneau repliable | Vidéo seule + bouton liste | Plein écran natif, liste en feuille |

---

## 10. Architecture technique retenue

| Sujet | Décision |
|---|---|
| Serveur | `http.server.ThreadingHTTPServer` (bibliothèque standard), commande `sdg ui [--port 8765] [--no-browser] [--window] [-o DOSSIER]`. Écoute **uniquement sur 127.0.0.1**, port 8765 (sinon le premier libre de 8766 à 8775). `SO_EXCLUSIVEADDRUSE` sous Windows. |
| Instance unique | `server.json` (pid, port) dans `%LOCALAPPDATA%\ShortDramaGen\`. Si `/api/health` répond, on ouvre simplement le navigateur. |
| Fenêtre | Navigateur par défaut ; `--window` lance `msedge --app=http://127.0.0.1:8765/ --window-size=1440,900`, avec repli sur `webbrowser.open`. |
| Temps réel | SSE `GET /api/events` avec rejeu (`Last-Event-ID`, tampon de 1000 événements) et `: ping` toutes les 15 s. Les commandes passent en REST/JSON. Pas de WebSocket. |
| Client | HTML, CSS et JS natifs, modules ES, **Custom Elements en light DOM**, store à signaux maison d'environ 50 lignes, routeur par hash. Pas de npm ni de build. Plan B : Preact + htm copié dans le dépôt, composant par composant. |
| Polices | IBM Plex Sans et Plex Mono en woff2 **auto-hébergées** dans `shortdramagen/web/fonts/` (licence OFL, environ 250 Ko). La maquette utilise Google Fonts. |
| Icônes | Sprite SVG, sous-ensemble de Lucide (licence ISC), trait de 1,75. |
| Jobs | File FIFO persistée dans `<downloads>/.sdg/jobs.json`. Voie téléchargement : 1 série à la fois, 3 épisodes en parallèle. Voie film : 1 fusion à la fois. Un **RateLimiter partagé** (0,3 s). Un verrou par `series_key`. Doublon refusé sur `(book_id, lang or "vo")`. |
| Bibliothèque | Scan de `downloads/*/manifest.json` avec cache par `mtime`, réconciliation avec le disque (§10.1), regroupement par `book_id`, ETag. Mise à jour poussée par l'écouteur du manifest. |
| Suppression | Déplacement (`os.replace`) vers `<downloads>/.sdg/trash/<id>/`, purge après 5 min et à l'arrêt. |
| Sécurité | Contrôle de `Host` (sinon 421), `Sec-Fetch-Site` = same-origin, en-tête `X-SDG-Token` (HMAC du secret, injecté dans `<meta>`), `Origin` vérifié sur les mutations, `Content-Type: application/json` obligatoire, CORP same-origin sur `/media`, CSP stricte (`default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`). **Aucun chemin fourni par le client** : les fichiers servis sont reconstruits par le serveur à partir de l'index. Aucune URL CDN signée ne sort de l'API. |
| Médias | `/media/…` avec `Range` (maison), plage ouverte plafonnée à 8 Mio (limite les verrous de fichiers Windows), `HEAD`, `If-Range`, 416. |
| Cycle de vie | Arrêt automatique après 10 min sans client SSE ni job ; `POST /api/shutdown`. Au démarrage, les jobs `running` deviennent `interrupted` puis sont remis en `queued` si la reprise automatique est activée. |
| État local | `%LOCALAPPDATA%\ShortDramaGen\` : `settings.json`, `secret`, `server.json`, `server.log` (rotation), `cache/covers/`. Dans `<downloads>/.sdg/` : `jobs.json`, `trash/`, `ignored.json`, `watch.json` (V1.1). |
| Distribution | `py -m shortdramagen ui`, puis un zip portable (Python embarquable), puis un `.exe` PyInstaller `--onedir` (V2). |

### 10.1 Réconciliation disque / manifest (statut exposé)

| Manifest | `E###.mp4` | `.part` | Job | Exposé |
|---|---|---|---|---|
| done | présent, taille = `bytes` | – | – | `done` (ou `done_unverified` si `from_official=false`) |
| done | présent, taille différente | – | – | `done` + `suspect` |
| done | absent | – | – | `missing` |
| downloading | – | oui | actif | `downloading` |
| downloading ou pending | – | oui | aucun | `partial` |
| downloading | – | non | aucun | `pending` |
| pending | – | non | actif, sélectionné | `queued` |
| pending | – | non | aucun, hors `requested.episodes` | `not_requested` |
| pending ou failed | présent | – | aucun | `done_unverified` (le prochain `fetch` le confirmera) |
| failed + `error_code=ep_unavailable` | absent | – | – | `unavailable` |
| failed (autre) | absent | – | – | `failed` |
| removed | absent | – | – | `removed` |

---

## 11. Contrat d'API (v1)

**Conventions**
- JSON UTF-8, clés en `snake_case`, dates ISO 8601 UTC, tailles en octets, durées en secondes. L'interface se charge de la mise en forme en fr-FR.
- `series_key` = nom du dossier, `^\d{8,14}-[a-z0-9-]{1,120}$`.
- Tout `/api/*` exige `X-SDG-Token`. Les mutations exigent `Content-Type: application/json`, avec un corps de 64 Kio au maximum.
- **Format d'erreur** : `{"error": {"code": "…", "message": "…", "details": {}}}`.
- **Codes d'erreur API** : `invalid_input`, `invalid_lang`, `invalid_episodes`, `series_not_found`, `source_unavailable`, `network`, `not_found`, `duplicate_job`, `series_busy`, `ffmpeg_missing`, `film_mixed_formats`, `film_missing_episodes`, `film_exists`, `film_failed`, `disk_space`, `file_locked`, `outside_library`, `forbidden`, `internal`.
- **Codes d'erreur d'épisode** (`error_code` dans le manifest) : `ep_unavailable`, `url_mismatch`, `url_rejected`, `size_mismatch`, `duration_mismatch`, `mp4_unreadable`, `quality_unavailable`, `network`, `disk_full`, `file_locked`, `unknown`.

### 11.1 Routes

| Méthode | Chemin | Rôle | Lot |
|---|---|---|---|
| GET | `/api/health` | Version, ffmpeg, dossier, espace libre, connectivité, jobs | MVP |
| POST | `/api/preview` | Aperçu d'une URL (site officiel + 1 `get_video`, **jamais de sonde**), cache de 15 min | MVP |
| GET | `/api/catalog/{book_id}` | Versions par langue : titre localisé, doublée ou non, `source_book_id` (cache de 24 h) | V1.1 (MVP : puces à partir de `languages` + repli) |
| GET | `/media/preview/{book_id}/{lang}/cover` | Cover d'aperçu (cache) | MVP |
| GET | `/api/jobs` | `{active, history}` | MVP |
| POST | `/api/jobs` | Créer un job `fetch` ou `film` | MVP |
| GET | `/api/jobs/{id}` | Détail d'un job | MVP |
| POST | `/api/jobs/{id}/pause` · `/resume` · `/cancel` | Contrôle (202) | MVP |
| DELETE | `/api/jobs/{id}` | Retirer de l'historique | MVP |
| POST | `/api/queue/pause-all` · `/resume-all` | Toute la file | V1.1 |
| POST | `/api/repair` | « Tout réparer » : actions sûres sur N versions | MVP |
| GET | `/api/library` | Bibliothèque regroupée (ETag / 304) | MVP |
| POST | `/api/library/rescan` | Relire le disque | MVP |
| GET | `/api/series/{key}` | Détail d'une version | MVP |
| POST | `/api/series/{key}/retry` | Réessayer les échecs, indisponibles, manquants et partiels | MVP |
| POST | `/api/series/{key}/redownload` | Retélécharger des épisodes dans une qualité (`force`) | MVP |
| POST | `/api/series/{key}/refresh` | Vérifier les nouveaux épisodes (renvoie le diff) | V1.1 |
| GET | `/api/series/{key}/film/plan` | Pré-vol + remèdes (`fixes`) | MVP |
| POST | `/api/series/{key}/film` | Créer le film (raccourci de `POST /api/jobs`) | MVP |
| GET | `/api/series/{key}/links` | Export des liens (texte ou JSON), re-résolus si expirés | V2 |
| POST | `/api/series/{key}/open` | Explorateur : dossier, film, épisode | MVP |
| POST | `/api/series/{key}/ignore` | Ignorer un problème d'« À traiter » | MVP |
| DELETE | `/api/series/{key}?scope=all\|episodes\|film\|parts` | Supprimer (corbeille) | MVP |
| POST | `/api/trash/{id}/restore` | Annuler une suppression | MVP |
| PUT | `/api/watch/{key}` | Position de visionnage `{n, position_s}` | V1.1 |
| GET / PATCH | `/api/settings` | Réglages | MVP |
| GET | `/api/events` | SSE | MVP |
| POST | `/api/shutdown` | Arrêt (met les jobs en pause) | MVP |
| GET, HEAD | `/media/series/{key}/episodes/{n}` · `/film` · `/film/chapters.vtt` · `/cover` | Médias avec Range | MVP |

### 11.2 Exemples de charges utiles

**`POST /api/preview`** `{"input": "https://www.dramaboxdb.com/es/movie/41000105199/one-night-to-forever", "lang": null}` → 200 :
```json
{"book_id": "41000105199", "lang": "es", "lang_source": "url", "source_book_id": "41000106297", "is_original": false,
 "title": "Una Noche Para Siempre", "title_vo": "One Night to Forever", "introduction": "…",
 "cover_url": "/media/preview/41000105199/es/cover", "from_official": true,
 "episode_count": 62, "duration_s": 5521, "episode_duration_s": {"min": 50, "max": 210},
 "episode_ref": null, "languages": ["ko","th","in","ja","en","fr","es"],
 "availability": {"source": "ok", "checked_episode": 62, "qualities": ["1080p","720p","540p"]},
 "estimate": {"1080p": {"bytes": 690000000, "basis": "prior"}, "720p": {"bytes": 380000000, "basis": "guess"}, "540p": {"bytes": 230000000, "basis": "guess"}},
 "eta_s": {"download": 71, "queue_wait": 135},
 "disk": {"free_bytes": 182340000000, "enough": true},
 "local": [
  {"series_key": "41000105199-one-night-to-forever", "lang": "en", "is_original": true, "done": 62, "total": 62, "film": "ready"},
  {"series_key": "41000105199-one-night-to-forever-fr", "lang": "fr", "is_original": false, "done": 59, "total": 62, "problems": 3, "film": null}],
 "queued_job_id": null, "warnings": []}
```
- `episode_ref` vaut le numéro d'épisode pour un lien `/ep/`.
- `warnings` peut contenir `{"code": "probe_mode", …}` ou `{"code": "lang_unavailable", "requested": "de", "used": "en"}`.
- Erreurs : 422 `invalid_input`, 404 `series_not_found`, 502 `network`.

**`GET /api/catalog/41000105199`** → `{"versions": [{"lang": "en", "status": "original", "title": "One Night to Forever", "source_book_id": "41000105199"}, {"lang": "fr", "status": "dubbed", "title": "Qui Est la Véritable Mme Lafont ?", "source_book_id": "41000111625"}, {"lang": "es", "status": "dubbed", "title": "Una Noche Para Siempre", "source_book_id": "41000106297"}, {"lang": "ko", "status": "title_only", "title": "…", "source_book_id": "41000105199"}], "checked_at": "2026-09-26T17:05:02Z"}`. Une langue non encore vérifiée a `"status": "pending"`.

**`POST /api/jobs`** (téléchargement) :
```json
{"kind": "fetch", "input": "41000105199", "lang": "es", "quality": "best", "episodes": null, "force": [], "strict_quality": false, "film_after": false}
```
→ 201, `Location: /api/jobs/j-81c0d4`, `{"job": {"id": "j-81c0d4", "kind": "fetch", "status": "queued", "position": 2, "phase": null, "title": "Una Noche Para Siempre", "cover_url": "/media/preview/41000105199/es/cover", "params": {…}, "series_key": null, "progress": null, "result": null, "error": null, "then": null}}`.
- 409 `duplicate_job` avec `details.job_id`.
- `film_after` crée à la fin un job `film` sur **toute la version**, seulement s'il n'y a aucun échec.

**`POST /api/jobs`** (film) : `{"kind": "film", "series_key": "41000105199-one-night-to-forever-fr", "reencode": false, "allow_missing": false, "chapters": true, "output_name": null, "replace": false}`. 409 `film_exists` si le fichier existe et que `replace` vaut `false`.

**Job en cours** (dans `GET /api/jobs` ou le `snapshot`) :
```json
{"id": "j-7f3a2c", "kind": "fetch", "status": "running", "phase": "downloading",
 "series_key": "41000123401-the-heiress-strikes-back", "title": "La Revanche de l'héritière",
 "progress": {"episodes": {"total": 80, "done": 21, "skipped": 0, "failed": 0, "active": [22, 23, 24], "queued": 56},
              "bytes_done": 231000000, "bytes_total": 880000000, "total_is_estimate": true, "speed_bps": 9700000, "eta_s": 67}}
```
- `status` vaut `queued`, `running`, `pausing`, `paused`, `cancelling`, `cancelled`, `interrupted`, `done` ou `failed`.
- `phase` vaut `metadata`, `probing` (avec `probed`), `downloading`, `finishing`, `repairing` ou `merging`.
- Un job terminé porte `result: {"done": [...], "skipped": [...], "failed": {"41": {"code": "duration_mismatch", "message": "…"}}, "quality_fallback": {"12": {"requested": "1080p", "got": "720p"}}}`.

**`POST /api/repair`** : `{"series_keys": null, "dry_run": true}` → `{"actions": [{"series_key": "…-fr", "retry": [40, 41], "redownload": [3], "bytes_estimate": 35000000}, {"series_key": "41000999999-serie", "resume": 14, "bytes_estimate": 150000000}], "bytes_estimate": 185000000}`. Avec `dry_run: false` → 201 `{"jobs": [...]}`. Les actions sont toujours sûres : jamais Compléter ni Harmoniser.

**`GET /api/library`** (ETag `"lib-58"`) :
```json
{"version": 58,
 "stats": {"groups": 12, "versions": 14, "bytes": 14328000000, "episodes_bytes": 8416000000, "films_bytes": 5912000000, "freeable_bytes": 5794000000, "free_bytes": 182340000000},
 "groups": [{"book_id": "41000105199", "titles": {"en": "One Night to Forever", "fr": "Qui Est la Véritable Mme Lafont ?", "es": "Una Noche Para Siempre"},
   "display_title": "Qui Est la Véritable Mme Lafont ?", "cover_url": "/media/series/41000105199-one-night-to-forever/cover",
   "languages_available": ["ko","th","in","ja","en","fr","es"], "updated_at": "2026-09-26T16:58:10Z", "last_activity_at": "2026-09-26T16:52:40Z",
   "versions": [
    {"series_key": "41000105199-one-night-to-forever", "lang": "en", "is_original": true, "state": "complete",
     "counts": {"total": 62, "done": 62, "done_unverified": 0, "failed": 0, "unavailable": 0, "missing": 0, "partial": 0, "queued": 0, "pending": 0, "not_requested": 0},
     "bytes": 702000000, "duration_s": 5521, "qualities": {"1080p": 62}, "film": {"state": "ready", "bytes": 717000000}, "job": null, "ignored": []},
    {"series_key": "41000105199-one-night-to-forever-fr", "lang": "fr", "is_original": false, "state": "failed",
     "counts": {"total": 62, "done": 59, "failed": 1, "unavailable": 1, "missing": 1, "partial": 0, "queued": 0, "pending": 0, "not_requested": 0},
     "bytes": 649000000, "duration_s": 5521, "qualities": {"1080p": 58, "720p": 1}, "film": null, "job": null, "ignored": []}]}]}
```

**`GET /api/series/{key}`** : même résumé, plus `introduction`, `source_book_id`, `from_official`, `requested` (`{"lang": "fr", "quality": "best", "episodes": null}`), `versions` (voisines), `active_job_id`, `manifest_updated_at` et :
```json
"episodes": [
 {"n": 1, "status": "done", "quality": "1080p", "origin": "dramafren", "bytes": 21200000, "duration_s": 153.1, "media_url": "/media/series/41000105199-one-night-to-forever-fr/episodes/1"},
 {"n": 3, "status": "missing", "quality": "1080p", "duration_s": 98.0},
 {"n": 12, "status": "done", "quality": "720p", "quality_requested": "1080p", "origin": "dramafren", "bytes": 7300000, "duration_s": 91.2, "media_url": "…/episodes/12"},
 {"n": 40, "status": "unavailable", "error_code": "ep_unavailable", "error": "Épisode 40 indisponible sur dramafren (…)", "duration_s": 79.1},
 {"n": 41, "status": "failed", "error_code": "duration_mismatch", "error": "dramafren 1080p : durée 72.3 s au lieu de 88.4 s (mauvais fichier ?)", "duration_s": 88.4}],
"film": null, "url_expires_at_min": "2026-10-17T16:50:00Z"
```
La durée de 98,0 s pour l'épisode 3 est une valeur d'exemple.

**`GET /api/series/{key}/film/plan`** → 200 :
```json
{"can_build": false,
 "checks": {"episodes": {"ok": false, "missing": [3, 40, 41]}, "format": {"ok": false, "groups": [{"format": "avc1 1080x1920, mp4a 44100 Hz 2 canaux", "episodes": "1-2, 4-11, 13-39, 42-62"}, {"format": "avc1 720x1280, mp4a 44100 Hz 2 canaux", "episodes": "12"}]},
            "ffmpeg": {"ok": true, "path": "C:\\ffmpeg\\bin\\ffmpeg.exe", "source": "PATH"}, "disk": {"ok": true, "needed_bytes": 717000000, "free_bytes": 182340000000},
            "output": {"name": "Qui Est la Véritable Mme Lafont.mp4", "exists": false}, "chapters": 62},
 "duration_s": 5521.0, "estimated_bytes": 717000000,
 "fixes": [
  {"action": "repair_then_film", "retry": [40, 41], "redownload": [3], "redownload_quality": {"12": "1080p"}, "bytes_estimate": 50000000, "label": "Réparer puis créer le film"},
  {"action": "allow_missing", "output_name": "Qui Est la Véritable Mme Lafont (épisodes 1-2, 4-39, 42-62).mp4", "label": "Créer un film partiel"},
  {"action": "reencode", "enabled": false, "reason": "Des épisodes manquent aussi", "label": "Créer quand même (ré-encodage, plusieurs minutes)"}]}
```

**`DELETE /api/series/{key}?scope=episodes`** → 200 `{"trash_id": "t-1a2b3c", "scope": "episodes", "freed_bytes": 649000000, "restorable_until": "2026-09-26T17:10:00Z"}`. 409 `series_busy`, 423 `file_locked` avec `details.file`.

**`GET /api/health`** → `{"version": "0.2.0", "api": 1, "platform": "win32", "downloads_dir": "C:\\Users\\…\\Videos\\ShortDramaGen", "free_bytes": 182340000000, "ffmpeg": {"found": true, "path": "C:\\ffmpeg\\bin\\ffmpeg.exe", "source": "PATH"}, "online": true, "official_reachable": true, "source_reachable": true, "checked_at": "2026-09-26T17:04:00Z", "jobs": {"running": 1, "queued": 1}}`.

**`PATCH /api/settings`** (sous-ensemble) :
```json
{"downloads_dir": "C:\\Users\\…\\Videos\\ShortDramaGen", "default_quality": "best", "preferred_langs": ["fr"], "title_lang": "preferred",
 "parallel_downloads": 3, "concurrent_series": 1, "film_after_download": false, "resume_on_start": true, "ffmpeg_path": null,
 "theme": "dark", "nav_shortcuts": true, "action_shortcuts": false, "sr_announcements": "milestones", "notifications": true,
 "auto_shutdown_minutes": 10, "trash_minutes": 5, "version": 3}
```
Réponses : 422 pour une valeur invalide, 409 pour un changement de `downloads_dir` pendant un job.

### 11.3 Événements SSE (`GET /api/events`)

| Événement | Quand | Charge utile |
|---|---|---|
| `snapshot` | Connexion, ou `Last-Event-ID` hors du tampon | `{jobs: {active, history}, library_version, settings_version, health}` |
| `job` | Création, changement de statut ou de phase, fin | `{"op": "created\|updated\|removed", "job": {…}}` |
| `progress` | Au plus 4 fois par seconde et par job actif, seulement si une valeur a changé (pas de rejeu) | `{"job_id": "j-7f3a2c", "kind": "fetch", "bytes_done": 231000000, "bytes_total": 880000000, "total_is_estimate": true, "speed_bps": 9700000, "eta_s": 67, "episodes": {"done": 21, "failed": 0, "queued": 56, "active": [{"n": 22, "bytes": 7300000, "total": 11400000}]}}` · pour un film : `{"job_id": "…", "kind": "film", "seconds_done": 2710.5, "seconds_total": 5521.0, "eta_s": 3}` |
| `episode` | Changement d'état d'un épisode (écouteur du manifest), ou résolution en cours | `{"series_key": "…", "job_id": "…", "n": 22, "status": "resolving\|downloading\|done\|failed\|pending", "quality": "1080p", "bytes": 11400000, "error_code": null}` |
| `log` | Message du moteur (texte français) | `{"job_id": "…", "level": "info\|warn\|error", "code": "quality_fallback", "message": "…", "at": "…"}` |
| `library` | Version créée, modifiée ou supprimée | `{"op": "upserted\|deleted", "series_key": "…", "version": 59}` |
| `health` | Changement de connectivité, de ffmpeg ou du disque | `{"online": false, …}` |
| `settings` | Réglages modifiés | `{"settings": {…}, "version": 4}` |
| `server` | Arrêt imminent | `{"op": "shutdown"}` |

---

## 12. Plan d'implémentation et changements Python

### 12.1 Étapes

| Étape | Contenu | Critère de fin | Estimation |
|---|---|---|---|
| **0. Moteur pilotable** (sans interface) ✅ fait, voir [04 §9](../04-frontend.md#étape-0--livrée) | `FetchControl` (stop injectable, limiteur partagé, `force`, `strict_quality`, callbacks `on_series`, `on_bytes`, `on_resolving`, `on_probe`, `on_event`) ; `Cancelled` remet l'épisode en `pending` ; `stop.wait` au lieu de `time.sleep` ; sonde interruptible avec progression ; `preview_series()` ; `error_code` stable ; événement `quality_fallback` ; `Manifest` v2 avec écouteur et nouveaux champs ; `film.make_film` déplacé depuis la CLI, `FilmError(code)`, `plan_summary()` avec `fixes` ; `parse_episodes` déplacé dans `inputs.py` ; `fetch_cover()` → `cover.jpg` | CLI identique, les 42 tests existants passent, plus des tests d'annulation, de `force`, d'écouteur, d'aperçu et de `strict_quality` | 1,5 j |
| **1. Serveur en lecture seule** ✅ fait, voir [04 §9](../04-frontend.md#étape-1--livrée) | `server/` (routes, JSON, erreurs, sécurité, fichiers statiques), `sdg ui` (port, instance unique, `--window`), `settings.py`, `library.py` (scan, réconciliation §10.1, groupes, ETag), `/api/health`, `/api/library`, `/api/series`, `/media/*` avec Range, `chapters.vtt` | On parcourt les téléchargements existants et on lit épisodes et film dans le navigateur | 1,5 j |
| **2. Jobs et temps réel** ✅ fait, voir [04 §9](../04-frontend.md#étape-2--livrée) | `events.py` (bus, séquence, rejeu), `jobs.py` (store persistant, voies, verrous, doublons, enchaînement film, agrégateur de progression, `repair`), preview, retry, redownload, film plan et création, delete + corbeille, open, ignore, PATCH settings, shutdown, reprise au démarrage, arrêt automatique, connectivité mesurée | Cycle complet faisable avec `curl` : ajout, pause, reprise, annulation, redémarrage, réparation, film | 2 j |
| **3. Client MVP** ✅ fait, voir [04 §9](../04-frontend.md#étape-3--livrée) | Coquille (en-tête, pilule, bandeaux, toasts, tiroir), champ et dialogue d'ajout, Bibliothèque (mur, liste, filtres, À traiter, sélection multiple), Fiche (héros, versions, grille, volet, film, stockage, détails), Théâtre, Réglages, Supprimer, aide des raccourcis, responsive 390 et Snap | On colle l'URL, on télécharge, on regarde l'ép. 1 pendant que la suite arrive, on répare, puis on crée le film, sans terminal | 4 à 5 j |
| **V1.1** | Catalogue des langues (`/api/catalog`), position de visionnage + « Continuer à regarder », vérification des nouveaux épisodes, notifications Windows, pause/reprise de toute la file, mini-syntaxe dans le champ, estimations calibrées sur la bibliothèque, zip portable, clé de lancement + cookie de session, fichier de verrou par série (cohabitation CLI et serveur) | — | 2 j |
| **V2** | Accès depuis le réseau local avec vraie authentification (usage mobile), 2 séries en parallèle, réordonnancement de la file, job `verify` non destructif, export des liens, `.exe` PyInstaller, `SharedWorker` pour les onglets multiples, miniatures d'épisodes, anti-veille pendant les téléchargements, alias de regroupement de séries | — | — |

### 12.2 Changements par fichier

| Fichier | Changement | Compatibilité |
|---|---|---|
| `pipeline.py` | `FetchControl` et `fetch(..., control=None)` ; interception de `Cancelled` → `pending` ; `stop.wait(2*attempt)` ; boucle `wait(timeout=0.5)` + `shutdown(cancel_futures=True)` ; limiteur injecté ; `force` qui contourne le « déjà présent » (le nouveau fichier ne remplace l'ancien qu'une fois vérifié) ; `strict_quality` (sans repli : `quality_unavailable`) ; événement `quality_fallback` ; `probe_series(stop, on_probe)` ; `preview_series()` (sans sonde, parallèle) ; `FetchResult.cancelled` ; `error_code` à chaque `failed` | Signature actuelle inchangée ; CLI identique |
| `manifest.py` | Écouteur optionnel appelé après chaque sauvegarde ; `schema_version: 2` ; champs `languages`, `titles`, `from_official`, `created_at`, `requested {lang, quality, episodes}`, `cover_file`, `total_duration_ms` ; par épisode `error_code`, `quality_requested`, `attempts`, `finished_at` ; statut `removed` ; `error` effacé dès qu'on repasse en `downloading` | Anciens manifests lisibles (champs optionnels) |
| `film.py` | `make_film()` venu de `cli.py` (avec `stop`, `on_progress`, `log`) ; `FilmError(code, message)` ; `plan_summary()` → checks + `fixes` + espace disque ; `film.chapters` stocké ; `replace=False` refusé si le fichier existe (`film_exists`) ; `-y` gardé seulement quand `replace=True` | La CLI appelle `film.make_film(replace=True)` pour garder son comportement |
| `official.py` | Conserver `languages`, `bookNameEn` (`title_vo`), `tags` ; `fetch_locale_title(book_id, lang)` pour le catalogue | — |
| `cli.py` | Sous-commande `ui` ; imports de `parse_episodes` et `make_film` | Options existantes inchangées |
| `inputs.py` | Reçoit `parse_episodes` (tiret long et espaces tolérés) ; renvoie `episode_ref` pour les URL `/ep/` | — |
| `download.py`, `http.py`, `dramafren.py`, `cdn.py`, `mp4.py` | Aucun changement (en V2, éventuellement un `stop` dans `Http`) | — |
| Nouveaux | `events.py`, `jobs.py`, `library.py`, `settings.py`, `server/{app,api,media,sse,security}.py` (environ 1500 lignes), `web/` (environ 2500 lignes de JS et 1000 de CSS, polices, sprite) | — |
| `pyproject.toml` | `package-data` : `web/**/*` ; version 0.2.0 | — |
| Tests | `test_server.py`, `test_jobs.py` (cycle de vie, pause qui garde le `.part`, redémarrage, 409), `test_library.py` (table §10.1), `test_security.py` (Host, Sec-Fetch-Site, jeton, `..`/`%2e%2e`, film hors dossier, lien symbolique, 413, 415), `test_media.py` (`bytes=0-`, suffixe, 416, plafond de 8 Mio, HEAD) | Tout hors ligne ; l'interface est vérifiée par une liste de contrôle manuelle sous Edge et Chrome (Windows) |
| Docs | `docs/04-frontend.md` (cette spécification) ; section « Interface » du README | — |

---

## 13. À tester et questions ouvertes

1. **Affiche désaturée** : est-elle lue comme « désactivée » ? Test rapide sur 5 cartes. Solution de repli : couleur conservée + bande lavande.
2. **Codecs** : mesuré sur la série de test, H.264 High + AAC HE (44,1 kHz stéréo), identiques dans une même qualité. Si une série est en HEVC, on affiche l'état « codec illisible » avec l'ouverture dans le lecteur externe.
3. **Position du `moov`** : mesurée, les épisodes sont en « faststart » (`ftyp`, `moov`, puis `mdat`). La lecture peut démarrer dès les premiers octets.
4. **Estimations en 720p et 540p** : aucune mesure réelle. Elles restent marquées « estimation » jusqu'à leur calibration sur la bibliothèque.
5. **Langues doublées de One Night to Forever** autres que VF et VE : non vérifiées. Dans la maquette, « titre traduit seulement » pour ko, th, in et ja est **illustratif**.
6. **Plafond de plage de 8 Mio** : vérifier que Chrome et Edge enchaînent bien les requêtes suivantes (test manuel).
7. Faut-il proposer « supprimer les épisodes après création du film » comme réglage ? Recommandation : non, seulement comme suggestion unique après la création.
