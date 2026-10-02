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
