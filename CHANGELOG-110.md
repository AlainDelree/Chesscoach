# Changelog — Issue #110

## Fiabilité du coach 14 : type de pièce cité avec une case SANS préposition (« le pion d4 » alors que d4 porte un cavalier noir)

Signalement d'Alain (14 octobre 2026, mode Exercice, commentaire « pas de
pion d4 »). Position `3r1rk1/pppq1ppp/4pn2/4R3/2Bn4/2NQB3/PP3PPP/R5K1 w - -
3 15`, Alain joue les Blancs, coup proposé Rd1 (meilleur coup, +3,53 selon
Stockfish 16 — reconfirmé localement avec un vrai Stockfish, +3,57 à la
profondeur 18). La case d4 porte un CAVALIER NOIR (attaqué par la dame d3 et
le fou e3, défendu par la dame d7 — vérifié avec python-chess ; la tour a1
n'est, elle, attaquée par aucune pièce noire). Le coach a répondu : « ... il
place la tour sur la colonne d, où elle double les pièces sur le dossier
avec ta dame et prépare à peser sur le pion d4/la colonne centrale. » Il n'y
a pas de pion en d4 — pastille verte à tort, aucun contrôle déclenché : le
contrôle « pièce présente sur la case » (`detecter_case_piece_incoherente`,
issues #87/#103) ne reconnaît que les formulations AVEC préposition (« pion
en d4 »/« pion sur d4 »), jamais « le pion d4 » (nom de pièce directement
suivi de la case, sans « en »/« sur »).

### Nouveau contrôle : type de pièce cité avec une case, sans préposition

`detecter_case_piece_sans_preposition_incoherente` (`coach_reliability.py`)
détecte une citation « le »/« la »/« les »/« un »/« une » (ou un possessif
« ton »/« ta »/« tes »/« mon »/« ma »/« mes »/« son »/« sa »/« ses »/
« notre »/« nos »/« votre »/« vos »/« leur »/« leurs ») directement accolé à
un nom de pièce puis à une case, SANS « en »/« sur » entre les deux
(`_CASE_PIECE_SANS_PREP_RE`) — exemples couverts : « le pion d4 », « le
cavalier f6 », « la tour e1 », « la dame d3 », « pion d4/la colonne
centrale » (la citation réelle du signalement).

Exclusif par construction de `_CASE_PIECE_RE` (contrôle existant) : l'espace
entre le nom de pièce (et sa couleur optionnelle) et la case n'accepte que
des espaces, jamais le mot « en »/« sur » — une citation avec préposition
échoue donc toujours à ce nouveau motif et reste traitée UNIQUEMENT par le
contrôle existant, jamais les deux à la fois (consigne explicite de
l'issue, « ne pas dupliquer »).

Contrairement à `detecter_case_piece_incoherente`, la couleur n'a PAS besoin
d'être explicite : seul le TYPE de pièce compte, quelle que soit sa couleur
(« le pion d4 » est contrôlé même sans aucun mot de couleur). Si une couleur
est malgré tout citée (« le cavalier noir d4 »), elle est comparée EN PLUS
du type. Même pool de positions et même tolérance que
`detecter_case_piece_incoherente` : position de départ, position actuelle,
`candidats` (lignes principales et trait inversé compris) et chaque
position atteinte en rejouant une suite de coups citée dans le texte
lui-même (coup précédent cité et demi-coup caché compris) — une citation
cohérente avec AU MOINS UNE de ces positions n'est jamais signalée (couvre
notamment, sans règle dédiée, une pièce qui change de camp ou de nature sur
cette case après une capture citée, ex. « Qxd4 Qxd4 »).

Le message d'alerte cite la case, le type annoncé ET la pièce RÉELLEMENT
présente (type et couleur, ou « case vide ») — ex. : `"le pion d4" annonce
un pion en d4 sans préposition ("en"/"sur"), alors que d4 porte un cavalier
noir — jamais de pion — dans aucune des N position(s) connue(s)...`.
Gravité toujours « orange » (contrairement à d'autres contrôles du module,
aucune heuristique de connecteur de verdict ou de répétition n'élève ici la
gravité à « rouge »).

**Prudence (« en cas de doute, ne rien signaler »)** : une occurrence
précédée, à moins de 30 caractères, d'une négation (« pas »/« jamais »/
« aucun... »/« ni »/« non »), d'un « si » hypothétique, ou d'un verbe qui
fait manifestement de la case une DESTINATION proposée plutôt qu'une pièce
déjà présente (« pousser »/« jouer »/« avancer »/« mettre »/« placer »/
« déplacer »/« amener » juste avant, ex. « pousser le pion d4 ») n'est
jamais contrôlée. Un coup noté (« jouer d4 », « le coup d4 », « avec d4 »,
« Qd4 », « d4 est poussé ») ou une simple mention de la case (« la case
d4 », « le contrôle de d4 ») ne déclenche jamais ce contrôle par
construction : aucun nom de pièce français n'est directement accolé à la
case dans ces tournures.

`llm_coach.get_coach_response` n'a nécessité AUCUNE modification : la
relance automatique de fiabilité reprend déjà, pour tout type d'alerte sans
consigne ciblée dédiée (même traitement que `case_incoherente` et
`clouage_errone`), le message générique bâti sur `fiabilite["raison"]`, qui
cite directement le détail de la première alerte — donc la case, la pièce
annoncée et la pièce réellement présente, comme demandé.

### Limite découverte en cours de route (non corrigée, hors périmètre)

En écrivant des cas de test avec couleur explicite masculine (« cavalier
blanc », sans "e" final), un bug latent PRÉEXISTANT a été repéré dans le
groupe couleur de `_CASE_PIECE_RE` (contrôle existant, issues #87/#92/
#103) : le motif `(blanche?s?|noire?s?)` ne reconnaît QUE la forme féminine
"blanche"/"blanches" pour le blanc (jamais "blanc"/"blancs", qui n'a pas de
"h" final — contrairement à "noir"/"noire", où le motif fonctionne pour les
deux genres car l'un est un simple suffixe de l'autre). Conséquence : une
citation telle que « le fou blanc en e5 » ou « le cavalier blanc en d4 »
n'est actuellement JAMAIS reconnue par `detecter_case_piece_incoherente` ni
`detecter_clouage_errone` (faux négatif silencieux, jamais de faux
positif). Repéré car hors du périmètre strict de cette issue (modifier
`_CASE_PIECE_RE` affecterait deux contrôles déjà testés et n'a pas été
demandé) — **non corrigé**, seulement signalé à Alain. Le nouveau motif
`_CASE_PIECE_SANS_PREP_RE` introduit par cette issue utilise, lui, la forme
correcte à deux alternatives (`blancs?|blanches?|noirs?|noires?`, identique
à `_PIECE_COULEUR_ADJ_RE`) et n'est donc pas affecté.

### Nouveau cas de non-régression

`tests/cas_coach/rd1_cavalier_d4.case` (`rd1_cavalier_d4`), FEN et contexte
ci-dessus, `camp_alain: blancs`, `coup_propose: Rd1`, `meilleur_coup: Rd1` :

- la phrase réelle du signalement (« ... prépare à peser sur le pion d4/la
  colonne centrale ») est signalée, message citant le cavalier noir ;
- même idée avec le bon type de pièce (« le cavalier d4 ») reste verte ;
- un coup noté (« pousser d4 »), une simple mention de case (« le contrôle
  de d4 »), une négation (« il n'y a pas le pion d4... »), un verbe de mise
  en jeu (« pousser le pion d4 ») : tous verts ;
- couleur explicite correcte (« le cavalier noir d4 ») : vert ; couleur
  explicite incorrecte (« le cavalier blanc d4 ») : signalé ;
- non-régression du contrôle existant avec préposition et couleur
  explicite (« le pion noir en d4 ») : reste signalé, sans duplication par
  le nouveau contrôle ;
- plusieurs mentions dans le même texte et pièce qui change de camp après
  une suite de coups citée (« Après Qxd4 Qxd4, la dame d4... la dame d4... »
  — la dame NOIRE occupe réellement d4 après cette suite, vérifié avec
  python-chess) : reste verte.

Vérifié séparément (hors `.case`, cette position n'a structurellement aucun
pion capable d'atteindre d4) : sur une position distincte où un pion occupe
RÉELLEMENT d4, « le pion d4 » ne déclenche aucune alerte — confirmé par un
appel direct à `detecter_case_piece_sans_preposition_incoherente`.

### Tests

`python3 non_regression_coach.py` (vrai Stockfish, pas d'appel API) : les 7
cas (`bxh7_coup_interroge`, `c4_bxc6_bxc6_reste_verte`,
`dame_noire_c6_possessif_case`, `h4_menace_gxh3_defensif`,
`qa4_ligne_depart`, `rd1_cavalier_d4`, `re3_dame_contre_tour`) passent tous
— aucune régression sur les contrôles existants. Les faits bruts de la
position (cavalier noir en d4, attaqué par la dame d3 et le fou e3, défendu
par la dame d7 ; tour a1 non attaquée ; Rd1 double la dame d3 sur la
colonne d) ont été vérifiés directement avec python-chess et un vrai
Stockfish local (profondeur 18, Stockfish 16 trouvé sur ce poste,
`/usr/games/stockfish`).

**Limite** : aucun appel réel à l'API Claude n'a pu être effectué pour
cette issue — le fichier `.env` (clé API) est absent de ce worktree (comme
pour l'issue #106). Seule la vérification par les faits et par simulation
déterministe (`reponse_simulee_verte`/`reponse_simulee_signalee`, sans
appel API) a donc pu être menée ; Alain peut relancer `python3
non_regression_coach.py --api --repetitions 5` lui-même une fois la clé
disponible dans ce worktree, pour confirmer le comportement du vrai coach
sur ce nouveau cas.

La phrase « Rd1 met ta tour en jeu sur la colonne centrale, à l'abri »
(tour a1 non attaquée, donc sans objet) mentionnée dans le contexte du
signalement n'est pas traitée par cette issue : la tâche demandée (quatre
points, voir l'en-tête) ne porte que sur la détection pièce+case sans
préposition, pas sur cette formulation distincte repérée par Alain dans la
même conversation.
