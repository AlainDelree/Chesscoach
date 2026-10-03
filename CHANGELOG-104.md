# Changelog — Issue #104

## Fiabilité du coach : inventaire de matériel pris pour un échange, motif interdit re3 resserré

Série de 20 appels réels après la fusion des issues #94 à #103 : 18 cas sur
20 (bxh7 5/5, c4 5/5, h4 4/5, re3 4/5), trois relances, toutes sur re3. Les
deux échecs venaient des contrôles, jamais du coach :

1. Cas h4, essai 1 : pastille rouge « cavalier contre dame » sur un texte
   contenant « tu restes solidement en avance au matériel (dame, deux
   tours, deux fous, un cavalier contre dame, deux tours, un fou, un
   cavalier pour l'adversaire) » — ici « contre » sépare deux énumérations
   de pièces (le décompte d'Alain, puis celui de l'adversaire), ce n'est
   pas un échange. La règle « X contre Y » (issue #99) l'a pris pour un
   échange et l'a rattaché à la suite citée juste avant. Réponse correcte,
   relance inutile : faux positif pur.
2. Cas re3, essai 4 : échec du motif interdit `\bfou\b.{0,60}?attaque.{0,20}?tour`
   sur « Re3 attaque bien le fou en c3 et le met hors de portée de son
   attaque sur ta tour » — phrase exacte et correcte. Le motif était trop
   large : il attrape toute phrase où « fou » précède « attaque » puis
   « tour », même séparés par un « son attaque » sans rapport.

### 1. Règle « X contre Y » resserrée (`coach_reliability.py`)

`detecter_echange_type_incoherent` ne traite désormais un match de
`_ECHANGE_TYPE_CONTRE_RE` comme un échange (`_est_echange_type_contre`) que
si l'une des deux conditions suivantes est vraie :

- le mot « échange »/« échanger »/« échanges »/« troc » apparaît dans les
  40 caractères qui précèdent, dans la même proposition (jamais au-delà
  d'un « . »/« ; » rencontré en remontant, `_mot_echange_proche_contre`) ;
- « X contre Y » suit IMMÉDIATEMENT la suite de coups citée elle-même,
  sans aucun autre mot entre les deux (`_suit_suite_sans_autre_mot`).

Même quand l'une de ces conditions est vraie, « X contre Y » reste ignoré
s'il ressemble à un inventaire de matériel plutôt qu'à un échange
(`_ressemble_inventaire_materiel`) :

- les mots « matériel »/« avantage »/« adversaire »/« adverse » à
  proximité immédiate (±100 caractères) — couvre « en avance au
  matériel (...) », « ... pour l'adversaire », « côté adverse » ;
- « contre » séparant deux énumérations de pièces : une virgule suivie
  (avec ou sans quantité) d'un type de pièce juste avant le match, ou
  juste après.

En cas de doute (aucune des deux conditions n'est remplie), rien n'est
signalé, comme demandé. Comportement inchangé pour « échange de X contre
Y » (le mot « échange » précède toujours « de X contre Y » de peu) et pour
« échange de X » seul (`_ECHANGE_DE_TYPE_RE`, jamais concerné par ces
gardes-fous).

### 2. Motif interdit re3 resserré (`tests/cas_coach/re3.case`)

Le motif `regex:\bfou\b.{0,60}?attaque.{0,20}?tour` est remplacé par un
motif limité à l'idée fausse réellement visée (« après Be5, le fou attaque
la tour », qui est géométriquement impossible) :

```
regex:apr[eè]s\s+Be5\b(?:(?!son\s+attaque\b|avant\b|[.\n]).){0,120}?\bfou\b(?:(?!son\s+attaque\b|avant\b|[.\n]).){0,60}?attaque(?:(?!son\s+attaque\b|avant\b|[.\n]).){0,20}?(?:ta|la)\s+tour
```

Exige désormais une citation « après Be5 » dans la MÊME phrase (jamais
au-delà d'un « . »/retour à la ligne, ni d'un « son attaque »/« avant »
entre les deux) juste avant « le fou ... attaque ... (ta|la) tour ».

### 3. Cas de test ajoutés

- `h4.case` : réponse simulée verte contenant exactement l'inventaire de
  matériel cité ci-dessus après « Qg6 Re1 h6 » ; réponse simulée signalée
  pour « un échange de cavalier contre dame » après Qxh4 gxh4 (faux : la
  dame noire y est perdue contre un pion).
- `re3.case` : réponse simulée verte pour la phrase exacte « Re3 attaque
  bien le fou en c3 et le met hors de portée de son attaque sur ta tour » ;
  réponse simulée signalée pour « Après Be5, le fou attaque ta tour »
  (variante sans qualificatif de couleur de l'invention déjà couverte).

### Tests

Vérifié directement via `coach_reliability.detecter_echange_type_incoherent`
et `non_regression_coach._motif_interdit_present` (sans appel API) :

- l'inventaire de matériel du cas h4 (vert) et « un échange de cavalier
  contre dame » après Qxh4 gxh4 (signalé) ;
- « Bxc6+ Qxc6, un échange de cavalier contre fou » (cas c4, vert,
  inchangé) ;
- « cavalier contre fou » (vrai) et « cavalier contre cavalier » (faux)
  immédiatement après une suite de captures citée, SANS le mot
  « échange » : traités comme un échange (condition 1, deuxième
  disjonction) — vert pour le premier, signalé pour le second ;
- la même affirmation fausse, ni précédée du mot « échange » ni collée à
  la suite citée : ignorée (prudence, « en cas de doute ») ;
- le nouveau motif re3 : vert sur la phrase réelle de l'essai 4,
  signalé sur « après Be5, le fou attaque ta tour » et sur l'ancienne
  phrase fautive « Après Be5, ton fou adverse attaque la tour. ».

`python3 non_regression_coach.py --cas h4_menace_gxh3_defensif
re3_dame_contre_tour c4_bxc6_bxc6_reste_verte` (sans `--api`, donc sans
appeler Claude) : les trois cas passent `OK` sur `faits_attendus`, y
compris les nouvelles lignes `reponse_simulee_*` — aucune régression
constatée sur les contrôles d'attaque, de bilan, de suites illégales, de
case, de reprise de phrase et de possessif. Le cas `bxh7_coup_interroge`
est flaky indépendamment de ce changement (confirmé en rejouant sur le
code d'avant cette issue, via `git stash` : échec/succès alternent selon
l'exécution — meilleur coup Stockfish calculé différemment d'une fois à
l'autre, `Re8` vs `Nb4`), cause externe (moteur), non liée à cette tâche.

### Limites

Aucun vrai appel API n'a été fait dans cette session (pas de relance avec
cinq essais par cas) — seuls les contrôles déterministes (sans API) ont
été exercés, comme listé ci-dessus. Le motif interdit `.case` n'est de
toute façon vérifié que sur une vraie réponse API (`--api`), jamais sur
les `reponse_simulee_*` (qui testent uniquement `coach_reliability.py`) ;
les deux nouvelles entrées sur chaque cas couvrent donc les deux chemins
séparément. La règle « X contre Y » reste une heuristique textuelle : un
inventaire de matériel rédigé différemment (sans virgule, sans mot
« matériel »/« adversaire » à proximité) pourrait encore échapper à ce
garde-fou et être pris pour un échange — faux négatif assumé, prudence
préférée à un risque de masquer un vrai échange mal qualifié.
