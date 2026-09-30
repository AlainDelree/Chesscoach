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
