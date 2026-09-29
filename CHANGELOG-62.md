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
