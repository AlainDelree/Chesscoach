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
