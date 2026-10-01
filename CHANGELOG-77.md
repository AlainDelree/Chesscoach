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
