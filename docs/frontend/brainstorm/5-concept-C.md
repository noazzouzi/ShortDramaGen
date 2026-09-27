# Concept C — Poste de pilotage

# Concept C : « Poste de pilotage »

> Frontend local de ShortDramaGen, pensé pour quelqu'un qui gère des dizaines de séries, de versions et de jobs. L'écran est découpé en panneaux, on peut tout faire au clavier et la supervision reste visible en permanence. Toutes les données viennent des faits vérifiés : « One Night to Forever », 62 épisodes, 1 h 32, environ 700 Mo en 1080p, un téléchargement complet en 40 s à 1 min 40, un film fusionné en environ 6 s.

---

## 1. Idée directrice

**En deux phrases.** ShortDramaGen devient un poste de pilotage en quatre zones fixes, sur le modèle de VS Code : on choisit à gauche, on voit au centre, on agit à droite dans l'inspecteur et on surveille en bas avec le dock d'activité et la barre d'état, sans jamais quitter l'écran. Tout commence dans une seule barre, « Colle ou cherche », accessible par Ctrl+V n'importe où ou par Ctrl+K. Elle comprend les liens DramaBox, les titres de la bibliothèque dans toutes les langues, les actions, et même une mini-syntaxe reprise de la CLI (`fr 720p 1-10 film`).

**Pourquoi c'est le bon choix pour cet utilisateur**

- **Il vient de la CLI et il s'est lancé un défi.** L'interface doit en faire au moins autant que `sdg` : toutes les options sont là et la commande équivalente se copie. Elle doit aussi être plus rapide au clavier : 2 frappes (Ctrl+V, Entrée) remplacent `sdg fetch <url> --lang fr --film`.
- **Le goulot, c'est la supervision, pas le téléchargement.** Une série arrive en environ 1 min. Ce qui prend du temps, c'est de suivre 50 séries, leurs VO, VF et VE, les films, les échecs et l'espace disque. Il faut donc une vue d'ensemble dense et une file visible en permanence, pas un assistant pas à pas.
- **Les opérations sont courtes.** La progression reste en périphérie (barre d'état, titre de l'onglet, ruban dans la liste). Pas de page d'attente, pas de modale, et le centre ne change jamais sans que l'utilisateur l'ait demandé.
- **La forme des zones suit celle du contenu.** La colonne de droite, haute et étroite, convient à une cover 9:16 (180×320 px, nette à partir d'une source de 360×640) et à une liste d'épisodes. La bande du bas, large et basse, convient à une ligne de job : ruban de 62 segments, octets, débit, temps restant.
- **Il est sous Windows.** On reprend ses conventions : F6 pour passer d'un panneau à l'autre, Suppr, Maj+clic, menu contextuel (touche Menu ou Maj+F10), Explorateur. Aucun ⌘, et des raccourcis compatibles AZERTY.
- **Il veut contrôler et faire confiance.** Tout ce qui se passe est visible : la file, un journal structuré et une boîte « À traiter ». Rien ne se passe dans son dos.

**Les cinq règles du poste**

1. **Quatre zones, aucun changement d'écran forcé.** Naviguer à gauche, voir au centre, agir à droite, surveiller en bas.
2. **La sélection pilote l'inspecteur.** Une série, un épisode ou un job sélectionné : l'inspecteur affiche son détail et ses actions.
3. **Tout se fait au clavier, rien n'exige le clavier.** Chaque action a un bouton visible, et chaque bouton affiche son raccourci.
4. **La périphérie informe, le centre reste stable.** La progression s'affiche dans le dock, la barre d'état et le ruban, jamais par une redirection.
5. **Chaque problème a une adresse et un bouton.** Le panneau « À traiter » regroupe les problèmes, et chaque groupe a une action en masse.

---

## 2. Architecture de l'information

### 2.1 Les quatre zones (desktop 1440)

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◆ ShortDramaGen  ⌕ Colle un lien DramaBox ou cherche une série…            Ctrl K    ↓ 1   ⚠ 1   ?   ⚙                        │
├───────────────────────┬──────────────────────────────────────────────────────────────────────┬────────────────────────────────┤
│ ◉ Bibliothèque     54 │ Bibliothèque · 54 séries · 38,4 Go     [≡ Liste] [▦ Affiches]        │ SÉRIE              Épingler ✕  │
│   Continuer         4 │ Tri : Ajoutées récemment ▾                Densité : standard ▾       │ ┌────────┐ Qui Est la          │
│   En cours          2 │ ────────────────────────────────────────────────────────────         │ │ cover  │ Véritable Mme       │
│   Incomplètes       3 │ ☐    Titre                   Versions Épisodes         État          │ │  9:16  │ Lafont ?            │
│   Avec échecs       1 │ ────────────────────────────────────────────────────────────         │ │180×320 │ One Night to        │
│   Complètes        47 │▌☐ ▯ Qui Est la Véritable…    VO [VF]  ▰▰▰▰▰▱▱▱ 34/62  ↓ 55 %         │ │ (flou  │ Forever · VO        │
│   Avec film        31 │       One Night to Forever                                           │ │ derr.) │                     │
│   Libérable    8,4 Go │ ☐ ▯ Série B                  VO       ▰▰▰▰▰▰▰▰ 62/62  ✓ Film         │ └────────┘                     │
│ VERSIONS              │       Titre VO de B                                                  │ 62 ép. · 1 h 32 · 1080p        │
│   VO 41 · VF 9 · VE 4 │ ☐ ▯ Série C                  VO VF    ▰▰▰▰▰▰▰▱ 58/62  ◐ Incomplète   │ Version  VO  [VF]  + Ajouter   │
│ VUES ENREGISTRÉES     │       Titre VO de C                                                  │ ▰▰▰▰▰▱▱▱ 34/62 · 55 % · ~40 s  │
│   ☆ 720p à refaire    │ ☐ ▯ Série D                  VE       ▰▰▰▰▰▰!▰ 79/80  ! 1 échec      │ [ ⏸ Mettre en pause      P ]   │
│ ────────────────────  │ ☐ ▯ Série 41000999999        —        ▰▰▰▰▰▰▰▰ 48/48  ≈ Non vérifiée │ Fiche ⏎ · Lire L · Dossier O ⋯ │
│ ⚠ À traiter         3 │ …                                                                    │ ÉPISODES                       │
│ ↓ Activité          2 │                                                                      │ ■■■■■■■■■■  ■ ■ ■ = 1 case     │
│ ⚙ Réglages            │                                                                      │ ■■■■■■■■■■  par épisode        │
│                       │                                                                      │ ■■■■■■■■■■                     │
│ C: 182 Go libres ▰▰▰▱ │                                                                      │ ■■■◧◧◧□□□□                     │
│                       │                                                                      │ □□□□□□□□□□ □□                  │
│                       │                                                                      │ FILM · après 62/62 (auto)      │
│                       │                                                                      │ Détails techniques ▸           │
├───────────────────────┴──────────────────────────────────────────────────────────────────────┴────────────────────────────────┤
│ File (3) │ Problèmes (1) │ Journal │ Historique                                    ⏸ Tout mettre en pause   ▾ Réduire  T      │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▯ Qui Est la Véritable Mme Lafont ? · VF  Téléchargement  ▰▰▰▰▰▱▱▱ 34/62 · 432/684 Mo · 12,4 Mo/s · ~40 s   ⏸ ✕               │
│ ▯ One Night to Forever · VE               En file · démarre ensuite                                   ↑ ↓ ⏸ ✕                 │
│ ▯ Série C · VO                            Voie film · Assemblage… 38/62 épisodes · ~3 s                      ✕                │
├───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ● Moteur │ ↓ 1 actif · 1 en file · 34/124 ép. · 12,4 Mo/s · ~1 min 50 │ ⚠ 1 problème │ C: 182 Go libres │ ffmpeg ✓            │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Zone | Taille à 1440 | Rôle | Masquer / afficher |
|---|---|---|---|
| Barre supérieure | 48 px | Omnibar « Colle ou cherche » (Ctrl+K), indicateurs (jobs, problèmes), aide, réglages | toujours visible |
| Barre latérale | 232 px, réduite à un rail de 56 px | Vues intelligentes avec compteurs, versions, vues enregistrées, À traiter, Activité, Réglages, jauge disque | Ctrl+B |
| Centre | flexible, 640 px minimum | Bibliothèque (liste ou affiches), fiche série, lecteur, À traiter, Activité, Réglages | — |
| Inspecteur | 360 px (redimensionnable de 320 à 480) | Détail et actions de la sélection, aperçu d'ajout, pré-vol du film | I |
| Dock | panneau de 240 px (redimensionnable) + barre d'état de 32 px permanente | File, Problèmes, Journal, Historique | T (la barre d'état reste toujours visible) |

**Pourquoi le dock est en bas et l'inspecteur à droite (et non l'inverse).** Le contenu portrait (covers, lecteur 9:16, liste d'épisodes) remplit une colonne haute. Les lignes de job (ruban, débit, temps restant) remplissent une bande large. Un dock placé à droite entrerait en concurrence avec l'inspecteur, et c'est l'inspecteur qui porte l'action.

### 2.2 Arborescence des vues et routes

```
ShortDramaGen
├── Omnibar / Palette ........................ global (Ctrl+K, Ctrl+V hors champ, glisser-déposer d'un lien)
├── Barre latérale
│   ├── Bibliothèque ......................... #/bibliotheque
│   │   ├── Vues intelligentes : Toutes · Continuer à regarder · En cours · Incomplètes · Avec échecs
│   │   │   · Complètes · Avec film · Sans film · Qualités mélangées · Non vérifiées (mode sonde)
│   │   │   · Libérable (épisodes déjà fusionnés en film)
│   │   ├── Versions : VO · VF · VE · … (filtre cumulable)
│   │   └── Vues enregistrées (combinaisons filtres + tri nommées)
│   ├── À traiter ............................ #/a-traiter
│   ├── Activité (plein écran) ............... #/activite
│   └── Réglages ............................. #/reglages/<section>
├── Centre
│   ├── Bibliothèque : Liste | Affiches ...... #/bibliotheque?vue=incompletes&v=fr&tri=ajout&sel=41000105199
│   ├── Fiche série .......................... #/serie/41000105199/fr
│   │   ├── Lecteur (mode théâtre) ........... #/serie/41000105199/fr/ep/14
│   │   └── Lecteur du film .................. #/serie/41000105199/fr/film
│   ├── Ajout en lot (plusieurs liens) ....... #/ajout
│   ├── À traiter · Activité · Réglages
├── Inspecteur (contextuel, voir 2.4)
└── Dock : barre d'état + onglets File | Problèmes | Journal | Historique
```

Les filtres, le tri, la vue et la sélection vivent dans l'URL (routeur par hash). Le bouton Retour fonctionne donc, et une vue se met en favori.

### 2.3 Navigation

- **Souris** : barre latérale, fil d'Ariane dans l'en-tête de la fiche (« ← Bibliothèque › One Night to Forever »), double-clic sur une ligne pour ouvrir la fiche.
- **Clavier entre zones** : F6 et Maj+F6 font le tour Omnibar → Barre latérale → Centre → Inspecteur → Dock, selon la convention Windows. Chaque zone est une région ARIA nommée.
- **Séquences « G »** : G puis B (Bibliothèque), A (Activité), P (À traiter, pour « Problèmes »), R (Réglages).
- **Échap remonte d'un niveau** : fermer la palette, puis vider la sélection, puis revenir de la fiche à la bibliothèque.
- **Aucune redirection automatique** : lancer un téléchargement, créer un film ou supprimer ne change jamais la vue centrale.

### 2.4 L'inspecteur : ce qu'il montre selon le contexte

| Contexte (sélection) | Contenu de l'inspecteur |
|---|---|
| Bibliothèque, rien de sélectionné | Résumé de la collection : 54 séries, 38,4 Go, espace libre, « À traiter (3) », dernière activité, aide « Colle un lien » |
| 1 série | **Inspecteur de série** (§3.2) |
| n séries cochées | **Sélection multiple** : totaux et actions en masse (§3.2) |
| Lien collé (n'importe où) | **Aperçu d'ajout** (§3.3). Il est prioritaire et rend la main au contexte précédent après le lancement. |
| Fiche : 1 épisode ciblé | **Détail de l'épisode** (§3.4) |
| Fiche : n épisodes sélectionnés | **Sélection d'épisodes** : taille, actions |
| Fiche ou inspecteur : « Créer le film » | **Pré-vol du film** (§3.5) |
| Dock : un job | **Détail du job** : paramètres, phases, erreurs par épisode, commande équivalente |
| Lecteur | Liste des épisodes (vus, en cours) ou chapitres du film |
| À traiter : un groupe | Séries concernées et remède proposé |

**Épingler** fige le contenu de l'inspecteur (par exemple une série) pendant qu'on parcourt ailleurs. C'est utile pour comparer ou pour surveiller une série précise.

---

## 3. Écrans

Format de chaque écran : **But**, **Zones de haut en bas**, **Actions** (primaires en gras), **États**.

### 3.0 Coquille (cadre permanent)

- **But** : un cadre stable où chaque information a une place fixe.
- **Zones** : barre supérieure (logo qui ramène à la bibliothèque, omnibar de 560 px avec l'indice « Ctrl K », indicateur « ↓ n » des jobs actifs, « ⚠ n » des problèmes, `?`, ⚙), barre latérale, centre, inspecteur, dock avec barre d'état.
- **Actions** : Ctrl+K, Ctrl+V, F6, T, I, Ctrl+B, `?`.
- **États** :
  - **Chargement** : squelettes statiques dans les quatre zones et « Lecture de ta bibliothèque… 23 séries trouvées ».
  - **Moteur injoignable** : bandeau rouge sous la barre supérieure (`role="alert"`), « Le moteur ne répond plus. On essaie de se reconnecter… » avec [Réessayer maintenant]. Toute l'interface passe en lecture seule avec le dernier état connu, et la reconnexion est tentée toutes les 5 s.
  - **Hors ligne** : pastille ambre « Hors ligne » dans la barre d'état et un seul bandeau discret : « Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls. »
  - **Reprise au démarrage** : le dock s'ouvre sur un bandeau (parcours f).
  - Titre de l'onglet : « (55 %) ShortDramaGen », puis « Terminé · ShortDramaGen ». Le favicon porte un anneau de progression.

### 3.1 Bibliothèque (centre)

- **But** : voir toute la collection, la chercher, la filtrer, la trier, sélectionner et agir en masse.
- **Zones** :
  1. **En-tête** : « Bibliothèque · 54 séries · 38,4 Go » (ou « 12 séries sur 54 » avec [Effacer les filtres] si un filtre est actif), bascule **Liste / Affiches** (V), tri, densité.
  2. **Puces des filtres actifs**, supprimables une à une, et [Enregistrer cette vue].
  3. **Liste dense** (vue par défaut du poste), une ligne par série d'origine (`book_id`) et non par dossier :

     | Colonne | Contenu |
     |---|---|
     | ☐ | Case à cocher (visible au survol, au focus, ou en permanence dès qu'une ligne est cochée) |
     | Mini-cover | 28×50, 9:16 |
     | Titre | Titre de la version préférée (VF si elle existe) avec l'attribut `lang`, titre VO en dessous en gris, 2 lignes, titre complet en infobulle |
     | Versions | Puces VO · VF · VE. La version active est soulignée. « +4 » en gris pour les langues disponibles non téléchargées |
     | Épisodes | **Ruban de complétude** (§5.3) et « 58/62 » |
     | Qualité | 1080p · 720p · « Mixte » (ambre) |
     | Taille | « 684 Mo » (tri possible, pour libérer de l'espace) |
     | Film | ✓ Prêt · Partiel · Obsolète · — |
     | Ajoutée | « il y a 3 j » |
     | État | **Un seul badge**, par priorité : En cours > En file > En pause / Interrompu > Échecs (n) > Incomplète > Complète. S'y ajoute « Non vérifiée » en mode sonde. |
     | ⋯ | Menu contextuel (même contenu que l'inspecteur) |

  4. **Vue Affiches** : cartes de 160 px (cover 160×284), ruban sous l'affiche, titre sur 2 lignes, « 62 ép. · 1 h 32 ». Badges de versions et de film dans les coins bas, jamais sur les visages. 4 colonnes quand l'inspecteur est ouvert, 7 quand il est masqué.
- **Recherche** : taper du texte (et non un lien) dans l'omnibar filtre la liste en direct. La recherche porte sur les titres de toutes les langues et sur le n° de série, en moins de 100 ms sur l'index local. La correspondance est surlignée, avec « trouvé dans le titre VF ». Le menu déroulant de l'omnibar propose en plus le premier résultat et les actions (§3.9).
- **Actions** :
  - **Clic** : sélectionner, ce qui remplit l'inspecteur. **Entrée ou double-clic** : ouvrir la fiche.
  - X ou Espace : cocher. Maj+clic ou Maj+↑↓ : plage. Ctrl+A : tout cocher parmi le résultat filtré.
  - Raccourcis de série sur la ligne ciblée : R, C, F, L, O, P, Suppr (§5.9).
- **États** :
  - **Vide** : voir §3.12.
  - **Chargement** : 8 lignes squelettes, sans effet de scintillement si reduced-motion est activé.
  - **Partiel** : « 2 dossiers n'ont pas pu être lus » (manifest corrompu), avec [Voir lesquels], qui mène à À traiter.
  - **Erreur** : plein centre, « Impossible d'ouvrir ton dossier de séries (C:\…\ShortDramaGen). Il a peut-être été déplacé, ou le disque est débranché. » avec [Choisir un autre dossier] et [Réessayer].
  - **Aucun résultat** : « Aucune série « lafont » avec les filtres VE · Complètes. 1 résultat sans ces filtres. » avec [Effacer les filtres]. Si le texte ressemble à un lien : « Ça ressemble à un lien DramaBox » avec [Ajouter cette série].
  - **Hors ligne** : identique, car les covers sont en cache local. Les actions réseau affichent leur raison : « Disponible au retour de la connexion ».

### 3.2 Inspecteur de série (et sélection multiple)

- **But** : tout savoir sur une série et agir sans ouvrir sa fiche.
- **Zones** :
  1. **Cover 180×320** sur un fond fait de la même cover floutée, sous un voile à 85 %. Si la cover manque, une affiche est générée : dégradé calculé à partir du titre, avec le titre en clair.
  2. **Titre** de la version choisie, titre VO, méta « 62 ép. · 1 h 32 · 1080p · 684 Mo ».
  3. **Sélecteur de version** : puces VO (anglais) · VF · VE, puis [+ Ajouter une version] (menu des langues doublées avec leur taille estimée ; les langues sans doublage sont désactivées avec leur raison). Changer de puce met à jour tout ce qui suit.
  4. **Santé** : ruban, puis une phrase : « 58/62 · 4 manquants (59 à 62) », « 62/62 vérifiés » ou « Durées non vérifiées (mode sonde) ».
  5. **Bouton principal contextuel**, raccourci affiché :

     | État de la version | Bouton principal |
     |---|---|
     | En cours | **Mettre en pause** (P) |
     | En file | **Passer en premier** |
     | Interrompue | **Reprendre (34/62)** (P) |
     | Échecs | **Réessayer les 2 épisodes** (R) |
     | Incomplète | **Télécharger les 4 manquants** (C) |
     | Complète sans film | **Créer le film** (F) |
     | Complète avec film | **Lire le film**, ou **Reprendre · Ép. 14** si un visionnage est en cours (L) |

  6. **Actions secondaires** : Ouvrir la fiche (Entrée) · Lire (L) · Dossier (O) · ⋯ (Retélécharger en…, Copier la commande, Copier les liens, Supprimer… (Suppr)).
  7. **Mini-grille des épisodes** : 10 par ligne, cases de 28 px. Un clic ouvre la fiche avec le focus sur cet épisode.
  8. **Film** : état et action, plus trois pastilles de pré-vol calculées dès la sélection (épisodes, format, ffmpeg).
  9. **Détails techniques** (repliés) : n° de série, n° de la version doublée, dossier, dernière mise à jour, commande CLI [Copier], [Copier les liens] (équivalent de `links`, les URL signées ne sont jamais affichées).
- **Sélection multiple** : « 5 séries · 7 versions · 3,4 Go », puis des actions chiffrées :
  - [Compléter · ≈ 1,2 Go] ;
  - [Réessayer les échecs (4 épisodes)] ;
  - [Créer les films (3 possibles · 2 bloqués, pourquoi ?)] ;
  - [Supprimer les épisodes, garder les films · libère 2,1 Go] ;
  - [Supprimer…].
- **États** :
  - **Chargement** : squelette.
  - **Dossier introuvable** : « Le dossier de cette version est introuvable. » avec [Le retrouver…], [Retélécharger] et [Retirer de la bibliothèque].
  - **Mode sonde** : « Série 41000999999 · sans métadonnées · durées non vérifiées ».
  - **Hors ligne** : réessayer, compléter et ajouter une version sont désactivés, avec le texte « au retour de la connexion ». Lire, Film et Dossier restent actifs.

### 3.3 Aperçu d'ajout (inspecteur) et ajout en lot (centre)

```
┌────────────────────────────────────────────┐
│ AJOUTER UNE SÉRIE                   ✕      │
│ ✓ Lien DramaBox · n° 41000105199 · fr      │
│ ┌─────────┐ Qui Est la Véritable           │
│ │  cover  │ Mme Lafont ?                   │
│ │  9:16   │ One Night to Forever (VO)      │
│ │ 180×320 │ 62 épisodes · 1 h 32           │
│ │         │ Source ● disponible            │
│ └─────────┘ 1080p · 720p · 540p            │
│ Synopsis sur 3 lignes………………… Lire plus     │
│ ─────────────────────────────────────      │
│ Version   (VF)  ( VO anglais )  ( VE )     │
│   Autres langues : titre traduit,          │
│   doublage à confirmer  ⓘ                  │
│ ─────────────────────────────────────      │
│ ≈ 700 Mo · ≈ 1 min · 182 Go libres (C:)    │
│ ⚙ 1080p · tous les épisodes · sans film    │
│                              Modifier ▾    │
│ ┌──────────────────────────────────────┐   │
│ │  ↓ Tout télécharger · 62 épisodes  ⏎ │   │
│ └──────────────────────────────────────┘   │
│   Ctrl+⏎ : + créer le film à la fin        │
│ Choisir les épisodes · Copier la commande  │
└────────────────────────────────────────────┘
```

- **But** : vérifier en moins de 2 s que c'est la bonne série, dans la bonne version, pour le bon coût, puis lancer en une frappe.
- **Déclencheurs** : Ctrl+V hors champ (l'événement `paste` du document, qui ne demande aucune permission presse-papiers), collage dans l'omnibar, glisser-déposer d'un lien sur la fenêtre.
- **Zones** :
  1. **Reconnaissance locale instantanée** : « ✓ Lien DramaBox · n° 41000105199 · fr ».
  2. Cover, titre dans la version, titre VO, « 62 épisodes · 1 h 32 », disponibilité de la source et qualités.
  3. Synopsis sur 3 lignes, dépliable.
  4. **Versions** : seules les langues **réellement doublées** sont proposées. La locale de l'URL est présélectionnée, sinon la version préférée des réglages, sinon la VO. On évite ainsi le repli « langue indisponible » au lieu de le signaler après coup.
  5. **Coût** : « ≈ 700 Mo · ≈ 1 min · 182 Go libres (C:) ». Les estimations en 720p et 540p sont marquées « approximatives ».
  6. **Ligne d'options résumée**, cliquable, mémorisée d'une fois sur l'autre : qualité · épisodes · film. Elle se déplie en qualité (taille par qualité), épisodes (Tous / Sélection / Seulement les manquants, avec la **grille-sélecteur** du §5.4), film à la fin, dossier.
  7. **Bouton principal focalisé** : « Tout télécharger · 62 épisodes ». Ctrl+Entrée : idem, avec le film à la fin. Maj+Entrée : déplier les options.
  8. Liens secondaires : Choisir les épisodes · Copier la commande (`sdg fetch 41000105199 --lang fr --film`).
- **Après le lancement** : l'inspecteur revient au contexte précédent. La série apparaît en tête de liste, surlignée pendant 2 s. La barre d'état s'allume. Un toast annonce « Téléchargement lancé : Qui Est la Véritable Mme Lafont ? (VF) · 62 épisodes » avec [Voir]. L'omnibar est vidé et **reste focalisé** pour enchaîner un autre lien.
- **Variante « déjà dans ta bibliothèque »** : un bloc « VO complète (62/62) · VF 40/62 » remplace le bouton principal par **« Compléter la VF (22 manquants) »** ou **« Ouvrir »**. Une URL VF d'une série déjà présente en VO **ajoute une version** et ne crée pas de nouvelle série.
- **Variante lien d'épisode** : « C'est le lien de l'épisode 14 : on te propose toute la série. » avec [Seulement l'épisode 14]. Cela suppose que le moteur expose le numéro d'épisode de l'URL.
- **Ajout en lot** (coller plusieurs lignes) : le centre affiche un tableau d'aperçus compacts (cover, titre, épisodes, taille, version, statut local). Les séries « Déjà complètes » sont décochées par défaut. Pied de tableau : **« Télécharger 10 séries · ≈ 7 Go · 182 Go libres »**. Les lignes non reconnues sont signalées : « La ligne 3 n'est pas un lien DramaBox ». Après confirmation, le lot se range dans la file : il ne devient jamais une deuxième file.
- **États** :
  - **Chargement** : squelette 9:16. « Recherche de la série… », puis au-delà de 4 s : « Le site officiel met du temps à répondre… ».
  - **Mode sonde** : « Infos limitées : cette série n'est pas sur le site officiel. Les épisodes seront détectés pendant le téléchargement, sans contrôle de durée. » Bouton : « Télécharger quand même ».
  - **Lien invalide** (sous l'omnibar, texte conservé, partie fautive surlignée) : « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage, dramafren, ou le n° de série (ex. 41000105199). »
  - **Introuvable** : « On n'a trouvé cette série ni sur le site officiel ni à la source. »
  - **Réseau** : « Impossible de joindre DramaBox. » avec [Réessayer].
  - **Source indisponible** (sonde du dernier épisode en échec) : pastille rouge « Source indisponible pour le moment » ; le téléchargement reste possible, marqué « déconseillé ».
  - **Hors ligne** : « L'aperçu a besoin d'Internet. » avec [Garder le lien pour plus tard] (mis en file au retour).

### 3.4 Fiche série (centre) et inspecteur d'épisode

```
┌────────────────────────────────────────────────────────────────────────────────────┬──────────────────────────────────┐
│ ← Bibliothèque › One Night to Forever                                              │ ÉPISODES 40 ET 41             ✕  │
│ ┌──────┐ Qui Est la Véritable Mme Lafont ?                                         │ 2 sélectionnés · ≈ 24 Mo         │
│ │cover │ One Night to Forever · VF · n° 41000105199                                │ ─────────────────────────────    │
│ │144×  │ 62 épisodes · 1 h 32 · 1080p · 662 Mo                                     │ ! Épisode 40 · 1 min 19          │
│ │ 256  │ [VO (anglais)]  [VF ●]  [+ Ajouter une version ▾]                         │   Pas disponible à la source     │
│ │      │ Synopsis sur 2 lignes…………………………………………… Lire plus                          │   pour le moment.                │
│ └──────┘                                                                           │   Détails techniques ▸           │
│ ⚠ 60/62 · 1 échec (ép. 40) · 1 interrompu (ép. 41)  [ ↻ Réessayer les 2  R ]       │ ⏸ Épisode 41 · 1 min 28          │
│ ──────────────────────────────────────────────────────────────────────────         │   Interrompu à 40 %,             │
│ ■ Téléchargé 60 (dont ◇ 720p : 1)  ! Échec 1  ⏸ Interrompu 1   ← légende = filtres │   reprendra au bon octet.        │
│ Sélection : Tous · Aucun · Manquants · Échecs · Inverser   [ 40-41        ]        │ ─────────────────────────────    │
│  [ 1][ 2][ 3][ 4][ 5][ 6][ 7][ 8][ 9][10][11]{12◇}                                 │ [ ↻ Réessayer les 2       R ]    │
│  [13][14][15][16][17][18][19][20][21][22][23][24]                                  │ Retélécharger en… ▾              │
│  [25][26][27][28][29][30][31][32][33][34][35][36]                                  │ Supprimer les fichiers           │
│  [37][38][39]{40!}{41⏸}[42][43][44][45][46][47][48]                                │ ─────────────────────────────    │
│  [49][50][51][52][53][54][55][56][57][58][59][60]                                  │ (1 épisode : Lire ⏎, Afficher    │
│  [61][62]            2 sélectionnés · ≈ 24 Mo                                      │  dans le dossier, qualité,       │
│ ──────────────────────────────────────────────────────────────────────────         │  taille, origine, vérification)  │
│ FILM   Pas encore de film · 1 h 32 · 62 chapitres                                  │                                  │
│        ✓ ffmpeg   ! 2 épisodes manquants   ◇ ép. 12 en 720p                        │                                  │
│        [ Réparer puis créer le film ]   Film partiel…   Ré-encoder…                │                                  │
│ FICHIERS  C:\…\41000105199-one-night-to-forever-fr · 662 Mo                        │                                  │
│        [ Ouvrir le dossier  O ]   Supprimer…  Suppr                                │                                  │
│ DÉTAILS TECHNIQUES ▸     JOURNAL DE CETTE VERSION ▸                                │                                  │
└────────────────────────────────────────────────────────────────────────────────────┴──────────────────────────────────┘
```

- **But** : diagnostiquer et réparer une version, voir ses épisodes un par un, gérer ses versions, son film et ses fichiers.
- **Zones** :
  1. **En-tête compact** : cover 144×256 sur fond flouté, titre, titre VO, n° de série, méta, **onglets de version**, synopsis sur 2 lignes.
  2. **Bandeau de santé et action principale unique** (même logique que §3.2).
  3. **Barre de la grille** :
     - **légende avec compteurs, qui sert de filtre** : cliquer sur « Échec 1 » sélectionne et met en valeur les cases concernées ;
     - raccourcis de sélection : Tous · Aucun · Manquants · Échecs · Inverser ;
     - **champ de plage « 1-10, 28, 50- »** synchronisé dans les deux sens avec la grille.
  4. **Grille d'épisodes** : 12 par ligne, cases de 48 px, numéros « 1 » à « 62 ». Au-delà de 120 épisodes : cases de 36 px, et onglets de plages au-delà de 200.
  5. **Film** : état, pré-vol, remèdes (§3.5).
  6. **Fichiers** : chemin, taille, [Ouvrir le dossier], [Supprimer…].
  7. **Détails techniques** et **Journal de cette version** (repliés).
- **Inspecteur d'épisode** :
  - un épisode : « Épisode 28 · E028.mp4 », état en langage courant (« Téléchargé et vérifié · 2 min 14 · 1080p · 12,8 Mo · source dramafren »), puis [Lire] (Entrée), [Afficher dans le dossier], [Retélécharger en… ▾], [Réessayer] (en cas d'échec), [Supprimer le fichier] ;
  - en cours : « 45 % · 5,8/12,8 Mo · 3,1 Mo/s » ;
  - en échec : la raison, puis « Détails techniques » avec le message brut du moteur, copiable, sans URL signée ;
  - plusieurs épisodes : totaux et actions groupées.
- **Onglets de version** : `VO (anglais)` · `VF` · `+ Ajouter une version ▾`. Le menu liste les langues doublées (« VE · ≈ 700 Mo · Télécharger ») ; les autres sont désactivées avec leur raison (« Coréen : titre traduit seulement »). Chaque onglet a sa propre grille, sa taille et son film.
- **États** :
  - **Vide** : « Aucun épisode téléchargé pour l'instant. » avec [Tout télécharger · 62 épisodes].
  - **Chargement** : squelettes de l'en-tête et de la grille.
  - **Partiel** :
    - « 58/62 · 4 manquants (59 à 62) » ;
    - « 60 épisodes en 1080p, 1 en 720p » ;
    - « Durées non vérifiées : cette série n'est pas sur le site officiel ».
  - **Erreur** : « 2 épisodes en échec (40 et 41) ». Si le dossier est introuvable : [Le retrouver…], [Retélécharger], [Retirer].
  - **Hors ligne** : les actions réseau sont désactivées avec leur raison ; la lecture, le film et le dossier restent actifs.

### 3.5 Film : pré-vol, création, remèdes

- **But** : un clic quand tout va bien ; sinon, un refus transformé en choix.
- **Pré-vol** : il est calculé dès la sélection, sans ffmpeg (lecture des boîtes MP4) et affiché en liste de contrôle :
  - Épisodes : ✓ 62/62, ou « ! 2 manquants : 40, 41 » ;
  - Format : ✓ « 1080p homogène », ou « ◇ ép. 12 en 720p » ;
  - ffmpeg : ✓ « prêt (PATH) », ou « absent » ;
  - Espace : ✓ « 717 Mo requis · 182 Go libres » ;
  - Nom : « Qui Est la Véritable Mme Lafont.mp4 » (modifiable). S'il existe déjà : case « Remplacer le film existant », obligatoire, car le moteur écrase sans prévenir ;
  - Chapitres : un par épisode (activé).
- **Création** : quand tout est vert, F ou un clic lance la fusion directement. **La progression s'affiche dans le bouton**, par exemple « Assemblage… 38/62 », sans modale, en 6 s environ. Le job apparaît aussi dans la voie « film » du dock.
- **Remèdes**, du plus recommandé au moins recommandé :

  | Blocage | Boutons |
  |---|---|
  | Épisodes manquants | **[Les télécharger puis créer le film]** · [Créer un film partiel « … (épisodes 1-39, 42-62) »] |
  | Qualités mélangées | **[Retélécharger l'ép. 12 en 1080p (~13 Mo)]** · [Tout ré-encoder (plusieurs minutes)] |
  | Les deux à la fois | **[Réparer puis créer le film]** enchaîne réessai, retéléchargement et fusion |
  | ffmpeg absent | « Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans. » avec `winget install Gyan.FFmpeg` / `pip install imageio-ffmpeg` [Copier] et [Revérifier] |
  | Durée incorrecte | « Le film créé n'a pas la durée attendue (1 h 29 au lieu de 1 h 32). » avec [Réessayer] et [Détails techniques] |

- **Après** : carte « Film prêt · 1 h 32 · 717 Mo · 62 chapitres » avec [Lire le film] et [Afficher dans le dossier]. Une seule fois, sans insister : « Libérer 684 Mo en supprimant les épisodes ? Le film reste. »
- **États du film** : Aucun · Prêt · Partiel (« Film partiel (épisodes 1-10). 52 épisodes ajoutés depuis. » avec [Recréer le film complet]) · Obsolète · Fichier disparu · Hors bibliothèque (chemin `-f` en dehors du dossier : seul « Ouvrir le dossier » est proposé).
- **Enchaînement « film à la fin »** : comme la CLI, le film n'est créé que s'il n'y a aucun échec. Sinon, le dock affiche « Film non créé : il manque l'épisode 40 » avec [Réessayer puis créer].

### 3.6 Lecteur (« mode théâtre » dans le centre)

- **But** : regarder un épisode ou le film sans quitter le poste.
- **Zones** :
  - le centre passe au noir, avec une vidéo verticale ajustée à la hauteur (environ 460×820 à 1440×900) ;
  - le dock se replie sur la barre d'état ;
  - l'inspecteur affiche la liste des épisodes (vu, en cours, non téléchargé) ou les chapitres du film, marqués aussi sur la barre de lecture ;
  - en bas de la vidéo : « Épisode 14 sur 62 », précédent / suivant, vitesse, [Ouvrir dans le lecteur par défaut].
- **Interactions** :
  - enchaînement automatique : « Épisode suivant dans 5 s » avec [Annuler] (en texte seul si reduced-motion) ;
  - position mémorisée : « Reprise à 1:12 » avec [Revenir au début] ;
  - un épisode encore en téléchargement est lisible dès qu'il passe à « terminé ».
- **Clavier** : Espace ou K (lecture/pause), ← → (5 s), Maj+← → (épisode ou chapitre), F (plein écran), M (muet), Échap (quitter le mode théâtre).
- **États** :
  - **Fichier absent** : « Ce fichier n'est plus dans le dossier. » avec [Retélécharger l'épisode].
  - **En cours** : « Cet épisode est encore en téléchargement (45 %). »
  - **Non téléchargé** : « Épisode 59 non téléchargé : on passe au 60. »
  - **Codec illisible** (HEVC, par exemple) : « Ton navigateur n'arrive pas à lire cette vidéo. » avec [Ouvrir dans le lecteur par défaut].
  - **Hors ligne** : identique, car tout est local.
  - Le lecteur est coupé avant toute suppression, pour éviter le verrou de fichier sous Windows.

### 3.7 Dock d'activité, barre d'état et page Activité

- **But** : superviser en périphérie des dizaines de jobs (file persistée : une série à la fois, 3 épisodes en parallèle, et une voie film indépendante).
- **Barre d'état** (toujours visible, 32 px, chiffres tabulaires) :
  - `● Moteur` ;
  - `↓ 1 actif · 1 en file · 34/124 ép. · 12,4 Mo/s · ~1 min 50` ;
  - `⚠ 1 problème` ;
  - `C: 182 Go libres` ;
  - `ffmpeg ✓` ;
  - un clic sur un segment ouvre l'onglet correspondant.
- **Panneau** (T), avec 4 onglets :
  1. **File (n)** :
     - groupes repliables En cours · En file · En pause · Terminés récemment ;
     - une ligne par job : mini-cover, titre et version, phase (« Détection des épisodes… 23 trouvés », « Téléchargement », « Mise en pause… », « Annulation… »), ruban, « 34/62 · 432/684 Mo · 12,4 Mo/s · ~40 s », puis ⏸ ✕ ⋯ ;
     - réordonnancement par Alt+↑/↓ ou « Passer en premier », sans glisser-déposer obligatoire ;
     - barre d'outils : [Tout mettre en pause] [Tout reprendre] [Effacer les terminés (tes fichiers restent)].
  2. **Problèmes (n)** : les problèmes des jobs en direct, avec leurs actions. C'est un extrait en direct du panneau « À traiter ».
  3. **Journal** : lignes structurées (heure, série, épisode, niveau), filtrables par job et par niveau, en police mono, [Copier]. **Les URL signées n'y figurent jamais.**
  4. **Historique** : les 50 derniers jobs, avec leur résultat (« 62/62 vérifiés · 684 Mo · 1 min 38 s » ou « 2 échecs »), [Réessayer] et [Restaurer] pour une suppression récente.
- **Sélection d'un job** : l'inspecteur affiche le détail du job (paramètres, frise des phases, erreurs par épisode, commande équivalente).
- **Page Activité** (G A) : la même chose en plein centre, sous forme de tableau (série·version, type, statut, progression, débit, temps restant, créé le, actions), avec sélection multiple. C'est pour les grosses sessions en lot.
- **Fin d'une série** : toast et notification Windows (demandée au premier téléchargement terminé, pas au démarrage) : « One Night to Forever (VF) est prêt · 62 épisodes vérifiés, 684 Mo », avec [Lire], [Créer le film] et [Ouvrir le dossier].
- **États** :
  - **Vide** : le dock reste replié, et la barre d'état affiche « Rien en cours · dernière activité il y a 2 h ».
  - **Pause ou annulation lente** : état transitoire « Mise en pause… ». Sur un réseau figé, cela peut prendre jusqu'à 30-45 s, et on le dit.
  - **Disque plein** : « Arrêté : disque plein (il manque 312 Mo sur C:). Libère de la place puis reprends. »
  - **Erreurs répétées** : « Arrêté après plusieurs erreurs de suite. Vérifie ta connexion. »
  - **Hors ligne** : « Hors ligne · jobs en pause · nouvel essai dans 12 s » avec [Réessayer maintenant] ; aucun échec n'est compté.
  - **Moteur injoignable** : lecture seule.

### 3.8 À traiter (centre)

- **But** : une boîte de réparation, où chaque type de problème a une action en masse.
- **Zones** : un en-tête « 3 sujets · 7 épisodes · 4 séries » avec **[Tout réparer]** (actions sûres uniquement : réessayer, reprendre, compléter), puis des groupes repliables :

  | Groupe | Contenu | Action de groupe |
  |---|---|---|
  | Échecs réessayables | « 5 épisodes dans 3 séries » | **Réessayer tout** |
  | Indisponibles à la source | Pas de réessai automatique | Réessayer quand même · Ignorer |
  | Interrompus | `.part` présents, aucun job | **Tout reprendre** |
  | Incomplètes | Épisodes jamais demandés ou nouveaux | **Compléter tout · ≈ 1,2 Go** |
  | Qualités mélangées | Bloque le film sans ré-encodage | **Retélécharger en 1080p (3 ép.)** |
  | Fichiers disparus | `done` dans le manifest, fichier absent | Retélécharger |
  | Films obsolètes ou partiels | Épisodes ajoutés depuis le film | Recréer |
  | Non vérifiées (mode sonde) | Information | Ignorer |
  | Dossiers illisibles | Manifest corrompu | Voir · Retirer |

  Chaque ligne affiche la mini-cover, « titre · version », une description courte et une action. Cocher des lignes permet d'agir sur une partie seulement.
- **États** :
  - **Vide** : « Rien à traiter. Ta collection est complète et vérifiée. »
  - **Hors ligne** : les actions réseau sont désactivées, avec la raison.

### 3.9 Palette de commandes (Ctrl+K)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ⌕ https://www.dramaboxdb.com/fr/movie/41000105199/… 720p 1-10 film       │
│   Compris : [VF] [720p] [épisodes 1-10 · 10] [film à la fin]             │
│ ─────────────────────────────────────────────────────────────────────    │
│ AJOUTER                                                                  │
│ ▸ ↓ Télécharger « Qui Est la Véritable Mme Lafont ? » · VF         ⏎     │
│     10 épisodes · ≈ 70 Mo · film partiel « … (épisodes 1-10).mp4 »       │
│     sdg fetch 41000105199 --lang fr -q 720p -e 1-10 --film   Copier      │
│   ⓘ Déjà dans ta bibliothèque : VO complète (62/62)                      │
│ ─────────────────────────────────────────────────────────────────────    │
│ (texte « lafont » → SÉRIES : titres toutes langues + n° de série ;       │
│  ACTIONS : Réessayer tous les échecs (3), Créer le film de…, Aller à…)   │
│ ↑↓ naviguer · ⏎ exécuter · Ctrl+⏎ variante · Tab options · Échap         │
└──────────────────────────────────────────────────────────────────────────┘
```

- **But** : un point d'entrée unique pour ajouter, trouver et agir. C'est la forme dépliée de l'omnibar.
- **Modes, détectés automatiquement** :
  - **lien** : ajout, avec aperçu compact ;
  - **texte** : séries (titres de toutes les langues), filtres (« Filtrer : Incomplètes »), actions ;
  - **11 chiffres** : n° de série, local ou à ajouter ;
  - **« > »** : actions seulement.
- **Actions disponibles** : Réessayer tous les échecs (n) · Tout reprendre / Tout mettre en pause · Créer le film de… · Ouvrir le dossier de… / du dossier de téléchargements · Aller à : À traiter, Activité, Réglages › Films · Basculer : Liste/Affiches, inspecteur, dock, thème · Copier la commande de… · Exporter les liens de….
- **Pas de recherche en ligne par titre** (le moteur ne sait pas le faire). Sans résultat, la palette affiche : « Aucune série locale « xyz ». Colle un lien DramaBox pour l'ajouter. »
- **États** : lien invalide (message sous le champ, texte conservé), jeton de syntaxe inconnu (surligné en ambre, non bloquant : « “4k” ignoré, qualités : 1080p, 720p, 540p »), hors ligne (l'ajout devient « Garder pour plus tard »).

### 3.10 Dialogue de suppression

- **But** : supprimer en connaissance de cause, avec l'espace libéré chiffré et une annulation possible.
- **Contenu** : « Que veux-tu supprimer ? », avec un choix unique :
  - ( ) Seulement le film (717 Mo) ;
  - ( ) Seulement les épisodes (684 Mo), le film reste ;
  - ( ) Tout : épisodes, film et dossier (1,4 Go) ;
  - (option) « Nettoyer les fichiers partiels (.part, 12 Mo) ».

  Pour plusieurs séries : « 5 séries · 3,4 Go » et la liste. Boutons : [Supprimer] (danger, écarté de 8 px) et [Annuler] (focus par défaut).
- **Après** : toast « Supprimé · 684 Mo libérés » avec [Annuler] pendant 10 s (prolongé tant qu'il a le focus ou qu'il est survolé). La suppression reste restaurable 5 min depuis Historique, grâce à la corbeille interne `.sdg/trash`.
- **États** :
  - **Série occupée** : « Un téléchargement est en cours sur cette série. » avec [Mettre en pause puis supprimer].
  - **Fichier verrouillé** : « Impossible de supprimer E014.mp4 : il est ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. »
  - **Partiel** : « 60 fichiers supprimés sur 62. » avec [Voir lesquels].

### 3.11 Réglages et santé

- **Navigation interne** : Général · Téléchargement · Films · Affichage · Clavier · Notifications · Stockage · Avancé · Santé. Enregistrement automatique avec « Enregistré. » en ligne.
- **Contenu** :
  - **Général** : dossier de téléchargement (absolu, par défaut `%USERPROFILE%\Videos\ShortDramaGen`), version préférée (« Français si disponible, sinon VO »), qualité (Meilleure 1080p), film à la fin, reprise automatique au démarrage.
  - **Téléchargement** : téléchargements simultanés (3, recommandé ; au-delà, l'avertissement « la source risque de te bloquer »), séries en parallèle (V2).
  - **Films** : état de ffmpeg (chemin et origine : PATH, imageio ou manuel), commandes d'installation, chapitres par défaut.
  - **Affichage** : thème (sombre, clair, système), densité, titre affiché (version préférée ou VO), vue par défaut.
  - **Clavier** : liste des raccourcis, désactivation des raccourcis à une touche.
  - **Notifications** : Windows (oui/non), annonces lecteur d'écran (paliers / fin seulement / aucune).
  - **Stockage** : espace par série, purge des `.part`, durée de la corbeille.
  - **Avancé** : port, arrêt automatique, journal.
  - **Santé** : version du moteur, dossier accessible en écriture, espace disque, ffmpeg, site officiel et source joignables.
- **Santé visible ailleurs** : une pastille sur ⚙ et un message **seulement là où le problème bloque** (par exemple sur le bouton Film).
- **États** :
  - **Dossier non inscriptible** : « Choisis-en un autre. »
  - **Changement de dossier pendant un job** : « Mets les téléchargements en pause d'abord. »
  - **Installation de ffmpeg en échec** : [Réessayer] et [Méthode manuelle].

### 3.12 Premier lancement et bibliothèque vide

- Le poste démarre **au calme** : dock replié sur la barre d'état, inspecteur masqué, compteurs de la barre latérale à zéro masqués.
- **Centre** : l'omnibar en grand, déjà focalisé. « Ta bibliothèque est vide. Colle le lien d'une série DramaBox : on récupère tous les épisodes, vérifiés, jusqu'en 1080p. »
- En dessous :
  - les formats acceptés ;
  - [Essayer avec un exemple] (One Night to Forever) ;
  - une carte « Réglages rapides » sur une seule ligne : dossier · version préférée · ffmpeg (optionnel : « Films : ffmpeg manquant » avec [Installer]).
- Si des dossiers créés par la CLI existent : « 3 séries trouvées sur le disque », affichées immédiatement, puisque la bibliothèque lit les manifests.
- Une astuce discrète dans le coin : « Ctrl+V fonctionne n'importe où · Ctrl+K pour tout le reste · ? pour les raccourcis ».

### 3.13 Mobile 390 (« télécommande ») et responsive

```
┌────────────────────────────────┐   ┌────────────────────────────────┐
│ ◆ ⌕ Colle ou cherche… [Coller] │   │ ‹  Qui Est la Véritable Mme…  ⋯│
│ (Toutes 54)(En cours 2)(Incom› │   │ ┌────┐ One Night to Forever    │
│ ────────────────────────────── │   │ │cov.│ VF · 62 ép. · 1 h 32    │
│ ▯ Qui Est la Véritable Mme…    │   │ │9:16│ [VO] [VF●] [+]          │
│ ▯ VO·VF ▰▰▰▰▱▱ 34/62 ↓ 55 %    │   │ └────┘                         │
│ ────────────────────────────── │   │ ⚠ 60/62 · 2 à réparer          │
│ ▯ Série B                      │   │ ── Épisodes ─── 6 par ligne ── │
│ ▯ VO ▰▰▰▰▰▰ 62/62 · Film ✓     │   │ [ 1][ 2][ 3][ 4][ 5][ 6]       │
│ ────────────────────────────── │   │ [ 7][ 8][ 9][10][11][12]       │
│ ▯ Série D                      │   │ …   tuiles 52 px               │
│ ▯ VE ▰▰▰▰!▰ 79/80 · 1 échec    │   │ [37][38][39][40!][41⏸][42]     │
│ ────────────────────────────── │   │ …                              │
│ …                              │   │ ── Film ─────────────────────  │
│                                │   │ Film : 2 épisodes manquants    │
│ ↓ Mme Lafont · 34/62 · ~40 s ⏸ │   │                                │
│ ────────────────────────────── │   │ ┌────────────────────────────┐ │
│ Biblio  À traiter ⊕ Activité ⚙ │   │ │ ↻ Réessayer les 2 épisodes │ │
│          (3)    Ajouter  (1)   │   │ └────────────────────────────┘ │
└────────────────────────────────┘   └────────────────────────────────┘
```

Sur mobile, le poste de pilotage devient une **télécommande** : même modèle, zones empilées.
- L'omnibar reste en haut, avec un bouton [Coller].
- Les vues intelligentes deviennent des puces défilantes.
- La liste devient compacte (cover 36×64, titre, ruban, badge), avec une vue Affiches en 3 colonnes.
- Le dock devient un **mini-lecteur d'activité** au-dessus de la barre du bas (façon « lecture en cours »).
- L'inspecteur devient une **page plein écran**, avec l'action principale collée en bas.
- La palette devient une feuille de recherche plein écran.
- Barre du bas : Bibliothèque · À traiter · **Ajouter** · Activité · Réglages (5 cibles de 78 px de large).
- Sont masqués (et non désactivés) : Ouvrir le dossier, ffmpeg, la liste dense, l'aide des raccourcis.
- *Réserve* : l'accès depuis un téléphone suppose le mode réseau local, exclu de la V1 faute d'authentification. En V1, cette mise en page sert aux fenêtres étroites (Edge `--app` réduit) et prépare la V1.1.

| Zone | ≥ 1366 (1440) | 1024-1365 (1280) | 600-1023 | < 600 (390) |
|---|---|---|---|---|
| Barre latérale | 232 px | Rail de 56 px (icônes, infobulles, noms accessibles) | Rail | Barre du bas |
| Inspecteur | Ancré, 360 px | Ancré, 320 px ; en superposition sous 1180 px | En superposition (épinglable) | Page plein écran |
| Dock | Panneau de 240 px et barre d'état | Idem, replié par défaut | Barre d'état seule, panneau en superposition | Mini-barre et page Activité |
| Bibliothèque | Liste dense, ou affiches en 4 à 7 colonnes | Liste (colonnes Taille et Ajoutée masquées), ou 4-5 colonnes | Liste compacte, ou 3-4 colonnes | Liste compacte, ou 3 colonnes (112 px) |
| Grille de la fiche | 12 par ligne, 48 px | 10 par ligne, 48 px | 8 par ligne | 6 par ligne, 52 px (6×52 + 5×8 = 352 px pour 358 px utiles) |
| Lecteur | Mode théâtre et liste dans l'inspecteur | Idem, liste rétractable | Plein centre | Plein écran natif, liste en feuille du bas |
| Gouttières | 32 px | 24 px | 24 px | 16 px, aucun défilement horizontal |

### 3.14 Carte des erreurs : où chacune apparaît dans le poste

| Cas moteur | Lieu | Message | Action |
|---|---|---|---|
| URL invalide | Sous l'omnibar ou la palette | « Ce lien n'est pas reconnu. Liens acceptés : … » | Texte conservé, exemples |
| Série absente du site officiel (mode sonde) | Aperçu, puis phase du job dans le dock | « Infos limitées… » puis « Détection des épisodes… 23 trouvés » | Télécharger quand même |
| Introuvable partout | Aperçu | « On n'a trouvé cette série ni sur le site officiel ni à la source. » | Vérifier le lien |
| Langue indisponible | **Évitée** : absente des puces de version | « Coréen : titre traduit seulement » | Choisir une version doublée |
| Épisode indisponible à la source | Case (hachures), Problèmes, À traiter | « Pas disponible à la source pour le moment. » | Réessayer (pas de boucle automatique) |
| URL signée expirée | Nulle part (re-résolution automatique) | Seulement si elle échoue : « Lien de téléchargement expiré, impossible d'en obtenir un nouveau pour l'instant. » | Réessayer |
| Mauvais épisode renvoyé (chemin CDN) | Nulle part tant que la source suivante réussit | Sinon : « La source a renvoyé une vidéo qui n'est pas cet épisode. » | Réessayer |
| Vérification de durée échouée | Case, inspecteur d'épisode | « Le fichier reçu ne correspond pas : 1 min 12 au lieu de 2 min 05. » | Réessayer |
| Erreur réseau | Nulle part tant que les réessais réussissent, puis Problèmes | « Connexion perdue · 3 échecs » | Réessayer les échecs |
| Hors ligne | Barre d'état, dock | « Hors ligne · nouvel essai dans 12 s » | Réessayer maintenant |
| Interruption (fermeture, Ctrl+C, veille) | Bandeau du dock au démarrage, badge « Interrompu » | « 2 téléchargements interrompus (34/62 et 0/48) » | Tout reprendre |
| ffmpeg absent | Pastille sur ⚙, pré-vol du film | « Pour créer un film, il faut ffmpeg… » | Commandes à copier |
| Qualités mélangées | Pré-vol, À traiter | « L'épisode 12 est en 720p, les autres en 1080p. » | Retélécharger en 1080p / Ré-encoder |
| Épisodes manquants pour le film | Pré-vol | « Il manque 2 épisodes (40 et 41). » | Télécharger puis créer / Film partiel |
| Plusieurs langues = plusieurs dossiers | Aucune erreur : une ligne, plusieurs puces de version | — | + Ajouter une version |
| Disque plein, fichier verrouillé, dossier déplacé, manifest corrompu | Dock (arrêt), dialogue, À traiter | Voir §3.7, §3.10, §3.8 | Libérer, fermer, retrouver, retirer |

Chaque message a un lien « Détails techniques » : cause brute, n° de série, épisode, horodatage, et [Copier].

---

## 4. Les six parcours dans le poste

Convention : 1 interaction = 1 clic, 1 raccourci, 1 validation ou 1 collage. Taper une recherche compte pour 1. Le défilement ne compte pas.

| Parcours | Clavier | Souris | Ce qu'on voit |
|---|---|---|---|
| **(a) URL → aperçu → tout télécharger** | **2** : Ctrl+V (n'importe où), Entrée | **3** : clic sur l'omnibar, collage, clic sur « Tout télécharger » | Aperçu en moins de 2 s dans l'inspecteur, bouton focalisé. Après Entrée : la série apparaît dans la liste, la barre d'état s'allume, l'omnibar est prêt pour le lien suivant. Avec le film : Ctrl+Entrée (toujours 2). Avec des options : Ctrl+K, collage de `… fr 720p 1-10 film`, Entrée (3). Mobile : [Coller], puis « Tout télécharger » (2, +1 pour la permission la première fois). |
| **(b) Suivre sans rester dessus** | **0** | **0** | Barre d'état (« 34/124 ép. · 12,4 Mo/s · ~1 min 50 »), titre d'onglet « (55 %) », anneau du favicon, ruban de la ligne. Détail : T ou clic sur la barre d'état (1). Fin : notification Windows et toast avec [Lire], [Créer le film], [Ouvrir le dossier]. |
| **(c) Retrouver une série parmi 50 et plus** | **3** : Ctrl+K, « lafont », Entrée | **2-3** : clic sur une vue intelligente (ex. Incomplètes), clic sur la ligne | Résultats à chaque frappe, en moins de 100 ms, avec « trouvé dans le titre VF ». Moins de 5 s au total. |
| **(d) Gérer une série** | voir le détail ci-dessous | voir le détail ci-dessous | L'inspecteur porte tout ; la fiche sert au détail par épisode |
| **(e) Regarder** | **1** : L sur la ligne ciblée (« Reprendre · Ép. 14 ») ; Entrée sur une case de la grille | **1** : bouton principal de l'inspecteur ou clic sur une case terminée | Mode théâtre, lecture en moins de 1 s, enchaînement automatique. Film : bouton « Lire le film » (1). |
| **(f) Reprendre après fermeture ou coupure** | **0 à 1** | **0 à 1** | Voir le détail ci-dessous |

**Détail de (d)**

| Sous-tâche | Clavier | Souris |
|---|---|---|
| Réessayer les échecs d'une série | R (1) | Bouton principal (1) |
| Réessayer tous les échecs de la collection | G P, Entrée sur « Tout réparer » (3) | À traiter, puis « Réessayer tout » (2) |
| Compléter une série | C (1) | Bouton principal (1) |
| Compléter toutes les incomplètes | Vue Incomplètes (clic), Ctrl+A, C (3) | Filtre, « Tout cocher », « Compléter · ≈ 1,2 Go » (3) |
| Ajouter une autre langue | — | « + VE » dans l'inspecteur, puis Entrée dans l'aperçu (2) |
| Créer le film | F (1 si le pré-vol est vert ; +1 pour un choix de remède) | Bouton « Créer le film » (1-2), environ 6 s, progression dans le bouton |
| Retélécharger un épisode en 1080p | Fiche, case, Maj+F10, « Retélécharger en 1080p » (3) | Case, puis bouton de l'inspecteur (2) |
| Ouvrir le dossier | O (1) | Bouton Dossier (1) : l'Explorateur s'ouvre, fichier présélectionné si on part d'un épisode |
| Supprimer | Suppr, choix de portée, Entrée (3) | ⋯, Supprimer…, choix, Supprimer (3-4). Annulation possible 10 s. |

**Détail de (f)**

| Scénario | Comportement | Interactions |
|---|---|---|
| Onglet fermé, moteur actif | Les jobs continuent ; à la réouverture, l'état est exact | 0 |
| Moteur relancé (PC redémarré) | Reprise automatique (réglage par défaut) ; le bandeau du dock annonce « 2 téléchargements interrompus ont repris » avec [Mettre en pause] | 0 (1 si la reprise automatique est désactivée : [Tout reprendre]) |
| Coupure Internet | File en pause « Hors ligne », aucun échec compté, reprise automatique à l'octet près | 0 |
| Moteur injoignable | Lecture seule, reconnexion toutes les 5 s | 0-1 |
| Lien expiré | Re-résolution invisible | 0 |
| Fichier supprimé dans l'Explorateur | À traiter › « Fichiers disparus », puis [Retélécharger] | 1-2 |

---

## 5. Interactions signatures

### 5.1 L'omnibar « Colle ou cherche » et sa mini-syntaxe CLI

- **Un champ, trois usages** : ajouter (lien ou n° de série), trouver (titres de toutes les langues), agir (commandes). Ctrl+V hors champ produit exactement le même effet que coller dans l'omnibar.
- **Reconnaissance locale instantanée** (mêmes règles que `inputs.py`), avant tout appel réseau : « ✓ Lien DramaBox · n° 41000105199 · fr ». Le serveur confirme ensuite.
- **Mini-syntaxe** : des jetons après le lien ou le n° de série préremplissent les options et s'affichent en puces « Compris : … » :

  | Jeton | Effet |
  |---|---|
  | `fr`, `es`, `vo`… | Version |
  | `1080p`, `720p`, `540p`, `best` | Qualité |
  | `1-10,28,50-` (tolère « – », les espaces, « 50-62 ») | Épisodes |
  | `film` | Film à la fin |

  La palette affiche la commande équivalente et les conséquences. Par exemple, `-e 1-10` avec `film` donne le film partiel « … (épisodes 1-10).mp4 », comme dans le moteur.
- **Tolérance** : un jeton inconnu est surligné mais ne bloque pas. Le texte n'est jamais effacé en cas d'erreur.
- **Lot** : plusieurs lignes collées ouvrent l'ajout en lot au centre.

### 5.2 L'inspecteur contextuel

On sélectionne, on voit, on agit, sans navigation. La table du §2.4 garantit que la même zone répond toujours à la question « que puis-je faire avec ce que j'ai sélectionné ? ». L'aperçu d'ajout est prioritaire mais **rend la main** au contexte précédent. L'épinglage fige le contenu. Le bouton principal change selon l'état, et un seul bouton a le poids « principal » à un instant donné.

### 5.3 Le ruban de complétude

- Une barre de N micro-segments, un par épisode. Il apparaît partout : lignes de la bibliothèque, cartes d'affiches, lignes du dock, inspecteur, mini-barre mobile.
- Couleurs :
  - vert = téléchargé ;
  - violet qui se remplit = en cours ;
  - rouge **plus haut d'un pixel, avec une encoche** = échec ;
  - hachures grises = indisponible ;
  - ambre = interrompu, disparu ou 720p isolé ;
  - contour gris = à télécharger.
- Espace de 1 px entre segments jusqu'à 80 épisodes. Au-delà de 150, les épisodes sont regroupés par paquets, le plus mauvais statut gagnant.
- Le survol affiche « Épisode 40 · Échec ».
- Le ruban est `aria-hidden`. Il est toujours doublé d'un texte (« 58/62 · 1 échec ») : la couleur n'est jamais le seul signal.
- Il se met à jour en direct via SSE, au plus 4 fois par seconde.

### 5.4 La grille-sélecteur d'épisodes (sélection par plages)

- **Un seul composant** pour le statut, la sélection et la progression, réutilisé dans les options de l'aperçu, la fiche et l'inspecteur.
- **Gestes** :
  - clic : cocher ou décocher (dans l'aperçu), ou action de la case (dans la fiche) ;
  - Maj+clic : plage ;
  - Ctrl+clic : ajout ;
  - glisser : lasso ;
  - raccourcis Tous · Aucun · Manquants · Échecs · Inverser ;
  - la légende sert de filtre.
- **Champ « 1-10, 28, 50- »** synchronisé dans les deux sens avec la grille. Résumé en direct : « 23 épisodes · ≈ 270 Mo ». La sélection est conservée quand on change de qualité.
- **Clavier** : `role="grid"`, un seul arrêt de tabulation, flèches, Début/Fin, Espace (sélection), Maj+flèches (étendre), Entrée (action), Maj+F10 (menu).
- **Nom accessible complet** : « Épisode 14, 2 min 05, téléchargé et vérifié, 13,2 Mo, 1080p ».
- **Rendu** : chaque case est un `<button data-status data-quality style="--p:.42">`. Une mise à jour de progression ne touche que `--p` des cases actives, ce qui reste fluide jusqu'à 1000 cases.

### 5.5 La progression en direct, du plus discret au plus détaillé

Titre de l'onglet et favicon, puis barre d'état, puis ruban de la ligne, puis ligne du dock, puis remplissage des cases de la fiche.

- **Règles** :
  - l'unité est l'épisode (les octets sont secondaires), donc **la barre ne recule jamais** ;
  - le temps restant n'est publié qu'après 3 s de mesure, lissé (moyenne mobile exponentielle) et arrondi (« environ 40 s », « moins d'une minute ») ;
  - chiffres tabulaires, pour que les compteurs ne tremblent pas ;
  - un échec ne bloque pas la série : les autres épisodes continuent.
- **Lecteur d'écran** : une seule région `status`, avec des annonces au lancement, à 25, 50 et 75 %, à la fin, et pour chaque échec regroupé. Jamais une annonce par épisode, et au moins 10 s entre deux annonces.
- **E001 est lisible pendant que la suite arrive** : une case devient cliquable dès qu'elle passe à « terminé ».

### 5.6 La fusion en film avec pré-vol

La liste de contrôle est calculée dès la sélection (épisodes, format, ffmpeg, espace, nom). Quand tout est vert, la fusion part en un geste (F), avec la progression **dans le bouton** pendant environ 6 s. Un refus devient des boutons classés du plus recommandé au moins recommandé (« Retélécharger l'ép. 12 en 1080p » avant « Ré-encoder »). Remplacer un film existant demande une case explicite. Une fois le film prêt, l'interface propose une seule fois de libérer 684 Mo.

### 5.7 « À traiter » et la réparation en masse

Tous les problèmes de la collection sont rangés par type, chaque groupe a son action (§3.8). « Tout réparer » n'exécute que des actions sûres. Combiné aux vues intelligentes et à Ctrl+A, cela permet par exemple de retélécharger en 1080p tous les épisodes en 720p en 3 gestes, depuis la vue « Qualités mélangées ».

### 5.8 Actions en masse et annulation

La sélection multiple (cases, Maj+clic, Ctrl+A sur le résultat filtré) transforme l'inspecteur en barre d'actions **chiffrées** : « Supprimer les épisodes, garder les films · libère 2,1 Go ». Les actions destructives affichent un toast [Annuler] pendant 10 s, restaurable 5 min depuis Historique. Les toasts d'une même vague sont regroupés (« 3 épisodes en échec », pas trois toasts), 3 au maximum à l'écran, et tous sont consignés dans Historique.

### 5.9 Le clavier comme pilote automatique

| Portée | Touche | Action |
|---|---|---|
| Global | **Ctrl+K** | Palette et omnibar |
| Global, hors champ | **Ctrl+V** | Coller un lien, ce qui ouvre l'aperçu |
| Global | F6 / Maj+F6 | Zone suivante / précédente |
| Global | G puis B / A / P / R | Bibliothèque / Activité / À traiter / Réglages |
| Global | T · I · Ctrl+B | Dock · Inspecteur · Barre latérale |
| Global | `?` · Échap | Aide des raccourcis · Fermer ou remonter |
| Liste | ↑↓ ou J/K · Entrée · X ou Espace · Maj+↑↓ · Ctrl+A · V | Naviguer · Fiche · Cocher · Étendre · Tout · Liste/Affiches |
| Série ciblée | R · C · F · L · O · P · Suppr · Maj+F10 | Réessayer · Compléter · Film · Lire · Dossier · Pause/Reprendre · Supprimer · Menu |
| Aperçu | Entrée · Ctrl+Entrée · Maj+Entrée | Tout télécharger · Avec film · Options |
| Dock | Alt+↑/↓ · P · Suppr | Réordonner · Pause · Annuler (annuler ne supprime aucun épisode terminé) |
| Lecteur | Espace/K · ←/→ · Maj+←/→ · F · M · Échap | Lecture · 5 s · Épisode ou chapitre · Plein écran · Muet · Quitter |

- **AZERTY** : les raccourcis lisent `event.key` ; `?` s'obtient par Maj+, et fonctionne. On n'utilise ni `/`, ni `` ` ``, ni `[`, ni les chiffres en raccourci principal.
- **Collisions avec le navigateur évitées** : pas de Ctrl+J (téléchargements de Chrome et Edge), pas de Ctrl+Maj+P ni Ctrl+Maj+N.
- Les raccourcis à une touche sont inactifs dans les champs et désactivables (WCAG 2.1.4). Chaque bouton affiche son raccourci, et l'aide (`?`) est toujours au même endroit.

---

## 6. Direction visuelle

### 6.1 Ambiance

**« Salle de contrôle de nuit »**, dans la continuité du bleu nuit de dramafren. L'interface est sobre et plate, découpée en panneaux séparés par des filets de 1 px plutôt que par des ombres. **Ce sont les covers qui apportent la couleur.** Le bleu d'accent est rare : focus, bouton principal, sélection. Les états ont leurs propres couleurs, et l'accent ne sert jamais pour « en cours », afin qu'on ne confonde pas sélection et progression.

**Thème sombre par défaut**, justifié :
- le contenu est vidéo et on regarde dans l'appli ;
- l'utilisateur a déjà ce repère avec dramafren ;
- le poste reste ouvert en arrière-plan ou sur un second écran pendant de longues sessions ;
- les covers ressortent mieux sur un fond sombre.

Un thème clair existe avec les mêmes rôles de couleur (réglage : sombre, clair ou système).

### 6.2 Palette (sombre)

| Jeton | Hex | Usage | Contraste |
|---|---|---|---|
| `bg` | `#0B1220` | Fond de l'application, barre latérale, dock | — |
| `surface` | `#131C2E` | Centre, inspecteur | — |
| `raised` | `#1B2640` | Survol, cartes, menus, palette | — |
| `selected` | `#1C2D52` | Ligne sélectionnée (avec une barre d'accent de 2 px à gauche) | texte 12:1 environ |
| `line` | `#24304A` | Filets entre panneaux (décoratifs) | — |
| `border-control` | `#6A7A99` | Contours des champs, des cases « à télécharger », pointillés | 4,3:1 sur `bg` (≥ 3:1) |
| `text` | `#E8ECF4` | Texte principal | 15,8:1 sur `bg` |
| `text-muted` | `#A3AEC4` | Méta, titre VO, aides | 8,4:1 sur `bg` |
| `accent` | `#5B9BFF` | Bouton principal (texte `#0B1220` : 6,8:1), liens, sélection | 6,8:1 sur `bg` |
| `accent-strong` | `#2F6FE0` | Variante du bouton si le texte doit être blanc (4,7:1) | — |
| `focus` | `#8FC1FF` | Anneau de focus de 2 px, décalé de 2 px | 10:1 sur `bg` |
| `success` | `#3DD68C` | Téléchargé et vérifié, film prêt | 10:1 sur `bg` |
| `active` | `#A78BFA` | En cours ou résolution (violet, comme Sonarr) | ≈ 6,9:1 sur `bg`, ≈ 6,3:1 sur `surface` |
| `warning` | `#F5B544` | Incomplète, interrompu, 720p isolé, fichier disparu, non vérifié | 10,3:1 sur `bg` |
| `danger` | `#FF6B6B` | Échec, suppression | 6,8:1 sur `bg` |
| `hatch` | `#3A4660` sur `#6A7A99` | Indisponible à la source (hachures) | forme et contraste de bord ≥ 3:1 |

Thème clair, mêmes rôles : `bg #F4F6FB`, `surface #FFFFFF`, `raised #EEF2F9`, `line #D9E0EC`, `text #0F172A`, `text-muted #475569`, `accent #1F5FD6`, `active #6D4ED8`, `success #0F8A57`, `warning #A86200`, `danger #C73535`. Les ratios de 4,5:1 restent à valider.

Le mode **Contraste élevé de Windows** (`forced-colors`) est pris en charge : les états se distinguent par les bordures et les icônes, et les rubans gardent un contour.

### 6.3 Codage des statuts d'épisode (couleur, forme et icône)

| Statut affiché | Source dans le moteur | Case de la grille | Segment du ruban |
|---|---|---|---|
| À télécharger | `pending` sans `.part` | Contour pointillé `border-control`, numéro en `text-muted` | Contour gris |
| En file | Job actif, épisode pas encore démarré | Contour plein gris, petite horloge | Gris clair |
| En cours X % | `downloading` (événements) | Fond `active` à 20 %, remplissage depuis le bas à `--p`, flèche ↓ | Violet partiel |
| Téléchargé et vérifié | `done`, durée conforme | Fond `success` plein, numéro foncé, petite coche | Vert |
| Téléchargé, non vérifié | `done` en mode sonde, ou réconcilié | Contour `success` et fond à 25 %, icône « ≈ » | Vert clair |
| Interrompu | `.part` sans job, ou `downloading` figé | Contour `warning`, icône ⏸ | Ambre |
| Échec | `failed`, cause réessayable | Fond `danger` à 20 %, bord de 2 px, « ! » | Rouge, encoche |
| Indisponible | `failed`, cause source | Hachures grises, « – » | Hachuré |
| Fichier disparu | `done` sans fichier | Contour `warning`, « ? » | Ambre |
| Qualité différente | `quality` ≠ majorité | Coin marqué « 720 » (◇) | Ambre si isolé |
| Sélection (cumulable) | — | Contour `accent` de 2 px décalé et coche en coin, **jamais de fond** | — |

### 6.4 Typographie

- **Interface** : `"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`. Police native de Windows 10 et 11 : rien à télécharger, excellent rendu ClearType, cohérent avec le zéro dépendance.
- **Titres** (fiche, inspecteur) : `"Segoe UI Variable Display"`, semi-gras.
- **Mono** : `"Cascadia Mono", Consolas, monospace` pour le n° de série, les commandes, le journal et le champ de plages.
- **Chiffres tabulaires** (`font-variant-numeric: tabular-nums`) sur tous les compteurs, débits, tailles et temps restants.
- **Échelle** en rem, pour une base de 16 px : 12 px (barre d'état, légendes) · 13 px (tableaux, méta) · 14 px (texte de base de l'interface) · 16 px (titres de panneau) · 20 px (titre de l'inspecteur) · 24 px (titre de la fiche). Interlignage de 1,4.
- **Français** : espace insécable avant « ? : ! », guillemets « », « 684 Mo », « 1 h 32 », « 12,8 Mo ». Titres sur 2 lignes au maximum, avec points de suspension et titre complet en infobulle. Attribut `lang` sur les titres étrangers (`es`, `ko`, `ja`…).

### 6.5 Densité, formes, images, mouvement

- **Grille de 4 px.**
  - Lignes : 56 px en densité standard, 40 px en densité compacte (option), avec des cibles ≥ 24 px.
  - Cases d'épisode : 48 px dans la fiche, 28 px dans l'inspecteur, 52 px sur mobile. Cibles de 44 px minimum pour les contrôles principaux.
  - Rayons : 8 px (panneaux, cartes), 6 px (boutons), 4 px (cases).
- **Covers**, affichées à leur taille native ou en dessous, jamais agrandies :
  - 28×50 en liste ;
  - 144×256 dans la fiche ;
  - 160×284 en affiches ;
  - 180×320 dans l'inspecteur (source 360×640, nette avec une mise à l'échelle de 200 %).

  Jamais de bandeau paysage étiré. Les fonds sont faits de la même cover floutée à 40 px, sous un voile `#0B1220` à 85 %. Le texte n'est jamais posé directement sur une image.
- **Icônes** : sprite SVG Lucide (licence ISC), 16 et 20 px, trait de 1,75.
- **Mouvement** : 120-160 ms, ease-out, pour les tiroirs et les apparitions. Avec `prefers-reduced-motion` : aucun scintillement, aucune rayure animée, apparitions directes, décompte en texte seul. Rien ne clignote plus de 3 fois par seconde.

---

## 7. Risques et faiblesses assumés

| # | Risque | Pourquoi on l'accepte | Atténuation |
|---|---|---|---|
| 1 | **Allure d'IDE au premier lancement** : quatre zones peuvent intimider, alors qu'une série se télécharge en 1 min | L'utilisateur est un power user qui vient de la CLI | Démarrage au calme (§3.12) : dock replié, inspecteur masqué, omnibar au centre. Les zones apparaissent quand elles servent. |
| 2 | **Moins « Netflix »** : la liste dense par défaut flatte moins la collection qu'un mur d'affiches | La densité sert la supervision de dizaines de séries | Vue Affiches à une touche (V), mémorisée ; grande cover dans l'inspecteur ; lecteur en mode théâtre |
| 3 | **Largeur à 1280 px et en dessous** : barre latérale, centre et inspecteur se disputent la place | Le laptop reste un cas secondaire | Rail de 56 px, inspecteur en superposition sous 1180 px, colonnes masquables |
| 4 | **Dock souvent vide** : le moteur traite une série à la fois et les jobs durent environ 1 min | Il est précieux lors des ajouts en lot et des problèmes | Replié par défaut sur la barre d'état ; s'ouvre seul uniquement pour la reprise au démarrage |
| 5 | **Découvrabilité** : palette, mini-syntaxe et raccourcis restent invisibles pour qui ne les cherche pas | Cœur de l'angle « power user » | Chaque bouton affiche son raccourci, indice « Ctrl K » dans l'omnibar, puces « Compris : … », aide `?`. Rien n'est accessible **uniquement** par la palette. |
| 6 | **Clavier sous Windows** : collisions avec le navigateur, AZERTY | Un poste de pilotage se doit d'être rapide au clavier | Choix vérifiés (§5.9), raccourcis à une touche désactivables, mode fenêtre Edge `--app` qui neutralise une partie des raccourcis du navigateur |
| 7 | **Le mobile n'est plus un poste de pilotage** : sur 390 px, la mise en page devient une télécommande empilée | Le canapé sert à ajouter et suivre, pas à superviser | Même modèle mental (liste, inspecteur en page, mini-dock). Le réseau local reste hors V1 faute d'authentification. |
| 8 | **Forte dépendance aux ajouts du moteur**. P0 : événements structurés (octets, phases), annulation programmable qui remet les épisodes à `pending`, codes d'erreur stables, index de bibliothèque avec réconciliation disque, `force` pour retélécharger dans une autre qualité, vitesse et temps restant, file de jobs persistée. P1 : pré-vol du film avec remèdes, catalogue doublé / non doublé par langue, statut de connectivité mesuré par le moteur. Pour « Continuer à regarder » : stocker la progression de visionnage. | Sans eux, le poste mentirait (des `downloading` figés, ou « Indisponible » confondu avec « Échec ») | Livrer d'abord l'étape « moteur pilotable » (§7 de l'architecture) ; les zones dont les données manquent restent masquées plutôt que fausses |
| 9 | **Le ruban de complétude devient illisible au-delà de 150 épisodes**, et il repose sur la couleur | Excellent pour 60 à 100 épisodes | Regroupement par paquets au-delà, texte « 58/62 · 1 échec » toujours présent, encoche et hachures en plus de la couleur |
| 10 | **Plusieurs onglets ouverts** : chaque onglet garde une connexion SSE, et Chrome se bloque vers 5 onglets avec la vidéo | Le poste est pensé pour une seule fenêtre | Mode fenêtre Edge `--app`, avertissement « déjà ouvert dans un autre onglet », `SharedWorker` en V2 |
| 11 | **Sur-conception pour un seul utilisateur** : vues enregistrées, page Activité plein écran, journal structuré | Nourrit le « défi » et le débogage | Ces éléments sont en V1.1 ou V2 ; le MVP garde omnibar, bibliothèque, inspecteur, fiche, dock (File et Journal), film et réglages |