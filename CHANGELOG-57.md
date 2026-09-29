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
