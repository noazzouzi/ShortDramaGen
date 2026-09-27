# ShortDramaGen : système de design v1

> Direction : **« Salle de projection bleu nuit »**, dans la continuité de dramafren. L'interface reste plate, sobre et désaturée : ce sont les covers qui apportent la couleur. L'accent bleu est rare (action principale, lien, sélection). Le lavande est réservé à « en cours ». Thème sombre par défaut ; un thème clair est fourni.
> **Interdits** : dégradés décoratifs (un voile plein sous le texte d'une cover est permis), emoji, bordures gauches colorées sur les cartes et les bandeaux, ombres sur les cartes au repos, drapeaux pour les langues, texte blanc sur l'accent en thème sombre, symbole ⌘.

---

## 1. Couleurs : thème sombre (par défaut)

Les ratios ci-dessous ont été calculés avec la formule WCAG 2.x (luminance relative). Règle : **texte ≥ 4,5:1** sur toute surface où il apparaît ; **bords et composants ≥ 3:1**.

### 1.1 Fonds et surfaces

| Jeton | Hex | Usage |
|---|---|---|
| `bg` | `#0B1220` | Fond de page, en-tête |
| `surface-1` | `#131C2E` | Cartes, panneaux, volet, tiroir, dialogues, fond de la grille d'épisodes |
| `surface-2` | `#1B2640` | Contrôles (boutons secondaires, champs au survol), menus, tuile « en file », squelettes |
| `surface-3` | `#243150` | Survol dans les menus, pistes de progression, badges neutres, infobulles |
| `backdrop` | `#05080F` | Fond du Théâtre |
| `scrim` | `rgba(11,18,32,0.85)` | Voile plein sous tout texte posé sur une cover |
| `overlay` | `rgba(5,8,15,0.60)` | Voile derrière les dialogues modaux |

### 1.2 Bordures

| Jeton | Hex | Usage | Ratio sur bg / s1 / s2 / s3 |
|---|---|---|---|
| `border-subtle` | `#26324D` | Séparateurs et filets décoratifs (non porteurs d'information) | 1,47 sur bg (décoratif) |
| `border-default` | `#2E3A57` | Contour des boutons secondaires, puces et cartes compactes (décoratif) | décoratif |
| `border-control` | `#7888A8` | Contours porteurs d'information : champs, tuiles « à télécharger », « en file », pointillés | 5,25 / 4,77 / 4,21 / 3,61 |

### 1.3 Texte

| Jeton | Hex | Usage | Ratio sur bg / s1 / s2 / s3 |
|---|---|---|---|
| `text-primary` | `#E8ECF4` | Texte principal, titres, numéros de tuiles sombres | 15,81 / 14,38 / 12,69 / 10,88 |
| `text-secondary` | `#A7B2C8` | Méta, titre VO, aides, stats | 8,78 / 7,98 / 7,04 / 6,04 |
| `text-tertiary` | `#8E9BB4` | Étiquettes de rangée, surtitres, compteurs de puces, placeholders | 6,68 / 6,05 / 5,36 / 4,60 |
| `text-on-accent` | `#0B1220` | Texte sur accent, succès, avertissement, danger ou échec plein | 6,76 sur accent · 9,98 sur success · 10,32 sur warning · 6,75 sur danger |
| `text-on-tile-done` | `#FFFFFF` | Numéro et glyphe sur tuile téléchargée | 4,97 sur `tile-done` |

### 1.4 Accent et focus

| Jeton | Hex | Usage | Ratio |
|---|---|---|---|
| `accent` | `#5B9BFF` | Bouton principal (texte `#0B1220`), liens, onglet actif, puces sélectionnées, anneau de sélection | 6,76 / 6,14 / 5,42 / 4,65 |
| `accent-hover` | `#7DB0FF` | Survol du bouton principal | texte sombre 8,49 |
| `accent-pressed` | `#4A86EB` | Bouton principal pressé | texte sombre 5,26 |
| `accent-subtle` | `#1A2C52` | Fond de puce sélectionnée, épisode en lecture | accent dessus 4,97 · texte 11,62 |
| `focus` | `#8FC1FF` | Anneau de focus de 2 px, décalé de 2 px (sur tuile cochée : 5 px) | 10,02 / 9,11 / 8,04 / 6,89 |

### 1.5 États sémantiques

| Jeton | Hex | Fond associé (`-subtle`) | Couleur sur son fond | Ratio sur bg / s1 / s2 / s3 | Usage |
|---|---|---|---|---|---|
| `success` | `#3DD68C` | `#12352A` | 7,14 | 9,98 / 9,08 / 8,01 / 6,87 | Vérifié, terminé, santé OK |
| `warning` | `#F5B544` | `#3E3113` | 7,00 | 10,32 / 9,39 / 8,28 / 7,10 | Interrompu, manquant, 720p isolé, à compléter, film obsolète |
| `danger` | `#FF6B6B` | `#4C1B26` | 5,07 | 6,75 / 6,14 / 5,41 / 4,64 | Échec, suppression, moteur injoignable |
| `info` | `#56C8E8` | `#10324A` | 6,86 | 9,65 / 8,78 / 7,74 / 6,64 | Mode sonde (« Infos limitées »), hors ligne, reprise, « déjà possédée » |
| `active` (en cours) | `#C4B5FF` | `#2B2360` | 7,54 | 10,16 / 9,24 / 8,14 / 6,99 | **Uniquement** « en cours » : barres, rubans, tuile, pilule, badge |

`text-primary` sur chaque fond `-subtle` : 11,31 (success) · 10,73 (warning) · 11,89 (danger) · 11,25 (info) · 11,73 (active).

**Séparation par la luminance**
- `active` (L = 0,52) se distingue de l'accent (L = 0,33, rapport 1,50) et du danger (rapport 1,51).
- Face au succès (L ≈ 0,51), la teinte seule ne suffit pas : la distinction repose sur la **forme** (tuile sombre avec barre basse et glyphe ↓, contre tuile pleine avec ✓) et sur la hauteur des segments du ruban.

### 1.6 Tuiles d'épisode (couleurs dédiées)

| Jeton | Hex | Luminance | Ratio |
|---|---|---|---|
| `tile-done` | `#1E7F55` | 0,161 | 3,42 contre surface-1 ; texte blanc 4,97 |
| `tile-unverified` | `#1D4A38` | 0,054 | texte 8,49 ; bord success 5,36 |
| `tile-failed` | `#FF6B6B` (= danger, plein) | 0,328 | texte sombre 6,75 ; 6,14 contre surface-1 |
| `tile-active` | `#2B2360` (= active-subtle) | 0,026 | bord active 7,54 contre la tuile, 9,24 contre surface-1 |
| `tile-interrupted` | `#3E3113` (= warning-subtle) | 0,033 | bord warning 7,00 |
| `tile-queued` | `#1B2640` (= surface-2) | 0,020 | bord `border-control` 4,21 |
| `hatch-a` / `hatch-b` | `#1B2640` / `#33405C` | — | hachures à 45°, bandes de 4 px (texture, non porteuse seule) |

---

## 2. Couleurs : thème clair (option)

| Jeton | Hex | Ratio sur bg `#F4F6FA` / s1 `#FFFFFF` / s2 `#EDF1F8` |
|---|---|---|
| `bg` | `#F4F6FA` | — |
| `surface-1` | `#FFFFFF` | — |
| `surface-2` | `#EDF1F8` | — |
| `surface-3` | `#E2E8F2` | — |
| `border-control` | `#7A8599` | 3,44 sur bg |
| `text-primary` | `#111827` | 16,40 / 17,74 / 15,66 |
| `text-secondary` | `#475467` | 7,10 / 7,69 / 6,79 |
| `text-tertiary` | `#5B6478` | 5,48 / 5,93 / 5,24 |
| `accent` | `#1F5FD1` | 5,37 / 5,81 / 5,13 (**texte blanc 5,81**) |
| `success` | `#137A4B` | 4,96 / 5,37 / 4,74 |
| `warning` | `#8F5A00` | 5,35 / 5,78 / 5,11 |
| `danger` | `#C62828` | 5,20 / 5,62 / 4,96 |
| `info` | `#0B6E8C` | 5,36 / 5,80 / 5,12 |
| `active` | `#6B46E0` | 5,43 / 5,87 / 5,18 |
| `tile-done` | `#1A7A50` | texte blanc 5,33 |
| `tile-failed` | `#C62828` | texte blanc 5,62 |

Dans le thème clair, les fonds `-subtle` deviennent des teintes à 10 % sur blanc, et le texte y utilise la couleur d'état foncée ci-dessus.

---

## 3. Statuts d'épisode : fond, luminance, bord et glyphe

**Paliers de luminance du fond**
- **P0** : transparent (on voit surface-1, L ≈ 0,012).
- **P1** : teinte sombre (L 0,02 à 0,05).
- **P2** : moyen (L ≈ 0,16).
- **P3** : vif (L ≈ 0,33).

Les deux états les plus fréquents, **téléchargé (P2)** et **pas encore (P0 ou P1)**, se distinguent donc par la luminance seule. L'échec (P3) est l'état le plus clair et le plus saillant. Tous les autres statuts se distinguent par la forme du bord et par le glyphe.

| Statut | Fond (palier) | Bord | Glyphe (14 px, trait de 1,75, coin bas-droit) | Numéro | Élément ajouté |
|---|---|---|---|---|---|
| À télécharger | transparent (P0) | 1 px **tirets** `border-control` | — | `text-secondary` 7,98 | — |
| Non demandé | transparent (P0) | aucun | — | `text-tertiary` 6,05 | — |
| En file | `tile-queued` (P1) | 1 px plein `border-control` | horloge, `text-tertiary` | `text-primary` 12,69 | — |
| En cours | `tile-active` (P1) | 2 px plein `active` | flèche ↓ `active` | `text-primary` 11,73 | barre de 4 px en bas (piste `surface-3`, remplissage `active` à `--p`) |
| Interrompu | `tile-interrupted` (P1) | 2 px plein `warning` | pause ‖ `warning` | `text-primary` 10,73 | barre de 4 px `warning` figée à X % |
| Téléchargé et vérifié | `tile-done` (**P2**) | aucun | coche ✓ blanche | `#FFFFFF` 4,97 | — |
| Téléchargé, non vérifié (sonde) | `tile-unverified` (P1) | 1 px tirets `success` | ≈ `success` | `text-primary` 8,49 | — |
| Échec | `tile-failed` (**P3**) | aucun | ! `#0B1220` | `#0B1220` 6,75 | — |
| Indisponible à la source | hachures (P1) | 1 px tirets `border-control` | – `text-secondary` | `text-secondary` | — |
| Fichier manquant | transparent (P0) | 2 px tirets `warning` | ? `warning` | `text-primary` 14,38 | — |
| Retiré (film conservé) | transparent (P0) | aucun | pellicule `text-tertiary` | `text-tertiary` | — |
| **Qualité différente** (se cumule) | — | — | — | — | badge de 22 × 14 dans le coin haut-droit, fond `warning`, « 720 » en 10/12 600 `#0B1220` (10,32) |
| **Sélection** (se cumule) | inchangé | anneau accent de 2 px **à l'extérieur**, séparé de 2 px (`box-shadow: 0 0 0 2px #131C2E, 0 0 0 4px #5B9BFF`, 6,14 contre surface-1) | pastille de 16 px `accent` avec coche `#0B1220`, coin haut-gauche | — | — |
| **Focus** | inchangé | `outline: 2px solid #8FC1FF`, décalage de 2 px (5 px si cochée) | — | — | — |
| **Vu** (Théâtre) | inchangé | — | — | — | point de 4 px `text-secondary` centré en bas |

**Ruban de complétude.** Hauteur 6 px, piste `surface-3`, segments égaux avec 1 px d'espace. La hauteur change selon le statut, ce qui donne un repère non chromatique :

| Statut | Segment | Ratio contre la piste |
|---|---|---|
| Vérifié | plein `success` | 6,87 |
| En cours | plein `active` | 6,99 |
| Échec | `danger`, **10 px** (dépasse de 2 px en haut et en bas) | 4,64 |
| Interrompu, manquant ou 720p | `warning`, **3 px** centré | 7,10 |
| Indisponible | hachures `border-control` | — |
| À venir | piste seule | — |

**Badges de série** (22 px, rayon plein, 12/16 500, glyphe de 12)

| Badge | Fond | Texte | Glyphe |
|---|---|---|---|
| En cours | `active-subtle` | `active` | ↓ |
| En file | `surface-3` | `text-secondary` | horloge |
| Interrompu | `warning-subtle` | `warning` | ‖ |
| Avec échecs | `danger-subtle` | `danger` | ! |
| À compléter | `warning-subtle` | `warning` | demi-cercle |
| Non vérifiée | `info-subtle` | `info` | ≈ |
| Version (VO, VF…) | `surface-3` | `text-primary` | — |
| Film | `surface-3` | `text-primary` | clap |
| Film partiel | transparent + 1 px tirets `border-control` | `text-secondary` | clap |
| Film obsolète | `warning-subtle` | `warning` | clap |

« Complète » n'a pas de badge : l'état nominal reste silencieux.

---

## 4. Typographie

- **Familles** (Google Fonts pour la maquette ; woff2 auto-hébergés dans le produit, licence OFL) :
  - **IBM Plex Sans** 400, 500 et 600 pour toute l'interface, titres compris. Chiffres tabulaires via `font-variant-numeric: tabular-nums` sur les compteurs, tailles, débits, temps et numéros de tuiles.
  - **IBM Plex Mono** 400 et 500 pour les n° de série, les commandes, les chemins, le journal, le champ de plages et le `kbd`.
  - Lien de la maquette : `https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap`.
  - Repli : `"IBM Plex Sans", "Segoe UI", system-ui, sans-serif` et `"IBM Plex Mono", "Cascadia Mono", Consolas, monospace`.

| Jeton | Taille / interligne (px) | Graisse | Approche | Usage |
|---|---|---|---|---|
| `display` | 32 / 40 | 600 | −0,5 px | Titre d'état vide (« Ta bibliothèque est vide ») |
| `title-xl` | 28 / 36 | 600 | −0,25 px | Titre de la fiche série |
| `title-l` | 24 / 32 | 600 | 0 | Titre de page (Bibliothèque, Réglages) |
| `title-m` | 20 / 28 | 600 | 0 | Sections (Épisodes, Film), titres de dialogue |
| `title-dialog-series` | 22 / 28 | 600 | 0 | Titre de série dans l'aperçu d'ajout |
| `title-s` | 16 / 24 | 600 | 0 | Titres de panneau, de tiroir, d'étagère |
| `body-l` | 16 / 24 | 400 | 0 | Synopsis, textes d'état vide, phrases d'état du film |
| `body` | 14 / 20 | 400 | 0 | Texte d'interface par défaut, messages |
| `button` | 14 / 20 | 500 | 0 | Boutons md et lg (15 / 20 600 pour lg) ; sm : 13 / 18 500 |
| `card-title` | 14 / 18 | 600 | 0 | Titre de carte affiche (2 lignes au plus, points de suspension) |
| `label` | 13 / 18 | 500 | 0 | Puces, onglets, méta, légendes, stats |
| `caption` | 12 / 16 | 500 | 0 | Badges, lignes d'état des cartes, pilule compacte, étiquettes de rangée |
| `overline` | 12 / 16 | 500 | +0,6 px, majuscules | Titres de section du tiroir (EN COURS, EN FILE) |
| `tile` | 14 / 16 | 600 | 0, tabulaire | Numéros de tuiles (desktop et mobile) ; 13 / 16 dans les mini-grilles |
| `tile-badge` | 10 / 12 | 600 | 0 | Badge « 720 » |
| `mono` | 13 / 20 | 400 | 0 | Commandes, chemins, n° de série |
| `mono-s` | 12 / 16 | 400 | 0 | Journal, `kbd` |
| `omnibar-hero` | 20 / 28 | 400 | 0 | Champ central de l'état vide (56 px) |

**Règles françaises**
- Espace fine insécable (U+202F) avant « ? ! ; » et espace insécable (U+00A0) avant « : » et à l'intérieur des guillemets « ».
- Formats : « 12,8 Mo », « 1 h 32 », « 1 min 10 s », « 9,7 Mo/s » (virgule décimale).
- Titres limités à 2 lignes, avec le titre complet en infobulle.

---

## 5. Espacements, rayons, élévations

- **Espacements** (base 4, rythme 8) : `space-1` 4 · `space-2` 8 · `space-3` 12 · `space-4` 16 · `space-5` 20 · `space-6` 24 · `space-8` 32 · `space-10` 40 · `space-12` 48 · `space-16` 64.
- **Rayons** :

| Jeton | Valeur | Usage |
|---|---|---|
| `radius-xs` | 4 | Badge « 720 », `kbd` |
| `radius-sm` | 6 | Tuiles d'épisode, infobulles |
| `radius-md` | 8 | Boutons, champs, select, éléments de menu, segments |
| `radius-lg` | 10 | Cartes, covers, panneaux, barre de santé, toasts |
| `radius-xl` | 14 | Dialogues, héros de la fiche |
| `radius-full` | 999 | Puces, badges, pilule, interrupteurs |

- **Élévations** (uniquement pour ce qui flotte) :
  - `e0` : aucune ombre (cartes, panneaux). La profondeur vient des surfaces.
  - `e1` (menus, popovers, infobulles, liste du champ) : `0 4px 12px rgba(0,0,0,0.40), 0 0 0 1px #26324D`.
  - `e2` (dialogues, tiroir, toasts, barre de sélection flottante) : `0 16px 40px rgba(0,0,0,0.55), 0 0 0 1px #2E3A57`.
- **Icônes** : Lucide, **trait de 1,75 px**, `stroke-linecap: round`. Tailles : 12 (badges), 14 (glyphes de tuiles), 16 (inline, champs, menus), 20 (boutons, barre de santé, bandeaux, pré-vol), 24 (barre du bas mobile, logo). Correspondances :
  - `search`, `clipboard-paste`, `plus`, `arrow-down-to-line` (téléchargement), `pause`, `play`, `rotate-cw` (réessayer), `check`, `circle-check`, `circle-alert` ;
  - `minus` (indisponible), `circle-help` (manquant), `clock` (en file), `clapperboard` (film), `folder-open`, `trash-2`, `settings`, `activity`, `x`, `ellipsis`, `chevron-down`, `chevron-left`, `chevron-right`, `hard-drive`, `wifi-off`, `plug-zap` (moteur), `languages`, `keyboard`, `copy`, `terminal`.

---

## 6. Grilles de mise en page

| | Desktop 1440 | Laptop 1280 | Snap 600-1023 | Mobile 390 |
|---|---|---|---|---|
| Marges latérales | 32 | 24 | 24 | 16 |
| Colonnes / espacement | 12 / 24 (colonne ≈ 92,7) | 12 / 24 | 8 / 16 | 4 / 16 (colonne 77,5) |
| Largeur de contenu | 1376 | 1232 | fluide | 358 |
| En-tête | 64 | 64 | 64 | barre d'app de 56 + barre du bas de 64 |
| Mur d'affiches | `auto-fill, minmax(164px, 1fr)`, espacement de 20 → **7 × 180** (cover 180 × 320) | 6 × ≈ 188 | 4 × ≈ 150 | **3 × 112** (cover 112 × 199), espacement de 10 |
| Fiche | cover du héros 240 × 427 ; colonne principale de 984 + volet de 360, espacement de 32 | cover de 200 ; colonne principale + volet de 320 | une colonne | une colonne, cover de 96 × 171 |
| Grille d'épisodes | **10 × 56 × 48**, espacement de 12, étiquettes de rangée de 44 → 724 de large | 10 × 52 × 44 | 10 × 48 × 44 | **5 × 60 × 48**, espacement de 12 → 348 |
| Tiroir | 400, sous l'en-tête | 400, en surimpression | 360, en surimpression | page |
| Dialogue d'ajout | 760 | 720 | largeur − 48 | feuille plein écran |

Covers : jamais agrandies au-delà de leur taille native de 360 × 640 à 2x, donc 180 px de large au plus dans les grilles. Format 9:16 toujours fixé (`aspect-ratio: 9/16`) pour éviter les décalages de mise en page. Chargement différé.

---

## 7. Composants : mesures exactes

### 7.1 Boutons

| Variante | Hauteur | Marges | Texte | Fond / texte | Survol | Pressé |
|---|---|---|---|---|---|---|
| Principal | sm 32 · md 40 · lg 48 | 0 12 · 0 16 · 0 20 | 13/500 · 14/500 · 15/600 | `accent` / `#0B1220` | `accent-hover` | `accent-pressed` |
| Secondaire | idem | idem | idem | `surface-2` + 1 px `border-default` / `text-primary` | `surface-3` | `surface-1` |
| Fantôme | idem | idem | idem | transparent / `text-secondary` | `surface-2` + `text-primary` | — |
| Danger | idem | idem | idem | `danger` / `#0B1220` | `#FF8585` | `#F05555` |
| Icône | 32 × 32 · 40 × 40 (44 × 44 sur mobile) | — | icône de 16 ou 20 | transparent / `text-secondary` | `surface-2` | — |

- **Désactivé** : fond `surface-2`, texte `text-tertiary`, **toujours avec la raison** en texte `caption` sous le bouton ou dans une infobulle accessible au clavier (`aria-describedby`).
- **En cours** : spinner de 16 à gauche, ou progression inscrite dans le bouton (« Assemblage… 38/62 ») avec un remplissage `accent-hover` à `--p` derrière le texte (ratio du texte ≥ 6,76).
- Icône et texte séparés de 8 px. Un bouton qui a un raccourci l'affiche dans son infobulle via `kbd`.

### 7.2 Champs
- **Champ standard** : hauteur 40, marges 0 12, fond `surface-1`, bord 1 px `border-control`, rayon 8, texte `body`.
  - Focus : bord `accent` + anneau `focus`.
  - Erreur : bord `danger` + message `caption` `danger` sous le champ, relié par `aria-describedby`.
- **Champ « Chercher ou coller »** : 560 × 40, icône loupe de 16 à 12 px du bord gauche, `kbd` « Ctrl K » (hauteur 22, `mono-s`, fond `surface-3`, rayon 4) à 8 px du bord droit.
  - Puce de détection : hauteur 24, fond `info-subtle`, texte `info`, `caption`.
  - Liste déroulante : 560 de large, rangées de 48 (série, avec cover de 24 × 43) ou 36 (action), `e1`.
- **Champ central de l'état vide** : 640 × 56, `omnibar-hero`.
- **Champ de plages** : 200 × 40, `mono`.
- **Select** : 40, chevron de 16.
- **Case à cocher** : 18 × 18, rayon 4, bord `border-control`, cochée en `accent` avec coche `#0B1220`. Zone de clic de 32 (44 sur mobile).
- **Radio** : 18, point de 8. Rangée de radio du dialogue Supprimer : 48 de haut.
- **Interrupteur** : 36 × 20, bouton de 16, activé en `accent`.

### 7.3 Puces, badges, onglets, contrôle segmenté
- **Puce de filtre** : hauteur 32, marges 0 12, rayon plein, bord 1 px `border-default`, texte `label` `text-secondary`, compteur en `text-tertiary` tabulaire à 6 px du texte.
  - Sélectionnée : fond `accent-subtle`, bord `accent`, texte `text-primary`, coche de 14.
  - Espacement entre puces : 8.
- **Puce de version** (dialogue d'ajout) : hauteur 36, marges 0 14, même style.
  - État « vérification… » : texte `text-tertiary`, pulsation d'opacité de 0,6 à 1 en 1,2 s (aucune si reduced-motion).
- **Badge** : hauteur 22, marges 0 8, rayon plein, `caption`, glyphe de 12. Deux badges au maximum sur une carte, « +1 » au-delà.
- **Onglets de version** : hauteur 44, marges 0 16, texte `label` 500. Onglet actif : `text-primary` + soulignement de 2 px `accent`. Inactif : `text-secondary`. Le statut de chaque onglet (« ✓ 62/62 », « 59/62 ! ») est en `caption` à 8 px du texte.
- **Contrôle segmenté** : hauteur 32, segments de 0 12, fond `surface-1`, segment actif `surface-3` + `text-primary`.

### 7.4 Tuiles et grilles d'épisodes

| Contexte | Tuile | Espacement | Par ligne | Numéro |
|---|---|---|---|---|
| Fiche desktop | 56 × 48, rayon 6 | 12 | 10 | `tile` 14/16 600 centré ; glyphe de 14 à 4 px du coin bas-droit ; barre de 4 px en bas pour « en cours » et « interrompu » |
| Dialogue d'ajout | 44 × 36 | 6 | 10 | 13/16 |
| Théâtre | 48 × 40 | 8 | 5 | 13/16 |
| Mobile | 60 × 48 | 12 | 5 | 14/16 |

- Étiquettes de rangée (« 1–10 ») : colonne de 44, `caption` tabulaire `text-tertiary`, alignées à droite, 12 px avant la première tuile.
- **Légende-compteurs** : puces de 32 (glyphe + libellé + nombre).
- **Barre de mode sélection** : hauteur 40, fond `accent-subtle`, texte `label`, bouton fantôme « Quitter (Échap) ».
- **Infobulle de tuile** : `e1`, fond `surface-3`, `caption`, marges 6 8, largeur maximale 280, apparaît après 300 ms.

### 7.5 Cartes

- **Carte affiche**
  - Desktop 180 × (320 + 8 + 6 + 36 + 18) ; mobile 112 × (199 + 6 + 6 + 36 + 16 + 44 si une action est affichée).
  - Cover : rayon 10.
  - Bande d'état : 72 px de voile plein `scrim` en bas de la cover, marges 10 ; ligne d'état en `caption` (couleur de l'état ou `text-primary`), badges à 6 px en dessous.
  - Au survol ou au focus : case de 24 à 8/8 du coin haut-gauche · bouton icône ⋯ de 32 à 8/8 du coin haut-droit (fond `scrim`) · action principale (sm 32, largeur 180 − 16 − 40) et bouton ▶ (32 × 32) en bas de la cover, à 8 px des bords.
  - Carte cochée : anneau accent de 2 px à l'extérieur avec 2 px d'écart, et pastille coche de 20.
  - Coloration : couche grise (`filter: grayscale(1) brightness(.6)`) + couche couleur découpée par `clip-path` selon `--p`, transition de 300 ms par palier (aucune si reduced-motion).
  - **Pas de bordure gauche colorée, pas d'ombre.**
- **Carte compacte « À traiter »** : 344 × 104 (mobile 280 × 96), fond `surface-1`, bord 1 px `border-subtle`, rayon 10, marges 12, cover de 48 × 85 à gauche (rayon 6), texte à 12 px. Titre `title-s` 14/20 600 sur 1 ligne, problème en `label` `text-secondary`, bouton sm en bas à droite, ⋯ de 32 en haut à droite.
- **Ligne de liste** : hauteur 56, affiche de 32 × 57, séparateur `border-subtle`. Survol : `surface-1`. Ligne sélectionnée : `accent-subtle`.
- **Barre de santé** (fiche) : hauteur 72, fond `surface-1`, rayon 10, marges 16 20, icône de 20 dans la couleur de l'état, phrase en `body`, boutons md à droite espacés de 8.
- **Carte Film** : fond `surface-1`, rayon 10, marges 24. Lignes de pré-vol de 40 (icône de 20 `success`, `danger` ou `warning` + libellé `body` 500 + détail `body` `text-secondary`). Remèdes : boutons lg empilés avec un espacement de 8 ; sous-titre en `caption` `text-secondary` sous le bouton recommandé.

### 7.6 Progression
- **Barre** : 6 px (tiroir, fiche, aperçu) ou 4 px (tuile, pilule, mini-barre), rayon plein, piste `surface-3`. Remplissage `active` (téléchargement), `success` (terminé), `warning` (pause ou interrompu), `accent-hover` (film dans le bouton). Transition linéaire de 250 ms, jamais vers l'arrière.
- **Ruban** : voir §3. Largeur : pleine largeur de la ligne ; 80 px en vue Liste.
- **Anneau** (pilule, favicon) : 16 px, trait de 2, piste `surface-3`, arc `active`.

### 7.7 Pilule, tiroir, mini-barre
- **Pilule d'activité** : hauteur 32, marges 0 12 0 8, rayon plein, fond `surface-2`, bord 1 px `border-default`, anneau de 16 + texte `label` tabulaire `text-primary`, séparateurs « · » en `text-tertiary`. Largeur automatique, au plus 320.
- **Tiroir** : 400 de large, fond `surface-1`, `e2`. En-tête de 56 (marges 0 16). Sections avec titre `overline` à 24/16/8.
  - Ligne de job : marges 16 ; cover de 40 × 71 (rayon 6) ; 12 px, puis bloc texte ; barre de 6 à 8 px sous le titre ; ruban de 6 à 8 px dessous ; boutons sm espacés de 8.
- **Mini-barre mobile** : hauteur 56, fond `surface-2`, bord haut `border-subtle`, cover de 24 × 43, texte `label`, bouton icône de 44.

### 7.8 Toasts, bandeaux, dialogues, menus
- **Toast** : 360 de large, hauteur minimale 56, marges 12 16, fond `surface-2`, `e2`, rayon 10, icône de 20 (couleur de l'état), texte `body`, actions en boutons fantômes sm à droite. Position : en bas à gauche, à 24 px ; empilement avec 8 px d'espace, 3 au maximum. Entrée : fondu et glissement de 8 px en 160 ms (fondu seul si reduced-motion).
- **Bandeau** : pleine largeur de contenu, hauteur minimale 48, marges 12 16, fond `-subtle` de l'état, icône de 20 de l'état, texte `body` `text-primary`, actions sm à droite. **Pas de bordure gauche colorée.** Rayon 10 dans le contenu, 0 sous l'en-tête.
- **Dialogue** : largeurs de 760 (ajout), 520 (suppression, confirmation) et 640 (raccourcis). Fond `surface-1`, rayon 14, `e2`, marges 24, en-tête de 56 (titre `title-m`, bouton × de 40). Pied avec boutons alignés à droite, espacement de 8 (le bouton principal est à droite). Voile `overlay`.
- **Popover** (« Tout réparer ») : 360 de large, marges 16, `e1`, rayon 10.
- **Menu** : largeur minimale 220, marges 4, éléments de 36 (marges 0 12, icône de 16, raccourci aligné à droite en `mono-s` `text-tertiary`), séparateur de 1 px `border-subtle`. Élément destructif en `danger`.
- **Infobulle** : `surface-3`, `caption`, marges 6 8, rayon 6.

### 7.9 Théâtre
- Fond `backdrop`, barre haute de 56 (fond `bg`).
- Vidéo 9:16 centrée dans la zone gauche : 434 × 772 à 1440 × 900, rayon 10.
- Boutons de navigation d'épisode (secondaires md) à 24 px de la vidéo.
- Contrôles de 72 : bouton lecture de 44, barre de lecture de 4 px (8 px au survol) avec repères de chapitre de 2 × 8 px en `text-tertiary`, temps en `label` tabulaire.
- Panneau droit de 360 (`surface-1`, marges 20).

### 7.10 États de chargement
- **Squelettes** : blocs `surface-2` aux dimensions exactes du contenu (covers 9:16, lignes de 12 et 16 px, rayons conservés). Pulsation d'opacité de 0,6 à 1 en 1,2 s ; **aucune** avec reduced-motion. Pas de balayage lumineux.
- **Barre indéterminée** (démarrage, sonde) : 2 px, segment `accent` de 30 % qui se déplace ; version statique à 30 % si reduced-motion.

### 7.11 Mobile
- **Barre d'app** de 56 : logo de 24 à 16 px, titre `title-s`, icônes de 44.
- **Barre du bas** de 64 + zone sûre, fond `bg`, bord haut `border-subtle`. 4 cibles de 97,5 × 64 : icône de 24 + libellé `caption`. Actif : `accent` ; inactif : `text-secondary`. Badge de 18 en `danger` ou `active`.
- **Feuille du bas** : rayon 14 en haut, poignée de 36 × 4 (`border-control`), marges 16, `e2`.
- **Action collée en bas** : 358 × 48, à 16 px des bords, au-dessus de la mini-barre ; fond de zone `bg` avec un filet haut.

---

## 8. Mouvement

| Élément | Durée | Courbe |
|---|---|---|
| Survol, puces, boutons | 120 ms | ease-out |
| Menus, popovers, infobulles | 160 ms | ease-out (fondu + 4 px) |
| Tiroir | 200 ms | ease-out (glissement de 400 px) |
| Dialogue | 160 ms | fondu + échelle de 0,98 à 1 |
| Palier de coloration d'une affiche | 300 ms | linéaire |
| Barres | 250 ms | linéaire |

- Rien ne tourne en continu sauf les spinners (1 s par tour).
- Rien ne clignote plus de 3 fois par seconde.
- **`prefers-reduced-motion: reduce`** : toutes les durées passent à 0, pas de pulsation, remplissages par paliers, décomptes en texte seul, aucune vidéo en lecture automatique.

---

## 9. Checklist d'application

1. Chaque statut combine fond (palier de luminance), bord, glyphe et nom accessible : jamais la couleur seule.
2. `active` (lavande) ne sert **qu'à** « en cours » ; `accent` ne sert **qu'à** l'action, au lien et à la sélection ; `focus` ne sert qu'au focus.
3. Une seule action en style principal par vue ou par carte.
4. Texte sur une cover : uniquement sur le voile `scrim`.
5. Chiffres tabulaires partout où ça bouge.
6. Quand tout va bien, les cartes n'affichent aucun badge d'état.
7. Cibles ≥ 44 sur mobile, ≥ 32 sur desktop ; 8 px entre une action destructive et ses voisines.
8. Pas de dégradé, pas d'emoji, pas de bordure gauche colorée, pas d'ombre sur les éléments posés.
