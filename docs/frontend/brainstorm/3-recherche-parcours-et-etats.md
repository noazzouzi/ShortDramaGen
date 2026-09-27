# ShortDramaGen : fondations UX du frontend

> Base centrée utilisateur pour la maquette : persona et JTBD, parcours clés, matrice complète des états avec microcopy, exigences d'accessibilité et de responsive, principes directeurs.
> Sources : README, `docs/02`, `docs/03`, code du moteur (`pipeline.py`, `manifest.py`) et faits vérifiés du brief.

---

## 0. Cadrage et hypothèses

| Sujet | Décision / hypothèse | Pourquoi |
|---|---|---|
| Nature du frontend | Interface **locale** au-dessus du moteur Python existant, ouverte dans Edge ou Chrome sous Windows. Le moteur reste la source de vérité : un `manifest.json` par dossier. | Le moteur est déjà fiable (reprise, vérification). Le frontend l'orchestre, il ne le remplace pas. |
| Mobile (390 px) | Même application, consultée depuis le téléphone **sur le réseau local**. C'est une option à activer, à valider côté architecture. | C'est sur le téléphone qu'on obtient le « lien de partage de l'app » DramaBox (voir §1.2). |
| Langue et ton | Interface en français, **tutoiement**, phrases courtes, zéro jargon réseau. | C'est cohérent avec le README (« Ne republie pas… ») et avec un projet personnel. |
| Thème | Sombre par défaut : bleu nuit, accent bleu, dans la continuité de dramafren. Un thème clair est possible plus tard, avec les mêmes exigences de contraste. | Le contenu est vidéo, et l'utilisateur a déjà ses repères visuels. |
| Hors périmètre V1 | Recherche par titre sur DramaBox (l'onglet « Search Title » de dramafren), multi-utilisateur, export pour republication. | Le moteur ne sait pas chercher par titre. **On n'affiche pas une fonction qui ne marche pas**, on réserve seulement l'emplacement. |
| Parité CLI | Tout ce que fait la CLI (`info`, `fetch` et ses options, `links`, `film`) doit être faisable dans l'UI. | Un power user n'accepte pas une interface moins capable que sa CLI. |

---

## 1. Persona et jobs-to-be-done

### 1.1 Persona principal : le collectionneur-bidouilleur

| | |
|---|---|
| **Qui** | L'utilisateur unique du projet. Francophone, à l'aise en technique, il a lancé ce projet comme « un défi que je me lance ». |
| **Contexte d'usage** | Windows 10/11, Edge ou Chrome, écran 1440 px ou laptop 1280 px, souvent sur un second écran. Il a l'Explorateur Windows et VLC ou MPC-HC ouverts à côté. Il lance un téléchargement puis passe à autre chose. |
| **Niveau** | Power user : il utilise la CLI et les raccourcis, lit les logs. Il veut voir les détails techniques **quand il le décide**, pas qu'on les lui impose. |
| **Objectif** | Se constituer une **collection** de séries complètes, vérifiées, dans la meilleure qualité, dans la bonne langue, et en faire des films. |
| **Motivations** | Le défi technique réussi (« ça marche tout seul »), une collection propre et complète, le contrôle. |
| **Frustrations avec l'existant** | Sur dramafren : un clic par épisode dans une grille « Ep 1 … Ep 62 », aucune garantie que le fichier est le bon ou qu'il est complet, rien ne reprend après une coupure. Avec la CLI : aucune vue d'ensemble de la collection, des options à retaper, des versions de langue éclatées en plusieurs dossiers. |
| **Ce qui le ferait décrocher** | Un statut qui ment (« terminé » alors qu'il manque des épisodes). Une UI plus lente que la CLI. Devoir re-choisir la langue ou la qualité à chaque fois. Perdre un téléchargement en fermant l'onglet. |
| **Citation type** | « Je colle le lien, je vais faire autre chose, et quand je reviens tout est là, vérifié. » |

### 1.2 Contexte secondaire : le mode canapé (mobile 390 px)

C'est la même personne, sur son téléphone. Elle voit une série dans l'app DramaBox, fait **Partager**, copie le lien et le colle dans ShortDramaGen ouvert sur le téléphone. C'est le PC qui télécharge. Sur mobile, les tâches prioritaires sont : ajouter un lien, suivre la progression, parcourir la bibliothèque, regarder un épisode.
Ce qui ne sert à rien sur mobile : « Ouvrir le dossier », l'installation de ffmpeg, les réglages avancés. Ces éléments sont masqués sur mobile, pas seulement désactivés.

### 1.3 Anti-persona

On ne conçoit pas pour : quelqu'un qui republie ou diffuse, plusieurs comptes, un grand public qui aurait besoin d'un tutoriel d'installation. Conséquences : pas d'export « réseaux sociaux », pas de gestion de comptes, pas d'onboarding en plusieurs écrans.

### 1.4 Jobs-to-be-done

| # | Quand… | je veux… | pour… | Fréquence | Critère de réussite |
|---|---|---|---|---|---|
| J1 (principal) | je découvre une série qui me plaît (app ou site) | la récupérer **en entier** en un seul geste | l'avoir chez moi, complète et en bonne qualité, sans cliquer 62 fois | Plusieurs fois par semaine | 3 interactions au plus entre le collage et le lancement |
| J2 | un téléchargement tourne | savoir d'un coup d'œil où il en est, sans rester dessus | continuer à faire autre chose | À chaque téléchargement | 0 interaction pour connaître l'avancement |
| J3 | ma collection dépasse 50 séries | retrouver une série et savoir tout de suite si elle est complète | ne pas douter de ma collection | Quotidienne | Moins de 5 s, 3 interactions au plus |
| J4 | quelque chose a échoué | comprendre quoi et le réparer en un clic | ne pas lire de logs | Occasionnelle | 1 clic par réparation, raison en langage clair |
| J5 | une série est complète | en faire **un seul film** chapitré | la regarder d'une traite ou dans mon lecteur | Par série | 1 clic, environ 6 s |
| J6 | une série existe en VF ou en VE | obtenir cette version (ou plusieurs) sans doublon confus | garder une collection lisible | Occasionnelle | Les versions sont regroupées sous une seule série |
| J7 | j'ai dix minutes | reprendre là où je m'étais arrêté | regarder sans chercher | Quotidienne | 1 interaction depuis la bibliothèque |
| J8 | je veux aller plus loin | régler qualité, sélection d'épisodes, liens bruts, commande CLI | garder la maîtrise | Rare | Accessible en 1 clic (« Options »), invisible sinon |

**Jobs émotionnels** : me sentir **en contrôle** (rien ne se passe dans mon dos), avoir **confiance** (chaque fichier a été vérifié), éprouver de la **fierté** (le défi fonctionne, c'est beau et rapide).

### 1.5 Ce que les données réelles imposent à l'UI

| Fait vérifié | Conséquence de design |
|---|---|
| 62 épisodes de 50 s à 3 min 30 | L'épisode est une unité **petite et nombreuse**. On l'affiche dans une grille compacte « Ép. 1 … Ép. 62 » (repère déjà connu sur dramafren), jamais dans une liste de 62 lignes par défaut. |
| Une série complète en 40 s à 1 min 40, un film en environ 6 s | Les attentes sont courtes. Progression affichée sur place, **aucune modale bloquante**, temps restant en langage humain (« environ 1 min »). |
| 650 à 720 Mo par série, donc environ 35 Go pour 50 séries | Afficher la taille estimée **avant** de télécharger, et l'espace disque utilisé et libre dans la bibliothèque et les réglages. |
| Covers 360×640 et vidéos 1080×1920 (9:16) | Grille d'**affiches portrait**, lecteur **vertical**. En paysage, la place libre à côté de la vidéo accueille la liste des épisodes. |
| Titres très différents selon la langue (« One Night to Forever », « Qui Est la Véritable Mme Lafont ? », « Una Noche Para Siempre ») | La recherche porte sur **tous** les titres. La carte montre le titre de la version préférée, avec le titre VO en second. |
| Une langue = un dossier côté moteur | L'UI **regroupe** par série d'origine et présente les langues comme des **versions** de la même série. |
| 7 langues listées par le site, mais seules certaines sont de vraies versions doublées (VF et VE vérifiées) ; sinon le moteur se replie sur la VO avec un avertissement | L'aperçu ne propose que les versions **réellement doublées**, au lieu de prévenir du repli après coup. Dépendance moteur : exposer « doublée : oui/non » pour chaque langue. |
| URL signées valides environ 3 semaines, re-résolution automatique | Invisible pour l'utilisateur. On n'affiche « lien expiré » que si la re-résolution échoue. |
| Mode sonde : série absente du site officiel, sans contrôle de durée | Il faut un état explicite « Téléchargé, non vérifié ». On ne présente jamais un fichier non vérifié comme vérifié. |
| Refus de fusion si les qualités sont mélangées ou s'il manque des épisodes | Chaque refus devient un **choix clair en 1 clic** (retélécharger, film partiel ou ré-encodage). |

### 1.6 Vocabulaire de l'interface (terme moteur → terme affiché)

| Moteur | Interface | Remarque |
|---|---|---|
| `bookId` | « n° de série » | Visible uniquement dans « Détails techniques » et dans la recherche |
| `manifest.json` | (jamais affiché) | « Infos de la série » dans les Détails techniques |
| `pending`, `resolved` | **En attente** | La résolution est un détail interne |
| `downloading` | **En cours · 45 %** | |
| `done` | **Téléchargé** + icône « Vérifié » | Durée conforme à ±1 s |
| `done` en mode sonde | **Téléchargé · non vérifié** | Icône distincte, pas de coche |
| `failed` + message | **Échec** + raison courte | Voir le catalogue d'erreurs (§4) |
| fichier `.part` après interruption | **Interrompu · 40 %** | Reprend là où il s'était arrêté |
| non demandé (sélection `-e`) | **Non téléchargé** | |
| `lang` | **Version** : VO (anglais), VF, VE… | Nom complet au survol et au lecteur d'écran |
| `film` / `concat` | **Film** | |
| `--allow-missing` | **Film partiel** | Nom de fichier : « Titre (épisodes 1-10).mp4 » |
| `--reencode` | **Ré-encoder (plus lent)** | |
| `-q best` | **Meilleure (1080p)** | |
| `-j 3` | **Téléchargements simultanés : 3** | |
| CDN, Range, signée, get_video, dramafren | (réservés aux « Détails techniques ») | Dans les messages : « la source » |

**Statut d'une version de série** (dérivé du manifest), un seul badge principal selon cette priorité :
**En cours** > **En file** > **En pause / Interrompu** > **Échecs (n)** > **Incomplète (58/62)** > **Complète (62/62)**.
Le badge **Film prêt** ou **Film partiel** est secondaire et cumulable.

---

## 2. Parcours clés

Convention de comptage : une interaction = un clic ou tap, un raccourci clavier, ou une validation (Entrée). Coller compte pour 1. Le défilement ne compte pas.

### (a) Coller une URL → aperçu → tout télécharger

**Cibles** : **3 interactions** (2 au clavier : Ctrl+V puis Entrée). Aperçu en moins de 2 s. Premier retour de progression moins de 1 s après le clic.

**Points d'entrée** (l'utilisateur ne cherche jamais où coller) :
1. Bouton **« Ajouter une série »** toujours visible dans l'en-tête (raccourci `A`).
2. **Ctrl+V n'importe où hors d'un champ** : si le presse-papiers contient un lien reconnu, le panneau d'ajout s'ouvre pré-rempli et l'analyse démarre.
3. Glisser-déposer d'un lien sur la fenêtre.
4. Bibliothèque vide : le champ est au centre de l'écran et **déjà focalisé**.
5. Mobile : champ plus bouton **« Coller »**.

| # | Utilisateur | Système | Retour visible |
|---|---|---|---|
| 1 | Ctrl+V dans le champ (ou n'importe où) | Validation **locale** immédiate du format, **sans bouton « Analyser »** | « Lien reconnu. Recherche de la série… » ; squelette d'aperçu 9:16 |
| 2 | — | Métadonnées officielles et versions disponibles | Aperçu : cover, titre, titre VO, synopsis sur 3 lignes, « 62 épisodes · 1 h 32 · environ 700 Mo en 1080p », puces de versions (VO présélectionnée ou langue préférée si elle existe), bouton principal **focalisé** |
| 3 | (optionnel) Clic sur une puce de version (VF) | Titre, synopsis et taille mis à jour | « Qui Est la Véritable Mme Lafont ? · VF » |
| 4 | Entrée ou clic sur **« Tout télécharger · 62 épisodes »** | Mise en file, démarrage | Le bouton devient une barre « 0/62… », l'indicateur global s'allume. Le champ se **vide et reste focalisé** pour enchaîner un autre lien. |

**Options** (repliées sous « Options », **mémorisées** d'une fois sur l'autre, conformément à WCAG 3.3.7) :
- Version : VO / VF / VE… Les langues sans doublage n'apparaissent pas, sauf dans une ligne d'aide : « Coréen, thaï… : titre traduit seulement ».
- Qualité : Meilleure (1080p) / 720p / 540p, avec la taille estimée pour chacune.
- Épisodes : Tous / Sélection (« 1-10, 28, 50- », avec un exemple sous le champ) / Seulement les manquants.
- « Créer le film à la fin » (case, mémorisée).
- Dossier : chemin affiché, bouton [Changer].
- « Copier la commande équivalente », par exemple `sdg fetch 41000105199 --lang fr --film`, pour garder le lien avec la CLI.

**Variantes**

| Variante | Comportement | Interactions |
|---|---|---|
| a2 · Série déjà dans la bibliothèque | Aperçu : « Déjà dans ta bibliothèque : VF complète (62/62). » avec [Ouvrir] et [Ajouter la VO]. Si la version est incomplète : [Télécharger les 4 manquants]. | 2 |
| a3 · Plusieurs liens (un par ligne) | Liste compacte d'aperçus, puis « Tout télécharger · 3 séries · environ 2,1 Go » | 2 |
| a4 · Lien d'un épisode | « C'est le lien de l'épisode 14 : on te propose toute la série. » avec l'option [Seulement l'épisode 14] | 2-3 |
| a5 · Série absente du site officiel (mode sonde) | Chargement plus long, avec un compteur : « Série absente du site officiel. Recherche des épisodes à la source… 23 trouvés » | 2 |
| a6 · Hors ligne | [Garder pour plus tard] : le lien est analysé et mis en file au retour de la connexion | 2 |

**À éviter** : un bouton « Analyser » obligatoire, une modale « Êtes-vous sûr ? » avant un téléchargement, choisir le dossier à chaque fois, une redirection forcée vers la page Téléchargements (on reste où on est et l'indicateur global prend le relais).

### (b) Suivre la progression en faisant autre chose

**Cibles** : **0 interaction** pour connaître l'avancement, **1** pour le détail, et une notification à la fin.

Couches de visibilité, de la plus périphérique à la plus détaillée :
1. **Titre de l'onglet** : « (34/62) ShortDramaGen », puis « Terminé · ShortDramaGen ». Favicon avec anneau de progression. Visible depuis la barre des tâches Windows.
2. **Notification système Windows** en fin de série et en cas d'échec. On la demande **au premier téléchargement terminé**, pas au lancement de l'appli.
3. **Indicateur global** dans l'en-tête, sur tous les écrans : anneau et « 2 en cours ». Un clic ouvre le panneau.
4. **Panneau Téléchargements** : tiroir à droite sur desktop, page dédiée sur mobile.
5. **Page série** : la grille d'épisodes se remplit en direct.

| # | Utilisateur | Système | Retour |
|---|---|---|---|
| 1 | Lance, puis change d'onglet ou d'application | Téléchargement : une série à la fois, 3 épisodes en parallèle | Titre d'onglet et favicon mis à jour |
| 2 | (optionnel) Clic sur l'indicateur | Ouvre le panneau sans quitter l'écran courant | Ligne : cover, titre et version, barre en **épisodes**, « 34/62 · 18 Mo/s · environ 40 s » |
| 3 | (optionnel) Pause, Annuler, Monter/Descendre dans la file | Action immédiate | « En pause par toi · 34/62 » avec [Reprendre] |
| 4 | — | Fin de la série | Notification « One Night to Forever (VF) est prêt · 62 épisodes vérifiés, 684 Mo ». La ligne passe dans « Terminés récemment » avec [Regarder] et [Créer le film]. |

**Règles** :
- L'unité de progression est l'**épisode**, les octets restent secondaires.
- Le temps restant est arrondi (« moins d'une minute », « environ 2 min »).
- La barre ne **recule jamais**.
- Un échec ne bloque pas la série : les autres épisodes continuent et les échecs sont comptés à part.
- La file se réordonne aussi **sans glisser-déposer**, avec des boutons Monter/Descendre (WCAG 2.5.7).

### (c) Retrouver une série parmi 50 et plus

**Cibles** : **3 interactions au plus**, moins de **5 s**, résultats **à chaque frappe** en moins de 100 ms (index local).

| # | Utilisateur | Système |
|---|---|---|
| 1 | `/` ou Ctrl+K (ou clic sur la recherche) | Focus sur la recherche |
| 2 | Tape « lafont » | Filtrage instantané sur les titres VO, VF et VE et le n° de série. Mention « trouvé dans le titre VF ». |
| 3 | Entrée (ou flèches puis Entrée) | Ouvre la série |

- **Filtres** (puces, cumulables) : Statut (Complètes / Incomplètes / Avec échecs / En cours) · Film (Film prêt / Sans film) · Version (VO, VF, VE…) · Qualité (1080p / 720p / 540p / Mélangée).
- **Tri** : Ajoutées récemment (par défaut) · Regardées récemment · Titre A→Z · Taille · Durée · Nombre d'épisodes.
- **Vues** : **Affiches** (par défaut) ou **Liste dense** avec les colonnes titre, versions, épisodes, durée, taille, film, date d'ajout. La vue dense est faite pour le power user à 50 séries et plus.
- **Rangées intelligentes** en tête, affichées seulement si elles ne sont pas vides : **« À traiter (3) »** (échecs, incomplètes, interrompues) et **« Continuer à regarder »**.
- Filtres, tri et vue sont **mémorisés et reflétés dans l'URL**, pour que le bouton Retour fonctionne. Compteur « 12 séries sur 54 » avec [Effacer les filtres].
- Si ce qu'on tape ressemble à un lien ou à un n° de série : « Ça ressemble à un lien DramaBox » avec [Ajouter cette série].

### (d) Gérer une série

**Structure de la page série** :
1. En-tête : cover, titre, titre VO, synopsis repliable, méta (« 62 épisodes · 1 h 32 · 1080p · 684 Mo »).
2. Onglets de versions : `VO (anglais)` · `VF` · `+ Ajouter une version`.
3. **Résumé de santé**, avec **une seule action principale contextuelle**.
4. Grille d'épisodes, dont la légende sert aussi de filtre (voir plus bas).
5. Section Film.
6. Fichiers : chemin, taille, [Ouvrir le dossier], [Supprimer…].
7. « Détails techniques » repliés : n° de série, source, qualité par épisode, expiration des liens, chemin complet, commande CLI, [Copier les liens] (équivalent de `links`), [Exporter en JSON].

**Action principale selon l'état** :

| État de la version | Bouton principal |
|---|---|
| Échecs | **Réessayer les 2 épisodes en échec** |
| Incomplète (épisodes jamais demandés) | **Télécharger les 4 épisodes manquants** |
| En cours | **Mettre en pause** |
| Interrompue | **Reprendre (34/62)** |
| Complète sans film | **Créer le film** |
| Complète avec film | **Regarder le film**, ou **Reprendre · Ép. 14** si un visionnage est en cours |

**Grille d'épisodes** :
- Chaque tuile fait au moins 44×44 px et affiche « 14 » avec une icône d'état. Le bord et la couleur sont redondants avec l'icône.
- La légende au-dessus de la grille donne les compteurs : « Téléchargé 58 · En cours 2 · Échec 2 · Non téléchargé 0 ». **Cliquer sur une entrée de la légende filtre la grille.**
- **Clic sur une tuile = l'action la plus utile pour son état** : téléchargé → regarder ; en échec → volet de détail avec la raison et [Réessayer] ; non téléchargé → [Télécharger cet épisode].
- Sélection multiple : Maj+clic, Ctrl+clic, ou Espace au clavier. Le menu contextuel (clic droit, bouton « … » ou touche Menu) propose : Regarder, Réessayer, Retélécharger en 1080p, Afficher dans le dossier.

| Sous-tâche | Chemin | Interactions |
|---|---|---|
| d1 Réessayer les échecs | Bouton principal de la page, ou action directe sur la carte « À traiter » en bibliothèque | 1 |
| d2 Compléter une série | Bouton principal | 1 |
| d3 Retélécharger un épisode précis | Tuile → menu → « Retélécharger » | 2 (3 en sélection multiple) |
| d4 Ajouter une autre version | « + Ajouter une version » → VF → « Tout télécharger » | 3 |
| d5 Créer le film | « Créer le film » ; +1 si un choix est requis (film partiel ou ré-encodage) | 1-2 |
| d6 Ouvrir le dossier | [Ouvrir le dossier] → Explorateur Windows (fichier présélectionné si on part d'un épisode) | 1 |
| d7 Supprimer | [Supprimer…] → portée (Film seul / Épisodes seuls / Tout, avec la place libérée) → [Supprimer] → toast [Annuler] pendant 10 s. Envoi vers la **Corbeille** de Windows. | 3 |
| d8 Harmoniser la qualité | Depuis l'erreur « qualités mélangées » : [Retélécharger 2 épisodes en 1080p] | 1 |

### (e) Regarder un épisode ou le film

**Cibles** : **1 interaction** depuis la bibliothèque (« Reprendre · Ép. 14 » sur la carte, au survol, au focus ou dans « Continuer à regarder ») ; **1** depuis la grille.

- **Lecteur vertical 9:16**, centré et ajusté à la hauteur. Sur desktop, la liste des épisodes est à droite, avec l'état « vu » et une barre de progression par épisode.
- **Enchaînement automatique** : « Épisode suivant dans 5 s » avec [Annuler]. Avec reduced-motion, le décompte est affiché en texte seul, sans animation.
- **Position mémorisée** par épisode et pour le film.
- **Film** : chapitres marqués sur la barre de lecture et listés à droite (« Épisode 1 », « Épisode 2 »…).
- [Ouvrir dans le lecteur par défaut] (VLC, MPC-HC…) sur desktop uniquement.
- Mobile : plein écran natif.
- Clavier : `Espace`/`K` lecture/pause · `←`/`→` 5 s · `Maj+←`/`Maj+→` épisode ou chapitre précédent/suivant · `F` plein écran · `M` muet · `Échap` quitter.
- Dépendance moteur : **stocker la progression de visionnage** (le manifest actuel ne le fait pas).

### (f) Reprendre après fermeture de l'appli ou coupure réseau

| Scénario | Comportement | Interactions |
|---|---|---|
| f1 · Onglet ou navigateur fermé, moteur toujours actif | Les téléchargements **continuent**. À la réouverture, l'état est exact. | 0 |
| f2 · Moteur arrêté, PC éteint ou en veille | Au démarrage, le moteur relit les manifests et passe les épisodes « en cours » à « Interrompu ». Bandeau : « 2 téléchargements ont été interrompus (34/62 et 0/48). » avec [Tout reprendre] et [Voir]. Réglage « Reprendre automatiquement au démarrage ». | 1 (0 avec le réglage) |
| f3 · Coupure Internet en cours de téléchargement | File en **pause automatique** « Hors ligne », **aucun échec compté**. Nouveaux essais à 5 s, 15 s, 30 s puis toutes les 60 s, avec « Nouvel essai dans 12 s » et [Réessayer maintenant]. Reprise automatique au retour, là où chaque fichier s'était arrêté. Bibliothèque, lecteur et film restent **pleinement utilisables** (tout est local). | 0 |
| f4 · Moteur injoignable (fenêtre du moteur fermée) | La page déjà ouverte garde le dernier état connu en **lecture seule**, avec un bandeau et une reconnexion automatique toutes les 5 s. | 0 à 1 |
| f5 · Lien expiré (plus de 3 semaines) | Re-résolution automatique, invisible. Si elle échoue : épisode en échec avec [Réessayer]. | 0 (1 si échec) |
| f6 · Fichier supprimé à la main dans l'Explorateur | Au scan suivant, l'épisode passe en « Fichier manquant » avec [Retélécharger]. Dépend de `sdg verify` (roadmap 4b). | 1 |

### Récapitulatif des cibles

| Parcours | Interactions cibles | Temps cible |
|---|---|---|
| (a) URL → tout télécharger | 3 (2 au clavier) | Aperçu < 2 s ; retour < 1 s après le clic |
| (b) Connaître l'avancement | 0 (détail : 1) | Visible en périphérie en permanence |
| (c) Retrouver une série | ≤ 3 | < 5 s |
| (d) Réparer ou compléter | 1 | — |
| (d) Créer le film | 1-2 | Environ 6 s |
| (e) Reprendre le visionnage | 1 | Lecture < 1 s |
| (f) Reprendre après coupure | 0-1 | Automatique au retour du réseau |

---

## 3. Matrice complète des états d'interface

**Règles de microcopy** :
- Tutoiement.
- Structure en trois temps : **ce qui s'est passé**, puis **ce qu'on fait**, puis **ce que tu peux faire**.
- Boutons formulés comme des verbes d'action (« Réessayer les 2 épisodes », jamais « OK »).
- Nombres à la française : « 684 Mo », « 1 h 32 », « 1 min 38 s », avec une espace insécable avant « : ? ! » et des guillemets « ».
- Aucun code HTTP ni terme réseau dans le message principal. La cause brute est copiable dans « Détails techniques ».
- Les actions désactivées **disent pourquoi**, pas seulement en grisé.

« n/a » signale un état qui ne peut pas exister, avec la raison. Chaque cellule reste ainsi traitée.

### A. Coquille globale (en-tête, navigation, indicateur de téléchargements, bandeaux)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | En-tête et navigation. L'indicateur de téléchargements est **masqué** (on n'affiche pas « 0 en cours »). | — |
| Chargement | Logo et barre fine indéterminée (statique si reduced-motion) | « Démarrage de ShortDramaGen… » ; au-delà de 3 s : « Lecture de ta bibliothèque… 23 séries trouvées » |
| Succès | Indicateur actif | « 2 en cours · 34/62 » ; en fin de série : « Terminé », affiché 5 s puis masqué |
| Partiel | Indicateur avec pastille d'alerte | « 1 en cours · 2 échecs » |
| Erreur | Bandeau rouge persistant, interface en lecture seule | « Le moteur ne répond plus. Tes téléchargements sont peut-être arrêtés. On essaie de se reconnecter… » [Réessayer maintenant] · aide : « Si tu as fermé la fenêtre du moteur, relance ShortDramaGen. » |
| Hors ligne | Bandeau discret non bloquant | « Hors ligne. Ta bibliothèque et tes vidéos restent disponibles ; les téléchargements reprendront tout seuls. » · au retour : toast « De retour en ligne. Reprise des téléchargements. » |

### B. Champ « Ajouter une série »

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Champ, placeholder et aide | Placeholder : « Colle un lien DramaBox ou un n° de série » · aide : « Astuce : Ctrl+V fonctionne n'importe où dans l'appli. » |
| Chargement | Icône de progression dans le champ | « Lien reconnu. Recherche de la série… » |
| Succès | Coche verte, aperçu en dessous | « Série trouvée » |
| Partiel | Avertissement jaune | Plusieurs liens : « 2 liens reconnus sur 3. La ligne 2 n'est pas un lien DramaBox. » · lien d'épisode : « C'est le lien de l'épisode 14 : on te propose toute la série. » |
| Erreur | Bord et texte en danger, focus conservé dans le champ | « Ce lien n'est pas reconnu. Liens acceptés : dramaboxdb.com, dramabox.com, lien de partage de l'app DramaBox, dramafren, ou le n° de série (ex. 41000105199). » · presse-papiers : « Le presse-papiers est vide ou inaccessible. Colle le lien avec Ctrl+V dans ce champ. » |
| Hors ligne | Champ actif | « Hors ligne : on gardera ce lien et on l'analysera dès le retour de la connexion. » [Garder pour plus tard] |

### C. Aperçu de la série (avant téléchargement)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Zone réservée sous le champ | « L'aperçu de la série s'affichera ici. » |
| Chargement | Squelette : affiche 9:16, 3 lignes de texte, bouton inactif | « Recherche de la série… » ; au-delà de 4 s : « Le site officiel met du temps à répondre… » · mode sonde : « Série absente du site officiel. Recherche des épisodes à la source… 23 trouvés » |
| Succès | Cover, titres, synopsis, méta, versions, bouton principal focalisé | « 62 épisodes · 1 h 32 · environ 700 Mo en 1080p » · [Tout télécharger · 62 épisodes] · [Options] |
| Partiel | Aperçu complet avec une note | Mode sonde : « Infos limitées : cette série n'est pas sur le site officiel. On a trouvé 48 épisodes, mais on ne pourra pas vérifier leur durée. » · langue : « Pas de version française pour cette série. Versions disponibles : VO (anglais), VE. » · doublon : « Déjà dans ta bibliothèque : VF complète (62/62). » [Ouvrir] [Ajouter la VO] · cover absente : affiche générée avec le titre |
| Erreur | Message et action, champ refocalisable | Introuvable : « On n'a trouvé cette série ni sur le site officiel ni à la source. Vérifie le lien ou essaie avec le n° de série (11 chiffres). » · réseau : « Impossible de joindre DramaBox. Vérifie ta connexion puis réessaie. » [Réessayer] |
| Hors ligne | Pas d'aperçu | « Tu es hors ligne : l'aperçu a besoin d'Internet. » [Garder le lien pour plus tard] |

### D. Panneau et page Téléchargements (file d'attente)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Illustration légère et action | « Aucun téléchargement en cours. Colle un lien pour en lancer un. » [Ajouter une série] |
| Chargement | Lignes squelettes (moins de 1 s) | Lecteur d'écran : « Chargement des téléchargements… » |
| Succès | Lignes actives, puis « Terminés récemment » | Active : « 34/62 · 18 Mo/s · environ 40 s » · en file : « En file · démarre après One Night to Forever » · en pause : « En pause par toi · 34/62 » [Reprendre] · terminée : « One Night to Forever (VF) · 62/62 vérifiés · 684 Mo · 1 min 38 s » [Regarder] [Créer le film] · [Effacer la liste (tes fichiers restent)] |
| Partiel | Ligne avec compteur d'échecs | « Terminé avec 2 échecs (épisodes 14 et 40). » [Réessayer les 2] · interrompue : « Interrompu · 34/62. Reprend là où il s'était arrêté. » [Reprendre] |
| Erreur | Ligne arrêtée, bord en danger | Disque : « Arrêté : disque plein (il manque 312 Mo sur D:). Libère de la place puis reprends. » [Reprendre] · répété : « Arrêté après plusieurs erreurs de suite. Vérifie ta connexion, puis reprends. » [Reprendre] [Détails techniques] |
| Hors ligne | Toutes les lignes en pause | En-tête : « Hors ligne. Reprise automatique au retour de la connexion. Nouvel essai dans 12 s. » [Réessayer maintenant] · ligne : « En pause · hors ligne » |

### E. Tuile d'épisode (grille) et volet de détail

| État | Tuile (visible) | Nom accessible et microcopy du volet |
|---|---|---|
| Vide | « 14 », contour pointillé | « Épisode 14, 2 min 05, non téléchargé » · volet : [Télécharger cet épisode] |
| Chargement | « 14 », remplissage progressif, « 45 % » | « Épisode 14, en cours, 45 % » · en attente : « Épisode 14, en attente » |
| Succès | « 14 » et coche | « Épisode 14, 2 min 05, téléchargé et vérifié, 13,2 Mo, 1080p » · volet : [Regarder] [Afficher dans le dossier] |
| Partiel | « 14 » et icône « non vérifié » ou badge « 720p » | « Épisode 14, téléchargé, durée non vérifiable » · qualité : « Épisode 14, téléchargé en 720p (le reste de la série est en 1080p) » [Retélécharger en 1080p] · interrompu : « Interrompu à 40 %. » [Reprendre] |
| Erreur | « 14 », triangle, bord en danger | Indisponible : « Cet épisode n'est pas disponible à la source pour le moment. Réessaie plus tard. » [Réessayer] · intégrité : « Le fichier reçu ne correspond pas : 1 min 12 au lieu de 2 min 05. » [Réessayer] · fichier absent : « Le fichier n'est plus dans le dossier. » [Retélécharger] |
| Hors ligne | « 14 », icône pause | « Épisode 14, en pause, hors ligne. Reprise automatique. » |

### F. Bibliothèque (grille d'affiches ou liste dense)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Écran d'accueil : champ centré et focalisé | « Ta bibliothèque est vide. Colle le lien d'une série DramaBox : on récupère tous les épisodes, vérifiés, jusqu'en 1080p. » · aide : « Tes séries apparaîtront ici, avec leurs épisodes, leurs versions et leurs films. » |
| Chargement | Affiches squelettes 9:16 (sans shimmer si reduced-motion) | « Lecture de ta bibliothèque… » |
| Succès | Rangées « À traiter » et « Continuer à regarder », puis la grille | « 54 séries · 38,4 Go · 120 Go libres sur D: » |
| Partiel | Grille et note | « 2 dossiers n'ont pas pu être lus et sont masqués. » [Voir lesquels] · cover manquante : affiche générée avec le titre |
| Erreur | Message plein écran | « Impossible d'ouvrir ton dossier de séries (D:\Séries). Il a peut-être été déplacé, ou le disque est débranché. » [Choisir un autre dossier] [Réessayer] |
| Hors ligne | Identique au succès (tout est local, covers en cache) | Le bouton Ajouter indique : « Hors ligne : ajout possible, analyse au retour de la connexion. » |

### G. Carte de série (bibliothèque)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | n/a | Une carte n'existe que si une version est connue |
| Chargement | Fine barre en bas de l'affiche | « En cours · 34/62 » · en file : « En file » |
| Succès | Badges de versions et badge film | « 62 ép. · 1 h 32 » · « VO · VF » · « Film prêt » · action au survol ou au focus : [Reprendre · Ép. 14] |
| Partiel | Badge jaune | « 58/62 » · « Film partiel » · « Interrompu · 34/62 » |
| Erreur | Pastille rouge et action directe | « 2 échecs » [Réessayer] |
| Hors ligne | Identique ; les actions réseau indiquent la raison | « Réessayer au retour de la connexion » |

### H. Recherche, filtres et tri

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Champ et puces de filtres | « Rechercher un titre (VO, VF, VE…) ou un n° de série » |
| Chargement | n/a en pratique (index local instantané) ; au-delà de 300 ms, indicateur discret | « Recherche… » |
| Succès | Résultats avec le terme surligné | « 3 séries pour « lafont » » · « Trouvé dans le titre VF » |
| Partiel | Aucun résultat avec les filtres, mais des résultats sans eux | « Aucune série ne correspond à « lafont » avec les filtres Complètes · VE. 1 résultat sans ces filtres. » [Effacer les filtres] |
| Erreur | Aucun résultat, ou index indisponible | « Aucune série « lafont » dans ta bibliothèque. » · ressemble à un lien : « Ça ressemble à un lien DramaBox. » [Ajouter cette série] · index : « La recherche ne marche pas pour le moment. Toutes tes séries restent listées ci-dessous. » |
| Hors ligne | Identique (local) | — |

### I. Page série : en-tête et résumé de santé

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Série connue, 0 épisode | « Aucun épisode téléchargé pour l'instant. » [Tout télécharger · 62 épisodes] |
| Chargement | Squelette de l'en-tête et de la grille | Lecteur d'écran : « Chargement de la série… » |
| Succès | Coche et méta | « 62/62 épisodes téléchargés et vérifiés · 1 h 32 · 684 Mo · 1080p » · action : [Créer le film] ou [Regarder] |
| Partiel | Bandeau jaune et action principale | « 58/62 épisodes · 4 manquants (59 à 62). » [Télécharger les 4 manquants] · sonde : « Durées non vérifiées : cette série n'est pas sur le site officiel. » · qualités : « 60 épisodes en 1080p, 2 en 720p. » |
| Erreur | Bandeau rouge | « 2 épisodes en échec (14 et 40). » [Réessayer les 2] · dossier : « Le dossier de cette version est introuvable (déplacé ou supprimé en dehors de l'appli). » [Le retrouver…] [Retélécharger] [Retirer de la bibliothèque] |
| Hors ligne | Actions réseau désactivées avec leur raison | « Disponible au retour de la connexion » ; Regarder, Film et Dossier restent actifs |

### J. Versions (langues)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Une seule version | Onglet `VO (anglais)` et [+ Ajouter une version] |
| Chargement | Menu en cours | « Recherche des versions disponibles… » |
| Succès | Onglets et menu d'ajout | `VO` · `VF` · « VE disponible · environ 700 Mo » [Télécharger] |
| Partiel | Langues sans doublage désactivées, avec la raison | « Coréen : titre traduit seulement, pas de version doublée. » |
| Erreur | Menu en erreur | « Impossible de vérifier les versions disponibles. » [Réessayer] |
| Hors ligne | Versions locales actives, ajout désactivé | « Ajouter une version : disponible au retour de la connexion. » |

### K. Film (section et création)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Encart et bouton | « Pas encore de film. Réunis les 62 épisodes en un seul fichier (1 h 32, un chapitre par épisode), en quelques secondes. » [Créer le film] |
| Chargement | Progression dans le bouton, sans modale | « Création du film… 38/62 épisodes assemblés » |
| Succès | Carte du film | « Film prêt : Qui Est la Véritable Mme Lafont.mp4 · 1 h 32 · 717 Mo · 62 chapitres » [Regarder] [Afficher dans le dossier] |
| Partiel | Film partiel, ou choix requis | Existant : « Film partiel (épisodes 1-10). 52 épisodes ont été ajoutés depuis. » [Recréer le film complet] · manquants : « Il manque 2 épisodes (61 et 62). » [Les télécharger puis créer le film] [Créer un film partiel (épisodes 1-60)] |
| Erreur | Explication et choix | ffmpeg : « Pour créer un film, il faut ffmpeg (l'outil qui assemble les vidéos). Tout le reste marche sans. » [Installer ffmpeg] · qualités : « Les épisodes 12 et 40 sont en 720p, les autres en 1080p. Pour un film sans perte en quelques secondes, retélécharge-les en 1080p. » [Retélécharger 2 épisodes en 1080p] [Créer quand même (ré-encodage, plusieurs minutes)] · durée : « Le film créé n'a pas la durée attendue (1 h 29 au lieu de 1 h 32). » [Réessayer] [Détails techniques] |
| Hors ligne | Identique au succès (ffmpeg est local) | Seule l'installation de ffmpeg demande Internet : « Installation possible au retour de la connexion. » |

### L. Lecteur vidéo

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Fichier absent | « Ce fichier n'est plus dans le dossier. » [Retélécharger l'épisode] |
| Chargement | Cover en fond et indicateur | Lecteur d'écran : « Chargement de l'épisode 14… » |
| Succès | Lecture, liste d'épisodes et chapitres | « Épisode 14 sur 62 » · fin : « Épisode suivant dans 5 s » [Annuler] · reprise : « Reprise à 1:12 » [Revenir au début] |
| Partiel | Épisode pas encore prêt, ou série incomplète | « Cet épisode est encore en téléchargement (45 %). Il sera lisible dès qu'il sera terminé. » · « Épisode 59 non téléchargé : on passe au 60. » |
| Erreur | Lecture impossible | « Ton navigateur n'arrive pas à lire cette vidéo. » [Ouvrir dans le lecteur par défaut] |
| Hors ligne | Identique (fichiers locaux) | — |

### M. Suppression (dialogue)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | n/a | Le dialogue ne s'ouvre que sur une série existante |
| Chargement | Bouton en cours | « Suppression… » |
| Succès | Toast avec annulation (10 s) | Dialogue : « Que veux-tu supprimer ? » ( ) « Seulement le film (717 Mo) » ( ) « Seulement les épisodes (684 Mo) : le film reste » ( ) « Tout : épisodes, film et dossier (1,4 Go) » · note : « Tout ira dans la Corbeille de Windows. » [Supprimer] [Annuler] · toast : « Supprimé. » [Annuler] |
| Partiel | Toast d'avertissement | « 60 fichiers supprimés sur 62. 2 sont ouverts dans un autre programme. » [Voir lesquels] |
| Erreur | Message dans le dialogue | « Impossible de supprimer E014.mp4 : il est ouvert dans un autre programme (VLC ?). Ferme-le, puis réessaie. » [Réessayer] |
| Hors ligne | Identique (action locale) | — |

### N. Réglages (dossier, préférences, ffmpeg, espace disque)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Valeurs par défaut | « Dossier : …\downloads · Qualité : Meilleure (1080p) · Version préférée : VO · Téléchargements simultanés : 3 (recommandé) » |
| Chargement | Ligne ffmpeg | « Vérification de ffmpeg… » · installation : « Installation de ffmpeg… » |
| Succès | Confirmation en ligne | « Enregistré. » · « ffmpeg est prêt. » |
| Partiel | Avertissement | Plus de 3 simultanés : « Au-delà de 3, la source risque de te bloquer temporairement. » · espace : « Il reste 4 Go sur D:, soit environ 6 séries en 1080p. » |
| Erreur | Champ en erreur | Dossier : « Ce dossier n'est pas accessible en écriture. Choisis-en un autre. » · ffmpeg : « L'installation a échoué. » [Réessayer] [Méthode manuelle : winget install Gyan.FFmpeg] |
| Hors ligne | Installation de ffmpeg désactivée | « Installation possible au retour de la connexion. » |

### O. Notifications (toasts et notifications Windows)

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Aucune | — |
| Chargement | Demande de permission, au premier téléchargement terminé | « Te prévenir quand un téléchargement est fini, même si l'appli est en arrière-plan ? » [Oui, me prévenir] [Non merci] |
| Succès | Notification Windows | « One Night to Forever (VF) est prêt · 62 épisodes vérifiés, 684 Mo » |
| Partiel | Notification | « One Night to Forever : terminé avec 2 échecs. Clique pour réessayer. » |
| Erreur | Notification (arrêts bloquants seulement) | « Téléchargements arrêtés : disque plein sur D:. » |
| Hors ligne | Une seule notification, pas une par épisode | « Connexion perdue : téléchargements en pause, reprise automatique. » |

### P. Démarrage et reprise

| État | Ce qu'on voit | Microcopy |
|---|---|---|
| Vide | Premier lancement : vérification rapide sans assistant | « Tout est prêt. Colle un lien pour commencer. » · ffmpeg absent : note discrète « Films : ffmpeg manquant » [Installer] |
| Chargement | Scan des dossiers | « Lecture de ta bibliothèque… 23 séries trouvées » |
| Succès | Rien à reprendre | — (aucun message inutile) |
| Partiel | Bandeau de reprise | « 2 téléchargements ont été interrompus (34/62 et 0/48). » [Tout reprendre] [Voir] · case « Reprendre automatiquement la prochaine fois » |
| Erreur | Moteur absent | « Impossible de démarrer le moteur ShortDramaGen. » [Réessayer] [Détails techniques] |
| Hors ligne | Bibliothèque disponible, reprise différée | « Hors ligne : les 2 téléchargements interrompus reprendront au retour de la connexion. » |

---

## 4. Catalogue des erreurs (cause technique → ce qu'on affiche)

| Cause (moteur) | Automatique ? | Message affiché | Action proposée |
|---|---|---|---|
| URL invalide | — | « Ce lien n'est pas reconnu. Liens acceptés : … » | Corriger (focus dans le champ) |
| Série absente du site officiel (mode sonde) | Oui, bascule sur la source | « Infos limitées… durées non vérifiables » | Continuer |
| Série introuvable partout | — | « On n'a trouvé cette série ni sur le site officiel ni à la source. » | Vérifier le lien, essayer le n° de série |
| Langue indisponible (repli VO) | **Évitée en amont** | « Pas de version française pour cette série. Versions disponibles : … » | Choisir une version disponible |
| Épisode indisponible à la source | Essai de la source suivante | « Cet épisode n'est pas disponible à la source pour le moment. » | [Réessayer] |
| URL signée expirée | Oui, re-résolution | (rien) ; en cas d'échec : « Lien de téléchargement expiré, et impossible d'en obtenir un nouveau pour l'instant. » | [Réessayer] |
| Échec d'intégrité (durée) | — | « Le fichier reçu ne correspond pas : 1 min 12 au lieu de 2 min 05. » | [Réessayer] |
| Mauvais épisode renvoyé (chemin CDN) | Oui, source suivante | (rien) ; en cas d'échec : « La source a renvoyé une vidéo qui n'est pas cet épisode. » | [Réessayer] |
| Erreur réseau ponctuelle | Oui, nouvel essai | (rien tant que ça se règle) | — |
| Hors ligne | Oui, pause puis reprise | « Hors ligne. Reprise automatique… » | [Réessayer maintenant] |
| Interruption (fermeture, veille) | Reprise `.part` | « Interrompu · 34/62. Reprend là où il s'était arrêté. » | [Reprendre] |
| ffmpeg absent | — | « Pour créer un film, il faut ffmpeg… » | [Installer ffmpeg] / méthode manuelle |
| Qualités mélangées | — | « Les épisodes 12 et 40 sont en 720p… » | [Retélécharger en 1080p] / [Créer quand même (ré-encodage)] |
| Épisodes manquants pour le film | — | « Il manque 2 épisodes (61 et 62). » | [Les télécharger puis créer] / [Film partiel] |
| Plusieurs langues = plusieurs dossiers | UI regroupe | (aucune erreur : une série, plusieurs versions) | — |
| *À prévoir* : disque plein | Arrêt de la file | « Arrêté : disque plein (il manque 312 Mo sur D:). » | [Reprendre] |
| *À prévoir* : fichier ouvert ailleurs | — | « … est ouvert dans un autre programme (VLC ?). » | [Réessayer] |
| *À prévoir* : dossier déplacé ou supprimé | Au scan | « Le dossier de cette version est introuvable. » | [Le retrouver…] / [Retélécharger] / [Retirer] |
| *À prévoir* : moteur injoignable | Reconnexion | « Le moteur ne répond plus… » | [Réessayer maintenant] |

Chaque message d'erreur comporte un lien « Détails techniques » qui déplie la cause brute (message du moteur, n° de série, épisode, URL, horodatage) et un bouton [Copier].

---

## 5. Accessibilité (WCAG 2.2 niveau AA)

### 5.1 Contraste : palette sombre proposée, ratios calculés

| Jeton | Valeur | sur `bg` #0B1220 | sur `surface` #131C2E | sur `raised` #1B2640 | Usage |
|---|---|---|---|---|---|
| `text` | #E8ECF4 | 15,8:1 | 14,4:1 | 12,7:1 | Texte principal |
| `text-muted` | #A3AEC4 | 8,4:1 | 7,6:1 | 6,7:1 | Méta, aides |
| `accent` | #5B9BFF | 6,8:1 | 6,1:1 | 5,4:1 | Liens, états actifs |
| `success` | #3DD68C | 10,0:1 | 9,1:1 | 8,0:1 | Téléchargé / vérifié |
| `warning` | #F5B544 | 10,3:1 | 9,4:1 | 8,3:1 | Partiel |
| `danger` | #FF6B6B | 6,8:1 | 6,1:1 | 5,4:1 | Échec |
| `focus` | #8FC1FF | 10,0:1 | 9,1:1 | 8,0:1 | Anneau de focus |
| `border-control` | #6A7A99 | 4,3:1 | 3,9:1 | 3,5:1 | Contours de champs et tuiles (≥ 3:1, critère 1.4.11) |

- **Bouton principal** : texte `#0B1220` sur `#5B9BFF`, soit 6,8:1. Le **texte blanc sur cet accent est interdit** (2,8:1). Si on veut un bouton à texte blanc, il faut un accent `#2F6FE0` (4,7:1).
- **Anneau de focus** : 2 px de `focus` avec 2 px de décalage sur le fond. Sans ce décalage, l'anneau ne contraste pas avec un bouton accent (1,5:1).
- **Texte posé sur une cover** : toujours au-dessus d'un voile sombre (dégradé `#0B1220` à 85 %), jamais directement sur l'image.
- **Jamais la couleur seule** (critère 1.4.1) : chaque état d'épisode ou de série combine une **icône**, une **forme de bord** (pointillé, plein, épais) et un **texte** ou nom accessible.
- **Mode Contraste élevé de Windows** : gérer `forced-colors: active`. Les états se distinguent par des bordures et des icônes système, et les barres de progression gardent un contour visible.

### 5.2 Focus et clavier

- Focus visible partout (2.4.7), et **jamais masqué** par l'en-tête collant, le panneau Téléchargements ou un toast (2.4.11) : utiliser `scroll-padding-top` et faire en sorte que les toasts ne recouvrent pas la zone de focus.
- Lien d'évitement « Aller au contenu ». Ordre de tabulation : en-tête, action principale, contenu.
- **Grille d'épisodes** : un seul arrêt de tabulation, puis déplacement aux flèches (roving tabindex, `role="grid"`). `Début`/`Fin` pour la première et la dernière tuile. `Entrée` = action de la tuile, `Espace` = sélectionner, `Maj+flèches` = sélection étendue, touche Menu ou `Maj+F10` = menu contextuel.
- Raccourcis globaux : `A` ajouter · `/` ou `Ctrl+K` rechercher · `T` téléchargements · `?` aide des raccourcis · `Échap` fermer. **Les raccourcis à une touche sont inactifs dans les champs et peuvent être désactivés** dans les réglages (2.1.4). Ctrl+V hors champ ouvre l'ajout.
- Dialogues : focus piégé à l'intérieur, retour du focus sur l'élément d'origine à la fermeture. Après un changement de contenu (comme « Tout télécharger »), le focus reste à un endroit prévisible (3.2.2).
- Glisser-déposer (file, lien) toujours doublé d'une alternative par boutons (2.5.7).
- Aucune action n'existe **uniquement au survol** : les actions de carte apparaissent aussi au focus et restent accessibles au tactile.

### 5.3 Cibles tactiles et pointeur

- **44×44 px minimum** pour toutes les cibles (au-delà du minimum AA de 24 px en 2.5.8, on vise 2.5.5). Cela inclut les tuiles d'épisodes, les puces de filtre, les boutons Pause/Annuler et les contrôles du lecteur.
- Au moins 8 px entre deux cibles destructives et leurs voisines (Annuler ou Supprimer, par exemple).

### 5.4 Lecteurs d'écran et progression

- **Barre de progression** : `role="progressbar"`, avec `aria-valuenow`/`max` et un `aria-valuetext` parlant, par exemple « 34 épisodes sur 62, environ 40 secondes restantes ».
- **Une seule région live** `role="status"` (`aria-live="polite"`) pour les téléchargements. Annonces **limitées** : au démarrage (« Téléchargement lancé : One Night to Forever, 62 épisodes »), à 25, 50 et 75 %, à la fin (« 62 épisodes téléchargés et vérifiés »), et à chaque nouvel échec regroupé (« 2 épisodes en échec »). Au moins 10 s entre deux annonces, **jamais une annonce par épisode**. Réglage : « Annonces : paliers / fin seulement / aucune ».
- `role="alert"` réservé aux erreurs bloquantes (moteur injoignable, disque plein).
- Messages d'état sans déplacer le focus (4.1.3). Erreurs de saisie liées au champ par `aria-describedby`, avec une suggestion de correction (3.3.1 et 3.3.3).
- **Noms accessibles complets** pour les tuiles et les cartes (voir la section E de la matrice) : l'information visible (« 14 » et une icône) est enrichie pour le lecteur d'écran.
- **Attribut `lang`** sur les titres dans une autre langue (`lang="es"` pour « Una Noche Para Siempre », `lang="ko"`, `lang="ja"`…) pour une prononciation correcte. `lang="fr"` sur la page.
- Covers : `alt=""` quand le titre est déjà affiché à côté (image décorative), sinon « Affiche de … ».
- Médias : DramaBox ne fournit aucun sous-titre aujourd'hui. On le signale (« Sous-titres non fournis par la source ») et on prévoit l'emplacement d'une piste de sous-titres.

### 5.5 Mouvement et temps

- `prefers-reduced-motion` : pas de shimmer sur les squelettes (aplat statique), pas de rayures animées sur les barres (mise à jour par paliers), pas de glissement des toasts ni des tiroirs (apparition directe), décompte « épisode suivant » en texte seul, aucune lecture automatique d'aperçu vidéo.
- Rien ne clignote plus de 3 fois par seconde. **Aucune limite de temps** imposée à l'utilisateur. Le toast « Annuler » (10 s) est prolongé tant qu'il a le focus ou qu'il est survolé, et l'action reste possible ensuite depuis la page de la série.

### 5.6 Zoom et reflow

- Utilisable à 200 % de zoom et en reflow à 320 px CSS de large sans défilement horizontal (1.4.10), sauf le lecteur vidéo.
- Respect des espacements de texte augmentés (1.4.12). Tailles en `rem`.

### 5.7 Aide cohérente et saisie redondante

- L'aide des raccourcis (`?`) et le lien « Détails techniques » sont toujours au même endroit (3.2.6).
- Langue, qualité, « film à la fin » et dossier sont **mémorisés** : on ne les redemande jamais (3.3.7).

---

## 6. Responsive

Points de rupture : **< 600 px** mobile · **600 à 1023** tablette · **1024 à 1365** laptop · **≥ 1366** desktop.

| Zone | Desktop 1440 | Laptop 1280 | Mobile 390 |
|---|---|---|---|
| Navigation | Barre latérale de 240 px (Bibliothèque, Téléchargements, Réglages) ; « Ajouter une série » dans l'en-tête | Barre latérale en icônes (72 px), libellés en infobulle et en nom accessible | **Barre du bas** : Bibliothèque · Ajouter · Téléchargements · Réglages (4 cibles de 44 px et plus) |
| Téléchargements | **Tiroir à droite** de 360 px, épinglable | Tiroir en surimpression | Page dédiée ; indicateur sur l'onglet de la barre du bas |
| Bibliothèque | Affiches 9:16 d'environ 160 px, **7 colonnes** ; liste dense disponible | **5 à 6 colonnes** | **3 colonnes** (environ 112 px) ; liste dense remplacée par une liste compacte (cover, titre, statut) |
| Recherche et filtres | Barre de recherche avec puces sur une ligne, tri à droite | Idem, puces repliées dans « Filtres (2) » si elles débordent | Recherche en haut ; filtres et tri dans une **feuille du bas** |
| Aperçu (ajout) | Panneau : cover à gauche, infos à droite | Idem | Cover réduite en haut, infos dessous, bouton principal **collé en bas de l'écran** ; bouton « Coller » |
| Page série | 2 colonnes : cover et méta (320 px) à gauche ; santé, grille et film à droite ; grille de **12 tuiles par ligne** | 2 colonnes (280 px), grille de **10 par ligne** | 1 colonne : en-tête compact, action principale collée en bas, grille de **6 par ligne** (tuiles de 52 px : 6×52 + 5×8 = 352 px pour 358 px utiles) |
| Lecteur | Vidéo verticale ajustée en hauteur, liste des épisodes et chapitres à droite | Idem, liste rétractable | Plein écran natif ; liste en feuille du bas |
| Actions desktop | [Ouvrir le dossier], [Ouvrir dans le lecteur par défaut], ffmpeg | Idem | **Masquées** (sans objet à distance) |
| Gouttières | 32 px | 24 px | **16 px**, aucun défilement horizontal |

---

## 7. Principes UX directeurs

1. **Une URL, un geste.** Le chemin nominal tient en 3 interactions au plus, avec des valeurs par défaut intelligentes : meilleure qualité, version préférée si elle existe, tous les épisodes. Tout le reste est replié dans « Options » et mémorisé. Le cas simple ne paie jamais pour le cas avancé.

2. **La série, pas le fichier.** L'unité mentale est la série, avec ses **versions** et son **film**. Dossiers, n° de série, manifest et liens signés existent, mais seulement dans « Détails techniques ». Les langues éclatées en dossiers par le moteur sont regroupées dans l'interface.

3. **La confiance se prouve.** Chaque épisode affiche s'il est **vérifié** (bon épisode, bonne durée). La complétude « 62/62 » est visible partout. Un « Terminé » n'apparaît que si tout l'est, et un fichier non vérifié ne ressemble jamais à un fichier vérifié.

4. **Le système répare, l'utilisateur décide.** Nouveaux essais, liens expirés, reprise après coupure : tout cela est automatique et silencieux. On ne dérange l'utilisateur que pour une **décision** (film partiel, ré-encodage, suppression), et chaque problème arrive avec son bouton de réparation.

5. **Tranquille en arrière-plan.** La progression se lit en périphérie (titre d'onglet, indicateur global, notification Windows). Aucune modale ne bloque, on ne change jamais d'écran de force, et on peut enchaîner les liens pendant que ça télécharge. Hors ligne, tout ce qui est local continue de marcher.

6. **Vertical d'abord.** Le contenu est en 9:16 : affiches portrait, lecteur vertical, grille d'épisodes compacte héritée de dramafren. La place libre en paysage sert au contexte (liste des épisodes, chapitres), pas à étirer la vidéo.

7. **Rien ne se perd, tout se contrôle.** Les suppressions passent par la Corbeille, avec [Annuler]. La reprise est idempotente. Filtres et préférences sont conservés. Et le power user garde la main : raccourcis, sélection d'épisodes, commande CLI équivalente, détails bruts copiables, à parité avec la CLI.

---

## 8. Dépendances côté moteur relevées par ce travail

Ce sont des points que l'architecture devra couvrir pour que ces parcours tiennent :

- Flux d'événements de progression (SSE ou WebSocket) : état par épisode, débit, temps restant.
- File multi-séries **persistée** : pause, reprise, annulation, réordonnancement.
- Indication « doublée : oui/non » pour chaque langue listée par le site.
- Compteur de progression en mode sonde.
- Statut de connectivité Internet mesuré **par le moteur** : `navigator.onLine` n'est pas fiable pour une page servie en local.
- Réconciliation au démarrage : `downloading` devient « Interrompu », et scan des fichiers manquants (`sdg verify`, roadmap 4b).
- Stockage de la progression de visionnage, et index de bibliothèque (titres toutes langues, tailles, dates).
- Cover enregistrée localement dans chaque dossier (bibliothèque utilisable hors ligne).
- Actions système : ouvrir le dossier ou le fichier dans l'Explorateur, envoyer à la Corbeille, ouvrir dans le lecteur par défaut, installer ffmpeg, espace disque libre.
- Service des MP4 locaux avec les requêtes `Range` pour le lecteur intégré.
- Accès depuis le réseau local désactivé par défaut, à activer explicitement (usage mobile).