# Changelog — Issue #143

## Issue #143 — Suite #142 : sélection des exercices pour la page « club » (script de tri selon l'écart entre les meilleurs coups de Stockfish)

But : préparer, en hors-ligne, un lot d'exercices pour la future page
« club » (étape 4) — un mélange de positions ÉVIDENTES (un seul bon coup
nettement meilleur que les autres) et DISCUTABLES (plusieurs coups presque
équivalents), autant de Blancs que de Noirs que possible. Cette issue ne
fait QUE le script de sélection : aucune page, aucun appel à une IA, aucun
réseau.

**`scripts/selection_club.py`** (nouveau) : lit `data/erreurs_detectees.json`
(même fichier que le mode « Mes erreurs », fonction de chargement
reproduite localement pour éviter d'importer app.py — cf. docstring du
script, l'import aurait lu plusieurs fichiers personnels réels dès le
chargement du module). Pour chaque position candidate, interroge un SEUL
processus Stockfish (ouvert une fois, fermé dans un `finally`, limite de
temps globale configurable) avec les trois meilleurs coups (multi-lignes, à
`DEPTH_EXERCICE_TEMPS_REEL` — même profondeur que le mode Exercice/
`api_club_eval`), du point de vue du camp qui a le trait dans la position de
départ. Les scores de mat sont plafonnés à ±1000 centipions, le même plafond
que la classification officielle Lichess (issue #125).

Catégories (constantes nommées, modifiables en ligne de commande) : « évident »
si l'écart 1er/2e coup >= 200 cp ; « discutable » si cet écart est <= 40 cp ET
l'évaluation de la position reste entre −300 et +300 cp (sinon la position est
déjà décidée). Exclues des deux : mat forcé annoncé en <= 3 coups, position
invalide ou partie terminée, doublon de FEN, moins de deux coups légaux.

Sélection par défaut : 3 évidentes + 9 discutables (options `--n-evidents`/
`--n-discutables`), équilibre Blancs/Noirs en best-effort, mélange des phases
si connues, au plus une position par partie toutes catégories confondues —
jamais de complément par une position hors critère : une pénurie est
signalée clairement (résumé terminal + JSON). Déterministe (tri avec
départage explicite par FEN).

Sortie : `data/club_selection.json` par défaut (chemin configurable) —
position, camp, catégorie, écarts 1er/2e et 1er/3e coup, les trois meilleurs
coups avec leur évaluation (convention de Lichess), phase et identifiant de
partie si connus — plus un résumé lisible dans le terminal.

**Documentation** : `docs/contexte/page_club.md` complété (nouvelle section
« Sélection des exercices »), une ligne ajoutée dans `CONTEXTE.md` (section
« Page « club » »).

**Tests** (`test_issue143_selection_club.py`, nouveau, jeu de données
fabriqué — jamais `data/erreurs_detectees.json` réel) : position évidente
(pièce pendante, Blancs et Noirs), positions discutables (coups équivalents,
Blancs et Noirs), position décidée à écart faible qui ne doit PAS être
classée discutable, mat forcé en 1 coup exclu des deux catégories, position
invalide, doublon de position, doublon de partie (« au plus une position par
partie »), seuils modifiables en ligne de commande, équilibre Blancs/Noirs,
pénurie signalée sans complément hors critère, stabilité entre deux
exécutions, fermeture propre du moteur même après une panne simulée en cours
d'analyse (un seul processus créé, `quit()` appelé). 12 tests, 12 réussis, 0
ignoré. Non-régression : `test_issue142_page_club.py` et
`test_issue141_golden_master.py` rejoués séparément (aucun fichier de l'appli
modifié).
