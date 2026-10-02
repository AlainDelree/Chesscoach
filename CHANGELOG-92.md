# Changelog — Issue #92

## Coach : fiabilité 4 — mêmes données pour les trois sources d'exercice, pièces clouées, contrôles « échange de X »/clouage/bilan matériel annoncé

Cas réel ayant motivé cette issue (journal du coach, 2 octobre 2026 16:58,
Sonnet, même FEN que les issues #90/#91 : `Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/
P5PP/4R2K w - - 9 35`, coup proposé Re3, meilleur coup Re8) : la réponse,
pourtant courte et au verdict juste, contenait encore quatre affirmations
fausses que les contrôles existants ne voyaient pas — « il force un échange
de dames (Qxe8 Qxe8) » (faux : une tour perdue contre une dame gagnée, pas
un échange de dames), « ta dame en a8 reste clouée » (faux, vérifié avec
python-chess), « après l'échange, tu récupères l'équilibre matériel » (faux,
+2 points pour les Blancs), « Rxe5 Nxe5 ne t'apporte rien de décisif »
(minimise une perte tour contre fou). Constat séparé : la source « Problèmes
Lichess » ne recevait pas les champs de réponse adverse forcée, câblés
uniquement dans le chemin « mes erreurs »/« position précise » par l'issue
#91.

### 1. Parité des sources (`app.py`)

Tableau des champs de contexte transmis au coach, avant/après cette issue,
par source d'exercice :

| Champ                                          | Mes erreurs (avant→après) | Position précise (avant→après) | Lichess (avant→après) |
|-------------------------------------------------|----------------------------|----------------------------------|-------------------------|
| `materiel_resume_texte`, `menace_adverse_texte`, `pieces_depart_texte`/`pieces_actuelles_texte`, `idees_*_texte`, `pv_*_detail` | présent → présent | présent → présent | présent → présent |
| `reponse_adverse_coup_propose_texte`/`reponse_adverse_meilleur_coup_texte` | présent → présent | présent → présent | **absent → présent** |
| `pieces_clouees_texte` (nouveau, tâche 2)       | absent → présent          | absent → présent                 | absent → présent        |
| `coup_reel`/`idees_coup_reel_texte` (N/A, pas de partie d'origine pour "position précise"/"Lichess") | présent | absent (déjà le cas, inchangé) | absent (déjà le cas, inchangé) |

`_on_exercise_answer_lichess` (app.py) calcule désormais `reponse_adverse_
coup_propose_texte`/`reponse_adverse_meilleur_coup_texte` exactement comme
`on_exercise_answer` (même `game_facts.build_reponse_adverse_obligee_texte`
+ `_calculer_reponses_adverses`, aucune duplication de logique de calcul —
seul le câblage était absent), et les trois sources calculent désormais
`pieces_clouees_texte` sur la position de DÉPART de l'exercice (même
référence stable que `materiel_resume_texte`). Les deux nouveaux champs sont
aussi renvoyés au client (`exercise_comment`) et captés par `static/
exercise.js` (`exercisePiecesCloueesTexte`, déjà fait pour `reponse_
adverse_*_texte` côté Lichess) pour une question de suivi dans le chat
libre.

### 2. Pièces clouées (`game_facts.py`)

- `game_facts.describe_pieces_clouees(fen, camp_alain)` (nouveau, API
  publique) : liste, pour chaque camp, les pièces clouées (case + pièce) ou
  « aucune pièce clouée » — calcul déterministe `chess.Board.is_pinned`,
  jamais une lecture géométrique du coach. Le roi n'est jamais listé (il ne
  peut pas être « cloué » au sens des échecs).
- Câblée dans `_build_context_text` (llm_coach.py, nouveau champ de
  contexte `pieces_clouees_texte`, ligne ajoutée juste après le résumé du
  matériel) et dans les trois sources d'exercice (app.py, cf. tableau
  ci-dessus).

Vérifié avec Stockfish réel (16, `/usr/games/stockfish`) sur le cas Re3/Re8 :
`describe_pieces_clouees` renvoie bien « aucune pièce clouée » pour les deux
camps sur la position de départ, et `get_reponses_adverses`/
`build_reponse_adverse_obligee_texte` confirment Qxe8 comme SEULE réponse
qui évite le mat (« Qxe8 est la SEULE réponse qui évite une perte nette ou
un mat... mat en 2 demi-coup(s) (Bxb4 Qb8#) » sur les 4 autres réponses
comparées) — les deux affirmations attendues par le test de l'issue.

### 3. Trois contrôles automatiques supplémentaires (`coach_reliability.py`)

Réutilisent `_extraire_suites`/`_tenter_suite`/`_construire_candidats` déjà
en place (issues #90/#91), jamais dupliqués. `_extraire_suites` gagne deux
champs plus fins (`entre_parentheses`, `si_hypothetique`, au lieu du seul
booléen `douteuse`) : le cas réel citait sa suite ENTRE PARENTHÈSES par
simple concision (« un échange de dames (Qxe8 Qxe8) »), que l'ancien filtre
« douteuse » de l'issue #90 aurait exclu à tort en la confondant avec une
vraie hypothèse non confirmée (« si Dxd5... »). Les deux contrôles ci-dessous
tolèrent donc une suite entre parenthèses (un filet de sécurité reste la
tentative de rejeu elle-même) mais excluent toujours une suite introduite
par « si » — `detecter_suites_illegales`/`detecter_echanges_mal_qualifies`
(existants) restent inchangés, aucune régression sur leur filtre
`douteuse`.

- **`detecter_clouage_errone`** (tâche 3b) : une pièce citée « \<type\>
  [\<couleur\>] en/sur \<case\> » dite clouée (mot de la famille « clou... »
  dans la même phrase, avant ou après — fenêtre bornée par la ponctuation de
  fin de phrase des deux côtés) est comparée à `python-chess` sur la
  position de départ, la position actuelle et chaque étape des lignes/suites
  déjà construites pour les autres contrôles — signalée seulement si elle
  n'est clouée nulle part. La couleur n'a pas besoin d'être explicite dans
  le texte (« ta dame en a8 », cas réel) : la case suffit à l'identifier
  sans ambiguïté via les positions de référence ; sinon la mention n'est
  simplement pas contrôlée (faux négatif assumé). Une mention niée (« pas
  clouée ») ou hypothétique (« si... était clouée ») n'est jamais signalée.
- **`detecter_echange_type_incoherent`** (tâche 3a) : « échange de
  dames »/« de tours »/« de fous »/« de cavaliers » accolé à une suite d'au
  moins deux coups cités est signalé si cette suite, rejouée sur
  l'échiquier, ne retire PAS une pièce de ce type précis à CHACUN des deux
  camps (ex. une dame prise contre une tour). Gravité orange/rouge selon
  `SEUIL_ECHANGE_GRAVE_PTS` (3 points, déjà réglable depuis l'issue #91,
  partagé).
- **`detecter_bilan_materiel_annonce`** (tâche 3c) : « équilibre
  matériel »/« matériel égal »/« égalité matérielle » à propos du résultat
  d'une suite citée est comparé au bilan matériel RÉEL (total absolu de
  chaque camp, pas le delta provoqué par la suite) après cette suite,
  rejouée sur l'échiquier — signalé si l'écart atteint `SEUIL_BILAN_
  MATERIEL_PTS` (2 points, réglable en ce seul endroit), gravité plus forte
  au-delà de `SEUIL_BILAN_MATERIEL_GRAVE_PTS` (4 points). Fenêtre de
  recherche volontairement plus large que celle de `detecter_echanges_mal_
  qualifies` (250 caractères, coupée au prochain saut de paragraphe plutôt
  qu'à la première fin de phrase) : le cas réel annonçait l'équilibre dans
  une phrase SÉPARÉE de la suite citée (« ...perd une tour. Mais après
  l'échange, tu récupères l'équilibre matériel. »).

Les trois nouveaux contrôles sont ajoutés à la liste `controles` du rapport
de fiabilité (journalisé dans `coach_calls.log`) et déclenchent la même
relance automatique unique que les contrôles existants dès qu'une alerte est
détectée (`get_coach_response`, llm_coach.py, inchangé).

**Ce qui n'est PAS détecté** (prudence délibérée, un faux négatif reste
préférable à un faux positif) : une suite ambiguë ou illégale sur toutes les
positions connues (aucune alerte des trois nouveaux contrôles, le rejeu
échoue silencieusement — un éventuel « coup_illegal » reste du ressort de
`detecter_suites_illegales`, inchangé) ; un qualificatif ou un mot de
clouage niés (« pas clouée », « n'est pas équilibré ») ; une suite ou une
pièce introduite par une hypothèse (« si... ») ; une pièce clouée dont la
case ou le type n'est pas identifiable sans ambiguïté sur les positions de
référence ; une formulation différente de « échange de \<type\> » ou
« équilibre matériel »/« matériel égal »/« égalité matérielle » (ex. « ils
échangent leurs dames », non reconnu).

### 4. Prompt (`llm_coach.py`)

- `_MATERIEL_ADDENDUM` (étendu, 3 nouveaux paragraphes, tâches 4i/4ii/4iv) :
  qualifier le résultat d'une ligne par son solde matériel fourni plutôt que
  par une impression (« équilibre »/« égalité » seulement si le solde est
  proche de zéro, jamais à 2 points ou plus) ; décrire une suite de
  captures par ce qu'elle donne et prend (« tu gagnes une dame pour une
  tour »), et ne dire « échange de dames »/« de tours »/« de fous »/« de
  cavaliers » que si chaque camp perd effectivement une pièce de ce type ;
  ne jamais minimiser une perte de matériel montrée par le solde.
- `_CLOUAGE_ADDENDUM` (nouveau, tâche 4iii, conditionné à la présence de
  `pieces_clouees_texte` dans le contexte — même câblage indépendant que
  `_GAME_FACTS_ADDENDUM`) : ne parler de clouage que si le bloc « Pièces
  clouées dans cette position » l'indique explicitement pour ce camp.

### Tests

Reproduit avec un vrai Stockfish (16, `/usr/games/stockfish`, aucune clé API
Anthropic disponible dans ce worktree — `ANTHROPIC_API_KEY` absente et pas
de `.env` : impossible de vérifier un vrai appel API bout-en-bout, voir
limite ci-dessous) :

- Cas Re3/Re8 : `pieces_clouees_texte` confirme « aucune pièce clouée » pour
  les deux camps, `reponse_adverse_meilleur_coup_texte` confirme Qxe8 comme
  seule réponse évitant le mat — cf. section 2 ci-dessus.
- Texte simulé reprenant les 4 erreurs réelles (`evaluer_fiabilite`,
  contrôles seuls, pas d'appel API — comme le permet explicitement l'issue)
  : 4 alertes détectées (`clouage_errone`, `echange_type_incoherent`,
  2×`bilan_materiel_incoherent` sur les deux suites citées), pastille rouge.
- Texte corrigé (« tu gagnes une dame pour une tour », « pas de clouage »,
  « tu passes en avance de deux points ») : aucune alerte, pastille verte.
- Non-détection : suite illégale sur toutes les positions (aucune alerte
  des 3 nouveaux contrôles), hypothèse « si... », négation (« n'est pas
  clouée »), pièce réellement clouée (position construite à la main,
  `Board.is_pinned` positif) : aucune alerte dans tous les cas.
- Vrai échange de dames (position à 2 dames par camp construite pour rendre
  « chaque camp perd une dame » mécaniquement possible sur `Qxd5 Qxd5` — un
  échange dame-contre-dame strict en une seule paire de demi-coups sur la
  même case est par construction impossible avec une seule dame par camp,
  cf. limite ci-dessous) : aucune alerte.
- Parité : `_on_exercise_answer_lichess` construit désormais `reponse_
  adverse_*_texte` (vérifié par lecture de code + test unitaire de
  `build_reponse_adverse_obligee_texte` isolé).
- Régression (texte simulé + `evaluer_fiabilite`, contrôles seuls) : cas c4
  (« Bxc6+ bxc6, un échange équilibré » sur la FEN de l'issue #90, toujours
  vert), exercice h4 (position de l'issue #80, toujours vert).

**Limite du test** : aucune clé API Claude disponible dans ce worktree
(`ANTHROPIC_API_KEY` absente, pas de `.env`) — impossible de vérifier un
vrai appel au coach bout-en-bout (modes de partie/analyse/ouverture compris)
dans cette tentative ; tous les contrôles ont été exercés directement
(`coach_reliability.evaluer_fiabilite`, `game_facts.*`) avec un vrai
Stockfish pour les données de position, et du texte simulé pour les
réponses du coach, comme le permet explicitement l'issue. Autre limite déjà
documentée (cf. commentaire dans `coach_reliability.py`) : la sélection du
premier candidat « rejouable » par `_tenter_suite`/`_construire_candidats`
(logique inchangée, partagée avec les contrôles existants) peut retenir une
position de départ différente de celle narrativement visée par le coach
quand plusieurs candidats permettent de rejouer la même suite SAN (ex.
« Qxe8 » sans capture réelle reste accepté par `python-chess.parse_san` si
la case est simplement atteignable) — cela n'empêche jamais une
incohérence réelle d'être détectée, mais peut faire citer un camp différent
dans le détail de l'alerte.
