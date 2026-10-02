# Changelog — Issue #96

## Coach : évaluation d'un coup précis interrogé par Alain (ex. « et Bxh7+ ? »)

Cas réel (signalement d'Alain, 2 octobre 2026, mode Exercice, FEN
r2q1rk1/pppbbppp/2n2n2/3p2N1/3P4/3BB3/PPP1QPPP/RN2K2R b KQ - 11 9, coup
proposé g6, coup réel Ne4, meilleur coup Nb4) : Alain a demandé « et Bxh7+
? » dans le chat libre, un coup qu'il n'avait lui-même jamais proposé. Le
coach n'avait aucune donnée sur ce coup et a répondu qu'il ne voyait pas
cette idée, sans jamais pouvoir dire que Bxh7+ existe pour les Blancs dans
la position de départ (mauvais : Nxh7 Nxh7 Kxh7, environ -3,6) mais devient
impossible après g6 ou Ne4 (diagonale d3-h7 bloquée par le pion g6).

### 1. Détection et évaluation d'un coup interrogé (`game_facts.py`)

- `detect_moves_in_text` : détecte dans le texte d'Alain un ou plusieurs
  coups en notation SAN (castling, pièce avec capture/désambiguïsation/
  promotion/échec facultatifs, pion) ou décrits par case de départ et
  d'arrivée (« d3-h7 », « d3 vers h7 »), dédoublonnés, limités à
  `MAX_COUPS_QUESTION` (réglable en un seul endroit). Permissif sur la
  forme (une simple mention de case comme « e4 » est détectée), jamais sur
  le fond.
- `resolve_coup_sur_position` : teste la légalité du coup sur une position
  donnée, en essayant le trait RÉEL puis le trait INVERSÉ — une question
  porte souvent sur un coup de l'autre camp que celui qui a la main dans
  cette position précise (Bxh7+ est un coup blanc posé alors que les Noirs
  ont le trait dans la position de départ de l'exercice). Une notation
  réellement ambiguë sur cette position (`chess.AmbiguousMoveError`, deux
  pièces candidates sans désambiguïsation) ne tranche RIEN, par prudence.
- `_explique_coup_impossible`/`_explique_trajectoire`/`_trajectoire_bloquee` :
  quand un coup est illégal, explique en une phrase mécanique pourquoi
  (trajectoire bloquée par une pièce nommée et sa case via `chess.between`,
  pièce absente ou ayant changé de case, case occupée par une pièce amie,
  pion sans cible à prendre, roque bloqué par une pièce entre le roi et la
  tour malgré un droit de roque toujours valide — distinct d'un droit
  réellement perdu) — jamais une supposition.
- `build_coup_interroge_bloc`/`build_coups_interroges_texte` : pour chaque
  coup détecté, teste la légalité sur chaque position pertinente transmise
  par l'appelant (position de départ, après coup proposé/réel/meilleur
  coup, après les lignes déjà calculées), décrit mécaniquement le coup
  (`_decrit_coup_mecanique`, même fonction que coup_propose/coup_reel/
  meilleur_coup, avec le trait forcé sur le bon camp) et l'évaluation
  Stockfish injectée par un callback optionnel (`evaluateur`, jamais
  d'appel moteur direct dans `game_facts.py`) quand légal, ou la raison
  mécanique sinon. Positions consécutives au même résultat regroupées.
  Chaîne vide si le coup est ambigu sur TOUTES les positions testées, ou
  si aucun coup n'a été détecté. Texte tronqué à `MAX_CARACTERES_COUP_
  QUESTION` par coup (700 par défaut, réglable au même seul endroit que
  `MAX_COUPS_QUESTION`).

### 2. Contexte et prompt (`app.py`, `llm_coach.py`)

- `app.py` : `_positions_pour_coup_interroge` construit la liste des
  positions pertinentes de l'exercice en cours à partir du contexte déjà
  transmis (fen_depart_exercice/coup_propose/coup_reel/meilleur_coup/
  pv_coup_propose/pv_meilleur_coup). `_enrich_context_with_coup_interroge`,
  appelée uniquement par le handler `coach_ask` (chat libre, pas le bouton
  « Demander l'avis du coach » qui ne transmet aucune question texte),
  détecte un coup dans la dernière question d'Alain et ajoute
  `context["coup_interroge_texte"]` — limité au mode exercice (seul mode
  où ces positions de référence sont disponibles), best-effort.
- `llm_coach.py` : `_build_context_text` transmet ce texte au coach, et un
  nouveau paragraphe de `_EXERCISE_SYSTEM_ADDENDUM` impose de répondre
  UNIQUEMENT à partir de ces faits (légalité, évaluation, raison) et
  interdit de répondre « je ne vois pas cette idée » quand ce bloc est
  présent, même si son verdict est « mauvais » ou « illégal partout » —
  cette formule n'est autorisée que si le bloc est absent malgré une
  question qui porte clairement sur un coup précis. Le contexte ajouté
  apparaît automatiquement dans l'entrée du journal (`_log_coach_call`
  journalise déjà le dict `context` complet).

### 3. Non-régression (`non_regression_coach.py`, `tests/cas_coach/`)

- Nouveau champ optionnel `question` dans les fichiers `.case` : simule une
  question de suivi du chat libre (au lieu du message initial habituel) et
  enrichit le contexte reconstruit avec le même calcul que
  `app.py`/`game_facts.py` (fonction `_positions_pour_coup_interroge`
  dupliquée localement, comme les autres fonctions de ce script —
  isolation voulue, jamais sur une instance de l'application en cours
  d'exécution).
- Nouveau cas `bxh7_coup_interroge.case` : reproduit le signalement réel
  (coup_propose g6, meilleur coup recalculé par un vrai Stockfish = Re8,
  question « et Bxh7+ ? ») — vérifie que le contexte envoyé au coach
  contient bien l'évaluation (« blunder ») de Bxh7+ dans la position de
  départ et l'explication du blocage (« la trajectoire d3-h7 est bloquée
  par Pion noir en g6 ») après le coup proposé, avec des motifs interdits/
  attendus pour --api (« je ne vois pas cette idée » interdit, « mauvais/
  blunder/impossible/bloqué » attendu).

### Correctifs trouvés par une revue indépendante

Une revue de code dédiée (agent distinct, sans contexte de l'implémentation)
a trouvé 2 bugs réels et 1 risque, tous corrigés :

- `resolve_coup_sur_position` abandonnait le test du trait inversé dès la
  première `AmbiguousMoveError` sur le trait réel, sans jamais essayer
  l'autre camp — alors qu'une interprétation parfaitement claire pouvait
  exister côté camp forcé (ex. deux cavaliers blancs ambigus pour "Nd2",
  mais un seul cavalier noir, non ambigu, de l'autre côté). Corrigé : les
  deux couleurs sont désormais toujours essayées, une interprétation légale
  trouvée l'une ou l'autre l'emporte sur une ambiguïté rencontrée côté
  opposé ; "ambigu" n'est retenu que si aucune couleur ne donne
  d'interprétation légale.
- `_explique_trajectoire` (capture de pion) répondait « probablement un roi
  laissé en échec » même quand la case cible était occupée par une pièce du
  MÊME camp (capture de sa propre pièce, impossible pour une raison
  certaine et différente). Nouvelle fonction partagée
  `_raison_malgre_portee` distinguant les deux seules raisons possibles une
  fois la portée géométrique confirmée (pièce amie sur la case, ou roi
  laissé en échec) — réutilisée aussi par la branche pièces non-pions et
  les poussées de pion, qui employaient la même formulation hasardeuse.
- La notation case à case acceptait un simple tiret nu ("d3-h7") comme
  séparateur, collisionnant avec des phrases descriptives françaises
  légitimes qui utilisent la même forme sans viser un coup (« la diagonale
  d3-h7 », « la chaîne de pions d4-d5 »). Corrigé en deux temps : seuls des
  séparateurs explicitement directionnels (« vers », « -> », « à »)
  déclenchent désormais la notation case à case ; l'alternative « coup de
  pion poussée » (repli SAN le plus permissif) est en plus exclue quand
  elle est immédiatement adjacente à un tiret, pour qu'un simple tiret nu
  ne produise plus deux fausses détections séparées (ex. "d4"+"d5") à la
  place d'une seule.

### Tests effectués

- Cas réel Bxh7+ reproduit avec un vrai Stockfish (binaire système) : texte
  produit conforme à l'analyse de l'issue (mauvais dans la position de
  départ avec la ligne Bxh7+ Nxh7 Nxh7 Kxh7, impossible après g6 — diagonale
  bloquée par le pion —, toujours légal après le meilleur coup réellement
  calculé Re8).
- Question sans coup identifiable → aucun ajout.
- Notation réellement ambiguë (deux cavaliers pouvant tous deux rejoindre
  la même case sans désambiguïsation) → aucun ajout, même mélangée à un
  coup clair dans la même question.
- Plusieurs coups dans la même question → chacun traité et rapporté
  séparément.
- Coup illégal sur toutes les positions testées (Rxh8) → dit en une phrase
  par position, regroupées.
- Roque et promotion : roque bloqué par une pièce entre roi et tour
  distingué d'un droit de roque réellement perdu (bug trouvé et corrigé en
  cours de développement — le droit de roque seul ne suffisait pas) ;
  promotion illégale correctement expliquée des deux côtés.
- Suite de non-régression complète (`python3 non_regression_coach.py
  --verbose`, sans `--api`) : les 4 cas (dont le nouveau) passent, aucune
  régression sur les cas existants (re3, c4, h4).
- Appel API réel non disponible dans cet environnement (aucune clé
  configurée dans ce worktree) : non testé avec un vrai modèle Sonnet —
  seul le contenu des données transmises au coach a été vérifié.

### Limites connues

- La détection de coups par notation SAN est volontairement permissive sur
  la forme : une simple mention de case à deux caractères (ex. « h7 » dans
  « la case h7 est faible ») peut être interprétée comme un coup de pion.
  C'est un compromis assumé avec l'exemple demandé par l'issue (« e4 » doit
  être détectable comme un coup) plutôt qu'un vrai filtre sémantique.
- `_explique_coup_impossible` ne couvre que les raisons mécaniques les plus
  fréquentes (trajectoire bloquée, pièce absente, case occupée, roque
  bloqué) ; un coup illégal uniquement parce qu'il laisse le roi en échec
  (clouage, échec déjà en cours) retombe sur une formulation générique
  (« probablement un roi laissé en échec ») plutôt que sur l'identification
  précise de la pièce clouante.
- Les positions testées pour les lignes principales (pv_coup_propose/
  pv_meilleur_coup) sont la position finale après toute la ligne, pas
  chaque demi-coup intermédiaire — un coup qui ne devient pertinent qu'au
  milieu d'une ligne déjà calculée n'est donc pas testé à ce stade
  intermédiaire précis.
