# Changelog — Issue #56

## Explications de coups de l'analyse post-partie : étiqueter chaque coup par son auteur ; compléter le bloc de faits avec la fin de partie

- Contexte : en usage réel après « Analyser cette partie » sur une partie
  pédagogique abandonnée (Alain Blancs, Stockfish Noirs), l'explication du
  coup flagué « 10. (Noirs) Bf8 » disait « Alain le replie en f8 » — un coup
  des Noirs attribué à Alain — et nommait l'ouverture « Française » alors
  que la partie commençait par 1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 (pas une
  Française). Même famille de bug que l'issue #55 (chat libre), mais sur un
  autre chemin de code : le module d'explications narratives des coups
  décisifs (`get_move_explanations`, appel en lot, issue #42) et
  l'explication à la demande d'un coup unique (`on_analyse_expliquer_coup`)
  ne recevaient jusque-là aucune information sur le camp d'Alain.
- `game_facts.py` :
  - `_camp_label` renommée `camp_label` (fonction publique) pour être
    réutilisée telle quelle par `llm_coach.py`, au lieu d'en redupliquer la
    logique (« Blancs (Alain) »/« Noirs (adversaire) », jamais une simple
    déduction du trait) ;
  - nouvelle fonction `camp_alain_from_pgn_headers(white, black)` : déduit
    le camp d'Alain depuis les en-têtes PGN White/Black — pseudo
    Lichess/Chess.com (`athanatos123`, casse ignorée) pour une partie
    importée de la bibliothèque, ou le nom « Alain » pour une partie jouée
    dans l'appli (pédagogique/ouverture/finales taguent déjà leurs en-têtes
    ainsi avant l'analyse). Retourne `""` si aucun des deux en-têtes ne
    correspond (partie entre deux tiers, partie libre où les deux camps
    peuvent être joués par Alain) — jamais une devinette ;
  - `build_game_facts_text` : la fin de partie (mat, pat, nulle par la
    règle — matériel insuffisant/75 coups/répétition quintuple —, ou
    abandon déduit du `Result` PGN si aucune de ces règles ne s'applique)
    est désormais ajoutée comme dernier moment clé, même sans aucune
    variation matérielle d'au moins 2 points. Constat en test réel : une
    partie perdue par mat en 9 coups (9...Qxh2#) sans la moindre perte de
    matériel ne déclenchait jusque-là aucun moment clé, le coach ne s'en
    sortant que grâce au signe « # » du texte PGN — ce qui n'est plus
    laissé au hasard (calculé mécaniquement avec `board.is_checkmate()`/
    `is_stalemate()`/`is_insufficient_material()`/`is_seventyfive_moves()`/
    `is_fivefold_repetition()`).
- `llm_coach.py` :
  - `get_move_explanations(flagged_moves, camp_alain, config)` — nouveau
    paramètre `camp_alain`. Chaque coup flagué reçoit désormais un champ
    `auteur` déjà calculé (via `game_facts.camp_label`, réutilisé plutôt que
    reduplié) — p. ex. `"Noirs (adversaire)"` — que le prompt système lui
    demande explicitement de recopier tel quel, jamais de redéduire lui-même
    depuis le seul champ `camp`. Le JSON envoyé au coach passe d'une simple
    liste de coups à `{"camp_alain": "blancs"|"noirs"|null, "coups": [...]}}`
    (le format de la réponse attendue, `{"choix": [{"id", "explication"}]}`,
    est inchangé — aucun impact sur la réassociation côté client) ;
  - `_MOVE_SELECTION_SYSTEM_PROMPT` renforcé : un coup dont l'auteur ne
    contient pas « Alain » n'est jamais présenté comme joué par lui ; pour
    l'erreur d'un adversaire, expliquer ce qu'elle offre à Alain plutôt que
    de la commenter comme un coup d'Alain ; si `camp_alain` est `null`, ne
    prêter aucun coup ni à Alain ni à « l'adversaire » (décrire uniquement
    Blancs/Noirs) ; ne jamais nommer une ouverture précise (elle n'est
    jamais fournie dans les données) — décrire la structure sans lui donner
    de nom inventé ;
  - nouvel addendum `_ANALYSE_PARTIE_ADDENDUM`, ajouté par
    `get_coach_response` quand `context.mode_origine == "analyse_partie"`
    (explication à la demande d'un coup unique, `on_analyse_expliquer_coup`) :
    même garde-fou (camp_alain seule source fiable, jamais de nom
    d'ouverture inventé), indépendant et cumulable avec les addenda
    existants (exercice, faits calculés, etc.) ;
  - `_build_context_text` : nouveau cas `camp_alain_inconnu` (distinct de
    l'absence simple de `camp_alain`) — dit explicitement au coach que le
    camp d'Alain a été recherché mais n'a pas pu être déterminé, pour qu'il
    décrive les coups par Blancs/Noirs sans deviner qui est Alain.
- `app.py` :
  - nouvelle fonction `_camp_alain_pour_analyse(data)` : appelle
    `game_facts.camp_alain_from_pgn_headers` sur les champs `white`/`black`
    transmis par le client, et distingue « camp indéterminable » (au moins
    un en-tête transmis, aucun ne correspond à Alain) d'« aucune info
    transmise » ;
  - `on_analyse_choisir_coups_decisifs` et `on_analyse_expliquer_coup`
    l'utilisent pour passer `camp_alain`/`camp_alain_inconnu` au coach.
- `static/board.js` : `reviewWhite`/`reviewBlack` mémorisent les en-têtes
  PGN White/Black de la partie chargée en revue (`parsePgn`), qu'elle vienne
  de la bibliothèque ou du bouton « Analyser cette partie » depuis la
  bannière de fin de partie (pédagogique/ouverture/finales taguent déjà
  leurs en-têtes PGN avec « Alain »/le nom de l'adversaire avant d'appeler
  `analyserPartieDepuisPgn`).
- `static/game_analysis.js` : `demanderExplicationsCoach` et
  `demanderExplicationCoup` transmettent désormais `white`/`black` au
  serveur avec les coups flagués.
- Testé (sans appel API réel — clé API non vérifiée depuis ce worktree,
  cf. rapport de clôture) :
  - PGN de test d'acceptation (1.c4 Nf6 2.d4 c6 3.Nf3 e6 4.g3 ... 18...Qxa4,
    Alain Blancs) : `camp_alain_from_pgn_headers("Alain", "Stockfish")` →
    `"blancs"` ; `build_game_facts_text` étiquette bien 10...Bf8 et
    11...Nxe4 « Noirs (adversaire) » ; aucun nom d'ouverture dans les
    données envoyées au coach (jamais calculé, seulement les coups/camps/
    auteurs) ;
  - PGN de bibliothèque avec en-tête Black = `athanatos123` (Alain aux
    Noirs) : camp déduit `"noirs"` ; avec deux pseudos tiers, camp déduit
    `""` (indéterminable, propagé tel quel) ;
  - partie perdue par mat en 9 coups (matériel intact avant le mat) :
    nouveau moment clé de fin de partie généré mécaniquement, sans dépendre
    du signe « # » du texte PGN.
