# Changelog — Issue #131

## Élagage de CONTEXTE.md : noyau injecté ~9 ko, fiches de détail dans docs/contexte/, sections fausses retirées

Travail de documentation uniquement (aucun fichier de code, de test, ni de
configuration modifié). CONTEXTE.md passe de 35 796 octets à 8 804 octets
(noyau injecté dans chaque issue), le détail retiré est préservé dans neuf
fiches sous docs/contexte/, lues à la demande.

### Sections supprimées (fausses, sans remplacement)
- « État d'avancement » : annonçait un squelette Flask minimal "en cours"
  alors que l'application est complète.
- « Prochaines étapes prévues » : feuille de route (squelette Flask, passe
  d'analyse Stockfish/Claude sur l'historique PGN, nouvel index.html) déjà
  entièrement réalisée.

### Historique déplacé depuis CONTEXTE.md vers ce changelog

**Architecture / migration depuis AlChess** : ChessCoach réutilise des
modules adaptés d'AlChess, débarrassés de tout ce qui est spécifique à
AlChess (trilingue FR/EN/DE, mode pédagogique débutant, hardware Chessnut).

**Modules adaptés lors de la migration** (la carte des fichiers actuelle,
tous à la racine du dépôt, est désormais dans le noyau CONTEXTE.md — le
dossier `export_chesscoach/` mentionné dans d'anciennes notes n'existe pas
dans ce dépôt) :
- library_manager.py — import PGN mono/multi-parties
- socketio_pgn_handlers.py — 6 handlers SocketIO (register_pgn_library_handlers)
- llm_coach.py — adapté de llm_explainer.py AlChess (issue #196) : system
  prompt + appel Claude + conversation multi-tours + load_coach_memory/
  save_coach_memory (fichier mémoire JSON externe)
- engine_stockfish.py — EngineManager (UCI générique), Maia/Rodent IV retirés
- static/board.js, static/board.css — plateau, matériel, flèches, barre
  d'éval, chat coach (renommé coach*) ; i18n, sync Chessnut, sauvegarde
  NicLink retirés

**Tables de finales Syzygy — avant l'issue #32** : le moteur dédié au mode
"travail de finales" réutilisait par erreur le moteur Elo limité (~1500) du
bouton "Coup Stockfish" du mode partie libre, ce qui dégradait les
techniques de mat longues et précises. Depuis l'issue #32, ce moteur est
dédié et tourne en pleine force (UCI_LimitStrength désactivé) — invariant
vivant désormais documenté dans le noyau CONTEXTE.md.

**Correctifs manuels du 20 octobre 2026 (hors issue, avant l'issue #128)**

Trois correctifs appliqués directement en commits sur master le 20 octobre
2026, sans issue ni tests dédiés au moment où ils ont été écrits (régularisés
par l'issue #128, suite #126) :
1. `game_facts.py` : les pièces « en prise » du bloc de faits python-chess
   par coup (issue #126) sont désormais calculées par un vrai calcul
   d'échange sur la case (`_gain_capture` : captures légales en chaîne,
   clouages compris — un défenseur cloué ne compte pas) au lieu de l'ancienne
   comparaison de valeurs brutes. Les camps et le solde sont nommés pour
   l'utilisateur, les coups des Blancs sont numérotés (ex. « 31.R5xe4 »,
   « 30...Rxb6 » pour les Noirs), et les roques sont nommés « petit roque »
   (côté roi) / « grand roque » (côté dame).
2. `engine_stockfish.py` et `game_facts.py` : les lignes calculées (PV) sont
   limitées à 4 coups puis prolongées d'au plus 2 coups tant que le dernier
   coup retenu est une capture (`_couper_pv` côté moteur, même règle
   dupliquée côté `describe_pv_with_balance`/`describe_pv_facts` avec un
   test sur la présence de « x » dans la SAN) — pour ne jamais présenter au
   coach la fin d'une ligne arrêtée au milieu d'un échange, dont le solde
   matériel serait alors trompeur.
3. `llm_coach.py` : consignes ajoutées sur la formulation des pièces
   capturées, le coup joué à l'époque dans la partie d'origine (ne pas le
   juger sans évaluation fournie), la mise en page en paragraphes distincts,
   et les noms de roque.

Ces trois correctifs n'ont pas changé de comportement avec l'issue #128
(toujours en place) ; seule la convention de signe des évaluations/soldes a
changé (section dédiée du noyau CONTEXTE.md, détail complet dans
docs/contexte/convention_signe.md).

### Correction apportée lors de la revérification (issue #131)

Le diagnostic de l'issue #129 (support de cette issue #131) indiquait que
`eval_alain_cp`/`eval_alain_mat` restaient utilisés pour la barre
d'évaluation de l'affichage, hors périmètre de l'issue #128. En revérifiant
le code au moment d'écrire cette issue (le diagnostic datait d'environ un
jour), ces deux noms de champ n'existent plus du tout dans le dépôt : la
fonction `updateEvalBar` (static/board.js) qui alimente la barre existe
toujours mais n'est appelée depuis aucun fichier du dépôt — elle semble être
devenue du code mort suite à un refactor non documenté, probablement
antérieur à cette issue. Comme l'issue #131 est strictement de la
documentation (aucune modification de code autorisée par sa consigne), ce
point est seulement signalé ici et dans docs/contexte/convention_signe.md —
à vérifier et, le cas échéant, corriger par une issue de code dédiée.
