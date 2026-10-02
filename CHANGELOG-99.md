# Changelog — Issue #99

## Coach : fiabilité 8 — suites sans leur premier coup, échange « de X contre Y »

Cas réel (20 appels réels, script de non-régression, 4 cas x 5 essais,
après la fusion des issues #94 à #98) : les quatre cas passent 5 fois sur
5, avec 3 relances. Lecture du journal des premières réponses (celles
ayant déclenché une relance) : deux faux positifs identifiés.

1. Cas bxh7 (exercice, question « et Bxh7+ ? ») : alerte `coup_illegal`
   sur la suite citée « Nxh7 Nxh7 Kxh7 », injouable depuis toutes les
   positions candidates — alors que « Bxh7+ » est cité juste avant, dans
   la même phrase (« Bxh7+ était jouable mais mauvais pour les Blancs :
   après Nxh7 Nxh7 Kxh7... »), et que la suite complète est légale depuis
   la position de départ. Le contrôle des suites illégales n'essayait un
   coup caché que pour une suite d'UN SEUL coup (issue #94) ; pour une
   suite de plusieurs coups, le coup précédent cité juste avant une
   parenthèse n'était cherché que pour une suite ENTRE PARENTHÈSES (issue
   #97) — ni l'un ni l'autre ne couvrait ce cas.
2. Cas c4 (exercice, meilleur coup Nf6) : alerte `echange_type_incoherent`
   sur « la ligne se poursuit avec Bxc6+ Qxc6, un échange de cavalier
   contre fou » — formulation correcte (le cavalier noir est échangé
   contre le fou blanc), signalée à tort car le contrôle n'existait que
   pour « échange de X » (chaque camp perd une pièce de CE type) et
   l'exigeait donc à tort des DEUX camps sur « cavalier », alors que seuls
   les Noirs perdent un cavalier (les Blancs perdent un fou).

### 1. Suites sans leur premier coup (`coach_reliability.py`)

- `_coup_precedent_cite` (ex-fonction limitée à une suite entre
  parenthèses, issue #97) généralisée : fenêtre élargie de 80 à 250
  caractères, et bornée désormais à AU PLUS une fin de phrase franchie en
  remontant (la phrase qui contient la suite, et celle qui la précède
  immédiatement — « même phrase ou phrase précédente »), au lieu de
  s'arrêter à la toute première fin de phrase rencontrée.
- `_extraire_suites` calcule désormais ce coup précédent pour TOUTE suite
  d'au moins deux coups (pas seulement entre parenthèses) qui n'est ni
  entre parenthèses ni hypothétique (« si... ») — cherché juste avant le
  DÉBUT de la suite elle-même dans ce cas.
- `detecter_suites_illegales` : le filet de sécurité « demi-coup caché
  quelconque » (issue #94), jusqu'ici limité à une suite d'UN SEUL coup,
  s'applique désormais à une suite de n'importe quelle longueur, via
  `_rassembler_lectures` (déjà utilisée par les contrôles de qualificatif
  depuis l'issue #97) — qui combine pour chaque position candidate (y
  compris trait inversé) : la lecture directe, la lecture avec le coup
  précédent cité inséré devant, puis, à défaut, un demi-coup caché
  quelconque inséré devant chacune de ces deux lectures. Une suite n'est
  signalée que si AUCUNE de ces lectures n'est valide nulle part.
  `_legal_apres_demi_coup_cache`, devenue redondante avec
  `_lectures_demi_coup_cache`, a été supprimée.
- Conséquence directe : la lecture ainsi trouvée (coup précédent ou
  demi-coup caché) est automatiquement réutilisée par les calculs
  matériels des autres contrôles de qualificatif (échange, bilan), qui
  appellent déjà `_rassembler_lectures` sur la même suite — aucun
  changement séparé nécessaire pour eux.

### 2. Échange « de X contre Y » (`coach_reliability.py`)

- `detecter_echange_type_incoherent` reconnaît désormais, en plus de la
  forme symétrique existante « échange de dames/tours/fous/cavaliers »
  (« du » ajouté aux articles reconnus), une forme ASYMÉTRIQUE : « échange
  de `<type1>` contre `<type2>` », « du `<type1>` contre le `<type2>` », ou
  simplement « `<type1>` contre `<type2>` » (nouvelle regex
  `_ECHANGE_TYPE_CONTRE_RE`), avec deux types de pièces DIFFÉRENTS.
- Pour cette forme, le contrôle accepte les deux sens (« le cavalier noir
  contre le fou blanc », ou l'inverse) : un camp doit perdre une pièce de
  type1 et l'AUTRE une pièce de type2, dans AU MOINS UNE lecture valide de
  la suite citée — ne signale que si aucune lecture, dans aucun sens, ne
  correspond.
- Si les deux types cités sont identiques (« cavalier contre cavalier »,
  « fou contre fou »), la forme asymétrique retombe sur l'ancienne règle
  symétrique (chaque camp doit perdre une pièce de ce type) — un « X
  contre X » affirme bien que les deux camps perdent un X.
- `_ECHANGE_DE_TYPE_RE` (forme symétrique, sans « contre ») exclut
  désormais, par un lookahead négatif, le cas où « contre `<type>` » suit
  immédiatement — pour ne jamais faire porter l'ancienne règle symétrique
  sur un « échange de X contre Y » qui relève de la nouvelle forme
  asymétrique.

### 3. Cas de non-régression (`tests/cas_coach/`)

- `bxh7_coup_interroge.case` : nouveau `reponse_simulee_verte` reprenant
  le texte exact du cas réel ci-dessus (« Bxh7+ ... Dans la position de
  départ, Bxh7+ était jouable mais mauvais pour les Blancs : après Nxh7
  Nxh7 Kxh7... ») — aucune alerte attendue.
- `c4.case` : nouveau `reponse_simulee_verte` pour « Bxc6+ Qxc6, un
  échange de cavalier contre fou » (vert attendu) et deux
  `reponse_simulee_signalee` pour les variantes fausses « cavalier contre
  cavalier » et « fou contre fou » (signalées attendu, règle symétrique
  sur deux types identiques).
- Tous les cas déjà présents (`re3_dame_contre_tour`, `h4_menace_gxh3_
  defensif`, et les faits/motifs déjà couverts de `c4`/`bxh7`) ont été
  rejoués sans régression : `python3 non_regression_coach.py` (4/4 OK).

### 4. Tests et limites

Vérifié sans appel API (`ANTHROPIC_API_KEY` absent de cet environnement
d'exécution — impossible de relancer le script `--api` avec cinq essais
par cas comme demandé, cela reste à faire par Alain) : les quatre cas de
non-régression, plus des scénarios Python ad hoc reproduisant exactement
les contrôles de l'issue (voir rapport de clôture) :
- les deux faux positifs ci-dessus ne sont plus signalés ;
- les régressions explicitement demandées restent détectées : « échange de
  dames » sur Qxe8 Qxe8, « Qxh4 gxh4 : échange équilibré », « ton fou
  adverse attaque la tour » après Be5, coups réellement illégaux (Rxh5,
  Qxa1) ;
- « Bxh6 Qxh6 » équilibré (issue #97) reste vert.

Limites assumées (élargissement volontaire de la tolérance, même
philosophie que les issues #94/#97 — un faux négatif occasionnel reste
préférable à un faux positif) :
- la fenêtre de 250 caractères pour le coup précédent cité, même élargie
  à la phrase précédente, peut en théorie retrouver un coup cité dans une
  proposition sans rapport avec la suite si aucune fin de phrase ne les
  sépare dans cette fenêtre — risque atténué en pratique par le fait que
  ce coup doit réellement rendre la suite citée jouable une fois inséré
  devant elle (un coup sans rapport n'y parvient qu'exceptionnellement) ;
- le demi-coup caché, désormais essayé aussi pour une suite de plusieurs
  coups (plus seulement un coup isolé), élargit l'espace de recherche
  d'une lecture « chanceuse » qui masquerait une vraie suite illégale —
  risque déjà documenté pour les contrôles de qualificatif depuis l'issue
  #97, qui s'étend maintenant au contrôle des coups illégaux lui-même ;
- la forme asymétrique « X contre Y » reste basée sur un seuil "au moins
  une pièce perdue de chaque type", comme l'ancienne règle symétrique :
  une suite plus complexe (plusieurs pièces du même type perdues par un
  camp) peut satisfaire le contrôle sans que la description « un échange
  simple » soit entièrement fidèle au détail du bilan ;
- `_ECHANGE_TYPE_CONTRE_RE` ne couvre que la tournure « `<type1>` [contre]
  `<type2>` » avec au plus un déterminant simple devant chaque type — une
  tournure équivalente mais plus élaborée (« un cavalier s'échange avec le
  fou ») échappe toujours au contrôle (faux négatif assumé, même
  philosophie que le reste du module).
