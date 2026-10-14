## Issue #111 — Coach : fiabilité 15 : couleur « blanc »/« blancs » (forme masculine) reconnue dans le contrôle pièce+case et clouage

Défaut préexistant relevé pendant l'issue #110 : `_CASE_PIECE_RE`
(`coach_reliability.py`), motif utilisé par `detecter_case_piece_incoherente`
("pièce présente sur la case", forme AVEC préposition "en"/"sur") ET par
`detecter_clouage_errone` (contrôle de clouage), reconnaissait pour les
Blancs uniquement `blanche?s?` (= "blanch" + "e" et "s" optionnels, donc
"blanche"/"blanches", jamais "blanc"/"blancs" faute de "h" final) alors
que pour les Noirs `noire?s?` couvre bien les quatre formes ("noir" n'a pas
de "h"). Conséquence : "le fou blanc en e5" ou "le cavalier blanc en c6"
n'étaient jamais contrôlés, contrairement à "la tour noire en e5" — faux
négatif silencieux.

Correctif : `(?:\s+(blancs?|blanches?|noirs?|noires?))?` (même forme déjà
utilisée par `_CASE_PIECE_SANS_PREP_RE`, corrigée à l'issue #110).

Motifs de couleur du module examinés (tous les groupes capturants
`blanc...|noir...` trouvés par recherche exhaustive) :
- `_PIECE_COULEUR_ADJ_RE` (ligne ~310, "tour blanche") : déjà correct
  (`blancs?|blanches?|noirs?|noires?`).
- Motif "des Blancs"/"des Noirs" (ligne ~314) : déjà correct (forme
  nominale, pas d'adjectif féminin/masculin à distinguer).
- Motif "deux tours blanches" (ligne ~350) : déjà correct.
- **`_CASE_PIECE_RE` (ligne ~425) : CORRIGÉ** (seul motif fautif trouvé).
- `_CASE_PIECE_SANS_PREP_RE` (ligne ~450, issue #110) : déjà correct.
- `_CAMP_NOM_GROUPE` (ligne ~1325) : déjà correct.
- `_PIECE_MOD_RE` (ligne ~2100, possessifs/"adverse") : déjà correct.
- Motifs attaque/défense incohérente (lignes ~2480, ~2560) : déjà corrects.

Comme ce motif est partagé par les deux contrôles, le correctif profite
aux deux à la fois sans modification supplémentaire.

Cas de test ajoutés à `tests/cas_coach/rd1_cavalier_d4.case` (FEN réelle du
signalement d'origine, d4 = cavalier noir, a1 = tour blanche, e5 = tour
blanche donc AUCUN fou nulle part) :
- "le fou blanc en e5" (aucun fou, encore moins blanc, en e5) : signalée.
- "le cavalier noir en d4" (vrai) : verte.
- "la tour blanche en a1" (vrai) : verte.
- "le fou blanc en d4" (faux, d4 = cavalier noir) : signalée.
- Variantes plurielles masculines ("les fous blancs en e5/d4", "les
  cavaliers noirs en d4") : même verdict que leurs équivalents singuliers,
  confirmant que la forme plurielle masculine est désormais bien reconnue.
- "Les Blancs jouent..."/"le trait aux Blancs" (nom de camp, pas de pièce
  adjacente) : verte — aucun faux positif introduit.

Comportement inchangé pour le reste : aucune règle de prudence, position
examinée ou gravité modifiée ; portée strictement limitée à la
reconnaissance de la couleur.

Tests : `python3 non_regression_coach.py --verbose` (vrai Stockfish, sans
appel API) — 7/7 cas OK (bxh7_coup_interroge, c4_bxc6_bxc6_reste_verte,
dame_noire_c6_possessif_case, h4_menace_gxh3_defensif, qa4_ligne_depart,
rd1_cavalier_d4, re3_dame_contre_tour). `python3 -m py_compile
coach_reliability.py` OK. Vérification manuelle additionnelle (script
Python ad hoc, `detecter_case_piece_incoherente` sur la FEN réelle) :
les 7 phrases listées ci-dessus produisent exactement le verdict attendu.

Limite : appel API réel (`--api`, 5 essais/cas) non effectué — aucune clé
API disponible/activée dans cet environnement d'exécution ; seule la
vérification sans appel API (`--verbose`, faits de contexte) a pu être
faite, comme annoncé dans ce rapport.
