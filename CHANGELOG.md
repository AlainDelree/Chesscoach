# Changelog — Issue #47

# Changelog — Issue #94

## Coach : fiabilité 5 — échanges par gain net exact, contrôle des parenthèses, coup isolé, journal de la relance, non-régression plus tolérant

Premier test de non-régression avec de vrais appels API (3 essais, modèle
Sonnet) : Re3 et c4 réussissent 3/3, h4 échoue 3/3. Analyse avec Stockfish
16 réel et python-chess : le coach a qualifié « échange équilibré » une
suite où les Noirs perdent leur dame contre un pion (8 points), parce que
les descriptions mécaniques elles-mêmes employaient l'étiquette floue
« échange favorable ou équilibré » — et parce que le contrôle des échanges
mal qualifiés ignorait les suites citées entre parenthèses. Un coup isolé
légal (« gxh4 » cité sans écrire le « Qxh4 » qui le précède) a aussi
déclenché une relance automatique inutile, dont la première réponse
n'était pas journalisée.

### 1. Étiquettes d'échange précises (`game_facts.py`)

- `SEUIL_ECHANGE_EQUILIBRE_PTS` (0 par défaut, réglable en un seul endroit)
  — solde net d'une capture/reprise immédiate en deçà duquel l'échange
  reste qualifié « équilibré ».
- `_resultat_echange_case` (seule fonction produisant cette étiquette —
  réutilisée par `describe_move_mechanically`/`_attaques_defenses_arrivee`
  pour les captures et le coup proposé/meilleur coup, et par
  `describe_pv_with_balance`/`_statut_attaque_case` pour les lignes
  principales) réécrite : ne dit plus jamais « échange favorable ou
  équilibré », mais « échange équilibré » (solde nul), ou « gain net »/
  « perte nette » de N points pour le camp qui possédait la pièce
  initialement attaquée, précédé d'une courte phrase disant ce qui est pris
  et donné.
- Vérifié avec Stockfish réel et python-chess :
  - Cas h4 (`1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - -
    0 23`, coup h4) : « Qxh4 gxh4, Noirs (adversaire) prennent un pion puis
    perdent la dame en reprise : gain net de 8 point(s) pour Blancs
    (Alain) » — plus jamais « équilibré ».
  - Cas Re8 (`Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35`, meilleur
    coup Re8) : « Qxe8 Qxe8, Noirs (adversaire) prennent la tour puis
    perdent la dame en reprise : gain net de 4 point(s) pour Blancs
    (Alain) ».
  - Cas sans reprise (variation seule) : désormais chiffré aussi
    (« perte nette de N point(s) pour <camp> »), plus seulement « perdrait
    la dame » sans magnitude.

### 2. Prompt (`llm_coach.py`, `_MATERIEL_ADDENDUM`)

- Nouvelle consigne courte : reprendre le gain net/la perte nette/
  l'équilibre déjà chiffrés par les données plutôt que de les requalifier
  soi-même en « favorable »/« équilibré »/« défavorable ».

### 3. Contrôle des parenthèses (`coach_reliability.detecter_echanges_mal_qualifies`)

- Ne skip plus les suites citées ENTRE PARENTHÈSES (seul
  `si_hypothetique` reste ignoré — même traitement que
  `detecter_echange_type_incoherent` depuis l'issue #92) : une suite de
  concision du type « (Qxh4 gxh4) : échange équilibré » est désormais
  analysée comme une suite normale.
- Vérifié : « si la dame prend en h4, gxh4 reprend (Qxh4 gxh4) : un
  échange équilibré » → alerte **rouge**, écart de 8 points, détectée ;
  « (Qxh4 gxh4) : tu gagnes la dame pour un pion » → aucune alerte (pas de
  qualificatif contredit) ; échange réellement équilibré entre
  parenthèses → aucune alerte ; hypothèse « si Dxd5... » → toujours
  ignorée ; cas c4 (« Bxc6+ bxc6, un échange équilibré », sans
  parenthèses) → toujours aucune alerte (régression vérifiée).

### 4. Coup isolé : demi-coup caché (`coach_reliability.detecter_suites_illegales`)

- Nouvelle fonction `_legal_apres_demi_coup_cache` : pour une suite d'UN
  SEUL coup cité, illégale sur toutes les positions candidates, essaie
  aussi de la jouer après chacun des coups légaux (un seul, caché,
  n'importe lequel) de chaque position candidate. Devient légale → aucune
  alerte (coup plausible, prudence conforme à l'issue #90).
- Vérifié : « si la dame prend en h4, gxh4 reprend » sur le cas h4 →
  aucune alerte (le demi-coup caché « Qxh4 » rend « gxh4 » légal) ; coups
  réellement illégaux cités isolément (« Rxh5 », « Qxa1 » — pièce absente
  de la case, aucune prise possible même avec un demi-coup caché) →
  toujours signalés en rouge.
- Limite assumée (conforme à la philosophie « mieux vaut un faux négatif
  qu'une fausse alerte » déjà documentée dans ce module) : quelques coups
  isolés cités à tort peuvent désormais échapper au contrôle s'ils
  deviennent accidentellement légaux via un demi-coup caché sans rapport
  avec l'intention du coach (observé sur deux coups de test artificiels
  pendant la vérification) — un vrai coup absurde (pièce totalement
  étrangère à la position) reste détecté.

### 5. Journal de la relance (`llm_coach.py`, `lire_journal_coach.py`)

- `_log_coach_call` accepte un nouveau paramètre `premiere_reponse`
  (dict `{"texte": str, "alertes": list}` ou `None`), écrit comme nouveau
  champ `"premiere_reponse"` de l'entrée JSON — ne modifie aucune clé
  existante (aucun impact sur `lire_journal_coach.py` ni sur la fonction
  `coachlog` d'Alain, non lue — hors périmètre strict de ce worktree —
  mais protégée par construction : un lecteur qui ne connaît pas cette
  clé l'ignore simplement).
- `get_coach_response` capture `response`/`fiabilite["alertes"]` dans
  `premiere_reponse` AVANT la relance automatique, qu'elle réussisse ou
  non — jusqu'ici, une relance réussie écrasait silencieusement la
  première réponse, la rendant irrécupérable pour juger un faux positif
  après coup.
- `lire_journal_coach.py` affiche désormais cette première réponse (et
  les alertes qui l'ont déclenchée) quand elle est présente, avant la
  réponse finale.
- Vérifié par un appel simulé (`_call_claude` mocké, pas d'appel API
  réel) reproduisant exactement le cas h4 fautif suivi d'une correction :
  l'entrée du journal contient bien `premiere_reponse.texte` (la réponse
  fautive) et `premiere_reponse.alertes` (l'alerte « échange_mal_qualifie »
  qui a déclenché la relance), en plus de `reponse` (la réponse finale
  corrigée) — `lire_journal_coach.py` affiche les deux.

### 6. Script de non-régression (`non_regression_coach.py`, `tests/cas_coach/`)

- `motifs_interdits`/`motifs_attendus` acceptent désormais des
  alternatives séparées par `|` (présent si au moins une correspond) et un
  préfixe `regex:` (expression régulière Python complète, recherchée sur
  le texte brut).
- `motifs_interdits` (motifs ordinaires, pas `regex:`) tolère une négation
  proche (« pas », « jamais », « aucun(e) », « ni », « non » — fenêtre de
  20 caractères) : une occurrence précédée d'une négation ne compte plus
  comme une présence du motif interdit.
- Échec de pastille (`pastille_attendue`) : affiche désormais la couleur
  réellement obtenue, la raison (`fiabilite["raison"]`) et les types de
  contrôles déclenchés, à la fois dans le tableau récapitulatif et dans le
  détail par tentative.
- Cas `h4_menace_gxh3_defensif` mis à jour : `motifs_attendus` avec
  alternatives (`défensif|pare la menace|sécurité du roi`, le coach ne dit
  pas toujours « défensif » littéralement) ; nouveau `motifs_interdits`
  `regex:` limité au voisinage de « Qxh4 gxh4 » pour l'étiquette
  « équilibré » (sans toucher le cas c4, dont l'« échange équilibré » porte
  sur des coups différents) ; nouveau `faits_attendus` vérifiant la
  présence du texte exact « gain net de 8 point(s) pour Blancs (Alain) »
  dans le contexte réellement envoyé au coach (vérifié avec Stockfish
  réel : la vraie meilleure ligne après h4 est en fait `h4 Qg6 Re1 h6 Kg1
  Nh7`, mais l'étiquette hypothétique de la prise en h4 reste bien décrite
  avec l'exacte magnitude).
- `tests/cas_coach/README.md` mis à jour : syntaxe des alternatives/regex,
  tolérance à la négation, affichage enrichi d'un échec de pastille.
- Vérifié : relance des trois cas (`re3_dame_contre_tour`,
  `c4_bxc6_bxc6_reste_verte`, `h4_menace_gxh3_defensif`) sans `--api` —
  faits exacts avec Stockfish réel, trois cas OK ; test ciblé avec
  `appeler_coach` simulé (sans appel API réel) sur trois réponses
  (correcte avec négation+alternative, fautive avec regex+pastille,
  motif attendu absent) — les trois comportements attendus confirmés.

### Limites

- Appel API réel non effectué dans cette tâche (pas de budget/accord
  explicite donné pour relancer `--api` avec de vrais tokens) : toutes les
  vérifications de contrôle (parenthèses, coup isolé, motifs, pastille,
  journal) ont été faites avec des réponses **simulées** reproduisant
  fidèlement les cas réels décrits dans l'issue, jamais avec un vrai appel
  Claude. Les faits (données Stockfish/python-chess réelles) ont, eux,
  été entièrement vérifiés avec un vrai Stockfish 16.
- `coachlog` (fonction bash d'Alain, `~/.bashrc`) n'a pas été lue ni
  modifiée : hors du périmètre strict de ce worktree. Le nouveau champ
  `premiere_reponse` est additif (aucune clé existante modifiée), donc
  sans impact attendu sur son affichage — à confirmer par Alain.
- Le demi-coup caché du contrôle des coups isolés (point 4) accepte par
  construction quelques faux négatifs supplémentaires (cf. limite déjà
  documentée dans ce module) en échange de la suppression du faux positif
  réel ayant motivé cette issue.

# Changelog — Issue #93

## Script de non-régression du coach : rejouer des positions où le coach s'est trompé

Plusieurs explications fausses du coach ont été relevées et corrigées en
série (issues #87, #90, #91...) : tour inexistante citée, coup qualifié
« illégal » à tort, « échange de dames » pour une dame prise contre une
tour, « dame clouée » alors qu'elle ne l'est pas, « équilibre matériel »
annoncé alors qu'un camp est en avance. Jusqu'ici, vérifier qu'une
modification du prompt ou des données n'aggrave pas un de ces cas obligeait
à retester à la main sur le téléphone.

### 1. Fichiers de cas (`tests/cas_coach/*.case`)

- Format texte simple (`clé: valeur` / blocs indentés, commentaires `#`),
  documenté dans `tests/cas_coach/README.md` : identifiant, description,
  source, FEN de départ, camp d'Alain, coup proposé, meilleur coup attendu,
  faits attendus dans les données envoyées au coach, motifs interdits/
  attendus dans la réponse du coach, pastille de fiabilité attendue.
- Trois cas créés : `re3_dame_contre_tour` (issue #91 — gain de dame mal
  qualifié d'« échange », dame non clouée dite « clouée », matériel dit
  « équilibré »), `c4_bxc6_bxc6_reste_verte` (issue #90 — la suite
  « Bxc6+ bxc6 » ne doit plus être signalée illégale), `h4_menace_gxh3_defensif`
  (issue #80 — h4 pare une menace réelle, ne doit pas être présenté comme
  offensif).
- Deux cas supplémentaires tirés de `parties_test_coach.pgn` (parties sans
  erreur connue) étaient prévus par l'issue mais n'ont pas pu être créés :
  ce fichier n'est pas présent dans le périmètre du projet traité ici.

### 2. Script (`non_regression_coach.py`, racine du projet)

- Reconstruit, pour chaque cas, exactement le contexte envoyé au coach par
  le mode « Exercice » (mêmes fonctions que l'application —
  `game_facts.py`, `coach_reliability.py`, `engine_stockfish.py` — avec un
  vrai Stockfish lancé par le script lui-même, jamais via l'interface, une
  connexion SocketIO, ou l'instance de l'application en cours d'exécution).
- Vérifie les faits attendus (`faits_attendus`) sur ce contexte : par
  défaut une sous-chaîne cherchée dans le texte réellement injecté dans le
  system prompt (`llm_coach._build_context_text`), ou une directive dédiée
  (`camp_sans_tour`, `camp_a_une_tour`, `aucune_piece_clouee`,
  `menace_significative_contient`, `reponse_simulee_verte` — ce dernier
  rejoue `coach_reliability.evaluer_fiabilite` sur un texte simulé, sans
  appel API, utile pour les régressions de détection).
- Deux contrôles systématiques, même sans `faits_attendus` : coup proposé
  légal sur le FEN, et meilleur coup recalculé par le vrai Stockfish
  conforme au `meilleur_coup` attendu du cas.
- Option `--api` (désactivée par défaut, pour que la commande de base ne
  dépense rien) : appelle réellement le coach (`llm_coach.get_coach_response`,
  modèle `--modele sonnet|haiku`, défaut = modèle actif de l'application)
  et vérifie sa réponse (aucun motif interdit, motifs attendus présents,
  pastille conforme), répété `--repetitions` fois par cas (3 par défaut —
  la réponse d'un modèle de langage varie d'un appel à l'autre). Affiche
  une estimation du nombre d'appels avant de les lancer.
- Options `--cas ID [ID...]` (sous-ensemble de cas), `--verbose` (détail
  des réponses fautives). Résumé final en tableau (faits OK/KO, réussites
  X/N), liste des échecs avec motif et extrait de réponse, code de sortie
  non nul en cas d'échec.

### 3. Isolation

- Jamais de lecture/écriture de `coach_memory.json`, `erreurs_detectees.json`,
  `exercice_historique.json`, `coach_calls.log` ni `signalements.log` —
  mémoire de progression neutre (`{}`) passée à `get_coach_response`,
  journal dédié `data/logs/non_regression_coach_calls.log` (chemin relatif
  au script lui-même, jamais `config.DATA_DIR`), aucun `usage_path` (le
  compteur de tokens personnel n'est jamais modifié).
- Aucune connexion à une instance de l'application en cours d'exécution :
  instance Stockfish propre au script, jamais `app.py`/Flask/SocketIO.
- Seule exception, en lecture seule et à la demande explicite d'Alain :
  `--depuis-signalement` lit `signalements.log` pour créer un squelette de
  cas (FEN/coup/camp pré-remplis, réponse fautive citée en commentaire).

### 4. Tests réalisés (sans clé API dans l'environnement — `.env` non lu)

- Lancement sans `--api` : faits vérifiés avec succès sur les 3 cas
  (vrai Stockfish).
- Simulation d'une réponse correcte (`llm_coach._call_claude` remplacé) :
  cas réussi, code de sortie 0. Simulation d'une réponse fautive (motif
  interdit présent) : cas échoué, code de sortie 1, extrait affiché avec
  `--verbose`.
- `--cas <id>` (sélection), estimation du nombre d'appels affichée avant
  `--api`, isolation vérifiée par empreinte MD5 de `~/ChessCoach/data`
  avant/après (identique), création d'un squelette depuis un signalement
  factice (fichier temporaire, jamais le vrai `signalements.log`).
- Aucun appel API réel n'était possible dans cet environnement (clé absente,
  `.env` volontairement non lu).

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

# Changelog — Issue #91

## Coach : fiabilité 2 — réponse adverse forcée, réponses plus courtes et structurées, vérification des échanges cités

Cas réel ayant motivé cette issue (journal du coach, 2 octobre 2026 15:19,
modèle Sonnet) : exercice FEN `Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w -
- 9 35`, coup proposé Re3 (gaffe), meilleur coup Re8. Le verdict était juste
et la pastille verte, mais l'explication contenait plusieurs erreurs :
« Re8 force un échange de dames » (faux : gain net de dame contre une
tour), « sans Qxe8 la dame perd la tour gratuitement » (faux : toute autre
réponse perd par mat en 1, menace Qb8 mat — jamais dite au coach), « après
Rxe5 Nxe5 l'échange reste équilibré » (faux : tour contre fou), et une
reprise de phrase au milieu de la réponse (« ton fou... pardon, le fou
adverse » — les Blancs n'ont pourtant aucun fou).

### 1. Réponses adverses alternatives (`engine_stockfish.py`, `game_facts.py`, `app.py`)

- `EngineManager.get_multipv` : nouveau paramètre optionnel `with_pv`
  (+ `pv_max_plies`) — ajoute, par candidat, la ligne complète (`pv`, UCI)
  calculée par le moteur pour CE coup précis, pas seulement son premier
  demi-coup. Désactivé par défaut (`with_pv=False`), aucun changement pour
  les appelants existants (`get_threats`).
- `EngineManager.get_reponses_adverses(board, depth, n, pv_max_plies)`
  (nouveau) : les `n` meilleures réponses du camp au trait sur `board`
  (typiquement la position APRÈS le coup proposé ou le meilleur coup), avec
  la perte d'avantage de chacune par rapport à la meilleure (`perte_cp`,
  même barème mat/cp que `evaluate_move`). Ne décide rien elle-même (faits
  bruts seulement, même séparation que `get_threats`/
  `describe_menace_adverse`).
- `game_facts.SEUIL_REPONSE_FORCEE_CP = 300` (nouveau, réglable en CE SEUL
  endroit) : perte au-delà de laquelle une réponse alternative est jugée
  perdante (en plus d'un mat détecté directement, toujours perdant quel que
  soit ce seuil).
- `game_facts._decrire_menace_evitee` (nouveau) : rejoue la ligne calculée
  pour la MOINS mauvaise réponse perdante, coup par coup, jusqu'au premier
  mat rencontré — décrit alors mécaniquement qui défend la pièce qui mate
  (ex. « dame protégée par la tour e8 »), l'information manquante dans le
  cas réel.
- `game_facts.build_reponse_adverse_obligee_texte(label, fen_apres_coup,
  reponses_data, camp_alain)` (nouveau, API publique) : formate le tout en
  texte de contexte — dit explicitement si la réponse de la ligne
  principale est la SEULE qui évite une perte nette ou un mat (avec la
  menace évitée), ou si plusieurs réponses se valent, ou si le calcul est
  indisponible (position terminale / Stockfish indisponible) — jamais un
  silence.
- `app.py` : `N_REPONSES_ADVERSES = 4` (réglable), `_calculer_reponses_
  adverses(fen_apres_coup)` (mode-agnostique, même pattern que
  `_calculer_menace_adverse`/`_calculer_idees_coup`), câblé dans
  `on_exercise_answer` (source « mes erreurs »/« position précise ») pour
  le coup proposé ET pour le meilleur coup — deux nouveaux champs de
  contexte `reponse_adverse_coup_propose_texte`/
  `reponse_adverse_meilleur_coup_texte`, transmis au coach ET renvoyés au
  client (`exercise_comment`) pour une question de suivi dans le chat
  libre (`static/exercise.js`, `exerciseChatContextExtra`).

**Extrait réel obtenu avec Stockfish 16 sur le cas Re8** (profondeur 18,
4 réponses comparées) :

```
Qxe8 -497  (meilleure)
Bxb4  mat en -1 (pour les Noirs), perte 99502
f4    mat en -1, perte 99502
h6    mat en -1, perte 99502
```

Texte produit : « Réponse adverse après le coup Re8 (issue #91) : Qxe8 est
la SEULE réponse qui évite une perte nette ou un mat — toute autre réponse
perd (mat en 2 demi-coup(s) (Bxb4 Qb8#), la dame protégé(e) par Tour e8).
N'invente AUCUNE autre raison : c'est la vraie raison pour laquelle cette
réponse est forcée. » — correspond exactement à la menace réelle (Qb8 mat,
dame protégée par la tour e8 et la dame a8) citée par l'issue.

Sur Re3 (coup proposé, gaffe) : 4 réponses noires comparables (Be5 369,
Bf6 278/perte 91, Bxb4 195/perte 174, Ne7 88/perte 281) → aucune n'est
« forcée » au sens du seuil, texte : « plusieurs réponses se valent ... la
meilleure selon Stockfish est Be5 » — confirmé sans incohérence avec le
test demandé (Be5 est la meilleure réponse, ET elle n'attaque pas la tour
en e3, vérifié séparément via `game_facts._statut_attaque_case`, mécanisme
déjà existant de l'issue #87 : « Tour blanche en e3 n'est PAS attaqué(e)
par ce coup »).

### 2. Prompt : réponse plus courte, structurée, sans reprise (`llm_coach.py`)

- `_LONGUEUR_MAX_MOTS_REPONSE_EXERCICE = 120` (nouveau, réglable en CE SEUL
  endroit, indicatif — jamais vérifié mécaniquement après coup).
- `_REPONSE_STRUCTUREE_ADDENDUM` (nouveau complément de system prompt,
  ajouté en mode "exercice" juste après `_EXERCISE_SYSTEM_ADDENDUM`) :
  - structure imposée en 4 parties (verdict ; pourquoi, en s'appuyant sur
    la réponse adverse réelle de la ligne principale ; idée du meilleur
    coup en 1-2 phrases, y compris le caractère FORCÉ de la réponse
    adverse quand le bloc "Réponse adverse après..." le précise
    explicitement ; une phrase de conseil) ;
  - interdiction de se reprendre en cours de réponse (« pardon », « en fait
    non », « je me corrige »...) ;
  - interdiction de qualifier un échange (« équilibré », « favorable »,
    « défavorable ») hors des données fournies, et d'appeler « échange »
    une capture qui gagne du matériel net d'après ces mêmes données ;
  - objectifs personnels d'Alain cités au plus une fois.
- `_build_context_text` : lit et injecte les deux nouveaux champs
  `reponse_adverse_coup_propose_texte`/`reponse_adverse_meilleur_coup_texte`
  juste après les blocs `pv_coup_propose`/`pv_meilleur_coup` existants.
- Message de relance automatique (`get_coach_response`) étendu pour
  mentionner aussi l'incohérence d'échange mal qualifié (issue #91) parmi
  les points que la relance doit corriger.

### 3. Vérification des échanges cités (`coach_reliability.py`)

Construite SUR la logique de suites déjà présente (issue #90,
`_extraire_suites`/`_tenter_suite`/`_construire_candidats`), jamais
dupliquée ni contredite — `_extraire_suites` gagne juste deux champs
(`debut`/`fin`, offsets dans le texte) pour localiser le voisinage d'un
qualificatif.

- `coach_reliability.SEUIL_ECHANGE_GRAVE_PTS = 3` (nouveau, réglable en CE
  SEUL endroit) : écart matériel au-delà duquel l'incohérence est jugée
  grave (pastille rouge) plutôt que mineure (orange) — **c'est la première
  famille d'alerte qui n'entraîne pas automatiquement une pastille
  rouge** ; `evaluer_fiabilite` choisit désormais la couleur en fonction du
  champ `gravite` de chaque alerte (absent = rouge, comportement d'avant
  l'issue #91 inchangé pour tous les contrôles existants).
- `detecter_echanges_mal_qualifies(texte, candidats)` (nouveau) : pour
  chaque suite d'AU MOINS DEUX captures citées (suite d'un seul coup non
  concernée), rejoue la suite depuis l'une des positions candidates
  (mêmes candidats que `detecter_suites_illegales`, une suite illégale
  partout/ambiguë/douteuse est simplement ignorée ici — c'est l'autre
  contrôle qui la signale), calcule le résultat matériel réel (différence
  Blancs−Noirs avant/après, barème pion=1/cavalier=3/fou=3/tour=5/dame=9) et
  le compare au qualificatif trouvé à proximité dans le texte :
  - `"équilibré(e)"` : incohérent si le delta réel n'est pas nul ;
  - `"favorable"`/`"défavorable"` : vérifié SEULEMENT si un camp
    (Blancs/Noirs) est explicitement mentionné à moins de 30 caractères du
    qualificatif — sinon trop incertain, rien n'est signalé ;
  - une négation à moins de 20 caractères avant le qualificatif (« pas »,
    « jamais »...) désactive la vérification de cette occurrence (prudence :
    « ce n'est PAS un échange équilibré » affirme l'inverse, une inversion
    de sens par regex serait trop incertaine).
  - **Délibérément PAS vérifié** (prudence explicite, documenté dans le
    docstring du module et ci-dessous) : les verbes "gagne"/"perd" cités en
    exemple par l'issue — trop généraux en français (« gagner la partie »,
    « perdre du temps »...) pour être associés avec confiance à la suite
    citée juste avant, même avec un camp explicite à proximité. Mieux vaut
    ne rien signaler qu'un faux positif.
- `evaluer_fiabilite` appelle ce nouveau contrôle en plus des précédents et
  l'ajoute à la liste `controles` (documentation des limites, pour le
  rapport et pour `lire_signalements.py`).

### Tests effectués

- **Reproduction exacte du cas réel** (FEN de l'issue, vrai Stockfish 16,
  `depth=18`) : confirmé ci-dessus — Qxe8 seul coup qui évite le mat après
  Re8 (menace Qb8 mat décrite avec défenseurs), Be5 meilleure réponse après
  Re3 sans attaquer la tour en e3.
- **Vérification des échanges, textes simulés** (position FEN
  `4k3/8/6n1/4b3/8/4R3/8/4K3 w - - 0 1`, tour e3 / fou e5 défendu par
  cavalier g6) :
  - qualificatif FAUX (« Rxe5 Nxe5, l'échange reste équilibré ») → détecté,
    orange (écart 2 points, sous SEUIL_ECHANGE_GRAVE_PTS) ;
  - qualificatif FAUX avec camp explicite (« échange favorable pour les
    Blancs ») → détecté ;
  - qualificatif CORRECT (« favorable pour les Noirs ») → non détecté,
    vert ;
  - qualificatif AMBIGU (pas de mot-clé de camp, ou qualificatif absent) →
    non détecté, vert ;
  - qualificatif NIÉ (« ce n'est PAS un échange équilibré ») → non détecté
    (prudence sur la négation) ;
  - sur le cas réel Re8/Qxe8 (gain net de 5 points) avec qualificatif
    « équilibré » → détecté, **rouge** (écart ≥ SEUIL_ECHANGE_GRAVE_PTS).
- **Non-régression issue #90** (FEN `r1b1kbnr/pp3ppp/1qn1p3/1Bpp4/3PP3/
  2PQ1P2/PP4PP/RNB1K1NR b KQkq - 4 6`, textes exacts du changelog #90
  dont « Bxc6+ bxc6, un échange équilibré » — bishop contre cavalier,
  réellement équilibré) → toujours vert, aucune fausse alerte introduite
  par le nouveau contrôle.
- **Non-régression exercice h4** (FEN `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/
  2N3PP/PP3PK1/R1B2R2 w - - 0 23`) : `evaluer_fiabilite` sur un texte neutre
  → vert ; `get_reponses_adverses`/`build_reponse_adverse_obligee_texte`
  sur ce FEN (coup h4, vrai Stockfish) → aucune exception, texte cohérent
  (« plusieurs réponses se valent ... la meilleure selon Stockfish est
  Qg6 »).
- **`_build_context_text`** : contexte simulé complet (Re3/Re8, verdict
  blunder, les deux nouveaux champs `reponse_adverse_*`) → texte de
  contexte généré sans erreur, blocs insérés au bon endroit (juste après
  les lignes PV de chaque coup).
- **`app.py` s'importe et démarre le moteur sans erreur** (Stockfish 16
  détecté, Elo limité, WDL, Syzygy, eval breakdown — logs normaux).
- **py_compile** sur les 5 fichiers modifiés (`coach_reliability.py`,
  `engine_stockfish.py`, `game_facts.py`, `app.py`, `llm_coach.py`) et
  `node --check` sur `static/exercise.js` : OK.

### Limites (à documenter dans le rapport de clôture)

- Les réponses adverses alternatives ne sont câblées QUE dans le chemin
  principal du mode "Exercice" (`on_exercise_answer`, sources « mes
  erreurs » et « position précise » — pas la source « Problèmes Lichess »,
  qui n'a qu'un coup de solution unique et pas de comparaison coup
  proposé/meilleur coup de la même façon, ni les autres modes
  pédagogique/ouverture/finales) — portée volontairement limitée au
  périmètre exact du cas réel et du plan de test de l'issue.
- Aucun appel API Claude réel n'a pu être effectué (`ANTHROPIC_API_KEY`
  absente de l'environnement de cette session, pas de fichier `.env` dans
  ce worktree, non modifié conformément à la consigne) : la demande "poser
  la question sous Sonnet et sous Haiku" n'a pas pu être exécutée — vérifié
  à la place le contenu exact des données transmises (ci-dessus) et la
  construction du prompt système, comme demandé en repli par l'issue.
- Vérification des échanges : ne couvre que les suites d'AU MOINS DEUX
  captures et les qualificatifs "équilibré"/"favorable"/"défavorable" (ce
  dernier couple seulement avec camp explicite à proximité) — "gagne"/
  "perd" délibérément exclus (trop ambigus), une suite à un seul coup
  n'est jamais concernée par ce contrôle précis (mais reste couverte par
  les règles de prompt de la tâche 2 et par `detecter_suites_illegales`
  pour sa légalité).

# Changelog — Issue #90

## Coach : fiabilité 3 — le contrôle des coups cités ne signale plus à tort une suite légale, et `lire_signalements.py` affiche la pastille et sa raison

Cas réel ayant motivé cette issue (signalement d'Alain, 2 octobre 2026) :
exercice « Mes erreurs », FEN
`r1b1kbnr/pp3ppp/1qn1p3/1Bpp4/3PP3/2PQ1P2/PP4PP/RNB1K1NR b KQkq - 4 6`, coup
proposé c4 (imprécision), meilleur coup Nf6. La réponse du coach était
correcte (Stockfish confirme Nf6 ≈ +1,3, c4 ≈ +0,6 pour les Noirs, toutes
les lignes citées sont légales), mais la pastille est passée au rouge :
« coup cité "bxc6" illégal... », déclenchant une relance automatique
inutile. Cause : le contrôle introduit par l'issue #87 testait chaque coup
cité ISOLÉMENT sur la position de départ puis la position actuelle (trait
inversé compris) — alors que le coach cite des SUITES ("Bxc6+ bxc6", "Qc2
Nf6 Ne2"...), dont chaque coup ne devient jouable qu'après les précédents
de la même suite.

### 1. Suivi des suites de coups cités (`coach_reliability.py`)

- `_extraire_suites(texte)` (remplace l'ancienne extraction coup par coup) :
  regroupe les coups cités en SAN consécutifs dans le texte en suites —
  séparés uniquement par un espace, une virgule, un numéro de coup
  ("12."/"12..."/"6...") ou une annotation (!, ?, !?, ?!) ; tout autre texte
  interrompt la suite en cours (ex. "Après Nf6 Ne2 c4 ... la ligne continue
  Bxc6+ Qxc6" produit deux suites distinctes). Détecte aussi les suites
  "douteuses" : coup cité entre parenthèses, ou introduit par "si"
  (hypothèse jamais vérifiée, point 2).
- `_construire_candidats(...)` : construit, dans l'ordre demandé, les
  positions depuis lesquelles essayer de jouer une suite — position de
  départ, position actuelle, après le coup proposé, après le coup
  réellement joué, après le meilleur coup, puis CHAQUE position
  intermédiaire des lignes (PV) calculées par le moteur pour le coup
  proposé et pour le meilleur coup (en reprenant la suite à chacune de
  leurs étapes), et enfin le trait inversé des deux positions de référence
  directes (conservé de l'issue #87, pour un coup isolé cité du point de
  vue de l'adversaire).
- `_tenter_suite(coups, board)` : rejoue une suite coup par coup sur une
  COPIE de la position candidate, en distinguant trois issues :
  `chess.IllegalMoveError` (coup syntaxiquement valide mais impossible —
  seul cas qui compte comme un échec réel), et `chess.AmbiguousMoveError`/
  `chess.InvalidMoveError` (notation ambiguë ou invalide — jamais traitée
  comme une preuve d'illégalité, point 2).
- `detecter_suites_illegales(texte, candidats)` : une suite n'est signalée
  QUE si elle est injouable depuis TOUTES les positions candidates ET que
  cet échec n'est, sur aucune d'elles, une simple ambiguïté/notation
  invalide, ET qu'elle n'a pas été marquée "douteuse" à l'extraction. Les
  alertes portent désormais `coups_cites` et `positions_essayees` (liste
  des libellés essayés, dans l'ordre), pour le journal (point 3).
- `evaluer_fiabilite` accepte 5 nouveaux paramètres optionnels
  (`coup_propose`, `coup_reel`, `meilleur_coup`, `pv_coup_propose`,
  `pv_meilleur_coup`, tous `""` par défaut) transmis par l'appelant — sans
  eux, le contrôle se limite comme avant aux deux positions de référence.
- **Correctif annexe sur `_SAN_RE`** : la frontière de fin `\b` échouait
  silencieusement sur un coup se terminant par "+"/"#" suivi d'un espace
  (deux caractères non-mot consécutifs ne forment jamais une frontière
  `\b`) — "a8=Q+" était tronqué en "a8=Q", que python-chess rejette ensuite
  (il exige la notation d'échec exacte). Remplacé par une anticipation
  négative `(?!\w)`, qui accepte correctement tout caractère suivant non
  alphanumérique (espace, virgule, fin de texte) — nécessaire pour "gérer
  correctement les échecs et mats notés avec + ou #" (cahier des charges,
  point 2).

### 2. Prudence (point 2)

En cas de doute (coup isolé non rattachable à une suite résolue, notation
ambiguë/invalide, coup entre parenthèses ou introduit par "si"), rien n'est
signalé : pas de pastille orange ni rouge, pas de relance. Seule une suite
dont TOUS les points de départ essayés la rendent franchement illégale (pas
une ambiguïté) déclenche encore une alerte — donc toujours la relance
automatique UNIQUE existante (issue #87, point 4, non modifiée).

### 3. Journal (`llm_coach.py`)

- Les deux appels à `coach_reliability.evaluer_fiabilite` (réponse initiale
  et relance) transmettent désormais `coup_propose`/`coup_reel`/
  `meilleur_coup`/`pv_coup_propose`/`pv_meilleur_coup`, relus tels quels
  depuis `context` (déjà présents pour construire le texte de contexte
  envoyé au coach — rien de recalculé).
- Chaque alerte (`coup_illegal`) porte désormais `coups_cites` et
  `positions_essayees` — écrits tels quels dans l'entrée du journal
  (`fiabilite.alertes`, champ déjà journalisé par `_log_coach_call` depuis
  l'issue #87) : permet de juger après coup un éventuel faux positif sans
  deviner quelles positions ont été essayées.

### 4. `lire_signalements.py` (commande `sigcoach`)

- `_charger_index_journal()` : index `{id: entrée}` de tout
  `coach_calls.log` (toutes archives comprises), construit UNE SEULE FOIS
  par exécution plutôt que rescanné à chaque signalement affiché.
- `_trouver_entree_journal` accepte désormais cet index en paramètre
  optionnel (repli sur un chargement à la volée si omis — compatible avec
  l'usage existant dans `_texte_pret_a_coller`).
- `_lignes_pastille(journal)` (nouveau) : affiche la pastille (couleur +
  raison), l'avertissement éventuel (avant relance) et les contrôles
  déclenchés (type, détail, positions essayées) relus dans l'entrée du
  journal reliée par `log_id` — une seule ligne dédiée si cette entrée est
  introuvable (log_id absent ou archive déjà purgée), au lieu de rien
  afficher du tout. Câblé dans `_afficher_resume` (listing `--n`) ET
  `_texte_pret_a_coller` (`--dernier`).

### Tests effectués

- **Reproduction exacte du cas réel** (FEN de l'issue, textes calqués sur
  les passages cités : "Bxc6+ bxc6, un échange équilibré", "la suite Qc2
  Nf6 Ne2", "Après Nf6 Ne2 c4 ... la ligne continue Bxc6+ Qxc6") :
  `evaluer_fiabilite` → vert, aucune alerte. Vérifié aussi de bout en bout
  via `llm_coach.get_coach_response` avec `_call_claude` simulé (réponse
  fixe) : **1 seul appel API, aucune relance**, pastille verte — contre 2
  appels et une pastille rouge avant ce correctif (reproduit sur le code
  d'avant modification avant de corriger, pour confirmer le faux positif).
- **Casse jamais confondue** : `bxc6` (pion) isolé reste détecté illégal
  (rouge) sur la position de départ seule ; `Bxc6+` (fou) isolé reste
  légal (vert) — comportement identique avec ou sans la casse, aucune
  normalisation ne touche à la casse à aucune étape.
- **Suite légale citée depuis le coup réel/meilleur coup** : vérifié via le
  cas réel ci-dessus (suite "Nf6 Ne2 c4 Bxc6+ Qxc6" entière, point de départ
  = position de départ ; suite "Qc2 Nf6 Ne2", point de départ = position
  intermédiaire de `pv_coup_propose`).
- **Coup réellement illégal** (`Nxe3`, régression du cas Re3 de l'issue
  #87, FEN `Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35`) : toujours
  détecté, rouge, confirmé aussi de bout en bout (2 appels API, 1 relance,
  pastille rouge si la relance ne corrige pas).
- **Suite partiellement ambiguë** (position fictive à deux cavaliers
  pouvant tous deux rejoindre la même case, `Ne6` ambigu — confirmé
  `chess.AmbiguousMoveError` isolément) : rien signalé, pastille verte.
- **Coup entre parenthèses** ("si Txh8 les Noirs gagnent une pièce" entre
  parenthèses) et **coup hypothétique introduit par "si"** ("Si Dxd5
  alors...") : rien signalé dans les deux cas, pastille verte.
- **Roque, promotion, échec, mat, annotations, numéros de coup** : "12.
  O-O-O! et après ... Rb8" et "1. b8=Q+ et le roi noir est en échec" →
  vert dans les deux cas (le second a aussi servi à révéler puis corriger
  le bug de frontière `\b`/`(?!\w)` ci-dessus).
- **Non-régression** : texte neutre sur la position de l'exercice h4
  (`1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`,
  issue #80) → vert, aucun faux positif.
- **`lire_signalements.py`** testé avec des fichiers factices (jamais les
  fichiers réels d'Alain, écrits dans `/tmp` puis supprimés) : listing
  (`--n`) et `--dernier` affichent la pastille, l'avertissement et les
  contrôles déclenchés (avec positions essayées) d'une entrée existante ;
  une entrée introuvable (`log_id` inconnu) produit une ligne dédiée sans
  erreur.
- **Appel API réel** : non effectué — aucune `ANTHROPIC_API_KEY` ni fichier
  `.env` dans ce worktree isolé (`/home/alain/chesscoach-issue90`), conforme
  à la consigne de ne jamais lire ce fichier hors de l'usage normal de
  l'application. `_call_claude` simulé à la place (textes fixes calqués sur
  le cas réel), comme pour l'issue #87.
- `py_compile` sur `coach_reliability.py`/`llm_coach.py`/
  `lire_signalements.py` : OK.

### Limites assumées (documentées dans `coach_reliability.py`)

- Une ligne hypothétique qui ne part d'AUCUN des points de départ essayés
  (position de départ/actuelle, après coup proposé/réel/meilleur, étapes
  des deux PV) reste hors de portée — faux négatif assumé, jamais remplacé
  par une supposition sur une position non transmise.
- La détection "douteuse" (parenthèses, "si") est une heuristique textuelle
  simple (fenêtre de ~20 caractères avant/après le coup cité) — une
  tournure très différente exprimant la même prudence peut échapper à la
  détection et être vérifiée comme une affirmation normale.
- Ces contrôles ne vérifient toujours QUE des faits bruts (légalité,
  existence de pièce) — jamais la justesse stratégique ou tactique de
  l'explication.

# Changelog — Issue #89

## Bouton « Signaler » sur les réponses du coach : commentaire libre, lien avec le journal, script d'affichage prêt à coller

Jusqu'ici, signaler une explication fausse ou confuse du coach obligeait
Alain à retrouver l'entrée correspondante dans `data/logs/coach_calls.log`
avec des commandes Python composées à la main, puis à copier le résultat
pour Claude Chat — ce qui prenait du temps et perdait parfois l'explication
avant qu'il ait pu la chercher.

### 1. Identifiant unique par entrée du journal (`llm_coach.py`)

- `_log_coach_call` génère désormais un `id` (uuid4 abrégé, 12 caractères)
  pour chaque entrée écrite dans `coach_calls.log`, et le retourne (`None`
  si l'écriture échoue ou si aucun chemin de log n'est configuré) — sans
  cet identifiant, retrouver sans ambiguïté l'entrée correspondant à une
  réponse précise était impossible dès qu'un même coup/FEN se répétait dans
  une partie (ex. échecs par va-et-vient d'une tour, déjà rencontré issue
  #85).
- `get_coach_response` retourne désormais `(réponse, erreur, fiabilite,
  log_id)` (4-uplet, au lieu de 3) — mis à jour dans les 8 points d'appel
  d'`app.py`.
- `get_move_explanations` (sélection des coups décisifs du rapport
  d'analyse) attache un `log_id` par explication retenue.

### 2. Bouton « Signaler » (tous les modes, `static/board.css`/`board.js` + modules de mode)

- `_coachBuildSignalerUI` (`static/board.js`) : bouton « Signaler » discret
  (texte souligné terracotta, `--cc-accent`) sous toute réponse du coach.
  Un clic ouvre un champ de texte libre facultatif + bouton « Envoyer » ;
  l'envoi grise immédiatement le bouton (« Signalé ») — un signalement par
  message, sans accusé de réception attendu (jamais d'erreur visible en cas
  de panne d'écriture côté serveur).
- Intégré à `_coachRenderBubble` (nouveau paramètre `reportMeta`, 6ᵉ
  argument) : couvre uniformément le chat libre, le bouton « Demander
  l'avis du coach », les commentaires automatiques après chaque coup
  (pédagogique/ouverture/finales) et le verdict d'exercice — un seul point
  d'intégration pour tous ces modes, déjà partagé avant cette issue.
- Analyse de partie (`static/game_analysis.js`) : un bouton par commentaire
  de coup dans `renderGameAnalysisReport` (coups décisifs retenus par le
  coach ET explications à la demande), réutilisant la même fonction
  `_coachBuildSignalerUI` sur un bloc de rapport plutôt qu'une bulle de
  chat.
- `fen`/`move`/`mode_origine`/`log_id` transmis par le serveur dans chaque
  payload de réponse du coach (`app.py`, 8 points d'appel + la sélection de
  coups décisifs) — repris tels quels côté client, jamais recalculés.

### 3. Enregistrement (`app.py`, `config.py`)

- `config.SIGNALEMENTS_LOG_PATH` (`data/logs/signalements.log`, sous
  `DATA_DIR` donc gitignoré, pas de clé API ni contenu du `.env`).
- `on_signalement_envoyer` (nouveau handler SocketIO `signalement_envoyer`)
  + `_log_signalement` (best-effort, même pattern que `_log_analyse_erreur`
  existant) : une ligne JSON par signalement (horodatage, mode, `log_id`,
  FEN, coup, réponse signalée, commentaire d'Alain, `traite: false`). Une
  panne d'écriture (dossier non inscriptible...) reste entièrement
  invisible pour Alain — le client affiche sa confirmation sans attendre de
  réponse de ce handler.

### 4. Script de lecture (`lire_signalements.py`, racine du projet)

- Affiche les derniers signalements (`--n`), marque un signalement comme
  traité (`--traiter ID`).
- `--dernier` : texte complet prêt à coller dans un chat — commentaire
  d'Alain, mode, FEN, coup, réponse du coach, contexte envoyé au coach
  (allégé des champs volumineux, réutilise `lire_journal_coach._fichiers_journal`/
  `_charger_entrees`/`_contexte_allege` pour retrouver l'entrée via
  `log_id`), et la ligne principale de Stockfish (recalculée en direct sur
  la FEN signalée, jamais relue d'une éventuelle valeur déjà présente dans
  le journal qui peut être absente selon le mode).
- Commande pour afficher le dernier signalement :
  `python3 lire_signalements.py --dernier`

### Tests

- `py_compile` sur tous les fichiers Python modifiés + `node --check` sur
  tous les fichiers JS modifiés.
- Bout en bout réel (serveur de test sur un port dédié, client SocketIO
  Python) : écriture correcte dans `signalements.log`, nettoyé aussitôt
  après vérification.
- Navigateur réel (Playwright, Chromium) : viewports 390×750 et 360×640
  (`has_touch`) et bureau — bouton visible sous chaque réponse, formulaire
  tactile, confirmation + grisage après envoi, un signalement par message
  (deux bulles indépendantes), commentaire vide accepté, aucune erreur
  console, **aucun débordement horizontal** sur les trois largeurs.
- `renderGameAnalysisReport` (analyse de partie) testé directement avec des
  données factices : bouton par commentaire de coup, FEN/coup/log_id
  corrects dans le payload émis.
- `lire_signalements.py` testé avec des fichiers factices (jamais les
  fichiers réels d'Alain) : résumé, `--dernier`, `--traiter`, entrée du
  journal introuvable (`log_id` absent) gérée sans erreur.

# Changelog — Issue #87

## Coach : fiabilité des explications d'un coup (résumé du matériel, réponse adverse décrite, contrôle automatique, pastille de fiabilité)

Cas réel ayant motivé cette issue (journal du coach, entrée n°180, 2 octobre
2026, mode Exercice) : sur la position
`Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35` (coup proposé Re3,
verdict "erreur"), les données transmises au coach étaient déjà exactes
(listes de pièces, descriptions mécaniques) mais sa réponse a quand même
parlé d'un "échange tour contre tour" dans une position où un seul camp avait
une tour, et affirmé qu'un fou en e5 attaquait une tour en e3 — ce qui est
géométriquement faux. Un silence dans les données (aucune absence ni aucune
non-attaque dite explicitement) n'empêchait pas ces inventions.

### 1. Résumé du matériel (`game_facts.describe_material_summary`)

- Nouvelle fonction dans `game_facts.py` : matériel de chaque camp PAR TYPE
  de pièce (dame/tour/fou/cavalier/pion), avec les absences dites
  explicitement ("aucune tour"), le total en points classiques et
  l'équilibre matériel. Complète `describe_pieces_lists` (case par case,
  mais jamais explicite sur une absence totale d'un type).
- Jointe au contexte du mode Exercice (`materiel_resume_texte`, dans
  `app.py` — deux call sites, source "mes erreurs" et source "Problèmes
  Lichess") et automatiquement à `build_game_facts_text` (tous les modes de
  partie avec historique — libre, pédagogique, ouverture, finales, revue de
  bibliothèque), qui généralise ainsi les deux lignes "n'a plus de dame"
  déjà existantes à tous les types de pièces.
- Nouveau complément de system prompt `_MATERIEL_ADDENDUM` (`llm_coach.py`),
  ajouté dès que `materiel_resume_texte` est présent dans le contexte :
  interdiction explicite de parler d'échange/prise/perte d'un type de pièce
  marqué absent pour le camp concerné.

### 2. Réponse adverse décrite, y compris quand elle n'attaque PAS

- `game_facts._statut_attaque_case` (nouvelle fonction) : dit TOUJOURS
  explicitement si la pièce jouée au premier demi-coup d'une ligne (coup
  proposé ou meilleur coup) est désormais attaquée OU PAS attaquée après la
  réponse adverse immédiate — comble l'angle mort réel des descriptions
  mécaniques existantes, qui ne mentionnaient une pièce que lorsqu'elle
  était attaquée (silence total sinon, jamais une négation explicite).
- Câblée dans `describe_pv_with_balance` : le second demi-coup de toute
  ligne (`pv_coup_propose_detail`/`pv_meilleur_coup_detail`, déjà transmis
  au coach depuis l'issue #75) porte désormais cette mention. Sur le cas
  Re3, la description de Be5 se termine par "Tour blanche en e3 n'est PAS
  attaqué(e) par ce coup".
- Le premier coup de la ligne du meilleur coup était déjà transmis
  (`pv_meilleur_coup_detail`, issue #75) — vérifié non régressé.

### 3. Prompt : ancrage strict sur les données fournies

`_MATERIEL_ADDENDUM` (`llm_coach.py`) impose aussi :
- toute affirmation sur une attaque/défense/capture/échange doit se
  retrouver dans les descriptions mécaniques, les listes de pièces ou le
  résumé du matériel — sinon ne pas l'affirmer ;
- pour expliquer une ERREUR : partir d'abord de la ligne principale du coup
  proposé (ce que l'adversaire y répond, ce que cela change — pièce sauvée,
  avantage conservé, occasion manquée) et de la différence d'évaluation
  avec le meilleur coup, jamais d'un échange imaginé ;
- pour expliquer le MEILLEUR coup : s'appuyer sur sa ligne (ce qu'il gagne
  ou menace réellement) sans déformer son résultat — une dame gagnée pour
  une tour n'est jamais un "échange de tours".

### 4. Contrôle automatique après la réponse (`coach_reliability.py`, nouveau module)

- Contrôles déterministes (python-chess, aucun appel API supplémentaire),
  exécutés dans `llm_coach.get_coach_response` après chaque réponse :
  type de pièce absent cité (adjacent à une couleur, ex. "tour blanche"/
  "fou des Noirs"), nombre de pièces excessif cité, échange "type contre
  type" matériellement impossible (couvre justement le cas réel "échange
  tour contre tour", sans même avoir besoin d'associer une couleur), case
  citée incohérente avec la pièce annoncée, coup cité illégal en notation
  SAN.
- Si une incohérence est détectée : avertissement écrit dans l'entrée du
  journal du coach (champs `avertissement`/`fiabilite`, `_log_coach_call`
  étendu) et relance automatique UNIQUE (un rappel court de la règle
  enfreinte) — jamais une seconde relance même en cas de nouvel échec. Une
  panne pendant la relance (API, réseau) ne remonte jamais à Alain : la
  première réponse, déjà obtenue avec succès, reste celle retournée.
- Rien de visible pour Alain dans le cas normal (aucune incohérence
  détectée) : ni avertissement journalisé, ni relance.
- `get_coach_response` retourne désormais un triplet
  `(response, error, fiabilite)` au lieu d'un couple — les 8 points d'appel
  dans `app.py` et les 6 points de rendu correspondants côté client
  (`board.js`/`exercise.js`/`pedagogic.js`/`opening.js`/`finales.js`) ont
  été mis à jour en conséquence.

### 5. Pastille de fiabilité

- Badge coloré (vert/orange/rouge) ajouté par `_coachRenderBubble`
  (`board.js`) à côté de chaque réponse du coach rendue dans le chat partagé
  — mode Exercice, chat libre, "Demander l'avis du coach", pédagogique,
  ouverture, finales (tous les modes qui passent par cette fonction commune ;
  le rapport d'analyse de partie, qui a son propre rendu de rapport distinct
  du chat, n'a pas été câblé — hors péritmètre "si c'est simple").
- Vert = "aucune incohérence détectée par les contrôles automatiques — cela
  ne garantit pas que l'explication est juste" (texte explicite, jamais
  présenté comme une garantie). Orange = analyse partielle/indisponible OU
  relance automatique nécessaire (qu'elle ait corrigé ou non — dans ce
  second cas la couleur finale retombe en rouge, cf. point 4). Rouge =
  incohérence détectée et non corrigée après la relance.
- Lisible sans dépendre de la seule couleur : glyphe (✓/!/✕) ET texte court
  ("Fiabilité : OK"/"prudence"/"attention") en plus de la couleur. Couleurs
  (vert/orange-doré/rouge) volontairement différentes du terracotta
  (`--cc-accent`, réservé au cliquable d'après la règle de palette d'Alain).
- Un clic/tap bascule l'affichage de la raison complète (une phrase) ; un
  survol suffit sur desktop. Le détail s'affiche dans le FLUX NORMAL du
  document (jamais en position absolue superposée), pour ne jamais déborder
  du viewport à 390×750/360×640 — contrairement au risque déjà documenté
  pour `#eval-status-detail` (issue #82) que `position:fixed` avait dû
  corriger après coup ; choisi ici dès le départ pour l'éviter.
- Couleur et raison enregistrées dans l'entrée du journal du coach
  (`fiabilite` dans `_log_coach_call`).

### Tests effectués

- **Reproduction du cas Re3** (FEN de l'issue, vrai moteur Stockfish 16 à
  depth=18 via `EngineManager.evaluate_move`) : verdict "blunder" (871
  centipawns de perte), `pv_coup_propose` = "Re3 Be5 Qxa7 d4 Rd3 Kc8",
  `pv_meilleur_coup` = "Re8 Qxe8 Qxe8 b5 Qe6 Ne5" — conformes à la
  vérification Stockfish indépendante citée dans l'issue. Le texte de
  contexte réellement construit (`llm_coach._build_context_text`) contient
  bien : le résumé du matériel ("Noirs (adversaire) : 1 dame, aucune tour,
  1 fou, 1 cavalier..."), et la description de Be5 se terminant par "Tour
  blanche en e3 n'est PAS attaqué(e) par ce coup" ; Re8 est décrit comme un
  gain de dame (solde net +4 puis +9 points), jamais comme un échange de
  tours.
- **Appel API réel** : non effectué. Aucune `ANTHROPIC_API_KEY` n'est
  présente dans l'environnement de ce worktree isolé (`/home/alain/
  chesscoach-issue87`), et aucun fichier `.env` n'y a été déposé — conforme
  à la consigne de ne pas lire ce fichier en dehors de l'usage normal par
  l'application. Vérifié à la place le contenu exact des données envoyées
  (ci-dessus) et le comportement complet de `get_coach_response` avec
  `_call_claude` simulé (ci-dessous).
- **Contrôle automatique + relance**, `get_coach_response` avec
  `_call_claude` simulé (4 scénarios, tous conformes) :
  1. texte incohérent puis relance qui corrige → 2 appels API, réponse
     finale = la corrigée, pastille orange, avertissement journalisé ;
  2. texte incohérent et relance qui ne corrige pas → 2 appels API (jamais
     3e relance), réponse = la première, pastille rouge, avertissement
     journalisé ;
  3. texte correct dès le premier appel → 1 seul appel API, aucune relance,
     aucun avertissement journalisé, pastille verte ;
  4. panne simulée (exception) pendant l'appel de relance → aucune erreur
     remontée à l'appelant (`error is None`), réponse = la première réponse
     (déjà obtenue avec succès), pastille rouge, avertissement journalisé.
- **Pastille** : `coach_reliability.evaluer_fiabilite` vérifiée verte sur un
  texte correct, orange avec `analyse_indisponible=True`, rouge sur un texte
  simulé citant une pièce absente ("tour contre tour" dans une position sans
  tour noire) et sur un coup illégal cité ("Nxe3"). Rendu visuel capturé en
  Chromium headless à 390×750 et 360×640 (bulle de chat avec badge +
  détail déplié) : aucun débordement horizontal, texte et glyphe lisibles
  aux deux largeurs.
- **Non-régression** : `describe_material_summary`/`describe_pv_with_balance`
  exécutés sans exception sur la position de départ standard, une finale
  tour-contre-rien, une position de milieu de partie complexe avec roques
  des deux côtés, et sur la position de l'exercice h4
  (`1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`,
  issue #80) — aucun faux positif de `evaluer_fiabilite` sur un texte neutre
  dans ces positions. Un premier jet du contrôle "type de pièce absent"
  (association par clause entière) produisait un faux positif réel, détecté
  par ce test et corrigé AVANT la version finale (association exigée
  directement adjacente au nom de la pièce, ex. "tour blanche" — cf.
  limites documentées dans `coach_reliability.py`).
- `py_compile` sur `game_facts.py`/`coach_reliability.py`/`llm_coach.py`/
  `app.py`, et `node --check` sur les 5 fichiers JS modifiés : tous OK.
- **Non tenté** : un import complet de `app.py` (vérification de démarrage
  bout en bout) est resté bloqué plus de 2 minutes sans sortie exploitable
  dans cet environnement (probablement lié à l'initialisation réseau/
  SocketIO du module, indépendante de cette issue) — abandonné conformément
  à la consigne de ne jamais insister sur une commande sans progrès ; les
  tests ciblés ci-dessus (import direct des modules modifiés, appels de
  fonctions réels) couvrent le même code sans ce blocage.

### Limites assumées (documentées aussi dans l'en-tête de `coach_reliability.py`)

- Détection par expressions régulières sur le français, pas par compréhension
  du langage : une tournure inhabituelle peut échapper à la détection (faux
  négatif), couvert par la marge de prudence de la pastille orange/vert
  plutôt qu'une garantie.
- Couleur exigée directement adjacente au nom de la pièce (ex. "tour
  blanche") : une couleur exprimée plus loin dans la phrase n'est jamais
  associée à tort, mais peut donc ne pas être détectée.
- Contrôles "case/pièce" et "coup illégal" : ne connaissent que la position
  de départ et la position actuelle transmises — un coup ou une case d'une
  ligne hypothétique plus profonde peuvent être signalés à tort, ou une
  vraie erreur sur une position intermédiaire peut passer inaperçue.
- Ces contrôles ne vérifient JAMAIS la justesse stratégique ou tactique de
  l'explication, seulement des faits bruts : une réponse peut rester fausse
  sur le fond sans déclencher la moindre alerte (d'où le texte systématique
  de la pastille verte, qui ne prétend jamais garantir une réponse juste).
- Pastille câblée sur le rendu de chat partagé (`_coachRenderBubble`), pas
  sur le rapport d'analyse de partie (`analyse_expliquer_coup_response`,
  rendu dans un tableau séparé par `game_analysis.js`) — laissé de côté
  faute d'être "simple" à intégrer dans ce rendu différent.

### Fichier non touché

`.env` n'a pas été lu ni modifié.

# Changelog — Issue #86

## Mobile : plateau réduit stabilisé (hystérésis), bandeau de fin de partie compact, onglets remis en haut, conversation du coach propre à chaque mode, avertissement moteur corrigé

Suite des tests GSM sur l'issue #81 : `static/mobile_game.js`,
`static/board.js`, `static/controls.js`, `templates/index.html`,
`engine_stockfish.py`.

### Point 2 — Règle du plateau réduit (AVANT / APRÈS)

**Règle AVANT cette issue** (`_updateBoardCompactState`, `mobile_game.js`) :
un seul seuil de défilement (`BOARD_COMPACT_SCROLL_THRESHOLD = 24px`)
pilotait les DEUX sens via `wrap.classList.toggle("board-compact", focused
|| scrolled)` — le plateau redevenait complet dès que `scrollY` repassait
sous 24px, pas seulement en remontant tout en haut. Deux conséquences
observées par Alain : (1) aucune hystérésis — un micro-défilement autour du
seuil faisait battre le plateau entre les deux tailles ; (2) cette bascule
changeant elle-même la hauteur de `#board-sticky-wrap` (collé en haut), un
geste de défilement tactile en cours pouvait redéclencher la mesure au tick
suivant — oscillation perçue comme aléatoire. Par ailleurs,
`_isCurrentGameRunning()` excluait aussi bien l'état "avant toute partie" que
l'état "partie terminée" du plateau réduit : juste après un abandon/un mat,
le plateau restait donc toujours forcé en complet, quelle que soit la
hauteur du contenu de l'onglet ouvert.

**Règle APRÈS** :
- `_updateBoardCompactState()` (défilement/clavier) est désormais **purement
  additive** pour le passage en réduit (`wrap.classList.add(...)`, jamais
  `toggle`) : un défilement au-delà de 24px ou le focus du champ de question
  ajoute l'état réduit, mais plus rien ne le retire automatiquement en
  cours de route.
- Le **seul** retrait piloté par le défilement reste `scrollY <= 0` strict
  (remontée tout en haut de la zone) — un seuil différent de celui de
  déclenchement (hystérésis : 24px à l'aller, 0px au retour).
- Les 4 actions de retour prévues par la tâche restent les seules à
  redonner le plateau complet : toucher le plateau réduit
  (`boardCompactExpand`), un coup joué (`_forceBoardFull`, appelée par
  `_mobileGameOnMoveCountChanged`), la lecture d'une ligne ("Play",
  `_linePlaybackActive()` court-circuite tout l'état réduit), et la
  remontée tout en haut ci-dessus. Aucune autre voie ne retire la classe.
- `_isGameSessionActive()` (nouveau) = `_isCurrentGameRunning() ||
  body.classList.contains("game-over-active")` remplace
  `_isCurrentGameRunning()` dans les deux gardes (`_updateBoardCompactState`,
  `_autoCompactForOverflow`) : le plateau réduit redevient utilisable juste
  après la fin d'une partie (abandon/mat), pas seulement pendant qu'elle est
  en cours. `showGameOverBanner()` (`board.js`) appelle désormais
  `_mobileGameOnGameOver()` (nouveau) qui relance tout de suite
  `_autoCompactForOverflow()` : si l'onglet déjà ouvert déborde au moment où
  la partie se termine, le plateau passe en réduit sans attendre un
  défilement ou un changement d'onglet.
- **Contenu qui arrive après coup** (résultats d'analyse qui se chargent,
  tableau des lignes qui se peuple) : un `ResizeObserver` générique sur les
  4 panneaux d'onglets (`_ensureGameTabPanelsObserved`, nouveau) appelle
  `_autoCompactForOverflow()` à chaque changement de taille, plutôt que de
  devoir ajouter un appel explicite dans chaque fichier qui peut faire
  grandir leur contenu. Garde-fou propre à cet observateur (asynchrone, donc
  pouvant se déclencher après la remise à plat d'`onGameUiRefresh()`) : il
  ignore son propre déclenchement tant que `scrollY<=0` ET qu'aucune partie
  n'est terminée — sans ce garde-fou, un test Playwright de cette issue a
  montré qu'il cassait la garantie de l'issue #71 point 2 ("jamais avant
  d'avoir vu le plateau complet une seule fois") en rebasculant le plateau
  en réduit juste après l'arrivée sur un mode de partie, à cause du contenu
  de base (encore vide) de l'onglet Coach qui venait d'être déplacé dans son
  panneau.

### Point 1 — Bandeau de fin de partie compact

- `#mobile-game-over-bar` (`templates/index.html`) : AVANT, le texte de
  résultat était en `flex: 1 1 100%` (sa propre ligne) et les deux boutons se
  répartissaient la largeur sur la ligne suivante — deux lignes dans les
  faits malgré le commentaire de l'issue #77 qui visait une seule ligne.
  APRÈS : `flex-wrap: nowrap`, texte en `flex: 1 1 auto` + `min-width: 0` +
  ellipse (`text-overflow: ellipsis`) plutôt que de forcer sa propre ligne,
  boutons `flex: 0 0 auto` (jamais tronqués, toujours pleinement cliquables)
  avec une police/un remplissage réduits (0.72rem/6px 8px au lieu de
  0.8rem/8px 6px). Mesuré (Playwright, voir plus bas) : hauteur totale
  passée de 105px (3 lignes avec un message long) à 42px (1 ligne, quel que
  soit le message) — compact mais les boutons restent lisibles et cliquables.
- Reste masqué en plateau réduit (règle CSS déjà existante depuis l'issue
  #77, listée avec `#review-controls`/`#shared-mode-controls`) — désormais
  réellement atteignable juste après une fin de partie grâce au point 2
  ci-dessus (avant cette issue, le plateau restait forcé en complet après
  une fin de partie, donc cette règle ne s'appliquait jamais en pratique).
  Choix retenu parmi les deux options de la tâche : rendu compact **et**
  disparition en plateau réduit (pas de sortie de la partie fixe, qui
  aurait demandé de déplacer son nœud DOM hors de `board-sticky-wrap` et
  changé l'ordre d'affichage sans bénéfice supplémentaire une fois la bande
  elle-même compacte).

### Point 3 — Onglets remis en haut à chaque changement

- `switchGameTab()` (`mobile_game.js`) : à chaque VRAI changement d'onglet
  (`tabKey !== _currentGameTab` — pas aux réappels internes
  d'`onGameUiRefresh()` avec le même onglet, par ex. après chaque coup),
  `window.scrollTo(0, 0)` remet la zone de contenu en haut (même principe que
  `switchModeTab`, `controls.js`, issue #71 point 2).
- Le `scrollTo` déclenche un évènement `scroll` natif asynchrone qui repasse
  par `_updateBoardCompactState()` (déjà posé en écouteur au chargement de
  page, donc appelé AVANT tout nouvel écouteur ajouté après coup) et force
  le plateau complet (`scrollY<=0`) — potentiellement par-dessus la décision
  "le nouvel onglet déborde encore" de `_autoCompactForOverflow()`. Pour que
  cette dernière garde le dernier mot sans jamais annuler la remontée en
  haut elle-même, un second appel est différé d'un tick
  (`setTimeout(…, 0)`), qui s'exécute après cet évènement.
- Vérifié (Playwright) : après un onglet Coach rempli de 25 messages longs
  (défilé à 900px), passage successif à Lignes/Analyse/Coups — les trois
  onglets atterrissent à `scrollY = 0` avec le début de leur contenu dans le
  viewport (`panel.getBoundingClientRect().top < innerHeight`), et restent
  défilables (le plateau réduit se réengage immédiatement si le nouveau
  contenu déborde encore, cf. point 2).

### Point 4 — Conversation propre à chaque mode

- `switchModeTab()` (`controls.js`) : appelle désormais `coachClear()`
  (`board.js`, déjà utilisée par le bouton "Effacer") dès que `tabKey !==
  currentModeTab` (évalué AVANT la réaffectation) — un VRAI changement de
  mode (Exercice → Partie pédagogique, Bibliothèque → Éditeur, etc.) vide
  l'affichage (`#coach-history`) ET l'historique envoyé à l'API
  (`_coachHistory = []`, `_coachSegmentStart = 0`). Revisiter l'onglet déjà
  actif (reclic, ou réouverture du menu déroulant mobile, qui rappelle
  `switchModeTab` avec la même clé) ne déclenche rien.
- Les traits de séparation "Nouvelle partie"/"Nouvel exercice"
  (`coachNewSegment`, appelée au démarrage effectif d'une partie/d'un
  exercice, jamais à la navigation) et le comportement déjà en place pour
  les exercices sont inchangés — `coachClear()` remet de toute façon
  `_coachHistory`/`_coachSegmentStart` à zéro, un segment précédent n'a donc
  plus rien à séparer une fois qu'on a changé de mode.
- Vérifié (Playwright) : 2 messages injectés en mode Exercice (affichage +
  `_coachHistory`) → revisite du même onglet Exercice → les 2 messages et les
  2 entrées d'historique restent intacts → changement réel vers Partie
  pédagogique → affichage et historique à 0 dans les deux cas.

### Point 5 — Avertissement moteur (coup nul, issue #80)

- Cause confirmée : `EngineManager.get_threats()` (`engine_stockfish.py`)
  construisait `board_nul` par `board.copy()` (garde tout l'historique de la
  position réelle) `+ push(chess.Move.null())`, puis transmettait ce plateau
  tel quel à `get_multipv()` → `engine.analyse()`. python-chess
  (`chess/engine.py`, `_position()`) refuse de transmettre un historique
  contenant un coup nul au moteur UCI (`safe_history = all(board.move_stack)`,
  un coup nul est "falsy") et journalise `WARNING:chess.engine:Not
  transmitting history with null moves to UCI engine` avant de retomber de
  toute façon sur la position seule (même résultat, juste bruyant).
- Correctif (une ligne ajoutée) : après avoir poussé le coup nul pour obtenir
  la bonne position, reconstruction d'un plateau **neuf à partir du FEN**
  (`board_nul = chess.Board(board_nul.fen())`) avant l'appel à
  `get_multipv()` — `move_stack` vide, donc plus aucun coup nul ne peut
  déclencher l'avertissement ; seule la position compte pour l'évaluation,
  le résultat est donc identique.
- Autre source recherchée (`grep -rn "Move.null()"`) : un seul autre usage,
  dans `game_facts.py` (`describe_menace_adverse`), qui construit déjà un
  plateau neuf depuis un FEN (`chess.Board(fen_avant)`) uniquement pour
  obtenir un FEN texte — aucun appel moteur, donc aucun risque
  d'avertissement là. Pas d'autre source identifiée.
- Vérifié par un script isolé (`EngineManager` réel sur `/usr/games/stockfish
  16`, capture du logger `chess.engine`) : AVANT le correctif (reproduit en
  appelant `get_multipv` directement sur l'ancien `board_nul`), la ligne
  `Not transmitting history with null moves to UCI engine` apparaît bien
  (sanity-check que le test détecte réellement l'avertissement). APRÈS le
  correctif, sur une position avec un historique réel (5 coups joués,
  `get_threats(board, depth=10, n=2)`), le journal capturé est vide et les
  menaces sont calculées normalement (`disponible: true`, 2 coups avec leurs
  `cp`/`perte_cp`).

### Tests (Playwright/Chromium, gabarit réel rendu directement par Jinja2)

Comme pour les issues mobiles précédentes, aucun appel réel à l'API Claude ni
au serveur Flask/SocketIO complet : `templates/index.html` est rendu par un
petit serveur Flask jetable (`_test_harness/serve.py`, non commité) avec un
contexte minimal simulé, servant le CSS/JS réel du dépôt — l'état de partie
(`pedagogicActive`, `pedagogicGame`...) et les messages du coach sont
injectés via `page.evaluate()` en appelant les vraies fonctions
(`switchModeTab`, `setActiveMode`, `showGameOverBanner`, `coachClear`...),
jamais de logique dupliquée à la main. Viewports 390×750 et 360×640,
`is_mobile=True, has_touch=True`.

- **Oscillation au défilement** (390×750 et 360×640, onglet Coach avec 25
  messages longs, partie pédagogique en cours) : défilement pas à pas de 0 à
  1140px puis retour à 0px par incréments de 60px — **0 bascule** pendant
  toute la descente (reste compact du début à la fin, puisque le contenu
  déborde déjà), **1 seule bascule** pendant la remontée, exactement à
  `scrollY = 0` (le retour explicite au plateau complet) — aucune
  oscillation incohérente entre-temps, conforme à la règle corrigée.
- **Part de hauteur disponible pour le contenu, 3 réglages** (pendant une
  partie pédagogique active, plateau non réduit) :

  | Écran | Réglage | Plateau | Contenu visible sous les onglets |
  |---|---|---|---|
  | 390×750 | Compact | 231px | 150px (20,0 %) |
  | 390×750 | Normal | 281px | 100px (13,3 %) |
  | 390×750 | Grand | 321px | 60px (8,0 %) |
  | 360×640 | Compact/Normal/Grand | 170px (plancher) | 52px (8,1 %) |

  À 390×750, les 3 réglages se différencient désormais correctement (avant
  le correctif du point 2, un bug de l'observateur de redimensionnement
  faisait basculer le plateau en réduit dès l'arrivée sur le mode, et les 3
  réglages retombaient tous sur le même plancher `clamp(150px,42vw,170px)` —
  42 % de 390 = 163,8px dans les 3 cas, bug repéré et corrigé pendant cette
  session, cf. point 2). À 360×640, l'écran est trop étroit pour que les 3
  réglages se différencient pendant une partie active (les trois atteignent
  le plancher `GAME_BOARD_MIN_SIZE`), comportement déjà documenté comme
  attendu depuis l'issue #81.
- **Bandeau de fin de partie, une ligne** (isolé des effets du plateau
  réduit, classes appliquées directement) : hauteur mesurée à **42px** à
  390×750 et 360×640, quelle que soit la longueur du message de résultat
  (testé avec un message volontairement long : toujours 42px, texte tronqué
  en ellipse, aucun débordement horizontal
  `document.documentElement.scrollWidth === clientWidth`). AVANT (ancien
  CSS reproduit avec `page.add_style_tag`) : 105px sur le même message long
  (texte sur 3 lignes). Boutons "Analyser cette partie"/"Nouvelle partie"
  toujours visibles et cliquables dans les deux cas (captures d'écran,
  `_test_harness/shot_banner_*`).
- **Onglet Analyse qui déborde après un abandon** (contenu injecté APRÈS la
  fin de partie, simulant des résultats d'analyse qui arrivent en différé) :
  le plateau passe en réduit automatiquement (`board-compact` devient vrai)
  sans action de l'utilisateur, aux deux largeurs testées.
- **Séquence Coach long → Lignes → Analyse → Coups** : les 3 onglets
  atterrissent à `scrollY = 0` avec leur contenu visible dans le viewport.
- **Conversation par mode** : 2 messages (affichage + historique API)
  injectés en mode Exercice → revisite du même onglet → les 2 messages et
  les 2 entrées d'historique restent → changement réel vers Partie
  pédagogique → affichage et historique à 0 dans les deux cas.
- **Actions de retour explicites, non-régression** : toucher le plateau
  réduit (`boardCompactExpand`) le ramène en complet et remonte en haut ;
  jouer un coup (`_mobileGameOnMoveCountChanged`) force le plateau complet
  même en plein défilement ; démarrer la lecture d'une ligne
  (`gameCoachLinesPlayingIdx`) force le plateau complet quel que soit le
  défilement — les 3 vérifiées indépendamment, toutes correctes après le
  correctif.
- Captures d'écran prises pendant la session (plateau complet en partie
  pédagogique réglage Grand, bandeau de fin de partie compact une ligne,
  message long tronqué avant/après correctif) — outillage de test
  (`_test_harness/` : serveur Flask jetable + script Playwright + captures)
  supprimé du disque après vérification, jamais commité.

### Limites

- Aucun appel réel à l'API Claude ni au serveur Flask/SocketIO complet (pas
  de `RESEAU`, contexte simulé côté Jinja2 comme les issues mobiles
  précédentes) — l'état de partie/les messages du coach sont injectés
  directement en JS plutôt que joués via de vrais échanges réseau.
- `--bd-size-game-max` reste figé (non remesuré) pendant tout l'état "partie
  terminée" (`game-over-active`, limitation déjà en place depuis l'issue
  #77, volontairement conservée) : le plateau peut rester légèrement plus
  petit que nécessaire juste après une fin de partie, jamais plus grand que
  l'espace réellement disponible — sans conséquence pratique puisque la
  bande de fin de partie compacte (point 1) prend de toute façon moins de
  place que les contrôles de partie actifs qu'elle remplace. Si le contenu
  de l'onglet ouvert déborde malgré cette valeur figée,
  `_mobileGameOnGameOver()`/le `ResizeObserver` des panneaux passent de
  toute façon directement en plateau réduit (point 2).
  - Les chiffres de la table "part de hauteur disponible" ci-dessus sont
  mesurés sur le gabarit réel mais avec un contexte minimal simulé (pas de
  vraie conversation, pas de vrai historique de coups) — l'ordre de grandeur
  et les écarts relatifs entre réglages sont fiables, les valeurs absolues
  peuvent différer légèrement d'un appareil réel avec du contenu réel.
- Pas de test sur un véritable appareil physique (GSM/PC) ni dans un vrai
  navigateur mobile (Safari iOS, Chrome Android) — seule l'émulation de
  viewport/tactile de Chromium a été utilisée.
- `.env` non touché.

# Changelog — Issue #85

## Journal du coach : couverture de tous les points d'appel, rotation/limite de taille, script de lecture

`llm_coach.py`, `app.py`, `lire_journal_coach.py` (nouveau, racine du dépôt).

### Couverture (part. 1)

Recensement de tous les points d'appel à l'API du coach (9 appels à
`get_coach_response`, plus `get_move_explanations`, `get_opening_moves`,
`get_training_program`) :

- Déjà journalisés avant cette issue : les 9 appels à `get_coach_response`
  (exercice, exercice Lichess, pédagogique, ouverture, finales, chat libre,
  "Demander l'avis du coach", "Expliquer ce coup" en analyse de partie,
  question de suivi `coach_ask`).
- **Non journalisés avant cette issue** (cause du commentaire introuvable
  signalé par Alain) :
  - `get_move_explanations` (étape 1 du module d'explications narratives de
    l'analyse de partie, `on_analyse_choisir_coups_decisifs` — le
    commentaire "coup 6...Nf6, Erreur -117cp, Bb4" vient de ce chemin) ;
  - `get_opening_moves` (identification des coups caractéristiques d'une
    ouverture, `on_opening_start`) ;
  - `get_training_program` (bouton "Établir mon programme d'entraînement",
    `on_training_program_build`).
  Dans les trois cas, `coach_log_path` était déjà transmis dans `llm_config`
  côté `app.py` mais ignoré côté `llm_coach.py` — correction uniquement
  côté `llm_coach.py`.
- `get_move_explanations` journalise désormais **une entrée par coup
  réellement expliqué** (pas une entrée unique pour tout l'appel groupé) :
  `context` porte `fen`/`move`/`coup_plein`/`camp`/`verdict_qualite`/
  `verdict_delta_cp`/`meilleur_coup`, cohérent avec les entrées "fen"/"move"
  déjà utilisées par `on_analyse_expliquer_coup` (analyse de partie à la
  demande) et par l'exercice. Le FEN ("fen_avant") est ajouté par
  `app.py::_prepare_flagged_moves_for_coach` uniquement pour ce logging —
  retiré par `get_move_explanations` avant tout envoi à l'API (jamais
  transmis au coach, coût de tokens inchangé).
- `get_opening_moves`/`get_training_program` journalisent une entrée par
  appel, `mode_origine` dédié (`ouverture_coups` / `programme_entrainement`)
  distinct des `mode_origine` déjà utilisés par le chat coach.
- Format des entrées existantes inchangé (mêmes clés : horodatage,
  mode_origine, model, system_prompt, context, messages, reponse, erreur,
  usage).

### Taille maîtrisée (part. 2)

- Rotation mensuelle dans `_log_coach_call` (`llm_coach.py`) :
  `coach_calls.log` → `coach_calls-AAAA-MM.log`, un fichier par mois. Le
  fichier d'origine (sans suffixe, 184 entrées/4 Mo accumulées depuis
  septembre) n'est plus jamais réécrit — il reste tel quel, comme l'archive
  la plus ancienne, et demeure lisible par le script de lecture.
- Limite de taille totale réglable en un seul endroit :
  `llm_coach._COACH_LOG_MAX_TOTAL_MB` (20 Mo par défaut). Après chaque
  écriture, `_purge_vieux_logs_coach` supprime les archives mensuelles les
  plus anciennes tant que la taille totale (actif + archives) dépasse cette
  limite — jamais le fichier du mois en cours, même s'il la dépasse seul.
- Panne d'écriture (dossier non accessible, disque plein...) : déjà
  entourée d'un `try/except Exception` best-effort avant cette issue (juste
  un `logger.warning` interne) ; la rotation/purge est ajoutée À
  L'INTÉRIEUR de ce même bloc, donc couverte par la même garantie — testé
  avec un dossier en lecture seule (voir Tests).
- Dédoublonnage du system prompt par empreinte (évalué, PAS implémenté) :
  voir section "Limites" ci-dessous.

### Script de lecture (part. 3)

`lire_journal_coach.py` (nouveau, racine du dépôt) : lecture JSON Lines du
fichier actif et de toutes les archives mensuelles, filtres `--mode`
(mode_origine exact), `--mot` (recherche insensible à la casse dans toute
l'entrée), `--date` (préfixe de l'horodatage ISO), `--coup` (numéro de
coup, `context.coup_plein`), `--n` (nombre d'entrées, défaut 10),
`--log-dir` (dossier de test, sinon celui de `config.COACH_CALLS_LOG_PATH`).
Pour chaque entrée : horodatage/mode/modèle, position (FEN), coup (+
numéro), contexte allégé (tous les champs sauf `pgn`/`faits_calcules`,
volumineux et peu utiles à une relecture rapide), dernière question
("user" le plus récent dans `messages`) et réponse/erreur.

Commande (une ligne) :
```
python3 lire_journal_coach.py --n 10 --mode analyse_partie --mot "Bb4" --date 2026-10-02 --coup 6
```
(chaque filtre est optionnel et indépendant ; sans aucun filtre, affiche
les 10 dernières entrées toutes origines confondues).

### Confidentialité (part. 4)

- `data/` est déjà exclu par `.gitignore` (ligne existante, vérifiée — rien
  à modifier) ; `*.log` est également exclu en plus, par précaution
  générale. Le journal (sous `DATA_DIR/logs/`) reste donc hors git.
- Aucune entrée ne contient la clé API : `_call_claude`/`_log_coach_call` ne
  reçoivent et n'écrivent jamais `api_key` — vérifié par test (voir
  ci-dessous).

### Tests

Aucun appel réseau réel (en-tête de l'issue : RESEAU=non) — `llm_coach.
_call_claude` a été remplacé par une fonction factice (monkeypatch) dans un
harnais de test isolé, sous `.test_tmp/` (jamais committé, supprimé après
exécution), avec un `log_path`/`log_dir` pointant dans ce même dossier
temporaire du worktree — jamais vers `~/ChessCoach/data` (hors périmètre de
ce worktree, non touché). `parties_test_coach.pgn`, mentionné par l'issue,
existe sur la machine mais hors du périmètre strict de ce worktree
(`~/Téléchargements/...`) : non utilisé, remplacé par un coup flagué
synthétique représentatif (6...Nf6, -117cp, meilleur coup Bb4 — le cas
exact signalé par Alain).

Scénarios validés :

1. **Analyse de partie** (`get_move_explanations`) : 1 coup flagué simulé →
   1 entrée journalisée, `context.fen`/`move`/`coup_plein`/`camp`/
   `verdict_delta_cp`/`meilleur_coup` corrects, réponse = l'explication
   reçue, `fen_avant` absent du payload réellement envoyé à l'API (vérifié
   sur les arguments reçus par la fonction factice).
2. **Exercice** (`get_coach_response`, mode_origine=exercice) : entrée
   journalisée (comportement déjà correct avant cette issue, non régressé).
3. **Partie libre / question de suivi** (`get_coach_response`,
   mode_origine déduit `chat_libre`) : entrée journalisée.
4. **Partie pédagogique** (`get_coach_response`, mode_origine=pedagogique) :
   entrée journalisée.
5. **`get_opening_moves`** et **`get_training_program`** (nouvellement
   journalisés) : une entrée chacun, mode_origine `ouverture_coups` /
   `programme_entrainement`.
6. Script `lire_journal_coach.py --log-dir .test_tmp/logs` : retrouve
   l'entrée "coup 6...Nf6" par `--mot Bb4`, par `--coup 6`, par `--mode
   analyse_partie`, par `--date` (jour du test) ; `--mode foo_bar`
   (inexistant) affiche "Aucune entrée ne correspond." sans erreur ;
   `--log-dir` inexistant affiche un message clair (code de sortie 1, pas
   de trace Python).
7. **Rotation + limite de taille basse** : `_COACH_LOG_MAX_TOTAL_MB` abaissé
   à 1 Mo en mémoire, 3 fausses archives mensuelles de 512 Ko ajoutées +
   fichier actif → après écriture, les archives les plus anciennes sont
   supprimées, le fichier actif est conservé, taille totale repassée sous
   la limite (543 Ko constatés sur 1024 Ko). Les archives restantes, avec
   du contenu non-JSON (simulation), ne font pas planter la lecture
   (lignes invalides ignorées silencieusement, par le code de lecture déjà
   existant ET par `lire_journal_coach.py`).
8. **Dossier de logs non inscriptible** (`chmod 0500`) : la réponse du coach
   est quand même retournée sans erreur visible pour l'appelant (seul un
   `logger.warning` interne, déjà le comportement avant cette issue).
9. **Clé API absente** : recherche de la clé factice utilisée dans le test
   sur le contenu brut de tous les fichiers de journal écrits — absente.
10. Anciennes entrées lisibles par le script : confirmé (le fichier
    d'origine, jamais réécrit après la rotation, reste inclus dans le motif
    de recherche `coach_calls*.log`).

`py_compile` sur `app.py`, `llm_coach.py`, `lire_journal_coach.py` : OK.

### Limites

- **Dédoublonnage du system prompt par empreinte** (demandé par l'issue
  comme piste à évaluer, pas à implémenter par défaut) : jugé **pas assez
  simple/sans risque** pour l'implémenter dans cette issue. Le system
  prompt varie presque à chaque appel (mémoire du coach + contexte de
  position concaténés dedans), donc peu d'entrées partageraient
  réellement la même empreinte ; implémenter un stockage par référence
  obligerait à maintenir un fichier d'index séparé, à le synchroniser avec
  la rotation/purge (ne jamais supprimer une empreinte encore référencée
  par une entrée vivante), et à adapter le script de lecture — complexité
  et risque (empreinte orpheline après une purge mal synchronisée)
  disproportionnés par rapport au gain, déjà couvert par la rotation
  mensuelle + la limite de taille totale. Non implémenté.
- Test de bout en bout (vrai appel API Claude, vraie partie importée) non
  effectué : RESEAU=non dans l'en-tête de l'issue, et la donnée réelle
  (`~/ChessCoach/data/logs/coach_calls.log`, `parties_test_coach.pgn`) est
  hors du périmètre strict de ce worktree. Les 10 scénarios ci-dessus
  couvrent la logique unitairement (mock de `_call_claude`) mais pas le
  trajet complet SocketIO → navigateur.
- La purge par taille totale compare au nom de fichier (tri chronologique
  par préfixe `AAAA-MM`), pas à la date de dernière modification : fiable
  tant que l'horloge système n'est pas modifiée manuellement entre deux
  mois.

# Changelog — Issue #83

## Exercice : choix de la catégorie des problèmes Lichess, « Position précise » (FEN) et énoncé visible à côté du plateau

Suite des issues #78 (source « Problèmes Lichess ») et #63/#76 (feuille
« Nouvel exercice » mobile) : `lichess_puzzles.py`, `app.py`,
`static/exercise.js`, `templates/index.html`.

### 1. Choix de la catégorie (`lichess_puzzles.py`, `app.py`)

- `lichess_puzzles.tirer_probleme` accepte un nouveau paramètre
  `categorie_forcee` (une des 16 clés de `CATEGORIES`, ou `None` pour le
  tirage pondéré automatique d'origine, inchangé) et retourne désormais un
  triplet `(entree, categorie, avertissement)` au lieu d'une paire.
  **Combinaison phase/catégorie** : en automatique, la phase filtre d'abord
  l'ensemble des catégories compatibles, puis une catégorie est tirée parmi
  elles (pondérée par niveau) — comportement d'origine inchangé. Catégorie
  imposée : c'est l'inverse — on filtre d'abord par catégorie, puis on tente
  d'appliquer la phase ; si l'intersection catégorie+phase est vide, la
  **phase est ignorée pour ce tirage** et un avertissement d'une phrase est
  renvoyé (`"Aucun problème de catégorie « X » pour cette phase de partie :
  la phase a été ignorée pour ce tirage."`) plutôt que d'échouer le tirage
  ou de rester silencieux sur l'écart. La tranche de note reste choisie
  automatiquement d'après le niveau d'Alain dans la catégorie (imposée ou
  tirée) — seule la catégorie elle-même devient un choix explicite.
- `app.py` : `on_exercise_new` lit `data.categorie` (`"automatique"` par
  défaut) et le transmet à `_on_exercise_new_lichess`, qui ignore
  silencieusement une clé non reconnue (repli sur automatique). L'événement
  `exercise_position` transporte deux champs en plus pour la source
  `"lichess"` : `categorie_demandee` (le choix explicite, pour qu'"Exercice
  suivant" le reproduise) et `avertissement` (la phrase ci-dessus, ou
  `None`).
- `index()` passe au gabarit `lichess_categories_triees` (les 16 catégories
  triées par libellé français) pour générer les `<option>`/pastilles sans
  dupliquer la liste côté client.

### 2. Énoncé visible à côté du plateau (`templates/index.html`, `static/exercise.js`)

- Nouvel élément `#exercise-statement-line`, placé **dans
  `#board-sticky-wrap`** (juste sous le plateau/matériel, avant la barre de
  lecture des lignes du coach) — ce conteneur reste collé en haut de l'écran
  sur mobile (issue #69) et suit le plateau sur grand écran, contrairement à
  l'ancienne ligne `#exercise-lichess-info` (dans l'onglet Exercice) qui,
  elle, finissait **sous le panneau du coach** une fois celui-ci rempli de
  messages (constat d'Alain, GSM 390×750) : hors écran, invisible sans
  défiler. `#exercise-lichess-info` est retirée (remplacée).
- `_exerciseUpdateStatementLine()` (exercise.js) construit une ligne courte :
  camp au trait + `· Problème <note> · <catégorie> · niveau <N>` (source
  Lichess), `· Mes erreurs · <phase>` (source historique), ou `· Position
  libre` (position précise) ; l'avertissement phase/catégorie (point 1),
  rare, est ajouté en fin de ligne. Appelée à chaque tirage et après chaque
  verdict (le niveau affiché reflète alors le résultat).
- `#exercise-status` (ligne d'état transitoire, juste en dessous) ne répète
  plus le camp/la source — simplifié en « Chargement d'une position... » /
  « Fais ton coup. » / messages d'erreur, pour ne pas faire doublon avec
  l'énoncé désormais toujours visible.
- Mesuré à 390×750 et 360×640 (captures ci-dessous) : l'énoncé reste dans le
  viewport sans défiler, sur une seule ligne (~23px de haut), pour les trois
  sources.

### 3. Position précise (`app.py`, `static/exercise.js`, `templates/index.html`)

- Nouvelle source `"position_precise"` : `_valider_fen_position_precise`
  (app.py) valide un FEN collé par Alain — lisible par python-chess, légal
  (mêmes messages que l'éditeur de position, `_EDITOR_STATUS_MESSAGES`), et
  camp au trait **ni mat ni pat** (sans quoi aucun coup n'est possible).
  `_on_exercise_new_position_precise` émet `exercise_position` (succès) ou
  `exercise_error` (`"fen_invalide"` + message prêt à afficher) — **sans
  aucun appel à `exercise_history`** (ni `enregistrer_proposition` au
  tirage, ni `enregistrer_resultat` au verdict dans `on_exercise_answer`,
  gardé par le drapeau `is_position_precise`) : une position collée à la
  main ne fausse donc ni le niveau d'Alain ni l'historique des erreurs, et
  ne peut pas non plus être enregistrée dans « Mes erreurs » (ce mécanisme
  n'existe que pour la source `mes_erreurs`, jamais invoqué ici).
- Le reste du jugement (verdict Stockfish, menace adverse, idées détectées,
  listes de pièces, lignes du coach) réutilise **exactement** le même calcul
  que la source « Mes erreurs » — `coup_reel` est naturellement vide (pas de
  "coup réellement joué" ni de comparaison avec une "partie d'origine"),
  avec un texte d'introduction adapté pour le coach.
- Interface : nouvelle option "Position précise" dans le sélecteur de
  source (desktop + feuille mobile), avec un champ FEN qui apparaît
  seulement pour cette source. Le champ vide est bloqué côté client (la
  feuille mobile reste ouverte avec un message inline) ; toute autre erreur
  (FEN illisible, position illégale, déjà mat/pat) est validée côté serveur
  et affichée dans `#exercise-status`. L'énoncé indique "Position libre".

### Fenêtre « Nouvel exercice » (desktop + feuille mobile)

- Sélecteur `#exercise-categorie-select` (desktop) / pastilles
  `#exercise-categorie-options` (mobile) : "Automatique" + 16 catégories
  triées par libellé français, visibles uniquement pour la source
  "Problèmes Lichess" (`_exerciseUpdateSourceDependentUI`). Dernier choix
  retenu **par appareil** via `localStorage`
  (`chesscoach-exercise-categorie`, même pattern que
  `GAME_BOARD_SIZE_STORAGE_KEY` de `mobile_game.js`) — appliqué au
  chargement de la page et après rechargement (testé).
- La feuille mobile (`#exercise-phase-sheet`) a été restructurée en
  flex-colonne : le contenu (phase/source/catégorie/FEN) défile dans un
  conteneur interne (`#exercise-phase-sheet-scroll`), et le bouton "Lancer
  l'exercice" devient un **pied de feuille fixe**, toujours visible, jamais
  recouvert ni à atteindre en défilant — testé à 360×640 avec les 17
  pastilles de catégorie affichées (dépasse 80vh sans ce changement). Un
  premier essai avec `position: sticky` sur le seul bouton a été rejeté : il
  flottait par-dessus le haut du contenu tant que la feuille n'était pas
  défilée jusqu'en bas (visible sur capture, overlap avec la pastille
  "Automatique").

## Tests

Vrai Stockfish 16 (`/usr/games/stockfish`) et vrai appel API (clé
`ANTHROPIC_API_KEY` du `.env`, modèle Sonnet configuré), via une seconde
instance de l'appli lancée sur le port 5099 (jamais sur le port 5000 où
tourne l'instance réelle d'Alain, laissée intacte) :

- **Backend (script Python direct)** : `tirer_probleme` avec catégorie
  forcée "fork" (automatique de phase) → catégorie bien "fork" et thème
  vérifié sur le problème tiré ; catégorie "pawnEndgame" + phase "opening"
  (incompatible exprès) → avertissement renvoyé, phase ignorée ; automatique
  → comportement inchangé (`avertissement=None`). `_valider_fen_position_precise` :
  FEN vide, FEN illisible, échiquier vide (illégal), FEN de mat (Fool's
  mate) → chacun son message d'erreur ; FEN de l'issue (position donnée,
  `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`) → validée.
- **Intégration Socket.IO (client `python-socketio`)** : les 6 scénarios
  ci-dessus rejoués via `exercise_new`/`exercise_answer` sur le vrai
  serveur ; pour la position de l'issue, un coup de remplissage (a2a3) a
  déclenché un vrai appel à l'API Claude (Sonnet) — **la menace adverse
  transmise au coach mentionne bien "le pion noir de g4 capture un pion de
  Blancs (Alain) en h3 [...] échec" (gxh3+)**, les listes de pièces sont
  transmises (`pieces_depart_texte` non vide), et la réponse réelle du coach
  cite explicitement **"gxh3+"** et le mat annoncé par Stockfish en suivant
  (+296 puis mentions de Qf3 etc.) — confirmant que le coach reçoit bien la
  menace et les pièces demandées par l'énoncé de tâche.
- **UI (Playwright, émulation tactile)** à 390×750, 360×640 et desktop
  1440×900 : ouverture de la feuille, choix de chaque élément testé
  (catégorie "Fourchette", "Mat"), vérification que le problème tiré
  appartient à la catégorie choisie (via l'énoncé affiché) ; "Automatique"
  conservé comme valeur par défaut ; choix de catégorie mémorisé après
  rechargement de page (`page.reload()`, revérifié) ; feuille sans
  débordement du bouton "Lancer l'exercice" (toujours dans le viewport,
  avant ET après défilement du contenu) ; énoncé visible sans défiler pour
  un exercice Lichess, un exercice "Mes erreurs" et une position précise ;
  FEN vide bloqué avec message inline (feuille reste ouverte) ; FEN valide
  lancé avec succès, "Position libre" affiché. Captures dans
  `/tmp/shots_issue83/` (environnement de l'agent, non committées).
- **Historique/statistiques** : fichiers personnels
  `exercice_historique.json`/`niveau_exercices_lichess.json` sauvegardés
  avant les tests, comparés après (hash MD5) — confirmé qu'aucune entrée
  "position_precise" n'apparaît dans l'historique et que le niveau Lichess
  n'a pas bougé pour ce test ; fichiers restaurés dans leur état exact
  d'avant-test à la fin (les quelques tirages "mes erreurs"/"lichess" faits
  pendant les tests UI, qui enregistrent légitimement une proposition,
  étaient inclus dans cette restauration pour ne rien laisser dans les
  données réelles d'Alain).
- **Non-régression** : tirage "mes erreurs" (`exercise_new` sans catégorie)
  inchangé ; `_on_exercise_answer_lichess` non touché par cette issue
  (aucune ligne modifiée dans cette fonction).
- `python3 -m py_compile app.py lichess_puzzles.py exercise_history.py
  config.py` et `node --check static/exercise.js` : OK.

## Limites

- Le pied de feuille fixe (bouton "Lancer l'exercice") a nécessité de
  restructurer `.phase-sheet` en flex-colonne avec un conteneur de défilement
  interne (`#exercise-phase-sheet-scroll`) — changement de structure plus
  large que le minimum pour une seule issue, mais nécessaire pour éviter le
  chevauchement visuel constaté avec `position: sticky`.
- Pas de test manuel sur un vrai GSM (émulation Playwright tactile
  390×750/360×640 uniquement, comme les issues précédentes sur ce mode).
- L'avertissement phase/catégorie n'a été exercé qu'avec une seule
  combinaison délibérément incompatible (pawnEndgame + ouverture) ; les 16×3
  combinaisons n'ont pas toutes été parcourues.

# Changelog — Issue #82

## Alerte visible quand la décomposition d'évaluation Stockfish n'est plus disponible : icône d'état dans l'en-tête et journal

Suite de l'issue #80 (idées du coup basées sur la commande `eval`, retirée par
Stockfish à partir de la 16.1) : `engine_stockfish.py`, `config.py`, `app.py`,
`templates/index.html`, `static/controls.js`.

### Détection (`engine_stockfish.py`)

- `EngineManager._detecter_eval_breakdown()` : appelle
  `get_eval_breakdown()` (issue #80) sur la position de départ (position de
  test simple) et mémorise le résultat dans `_eval_breakdown_disponible`
  (bool) / `_eval_breakdown_version` (texte complet du moteur, ex.
  `"Stockfish 16"`) — exposés en lecture via les propriétés
  `eval_breakdown_disponible` / `eval_breakdown_version`. Jamais retesté à
  chaque exercice : `get_eval_breakdown` reste appelé normalement à chaque
  coup (comportement de l'issue #80 inchangé), seule cette détection d'état
  est mise en cache.
- Appelée une fois à la fin de `_init_engines()` (démarrage de l'appli) et de
  nouveau dans `_appel_protege()` chaque fois que le moteur d'évaluation
  (`_engine_eval`) est relancé avec succès par la reprise automatique (issue
  #79) — comparaison par égalité de méthode liée (`creer ==
  self._creer_moteur_eval`), sans toucher aux relances des trois autres
  instances (play/pédagogique/finales), sans rapport avec cette commande.
- État persisté dans `EVAL_BREAKDOWN_STATE_PATH` (nouveau,
  `data/eval_breakdown_state.json`, `config.py`) pour comparer au démarrage
  suivant : si la disponibilité ou la version a changé depuis le fichier
  précédent, une ligne `WARNING` dédiée est journalisée en plus de la ligne
  `INFO` systématique — toutes deux préfixées `[EVAL_BREAKDOWN]`, faciles à
  retrouver dans le journal applicatif (`logger` standard, pas de nouveau
  fichier de log).
- Testé avec le vrai Stockfish 16 installé (`/usr/games/stockfish`, qui
  supporte encore `eval`) : `disponible=True`, `version='Stockfish 16'`.
  Testé aussi en forçant `get_eval_breakdown` à renvoyer `None` (simulation
  d'un Stockfish 16.1+) après avoir pré-rempli l'état précédent à
  `disponible=True` : la ligne de changement apparaît bien dans le journal,
  le nouvel état est persisté.

### Icône d'état (`templates/index.html`, `static/controls.js`)

- `#eval-status-widget` (bouton texte discret `eval` + panneau de détail au
  survol/clic, même mécanique que `#usage-tokens-widget` existant) posé dans
  `.header-actions` de l'en-tête (grand écran), rendu initial entièrement
  côté serveur (`app.py` `index()`) à partir de
  `engine_manager.eval_breakdown_disponible/_version` — **absent du DOM**
  (pas seulement masqué) si Stockfish est entièrement introuvable
  (`engine_manager is None`, autre panne déjà signalée ailleurs, hors sujet
  ici).
- Déplacé vers `#mobile-mode-bar-slot`, juste après le menu `"..."`
  (`#game-menu-btn`, posé par l'issue #70/#81) sur mobile (<900px, dans tous
  les modes) par `_registerMobileRelocatable` (`controls.js`, même mécanisme
  que les autres blocs déjà déplacés — `#eval-status-widget` n'existe que
  s'il est présent côté serveur, l'enregistrement est un no-op sinon).
- État normal : texte `eval` en gris discret (`--cc-text-muted`). État
  indisponible : classe `.eval-status-alert`, couleur rouge `#cc2200` (déjà
  utilisée ailleurs pour les coups en erreur, `.move-chip.erreur`) — jamais
  le terracotta `--cc-accent`, réservé au cliquable d'après la règle de
  palette existante.
- Message au survol (desktop) ou au tap (bascule d'une classe
  `.eval-status-open`, même recette que `#usage-tokens-widget`) :
  - normal : « Décomposition d'évaluation disponible, Stockfish `<version>`. »
  - indisponible : « Stockfish `<version>` ne fournit plus la décomposition
    d'évaluation : les idées du coup ne sont plus calculées (seules les
    idées mécaniques restent). Une mise à jour de Stockfish est probablement
    la cause. »
  - `<version>` = nom du moteur sans le préfixe `"Stockfish "` s'il est
    présent (`app.py` `_version_stockfish_affichee`), pour éviter de le
    répéter deux fois dans le message.
- Panneau de détail en `position:fixed` sur mobile (ancré dynamiquement sous
  le bouton par JS), même recette que `#usage-detail` (issue #54) — choisie
  pour la même raison : un panneau `position:absolute` déborderait du
  viewport selon la position du widget dans la rangée.

### Vérifications (Playwright, serveur Flask local, vrai Stockfish 16)

- 1280×900, 390×750, 360×750 : icône visible, état normal (gris), message
  correct au clic, **aucun débordement horizontal**
  (`document.documentElement.scrollWidth === clientWidth`) dans les trois
  tailles.
- Même mesures après `app.engine_manager._eval_breakdown_disponible = False`
  (simulation du scénario "Stockfish mis à jour") : classe
  `eval-status-alert`, couleur `rgb(204, 34, 0)` (`#cc2200`), message avec la
  version simulée, toujours aucun débordement horizontal.
- `#eval-status-widget` confirmé replacé dans `#mobile-mode-bar-slot` juste
  après `#game-menu-btn` sur mobile, et toujours visible après passage en
  mode "partie libre" (`body.mobile-game-active`) — l'en-tête `<header>`
  d'origine est bien masqué (`display:none`) comme pour le reste de la
  rangée combinée (issue #81).
- `engine_manager is None` (Stockfish absent) : `<div id="eval-status-widget">`
  bien absent du HTML rendu (vérifié par recherche de la balise elle-même,
  pas d'un simple mot dans un commentaire HTML).

### Limites

- La reprise automatique du moteur d'évaluation (issue #79) n'a pas été
  déclenchée avec un vrai crash de processus dans le cadre de cette tâche
  (aucune manipulation destructrice du Stockfish système demandée) : le
  branchement dans `_appel_protege` est vérifié par lecture de code
  (comparaison de méthode liée `creer == self._creer_moteur_eval`, placée
  après un appel réussi sur la nouvelle instance) plutôt que par un crash
  réel comme l'avait fait le rapport de l'issue #79 elle-même.
- Pas de simulation d'un vrai Stockfish 16.1+ sans la commande `eval` (le
  binaire installé sur cette machine, Stockfish 16, la supporte encore) : la
  détection de l'état "indisponible" est vérifiée en forçant directement le
  résultat (`get_eval_breakdown` monkeypatché / attribut forcé), comme
  suggéré par l'énoncé de l'issue.
- Comportement de repli sur les idées mécaniques (issue #80) strictement
  inchangé : aucune modification de `get_eval_breakdown()` elle-même ni de
  ses appelants (`app.py`), seule une détection d'état en plus, jamais
  consultée par le calcul des idées du coup.

# Changelog — Issue #81

## Mobile : place pour lire le coach, tailles du plateau distinctes, onglets vides, taille du plateau dans tous les modes

Suite de l'issue #80 (corrections après test GSM, 2/2) : `static/mobile_game.js`,
`static/board.js`, `static/exercise.js`, `static/game_coach_lines.js`,
`static/game_analysis.js`, `templates/index.html`.

### Point 1 — Plateau réduit, plus de déclencheurs

- `_updateBoardCompactState()` (`mobile_game.js`) inchangée (scroll/clavier) ;
  nouvelle fonction `_activeTabContentOverflows()` (avec une marge de 24px,
  `BOARD_COMPACT_SCROLL_THRESHOLD`, pour ne pas basculer en réduit sur le
  seul message d'état vide d'un onglet) et `_autoCompactForOverflow()`
  (additive uniquement — ne referme jamais le plateau réduit toute seule),
  appelées après `switchGameTab()` et à l'arrivée de chaque réponse du coach
  (`_mobileGameOnCoachMessage()`, hooké depuis `_coachRenderBubble()`,
  `board.js` — pas pour les annonces automatiques "je joue ...").
- `_forceBoardFull()` + `_mobileGameOnMoveCountChanged()` : un coup
  réellement joué (compte de coups en hausse, mesuré dans `renderHistory()`,
  déjà appelée après chaque coup tous modes confondus) redonne sa taille
  complète au plateau, même si l'onglet affiché reste trop long pour l'écran.
  "Lance une lecture avec Play" était déjà couvert par le garde-fou existant
  (`_linePlaybackActive()`).
- Mesuré (Playwright, 390×750, free play, 1 coup joué) : part de hauteur
  disponible pour le contenu sous le plateau — plateau complet 21% (Compact) /
  13% (Normal) / 8% (Grand) ; plateau réduit **71%** dans les trois cas (taille
  fixe `clamp(150px,42vw,170px)`, indépendante du réglage). À 360×640 :
  19%/16%/9% (complet) contre 68% (réduit).

### Point 2 — Compact/Normal réellement distincts

- `GAME_BOARD_SIZE_PRESETS` (`mobile_game.js`) : `minVisibleBelowTabs`
  désormais distinct par préréglage (150/100/60px au lieu de 180/180/120px
  partagés) — la garantie de contenu visible écrasait Compact et Normal sur
  la même valeur mesurée (`--bd-size-game-max`) sur un téléphone courant.
  Pct également ajusté : Compact 32% (était 38%), Normal 40% (était 44%),
  Grand inchangé (52%, mais garantie abaissée à 60px pour rester le plus
  grand des trois après l'ajustement de Normal).
- Mesuré (Playwright) : à 390×750, Compact=240px (32.0%), Normal=300px
  (40.0%), Grand=340px (45.3%, plafonné par la garantie/la largeur d'écran).
  À 360×640 : Compact=170px (26.6%, plancher `GAME_BOARD_MIN_SIZE`),
  Normal=190px (29.7%), Grand=230px (35.9%) — les trois valeurs restent
  distinctes aux deux largeurs, ordre Grand > Normal > Compact préservé.

### Point 3 — États vides des 4 onglets

- Lignes : nouvel élément statique `#game-tab-lignes-empty` dans
  `game-tab-panel-lignes` (texte « Aucune ligne pour l'instant. Demande au
  coach, par exemple : « Que devais-je jouer au coup 8 ? » »), basculé par
  `renderGameCoachLinesTable()` (`game_coach_lines.js`) selon
  `gameCoachLines.length`.
- Coups : `renderHistory()` (`board.js`) affiche désormais « Aucun coup pour
  l'instant. » (classe `.game-tab-empty-msg`, globale — s'applique aussi à
  `#historique-column` grand écran) au lieu d'une table réduite à sa seule
  ligne d'en-tête quand `total === 0` ; il se remplissait "seulement plus
  tard" simplement parce qu'aucun coup n'avait encore été joué — pas un bug
  de remplissage, confirmé par test.
- Analyse : nouvel élément `#game-analysis-help` + nouvelle fonction
  `_updateGameAnalysisAvailability()` (`game_analysis.js`, appelée depuis
  `onGameUiRefresh()`) — bouton grisé et phrase « Disponible quand la partie
  est terminée. » tant que la partie en cours (un des 4 modes de partie)
  n'est pas terminée ; statut par défaut « Analyse non lancée. » tant
  qu'aucun résultat n'est en mémoire. Toujours disponible hors contexte "en
  place" (Bibliothèque/Revue PGN).

### Point 4 — Taille du plateau dans tous les modes

- `#game-model-pill`/`#game-menu-btn`/`#game-menu-dropdown` (menu "...",
  déjà existant pour les 4 modes de partie) généralisés à TOUS les modes sur
  mobile (`templates/index.html`, CSS dé-préfixée de `body.mobile-game-active`
  vers la media query générale) ; "Extraire le FEN"/"Importer un PGN"
  restent réservés aux modes de partie (classe `.game-menu-item-gameonly`,
  masquée via `body:not(.mobile-game-active)`).
- `HEADER_ALWAYS_RELOCATE` (`mobile_game.js`, nouveau, séparé de
  `GAME_ALWAYS_RELOCATE`) : pastille de modèle + compteur de jetons
  rejoignent le menu dès qu'on est sur mobile, quel que soit le mode —
  `<header>` masqué partout sur mobile (menu commun unique, pas de doublon).
- Deux nouvelles familles de taille, même réglage partagé (une seule clé
  localStorage) que les 4 modes de partie : `EXERCISE_BOARD_SIZE_PCT`
  (22/30/38dvh, classe `body.mobile-size-exercise-active`, coordonnées/barre
  d'éval gardées visibles) et `WIDE_BOARD_SIZE_PCT` (46/58/68dvh, classe
  `body.mobile-wide-board` déjà existante, Bibliothèque/Revue PGN + Éditeur).
  Normal reproduit exactement l'ancienne valeur fixe de chaque mode (30dvh/
  58dvh) — défaut inchangé. Aucun débordement horizontal mesuré à 360px avec
  Grand (vérifié Playwright, les 4 familles de modes).

### Point 5 — Bibliothèque uniquement dans la Bibliothèque

- `#single-pgn-import-block` et `#training-program-panel` déplacés dans
  `templates/index.html` depuis `#board-column`/`#coach-column` (visibles
  dans TOUS les modes, grand écran compris — le vrai bug, pas seulement
  mobile) vers `#tab-panel-library`, aux côtés de `#pgn-lib-browse-block`/
  `#game-analysis-panel` déjà bien scopés eux.
- `mobile-non-library-tab` (nouvelle classe body, `mobile_game.js`,
  `onGameUiRefresh`) masque `#mobile-bottom-slot`/`#mobile-analysis-slot` en
  Exercice/Éditeur sur mobile (les 4 modes de partie l'étaient déjà via
  `mobile-game-active`) — ces slots recevaient ces blocs par
  `_placeMobileRelocatablesForViewport` (`controls.js`, inchangé)
  indépendamment de l'onglet actif, d'où leur présence partout avant ce
  correctif.
- Vérifié (Playwright, 390×750 et grand écran 1400×900) : les 3 blocs ne
  sont visibles qu'en Bibliothèque, dans tous les autres modes testés (Partie
  libre, Exercice, Éditeur).

### Point 6 — Conversation effacée à chaque nouvel exercice

- `exercise.js`, `startExercise()` (appelée par "Nouvel exercice"/"Autre
  catégorie" via `launchExerciseFromSheet()` et par "Exercice suivant" via
  `startNextExercise()`, point d'entrée unique) : remplace
  `coachNewSegment("Nouvel exercice")` (simple trait, historique visible
  conservé) par `coachClear()` (même effet que le bouton "Effacer" — vidage
  intégral messages + segment API). Le tableau "Lignes du coach" de
  l'Exercice était déjà vidé par ailleurs (`_exerciseResetCoachLines()`).
  Les autres modes (partie libre/pédagogique/ouverture/finales) gardent
  `coachNewSegment("Nouvelle partie")`, inchangé.

### Tests

Flask lancé dans le worktree avec `HOME` redirigé vers un répertoire
temporaire isolé (`/tmp/chesscoach-test-home`) — `config.DATA_DIR`/
`ENGINES_DIR` dérivent de `Path.home()`, aucune lecture/écriture dans le
`~/ChessCoach` réel. Playwright (Chromium, émulation tactile 390×750 et
360×640) : mesures de taille/pourcentages, bascule plateau réduit/complet
(coup joué, toucher, réponse simulée du coach), onglets vides/remplis,
réglage de taille dans les 4 modes + Bibliothèque/Éditeur, absence de
débordement horizontal à 360px, grand écran (1400×900) inchangé, et
enchaînement d'exercices (conversation vidée). Aucune clé API disponible
dans cet environnement (`ANTHROPIC_API_KEY` absente) : la "réponse du coach"
du point 1 a été simulée en appelant directement `_coachRenderBubble()`
plutôt qu'un vrai aller-retour API — comportement du déclencheur vérifié,
mais pas le contenu réel d'une réponse Claude. Aucune erreur console/page
JS relevée sur l'ensemble des passages (7 onglets, 4 onglets de jeu, 3
tailles de plateau).

### Limites

- Les pourcentages/garanties de hauteur restent des plafonds mesurés dans un
  état précis (1 coup joué, pas de bandeau de fin de partie ni de repli des
  boutons sur 2 lignes) — comme avant cette issue, l'état réel varie selon
  ce qui entoure le plateau à un instant donné.
- Le seuil de débordement de contenu (point 1) utilise une marge fixe de
  24px ; un contenu dépassant de quelques px seulement (en dessous de cette
  marge) ne déclenche pas le plateau réduit — compromis choisi pour éviter
  qu'un simple message d'état vide ne le déclenche à tort.

# Changelog — Issue #80

## Coach : explique les menaces, les attaques/défenses et les idées du coup au lieu de recopier les FEN

- **Constat de départ** (position `1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`,
  Alain Blancs, coup proposé h4) : le coach n'avait aucune donnée sur la
  menace adverse (`...gxh3+`/`...Qxh3+`) et a présenté un coup purement
  défensif comme « une expansion à l'aile roi » ; relancé sur la menace, il a
  affirmé à tort que le pion g3 protégeait h3 (un pion blanc en g3 attaque
  f4/h4, pas h3), puis a recopié le FEN de mémoire avec une erreur de
  transcription et conclu que le FEN d'Alain était invalide.

### Tâche 1 — Menace adverse (coup nul)

- `engine_stockfish.py`, `EngineManager.get_threats(board, depth, n=2)` :
  joue un coup nul (`chess.Move.null()`, légal seulement hors échec) sur la
  position et redemande au moteur d'évaluation ses `n` meilleurs coups
  (réutilise `get_multipv` tel quel) — ce sont les meilleures menaces de
  l'adversaire si le camp au trait passait son tour. Retourne
  `{"disponible": False, "raison": "en_echec"|"moteur_indisponible"}` si la
  position est en échec ou si Stockfish est indisponible, sinon
  `{"disponible": True, "baseline": {...}, "menaces": [{"move", "cp", "mate",
  "perte_cp"}, ...]}` — `perte_cp` est l'écart entre l'évaluation de la
  position (déjà le meilleur coup du camp au trait) et l'évaluation
  résultant de chaque menace, toujours ≥ 0. Fonction mode-agnostique,
  appelée depuis `app.py` (`_calculer_menace_adverse`, lui-même réutilisable
  par d'autres modes que l'Exercice).
- `game_facts.py`, `describe_menace_adverse(menace_data, fen_avant,
  camp_alain)` : formate ce résultat en texte de contexte — chaque menace
  décrite mécaniquement (`describe_move_mechanically`, donc pièce, case,
  capture, échec, défense, solde net), son évaluation résultante et sa
  perte d'avantage, étiquetée « SIGNIFICATIVE » au-delà de
  `SEUIL_MENACE_SIGNIFICATIVE_CP = 100` centipions (constante unique,
  reprise par le prompt). Toujours un texte explicite, y compris en cas
  d'indisponibilité (échec/moteur en panne) — jamais un bloc silencieusement
  absent.

### Tâche 2 — Attaques et défenses avant/après le coup

- `game_facts._decrit_coup_mecanique` (fonction déjà partagée par
  `describe_move_mechanically`/`describe_pv_mechanically`/
  `describe_pv_with_balance`, donc par TOUS les coups cités — proposé, réel,
  meilleur coup, PV) enrichie de trois nouveaux calculs :
  - `_attaques_defenses_arrivee` : qui attaque/défend la case d'arrivée
    après le coup, et quels anciens attaquants de la case de départ ne
    l'atteignent plus (`chess.Board.attackers`) ;
  - `_resultat_echange_case` : si la pièce qui vient d'arriver est
    attaquée, le résultat si l'adversaire la capture (attaquant le moins
    cher d'abord, puis reprise mécanique comme `_solde_net_apres_capture`) —
    reproduit l'exemple demandé : « Qxh4 gxh4, échange favorable ou
    équilibré pour Blancs » ;
  - `_pieces_amies_changement_attaque` : pièces amies (hors case de
    départ/arrivée) qui gagnent ou perdent l'attaque adverse suite à ce
    coup (attaque découverte, mise à l'abri), limité à 3 par liste.
  - Omis sur un mat (plus aucun coup adverse possible). Limite connue : le
    coup de la tour lors d'un roque n'est pas modélisé séparément (l'objet
    `chess.Move` n'encode que le roi) — ses propres changements d'attaque ne
    sont donc pas détectés.

### Tâche 3 — Listes de pièces + interdiction de citer un FEN

- `game_facts.describe_pieces_lists(fen, camp_alain)` : liste des pièces de
  chaque camp par case pour une position FEN isolée, même présentation que
  le bloc de faits des modes de partie (`_liste_pieces`) — réutilisable pour
  le mode Exercice, qui ne rejoue aucun PGN.
- `app.py` (`on_exercise_answer`/`_on_exercise_answer_lichess`) : jointe au
  contexte pour la position de DÉPART et la position ACTUELLE de
  l'exercice.
- `llm_coach.py`, nouveau bloc de prompt (dans `_EXERCISE_SYSTEM_ADDENDUM`) :
  ne jamais recopier/citer un FEN dans une réponse, ne jamais déclarer un
  FEN invalide ou mal formé, ne s'appuyer que sur les listes/descriptions
  fournies, ne jamais affirmer qu'une pièce en protège une autre sans que
  les données le disent explicitement.

### Tâche 4 — Prompt : la menace d'abord

- `llm_coach.py`, même addendum : quand un bloc de menace marque au moins
  une menace « SIGNIFICATIVE », ou quand la description mécanique d'un coup
  cité indique qu'une pièce amie « n'est plus attaqué(e) » par rapport à
  avant ce coup, le coach doit expliquer la menace d'abord (ce que
  l'adversaire aurait joué et ce que cela aurait provoqué), puis pourquoi le
  coup la pare, puis les points secondaires — et ne jamais présenter un coup
  défensif/préventif comme un plan offensif. Sans menace marquante, consigne
  explicite de ne rien inventer.

### Tâche 5 — Idées du coup (décomposition de l'évaluation Stockfish)

- `engine_stockfish.py`, `EngineManager.get_eval_breakdown(fen, timeout=5s)`
  : lance un sous-processus Stockfish séparé des instances permanentes
  (commande UCI non standard « eval », absente depuis Stockfish 16.1),
  envoie `position fen ...` puis `eval`, parse la table « Contributing terms
  for the classical eval » (colonne Total, MG/EG, par terme). Retourne
  `None` si le binaire est introuvable, si le délai est dépassé, ou si la
  sortie ne contient pas cette table (jamais d'exception).
- `game_facts.py` :
  - `_diff_termes_evaluation` : variation de chaque terme entre AVANT et
    APRÈS un coup, du point de vue d'Alain, au-delà de
    `SEUIL_IDEE_PION = 0.3` pion (constante unique) — phase MG/EG choisie
    selon le matériel restant (`_phase_mg_ou_eg`, ≤ 12 pièces = finale,
    même heuristique que `app._analyse_full_game`). Termes traduits en
    français (`_IDEE_LIBELLES` : King safety → sécurité du roi, Threats →
    menaces sur les pièces adverses, Mobility → activité des pièces, Passed
    → pion passé, Space → espace, Pawns → structure de pions, Knights/
    Bishops/Rooks → meilleur placement du cavalier/fou/tour, Material +
    Imbalance → matériel, fusionnés) ;
  - idées mécaniques complémentaires : `_idee_parade_menace` (la menace la
    plus sévère de la tâche 1 n'est plus légale après ce coup),
    `_idee_developpement_centralisation` (cavalier/fou qui quitte sa case
    de départ, pièce qui rejoint d4/d5/e4/e5), plus échec/mat directement
    dans `build_idees_coup` ;
  - `build_idees_coup(fen_avant, coup, camp_alain, breakdown_avant,
    breakdown_apres, menace_data, max_idees=3)` : combine le tout par
    paliers (mat/échec toujours en tête, puis les idées moteur triées par
    magnitude, puis les idées mécaniques complémentaires triées par
    magnitude) — un mat/échec reste prioritaire sur tout le reste, mais une
    parade de menace ne doit pas éclipser l'idée moteur qui la mesure déjà
    (ex. « sécurité du roi » doit rester en tête sur h4, la parade de
    `...gxh3+` listée ensuite). Retourne `[]` sans erreur visible si la
    décomposition est indisponible et qu'aucune idée mécanique n'est
    détectée ;
  - `format_idees_coup(label, idees)` : texte de contexte, jamais de valeur
    chiffrée.
- `app.py`, `_calculer_idees_coup` (mode-agnostique) : appelle
  `get_eval_breakdown` avant/après, puis `build_idees_coup` — branché pour
  le coup proposé, le coup réellement joué (source « mes erreurs ») et le
  meilleur coup, dans `on_exercise_answer` ET `_on_exercise_answer_lichess`.

### Tâche 6 — Prompt : présenter les idées comme des indications

- `llm_coach.py`, même addendum : le coach énonce les idées dans l'ordre
  fourni, précise pour chacune comment elle se réalise (pièces/cases/
  menaces, à partir des descriptions et listes déjà fournies), n'ajoute
  jamais d'idée absente de la liste, les présente comme des indications du
  moteur (« le moteur indique que... ») et jamais comme des vérités, ne cite
  aucune valeur chiffrée, dit que le coup se justifie surtout par la ligne
  calculée ou la tactique si aucune idée n'est détectée, et compare les
  idées du coup proposé et du meilleur coup quand ils diffèrent.

## Fichiers touchés

- `engine_stockfish.py` : `EngineManager.get_threats`,
  `EngineManager.get_eval_breakdown`.
- `game_facts.py` : `describe_pieces_lists`, `describe_menace_adverse`,
  `_attaques_defenses_arrivee`/`_resultat_echange_case`/
  `_pieces_amies_changement_attaque` (dans `_decrit_coup_mecanique`),
  `build_idees_coup`/`format_idees_coup` + fonctions privées associées,
  nouvelles constantes `SEUIL_MENACE_SIGNIFICATIVE_CP`/`SEUIL_IDEE_PION`.
- `llm_coach.py` : `_build_context_text` (nouveaux champs
  `pieces_depart_texte`/`pieces_actuelles_texte`/`menace_adverse_texte`/
  `idees_coup_propose_texte`/`idees_coup_reel_texte`/
  `idees_meilleur_coup_texte`), nouvel addendum dans
  `_EXERCISE_SYSTEM_ADDENDUM`.
- `app.py` : `_calculer_menace_adverse`/`_calculer_idees_coup` (nouvelles,
  mode-agnostiques), branchées dans `on_exercise_answer`,
  `_on_exercise_answer_lichess` et la liste blanche de
  `on_coach_comment_on_demand`.
- `static/exercise.js` : nouvelles variables mémorisant ces champs reçus
  avec le verdict, réinjectées dans `exerciseChatContextExtra()` pour
  qu'une question de suivi dans le chat libre dispose du même contexte.

## Tests

- Unitaires (sans API, moteur réel `/usr/games/stockfish` 16) : position de
  l'exemple h4 — `get_threats` trouve `gxh3+`/`Qxh3+` (pertes ≈ 194/168cp,
  cohérent avec l'estimation indépendante de l'issue, ≈ 290/410cp de perte
  selon la méthode de calcul) ; `get_eval_breakdown` avant/après h4 confirme
  `King safety` MG +1.07 pion et rien d'autre de marquant (valeur exacte de
  l'issue), Qa7 ne change aucun terme marquant ; `build_idees_coup` place
  « sécurité du roi » en tête pour h4 (avec la parade de `gxh3+` ensuite),
  aucune idée pour Qa7, « menaces sur les pièces adverses » pour `Rc1` sur
  `r2qk2r/ppp2ppp/2n1p3/4P3/2BP2b1/2b1BN2/P4PPP/R2Q1RK1 w kq - 0 11` (les
  trois résultats demandés par l'issue sont vérifiés).
- `describe_move_mechanically(fen, "h4", "blancs")` reproduit exactement
  l'exemple attendu par l'issue : « ... en h4, attaqué(e) par Dame h5,
  défendu(e) par Pion g3 : Qxh4 gxh4, échange favorable ou équilibré pour
  Blancs (Alain) ; n'est plus attaqué(e) par Pion g4 ».
- Cas limites : position en échec → `get_threats` retourne
  `disponible=False, raison="en_echec"`, texte explicite correspondant ;
  mat (`Ra8#`) → idée « échec et mat » en tête ; finale K+P vs K → pipeline
  complet sans erreur, aucune menace marquante détectée ; décomposition
  absente (simulée en forçant `breakdown_avant/apres=None`) → idées
  mécaniques seules (ex. développement), aucune exception ; position calme
  (`4...Nc6` dans une Italienne) → `describe_menace_adverse` ne qualifie
  aucune menace de significative. Régression : `describe_move_mechanically`
  revérifié sur roque, prise en passant et promotion (toujours correct avec
  les nouveaux segments), et sur un contexte de mode partie sans aucun des
  nouveaux champs (aucune section pièces/menace/idées ajoutée à tort).
- Appel réel à l'API Claude (`claude-sonnet-5`, clé lue depuis
  `~/ChessCoach/.env`, jamais modifié) sur la position/coup `h4` de
  l'exemple : la réponse explique la menace adverse (`...gxh3+`/`...Qxh3+`)
  EN PREMIER, explique pourquoi h4 la pare, qualifie explicitement le coup
  de défensif (« Ce coup est donc avant tout défensif... pas une expansion
  offensive à l'aile roi »), et ne recopie ni ne met en cause le FEN. Une
  question de suivi reproduisant l'erreur originale (« mon pion g3 ne
  protège-t-il pas h3 ? ») reçoit une réponse qui corrige correctement
  l'intuition (« Ton pion g3 ne protège pas la case h3... il défendrait une
  pièce noire en h4, pas en h3 ») sans jamais recopier le FEN ni le
  déclarer invalide — le bug source de l'issue ne se reproduit plus.

## Limites connues

- Idées mécaniques de développement/centralisation : heuristiques simples
  (case de départ standard du cavalier/fou, carré central d4/d5/e4/e5), pas
  une détection générale de plans positionnels.
- Le roque n'enrichit les attaques/défenses que pour le roi (la tour qui se
  déplace silencieusement n'est pas analysée séparément).
- `get_eval_breakdown` dépend d'une commande non standard, absente à partir
  de Stockfish 16.1 : dégradation déjà prévue et testée (repli sur les
  idées mécaniques seules), mais aucune décomposition moteur ne sera plus
  disponible le jour où Alain mettra à jour son binaire Stockfish.
- Seule la source « mes erreurs » et la source « Problèmes Lichess » du
  mode Exercice sont couvertes ; les autres modes (pédagogique, ouverture,
  finales, partie libre) ne reçoivent pas encore ces données — hors
  périmètre explicite de l'issue, mais les fonctions ajoutées
  (`_calculer_menace_adverse`/`_calculer_idees_coup`/`describe_pieces_lists`)
  sont déjà mode-agnostiques et réutilisables sans modification.

# Changelog — Issue #79

## Moteur Stockfish : reprise automatique après une panne, erreur visible, coach honnête sans verdict

- **Cause probable identifiée** : `chess.engine.SimpleEngine` ne se relance
  jamais seul après la mort de sa boucle d'événements (process Stockfish
  tué/crashé, ou appel bloqué indéfiniment) — tout appel suivant échoue en
  boucle (`EngineTerminatedError`/« engine event loop dead ») jusqu'au
  redémarrage complet de l'appli, exactement le symptôme constaté. Les
  verrous par instance (`_lock_play`/`_lock_eval`/...) existaient déjà
  (issues précédentes) : l'accès concurrent entre fils SocketIO n'est donc
  pas la cause principale — en revanche, `evaluate()`/`analyse()` (appels
  bornés en PROFONDEUR, majorité des appels) n'avaient jusqu'ici AUCUN
  timeout côté python-chess (seuls les appels bornés en temps, ex.
  `get_move`, ont un timeout interne) : un moteur silencieux pouvait donc
  bloquer indéfiniment le fil appelant — cause probable retenue et corrigée
  (`TIMEOUT_APPEL_SECONDES = 12s`, via un `ThreadPoolExecutor` dédié).
- `engine_stockfish.py` : reprise automatique générique (`_appel_protege`)
  appliquée à TOUS les appels moteur (`get_move`, `get_move_pedagogique`,
  `get_move_finales`, `evaluate`, `evaluate_move` + son repli MultiPV,
  `get_punishment_line`, `get_multipv`) — détecte la mort du moteur, le
  timeout d'appel ou toute exception UCI, ferme l'instance morte, en relance
  une neuve (capacités/Elo/Syzygy/Hash/Threads reconfigurés) et rejoue
  l'appel une seule fois. Quota partagé de 3 relances par fenêtre glissante
  de 60s avec pause croissante (1 à 5s) avant chaque relance, pour éviter une
  boucle serrée en cas de panne systémique (binaire absent, bibliothèque
  incompatible). `Hash=64 Mo`/`Threads=1` désormais fixés explicitement par
  instance (point 7, par prudence — pas identifiés comme cause de la panne
  observée, aucun processus tué pour mémoire côté système).
- `evaluate()`/`evaluate_move()` distinguent désormais explicitement une
  VRAIE panne moteur (`"indisponible": True`, `qualite=None`) d'une position
  terminale légitime (`cp`/`mate` à `None` mais `indisponible=False`) — avant
  ce correctif, les deux cas étaient indiscernables et `evaluate_move`
  rendait un verdict `"bon"`/0 INVENTÉ en cas de panne totale, transmis tel
  quel au coach (cas réel constaté : Re5, classé « gaffe » alors que
  Stockfish le classe meilleur coup, delta ≈ 0).
- `config.py` : nouveau `MOTEUR_ERREURS_LOG_PATH`
  (`data/logs/moteur_erreurs.log`, donnée personnelle hors git) — heure,
  opération, message d'erreur, code de sortie du processus, dernières lignes
  de stderr Stockfish (capturées via un handler sur le logger
  `chess.engine`) et nombre de relances tentées pour chaque panne.
- `app.py` : nouveau drapeau `analyse_indisponible` propagé par tous les
  chemins qui construisent le contexte du coach (exercices "mes erreurs" et
  "Problèmes Lichess", `coach_ask`/`coach_comment_on_demand`, pédagogique,
  ouverture, finales) ; pour la source Lichess, un coup sans correspondance
  connue (ni solution ni mat) alors que le moteur est indisponible ne reçoit
  plus le verdict "erreur" par défaut (verdict inventé) mais `None`
  (indéterminé).
- `exercise_history.py` : un exercice sans verdict calculable n'est plus
  enregistré dans l'historique (gating `verdict_qualite is not None`/
  `verdict_final is not None` côté `app.py`, déjà en place pour la partie
  "verdict" — complété ici côté tirage) ; une entrée à `dernier_resultat:
  None` (ancienne ou produite malgré tout) est désormais traitée comme
  "ratée" par `choisir_exercice` (révision courte) plutôt que comme
  "réussie" (révision longue, bug de l'ancien `else`) — jamais comptée comme
  un succès.
- `llm_coach.py` : (a) `get_coach_response` refuse l'appel API, SANS
  journaliser ni interroger le modèle, quand `mode_exercice` est vrai et
  qu'aucun `verdict_qualite` n'est présent dans le contexte — message fixe
  `"pas_de_verdict_exercice"`, retourné avant tout accès réseau (vérifié :
  une fausse clé API ne lève aucune exception réseau, donc aucune requête
  n'est tentée) ; couvre aussi bien un rechargement de page qu'un événement
  tardif, puisque c'est le contexte reçu qui est vérifié, pas un état côté
  client. (b) Si une analyse Stockfish manque malgré tout (autres modes, ou
  deuxième ligne de défense), `_build_context_text` écrit explicitement
  "Analyse Stockfish indisponible pour cet exercice/cette position : aucun
  verdict, aucune évaluation, aucun meilleur coup" et un nouvel addendum
  système (`_ANALYSE_INDISPONIBLE_ADDENDUM`) interdit formellement d'inventer
  un verdict/une évaluation/un meilleur coup/une ligne. (c) Données
  partielles (verdict rendu mais évaluation, meilleur coup ou ligne
  principale manquants) signalées champ par champ ("évaluation
  indisponible", "ligne principale indisponible"...) avec interdiction
  explicite de les inventer.
- `static/exercise.js`/`templates/index.html` : minuteur de garde côté
  interface (30s, indépendant du délai serveur) — si le verdict ne revient
  pas, remplace « Le coach réfléchit... » par « L'analyse Stockfish est
  indisponible » avec un bouton « Réessayer » (rejoue le même coup sans
  redemande) ; le plateau reste explorable et « Exercice suivant » reste
  utilisable. Champ de question, bouton « Envoyer » et bouton « Demander
  l'avis du coach » désactivés et grisés (placeholder/texte d'aide
  « Disponible après le verdict ») tant qu'aucun verdict n'est obtenu pour la
  tentative en cours — réactivés dès l'arrivée du verdict ou en quittant le
  mode exercice.
- `static/controls.js`/`static/board.js` : `MODE_CAPS.exercise.
  askCoachAvailable` exige désormais un verdict rendu ; défense en
  profondeur côté `coachSend()` (ignore un envoi programmatique qui
  contournerait l'état `disabled` du DOM) ; messages d'erreur
  `pas_de_verdict_exercice` mappés vers le même texte que le minuteur de
  garde sur les 3 canaux concernés (`coach_ask`, `exercise_answer`,
  `coach_on_demand`).

### Tests effectués (moteur réel `/usr/games/stockfish`, cf. rapport de clôture)

- Mort du moteur pendant l'inactivité puis pendant un appel (`SIGKILL` du
  process sous-jacent) : reprise automatique réussie dans les deux cas,
  verdict réel obtenu après une seule relance (0,2 à 1,8s).
- Panne persistante (reconstruction forcée en échec) : quota de 3 relances
  respecté, jamais de blocage, `indisponible=True` retourné à chaque appel
  au-delà du quota.
- Deux appels concurrents (2 fils) après une mort du moteur : les deux
  aboutissent sans corruption ni blocage (verrou par instance déjà en
  place).
- Fichier `moteur_erreurs.log` : contenu vérifié (heure, opération, message,
  code de sortie, relances, stderr).
- Contexte coach sans verdict : `get_coach_response` refuse l'appel
  (`pas_de_verdict_exercice`) avant toute requête réseau (vérifié avec une
  clé API factice) ; `_build_context_text` produit la mention explicite
  requise sans jamais inventer de verdict ; cas de données partielles
  (verdict "bon" sans évaluation ni ligne, reproduisant le cas réel Rc1)
  vérifié champ par champ.
- Démarrage à froid réel (import de `app.py`, nouvelle instance Stockfish) :
  `get_move`/`evaluate` fonctionnels immédiatement.
- Position réelle du signalement (Re5, `4r2k/5p1p/pp1q1p2/2p2Q2/1PPp4/P6P/
  5PP1/3R2K1 b - - 0 23`) : confirmé avec le vrai moteur que Re5 est
  classé "bon" (delta ≈ 33cp), pas une gaffe — corrobore le constat
  d'Alain.
- Aucun appel API réel effectué (pas de clé configurée dans ce worktree,
  conformément à la consigne de ne pas toucher au `.env`) : vérifié à la
  place le contenu exact du contexte/system prompt transmis en amont de
  l'appel.

### Limites connues

- La cause exacte de la toute première panne réelle (19h25/19h26) reste
  non reproduite à l'identique (pas de cause unique confirmée : le candidat
  retenu — appel bloquant sans timeout — est corrigé par prudence, sans
  certitude absolue qu'il s'agisse de LA cause ; aucune autre cause probable
  trouvée dans le code des issues #75/#76/#77 examiné).
- Le minuteur de garde côté interface (30s) et le délai d'appel moteur
  (12s) + une relance sont indépendants : un cas pathologique pourrait en
  théorie dépasser 30s côté interface tout en restant sous le délai moteur
  cumulé — jugé acceptable (le message « analyse indisponible » reste
  correct dans ce cas, juste potentiellement affiché un peu après que le
  serveur ait déjà résolu la panne de son côté).

# Changelog — Issue #78

## Exercices : nouvelle source « Problèmes Lichess » avec niveau adaptatif par thème

- Nouveau script `preparer_puzzles_lichess.py` (hors-ligne, sans accès
  réseau) : lit le CSV de la base ouverte Lichess (licence CC0, décompressé,
  `.gz` via la stdlib, `.zst` via le module tiers optionnel `zstandard` sinon
  message clair pour décompresser à la main), filtre les problèmes fiables
  (Rating 800-2200, RatingDeviation ≤ 100, NbPlays ≥ 500, Popularity ≥ 80),
  classe chacun dans les 16 catégories de thème et par phase
  (opening/middlegame/endgame), échantillonne au plus 200 problèmes par
  (catégorie, tranche de note de 100 points), affiche un résumé et écrit
  `data/puzzles_lichess.json` (donnée personnelle, hors git). CSV d'essai
  fourni à la racine (`puzzles_lichess_exemple.csv`, 34 lignes, tous thèmes,
  mats en un/plusieurs coups, quelques lignes volontairement hors filtre).
- Nouveau module `lichess_puzzles.py` : les 16 catégories de niveau
  (clouage, attaque à la découverte, coup défensif, coup silencieux,
  zugzwang, finale de tours, finale, finale de pions, roi exposé,
  attraction, attaque sur l'aile roi, pion avancé, sacrifice, mat,
  fourchette, milieu de jeu) avec leur libellé FR ; valeur de départ par
  catégorie pondérée vers 1471 (performance Lichess globale d'Alain) selon
  le nombre de problèmes déjà faits dans cette catégorie
  (`(n*perf+5*1471)/(n+5)`, poids réglable) ; tirage pondéré par catégorie
  (favorise les niveaux bas, `poids=1/niveau`) puis par fenêtre de note
  (±100, élargie par paliers si vide) en réutilisant tel quel
  `exercise_history.choisir_exercice` (clé d'historique
  `"lichess:<PuzzleId>"`, pas une FEN — même fichier
  `exercice_historique.json` que la source "Mes erreurs", sans collision) ;
  mise à jour du niveau selon la formule Elo après chaque résultat (pas
  réglable `PAS_ELO=28`, borné à [400, 3000]), persistée dans
  `data/niveau_exercices_lichess.json`.
- `config.py` : `LICHESS_PUZZLES_PATH`/`LICHESS_NIVEAUX_PATH` (sous
  `DATA_DIR`, gitignorés).
- `app.py` : `exercise_new`/`exercise_answer` acceptent `data.source`
  (`"mes_erreurs"` par défaut, inchangé, ou `"lichess"`). Branche dédiée
  `_on_exercise_new_lichess`/`_on_exercise_answer_lichess` : jugement du
  premier coup (réussi si identique à la solution, s'il donne mat — y
  compris un mat différent de la solution — ou s'il est équivalent d'après
  Stockfish réel : perte < 30cp, `SEUIL_PUZZLE_EQUIVALENT_CP`, plus strict
  que le seuil "bon" 50cp de "Mes erreurs" car la solution Lichess est
  unique par construction, ou garde-fou "position déjà décidée" détecté) ;
  "meilleur coup"/ligne jouable = la solution déclarée du problème (jamais
  une ligne recalculée par Stockfish) ; aucun `coup_reel` transmis pour
  cette source ; met à jour le niveau de la seule catégorie ayant servi au
  tirage, même si le problème porte plusieurs thèmes de catégorie.
- `llm_coach.py` : `_build_context_text` ajoute thèmes/note du problème/
  niveau d'Alain dans la catégorie quand transmis ; nouvel addendum système
  `_EXERCISE_LICHESS_ADDENDUM` (réponse courte, pas de "coup réel à
  l'époque") ajouté en complément de `_EXERCISE_SYSTEM_ADDENDUM` existant.
- `templates/index.html`/`static/exercise.js` : sélecteur de source ("Mes
  erreurs"/"Problèmes Lichess") à côté du sélecteur de phase (desktop) et
  dans la feuille "Nouvel exercice" (mobile, pilote le même `<select>`) —
  désactivé avec une phrase explicite si `data/puzzles_lichess.json` est
  absent (`lichess_puzzles_disponible`, calculé au démarrage, rendu côté
  serveur). "Exercice suivant"/"Autre catégorie" conservent la source
  choisie (`exerciseCurrentSource`, même mécanisme que `exerciseCurrentPhase`
  pour la phase, issue #76). Ligne d'état dédiée `#exercise-lichess-info`
  ("Problème `<note>` · ton niveau en `<catégorie>` `<niveau>`"). La ligne
  "Solution du problème" réutilise le tableau "Lignes du coach"/le mécanisme
  Play existants (`_exerciseAddStockfishLine`, libellé conditionnel selon la
  source). Source "Mes erreurs" inchangée (code intact, juste un paramètre
  `source` supplémentaire par défaut sur sa valeur historique).
- `engine_stockfish.py` : nouvelle constante `SEUIL_PUZZLE_EQUIVALENT_CP`
  (30cp), documentée en regard de `SEUIL_IMPRECISION` pour reconnaître le
  garde-fou "position déjà décidée".
- `CONTEXTE.md` : section dédiée (format du pool, commande de préparation,
  catégories, formule et paramètres du niveau, jugement, interface).

### Tests
Sur `puzzles_lichess_exemple.csv` (34 lignes) :
`preparer_puzzles_lichess.py` → 24 problèmes conservés, 9 écartés par le
filtre de fiabilité, 1 sans catégorie connue, les 16 catégories toutes
représentées après échantillonnage. Tirages directs (`lichess_puzzles`) :
notes toujours dans la fenêtre, thèmes conformes à la phase demandée pour
`toutes`/`opening`/`middlegame`/`endgame`, jamais deux fois le même problème
de suite sur un pool restreint. Mise à jour Elo : 8 réussites font monter le
niveau, 20+500 échecs le font redescendre sans jamais sortir de [400, 3000],
500 réussites ne dépassent jamais 3000. Jugement avec un **vrai moteur
Stockfish** (`/usr/games/stockfish`) : coup identique à la solution (mat en
1, Scholar's mate) → réussi ; mat différent de la solution (position à deux
mats construite pour le test) → réussi ; coup équivalent (double reprise de
cavalier, delta 0cp) → réussi ; coup clairement hors-sujet → raté. Scénario
serveur complet (`app.py`, sans passer par un vrai réseau SocketIO,
handlers appelés directement avec `emit`/`llm_coach.get_coach_response`
interceptés) : tirage, réponse, historique ("déjà fait" après coup),
niveau Elo mis à jour et persisté, source "Mes erreurs" inchangée (pool
vide → erreur propre), source Lichess désactivée proprement si le fichier
est absent même en forçant l'événement socket côté client. Contenu exact
envoyé au coach vérifié (`source_lichess`, `themes_lichess`,
`rating_probleme`, `niveau_categorie`, `categorie_libelle`, absence de la
clé `coup_reel`) — **aucun appel réseau réel à l'API Claude** n'a été fait
(aucune clé API dans le worktree, conformément au périmètre strict : la clé
réelle d'Alain vit dans `~/ChessCoach/.env`, hors périmètre), conformément
au repli prévu par l'énoncé. UI vérifiée avec un vrai navigateur
(Playwright/Chromium) : sélecteur de source et ligne d'état sur desktop et
en émulation mobile 390×750 (aucun débordement horizontal), feuille mobile,
"Exercice suivant" conservant phase+source, désactivation propre de la
source (option et pill grisées, message explicatif, garde-fou serveur même
en forçant l'événement) quand `data/puzzles_lichess.json` est absent.
Toutes les données de test ont été isolées sous `/tmp` (chemins de
configuration redirigés avant import) — aucune donnée personnelle réelle
sous `~/ChessCoach/data` n'a été modifiée par ces tests.

# Changelog — Issue #77

## Analyse de partie — échec systématique pour toute position de départ non standard

- Cause racine trouvée et reproduite de façon déterministe : `lancerAnalyse()`
  (board.js) et `_analyse_full_game()` (app.py, bouton "Analyser cette
  partie") ne transmettaient/ne rejouaient jamais la position de départ
  réelle de la partie — toujours `chess.Board()` standard côté serveur. Pour
  une partie pédagogique avec Alain aux Noirs (Stockfish joue 1.e3/1.d4/...
  avant que la partie ne commence pour lui, `[SetUp "1"]`/`[FEN "..."]`) ou
  pour le mode travail de finales (position-type toujours non standard), le
  premier demi-coup rejoué ne correspondait jamais au trait de la position
  standard → `ValueError("Coup illégal")` → "L'analyse a échoué" à chaque
  fois, pas de façon ponctuelle. Reproduit via un client SocketIO direct
  (sans navigateur) avant correctif, confirmé corrigé après.
- `static/board.js` (`reviewStartFen`, `parsePgn`, `lancerAnalyse`),
  `static/controls.js` (`getActiveModeStartFen`), `static/game_analysis.js`
  (`analyserPartieCourante`) : la position de départ réelle (FEN de l'en-tête
  PGN, posé automatiquement par chess.js dès qu'une position non standard est
  chargée) est désormais transmise au serveur avec les coups UCI.
- `app.py` (`_analyse_full_game`, `on_analyser_pgn`) : rejoue désormais depuis
  `start_fen` si fourni, au lieu de toujours `chess.Board()`.
- Messages d'erreur distincts dans l'onglet Analyse (`game_analysis.js`) au
  lieu du seul "L'analyse a échoué" : moteur indisponible, partie vide,
  position de départ invalide, coup incohérent, erreur interne.
- Relance automatique unique en cas d'absence de réponse du serveur (délai
  de 75s, `_lancerAnalyseAvecRelance`) — couvre le cas "moteur occupé" ou
  "délai dépassé" évoqué dans le rapport de test, même si la cause
  effectivement reproduite ci-dessus est désormais corrigée.
- `config.py`/`app.py` (`ANALYSE_ERREURS_LOG_PATH`, `_log_analyse_erreur`) :
  chaque échec de l'analyse est tracé dans `data/logs/analyse_erreurs.log`
  (heure, mode d'origine, message) — fichier de données personnelles, sous
  `DATA_DIR`, gitignoré.

## Bandeau de fin de partie mobile

- Nouvelle bande compacte (`#mobile-game-over-bar`, d'après
  `design/partie_mobile/FinCoach.dc.html`) qui remplace la barre d'actions
  sur mobile à la fin d'une partie : résultat + boutons "Analyser cette
  partie" (si disponible) et "Nouvelle partie". L'ancien grand bandeau
  (`#game-over-banner`) est masqué sur mobile (`body.mobile-game-active
  #game-over-banner { display:none!important; }`) et reste inchangé sur
  grand écran. Disparaît en plateau réduit comme la barre d'actions.
- `static/controls.js` (`switchModeTab`) : le bandeau/la bande de fin de
  partie se masque désormais en changeant d'onglet vers un mode différent de
  celui où la partie s'est terminée (Bibliothèque/Revue PGN, Exercice,
  Éditeur, ou un autre mode de partie) — auparavant il restait affiché
  indéfiniment au-dessus du plateau partagé par tous les onglets.
- `static/mobile_game.js` (`mobileNewGameFromBanner`) : "Nouvelle partie"
  ramène l'écran à l'état avant-partie du mode actif (boutons "Jouer les
  Blancs/Noirs" ou contrôles de démarrage), sans recharger la page — jusqu'ici
  la classe "game-over-active" verrouillait ces contrôles sur mobile sans
  aucun moyen de la lever avant qu'une nouvelle partie démarre effectivement
  (boutons invisibles en boucle fermée).

## Bouton "..." redondant de la rangée de navigation

- Supprimé (`#review-more-menu`, templates/index.html + fonctions
  `toggleReviewMoreMenu`/`closeReviewMoreMenu`, controls.js) : faisait double
  emploi avec le menu "..." de l'en-tête (`#game-menu-dropdown`), qui contient
  déjà "Extraire le FEN".

## Modes ouverture et finales inertes sur mobile

- Cause trouvée (reproduite par exécution JS réelle en DOM headless) : les
  seuls contrôles permettant de réellement démarrer ces deux modes (le champ
  "Nom de l'ouverture" + son message d'erreur ; le sélecteur de position-type
  de finale + "Camps inversés") étaient enfermés dans le menu "..." (fermé
  par défaut sur mobile), hors de la zone toujours visible où se trouvent les
  boutons "Jouer les Blancs/Noirs" — un clic sur ces boutons, visibles mais
  dépendants d'un champ invisible, ne faisait rien.
- `templates/index.html` : `#opening-name-input`/`#opening-status` déplacés
  dans `#opening-start-buttons` (déjà toujours visible sur mobile) ; nouveau
  `#finale-picker-row` (sélecteur + "Camps inversés") extrait de
  `#finale-extra-controls` et placé dans un nouveau slot toujours visible
  `#mobile-finale-start-slot`.
- `static/finales.js` (`placeFinaleStartButtonsForViewport`) : même mécanique
  que `placeOpeningStartButtonsForViewport` (opening.js).
- `static/mobile_game.js` : `mobile-finale-start-slot` ajouté aux blocs
  relocalisés ; "finale" rejoint "pedagogic"/"opening" dans les modes à slot
  de démarrage dédié (`_updateActionBarState`).

## Abandon modifiant l'apparence du plateau sur mobile

- Régression du diff en cours de cette même issue (le nouveau
  `#mobile-game-over-bar` ci-dessus, une fois placé dans la zone mesurée par
  `_updateGameBoardMaxSize` comme "chrome" sous le plateau, faisait varier
  `--bd-size-game-max` au moment précis de l'abandon — sans jamais toucher
  `.board-compact` ni le réglage de taille choisi). Corrigé en sautant la
  remesure tant que "game-over-active" est actif (`static/mobile_game.js`,
  `_updateGameBoardMaxSize`) : conserve la dernière taille mesurée pendant la
  partie jusqu'au retour à une nouvelle partie.

## Tests

Vrai Stockfish (`/usr/games/stockfish`) + vraie clé API Claude (chargée
depuis `~/ChessCoach/.env`, sans le modifier, dans un processus séparé sur le
port 5001 — le `.env` lui-même n'a pas été touché) + Playwright (Chromium
headless, viewports 390×750 et 360×640, émulation tactile) :
- Partie pédagogique, Alain Noirs puis Blancs, depuis la position de départ
  après le premier coup de Stockfish : quelques coups, abandon, "Analyser
  cette partie" — analyse aboutit et s'affiche dans l'onglet Analyse, dans
  les deux cas.
- "Nouvelle partie" sans recharger la page, puis démarrage effectif d'une
  deuxième partie (Blancs) — fonctionne, analyse de cette deuxième partie
  aussi vérifiée.
- Changement vers Bibliothèque/Ouverture/Finales/Exercice/Éditeur après fin
  de partie : aucun reste du bandeau ni du rapport, aux deux largeurs d'écran.
- Démarrage et jeu en mode ouverture (nom saisi + "Jouer les Blancs", coup
  joué) et en mode finales (sélection + coup joué) sans ouvrir le menu "...".
- Réglage `--bd-size-game-max` identique avant/après abandon, en ouverture et
  en finales (`.board-compact` jamais posée).
- Aucun débordement horizontal (390×750 et 360×640).
- Grand écran (1280×900) : ancien bandeau inchangé, analyse fonctionnelle,
  `mobile-game-active` jamais posé.

## Limites

- L'échec "ponctuel" de l'analyse décrit par Alain n'a pas pu être reproduit
  à l'identique (succès puis réussite immédiate sans modification) : la
  cause trouvée et corrigée ci-dessus est en revanche parfaitement
  déterministe (échoue à 100% avant correctif, jamais après) et correspond
  exactement au scénario et au FEN décrits dans l'issue — très probablement
  la cause réelle, le caractère "ponctuel" relevant d'une imprécision de
  souvenir plutôt que d'une véritable intermittence.
- La relance automatique en cas de délai dépassé (nouveau code,
  `GAME_ANALYSIS_TIMEOUT_MS`) n'a pas pu être testée en conditions réelles
  (il aurait fallu simuler un moteur qui ne répond jamais pendant 75s) —
  relue mais pas exercée en direct.
- Écart pré-existant non traité ici (hors périmètre de cette issue) : le mode
  "partie libre" n'a toujours pas de contrôle de démarrage dédié visible sur
  mobile hors du menu "...", seulement le message d'invite générique.

# Changelog — Issue #76

## Mode Exercice — variété et historique des positions, indicateur « déjà fait », bouton « Exercice suivant »

- Nouveau module `exercise_history.py` : historique local des exercices
  proposés (donnée personnelle, `config.EXERCICE_HISTORIQUE_PATH` =
  `data/exercice_historique.json`, hors git comme le reste de `data/`),
  indexé par FEN de départ — `{nb_fois, derniere_date, dernier_resultat}`
  par position. `enregistrer_proposition` (appelé au tirage) incrémente
  `nb_fois`/met à jour `derniere_date` sans toucher au résultat ;
  `enregistrer_resultat` (appelé après verdict) enregistre réussi/raté sans
  toucher `nb_fois`/`derniere_date`.
- `choisir_exercice` remplace le tirage uniforme avec remise d'origine
  (issue #7) par un tirage priorisant la variété : (1) positions jamais
  proposées, (2) à défaut positions « dues » pour révision espacée — ratées
  depuis `DELAI_REVISION_RATE_JOURS` (3 jours) ou réussies depuis
  `DELAI_REVISION_REUSSI_JOURS` (14 jours), ces deux constantes réglables en
  un seul endroit du module — (3) catégorie épuisée (ni 1 ni 2) : reprise du
  quart le plus ancien de la phase, délais ignorés. Dans le niveau retenu,
  tirage uniforme (comme l'origine, pas de pondération) en évitant si
  possible de reproposer la même « nature » (`sous_type`
  matériel/positionnel) que le tirage précédent — mémorisée côté serveur
  (`_dernier_sous_type_tire`, app.py), pas persistée entre deux lancements.
- `app.py` (`on_exercise_new`) : lit l'historique avant tirage (pour
  l'indicateur « déjà fait »), appelle `choisir_exercice`, puis
  `enregistrer_proposition` ; transmet au client `deja_fait`/`nb_fois`/
  `dernier_resultat` (état AVANT ce tirage). `on_exercise_answer` :
  enregistre le résultat (réussi = verdict Stockfish « bon », qui couvre
  aussi le cas « coup proposé == meilleur coup » puisqu'un coup identique au
  meilleur coup a toujours un delta_cp de 0, classé « bon » par
  `engine_stockfish.classifier_coup`) dès qu'un verdict a pu être rendu.
- `exercise.js`/`templates/index.html` : indicateur « Déjà fait · N fois ·
  dernier résultat : réussi/raté » dans la ligne d'état de l'exercice,
  couleur `--cc-text-muted` (jamais `--cc-accent`/terracotta, réservé au
  cliquable dans cette appli) — discret, non cliquable, n'empêche jamais de
  rejouer l'exercice, absent pour une position jamais proposée, visible dès
  l'affichage de la position (avant toute réponse). Visible sur mobile et
  grand écran (pas de media query spécifique, hérite du flux normal de la
  colonne du mode exercice).
- Bouton « Exercice suivant » : relance directement un exercice de la même
  catégorie (phase) que l'exercice en cours, sans ouvrir la feuille ni le
  sélecteur de phase (`exerciseCurrentPhase`, mémorisée à chaque tirage,
  indépendante du `<select>`). Grand écran : à côté de « Nouvel exercice »
  dans l'onglet Exercice. Mobile : devient l'action principale
  (`btn-filled`) de la barre du bas à 3 boutons (« Reprendre » / « Exercice
  suivant » / « Autre catégorie » — ex-« Nouvel exercice », renommé pour
  rester clair à 3 boutons côte à côte ; comportement inchangé, ouvre
  toujours la feuille de choix de phase) ; gap/padding/taille de police de
  la barre resserrés pour que les trois restent lisibles sans débordement
  horizontal sur un écran de 390px. Disponible dans tous les états d'un
  exercice déjà chargé (avant réponse, après verdict, en exploration
  libre) — comme `exercise_new`, aucun état serveur à nettoyer entre deux
  tirages.
- Tests : vrai appel socket.io/Stockfish/Flask-SocketIO possible depuis ce
  worktree (venv `~/ChessCoach/venv`, Stockfish 16 réel, les 1051 vraies
  entrées de `~/ChessCoach/data/erreurs_detectees.json`) — utilisé pour
  toute la vérification fonctionnelle, historique redirigé vers un fichier
  temporaire à chaque run pour ne jamais écrire dans les données
  personnelles réelles. Scénarios simulés et vérifiés bout en bout :
  positions réussies récemment → jamais reproposées tant qu'une alternative
  existe ; position ratée ancienne (10 jours) → seule à ressortir face à un
  reste de catégorie « réussi » récent ; catégorie épuisée (tout un pool
  « réussi » récent) → repli sur le quart le plus ancien. Indicateur « déjà
  fait » vérifié par capture d'écran (Playwright/Chromium réel) : absent sur
  une position neuve, texte et couleur (`--cc-text-muted`, pas
  `--cc-accent`) corrects sur une position connue. Plusieurs « Exercice
  suivant » enchaînés en catégorie Finale sans rouvrir la feuille, phase
  inchangée à chaque tirage, vérifié en grand écran ET sur émulation mobile
  390×750 (Playwright) : pas de débordement horizontal
  (`scrollWidth`/`clientWidth`), 3 boutons de la barre du bas lisibles. Pas
  de vrai appel à l'API Claude (pas de `ANTHROPIC_API_KEY` dans
  l'environnement de cette session) : le verdict Stockfish et
  l'enregistrement dans l'historique ne dépendent pas de cet appel (ont lieu
  avant), seul le commentaire du coach échoue proprement (`no_api_key`),
  sans rapport avec l'objet de cette issue.
- Limites connues : le compteur « nombre de fois proposé »/« déjà fait »
  est indexé par FEN de départ exacte — deux erreurs distinctes partageant
  rigoureusement la même position de départ (parties différentes) comptent
  comme un seul exercice du point de vue de l'historique, ce qui est le
  comportement voulu. L'anti-répétition « même nature à la suite »
  (`sous_type`) ne survit pas à un redémarrage de l'appli (mémoire de
  processus, pas de fichier) — jugé sans intérêt à persister pour un simple
  confort de variété à l'intérieur d'une session.

# Changelog — Issue #75

## Mode exercices (suite) : verdict fiable (mats, positions décidées), grands nombres en mots, lignes principales décrites, qualité des positions proposées

Suite de l'issue #73, à partir d'un audit de 18 appels réels du mode
exercices (15 exercices, Haiku) vérifiés avec Stockfish.

- **Grands nombres cités comme des pions** (`engine_stockfish.py`,
  `game_facts.py`, `llm_coach.py`) : `EngineManager.evaluate_move` ne
  plafonnait jamais `delta_cp` (contrairement à `build_patterns_erreurs.py`/
  `_analyse_full_game`), et `_eval_blancs_apres` (app.py) transmet un score
  Stockfish brut, non borné — dans une position de gain forcé pas encore
  détectée comme un mat, Stockfish peut reporter plusieurs milliers de
  centipawns (constat réel : 19974/3456 cp cités "+199,74"/"+34,56" pions).
  `game_facts.describe_eval_alain_cp_clause`/`describe_perte_cp_clause`
  (nouveau seuil `SEUIL_GRANDE_VALEUR_CP = 1000`, même valeur que
  `SEUIL_DEJA_DECISIF`/`SEUIL_DECIDE`) reformulent désormais en mots
  ("position gagnée de façon forcée pour Alain"/"perte d'une ampleur
  extrême...") toute évaluation ou perte au-delà de ce seuil, jamais le
  chiffre brut — utilisées par `_build_context_text` pour `eval_alain_cp`/
  `verdict_delta_cp`, et par `build_game_facts_text` pour `perte_cp`.
  `_EXERCISE_SYSTEM_ADDENDUM` interdit désormais explicitement au coach
  d'inventer un chiffre pour remplacer une formulation en mots, même si
  Alain le demande explicitement.

- **Verdict faux sur un mat** (`engine_stockfish.py`, point 2a) : cause
  racine identifiée dans `EngineManager.evaluate_move` — dès que
  l'évaluation APRÈS le coup était un score de mat (`cp_apres is None`),
  l'ancien code renvoyait toujours `"bon", 0`, sans jamais vérifier de QUEL
  côté était ce mat. Un coup qui permet un mat forcé CONTRE le joueur
  (ex. `Ra8` dans `3Bk3/R6p/8/2pb4/7P/6P1/1r3P2/6K1 w - - 3 31`, qui autorise
  `Rb1+ Kh2 Rh1#`) recevait donc le même verdict `"bon"` qu'un coup qui mate
  l'adversaire. Réécriture complète sur un barème unique mat/cp
  (`_score_valeur_joueur`, formule `mate_score=100000` déjà utilisée par
  `build_patterns_erreurs.py`/`_analyse_full_game`), avec vérification
  explicite du signe du score de mat après coup (`qualite = "blunder"`,
  `delta_cp = DELTA_CP_MAT_CONTRE = 9999`, sentinelle hors échelle).

- **Verdicts trop sévères en position déjà décidée** (`engine_stockfish.py`,
  point 2b) : nouveau seuil `SEUIL_DECIDE = 600` — un coup qui conserve un
  avantage supérieur à ce seuil pour le joueur, avant ET après le coup, est
  désormais ramené à `"imprecision"` au plus, jamais `"erreur"`/`"blunder"`
  (ex. `Rf6+` dans `8/1p3kpp/3rr3/1R3K2/8/8/8/8 b - - 5 48`, position déjà
  +9,1 pour Alain, n'est plus "erreur"). Ce garde-fou ne s'applique JAMAIS
  quand le coup fait basculer vers un mat forcé contre le joueur (point 2a
  prioritaire).

- **Lignes principales racontées de mémoire** (`game_facts.py`, point 3) :
  nouvelles fonctions `describe_pv_with_balance`/`format_pv_with_balance`,
  qui décrivent mécaniquement (`_decrit_coup_mecanique`, déjà utilisée par
  `describe_move_mechanically`) chacun des 4 premiers demi-coups d'une ligne
  principale ET le solde matériel CUMULÉ pour Alain après chaque demi-coup
  (`_materiel_alain`) — ex. `Qh8+ Ke7 Qxd8+ Kxd8` dans
  `3q1k2/5p2/1p6/1P2Q3/8/5P2/6P1/6K1 w - - 7 47` affiche un solde qui revient
  à +1 après le dernier coup, identique à avant la séquence : un échange de
  dames, pas un gain net. `on_exercise_answer` (app.py) calcule ce détail
  pour `pv_coup_propose`/`pv_meilleur_coup` et le transmet dans le contexte
  (`pv_*_detail`) et au client (`exercise_comment`, `exerciseChatContextExtra`
  dans exercise.js). `_EXERCISE_SYSTEM_ADDENDUM` interdit au coach d'annoncer
  un gain/perte de pièce sur une ligne si ce solde cumulé ne le confirme pas.

- **Qualité des positions proposées** (point 4) :
  - `build_patterns_erreurs.py` : nouvelle fonction `_revalider_erreur`,
    appelée sur chaque candidat `"erreur"`/`"blunder"` détecté en première
    passe (profondeur `PROFONDEUR = 10`, choix de vitesse) avant écriture
    dans `erreurs_detectees.json` — réévalue à `DEPTH_ANALYSE_PARTIE` (16,
    déjà utilisée par "Analyser cette partie") et écarte le candidat si le
    coup réel perd moins d'~100cp par rapport au meilleur coup à cette
    profondeur (seuil déjà intégré à `classifier_coup`, pas de constante
    redondante), ou si la position reste décidée dans le MÊME sens avant et
    après le coup (`SEUIL_DECIDE = 600`, gagnant ou perdant). Testé sur la
    position Qh4 citée dans l'issue (`r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/
    P1R2qPP/3QR2K b - - 3 26`) : écartée (confirmé ci-dessous).
  - Nouveau script `revalider_erreurs_detectees.py` (livré, PAS exécuté sur
    les données réelles) : revalide un `erreurs_detectees.json` déjà
    existant avec `build_patterns_erreurs._revalider_erreur`, sauvegarde
    automatique horodatée de l'ancien fichier avant toute écriture, résumé
    conservées/écartées. Commande à lancer (après sauvegarde automatique) :
    `python3 revalider_erreurs_detectees.py`
  - `_EXERCISE_SYSTEM_ADDENDUM` (prompt) : quand le coup réel était
    pratiquement aussi bon que le coup de référence (verdict `"bon"`/
    `"imprecision"`), le texte du contexte le dit déjà explicitement (verdict
    qui "fait foi") — pas de changement de prompt séparé nécessaire, le
    garde-fou de point 2b couvre aussi ce cas en amont (une position qui
    reste décidée identiquement des deux côtés n'est de toute façon plus
    classée erreur par le correctif ci-dessus).

- **Bouton "Demander l'avis du coach" pendant un exercice** (point 5,
  `static/board.js`, `static/exercise.js`, `app.py`) : ce bouton
  (`askExerciseCoach` → `askCoachOnDemand` → `coach_comment_on_demand`) ne
  transmettait que `fen`/`camp_alain`, contrairement à une question posée
  dans le chat libre pendant le même exercice (`coachBuildContext`, qui
  fusionne déjà `exerciseChatContextExtra()`). `askCoachOnDemand` accepte
  désormais un 4e paramètre optionnel `extraContext`, fusionné dans le
  payload envoyé ; `askExerciseCoach` lui passe `exerciseChatContextExtra()`.
  Côté serveur, `on_coach_comment_on_demand` fusionne ces champs
  supplémentaires dans le contexte transmis au coach (`mode_exercice`,
  `fen_depart_exercice`, descriptions mécaniques, verdict, PV détaillées) —
  `meilleur_coup`/`eval_alain_cp`/`eval_alain_mat` de l'exercice (profondeur
  `DEPTH_EXERCICE_TEMPS_REEL`) priment sur le calcul générique du handler
  (profondeur 8) quand disponibles. Les autres modes (pédagogique,
  ouverture, finales) gardent leur comportement inchangé (`extraContext`
  absent).

### Seuils retenus

| Constante | Valeur | Rôle |
|---|---|---|
| `SEUIL_GRANDE_VALEUR_CP` (game_facts.py) | 1000 cp | au-delà, évaluation/perte reformulée en mots |
| `SEUIL_DECIDE` (engine_stockfish.py) | 600 cp | position "déjà décidée" (point 2b), avant ET après |
| `DELTA_CP_PLAFOND` (engine_stockfish.py) | 1000 cp | plafond générique du delta reporté (hors mat) |
| `DELTA_CP_MAT_CONTRE` (engine_stockfish.py) | 9999 cp | sentinelle dédiée : mat forcé contre le joueur |
| seuil de perte "pas une vraie erreur" (build_patterns_erreurs.py) | ~100 cp | déjà intégré à `classifier_coup` (`SEUIL_IMPRECISION`), pas de nouvelle constante |

### Vérifications effectuées (Stockfish réel, `/usr/games/stockfish`, depth=18)

- `3Bk3/R6p/8/2pb4/7P/6P1/1r3P2/6K1 w - - 3 31`, `Ra8` : **avant** `"bon"`,
  `delta=0` → **après** `"blunder"`, `delta=9999`, `eval_alain_mat=-2`
  ("mat forcé en 2 coup(s) en faveur de l'adversaire" dans le texte envoyé
  au coach, jamais un chiffre). `Kh2` (même position) reste `"blunder"`,
  `delta≈403-431` (pas de changement : perte réelle, pas un faux positif).
- `8/1p3kpp/3rr3/1R3K2/8/8/8/8 b - - 5 48`, `Rf6+` : **avant** `"erreur"`,
  `delta=100` → **après** `"imprecision"`, `delta=1000` (position déjà
  décidée, +9,1 avant et après).
- `3q1k2/5p2/1p6/1P2Q3/8/5P2/6P1/6K1 w - - 7 47`, `Qh8+` : `"bon"`,
  `delta=0` (coup déjà correctement classé ; le nouveau détail coup par coup
  montre le solde cumulé pour Alain revenant à +1 après `Qxd8+ Kxd8`,
  confirmant l'échange de dames plutôt qu'un gain).
- `describe_eval_alain_cp_clause(19974)` → "position gagnée de façon forcée
  pour Alain (valeur extrême...)" ; `describe_perte_cp_clause(9999)` →
  "perte d'une ampleur extrême..." (jamais de chiffre).
- `revalider_erreurs_detectees.py` sur un fichier de test à 2 entrées
  (jamais sur les données réelles) : la position Qh4
  (`r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/P1R2qPP/3QR2K b - - 3 26`) est écartée
  (1 conservée, 1 écartée) ; la position `Ra8` (vraie gaffe) est conservée,
  reclassée `"blunder"`.
- Contexte exact envoyé au coach (`llm_coach._build_context_text`) vérifié
  texte par texte pour les cas `Ra8`/`Qh8+` ci-dessus (voir rapport de
  clôture de l'issue) : aucun chiffre brut >1000cp, verdict/solde matériel
  cohérents entre eux.
- Fusion de contexte du bouton "Demander l'avis du coach" pendant un
  exercice (point 5) vérifiée par simulation directe de
  `on_coach_comment_on_demand` : `mode_exercice`/`fen_depart_exercice`/
  descriptions mécaniques/verdict bien fusionnés, `meilleur_coup`/
  `eval_alain_mat` de l'exercice priment sur le calcul générique.

### Limites

- Aucune clé API Claude n'est configurée dans ce worktree (`.env` absent) :
  impossible de faire un appel réel à l'API pour vérifier le texte produit
  par le modèle — seul le contenu exact des données envoyées a été vérifié
  (voir ci-dessus), pas la réponse effective d'Haiku/Sonnet à ce nouveau
  contexte.
- `EngineManager.evaluate_move` calcule désormais systématiquement les deux
  évaluations (avant/après coup), y compris dans le cas, auparavant
  optimisé, où la position était déjà un mat forcé avant le coup et
  `return_pv=False` : un appel moteur de plus dans ce cas précis (rare en
  pratique), nécessaire pour détecter qu'un coup peut transformer un mat
  forcé EN FAVEUR du joueur en mat forcé CONTRE lui.
- Le garde-fou "position déjà décidée" (`SEUIL_DECIDE`) de
  `EngineManager.evaluate_move` est scopé à l'avantage DU JOUEUR évalué
  (conforme à la formulation de l'issue, point 2b) ; `build_patterns_
  erreurs._revalider_erreur` applique une variante symétrique (gagnant OU
  perdant) propre à l'amorçage du mode exercice, documentée dans son
  docstring.
- `revalider_erreurs_detectees.py` est livré mais PAS exécuté sur
  `erreurs_detectees.json` réel, conformément à la consigne — la commande à
  lancer par Alain (sauvegarde automatique horodatée avant toute écriture) :
  `python3 revalider_erreurs_detectees.py`

# Changelog — Issue #74

## Mobile : taille du plateau réglable par l'utilisateur (menu « ... »)

- Nouveau réglage « Taille du plateau » dans le menu « ... » des modes de
  partie mobile (libre/pédagogique/ouverture/finales, `<900px`) : trois
  choix (Compact/Normal/Grand), 3 boutons côte à côte sous un titre de
  section, directement sous « Importer un PGN » (`templates/index.html`,
  `#game-menu-dropdown`). Normal reprend exactement le comportement de
  l'issue #71 (confirmé par mesure : tailles identiques avant/après sur un
  même écran).
- `GAME_BOARD_SIZE_PRESETS` (`static/mobile_game.js`) est l'unique endroit
  où sont définis les 3 pourcentages visés et leur garantie de contenu
  visible sous les onglets : Compact 38 % / 180px, Normal 44 % / 180px,
  Grand 52 % / 120px (garantie abaissée exprès — le choix explicite
  d'Alain prime sur elle). `--bd-size-game-pct` (posée par
  `_applyGameBoardSizeChoice`) remplace le `44dvh` auparavant codé en dur
  dans `--bd-size` (`body.mobile-game-active`, `templates/index.html`) ;
  `_updateGameBoardMaxSize` lit désormais `minVisibleBelowTabs` du préréglage
  actif au lieu d'une constante unique. Le plancher `GAME_BOARD_MIN_SIZE`
  (170px, taille du plateau réduit) reste appliqué quel que soit le
  réglage, pour ne jamais descendre en dessous sur les très petits écrans.
- Choix persisté par appareil via `localStorage`
  (`chesscoach-mobile-board-size`), avec `try/catch` à la lecture et à
  l'écriture (navigation privée stricte, quota) — en cas d'échec, le
  réglage reste actif pour la session en cours mais non persisté, sans
  jamais faire planter l'appli. Valeur par défaut : Normal. Appliqué dès
  `DOMContentLoaded` (avant le premier calcul de `--bd-size-game-max`, pour
  ne pas perdre un cycle de rafraîchissement) et immédiatement au clic
  (`gameBoardSizeSet`, sans recharger la page) ; la mise à jour après
  rotation d'écran repose sur l'écouteur `resize` déjà en place depuis
  l'issue #71 (`--bd-size-game-pct` suit nativement les unités `dvh`, et
  `_updateGameBoardMaxSize` se redéclenche).
- Mode exercice, Bibliothèque/Revue PGN, éditeur de position, plateau
  réduit au défilement et disposition grand écran inchangés : le réglage
  n'agit que sur `--bd-size-game-pct`, consommée uniquement par la règle
  `body.mobile-game-active` ; la règle `.board-compact` (plateau réduit)
  continue d'imposer son propre `clamp(150px, 42vw, 170px)`, prioritaire,
  sans lien avec le nouveau réglage.
- **Bug préexistant corrigé au passage** (issues #63/#70/#71, sans rapport
  direct avec cette tâche mais touchant directement sa zone d'affichage) :
  `#mobile-mode-bar-slot` (pastille de modèle + menu « ... », donc
  désormais aussi les 3 nouveaux boutons) n'était caché par AUCUNE règle
  CSS au-dessus de 900px — seule la media query `<900px` le passait en
  `display:flex` ; un `<div>` étant `display:block` par défaut, tout son
  contenu statique (y compris `#game-menu-dropdown`, dont le `display:none`
  n'était lui aussi posé que dans cette même media query) s'affichait donc
  en pleine page au-dessus de l'en-tête sur grand écran. Repéré en testant
  cette issue (captures d'écran desktop) : sans correctif, les 3 nouveaux
  boutons Compact/Normal/Grand auraient rendu ce défaut plus visible
  encore. Correctif : `#mobile-mode-bar-slot { display: none; }` ajouté
  AVANT la media query `<900px` (`templates/index.html`) — placée après
  cette media query, la même règle aurait annulé le `display:flex` mobile
  (déclaration la plus basse dans le fichier l'emporte à spécificité égale,
  même mécanisme de cascade que
  documenté dans le rapport de clôture de l'issue #71). Vérifié identique
  à l'état d'avant cette issue sur grand écran après correctif (plateau
  560px, aucun élément du menu visible hors media query).

### Tests (émulation Playwright/Chromium headless, pas de serveur Flask réel
disponible hors ligne — voir « Limites » ci-dessous)

- 390×750 et 360×640, mode « partie libre », avant et pendant une partie
  réelle (`startFreeGame()`) :
  - Avant partie, 390×750 : Compact 263px, Normal 263px (identique),
    Grand 323px. Pendant partie (chrome plus grand) : Compact 220px,
    Normal 220px (identique), Grand 280px.
  - Avant partie, 360×640 : Compact/Normal 170px (plancher), Grand 213px.
    Pendant partie : Compact/Normal/Grand tous à 170px (plancher — sur cet
    écran, même la garantie réduite de Grand ne suffit pas à dépasser la
    taille du plateau réduit pendant une partie active, comportement
    voulu).
  - Aucun débordement horizontal détecté (`scrollWidth`/`clientWidth`)
    dans aucune configuration testée.
- Persistance : réglage Grand choisi, rechargement de page (nouvelle
  requête HTTP complète, pas juste un re-render JS) → Grand toujours actif
  et appliqué (323px/213px selon l'écran), bouton actif correctement
  surligné dans le menu.
- Application immédiate : chaque clic Compact/Normal/Grand change la
  taille du plateau sans rechargement, vérifié par mesure directe après
  chaque clic.
- Rotation d'écran (viewport 390×750 → 750×390 avec Grand actif) :
  recalcul automatique sans action manuelle (plateau retombe à 170px, le
  plancher, l'espace disponible en paysage avec le chrome fixe étant plus
  restreint).
- Plateau réduit au défilement, avec Grand actif et une partie en cours :
  `window.scrollTo(0, 300)` déclenche bien `.board-compact`
  (`clamp(150px, 42vw, 170px)`, mesuré 164px à 390px de large et 151px à
  360px, conforme à la formule), la zone à onglets reste défilable
  (`scrollHeight >= clientHeight`), et le tap sur le plateau réduit
  restaure le plateau complet à la taille Grand (280px/170px) — aucune
  régression du comportement de l'issue #71 point 4.
- Menu « ... » : 3 boutons de 100×36px chacun à 360px de large, dropdown
  entièrement contenu dans le viewport (droite à 352px sur 360px),
  lisible, état actif visuellement distinct (fond vert clair, même
  habillage que les autres « items de menu actifs » de l'appli).
- Mode exercice (`mobile-game-active` reste `false`), Bibliothèque
  (`mobile-wide-board` reste `true`, 338px) et grand écran (1400×900,
  560px, slot masqué) : mesurés identiques à l'état attendu, aucune
  régression.
- Captures d'écran prises (menu replié/déployé, Compact/Normal/Grand côte
  à côte, plateau réduit au défilement, comparaison desktop avant/après le
  correctif du bug préexistant).

### Limites

- Aucun appel réel à l'API Claude ni au backend Flask/SocketIO : le
  worktree ne dispose pas de `flask_socketio` installé et la tâche
  indique `RESEAU | non` (pas d'installation de paquet via pip). Les
  tests ont donc porté sur le gabarit `templates/index.html` rendu
  directement par Jinja2 (hors `app.py`, avec un contexte minimal simulé)
  et servi en statique, piloté par Playwright/Chromium headless
  (viewports mobiles, `has_touch=True`, clics réels sur les boutons) —
  clairement une émulation plutôt qu'un vrai appel API, mais qui exerce le
  code CSS/JS réel du dépôt (aucune logique dupliquée ni simulée à la
  main) plutôt qu'une lecture statique du code.
- `demarrerPartieLibre` n'existe pas : la fonction réelle est
  `startFreeGame()` (`static/free_play.js`), utilisée pour les tests
  « pendant une partie ».
- Pas de test sur un véritable appareil physique (GSM/PC) ni dans un
  vrai navigateur mobile (Safari iOS, Chrome Android) — seule l'émulation
  de viewport/tactile de Chromium a été utilisée.

# Changelog — Issue #73

## Mode exercices : questions de suivi avec la bonne position, évaluations du point de vue d'Alain, verdict du coach non contredit

- Cause des trois défauts constatés en usage réel (Haiku, exercice fxg4 sur
  r4rk1/pp2n1pp/8/3p1p2/4p1B1/8/P1R2qPP/3QR2K b - - 3 26) :
  - Le contexte transmis au coach (`llm_coach._build_context_text`) ne
    distinguait jamais la position de DÉPART de l'exercice de la position
    ACTUELLEMENT affichée sur l'échiquier — une question de suivi posée
    dans le chat libre pendant l'exercice (`coach_ask`) transmettait
    uniquement le FEN courant (`exerciseGame.fen()`, déjà après le coup
    proposé), jamais le FEN de départ, ce qui a fait nier au coach la
    présence d'un fou pourtant bien présent avant le coup.
  - Les évaluations centipawns (`eval_blancs_cp`/`eval_mat`) étaient
    transmises "point de vue des Blancs" (positif = avantage Blancs),
    signe ambigu dès qu'Alain joue les Noirs — un -131 a déjà été lu par
    le coach comme "légèrement en faveur des Blancs" alors qu'il
    signifiait +131, un avantage pour Alain.
  - Le mode exercice ne réutilisait pas `game_facts.describe_move_
    mechanically` (issue #66, déjà utilisé par le mode "analyse_partie")
    pour décrire les trois coups comparés (proposé/réel/meilleur) : seule
    une fonction locale `_move_details_fr` (app.py), donnant juste le type
    de pièce jouée/capturée sans défenseur ni solde net, était utilisée.
- Correctifs (app.py, llm_coach.py, static/exercise.js) :
  - `on_exercise_answer` transmet désormais `fen_depart_exercice` (position
    de départ) ET `fen` (position actuelle, après le coup proposé),
    séparément étiquetées dans `_build_context_text` — avec une consigne
    explicite de ne jamais conclure qu'une pièce "n'existe pas" sans
    comparer les deux. Le serveur retransmet ces deux FEN, les descriptions
    mécaniques des trois coups et l'évaluation au client dans le payload
    `exercise_comment` ; `exerciseChatContextExtra()` (exercise.js) les
    réinjecte dans toute question de suivi posée ensuite dans le chat
    libre, verdict compris ou en exploration libre.
  - Nouvelle fonction `_vers_point_de_vue_alain` (app.py), appliquée aux
    5 points de contexte transmettant une évaluation Stockfish (exercice,
    pédagogique, ouverture, finales, "Demander l'avis du coach") : le
    contexte ne transmet plus que `eval_alain_cp`/`eval_alain_mat`
    (positif = avantage pour Alain), plus aucun chiffre dont le signe
    dépend de la couleur.
  - `_move_details_fr`/`_parse_move_flexible`/`_PIECE_FR` (app.py)
    supprimées, remplacées par trois appels à `game_facts.
    describe_move_mechanically` (coup proposé, coup réel, meilleur coup),
    calculés depuis la position de départ — mêmes informations
    (défenseur, solde net après reprise, pièces désormais attaquées) que
    le mode "analyse_partie".
  - `_EXERCISE_SYSTEM_ADDENDUM` (llm_coach.py) renforcé : le verdict fait
    foi et ne doit jamais être présenté comme bon/solide même si Alain
    reste mieux dans l'absolu (consigne explicite de le dire dans ce cas :
    "tu restes mieux, mais tu laisses filer l'essentiel de ton avantage"),
    le coach doit énoncer le verdict en premier, et ne doit jamais
    conclure qu'une pièce/case "n'existe pas" sans comparer position de
    départ et position actuelle.
- Point 4 (examen sans correction, cf. rapport de clôture de l'issue) : le
  coup réellement joué à l'époque (Qh4) sur cette position précise est
  quasi équivalent au meilleur coup à partir de depth=16 (delta ≤ 40cp),
  mais apparaît comme une "erreur" (148cp de perte) à depth=10, la
  profondeur utilisée par `build_patterns_erreurs.py` pour qualifier les
  positions d'exercice — un probable artefact d'instabilité de recherche à
  faible profondeur plutôt qu'une vraie gaffe, jamais revalidé à une
  profondeur plus élevée avant inclusion dans `erreurs_detectees.json`.

# Changelog — Issue #72

## Analyser la partie sans quitter l'écran de partie (onglet Analyse)

- Cause du problème signalé par Alain : `analyserPartieDepuisPgn()`
  (`static/game_analysis.js`, point d'entrée du bouton "Analyser cette
  partie" du bandeau de fin de partie) basculait systématiquement vers
  `switchModeTab("library")` puis chargeait la partie dans la revue de
  bibliothèque (`parsePgn`, `board.js`) avant de l'analyser — sur mobile,
  cela masquait l'écran de partie (plateau fixe + onglets Coach/Lignes/
  Analyse/Coups, issue #70/#71) et affichait à sa place tout le contenu de
  la Bibliothèque (chat coach, formulaire d'import, liste des PGN
  enregistrés, programme d'entraînement) en plus du rapport d'analyse.
- Nouveau comportement, uniquement quand l'écran de jeu mobile est actif
  (`isGameUiActive()`, `mobile_game.js` — écran <900px ET mode de partie
  libre/pédagogique/ouverture/finale affiché) :
  - `analyserPartieCourante()` (`game_analysis.js`, bouton de l'onglet
    Analyse ET bandeau de fin de partie via `analyserPartieDepuisPgn`/
    `_lancerAnalyseEnPlaceDepuisBanniere`, nouvelles fonctions) analyse les
    coups RÉELS du mode actif (`getActiveModeMoves()`, `controls.js`) au
    lieu de `reviewMoves`, sans jamais appeler `switchModeTab("library")`
    ni `parsePgn` — le plateau, la position, l'historique et le bandeau de
    fin de partie restent donc exactement ceux du mode en cours, avant et
    après l'analyse.
  - Ouvre directement l'onglet Analyse (`switchGameTab("analyse")`,
    `mobile_game.js`) — le bouton du bandeau et celui de l'onglet lancent
    désormais la même analyse et amènent tous les deux sur ce même onglet.
  - La réponse du serveur (`analyser_pgn_response`) ne touche ni
    `reviewMoves` ni `renderReview()` dans ce cas (nouveau flag
    `_gameAnalysisEnPlace`) — seul `renderGameAnalysisReport()`, déjà
    autonome (ne lit que `_gameAnalysisResults`), affiche le rapport dans
    l'onglet. Le point de nouveauté sur l'onglet (`_gameTabMarkNovelty`,
    déjà existant depuis #71) continue de fonctionner à l'identique.
  - Le cache de session (une partie déjà analysée n'est pas réanalysée,
    issue #59), le défilement automatique vers le rapport et le
    comportement "un clic = une analyse" sont conservés intégralement,
    simplement rebasés sur les coups réels au lieu de `reviewMoves`.
  - Les en-têtes PGN White/Black nécessaires à la déduction du camp
    d'Alain côté serveur (issue #56, `demanderExplicationsCoach`/
    `demanderExplicationCoup`) sont extraits à la volée du PGN de la
    partie en cours (`_gameAnalysisPgnForActiveMode`, réutilise les
    fonctions `_xxxGamePgnForAnalysis` déjà existantes de chaque mode)
    plutôt que de dépendre de `parsePgn` — sans cet ajout, le serveur
    n'aurait plus eu aucun moyen de savoir qui est Alain.
  - Le transfert au coach des coups signalés comme contexte de chat
    (`_coachAnalysisFlaggedMoves`, `board.js`) n'a nécessité AUCUNE
    modification : il comparait déjà `_gameAnalysisResults` aux coups
    réels du mode actif (`getActiveModeMoves()`), pas à `reviewMoves` —
    fonctionne donc identiquement, en place ou pas.
- Hors de ce contexte (grand écran, ou Bibliothèque/Revue PGN elle-même) :
  comportement historique intégralement conservé, aucune ligne de code
  changée sur ce chemin (`switchModeTab("library")` + `parsePgn` +
  `_lancerAnalyseAutoDepuisBanniere`/`analyserPartieCourante` avec
  `reviewMoves`) — décision documentée dans le rapport de clôture (point 5
  de l'issue : changer aussi le grand écran aurait été plus invasif pour
  un gain flou, la Bibliothèque/Revue PGN n'a pas d'écran de jeu à onglets
  à préserver).

## Point 2 — Cliquer sur un coup signalé pendant une analyse en place

- Implémenté (jugé possible sans casser le reste) : en place,
  `explorerCoupFlagge(idx)` prévisualise la position juste avant le coup
  flagué directement sur le plateau réel (`renderBoard(fen_avant, ...)`),
  en réutilisant TEL QUEL le mécanisme de blocage/retour déjà existant de
  la lecture des lignes du coach (`gameCoachLinesPreviewActive`, issue
  #68, `game_coach_lines.js`) : les 4 modes de partie bloquent déjà leurs
  clics de plateau sur ce flag, et `mobile_game.js` suspend déjà sur lui
  le rétrécissement du plateau au défilement — aucun nouveau garde-fou à
  écrire. Un bouton "◀ Revenir à la partie" (barre déjà existante
  `#board-lines-command-bar`, étendue d'un cas supplémentaire) ramène à la
  position finale réelle en redessinant le plateau du mode actif
  (`_gameLinesRerenderCurrentMode`), sans avoir modifié le moindre état
  réel entre-temps (aucun `game.move()`, aucun `socket.emit`).
- Hors de ce contexte (Bibliothèque/Revue PGN), comportement existant
  inchangé : clic sur un coup flagué → mode "partie libre" explorable.

## Point 5 — Grand écran

- Conservé tel quel, comme autorisé par l'issue : `isGameUiActive()`
  (media query stricte <900px) ne peut jamais être vraie en grand écran,
  donc `analyserPartieDepuisPgn`/`analyserPartieCourante` y retombent
  toujours sur le chemin historique (bascule en Bibliothèque/Revue).
  Changer ce comportement aurait demandé de construire un équivalent de
  l'écran de jeu à onglets pour le grand écran, largement hors périmètre
  de cette issue.

## Fichiers modifiés

- `static/game_analysis.js` : nouvelles fonctions
  `_gameAnalysisLiveMoves`/`_gameAnalysisPgnForActiveMode`/
  `_appliquerEntetesPgn`/`_lancerAnalyseEnPlaceDepuisBanniere`/
  `gameAnalysisReturnToPartie` ; `analyserPartieCourante`/
  `analyserPartieDepuisPgn`/`explorerCoupFlagge`/le handler
  `analyser_pgn_response` étendus d'un branchement "en place" sans
  toucher au chemin existant (comportement `enPlace=false` identique
  ligne à ligne à avant, hormis un `_gameAnalysisEnPlace = false` explicite
  ajouté par prudence dans `_lancerAnalyseAutoDepuisBanniere`, cf. rapport
  de clôture).
- `static/game_coach_lines.js` : `_updateBoardLinesCommandBar` gère un cas
  supplémentaire (coup flagué prévisualisé) ; `gameLinesRestore`/
  `gameCoachLinesReset` remettent aussi `_gameAnalysisFlaggedPreviewIdx` à
  `null` par précaution (les deux mécanismes de prévisualisation ne
  doivent jamais rester incohérents entre eux).
- Aucun fichier Python, template ou CSS modifié.

## Tests

- Vérification de syntaxe : `node --check` sur les deux fichiers modifiés
  (OK). Aucun fichier Python touché (`py_compile` non applicable).
- Aucun test E2E réel en navigateur/émulation tactile n'a pu être mené
  depuis ce worktree : aucun outil d'automatisation de navigateur
  (Playwright/Chrome DevTools MCP) n'était disponible parmi les outils de
  cette session, et lancer l'appli Flask réelle aurait fait écrire
  `config.py`/`DATA_DIR` sous `~/ChessCoach/data/`, hors du périmètre
  strict de ce worktree (`/home/alain/chesscoach-issue72`) — cf. précédent
  documenté dans `CHANGELOG.md` (issues #45/#46). Aucune
  `ANTHROPIC_API_KEY` n'était non plus présente dans l'environnement, donc
  un vrai appel à l'API Claude était de toute façon hors de portée.
- À la place : simulation Node (module `vm`, sans jsdom/Flask/Stockfish)
  chargeant les deux fichiers JS réels modifiés avec un DOM et des
  fonctions de mode minimalement mockés, pour exercer le code de contrôle
  réellement modifié. Six scénarios vérifiés avec succès :
  1. Clic direct sur le bouton de l'onglet Analyse pendant une partie
     pédagogique affichée en écran de jeu mobile → ouvre l'onglet, ne
     bascule jamais de mode, n'appelle jamais `parsePgn`, envoie les coups
     réels à l'analyse, renseigne correctement les en-têtes White/Black.
  2. Réponse serveur simulée en place → `reviewMoves` non muté,
     `renderReview()` jamais appelé, rapport bien rendu.
  3. Clic sur un coup flagué → prévisualisation via `renderBoard` sur la
     position correcte, `gameCoachLinesPreviewActive` activé, jamais de
     bascule vers le mode "partie libre".
  4. Retour à la partie → drapeaux remis à zéro, redessin du mode réel
     déclenché.
  5. Hors écran de jeu mobile (grand écran/Bibliothèque) →
     `switchModeTab("library")` + `parsePgn` appelés comme avant,
     comportement historique intact.
  6. Cache de session depuis le bandeau (même partie déjà analysée) →
     aucun nouvel appel à `lancerAnalyse`, réaffichage immédiat.
- Non couvert par cette simulation (à vérifier par Alain en conditions
  réelles, notamment via l'émulation de téléphone demandée par l'issue) :
  rendu visuel effectif (pas de débordement horizontal, positionnement des
  boutons), le point de nouveauté sur l'onglet quand un autre onglet est
  affiché pendant le calcul Stockfish, et le comportement avec un vrai
  appel Stockfish/API Claude.

## Limites connues

- Comme pour la prévisualisation des lignes du coach (issue #68), rien
  n'empêche explicitement un événement serveur arrivant PENDANT une
  partie encore active (ex. `pedagogic_stockfish_move`) de redessiner le
  plateau par-dessus une prévisualisation de coup flagué en cours — limite
  déjà présente avant cette issue pour les lignes du coach, non traitée
  ici (analyser une partie non encore terminée reste un cas marginal, la
  bannière de fin de partie n'apparaissant qu'après abandon/mat/pat/nulle).
- `activeMode` peut, en théorie, ne pas correspondre à `currentModeTab`
  (ex. après un changement d'onglet sans démarrer de partie dans le
  nouveau mode) — ambiguïté déjà présente avant cette issue dans
  `renderHistory`/`coachBuildContext`/`getActiveModeMoves`, non introduite
  ni aggravée ici.

# Changelog — Issue #71

## Mobile : corrections après test de la nouvelle disposition (sélecteur de mode, arrivée dans un mode, plateau plus grand, plateau réduit, écrans mélangés)

- Contexte : Alain a testé sur son GSM les issues #69/#70 et relevé six
  problèmes concrets. Tous corrigés dans le périmètre mobile (<900px)
  existant (`body.mobile-game-active`/nouvelle classe `.mobile-wide-board`,
  `mobile_game.js`/`controls.js`) — grand écran et mode exercice vérifiés
  inchangés (Playwright, cf. tests plus bas).

### Point 1 — Sélecteur de mode toujours accessible
- `#mobile-mode-bar-slot` (contient `.mode-tab-bar`, déplacé par
  `placeModeTabBarForViewport`) redevient `position:sticky; top:0` dans
  **tous** les modes mobiles, pas seulement en mode jeu — l'issue #69 l'avait
  retiré, ce qui privait `.mode-tab-bar.open` (position:absolute) de tout
  ancêtre positionné hors mode jeu : la liste ouverte se positionnait alors
  par rapport à la racine du document entier plutôt que sous le sélecteur
  (symptôme observé : "la liste disparaît, réapparaît au milieu de l'écran
  après défilement").
- Une règle `#mobile-mode-bar-slot { display:block; }` sans media query,
  plus bas dans le fichier, entrait en conflit de cascade avec le nouveau
  `display:flex` (même spécificité, dernière règle du fichier qui gagne) —
  supprimée (un `<div>` est `display:block` par défaut).
- `#board-sticky-wrap` (plateau) se colle désormais juste EN DESSOUS de ce
  sélecteur (`top: var(--mobile-header-h)`, hauteur republiée en continu par
  un `ResizeObserver` dans `controls.js`, même principe que
  `--scroll-padding-top`) plutôt qu'au même niveau.

### Point 2 — Arrivée dans un mode
- `switchModeTab()` (`controls.js`) remonte désormais la page tout en haut
  (`window.scrollTo(0,0)`) à chaque changement d'onglet.
- `_updateBoardCompactState()` (`mobile_game.js`) n'active plus jamais l'état
  réduit tant qu'aucune partie n'est en cours (nouvelle fonction partagée
  `_isCurrentGameRunning()`) ni tant que `window.scrollY <= 0`.
- Capture (390×750, arrivée en partie pédagogique depuis une page défilée) :
  plateau complet, boutons "Jouer les Blancs/Noirs", sélecteur de mode —
  plus d'écran vide.

### Point 3 — Plateau plus grand
- Mode jeu : `--bd-size` (seule variable à ajuster, `templates/index.html`)
  cible jusqu'à 44% de la hauteur dynamique d'écran, sans dépasser
  `calc(100vw - 24px)`. Un 4e terme `var(--bd-size-game-max)`, mesuré en
  continu sur le DOM réel par `_updateGameBoardMaxSize()`
  (`mobile_game.js`, ResizeObserver sur `#board-sticky-wrap`), garantit les
  ~180px de contenu visible sous les onglets demandés — voir "Tailles
  obtenues" et "Limites" plus bas, ce terme est presque toujours la
  contrainte déterminante en pratique.
- `#coord-rank`/`#coord-file` et la barre d'éval Stockfish sont masqués en
  mode jeu ; les coordonnées (lettres/chiffres) sont repliées dans le coin
  haut-gauche de chaque case de bord via `buildBoard()` (`board.js`, nouveaux
  `data-rank-label`/`data-file-label`) + un seul pseudo-élément CSS
  `::before` (`::after` déjà pris par le hachurage `.finale-king-restricted`
  du mode finales).
- Bibliothèque/Revue PGN et Éditeur de position (régression de largeur de
  l'issue #69, `--bd-size` réduit à `30vh` sans ajuster la largeur
  soustraite) : nouvelle classe `.mobile-wide-board` (posée par
  `onGameUiRefresh`) élargit `--bd-size` à `min(58vh, 480px, calc(100vw -
  52px))`, coordonnées repliées dans les cases comme en mode jeu. Mode
  exercice explicitement exclu de cette classe — formule générale (`30vh`)
  inchangée, vérifié identique en px avant/après.

### Point 4 — Plateau réduit au défilement
- L'ancienne bande uniquement textuelle (`#board-compact-strip`) est
  supprimée. `#board-full-view` (le plateau réel, jamais dupliqué) rétrécit
  simplement via un `--bd-size` local (`clamp(150px, 42vw, 170px)`) posé par
  la classe `.board-compact` déjà existante — même rendu, mêmes pièces,
  aucun code de rendu dupliqué. Le matériel capturé est masqué (redondant
  avec `#game-status-line`, qui reste affichée à côté). Les cases
  n'acceptent plus les clics tant que réduit (`pointer-events:none` sur
  `#board`) ; un tap sur `#board-full-view` restaure le plateau complet via
  la nouvelle fonction `_boardFullViewClick()` (vérifie elle-même la classe
  `board-compact`, donc sans effet sur les clics de déplacement de pièce en
  plateau complet).

### Point 5 — Menu "..." sans doublon
- Entrée "Bibliothèque" retirée de `#game-menu-dropdown`
  (`templates/index.html`) — déjà présente dans le sélecteur de mode
  principal.

### Point 6 — Écrans mélangés
- `placePedagogicStartButtonsForViewport`/`placeOpeningStartButtonsForViewport`
  (déjà correctement conditionnées à l'onglet consulté) sont désormais
  appelées à CHAQUE `onGameUiRefresh`, y compris en quittant un mode de
  partie — avant ce correctif, elles n'étaient plus jamais rappelées après
  un passage vers Bibliothèque/Exercice/Éditeur (retour anticipé de
  `onGameUiRefresh` avant leur appel), laissant les boutons "Jouer les
  Blancs/Noirs" coincés dans `#board-column` (visible sur tous les onglets
  mobiles).
- `#shared-mode-controls` ("Contrôles du mode actif") vit hors des onglets
  (issue #15, `#board-column` toujours visible sur mobile) pour rester
  utilisable en arrière-plan sur grand écran — nouvelle classe
  `mode-controls-mismatch` (posée par `_updateModeControlsMismatch()`,
  `mobile_game.js`) le masque sur mobile uniquement quand `activeMode`
  diffère réellement de l'onglet consulté ET que cet onglet est
  Bibliothèque/Exercice/Éditeur (jamais quand il leur appartient lui-même —
  Exercice a besoin de son propre bouton "Demander l'avis du coach", pas
  dupliqué dans la barre du bas mobile).
- `_clearGameAnalysisDisplay()` (nouvelle fonction, `game_analysis.js`) vide
  l'AFFICHAGE du rapport d'analyse (liste, statuts, barre de progression)
  sans toucher au cache `_gameAnalysisResults` (préserve la réutilisation
  automatique de l'issue #59) — appelée au chargement d'une autre partie
  (`parsePgn`, `board.js`), au démarrage de chaque mode de partie/exercice
  (`startFreeGameFromFen`/`startPedagogicGame`/`startOpeningGame`/
  `loadSelectedFinale`/`startFinaleDemo`/`startExercise`) et à chaque
  changement de mode (`switchModeTab`, `controls.js`).

## Tests (Playwright, émulation tactile 390×750 et 360×640)
Aucun vrai appel API/Socket.IO n'était possible depuis ce worktree : lancer
`app.py` charge `config.py`, qui écrit dans `~/ChessCoach/data` (hors
périmètre du worktree). `templates/index.html` a donc été rendu en statique
avec Jinja2 (sans passer par Flask/config.py, aucune donnée personnelle
lue), servi par un simple serveur HTTP local, et piloté par Playwright ;
l'état d'une partie en cours a été simulé en assignant directement les
variables JS globales (`pedagogicActive`, `activeMode`, etc.) plutôt que via
un aller-retour serveur réel — limite documentée, aucun appel Claude/
Stockfish n'a été exercé.

- Point 1 : liste ouverte depuis chaque mode, page défilée (800px) ou non —
  toujours visible entièrement dans le viewport, juste sous le sélecteur ;
  clic en dehors la ferme.
- Point 2 : arrivée en pédagogique depuis une page défilée — scrollY revient
  à 0, plateau complet + boutons "Jouer les Blancs/Noirs" visibles, jamais
  d'état réduit.
- Point 3 — tailles mesurées :
  - Mode jeu (partie pédagogique, avant le premier coup) : 390×750 → plateau
    228px (58,5% largeur / 30,4% hauteur) ; 360×640 → 170px (47,2% largeur /
    26,6% hauteur). En pleine partie (boutons Reprendre/Abandonner affichés,
    passent sur 2 lignes à 360px) : 390×750 → 201px ; 360×640 → 170px
    (plancher `GAME_BOARD_MIN_SIZE`, cf. Limites).
  - Bibliothèque/Éditeur (`.mobile-wide-board`) : 390×750 → 338px (86,7%
    largeur) ; 360×640 → 308px (85,6% largeur) — nettement au-dessus du
    seuil pré-#69 (80,5%).
  - Exercice (formule générale inchangée) : 390×750 → 225px, 360×640 →
    192px — identiques px pour px à la formule d'avant cette issue
    (`min(30vh,420px,calc(100vw-76px))`), confirmant l'absence de
    régression.
  - Plateau réduit (défilement) : 390×750 → 164px ; 360×640 → 151px (cible
    150-170px respectée).
- Point 4 : défilement en onglet Coach → plateau réduit visible (vraie
  mini-vue de la position, plus de bande texte), ligne d'état lisible en
  dessous, boutons masqués, onglets visibles ; tap → retour au plateau
  complet (scrollY=0, classe `board-compact` retirée).
- Point 5 : menu "..." → `["Extraire le FEN", "Importer un PGN", "Coût
  API"]`, pas de "Bibliothèque".
- Point 6 : `activeMode="pedagogic"` + onglet Bibliothèque →
  `#shared-mode-controls` masqué (`display:none`), classe
  `mode-controls-mismatch` posée.
- Aucun débordement horizontal détecté (`scrollWidth <= clientWidth`) sur
  Bibliothèque ni en mode jeu, aux deux largeurs testées.
- Grand écran (1400px) : en-tête visible, `#mobile-mode-bar-slot` vide
  (`display:block`, sans effet), plateau 560px (formule desktop `min(70vh,
  560px)`, inchangée), `mode-tab-bar` reste dans son panneau d'origine,
  `mobile-game-active` jamais posée quel que soit l'onglet — comportement
  desktop intégralement inchangé.
- Aucune erreur JavaScript de page relevée (`page.on("pageerror")`) sur
  l'ensemble des scénarios ci-dessus. `node --check` OK sur les 9 fichiers
  JS modifiés.

## Limites
- La fourchette "44-46% de la hauteur d'écran" demandée pour le plateau des
  modes de partie est un PLAFOND, pas une valeur garantie : sur les
  téléphones courants (~640-800px de haut), la garantie des ~180px de
  contenu visible sous les onglets (elle aussi demandée) est presque
  toujours la contrainte la plus stricte des deux, et donne un plateau plus
  petit que 44% (mesuré : 26,6-30,4% avant la première partie, moins encore
  pendant une partie active sur le plus petit écran testé). Choix assumé :
  la garantie "au moins 180px visibles" a été traitée comme prioritaire sur
  le pourcentage, car sa violation reproduisait un symptôme proche du bug
  d'origine (contenu invisible sans indice de défilement) — seule la valeur
  `GAME_BOARD_MIN_VISIBLE_BELOW_TABS` (`mobile_game.js`) est à ajuster pour
  changer cet arbitrage.
- Sur le plus petit écran testé (360×640), PENDANT une partie active, les 3
  boutons de `#shared-mode-controls` ("Reprendre mon coup"/"Abandonner"/
  "Demander l'avis du coach") passent sur 2 lignes et consomment environ
  128px à eux seuls — dans ce cas précis, ni le plafond des 180px visibles
  ni celui des 44-46% ne sont atteints : le plateau reste bloqué à son
  plancher de sécurité (`GAME_BOARD_MIN_SIZE = 170px`, aligné sur le haut de
  la fourchette du plateau réduit, pour ne jamais devenir plus petit que
  lui) et le contenu visible sous les onglets tombe alors à environ 120px.
  Compromis documenté plutôt que corrigé plus avant (aurait nécessité de
  retravailler la disposition de `#shared-mode-controls` lui-même, hors
  périmètre de cette issue).
- Aucun vrai appel API Claude ni Stockfish n'a été exercé (cf. "Tests"
  ci-dessus) — seul le comportement DOM/CSS/JS a été vérifié. Les captures
  Playwright sont dans `.test_screens/` (non commité, worktree local
  uniquement).
- `.test_render.html` (rendu Jinja2 statique utilisé pour les tests) a été
  supprimé après usage — non commité.

# Changelog — Issue #70

## Écran de partie mobile : plateau fixe, onglets Coach/Lignes/Analyse/Coups, bande compacte (maquette Claude Design)

- Contexte : la disposition mobile précédente (issue #69) gardait déjà le
  plateau visible en permanence, mais tout le reste (chat, lignes, analyse,
  historique, contrôles de mode) restait empilé verticalement. Alain a fait
  dessiner une nouvelle disposition avec Claude Design
  (`design/partie_mobile/`, 14 écrans) : plateau fixe ~36-40% d'écran, barre
  de navigation et barre d'actions compactes, quatre onglets internes
  (Coach/Lignes/Analyse/Coups) sous lesquels seule la zone de contenu
  défile, bande compacte du plateau pendant le défilement ou le clavier
  ouvert, pastille de modèle cliquable et menu "...". Uniquement sur mobile
  (<900px) et uniquement pour les modes partie libre/pédagogique/ouverture/
  finales (`body.mobile-game-active`, posée par `mobile_game.js`) — le mode
  exercice, la bibliothèque/revue, l'éditeur de position et le grand écran
  gardent la disposition existante (issues #50/#63/#65/#69), entièrement
  inchangée en dehors de cette classe (vérifié à 1440px, capture dans le
  rapport de clôture).
- Aucune logique de jeu dupliquée ni réécrite : tout le nouveau fichier
  `static/mobile_game.js` déplace des nœuds DOM existants entre leur
  emplacement d'origine et les nouveaux onglets/menu (même principe que
  `placeModeTabBarForViewport`/`_placeMobileRelocatablesForViewport`,
  `controls.js`, issues #63/#69) — `board.js`/`game_coach_lines.js`/
  `game_analysis.js`/`llm_model.js`/`usage_tokens.js` retrouvent leurs
  éléments par id, peu importe leur parent réel.

### static/mobile_game.js (nouveau)

- `isGameUiActive()` : vrai si <900px ET l'onglet de mode affiché
  (`currentModeTab`, `controls.js`) est free/pedagogic/opening/finale.
- `onGameUiRefresh()` : rafraîchissement central, appelé depuis
  `controls.js` (hooks ajoutés en fin de `switchModeTab`/
  `updateSharedControlBar`, cette dernière déjà appelée par tous les modes à
  chaque démarrage/abandon/reprise/fin de partie — un seul point de
  branchement couvre toutes les transitions). Bascule la classe
  `mobile-game-active` sur `<body>`, déplace les blocs existants (panneau du
  coach, tableau "Lignes du coach", panneau d'analyse de partie, historique
  des coups, sélecteur de modèle, compteur de jetons, barre de navigation,
  barre d'actions partagée, boutons "Jouer les Blancs/Noirs" pédagogique/
  ouverture, onglets) vers leur nouvel emplacement, ou les restaure à leur
  place d'origine si le mode jeu n'est plus actif.
- `switchGameTab`/`_gameTabMarkNovelty` : les quatre onglets internes, avec
  point de nouveauté (petit point non cliquable, donc pas en terracotta) sur
  Lignes/Analyse quand du contenu arrive pendant qu'un autre onglet est
  affiché — appelé depuis `game_coach_lines.js`/`game_analysis.js`.
- `gameMenuToggleModelPopup`/`gameMenuToggleDropdown`/`gameMenuClose` :
  pastille de modèle (miroir texte de `#llm-model-selector`, qui reste la
  source de vérité — déplacé tel quel dans le popup) et menu "..." (Extraire
  le FEN, Importer un PGN, Bibliothèque, contrôles propres au mode actif,
  compteur de jetons, Coût API).
- `_updateBoardCompactState`/`boardCompactExpand` : bascule plateau complet/
  bande compacte sur défilement de page (`window.scrollY`) ou focus du champ
  de question (clavier), jamais pendant une lecture/preview de ligne du
  coach (plateau alors affiché en grand, point 6) ; un tap sur la bande
  remonte en haut de page et enlève le focus, ce qui la fait redevenir
  pleine via les mêmes conditions.
- `_updateActionBarState` : avant une partie pédagogique/ouverture (choix de
  camp), affiche les deux gros boutons "Jouer les Blancs/Noirs" + "Choisis
  ta couleur pour commencer" à la place de `#shared-mode-controls` ; pour
  partie libre/finales (pas de choix de camp, voir écarts ci-dessous), un
  message "Utilisez le menu ⋯ pour démarrer une partie." ; pendant une
  partie, `#shared-mode-controls` normal (3 boutons, sans titre ni texte de
  statut) ; en fin de partie, tout est masqué (le bandeau de résultat
  existant, `#game-over-banner`, suffit — voir écart ci-dessous).

### templates/index.html

- En-tête combiné (point 1) : `#mobile-mode-bar-slot` devient une rangée
  flex avec le sélecteur de mode existant (inchangé), `#game-model-pill`
  (pastille, texte initial rendu côté serveur) et `#game-menu-btn`
  (bouton "..."), plus les popups `#game-model-popup`/`#game-menu-dropdown`.
  `<header>` (sélecteur de modèle complet, compteur de jetons, lien Coût
  API) masqué en mode jeu mobile — son contenu utile est déplacé dans
  pastille/menu par JS, rien n'est dupliqué. `position: relative` ajouté à
  `#mobile-mode-bar-slot` (sans quoi les popups, `position: absolute; top:
  100%`, se positionnaient par rapport à un ancêtre bien plus haut que
  l'écran — bug repéré avec Playwright, cf. tests).
- `#board-sticky-wrap` restructuré : `#board-full-view` (matériel, plateau,
  nouvelle ligne d'état `#game-status-line`) et `#board-compact-strip`
  (bande ~56px, basculés par la classe `.board-compact`) ; `--bd-size`
  ramené à `min(36dvh, 400px, calc(100vw - 76px))` en mode jeu mobile
  (dvh pour la hauteur dynamique d'écran, point 10). La barre de navigation
  (`#review-controls`), la barre d'actions (`#shared-mode-controls`), les
  bandes avant-partie (`#mobile-pedagogic-start-slot`/
  `#mobile-opening-start-slot`/`#mobile-game-idle-msg`) et la barre d'onglets
  (`#game-tab-bar`) sont déplacées par JS COMME ENFANTS de
  `#board-sticky-wrap` (déjà collé en haut, issue #69) pour que "tout ce qui
  précède l'onglet actif" reste fixe — masquées ensemble (`!important`,
  au-dessus du `style.display` posé par JS) quand la bande compacte est
  active, conformément au point 5 ("le plateau complet ET les deux barres de
  boutons sont remplacés par une bande").
- Quatre onglets (`#game-tabs-column`, point 1) : `game-tab-panel-coach`
  reçoit le panneau du coach existant (`#coach-drawer-panel`, nouvel id) ;
  `game-tab-panel-lignes` reçoit `#game-coach-lines` ; `game-tab-panel-analyse`
  reçoit `#game-analysis-panel` (voir "Analyse" ci-dessous) ;
  `game-tab-panel-coups` reçoit `#historique` (table restylée par le CSS
  existant, aucune réécriture). Les messages automatiques "je joue ..."
  restent masqués sur mobile (issue #69 point 3, inchangé — la classe
  `.coach-bubble-auto-move` ne dépend pas du mode jeu).
- Contrôles propres à chaque mode (point 8) : `#free-extra-controls`/
  `#pedagogic-extra-controls`/`#opening-extra-controls`/
  `#finale-extra-controls` enveloppent chacun le contenu déjà existant de
  leur panneau (inchangé), déplacés dans `#game-menu-mode-extra` (menu
  "...") pour le mode actuellement affiché — **choix retenu : le menu
  "...", le plus simple à mettre en œuvre** (un seul emplacement suffit
  pour les quatre modes, contre un habillage variable en tête de l'onglet
  Coach). `#opening-start-buttons` (nouveau, mécanique identique à
  `#pedagogic-start-buttons`) sépare le choix de camp des contrôles
  secondaires (nom d'ouverture, suggestions).
- `#review-move-info-row`/`#fen-extract-status` masqués en mode jeu mobile
  (remplacés par `#game-status-line` et le menu) ; `#mobile-bottom-slot`
  (import PGN générique, navigation dans la collection, programme
  d'entraînement) masqué aussi — ces éléments restent dans la Bibliothèque,
  comme demandé (point 3), sans changement pour les autres modes mobiles.
- `#game-analysis-progress` : indicateur d'attente sans compteur pendant
  l'analyse (barre indéterminée, neutralisée par
  `prefers-reduced-motion: reduce`), classe posée/retirée par
  `game_analysis.js`.
- `html { overflow-anchor: none; }` (hors media query, cf. bug ci-dessous).

### static/board.js

- `updateGameStatusLine()` (nouveau) : "Coup N · coup" (même convention de
  numérotation que `review-move-info` existant — nombre de demi-coups joués,
  pas le numéro de coup plein de la maquette, pour rester cohérent avec le
  reste de l'appli) + matériel capturé condensé (pastille de la couleur en
  avance, "=" à égalité) + camp au trait (lu dans le FEN complet pour les
  modes interactifs, par parité pour la revue qui démarre toujours de la
  position standard). Appelée depuis `renderHistory()` (déjà invoquée après
  chaque coup par tous les modes et par la revue) — alimente à la fois
  `#game-status-line` et `#board-compact-strip`.
- `showGameOverBanner`/`hideGameOverBanner` : posent/retirent la classe
  `game-over-active` sur `<body>`, lue par le CSS du mode jeu mobile pour
  masquer la barre d'actions/le bandeau avant-partie quand le bandeau de
  résultat est affiché (point 4).

### static/controls.js

- Deux hooks minimaux (`if (typeof onGameUiRefresh === "function")
  onGameUiRefresh();`) en fin de `switchModeTab`/`updateSharedControlBar` —
  aucune dépendance dure vers `mobile_game.js` (no-op s'il n'est pas chargé).

### static/opening.js, static/pedagogic.js

- `placeOpeningStartButtonsForViewport()` (nouveau, mécanique identique à
  `placePedagogicStartButtonsForViewport()` existant) : déplace
  `#opening-start-buttons` vers `#mobile-opening-start-slot` sur mobile, tant
  qu'aucune partie d'ouverture n'est en cours ET que l'onglet "opening" est
  affiché. `placePedagogicStartButtonsForViewport()` reçoit la même
  condition supplémentaire sur `currentModeTab` (corrige au passage un
  travers pré-existant de l'issue #65 : ces boutons pouvaient apparaître
  au-dessus du plateau même en étant sur un autre onglet, tant qu'aucune
  partie pédagogique n'était active).

### static/game_coach_lines.js, static/game_analysis.js

- Points de nouveauté (point 7) : `_gameTabMarkNovelty("lignes")` après
  ajout d'une ligne (coach ou Stockfish) ; `_gameTabMarkNovelty("analyse")`
  après un rapport d'analyse ou une sélection de coups décisifs par le
  coach.
- `_setReviewControlsHiddenForLinePlayback()` (`game_coach_lines.js`) :
  pendant la lecture/preview d'une ligne, masque `#review-controls`
  uniquement si `body.mobile-game-active` (sans effet sur la bibliothèque/
  revue, dont le comportement mobile existant est inchangé) — la barre
  `#board-lines-command-bar` ("En lecture · Stop · Revenir à la partie")
  la remplace visuellement (point 6).
- `game_analysis.js` : classe `.show` posée/retirée sur
  `#game-analysis-progress` autour de l'appel `lancerAnalyse`.

### static/llm_model.js

- `_llmModelSetActive()` met aussi à jour `#game-model-pill` (premier mot du
  libellé actif, comme `.llm-model-compact` existant dans l'en-tête) — pur
  miroir d'affichage, `#llm-model-selector` reste la seule source de vérité
  et le seul point d'émission de `set_llm_model`.

## Bug de défilement diagnostiqué et corrigé (scroll anchoring)

- Constaté avec Playwright (émulation 390×750) : au passage en bande
  compacte pendant un défilement, la page revenait instantanément tout en
  haut. Cause : `#board-sticky-wrap` (`position: sticky`) rétrécit d'environ
  450-500px (plateau complet + deux barres de boutons + onglets remplacés
  par une bande ~56px) — Chromium/Firefox tentent de compenser ce
  rétrécissement par un ajustement automatique du défilement ("scroll
  anchoring", CSS Scroll Anchoring Module) qui, ici, dépasse la position de
  défilement courante et la ramène à 0. Deux correctifs complémentaires :
  `html { overflow-anchor: none; }` (l'ancre choisie par le navigateur peut
  être n'importe quel enfant de la page, la propriété ne s'hérite pas — une
  règle scopée à `#board-sticky-wrap` seul s'est révélée insuffisante lors
  des tests) et `body.mobile-game-active #app { min-height: 160dvh; }` (sans
  quoi, sur une page encore courte — ex. juste après le début d'une partie,
  onglet Coach vide — rétrécir en dessous de la hauteur de la fenêtre forçait
  quand même un défilement à 0, qui annulait aussitôt le passage en bande
  compacte : va-et-vient observé de façon non déterministe sur plusieurs
  lancements). `overflow-anchor` n'est pas supporté par Safari (l'ajoute
  depuis plusieurs versions de Chrome/Firefox, utilisés dans les tests) —
  limite documentée, résiduelle sur cette plateforme précise.

## Écarts avec la maquette (et raisons)

- **Modes ouverture et finales (point 8)** : contrôles propres (nom
  d'ouverture + suggestions ; sélection de la finale + camps inversés +
  démonstration) placés dans le menu "..." plutôt qu'en tête de l'onglet
  Coach — choix le plus simple (un seul emplacement, pas d'habillage
  variable selon le mode). Conséquence pour l'ouverture : si le nom de
  l'ouverture est vide, le message d'erreur ("Indiquez le nom d'une
  ouverture.") s'affiche dans `#opening-status`, à l'intérieur du menu —
  moins visible que s'il était sur l'écran principal, limite acceptée plutôt
  que dupliquer ce texte ailleurs.
- **Partie libre et travail de finales — pas de "choix de camp" avant-partie
  (point 4)** : la maquette montre deux gros boutons "Jouer les Blancs/
  Noirs" avant toute partie pédagogique, mais ce choix n'a pas de sens pour
  ces deux modes (partie libre : les deux camps sont joués librement, aucun
  `startFreeGame(camp)` ; finales : le camp est fixé par la position-type
  elle-même, "camps inversés" en tient lieu). Remplacé par un message
  "Utilisez le menu ⋯ pour démarrer une partie." — ces deux modes démarrent
  via leurs propres contrôles (désormais dans le menu "..."), pas par un
  choix de couleur.
- **Nouveau numéro de coup vs maquette** : "Coup N" reprend la convention
  déjà utilisée par `review-move-info` (nombre de demi-coups joués), pas le
  numéro de coup plein affiché par la maquette (ex. "Coup 6" pour 6.Nxe4
  dans la maquette correspondrait à "Coup 11" avec la convention de l'appli,
  11 demi-coups joués) — cohérence avec le reste de l'appli plutôt que deux
  numérotations différentes.
- **Bande compacte sans mini-plateau visuel (point 5)** : la maquette montre
  une miniature de l'échiquier dans la bande compacte. Implémenté comme une
  bande de texte (coup, matériel, camp au trait, chevron) sans miniature —
  dupliquer/déplacer le rendu réel du plateau (`#board`, avec ses
  gestionnaires de clic) dans un second conteneur mis à l'échelle aurait
  ajouté un risque de régression (coordonnées de clic, flèches SVG) pour un
  gain visuel jugé secondaire ; fonctionnellement équivalent (coup/matériel/
  trait toujours visibles), visuellement plus simple que la maquette.
- **Bandeau de fin de partie (point 4)** : resté à son emplacement existant
  (au-dessus du plateau, issue #31, déjà très visible et collé en haut) au
  lieu de remplacer la barre d'actions à l'endroit où elle se trouvait — la
  barre d'actions/le bandeau avant-partie sont simplement masqués pendant ce
  temps (classe `game-over-active`), plutôt que de déplacer un composant
  existant et bien établi.
- **Analyse (point 9)** : mécanisme conservé tel quel (l'analyse se lance
  toujours dans la revue de bibliothèque, `analyserPartieCourante()`/
  `reviewMoves`, inchangé) — l'onglet Analyse du mode jeu affiche
  directement `#game-analysis-panel` (bouton, indicateur d'attente, rapport)
  par déplacement du même élément, sans le dupliquer ni reconstruire un
  second chemin d'analyse. Intégrer l'analyse complètement dans l'écran de
  partie (sans passer par la bibliothèque) aurait demandé de dupliquer l'état
  `_gameAnalysisResults`/`reviewMoves` ou de le rendre accessible aux quatre
  modes de partie simultanément — jugé trop invasif pour cette issue.

## Tests

- Émulation Playwright (chromium headless, `is_mobile`/`has_touch`) à
  390×750 puis 360×640 : partie pédagogique en priorité (démarrage réel avec
  Stockfish — pas de clé API nécessaire pour l'adversaire —, un coup joué,
  historique/statut/matériel corrects), contrôle rapide en partie libre
  (message avant-partie), ouverture (boutons + menu), finales (message
  avant-partie + menu) ; onglets Coach/Lignes/Analyse/Coups (bascule,
  contenu réel après chargement d'une partie de 120 demi-coups depuis la
  bibliothèque — historique coloré par qualité de coup, panneau d'analyse
  fonctionnel avec Stockfish réel) ; plateau qui passe en bande compacte au
  défilement (`window.scrollY`) et qui revient (tap sur la bande) ; clavier
  simulé (focus du champ de question + réduction de la hauteur de fenêtre
  d'environ 300px, 750→450) ; Play/Stop/Revenir à la partie non testé avec
  un vrai appel API (voir ci-dessous) mais le câblage
  `_setReviewControlsHiddenForLinePlayback`/bande visible en lecture vérifié
  par lecture de code ; points de nouveauté (appel direct de
  `_gameTabMarkNovelty`, apparition/disparition vérifiées) ; pastille de
  modèle et menu "..." (ouverture, positionnement, Extraire le FEN,
  Bibliothèque) ; fin de partie par abandon (bandeau + barre d'actions
  masquée) — **fin par mat non déclenchée dans les tests** (aucun moyen
  pratique de forcer un mat contre Stockfish dans le temps imparti ; le
  chemin de code est strictement identique à l'abandon,
  `showGameOverBanner`/`hideGameOverBanner`, seul le message diffère) ;
  aucun débordement horizontal mesuré à 360×640 (`scrollWidth -
  clientWidth === 0`) ; exercice/bibliothèque/éditeur et rendu à 1440px
  vérifiés inchangés (captures identiques à avant l'issue, aucune classe
  `mobile-game-active` posée). Comparaison visuelle qualitative avec les
  captures `design/partie_mobile/png/` : disposition proche (en-tête
  combiné, plateau fixe, ligne d'état, nav compacte, barre d'actions,
  onglets), écarts listés ci-dessus.
- Aucune `ANTHROPIC_API_KEY` disponible dans l'environnement de cette
  session (`config.LLM_API_KEY` vide) : les appels au coach (commentaire
  après un coup, sélection de coups décisifs, chat libre) n'ont pas pu être
  exercés avec un vrai modèle — testés en confirmant l'absence d'erreur JS
  et le message de repli attendu ("Clé API Claude manquante"/"Sélection du
  coach indisponible"). Stockfish (adversaire pédagogique/ouverture/finales,
  analyse de partie) a en revanche été exercé réellement (moteur système
  détecté, aucune clé requise).
- Serveur de test lancé sur le port 5051 (le port 5000 sert l'instance
  réelle d'Alain, non touchée) via le venv `~/ChessCoach/venv` ; arrêté en
  fin de session.
- `py_compile` sur les fichiers Python existants : OK (aucun changé par
  cette issue). Vérification de la fermeture des balises de
  `templates/index.html` (parseur HTML tolérant) : aucune balise non
  fermée/mal imbriquée détectée.

## Limites connues

- `#fen-extract-status` (résultat visuel d'"Extraire le FEN") reste masqué
  en mode jeu mobile — la copie presse-papiers fonctionne, mais aucun retour
  visuel n'est affiché dans ce mode (regression mineure par rapport au
  grand écran/aux autres modes mobiles, où ce texte reste visible).
- Le nom de l'ouverture vide affiche son message d'erreur dans le menu
  "..." plutôt que sur l'écran principal (cf. écarts ci-dessus).
- La bande compacte du plateau est un résumé textuel, pas une miniature du
  plateau réel (cf. écarts ci-dessus).
- `overflow-anchor: none` n'a pas d'effet sur Safari — le bug de
  défilement corrigé ici pourrait resurgir sur cette plateforme (non testée,
  hors du navigateur de test disponible dans ce worktree).
- Fin de partie par mat non testée en conditions réelles (voir section
  Tests) — seul le chemin par abandon, identique en code, a été exercé.

# Changelog — Issue #69

## Mobile (modes de partie) : plateau toujours visible, panneau réorganisé et lecture des lignes sans redescendre

- Contexte : sur écran étroit, tous les éléments des modes de partie étaient
  empilés dans une seule colonne (issue #50/#63/#65/#68) — plus le panneau du
  coach/les lignes/l'analyse est long, plus le plateau est loin. Constat
  d'Alain sur GSM en partie pédagogique : pour poser une question au coach ou
  lire une ligne avec Play, il fallait descendre loin, puis remonter pour
  revoir le plateau. Correctif intermédiaire volontairement simple — une
  nouvelle maquette de l'écran de partie est demandée en parallèle à Claude
  Design (issue ultérieure). Uniquement sur mobile (<900px) ; disposition
  grand écran strictement inchangée (vérifiée pixel pour pixel à 1440px,
  voir rapport de clôture).

### templates/index.html

- Nouveau `#board-sticky-wrap` : regroupe le bandeau de fin de partie, le
  matériel capturé, le plateau (avec ses lettres/chiffres de coordonnées) et
  la nouvelle barre de lecture des lignes du coach. Sur mobile, ce nœud est
  déplacé par JS comme enfant direct de `#app` (et non laissé imbriqué dans
  `#board-column`, trop court pour qu'un `position: sticky` y reste collé
  jusqu'au bas d'une page mobile bien plus longue) — restauré à sa place
  d'origine dans `#board-column` sur grand écran. `--bd-size` recalculé
  (`min(30vh, 420px, calc(100vw - 76px))`) pour que le plateau tienne dans
  environ 42% de la hauteur d'écran en partie active.
- Nouveau `#board-lines-command-bar` : petite barre Stop/"Revenir à la
  partie" affichée dans la zone collée, juste sous le plateau, pendant et
  après la lecture d'une ligne du tableau "Lignes du coach" — remplie par
  `_updateBoardLinesCommandBar()` (game_coach_lines.js).
- Rangée de navigation (`#review-controls`) rendue compacte sur une seule
  ligne sur mobile (Précédent/Suivant/Retourner/Meilleur coup) ; "Extraire le
  FEN" part dans un nouveau menu "..." (`.review-more-menu`, piloté par
  `toggleReviewMoreMenu()`/`closeReviewMoreMenu()`, controls.js) — même
  `extraireFen()`, aucune logique dupliquée.
- Nouveaux points d'ancrage pour ce qui ne sert pas pendant la partie : le
  bloc PGN unique (`#single-pgn-import-block`), le bloc de navigation dans la
  collection PGN (`#pgn-lib-browse-block` : sélecteur de collection,
  recherche, filtre, liste des parties, import dans la collection) et le
  panneau "Programme d'entraînement" (`#training-program-panel`) sont
  déplacés sur mobile vers `#mobile-bottom-slot` (après l'historique des
  coups) ; le panneau "Analyser cette partie" (`#game-analysis-panel`) est
  déplacé vers `#mobile-analysis-slot`, juste après le tableau "Lignes du
  coach" dans le panneau du coach. Tous ces slots sont `display: contents`
  et sans effet sur grand écran.
- Le sélecteur de mode (`#mobile-mode-bar-slot`) n'est plus collé en haut de
  l'écran (`position: sticky` retirée) — il défile désormais normalement,
  le plateau reprenant ce rôle.
- Messages automatiques de coup joué ("Partie pédagogique — je joue d4" et
  équivalents ouverture/finales) masqués dans le chat sur mobile via une
  nouvelle classe `.coach-bubble-auto-move` — purement présentationnel,
  n'affecte ni `_coachHistory` ni les données envoyées à l'API.

### static/controls.js

- `_registerMobileRelocatable(id, slotId)` / `_placeMobileRelocatablesForViewport(isMobile)` :
  mécanique générique de déplacement de nœud DOM entre son emplacement
  d'origine et un slot mobile dédié (même principe que
  `placeModeTabBarForViewport`, déjà existant depuis l'issue #63), réutilisée
  pour les 4 blocs cités ci-dessus plutôt que de dupliquer cette logique une
  par une.
- `_updateStickyScrollPadding()` + `ResizeObserver` sur `#board-sticky-wrap` :
  synchronise `scroll-padding-top` (`<html>`) sur la hauteur RÉELLEMENT
  rendue du plateau collé, qui varie selon le bandeau de fin de partie, les
  boutons de démarrage rapide du mode pédagogique ou la barre de lecture des
  lignes — sans ça, `scrollIntoView` (rapport d'analyse, réponse du coach à
  une question posée) plaçait sa cible partiellement sous le plateau collé.
- `toggleReviewMoreMenu()`/`closeReviewMoreMenu()` + fermeture au clic
  ailleurs (même principe que le menu déroulant du sélecteur de mode).

### static/game_coach_lines.js

- `_updateBoardLinesCommandBar()` : pilote `#board-lines-command-bar` à
  partir de l'état déjà existant (`gameCoachLinesPlayingIdx`,
  `gameCoachLinesPreviewActive`) — appelle directement `gameLineToggle()`/
  `gameLinesRestore()` (aucune logique de lecture dupliquée), appelée à
  chaque `renderGameCoachLinesTable()`, donc à chaque changement d'état.

### static/board.js

- `_coachRenderBubble(role, text, allowPageScroll, extraClass)` : nouveau
  4e paramètre optionnel pour ajouter une classe CSS à la bulle
  (`coach-bubble-auto-move`), sans toucher au comportement existant des
  3 premiers paramètres.

### static/pedagogic.js, static/opening.js, static/finales.js

- Les 3 messages "je joue ..." passent `"coach-bubble-auto-move"` à
  `_coachRenderBubble`. Le message équivalent du mode exercice
  (`static/exercise.js`) n'est PAS concerné : il alimente aussi
  `_coachHistory` (continuité du chat libre) et reste affiché partout, comme
  demandé (mode exercice hors périmètre de cette issue).

### Bugs corrigés en cours de vérification (jamais visibles en usage normal, détectés par les tests ci-dessous)

- `#review-controls` (flex item d'un parent `flex-direction: column`)
  débordait de 6px à 360px de large — `min-width: auto` implicite des
  éléments flex, corrigé avec `min-width: 0`.
- `#mobile-bottom-slot` étant `display: contents`, l'`order` CSS posé
  dessus n'avait aucun effet (un élément `display: contents` disparaît de
  l'arbre de boîtes) — corrigé en posant `order: 5` directement sur les 3
  éléments déplacés (`#single-pgn-import-block`, `#pgn-lib-browse-block`,
  `#training-program-panel`), qui sans ce correctif s'affichaient AVANT le
  plateau plutôt qu'après l'historique.
- `#training-program-panel` (classe `.panel`, `padding: 14px 16px`)
  débordait de 32px avec `width: 100%` en `box-sizing: content-box` — ajout
  de `box-sizing: border-box` (même motif que `#shared-mode-controls`,
  déjà présent dans le gabarit).

## Tests effectués

Aucun serveur SocketIO disponible dans ce worktree (`flask_socketio` absent
de l'environnement Python accessible, `RESEAU: non` dans l'en-tête de
l'issue — aucune tentative d'installation) : impossible de faire un vrai
appel à l'API Claude ou à Stockfish. Tests faits avec Chromium/Playwright
(déjà en cache local) sur un petit serveur Flask temporaire (jamais commité,
supprimé en fin de tâche) qui rend `templates/index.html` avec un contexte
mocké minimal — vérifie donc la mise en page/le comportement JS réels, pas
les réponses du coach.

- 390×844 et 360×740 (émulation tactile Playwright) : plateau collé visible
  du haut jusqu'au bas de la page (vérifié en forçant un défilement jusqu'à
  `document.body.scrollHeight`) ; aucun débordement horizontal mesuré
  (`scrollWidth <= clientWidth`) sur les deux tailles, y compris pendant/
  après correctifs ; rangée de navigation tient sur une seule ligne sans
  scroll interne sur les deux tailles.
- Hauteur du plateau collé : ~46-48% de l'écran à l'état "repos" (avec les
  boutons "Jouer les Blancs/Noirs" du mode pédagogique, qui s'affichent tant
  qu'aucune partie n'est en cours, issue #65 point 6 — non modifié par cette
  issue) ; ~40% en partie pédagogique active (sans ces boutons) — proche de
  la cible "environ 42%" dans le cas d'usage principal signalé par Alain
  (poser une question/lire une ligne PENDANT une partie).
- Partie pédagogique simulée directement en JS (pas de partie réellement
  démarrée via socket, cf. limite ci-dessus) : messages automatiques
  "je joue ..." bien masqués dans le chat, réponse du coach normalement
  visible.
- Tableau "Lignes du coach" simulé (ligne factice) : barre de commande
  masquée par défaut, affiche "Stop" pendant la lecture (clic réel ->
  `gameLineToggle`), puis "Revenir à la partie" après arrêt (clic réel ->
  `gameLinesRestore`, plateau redessiné sans exception).
- Partie libre RÉELLE (pas de simulation d'état — `startFreeGame()`/
  `onFreePlayBoardClick` sont purement client, aucun aller-retour SocketIO
  nécessaire pour un coup manuel) : deux coups joués par de vrais événements
  `click` (e2-e4, d7-d5) sans que `window.scrollY` ne bouge — confirmé aussi
  sur le code d'avant cette issue (même comportement, pas de régression).
  Note méthodologique : `page.tap()` de Playwright fait lui-même défiler la
  page vers `sq-e2` avant de taper dessus (heuristique d'"actionabilité" de
  l'outil sur un élément `position: sticky`, pas un comportement du site) —
  écarté en dispatchant directement l'événement `click`, qui confirme
  l'absence de saut réel.
- Changement de tous les onglets (bibliothèque/libre/pédagogique/ouverture/
  finales/exercice/éditeur) sans exception JS.
- `scroll-padding-top` dynamique : rapport d'analyse simulé, son haut reste
  sous le plateau collé après `_scrollVersPanneauAnalyse()` (marge
  recalculée par `ResizeObserver`, pas seulement la valeur CSS statique de
  secours).
- Rendu à 1440px : comparaison pixel par pixel (`git stash`/capture d'écran
  avant-après avec Playwright) de `#board-column`/`#coach-column`/
  `#mode-tabs-column`/`#historique-column`/`#board`/`#review-controls`/
  `#shared-mode-controls` — coordonnées strictement identiques, captures
  d'écran identiques au pixel près (`ImageChops.difference` : bbox vide).

## Limites et points pour la future maquette (Claude Design)

- Hauteur du plateau collé à l'état "repos" (~46-48% au lieu de ~42%) tant
  que les boutons "Jouer les Blancs/Noirs" du mode pédagogique (issue #65
  point 6) s'affichent au-dessus — n'a pas semblé justifier de réduire la
  taille du plateau EN PARTIE ACTIVE (le cas d'usage réel signalé par Alain)
  pour ce cas transitoire ; la future maquette pourra reconsidérer ce
  placement.
- Sur le plus petit écran testé (360px), la rangée de navigation compacte
  tient tout juste sur une seule ligne (police 0.72rem, padding réduit à
  6px 5px) — resterait fragile si un futur bouton s'ajoutait à cette rangée
  sans revoir la maquette.
- Les contrôles spécifiques à chaque mode (démarrer une partie d'ouverture,
  choisir une finale, etc., dans `#mode-tabs-column`) n'ont pas été
  réordonnés individuellement — seuls le panneau d'analyse et les 4 blocs de
  navigation/collection listés dans l'issue ont été déplacés ; le reste de
  `#mode-tabs-column` garde sa position (après le chat/lignes/analyse,
  avant l'historique), un compromis pour rester un correctif simple.
- Aucun vrai appel API/Stockfish testé (contrainte de l'environnement, cf.
  section Tests) — comportement du chat/de l'analyse/des lignes vérifié en
  simulant l'état JS, pas en conditions réelles de bout en bout.

# Changelog — Issue #68

## Lignes du coach rejouables sur l'échiquier dans les modes de partie et en revue

- Contexte : le mode exercice (issue #58) possède un tableau "Lignes du
  coach" qui extrait les lignes de coups citées par le coach et les rejoue
  sur l'échiquier. Ce tableau n'existait que dans ce mode — en usage réel en
  partie pédagogique, Alain a demandé au coach ce qu'il aurait dû jouer au
  coup 8, mais n'a eu aucun moyen de voir cette ligne sur l'échiquier.
  `static/coach_lines.js` avait été conçu réutilisable depuis le départ.

### static/coach_lines.js

- Nouvelle fonction `extractCoachGameLines(text)` : étend
  `extractCoachMoveLines` (inchangée, toujours utilisée telle quelle par le
  mode exercice) en associant chaque ligne trouvée à une éventuelle mention
  de départ "depuis le coup N... (Camp)" / "depuis le coup N (Camp)" qui la
  précède immédiatement dans le texte (`_COACH_LINE_ANCHOR_RE`). Une ligne
  sans mention reconnaissable reste "sans ancre" — jamais de déduction.

### static/game_coach_lines.js (nouveau)

- Tableau "Lignes du coach" mode-agnostique pour les modes de partie (libre,
  pédagogique, ouverture, finales) et la revue de bibliothèque, pendant du
  tableau du mode exercice mais réutilisant directement
  `resolveCoachLineStart`/`playCoachLineSequence`/`extractCoachGameLines`
  (coach_lines.js) plutôt que de les redupliquer.
- `_gameLinesFenForAnchor`/`_gameLinesReplayFen` : résolvent une mention de
  départ ou la position actuelle PAR REJEU (jamais par arithmétique de
  numéro de coup), en comparant à chaque demi-coup le numéro/camp affiché
  par chess.js lui-même (fullmove number + turn du FEN courant) — reste
  correct même pour une partie démarrant à un demi-coup impair (SetUp/FEN
  personnalisé, ex. une finale, ou la partie de test de l'issue).
- `_gameLinesCandidates` : essaie la position juste avant le coup visé par
  la mention (si présente et résoluble), PUIS la position actuelle, jamais
  d'autre repli — `resolveCoachLineStart` retourne "ligne non jouable" (pas
  de bouton Play) si aucun des deux candidats ne rend la ligne légale.
  Aucune ligne de moins de deux coups (hérité de coach_lines.js).
  `gameCoachLinesOnStockfishLine` : bonus "Ligne de Stockfish" en tête de
  tableau quand le serveur en transmet une (voir app.py).
- La lecture (`gameLineToggle`) ne fait QUE redessiner le plateau
  (`renderBoard`) à partir de positions déjà résolues — aucun appel à
  `game.move()` sur l'instance réelle du mode, aucun `socket.emit` : Stop/
  "Revenir à la partie" n'ont donc jamais besoin de restaurer autre chose
  que l'affichage (position, historique, bandeau de fin compris, puisque
  rien d'autre n'a été modifié entre-temps) — `gameLinesRestore` se contente
  de rappeler la fonction de rendu réelle du mode actif (ou `renderReview`).
  `gameCoachLinesPreviewActive` bloque les clics du plateau pendant la
  prévisualisation (guardé dans les 4 handlers de clic, voir plus bas) et la
  navigation de revue (`reviewPrev`/`reviewNext`/`reviewGoTo`, board.js).

### static/board.js

- `coachNewSegment` (point de coupure déjà existant, issue #64) appelle
  aussi `gameCoachLinesReset()` : le tableau est vidé aux mêmes moments que
  l'isolation du chat par partie (nouvelle partie, ou autre partie chargée
  en revue) — un seul point d'entrée pour tous les modes.
  Les handlers `coach_response`/`coach_on_demand_response` alimentent aussi
  ce tableau (`gameCoachLinesOnCoachText`), et `coach_response` transmet la
  "Ligne de Stockfish" bonus si `data.stockfish_line` est présent.
- `reviewPrev`/`reviewNext`/`reviewGoTo` : no-op pendant une prévisualisation
  de ligne du coach en revue de bibliothèque (`gameCoachLinesPreviewActive`).
- `parsePgn` : appelle désormais `setActiveMode(null)` après
  `ensureModeSwitchClean("library")`. Correction nécessaire découverte en
  cours d'implémentation — seuls `abandonExerciseGame`/
  `abandonPositionEditor` remettaient `activeMode` à `null`, jamais les
  modes de partie (libre/pédagogique/ouverture/finales) : charger une partie
  en revue juste après en avoir joué une laissait `activeMode` pointer sur
  l'ancien mode, donc `coachBuildContext()`/`gameCoachLinesOnCoachText`
  continuaient de lire l'ancienne partie interactive au lieu de celle qu'on
  vient de charger (et les boutons Précédent/Suivant/Meilleur coup
  restaient grisés, `updateReviewControlsEnabled`). N'affecte que le chemin
  "charger une partie en revue" — inchangé pour la fin de partie/l'abandon
  d'un mode interactif, qui reste affiché tel quel comme avant.

### static/controls.js, static/free_play.js, static/pedagogic.js, static/opening.js, static/finales.js

- `setActiveMode` : masque immédiatement le tableau au passage vers
  exercice/éditeur (`renderGameCoachLinesTable`).
- `onFreePlayBoardClick`/`onPedagogicBoardClick`/`onOpeningBoardClick`/
  `onFinaleBoardClick` : bloqués pendant une prévisualisation de ligne du
  coach (`gameCoachLinesPreviewActive`) — empêche tout coup d'Alain, donc
  toute réponse de Stockfish déclenchée par la lecture.
- `pedagogic_comment`/`opening_comment`/`finale_comment` (commentaire
  automatique "Commenter chaque coup") alimentent aussi le tableau — ces
  événements ne passent pas par les handlers génériques de board.js.

### templates/index.html

- Nouveau bloc `#game-coach-lines` sous le chat du coach (`.coach-drawer`),
  visible dans tous les modes sauf exercice/éditeur — mêmes classes CSS que
  le tableau du mode exercice (`.coach-line-*`, déjà adaptées mobile depuis
  les issues #63/#65), donc aucun CSS nouveau nécessaire. Sélecteur de
  vitesse (0,5 s / 1 s, 1 s par défaut) et bouton "Revenir à la partie".
  Script `game_coach_lines.js` chargé après `coach_lines.js`.

### llm_coach.py

- Nouveau `_GAME_LINES_ADDENDUM` : demande au coach, pour tous les modes
  hors exercice, le format fixe de mention de départ ("depuis le coup N...
  (Camp)") pour une ligne alternative qui ne part pas de la position
  actuelle — jamais imposé en mode exercice (déjà couvert par
  `_EXERCISE_SYSTEM_ADDENDUM`, une position isolée sans historique).
  `get_coach_response` : ajouté indépendamment du garde-fou
  anti-invention existant (verdict/PV Stockfish), qui reste conditionnel
  comme avant.

### app.py

- `_enrich_context_with_game_facts` retourne désormais `(context,
  stockfish_line)` — `stockfish_line` reprend `fen_avant`/`ligne_principale`
  (déjà calculés par `_stockfish_check_key_moment`, aucun appel moteur
  supplémentaire) du premier moment vérifié qui en a une, ou `None` sinon.
  `on_coach_ask` transmet `stockfish_line` dans la réponse `coach_response`
  sous la clé du même nom, omise si absente.

### Tests effectués

- Logique pure (extraction/ancrage/résolution/lecture), Node.js, en dehors
  du périmètre applicatif (aucune dépendance à Flask/DATA_DIR) : partie de
  test de l'issue (SetUp/FEN personnalisé, abandon, ligne "depuis le coup
  8... (Noirs)" avec la ligne exacte de l'énoncé) → résolue, 6 coups, FEN de
  départ vérifiée ; ligne sans mention légale depuis la position actuelle ;
  ligne illégale (ni depuis l'ancre ni depuis la position actuelle) → "ligne
  non jouable" ; faux positif "c3-d3-e3" → aucune ligne extraite ; mode de
  partie "live" (pédagogique) avec `header().FEN` personnalisé ; bonus
  "Ligne de Stockfish" ; Stop en cours de lecture puis "Revenir à la
  partie" → position/historique de la partie réelle inchangés. 22
  assertions, toutes passées.
- Prompt système (`llm_coach.get_coach_response`), Python, `_call_claude`
  monkeypatché (aucun appel réseau, `coach_log_path`/`usage_path=None` pour
  ne toucher aucun fichier hors du périmètre) : `_GAME_LINES_ADDENDUM`
  présent pour partie libre/pédagogique (avec verdict)/revue de
  bibliothèque, absent en mode exercice (remplacé par
  `_EXERCISE_SYSTEM_ADDENDUM`) ; garde-fou anti-invention toujours combiné
  quand un verdict/une PV est transmis. 8 assertions, toutes passées.
- Bout en bout en navigateur réel (Playwright + Chromium système, un
  serveur Flask minimal servant uniquement `templates/`/`static/` de ce
  worktree — sans jamais importer `app.py` ni `config.py`, donc sans
  toucher `~/ChessCoach/data`, hors périmètre) : scénario de l'issue simulé
  en partie libre (position personnalisée, 16 coups rejoués, bandeau
  d'abandon affiché) puis réponse du coach simulée avec la ligne exacte de
  l'énoncé → tableau affiché avec le bon libellé d'ancre ; clic Play → clics
  du plateau bloqués (vérifié directement) ; en cours de lecture le bouton
  affiche "Stop" ; Stop puis "Revenir à la partie" → position/historique/
  bandeau de fin identiques à avant la lecture (FEN comparée strictement
  égale). Vue mobile 390×844 : tableau lisible, bouton Play mesuré à
  61×46 px (largement au-dessus du minimum tactile recommandé de 44×44).
  Aucune vraie clé API Claude disponible dans ce worktree (pas de `.env`) —
  impossible de vérifier que le VRAI modèle Claude respecte le format de
  mention demandé ; seule la partie client (extraction/résolution/lecture)
  et l'assemblage du system prompt ont pu être vérifiés directement.

### Limites connues

- Le format de mention de départ n'a pu être vérifié qu'en simulant la
  réponse du coach (aucune clé API dans ce worktree) — un vrai appel
  pourrait s'écarter du format malgré la consigne, comme pour toute
  consigne de prompt.
- La "Ligne de Stockfish" bonus (point 5) ne peut apparaître que via le chat
  libre (`coach_ask`), seul point où `_enrich_context_with_game_facts` est
  appelé côté serveur — jamais via le commentaire automatique après un coup
  (`pedagogic_comment`/`opening_comment`/`finale_comment`), qui ne calcule
  pas ce bloc de faits. Elle n'apparaît pas non plus en revue de
  bibliothèque : `camp_alain` n'y est jamais transmis au serveur
  (limitation déjà documentée pour l'issue #55, volontairement pas étendue
  ici).
- Non géré (limite assumée, pas de garde ajoutée) : si une réponse de
  Stockfish était déjà en vol au moment où Alain clique Play (ex. il vient
  de jouer un coup en partie pédagogique, Stockfish n'a pas encore répondu),
  son arrivée continue de redessiner le plateau avec sa propre position dès
  qu'elle arrive (`pedagogic_stockfish_move` et équivalents ne testent pas
  `gameCoachLinesPreviewActive`) — cela interromprait visuellement
  l'aperçu en cours (sans jamais le corrompre : l'état réel de la partie
  reste correct, et la lecture de la ligne reprend son propre affichage au
  coup suivant de son minuteur). N'affecte que cette fenêtre de course très
  étroite (coup d'Alain suivi immédiatement d'un clic Play avant la
  réponse) ; les clics/coups d'Alain eux-mêmes restent bloqués pendant tout
  l'aperçu, comme demandé.

# Changelog — Issue #67

## Mobile : ne plus faire défiler la page vers le chat à chaque coup joué

- Contexte : suite à l'issue #65 (suppression de la zone de défilement
  interne du chat sur mobile), la fonction commune de révélation des
  messages du chat coach s'appuie désormais sur le défilement de la PAGE.
  Or chaque coup joué en partie pédagogique ajoute un message automatique
  d'Alain dans le chat ("Partie pédagogique — je joue ..."), qui déclenchait
  ce défilement — le plateau sortait de l'écran après chaque coup. Constaté
  par Alain sur capture d'écran ; les autres modes de partie (libre,
  ouverture, finales, exercice) présentaient le même défaut pour leurs
  propres messages automatiques (coup joué, commentaire "Commenter chaque
  coup", info, erreur).

### static/board.js

- `_coachScrollReveal(history, el, toStart, allowPageScroll)` : nouveau
  4ᵉ paramètre. La branche "défilement interne" (bureau, ou mobile si un
  CSS venait à réintroduire un `overflow-y:auto`) est strictement
  inchangée — elle défile toujours, quel que soit `allowPageScroll`. La
  branche "page qui défile" (mobile, cas normal depuis l'issue #65) ne
  déclenche `scrollIntoView` que si `allowPageScroll` est vrai.
- `_coachRenderBubble(role, text, allowPageScroll)` : nouveau 3ᵉ paramètre,
  transmis tel quel à `_coachScrollReveal`. Absent (donc `undefined`/faux)
  par défaut sur tous les appels existants — comportement mobile "ne
  défile pas" par défaut.
- Seuls les deux cas où Alain attend activement une réponse passent
  `allowPageScroll = true` explicitement : la réponse du coach à une
  question tapée dans le chat (`coach_response`) et la réponse au bouton
  "Demander l'avis du coach" (`coach_on_demand_response`).
- `_coachRenderCreditInsuffisant` et `coachNewSegment` (séparateur
  "Nouvelle partie") continuent d'appeler `_coachScrollReveal` sans ce
  4ᵉ argument : plus de défilement de page sur mobile pour ces messages
  d'erreur/séparateur, comportement bureau inchangé.

### static/exercise.js

- Verdict d'exercice (`exercise_comment`) : seul appel hors board.js à
  passer `allowPageScroll = true` — comportement voulu par la maquette
  (le début du verdict doit se placer en haut de l'écran).

### Cas qui ne défilent plus la page sur mobile (comportement bureau inchangé)

- Messages automatiques "je joue ..." (pédagogique, ouverture, finales,
  exercice) — `_coachRenderBubble("user", ...)` sans 3ᵉ argument.
- Commentaires "Commenter chaque coup" (`pedagogic_comment`,
  `finale_comment`) et commentaires équivalents d'ouverture
  (`opening_comment`).
- Messages informatifs statiques ("Finale chargée", "Ouverture chargée",
  "Démonstration chargée").
- Messages d'erreur (`_coachRenderCreditInsuffisant`, `no_api_key`, etc.).
- Séparateur "Nouvelle partie"/"Nouvel exercice" (`coachNewSegment`).
- Message d'Alain lui-même envoyé depuis le champ du chat (`coachSend`,
  `_coachRenderBubble("user", question)`) — seule sa réponse déclenche le
  défilement, pas l'envoi de la question.

### Tests effectués

- Lecture complète du code (pas d'environnement mobile réel/émulateur
  tactile disponible dans ce worktree non-interactif ; aucun appel API
  Claude réel effectué — pas de clé/contexte d'exécution serveur monté
  dans cette session). Vérification statique de tous les appelants de
  `_coachRenderBubble`/`_coachScrollReveal` dans board.js, pedagogic.js,
  finales.js, opening.js, exercise.js, free_play.js, llm_model.js :
  chaque site a été classé dans la bonne catégorie (défile / ne défile
  pas) et corrigé en conséquence. `node -c` sur les deux fichiers modifiés
  (syntaxe JS valide) — pas de suite de tests automatisés pour ce module
  front-end dans le dépôt.
- Limite assumée : aucune vérification visuelle réelle (émulation
  tactile 390×844, clic sur les coups, capture d'écran) n'a été faite —
  seule une relecture exhaustive du flux de code garantit le comportement
  attendu. À confirmer par Alain en conditions réelles sur mobile.

# Changelog — Issue #66

## Bloc de faits : décrire mécaniquement chaque coup cité et signaler les pions perdus sans reprise

- Contexte : test réel sur une partie pédagogique (Haiku, Alain Noirs,
  abandonnée après 9.Nxe5). Le bloc de faits (matériel, moment le plus
  grave, meilleur coup Stockfish, perte estimée) était exact, mais la
  réponse du coach attribuait le coup Nxg4 au mauvais cavalier (b6 au lieu
  de f6), disait que Bxe5 capturait un cavalier au lieu d'un pion, et
  plaçait le cavalier blanc "en e5" au lieu de g4 pour 7...h5 — le modèle
  reconstituait de tête, à partir de la seule notation SAN, quelle pièce
  joue et où sont les autres, et se trompait (même famille que "dame en
  b5"/confusion de camp, issues #25/#44/#55). Avec Sonnet sur la même
  partie, aucune erreur de pièce/case, mais 8...Nxg4 était présenté comme
  "pris gratuitement" alors que le cavalier g4 était défendu par le fou e2
  et repris dans la ligne principale Stockfish elle-même. Les chiffres de
  la vérification Stockfish n'étaient de plus pas stables d'un appel à
  l'autre pour la même partie.

### game_facts.py — description mécanique des coups (points 1 et 2)

- Nouvelles fonctions `describe_move_mechanically(fen_avant, coup,
  camp_alain="")` et `describe_pv_mechanically(fen_avant, pv_text,
  camp_alain="", max_plies=2)` (cœur commun `_decrit_coup_mecanique`) :
  calculent avec python-chess, jamais deviné, pour UN coup (SAN ou UCI)
  légal sur une position donnée — quelle pièce joue (type et case de
  départ), case d'arrivée, capture éventuelle (type/case, défendue ou non
  — via un nouveau `_premier_coup_vers` — et solde net après reprise,
  réutilise `_solde_net_apres_capture` de l'issue #57), échec/mat, et
  quelles pièces adverses (hors roi, déjà couvert par l'échec) ce coup
  attaque désormais (`_pieces_attaquees_apres`, `board.attacks`). Nouveaux
  helpers `_couleur_accordee` (accord "blanc"/"blanche") et
  `_nom_piece_capturee` (article indéfini pour un pion générique, défini
  pour les autres pièces).
- `find_stockfish_check_targets` : chaque cible porte désormais
  `uci_reponse_suivante` (le coup réellement joué ensuite dans la partie,
  nécessairement celui de l'adversaire) — nécessite `idx`/`uci` ajoutés à
  chaque entrée de l'historique interne.
- `build_game_facts_text`, section "Vérification Stockfish ciblée" :
  chaque cible reçoit maintenant la position juste avant le coup joué
  (pièce par pièce, comme la position actuelle — point 2), puis la
  description mécanique du coup joué, du meilleur coup, de la réponse
  anticipée par la ligne principale (2e pli, le 1er étant déjà celui du
  meilleur coup) et de la réponse réellement jouée ensuite dans la partie.

### game_facts.py — pions perdus sans reprise (point 4)

- Nouvelle rubrique "Pions perdus sans reprise" dans `build_game_facts_text`
  : capture d'UN pion (variation exactement 1 point, donc sous le seuil des
  "moments clés" de 2 points), sans aucune reprise légale immédiate — les
  `_MAX_PIONS_PERDUS_SANS_REPRISE` (3) plus récents de la partie seulement.
  Sur la partie de test, 6.Nxe5 (pion e5 laissé sans défense par 5...Nb6)
  y apparaît désormais, alors qu'il restait invisible du bloc jusqu'ici.

### app.py — même principe pour "Analyser cette partie" (point 5)

- `_prepare_flagged_moves_for_coach` (appel en lot,
  `get_move_explanations`) et `on_analyse_expliquer_coup` (explication à la
  demande d'un coup unique) ajoutent chacun `description_mecanique`/
  `meilleur_coup_description` (resp. `coup_description_mecanique`/
  `meilleur_coup_description_mecanique` dans le contexte) via
  `game_facts.describe_move_mechanically` — même risque que le chat coach,
  même correctif.

### app.py — reproductibilité de la vérification Stockfish (point 6)

- `STOCKFISH_CHECK_TIME_PAR_POSITION` (limite de temps, movetime) remplacée
  par `STOCKFISH_CHECK_DEPTH = 14` (profondeur fixe) dans
  `_stockfish_eval_cible` : une limite de temps ne garantit pas la
  profondeur réellement atteinte par Stockfish (donc pas le résultat) d'un
  appel à l'autre sur EXACTEMENT la même position, ce qui a fait constater
  des chiffres de perte et des meilleurs coups différents en usage réel.
  `STOCKFISH_CHECK_BUDGET_TOTAL` (garde globale en temps, best-effort)
  inchangée. Le cache par partie `_stockfish_check_cache` (clé
  `(camp_alain, pgn)`) existait déjà depuis l'issue #57 ; combiné à la
  profondeur fixe, deux questions successives sur la même partie reçoivent
  désormais exactement les mêmes chiffres, y compris après un redémarrage
  du process qui aurait vidé le cache (nouveau calcul à la même profondeur
  ⇒ même résultat).

### llm_coach.py — renforcement du prompt (point 3)

- `_GAME_FACTS_ADDENDUM` (chat coach) : règle absolue ajoutée — pour toute
  pièce ou case liée à un coup cité par la "Vérification Stockfish ciblée",
  ne reprendre QUE la description mécanique calculée fournie ; ne jamais
  affirmer soi-même quelle pièce joue, où se trouve une pièce, ou ce qu'un
  coup attaque si cette description est absente (citer alors le coup en
  notation abrégée sans commentaire de position) ; ne jamais qualifier de
  "gratuite" une capture que la description indique défendue et reprise.
  Mention de la nouvelle rubrique "Pions perdus sans reprise".
- `_MOVE_SELECTION_SYSTEM_PROMPT` (choix de coups décisifs en lot) et
  `_ANALYSE_PARTIE_ADDENDUM` (explication d'un coup isolé) : même règle
  absolue, appliquée aux nouveaux champs `description_mecanique`/
  `meilleur_coup_description` (lot) et `coup_description_mecanique`/
  `meilleur_coup_description_mecanique` (contexte, coup isolé) —
  `_build_context_text` les sérialise avant `reponse_suivante`.

### Vérifications faites

- `py_compile` sur `game_facts.py`/`app.py`/`llm_coach.py` : OK.
- Rejeu complet de la partie de test de l'issue (position de départ non
  standard `[FEN ...]`, 1...c6...9.Nxe5, Alain Noirs) avec un venv de test
  temporaire (`python-chess==1.999`, hors dépôt, supprimé après usage) :
  le bloc généré signale bien 9.Nxe5 comme moment clé (capture du fou sans
  reprise, 3 points) et 6.Nxe5 comme pion perdu sans reprise (1 point) ; la
  vérification Stockfish ciblée simulée (meilleur coup 8...Nxg4 injecté à
  la main, sans appel moteur réel à cette étape) produit exactement le
  texte attendu par l'exemple de l'issue : "le fou noir de d6 capture un
  pion de Blancs (adversaire) en e5" pour Bxe5, "le cavalier noir de f6
  capture le cavalier de Blancs (adversaire) en g4 — était défendu(e) par
  le fou blanc de e2 : reprise possible, solde net +0 points" pour Nxg4
  (donc PAS gratuit, corrige l'erreur constatée avec Sonnet), et "le
  cavalier blanc de g4 capture le fou de Noirs (Alain) en e5 — aucune
  reprise possible" pour la réponse réelle 9.Nxe5.
- Reproductibilité (point 6) vérifiée avec le vrai moteur Stockfish
  (`/usr/games/stockfish`, présent sur cette machine) : deux appels
  `analyse(depth=14)` successifs sur EXACTEMENT la même position (les deux
  cibles de la partie de test) renvoient le même meilleur coup et le même
  score centipawns à chaque fois (testé aussi avec `Limit(time=0.7s)`,
  l'ancienne méthode, qui s'est révélée stable sur cette machine idle mais
  reste, par construction, dépendante de la charge machine — la profondeur
  fixe supprime ce risque par nature plutôt que par constat empirique).
- Scénarios supplémentaires testés directement sur `game_facts.py`
  (mat, promotion, `describe_pv_mechanically` sur 3 plis) : pas d'exception,
  texte cohérent ("promotion en dame", "échec et mat"...).
- `describe_move_mechanically`/`describe_pv_mechanically` retournent `None`/
  `[]` sur un coup illégal ou une position illisible plutôt que de lever
  une exception, cohérent avec le reste du module (`describe_reponse_suivante`
  notamment).

### Limites

- **Aucun vrai appel à l'API Claude n'a pu être fait** (ni Haiku ni Sonnet)
  : aucune `ANTHROPIC_API_KEY` dans l'environnement de ce worktree, aucun
  `.env` (non touché, conformément à la consigne). La demande de l'issue
  de comparer la réponse réelle du coach sous les deux modèles n'a donc
  pas pu être exécutée — seul le contenu exact du bloc de faits/contexte/
  system prompt a été vérifié, pas la réponse finale du modèle.
- **Le "fichier de tests de Claude Chat" (quatre parties Alain Blancs)**
  mentionné dans l'issue n'a pas été trouvé dans ce dépôt/worktree (aucun
  fichier PGN ni test correspondant sous `/home/alain/chesscoach-issue66`)
  : probablement des parties testées manuellement par Alain via l'interface
  Claude Chat, externes au dépôt. Non retesté, faute d'accès — à fournir
  par Alain si un nouveau test ciblé est nécessaire.
- `app.py` n'a pas été exécuté en direct (Flask/SocketIO/EngineManager) :
  `config.DATA_DIR` pointe vers `~/ChessCoach/data`, hors du périmètre
  strict de ce worktree (`~/chesscoach-issue66`), et le démarrer aurait pu
  y écrire (logs, cache, connexion moteur). Les nouveaux chemins de code
  d'`app.py` (`_prepare_flagged_moves_for_coach`, `on_analyse_expliquer_coup`)
  ont été vérifiés par lecture et par les fonctions `game_facts.py` sous-
  jacentes qu'ils appellent (déjà testées ci-dessus), pas par un appel réel
  du serveur.
- La description mécanique des "premiers coups de la ligne principale" se
  limite au 2e pli (la réponse anticipée après le meilleur coup) : au-delà,
  la ligne principale reste citée en texte brut sans description
  supplémentaire — jugé suffisant pour l'exemple de l'issue (Nxg4 Bxg4),
  une description plus longue aurait rendu le bloc disproportionné par
  rapport au reste.
- `STOCKFISH_CHECK_DEPTH = 14` est un compromis (temps de calcul par
  position légèrement plus long qu'à `movetime=0.7s` sur une position
  complexe) non mesuré en charge réelle de production — à surveiller si le
  budget global `STOCKFISH_CHECK_BUDGET_TOTAL` (6.0s) commence à tronquer
  des positions plus souvent qu'avant.

# Changelog — Issue #65

## Interface mobile : corrections après test réel sur GSM

- **Colonnes du plateau décalées (`templates/index.html`, `static/board.js`
  inchangé)** — `#coord-file` (lettres a-h) était un frère de `#board-row`
  au lieu d'être groupé avec `#board-wrapper` : centré seul sous toute la
  largeur de `#board-column`, il ignorait que `#board-row` inclut aussi
  `#coord-rank` et la barre d'éval avant le plateau, d'où un décalage
  gauche constant (mesuré ≈-17 à -19px, soit ~45 % d'une case à 390px de
  large comme signalé par Alain, ~25 % à 1440px — même défaut aux deux
  largeurs, seule sa part relative change). Introduction de
  `#board-file-column` (colonne flex centrée regroupant `#board-wrapper` et
  `#coord-file`) : les deux partagent désormais le même repère horizontal,
  et `#coord-file` hérite automatiquement des 2px de bordure de
  `#board-wrapper` de chaque côté. `#coord-rank` (numéros de rangs) : décalé
  de 2px vers le bas (`margin-top`) pour compenser la bordure du haut de
  `#board-wrapper`, dont il ne tenait pas compte (défaut bien plus discret,
  demandé en vérification par Alain). Les deux corrections sont purement
  CSS/DOM, valables dans les deux orientations et à toutes les largeurs.

- **Surbrillance Haiku/Sonnet qui disparaît après un tap (`templates/
  index.html`, `static/board.css`)** — sur écran tactile, un tap déclenche
  `:hover` puis le laisse "collé" (pas de souris pour le faire cesser)
  jusqu'au tap suivant ailleurs. Les règles `:hover` génériques
  (`button:hover:not(:disabled)`, `.btn-filled:hover`,
  `#llm-model-selector .llm-model-btn:hover`, `.opening-suggestion-btn:hover`)
  ont plus de sélecteurs de classe que les règles `.active`/`.playing`
  qu'elles sont censées compléter, donc gagnent la cascade CSS et masquent
  la surbrillance active tant que le survol tactile reste collé — pas
  seulement pour le sélecteur de modèle, mais pour tout bouton combinant un
  état `.active` avec un `:hover` générique (repéré aussi : `.mode-tab-btn`
  en vue desktop et `.phase-pill` de la feuille "Nouvel exercice" en vue
  mobile, tous deux vulnérables en théorie). Toutes ces règles `:hover`
  regroupées derrière `@media (hover: hover) and (pointer: fine)` — un vrai
  pointeur à survol, donc jamais un écran tactile. Le bouton réellement actif
  reste déterminé par `_llmModelSetActive` (llm_model.js, inchangé), piloté
  par la confirmation serveur `llm_model_changed` — déjà correct avant ce
  correctif, seul l'habillage CSS masquait le bon état.

- **Bulles du chat coach (`static/board.css`)** — couleurs inversées par
  rapport à la maquette (`.coach-bubble.assistant` en foncé/texte clair,
  `.coach-bubble.user` en clair/texte foncé) : permutées, l'alignement
  (utilisateur à droite, coach à gauche) étant déjà correct. Zone à
  défilement interne du chat (`.coach-drawer`/`.coach-history`,
  `overflow-y:auto` + `max-height`) supprimée sur mobile (`@media
  (max-width:900px)`) : c'est la page qui défile désormais, comme dans la
  maquette. `_coachRenderBubble`/`_coachRenderCreditInsuffisant`/
  `coachNewSegment` (board.js) : nouvelle fonction commune
  `_coachScrollReveal()` qui détecte si `#coach-history` est encore
  défilable en interne (`scrollHeight > clientHeight`, donc bureau) — dans
  ce cas comportement inchangé (`scrollTop`), sinon (mobile)
  `scrollIntoView()` sur l'élément ajouté, avec `block:"start"` pour une
  réponse du coach (issue #53 : son début visible en haut de l'écran,
  comportement demandé conservé) et `block:"end"` pour un message d'Alain/
  séparateur/erreur.

- **En-tête mobile trop haut (`templates/index.html`)** — `<h1>` masqué sur
  mobile (`display:none`), regroupement du sélecteur de modèle/compteur de
  tokens/lien "Coût API" dans `.header-actions` avec `flex-wrap:nowrap` sur
  la même media query : tient sur une seule ligne d'environ 60px de haut au
  lieu d'un bloc replié sur 2-3 lignes prenant ~1/3 de l'écran.

- **Doublon "Reprendre mon coup" en mode exercice sur mobile
  (`static/controls.js`)** — `updateSharedControlBar()` masque désormais
  `#shared-reprendre-btn` (carte "Contrôles du mode actif") uniquement
  quand `activeMode === "exercise"` ET que le viewport est mobile (`
  _mobileModeBarQuery.matches`, déjà déclaré pour le menu de mode) — la
  barre du bas (`#mobile-exercise-bar`) fournit alors déjà ce bouton. Les
  autres modes à "reprendre" (pédagogique/ouverture/finales), qui n'ont pas
  de barre du bas équivalente, gardent ce bouton sur mobile comme avant.

- **"Demander l'avis du coach" cliquable sans effet visible
  (`static/controls.js`, `static/{free_play,pedagogic,opening,finales}.js`)**
  — `MODE_CAPS` gagne un prédicat `askCoachAvailable` par mode (reflète la
  garde de la fonction `askXCoach` correspondante : partie démarrée, non
  terminée). `updateSharedControlBar()` désactive `#shared-ask-coach-btn`
  quand ce prédicat est faux — grisage via la règle générale
  `button:disabled { opacity:0.5 }` déjà utilisée ailleurs dans l'appli
  (aucune nouvelle règle CSS nécessaire). Rafraîchi à chaque abandon, à
  chaque détection de fin de partie côté serveur (mat/pat/nulle) et à
  chaque "Reprendre mon coup" (qui réactive le bouton). Nouvelle ligne
  `#shared-ask-coach-help` sous les boutons du mode actif : courte phrase
  expliquant ce que fait "Demander l'avis du coach" dans le mode affiché
  (texte dans `MODE_ASK_COACH_HELP`, controls.js). **Ce que fait ce bouton
  dans chaque mode** (pour le rapport, cf. `askXCoach` de chaque fichier) :
  demande un commentaire ponctuel du coach sur la position affichée, sans
  jouer de coup à sa place ni passer par le circuit "verdict" — en mode
  partie libre/pédagogique/ouverture/finales, un aller-retour SocketIO
  générique (`coach_comment_on_demand`, mutualisé via `askCoachOnDemand`,
  board.js), surtout utile quand "Commenter chaque coup" est décoché ; en
  mode exercice, disponible à tout moment (avant le verdict comme pendant
  l'exploration libre après), sans lien avec `exercise_answer`. **Limite
  assumée** : `askCoachAvailable` ne teste pas les courtes fenêtres
  `*Waiting` (coup adverse en cours de traitement côté serveur, ~1s) — un
  clic pile à ce moment reste un no-op silencieux, comme avant ce correctif.
  Le mode Éditeur de position n'a pas ce bouton (inchangé, pas de coach à la
  demande sans partie jouée) ; en mode partie libre, l'abandon reste
  cliquable même une fois la partie terminée (comportement pré-existant,
  non modifié — hors du périmètre explicite de cette demande).

- **"Jouer les Blancs/Noirs" hors de vue en mode partie pédagogique
  (`templates/index.html`, `static/pedagogic.js`)** — nouveau slot
  `#mobile-pedagogic-start-slot` (`display:contents`, donc invisible et
  sans effet tant qu'il est vide) juste avant le plateau dans
  `#board-column`. `placePedagogicStartButtonsForViewport()`
  (pedagogic.js, même mécanique que `placeModeTabBarForViewport` de
  controls.js) y déplace `#pedagogic-start-buttons` sur mobile tant
  qu'aucune partie n'est en cours (jamais démarrée, ou terminée/abandonnée)
  — les boutons reprennent leur emplacement d'origine (bas du panneau
  "Partie pédagogique") dès qu'une partie démarre, ou sur grand écran.
  Appelé au chargement, au redimensionnement franchissant le seuil mobile,
  au démarrage d'une partie, à l'abandon, à la détection de fin de partie et
  à "Reprendre mon coup". **Non étendu au mode Travail d'ouverture** (même
  paire de boutons en bas de panneau) : son démarrage exige un nom
  d'ouverture déjà saisi dans un champ resté, lui, en bas du panneau — les
  en extraire seuls aurait éloigné les boutons de leur champ obligatoire,
  jugé pas assez "simple" pour rester dans le périmètre de cette issue
  (clause "si c'est simple" de la demande). Le mode Travail de finales a un
  schéma différent (sélection dans un menu déroulant, pas de choix de
  camp), hors sujet.

## Vérification

Aucun serveur Flask-SocketIO ni clé API Claude disponibles dans ce worktree
(`flask_socketio`/`anthropic` absents des environnements Python présents,
et `RESEAU: non` sur cette tâche interdit une installation réseau) — un
vrai appel API n'a donc pas pu être exercé, comme demandé de le signaler
clairement le cas échéant.

À la place : page de test autonome (créée temporairement sous `static/`,
supprimée après usage — jamais committée) chargeant les fichiers réellement
livrés (`board.css`, `board.js`, `controls.js`, `pedagogic.js`, etc., sans
aucune copie/modification) avec `socket` réduit à un bouchon `{emit(){},
on(){}}`, servie en local (`python3 -m http.server`) et pilotée par
Playwright (Chromium déjà en cache local, donc sans réseau) :

- Alignement des lettres/chiffres mesuré par `getBoundingClientRect()` aux
  deux orientations (`flipBoard()`) et aux deux largeurs (390px/1440px) :
  écart au centre de chaque case ramené de ≈-17/-19px (structure d'origine,
  reproduite exprès pour comparaison) à moins de 2px (bruit de largeur de
  glyphe entre lettres, pas un défaut structurel) ; rangs à 0px exact dans
  les deux cas.
- Contexte navigateur tactile (`has_touch=True, is_mobile=True`) + un vrai
  `locator.tap()` sur le bouton Sonnet : capture de l'état juste après —
  fond terracotta correct (confirmé aussi en comparant avec la structure
  CSS d'origine rejouée dans la même page, qui affiche bien le fond clair
  de survol collé à la place, `:hover` matchant toujours après le tap) —
  et après un défilement simulé (`mouse.wheel`), sans changement.
- Bulles longues injectées via `_coachRenderBubble` en contexte 390px :
  couleurs/alignement conformes à la maquette, `#coach-history`/
  `.coach-drawer` confirmés non défilables en interne
  (`scrollHeight === clientHeight`), page entière défilable
  (`document.documentElement.scrollHeight > clientHeight`), début de la
  réponse du coach positionné en haut du viewport. Rejoué à 1440px :
  défilement interne toujours actif (`overflow-y:auto`, inchangé).
- En-tête à 390px : hauteur ramenée de ce qu'aurait donné le titre replié
  (non mesuré isolément, mais le nouveau total tient en une ligne) à 61px,
  une seule ligne (`flex-wrap:nowrap` confirmé), titre absent du DOM rendu.
- Mode partie pédagogique simulé par appel direct des fonctions réelles
  (`setActiveMode`, `abandonPedagogicGame`, `reprendrePedagogicCoup`, sans
  passer par un vrai socket) : bouton "Demander l'avis du coach" activé
  pendant la partie, désactivé après abandon, réactivé après "Reprendre mon
  coup" ; phrase d'aide affichée/masquée en cohérence. "Reprendre mon coup"
  confirmé masqué en mode exercice + mobile, visible partout ailleurs
  (desktop, ou mode pédagogique même sur mobile).
- Boutons "Jouer les Blancs/Noirs" confirmés déplacés dans le slot avant le
  plateau sur mobile tant qu'aucune partie n'est en cours, et de retour à
  leur emplacement d'origine dans le panneau une fois `placePedagogic
  StartButtonsForViewport()` rappelée après démarrage — jamais déplacés sur
  desktop (1440px).
- Captures d'écran prises pendant cette session (dossier temporaire, non
  conservées) : en-tête compact + boutons "Jouer les Blancs/Noirs" avant le
  plateau + lettres alignées dans les deux orientations ; bulles de chat
  couleurs/alignement conformes à la maquette ; "Demander l'avis du coach"
  visiblement grisé après abandon, avec sa phrase d'aide.

`.env` non touché. Aucun `git push`.

# Changelog — Issue #64

## Chat coach : isoler chaque partie (ne plus mélanger les échanges de deux parties successives)

- Cause confirmée : `_coachHistory` (tableau JS global, `static/board.js`)
  accumulait tous les échanges du chat depuis le dernier clic sur "Effacer"
  et était renvoyé **en entier** à l'API à chaque question (`coachSend()`),
  quel que soit le nombre de parties/exercices joués entre-temps. Aucun des
  points d'entrée « nouvelle partie » (`startFreeGameFromFen`,
  `startPedagogicGame`, `startOpeningGame`, `loadSelectedFinale`/
  `startFinaleDemo`, chargement d'une autre partie en revue de bibliothèque
  `parsePgn`) ne réinitialisait cet historique — seul `startExercise()` le
  faisait, via `coachClear()`, qui efface aussi tout l'affichage (pas le
  comportement demandé). Reproduit le constat de l'issue : questions/
  réponses de la partie 1 encore présentes dans les messages envoyés à
  l'API pour une question posée sur la partie 2.
- `static/board.js` : nouveau point de coupure `coachNewSegment(label)` —
  insère un séparateur discret (`.coach-separator`, "Nouvelle partie"/
  "Nouvel exercice") dans l'affichage seulement s'il y a déjà des messages
  depuis le précédent segment (pas de trait vide au tout premier segment, ni
  de traits empilés), et avance `_coachSegmentStart` (index dans
  `_coachHistory`) + horodate `_coachSegmentStartedAt`. `coachSend()` ne
  transmet plus que `_coachHistory.slice(_coachSegmentStart)` — l'affichage
  garde tout, l'API ne reçoit que le segment courant. `coachClear()` (bouton
  "Effacer") reste inchangé dans son effet (vide tout, y compris le
  segment). `coachBuildContext()` ajoute `nb_coups`/`debut_partie` au
  contexte (branche mode interactif ET branche revue de bibliothèque).
- `static/controls.js` : `activeModeGameState()` expose désormais `nbCoups`
  (longueur de `game.history()`), lu par `coachBuildContext()`.
- `static/free_play.js`, `pedagogic.js`, `opening.js`, `finales.js`
  (`loadSelectedFinale` ET `startFinaleDemo`) : appel de
  `coachNewSegment("Nouvelle partie")` juste après `ensureModeSwitchClean()`,
  au tout début de chaque fonction de démarrage de partie/finale — c'est le
  point déjà exécuté systématiquement à chaque nouvelle partie, y compris
  quand `activeMode` ne change pas d'un mode à l'autre (`ensureModeSwitchClean`
  seul ne suffisait pas : il ne nettoie l'ancien mode que lors d'une bascule
  vers un mode *différent*, pas quand une 2e partie démarre dans le même
  mode — exactement le scénario de l'issue).
- `static/exercise.js` (`startExercise`) : remplace `coachClear()` par
  `coachNewSegment("Nouvel exercice")` — un nouvel exercice repart avec un
  historique API vide comme avant, mais n'efface plus l'affichage des
  exercices précédents (changement de comportement demandé par l'issue).
- `static/board.js` (`parsePgn`) : `coachNewSegment("Nouvelle partie")`
  ajouté après `ensureModeSwitchClean("library")` — couvre à la fois
  l'import d'un fichier PGN local et le chargement d'une partie de la
  bibliothèque (`pgn_lib_game_loaded`, `pgn_library.js`, qui appelle la même
  fonction `parsePgn`).
- `static/board.css` : nouvelle classe `.coach-separator` (ligne fine de
  chaque côté, texte discret centré, `--cc-text-muted`/`--cc-neutral-200`,
  cohérente avec la palette existante).
- `llm_coach.py` :
  - `_SYSTEM_PROMPT` complété d'une consigne permanente d'isolation : ne
    jamais reprendre un coup/numéro de coup/situation absent du PGN ou du
    bloc de faits de la partie identifiée dans CET appel, même mentionné
    plus tôt dans la conversation affichée ; dire explicitement que
    l'information est absente plutôt que l'inventer.
  - `_build_context_text` : nouveau bloc "Identification de la partie/
    l'exercice actuellement discuté(e)" en tête du contexte (mode, nombre de
    coups déjà joués, heure de début du segment courant — champs
    `mode_origine`/`nb_coups`/`debut_partie` du contexte, désormais transmis
    par `coachBuildContext()`), avec consigne explicite d'ignorer tout
    message affiché plus haut qui évoquerait une partie différente.
- Audit des autres états pouvant fuiter d'une partie à l'autre (point 4 de
  la tâche) :
  - `_stockfish_check_cache` (`app.py`) : déjà clé par `(camp_alain, pgn)` —
    le PGN complet change dès la 1re différence entre deux parties, donc
    déjà isolé par construction. Aucune correction nécessaire.
  - `_gameAnalysisResults`/coups flagués de l'analyse mécanique
    (`game_analysis.js`, `_coachAnalysisFlaggedMoves` dans `board.js`) :
    déjà comparés coup à coup (mêmes SAN, même ordre, même longueur) à la
    partie réellement en cours avant transmission — retourne `[]` en cas de
    moindre différence. Aucune correction nécessaire, comportement déjà
    sûr.
  - État serveur de l'exercice (`_current_exercise`, `app.py`) et état
    client (`exerciseVerdictObtenu`, `_exerciseResetCoachLines()`, etc.,
    `exercise.js`) : déjà réinitialisés à chaque `exercise_new`/
    `startExercise()`. Aucune correction nécessaire.
  - `coach_memory.json` (patterns d'erreurs, objectifs courants) : fuite
    volontaire et documentée (mémoire de progression du coach d'une session
    à l'autre) — hors périmètre de ce bug, pas une régression.
- Tests exécutés (voir détails de la réponse de clôture) : aucun appel API
  réel possible depuis ce worktree (pas de `.env`, `ANTHROPIC_API_KEY` non
  défini) — vérifié à la place via deux harnais hors-réseau chargeant le
  vrai code : (1) `static/board.js` exécuté dans un bac à sable Node (vm)
  avec chess.js réel, scénario partie A (question posée) → partie B
  (question posée) en revue de bibliothèque : messages/contexte envoyés
  pour B ne contiennent aucune trace de A (ni "coup 30", ni le coup `Bb5`
  propre à A), PGN/nb_coups corrects pour B, séparateur "Nouvelle partie"
  bien inséré à l'écran, `coachClear()` remet bien tout à zéro ; (2)
  `llm_coach.get_coach_response`/`_build_context_text` appelés directement
  (venv `~/ChessCoach/venv`, `_call_claude` neutralisé pour éviter tout
  appel réseau) : system prompt + contexte + entrée journalisée dans
  `coach_calls.log` vérifiés champ par champ, rien de la partie A.
  Non testé : un serveur ChessCoach tournait déjà sur le port 5000 au
  moment de la vérification (process pré-existant, pas lancé par cette
  tâche) — pas de vérification visuelle du séparateur en émulation
  mobile/desktop dans un vrai navigateur, pour ne pas risquer d'interférer
  avec une session déjà active d'Alain (parties/exercices réels, compteur
  de tokens, bibliothèque PGN). Le rendu du séparateur a été relu dans le
  CSS/JS mais pas vérifié à l'écran — à confirmer par Alain à l'occasion
  d'un usage normal.

# Changelog — Issue #63

## Style commun (palette/typos/boutons) de la maquette Claude Design + disposition mobile du mode exercice

- Contexte : maquette statique dessinée avec Claude Design
  (`design/exercice.html` + captures d'écran) pour un nouveau look mobile —
  fond crème, plateau vert/beige, typographies Figtree/Caprasimo, boutons en
  pastille terracotta. Analysée en l'ouvrant dans un navigateur headless
  (Playwright) pour relever les styles calculés et la structure affichée
  (le fichier brut n'est qu'un gabarit `{{ ... }}` non rendu) ; contenu
  (textes, exercices, réponses du coach) volontairement ignoré, seuls
  l'apparence et la disposition sont repris.
- `static/board.css` : variables `--cc-*` (palette, `--cc-font-body`
  Figtree/`--cc-font-heading` Caprasimo, rayons, ombres) reprises telles
  quelles des tokens CSS embarqués dans la maquette
  (`--color-bg`/`--color-surface`/`--color-accent`/`--color-accent-2-*`...).
  Règle de conception d'Alain : le terracotta (`--cc-accent`) ne sert qu'au
  cliquable, tout le reste (titres, textes d'état, compteur de tokens,
  avatar du coach) est en brun foncé (`--cc-accent-strong`) ou gris
  (`--cc-text-muted`). Cases du plateau recolorées (beige/vert de la
  maquette) ; dernier coup joué en jaune doux (`--cc-last-move-from/to`,
  nouveauté demandée par Alain — absente de la maquette qui ne montre aucun
  coup en cours). Nouvelles classes `.coach-bubble.user/.assistant/.error`,
  `.coach-line-*` (tableau "Lignes du coach" restylé), `.coach-avatar`,
  historique repliable (`.historique-header-row`, `#historique-column.
  collapsed`).
- `templates/index.html` : police Figtree/Caprasimo chargées depuis Google
  Fonts (pile de secours `system-ui, sans-serif` identique à celle de la
  maquette) ; bouton générique en pastille terracotta appliqué à tous les
  modes (`button { ... }` + `.btn-filled` pour les actions principales) ;
  panneaux (`.panel`) et sélecteur de modèle Claude/compteur de tokens
  recolorés avec les nouvelles variables. Disposition desktop (1440px)
  inchangée (mêmes 4 colonnes) — vérifié sans débordement horizontal, à
  l'identique visuellement hormis la nouvelle palette.
  - Mode exercice, écrans étroits (<900px) : plateau agrandi
    (`--bd-size` mobile augmenté), panneau du coach/lignes du coach/
    historique restylés, feuille "Nouvel exercice" (`#exercise-phase-sheet`)
    qui monte du bas au clic sur le nouveau bouton "Nouvel exercice" de la
    barre fixe du bas, barre fixe (`#mobile-exercise-bar`, visible
    uniquement sur cet onglet) avec "Reprendre mon coup" (appelle
    `sharedReprendreCoup()` existant, jamais désactivé avant verdict comme
    demandé — contrairement à la maquette qui le montre grisé) et "Nouvel
    exercice".
  - Sélecteur de mode en menu déroulant (maquette) réalisé avec les 7
    boutons d'onglets existants (`switchModeTab`, `controls.js`) — aucune
    logique de changement de mode réécrite. `#mode-tab-bar` déplacé par JS
    (`placeModeTabBarForViewport`) entre son emplacement desktop d'origine
    et `#mobile-mode-bar-slot` collé en haut de l'écran sur mobile ; fermé,
    seul le bouton actif est visible (pastille + chevron) ; ouvert (clic
    délégué), les 7 s'affichent en liste, l'actif surligné en vert clair
    comme la maquette.
- `static/controls.js` : relocalisation du sélecteur de mode
  (`placeModeTabBarForViewport`, sur `matchMedia("(max-width:900px)")`),
  ouverture/fermeture du menu déroulant par délégation d'événement (aucun
  `onclick` des 7 boutons modifié), visibilité de la barre du bas liée à
  `switchModeTab`, historique repliable (`toggleHistoriqueCollapsed`,
  replié par défaut sur mobile seulement).
- `static/exercise.js` : feuille de phase mobile
  (`openExercisePhaseSheet`/`exercisePhaseSheetPick`/
  `launchExerciseFromSheet`) qui pilote le `<select id="exercise-phase-
  select">` existant (source de vérité, lu par `exercisePhaseFiltre()`
  inchangée) et appelle `startExercise()` sans le réécrire ; tableau
  "Lignes du coach" restylé en classes CSS (mêmes `<table>`/logique
  Play-Stop, `coach_lines.js` non touché).
- `static/board.js`/`static/llm_model.js` : bulles du chat et messages
  d'erreur (crédit épuisé, modèle indisponible) passés des couleurs codées
  en dur aux nouvelles classes `.coach-bubble.*` — pas de changement de
  comportement.
- Adaptations par rapport à la maquette (et pourquoi) :
  - Menu déroulant du sélecteur de mode : pousse en overlay (position
    absolute) plutôt que d'occuper une place fixe — évite de dupliquer les
    7 boutons.
  - Champ de saisie du coach : coins arrondis modérés (`--cc-radius-md`,
    16px) plutôt qu'une pastille pleine (99px) — la maquette n'a qu'un
    champ une ligne, l'appli utilise un `<textarea rows="3">` ; une pastille
    complète aurait été incongrue sur 3 lignes.
  - Bulle utilisateur du chat : couleur crème claire (`--cc-neutral-200`)
    choisie par cohérence avec la palette — la maquette ne montre aucun
    exemple de bulle utilisateur dans ses captures.
  - Avatar rond "C" du coach : ajouté par cohérence visuelle avec la
    maquette (élément décoratif, non cliquable, CSS pur — aucune image).
  - Sélecteur de phase natif (`<select>`) et bouton "Nouvel exercice"
    d'origine dans l'onglet Exercice : masqués sur mobile (`display:none`,
    jamais retirés du DOM) car remplacés à l'écran par la feuille du bas ;
    restent la source de vérité et fonctionnent tels quels au-dessus de
    900px.
  - Sélecteur de vitesse des lignes du coach : `<select>` d'origine
    restylé en pastille plutôt que remplacé par deux boutons — évite de
    dupliquer un état déjà porté par ce contrôle.
  - Ligne de statut `#exercise-status` : reste dans l'onglet Exercice
    (sous le plateau/coach en ordre mobile) plutôt que déplacée tout en
    haut comme la maquette — la repositionner en tête de page aurait
    nécessité une relocalisation JS supplémentaire pour un gain limité (le
    verdict apparaît de toute façon en premier plan dans le chat du coach).
- Tests (Playwright, émulation iPhone 13/390×844 tactile, + rendu Jinja2 du
  vrai template via un serveur Flask minimal ad hoc car `flask_socketio`/
  `python-chess` ne sont pas installés dans ce worktree et l'installation
  réseau est hors périmètre de cette tâche — **aucun appel API réel possible
  depuis ce worktree : ni `.env`, ni `data/`, ni `flask_socketio`/`chess`
  disponibles sans sortir du périmètre ou du réseau** ; le verdict/la
  réponse du coach n'ont donc pas pu être obtenus réellement, seulement
  simulés côté client pour vérifier le rendu) :
  - Mobile, mode exercice : ouverture de la feuille de phase, sélection
    d'une phase, "Lancer l'exercice" (fond assombri pendant la feuille,
    conforme à la capture `feuille_phase.png`) ; bulles utilisateur/coach et
    tableau "Lignes du coach" (Play/Stop) vérifiés avec des données
    injectées côté client ; dernier coup en jaune doux vérifié
    (`renderBoard` appelé directement) ; plateau côté Noirs déjà vérifié via
    la logique existante (`_boardFlipped`, inchangée) ; changement de mode
    via le menu puis retour à Exercice ; **aucun débordement horizontal
    mesuré** (`scrollWidth === clientWidth`) sur les 7 onglets.
  - Mobile, autres modes (partie libre, pédagogique, ouverture, finales,
    éditeur, bibliothèque) : changement d'onglet, capture d'écran, palette
    appliquée, aucune erreur JS (seuls des 404 attendus : favicon/
    Socket.IO, aucun serveur réel derrière ce test), aucun débordement.
  - Sélecteur de modèle Claude et compteur de tokens : rendu initial serveur
    (via le harnais Flask de test) vérifié fonctionnel avec les nouvelles
    couleurs.
  - Rendu 1440×900 comparé à l'avant : disposition à 4 colonnes inchangée,
    aucun débordement, seule la palette change.
- Limites connues : pas de test avec un vrai backend SocketIO/Stockfish/API
  Claude (indisponibles dans ce worktree sans réseau) — le parcours complet
  "coup → verdict → lecture d'une ligne" n'a été vérifié que par injection
  de données côté client, pas via un aller-retour serveur réel. Ligne de
  statut `#exercise-status` non repositionnée en tête de page (voir
  adaptations ci-dessus). Aucun fichier Python touché.

# Changelog — Issue #62

## Coach : cibler le moment le plus grave (pas seulement le premier) et donner aux explications la réfutation calculée

- Contexte : sur une partie pédagogique réelle perdue par Alain (Blancs), la
  vérification Stockfish ciblée du bloc de faits (issues #55-#57) portait
  sur 6.Nxd5/7.Qxd2 (perte nette de 2 points, le premier accroc) mais jamais
  sur 8.Qf4?? (perte de la dame sans reprise, 9 points, le vrai tournant) —
  le chat et l'analyse manuelle ne s'accordaient pas sur lequel des deux
  était "le vrai tournant". Par ailleurs, l'explication du coup flagué
  8.Qf4 ne mentionnait que "le roque était préférable pour la sécurité du
  roi", jamais la vraie raison (8...Nxf4 capture la dame) : le modèle devait
  la deviner au lieu de la recevoir.
- `game_facts.find_stockfish_check_targets` cible désormais jusqu'à DEUX
  moments (au lieu d'un seul) : "plus_grave" (la plus grande perte nette de
  toute la partie, ou un mat, toujours prioritaire) et
  "premier_significatif" (le premier moment ≥ 2 points nets ou mat, comme
  avant) — le moment le plus grave est toujours listé en premier (donc
  vérifié en priorité par app.py si le budget de temps est dépassé), les
  positions communes aux deux moments sont dédupliquées, et le second moment
  est omis s'il coïncide avec le premier. `build_game_facts_text` étiquette
  les deux groupes explicitement dans le bloc de faits ("Moment le plus
  grave" / "Premier moment significatif").
- `app.py` : `STOCKFISH_CHECK_BUDGET_TOTAL` rehaussé de 4.0s à 6.0s (jusqu'à
  4 positions désormais, contre 2 avant) — reste borné et non bloquant, la
  boucle de vérification traite les cibles dans l'ordre reçu (plus grave
  d'abord). Cache et réutilisation des résultats de "Analyser cette partie"
  inchangés.
- `game_facts.describe_reponse_suivante` (nouvelle fonction, réutilise
  `_materiel`/`_variation_materielle`/`_solde_net_apres_capture`/
  `_NOM_PIECE`/`camp_label` déjà existants) : calcule mécaniquement, depuis
  la position avant un coup flagué et le coup suivant réellement joué dans
  la partie (transmis en UCI par le client), sa conséquence matérielle
  immédiate — par exemple "réponse réellement jouée ensuite dans la partie :
  Nxf4 (Noirs (adversaire)) capture la dame de Blancs (Alain), perte nette
  de 9 points pour Blancs (Alain), aucune reprise possible." `None` si la
  réponse n'est pas une capture.
- `static/game_analysis.js` : chaque coup flagué transmis au serveur (en lot
  via `analyse_choisir_coups_decisifs`, ou à la demande via
  `analyse_expliquer_coup`) porte désormais `uci_suivant` (le coup suivant
  réellement joué, déjà en mémoire côté client) ; `app.py`
  (`_prepare_flagged_moves_for_coach`, `on_analyse_expliquer_coup`) calcule
  `reponse_suivante` via `describe_reponse_suivante` et l'ajoute aux données
  transmises au coach.
- `llm_coach.py` : `_build_context_text` affiche `reponse_suivante` comme
  fait "à expliquer EN PREMIER". `_MOVE_SELECTION_SYSTEM_PROMPT` et
  `_ANALYSE_PARTIE_ADDENDUM` demandent d'expliquer cette réfutation calculée
  en premier et interdisent de proposer une raison stratégique concurrente
  à sa place. Cohérence chat/analyse (point 3) : `_GAME_FACTS_ADDENDUM`
  désigne explicitement le "moment le plus grave" comme LE tournant ;
  `_MOVE_SELECTION_SYSTEM_PROMPT` n'autorise cette qualification que pour le
  coup de plus grosse perte de la liste transmise ; `_ANALYSE_PARTIE_ADDENDUM`
  (explication d'un coup isolé, sans visibilité sur le reste de la partie)
  interdit purement et simplement cette qualification.
- Vérifié avec le vrai python-chess (sans Stockfish, module hors périmètre
  de cet appel) sur les deux PGN de test de l'issue : cibles
  `[7.Qxd2, 8.Qf4 (plus_grave), 6.Nxd5 (premier_significatif)]` pour la
  première partie, `[15.Qb3, 16.Ke2 (plus_grave)]` pour la seconde (moments
  identiques, comme avant) ; `describe_reponse_suivante` sur 8.Qf4 renvoie
  bien la capture de la dame par 8...Nxf4 sans reprise. Pas d'appel API
  Claude réel effectué dans ce worktree (clé API hors périmètre/non
  disponible ici) — à vérifier par Alain en usage réel.

# Changelog — Issue #61

## Choix du modèle Claude (Haiku/Sonnet) depuis l'interface, sans redémarrage

- Contexte : le modèle était fixé une fois pour toutes par
  `CHESSCOACH_LLM_MODEL` (.env) — passer de Haiku (tests) à Sonnet (jeu
  sérieux) imposait d'éditer le .env et de relancer l'appli.
- `config.py` : `LLM_MODEL_HAIKU`/`LLM_MODEL_SONNET`/`LLM_MODEL_CHOICES`
  (id → libellé) définis en un seul endroit ; `config.set_llm_model(model_id)`
  change `config.LLM_MODEL` en mémoire (effet immédiat sur tous les appels
  suivants, tous chemins confondus) et persiste le choix dans
  `data/llm_model_choice.json` (nouveau fichier, séparé du .env, gitignoré
  comme le reste de data/). Au démarrage, reprend ce fichier s'il est valide,
  sinon `CHESSCOACH_LLM_MODEL` si elle correspond à l'un des deux choix,
  sinon Sonnet par défaut.
- templates/index.html : sélecteur `#llm-model-selector` dans l'en-tête, près
  du compteur de tokens — deux boutons contigus « Haiku (test) » /
  « Sonnet (sérieux) », libellés abrégés sous 900px (comme le reste de
  l'en-tête), vérifié sans débordement à 390×844 (Playwright).
- static/llm_model.js (nouveau) : clic → événement SocketIO `set_llm_model`,
  bascule le bouton actif sur confirmation (`llm_model_changed`), affiche un
  message clair dans le chat en cas de retour automatique
  (`llm_model_indisponible`).
- app.py : handler `set_llm_model` ; `_handle_llm_model_indisponible_si_besoin`
  appelé au début des 10 blocs `if error:` (un par point d'appel API) — si
  l'API refuse le modèle actif (HTTP 404 `not_found_error`, remonté par
  `llm_coach.ModeleIndisponibleError` en `error: "modele_indisponible"`),
  revient seul à l'autre choix (persisté) et prévient le client au lieu
  d'afficher une erreur technique brute.
- llm_coach.py : nouvelle exception `ModeleIndisponibleError` (même pattern
  que `CreditInsuffisantError`, issue #54), détectée dans `_call_claude` et
  propagée par les 4 fonctions publiques d'appel. `_log_coach_call` inscrit
  désormais un champ `model` explicite dans chaque entrée de
  `coach_calls.log` (déjà présent via `usage.model` sur les appels réussis,
  manquant sur les entrées d'erreur).
- Paramètres d'appel (`max_tokens=4096`, `thinking: {"type": "disabled"}`)
  vérifiés acceptés tels quels par les deux modèles — aucune adaptation par
  modèle nécessaire.
- Compteur de tokens par modèle (issue #54) déjà cohérent après un
  changement de modèle en cours de session (`_record_usage` cumule par
  modèle réellement résolu par l'API, indépendamment du sélecteur).
- CONTEXTE.md : nouvelle section « Choix du modèle Claude (Haiku/Sonnet)
  depuis l'interface (issue #61) ».

# Changelog — Issue #60

## Détection tolérante de l'erreur « crédit épuisé » de l'API (suite de l'issue #54)

- Contexte : la détection introduite à l'issue #54 ne reconnaissait qu'une
  seule forme exacte (HTTP 403, `error.type == "billing_error"`). Des
  retours d'utilisateurs de l'API (2024-2025, non revérifiables sans
  épuiser réellement un crédit) indiquent qu'un solde insuffisant peut
  aussi se manifester en HTTP 400 `invalid_request_error` avec un message
  du type « Your credit balance is too low to access the Anthropic API.
  Please go to Plans & Billing to upgrade or purchase credits. » — un cas
  qui tombait auparavant dans l'erreur générique, sans le message clair ni
  le lien vers la Console.
- `llm_coach.py` (`_call_claude`, gestion de `urllib.error.HTTPError`) :
  la détection reconnaît désormais trois formes, sans se fier à un unique
  couple (code, type) :
  - `error.type == "billing_error"`, quel que soit le code HTTP ;
  - code HTTP 402, quel que soit `error.type` ;
  - code HTTP 400 avec `error.type == "invalid_request_error"` dont le
    message contient (insensible à la casse) « credit balance »,
    « insufficient credit » ou « plans & billing »/« plans and billing ».
  - Une vraie erreur de permission (403 `permission_error`) et une vraie
    requête invalide (400 sans mention de crédit) continuent de propager
    l'erreur HTTP normale (pas de `CreditInsuffisantError`).
  - Le message affiché à l'utilisateur (bulle dédiée + lien Console) est
    inchangé : tous les appelants attrapent `CreditInsuffisantError` de la
    même façon qu'avant.
- Docstrings de `CreditInsuffisantError` et `_call_claude`, et `CONTEXTE.md`,
  mis à jour pour refléter la détection élargie.
- Vérification par simulation locale (`urllib.request.urlopen` mocké, aucun
  appel réseau réel — voir la section « Limite » ci-dessous) : les 5 cas
  suivants ont été rejoués et donnent le résultat attendu :
  1. HTTP 403 `billing_error` (forme historique) → `CreditInsuffisantError`.
  2. HTTP 402 `invalid_request_error` → `CreditInsuffisantError`.
  3. HTTP 400 `invalid_request_error`, message « Your credit balance is too
     low ... Plans & Billing ... » → `CreditInsuffisantError`.
  4. HTTP 403 `permission_error` (vraie erreur de permission) →
     `HTTPError` propagée normalement, PAS de `CreditInsuffisantError`.
  5. HTTP 400 `invalid_request_error` sans mention de crédit (« messages:
     at least one message is required ») → `HTTPError` propagée
     normalement, PAS de `CreditInsuffisantError`.
- Limite assumée : cette vérification simule le corps de réponse HTTP tel
  que rapporté par des utilisateurs de l'API ; elle ne constitue pas un
  test sur une vraie réponse de crédit épuisé (impossible à provoquer sans
  épuiser réellement le crédit de la clé API). Si la forme réelle
  divergeait encore de ces trois hypothèses, un nouvel ajustement resterait
  possible.

# Changelog — Issue #59

## « Analyser cette partie » depuis le bandeau de fin de partie : un seul clic

- Contexte : le bouton "Analyser cette partie" de la bannière de fin de
  partie (mat/pat/nulle/abandon) basculait vers l'onglet Bibliothèque /
  Revue PGN et y chargeait la partie, mais ne lançait pas l'analyse —
  Alain devait recliquer sur le bouton "Analyser cette partie" de l'onglet,
  placé sous la liste des parties importées (loin en bas sur GSM).
- `static/game_analysis.js` : `analyserPartieDepuisPgn()` (appelée par la
  bannière — `board.js showGameOverBanner`, câblée dans pedagogic.js/
  free_play.js/opening.js/finales.js) appelle désormais
  `_lancerAnalyseAutoDepuisBanniere()` une fois la partie chargée en revue :
  - Si la partie qui vient d'être chargée correspond coup à coup (mêmes SAN,
    même ordre) au dernier rapport en mémoire (`_gameAnalysisResults` — une
    analyse déjà menée cette session, quel que soit l'onglet actif depuis),
    réaffiche directement ce rapport sans relancer Stockfish.
  - Sinon, lance `analyserPartieCourante()` (état "en cours" affiché,
    bouton de l'onglet désactivé pendant l'analyse — comportement déjà
    existant, réutilisé tel quel).
  - Dans les deux cas, fait défiler la page pour amener
    `#game-analysis-panel` en vue (`scrollIntoView`), une fois le résultat
    (ou le rapport en cache) réellement affiché — important en mobile où ce
    panneau est placé sous la longue liste de parties importées.
- `templates/index.html` : ajout de l'id `game-analysis-panel` sur le
  conteneur du bouton/statut/rapport d'analyse (cible du scroll).
- Le bouton de l'onglet Bibliothèque / Revue PGN (`analyserPartieCourante`,
  clic manuel pour une partie chargée à la main) garde son comportement
  actuel — aucun changement de ce chemin, aucun défilement automatique
  ajouté pour lui.
- Vérifié en conditions réelles (Playwright + Stockfish local, viewport
  390×844) : partie pédagogique abandonnée après 1.e4 → un seul clic sur la
  bannière déclenche bien l'état "Analyse Stockfish en cours..." avec bouton
  désactivé, puis "Analyse terminée" avec le panneau ramené dans le
  viewport ; rejouer le même point d'entrée pour la même partie affiche
  directement "Analyse déjà disponible... réalisée plus tôt dans la
  session" sans nouvel appel réseau (0 émission socket `analyser_pgn`
  vérifiée). Même mécanisme revérifié en partie libre. Aucun appel à l'API
  Claude effectué (pas de clé `ANTHROPIC_API_KEY` disponible dans cet
  environnement de test) — seule l'analyse mécanique Stockfish a été
  vérifiée en conditions réelles ; les explications narratives du coach
  (`demanderExplicationsCoach`, appelées après l'analyse) n'ont pas été
  exercées.

# Changelog — Issue #58

## Mode exercices : tableau "Lignes du coach", extraction + lecture des lignes citées sur l'échiquier

- Contexte : en mode exercice, le coach cite souvent une ligne de coups
  dans sa prose (ex. « la ligne logique est Kc3 Ke1 Kd3 Kd1 Ke3 Kc2 »),
  qu'Alain devait jusqu'ici rejouer à la main pour la visualiser.
- `static/coach_lines.js` (nouveau, composant réutilisable mode-agnostique,
  ne dépend que de chess.js) :
  - `extractCoachMoveLines(text)` — repère les suites d'au moins deux coups
    en notation standard (numéros de coups et annotations !?+# tolérés et
    retirés), dédoublonne, et ignore les chemins de cases séparés par des
    tirets (`c3-d3-e3`) qui ne sont pas des coups.
  - `resolveCoachLineStart(candidates, moves)` — détermine la position de
    départ par légalité (jamais par déduction) : essaie chaque candidat
    fourni dans l'ordre et retient le premier où tous les coups sont
    légaux ; retourne `null` si aucun candidat ne convient.
  - `playCoachLineSequence(steps, opts)` — lecture pas à pas avec pause
    configurable, callback de rendu fourni par l'appelant, contrôleur
    `{stop()}` pour interrompre en cours de route.
- `static/exercise.js` : nouveau tableau "Lignes du coach" dans le panneau
  du mode exercice, alimenté à chaque réponse du coach reçue pendant
  l'exercice actif (verdict `exercise_comment`, et questions de suivi
  posées dans le chat libre/à la demande pendant l'exploration après
  verdict, via le nouveau hook générique `exerciseOnCoachText`) :
  - Pour chaque ligne, deux candidats de départ sont essayés dans l'ordre :
    la position d'avant le coup d'Alain (`exerciseFenAvant` — couvre aussi
    le cas où la ligne commence par son propre coup), puis la position
    juste après (`exerciseFenApresCoup`, nouvelle variable capturée dans
    `submitExerciseAnswer`). Le tableau affiche laquelle a été retenue
    (« depuis la position de départ » / « depuis la position après ton
    coup »), ou « ligne non jouable » (discret, sans bouton) si aucune des
    deux ne convient.
  - Bonus : la meilleure ligne déjà calculée par Stockfish
    (`exercisePvMeilleurCoup`, transmise avec le verdict depuis l'issue
    #20) est ajoutée en première ligne, étiquetée « Ligne de Stockfish »,
    dédoublonnée contre une ligne identique citée par le coach en prose.
  - Bouton Play/Stop par ligne, sélecteur de vitesse (0,5 s / 1 s, 1 s par
    défaut) partagé par le tableau. Pendant la lecture, le plateau affiche
    la ligne (surlignage du dernier coup comme d'habitude) sans toucher à
    `exerciseGame`, à l'historique de l'exercice ni au chat, et sans
    déclencher de commentaire automatique — un bouton « Revenir à la
    position de l'exercice » (affiché dès la première lecture, masqué
    après usage) restaure la position réelle de l'exercice. Les clics sur
    le plateau sont bloqués tant que cette prévisualisation est active,
    pour ne jamais mélanger les deux positions.
  - Tableau vidé à chaque nouvel exercice (et à l'abandon), conservé lors
    d'un « Reprendre mon coup » (juste sorti du mode prévisualisation).
- `static/board.js` : `coach_response` et `coach_on_demand_response`
  appellent désormais `exerciseOnCoachText(text)` si cette fonction existe
  (no-op hors mode exercice) — mécanisme générique, pas de dépendance
  directe de board.js à exercise.js.
- `llm_coach.py` (`_EXERCISE_SYSTEM_ADDENDUM`) : consigne courte ajoutée au
  prompt du coach en mode exercice pour écrire toute ligne de coups en
  notation standard, coups séparés par des espaces — fiabilise
  l'extraction côté client.
- `templates/index.html` : inclusion de `coach_lines.js` (avant
  `exercise.js`) et nouveau bloc HTML `#exercise-coach-lines` (titre,
  sélecteur de vitesse, tableau, bouton de retour) dans le panneau du mode
  exercice.

### Tests réalisés

- Tests unitaires Node purs (extraction + résolution de légalité, sans
  navigateur) : exemple de l'issue (ligne démarrant par le coup d'Alain,
  résolue « depuis la position de départ »), ligne légale seulement depuis
  la position après le coup, ligne illégale depuis les deux candidats (→
  `null`, aucun bouton), faux positif `c3-d3-e3` (aucune ligne extraite),
  numéros de coups + annotations `!?+#` correctement nettoyés,
  dédoublonnage de lignes identiques.
- Tests bout en bout avec Playwright (Chromium) contre le serveur Flask du
  worktree, **avec de vrais appels à l'API Claude** (clé lue depuis le
  `.env` existant de `~/ChessCoach`, non modifié, seulement exportée dans
  l'environnement du process de test) :
  - Nouvel exercice → coup joué → verdict reçu → tableau peuplé
    correctement, avec une ligne Stockfish bonus et une ligne citée par le
    coach commençant par son propre coup (« depuis la position de
    départ »).
  - Un second essai a naturellement produit le cas « ligne qui ne démarre
    qu'après le coup d'Alain » (résolue « depuis la position après ton
    coup ») avec un vrai texte de coach.
  - Play → lecture animée visible sur le plateau (capture d'écran) → Stop
    en cours de lecture (bouton repasse à "Play", `exerciseGame.fen()`
    inchangé) → « Revenir à la position de l'exercice » restaure bien la
    position réelle et se masque ensuite ; nombre de bulles du chat
    inchangé après lecture/arrêt/retour (aucun commentaire auto, aucun
    effacement).
  - Ligne illégale injectée (`Qxh7 Rxh7` sur une position sans dame ni
    tour disponibles) → affichée « ligne non jouable », sans bouton ; texte
    contenant un chemin `c3-d3-e3` → aucune ligne fantôme créée.
  - Viewport mobile 390×844 (tactile, `page.tap`) : tableau lisible sans
    débordement horizontal, bouton Play ~52×44 px (cible tactile correcte),
    Play/Stop/retour fonctionnels au toucher.
- `python3 -m py_compile` sur les fichiers Python modifiés, `node --check`
  sur les fichiers JS modifiés/créés.

# Changelog — Issue #57

## Bloc de faits du chat : solde net après reprise, et coup décisif vérifié par Stockfish

- Contexte : test réel du bloc de faits calculés (issues #55/#56) sur une
  partie pédagogique perdue (Alain Blancs). Deux défauts constatés dans la
  réponse réelle du coach : (1) le moment clé « 16...Rxb3 : Noirs capture la
  dame en b3 (reprise possible), variation matérielle de 9 points » a été lu
  par le coach comme une perte sèche de 9 points, en ignorant que la reprise
  (Bxb3/Nxb3/axb3) ramène le solde réel à 4 points ; (2) le bloc ne contenait
  aucune évaluation par un moteur, donc rien ne pouvait mettre le coach sur
  la piste du vrai remède (15...Nxd3+ 16.Qxd3 échappait à la tour) — il s'est
  contenté de suggérer « vérifier ce qui attaquait la dame ».

- `game_facts.py` :
  - `_variation_materielle` : factorise le calcul de la variation matérielle
    signée d'un demi-coup, déjà présent dans la boucle de
    `build_game_facts_text`, pour que le ciblage Stockfish (voir plus bas)
    s'accorde exactement sur les mêmes demi-coups ;
  - `_solde_net_apres_capture` : calcule mécaniquement (python-chess, coups
    légaux réels, aucun moteur) le solde net, du point de vue du camp qui
    vient de perdre une pièce, s'il la reprend immédiatement sur la même
    case (une seule reprise, pas de recherche tactique plus profonde) ;
    retourne `None` si aucune reprise n'est légale ;
  - `_decrit_moment_cle` : un moment clé qui capture une pièce indique
    désormais, quand une reprise est possible, le solde net après cette
    reprise et dit explicitement qu'il s'agit du résultat réel de l'échange
    (pas la variation brute) ; quand aucune reprise n'est possible, dit
    explicitement que la variation brute est bien le résultat final — dans
    les deux cas, plus d'ambiguïté sur lequel des deux chiffres retenir ;
  - nouvelle fonction `find_stockfish_check_targets(pgn_text, camp_alain)` :
    identifie, SANS appeler Stockfish (le module n'en fait toujours aucun
    appel direct), les deux derniers coups d'Alain qui précèdent le premier
    moment où il perd au moins 2 points nets (après reprise mécanique
    éventuelle) ou se fait mater — le coup qui a permis la perte, et celui
    d'avant. Retourne les FEN/SAN de ces positions ; c'est l'appelant
    (`app.py`, qui détient `engine_manager`) qui fait le calcul Stockfish
    lui-même ;
  - `build_game_facts_text` : nouveau paramètre optionnel `stockfish_check`
    (liste de dicts `{numero, san, camp, meilleur_coup, perte_cp,
    ligne_principale}`) qui ajoute une section « Vérification Stockfish
    ciblée » au bloc quand elle est fournie et non vide.

- `engine_stockfish.py` : `EngineManager.evaluate()` et `.evaluate_move()`
  acceptent un nouveau paramètre optionnel `time_limit` (secondes) qui, s'il
  est fourni, borne la recherche Stockfish en TEMPS plutôt qu'en profondeur
  (`chess.engine.Limit(time=...)` au lieu de `Limit(depth=...)`) — une
  profondeur fixe ne borne pas le temps de calcul sur une position complexe,
  alors que Stockfish respecte lui-même un temps de recherche donné
  (movetime), sans thread de timeout externe. Comportement par défaut
  (`time_limit=None`) inchangé pour tous les appelants existants.

- `app.py` :
  - nouvelles fonctions `_cached_stockfish_eval` (réutilise un résultat déjà
    calculé par « Analyser cette partie » cette session si la position
    correspond exactement, via `fen_avant`), `_stockfish_eval_cible` (appel
    Stockfish borné à `STOCKFISH_CHECK_TIME_PAR_POSITION` = 0.7s par
    position) et `_stockfish_check_key_moment` (orchestration : cible via
    `game_facts.find_stockfish_check_targets`, cache ou calcul, budget
    global `STOCKFISH_CHECK_BUDGET_TOTAL` = 4s, jamais d'exception qui
    remonterait jusqu'à la réponse du coach) ;
  - cache mémoire process (`_stockfish_check_cache`, clé
    `(camp_alain, pgn)`) pour ne pas relancer Stockfish à chaque tour du
    chat sur la même position — le PGN change dès qu'un nouveau coup est
    joué, la clé se périme donc naturellement ; purge grossière au-delà de
    50 entrées ;
  - `_enrich_context_with_game_facts` appelle désormais
    `_stockfish_check_key_moment` et transmet son résultat à
    `build_game_facts_text` via `stockfish_check`.

- `static/board.js` : `_coachAnalysisFlaggedMoves()` transmet désormais
  aussi `fen_avant`/`best_move` (déjà présents dans `_gameAnalysisResults`,
  simplement pas encore relayés) pour permettre au serveur de reconnaître une
  position déjà analysée par « Analyser cette partie » cette session, et
  d'éviter un nouvel appel Stockfish pour la vérification ciblée du chat.

- `llm_coach.py` (`_GAME_FACTS_ADDENDUM`) : renforcement du prompt —
  (1) le coach doit citer le solde net (pas la variation brute) quand le
  bloc en fournit un, et ne doit jamais annoncer un chiffre de variation
  matérielle différent de celui du bloc ; (2) le coach ne doit s'appuyer que
  sur le meilleur coup / la ligne principale Stockfish tels qu'ils figurent
  dans la section « Vérification Stockfish ciblée » — jamais d'invention de
  variante si cette section est absente ou ne couvre pas le coup en
  question (Stockfish indisponible/trop lent), auquel cas le coach dit
  qu'il ne sait pas plutôt que d'improviser ; (3) le chiffre brut de
  centipawns de « perte estimée » ne doit jamais être cité tel quel
  (reformulation en langage naturel, même consigne que le mode exercice).

- Test réel (positions rejouées mécaniquement + Stockfish 16 local, PGN de
  l'issue, Alain Blancs) :
  - le solde net calculé au coup 16 est bien **-4** (variation brute 9,
    reprise de la tour possible par Blancs (Alain)) ;
  - les deux positions ciblées automatiquement sont bien 15.Qb3 et 16.Ke2 ;
  - Stockfish (0.7s/position, 2.8s au total dans ce test) trouve **d4**
    (perte 317cp) comme meilleur coup à la place de 15.Qb3, et **Kf1**
    (perte 65cp) à la place de 16.Ke2 ;
  - **écart avec l'énoncé de l'issue** : l'énoncé attendait que Qxd3
    ressorte comme meilleur coup à la place de 16.Ke2. Une analyse Stockfish
    plus poussée (multipv, 3s) montre que Qxd3 est en réalité le PLUS
    mauvais des 4 coups légaux à cette position (-1326cp contre -1066 pour
    Kf1) : le pion noir resté en e4 depuis 3...dxe4 (jamais repris) garde la
    case d3 sous surveillance, donc 16.Qxd3 hangerait la dame à 16...exd3.
    Le bloc reflète donc fidèlement ce que Stockfish calcule réellement
    (Kf1), pas l'hypothèse de l'énoncé — c'est exactement le comportement
    voulu par la consigne « le coach ne doit s'appuyer que sur le meilleur
    coup de Stockfish tel qu'il figure dans le bloc, pas d'invention » ;
    l'énoncé se trompait sur ce point précis d'analyse humaine ;
  - dégradation gracieuse vérifiée : Stockfish indisponible
    (`engine_manager` absent) → bloc sans section Stockfish mais solde net
    toujours présent ; erreur/lenteur simulée pendant l'appel moteur →
    aucune exception ne remonte, la ligne concernée est simplement omise ;
  - réutilisation du cache vérifiée : un résultat déjà présent dans
    `analyse_mecanique_flags` (simulant « Analyser cette partie » déjà
    lancée) est utilisé tel quel, sans second appel Stockfish.

- Pas d'appel réel à l'API Claude dans ce test (clé API non sollicitée pour
  cette vérification) : contenu exact du bloc de faits vérifié directement
  (voir ci-dessus), comportement du coach lui-même non observé en conditions
  réelles — cohérent avec le renforcement de prompt apporté, mais non
  exécuté de bout en bout.

- Limites connues : le solde net ne regarde qu'UNE reprise immédiate (pas de
  recherche tactique plus profonde, ex. un fork qui suivrait la reprise) —
  volontairement mécanique, pas une évaluation Stockfish ; la vérification
  Stockfish ne porte que sur le premier moment clé de perte nette
  d'au moins 2 points ou de mat, jamais sur plusieurs moments de la même
  partie ; le cache de vérification est un simple dict process (pas de
  notion de session à isoler, cohérent avec l'usage mono-utilisateur de
  l'appli).

# Changelog — Issue #56

## Explications de coups de l'analyse post-partie : étiqueter chaque coup par son auteur ; compléter le bloc de faits avec la fin de partie

- Contexte : en usage réel après « Analyser cette partie » sur une partie
  pédagogique abandonnée (Alain Blancs, Stockfish Noirs), l'explication du
  coup flagué « 10. (Noirs) Bf8 » disait « Alain le replie en f8 » — un coup
  des Noirs attribué à Alain — et nommait l'ouverture « Française » alors
  que la partie commençait par 1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 (pas une
  Française). Même famille de bug que l'issue #55 (chat libre), mais sur un
  autre chemin de code : le module d'explications narratives des coups
  décisifs (`get_move_explanations`, appel en lot, issue #42) et
  l'explication à la demande d'un coup unique (`on_analyse_expliquer_coup`)
  ne recevaient jusque-là aucune information sur le camp d'Alain.
- `game_facts.py` :
  - `_camp_label` renommée `camp_label` (fonction publique) pour être
    réutilisée telle quelle par `llm_coach.py`, au lieu d'en redupliquer la
    logique (« Blancs (Alain) »/« Noirs (adversaire) », jamais une simple
    déduction du trait) ;
  - nouvelle fonction `camp_alain_from_pgn_headers(white, black)` : déduit
    le camp d'Alain depuis les en-têtes PGN White/Black — pseudo
    Lichess/Chess.com (`athanatos123`, casse ignorée) pour une partie
    importée de la bibliothèque, ou le nom « Alain » pour une partie jouée
    dans l'appli (pédagogique/ouverture/finales taguent déjà leurs en-têtes
    ainsi avant l'analyse). Retourne `""` si aucun des deux en-têtes ne
    correspond (partie entre deux tiers, partie libre où les deux camps
    peuvent être joués par Alain) — jamais une devinette ;
  - `build_game_facts_text` : la fin de partie (mat, pat, nulle par la
    règle — matériel insuffisant/75 coups/répétition quintuple —, ou
    abandon déduit du `Result` PGN si aucune de ces règles ne s'applique)
    est désormais ajoutée comme dernier moment clé, même sans aucune
    variation matérielle d'au moins 2 points. Constat en test réel : une
    partie perdue par mat en 9 coups (9...Qxh2#) sans la moindre perte de
    matériel ne déclenchait jusque-là aucun moment clé, le coach ne s'en
    sortant que grâce au signe « # » du texte PGN — ce qui n'est plus
    laissé au hasard (calculé mécaniquement avec `board.is_checkmate()`/
    `is_stalemate()`/`is_insufficient_material()`/`is_seventyfive_moves()`/
    `is_fivefold_repetition()`).
- `llm_coach.py` :
  - `get_move_explanations(flagged_moves, camp_alain, config)` — nouveau
    paramètre `camp_alain`. Chaque coup flagué reçoit désormais un champ
    `auteur` déjà calculé (via `game_facts.camp_label`, réutilisé plutôt que
    reduplié) — p. ex. `"Noirs (adversaire)"` — que le prompt système lui
    demande explicitement de recopier tel quel, jamais de redéduire lui-même
    depuis le seul champ `camp`. Le JSON envoyé au coach passe d'une simple
    liste de coups à `{"camp_alain": "blancs"|"noirs"|null, "coups": [...]}}`
    (le format de la réponse attendue, `{"choix": [{"id", "explication"}]}`,
    est inchangé — aucun impact sur la réassociation côté client) ;
  - `_MOVE_SELECTION_SYSTEM_PROMPT` renforcé : un coup dont l'auteur ne
    contient pas « Alain » n'est jamais présenté comme joué par lui ; pour
    l'erreur d'un adversaire, expliquer ce qu'elle offre à Alain plutôt que
    de la commenter comme un coup d'Alain ; si `camp_alain` est `null`, ne
    prêter aucun coup ni à Alain ni à « l'adversaire » (décrire uniquement
    Blancs/Noirs) ; ne jamais nommer une ouverture précise (elle n'est
    jamais fournie dans les données) — décrire la structure sans lui donner
    de nom inventé ;
  - nouvel addendum `_ANALYSE_PARTIE_ADDENDUM`, ajouté par
    `get_coach_response` quand `context.mode_origine == "analyse_partie"`
    (explication à la demande d'un coup unique, `on_analyse_expliquer_coup`) :
    même garde-fou (camp_alain seule source fiable, jamais de nom
    d'ouverture inventé), indépendant et cumulable avec les addenda
    existants (exercice, faits calculés, etc.) ;
  - `_build_context_text` : nouveau cas `camp_alain_inconnu` (distinct de
    l'absence simple de `camp_alain`) — dit explicitement au coach que le
    camp d'Alain a été recherché mais n'a pas pu être déterminé, pour qu'il
    décrive les coups par Blancs/Noirs sans deviner qui est Alain.
- `app.py` :
  - nouvelle fonction `_camp_alain_pour_analyse(data)` : appelle
    `game_facts.camp_alain_from_pgn_headers` sur les champs `white`/`black`
    transmis par le client, et distingue « camp indéterminable » (au moins
    un en-tête transmis, aucun ne correspond à Alain) d'« aucune info
    transmise » ;
  - `on_analyse_choisir_coups_decisifs` et `on_analyse_expliquer_coup`
    l'utilisent pour passer `camp_alain`/`camp_alain_inconnu` au coach.
- `static/board.js` : `reviewWhite`/`reviewBlack` mémorisent les en-têtes
  PGN White/Black de la partie chargée en revue (`parsePgn`), qu'elle vienne
  de la bibliothèque ou du bouton « Analyser cette partie » depuis la
  bannière de fin de partie (pédagogique/ouverture/finales taguent déjà
  leurs en-têtes PGN avec « Alain »/le nom de l'adversaire avant d'appeler
  `analyserPartieDepuisPgn`).
- `static/game_analysis.js` : `demanderExplicationsCoach` et
  `demanderExplicationCoup` transmettent désormais `white`/`black` au
  serveur avec les coups flagués.
- Testé (sans appel API réel — clé API non vérifiée depuis ce worktree,
  cf. rapport de clôture) :
  - PGN de test d'acceptation (1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 ... 18...Qxa4,
    Alain Blancs) : `camp_alain_from_pgn_headers("Alain", "Stockfish")` →
    `"blancs"` ; `build_game_facts_text` étiquette bien 10...Bf8 et
    11...Nxe4 « Noirs (adversaire) » ; aucun nom d'ouverture dans les
    données envoyées au coach (jamais calculé, seulement les coups/camps/
    auteurs) ;
  - PGN de bibliothèque avec en-tête Black = `athanatos123` (Alain aux
    Noirs) : camp déduit `"noirs"` ; avec deux pseudos tiers, camp déduit
    `""` (indéterminable, propagé tel quel) ;
  - partie perdue par mat en 9 coups (matériel intact avant le mat) :
    nouveau moment clé de fin de partie généré mécaniquement, sans dépendre
    du signe « # » du texte PGN.

# Changelog — Issue #55

## Chat coach : bloc de faits calculés (camps, matériel, moments clés) pour ne plus faire relire le PGN au modèle

- Contexte : en usage réel, le chat libre après une partie pédagogique
  abandonnée (Alain Blancs, 18...Qxa4) a attribué à Alain des coups des
  Noirs, inventé un échange de dames inexistant, et manqué l'événement
  décisif (perte de la dame blanche au coup 15, sans reprise possible) —
  le modèle reconstitue mal la partie en relisant lui-même le PGN en texte,
  et l'appli ne lui fournissait jusque-là aucun fait déjà calculé pour ce
  chat (contrairement aux autres modes, déjà ancrés sur des données
  calculées, cf. issues #25/#44).
- `game_facts.py` (nouveau module) : `build_game_facts_text(pgn, camp_alain,
  flagged_moves=None)` calcule mécaniquement, avec python-chess (aucun appel
  à Stockfish, aucun appel API supplémentaire) :
  1. la liste des coups numérotés (`15.`/`15...`) avec le camp explicite de
     chaque coup (« Blancs (Alain) »/« Noirs (adversaire) », ou l'inverse
     selon `camp_alain` — y compris les camps inversés en finales, déjà
     résolus côté client) et le bilan matériel après chaque coup, en points
     classiques, du point de vue d'Alain ;
  2. les « moments clés » : chaque coup où le bilan matériel varie d'au
     moins 2 points, avec qui capture quoi et si une reprise immédiate est
     légale (`board.legal_moves` après le coup — pas une supposition, ce qui
     avait justement fait inventer une reprise impossible dans l'incident
     source) ;
  3. la position actuelle : liste des pièces par camp avec leurs cases
     exactes, FEN, matériel restant, et une ligne explicite dès qu'un camp
     n'a plus de dame ;
  4. si fournis (`flagged_moves`), les coups déjà flagués par une analyse
     mécanique Stockfish faite pendant la session (bouton « Analyser cette
     partie »).
  Repli silencieux (`""`) si le PGN est vide/illisible ou si `camp_alain`
  n'est pas `"blancs"`/`"noirs"` : le chat reste utilisable sans ce bloc.
- `app.py` : nouvelle fonction `_enrich_context_with_game_facts`, appelée
  par le handler `coach_ask` (chat libre) avant `get_coach_response`. N'agit
  que quand le contexte transmis par le client contient à la fois un PGN et
  un `camp_alain` non vide — c'est-à-dire les modes interactifs (partie
  libre, pédagogique, ouverture, finales), jamais la revue de la
  bibliothèque PGN (qui ne transmet pas `camp_alain`, cf. `board.js`) ni le
  mode exercice (déjà ancré sur Stockfish, pas de PGN transmis) ni une
  démonstration Stockfish-contre-Stockfish (`mode_demonstration`, issue
  #29 — aucun camp n'y est réellement « Alain »). Best-effort : une erreur
  de calcul renvoie le contexte inchangé, sans jamais faire échouer la
  réponse du coach.
- `llm_coach.py` : le nouveau champ de contexte `faits_calcules` est
  sérialisé dans `_build_context_text` juste avant le PGN, et déclenche un
  nouvel addendum de prompt système (`_GAME_FACTS_ADDENDUM`, dans
  `get_coach_response`) : appuyer chaque affirmation sur ce bloc et sur le
  PGN, ne jamais citer un coup/une capture/une reprise/une pièce absente de
  ces données, ne jamais attribuer un coup au mauvais camp, dire qu'on n'est
  pas sûr en cas de doute, et commencer par les moments clés pour toute
  question du type « que s'est-il passé ? ». Indépendant des autres
  addenda (exercice/anti-invention/démonstration) : peut se combiner avec
  eux.
- `static/board.js` (`coachBuildContext`) : nouvelle fonction
  `_coachAnalysisFlaggedMoves()` qui rapproche le rapport mécanique de la
  dernière analyse « Analyser cette partie » (`_gameAnalysisResults`,
  `game_analysis.js`, qui reste en mémoire tant que la page n'est pas
  rechargée) de la partie réellement en cours dans le mode interactif actif
  — coup à coup, même longueur et mêmes SAN dans le même ordre — pour
  éviter de transmettre par erreur l'analyse d'une autre partie. Ajouté au
  contexte (`analyse_mecanique_flags`) uniquement pour les modes qui
  transmettent déjà l'historique (`avecHistorique` : libre/pédagogique/
  ouverture/finales).
- Non modifié, volontairement hors périmètre de l'issue : le mode exercice
  (déjà ancré sur Stockfish) et la revue de parties importées de la
  bibliothèque.

### Vérifications faites

- Rejeu exact du PGN de test de l'issue (Alain Blancs, partie abandonnée
  après 18...Qxa4) via `game_facts.build_game_facts_text` : le bloc généré
  signale bien, au coup `15... Qxd1+`, la capture de la dame blanche par
  les Noirs (adversaire) sans reprise possible (variation de 9 points), une
  position finale sans dame blanche, la dame noire en a4, et un matériel de
  24 (Alain) contre 32 (adversaire) — exactement les valeurs attendues par
  le test d'acceptation.
- Contrôle croisé indépendant du matériel final avec un rejeu manuel du même
  PGN en python-chess (script ad hoc, hors du dépôt) : mêmes totaux (24/32),
  même case pour la dame noire (a4), mêmes deux camps sans doublon de pièces.
- `_enrich_context_with_game_facts` (`app.py`) testé directement (venv de
  test hors dépôt, `python-chess`/`Flask`/`Flask-SocketIO` installés
  temporairement) : ajoute bien `faits_calcules` quand `pgn`+`camp_alain`
  sont présents, renvoie le contexte inchangé si `camp_alain` est absent
  (cas de la revue bibliothèque) ou si `mode_exercice` est vrai.
- Pipeline complet `llm_coach.get_coach_response` testé avec `_call_claude`
  intercepté (pas d'appel réseau) : le system prompt final contient bien
  l'addendum `_GAME_FACTS_ADDENDUM` et le bloc de faits calculés, y compris
  la ligne du moment clé du coup 15.
- Cas d'une position de départ non standard (`[SetUp "1"]`/`[FEN ...]`,
  scénario des modes finales/ouverture) : `chess.pgn.read_game` respecte
  bien ces en-têtes (confirmé aussi côté client : `chess.js` les pose
  automatiquement dès que la position de départ diffère de la position
  standard, `static/vendor/chess.js/chess.min.js`), le bloc généré reflète
  la bonne position de départ.
- `py_compile` sur `app.py`/`llm_coach.py`/`game_facts.py` : OK. `node
  --check` sur `static/board.js` : OK.

### Limites

- **Aucun vrai appel à l'API Claude n'a pu être fait** : aucune
  `ANTHROPIC_API_KEY` n'est présente dans l'environnement de ce worktree et
  le `.env` n'a pas été touché (consigne explicite). La vérification s'est
  donc arrêtée au contenu exact du contexte construit et du system prompt
  assemblé (voir ci-dessus), pas à la réponse réelle du coach en conditions
  réelles — à confirmer par Alain en usage réel sur ce cas précis.
- Le rapprochement de l'analyse mécanique à la partie en cours (point 4,
  `_coachAnalysisFlaggedMoves`) est fait par comparaison exacte des SAN —
  toute divergence (partie reprise différemment, coup annulé/rejoué) fait
  disparaître silencieusement les coups flagués du contexte plutôt que de
  risquer un rapprochement erroné ; ce choix n'a pas été testé en conditions
  réelles d'interface (pas de navigateur disponible dans ce worktree).
- « Reprise possible » est calculé comme « un coup légal peut reprendre
  immédiatement sur cette case », ce qui couvre le cas de l'incident source
  (fou c1 bloquant la tour a1) mais ne distingue pas une reprise possible
  mais désavantageuse d'une reprise réellement favorable — hors périmètre
  de la tâche demandée (faits, pas jugement).

# Changelog — Issue #54

## Compteur discret de tokens consommés dans l'en-tête (sans notion de prix)

- Contexte : le solde restant de la clé API n'est pas lisible par
  programme (uniquement sur la Console) et Alain préfère ne pas maintenir
  de table de prix par modèle côté ChessCoach — décision explicite :
  afficher uniquement des tokens bruts, sans aucun prix ni équivalent en
  argent.
- `llm_coach.py` (`_call_claude`) : relève `usage.input_tokens` /
  `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens`
  depuis la réponse de chaque appel réussi à l'API — aucun appel
  supplémentaire, ces informations sont déjà présentes dans la réponse
  normale. Cumulés par modèle réellement utilisé (`data["model"]` de la
  réponse, pas le paramètre d'entrée qui peut être un alias ou vide) dans
  `data/usage_tokens.json` (nouveau `config.USAGE_TOKENS_PATH`, sous
  `DATA_DIR`, donc gitignoré comme le reste de `data/`) via
  `_record_usage`/`_save_usage`/`load_usage`/`get_usage_summary`/
  `reset_usage`. Le fichier garde une date de départ du cumul et le détail
  du dernier appel ; il survit à un redémarrage de l'appli.
  Tous les chemins d'appel sont couverts (`get_coach_response`,
  `get_move_explanations`, `get_opening_moves`, `get_training_program`) —
  donc chat du coach, explications de coups, programme d'entraînement, et
  commentaires des modes ouverture/finales/pédagogique/exercice, tous
  branchés sur `_call_claude`.
- `app.py` : nouveaux handlers SocketIO `usage_get` (demande explicite du
  compteur, utilisé au chargement de la page) et `usage_reset` (remise à
  zéro, bouton discret de l'en-tête). `_emit_usage_update()` pousse le
  compteur à jour après chaque appel au coach (succès ou échec). Rendu
  initial fait côté serveur dans `index()` (`usage_summary`) pour éviter
  un flash "—" avant la première connexion Socket.IO.
- `templates/index.html` / `static/usage_tokens.js` (nouveau fichier) :
  widget discret `#usage-tokens-widget` près du lien "Coût API" existant —
  tokens du dernier appel et total cumulé depuis la date de départ
  (entrée/sortie séparées), détail par modèle au survol (desktop) ou au
  tap (tactile, bascule de classe CSS). Sur écran étroit (media query
  `max-width: 900px`), le texte bascule vers une forme compacte
  (`Σ … in / … out`). Bouton "Remettre le compteur à zéro" dans le détail,
  avec confirmation `confirm()` légère.
  - Bug trouvé et corrigé en testant au rendu réel (Playwright, viewport
    390×844) : le panneau de détail, positionné en `absolute` par rapport
    au widget, débordait d'environ 100 px hors du viewport sur mobile
    dès que le widget se trouvait excentré dans l'en-tête (le titre passe
    sur 3 lignes à cette largeur, ce qui déplace tout le groupe). Corrigé
    en passant `#usage-detail` en `position: fixed` avec des marges liées
    au viewport (`left/right: 8px`) sous 900 px, et en calculant sa
    position verticale (`top`) en JS à l'ouverture (`usage_tokens.js`) —
    `position: fixed` ne peut pas hériter d'un ancrage type
    `top: 100% du parent` comme `absolute`. Texte du détail passé en
    `white-space: normal` (au lieu de `nowrap`) sous 900 px pour permettre
    le retour à la ligne.
- `llm_coach.py` (`_call_claude`) : nouvelle exception
  `CreditInsuffisantError`, levée quand l'API répond HTTP 403 avec
  `error.type == "billing_error"` (distingué de `permission_error`, qui
  partage le même code HTTP mais désigne une clé sans les droits
  nécessaires — testé explicitement pour ne pas confondre les deux).
  Toutes les fonctions publiques (`get_coach_response`,
  `get_move_explanations`, `get_opening_moves`, `get_training_program`)
  la rattrapent et renvoient `error: "credit_insuffisant"` au lieu de la
  chaîne d'erreur technique brute.
- `static/board.js` (nouvelle fonction `_coachRenderCreditInsuffisant`),
  `static/exercise.js`, `static/finales.js`, `static/opening.js`,
  `static/pedagogic.js`, `static/game_analysis.js` : sur
  `error === "credit_insuffisant"`, message clair dans le chat (ou message
  inline selon le mode) avec un lien vers la Console pour recharger, au
  lieu d'une erreur technique générique.
- `llm_coach.py` (`_log_coach_call`) : nouveau champ `usage` dans chaque
  entrée de `data/logs/coach_calls.log` (tokens de cet appel précis, ou
  `null` si l'appel n'a pas abouti), en complément du compteur cumulé.
- `CONTEXTE.md` : nouvelle section documentant le fonctionnement du
  compteur et l'emplacement des données (`data/usage_tokens.json`).

## Tests réalisés

Tests faits sur l'instance réelle d'Alain (port 5000, jamais touchée) :
aucun. Tout ce qui suit tourne sur une instance de test isolée (processus
Flask/SocketIO séparé, port différent, `config.DATA_DIR` redirigé vers un
dossier `/tmp` dédié — jamais `~/ChessCoach/data`), avec l'appel HTTP à
l'API Claude (`urllib.request.urlopen`) simulé (pas de vrai appel API
fait — clé API réelle non nécessaire, `.env` non touché).

- Logique de cumul (`llm_coach.py`) testée directement : réponses d'API
  simulées avec `usage` (deux modèles différents), vérification du cumul
  par modèle et des totaux, `reset_usage` (date de départ ré-initialisée,
  compteurs à 0), distinction `billing_error` (403) vs `permission_error`
  (403, ne doit PAS lever `CreditInsuffisantError`), champ `usage` bien
  écrit dans `coach_calls.log`.
- Bout en bout via un navigateur piloté par Playwright (Chromium, contre
  l'appli Flask/SocketIO réelle tournant en local sur un port de test) :
  - Rendu desktop (1280×900) : widget affichant "Dernier appel" et
    "Total depuis le [date]", détail par modèle au survol.
  - Rendu mobile (390×844) : forme compacte (`Σ … in / … out`), détail au
    tap, **aucun débordement horizontal** (`document.documentElement.
    scrollWidth === window.innerWidth`, vérifié avant et après le bugfix
    ci-dessus).
  - Question envoyée dans le chat du coach (réponse API simulée avec
    usage) : widget mis à jour en direct avec les tokens du nouvel appel.
  - Clic sur "Remettre le compteur à zéro" avec confirmation acceptée :
    compteur à 0, nouvelle date de départ.
  - Simulation d'une réponse HTTP 403 `billing_error` : bulle dédiée dans
    le chat ("Le crédit de l'API Claude est épuisé…") avec lien
    "Recharger sur la Console", au lieu d'une erreur technique.
  - **Persistance après redémarrage** : le processus de test a été
    entièrement arrêté puis relancé (nouveau processus Python, même
    dossier de données sur disque, sans ré-injecter de données) — le
    total cumulé affiché après redémarrage correspond exactement à celui
    d'avant l'arrêt.
- `python3 -m py_compile app.py config.py llm_coach.py` : OK.

Aucun test n'a modifié `.env` ni les données réelles d'Alain
(`~/ChessCoach/data`) ; aucun `git push`.

# Changelog — Issue #53

## Chat coach : afficher le début de la nouvelle réponse, pas sa fin

- Constat : à l'arrivée de chaque bulle (message d'Alain ou réponse du
  coach), `_coachRenderBubble()` (static/board.js) faisait systématiquement
  `history.scrollTop = history.scrollHeight`, donc défilait tout en bas.
  Pour une réponse longue, Alain voyait la fin du message et devait
  remonter pour lire le début — particulièrement gênant sur GSM où
  `.coach-drawer` est plafonné à `55vh` (templates/index.html, media query
  `max-width: 900px`, issue #50).
- `static/board.js` (`_coachRenderBubble`) : comportement désormais
  différencié selon le rôle de la bulle ajoutée.
  - `role === "user"` (message envoyé par Alain) : comportement inchangé,
    défilement tout en bas (`history.scrollTop = history.scrollHeight`).
  - `role === "assistant"` (réponse du coach) : défilement calé sur le
    HAUT de la nouvelle bulle plutôt que sur le bas de la zone, via
    `history.scrollTop += bubbleRect.top - historyRect.top` (delta entre
    les rectangles `getBoundingClientRect()` de la bulle et de la zone de
    défilement). Le message d'Alain qui précède peut sortir de la zone
    (comportement accepté par la demande).
  - `getBoundingClientRect()` plutôt que `bubble.offsetTop` : `#coach-history`
    n'a pas de `position` définie en CSS, donc ses enfants n'ont pas cette
    div comme `offsetParent` — le navigateur remonte jusqu'à `<body>`, ce
    qui aurait rendu `offsetTop` complètement faux pour ce calcul (repéré
    en testant l'implémentation initiale, corrigé avant commit).
  - Cas d'une réponse courte qui tient entièrement dans la zone : le
    navigateur borne nativement `scrollTop` à sa valeur maximale
    (`scrollHeight - clientHeight`), ce qui revient exactement à l'ancien
    comportement (tout en bas) et affiche la réponse en entier sans zone
    vide — aucun cas particulier à coder.
  - S'applique aussi aux réponses du coach déclenchées hors `coachSend()`
    (bouton "Demander l'avis du coach", `coach_on_demand_response`), qui
    passent par la même fonction `_coachRenderBubble("assistant", ...)`.

## Tests réalisés

Le backend (Flask/SocketIO, appel API Claude réel) n'a pas été lancé — test
ciblé sur le comportement de défilement, via une page HTML autonome jetable
(non committée) chargeant le vrai `static/board.css` + `static/board.js` et
reproduisant la structure DOM réelle du panneau coach (`#coach-history`,
`.coach-drawer`, media query `55vh` sous 900px), servie en local et pilotée
par Playwright (Chromium headless) pour simuler l'arrivée d'une bulle
utilisateur puis d'une bulle coach (courte et longue), aux deux résolutions
demandées :

- Mobile (390 × 844, `.coach-drawer` borné à `55vh` ⇒ ~329px de hauteur
  utile pour `#coach-history`) :
  - Réponse longue (~1300 caractères) : le haut de la bulle coach arrive
    en haut de la zone (`scrollTop` == position du haut de la bulle dans
    le contenu défilable) ; le message d'Alain qui précède est sorti de la
    zone visible, conforme à la demande.
  - Réponse courte (une phrase) : `scrollTop` reste à 0 (borné par le
    navigateur), la bulle est entièrement visible sans espace vide.
- Desktop (1440 × 900, pas de contrainte `55vh`, `.coach-drawer` limité à
  `calc(100vh - 60px)`) : mêmes vérifications, mêmes résultats — début de
  réponse visible en haut pour la réponse longue, réponse courte
  entièrement visible. Rendu CSS desktop non modifié (aucune règle CSS
  touchée par ce correctif, uniquement `static/board.js`).
- Message envoyé par Alain (`role: "user"`) : vérifié inchangé aux deux
  résolutions — défilement tout en bas après ajout de sa bulle, dans les
  deux scénarios ci-dessus.

`node --check static/board.js` : syntaxe JS valide.

# Changelog — Issue #52

## Conserve la partie affichée après « Abandonner » pour pouvoir en discuter avec le coach

- Constat : dans les modes partie libre / pédagogique / ouverture / finales,
  cliquer sur « Abandonner » remettait immédiatement le plateau à la
  position de départ (`resetBoardToNeutral()`, `activeMode` remis à `null`).
  Le chat libre sollicité juste après ne recevait donc plus que la FEN de
  départ et un PGN vide — constaté en usage réel sur le GSM (journal
  `coach_calls.log` : FEN de départ, PGN vide, réponse du coach « il n'y a
  pas encore de coup joué »).
- `static/free_play.js` / `static/pedagogic.js` / `static/opening.js` /
  `static/finales.js` (`abandonFreeGame`/`abandonPedagogicGame`/
  `abandonOpeningGame`/`abandonFinaleGame`) : « Abandonner » ne réinitialise
  plus le plateau ni `activeMode` — il fige la position atteinte (nouveaux
  drapeaux `freeGameOver`/`pedagogicGameOver` déjà existant réutilisé/
  `openingGameOver`/`finaleGameOver` mis à `true`, `*Abandonne` nouveau pour
  distinguer explicitement l'abandon d'une fin par mat/pat/nulle), bloque
  les coups suivants (guards déjà en place sur `*GameOver` dans
  `onFreePlayBoardClick`/`onPedagogicBoardClick`/`onOpeningBoardClick`/
  `onFinaleBoardClick`, réutilisés tels quels) et affiche le bandeau de fin
  de partie (`showGameOverBanner`, « défaite » pour les modes à camp
  identifié, message neutre en partie libre) avec le bouton « Analyser
  cette partie » (`analyserPartieDepuisPgn`, déjà utilisé pour les fins par
  mat) — même mécanique que les autres fins de partie, pas de nouveau
  chemin de code.
- `static/board.js` (`coachBuildContext`) : l'historique des coups
  (pgn/move, déjà transmis en pédagogique/ouverture/finales depuis
  l'issue #33) est étendu au mode partie libre — c'était le seul des
  quatre modes concernés par cette issue à en être privé. Nouveau champ
  `abandonne` lu depuis `activeModeGameState()` (`static/controls.js`,
  nouvelle fonction `_activeModeAbandoned()`) ; quand vrai, le contexte
  envoyé au coach porte `partie_terminee: true` et `resultat_partie`
  explicite.
- `llm_coach.py` (`_build_context_text`) : nouveau paragraphe explicite
  dans le contexte envoyé à Claude quand `partie_terminee` est vrai —
  précise qu'Alain ne jouera plus de coup dans cette partie et instruit le
  coach de répondre à partir du PGN complet plutôt que de nier qu'un coup
  ait été joué.
- Le plateau ne redevient vierge qu'au démarrage explicite d'une nouvelle
  partie (chaque `start*Game*`, qui réinitialise les drapeaux `*GameOver`/
  `*Abandonne`) ou à un changement de mode (`ensureModeSwitchClean`,
  inchangé — appelle toujours la fonction `abandon*` du mode quitté pour
  nettoyer l'état serveur, mais celle-ci ne fait plus rien si la partie
  était déjà terminée).
- Vérification : impossible de déclencher un vrai appel API Claude depuis
  ce worktree (pas de `.env`, `ANTHROPIC_API_KEY` absente de
  l'environnement — `DATA_DIR`/`coach_calls.log` pointent d'ailleurs vers
  `~/ChessCoach/data`, hors périmètre de ce worktree). Vérifié à la place :
  (1) simulation Node (chargement réel de `controls.js`/`free_play.js`/
  `pedagogic.js`/`coachBuildContext` dans un contexte `vm`, parties jouées
  via chess.js) confirmant qu'après abandon en mode libre et en mode
  pédagogique, `coachBuildContext()` renvoie bien le PGN complet,
  `partie_terminee: true`, `resultat_partie` mentionnant l'abandon, et que
  `resetBoardToNeutral()`/coups suivants restent bloqués ; (2) appel direct
  de `llm_coach.get_coach_response()` avec `_call_claude` monkeypatché
  (aucune requête réseau réelle, conforme à RESEAU=non) confirmant que
  `_log_coach_call` écrit bien le PGN complet et `partie_terminee: true`
  dans l'entrée journalisée (le format et l'emplacement du log,
  `data/logs/coach_calls.log` sous `DATA_DIR`, sont inchangés par ce
  correctif). `python3 -m py_compile` et `node --check` OK sur tous les
  fichiers modifiés.

# Changelog — Issue #51

## Désactivation du mode debug Flask (écoute sur 0.0.0.0 depuis l'issue #49)

- Constat : `socketio.run(...)` (app.py, démarrage) passait `debug=True` en
  dur alors que l'appli écoute sur toutes les interfaces (`0.0.0.0:5000`,
  issue #49) derrière `_FiltreAccesDistant`. Le débogueur interactif
  Werkzeug (console web, protégée seulement par un code PIN) peut être servi
  avant ce filtre WSGI, donc potentiellement joignable depuis le réseau
  local ou un wifi public — inacceptable pour une appli détenant la clé API
  Claude et des données personnelles.
- `config.py` : nouvelle variable `DEBUG_DEV`, lue depuis la variable
  d'environnement `CHESSCOACH_DEBUG_DEV` (`"1"` pour l'activer), `False` par
  défaut.
- `app.py` (bloc `if __name__ == "__main__":`) :
  - `debug=config.DEBUG_DEV` et `use_reloader=config.DEBUG_DEV` au lieu de
    `debug=True` en dur — désactive aussi le rechargement automatique du
    code par défaut.
  - `host` devient conditionnel : `127.0.0.1` si `DEBUG_DEV` est actif,
    `0.0.0.0` sinon (comportement inchangé pour l'usage normal via
    Tailscale). Le débogueur ne peut donc jamais être actif en même temps
    qu'une écoute ouverte sur les autres interfaces.
  - Port 5000, `allow_unsafe_werkzeug=True` et `_FiltreAccesDistant`
    inchangés.
- `CONTEXTE.md` : section « Accès distant » mise à jour — mention explicite
  qu'après une modification du code il faut désormais relancer le coach à la
  main (plus de rechargement automatique), et documentation de
  `CHESSCOACH_DEBUG_DEV=1` pour le développement local.
- Vérifications effectuées (venv temporaire jetable dans `/tmp`, `.env` non
  touché, port 5000 libéré après coup) :
  - Par défaut : log Werkzeug `Debug mode: off`, écoute confirmée sur
    `0.0.0.0:5000`, `GET /` renvoie 200 (page normale), et une requête vers
    la ressource du débogueur
    (`/?__debugger__=yes&cmd=resource&f=debugger.js`) renvoie la page HTML
    normale de l'appli (`Content-Type: text/html`) au lieu de la ressource
    JS du débogueur — la console n'est donc plus servie du tout (le
    middleware `DebuggedApplication` n'est même pas monté).
  - Avec `CHESSCOACH_DEBUG_DEV=1` : log `Debug mode: on`, `Debugger is
    active!` + PIN affiché, rechargeur actif (`Restarting with stat`),
    écoute confirmée **uniquement** sur `127.0.0.1:5000` (absente de
    `0.0.0.0`), et la même requête de ressource renvoie bien
    `Content-Type: text/javascript` (débogueur actif comme attendu en
    développement local).
- Aucune modification du filtre d'accès distant, du port, du mécanisme
  Tailscale ni de `.env`.

# Changelog — Issue #50

## Interface adaptée au GSM (affichage vertical, déplacement des pièces au toucher)

- Constat : aucune balise viewport dans `templates/index.html` — un mobile
  rendait donc la page comme un "layout viewport" de 980px puis la réduisait
  à l'échelle (plateau minuscule, zoom nécessaire pour jouer). La mise en
  page était par ailleurs figée en colonnes fixes (620/240/420/480px) sans
  aucune adaptation aux écrans étroits.
- `templates/index.html` :
  - Ajout de `<meta name="viewport" content="width=device-width,
    initial-scale=1, maximum-scale=1, viewport-fit=cover">`.
  - Nouvelle règle `@media (max-width: 900px)` (aucun effet au-dessus de ce
    seuil, vérifié par capture d'écran diff pixel-à-pixel à 1440px —
    strictement identique avant/après) :
    - `#app` passe en colonne unique (`flex-direction: column`) ; les 4
      colonnes (`#board-column`, `#coach-column`, `#mode-tabs-column`,
      `#historique-column`) passent à `width:100%` et sont réordonnées via
      `order` : plateau, puis chat du coach, puis onglets de mode, puis
      historique des coups (secondaire sur GSM) en dernier.
    - `--bd-size` (taille du plateau, définie dans `board.css`) reçoit une
      borne supplémentaire `calc(100vw - 92px)` pour tenir compte de la
      largeur écran disponible (auparavant seulement `min(70vh, 560px)`,
      indépendant de la largeur — débordait horizontalement sur un
      téléphone en portrait).
    - `.coach-drawer` : `max-height` réduit à `55vh` (au lieu de
      `calc(100vh - 60px)`) pour garder plateau + chat visibles ensemble
      sans trop défiler, comme souhaité par Alain.
    - `.mode-tab-bar` : défilement horizontal (`overflow-x:auto;
      flex-wrap:nowrap`) plutôt que retour à la ligne, comme demandé.
    - `#review-controls` : `flex-wrap:wrap` ajouté (sans quoi la rangée de 5
      boutons Précédent/Suivant/Retourner/Meilleur coup/Extraire le FEN
      dépassait la largeur de l'écran et provoquait un défilement horizontal
      de toute la page).
    - Cibles tactiles agrandies (`button`/`.mode-tab-btn` : `min-height:
      44px`) et police des champs de saisie forcée à `16px` (empêche le
      zoom automatique au focus sur iOS Safari).
- `static/board.css` : `touch-action: manipulation` ajouté sur `.square`
  (neutralise le double-tap-zoom pendant la séquence des deux taps du
  déplacement tactile ; sans effet visuel, donc neutre pour la souris).
- **Déplacement des pièces au toucher** : déjà entièrement fonctionnel sans
  changement de code JS — les 5 modes interactifs visés (partie libre,
  pédagogique, ouverture, finales, exercices) utilisent tous le même
  gestionnaire `boardEl.onclick = on<Mode>BoardClick`, avec le même schéma
  "tap sur la pièce à déplacer puis tap sur la case d'arrivée" que demandé
  dans l'issue — un tap génère un `click` DOM standard, déjà pris en charge
  par ce code. Le point bloquant était uniquement l'absence de balise
  viewport (rendait le plateau minuscule) et le manque de mise en page
  adaptée, tous deux corrigés ci-dessus.
- Note : le mode "Éditeur de position" utilise du drag-and-drop HTML5
  (`draggable`/`ondragstart`/`ondrop`) pour la palette de pièces, non
  compatible tactile — mais ce mode n'est pas dans la liste des 5 modes visés
  par l'issue, donc hors périmètre ici (limite connue, à traiter séparément
  si besoin).
- Vérification (Playwright, Chromium headless, serveur Flask lancé avec un
  `HOME` de test isolé sous le worktree pour ne pas toucher aux données
  réelles sous `~/ChessCoach/data`) :
  - Desktop 1440px : diff pixel-à-pixel avant/après = aucune différence.
  - Bascule de mise en page vérifiée exactement au seuil : 899px → colonne
    unique, 901px → mise en page desktop (`#app` `flex-direction`).
  - Mobile 390×844 (émulation tactile, `has_touch=True`) : aucun débordement
    horizontal de la page (`scrollWidth === clientWidth === 390`), barre
    d'onglets bien scrollable horizontalement (`scrollWidth` 963px pour un
    `clientWidth` de 356px).
  - Déplacement tactile testé avec deux taps successifs (`locator.tap()`) :
    - Mode "Partie libre" : coup e2-e4 joué avec succès (case de départ
      vidée, pion visible en e4, statut passé à "Trait aux Noirs").
    - Mode "Partie pédagogique" (Blancs) : coup d2-d4 joué avec succès,
      réponse automatique de Stockfish (d7-d5) reçue et affichée.
    - Les 3 autres modes visés (ouverture, finales, exercices) partagent
      strictement le même gestionnaire de clic sur case
      (`sqEl = e.target.closest(".square")` puis
      sélection/déplacement identiques) — non exécutés en bout en bout ici
      faute de données de test (livre d'ouverture, tables Syzygy, historique
      d'erreurs, tous gitignorés et absents de l'environnement de test
      isolé), mais le mécanisme est identique à celui validé sur les deux
      modes testés.
- Limites connues :
  - Éditeur de position non adapté au tactile (drag-and-drop HTML5, hors
    périmètre de l'issue).
  - Pas de test sur un appareil physique réel — seulement émulation
    Playwright/Chromium (viewport + événements tactiles synthétiques).
  - Le zoom pincé (pinch-to-zoom) volontaire reste possible
    (`maximum-scale=1` limite mais ne bloque pas totalement selon les
    navigateurs) ; seul le double-tap-zoom accidentel est neutralisé via
    `touch-action: manipulation`, choix délibéré pour ne pas sacrifier
    l'accessibilité (zoom volontaire toujours possible pour lire un texte
    petit) — bon compromis pratique pour rester conforme aux bonnes
    pratiques mobiles actuelles.

# Changelog — Issue #49

## Accès distant via Tailscale, restreint à la machine locale et au réseau Tailscale

- Contexte : Alain veut ouvrir le coach depuis son GSM via Tailscale (déjà
  installé et connecté des deux côtés). L'appli est strictement personnelle
  (parties, mémoire du coach, clé API) et n'a aucun mot de passe : elle ne
  doit donc jamais être joignable par quelqu'un d'autre.
- `app.py` : le serveur écoute désormais sur toutes les interfaces
  (`socketio.run(app, host="0.0.0.0", port=5000, ...)`, avant : bind
  implicite à `127.0.0.1` uniquement), mais un middleware WSGI
  (`_FiltreAccesDistant`, posé devant `app.wsgi_app` — donc devant les
  routes Flask ET le handshake Socket.IO, puisque flask_socketio remplace
  lui-même `app.wsgi_app`) n'accepte que `127.0.0.1`/`::1` et la plage
  Tailscale `100.64.0.0/10` ; toute autre adresse (LAN, wifi public) reçoit
  un `403 Forbidden` explicite avant d'atteindre la moindre route.
- Chat temps réel (Socket.IO) : aucune configuration CORS explicite
  nécessaire. La vérification d'origine par défaut de python-socketio
  (`cors_allowed_origins=None`) compare l'en-tête `Origin` du navigateur au
  `Host` de la requête — elle s'aligne donc automatiquement sur l'adresse
  utilisée pour ouvrir l'appli (locale ou Tailscale), et rejette avec un
  `400 "Not an accepted origin."` toute origine tierce (vérifié par test
  manuel, cf. rapport de clôture de l'issue).
- `CONTEXTE.md` : section ajoutée expliquant l'adresse à utiliser depuis le
  GSM (`http://100.92.48.81:5000`, adresse Tailscale du ThinkPad
  thinkpadcarbon7) et le mécanisme de filtrage.
- Rien ne change côté ThinkPad : l'alias `coach` continue d'ouvrir le
  navigateur en local (127.0.0.1 reste dans la liste blanche), même port
  5000 qu'avant.
- Non touché : `.env`, clé API Claude.

# Changelog — Issue #48

## Panneau Coach trop étroit et texte trop petit

- Constat (capture d'écran d'Alain) : sur un écran classique, `#coach-column`
  (largeur fixe 320px) laissait un espace vide important à droite de la
  page (~240px sur un viewport 1920px), alors que le texte des réponses du
  coach (`#coach-history`, réponses souvent longues — analyse de partie
  complète) était rendu en 0.85rem, inconfortable à lire.
- `templates/index.html` : largeur de `#coach-column` portée de `320px` à
  `480px` (+160px, absorbe l'essentiel de l'espace vide constaté sans
  toucher aux largeurs de `#board-column` (620px), `#historique-column`
  (240px) ni `#mode-tabs-column` (420px), qui restent inchangées).
- `static/board.js`, fonction `_coachRenderBubble` : taille de police des
  bulles de réponse (utilisateur et coach) portée de `0.85rem` à `1.05rem`,
  avec `line-height:1.45` ajouté pour l'aération du texte sur les réponses
  longues.
- Vérification via navigateur headless (Playwright) : captures avant/après
  à 1920×1080 confirmant l'élargissement du panneau (320→480px, coin droit
  passant de x=1664 à x=1824, toujours dans le viewport) et
  l'agrandissement du texte des bulles (13.6px → 16.8px). Vérifié aussi à
  1440×900 : le passage à la ligne (`flex-wrap`) du panneau Coach sous les
  autres colonnes existait déjà avant la modification à cette largeur (la
  somme des largeurs fixes dépassait déjà 1440px) — seul le seuil de wrap
  se déplace légèrement, pas de régression introduite.

## Chat libre — réponse vide (bloc thinking seul, sans texte) sur claude-sonnet-5

- Cause confirmée (documentation officielle de l'API Messages) : `_call_claude`
  (`llm_coach.py`) omettait le paramètre `thinking` dans le corps de la
  requête. Sur `claude-haiku-4-5`, cela ne change rien (Haiku ne raisonne
  jamais). Sur `claude-sonnet-5` (modèle d'Alain via
  `CHESSCOACH_LLM_MODEL`), omettre `thinking` active le raisonnement
  adaptatif *par défaut* — contrairement aux modèles Opus 4.7/4.8, où
  l'omettre désactive la réflexion. Ce raisonnement consomme une partie du
  budget `max_tokens` (2048) avant même de commencer à écrire la réponse ;
  sur une question simple, il pouvait consommer la totalité du budget et
  s'arrêter (`stop_reason: "max_tokens"`) après un unique bloc
  `{"type": "thinking", "thinking": ""}`, sans aucun bloc `text` — l'erreur
  observée par Alain (`"Aucun bloc de type 'text' dans la réponse Claude"`),
  levée par le parsing robuste ajouté en issue #46 (qui reste nécessaire et
  n'a pas été modifié).
- `llm_coach.py`, fonction `_call_claude` :
  - Ajout de `"thinking": {"type": "disabled"}` dans le corps de la requête
    — désactive explicitement le raisonnement adaptatif plutôt que de
    simplement lui laisser plus de budget, ce qui élimine la classe de
    problème à la racine (option demandée en priorité par l'issue). Un
    commentaire de coach aux échecs n'a pas besoin d'exposer un raisonnement
    séparé de la réponse ; Haiku, utilisé jusqu'à l'issue #44 pour le même
    usage, ne raisonnait jamais et convenait déjà — pas de régression de
    qualité attendue par rapport au comportement déjà validé.
  - `max_tokens` porté de 2048 à 4096 en complément (deuxième option
    demandée par l'issue), pour laisser une marge large même si un futur
    changement de modèle ou d'API réintroduisait un raisonnement consommant
    une partie du budget.
- Commentaires mis à jour en conséquence (rationale du budget de tokens et
  de la recherche défensive du bloc `text`, qui reste utile même avec
  `thinking` désactivé — au cas où l'API renverrait tout de même un bloc
  `thinking` vide).
- Hors périmètre respecté : aucune modification du parsing du bloc `text`
  ajouté par l'issue #46.
- Vérification : `python3 -m py_compile llm_coach.py` → OK. Simulation
  locale de `urllib.request.urlopen` (aucun appel réseau réel) confirmant
  que le corps de requête envoyé contient bien `"thinking": {"type":
  "disabled"}` et `"max_tokens": 4096`, et que la réponse texte est
  correctement extraite même en présence d'un bloc `thinking` vide en tête
  de `content`.
- **Vérification navigateur headless avec appel API réel demandée par
  l'issue : non effectuée.** Aucune `ANTHROPIC_API_KEY` n'est accessible
  dans le périmètre strict de ce worktree (`/home/alain/chesscoach-issue47`)
  — la clé réelle vit dans `~/ChessCoach/.env`, hors périmètre, et je n'ai
  pas le droit d'y accéder même si la tâche le demande explicitement (même
  limitation déjà rencontrée et documentée en issue #46). Alain devra
  confirmer par un échange réel dans l'interface, avec `claude-sonnet-5`
  configuré, qu'une réponse textuelle réelle est bien reçue en chat libre.

# Changelog — Issue #46

## Chat libre — KeyError('text') lors du parsing de la réponse API, apparu après le passage à Sonnet

- Diagnostic : impossible de retrouver l'entrée réelle dans
  `data/logs/coach_calls.log` — ce fichier vit sous `DATA_DIR`
  (`~/ChessCoach/data/logs/`), hors du périmètre strict de ce worktree
  (`/home/alain/chesscoach-issue46`). Le diagnostic s'appuie donc sur la
  documentation officielle de l'API Messages (comportement confirmé,
  non supposé) : sur `claude-sonnet-5`, quand le paramètre `thinking` est
  omis de la requête, le raisonnement adaptatif s'exécute *par défaut* et
  produit un bloc `{"type": "thinking", ...}` dans la liste `content` de la
  réponse — potentiellement avant le bloc `{"type": "text", ...}`. Sur
  Haiku, qui ne pense jamais, `content[0]` est toujours le bloc texte. La
  requête construite dans `_call_claude` (`llm_coach.py`) n'a jamais fixé le
  paramètre `thinking`, donc ce comportement s'active silencieusement dès
  que `CHESSCOACH_LLM_MODEL=claude-sonnet-5` (config d'Alain).
- `llm_coach.py`, fonction `_call_claude` (ligne ~637) : remplace
  `return data["content"][0]["text"]` (suppose une position fixe) par une
  itération sur `data["content"]` qui retourne le premier bloc dont
  `"type" == "text"`, quelle que soit sa position dans la liste. Lève une
  `ValueError` explicite si aucun bloc texte n'est trouvé (au lieu d'un
  `KeyError`/`IndexError` opaque).
- Hors périmètre respecté : aucune modification du paramètre `thinking`
  côté requête — uniquement le parsing de la réponse, comme demandé.
- Vérification fonctionnelle (aucune `ANTHROPIC_API_KEY` disponible dans
  l'environnement de cette session, et le module `anthropic` n'est pas
  installé — un vrai appel réseau à `claude-sonnet-5` n'a donc pas pu être
  effectué depuis ce worktree) : simulation de `urllib.request.urlopen` avec
  les deux formes de réponse possibles — (1) bloc `text` seul en position 0
  (forme Haiku historique) et (2) bloc `thinking` en position 0 suivi du
  bloc `text` en position 1 (forme Sonnet 5 à l'origine du bug) — confirme
  que `_call_claude` retourne le bon texte dans les deux cas, alors que
  l'ancien code levait `KeyError('text')` sur le cas (2). Alain devra
  confirmer par un échange réel dans l'interface avec `claude-sonnet-5`
  configuré.

# Changelog — Issue #45

## Chat libre — timeout de lecture sur l'appel API Claude

- `llm_coach.py` : le timeout HTTP de l'appel à l'API Claude dans
  `_call_claude` était codé en dur à 15s (`urllib.request.urlopen(req,
  timeout=15)`), devenu insuffisant avec un contexte volumineux
  systématiquement transmis (PGN complet + mémoire de progression complète :
  patterns_erreurs, repertoire_ouvertures, objectifs_courants) et depuis le
  passage de `CHESSCOACH_LLM_MODEL` à claude-sonnet-5. Provoquait "the read
  operation timed out" même sur une question triviale ("dis bonjour") en
  mode Bibliothèque/Revue avec une partie longue chargée. Porté à 90s.
- Vérifié qu'aucun autre timeout intermédiaire ne coupe la requête plus tôt :
  `SocketIO(app)` (app.py) n'a pas de `ping_timeout`/`ping_interval` custom,
  et le serveur Flask dev (`socketio.run`) n'a pas de timeout de requête
  configuré. Le seul timeout applicable au chemin `_call_claude` est bien
  celui de la ligne modifiée.
- Vérification fonctionnelle (sans clé API réelle disponible dans
  l'environnement d'exécution) : simulation d'une latence de 20s côté API
  via mock de `urllib.request.urlopen` — confirme qu'avec le nouveau
  timeout=90 la requête réussit (20s < 90s), alors qu'avec l'ancien
  timeout=15 la même latence aurait levé `TimeoutError`. Une vérification
  E2E via navigateur headless avec un vrai appel API n'a pas pu être
  réalisée : aucune `ANTHROPIC_API_KEY` n'était présente dans
  l'environnement de cette session, et `DATA_DIR` (`~/ChessCoach/data`,
  PGN réels + `coach_memory.json`) se situe hors du périmètre strict de ce
  worktree (`/home/alain/chesscoach-issue45`).

