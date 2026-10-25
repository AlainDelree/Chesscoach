# Changelog — Issue #141

## Issue #141 — Suite #140 : extraction de la construction du contexte coach des gestionnaires d'exercice (refactorisation sans changement de comportement)

Avant cette issue, `on_exercise_answer` et `_on_exercise_answer_lichess`
(`app.py`) dupliquaient chacun la construction du bloc de contexte envoyé
aux IA (menace adverse, listes de pièces, clouages, idées détectées,
descriptions mécaniques, détail coup par coup des lignes, faits
python-chess par coup de la PV, réponses adverses alternatives). Cette
logique est désormais isolée dans une seule fonction partagée,
`_construire_contexte_coup_exercice(fen_avant, camp_alain, source,
coup_propose_san, fen_apres, meilleur_coup, pv_coup_propose="",
pv_meilleur_coup="", coup_reel="")` — paramètres explicites uniquement,
aucune lecture de `_current_exercise` ni d'aucun autre état global. Les
deux gestionnaires lisent leur état comme avant puis appellent cette seule
fonction ; `source` distingue `"mes_erreurs"`/`"position_precise"`
(identiques dans cette fonction) de `"lichess"` (libellés différents,
ligne du meilleur coup sur 8 demi-coups au lieu de 4, pas de coup réel ni
de faits python-chess par coup de la PV — comportement déjà en place avant
cette extraction, reproduit à l'identique). Détail et liste des champs
rendus : fiche `docs/contexte/contexte_coach_exercice.md`.

Aucun changement de comportement observable visé ni constaté : mêmes
appels Stockfish/python-chess, mêmes évènements émis dans le même ordre,
même contenu de journal, même contexte transmis aux IA, mode série
inchangé (ligne de verdict immédiate, avis en arrière-plan, file
d'attente, compteur).

**Golden master (`test_issue141_golden_master.py`,
`golden_master_issue141.json`, `generer_golden_master_issue141.py`)** :
capture, via le VRAI gestionnaire (client de test Flask-SocketIO, IA
simulées au niveau `llm_coach._call_claude`/`_call_mistral`, chemins de
données redirigés vers un dossier temporaire comme `test_issue128.py`), le
contexte exact transmis à chaque IA et les évènements émis vers le
navigateur, sur 15 cas : deux sources (« Mes erreurs »/« Position précise »
et « Problèmes Lichess »), les deux camps, un coup « bon », une gaffe, le
meilleur coup, une position avec mat, et le mode série activé/désactivé.
Champs volatils exclus (`log_id`, `id`, `horodatage`, `version_info`,
`date_debut`, `dernier_appel`) ; listes `appels_ia`/`evenements`/`journal`
triées avant comparaison (deux threads indépendants — appel Claude
synchrone et Mistral/second appel en arrière-plan — dont l'ORDRE d'arrivée
n'est pas déterministe, le contenu l'est). Vérification de cette
tolérance : la capture a été exécutée deux fois sur le code D'ORIGINE
(avant toute modification, via `git stash` temporaire dans le worktree) —
les deux captures sont ressorties **strictement identiques** (zéro
différence, y compris sur les évaluations Stockfish), donc aucune
tolérance numérique supplémentaire n'a été nécessaire au-delà de
l'exclusion des champs volatils déjà en place. La capture sur le code
refactorisé est également ressortie strictement identique à celle du code
d'origine (zéro différence sur les 15 cas) et au golden master committé
(`test_issue141_golden_master.TestGoldenMasterIssue141`, exécuté comme
test automatique séparé du reste de la suite — même contrainte
d'isolation que `test_issue128.py`).

Documentation : nouvelle fiche `docs/contexte/contexte_coach_exercice.md`
(fonction partagée, paramètres, différences `source == "lichess"`, golden
master) ; une ligne ajoutée dans les invariants de `CONTEXTE.md` renvoyant
vers cette fiche, pour que les prochaines issues de la série (point
d'accès pour une page indépendante, sélection des exercices, affichage)
appellent cette fonction plutôt que de dupliquer à nouveau cette logique.

Aucun défaut repéré hors périmètre pendant cette issue.
