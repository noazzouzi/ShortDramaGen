# Jeu de données de la maquette

La spec ([spec-v1.md](spec-v1.md)) et le plan des artboards utilisent des **titres fictifs** pour les séries 2 à 12, et des covers **9:16**. Deux corrections s'appliquent à TOUS les écrans.

## Correction 1 : les covers sont en 3:4, pas en 9:16

Les affiches DramaBox réelles font **540 × 720 (3:4)**. Seules les **vidéos** sont verticales en 9:16. On garde donc le lecteur en 9:16 et on passe toutes les covers en 3:4 (`aspect-ratio: 3/4`, `object-fit: cover`) :

| Emplacement | Taille spec (9:16) | Taille à utiliser (3:4) |
|---|---|---|
| Carte affiche du mur desktop | 180 × 320 | **180 × 240** |
| Héros de la fiche | 240 × 427 | **240 × 320** |
| Héros réduit (Film) | 64 × 114 | **64 × 85** |
| Aperçu du dialogue d'ajout | 150 × 267 | **150 × 200** |
| Carte compacte « À traiter » | 48 × 85 | **48 × 64** |
| Ligne de job du tiroir | 40 × 71 | **40 × 53** |
| Mini-barre mobile | 24 × 43 | **24 × 32** |
| Liste du champ de recherche | 24 × 43 | **24 × 32** |
| Mur mobile (3 colonnes) | 112 × 199 | **112 × 149** |
| Aperçu mobile | 120 × 213 | **120 × 160** |
| Fiche mobile | 96 × 171 | **96 × 128** |
| Ligne de liste | 32 × 57 | **32 × 43** |
| **Vidéo du Théâtre** | 434 × 772 (9:16) | **inchangé, 434 × 772 (9:16)** |

Dans le Théâtre, la zone vidéo 9:16 montre la cover de la série en `object-fit: cover` comme image d'attente de la vidéo (placeholder crédible), sous les contrôles.

Une série sans cover (mode sonde, n° 41000999999) garde son **affiche générée** : un aplat uni bleu-gris (`#2A3A5C`), sans dégradé, avec « Série » en 13/18 et « 41000999999 » en IBM Plex Mono 16/20, centré, au format 3:4.

## Correction 2 : vraies séries, vrais titres, vraies covers

Les titres et nombres d'épisodes viennent du site officiel. Les **états** sont illustratifs mais cohérents entre eux. Les tailles et les durées des séries 2 à 12 sont **calculées à partir des moyennes mesurées** sur la série 1 : 11,3 Mo et 89 s par épisode en 1080p. Les covers sont déjà envoyées dans le canevas : utilise l'URL `/_blob/…` **telle quelle** dans `<img src="…">`.

Table de correspondance avec la spec : partout où la spec (ou le plan d'artboard) nomme le titre fictif de gauche, écris le titre réel et les chiffres de droite. Les séries réelles n'ont pas de « titre original » connu, sauf la n° 1 : **supprime la ligne « … · titre original »** pour les séries 2 à 12 (garde-la pour la n° 1 : « One Night to Forever · titre original »).

| # | Titre fictif (spec) | **Titre réel à afficher** | n° de série | Cover | Épisodes | Durée | État et chiffres |
|---|---|---|---|---|---|---|---|
| 1 | *(déjà réelle)* | **Qui Est la Véritable Mme Lafont ?** (VO : One Night to Forever) | 41000105199 | `/_blob/26d3092bb889c7e9a12af4b4f66a678f` | 62 | 1 h 32 | Inchangée : VO 62/62 ✓ 702 Mo + film VO 717 Mo ; VF 59/62, 649 Mo (3 manquant, 12 en 720p, 40 indisponible, 41 échec) → « ! VF · 3 à réparer » |
| 2 | La Revanche de l'héritière (80 ép.) | **La vie d'une belle-mère dans les années 1980** | 41000102609 | `/_blob/a5d40cc4231dbb325e34e29ccd43c618` | **82** | **2 h 02** | **En cours** : 21/82 vérifiés, ép. 22, 23 et 24 en cours (64 %, 31 %, 8 %), **231 / ≈ 927 Mo**, 9,7 Mo/s, **≈ 1 min 10 s**, coloration 26 % ; pilule « ↓ 21/82 · ≈ 1 min 10 s · +1 en file » ; titre d'onglet « (21/82) ShortDramaGen » |
| 3 | Ma femme de substitution (60 ép.) | **Un Pacte avec le Capitaine de Hockey** | 41000116285 | `/_blob/8207a53aafcbdac8ff934b54f5f7ab95` | **58** | **1 h 26** | **En file · 1er** : 0/58, ≈ 655 Mo, démarre dans ≈ 1 min 10 s |
| 4 | Série 41000999999 (sonde) | **Série 41000999999** (inchangée) | 41000999999 | affiche générée | 48 | inconnue | Interrompu hier à 23:14, 34/48, 370 Mo (+ 12 Mo de .part), badge « Non vérifiée » |
| 5 | Le Contrat d'un an (58/62) | **Fausse Romance Avec Mon Riche Ennemi** | 41000119532 | `/_blob/fd4e30e6a03e18924b0f4f3f5a853a34` | 62 | 1 h 32 | À compléter : 58/62, 4 nouveaux épisodes (59 à 62), 655 Mo |
| 6 | Mariée par erreur au PDG (71) | **Attention ! C'est la Patronne** | 41000121776 | `/_blob/ca04a7b5ba7d1b67bdf964628f3a8409` | **64** | **1 h 35** | Nominale, VO ✓, 723 Mo, film prêt 740 Mo |
| 7 | L'Héritier caché (64, VO+VF) | **L'Impardonnable le Jour du Mariage** | 41000116643 | `/_blob/c8fb2a95e10b2cfaf0517de7c18ef523` | **51** | **1 h 16** | Nominale, VO ✓ 576 Mo + VF ✓ 574 Mo, film VF prêt 590 Mo (badges « VO · VF » et « Film ») |
| 8 | Le Milliardaire amnésique (66) | **Un Accord Avec Mon Donateur Milliardaire** | 41000122689 | `/_blob/cf041e9c2d74ab06edf0347f16ae553a` | **61** | **1 h 30** | Nominale, 689 Mo, film 705 Mo |
| 9 | Trois ans de silence (58) | **Mon Mari Agent Secret** | 41000104105 | `/_blob/771d9f406e90a59131e0d21ce3720c73` | **57** | **1 h 25** | Nominale, 644 Mo, film 660 Mo |
| 10 | La Fiancée du tigre (70) | **Une nuit fatidique avec mon patron** | 41000103356 | `/_blob/e31a83cadcac9237656f9e2bdd327d20` | **56** | **1 h 23** | Nominale, 633 Mo, film 648 Mo |
| 11 | Le Dernier Rendez-vous (63) | **La PDG qu'on Prenait pour une Pauvre** | 41000119953 | `/_blob/b7946e560b5d14a266608f0be7c7fb1f` | **63** | **1 h 33** | Nominale, 712 Mo, film 728 Mo |
| 12 | Le Pacte de minuit (68) | **Gendre qui a choqué le village (Doublé)** | 41000106749 | `/_blob/93de8aeac270d4d30547def874c393d3` | **120** | **2 h 58** | Nominale, 1,36 Go, film 1,38 Go |

Covers en réserve, non possédées, utilisables dans un exemple de recherche ou d'aperçu si besoin :
- « Un Amour à Contretemps » (43 ép.) : `/_blob/59957605a4969d7fa03d4e4c14a15d5c`
- « Divorcée, Maintenant la Princesse Lycan (Doublé) » (67 ép.) : `/_blob/d08e465eefa9180c64dd150078b76a29`
- « Séduction Légale pour Milliardaire Glacial » (57 ép.) : `/_blob/76cfb56a944a3a50ba754330438c4ebc`

## Totaux recalculés (remplacent ceux de la spec)

- Stats de la bibliothèque : **« 12 séries · 14 versions · 14,7 Go · 182 Go libres sur C: »**.
- Réglages › Stockage : **« Bibliothèque 14,7 Go · épisodes 8,5 Go · films 6,2 Go · fichiers partiels 12 Mo »**.
- **Libérable : 6,0 Go** (épisodes déjà fusionnés dans un film complet).
- Puces de filtre : Toutes 12 · En cours 1 · En file 1 · À compléter 1 · Avec échecs 1 · Interrompues 1 · Film prêt 8 · Sans film 4 · Non vérifiées 1 · Libérable 6,0 Go · | · VO 12 · VF 2.
- Étagère « À traiter · 3 » :
  1. Qui Est la Véritable Mme Lafont ? · VF, [Réparer · 3] ;
  2. Série 41000999999, [Reprendre · 14] ;
  3. Fausse Romance Avec Mon Riche Ennemi · VO, « 4 nouveaux épisodes (59 à 62) », [Compléter · 4].
- Ordre du mur (tri « Activité récente ») : 2, 3, 1, 4, 5, 6, 7, 8, 9, 10, 11, 12.

## Job actif (série 2)

- Titre : « La vie d'une belle-mère dans les années 1980 · VO ». Démarré à 19:04:58.
- Progression : 21/82 vérifiés ; 22, 23 et 24 en cours (64 %, 31 %, 8 %) ; 25 à 82 en file.
- Volume et vitesse : 231 / ≈ 927 Mo, 9,7 Mo/s, ≈ 1 min 10 s.
- Ruban de **82** segments. Grille mobile : 17 rangées de 5 (la dernière n'en compte que 2).
- Journal :
  - 19:04:58 Infos officielles récupérées : 82 épisodes, version originale
  - 19:04:58 Téléchargement lancé : 82 épisodes, 1080p, 3 en parallèle
  - 19:05:01 Ép. 1 vérifié (1 min 52, 1080p, 14,1 Mo)
  - 19:05:27 Ép. 21 vérifié (1 min 31, 1080p, 11,4 Mo)

## Divers

- **File d'attente** : « Un Pacte avec le Capitaine de Hockey · VO · 58 ép. · ≈ 655 Mo · démarre dans ≈ 1 min 10 s ».
- **Aperçu d'ajout** (VE de la série 1, « Una Noche Para Siempre ») : ≈ 690 Mo · ≈ 1 min 10 s · démarre après 2 séries (≈ 2 min 20 s).
- **Instantané commun** : samedi 26 septembre 2026, 19:05 ; 182 Go libres sur C: ; dossier `C:\Users\…\Videos\ShortDramaGen`.
