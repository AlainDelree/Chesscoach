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
