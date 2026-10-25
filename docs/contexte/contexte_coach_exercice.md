# Construction du contexte coach en mode Exercice (issue #141, suite #140)

Avant cette issue, `on_exercise_answer` et `_on_exercise_answer_lichess`
(`app.py`) construisaient chacun, en dupliquant la logique, le bloc de
contexte envoyé à `llm_coach.get_coach_response`/`get_mistral_response` :
menace adverse, listes de pièces, clouages, idées détectées, descriptions
mécaniques, détail coup par coup des lignes (avec solde matériel, convention
de signe Lichess — voir `convention_signe`), faits python-chess par coup de
la PV, réponses adverses alternatives.

**Fonction partagée** : `app._construire_contexte_coup_exercice(fen_avant,
camp_alain, source, coup_propose_san, fen_apres, meilleur_coup,
pv_coup_propose="", pv_meilleur_coup="", coup_reel="")`. Paramètres
explicites uniquement — ne lit ni `_current_exercise` ni aucun autre état
global. `source` prend une valeur parmi `"mes_erreurs"`, `"position_precise"`
(se comportent à l'identique dans cette fonction) ou `"lichess"`. Rend un
dict (`pieces_depart_texte`, `pieces_actuelles_texte`, `materiel_resume_texte`,
`pieces_clouees_texte`, `menace_adverse_texte`, `idees_coup_propose_texte`,
`idees_coup_reel_texte`, `idees_meilleur_coup_texte`,
`coup_propose_description_mecanique`, `coup_reel_description_mecanique`,
`meilleur_coup_description_mecanique`, `pv_coup_propose_detail`,
`pv_meilleur_coup_detail`, `pv_coup_propose_faits`, `pv_meilleur_coup_faits`,
`reponse_adverse_coup_propose_texte`, `reponse_adverse_meilleur_coup_texte`)
fusionné par l'appelant dans le `context` passé aux IA.

`source == "lichess"` change trois choses, à l'identique du comportement
d'avant l'extraction : libellé du meilleur coup/de sa ligne ("la solution du
problème" plutôt que "le meilleur coup selon Stockfish"), longueur de la
ligne détaillée du meilleur coup (8 demi-coups — solution complète du
problème — plutôt que 4), absence de calcul côté coup réellement joué à
l'époque (`idees_coup_reel_texte`/`coup_reel_description_mecanique`, vides)
et de faits python-chess par coup de la PV (`pv_*_faits`, vides) — ce
problème n'a pas de partie d'origine.

Les deux gestionnaires lisent leur état (`_current_exercise`, position,
mode série...) comme avant, puis appellent cette seule fonction — aucune
duplication de la logique de construction du contexte, quel que soit le
chemin. Les futures issues de la série (point d'accès pour une page
indépendante, sélection des exercices, affichage) doivent appeler cette même
fonction plutôt que relire `_current_exercise` ou reconstruire ce bloc.

**Golden master** (`test_issue141_golden_master.py`,
`golden_master_issue141.json`) : capture, via le vrai gestionnaire (client de
test Flask-SocketIO, IA simulées au niveau `llm_coach._call_claude`/
`_call_mistral`), le contexte exact transmis aux IA et les évènements émis,
sur 15 cas (deux sources, deux camps, bon coup/imprécision/gaffe/meilleur
coup/mat, mode série activé/désactivé) — zéro différence attendue après
toute future modification de cette zone, hors champs volatils
(`log_id`/`id`/`horodatage`/`version_info`/`date_debut`/`dernier_appel`) et
hors ordre d'arrivée des listes `appels_ia`/`evenements`/`journal` (deux
threads indépendants quand Mistral est actif ou en mode série — contenu
identique, ordre non déterministe, trié avant comparaison). Régénérer la
référence avec `generer_golden_master_issue141.py` (jamais exécuté par la
suite de tests elle-même).
