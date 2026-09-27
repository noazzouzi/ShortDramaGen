# Benchmark UX : frontend ShortDramaGen

> **Objectif.** Relever dans des produits voisins les patterns à reprendre ou à éviter pour une interface qui (1) prend une URL, (2) télécharge tous les épisodes et (3) gère la bibliothèque de séries.
>
> **Légende des sources.** **[V]** = vérifié en ligne pendant cette recherche (sept. 2026). **[C]** = connaissance du produit, non revérifiée. **[C?]** = détail de mémoire à confirmer avant de s'en réclamer. Les sources sur les applis de short drama (ReelShort, DramaBox) sont surtout des blogs d'agences de développement : elles sont fiables sur les grands principes, moins sur les détails.

---

## 0. Huit constats qui cadrent le benchmark

1. **Nos opérations sont courtes.** Une série se télécharge en 40 s à 1 min 40, un film se crée en 6 s. On n'est pas qBittorrent, qui gère des heures de transfert et des centaines de torrents. Il faut donc une file de téléchargements légère : l'utilisateur lance, voit avancer, c'est fini. On privilégie le retour d'information dans la page et la notification de fin, pas les modales ni les réglages de file.
2. **Le volume est petit mais détaillé** : quelques dizaines de séries de ~60 épisodes chacune. L'unité visuelle est donc la **grille de 62 cases**, pas une table de 62 lignes.
3. **Il y a deux intentions : ajouter et gérer.** Les *arr séparent « Add New » et « Series », les médiathèques séparent « Accueil » et « Bibliothèque ». Chez nous, l'ajout doit être possible **depuis n'importe quelle page** (champ global) et la bibliothèque sert de page d'accueil.
4. **Les covers sont en portrait 9:16 et petites (360×640).** Le mur d'affiches façon Plex fonctionne. Le grand bandeau paysage façon Plex ou Infuse, lui, donnerait une image floue ou pixellisée. On affiche donc la cover nette à sa taille native, sur un fond fait de la même cover floutée.
5. **Une même série existe en plusieurs langues, avec des titres différents.** « One Night to Forever » s'appelle « Qui Est la Véritable Mme Lafont ? » en VF. Il faut donc un modèle « une série, plusieurs versions » (comme Plex ou Jellyfin) et une recherche sur tous les titres.
6. **Les erreurs sont connues et nommées (11 cas).** Chacune doit avoir un message et une action. Plusieurs peuvent être signalées **avant** le lancement, dès l'aperçu.
7. **L'utilisateur vient de dramafren** (thème bleu nuit, grille « Ep 1 … Ep 62 », onglet « Paste URL », sélecteur de langue + GO). On garde ces repères familiers et on retire ce qui n'aurait pas d'équivalent chez nous, comme la recherche en ligne par titre.
8. **Un seul utilisateur, francophone, sous Windows, qui se lance un défi.** Donc : densité modérée, français partout (« Mo », « 1 h 32 »), habitudes Windows (Explorateur, Ctrl+V, pas de ⌘), et un accès à la technique (commande CLI équivalente, manifest) sans l'imposer.

---

## 1. Panorama des références

| Référence | Problème résolu | À prendre | À éviter |
|---|---|---|---|
| **Sonarr / Radarr** | Suivre des séries et télécharger les épisodes manquants | Ajout en 3 temps (recherche, aperçu, options), barre de complétude colorée sous l'affiche, file d'activité avec compteur, filtre « Wanted › Missing », messages de santé système, éditeur de masse | Calendrier, suivi série par série (« monitored »), profils qualité avec seuils, jargon |
| **qBittorrent WebUI / VueTorrent** | Piloter beaucoup de transferts longs | Filtres de statut avec compteurs [V], espace disque libre visible, Maj+clic pour sélectionner une plage [V] | Tables à 15 colonnes, menus contextuels à 20 entrées, métriques réseau (pairs, ratio) |
| **JDownloader 2** | Capturer des liens en vrac | Écoute du presse-papier [V], vérification que le lien est valide avant téléchargement [V], regroupement en paquets | Deux zones séparées (LinkGrabber / Téléchargements) où les liens restent bloqués, interface surchargée, surveillance du presse-papier jugée intrusive [V] |
| **Pinchflat** | Archiver des chaînes YouTube via yt-dlp | Séparer « quoi » (sources) et « comment » (profils média) [V] | Profils nommés et indexation périodique : trop lourd pour nous |
| **Tube Archivist** | File YouTube auto-hébergée | « Télécharger maintenant » (priorité), « Ignorer », filtres par erreur + actions en masse sur le résultat filtré, ajout d'une URL par ligne, pas de doublon ajouté [V] | Une vidéo en échec n'est jamais réessayée [V] |
| **Parabolic** | Interface graphique pour yt-dlp | Champ pré-rempli depuis le presse-papier, étape « Valider » qui récupère titre, durée et formats, détection des playlists [V] | Une boîte de dialogue par téléchargement |
| **Stacher** | Interface graphique pour yt-dlp sous Windows | Préréglages (meilleure qualité / équilibré / petit fichier), 3 téléchargements en parallèle par défaut, Ctrl+Entrée pour voir la commande équivalente [V] | Exposer toutes les options de yt-dlp |
| **Plex / Jellyfin / Infuse** | Parcourir et regarder une médiathèque | Mur d'affiches, fiche détaillée, « Continuer » / « Next Up » [V], versions multiples d'un même titre | Grand bandeau paysage (nos covers sont en portrait et basse résolution) |
| **DramaBox / ReelShort / ShortMax** | Regarder des micro-séries verticales | Covers 9:16, grille d'épisodes numérotés, enchaînement automatique, lecteur vertical plein écran [V] | Cadenas, pièces, mur de paiement ; flux vidéo en lecture automatique comme page d'accueil |
| **dramafren** (existant) | Obtenir les épisodes | Repères : thème bleu nuit, « Paste URL », langue + GO, grille « Ep n » | Onglet « Search Title » (le moteur ne cherche pas par titre en ligne) |
| **Raindrop / Pocket / Notion** | Coller un lien et obtenir une carte | Récupération automatique du titre, de la description et de la vignette [V], menu au collage (Notion) [C] | — |
| **Linear / VS Code / Raycast / GitHub** | Accès rapide aux actions | Palette de commandes Ctrl+K [C] | Palette comme seul accès à une fonction |
| **Gmail / Google Drive / Chrome** | Retours sur les actions et opérations en cours | « Annuler » après une action destructive, panneau d'envoi repliable en bas à droite, bulle de téléchargements [C] | — |

---

## 2. Patterns détaillés

Chaque pattern suit le même format : **Quoi**, **Où**, **Pourquoi ça marche**, **Chez nous**, **Pièges**.

### A. Entrée d'URL et ajout

#### P1. Un champ unique pour coller une URL ou un identifiant
- **Quoi.** Un seul champ accepte tout : URL dramaboxdb.com ou dramabox.com, lien de partage, URL dramafren, ou identifiant seul. Il reconnaît le type au collage, sans demander à l'utilisateur de choisir le type d'entrée.
- **Où.** Barre d'adresse de Chrome (URL ou recherche) [C]. Sonarr « Add New » (nom ou `tvdb:ID`) [C]. Champ « Media URL » de Parabolic [V]. Onglet « Paste URL » de dramafren.
- **Pourquoi ça marche.** Aucune décision à prendre avant de coller. La reconnaissance immédiate (« Lien DramaBox détecté ») rassure avant même l'appel réseau.
- **Chez nous.**
  - Le champ est dans l'en-tête de **toutes les pages**, avec le texte d'aide « Colle une URL DramaBox ou un identifiant (ex. 41000105199) ».
  - L'analyse locale est instantanée (mêmes règles que `inputs.py`) et affiche une étiquette « DramaBox · série 41000105199 ».
  - Un texte libre filtre la bibliothèque locale au lieu de produire une erreur.
  - L'analyse démarre au collage ; Entrée confirme.
- **Pièges.**
  - Recopier les onglets « Paste URL / Search Title » de dramafren : l'onglet de recherche serait mort.
  - Afficher des erreurs en rouge pendant la frappe.
  - Exiger le préfixe `https://`.
  - Vider le champ en cas d'erreur : il faut garder le texte et surligner la partie fautive.

#### P2. Aperçu avant de lancer le téléchargement
- **Quoi.** Trois temps : analyser, afficher une carte d'aperçu, confirmer.
- **Où.**
  - Sonarr : le résultat de recherche affiche l'affiche et le synopsis, puis une modale d'options avec la case « lancer la recherche des manquants » [V partiel, wiki Servarr].
  - Parabolic : l'étape « Valider » récupère titre, durée et formats [V].
  - Raindrop : titre, description et vignette sont récupérés automatiquement [V].
  - Client qBittorrent : la boîte d'ajout affiche la taille et l'espace libre sur le disque [C].
- **Pourquoi ça marche.** L'utilisateur confirme que c'est la bonne série (cover + titre) avant de consommer 700 Mo. Il voit le coût (taille, durée, temps) et choisit la langue en sachant ce qui existe.
- **Chez nous.**
  - La carte montre : cover 9:16, titre dans la langue choisie et titre original, synopsis replié sur 3 lignes, « 62 épisodes · 1 h 32 ».
  - Les langues disponibles apparaissent en étiquettes ; celles qui manquent ne sont pas proposées.
  - Qualité, estimation « ≈ 700 Mo · ≈ 1 min · 180 Go libres ».
  - **Un seul bouton principal** : « Télécharger les 62 épisodes ». En secondaire : « Choisir les épisodes » et la case « Créer le film à la fin ».
  - Pendant l'analyse, une carte de chargement (squelette) remplace la carte.
  - *Implication technique : le moteur doit exposer `info` sous forme d'appel rapide et non bloquant.*
- **Pièges.**
  - Un aperçu qui se contente d'afficher l'identifiant.
  - Taire le **mode sonde** (série absente du site officiel, durées non vérifiées). Il faut une étiquette explicite.
  - Laisser choisir une langue indisponible puis prévenir *après* du repli sur la VO.

```
┌─────────────────────────────────────────────────────────────┐
│ ┌──────┐  Qui Est la Véritable Mme Lafont ?                 │
│ │cover │  One Night to Forever · VF                          │
│ │ 9:16 │  62 épisodes · 1 h 32 · Romance, PDG               │
│ │      │  Synopsis sur 3 lignes…                  [Lire plus]│
│ └──────┘  Langue [Français ▾]   Qualité [1080p ▾]            │
│           ≈ 700 Mo · ≈ 1 min · 182 Go libres                 │
│  [ Télécharger les 62 épisodes ]   Choisir les épisodes      │
│  ☐ Créer le film à la fin          sdg fetch … (copier)      │
└─────────────────────────────────────────────────────────────┘
```

#### P3. Réglages par défaut judicieux, options repliées
- **Quoi.** Le cas le plus fréquent ne demande aucun réglage.
- **Où.** Stacher : 3 préréglages et 3 téléchargements en parallèle par défaut [V]. Pinchflat : « Sources » d'un côté, « Media Profiles » de l'autre [V]. Sonarr : profils qualité [C].
- **Pourquoi ça marche.** L'essentiel des ajouts se résume à « tout, en meilleure qualité ». Chaque question en plus coûte une décision.
- **Chez nous.**
  - Préférences globales : qualité 1080p ; langue préférée (« Français si disponible, sinon VO », ce qui **évite** le cas « langue indisponible ») ; 3 en parallèle ; film automatique oui/non ; dossier de sortie.
  - L'aperçu les résume sur une ligne cliquable « 1080p · Français · film auto » qui se déplie au clic.
- **Pièges.**
  - Un système de profils nommés avec seuil qualité et mises à niveau : trop lourd pour un seul type de contenu.
  - Le réglage « parallélisme » au premier niveau alors que c'est un réglage d'expert.

#### P4. Presse-papier et collage n'importe où
- **Quoi.** L'appli reconnaît une URL copiée, ou accepte Ctrl+V depuis n'importe quel endroit de la page.
- **Où.** JDownloader écoute le presse-papier et envoie les liens dans LinkGrabber [V]. Parabolic pré-remplit le champ avec le contenu du presse-papier [V].
- **Pourquoi ça marche.** Le geste naturel est « copier dans le navigateur, revenir dans l'appli ». On supprime le clic dans le champ.
- **Chez nous.**
  - Ctrl+V en dehors d'un champ ouvre le champ d'ajout pré-rempli et lance l'analyse.
  - En option, au retour sur l'onglet : une suggestion discrète « Ajouter “One Night to Forever” ? » si le presse-papier contient une URL DramaBox absente de la bibliothèque. Lire le presse-papier demande une permission du navigateur : on ne la demande qu'après un geste de l'utilisateur.
- **Pièges.**
  - Une écoute permanente et automatique : celle de JDownloader est souvent désactivée par ses utilisateurs [V].
  - Lancer un téléchargement sans confirmation.
  - Demander la permission dès le premier écran.

#### P5. Reconnaître ce qui est déjà dans la bibliothèque
- **Où.** Tube Archivist n'ajoute pas ce qui est déjà en file, ignoré ou indexé [V]. Sonarr marque « Already in library » dans les résultats [C].
- **Chez nous.**
  - La clé est le bookId + la langue.
  - Si la série existe, l'aperçu devient « Déjà dans ta bibliothèque : VO complète (62/62), VF absente », avec les actions « Ouvrir », « Ajouter la VF », « Compléter (3 manquants) ».
  - Une URL VF d'une série déjà présente en VO **ajoute une version**, elle ne crée pas une nouvelle série.
- **Pièges.** Créer un second dossier sans rien dire. Afficher « existe déjà » sans proposer d'action.

#### P6. Ajout en lot (une URL par ligne)
- **Où.** Tube Archivist [V], Parabolic [V], JDownloader.
- **Chez nous.** Coller plusieurs lignes affiche une liste d'aperçus compacts, tous cochés, avec le bouton « Télécharger 4 séries (≈ 2,7 Go) ». Priorité basse.
- **Pièges.** La zone d'attente de JDownloader, séparée de la zone de téléchargement, où les liens restent en attente parce que l'utilisateur ne sait pas qu'il faut « démarrer » [C]. Chez nous, l'aperçu disparaît après confirmation : il ne devient **jamais** une deuxième file.

### B. Suivi des téléchargements

#### P7. Panneau d'activité persistant
- **Quoi.** Un indicateur global, repliable, toujours visible, qui reste à l'écran quand on change de page.
- **Où.** Panneau d'envoi de Google Drive en bas à droite [C]. Bulle de téléchargements de Chrome [C]. Barre d'état de qBittorrent (vitesses, espace libre) [C]. Compteur sur « Activity » dans le menu de Sonarr [C].
- **Pourquoi ça marche.** L'utilisateur continue à parcourir la bibliothèque pendant le téléchargement, sans aller sur une page « File » pour savoir où on en est.
- **Chez nous.**
  - **Replié** : une ligne « ↓ 2 séries · 34/124 ép. · 12 Mo/s · ~40 s » avec une barre fine.
  - **Déplié** : une ligne par série avec cover miniature, titre, barre de progression, mini-grille d'épisodes, Pause / Annuler, puis l'historique récent.
  - Le titre de l'onglet affiche « (54 %) ShortDramaGen ».
  - Quand tout est fini, le panneau affiche « Terminé · 62/62 · Ouvrir », puis se masque.
  - *Implication technique : un flux d'événements (SSE) avec octets et statut par épisode, limité à 2 à 4 mises à jour par seconde.*
- **Pièges.**
  - Un panneau qui masque le contenu : prévoir une marge en bas de page.
  - Une barre qui recule parce qu'on mélange calcul par octets et calcul par nombre d'épisodes.
  - Un temps restant qui saute : il faut le lisser.

#### P8. Progression à deux niveaux : série, puis épisodes
- **Où.** Paquets repliables de JDownloader [C]. File de Sonarr regroupable par série [C?].
- **Chez nous.** Niveau 1 : la série (x/62, %). Niveau 2 : les cases d'épisodes. Jamais une ligne par épisode dans la file.
- **Pièges.** 62 barres de progression concurrentes, ou 3 lignes « en cours » suivies de 59 lignes « en attente ».

#### P9. Grille de statut par épisode
- **Quoi.** Une case numérotée par épisode. Sa couleur **et** son icône indiquent le statut.
- **Où.**
  - Grille « Ep 1…Ep 62 » de dramafren et sélecteurs d'épisodes des applis de short drama [C].
  - Codes couleur du calendrier Sonarr : violet = en téléchargement, rouge = manquant [V] ; vert = téléchargé, bleu = pas encore diffusé [C].
  - Grille de contributions de GitHub [C].
- **Pourquoi ça marche.** Les 62 statuts se lisent d'un coup d'œil (environ 10×7 cases) ; les trous et les échecs sautent aux yeux. Le même composant sert à voir, sélectionner et relancer.
- **Chez nous.**
  - Un seul composant, réutilisé dans l'aperçu (sélection), la fiche série (statut et lecture) et le panneau d'activité (en miniature).
  - Cinq statuts visibles au maximum (voir §3).
  - Au survol ou au focus, une infobulle : « E028 · 2 min 14 · 1080p · 12,8 Mo · Terminé ».
  - Clic : lire l'épisode s'il est terminé. Menu : Réessayer / Retélécharger dans une autre qualité / Afficher dans l'Explorateur.
  - **Légende toujours visible** avec compteurs cliquables : « 3 échecs » sélectionne ces trois cases.
- **Pièges.**
  - La couleur seule, illisible pour les daltoniens. Sonarr a dû ajouter une légende après des questions d'utilisateurs [V].
  - Un bleu « en cours » confondu avec le bleu d'accent de la sélection. La sélection se montre par un **contour et une coche**, jamais par une couleur de fond.
  - Une animation qui clignote en permanence : respecter le réglage « réduire les animations » (`prefers-reduced-motion`).

```
  1  2  3  4  5  6  7  8  9 10 11 12      ■ Terminé (58)  ◧ En cours (1)
 13 14 15 16 17 18 19 20 21 22 23 24      ! Échec (2)     ▨ Indisponible (1)
 …                                         □ À télécharger (0)
 61 62                                    [Réessayer les 2 échecs]
```

#### P10. Contrôles de file réduits au minimum
- **Où.** Tube Archivist : « Download now », « Ignore », Stop / Cancel [V]. qBittorrent : pause, priorités, menu contextuel très riche [C].
- **Chez nous.**
  - Par série : Pause / Reprendre / Annuler. Pour tout : « Tout mettre en pause ».
  - La priorité est inutile au départ (une série prend environ 1 min). Au plus : « Passer en premier ».
  - **Annuler ne supprime pas** : les épisodes terminés restent sur le disque.
- **Pièges.** Des limites de vitesse. Un « Annuler » qui efface les fichiers.

#### P11. Fin d'opération : notification et suite logique
- **Chez nous.**
  - Un toast, plus une notification système si l'utilisateur l'a autorisée : « One Night to Forever · 62/62 · 712 Mo », avec les actions **Lire**, **Créer le film**, **Ouvrir le dossier**.
  - Si « film automatique » est coché, le film se crée à la suite, et l'interface le dit.
- **Pièges.** Une notification par épisode. Une notification sans action.

### C. Erreurs et reprise

#### P12. Des erreurs qui disent quoi faire
- **Où.** Tube Archivist : message d'erreur par vidéo, filtre « erreurs » et « Clear errors » en masse [V]. qBittorrent : filtre « Errored » [C]. Sonarr : icône d'avertissement dans la file, message au survol [C].
- **Pourquoi ça marche.** Un échec compréhensible et rattrapable ne casse pas la confiance ; un message technique brut, si.
- **Chez nous.**
  - Distinguer **Échec**, qu'on peut réessayer, de **Indisponible**, qui vient de la source et ne se réessaie pas en boucle.
  - Un message en langage courant, avec le détail technique replié (« Durée 48 s au lieu de 52 s attendues »). Voir le tableau du §4.
  - *Implication technique : le manifest doit porter un code d'erreur (`reason`) en plus du message.*
- **Pièges.** Ne jamais réessayer, comme Tube Archivist [V].

#### P13. Réessais automatiques, puis réessai manuel groupé
- **Chez nous.**
  - Erreurs réseau et URL signée expirée : réessais silencieux, avec un compteur discret. Le moteur sait déjà résoudre à nouveau une URL expirée.
  - Si l'échec persiste, l'épisode passe en Échec.
  - Un bouton unique « Réessayer les 3 échecs » dans la fiche et dans le panneau d'activité, et un filtre « Avec échecs » dans la bibliothèque.
- **Pièges.** Afficher « URL expirée » alors que c'est géré : c'est un détail interne.

#### P14. Reprise après interruption, au lancement
- **Où.** Clients torrent [C]. File persistante de Tube Archivist [V]. Notre moteur : relancer la commande ne fait que ce qui manque.
- **Chez nous.**
  - Au démarrage, si des manifests contiennent des épisodes `downloading` ou `pending`, un bandeau propose : « 2 téléchargements interrompus (37 épisodes) · Reprendre · Ignorer ».
  - Les fichiers `.part` permettent de reprendre au lieu de recommencer, et on l'affiche : « reprise à 64 % ».
  - Option « toujours reprendre automatiquement ».
- **Pièges.** Relancer 1,4 Go sans prévenir.

#### P15. Bandeau de santé système
- **Où.** Page « Health » de Sonarr, avec une pastille sur l'entrée « System » du menu [C]. Espace libre dans la barre d'état de qBittorrent [C].
- **Chez nous.**
  - Vérifications : ffmpeg présent, dossier de sortie accessible en écriture, espace libre suffisant, dramafren et site officiel joignables.
  - Une pastille sur « Réglages », et un message **uniquement là où le problème bloque**. Par exemple, le bouton « Créer le film » est désactivé avec « ffmpeg n'est pas installé · Comment l'installer ? » et les commandes `pip install imageio-ffmpeg` ou `winget install Gyan.FFmpeg`, avec un bouton Copier.
- **Pièges.** Un bandeau rouge permanent pour une fonction secondaire. Un bouton désactivé sans explication accessible au clavier.

#### P16. Transformer un refus en choix
- **Quoi.** Quand une opération est impossible telle quelle, proposer les issues possibles sous forme de boutons, la recommandée en premier.
- **Chez nous (création du film).**
  - Qualités mélangées : « 3 épisodes sont en 720p (E012, E040, E041). **[Retélécharger ces 3 en 1080p, ~15 s, recommandé]** [Tout ré-encoder, lent] ».
  - Épisodes manquants : « 4 épisodes manquent. **[Les télécharger puis créer le film]** [Créer un film partiel « … (épisodes 1-10) »] ».
  - La fusion prend 6 s : la progression s'affiche **dans le bouton**, sans modale.
- **Pièges.** Un refus sec du type « Mixed qualities ». Une modale bloquante pour 6 secondes.

### D. Bibliothèque

#### P17. Mur d'affiches 9:16 avec barre de complétude
- **Où.**
  - Plex, Jellyfin, Infuse [C].
  - Vue « Affiches » de Sonarr, avec une barre colorée sous chaque affiche : vert = complète et terminée, bleu = complète mais en cours de diffusion, rouge = épisodes suivis manquants, orange = manquants non suivis, violet = en téléchargement [C ; l'orange est vérifié V].
- **Pourquoi ça marche.** On reconnaît une série à sa cover plus vite qu'à son titre, surtout quand le titre traduit est long. La barre donne l'état sans ouvrir la fiche.
- **Chez nous.**
  - Cartes de 160 à 200 px de large. La cover native de 360 px reste nette jusqu'à 180 px sur un écran en mise à l'échelle 200 %.
  - Sous la cover : barre de complétude, titre sur 2 lignes maximum, « 62 ép. · 1 h 32 ».
  - Badges : langues (VO / VF / VE), « Film » si le film existe, pastille d'état (en cours, échecs).
  - Au survol : Lire, Compléter, Ouvrir le dossier.
  - Tri par défaut : ajout récent.
- **Pièges.**
  - Cinq badges par carte.
  - Des badges sur les visages : les covers de short drama sont presque toujours des visages. Mettre les badges, petits, dans les coins bas.
  - Du texte sur la cover sans dégradé derrière.

#### P18. Deux vues : affiches ou liste
- **Où.** Sonarr : Affiches / Aperçu / Tableau [C]. VueTorrent [V].
- **Chez nous.**
  - Vue Affiches par défaut.
  - Vue Liste : titre, langues, épisodes x/y, taille, film, date d'ajout, état. Triable par taille pour libérer de l'espace.
  - La vue choisie est mémorisée.
- **Pièges.** Des colonnes configurables pour un tableau de 7 colonnes.

#### P19. Filtres avec compteurs et recherche sur tous les titres
- **Où.** Barre latérale de qBittorrent : Statut, Catégories [V]. Tube Archivist [V]. Sonarr « Wanted › Missing » [C].
- **Chez nous.**
  - À ce volume, des filtres en étiquettes horizontales suffisent : Toutes (24) · En cours (2) · Incomplètes (3) · Avec échecs (1) · Avec film (10), plus un filtre par langue.
  - Recherche instantanée sur **tous les titres, toutes langues**, et sur le bookId.
- **Pièges.** Des filtres à 0 affichés comme les autres. Une recherche qui ne trouve pas « Mme Lafont » parce que la carte affiche le titre anglais.

#### P20. Une série, plusieurs versions de langue
- **Où.** Plex : « Lire la version… » [C]. Jellyfin : sélecteur « Version » [C].
- **Pourquoi ça marche.** L'utilisateur pense « la série One Night to Forever », pas « le dossier 41000105199-…-fr ».
- **Chez nous.**
  - Une seule carte par bookId d'origine.
  - Dans la fiche, des onglets de version : « VO (anglais) · VF · VE ». Chaque onglet a sa grille, sa taille et son film.
  - Les langues disponibles mais pas encore téléchargées apparaissent comme onglet « + Espagnol », qui s'ajoute en un clic.
  - Sur le disque, on garde un dossier par langue, comme le fait déjà le moteur.
- **Pièges.**
  - Trois cartes presque identiques pour la même série.
  - Des **drapeaux** pour les langues : un drapeau espagnol ne dit pas s'il s'agit d'espagnol d'Espagne ou d'Amérique latine.
  - Le code `in` affiché tel quel : c'est l'ancien code de l'indonésien, il faut écrire « Indonésien ».

#### P21. Fiche série
- **Où.** Plex, Jellyfin, Infuse : bandeau, affiche, informations, bouton Lire qui reprend au bon épisode [C]. DramaBox : cover, tags, synopsis, sélecteur d'épisodes [C]. Sonarr : en-tête, barre d'actions, table d'épisodes [C].
- **Chez nous.**
  - En-tête : cover nette à gauche (240 px max) sur un fond flouté tiré de la même cover. Titre, titre original, synopsis replié, informations (62 ép. · 1 h 32 · 712 Mo · 1080p), onglets de version, puis la grille d'épisodes et sa légende.
  - **Un seul bouton principal, qui change selon l'état** :

    | État de la série | Bouton principal |
    |---|---|
    | En cours de téléchargement | « Mettre en pause » |
    | Incomplète | « Compléter (4 manquants) » |
    | Complète, sans film | « Créer le film » |
    | Complète, avec film | « Lire le film » |

  - Actions secondaires : Afficher dans l'Explorateur ; menu Plus (Retélécharger en 720p, Vérifier, Supprimer).
  - Un panneau « Détails techniques » replié : bookId, chemin, origine des fichiers, commande CLI.
- **Pièges.** Un bandeau paysage étiré à partir d'une cover de 360×640. Huit boutons de même poids. Un synopsis déplié qui pousse la grille hors de l'écran.

#### P22. Actions en masse
- **Où.** Mode sélection de Sonarr [C]. Actions sur le résultat filtré dans Tube Archivist [V]. Maj+clic dans VueTorrent [V].
- **Chez nous.**
  - Une case apparaît sur chaque carte au survol ; Maj+clic sélectionne une plage.
  - Une barre d'actions apparaît : Compléter, Créer les films, Supprimer les épisodes (garder les films), Supprimer.
  - Exemple de combinaison : filtre « Incomplètes », tout sélectionner, Compléter.
- **Pièges.** Une action destructive en masse sans récapitulatif chiffré (« 5 séries, 3,4 Go »).

#### P23. Stockage et suppression au choix
- **Constat.** Le film et les épisodes font doublon : environ 700 Mo + 700 Mo par série.
- **Où.** Case « Supprimer le dossier » de Sonarr [C]. « Annuler » de Gmail [C].
- **Chez nous.**
  - Boîte de suppression à choix unique :
    - « Épisodes seulement (garder le film) : libère 700 Mo » ;
    - « Film seulement » ;
    - « Tout le dossier : 1,4 Go ».
  - Après la création d'un film, suggérer une fois, sans insister : « Supprimer les épisodes pour libérer 700 Mo ? ».
  - La suppression est différée de 8 s avec « Annuler ».
  - L'espace occupé par la bibliothèque et l'espace libre du disque sont visibles.
- **Pièges.** Un « Êtes-vous sûr ? » générique, que l'utilisateur valide sans lire.

#### P24. La bibliothèque reflète le disque
- **Où.** « Library Import » de Sonarr [C]. Analyse de bibliothèque de Plex et Jellyfin [C].
- **Chez nous.**
  - La source de vérité reste `downloads/*/manifest.json`, pour que le CLI et le frontend coexistent.
  - Au démarrage, et sur « Actualiser » : analyser les dossiers et importer ceux créés en CLI.
  - Signaler les incohérences, par exemple un épisode `done` dont le fichier a disparu : statut « À vérifier ».
- **Pièges.** Une base de données propre au frontend qui finit par diverger du disque.

### E. Codes propres au short drama

#### P25. Grille d'épisodes numérotés
- **Où.** DramaBox, ReelShort, ShortMax : tiroir d'épisodes avec onglets de plages, cases numérotées, épisode en cours mis en évidence [C], tiroir placé à portée du pouce [V]. dramafren : « Ep 1 … Ep 62 ».
- **Pourquoi ça marche.** Dans ce format, le numéro est l'identité de l'épisode : il n'y a pas de titre d'épisode.
- **Chez nous.**
  - Sur ordinateur, 62 cases tiennent en 10 à 12 colonnes sans onglets. Les onglets de plages (1–50, 51–100…) ne servent qu'au-delà de ~100 épisodes ou sur mobile.
  - L'interface affiche « 1 » à « 62 ». « E001 » reste le nom de fichier et apparaît dans l'infobulle.
- **Pièges.** Copier les cadenas et les pièces. Mettre en avant le badge « gratuit » des épisodes 1 à 10, sans intérêt ici.

#### P26. Lecture verticale et enchaînement (V2, optionnel)
- **Où.** ReelShort : plein écran 9:16, glisser vers le haut pour l'épisode suivant, enchaînement automatique [V]. « Next Up » de Jellyfin [V], « Continuer » de Plex [C].
- **Chez nous.**
  - Lecteur 9:16 centré, de la hauteur de l'écran, avec la grille d'épisodes à droite.
  - Enchaînement automatique ; flèches ↑ / ↓ pour l'épisode précédent ou suivant.
  - Mémoire du dernier épisode vu, pour afficher « Reprendre à l'épisode 28 » sur la carte.
  - Alternative en V1 : « Ouvrir dans le lecteur par défaut ». VLC gère déjà les chapitres du film.
- **Pièges.** Un flux vidéo en lecture automatique comme page d'accueil. Une vidéo verticale étirée en 16:9. Du son qui démarre au survol.

#### P27. Identité visuelle
- **Chez nous.**
  - Reprendre le bleu nuit et l'accent bleu de dramafren. Les covers apportent la vraie couleur de l'interface.
  - Titres longs : 2 lignes, points de suspension, titre complet en infobulle.
  - Typographie française : espace insécable avant « ? » et « : », unités « Mo », durées « 1 h 32 », virgule décimale « 12,8 Mo ».
- **Pièges.** L'accent bleu partout (boutons, liens, statuts, sélection) : il n'y a plus de hiérarchie.

### F. Patterns génériques

#### P28. Sélection d'épisodes par plages
- **Où.** Maj+clic dans l'Explorateur Windows, Gmail, VueTorrent [V]. Sélection au lasso [C]. Champ « Pages : 1-3, 5 » des boîtes d'impression [C]. Notre CLI : `-e 1-10,28,50-`.
- **Chez nous.**
  - Dans la grille : clic = cocher/décocher, Maj+clic = plage, glisser = plage.
  - Raccourcis : **Tous · Aucun · Manquants · Échecs · Inverser**.
  - Un champ texte « 1-10, 28, 50- » **synchronisé dans les deux sens** avec la grille.
  - Un résumé en direct : « 23 épisodes · ≈ 270 Mo ».
  - Au clavier : flèches, Espace, Maj+flèches.
- **Pièges.**
  - Une liste de 62 cases à cocher.
  - Une sélection perdue quand on change de qualité.
  - Une syntaxe texte trop stricte : il faut accepter « 1–10 » (tiret long), les espaces, « 50-62 » et « 50- ».

#### P29. Palette de commandes et raccourcis
- **Où.** Linear, VS Code, Raycast, GitHub [C].
- **Chez nous.**
  - Ctrl+K ouvre la palette :
    - coller une URL propose « Ajouter » ;
    - taper un titre (toutes langues) ouvre la série ;
    - actions : Reprendre tout, Réessayer les échecs, Créer le film de…, Ouvrir le dossier downloads.
  - Autres raccourcis : `/` pour rechercher, `?` pour l'aide.
  - L'indice « Ctrl K » est visible dans l'en-tête.
- **Pièges.**
  - La palette comme seul accès à une fonction.
  - Des raccourcis d'une lettre qui se déclenchent pendant la saisie.
  - Afficher « ⌘ » à un utilisateur Windows.

#### P30. Toasts, annulation, historique
- **Chez nous.**
  - Succès : toast qui disparaît après 5 s.
  - Erreur : toast qui reste, avec une action.
  - Action destructive : toast avec « Annuler » pendant 8 s.
  - **Regrouper** : « 3 épisodes en échec », pas trois toasts.
  - Chaque toast est aussi consigné dans l'historique du panneau d'activité.
  - 3 toasts empilés au maximum, annoncés aux lecteurs d'écran (`aria-live`).
- **Pièges.** 62 toasts. Une information importante uniquement dans un toast éphémère.

#### P31. États vides
- **Où.** Sonarr : « Ajouter une série / Importer une bibliothèque » [C]. Notion, Linear [C].
- **Chez nous.**
  - **Bibliothèque vide** : le champ d'ajout en grand, les formats acceptés, un lien « Essayer avec un exemple » (URL de One Night to Forever). Si un dossier `downloads` existe : « 3 séries trouvées sur le disque · Importer ».
  - **File vide** : « Rien en cours » et la dernière activité.
  - **Recherche sans résultat** : « Aucune série “xyz” · Coller une URL ? ».
  - **Premier lancement** : 3 étapes au maximum (dossier, langue préférée, ffmpeg optionnel).
- **Pièges.** Une illustration décorative sans action. Un carrousel d'accueil.

#### P32. Transparence technique à la demande
- **Où.** Stacher : Ctrl+Entrée affiche la commande yt-dlp [V]. Journaux de Sonarr [C].
- **Chez nous.** « Commande équivalente : `sdg fetch 41000105199 --lang fr -q 1080p --film` » avec un bouton Copier, et un journal par série. Cela nourrit le côté « défi » et aide au débogage.
- **Pièges.** Afficher bookId, URL signées et dates d'expiration au premier niveau de l'interface.

#### P33. À ne pas copier : calendrier et suivi des séries
- **Où.** Calendrier et « monitoring » de Sonarr et Radarr ; indexation périodique de Pinchflat [V].
- **Pourquoi pas.** Les séries sont le plus souvent complètes dès leur mise en ligne (à confirmer). Il n'y a pas de date de diffusion à suivre, et la logique suivi / non suivi ajoute de la complexité sans rien apporter.
- **Au plus.** Une action manuelle « Vérifier les nouveaux épisodes », qui relance `info` et compare le nombre d'épisodes.

---

## 3. Statuts recommandés

| Statut dans `manifest.json` | Libellé affiché | Aspect (couleur + forme) | Actions |
|---|---|---|---|
| `pending`, `resolved` | À télécharger | Contour gris, numéro gris (on ne distingue pas les deux) | Sélection |
| `downloading` | En cours | Fond bleu et remplissage interne selon la progression | Pause (au niveau série) |
| `done` | Terminé | Fond vert plein | Lire, Afficher dans l'Explorateur |
| `failed`, cause réessayable | Échec | Rouge avec « ! » | Réessayer, voir le détail |
| `failed`, cause source | Indisponible | Hachures grises avec « – » | Voir le détail, pas de réessai automatique |
| *(absent de la sélection)* | Non demandé | Contour en pointillés | Ajouter |
| *(fichier disparu)* | À vérifier | Ambre avec « ? » | Vérifier / Retélécharger |
| *Sélection (se combine aux autres)* | — | Contour d'accent de 2 px et coche | — |

**Statuts au niveau d'une série** : En file · En cours · Complète · Incomplète · Avec échecs · Film prêt.

---

## 4. Chaque erreur du moteur et sa réponse dans l'interface

| Cas | Quand on le montre | Message | Action proposée |
|---|---|---|---|
| URL invalide | Au collage, sous le champ | « Ce lien n'est pas reconnu. Formats acceptés : … » | Garder le texte collé, afficher des exemples |
| Série absente du site officiel (mode sonde) | Dans l'aperçu | Étiquette « Mode sonde : durées non vérifiées » | Continuer |
| Langue indisponible | Dans l'aperçu, **avant** le lancement | Langue absente de la liste, ou « VF indisponible, VO utilisée » | Choisir une autre langue |
| Épisode indisponible sur dramafren | Dans la grille | Statut Indisponible | Détail, pas de réessai en boucle |
| URL signée expirée | Jamais | — (nouvelle résolution automatique) | — |
| Vérification échouée (durée) | Dans la grille et le panneau d'activité | « Vérification échouée (48 s ≠ 52 s) » | Réessayer |
| Erreur réseau | Après les réessais automatiques | « Connexion perdue · 3 échecs » | Réessayer les échecs |
| Interruption | Au lancement de l'appli | « 2 téléchargements interrompus » | Reprendre / Ignorer |
| ffmpeg absent | Sur le bouton « Créer le film » + pastille Réglages | « ffmpeg n'est pas installé » | Commandes à copier |
| Qualités mélangées | Au clic sur « Créer le film » | « 3 épisodes en 720p » | Retélécharger (recommandé) / Ré-encoder |
| Épisodes manquants | Au clic sur « Créer le film » | « 4 épisodes manquent » | Compléter puis créer / Film partiel |
| Plusieurs langues d'une même série | Dans la bibliothèque | Une seule carte, onglets de version | « + Ajouter une langue » |

---

## 5. Anti-patterns transverses

1. Un onglet ou un bouton qui ne mène à rien (« Search Title »).
2. Une modale bloquante pour une opération de moins de 10 secondes.
3. Une notification par épisode.
4. La couleur comme seul indicateur de statut.
5. Des drapeaux pour désigner des langues.
6. Des détails internes au premier niveau (URL signées, expirations).
7. Deux files d'attente différentes (la zone d'attente de JDownloader).
8. Un bandeau paysage agrandi à partir d'une cover de 360×640.
9. Des mécaniques de monétisation (cadenas, pièces, « gratuit »).
10. Un flux vidéo en lecture automatique comme page d'accueil.
11. Un calendrier, un suivi série par série, des profils qualité avec seuils.
12. Une suppression sans chiffre ni annulation.
13. Des raccourcis macOS affichés à un utilisateur Windows.
14. Des états vides sans action.
15. Des tables denses façon qBittorrent pour 62 éléments.

---

## 6. Conséquences pour la maquette

- **En-tête global** : logo · champ d'ajout (Ctrl+V / Ctrl+K) · pastille de santé · Réglages.
- **Accueil = Bibliothèque** : filtres en étiquettes, tri, vues affiches ou liste, mode sélection.
- **Aperçu d'ajout** : carte qui s'ouvre sous le champ d'ajout, pour garder le contexte.
- **Fiche série** : cover floutée en fond, onglets de version, grille d'épisodes et légende, bouton principal selon l'état.
- **Panneau d'activité** en bas à droite, avec son historique.
- **Réglages** : préférences, dossier, espace disque, santé.
- **Lecteur vertical** : en V2.

**Parcours cibles.**
- **URL vers tout télécharger** : coller, puis Entrée. Aucun autre geste nécessaire.
- **Compléter** : filtre « Incomplètes », carte, « Compléter ».
- **Film** : « Créer le film », vérifications préalables, 6 s, puis « Lire » ou « Libérer 700 Mo ».

---

## 7. Top 15 des recommandations, classées par impact

| # | Recommandation | Impact | Effort | Patterns |
|---|---|---|---|---|
| 1 | Champ d'ajout global qui accepte URL ou identifiant, reconnaît le type au collage et fonctionne avec Ctrl+V n'importe où | Très élevé | S | P1, P4 |
| 2 | Carte d'aperçu avant lancement (cover, titre, épisodes, durée, langues, taille, temps, espace libre), avec un seul bouton principal « Télécharger les 62 épisodes » | Très élevé | M | P2, P3 |
| 3 | Un seul composant de grille d'épisodes pour le statut, la sélection et la progression, avec couleur **et** forme et une légende qui compte | Très élevé | M | P9, P25, §3 |
| 4 | Panneau d'activité persistant (replié / déplié), progression série puis épisodes, pourcentage dans l'onglet, notification de fin avec actions | Très élevé | M | P7, P8, P11 |
| 5 | Erreurs rangées par catégorie et réparables : réessais automatiques silencieux, Échec distinct d'Indisponible, « Réessayer les N échecs », reprise au lancement | Élevé | M | P12–P14, §4 |
| 6 | Bibliothèque en mur d'affiches 9:16 avec barre de complétude, badges de langue et de film, qui reflète le disque (import des dossiers créés en CLI) | Élevé | M | P17, P24 |
| 7 | Une série = une carte, les langues = des versions (onglets, recherche sur tous les titres, noms de langue au lieu de drapeaux) | Élevé | M | P20, P19 |
| 8 | Fiche série avec cover nette sur fond flouté et un bouton principal qui change selon l'état | Élevé | M | P21 |
| 9 | Création du film guidée : chaque refus devient un choix (retélécharger ou ré-encoder, compléter ou film partiel), progression dans le bouton | Élevé | S | P16 |
| 10 | Réglages par défaut judicieux (1080p, « Français si disponible »), résumé cliquable dans l'aperçu | Élevé | S | P3 |
| 11 | Sélection par plages : Maj+clic, glisser, raccourcis (Manquants, Échecs), champ « 1-10, 28, 50- » synchronisé | Moyen+ | M | P28 |
| 12 | Filtres avec compteurs (En cours, Incomplètes, Échecs, Film) et actions en masse sur le résultat filtré | Moyen+ | S | P19, P22 |
| 13 | Santé système affichée là où le problème bloque (ffmpeg, disque, sources) | Moyen | S | P15 |
| 14 | Stockage : suppression au choix avec espace libéré et annulation, suggestion « libérer 700 Mo » après le film | Moyen | S | P23 |
| 15 | États vides avec actions (exemple, import) et palette Ctrl+K, plus la commande CLI équivalente copiable | Moyen | S | P29, P31, P32 |

**Hors Top 15.** Lecteur vertical avec enchaînement et « Reprendre à l'épisode n » (P26), ajout en lot (P6), vérification manuelle des nouveaux épisodes (P33).

---

## 8. Sources consultées
- [Sonarr, légende des couleurs du calendrier](https://forums.sonarr.tv/t/calendar-color-legend/1203) · [Colored episode status](https://forums.sonarr.tv/t/colored-episode-status/11040) · [Couleur des séries non suivies](https://forums.sonarr.tv/t/tracking-status-color-for-unmonitored-series-is-wrong/29146) · [Servarr Wiki, bibliothèque Sonarr](https://wiki.servarr.com/sonarr/library)
- [Tube Archivist, page Downloads](https://docs.tubearchivist.com/downloads/) · [Pages Channels](https://docs.tubearchivist.com/channels/)
- [Pinchflat, Noted](https://noted.lol/pinchflat/) · [Pinchflat, XDA](https://www.xda-developers.com/this-app-turned-my-jellyfin-server-into-a-youtube-archive/)
- [Parabolic, Tecmint](https://www.tecmint.com/parabolic-download-videos-from-websites-linux/) · [Delightly Linux](https://delightlylinux.wordpress.com/2024/10/21/download-videos-with-parabolic/) · [OMG! Ubuntu](https://www.omgubuntu.co.uk/2024/10/parabolic-video-downloader-for-linux-updated)
- [Stacher7, Freewares](https://freewares.org/software/stacher7) · [Stacher, Linux Adictos](https://en.linuxadictos.com/Stacher--the-ideal-interface-for-squeezing-out-YT-DLP-without-a-console..html) · [Arroxy vs Stacher](https://arroxy.orionus.dev/blog/arroxy-vs-stacher/)
- [JDownloader 2, VideoProc](https://www.videoproc.com/download-record-video/how-to-use-jdownloader-2.htm) · [Désactiver le Clipboard Observer](https://www.vertigoisabitch.com/2023/10/jdownloader2-turn-off-linkgrabber.html)
- [qBittorrent WebUI, issue #7601 (barre latérale)](https://github.com/qbittorrent/qBittorrent/issues/7601) · [VueTorrent](https://github.com/VueTorrent/VueTorrent)
- [ReelShort vs DramaBox, Oyelabs](https://oyelabs.com/reelshort-vs-dramabox-what-keeps-users-watching/) · [Kanopy Labs](https://kanopylabs.com/blog/how-to-build-a-short-form-drama-streaming-app) · [FastPix](https://fastpix.com/tutorials/how-to-build-a-micro-drama-video-app-like-reelshort-or-dramabox)
- [Raindrop.io, aide Bookmarks](https://help.raindrop.io/bookmarks) · [Jellyfin « Next Up » (jellyrock PR #927)](https://github.com/jellyrock/jellyrock/pull/927)