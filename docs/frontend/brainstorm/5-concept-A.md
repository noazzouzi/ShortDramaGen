# Concept A — Bibliothèque d'abord

# Concept A : « Bibliothèque d'abord »

> **Ta vidéothèque se remplit toute seule.**
> Hypothèses reprises de la recherche :
> - serveur local `sdg ui` (stdlib, 127.0.0.1), flux SSE, page unique sans build, routes par hash ;
> - un manifest par dossier, donc un dossier par couple (série, langue) ;
> - statuts réellement écrits : `pending`, `downloading`, `done`, `failed`. `resolved` n'existe pas.
>
> Tout le texte de l'interface est en français et tutoie l'utilisateur.

---

## 1. Idée directrice

**En deux phrases.** Ta collection *est* l'application. L'accueil est un mur d'affiches 9:16 où chaque série montre son propre état, et tout se fait sur la série elle-même, depuis sa carte ou sa fiche : suivre, réparer, compléter, regarder, fusionner. Coller un lien n'ouvre pas un formulaire mais la fiche d'une série que tu n'as pas encore ; un appui sur Entrée, et son affiche prend place sur le mur, grise, puis se colore au fil des épisodes vérifiés.

**Pourquoi c'est le bon choix pour cet utilisateur**
- **Son objectif est une collection** : des séries complètes, vérifiées, dans la bonne langue, transformées en films. La CLI télécharge déjà très bien. Ce qui lui manque, c'est une **vue d'ensemble**. C'est exactement ce que ce concept met au premier plan.
- **Les opérations sont courtes** : une série en 40 s à 1 min 40, un film en environ 6 s. Une page « Téléchargements » serait vide 99 % du temps. L'activité se montre sur l'affiche, avec un badge et un tiroir, mais n'a pas d'écran de premier niveau.
- **Les covers portrait se reconnaissent plus vite que les titres traduits.** « Qui Est la Véritable Mme Lafont ? » et « One Night to Forever » désignent la même série : le visage sur l'affiche, lui, ne change pas.
- **Des repères qu'il connaît déjà** : le bleu nuit et la grille « Ep 1 … Ep 62 » de dramafren, le mur d'affiches de Plex et de DramaBox. Rien à apprendre.
- **Le mur reflète le disque** (`downloads/*/manifest.json`). La CLI et l'interface cohabitent : une série téléchargée en terminal apparaît sur le mur.

**Ce que le concept refuse, pour aller au bout de l'angle**
- Pas de page « File » ni « Téléchargements » en navigation principale (sauf sur mobile, où un onglet sert de tiroir).
- Pas de barre latérale : il n'y a que trois destinations, l'en-tête suffit et le mur prend toute la largeur.
- Pas de formulaire d'ajout : un lien collé devient une fiche.
- Pas de vue « fichiers ». Dossiers, n° de série et manifest restent dans « Détails techniques ».
- Pas d'onglet « Search Title » qui ne mènerait à rien.

---

## 2. Architecture de l'information

### 2.1 Arborescence

```
ShortDramaGen
├── En-tête (toujours visible)
│   ├── Logo ─────────────────────────► #/  Bibliothèque
│   ├── Barre « Chercher ou coller un lien »   (/, Ctrl+K ; Ctrl+V n'importe où)
│   │   ├── texte libre ──► résultats de la bibliothèque + commandes (palette)
│   │   └── lien ou n° ───► Aperçu d'ajout (panneau sous l'en-tête) ──► [Voir la fiche]
│   ├── [+ Ajouter]  (même barre, en mode ajout, avec un bouton « Coller »)
│   ├── Activité : icône ; anneau + nombre quand ça tourne ──► Tiroir Activité (T)
│   └── Réglages : pastille si un problème de santé
│
├── #/  Bibliothèque (accueil)
│   ├── Bandeaux conditionnels : reprise · hors ligne · moteur injoignable
│   ├── Barre d'outils : stats · filtres (puces + compteurs) · tri · vue Affiches | Liste
│   ├── Étagère « À traiter »            (si non vide, masquée pendant une recherche ou un filtre)
│   ├── Étagère « Continuer à regarder » (si non vide, V1.1)
│   └── Mur d'affiches, ou Liste dense   (+ sélection multiple → barre d'actions)
│
├── #/serie/<bookId>/<version>  Fiche série   (version = vo | fr | es …)
│   ├── Mode « Dans ta bibliothèque » ou mode « Aperçu » (série pas encore possédée)
│   ├── Héros : cover, titres, méta, synopsis, onglets de version (+ langue)
│   ├── Barre de santé + UNE action principale
│   ├── Épisodes : grille décimale + volet (épisode ou sélection)
│   ├── Film
│   ├── Stockage
│   ├── Détails techniques (repliés)
│   └── …/lire/<n> | …/lire/film ──► Théâtre (surcouche plein écran)
│
├── #/activite     (page sur mobile ; sur desktop, la même route ouvre le tiroir)
└── #/reglages/<section>   Général · Téléchargement · Film (ffmpeg) · Stockage · Affichage · Santé · À propos

Dialogues : Supprimer… · Choix du film · Ajout de plusieurs liens · Raccourcis (?)
```

### 2.2 Modèle mental et vocabulaire

| Objet affiché | Réalité moteur | Où on le voit |
|---|---|---|
| **Série** (une carte) | Groupe de dossiers qui partagent le même `book_id` | Mur, recherche |
| **Version** : VO (anglais), VF, VE… | Un dossier `<bookId>-<slug>[-<lang>]` + son `manifest.json` | Onglets de la fiche, puces sur la carte |
| **Épisode 14** | `E014.mp4` + une entrée du manifest | Tuile de la grille, théâtre |
| **Film** | `<Titre>.mp4` + l'entrée `film` du manifest | Section Film, puce « Film » |
| **Activité** | Jobs `fetch` et `film` (file persistée) | Affiche qui se colore, tiroir |
| « n° de série », dossier, commande CLI | `book_id`, chemin, `sdg fetch …` | Détails techniques uniquement |

### 2.3 Navigation

| | Desktop 1440 | Mobile 390 |
|---|---|---|
| Principale | En-tête de 64 px : logo · barre de recherche et de lien (640 px max) · [+ Ajouter] · Activité · Réglages | En-tête de 56 px (logo, champ) + **barre du bas** : Bibliothèque · Ajouter · Activité (badge) · Réglages |
| Profondeur | 2 niveaux au plus : Bibliothèque → Fiche (→ Théâtre en surcouche) | Idem |
| Retour | « ← Bibliothèque » dans la fiche. Le bouton Retour du navigateur restaure les filtres, le tri et la position de défilement. | Geste retour, ou flèche dans l'en-tête |
| État dans l'URL | `#/?f=a-completer&tri=activite&vue=affiches&q=lafont`, et version dans la route de la fiche | Idem |
| Raccourcis | `/` ou `Ctrl+K` : barre · `Ctrl+V` hors d'un champ : coller un lien · `A` : ajouter · `T` : activité · `?` : aide · `Échap` : fermer. Les raccourcis à une touche sont inactifs dans les champs et peuvent être désactivés. | — |

---

## 3. Écrans

Chaque écran est décrit selon le même plan : **But**, **Zones (de haut en bas)**, **Actions**, **États** et **Mobile 390**.

### 3.0 Coquille (en-tête, bandeaux, toasts, tiroir)

**But.** Garder l'ajout et l'activité à un geste, où que l'on soit.

**Zones**
1. **En-tête collant (64 px)**, avec cinq éléments :
   - le logo ;
   - la barre « Chercher dans ta bibliothèque ou coller un lien DramaBox », avec l'indice `Ctrl K` ;
   - [+ Ajouter] ;
   - l'icône Activité ;
   - l'icône Réglages.
2. **Bandeau contextuel** (au plus un à la fois, par priorité) : moteur injoignable > disque plein > reprise au démarrage > hors ligne.
3. **Contenu de la route.**
4. **Toasts** en bas à gauche (3 empilés au plus). Le tiroir Activité s'ouvre à droite (380 px) et ne recouvre donc jamais les toasts.

**Actions.** Coller n'importe où (`Ctrl+V` hors d'un champ remplit la barre et lance l'analyse), ouvrir l'activité, ouvrir les réglages.

**États**

| État | Rendu et texte |
|---|---|
| Démarrage | Barre fine sous l'en-tête. « Lecture de ta bibliothèque… 23 séries trouvées » |
| Activité au repos | Icône grise sans anneau. Le tiroir donne accès à l'historique. |
| Activité en cours | Anneau de progression + « 1 ». Titre d'onglet « (34/62) ShortDramaGen ». Favicon avec anneau. |
| Activité avec échecs | Pastille rouge sur l'icône. Titre d'onglet « (2 échecs) ShortDramaGen » |
| Hors ligne | Bandeau discret : « Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls. » |
| Moteur injoignable | Bandeau rouge (`role="alert"`), interface en lecture seule avec le dernier état connu : « Le moteur ne répond plus. On essaie de se reconnecter… » [Réessayer maintenant] · « Si tu as fermé la fenêtre du moteur, relance ShortDramaGen. » |
| Santé dégradée | Pastille sur Réglages (ffmpeg absent, disque presque plein). **Aucun bandeau permanent** : le message apparaît là où ça bloque. |

**Mobile 390.** Barre du bas de 4 cibles de 56 px ; la barre de recherche et de lien passe sous le logo ; les toasts s'affichent au-dessus de la barre du bas.

---

### 3.1 Bibliothèque (accueil)

**But.** Voir toute la collection d'un coup d'œil, savoir ce qui demande de l'attention et agir depuis la carte.

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ ShortDramaGen   [ Chercher dans ta bibliothèque ou coller un lien…   Ctrl K ] [+ Ajouter]  (o)1  Réglages• │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│ Bibliothèque   12 séries · 15 versions · 11,8 Go · 182 Go libres sur C:    Tri : Activité ▾  [Affiches|Liste] │
│ (Toutes 12) (En cours 1) (À compléter 3) (Avec échecs 1) (Film prêt 9) (Sans film 3) │ VO · VF · VE  │
│                                                                                            │
│ À traiter · 3                                                                              │
│ ┌────┐ Qui Est la Véritable…  ┌────┐ Contrat d'un an…   ┌────┐ Série 41000999999            │
│ │    │ VF · 2 échecs          │    │ VO · 58/62         │    │ Interrompu · 34/48            │
│ └────┘ [Réessayer les 2]      └────┘ [Compléter (4)]    └────┘ [Reprendre]                   │
│                                                                                            │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                │
│ │░░░░░░░░│ │        │ │        │ │        │ │        │ │        │ │        │                │
│ │░ gris ░│ │ cover  │ │        │ │        │ │        │ │        │ │        │                │
│ │▓▓▓▓▓▓▓▓│ │  9:16  │ │        │ │        │ │        │ │        │ │        │                │
│ │▓couleur│ │        │ │        │ │        │ │        │ │        │ │        │                │
│ │↓ 34/62 │ │        │ │! 2     │ │        │ │        │ │        │ │        │                │
│ │VF      │ │VO·VF Film│VO      │ │        │ │        │ │        │ │        │                │
│ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘                │
│ Una Noche   One Night   Qui Est la                                                          │
│ Para…       to Forever  Véritable…                                                          │
│ ≈ 40 s      62 ép.·1 h 32 60/62 ép.                                                         │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Zones (de haut en bas)**
1. **Ligne de titre** :
   - « Bibliothèque » ;
   - les stats (séries, versions, taille, espace libre sur le disque) ;
   - le tri : **Activité récente** (par défaut ; les séries actives remontent d'elles-mêmes), Ajoutées récemment, Regardées récemment, Titre A→Z, Taille, Durée, Nombre d'épisodes ;
   - le choix de vue Affiches ou Liste (mémorisé).
2. **Puces de filtre avec compteurs**, cumulables :
   - Statut : En cours, À compléter, Avec échecs, Interrompues, Film prêt, Sans film ;
   - Version : VO, VF, VE…, par nom et jamais par drapeau ;
   - « Qualités mélangées », affichée seulement si elle ne vaut pas 0. Les puces à 0 sont masquées.
   - Compteur « 12 séries sur 54 » et [Effacer les filtres] quand un filtre est actif.
3. **Étagère « À traiter »** : une rangée horizontale de cartes compactes, chacune avec son **bouton de réparation**. Elle regroupe les échecs, les versions incomplètes, les interrompues, les films obsolètes et les fichiers manquants. Elle est masquée si elle est vide, et pendant une recherche ou un filtre.
4. **Étagère « Continuer à regarder »** (V1.1, dépend du suivi de visionnage).
5. **Mur** : `repeat(auto-fill, minmax(160px, 1fr))`, soit 7 colonnes d'environ 180 px à 1440.
6. **Marge basse de 96 px**, pour que les toasts et la barre de sélection ne masquent jamais le dernier rang.

**Anatomie d'une carte (une par série)**

| Zone | Contenu | Règle |
|---|---|---|
| Affiche 9:16 | Cover locale `cover.jpg`, `alt=""` puisque le titre est affiché dessous | Affiche générée si la cover est absente (mode sonde) : dégradé tiré du n° de série + titre en grand |
| Bandeau bas (dégradé `#0B1220` à 85 %) | **Ligne d'état**, seulement si l'état n'est pas nominal : `↓ 34/62 · ≈ 40 s` · `! 2 échecs` · `‖ Interrompu · 34/62` · `En file · 2e` · `? 1 fichier manquant`. Puis les **puces** : versions possédées (« VO · VF ») et « Film » (violet) ou « Film partiel » (contour). | **Aucun badge en haut**, où sont les visages. 2 puces au maximum, « +1 » au-delà |
| Sous l'affiche | Barre de complétude de 4 px, **seulement si la série est incomplète** (segments vert, rouge, ambre). Titre sur 2 lignes (titre complet en infobulle). Méta : « 62 ép. · 1 h 32 » ou « 58/62 ép. · 4 manquants » | **Le mur est calme quand tout va bien** : pas de barre verte sur chaque carte complète |
| Au survol **et au focus** | Case à cocher en haut à gauche, bouton « ⋯ » en haut à droite, **action principale** en bas de l'affiche | Rien n'existe uniquement au survol : le focus clavier et le menu « ⋯ » donnent accès aux mêmes actions |
| Titre affiché | Titre de la **version préférée** si tu la possèdes (réglage « Titres en : Français si disponible »), sinon celui de la VO | La recherche porte sur tous les titres |

**Action principale d'une carte.** Elle suit la priorité des états, toutes versions confondues. **Sur la carte, la lecture l'emporte ; dans la fiche, c'est la gestion.**

| État le plus urgent | Bouton sur la carte |
|---|---|
| Téléchargement en cours | [Pause] |
| En file | [Pause] (avec la position affichée) |
| Épisodes en échec | [Réessayer (2)] |
| Interrompue | [Reprendre] |
| Incomplète | [Compléter (4)] |
| Complète, visionnage en cours | [▶ Reprendre · ép. 14] |
| Complète, avec film | [▶ Regarder le film] |
| Complète, sans film | [▶ Regarder] |

**Menu « ⋯ »** : Ouvrir la fiche · Regarder · Créer le film · Ajouter une version › · Ouvrir le dossier · Vérifier les nouveaux épisodes · Supprimer…

**Vue Liste (dense, lignes de 56 px)**
- Colonnes : Affiche 32×57 · Titre (+ titre VO en gris) · Versions · Épisodes (x/y + mini-barre) · Durée · Taille · Film · Qualité · Modifiée · État.
- Toutes les colonnes sont triables. Le tri par taille sert à libérer de l'espace.

**Sélection multiple**
- Clic sur la case, Maj+clic pour une plage, `Ctrl+A` quand le mur a le focus.
- Barre d'actions flottante en bas : « 3 séries · 2,1 Go · [Compléter] [Réessayer les échecs] [Créer les films] [Libérer l'espace (garder les films)] [Supprimer…] [×] ».
- Exemple de combinaison : filtre « À compléter », Ctrl+A, [Compléter].

**États**

| État | Rendu et texte |
|---|---|
| **Vide (premier lancement)** | La barre se place **au centre de l'écran, déjà focalisée** : « Ta bibliothèque est vide. Colle le lien d'une série DramaBox : on récupère tous les épisodes, vérifiés, jusqu'en 1080p. » [Essayer avec un exemple] remplit l'URL de *One Night to Forever*. Si un ancien dossier `downloads` de la CLI contient des manifests : « 3 séries trouvées dans …\ShortDramaGen\downloads » [Les afficher ici]. Note discrète si ffmpeg manque : « Films : ffmpeg manquant » [Installer]. |
| Chargement | Affiches squelettes 9:16 en aplat statique (sans scintillement si reduced-motion) |
| Succès | Étagères conditionnelles + mur |
| Partiel | « 2 dossiers n'ont pas pu être lus et sont masqués. » [Voir lesquels] (manifest corrompu) |
| Erreur | « Impossible d'ouvrir ton dossier de séries (D:\Séries). Il a peut-être été déplacé, ou le disque est débranché. » [Choisir un autre dossier] [Réessayer] |
| Filtre sans résultat | « Aucune série “À compléter · VE”. » [Effacer les filtres] |
| Hors ligne | Identique (covers en cache). Les actions réseau restent visibles, désactivées avec leur raison : « Au retour de la connexion ». |
| Changement sur le disque | Au retour du focus sur la fenêtre, le mur est relu (avec ETag). Toast discret : « Mis à jour depuis le disque : 1 série ajoutée. » |

**Mobile 390**
- 3 colonnes d'environ 112 px (gouttières de 16 px, espacement de 10 px), titre sur 2 lignes.
- « ⋯ » toujours visible sous le titre (cible de 44 px). Un appui sur la carte ouvre la fiche.
- Puces de filtre dans une rangée qui défile horizontalement (la page, elle, ne défile jamais horizontalement). Tri et filtres avancés dans une feuille du bas « Filtres (2) ».
- La vue Liste devient une liste compacte : cover, titre, état.

---

### 3.2 Barre « Chercher ou coller un lien » : recherche et palette

**But.** Un seul champ pour retrouver ce qu'on a et ajouter ce qu'on n'a pas.

**Détection au fil de la saisie** (locale, mêmes règles que `inputs.py`, sans réseau) :

| Ce que contient le champ | Mode | Puce affichée dans le champ | Comportement |
|---|---|---|---|
| Texte libre (« lafont ») | **Recherche** | — | Liste déroulante : 5 séries au plus (terme surligné, « trouvé dans le titre VF »), puis 3 commandes au plus. **Le mur filtre en direct** derrière. |
| URL dramaboxdb.com, dramabox.com, lien de partage, URL dramafren ou n° de 8 à 14 chiffres | **Lien** | « DramaBox · série 41000105199 · FR » | Ouvre l'**Aperçu d'ajout** (§3.3). Si la série est déjà dans la bibliothèque, l'aperçu le dit (voir 3.3). |
| Plusieurs lignes | **Lot** | « 3 liens reconnus sur 4 » | Aperçu en lot |
| Lien d'un autre site | Erreur | Bord rouge, texte conservé, partie fautive surlignée | « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199). » |

**Commandes (palette).** Elles s'affichent sous les résultats, filtrées par le texte : Réessayer tous les échecs (3) · Tout reprendre · Tout mettre en pause · Créer le film de… · Ouvrir le dossier de la bibliothèque · Réglages · Raccourcis clavier.

**Recherche sans résultat.** « Aucune série “xyz” dans ta bibliothèque. La recherche par titre sur DramaBox n'existe pas encore : colle le lien de la série. » Le message est honnête : on ne montre pas une recherche en ligne qui n'existe pas.

**Clavier et accessibilité**
- `role="combobox"`. Flèches pour parcourir, Entrée pour ouvrir, `Échap` pour vider puis quitter.
- Erreur reliée au champ par `aria-describedby`.

**Mobile.** Le champ occupe toute la largeur. Un bouton **[Coller]** lit le presse-papiers après un geste de l'utilisateur. Les résultats s'affichent en plein écran.

---

### 3.3 Aperçu d'ajout

**But.** Confirmer que c'est la bonne série, choisir la version en connaissance de cause, voir le coût, puis lancer en un geste.

**Forme.** Un panneau de 760 px ancré sous l'en-tête, qui n'est **pas une modale** : le mur reste visible, assombri à 60 %. `Échap` le ferme et le texte collé reste dans le champ.

```
[ https://www.dramaboxdb.com/fr/movie/41000105199/one-night…  ‹DramaBox · série 41000105199 · FR› ]
┌─ Pas encore dans ta bibliothèque ──────────────────────────────────────────────────┐
│ ┌────────┐  Qui Est la Véritable Mme Lafont ?                                      │
│ │        │  One Night to Forever · titre original                                  │
│ │ cover  │  62 épisodes · 1 h 32 · épisodes de 50 s à 3 min 30                      │
│ │ 150 px │  Synopsis sur 3 lignes……………………………………………………………  [Lire plus]        │
│ │        │  Version : ( VO · anglais ) ( ● Français ) ( Espagnol )                  │
│ └────────┘  Coréen, thaï, indonésien, japonais : titre traduit seulement           │
│  Réglages : Meilleure (1080p) · tous les épisodes · sans film          [Modifier]  │
│  ≈ 690 Mo · ≈ 1 min · 182 Go libres sur C:            ● Source disponible          │
│  [ Tout télécharger · 62 épisodes ]    Choisir les épisodes    Voir la fiche      │
└────────────────────────────────────────────────────────────────────────────────────┘
```

**Zones (de haut en bas)**
1. **Cover 9:16 de 150 px**. À droite : le titre dans la version choisie (attribut `lang`) et le titre VO en gris.
2. **Méta** : « 62 épisodes · 1 h 32 · épisodes de 50 s à 3 min 30 ». Synopsis sur 3 lignes, dépliable.
3. **Puces de version.**
   - On ne propose que les versions doublées. Les langues qui n'ont qu'un titre traduit sont listées sur une ligne d'aide.
   - Sélectionner une puce relance l'aperçu avec cette langue. Le titre, le synopsis et la taille changent en place.
   - Si le moteur répond `lang_source: fallback`, la puce se désactive **avant** tout lancement : « Pas de version espagnole doublée ».
   - Par défaut : la langue de l'URL, sinon la version préférée si elle existe, sinon la VO.
4. **Ligne de réglages résumée** (valeurs mémorisées). [Modifier] la déplie :
   - **Qualité** : Meilleure (1080p) · 720p · 540p, avec une taille estimée pour chacune (marquée « ≈ »). L'estimation n'est calibrée qu'en 1080p.
   - **Épisodes** : Tous · Choisir… (ouvre la fiche en mode sélection) · Seulement les manquants (si la version existe déjà).
   - **Créer le film à la fin** : case mémorisée. L'interface enchaîne son propre job film, elle ne dépend donc pas de `fetch --film`.
   - Le **dossier** est affiché en lecture seule ; on le change dans les Réglages.
   - [Copier la commande] : `sdg fetch 41000105199 --lang fr -q 1080p`.
5. **Coût et santé** : taille, durée estimée, espace libre sur le disque, et un point vert « Source disponible » (`get_video` sur le dernier épisode).
6. **Actions**
   - Principale, **focalisée** : **[Tout télécharger · 62 épisodes]**.
   - Secondaires : Choisir les épisodes · Voir la fiche.

**États**

| État | Rendu et texte |
|---|---|
| Chargement | Squelette (affiche, 3 lignes, bouton inactif). « Lien reconnu. Recherche de la série… » ; au-delà de 4 s : « Le site officiel met du temps à répondre… » |
| Déjà possédée | Titre du panneau « Dans ta bibliothèque : VO complète (62/62) · VF 40/62 ». Le bouton principal devient **[Compléter la VF (22 manquants)]** ; en secondaire [Ouvrir la fiche] [Ajouter l'espagnol]. |
| Lien d'épisode (`/ep/`) | « C'est le lien de l'épisode 14 : on te propose toute la série. » avec l'option [Seulement l'épisode 14] |
| Mode sonde | Affiche générée « Série 41000999999 », étiquette **« Infos limitées »** : « Cette série n'est pas sur le site officiel : titre, durées et cover indisponibles. Les épisodes seront détectés pendant le téléchargement, **sans contrôle de durée**. » Le bouton devient [Télécharger les épisodes trouvés]. |
| Source en panne | Point rouge : « La source ne répond pas pour cette série : le téléchargement risque d'échouer. » Le bouton reste actif. |
| Disque insuffisant | « Il manque ≈ 310 Mo sur C:. » Bouton désactivé, raison affichée, [Changer de dossier] |
| Introuvable | « On n'a trouvé cette série ni sur le site officiel ni à la source. Vérifie le lien ou essaie avec le n° de série (11 chiffres). » |
| Réseau | « Impossible de joindre DramaBox. Vérifie ta connexion. » [Réessayer] |
| Hors ligne | « Tu es hors ligne : l'aperçu a besoin d'Internet. » [Garder le lien pour plus tard] (le lien part dans l'Activité, « En attente de connexion », V1.1) |
| **Plusieurs liens** | Liste de lignes compactes (cover 40 px, titre, épisodes, taille, case cochée). Ligne invalide en rouge et décochée. Bouton **[Tout télécharger · 3 séries · ≈ 2,1 Go]**. |

**Après le lancement.** L'aperçu se referme en « s'envolant » vers la première place du mur (voir S2). Le champ se vide et **garde le focus**, pour enchaîner un autre lien. Toast : « Téléchargement lancé · Qui Est la Véritable Mme Lafont ? (VF) » [Voir la fiche].

**Mobile 390.** Feuille plein écran : cover de 120 px en haut, informations dessous, puces qui passent à la ligne, **bouton principal collé en bas de l'écran**.

---

### 3.4 Fiche série

**But.** Tout comprendre et tout faire pour une série : ses versions, ses épisodes, son film, ses fichiers.

```
← Bibliothèque
┌──────────────────────────── fond : même cover, floutée, voile #0B1220 à 80 % ────────────────────────────┐
│ ┌──────────┐  Qui Est la Véritable Mme Lafont ?                                                         │
│ │          │  One Night to Forever · titre original                                                     │
│ │  cover   │  62 épisodes · 1 h 32 · 684 Mo · 1080p                                                    │
│ │ 240×427  │  Synopsis sur 3 lignes…………………………………………………………………… [Lire plus]                              │
│ │          │                                                                                            │
│ │          │  [ VO · anglais  ✓ 62/62 ] [ Français  60/62 ! ] [ + Espagnol ] [ + Autres ▾ ]            │
│ └──────────┘                                                                                            │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ! 2 épisodes en échec (40 et 41) · 1 épisode en 720p (12)      [ Réessayer les 2 épisodes ]  ▶ Regarder  Dossier  ⋯ │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Épisodes   ✓ Téléchargés 59 · ↓ En cours 0 · ! Échecs 2 · ○ À télécharger 0 · 720p 1                     │
│ Sélection : Tous · Aucun · Manquants · Échecs · Inverser              Plages : [ 1-10, 28, 50-        ]   │
│                                                                                                          │
│   1–10  [ 1✓][ 2✓][ 3✓][ 4✓][ 5✓][ 6✓][ 7✓][ 8✓][ 9✓][10✓]     ┌─ Épisode 40 ─────────────────────┐   │
│  11–20  [11✓][12 720][13✓][14✓][15✓][16✓][17✓][18✓][19✓][20✓]     │ 1 min 19 · Échec                  │   │
│  21–30  [21✓] …                                                   │ Cet épisode n'est pas disponible  │   │
│  31–40  … [40 !]                                                  │ à la source pour le moment.       │   │
│  41–50  [41 !] …                                                  │ [ Réessayer ]  Détails techniques │   │
│  51–60  …                                                         └───────────────────────────────────┘   │
│  61–62  [61✓][62✓]                                                                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Film   Pas encore de film.   ✓ 62/62 épisodes   ✗ Formats : l'épisode 12 est en 720p   ✓ ffmpeg prêt       │
│        [ Retélécharger l'épisode 12 en 1080p puis créer le film ]   Créer quand même (ré-encodage, lent)   │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Stockage   Épisodes 684 Mo · Film — · C:\Users\…\ShortDramaGen\41000105199-one-night-to-forever-fr       │
│            [ Ouvrir le dossier ]   [ Supprimer… ]                                                         │
│ ▸ Détails techniques                                                                                     │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Zones (de haut en bas)**
1. **Fil de retour** : « ← Bibliothèque », qui restaure les filtres et la position de défilement.
2. **Héros**
   - Cover nette de 240 px, sur un fond fait de la même cover (flou de 40 px, voile à 80 %). Jamais de bandeau paysage étiré.
   - Titre H1 avec `lang`, titre VO, méta, tags si disponibles (dépendance : manifest enrichi), synopsis replié.
3. **Onglets de version.** Chaque onglet porte son état : « ✓ 62/62 », « 60/62 ! », « ↓ 34/62 ».
   - Les langues disponibles mais pas téléchargées apparaissent en **« + Espagnol »**.
   - Au survol, un aperçu est chargé en arrière-plan (« ≈ 700 Mo »). Au clic, l'onglet passe en mode Aperçu pour cette version, avec [Tout télécharger · 62 épisodes].
   - « + Autres ▾ » liste les langues qui n'ont qu'un titre traduit, désactivées avec la raison.
4. **Barre de santé**
   - Une phrase-bilan et **une seule action principale** (tableau ci-dessous).
   - Actions secondaires : [▶ Regarder] · [Dossier].
   - Menu ⋯ : Vérifier les nouveaux épisodes · Retélécharger la version dans une autre qualité · Vérifier les fichiers (V2) · Copier la commande CLI · Supprimer…
5. **Épisodes** : grille décimale et volet (§3.5).
6. **Film** (§3.6).
7. **Stockage** : taille des épisodes, du film et des `.part` orphelins (« Nettoyer 42 Mo »). Chemin, [Ouvrir le dossier], [Supprimer…]. Quand le film existe : [Libérer 684 Mo (garder le film)].
8. **Détails techniques** (repliés), pour la parité avec la CLI :
   - n° de série, n° vidéo de la version (`source_book_id`), origine et qualité par épisode, date d'expiration des liens (**jamais l'URL**) ;
   - la commande équivalente ;
   - [Copier les liens pour aria2c / IDM] (équivalent de `links`, copie sans affichage) et [Exporter en JSON] ;
   - le journal de la dernière tâche.

**Action principale selon l'état de la version**

| État | Phrase-bilan | Action principale |
|---|---|---|
| En cours | « Téléchargement · 34/62 · ≈ 40 s » | **Mettre en pause** |
| En file | « En file · démarre après *Una Noche…* » | **Télécharger maintenant** (V2) ou **Mettre en pause** (V1) |
| Interrompue | « Interrompu · 34/62 · reprend là où il s'était arrêté » | **Reprendre** |
| Échecs | « 2 épisodes en échec (40 et 41) » | **Réessayer les 2 épisodes** |
| Incomplète | « 58/62 · 4 à télécharger (59 à 62) » | **Télécharger les 4 manquants** |
| Fichier supprimé hors de l'appli | « 1 fichier manquant (épisode 14) » | **Retélécharger l'épisode 14** |
| Complète, sans film | « ✓ 62/62 téléchargés et vérifiés · 1 h 32 · 684 Mo » | **Créer le film** |
| Complète, film obsolète ou partiel | « Film partiel (épisodes 1-10) · 52 épisodes ajoutés depuis » | **Recréer le film complet** |
| Complète, avec film | « ✓ 62/62 · Film prêt » | **▶ Regarder le film** (ou **Reprendre · ép. 14**) |
| Sonde | « Durées non vérifiées : série absente du site officiel » | selon l'état, avec l'icône « non vérifié » |

**Mode Aperçu (série ou version pas encore possédée).** C'est la même page, et c'est ce qui distingue ce concept : **un lien collé devient une fiche**.
- Titre de barre : « Pas encore dans ta bibliothèque ».
- Toutes les tuiles sont en « à télécharger » (pointillés) et **sélectionnées**. Le clic coche ou décoche, puisqu'il n'y a rien à lire.
- L'action principale suit la sélection : **[Tout télécharger · 62 épisodes]** ou **[Télécharger 23 épisodes · ≈ 270 Mo]**, avec le sélecteur de qualité à côté.

**États**

| État | Rendu et texte |
|---|---|
| Chargement | Squelette du héros et de la grille (`role="status"` : « Chargement de la série… ») |
| Vide (version connue, 0 épisode) | « Aucun épisode téléchargé pour l'instant. » [Tout télécharger · 62 épisodes] |
| Dossier disparu | « Le dossier de cette version est introuvable (déplacé ou supprimé en dehors de l'appli). » [Le retrouver…] [Retélécharger] [Retirer de la bibliothèque] |
| Qualités mélangées | Mention dans la barre : « 60 épisodes en 1080p, 2 en 720p » ; la section Film propose la réparation |
| Hors ligne | Les actions réseau sont désactivées avec « Disponible au retour de la connexion ». Regarder, Film et Dossier restent actifs. |
| Moteur injoignable | Lecture seule, dernier état connu |

**Mobile 390**
- En-tête compact : cover de 96 px et titre sur 3 lignes à côté. Méta en dessous.
- Versions en puces qui défilent horizontalement.
- Barre de santé en texte ; **action principale collée en bas de l'écran**, au-dessus de la barre de navigation.
- Grille de 5 colonnes (§3.5). Le volet devient une feuille du bas.
- Film et Stockage en sections repliables. « Ouvrir le dossier » est **masqué** (sans objet à distance).

---

### 3.5 Grille d'épisodes et volet (composant partagé)

**But.** Voir, sélectionner, suivre et agir sur 60 à 100 épisodes avec un seul composant. Il sert aussi dans le tiroir Activité (version miniature en « ruban ») et dans le Théâtre.

**Zones**
1. **Légende-compteurs** : ✓ Téléchargés 59 · ↓ En cours 0 · ! Échecs 2 · ○ À télécharger 0 · 720p 1. Les entrées à 0 sont atténuées. **Cliquer sur une entrée sélectionne ces épisodes** (les autres s'atténuent) et le volet propose l'action groupée. On ne filtre pas, pour garder la géométrie de la grille.
2. **Outils de sélection** : Tous · Aucun · Manquants · Échecs · Inverser, et le champ **Plages**, synchronisé dans les deux sens avec la grille.
   - Il accepte « 1-10, 28, 50- », le tiret long « 1–10 », les espaces et « 50-62 ».
   - Une saisie invalide affiche un message sous le champ sans toucher la grille.
3. **Grille décimale.** **10 tuiles par ligne**, avec des étiquettes de rangée « 1–10 », « 11–20 »… On repère l'épisode 28 en rangée 3, colonne 8.
   - Au-delà de 100 épisodes, des onglets de centaine apparaissent (1–100 · 101–200).
4. **Volet** (360 px, à droite) : il montre soit l'épisode focalisé, soit le **résumé de la sélection**.
   - Exemple : « 23 épisodes · ≈ 270 Mo · [Télécharger] [Retélécharger en 1080p ▾] [Supprimer ces fichiers] ».

**Interactions**

| Geste | Tuile téléchargée | Tuile en échec | Tuile à télécharger | Tuile en cours |
|---|---|---|---|---|
| Clic | **Regarder** (Théâtre) | Volet : raison + [Réessayer] | Volet : [Télécharger cet épisode] | Volet : progression, source, « reprise à 64 % » |
| Ctrl+clic / Espace | Ajouter ou retirer de la sélection | idem | idem | idem |
| Maj+clic, Maj+flèches, glisser | Sélection d'une plage | | | |
| Clic droit, touche Menu, Maj+F10 | Menu : Regarder · Réessayer · Retélécharger en… · Afficher dans le dossier · Supprimer le fichier | | | |

Dès qu'une sélection existe, **le clic simple coche** (comme dans l'Explorateur et Gmail), jusqu'à [Aucun] ou `Échap`.

**Accessibilité**
- `role="grid"`, un seul arrêt de tabulation, déplacement aux flèches, `Début` et `Fin` pour aller aux extrémités.
- Nom accessible complet, par exemple « Épisode 14, 2 min 05, téléchargé et vérifié, 13,2 Mo, 1080p ».
- Infobulle au survol et au focus : « E014 · 2 min 05 · 1080p · 13,2 Mo · Vérifié ».

**Tailles.** Tuiles de 60×48 à 1440, 52×44 à 1280, 64×48 à 390 (5 par ligne, une dizaine sur 2 rangées). Toujours au moins 44×44 px.

---

### 3.6 Film (section de la fiche et choix)

**But.** Passer de « 62 fichiers » à « un film chapitré » en un clic, sans jamais tomber sur un refus sec.

**Zones**
1. **Carte d'état du film** (tableau ci-dessous).
2. **Contrôles préalables toujours visibles**, calculés sans réseau à partir du plan du film : « ✓ 62/62 épisodes · ✓ Même format (1080p) · ✓ ffmpeg prêt ». Chaque ✗ explique pourquoi et comment réparer.
3. **Action**, puis remèdes proposés sous forme de boutons, le recommandé en premier.
4. **Options du film** (repliées) : Chapitres « Épisode N » (activés) · Nom du fichier · Ré-encoder (plus lent) · Autoriser un film partiel. C'est la parité avec `sdg film`.

| État du film | Texte | Actions |
|---|---|---|
| Aucun, prêt à créer | « Réunis les 62 épisodes en un seul fichier (1 h 32, un chapitre par épisode), en quelques secondes. » | **[Créer le film]** |
| Création | La progression s'affiche **dans le bouton** : « Assemblage… 38/62 », sans modale (environ 6 s) | [Annuler] |
| Prêt | « Film prêt : Qui Est la Véritable Mme Lafont.mp4 · 1 h 32 · 717 Mo · 62 chapitres » | **[▶ Regarder le film]** [Afficher dans le dossier]. Suggestion affichée une seule fois : « Libérer 684 Mo en supprimant les épisodes ? Le film reste. » [Libérer] [Non merci] |
| Épisodes manquants | « Il manque 2 épisodes (61 et 62). » | **[Les télécharger puis créer le film]** · [Créer un film partiel (épisodes 1-60)] |
| Formats mélangés | « L'épisode 12 est en 720p, les autres en 1080p. Pour un film sans perte en quelques secondes, retélécharge-le en 1080p. » | **[Retélécharger l'épisode 12 en 1080p (~13 Mo) puis créer]** · [Créer quand même (ré-encodage, plusieurs minutes)] |
| ffmpeg absent | « Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans. » | [Comment l'installer ?] ouvre un encart avec `winget install Gyan.FFmpeg` et `pip install imageio-ffmpeg` (boutons Copier), puis [Vérifier à nouveau] |
| Partiel ou obsolète | « Film partiel (épisodes 1-10). 52 épisodes ajoutés depuis. » | **[Recréer le film complet]** |
| Fichier du film disparu | « Le film n'est plus dans le dossier. » | [Recréer le film] |
| Durée incorrecte | « Le film créé n'a pas la durée attendue (1 h 29 au lieu de 1 h 32). » | [Réessayer] · Détails techniques |
| Écrasement | Si un fichier du même nom existe : « Remplacer le film existant (717 Mo) ? » en confirmation dans la ligne, pas en modale | [Remplacer] [Garder les deux] |

**Mobile.** Section repliable ; les remèdes s'empilent en boutons pleine largeur.

---

### 3.7 Théâtre (lecteur vertical)

**But.** Regarder un épisode ou le film en 9:16, et enchaîner sans chercher.

```
┌────────────────────────────────────────────────────────────────────────────── [×] Échap ┐
│ Qui Est la Véritable Mme Lafont ? · VF                  │ Épisodes · 14 / 62              │
│                    ┌───────────────┐                    │ [ 1][ 2][ 3][ 4][ 5]            │
│                    │               │                    │ [ 6][ 7][ 8][ 9][10]            │
│                    │    vidéo      │                    │ [11][12][13][14▶][15]           │
│   [◀ Épisode 13]   │    9:16       │  [Épisode 15 ▶]    │  …                               │
│                    │  hauteur de   │                    │ Enchaînement automatique : oui  │
│                    │  la fenêtre   │                    │ Sous-titres non fournis par la  │
│                    │               │                    │ source                          │
│                    └───────────────┘                    │ [Ouvrir dans le lecteur par défaut] │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Zones**
- Fond `#05080F`. Vidéo `<video>` servie avec `Range`, ajustée à la hauteur de la fenêtre et jamais étirée.
- Précédent et suivant sur les côtés.
- À droite, la **grille miniature** (5 colonnes) avec l'épisode courant et les épisodes vus. Pour le film, la liste des **chapitres** (« Épisode 1 » à « Épisode 62 », fichier `chapters.vtt`), marqués aussi sur la barre de lecture.

**Comportement**
- Fin d'épisode : « Épisode suivant dans 5 s » [Annuler]. Avec reduced-motion, le décompte est en texte seul.
- Un épisode non téléchargé est sauté avec le message « Épisode 59 non téléchargé : on passe au 60 ».
- La position est mémorisée : « Reprise à 1:12 » [Revenir au début].
- Clavier : `Espace`/`K` lecture ou pause · `←`/`→` 5 s · `Maj+←`/`Maj+→` épisode ou chapitre précédent/suivant · `F` plein écran · `M` muet · `Échap` fermer (le focus revient sur la tuile d'origine).

**États**

| État | Texte |
|---|---|
| Chargement | Cover en fond (`role="status"` : « Chargement de l'épisode 14… ») |
| Épisode en cours de téléchargement | « Cet épisode est encore en téléchargement (45 %). Il sera lisible dès qu'il sera terminé. » |
| Fichier absent | « Ce fichier n'est plus dans le dossier. » [Retélécharger l'épisode] |
| Codec illisible (HEVC par exemple) | « Ton navigateur n'arrive pas à lire cette vidéo. » [Ouvrir dans le lecteur par défaut] |
| Hors ligne | Identique : les fichiers sont locaux |

**Mobile.** Plein écran natif ; la liste des épisodes passe dans une feuille du bas.

---

### 3.8 Activité (tiroir sur desktop, page sur mobile)

**But.** Le détail pour qui le veut. **L'information essentielle est déjà sur l'affiche.**

```
┌ Activité ───────────────────────────── [Épingler] [×] ┐
│ En cours                                               │
│ ┌──┐ Qui Est la Véritable Mme Lafont ? · VF            │
│ │  │ ██████████████░░░░░░░░  34/62                     │
│ └──┘ 18 Mo/s · ≈ 40 s · 1 échec                        │
│      ✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓↓↓↓··········   │
│      [Pause] [Annuler] [Voir la fiche]                 │
│ En file · 2                                            │
│  Una Noche Para Siempre · VE        [Pause] [Retirer]  │
│  Contrat d'un an · VO               [Pause] [Retirer]  │
│ Terminés récemment                         [Effacer]   │
│  One Night to Forever · VO · 62/62 vérifiés · 702 Mo   │
│  · 1 min 38 s          [▶ Regarder] [Créer le film]    │
│ ▸ Journal                                              │
└────────────────────────────────────────────────────────┘
```

**Zones**
1. **En cours**
   - Mini-cover, titre et version.
   - Barre en **épisodes** (elle ne recule jamais), débit lissé, temps restant arrondi (« moins d'une minute »).
   - **Ruban** de 62 points (grille miniature).
   - [Pause] [Annuler] [Voir la fiche].
   - Phases visibles : « Lecture des infos… », « Recherche des épisodes à la source… 23 trouvés » (sonde), « Téléchargement », « Création du film… ».
2. **En file** : position, [Pause] [Retirer]. Le réordonnancement viendra en V2, avec les boutons Monter et Descendre en plus du glisser-déposer.
3. **En pause / Interrompus** : [Reprendre].
4. **Terminés récemment**, avec des actions de suite : [▶ Regarder] [Créer le film] [Réessayer les 2]. [Effacer la liste (tes fichiers restent)].
5. **Journal** replié : les messages du moteur, avec horodatage.

**Règles**
- « Annuler » **ne supprime pas** les épisodes terminés. Une confirmation dans la ligne propose « Garder les fichiers partiels pour reprendre plus tard ».
- Pendant l'arrêt, états « Mise en pause… » et « Annulation… » (jusqu'à 30 à 45 s sur un réseau bloqué).
- Le tiroir n'assombrit pas la page et peut être épinglé.

**États**

| État | Texte |
|---|---|
| Vide | « Rien en cours. » + la dernière activité · [Coller un lien] |
| Terminé avec échecs | « Terminé avec 2 échecs (épisodes 40 et 41). » [Réessayer les 2] |
| Disque plein | « Arrêté : disque plein (il manque 312 Mo sur C:). Libère de la place puis reprends. » [Reprendre] |
| Hors ligne | « Hors ligne. Reprise automatique au retour de la connexion. Nouvel essai dans 12 s. » [Réessayer maintenant] |
| Doublon | Dans l'aperçu : « Cette série est déjà dans la file. » [Voir] |

**Mobile.** Page `#/activite`, avec un badge sur l'onglet de la barre du bas.

---

### 3.9 Réglages et santé

**But.** Régler une fois, ne plus y penser, et savoir ce qui bloque.

| Section | Contenu |
|---|---|
| Général | Dossier de la bibliothèque (absolu ; par défaut `%USERPROFILE%\Videos\ShortDramaGen`) [Changer] · Version préférée (« Français si disponible, sinon VO ») · Qualité (Meilleure 1080p) · Créer le film après chaque téléchargement · Reprendre automatiquement au démarrage |
| Téléchargement | Téléchargements simultanés : 3 (recommandé). Au-delà : « Au-delà de 3, la source risque de te bloquer temporairement. » |
| Film | État de ffmpeg : « ffmpeg prêt · C:\ffmpeg\bin\ffmpeg.exe (PATH) » ou « absent » avec les commandes à copier · chemin personnalisé · chapitres par défaut |
| Stockage | Bibliothèque 11,8 Go · libre 182 Go sur C: · fichiers partiels orphelins 42 Mo [Nettoyer] · durée de la corbeille d'annulation |
| Affichage | Thème (Système / Sombre / Clair) · Titres affichés (version préférée / VO) · Vue et densité du mur · Raccourcis à une touche (oui/non) · Annonces pour lecteur d'écran (paliers / fin seulement / aucune) |
| Santé | Liste de vérifications, chacune avec son état : ffmpeg · dossier accessible en écriture · espace libre · site officiel joignable · source joignable [Tout revérifier] |
| À propos | Version, commande `sdg ui`, [Aide des raccourcis], [Quitter ShortDramaGen] (met les téléchargements en pause) |

**États.** « Enregistré. » dans la ligne modifiée. Erreurs de champ, par exemple « Ce dossier n'est pas accessible en écriture. Choisis-en un autre. ». `409` pendant un job : « Tu pourras changer de dossier quand les téléchargements seront finis. »

**Mobile.** Liste de sections. Le dossier et ffmpeg sont masqués, car ce sont des actions sur le PC.

---

### 3.10 Dialogues

**Supprimer…** (`<dialog>`, focus piégé ; la suppression est **refusée pendant un job**)
- « Que veux-tu supprimer pour Qui Est la Véritable Mme Lafont ? (VF) »
  - ( ) Seulement le film · 717 Mo
  - (•) **Seulement les épisodes · 684 Mo : le film reste** (présélectionné, c'est le choix le moins destructif quand un film existe)
  - ( ) Tout : épisodes, film et dossier · 1,4 Go
- « Tu pourras annuler pendant 5 minutes. »
- [Supprimer 684 Mo] [Annuler]. Toast : « Supprimé · 684 Mo libérés » [Annuler]. Le toast reste tant qu'il a le focus ou qu'il est survolé.
- Erreur Windows : « Impossible de supprimer E014.mp4 : il est ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. » L'interface coupe d'abord son propre lecteur.
- En masse : un récapitulatif chiffré, par exemple « 5 séries · 3,4 Go ».

**Raccourcis (`?`)** : la liste complète, toujours au même endroit.

---

## 4. Les 6 parcours clés dans ce concept

Convention : une interaction = un clic ou tap, un raccourci, ou une validation. Coller compte pour 1. Le défilement ne compte pas.

### (a) Coller une URL → aperçu → tout télécharger

| # | Geste | Système | Retour visible |
|---|---|---|---|
| 1 | `Ctrl+V` n'importe où (ou clic dans la barre + `Ctrl+V`) | Détection locale immédiate, puis `POST /api/preview` | Puce « DramaBox · série 41000105199 · FR », squelette d'aperçu, mur assombri |
| — | — | Aperçu en moins de 2 s | Cover, titres, « 62 épisodes · 1 h 32 », ≈ 690 Mo, bouton principal **focalisé** |
| 2 | `Entrée` (ou clic sur **Tout télécharger · 62 épisodes**) | `POST /api/jobs` | L'aperçu s'envole vers le mur ; l'affiche grise « En file » se colore en moins d'une seconde ; l'anneau d'activité s'allume ; le champ se vide et garde le focus |

**Total** : **2 au clavier** · 3 à la souris · 3 sur mobile (Ajouter → Coller → Tout télécharger).

**Variantes**

| Variante | Comportement | Interactions |
|---|---|---|
| Autre version | Un clic sur la puce « Français » | +1 |
| Série déjà possédée | Bouton principal « Compléter la VF (22) » | 2 |
| Plusieurs liens | « Tout télécharger · 3 séries » | 2 |
| Lien d'épisode | La série entière est proposée par défaut | 2 (+1 pour « seulement l'épisode 14 ») |
| Choisir les épisodes | « Choisir les épisodes » → fiche Aperçu (tout est coché) → saisie de « 1-10 » → [Télécharger 10 épisodes] | 4 |

### (b) Suivre la progression en faisant autre chose

| Couche | Ce qu'on voit | Interactions |
|---|---|---|
| Barre des tâches Windows | Titre d'onglet « (34/62) ShortDramaGen », favicon avec anneau | 0 |
| Mur (si on y est) | **L'affiche se colore** du bas vers le haut ; « ↓ 34/62 · ≈ 40 s » | 0 |
| En-tête (partout) | Anneau et nombre sur l'icône Activité | 0 |
| Fin | Toast et notification Windows : « Qui Est la Véritable Mme Lafont ? (VF) est prêt · 62 épisodes vérifiés, 684 Mo » [Regarder] [Créer le film]. La permission est demandée au **premier** téléchargement terminé. | 0 |
| Détail | Tiroir Activité : débit, ruban, journal | **1** (clic sur l'icône ou `T`) |
| Épisode par épisode | Fiche : les tuiles se remplissent en direct | 1 (clic sur l'affiche) |

Lecteur d'écran : une seule région `role="status"`. Annonces au lancement, à 25/50/75 %, à la fin et par groupe d'échecs, avec au moins 10 s d'écart. **Jamais une annonce par épisode.**

### (c) Retrouver une série parmi 50 et plus

| Chemin | Gestes | Interactions |
|---|---|---|
| Par le titre, dans n'importe quelle langue | `/` → taper « laf » (en tête dès 3 lettres, « trouvé dans le titre VF ») → `Entrée` | **3** interactions (5 frappes), moins de 5 s |
| Par l'état | Puce « À compléter (3) » → affiche | 2 |
| Par la taille | Vue Liste → colonne Taille | 2 |
| Ce qui demande de l'attention | L'étagère « À traiter » est déjà affichée sur l'accueil | 0 pour voir, 1 pour agir |

### (d) Gérer une série

| Sous-tâche | Depuis le mur | Depuis la fiche |
|---|---|---|
| Réessayer les échecs | Étagère « À traiter » ou carte [Réessayer (2)] : **1** | Action principale : **1** |
| Compléter | Carte [Compléter (4)] : **1** | **1** |
| Ajouter une autre langue | Carte → onglet « + Espagnol » → [Tout télécharger] : **3** | **2** |
| Créer le film | « ⋯ » → Créer le film : **2** (+1 si un choix est demandé) | **1** (+1) |
| Réparer des qualités mélangées | — | [Retélécharger l'épisode 12 en 1080p puis créer] : **1** |
| Retélécharger un épisode | — | Clic droit sur la tuile → Retélécharger en… : **2** |
| Ouvrir le dossier | « ⋯ » → Ouvrir le dossier : **2** | [Dossier] : **1** |
| Supprimer | « ⋯ » → Supprimer… → [Supprimer 684 Mo] : **3** | **2** |
| En masse | Puce « À compléter » → `Ctrl+A` → [Compléter] : **3** | — |
| Vérifier les nouveaux épisodes | « ⋯ » → Vérifier : **2** | « ⋯ » → Vérifier : **2** |

### (e) Regarder un épisode ou le film

| Chemin | Interactions |
|---|---|
| Carte complète : [▶ Reprendre · ép. 14] (au survol ou au focus) | **1** |
| Carte avec film : [▶ Regarder le film] | **1** |
| Fiche : clic sur une tuile téléchargée | **1** |
| Enchaînement jusqu'à la fin de la série | 0 (auto) |
| Ouvrir dans VLC ou MPC-HC | 1 (bouton du Théâtre) |

### (f) Reprendre après fermeture ou coupure

| Scénario | Comportement | Interactions |
|---|---|---|
| Onglet fermé, moteur actif | Les téléchargements continuent ; état exact à la réouverture | 0 |
| PC éteint ou moteur arrêté | Au démarrage, les `downloading` sans job deviennent **Interrompu**. Bandeau « 2 téléchargements interrompus (34/62 et 0/48) » [Tout reprendre] [Voir], plus l'étagère « À traiter » | **1** (0 avec le réglage de reprise auto) |
| Coupure Internet | Pause automatique « Hors ligne », aucun échec compté, reprise automatique à l'octet près | 0 |
| Moteur injoignable | Lecture seule, reconnexion toutes les 5 s | 0 |
| Lien expiré (plus de 3 semaines) | Nouvelle résolution invisible | 0 (1 si elle échoue) |
| Fichier supprimé dans l'Explorateur | Au retour du focus, la tuile passe en « ? Manquant » et la série entre dans « À traiter » | **1** (Retélécharger) |

---

## 5. Interactions signatures

### S1. Coller, c'est ouvrir la fiche
- **Déclencheur** : `Ctrl+V` n'importe où, ou saisie dans la barre.
- **Comportement** : une puce de détection apparaît instantanément dans le champ, sans réseau. Suivent l'aperçu, puis Entrée. Le même champ cherche dans la bibliothèque et sert de palette de commandes. Il n'y a donc qu'un endroit pour « aller quelque part », que la série soit possédée ou non.
- **Détail** : un lien vers une série possédée ouvre sa fiche et propose la version manquante. Il ne crée pas de doublon.
- **Accessibilité** : combobox, l'erreur garde le texte collé, le focus reste dans le champ après le lancement.

### S2. L'affiche qui se colore
- **Principe** : une série qui n'est pas encore chez toi est **désaturée** (aperçu, en file). Pendant le téléchargement, la couleur **monte du bas vers le haut** à chaque épisode vérifié.
- **Technique** : deux couches (cover en niveaux de gris assombrie, et cover en couleur découpée par `clip-path: inset(calc((1 - var(--p)) * 100%) 0 0 0)`), avec `--p` = épisodes terminés / sélectionnés.
- **Arrivée sur le mur** : quand on lance le téléchargement, la carte d'aperçu « s'envole » en 350 ms vers la première place du mur (tri par activité).
- **Interruption** : le remplissage se fige, une icône pause s'affiche avec « Interrompu · 34/62 ».
- **Garde-fous**
  - Toujours doublé d'un texte (« ↓ 34/62 · ≈ 40 s »).
  - Réservé aux états actif, en file et interrompu. Une série incomplète au repos garde sa couleur et affiche une barre.
  - Avec reduced-motion : paliers sans transition, pas d'envol.

### S3. La grille décimale
- 10 tuiles par ligne avec étiquettes de rangée. La légende sert à la fois de compteur et de sélecteur.
- Sélection au clic, à Maj+clic, en glissant ou par le champ « 1-10, 28, 50- » synchronisé.
- Le volet latéral transforme toute sélection en action (« Réessayer ces 2 », « Retélécharger en 1080p »).
- En direct, seule la variable `--p` des tuiles actives change : le rendu reste fluide jusqu'à 1000 épisodes.

### S4. Une série, des versions
- Une carte par série. Dans la fiche, des onglets VO · VF · VE, chacun avec son état.
- **« + Espagnol »** : au survol, l'aperçu de cette version se charge en arrière-plan (« ≈ 700 Mo »). Au clic, la version s'ajoute en 2 interactions.
- Les langues qui n'ont qu'un titre traduit sont annoncées **avant** tout lancement. Jamais de drapeaux ; le code `in` s'affiche « Indonésien ».

### S5. Le film en un bouton
- Les contrôles préalables sont **visibles avant le clic** (✓ épisodes, ✓ format, ✓ ffmpeg).
- La progression s'affiche dans le bouton (environ 6 s, sans modale).
- Chaque refus devient une alternative, le choix recommandé en premier (retélécharger, film partiel ou ré-encodage).
- Une fois le film prêt, une proposition unique : « Libérer 684 Mo ? ».

### S6. Le théâtre vertical
- Vidéo 9:16 à hauteur d'écran ; la place libre sert au contexte (grille d'épisodes ou chapitres), pas à étirer la vidéo.
- Enchaînement automatique et position mémorisée. L'affiche de la bibliothèque propose ensuite « Reprendre · ép. 14 ».

### S7. L'étagère « À traiter »
- Chaque problème devient une carte avec **son** bouton de réparation : échecs, incomplète, interrompue, film obsolète, fichier manquant.
- Vide, elle disparaît. Quand tout va bien, l'accueil n'affiche que la collection.

### S8. Le mur reflète le disque
- La bibliothèque est relue au retour du focus (ETag, scan par dates). Les séries téléchargées par la CLI apparaissent.
- Les incohérences deviennent des états lisibles plutôt que des mensonges :
  - `downloading` sans job → Interrompu ;
  - `done` sans fichier → Manquant ;
  - `failed` avec un fichier présent → à confirmer.

---

## 6. Direction visuelle

### 6.1 Ambiance
Une **salle de projection bleu nuit**. L'interface est désaturée et calme ; **les covers apportent la couleur**. Le bleu d'accent est rare : il est réservé à l'action principale, au lien, au focus et à la progression. On garde la filiation dramafren (bleu nuit, accents bleus, grille numérotée) sans en copier la densité.

### 6.2 Palette (thème sombre, par défaut)

| Jeton | Hex | Usage | Contraste |
|---|---|---|---|
| `bg` | `#0B1220` | Fond de page | — |
| `surface` | `#131C2E` | Cartes, panneaux, tiroir | — |
| `raised` | `#1B2640` | Menus, volet, tuiles au survol | — |
| `backdrop` | `#05080F` | Fond du théâtre | — |
| `scrim` | `#0B1220` à 85 % | Dégradé sous le texte posé sur une cover, voile du héros | — |
| `text` | `#E8ECF4` | Texte principal | 15,8:1 sur `bg` |
| `text-muted` | `#A3AEC4` | Méta, aides, titres VO | 8,4:1 |
| `accent` | `#5B9BFF` | Bouton principal (**texte `#0B1220`**, 6,8:1), liens, progression | 6,8:1 |
| `accent-strong` | `#2F6FE0` | Seulement si un bouton doit porter un texte blanc (4,7:1) | — |
| `focus` | `#8FC1FF` | Anneau de 2 px, décalage de 2 px | 10,0:1 |
| `success` | `#3DD68C` | Téléchargé et vérifié | 10,0:1 |
| `warning` | `#F5B544` | Partiel, interrompu, qualité différente, manquant | 10,3:1 |
| `danger` | `#FF6B6B` | Échec | 6,8:1 |
| `film` | `#B69CFF` | Puce et section Film (se distingue des statuts) | ≈ 8:1 (calcul approché) |
| `border-control` | `#6A7A99` | Contours des tuiles et des champs | 4,3:1 (≥ 3:1) |
| `tile-done` | `#123524` | Fond de tuile téléchargée | `text` ≈ 11:1 |
| `tile-progress` | `#1D3E78` | Remplissage de tuile en cours | — |
| `tile-partial` | `#3B2F12` | Remplissage figé d'un épisode interrompu | — |
| `tile-fail` | `#3A1620` | Fond de tuile en échec | — |

### 6.3 Codage des états d'épisode (jamais la couleur seule)

| Statut affiché | Source (manifest + disque + job) | Fond | Bord | Icône et texte |
|---|---|---|---|---|
| À télécharger | `pending`, pas de `.part` | transparent | pointillé `border-control` | numéro en gris |
| En file | job actif, épisode pas encore démarré | transparent | plein `border-control` | petite horloge |
| En cours X % | événement `episode` et octets reçus | `tile-progress` monte du bas selon `--p` | `accent` | ↓ + « 45 % » dans l'infobulle |
| Interrompu | `.part` présent sans job, ou `downloading` sans job | `tile-partial` figé à X % | `warning` | ‖ |
| Téléchargé et vérifié | `done` + fichier présent | `tile-done` | `success` | ✓ |
| Téléchargé, non vérifié | `done` en mode sonde | `tile-done` | pointillé `success` | ✓ creux |
| Qualité différente | `quality` différente de la majorité | selon le statut | selon le statut | coin « 720 » sur fond `warning` |
| Échec | `failed` (erreur réessayable) | `tile-fail` | `danger`, 2 px | ! |
| Indisponible | `failed` avec une cause source (dépend de `error_code`) | hachures `raised` / `surface` | pointillé `danger` | – |
| Manquant | `done` sans fichier | transparent | `warning` | ? |
| Retiré (film conservé) | `removed` | transparent | pointillé | petite icône film |
| **Sélection** (s'ajoute aux autres) | — | inchangé | contour intérieur `text` de 2 px | coche en haut à droite |

- La sélection n'utilise jamais de couleur de fond, pour ne pas se confondre avec la progression.
- En mode Contraste élevé de Windows (`forced-colors: active`), bords et icônes système prennent le relais.

### 6.4 Typographies

| Rôle | Police | Taille / interligne | Remarque |
|---|---|---|---|
| Interface et texte | **Segoe UI Variable Text**, puis `Segoe UI`, `system-ui`, sans-serif | 14/20 (UI), 16/24 (synopsis) | Native sous Windows 11 : rien à télécharger, conforme à la CSP `font-src 'self'` et à la règle « zéro dépendance » |
| Titres | **Segoe UI Variable Display**, semi-gras | 28/34 (titre de fiche), 20/28 (sections), 36/44 (état vide) | Titre de carte : 14/18, semi-gras, 2 lignes au plus |
| Chiffres | Même police, `font-variant-numeric: tabular-nums` | 13 à 14 | Compteurs, tuiles, débits : pas de sautillement |
| Technique | **Cascadia Mono**, puis `Consolas`, monospace | 13/20 | n° de série, commande CLI, chemins |

Tailles en `rem`, espacements augmentés respectés (WCAG 1.4.12). Typographie française : espace insécable avant « : ? ! », « 12,8 Mo », « 1 h 32 », guillemets « ».

### 6.5 Mise en page et densité

| | Desktop 1440 | Laptop 1280 | Mobile 390 |
|---|---|---|---|
| Gouttières | 32 px | 24 px | 16 px, sans défilement horizontal de la page |
| Mur | 7 colonnes d'environ 180 px, espacement de 20 px | 6 colonnes | 3 colonnes d'environ 112 px, espacement de 10 px |
| Cover de fiche | 240 px | 200 px | 96 px |
| Grille d'épisodes | 10 × tuiles de 60×48, espacement de 8, + volet de 360 px | 10 × 52×44 + volet repliable | 5 × 64×48 (une dizaine sur 2 rangées) ; volet en feuille du bas |
| Densité | Mur **confortable**, grille **compacte**, liste **dense** (lignes de 56 px) | idem | confortable |

- Grille de base de 4 px.
- Rayons : 10 px pour les cartes, 8 px pour les tuiles et les boutons, 999 px pour les puces.
- Pas d'ombres portées : on marque la profondeur par les surfaces (`surface` puis `raised`).
- Une cover native de 360 px reste nette jusqu'à environ 180 px de large sur un écran en mise à l'échelle 200 %.

### 6.6 Covers
- **Fond flouté** tiré de la même image pour le héros et le théâtre ; jamais une image paysage agrandie.
- **Affiche générée** (sonde ou cover absente) : dégradé à deux teintes tiré du n° de série et titre en Display 20. Elle se distingue d'une vraie cover sans avoir l'air cassée.
- Chargement différé (`loading="lazy"`), dimensions fixées en 9:16 pour éviter les décalages de mise en page.

### 6.7 Mouvement
- 120 à 200 ms, `ease-out`, pour les survols, les puces et le tiroir. 350 ms pour l'envol de l'aperçu. 300 ms par palier de remplissage d'affiche.
- `prefers-reduced-motion` : pas d'envol ni de scintillement des squelettes, remplissages par paliers sans transition, décompte en texte seul, aucune vidéo en lecture automatique.
- Rien ne clignote plus de 3 fois par seconde.

### 6.8 Thème sombre ou clair ?
**Sombre par défaut.** Il y a trois raisons :
- le contenu est vidéo, et les covers saturées ressortent sur du bleu nuit ;
- c'est la continuité de dramafren ;
- on regarde souvent le soir.

**Clair en option** (Réglages → Affichage → Système / Sombre / Clair), avec les mêmes règles de contraste :

| Jeton | Hex |
|---|---|
| `bg` | `#F4F6FA` |
| `surface` | `#FFFFFF` |
| `raised` | `#EAEFF7` |
| `text` | `#111827` |
| `text-muted` | `#4B5568` |
| `accent` | `#1F5FD1` |
| `success` | `#137A4B` |
| `warning` | `#9A6200` |
| `danger` | `#C62828` |

Ratios ≥ 4,5:1 sur blanc (calcul approché, à valider).

---

## 7. Risques et faiblesses assumés

| # | Risque | Pourquoi on l'accepte | Parade |
|---|---|---|---|
| 1 | **L'activité est en retrait.** Quelqu'un qui enchaîne 5 liens veut voir la file. | Les téléchargements durent environ 1 min : une page File serait vide presque tout le temps. | Cartes « En file · 3e » sur le mur, tiroir épinglable, titre d'onglet. La route `#/activite` existe déjà (mobile) et peut devenir une page desktop si l'usage par lots se confirme. |
| 2 | **La barre a un double sens** (chercher ou ajouter) : un n° à 11 chiffres est ambigu. | Un seul champ, c'est moins de décisions ; le motif est connu (barre d'adresse). | Règle explicite : lien ou n° absent de la bibliothèque → aperçu ; présent → fiche + « Ajouter une version ». La puce de détection est toujours affichée. [+ Ajouter] reste visible. |
| 3 | **Le concept dépend des covers.** Sonde sans cover ; les anciens manifests ne gardent que l'URL distante (pas d'image hors ligne). | Le mur d'affiches est le cœur du concept. | Cache `cover.jpg` par dossier (P0 moteur), rempli au premier scan en ligne ; affiche générée en repli. |
| 4 | **Le regroupement par `book_id` est imparfait** : un n° de VF saisi directement, ou un dossier sonde `<id>-serie`, peut créer une carte en double. | C'est rare ; la clé `book_id` couvre le cas nominal. | Détection « Même série que… ? » [Regrouper] en V2 (alias dans `.sdg/aliases.json`). |
| 5 | **Des actions au survol** sont invisibles au clavier et au tactile. | Le survol garde le mur calme. | Mêmes actions au focus, « ⋯ » permanent sur mobile, fiche à un clic. |
| 6 | **L'affiche désaturée** peut être lue comme « désactivée » ou « en erreur ». | C'est le signal le plus fort et le plus beau de « ça arrive ». | Toujours accompagnée de « ↓ 34/62 », réservée aux états actif, en file et interrompu ; test utilisateur rapide à prévoir. |
| 7 | **Gérer une série demande d'ouvrir sa fiche** (2 niveaux). | Le mur reste lisible. | Actions principales sur la carte, étagère « À traiter », actions en masse sur le mur. |
| 8 | **Le mobile 390 n'est pas servi en V1** (écoute sur 127.0.0.1 seulement, faute d'authentification). | La sécurité passe avant. | La mise en page 390 sert dès la V1 aux fenêtres étroites (ancrage Windows) et au zoom jusqu'à 400 %. L'accès depuis le réseau local, avec authentification, viendra en V2. |
| 9 | **Titres multilingues** : quel titre montrer ? | Il faut en choisir un. | Réglage « Titres en : version préférée / VO », recherche sur tous les titres, titre VO en second dans la fiche. |
| 10 | **Pas de recherche par titre sur DramaBox.** Un champ « Chercher » peut laisser croire qu'elle existe. | Le moteur ne sait pas le faire. | Message explicite quand la recherche ne donne rien. L'emplacement est réservé en V3. |
| 11 | **Coût de rendu** : 100 affiches, fonds floutés, jusqu'à 1000 tuiles. | Volume réel modeste. | Chargement différé, flou appliqué à la petite image, tuiles pilotées par attributs et variables CSS. |
| 12 | **Beaucoup d'ajouts au moteur.** Sans eux, pas de pause ni de progression fine. | Le concept ne tient qu'avec eux. | Tableau ci-dessous, avec le mode dégradé de chaque ajout. |

### Ce que le concept exige du moteur

| Ajout moteur | Priorité | Sert à | Si absent (mode dégradé) |
|---|---|---|---|
| Événements structurés (octets, phases, épisodes) + SSE | P0 | S2, tiroir, tuiles en direct | Progression par paliers d'épisode, relue dans le manifest toutes les 2 s |
| Arrêt injecté ; `Cancelled` remet `pending` | P0 | Pause, Annuler, statut « Interrompu » fiable | Pas de pause ; l'état est réconcilié au scan |
| Index de bibliothèque + réconciliation disque | P0 | Mur, « À traiter », « Manquant » | — (bloquant) |
| Cache `cover.jpg` | P0 | Mur hors ligne | Cover distante, affiche générée hors ligne |
| Manifest enrichi : `languages`, `from_official`, réglages demandés, `error_code`, `created_at` | P0 | Onglets « + langue », « Compléter » avec les mêmes réglages, Échec ou Indisponible | Tous les échecs présentés comme réessayables ; langues inconnues pour les anciens manifests |
| Suppression avec corbeille (`scope` all / episodes / film / parts) | P0 | Dialogue Supprimer, « Libérer 684 Mo » | — |
| `force` / retéléchargement dans une qualité donnée | P0 | Remède « qualités mélangées » | Ré-encodage seulement |
| Plan du film avec `fixes`, `FilmError.code`, chapitres stockés, film obsolète | P1 | S5 | Refus traduits à partir du texte du message |
| Catalogue « doublée oui/non » par langue | P1 | Puces de version honnêtes | Aperçu relancé à la sélection (`lang_source: fallback`) |
| Estimation de taille + espace libre | P1 | Coût dans l'aperçu | « ≈ » calculé avec l'a priori 1080p |
| Rafraîchir les métadonnées (nouveaux épisodes) | P1 | « Vérifier les nouveaux épisodes » | Action masquée |
| Suivi de visionnage (`.sdg/watch.json`) | P1 (V1.1) | « Reprendre · ép. 14 », « Continuer à regarder » | Bouton « Regarder » depuis l'épisode 1 |
| Connectivité mesurée par le moteur | P1 | États hors ligne | Échecs réseau après les nouvelles tentatives |
| Vérification non destructive (`verify`) | V2 | « Vérifier les fichiers » | Réconciliation par taille seulement |