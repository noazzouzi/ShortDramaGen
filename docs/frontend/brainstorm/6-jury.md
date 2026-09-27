# 6 — Jury : notes et verdicts

Trois juges indépendants ont noté les trois concepts, chacun sous un angle différent, de 1 à 10 par critère.

**Total cumulé : A = 148 · B = 140 · C = 134.** Le concept A arrive premier chez les trois juges.

## Juge 1 — Heuristiques de Nielsen, erreurs, visibilité de l'état

| Critère | Concept A | Concept B | Concept C |
|---|---|---|---|
| Tâche principale | 8 | 9 | 8 |
| Gestion de la bibliothèque | 9 | 7.5 | 8.5 |
| États et erreurs | 8 | 8.5 | 9 |
| Clarté visuelle | 8.5 | 7.5 | 6 |
| Accessibilité et responsive | 8.5 | 8.5 | 8 |
| Faisabilité | 7 | 7 | 5 |
| **Total** | **49** | **48** | **44.5** |

**Verdict.** A l'emporte de peu sur B. C'est le concept qui répond le mieux à « visualiser et manager l'ensemble des séries » : son modèle mental est le plus cohérent (une série = une carte, et l'aperçu d'ajout est la fiche elle-même), son interface la plus sobre, et la tâche principale y tient en 2 gestes au clavier. Ses faiblesses (file peu visible, accent qui sert aussi à la progression, affiche désaturée ambiguë) se corrigent à faible coût en greffant la pilule ou la barre d'état et la couleur « en cours » de B et C, plus la pellicule de B. B est le meilleur pour lancer et suivre un téléchargement, mais il éclate la gestion et fait coexister deux unités (version dans le flux, série dans la bibliothèque). C offre la meilleure prévention d'erreurs et la meilleure visibilité, mais sa densité d'IDE et son coût de réalisation en JavaScript sans build sont disproportionnés pour un projet personnel où chaque job dure environ une minute. Recommandation : partir d'A, y ajouter le pré-vol du film et la carte des erreurs de C, et faire tester l'affiche désaturée.

**Idées à greffer sur le gagnant :**
- Ajouter à l'en-tête d'A une pilule d'activité en texte (« ↓ 34/62 · 33 s », venant de B), ou une barre d'état fine et permanente (venant de C). Cela comble le point faible d'A, la visibilité de la file, sans créer d'écran File.
- Réserver une couleur à « en cours » (le cyan #4FD1E8 de B), distincte de l'accent, pour les tuiles en cours et le remplissage des affiches. L'accent ne sert plus alors qu'aux actions, aux liens et au focus.
- Remplacer le ruban de points du tiroir Activité par la pellicule de B (un segment par épisode, proportionnel à sa durée, qui ne recule jamais), et la reprendre dans la barre de santé de la fiche.
- Proposer « Regarder l'ép. 1 » dès le premier épisode vérifié (B, S7), sur l'affiche en cours comme dans la fiche.
- Reprendre le pré-vol du film de C (espace disque, nom du fichier, case « Remplacer le film existant » obligatoire) à la place de « Garder les deux », qui exige un ajout au moteur (film.py écrase via ffmpeg -y).
- Adopter la carte des erreurs §3.14 de C comme spécification transverse : pour chaque cas moteur, un lieu, un message et une action.
- Ajouter [Tout réparer] à l'étagère « À traiter », limité aux actions sûres (C) et accompagné d'un récapitulatif chiffré (B). Y ajouter « Ignorer » mémorisé et la distinction « Non demandé » / « En attente » de B.
- Utiliser les puces de version « vérification… » non sélectionnables de B plutôt que le préchargement réseau au survol de « + Espagnol ».
- Ajouter en option la mini-syntaxe `fr 720p 1-10 film` avec puces « Compris : » (C), et Ctrl+Entrée pour « télécharger puis créer le film ».
- Accepter un lien glissé-déposé sur la fenêtre (B et C) et détecter les onglets multiples via BroadcastChannel avec [Utiliser ici] (B).
- Reprendre les règles clavier de C : raccourci affiché sur chaque bouton, Ctrl+K comme raccourci principal plutôt que `/` (AZERTY), F6 pour passer d'une région à l'autre.
- Ajouter le filtre « Libérable (x Go) » et des actions en masse chiffrées qui donnent la raison des blocages (« Créer les films : 3 possibles · 2 bloqués, pourquoi ? », C).
- Regrouper les toasts d'une même vague (C) et supprimer le toast de fin quand la carte l'affiche déjà (B).
- Harmoniser l'action principale entre carte et fiche pour une série complète sans film : ▶ Regarder en principal et « Créer le film » en secondaire, aux deux endroits.

<details><summary>Concept A : forces et faiblesses</summary>

**Forces**
- Le modèle mental est le plus cohérent des trois (Nielsen 4). Une carte correspond à une série partout, les versions sont des onglets, et l'aperçu d'ajout réutilise la fiche en mode « Aperçu ». Il y a donc un seul composant et un seul vocabulaire, que la série soit possédée ou non.
- Il privilégie la reconnaissance plutôt que le rappel (Nielsen 6). Le mur d'affiches 9:16 reste stable même quand le titre est traduit (« Qui Est la Véritable Mme Lafont ? » et « One Night to Forever » ont la même affiche). Les actions de survol sont aussi disponibles au focus et dans le menu « ⋯ ».
- L'interface est la plus sobre (Nielsen 8). Le mur est calme quand tout va bien : pas de barre verte sur les cartes complètes, aucun badge sur les visages, une ligne d'état seulement si l'état sort de la normale, et l'étagère « À traiter » disparaît quand elle est vide.
- La tâche principale se fait en 2 gestes au clavier (Ctrl+V, puis Entrée sur un bouton déjà focalisé). Les cas limites sont traités : série déjà possédée (« Compléter la VF (22 manquants) »), lien d'épisode, disque insuffisant (bouton désactivé avec sa raison) et puce de version désactivée avant le lancement si le moteur répond lang_source: fallback.
- Le film est bien traité. Les contrôles préalables sont visibles avant le clic (épisodes, format, ffmpeg), chaque refus devient un remède classé (« Retélécharger l'épisode 12 en 1080p puis créer » avant le ré-encodage), et la progression s'affiche dans le bouton, sans modale.
- Dans la grille, la légende sélectionne les épisodes sans les filtrer, ce qui garde la géométrie de 10 par rangée. Le champ « 1-10, 28, 50- » est synchronisé dans les deux sens. La suppression présélectionne le choix le moins destructif, est refusée pendant un job et peut être annulée pendant 5 minutes.
- Il est exact sur le moteur. C'est le seul concept qui note que `resolved` n'est jamais écrit, ce que j'ai vérifié : pipeline.py n'écrit que downloading, done et failed, et manifest.py initialise à pending. Sa réconciliation S8 transforme les incohérences en états lisibles (un `downloading` sans job devient « Interrompu », un `done` sans fichier devient « Manquant »).
- C'est le plan le plus réaliste. Chaque ajout au moteur a sa priorité et son mode dégradé, et il n'y a que 3 destinations.

**Faiblesses**
- La file d'attente est la moins visible des trois (Nielsen 1). Le détail est dans un tiroir, et il n'y a ni barre ni écran permanent. Si on enchaîne 5 liens, on ne voit que des cartes « En file · 3e » dispersées sur le mur.
- L'accent #5B9BFF sert à la fois au bouton principal, aux liens et à la progression (bord des tuiles en cours). L'état se confond donc avec l'action. B et C réservent une couleur à part pour « en cours ».
- L'affiche désaturée, censée dire « ça arrive », peut se lire « désactivée » ou « en erreur ». Le risque est reconnu mais pas encore testé.
- L'action principale n'est pas la même partout pour une série complète sans film : « Regarder » sur la carte, « Créer le film » dans la fiche (Nielsen 4).
- La barre sert à la fois à chercher et à ajouter, ce qui rend ambigu un numéro de 11 chiffres. Le raccourci `/` est malcommode sur un clavier AZERTY (Maj+:).
- Le choix [Garder les deux] en cas d'écrasement du film suppose un ajout au moteur : film.py lance ffmpeg avec -y (lignes 235 et 250) et écrase le fichier sans prévenir.
- Survoler « + Espagnol » précharge un aperçu, donc lance des appels réseau que l'utilisateur n'a pas demandés.
- Le clic sur une tuile n'a pas toujours le même effet (regarder, ou cocher dès qu'une sélection existe). C'est un mode implicite qui peut surprendre.

</details>

<details><summary>Concept B : forces et faiblesses</summary>

**Forces**
- C'est la meilleure tâche principale. Le champ de 56 px est focalisé dès l'ouverture, et on peut aussi utiliser Ctrl+V n'importe où, le glisser-déposer ou [Coller]. L'aperçu apparaît là où vivra la carte de téléchargement (permanence d'objet). Il faut 2 interactions pour une série et 2 pour un lot. Le mode express est optionnel, avec un décompte annulable et des exclusions (doublon, mode sonde, disque).
- L'état du système est très visible. La carte vit sous les yeux et sa pellicule a un segment par épisode, proportionnel à sa durée. Elle ne recule jamais et marque les « nouvel essai ». S'y ajoutent une pilule d'en-tête hors du Flux, le titre d'onglet et une seule notification Windows par série.
- Le tableau des états de carte suit les statuts de job du moteur, y compris les états transitoires (« Mise en pause… » jusqu'à 30 s), le hors-ligne avec compte à rebours et le film automatique bloqué.
- « À traiter » couvre toute la collection, avec « Ignorer » mémorisé. Distinguer « Non demandé » de « En attente » évite les fausses alertes sur une sélection partielle voulue, et un épisode indisponible s'affiche sans rouge permanent.
- La couleur « en cours » (cyan) est distincte de l'accent et de la sélection, donc le codage des états reste cohérent.
- « Regarder l'ép. 1 » est proposé pendant le téléchargement. Sur la page Flux, il n'y a pas de toast redondant, et la fiche propose un « Réparer » combiné qui détaille son contenu.
- C'est le concept le plus robuste techniquement. Il détecte les onglets multiples (BroadcastChannel) face à la limite de connexions SSE. La pellicule a un role=progressbar avec un aria-valuetext complet. Les puces de version affichent « vérification… » et restent non sélectionnables tant que le doublage n'est pas confirmé.

**Faiblesses**
- La gestion est éclatée : on répare dans le Flux, on parcourt dans la Bibliothèque et on agit en détail dans la fiche. Depuis l'accueil, supprimer demande 4 interactions et ajouter une langue en demande 3.
- L'unité n'est pas la même d'un écran à l'autre : une carte du flux est une version (bookId + langue), une affiche de la bibliothèque est une série (bookId). Il y a donc deux représentations à synchroniser, un risque que le concept reconnaît lui-même (risque 3).
- Comme une opération dure environ une minute, l'accueil est surtout un historique. Le libellé « Flux » est peu parlant (Nielsen 2) et reste à valider.
- Les codages s'accumulent (pellicule, grille, barre de complétude, colonne « Coup d'œil »). Les segments de pellicule ne font que quelques pixels et ne sont distingués que par la couleur.
- [Tout réparer] n'est pas limité aux actions sûres : il inclut « Harmoniser », qui retélécharge. Seul un récapitulatif est prévu.
- Même avec ses garde-fous, le mode express peut lancer 700 Mo par erreur.

</details>

<details><summary>Concept C : forces et faiblesses</summary>

**Forces**
- L'état du système est le plus visible des trois (Nielsen 1). La barre d'état de 32 px est permanente (jobs actifs, file, épisodes, débit, temps restant, problèmes, disque, ffmpeg), et le dock regroupe File, Problèmes, Journal et Historique. Tout cela sans aucune interaction.
- La carte des erreurs (§3.14) donne pour chaque cas moteur un lieu, un message et une action. C'est la couverture la plus systématique. La langue indisponible est évitée en amont plutôt que signalée après coup.
- La prévention des erreurs est la meilleure. La case « Remplacer le film existant » est obligatoire, ce qui est juste puisque le moteur écrase via ffmpeg -y. Le pré-vol du film vérifie aussi l'espace et le nom. [Tout réparer] se limite aux actions sûres, et dans le dialogue de suppression, [Annuler] a le focus et le bouton de danger est écarté.
- C'est le plus souple (Nielsen 7). La mini-syntaxe de la CLI (`fr 720p 1-10 film`) s'affiche en puces « Compris : », tolère les jetons inconnus et montre la commande équivalente et ses conséquences (nom du film partiel). Ctrl+Entrée lance avec le film.
- La gestion est puissante : vues intelligentes avec compteurs (dont « Libérable 8,4 Go »), vues enregistrées, inspecteur qui agit sans ouvrir la fiche, et actions en masse chiffrées (« Créer les films (3 possibles · 2 bloqués, pourquoi ?) »).
- Le clavier est pensé pour Windows : F6 pour passer d'une région ARIA à l'autre, compatibilité AZERTY (event.key, ni `/` ni chiffres), collisions avec le navigateur évitées, raccourcis affichés sur les boutons et désactivables (WCAG 2.1.4). Aucune redirection forcée, et le premier lancement est calme.

**Faiblesses**
- La charge cognitive est forte (Nielsen 8). Quatre zones, une barre latérale pleine de compteurs et des indicateurs redondants (↓1 et ⚠1 en haut, compteurs à gauche, barre d'état, dock), le tout pour des jobs d'une minute. Le dock est souvent vide.
- Les raccourcis à une touche sur la ligne ciblée (C = Compléter, soit plusieurs centaines de Mo ; F = film ; R = réessayer) peuvent se déclencher par accident, ce qui contredit le reste de sa prévention.
- L'efficacité repose sur la mémoire : mini-syntaxe, séquences G+B/A/P/R, liste dense par défaut qui laisse peu de place aux covers (Nielsen 6).
- La grille n'est pas cohérente : 12 épisodes par ligne dans la fiche à 1440, 10 dans l'inspecteur et à 1280, 6 sur mobile. On perd le repère décimal (épisode 28 = rangée 3, colonne 8) que A et B exploitent.
- C'est le concept le moins faisable : panneaux redimensionnables, inspecteur à 9 contextes, analyseur pour la palette, dock à onglets, vues enregistrées, page Activité, tout en JavaScript sans build. Le réordonnancement de la file (Alt+↑/↓, « Passer en premier ») n'existe pas dans le moteur.
- L'aperçu d'ajout s'affiche dans un inspecteur de 360 px, ce qui est étroit, et il remplace le contexte en cours sauf si on l'a épinglé.

</details>

## Juge 2 — Efficacité des tâches et charge cognitive

| Critère | Concept A | Concept B | Concept C |
|---|---|---|---|
| Tâche principale | 8.5 | 9 | 8 |
| Gestion de la bibliothèque | 8.5 | 7 | 9 |
| États et erreurs | 8.5 | 8.5 | 9 |
| Clarté visuelle | 8.5 | 7.5 | 6 |
| Accessibilité et responsive | 8 | 8 | 7.5 |
| Faisabilité | 7.5 | 6.5 | 5 |
| **Total** | **49.5** | **46.5** | **44.5** |

**Verdict.** A gagne parce qu'elle offre le meilleur compromis entre efficacité réelle et charge cognitive. Elle égale B et C sur la tâche n° 1 (2 interactions au clavier) et bat les deux pour regarder (1) et pour gérer des séries anciennes (fiche à 1 clic). Surtout, c'est le seul concept dont l'accueil répond directement à « manager l'ensemble des séries », avec un modèle mental unique (une carte = une série) qui s'apprend sans effort. B est le plus rapide pour ajouter, réparer et créer le film d'une série qui vient de finir (1 interaction). Mais il paie ce gain de deux représentations d'une même série et d'un accueil qui sert surtout d'historique, ce qui ne convient pas à des jobs d'une minute. C a la gestion en masse et la carte des erreurs les plus riches, mais ses 4 zones, sa douzaine de raccourcis, ses grilles incohérentes (12/10/6 par ligne) et sa faisabilité faible en font de la sur-conception pour un utilisateur seul. Recommandation : construire A en y greffant quatre idées : la pilule d'activité texte, les raccourcis de série et le [Tout réparer] limité aux actions sûres de C, et le « Regarder l'ép. 1 pendant le téléchargement » de B.

**Idées à greffer sur le gagnant :**
- [B, S7] « Regarder pendant que ça arrive » : pendant le téléchargement, ajouter [▶ Regarder l'ép. 1] en action secondaire de la carte et du tiroir d'A. Une tuile devient lisible dès qu'elle est vérifiée.
- [C, barre d'état / B, pilule] Remplacer l'icône Activité d'A (anneau + nombre) par une pilule texte « ↓ 34/62 · ≈ 40 s · 1 en file ». Elle corrige le risque n° 1 d'A (file peu visible lors des ajouts à la chaîne) sans créer de page.
- [C, §5.9] Raccourcis de série sur la carte focalisée du mur (R Réessayer, C Compléter, F Film, L Lire, O Dossier, P Pause), avec navigation aux flèches (role=grid) dans le mur. Créer le film d'une série ancienne passe à 1 au clavier, et la navigation clavier non spécifiée d'A est comblée.
- [C, §5.1] Mini-syntaxe optionnelle dans la barre unique d'A (`<lien> fr 720p 1-10 film`), avec les puces « Compris : … » et la commande CLI équivalente. Ctrl+Entrée = télécharger + film, Maj+Entrée = options.
- [B, S5 + C, §3.8] Étagère « À traiter » avec « Ignorer » mémorisé par ligne, « Réessayer plus tard » sans rouge permanent pour les épisodes indisponibles, et un [Tout réparer] limité aux actions sûres (réessayer, reprendre), sans « Compléter ». Réparer toute la collection passe de 3 à 1.
- [B, 6.2] Couleur « en cours » dédiée (cyan #4FD1E8, ou le violet de C), distincte de l'accent bleu #5B9BFF, pour que la progression ne se confonde plus avec le bouton principal et le focus.
- [C, §3.2] Filtre « Libérable (x Go) » et actions en masse chiffrées avec leurs blocages (« Créer les films · 3 possibles · 2 bloqués, pourquoi ? »).
- [C, §3.14] Livrer la carte des erreurs (cas moteur → lieu → message → action) comme spécification de référence pour les états d'A.
- [C, §3.5] Pré-vol du film complété par l'espace disque et une case « Remplacer le film existant », parce que le moteur écrase sans prévenir. plan_film() fournit déjà le calcul sans ffmpeg.
- [B, É0] Détection « déjà ouvert dans un autre onglet » (BroadcastChannel) et [Utiliser ici], à cause de la limite de connexions SSE par hôte.
- [B, 2.3] Point de rupture explicite 600-1023 px pour Windows Snap en demi-écran, et réglage « Page d'accueil : Bibliothèque / Activité ».
- [C, §3.12] Premier lancement « au calme », et règle générale : une zone dont les données moteur manquent reste masquée plutôt que fausse.
- [C] Garder une grille décimale stricte partout : 10 par ligne sur desktop, 5 sur mobile.

<details><summary>Concept A : forces et faiblesses</summary>

**Forces**
- Comptes honnêtes et vérifiables. URL → tout télécharger : 2 au clavier (Ctrl+V n'importe où, Entrée sur le bouton déjà focalisé), 3 à la souris. Regarder : 1 (bouton de la carte « Reprendre · ép. 14 »). Épisode précis : 2 (affiche, puis tuile). Réparer les échecs d'une série : 1 (étagère « À traiter » ou carte [Réessayer (2)], visibles sur l'accueil).
- Charge cognitive la plus faible des trois : 3 destinations, un seul champ pour chercher, ajouter et commander, une carte par série, une seule action principale par carte et par fiche. Les repères viennent de Plex et de dramafren, un power user est opérationnel sans rien apprendre.
- Le mur d'affiches colle au problème réel des titres multilingues : on reconnaît « Mme Lafont » à son visage plus vite qu'à ses 3 titres traduits. La recherche porte sur tous les titres et affiche « trouvé dans le titre VF ».
- Adapté à la durée réelle des opérations (40 s à 1 min 40, film en 6 s) : pas d'écran File vide en permanence. La progression se lit sur l'affiche (S2, clip-path sur --p), dans le titre d'onglet et sur le favicon.
- Gestion solide : filtres à compteurs (puces à 0 masquées), vue Liste dense triable par taille, sélection multiple chiffrée (« Libérer l'espace (garder les films) »), onglets de version avec « + Espagnol », section Stockage qui compte les .part orphelins.
- S8 « le mur reflète le disque » : l'hypothèse de départ est juste (pipeline.py n'écrit que pending, downloading, done et failed ; aucun statut resolved). Les incohérences deviennent des états lisibles : downloading sans job → Interrompu, done sans fichier → Manquant, failed avec fichier présent → à confirmer.
- Film sans impasse : contrôles préalables visibles avant le clic, que plan_film() permet déjà de calculer sans ffmpeg. Chaque refus a son remède, le recommandé en premier. Progression affichée dans le bouton.
- La surface est la plus réduite des trois (mur, fiche, tiroir, théâtre, réglages) : c'est le concept le plus réalisable en JS sans build servi par la stdlib.

**Faiblesses**
- Créer le film d'une série déjà complète demande 2 interactions depuis le mur (⋯ puis Créer le film), car l'action principale d'une carte complète est « Regarder ». La phrase « Sur la carte, la lecture l'emporte » contredit d'ailleurs le tableau de priorité, où Pause, Réessayer et Compléter passent avant Regarder.
- Réessayer TOUS les échecs de la collection coûte 3 interactions (palette ou filtre + Ctrl+A + action). Le Flux B fait la même chose en 1.
- La file est reléguée dans un tiroir. Un ajout de 5 liens à la chaîne ne se suit que par des cartes « En file · 2e » dispersées ou en ouvrant le tiroir (risque n° 1 reconnu).
- L'accent bleu sert à la fois au bouton principal, au focus et à la progression (bord accent des tuiles en cours, --p) : l'état « en cours » se confond avec l'appel à l'action. B et C réservent chacun une couleur distincte à l'état actif.
- Deux surfaces d'aperçu à maintenir : le panneau sous l'en-tête (§3.3) et le mode Aperçu de la fiche (§3.4). « Choisir les épisodes » fait passer de l'un à l'autre, et le parcours réel compte 5 interactions (Ctrl+V, Choisir, champ Plages, saisie, Télécharger), pas 4.
- La grille change de mode : dès qu'une sélection existe, un clic coche au lieu de lire. C'est une convention Gmail, mais c'est un mode caché.
- La navigation clavier dans le mur n'est pas spécifiée : le Tab traverse 50 cartes ou plus, dont chacune a plusieurs éléments focalisables, sans role=grid ni flèches, alors que C le prévoit pour sa liste.
- L'affiche désaturée risque d'être lue comme « désactivée » (risque n° 6). Le raccourci « / » est malcommode en AZERTY (Maj+:).
- L'étagère « À traiter » ne propose pas d'« Ignorer » : un épisode indisponible pour de bon y reste comme un reproche permanent.

</details>

<details><summary>Concept B : forces et faiblesses</summary>

**Forces**
- Le meilleur sur la tâche n° 1. Le champ est focalisé dès l'ouverture : Ctrl+V puis Entrée = 2 au clavier, et aussi 2 à la souris grâce au bouton [Coller] permanent (+1 pour l'autorisation du presse-papiers la première fois). Le Collage express optionnel descend à 1, avec des garde-fous : jamais pour un doublon, une sonde ou un disque insuffisant, et un décompte de 3 s annulable.
- Réparer est imbattable depuis l'accueil : « À traiter » couvre toute la bibliothèque, 1 interaction par problème, et [Tout réparer] règle tout en 1 (+ récapitulatif). « Ignorer » est mémorisé par ligne, et une sélection partielle voulue ne crée jamais d'alerte.
- Créer le film d'une série qui vient de finir : 1 interaction, c'est l'action principale de la carte « Terminé ».
- S7 « Regarder pendant que ça arrive » : [Regarder l'ép. 1] apparaît sur la carte dès le premier épisode vérifié. C'est la meilleure réponse au fait qu'une série arrive en 1 min.
- Couleur « en cours » (cyan) distincte de l'accent : progression et sélection ne se confondent pas.
- États de carte adossés à de vrais statuts de job : queued, running avec ses phases, pausing, paused, hors ligne, interrupted, cancelled (« Arrêté · 34 épisodes gardés »), film. Le cas « Autre onglet ouvert » est traité (BroadcastChannel, limite de connexions SSE).
- Une largeur intermédiaire est pensée pour Windows Snap en demi-écran (600-1023 px). Le réglage « Page d'accueil : Flux / Bibliothèque » laisse une porte de sortie.

**Faiblesses**
- Deux unités pour un même objet : le flux affiche une carte par version (VO et VF = 2 cartes), la Bibliothèque une carte par série. Deux représentations peuvent diverger (risque n° 3 reconnu) et augmentent la charge cognitive.
- L'accueil sert surtout d'historique, puisque les jobs durent environ 1 min (risque n° 2). La collection est à un clic, alors que « gérer l'ensemble des séries » est une demande explicite.
- Les tâches sur les séries anciennes coûtent plus cher. Regarder un épisode précis : 3 (Bibliothèque, affiche → fiche, tuile). Créer le film d'une ancienne série : 3 (ou Ctrl+K + saisie + Entrée, puis l'action). « Continuer à regarder » en 1 clic n'existe qu'au-delà de 1366 px (colonne Coup d'œil).
- Retrouver une série est annoncé « 2 + saisie », mais cela fait bien 3 interactions (Ctrl+K, saisie, Entrée), comme A et C.
- La pellicule proportionnelle à la durée n'est pas lisible au même rythme que le texte : à « 34/62 vérifiés », la barre peut montrer 45 % ou 60 % selon les durées. Deux mesures d'avancement se contredisent visuellement.
- [Tout réparer] inclut « Compléter » : cela peut lancer des centaines de Mo d'un clic. C limite ce bouton aux actions sûres.
- Plus de surfaces à coder que A : Flux et Bibliothèque en parallèle, pilule, aperçu en fenêtre flottante hors Flux, Coup d'œil, historique groupé par jour, journal traduit par carte, historique de jobs rattaché à chaque version.
- Le libellé « Flux » n'est pas validé (risque n° 11) et reste peu évocateur pour un francophone non technicien.

</details>

<details><summary>Concept C : forces et faiblesses</summary>

**Forces**
- La gestion la plus puissante. Vues intelligentes avec compteurs, dont « Libérable 8,4 Go » et « Non vérifiées ». Vues enregistrées. Liste dense triable. Actions en masse chiffrées (« Créer les films (3 possibles · 2 bloqués, pourquoi ?) », « Supprimer les épisodes, garder les films · libère 2,1 Go »). Page « À traiter » groupée par type, chaque groupe avec son action, et [Tout réparer] limité aux actions sûres.
- La mini-syntaxe de l'omnibar (`fr 720p 1-10 film`), avec les puces « Compris : … », la commande CLI équivalente et ses conséquences (nom du film partiel) : parfait pour un utilisateur qui vient de la CLI. Ctrl+Entrée lance le téléchargement avec le film, Maj+Entrée ouvre les options.
- Supervision sans effort : la barre d'état permanente (« 34/124 ép. · 12,4 Mo/s · ~1 min 50 · ⚠ 1 · C: 182 Go · ffmpeg ✓ ») donne 0 interaction pour suivre, même en lot.
- La carte des erreurs (§3.14) est la plus systématique des trois : chaque cas du moteur a son lieu, son message et son action (chemin CDN erroné, « 1 min 12 au lieu de 2 min 05 », erreurs répétées, suppression partielle « 60 sur 62 », film hors bibliothèque avec -f).
- Hygiène clavier Windows exemplaire : F6 entre zones, Maj+F10, event.key compatible AZERTY, collisions avec le navigateur évitées (Ctrl+J), raccourcis à une touche désactivables (WCAG 2.1.4), raccourci affiché sur chaque bouton.
- Le pré-vol du film inclut l'espace disque et une case explicite « Remplacer le film existant », parce que le moteur écrase sans prévenir.

**Faiblesses**
- Comptes optimistes. (e) « 1 : L sur la ligne ciblée » suppose que la ligne est déjà ciblée ; en réalité il faut 2 interactions (sélection + L, ou clic sur la ligne + bouton de l'inspecteur). Avec options, (a) annonce 3, mais Ctrl+K, collage, saisie des jetons et Entrée font 4. Réparer les échecs d'une série prend 2 interactions (sélection + R), contre 1 dans A et B.
- Charge cognitive la plus lourde : 4 zones, un inspecteur à 9 contextes, l'épinglage, un dock à 4 onglets, une page Activité, une page À traiter, une palette, des séquences G, une douzaine de raccourcis à une touche (R C F L O P V X J K T I). Pour un seul utilisateur dont les jobs durent 1 min, c'est de la sur-conception (risques n° 1, 4 et 11 reconnus).
- Grilles d'épisodes incohérentes : 12 par ligne dans la fiche (l'épisode 28 est en rangée 3, colonne 4, la lecture décimale est perdue), 10 dans l'inspecteur, 8 en tablette, 6 sur mobile. A et B gardent la dizaine partout.
- Mini-covers de 28×50 dans la liste par défaut : le repère visuel le plus fiable face aux titres multilingues est sacrifié. L'aperçu d'ajout est comprimé dans un inspecteur de 360 px.
- Dock souvent vide et inspecteur en superposition sous 1180 px : à 1280 px, barre latérale, centre et inspecteur se disputent la place.
- Faisabilité la plus faible en JS sans build : zones redimensionnables, analyseur de mini-syntaxe, vues enregistrées, réordonnancement de la file, sélection au lasso, 4 points de rupture qui changent le comportement des zones, et un inspecteur qui change de contenu à chaque déplacement aux flèches, ce qui demande des annonces soignées pour les lecteurs d'écran.

</details>

## Juge 3 — Hiérarchie visuelle, accessibilité, responsive, faisabilité

| Critère | Concept A | Concept B | Concept C |
|---|---|---|---|
| Tâche principale | 8.5 | 9 | 8 |
| Gestion de la bibliothèque | 8.5 | 7 | 9 |
| États et erreurs | 8.5 | 8.5 | 9 |
| Clarté visuelle | 8.5 | 7 | 6 |
| Accessibilité et responsive | 8 | 7 | 7.5 |
| Faisabilité | 7.5 | 7 | 5 |
| **Total** | **49.5** | **45.5** | **45** |

**Verdict.** Le concept A l'emporte. C'est le seul qui fait des covers 9:16 le cœur de la hiérarchie visuelle tout en répondant directement à la demande de « manager l'ensemble des séries ». C'est aussi le moins coûteux à construire avec la stack recommandée (serveur stdlib, SSE, JS sans build), grâce à ses composants partagés : la fiche sert aussi d'aperçu, la grille décimale sert partout, et l'affiche se colore avec un simple clip-path. B offre le meilleur parcours coller → télécharger et l'idée clé « regarder pendant que ça arrive ». Mais il éclate chaque série en trois représentations, réduit les covers à 54×96, et sa pellicule de 8 px ne distingue vert et cyan que par la teinte. C est le plus complet en erreurs, en clavier et en actions en masse, mais son chrome d'IDE (liste dense à covers de 28×50, grille de 12 par ligne, cinq zones) va contre le contenu et c'est de loin le plus lourd à coder en JS pur. Recommandation : construire A, lui greffer la pilule d'activité et le visionnage pendant le téléchargement de B, la carte des erreurs, les vues « Libérable », le pré-vol étendu et l'hygiène clavier de C, et corriger ses points faibles d'accessibilité (contraste des remplissages de tuiles, couleur « en cours » distincte de l'accent, aperçu sans ambiguïté de focus, action principale visible sur mobile).

**Idées à greffer sur le gagnant :**
- Depuis B (S7) : [▶ Regarder l'ép. 1] dès le premier épisode vérifié, sur la carte en cours, dans la fiche et dans le tiroir. Dans le théâtre, « encore en téléchargement (45 %) ».
- Depuis B (É0, pilule) ou C (barre d'état) : remplacer l'anneau seul de l'icône Activité par une pilule texte persistante « ↓ 34/62 · 40 s · 2 en file » dans l'en-tête. Cela corrige le risque n° 1 de A (file trop en retrait) sans créer de page File.
- Depuis B et C : une couleur « en cours » dédiée, distincte de l'accent et du focus. Pour éviter l'égalité de luminance (cyan contre vert à 1,04:1 chez B, violet contre bleu à 1,02:1 chez C), porter l'état par un motif ou une icône ↓ en plus de la teinte. Relever aussi tile-progress et tile-done au-dessus de 3:1 face au fond, ou compter explicitement sur le bord et l'icône.
- Depuis C (§3.14) : la carte des erreurs (cas moteur → lieu → message → action), adoptée comme contrat d'implémentation et comme jeu de tests des états.
- Depuis C : les vues intelligentes « Libérable (x Go) » et « Non vérifiées (mode sonde) » en puces de filtre du mur, et des actions en masse toujours chiffrées (« Supprimer les épisodes, garder les films · libère 2,1 Go »).
- Depuis C : pré-vol du film étendu à l'espace disque requis et au nom, avec une case « Remplacer le film existant » obligatoire (le moteur écrase sans prévenir).
- Depuis C (§5.9) : l'hygiène clavier Windows, soit F6 entre régions ARIA, event.key compatible AZERTY, pas de Ctrl+J, raccourci affiché sur les boutons, Alt+↑/↓ et « Passer en premier » pour réordonner la file sans glisser-déposer. Laisser en revanche les raccourcis d'action à une touche désactivés par défaut.
- Depuis C (§5.1), en V1.1 : la mini-syntaxe « fr 720p 1-10 film » dans la barre unique de A, avec les puces « Compris : … » et la commande CLI équivalente, en option pour utilisateur avancé et non bloquante.
- Depuis B : le glisser-déposer d'un lien sur la fenêtre. Pour le collage de plusieurs lignes, le message par ligne « La ligne 2 n'est pas un lien DramaBox ».
- Depuis B (S5) : « Ignorer » mémorisé sur chaque élément de « À traiter », aucune alerte pour une sélection partielle volontaire (stocker les options demandées dans le manifest), et « Réessayer plus tard » sans rouge permanent pour les épisodes indisponibles. [Tout réparer] limité aux actions sûres, avec un récapitulatif chiffré (C).
- Depuis B : détection de plusieurs onglets (BroadcastChannel + [Utiliser ici]) contre la limite de 6 connexions SSE. Notification Windows seulement si l'onglet est masqué, et pas de toast en doublon sur la vue qui affiche déjà l'information.
- Depuis B : ajouter un palier de mise en page pour Windows Snap (600 à 1023 px, environ 720 px) au responsive de A.
- Corrections propres à A, inspirées des autres concepts : sur mobile, une seule ligne d'état et l'action principale visible sous l'affiche (pas au survol) ; aperçu en vraie <dialog> modale, ou panneau sans voile, avec gestion du focus explicite ; aperçu « + Espagnol » chargé au clic ou après 300 ms de focus plutôt qu'au survol ; mode de sélection de la grille signalé par une barre « n sélectionnés · Échap pour quitter ».

<details><summary>Concept A : forces et faiblesses</summary>

**Forces**
- Adéquation au contenu la plus juste. Le mur d'affiches 9:16 fait 7 colonnes d'environ 180 px à 1440, soit la limite de netteté d'une cover native de 360 px à 200 %. Aucun badge en haut de l'affiche, sur les visages. Le mur reste calme quand tout va bien : pas de barre verte sur les cartes complètes. La hiérarchie est limpide : les covers apportent la couleur, l'accent est réservé à l'action principale.
- Vérifié dans le code : « resolved » n'est jamais écrit dans le manifest (pipeline.py n'écrit que pending, downloading, done et failed), et A est le seul à le relever. Il en tire aussi une réconciliation honnête (S8) : « downloading » sans job devient Interrompu, « done » sans fichier devient Manquant.
- « Un lien collé devient une fiche » : le mode Aperçu réutilise la fiche série (tuiles en pointillés présélectionnées, bouton qui suit la sélection). On a moins de composants distincts qu'en B et C, et « déjà possédée » ne crée pas de doublon.
- Grille décimale de 10 par ligne avec étiquettes de rangée « 1–10, 11–20… » : l'épisode 28 se trouve en rangée 3, colonne 8, et c'est la continuité directe du « Ep 1 … Ep 62 » de dramafren. La légende sert de sélecteur sans filtrer, ce qui garde la géométrie de la grille. Le champ « Plages » est synchronisé dans les deux sens et tolère « – ».
- L'étagère « À traiter » donne une carte par problème avec son propre bouton de réparation, et elle disparaît quand elle est vide. Sur les cartes, la priorité des actions est claire : la lecture sur la carte, la gestion dans la fiche.
- Accessibilité soignée et précise : role=grid avec un seul arrêt de tabulation, noms accessibles complets (« Épisode 14, 2 min 05… »), combobox avec aria-describedby, une seule région status limitée à 25/50/75 % et à 10 s d'écart, raccourcis à une touche désactivables (2.1.4), forced-colors, reduced-motion. La marge basse de 96 px pour que toasts et barre de sélection ne masquent pas le dernier rang répond à la règle 2.4.11 de WCAG 2.2 (focus non masqué).
- États et erreurs très complets et rédigés en langage courant. La recherche est honnête (« La recherche par titre sur DramaBox n'existe pas encore : colle le lien »). Les langues « titre traduit seulement » sont désactivées avant tout lancement. Dans le dialogue Supprimer, l'option la moins destructive est présélectionnée, avec annulation possible pendant 5 minutes.
- Faisabilité : l'affiche qui se colore tient en deux couches et un clip-path piloté par --p, et les tuiles sont pilotées par attributs et variables CSS. C'est très bon marché en JS pur sans build avec SSE. Chaque ajout au moteur a un mode dégradé documenté.

**Faiblesses**
- La file d'attente est trop en retrait (risque 1, assumé). L'icône Activité n'affiche qu'un anneau et un nombre, sans texte « ↓ 34/62 · 40 s » dans l'en-tête. Quand on enchaîne 5 liens, on ne voit la file qu'en ouvrant le tiroir.
- Les cartes sont surchargées à 390 px : sur une affiche de 112×199, on empile désaturation, remplissage clip-path, ligne d'état « ↓ 34/62 · ≈ 40 s », puces de version, puce Film, barre de complétude et « ⋯ ». Le texte sera tronqué, et l'action principale de la carte (visible au survol ou au focus) n'est pas accessible en un appui sur mobile.
- Remplissages de tuiles quasi invisibles : tile-progress #1D3E78, tile-done #123524 et tile-fail #3A1620 ne contrastent qu'à 1,8, 1,4 et 1,2:1 avec le fond #0B1220. Le niveau --p d'une tuile en cours n'est donc pas perceptible (1.4.11). Seuls les bords et les icônes portent l'état, et le pourcentage n'apparaît qu'en infobulle.
- L'accent sert à la fois à l'action principale, au lien, au focus et à la progression (bord « en cours » = accent, anneau #8FC1FF à 1,5:1 de l'accent). Une tuile en cours et une tuile focalisée se ressemblent. B et C séparent mieux la couleur « en cours ».
- Mode caché dans la grille : « dès qu'une sélection existe, le clic simple coche ». Le même geste regarde ou coche selon un état peu visible, ce qui expose à des erreurs de mode.
- L'aperçu est ambigu : « pas une modale », mais le mur est assombri à 60 %. Le comportement du focus et de l'arrière-plan (inert ou non) n'est pas défini, ce qui est un piège pour le clavier et les lecteurs d'écran.
- Charger l'aperçu au survol de « + Espagnol » lance des requêtes réseau (site officiel, get_video) à chaque passage de souris. C'est un risque de blocage par la source, que C signale ailleurs pour la concurrence.
- La désaturation « en file / aperçu » peut se lire comme « désactivé » (risque 6, assumé). La barre à double sens, chercher ou coller, reste ambiguë pour un n° à 11 chiffres.

</details>

<details><summary>Concept B : forces et faiblesses</summary>

**Forces**
- Meilleur parcours principal. Le champ est focalisé dès l'ouverture : Ctrl+V puis Entrée, soit 2 interactions, et 2 aussi à la souris grâce à [Coller]. On peut glisser-déposer un lien sur la fenêtre. Le Collage express (1 geste) est désactivé par défaut, avec un décompte de 3 s annulable par Échap, et exclu pour les doublons, le mode sonde et le disque insuffisant.
- S7 « Regarder pendant que ça arrive » : [Regarder l'ép. 1] apparaît dès que l'épisode 1 est vérifié. Dans le lecteur, « encore en téléchargement, 45 % ». C'est l'idée la plus juste face à un téléchargement d'une minute.
- Couleur « en cours » séparée de l'accent (active cyan #4FD1E8, 10,4:1) : le statut ne se confond pas avec la sélection ni avec le bouton principal.
- « À traiter » bien pensé : [Tout réparer] avec récapitulatif chiffré, « Ignorer » mémorisé, aucune alerte pour une sélection partielle volontaire, « Réessayer plus tard » sans rouge permanent pour les épisodes indisponibles.
- Tableau des états de carte aligné sur les statuts de job (queued, running avec ses phases, pausing, paused, interrupted, cancelled, états du film) : le contrat front/moteur est explicite. Tableau des états globaux (reprise, hors ligne avec 5/15/30/60 s, disque plein).
- Responsive pensé pour Windows Snap (600 à 1023 px, environ 720 px) en plus de 1440 et 390. Barre du bas à 3 cibles de 44 px et plus. Sur mobile, on masque plutôt que de désactiver ce qui n'a pas de sens à distance.
- Lucidité technique : limite de 6 connexions SSE par hôte, gérée par BroadcastChannel et [Utiliser ici]. Notification Windows seulement si l'onglet est masqué, et pas de toast sur la page Flux, qui montre déjà l'information.

**Faiblesses**
- La gestion de la collection, demandée explicitement par l'utilisateur, passe au second plan. Une même série existe sous trois formes (carte de flux, affiche de bibliothèque, fiche), qui peuvent diverger (risque 3). Et l'accueil n'est souvent que de l'historique, puisqu'une opération dure environ 1 min (risque 2).
- Les covers 9:16 sont reléguées à 54×96 dans une colonne de flux de 760 px. Sur l'accueil, le contenu visuel (visages, affiches) sert à peine, alors que c'est le meilleur repère pour des titres traduits différemment.
- La pellicule de 8 px est illisible aux cas réels : 62 segments proportionnels à la durée sur environ 600 px, ce qui donne à peu près 5 px pour un épisode de 50 s. Le « ! » et les hachures n'y tiennent pas, et un échec sur un épisode court devient le plus petit signal alors que c'est le plus important.
- Vert « vérifié » #3DD68C et cyan « en cours » #4FD1E8 ont la même luminance (1,04:1). Dans la pellicule, sans place pour une icône, ils ne se distinguent que par la teinte, difficile pour les daltoniens (1.4.1).
- Les aperçus « poussent les sections vers le bas » : décalage de mise en page, et « À traiter » descend sous la ligne de flottaison au moment où l'on colle plusieurs liens.
- Deux formes d'aperçu (en place dans le Flux, dans une fenêtre flottante ailleurs) et une pilule masquée sur le Flux : plus de surfaces à coder et à tester en JS pur que A. La 2.4.11 (focus masqué par l'action collée en bas et la barre du bas sur mobile) n'est pas traitée.
- Le libellé « Flux » n'est pas validé (risque 11) et le modèle « gestionnaire de téléchargements » pousse vers la densité, alors que l'objectif de l'utilisateur est une collection.

</details>

<details><summary>Concept C : forces et faiblesses</summary>

**Forces**
- La carte des erreurs (§3.14) est la meilleure des trois : pour chaque cas moteur, elle dit où le message apparaît, ce qu'il dit et quelle action il propose (mauvais épisode CDN, durée non conforme, lien expiré, langue indisponible « évitée »). C'est directement utilisable comme contrat d'implémentation.
- Gestion de collection la plus puissante. Vues intelligentes avec compteurs, dont « Libérable 8,4 Go » et « Non vérifiées ». Inspecteur contextuel pour agir sans naviguer. Actions en masse chiffrées (« Supprimer les épisodes, garder les films · libère 2,1 Go »). « À traiter » en page, avec une action par groupe et un [Tout réparer] limité aux actions sûres.
- Hygiène clavier exemplaire pour Windows : F6 et Maj+F6 entre régions ARIA nommées, event.key pour l'AZERTY, collisions avec le navigateur évitées (Ctrl+J), raccourci affiché sur chaque bouton, rien qui ne soit accessible que par la palette, réordonnancement par Alt+↑/↓ et « Passer en premier » sans glisser-déposer obligatoire (2.5.7).
- Pré-vol du film le plus complet : épisodes, format, ffmpeg, espace (« 717 Mo requis ») et nom, avec une case « Remplacer » obligatoire puisque le moteur écrase sans prévenir.
- La mini-syntaxe de l'omnibar (« fr 720p 1-10 film », puces « Compris : … », commande équivalente, conséquence « film partiel … (épisodes 1-10).mp4 ») fait un bon pont avec la CLI pour quelqu'un qui s'est lancé un défi.
- Tableau responsive par zone et par palier, avec les calculs (6×52 + 5×8 = 352 px pour 358 px utiles). Démarrage au calme (dock replié, inspecteur masqué) pour limiter l'effet IDE au premier lancement.

**Faiblesses**
- Mauvaise adéquation au contenu par défaut : liste dense avec des covers de 28×50, et affiches ramenées à 4 colonnes quand l'inspecteur est ouvert. Le 9:16 n'est mis en valeur que dans l'inspecteur (180×320). Cinq zones de chrome (barre, barre latérale, inspecteur, dock, barre d'état) pour une opération d'une minute : la hiérarchie visuelle se dilue.
- La grille de la fiche à 12 par ligne casse le repère décimal (l'épisode 28 est en rangée 3, colonne 4). Elle est incohérente avec la mini-grille de l'inspecteur (10 par ligne) et avec le mobile (6 par ligne), et s'éloigne du « Ep 1 … Ep 62 » de dramafren.
- Le violet « en cours » #A78BFA et l'accent de sélection #5B9BFF ont la même luminance (1,02:1). Malgré la règle affichée, sélection et progression ne diffèrent que par une teinte voisine. Dans le ruban, l'échec « plus haut d'un pixel avec une encoche » n'est pas un signal perceptible.
- Raccourcis d'action à une touche actifs par défaut sur la ligne ciblée (R, C, F, P) : une frappe égarée lance un réessai ou un complément de plusieurs centaines de Mo. C'est conforme à 2.1.4 grâce à l'option de désactivation, mais risqué par défaut.
- Faisabilité la plus faible avec la stack recommandée (serveur stdlib, SSE, JS sans build) : gestionnaire de panneaux redimensionnables, machine d'état de l'inspecteur avec épinglage et priorité à l'aperçu, analyseur de mini-syntaxe, séquences G, dock à 4 onglets, vues enregistrées, page Activité en tableau. C'est beaucoup de code sur mesure, et donc de bugs potentiels.
- À 1280 px, barre latérale, centre (640 px minimum) et inspecteur se disputent la place, et l'inspecteur passe en superposition sous 1180 px. Sur mobile, le concept se réduit à une « télécommande » qui perd son modèle à quatre zones.
- Sur-conception pour un seul utilisateur, avec une cinquantaine de séries et des jobs d'une minute : le dock est souvent vide (risque 4) et la découvrabilité de la palette et des raccourcis dépend d'indices (risque 5).

</details>
