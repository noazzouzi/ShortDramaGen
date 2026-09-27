# Concept B — Flux d'abord

# Concept B : « Flux d'abord »

> Concept de frontend pour ShortDramaGen. L'interface est locale (`sdg ui` sur 127.0.0.1:8765, dans un onglet ou une fenêtre Edge `--app`), en français, sous Windows, avec tutoiement.
> Hypothèses techniques reprises de la recherche : serveur en bibliothèque standard + SSE, application web sans build, file de jobs persistée. Par défaut, une série se télécharge à la fois avec 3 épisodes en parallèle, et les films ont leur propre voie.
> Dans les maquettes, les titres « Titre fictif A… E » sont des exemples inventés. Seule « One Night to Forever » / « Qui Est la Véritable Mme Lafont ? » est une série réelle.

---

## 1. Idée directrice

**L'accueil est un poste de pilotage : un grand champ « Colle un lien » en haut, et dessous un flux vivant de cartes, une par série, qui montrent ce que le moteur fait, a fini ou attend de toi. La collection entière vit à part, dans une Bibliothèque faite pour parcourir, regarder et ranger ; le flux, lui, sert à lancer, suivre et réparer.**

### Pourquoi c'est le bon choix pour cet utilisateur

1. **Le geste le plus fréquent est aussi le plus court.** Il récupère une série plusieurs fois par semaine (J1), et chaque opération dure de 40 s à 1 min 40. L'écran qui s'ouvre doit donc être celui de l'action : Ctrl+V puis Entrée, soit 2 interactions, sans aucune navigation.
2. **Il retrouve ses repères de dramafren.** L'accueil de dramafren, c'est déjà « Paste URL + langue + GO ». On garde le même geste au même endroit (en haut, au centre). La différence : un seul GO télécharge 62 épisodes vérifiés, au lieu de 62 clics sans garantie.
3. **Il lance, puis fait autre chose** (second écran, Explorateur, VLC). Le flux reprend la logique des gestionnaires de téléchargements qu'il connaît sous Windows (bulle de téléchargement de Chrome, JDownloader), mais avec une seule carte par série. En revenant, il lit l'état en une seconde.
4. **Il veut du contrôle et être fier de son « défi ».** Le flux montre la machine au travail : chaque épisode se remplit puis est marqué « vérifié », et un journal traduit ce qui se passe. Rien ne se fait dans son dos.
5. **La gestion n'est pas sacrifiée.** La section « À traiter » du flux regroupe les problèmes de **toute** la collection, avec un bouton de réparation pour chacun. La Bibliothèque garde ce qui relève de la consultation (parcourir, chercher, trier, regarder, supprimer), qu'on peut isoler sans coût.

### Ce que le concept pousse jusqu'au bout

- **Le champ est focalisé dès l'ouverture**, et Ctrl+V marche partout. En option, le « Collage express » lance le téléchargement avec un seul geste.
- **L'aperçu naît dans le flux**, exactement là où vivra la carte de téléchargement. Il n'y a ni modale, ni page « Ajouter », ni seconde file d'attente à la JDownloader.
- **Une carte correspond à une version de série** (bookId + langue), jamais à un job ou à un épisode. Réessayer, compléter ou créer le film fait remonter la même carte en haut du flux.
- **Le flux sert à trois choses à la fois** : lanceur, boîte de réparation et journal.

---

## 2. Architecture de l'information

### 2.1 Arborescence

```
ShortDramaGen  (http://127.0.0.1:8765, onglet ou fenêtre Edge --app)
│
├── Flux  #/                                     ← accueil, ouvert par défaut
│   ├── Bandeaux système (reprise, hors ligne, moteur injoignable, disque plein)
│   ├── Champ « Colle un lien » + aperçu(s) en place
│   ├── En cours            (1 série + 1 film au plus, réglages par défaut)
│   ├── En file
│   ├── À traiter           (problèmes de TOUTE la bibliothèque)
│   ├── Terminé             (Aujourd'hui · Hier · 7 derniers jours · Plus ancien)
│   └── Coup d'œil          (colonne : disque, santé, Continuer à regarder, Ajoutées récemment)
│
├── Bibliothèque  #/bibliotheque?vue=affiches&etat=incompletes&tri=activite&q=lafont
│   └── Fiche série  #/serie/41000105199?v=fr
│       ├── Versions            VO (anglais) · VF · + Espagnol
│       ├── Santé + action principale
│       ├── Épisodes            grille décimale → Lecteur / menu d'épisode
│       ├── Film                pré-vol, création, lecture
│       ├── Fichiers            dossier, taille, suppression
│       └── Détails techniques  n° de série, origine, qualité par épisode, CLI, journal
│
├── Lecteur  #/lecture/<series_key>/<n | film>   (couche plein écran, Échap = retour)
│
├── Réglages  #/reglages/{general|telechargements|film|stockage|clavier|avance}
│
└── Transversal : Ctrl+V global · palette Ctrl+K · pilule d'activité (hors Flux)
                  · toasts · notifications Windows · aide « ? »
```

### 2.2 Règles de navigation

- **Trois destinations, pas une de plus** : Flux, Bibliothèque, Réglages. Le lecteur, les dialogues et la palette sont des couches superposées, pas des pages.
- **Barre supérieure plutôt que barre latérale.** Avec trois destinations, une barre latérale gaspillerait 240 px. La barre supérieure laisse toute la largeur au flux et reste lisible quand la fenêtre occupe une moitié d'écran (Windows Snap, environ 720 px).
- **Le flux est trié par état, puis par date** : ce qui bouge, ce qui attend, ce qui cloche, puis ce qui est fini.
- **L'unité du flux est la version de série**, identifiée par `bookId + langue` (« vo » pour la VO). Une nouvelle opération sur une version déjà présente rattache son historique à la même carte.
- **On peut ajouter depuis partout** :
  - sur le Flux, avec le champ principal ;
  - ailleurs, avec le champ compact de l'en-tête, qui ouvre l'aperçu dans une fenêtre flottante (popover) sans quitter la page ;
  - avec Ctrl+V hors d'un champ ;
  - en glissant-déposant un lien sur la fenêtre (« Dépose le lien ici »).
- **Le flux te suit sur les autres pages.** Une **pilule d'activité** dans l'en-tête affiche « ↓ 34/62 · 33 s » avec une mini-pellicule. Un clic ouvre une fenêtre flottante avec la ou les cartes actives (même composant) et le lien « Ouvrir le flux ». Sur le Flux lui-même, la pilule est masquée, car elle ferait doublon.
- **L'onglet Flux porte un badge** : le nombre d'éléments « À traiter » (en ambre), plus un point cyan quand un téléchargement tourne.
- **Cartes et fiches sont reliées.** La cover ou le titre d'une carte ouvre la fiche. La fiche propose un lien « Historique dans le flux ». On ne change jamais d'écran de force.
- **L'état est dans l'URL** (filtres, tri, vue, version) : le bouton Retour fonctionne, et le flux garde sa position de défilement.

### 2.3 Navigation selon la largeur

| Largeur | Navigation | Flux | Pilule d'activité |
|---|---|---|---|
| ≥ 1366 (cible 1440) | Barre du haut : logo · Flux [n] · Bibliothèque [54] · « Rechercher, Ctrl K » · pilule · Réglages (avec pastille de santé) | Colonne de 760 px + colonne « Coup d'œil » de 320 px | Hors Flux |
| 1024 à 1365 | Idem | Une colonne de 760 px. « Coup d'œil » devient un bandeau horizontal repliable sous le champ | Hors Flux |
| 600 à 1023 (demi-écran Snap) | Barre compacte, libellés courts | Une colonne, cartes pleine largeur | Hors Flux |
| < 600 (cible 390) | **Barre du bas** : Flux [n] · Bibliothèque · Réglages (cibles ≥ 44 px) + en-tête avec la pilule | Une colonne, gouttières de 16 px | Toujours visible dans l'en-tête |

---

## 3. Écrans

Chaque écran est décrit selon le même plan : **But**, **Zones** (de haut en bas), **Actions**, **États**, **Mobile 390**.

### É0. Coquille globale

- **But.** Donner accès partout aux trois destinations, à l'ajout et à l'état du moteur.
- **Zones.**
  1. Lien d'évitement « Aller au contenu ».
  2. Barre du haut : logo, Flux [badge], Bibliothèque [nombre de séries], champ « Rechercher ou coller · Ctrl K » (il ouvre la palette ; s'il reçoit un lien, il ouvre l'aperçu), pilule d'activité, Réglages avec pastille de santé.
  3. Zone de bandeaux système, pleine largeur, sous la barre.
  4. Contenu.
  5. Toasts en bas à droite (3 au maximum, jamais sur l'élément qui a le focus).
  6. Une seule région `role="status"` pour les annonces.
- **Signaux périphériques.**
  - Titre d'onglet : « (34/62) ShortDramaGen », puis « Terminé · ShortDramaGen » pendant 5 s.
  - Favicon avec un anneau de progression.
  - Notification Windows **une fois par série**, seulement si l'onglet est masqué.
- **États.**

| État | Rendu et texte |
|---|---|
| Chargement | Barre fine indéterminée (statique si les animations sont réduites) · « Lecture de ta bibliothèque… 23 séries trouvées » |
| Moteur injoignable | Bandeau rouge persistant ; interface en **lecture seule**, dernier état connu ; reconnexion toutes les 5 s · « Le moteur ne répond plus. Tes téléchargements sont peut-être arrêtés. On essaie de se reconnecter… » [Réessayer maintenant] |
| Hors ligne (mesuré par le moteur) | Bandeau discret, non bloquant · « Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls. » |
| Disque plein | Bandeau rouge persistant · « Téléchargements arrêtés : il manque 312 Mo sur C:. » [Voir le stockage] [Reprendre] |
| Autre onglet ouvert | « ShortDramaGen est déjà ouvert dans un autre onglet. » [Utiliser ici] (limite du nombre de connexions SSE) |

### É1. Flux (accueil)

- **But.** Lancer une série en 2 gestes, suivre sans y penser, réparer en 1 clic, enchaîner sur ce qui vient de finir.

**Maquette desktop 1440** (colonne principale et colonne « Coup d'œil ») :

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ShortDramaGen    Flux [3]    Bibliothèque 54         [ Rechercher, Ctrl K ]         Réglages                 │
│──────────────────────────────────────────────────────────────────────────────────────────────────────────────│
│  ┌──────────────────────────────────────────────────────────────────────────┐   ┌──────────────────────────┐ │
│  │                                                                          │   │COUP D'ŒIL                │ │
│  │  Colle un lien DramaBox ou un n° de série                 [Coller]       │   │                          │ │
│  │                                                                          │   │Bibliothèque : 54 séries  │ │
│  └──────────────────────────────────────────────────────────────────────────┘   │█████████░░░░░ 38,4 Go    │ │
│   Liens acceptés : dramaboxdb.com, dramabox.com, partage de l'app,              │182 Go libres sur C:      │ │
│   dramafren, n° de série. Ctrl+V marche partout, même hors du champ.            │Films : ffmpeg prêt ✓     │ │
│                                                                                 │Sources : joignables ✓    │ │
│  EN COURS                                                                       │                          │ │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │CONTINUER À REGARDER      │ │
│  │┌──────┐  Qui Est la Véritable Mme Lafont ?              VF · 1080p       │   │▯ Lafont · VF · ép. 14    │ │
│  ││      │  One Night to Forever                                            │   │▯ Film · VO · 0:42:10     │ │
│  ││ cov  │  █████████████!█████████████████████▓▓▓░░░░░░░░░░░░░░░░░         │   │                          │ │
│  ││      │  34/62 vérifiés · 7,8 Mo/s · ≈ 33 s · 1 échec                    │   │AJOUTÉES RÉCEMMENT        │ │
│  ││      │  [Regarder l'ép. 1]              [Pause]   [⋯]                   │   │▯ ▯ ▯ ▯ ▯ ▯               │ │
│  │└──────┘                                                                  │   │Toute la bibliothèque →   │ │
│  └──────────────────────────────────────────────────────────────────────────┘   └──────────────────────────┘ │
│  EN FILE (1)                                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐                                │
│  │ ▯  Una Noche Para Siempre · VE      En file · démarre dans ≈ 35 s  [⋯]   │                                │
│  └──────────────────────────────────────────────────────────────────────────┘                                │
│  À TRAITER (3)                                          [Tout réparer]                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐                                │
│  │ !  Titre fictif A · VO      2 échecs (ép. 14, 40)   [Réessayer les 2]    │                                │
│  │ ≠  Titre fictif B · VF      3 ép. en 720p : film bloqué  [Harmoniser]    │                                │
│  │ ‖  Titre fictif C · VO      Interrompu · 21/48           [Reprendre]     │                                │
│  └──────────────────────────────────────────────────────────────────────────┘                                │
│  TERMINÉ · AUJOURD'HUI                                                                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐                                │
│  │┌──────┐  One Night to Forever · VO                     ✓ 62/62 vérifiés  │                                │
│  ││      │  702 Mo · 1 min 38 s · 19:02     [Créer le film]  [Regarder]  [⋯]│                                │
│  │└──────┘                                                                  │                                │
│  └──────────────────────────────────────────────────────────────────────────┘                                │
│  TERMINÉ · HIER (4)  ▸ afficher        Effacer l'historique (fichiers gardés)                                │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Zones.**
  1. **Bandeaux système**, seulement s'il y a lieu (voir É0 et É11).
  2. **Champ principal.**
     - 56 px de haut, texte en 20 px, focalisé à l'ouverture (sauf retour par l'historique du navigateur).
     - Le bouton [Coller] lit le presse-papiers ; le navigateur demande l'autorisation une seule fois.
     - Le champ accepte plusieurs lignes, pour un ajout en lot.
     - Une aide sous le champ liste les formats acceptés.
  3. **Aperçu(s)** en place (É2). Ils poussent les sections vers le bas.
  4. **En cours** : cartes actives complètes (É3). Par défaut, au plus un téléchargement et une fusion.
  5. **En file (n)** : cartes d'une ligne, dans l'ordre d'exécution, avec « démarre dans ≈ 35 s ».
  6. **À traiter (n)** + [Tout réparer] : une ligne par problème, **sur toute la bibliothèque**, du plus bloquant au plus bénin. Chaque ligne affiche une icône, le titre et la version, le problème en clair, **un** bouton de réparation et un menu ⋯ (Ignorer, Voir la fiche). Problèmes couverts :
     - échecs réessayables ;
     - téléchargement interrompu (fichier `.part` sans job actif) ;
     - série incomplète **non voulue** : une sélection explicite d'épisodes ne crée jamais d'alerte ;
     - qualités mélangées qui bloquent le film ;
     - film périmé (épisodes ajoutés après sa création) ;
     - fichier disparu ;
     - épisode indisponible à la source, avec [Réessayer plus tard], sans rouge permanent.
  7. **Terminé** : groupé par Aujourd'hui, Hier, 7 derniers jours et Plus ancien (replié). Cartes compactes, avec [Effacer l'historique (fichiers gardés)]. L'historique garde les 100 derniers jobs, comme dans le moteur.
  8. **Coup d'œil** (≥ 1366 px) : stockage, santé (ffmpeg, sources), « Continuer à regarder », « Ajoutées récemment » (6 covers qui mènent à la Bibliothèque).
- **Actions.**
  - Primaire : coller, puis Entrée (= « Tout télécharger »).
  - Secondaires : [Tout réparer], Pause ou Reprendre par carte, [Regarder], [Créer le film], ouvrir la fiche.
- **États.**

| État | Rendu et texte |
|---|---|
| Vide, premier lancement | Champ **au centre** de l'écran, focalisé · « Colle le lien d'une série DramaBox : on récupère tous les épisodes, vérifiés, jusqu'en 1080p. » · [Essayer avec un exemple] (remplit l'URL de One Night to Forever **sans lancer**) · si des dossiers existent déjà : « 3 séries trouvées dans ton dossier, créées en ligne de commande. » [Les voir] · ligne discrète « Dossier : C:\Users\…\Videos\ShortDramaGen [Changer] · Films : ffmpeg manquant [Comment l'installer ?] ». Pas d'assistant en plusieurs écrans. |
| Vide, usage courant | « Rien en cours. Colle un lien pour lancer une série. » Puis la section Terminé. |
| Chargement | 3 cartes squelettes (moins d'une seconde), statiques si les animations sont réduites |
| Succès | Comme la maquette |
| Partiel | « À traiter » n'est pas vide, et le badge du Flux est allumé |
| Erreur | Moteur injoignable : flux figé en lecture seule, boutons désactivés **avec leur raison** (« Indisponible : le moteur ne répond pas ») |
| Hors ligne | Cartes actives en « En pause · hors ligne · nouvel essai dans 12 s » [Réessayer maintenant] · un lien collé crée une carte « En attente de connexion » dans « En file » |

- **Mobile 390.** Champ + [Coller] en haut (maquette en É11). Les sections sont identiques, sur une seule colonne. « Coup d'œil » est réduit à une ligne de stockage en bas du flux. Toucher à nouveau l'onglet Flux remonte en haut et focalise le champ.

### É2. Aperçu (carte d'ajout)

- **But.** Confirmer que c'est la bonne série et la bonne version, voir le coût, lancer.
- **Déclenchement.**
  1. On colle, ou on appuie sur Entrée dans le champ.
  2. **Analyse locale immédiate**, avec les règles d'`inputs.py` : étiquette « Lien DramaBox · série 41000105199 · VF ».
  3. Appel `POST /api/preview` (environ 1 s). Cet appel ne lance **jamais** le mode sonde.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│┌────────────┐  Qui Est la Véritable Mme Lafont ?                          ✓ Série trouvée      │
││            │  One Night to Forever (VO anglais) · n° 41000105199                              │
││            │  62 épisodes · 1 h 32 · épisodes de 50 s à 3 min 30                              │
││            │  Synopsis sur 3 lignes, repliable…                                 Lire plus     │
││            │                                                                                  │
││ cover 9:16 │  Version   ( VO anglais )  (● VF )  ( VE )   + 4 langues ▾                       │
││            │  Qualité   Meilleure (1080p) ▾        Épisodes  Tous (62) ▾                      │
││            │  ≈ 690 Mo · ≈ 1 min 40 · 182 Go libres sur C:                                    │
││            │                                                                                  │
││            │  [ Tout télécharger · 62 épisodes   ↵ ]      [ ] Créer le film à la fin          │
││            │  Options ▾          sdg fetch 41000105199 --lang fr   [Copier]                   │
│└────────────┘                                                                                  │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Zones.**
  - Cover 135×240, sur un fond fait de la même cover floutée.
  - Titre dans la version choisie, titre VO et n° de série.
  - Méta : nombre d'épisodes, durée totale, fourchette de durée par épisode.
  - Synopsis sur 3 lignes, repliable.
  - Puces de **versions** :
    - version présélectionnée selon cet ordre : langue de l'URL, sinon langue préférée si elle existe, sinon VO ;
    - on ne propose que les versions **réellement doublées**. Les autres langues sont listées dans « + 4 langues » avec la mention « titre traduit seulement » ;
    - tant que le moteur n'a pas confirmé une langue, sa puce affiche « vérification… » et ne peut pas être choisie.
  - Qualité et épisodes, sous forme de résumés cliquables.
  - Estimation : taille, durée, espace libre.
  - Bouton principal **focalisé** et case « Créer le film à la fin » (mémorisée).
  - [Options ▾] et commande CLI équivalente, copiable.
- **Options dépliées** (toutes mémorisées d'une fois sur l'autre) :
  - Version ;
  - Qualité : « Meilleure (1080p) ≈ 690 Mo » / « 720p » / « 540p ». Les tailles en 720p et 540p sont marquées « estimation » tant que la bibliothèque n'a pas servi à les calibrer ;
  - Épisodes : Tous / Seulement les manquants / Choisir… (grille de sélection et champ de plages, voir S4) ;
  - Film à la fin ;
  - Dossier, en lecture seule, avec un lien vers les Réglages.
- **Le bouton principal s'adapte au cas.**

| Cas | Bouton principal | Secondaire |
|---|---|---|
| Nouvelle série | Tout télécharger · 62 épisodes | Options |
| Version déjà complète | Ouvrir la série | Ajouter la VO / la VE |
| Version incomplète | Compléter · 22 manquants | Ouvrir |
| Déjà en file ou en cours (`409 duplicate_job`) | Voir dans le flux | — |
| Série absente du site officiel (mode sonde) | Tout télécharger · détection à la source | — |
| Sélection partielle | Télécharger 23 épisodes · ≈ 270 Mo | Tous |
| Espace disque insuffisant | Désactivé : « Il manque 312 Mo sur C: » | [Voir le stockage] |

- **Actions.**
  - Primaire : Entrée.
  - Secondaires : ← / → pour passer d'une version à l'autre, Options, Échap (ferme l'aperçu et **garde** le texte du champ).
- **États.**

| État | Rendu et texte |
|---|---|
| Chargement | Squelette : affiche 9:16, 3 lignes, bouton inactif · au-delà de 4 s : « Le site officiel met du temps à répondre… » |
| Succès | Comme la maquette |
| Partiel | Mode sonde : « Infos limitées : cette série n'est pas sur le site officiel. Les épisodes seront détectés à la source, sans contrôle de durée. » (étiquette « non vérifié », cover générée) · Doublon : « Déjà dans ta bibliothèque : VF complète (62/62). » · Lien d'épisode : « C'est le lien d'un épisode : on te propose toute la série. » |
| Erreur, sous le champ | « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199). » Le texte est conservé et la partie fautive soulignée. · Introuvable : « On n'a trouvé cette série ni sur le site officiel ni à la source. » · Réseau : « Impossible de joindre DramaBox. » [Réessayer] |
| Hors ligne | « Tu es hors ligne : l'aperçu a besoin d'Internet. » [Garder pour plus tard] |

- **Lot.** Plusieurs lignes collées donnent une liste d'aperçus compacts, tous cochés, avec « Tout télécharger · 3 séries · ≈ 2,1 Go ». Les lignes non reconnues sont signalées : « La ligne 2 n'est pas un lien DramaBox. »
- **Hors du Flux.** C'est le même composant, dans une fenêtre flottante de 640 px sous l'en-tête. Il se referme après le lancement, et la carte apparaît dans la pilule.
- **Mobile 390.** Feuille du bas plein écran : cover de 90×160 en haut, bouton principal collé en bas de l'écran.

### É3. Carte de flux (et son détail déplié)

- **But.** Montrer la vie d'une version de série : où elle en est, et quelle est la prochaine chose à faire.
- **Anatomie repliée** (environ 112 px) :
  - cover 54×96 ;
  - titre sur 2 lignes au plus, titre VO ;
  - badges version et qualité ;
  - **pellicule** (S3) ;
  - ligne d'état : x/y vérifiés · débit · temps restant · échecs ;
  - **un** bouton principal, un secondaire et le menu ⋯.
- **Dépliée** (clic sur la carte ou la pellicule, ou Entrée) : grille décimale complète, légende qui sert aussi de filtre, journal de la série traduit en langage courant, lien « Détails techniques ».

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│┌──────┐  Qui Est la Véritable Mme Lafont ?                              VF · 1080p       │
││      │  One Night to Forever                                                            │
││ cov  │  █████████████!█████████████████████▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░         │
││      │  34/62 vérifiés · 7,8 Mo/s · ≈ 33 s · 1 échec        [Pause]  [Replier ▴]        │
││      │                                                                                  │
│└──────┘                                                                                  │
│                                                                                          │
│  [ 1✓] [ 2✓] [ 3✓] [ 4✓] [ 5✓] [ 6✓] [ 7✓] [ 8✓] [ 9✓] [10✓]                             │
│  [11✓] [12✓] [13✓] [14!] [15✓] [16✓] [17✓] [18✓] [19✓] [20✓]                             │
│  [21✓] [22✓] [23✓] [24✓] [25✓] [26✓] [27✓] [28✓] [29✓] [30✓]                             │
│  [31✓] [32✓] [33✓] [34✓] [35✓] [36▓] [37▓] [38▓] [39·] [40·]                             │
│  [41·] [42·] [43·] [44·] [45·] [46·] [47·] [48·] [49·] [50·]                             │
│  [51·] [52·] [53·] [54·] [55·] [56·] [57·] [58·] [59·] [60·]                             │
│  [61·] [62·]                                                                             │
│                                                                                          │
│  ✓ Vérifié 34   ▓ En cours 3   ! Échec 1   · En attente 24     (cliquer = filtrer)       │
│                                                                                          │
│  JOURNAL                                                       [Détails techniques]      │
│  19:04:11  Infos officielles récupérées : 62 épisodes, version VF                        │
│  19:04:30  Ép. 14 indisponible à la source : on continue avec les autres                 │
│  19:05:02  Ép. 35 vérifié (2 min 05, 1080p, 13,2 Mo)                                     │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**États de la carte**, construits sur les statuts de job du moteur :

| Job / phase | Ligne d'état | Bouton principal | Secondaires (⋯) |
|---|---|---|---|
| `queued` | En file · démarre dans ≈ 35 s | — | Mettre en pause · Retirer de la file |
| `running` · metadata | Récupération des infos… | Pause | Arrêter |
| `running` · probing | Série absente du site officiel · détection à la source… 23 épisodes trouvés (pellicule indéterminée) | Pause | Arrêter |
| `running` · downloading | 34/62 vérifiés · 7,8 Mo/s · ≈ 33 s | Pause | **Regarder l'ép. 1** (dès qu'un épisode est vérifié) · Arrêter (garder les 34 épisodes) |
| `pausing` / `cancelling` | « Mise en pause… » / « Arrêt… » (jusqu'à 30 s si la source ne répond pas) | — | — |
| `paused` | En pause par toi · 34/62 | Reprendre | Arrêter |
| Hors ligne | En pause · hors ligne · nouvel essai dans 12 s | Réessayer maintenant | — |
| `interrupted` | Interrompu · 34/62 · reprend là où il s'était arrêté | Reprendre | — |
| `done`, 0 échec | ✓ 62/62 vérifiés · 702 Mo · 1 min 38 s | Créer le film (ou Regarder le film s'il est déjà créé) | Regarder · Afficher dans le dossier · Fiche |
| `done` + échecs | Terminé avec 2 échecs (ép. 14 et 40) | Réessayer les 2 | Détail des échecs |
| `done` + qualités mélangées | 62/62 · 3 épisodes en 720p (1080p indisponible) | Harmoniser en 1080p | Créer le film quand même (ré-encodage) |
| `done`, film automatique bloqué | Film non créé : il manque l'épisode 40 | Réessayer puis créer le film | — |
| `failed` (bloquant) | « Série introuvable » / « Disque plein (il manque 312 Mo) » / « Impossible de joindre DramaBox » / « Erreur inattendue » | Réessayer · Voir le stockage | Copier le rapport |
| `cancelled` | Arrêté · 34 épisodes gardés | Compléter | Retirer du flux |
| Film en cours | Création du film… 38/62 assemblés · ≈ 3 s | — | Annuler |
| Film prêt | Film prêt · 1 h 32 · 717 Mo · 62 chapitres | Regarder le film | Afficher dans le dossier · Libérer 684 Mo |

- **Menu ⋯** : Voir la fiche · Afficher dans le dossier · Copier la commande CLI · Retirer du flux (fichiers gardés) · Arrêter.
- **Accessibilité.**
  - Chaque carte est un `article` avec un titre.
  - La pellicule a `role="progressbar"` et un `aria-valuetext` du type « 34 épisodes sur 62, 1 échec, environ 33 secondes restantes ».
  - Nom accessible de la carte : « Qui Est la Véritable Mme Lafont ?, version française, en cours ».
- **Mobile 390.** Cover de 40×72 et boutons de 44 px. Déplier ouvre la fiche, où se trouve la grille.

### É4. Bibliothèque

- **But.** Voir toute la collection, retrouver, filtrer, trier, agir en masse, regarder.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ShortDramaGen    Flux [3]    Bibliothèque 54         [ Rechercher, Ctrl K ]   ↓ 21/80 · 1 min   Réglages           │
│────────────────────────────────────────────────────────────────────────────────────────────────────────────────────│
│  [ Titre (VO, VF, VE…) ou n° de série        / ]      Tri : Activité récente ▾     [Affiches | Liste]              │
│  Toutes 54 · En cours 1 · Incomplètes 3 · Avec échecs 1 · Avec film 31 · Mélangée 1   Version : Toutes ▾           │
│  54 séries · 38,4 Go · 182 Go libres sur C:                                          [Sélectionner]                │
│                                                                                                                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │            │  │            │  │            │  │            │  │            │  │            │  │            │    │
│  │    9:16    │  │    9:16    │  │    9:16    │  │    9:16    │  │    9:16    │  │    9:16    │  │    9:16    │    │
│  │            │  │            │  │            │  │            │  │            │  │            │  │            │    │
│  │            │  │            │  │            │  │            │  │            │  │            │  │            │    │
│  │            │  │            │  │            │  │            │  │            │  │            │  │            │    │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │
│  ██████████████  ██████████▒▒!!  ▓▓▓▓▓▓░░░░░░░░  ██████████████  ██████████░░░░  ██████████████  ████████░░░░░░    │
│  Qui Est la      Titre fictif A  Titre fictif B  Titre fictif C  Série           Titre fictif D  Titre fictif E    │
│  Véritable Mme…                                                  41000999999                                       │
│  62 ép. 1 h 32   46/48 · 2 éch.  En cours 21/80  70 ép. 1 h 51   ~ non vérifiée  55 ép. 1 h 20   40/62             │
│  VO VF · Film    VO              VF              VO · Film       sonde           VE · Film       VO                │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Zones.**
  1. **Barre d'outils.**
     - Recherche instantanée (moins de 100 ms, index local) sur **tous les titres, toutes langues**, et sur le n° de série, avec la mention « trouvé dans le titre VF ».
     - Tri : Activité récente (par défaut), Ajoutées récemment, Regardées récemment, Titre A→Z, Taille, Durée, Nombre d'épisodes.
     - Vue : Affiches ou Liste.
  2. **Filtres en puces avec compteurs** : Toutes · En cours · Incomplètes · Avec échecs · Avec film · Sans film · Qualité mélangée · Sonde, plus le menu Version (noms complets : « Indonésien » pour `in`, jamais de drapeaux). Les puces à 0 sont masquées.
  3. **Statistiques** : « 54 séries · 38,4 Go · 182 Go libres sur C: ».
  4. **Rangée « Continuer à regarder »**, seulement si elle n'est pas vide.
  5. **Mur d'affiches**, **une carte par série** (bookId) :
     - barre de complétude avec le même codage de couleurs que la pellicule ;
     - titre de la version préférée sur 2 lignes ;
     - méta ;
     - badges texte « VO · VF » et « Film » ;
     - pastille d'état dans un coin bas, jamais sur les visages.
     - Au survol **et au focus** : [Regarder / Reprendre · ép. 14], [Compléter], ⋯ (Afficher dans le dossier, Créer le film, Supprimer…).
  6. **Vue Liste** (lignes de 48 px, triable) : Titre (autres titres en gris), Versions, Épisodes x/y, Durée, Taille, Qualité, Film, Ajoutée le, État.
  7. **Sélection multiple** avec [Sélectionner], Maj+clic ou Espace. Une barre collée en bas affiche « 5 séries · 3,4 Go » avec [Compléter], [Réessayer les échecs], [Créer les films] et [Supprimer…].
- **Actions.**
  - Primaire : ouvrir une série.
  - Secondaires : regarder, compléter, actions en masse.
- **États.**

| État | Rendu et texte |
|---|---|
| Vide | « Ta bibliothèque est vide. » avec le champ d'ajout sur place (même composant que dans le Flux) |
| Chargement | Affiches squelettes 9:16, sans effet de brillance animé si les animations sont réduites |
| Partiel | « 2 dossiers n'ont pas pu être lus et sont masqués. » [Voir lesquels] · cover absente : affiche générée |
| Recherche sans résultat | « Aucune série « xyz » dans ta bibliothèque. » · si le texte ressemble à un lien : « Ça ressemble à un lien DramaBox. » [Ajouter cette série] · avec filtres : « 1 résultat sans les filtres. » [Effacer les filtres] |
| Erreur | « Impossible d'ouvrir ton dossier de séries (C:\…). Il a peut-être été déplacé. » [Réglages] [Réessayer] |
| Hors ligne | Identique au succès : tout est local, covers en cache (`cover.jpg`) |

- **Mobile 390.** 3 colonnes d'environ 111 px. Recherche en haut, filtres et tri dans une feuille du bas, liste compacte à la place de la liste dense.

### É5. Fiche série

- **But.** Tout savoir et tout faire sur une série et ses versions.

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ShortDramaGen    Flux [3]    Bibliothèque 54         [ Rechercher, Ctrl K ]         Réglages           │
│────────────────────────────────────────────────────────────────────────────────────────────────────────│
│ ← Bibliothèque                                                                                         │
│                                                                                                        │
│  ┌──────────────────────────┐   Qui Est la Véritable Mme Lafont ?                                      │
│  │                          │   One Night to Forever · n° 41000105199                                  │
│  │                          │   62 épisodes · 1 h 32 · 662 Mo · 1080p (1 ép. en 720p)                  │
│  │                          │   Synopsis sur 3 lignes… Lire plus                                       │
│  │                          │                                                                          │
│  │                          │    VO (anglais) 62/62 ✓  │ [VF 60/62] │  + Espagnol (≈ 700 Mo)           │
│  │                          │   ────────────────────────────────────────────────────────────────────   │
│  │    cover nette 240 px    │   ┌──────────────────────────────────────────────────────────────────┐   │
│  │                          │   │! 1 échec (ép. 40) · 1 interrompu (ép. 41) · 1 ép. en 720p (12)   │   │
│  │                          │   │[ Réparer : réessayer 40, reprendre 41, 12 en 1080p ]   Autres ▾  │   │
│  │                          │   └──────────────────────────────────────────────────────────────────┘   │
│  │                          │                                                                          │
│  │                          │   ÉPISODES    ✓ 59   ≠ 720p 1   ! Échec 1   ‖ Interrompu 1   [Sélection] │
│  │                          │   [ 1✓] [ 2✓] [ 3✓] [ 4✓] [ 5✓] [ 6✓] [ 7✓] [ 8✓] [ 9✓] [10✓]            │
│  │                          │   [11✓] [12≠] [13✓] [14✓] [15✓] [16✓] [17✓] [18✓] [19✓] [20✓]            │
│  └──────────────────────────┘   [21✓] [22✓] [23✓] [24✓] [25✓] [26✓] [27✓] [28✓] [29✓] [30✓]            │
│  sur fond flouté de la cover    [31✓] [32✓] [33✓] [34✓] [35✓] [36✓] [37✓] [38✓] [39✓] [40!]            │
│                                 [41‖] [42✓] [43✓] [44✓] [45✓] [46✓] [47✓] [48✓] [49✓] [50✓]            │
│  [ Afficher dans le dossier ]   [51✓] [52✓] [53✓] [54✓] [55✓] [56✓] [57✓] [58✓] [59✓] [60✓]            │
│  [ Supprimer… ]                 [61✓] [62✓]                                                            │
│                                                                                                        │
│  Détails techniques ▸           FILM   Pas encore de film : 3 épisodes à régler avant la fusion.       │
│                                        [Réparer puis créer le film]   Autres choix ▾   ☑ Chapitres     │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Zones.**
  1. Lien de retour selon la provenance : « ← Bibliothèque » ou « ← Flux ».
  2. **En-tête** : cover nette de 240 px sur fond flouté, titre de la version, titre VO, n° de série, méta, synopsis replié.
  3. **Onglets de versions** : « VO (anglais) 62/62 ✓ » · « VF 60/62 » · « + Espagnol (≈ 700 Mo) ». Chaque version correspond à un dossier séparé sur le disque ; l'interface les regroupe.
  4. **Bandeau de santé** avec **une seule action principale**. Quand plusieurs problèmes se cumulent, ils sont combinés en une opération « Réparer ».
  5. **Grille décimale** (S4), légende-filtre avec compteurs, [Sélection].
  6. **Film** (É6).
  7. **Fichiers** : chemin, taille, fichiers partiels, [Afficher dans le dossier], [Supprimer…].
  8. **Détails techniques** (repliés) : n° de série de la version, origine et qualité par épisode, dernière opération, commande CLI, journal, lien « Historique dans le flux ». **Les URL signées ne sont jamais affichées.**
- **Action principale selon l'état**, par priorité décroissante :

| État | Action principale |
|---|---|
| En cours | Mettre en pause |
| Interrompue | Reprendre (34/62) |
| Échecs, partiels ou qualités mélangées | Réparer (n) |
| Incomplète | Télécharger les 4 manquants |
| Complète sans film | Créer le film |
| Complète avec film | Regarder le film, ou Reprendre · ép. 14 |

- **Tuile d'épisode.**
  - Le clic fait l'action utile pour son état : vérifié = regarder ; échec = petit volet avec la raison et [Réessayer] ; non téléchargé = [Télécharger cet épisode] ; interrompu = [Reprendre].
  - Menu (clic droit, ⋯ ou Maj+F10) : Regarder, Réessayer, Retélécharger en 1080p, Afficher dans le dossier, Copier le nom de fichier.
- **Autre langue.** « + Espagnol » ouvre un mini-aperçu (« Una Noche Para Siempre · 62 ép. · ≈ 700 Mo ») avec [Télécharger la VE] focalisé.
- **États.**

| État | Rendu et texte |
|---|---|
| Vide (0 épisode) | « Aucun épisode téléchargé pour l'instant. » [Tout télécharger · 62 épisodes] |
| Chargement | Squelette de l'en-tête et de la grille |
| En cours | La grille se remplit en direct, et les tuiles vérifiées deviennent lisibles aussitôt |
| Succès | « 62/62 épisodes téléchargés et vérifiés · 1 h 32 · 684 Mo · 1080p » |
| Partiel | Sonde : « Durées non vérifiées : cette série n'est pas sur le site officiel. » · Qualités : « 61 épisodes en 1080p, 1 en 720p. » |
| Erreur | « Le dossier de cette version est introuvable (déplacé ou supprimé hors de l'appli). » [Retélécharger] [Retirer de la bibliothèque] |
| Hors ligne | Les actions réseau sont désactivées avec la raison « Disponible au retour de la connexion ». Regarder, Film et Dossier restent actifs. |

- **Mobile 390.** Une colonne. Grille à 5 tuiles par ligne. Action principale collée en bas (maquette en É11).

### É6. Film (section de la fiche, et actions des cartes)

- **But.** Obtenir un seul fichier chapitré en 6 s environ, sans jamais tomber dans une impasse.
- **Pré-vol anticipé.** `GET /film/plan` est appelé dès que la section s'affiche : il lit les boîtes MP4 localement, sans ffmpeg ni réseau. Le bouton est donc **déjà** dans le bon état avant le clic.
- **États.**

| État | Rendu et texte |
|---|---|
| Possible | « Réunis les 62 épisodes en un seul fichier : 1 h 32, ≈ 717 Mo, un chapitre par épisode. » [Créer le film] · ☑ Chapitres |
| En cours | Progression **dans le bouton**, sans modale : « Création… 38/62 · ≈ 3 s » [Annuler] |
| Prêt | « Film prêt : Qui Est la Véritable Mme Lafont.mp4 · 1 h 32 · 717 Mo · 62 chapitres » [Regarder le film] [Afficher dans le dossier] · une seule fois : « Libérer 684 Mo en supprimant les épisodes ? Le film reste. » [Libérer] [Non merci] |
| Épisodes manquants | « Il manque 2 épisodes (61 et 62). » [Les télécharger puis créer le film] [Créer un film partiel (épisodes 1-60)] |
| Qualités mélangées | « L'épisode 12 est en 720p, les autres en 1080p. » [Retélécharger l'ép. 12 en 1080p (≈ 13 Mo) puis créer] [Créer quand même (ré-encodage, plusieurs minutes)] |
| ffmpeg absent | « Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans. » `winget install Gyan.FFmpeg` · `pip install imageio-ffmpeg` [Copier] [Revérifier] |
| Film partiel ou périmé | « Film partiel (épisodes 1-10). 52 épisodes ajoutés depuis. » [Recréer le film complet] · l'ancien fichier partiel est proposé à la suppression (le manifest ne garde qu'une entrée « film ») |
| Nom déjà pris | « Un film porte déjà ce nom. » [Remplacer] [Annuler] (le moteur écraserait le fichier sans rien demander) |
| Échec | « Le film créé n'a pas la durée attendue (1 h 29 au lieu de 1 h 32). » [Réessayer] [Détails techniques] |

### É7. Lecteur

- **But.** Regarder un épisode ou le film sans quitter l'application.
- **Zones (desktop).**
  - Fond bleu-noir, vidéo 9:16 centrée à la hauteur de la fenêtre (environ 484×860 px sur un écran 1440×900).
  - Colonne de droite de 360 px : titre et version, grille décimale compacte avec les états « vu » et « en cours de lecture » ; pour le film, la liste des chapitres « Épisode 1… 62 », qui sont aussi marqués sur la barre de lecture (`chapters.vtt`).
  - Commandes : lecture, ±5 s, épisode précédent/suivant, volume, vitesse, plein écran, [Ouvrir dans le lecteur par défaut].
- **Comportements.**
  - En fin d'épisode : « Épisode suivant dans 5 s » [Annuler]. Si les animations sont réduites, le décompte s'affiche en texte seul.
  - Épisode non téléchargé : « Épisode 59 non téléchargé : on passe au 60. »
  - Épisode encore en cours : « Cet épisode est encore en téléchargement (45 %). »
  - Reprise : « Reprise à 1:12 » [Revenir au début].
- **Clavier.** Espace ou K = lecture/pause · ← → = 5 s · Maj+← → = épisode ou chapitre · F = plein écran · M = muet · Échap = fermer.
- **États.**
  - Vide : « Ce fichier n'est plus dans le dossier. » [Retélécharger l'épisode]
  - Erreur de lecture (par exemple un codec HEVC) : « Ton navigateur n'arrive pas à lire cette vidéo. » [Ouvrir dans le lecteur par défaut]
  - Hors ligne : fonctionnement identique, les fichiers sont locaux.
- **Mobile 390.** Plein écran natif. La liste des épisodes passe dans une feuille du bas. Pas de geste de balayage, pour éviter les conflits avec le navigateur.

### É8. Dialogue de suppression

- **Titre.** « Que veux-tu supprimer ? · Qui Est la Véritable Mme Lafont ? (VF) »
- **Choix unique, sans présélection.** Le bouton se met à jour selon le choix (« Supprimer 684 Mo »).
  - « Seulement le film (717 Mo) »
  - « Seulement les épisodes (684 Mo) : le film reste »
  - « Tout : épisodes, film et dossier (1,4 Go) »
  - « Fichiers partiels (12 Mo) », seulement s'il en existe.
- **Avant la suppression**, le lecteur est coupé pour éviter le verrouillage de fichier sous Windows.
- **Après la suppression**, un toast « Supprimé · 684 Mo libérés » [Annuler]. La restauration reste possible 5 minutes (corbeille interne `.sdg/trash`), et le toast ne disparaît pas tant qu'il a le focus.
- **Erreurs.** « Impossible de supprimer E014.mp4 : il est ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. » [Réessayer] · Série en cours de téléchargement : « Mets d'abord le téléchargement en pause. »
- **En masse.** Même dialogue, avec « 5 séries · 3,4 Go ».
- **Mobile.** Feuille du bas.

### É9. Réglages et santé

- **En tête, un bloc « Santé »** :
  - ffmpeg : « Trouvé : C:\ffmpeg\bin\ffmpeg.exe (via PATH) » ou « Manquant » avec les commandes à copier et [Revérifier] ;
  - dossier accessible en écriture ;
  - espace libre ;
  - sources joignables, avec la date de la dernière vérification.
- **Général.**
  - Dossier des séries : chemin absolu, validé, avec [Afficher dans l'Explorateur]. On ne peut pas le modifier pendant un téléchargement (la raison est affichée).
  - Version préférée : « Français si disponible, sinon VO », sous forme de liste ordonnée.
  - Qualité : « Meilleure (1080p) ».
  - Film automatique après téléchargement.
  - **Page d'accueil : Flux / Bibliothèque.**
- **Téléchargements.**
  - Téléchargements simultanés : 3 (recommandé), de 1 à 6. Au-delà de 3 : « la source risque de te bloquer temporairement ».
  - Reprendre au démarrage : activé par défaut.
  - **Collage express** : désactivé par défaut.
- **Stockage.**
  - Répartition entre épisodes, films et fichiers partiels.
  - [Nettoyer les fichiers partiels orphelins (312 Mo)].
- **Clavier et accessibilité.**
  - Raccourcis à une touche activés ou non.
  - Annonces : paliers / fin seulement / aucune.
  - Thème : Sombre (par défaut) / Clair / Système.
  - Notifications Windows.
- **Avancé.** Arrêt automatique après 10 minutes sans onglet ouvert ni téléchargement, port, journal du serveur, [Quitter ShortDramaGen].
- **États.** « Enregistré. » affiché sur la ligne modifiée · erreurs de saisie liées au champ concerné · « Vérification de ffmpeg… » pendant le contrôle.
- **Mobile 390.** Liste de sections qui ouvrent des sous-pages. Le dossier et ffmpeg y sont en lecture seule.

### É10. Palette Ctrl+K

- **Un seul champ.**
  - S'il contient un lien ou un n° de série, la 1ʳᵉ ligne propose « Ajouter cette série » (ce qui ouvre l'aperçu).
  - Sinon, la palette propose d'abord des séries (tous titres, toutes langues, n° de série, avec « trouvé dans le titre VF »), puis des commandes : Reprendre tout, Tout mettre en pause, Réessayer tous les échecs, Créer le film de…, Afficher le dossier des séries, Aller à la Bibliothèque ou aux Réglages, Réglages : qualité…
- **Clavier** : ↑ ↓, Entrée, Échap. L'indice « Ctrl K » est visible dans l'en-tête. La palette n'est **jamais** le seul accès à une fonction.

### É11. Mobile 390 et états globaux

```
┌──────────────────────────────────┐    ┌──────────────────────────────────┐
│ShortDramaGen          ↓ 34/62    │    │← Bibliothèque                  ⋯ │
│──────────────────────────────────│    │──────────────────────────────────│
│┌────────────────────────────────┐│    │┌────────┐ Qui Est la             │
││Colle un lien DramaBox ou       ││    ││        │ Véritable Mme          │
││un n° de série      [Coller]    ││    ││        │ Lafont ?               │
│└────────────────────────────────┘│    ││  9:16  │ 62 ép. · 1 h 32        │
│EN COURS                          │    ││        │ 662 Mo                 │
│┌────────────────────────────────┐│    ││        │                        │
││┌───┐ Qui Est la Véritable…     ││    ││        │                        │
│││   │ VF · 34/62 · ≈ 33 s       ││    │└────────┘                        │
│││   │ ███████!████▓▓░░░░░░░     ││    │                                  │
│││   │ [Pause]            [⋯]    ││    │ VO ✓ │ [VF 60/62] │ + VE         │
││└───┘                           ││    │! 1 échec · 1 interrompu · 720p   │
│└────────────────────────────────┘│    │                                  │
│À TRAITER (3)     [Tout réparer]  │    │ [ 1✓] [ 2✓] [ 3✓] [ 4✓] [ 5✓]    │
│┌────────────────────────────────┐│    │ [ 6✓] [ 7✓] [ 8✓] [ 9✓] [10✓]    │
││! Titre A · 2 échecs            ││    │ [11✓] [12≠] [13✓] [14✓] [15✓]    │
││             [Réessayer les 2]  ││    │ [16✓] [17✓] [18✓] [19✓] [20✓]    │
│└────────────────────────────────┘│    │ …  (5 par ligne : 1-5, 6-10…)    │
│TERMINÉ · AUJOURD'HUI             │    │                                  │
│┌────────────────────────────────┐│    │FILM · bloqué (3 à régler)        │
││✓ One Night to Forever · VO     ││    │──────────────────────────────────│
││  62/62 · 702 Mo   [Regarder]   ││    │[   Réparer les 3 épisodes   ]    │
│└────────────────────────────────┘│    └──────────────────────────────────┘
│                                  │
│──────────────────────────────────│
│ Flux [3]  Bibliothèque  Réglages │
└──────────────────────────────────┘
```

**Sur mobile, on masque** (et on ne se contente pas de désactiver) : « Afficher dans le dossier », « Ouvrir dans le lecteur par défaut », l'installation de ffmpeg, les réglages avancés.

| État global | Comportement | Texte |
|---|---|---|
| Reprise au démarrage (réglage activé par défaut) | Les jobs interrompus repartent tout seuls ; bandeau d'information en haut du Flux | « Reprise de 2 téléchargements interrompus (34/62 et 0/48). » [Mettre en pause] [Voir] · si le réglage est désactivé : [Tout reprendre] |
| Hors ligne | Pause automatique, **aucun échec compté** ; nouveaux essais à 5, 15, 30 puis 60 s ; reprise à l'octet près | « Hors ligne. Reprise automatique au retour de la connexion. Nouvel essai dans 12 s. » [Réessayer maintenant] · au retour : « De retour en ligne. Reprise des téléchargements. » |
| Moteur injoignable | Lecture seule, reconnexion toutes les 5 s | voir É0 |
| Disque plein | Arrêt de la file, bandeau et notification | « Arrêté : disque plein (il manque 312 Mo sur C:). Libère de la place puis reprends. » |
| Fichier supprimé à la main | Détecté au scan suivant ; entrée dans « À traiter » | « Épisode 14 : le fichier n'est plus dans le dossier. » [Retélécharger] |
| Lien signé expiré | Invisible : le moteur résout à nouveau le lien | Message seulement si ça échoue : « Lien de téléchargement expiré, impossible d'en obtenir un nouveau pour l'instant. » [Réessayer] |

---

## 4. Les 6 parcours clés dans ce concept

**Convention de comptage.** Une interaction = un clic ou tap, un raccourci, ou Entrée. Coller compte pour 1. La saisie de texte est notée « + saisie ». Le défilement ne compte pas.

### (a) Coller une URL → aperçu → tout télécharger

**Chemin nominal, au clavier :**

| # | Geste | Système | Retour |
|---|---|---|---|
| 0 | Ouvrir l'appli (favori, onglet ou fenêtre Edge) | Flux affiché, champ focalisé | Curseur dans le champ |
| 1 | **Ctrl+V** | Analyse locale (< 50 ms), puis `preview` (environ 1 s) | « Lien DramaBox · série 41000105199 · VF », squelette, puis aperçu avec le bouton **focalisé** |
| 2 | **Entrée** | Job créé, l'aperçu **devient** la carte « En cours » | En moins d'une seconde : « Récupération des infos… » ; pellicule ; titre d'onglet ; champ vidé et refocalisé ; annonce « Téléchargement lancé : 62 épisodes » |

**Variantes :**

| Variante | Interactions |
|---|---|
| Nominal à la souris : [Coller] + clic sur le bouton (la 1ʳᵉ fois, le navigateur demande l'accès au presse-papiers) | 2 |
| Depuis une autre page : Ctrl+V n'importe où, aperçu dans une fenêtre flottante, Entrée | 2 |
| Choisir la VF plutôt que la VO présélectionnée : + → ou + clic sur une puce | 3 |
| Choisir des épisodes : Options + sélection (grille ou « 1-10, 28, 50- ») + Entrée | 4 à 5 (+ saisie) |
| Série déjà présente : l'aperçu propose « Compléter · 22 manquants » ou « Ouvrir » | 2 |
| Plusieurs liens (un par ligne) : « Tout télécharger · 3 séries » | 2 pour N séries |
| **Collage express** activé : Ctrl+V ; démarrage après un décompte de 3 s annulable par Échap | **1** |

**Cible de la recherche : 3 interactions au plus. Atteinte avec 2** (et 1 en mode express).

### (b) Suivre la progression en faisant autre chose

| Niveau | Où | Interactions |
|---|---|---|
| Périphérie | Titre d'onglet « (34/62) ShortDramaGen », favicon avec anneau, visibles depuis la barre des tâches Windows | 0 |
| En-tête | Pilule « ↓ 34/62 · 33 s » sur toutes les pages hors Flux | 0 |
| Flux | Carte vivante (pellicule, débit, temps restant, échecs comptés à part) | 0 |
| Fin | Notification Windows unique : « Qui Est la Véritable Mme Lafont ? (VF) est prêt · 62 épisodes vérifiés, 684 Mo » | 0 |
| Détail | Déplier la carte (grille + journal) ou cliquer sur la pilule | 1 |
| Contrôle | Pause / Reprendre / Arrêter | 1 |

La barre ne recule jamais. Un échec ne bloque pas la série. L'autorisation des notifications est demandée **sur la carte**, au premier téléchargement terminé : « Te prévenir la prochaine fois ? »

### (c) Retrouver une série parmi 50 et plus

| Chemin | Interactions |
|---|---|
| **Ctrl+K** + « lafont » + **Entrée** (trouvé dans le titre VF) | **2** + saisie |
| Bibliothèque + `/` + « lafont » + Entrée | 3 + saisie |
| Bibliothèque + puce « Incomplètes » + affiche | 3 |
| Série récente : directement sa carte dans le flux | 1 |

Résultats à chaque frappe en moins de 100 ms. L'objectif « moins de 5 s » est tenu.

### (d) Gérer une série

Comptage depuis le Flux :

| Sous-tâche | Chemin | Interactions |
|---|---|---|
| d1 Réessayer les échecs | « À traiter » → [Réessayer les 2] · toutes les séries d'un coup : [Tout réparer] | **1** |
| d2 Compléter | « À traiter » → [Compléter], ou recoller l'URL → « Compléter · 4 manquants » → Entrée | 1 (ou 2) |
| d3 Retélécharger un épisode précis | carte ou affiche → fiche → menu de tuile → « Retélécharger en 1080p » | 3 |
| d4 Ajouter une autre langue | fiche (1) → « + Espagnol » (2) → [Télécharger la VE] (3) · ou coller l'URL de la VE + Entrée | 3 (ou 2) |
| d5 Créer le film | carte terminée → [Créer le film] (environ 6 s, progression dans le bouton) ; +1 si un choix est nécessaire (film partiel, ré-encodage) | 1 à 2 |
| d6 Ouvrir le dossier | carte → ⋯ → « Afficher dans le dossier » (Explorateur Windows) | 2 |
| d7 Supprimer | fiche → [Supprimer…] → portée → [Supprimer 684 Mo] (+ [Annuler] possible) | 4 depuis le Flux (3 depuis la fiche) |
| d8 Harmoniser les qualités | « À traiter » → [Harmoniser] (retélécharge en forçant la qualité) | **1** |
| Trier, filtrer, agir en masse | Bibliothèque → puce ou tri → [Sélectionner] → action | 3 à 4 |

### (e) Regarder un épisode ou le film

| Chemin | Interactions |
|---|---|
| Flux → « Continuer à regarder » (colonne Coup d'œil) | **1** |
| Carte terminée → [Regarder] ou [Regarder le film] | 1 |
| **Pendant le téléchargement** → [Regarder l'ép. 1] sur la carte en cours | 1 |
| Bibliothèque → affiche (au survol ou au focus) → « Reprendre · ép. 14 » | 2 |
| Dans le lecteur → épisode suivant (enchaînement automatique) | 0 |

### (f) Reprendre après fermeture ou coupure

| Scénario | Comportement | Interactions |
|---|---|---|
| f1 Onglet fermé, moteur toujours actif | Les téléchargements continuent ; état exact à la réouverture | 0 |
| f2 Moteur arrêté ou PC éteint | Au démarrage : `downloading` figé devient « Interrompu », puis reprise automatique avec un bandeau d'information | 0 (1 si le réglage est désactivé) |
| f3 Coupure Internet | Pause automatique « hors ligne », aucun échec compté, reprise à l'octet près | 0 |
| f4 Moteur injoignable | Lecture seule, reconnexion automatique | 0 à 1 |
| f5 Lien signé expiré | Nouvelle résolution invisible | 0 (1 si échec) |
| f6 Fichier supprimé dans l'Explorateur | Entrée dans « À traiter » → [Retélécharger] | 1 |

### Récapitulatif

| Parcours | Cible (recherche) | Concept B |
|---|---|---|
| (a) URL → tout télécharger | ≤ 3 | **2** (1 en mode express) |
| (b) Connaître l'avancement | 0 | **0** |
| (c) Retrouver une série | ≤ 3, < 5 s | **2** + saisie |
| (d) Réparer ou compléter | 1 | **1** (depuis le Flux) |
| (d) Créer le film | 1 à 2 | **1 à 2** |
| (e) Reprendre le visionnage | 1 | **1** (Flux) / 2 (Bibliothèque) |
| (f) Reprendre après coupure | 0 à 1 | **0** |

---

## 5. Interactions signatures

### S1. Coller, c'est presque fini

- **Instantané.** Dès le collage, une étiquette locale confirme le type de lien (« Lien DramaBox · série 41000105199 · VF »), avant tout appel réseau. Puis un squelette 9:16, puis l'aperçu avec le bouton **déjà focalisé**. Il n'y a pas de bouton « Analyser ».
- **Partout.** Ctrl+V hors d'un champ passe par l'événement `paste`, ce qui ne demande aucune autorisation. On peut aussi glisser-déposer un lien sur la fenêtre.
- **À la chaîne.** Après Entrée, le champ se vide et **garde le focus** : on colle le lien suivant sans toucher la souris. Les séries s'empilent dans « En file ».
- **Collage express** (option, désactivée par défaut).
  - Un lien reconnu démarre après un décompte de 3 s **dans le bouton** : « Démarrage dans 3 s · Échap pour annuler ».
  - Jamais pour un doublon, en mode sonde, si l'espace disque manque, ou si la version préférée n'existe pas : dans ces cas, on revient à l'aperçu normal.

### S2. La carte qui vit

- **Un objet, une place, toute une vie.** Aperçu → en file → en cours → vérifié → film prêt.
- **Transition.** Au lancement, l'aperçu glisse jusqu'à sa section (240 ms, instantané si les animations sont réduites). Le focus revient au champ, et la région `status` annonce le lancement.
- **Une carte par version de série.** Relancer, compléter, harmoniser ou créer le film fait **remonter la même carte** en haut de la section concernée. Son historique (« 3 opérations ») se déplie dans le journal. On ne voit jamais trois cartes pour la même série.

### S3. La pellicule

- **Ce que c'est.** Une barre de 8 px divisée en **un segment par épisode, de largeur proportionnelle à sa durée** (de 50 s à 3 min 30). Elle montre donc à la fois l'avancement réel en temps de vidéo et le statut de chaque épisode.
- **Couleurs.** Vert = vérifié · cyan qui se remplit = en cours · rouge avec « ! » = échec · hachures = indisponible · ambre = interrompu ou 720p · vide = à venir.
- **La barre ne recule jamais.** Si un segment doit repartir de zéro (nouvelle source), il reste affiché à son maximum avec le repère « nouvel essai ».
- **Au survol** : « Ép. 36 · 2 min 14 · 45 % ». **Au clic** : la carte se déplie sur la grille.
- **Cas limites.** Durées inconnues (mode sonde) : segments égaux. Au-delà de 150 épisodes : barre continue avec des repères. La grille reste toujours la référence.

### S4. La grille décimale et la sélection par plages

- **10 tuiles par ligne sur desktop.** L'épisode 47 est ligne 5, colonne 7 : on le retrouve sans compter. C'est le repère « Ep 1 … Ep 62 » de dramafren, rendu lisible. Sur mobile, 5 par ligne (une dizaine = 2 lignes). Au-delà de 100 épisodes, des onglets 1–100, 101–200.
- **Un seul composant partout** : sélection dans l'aperçu, statut dans la carte dépliée et la fiche, navigation dans le lecteur.
- **Sélection.**
  - Clic = cocher ; Maj+clic ou glisser = plage.
  - Raccourcis : **Tous · Aucun · Manquants · Échecs · Inverser**.
  - Champ texte « 1-10, 28, 50- » **synchronisé dans les deux sens**. Il accepte le tiret long « 1–10 », les espaces et les plages ouvertes.
  - Résumé en direct : « 23 épisodes · ≈ 270 Mo ».
  - La sélection se montre par un contour et une coche, **jamais par la couleur de fond**, réservée au statut.
- **Clavier.** Un seul arrêt de tabulation, puis déplacement aux flèches (`role="grid"`). Début/Fin, Espace = sélectionner, Maj+flèches = étendre, Entrée = action de la tuile.

### S5. « À traiter » et « Tout réparer »

- **Une boîte de réparation, pas une liste d'erreurs.** Chaque ligne décrit le problème en langage courant et propose **son** remède : réessayer, reprendre, harmoniser, retélécharger, recréer le film.
- **[Tout réparer]** lance une opération par série concernée, avec un récapitulatif : « 3 séries · 5 épisodes · ≈ 60 Mo ».
- **Ce qu'on ne veut pas voir** peut être ignoré (choix mémorisé). Une série volontairement partielle n'y apparaît jamais. Un épisode indisponible à la source propose « Réessayer plus tard », sans rouge permanent.
- La section disparaît quand elle est vide, ce qui donne une vraie satisfaction de « boîte vide ».

### S6. Le film en un geste

- **Pré-vol anticipé** : l'état du bouton est connu avant le clic.
- **Progression dans le bouton** pendant environ 6 s : « 38/62 assemblés ».
- **Chaque refus devient un choix**, avec la solution recommandée en premier (retélécharger en 1080p plutôt que ré-encoder ; compléter plutôt que film partiel).
- Après la réussite, **une seule** suggestion : « Libérer 684 Mo en supprimant les épisodes ? Le film reste. »

### S7. Regarder pendant que ça arrive

Le moteur télécharge les épisodes dans l'ordre. Dès que l'épisode 1 est vérifié, la carte en cours propose [Regarder l'ép. 1]. Dans le lecteur, les épisodes suivants deviennent lisibles au fil de l'eau (« encore en téléchargement, 45 % »). Le téléchargement complet d'une minute devient invisible : on regarde déjà.

### S8. Présence périphérique

- Titre d'onglet et favicon avec anneau.
- Pilule d'en-tête qui résume le flux.
- **Une** notification Windows par série (fin ou arrêt bloquant), jamais une par épisode.
- Annonces pour lecteur d'écran par paliers (lancement, 25 %, 50 %, 75 %, fin, échecs regroupés), avec au moins 10 s entre deux annonces.
- Sur la page Flux, **pas de toast** pour une fin de série : la carte l'affiche déjà, on évite le doublon.

### S9. La technique, seulement quand on la demande

- Chaque carte a un journal traduit en langage courant (« Ép. 14 indisponible à la source : on continue avec les autres »).
- [Détails techniques] déplie le message brut du moteur, copiable.
- La commande CLI équivalente (`sdg fetch 41000105199 --lang fr --film`) est affichée dans l'aperçu et le menu ⋯. C'est le pont avec le « défi » en ligne de commande.
- Les URL signées ne sortent jamais du moteur.

---

## 6. Direction visuelle

### 6.1 Ambiance et thème

**Une « régie de nuit ».** Un bleu nuit calme et une interface presque monochrome. La couleur vient des covers (visages, rouges, ors) et des états. **La seule chose qui bouge, c'est ce qui progresse.**

**Le thème sombre par défaut se justifie par :**
- le contenu vidéo et le lecteur intégré ;
- des covers très saturées, qui ressortent sur fond sombre ;
- la continuité avec dramafren (bleu nuit, accents bleus) ;
- un usage en second écran, souvent le soir.

Un thème clair est disponible (Réglages : Sombre / Clair / Système), avec les mêmes exigences de contraste.

### 6.2 Palette (thème sombre)

| Jeton | Hex | Usage | Contraste sur `bg` |
|---|---|---|---|
| `bg` | #0B1220 | Fond | — |
| `surface` | #131C2E | Cartes, barre du haut | — |
| `raised` | #1B2640 | Champ, carte survolée, fenêtres flottantes | — |
| `line` | #26324D | Séparateurs décoratifs | décoratif |
| `border-control` | #6A7A99 | Contours de champs et de tuiles | 4,3:1 (≥ 3:1) |
| `text` | #E8ECF4 | Texte | 15,8:1 |
| `text-muted` | #A3AEC4 | Méta, aides | 8,4:1 |
| `accent` | #5B9BFF | Action principale (**texte #0B1220 dessus**, jamais blanc), liens, sélection | 6,8:1 |
| `focus` | #8FC1FF | Anneau de 2 px, décalé de 2 px | 10,0:1 |
| `active` | #4FD1E8 | **En cours** : remplissage de pellicule et de tuile, point d'activité | ≈ 10,5:1 |
| `success` | #3DD68C | Vérifié | 10,0:1 |
| `warning` | #F5B544 | Interrompu, 720p, fichier disparu, partiel | 10,3:1 |
| `danger` | #FF6B6B | Échec | 6,8:1 |
| `unavailable` | #7C8699 + hachures | Indisponible à la source | ≈ 5,1:1 |

La couleur « en cours » (**cyan**) est volontairement distincte de l'accent bleu : le statut « en cours » ne se confond jamais avec la sélection ou le bouton principal.

**Thème clair** (à valider au contrasteur, sauf l'accent) : `bg` #F6F8FC · `surface` #FFFFFF · `text` #0E1626 · `text-muted` #4A5670 · `accent` #1F5FD6 (≈ 5,7:1 sur blanc, texte blanc permis) · `active` #0E7C93 · `success` #177A4D · `warning` #9A5B00 · `danger` #C62828.

### 6.3 Codage des statuts (jamais par la couleur seule)

| Statut affiché | Moteur / dérivé | Tuile et segment | Icône |
|---|---|---|---|
| En attente | `pending` sélectionné | Contour plein `border-control`, numéro atténué | — |
| Non demandé | `pending` hors sélection | Contour **pointillé** | — |
| En cours 45 % | `downloading` + job actif | Remplissage cyan de bas en haut (`--p`) | flèche ↓ |
| Vérifié | `done` + durée conforme | Fond vert plein, numéro couleur fond | coche |
| Téléchargé, non vérifié | `done` en mode sonde | Fond vert à 35 % + contour vert | coche creuse « ~ » |
| Qualité différente | `done`, qualité ≠ majorité | Comme vérifié + coin ambre « 720 » | badge |
| Interrompu | `.part` sans job, ou `downloading` figé | Contour ambre, remplissage figé | « ‖ » |
| Échec | `failed` réessayable | Contour rouge de 2 px, fond rouge à 15 % | « ! » |
| Indisponible | `failed` (épisode indisponible à la source) | Hachures grises | « – » |
| Fichier disparu | `done` sans fichier | Contour ambre pointillé | « ? » |
| Retiré (film gardé) | `removed` | Vide, contour pointillé | pellicule |
| **Sélection** | — | Contour accent de 2 px + coche dans le coin | — |

- En mode Contraste élevé de Windows (`forced-colors`), on garde les bordures et les icônes système, et la barre de progression conserve son contour.
- Chaque tuile a un nom accessible complet : « Épisode 14, 2 min 05, téléchargé et vérifié, 13,2 Mo, 1080p ».

### 6.4 Typographie

- **Interface : Segoe UI Variable (Text et Display)**, avec repli sur « Segoe UI » puis `system-ui`.
  - Police native de Windows 11 (Segoe UI sur Windows 10) : zéro fichier à charger.
  - Compatible avec la politique de sécurité (CSP) `font-src 'self'`.
  - Accents français impeccables.
- **Chiffres tabulaires** (`tabular-nums`) partout où ça bouge (compteurs, débit, temps restant, tailles), pour éviter que les nombres sautillent.
- **Chasse fixe : Cascadia Mono, puis Consolas**, pour la commande CLI, les chemins, les n° de série et le journal.
- **Échelle (en rem, base 16 px)** : 12 (badges, légendes) · 13 (méta) · 14 (texte d'interface) · 16 (titres de carte) · 20 (champ principal, titres de section) · 28 (titre de fiche). Graisses 400 et 600. Titres limités à 2 lignes, titre complet en infobulle.
- **Mise en forme française** avec `Intl` en `fr-FR` : « 684 Mo », « 1 h 32 », « 7,8 Mo/s », espace insécable avant « : ? ! », guillemets « ».

### 6.5 Densité, grilles et covers

- **Flux.**
  - Colonne de 760 px pour la lisibilité ; cartes repliées de 112 px, 12 px d'écart.
  - Colonne « Coup d'œil » de 320 px.
  - Gouttières de 32 px (desktop), 24 px (laptop), 16 px (mobile).
  - Densité **confortable** : c'est l'écran qu'on regarde du coin de l'œil.
- **Pellicule** : 8 px de haut (12 px au survol), 1 px entre les segments.
- **Grille décimale.**
  - Desktop : tuiles de 48×48, 10 par ligne (10×48 + 9×6 = 534 px).
  - Mobile : tuiles de 60×60, 5 par ligne (5×60 + 4×8 = 332 px, pour 358 px utiles).
  - Cibles tactiles d'au moins 44 px partout.
- **Affiches.**
  - 7 colonnes d'environ 176 px à 1440 px : la cover native de 360 px reste nette jusqu'à 180 px en affichage à 200 %.
  - 5 à 6 colonnes à 1280 px, 3 à 390 px (environ 111 px).
  - Coins arrondis de 8 px ; badges petits, dans les coins bas, jamais sur les visages.
- **Covers.**
  - Jamais agrandies en bandeau paysage.
  - Cover nette posée sur la même cover floutée (flou 48 px, opacité 35 %) dans l'aperçu, la fiche et le lecteur.
  - Voile #0B1220 à 85 % sous tout texte posé sur une image.
  - Mode sonde : cover générée (dégradé dérivé du n° de série + « Série 41000105199 »).
- **Bibliothèque en vue Liste** : densité **dense** (lignes de 48 px), pensée pour un utilisateur avancé qui a plus de 50 séries.

### 6.6 Mouvement et icônes

- **Apparitions** : 150 à 200 ms, ease-out.
- **Transformation aperçu → carte** : 240 ms.
- **Pellicule et tuiles** : mises à jour 4 fois par seconde, transition linéaire de 250 ms. Rien d'autre n'est animé en continu.
- **Animations réduites** (`prefers-reduced-motion`) : tout devient instantané, sans effet de brillance ni rayures ; les décomptes s'affichent en texte.
- **Icônes** : sprite SVG tiré de Lucide (licence ISC), en 16 et 20 px, trait de 1,75.

---

## 7. Risques et faiblesses assumés

| # | Risque | Pourquoi on l'accepte | Parade |
|---|---|---|---|
| 1 | **La Bibliothèque passe au second plan** : regarder ou parcourir demande un clic de plus que dans un concept centré sur la collection. | Le geste le plus fréquent est l'ajout, et les réparations remontent déjà dans le flux. | Colonne « Coup d'œil » (Continuer à regarder, Ajoutées récemment), Ctrl+K, réglage « Page d'accueil : Bibliothèque ». Point à observer en usage. |
| 2 | **L'accueil est souvent au repos** : une opération dure une minute, donc le flux est surtout de l'historique. | Le champ reste le héros ; l'historique sert de raccourci (Regarder, Créer le film). | « À traiter » et « Coup d'œil » donnent de la valeur au flux même inactif ; historique groupé, replié, effaçable. |
| 3 | **Deux représentations d'une même série** (carte de flux et fiche) peuvent diverger. | C'est le prix d'un flux centré sur l'action. | Un seul store alimenté par SSE et l'index ; la carte n'est qu'une vue de la version ; même composant de grille ; une carte par version. |
| 4 | **Le Collage express peut déclencher des téléchargements involontaires** (environ 700 Mo). | Il pousse l'angle au bout, pour un utilisateur avancé. | Désactivé par défaut ; exclu pour les doublons, le mode sonde et le disque insuffisant ; décompte de 3 s annulable ; « Arrêter » garde les épisodes déjà vérifiés. |
| 5 | **La pellicule devient illisible aux extrêmes** : plus de 150 épisodes, durées inconnues, segments de 1 px. | Le cas réel mesuré tient dans 60 à 100 épisodes. | Repli en barre continue avec repères ; la grille reste la référence. |
| 6 | **« À traiter » peut devenir une liste de reproches** : épisodes indisponibles pour de bon, séries partielles voulues. | Une boîte de réparation vaut mieux que des erreurs dispersées. | « Ignorer » par ligne (mémorisé) ; une sélection explicite ne génère jamais d'alerte ; « Réessayer plus tard » sans rouge permanent. |
| 7 | **Forte dépendance au temps réel du moteur** (événements, annulation, codes d'erreur). Sans eux, le flux se dégrade en relecture des manifests toutes les 2 s : les tuiles sautent directement à « vérifié », sans débit ni temps restant. | La promesse du concept, c'est justement le suivi. | L'étape 0 du plan (moteur pilotable) est un **prérequis** ; voir l'annexe. |
| 8 | **La métaphore du gestionnaire de téléchargements attire vers la densité de qBittorrent** (colonnes, une ligne par épisode). | Le modèle mental est juste ; seul l'excès de densité serait nuisible. | Garde-fou : une carte par version, jamais une ligne par épisode ; la grille n'apparaît qu'en dépliant. |
| 9 | **Le mobile 390 est dessiné mais sans usage réel en V1** : le serveur n'écoute que sur 127.0.0.1, sans authentification pour le réseau local. | La disposition étroite sert dès maintenant aux fenêtres en demi-écran (Snap, 720 px). | Accès depuis le téléphone en V2, avec une vraie authentification. |
| 10 | **Plusieurs onglets ouverts** : un flux SSE par onglet, et Chrome limite à 6 connexions par hôte en HTTP/1.1. | Le flux reste typiquement ouvert en permanence. | MVP : détection via `BroadcastChannel` et [Utiliser ici] ; V2 : un `SharedWorker` pour une seule connexion. |
| 11 | **Le libellé « Flux » reste à valider** auprès de l'utilisateur. | Court, et distinct de « Bibliothèque ». | Alternatives à tester : « Activité », « Accueil ». |

---

## Annexe : ce que le concept exige du moteur

| Besoin du concept | Ajout côté moteur | Priorité (inventaire) |
|---|---|---|
| Pellicule, carte vivante, pilule, titre d'onglet | Événements structurés (octets, résolution, vérification, fin) diffusés en SSE, 4 fois par seconde au plus | P0 |
| Pause et « Arrêter (garder les 34 épisodes) » | Arrêt injectable de l'extérieur ; `Cancelled` remet l'épisode en `pending` | P0 |
| « Interrompu » fiable, reprise au démarrage | Réconciliation disque/manifest ; jobs persistés | P0 |
| Distinguer « Indisponible » d'« Échec » | Champ `error_code` dans le manifest | P0 |
| Aperçu en moins de 2 s, sans sonde | `preview_series()` + cache de 15 min ; progression en mode sonde dans le job | P0 |
| « Harmoniser », « Retélécharger en 1080p » | Option `force` + événement de repli de qualité | P0 |
| « Non demandé » ≠ « En attente » ; « Compléter » | Options demandées stockées dans le manifest | P0 |
| Coup d'œil et bibliothèque hors ligne | Index de bibliothèque + `cover.jpg` locale | P0 |
| Proposer seulement les versions doublées | Catalogue des langues (titre localisé, doublée oui/non) | P1 |
| Estimations taille, temps, espace libre | Débit mesuré + `disk_usage` | P1 |
| Remèdes du film | `plan_summary` avec `fixes` ; `FilmError.code` ; plusieurs films | P1 |
| « Continuer à regarder » | Stockage de la progression de lecture (`.sdg/watch.json`) | Nouveau |
| Mode hors ligne | Connectivité mesurée par le moteur | Nouveau |
| « C'est le lien de l'épisode 14 » | Lecture du numéro d'épisode dans les URL `/ep/` | Optionnel |