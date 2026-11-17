# ChessCoach — Contexte du projet

## Règles de travail
- Avant de fusionner le travail d'une issue vers master : vérifier que
  master est propre (aucun résidu non committé d'une tâche précédente).
- Avant d'affirmer quoi que ce soit sur une position (légalité d'un coup,
  meilleur coup, matériel, clouage, menace) : vérifier avec Stockfish ou
  python-chess, jamais de mémoire ni par déduction visuelle.
- Suppression d'une alerte de sécurité (outil d'audit, grep de sécurité) :
  uniquement si faux positif déjà jugé, raison en clair + code précis dans
  `.audit.json` (`exceptions`) — jamais de suppression silencieuse.
- Suite de tests : `python3 scripts/lancer_tests.py` (`--rapide` pour
  sauter les tests lents) — voir `docs/contexte/tests.md`.
  `python3 -m py_compile <fichier>` pour une vérification rapide.
- Toute modification de code passe par une issue Bridge_Agent
  (PROJET | chesscoach), même petite. CCL committe en local uniquement.

## Architecture
Coaching échecs personnel pour Alain (pas AlChess, pas Jess) : plateau
virtuel, import PGN (Chess.com/Lichess), coach Claude (+ Mistral en second
avis, mode Exercice) épaulé par Stockfish, mémoire JSON du coach entre
sessions. Dépôt séparé d'AlChess (AlainDelree/Chesscoach, périmètre
~/ChessCoach), mono-utilisateur, sans i18n ni support Chessnut.

Deux entrées Flask : `app.py` (port 5000, serveur principal — routes,
SocketIO, jeu) et `app_club.py` (port 5001, routes `/club` exclusivement,
jeton + clé API dédiés — fiche `page_club`). Modules racine :
`engine_stockfish.py` (EngineManager, UCI), `llm_coach.py` (Claude/Mistral,
mémoire du coach), `game_facts.py` (faits de position en texte),
`lichess_puzzles.py`, `library_manager.py`, `socketio_pgn_handlers.py`,
`config.py`, `static/*.js`/`templates/index.html`.

Mémoire du coach (`coach_memory.json`, DATA_DIR) : profil, patterns_erreurs,
repertoire_ouvertures, historique_sessions, objectifs_courants. Données
personnelles (PGN d'Alain) sous `data/pgn_import/` — DATA_DIR gitignoré,
dépôt public : jamais de données personnelles committées.

## Conventions
Rédaction de CE fichier : n'y écrire que ce qu'un agent doit savoir AVANT
d'écrire du code (invariant, convention, piège) — ce qu'une issue a *fait*
va au changelog, jamais ici. Remplacer une section plutôt que l'empiler
(pas de « (issue #N) » à côté de l'ancienne). Dès qu'un sujet dépasse ~6
lignes ou décrit une interface/un format, il part dans
`docs/contexte/<domaine>.md` avec un renvoi ici. Une issue qui rend un
passage faux le corrige ou le supprime dans le même commit, et le dit dans
son rapport. Noms réels (fichier et symbole) ; jamais « pour toi »/« pour
Alain »/« en ta faveur » à côté d'un chiffre signé (nommer le camp par sa
couleur) ; un nom de champ n'a qu'un sens — sinon le dire.

## Fiches de détail (docs/contexte/) — quand lire chacune
- `convention_signe` — avant de toucher un chiffre signé transmis à l'IA.
- `classification_coups` — avant de toucher au verdict/à la sélection.
- `modele_llm` — avant de toucher au choix Haiku/Sonnet ou son repli.
- `jetons_mistral_cout` — avant de toucher au coût/jetons Mistral.
- `temperature_llm` — avant de toucher à la température des appels IA.
- `exercices_lichess` — avant de toucher aux « Problèmes Lichess ».
- `suivi_version` — avant de toucher à l'étiquette de version/série.
- `compteur_tokens` — avant de toucher au compteur de tokens affiché.
- `syzygy_tailscale` — avant de toucher l'accès distant ou Syzygy.
- `mode_serie` — avant de toucher l'interrupteur mode série.
- `contexte_coach_exercice` — avant de toucher au contexte coach Exercice.
- `page_club` — avant de toucher la page club ou `app_club.py`.
- `lignes_calculees` — avant de toucher la longueur des lignes calculées
  (PV) ou le calcul de ce qui est « en prise ».
- `tests` — avant d'ajouter un test ou de toucher le lanceur.
