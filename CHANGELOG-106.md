# Changelog — Issue #106

## Fiabilité du coach : possessif contredit par la case (« ton cavalier en c6 » alors que la case appartient à l'adversaire)

Signalement d'Alain (7 octobre 2026, mode Exercice, « Confusion autour de
la dame noire »). Position `r1b2r1k/5ppp/2Nqpn2/p2P4/P2P4/3BP3/4QPPP/R4RK1
b - - 2 19`, Alain joue les Noirs. À la question « La dame noire reprend ?
Le cavalier ? Il est protégé par le pion », le coach a répondu : « Oui,
c'est exact : si Qxc6, le pion d5 reprend immédiatement en d5xc6 — ton
cavalier en c6 est bien défendu par ce pion. » Le fond était juste
(vérifié avec un vrai Stockfish : Qxc6 dxc6 perd la dame contre un
cavalier, +6,68 pour les Blancs à la profondeur 18), mais le cavalier en
c6 est BLANC — celui de l'adversaire, pas « ton cavalier » : Alain joue
les Noirs.

Le contrôle des possessifs contradictoires existant (`detecter_possessif_
incoherent`, issue #103) n'exige qu'une couleur explicite directement
accolée à la pièce, ou le mot « adverse » — ni l'un ni l'autre dans cette
phrase, donc aucune alerte, pastille verte à tort.

### Nouveau contrôle : possessif contredit par la case

`detecter_possessif_case_incoherent` (`coach_reliability.py`) détecte un
possessif « ton »/« ta »/« tes » (ou « mon »/« ma »/« mes », si le texte
parlait à la première personne — même traitement) accolé à un nom de
pièce suivi DIRECTEMENT d'une case, SANS couleur ni mot « adverse »
explicite entre les deux (`_POSSESSIF_PIECE_CASE_RE` — une négation
exclut explicitement le cas déjà couvert par `detecter_possessif_
incoherent`, pour ne jamais dupliquer ce contrôle).

Il compare la couleur de la pièce RÉELLEMENT présente sur la case citée
aux mêmes positions que `detecter_case_piece_incoherente` : position de
départ, position actuelle, chaque position de `candidats` (lignes
principales et trait inversé compris) et chaque position atteinte en
jouant les suites de coups citées dans le texte lui-même (coup précédent
cité et demi-coup caché compris, via `_extraire_suites`/`_rassembler_
lectures`, jamais recalculés — réutilisation complète, aucune règle de
lecture de suite dupliquée). La détection du camp d'Alain réutilise aussi
`_camp_alain_chess`, déjà présent pour les possessifs avec couleur.

Une incohérence n'est signalée que si, dans TOUTES les lectures où une
pièce de ce type occupe cette case (toutes couleurs confondues), cette
pièce appartient à l'adversaire d'Alain — une seule lecture où elle lui
appartient suffit à ne rien signaler, ce qui couvre aussi, sans règle
dédiée, le cas d'une pièce qui change de camp sur cette case d'une
lecture à l'autre (typiquement après une prise citée). Si la case ne
contient ce type de pièce dans aucune lecture (case vide, ou seulement un
autre type de pièce), rien n'est signalé non plus : c'est alors
`detecter_case_piece_incoherente` qui a vocation à couvrir cette case (si
une couleur y est explicitement citée). Sans `camp_alain` connu, ce
contrôle reste totalement inactif.

Gravité « orange » par défaut, « rouge » si un connecteur de
justification de verdict suit à proximité ou si la même paire (type de
pièce, case) se répète dans le texte — même heuristique approximative que
`detecter_attaque_defense_incoherente` (réutilise ses constantes
`_CONNECTEUR_VERDICT_RE`/`_FENETRE_CONNECTEUR_VERDICT`, jamais dupliquées).

`llm_coach.get_coach_response` reprend ce nouveau motif dans le message
de relance automatique (consigne ciblée en plus du rappel générique,
même traitement que `possessif_incoherent`).

### Nouveau cas de non-régression

`tests/cas_coach/dame_noire_c6.case` (`dame_noire_c6_possessif_case`),
FEN et contexte ci-dessus, `camp_alain: noirs`, `coup_propose: Qxc6`,
`meilleur_coup: Nxd5|exd5` (le vrai Stockfish installé préfère `Nxd5` à la
profondeur 18, `exd5` reste une alternative quasi égale) :

- la phrase réelle du signalement (« ... ton cavalier en c6 est bien
  défendu par ce pion ») reste signalée ;
- la même phrase avec « le cavalier adverse » à la place de « ton
  cavalier » (déjà couvert par `detecter_possessif_incoherent`, mais sans
  aucun possessif ici — rien à signaler côté nouveau contrôle) reste
  verte ;
- « ton cavalier en f6 » (cavalier noir, bien celui d'Alain) reste vert ;
- possessif juste avec une autre pièce/case (« ta dame en d6 »), case
  vide (« ton cavalier en h5 »), négation (« ton cavalier n'est pas en
  c6 ») : tous verts ;
- non-régression du contrôle à couleur explicite (issue #103) : « ton
  cavalier blanc en c6 » reste signalé après cet ajout.

### Tests

`python3 non_regression_coach.py` (vrai Stockfish, pas d'appel API) : les
5 cas (`bxh7_coup_interroge`, `c4_bxc6_bxc6_reste_verte`,
`dame_noire_c6_possessif_case`, `h4_menace_gxh3_defensif`,
`re3_dame_contre_tour`) passent tous — aucune régression sur les
contrôles existants. Les faits bruts de la position (cavalier blanc en
c6, attaqué par la dame noire, défendu par le pion blanc d5 ; Qxc6 dxc6
perd la dame contre le cavalier) ont été vérifiés directement avec
python-chess et un vrai Stockfish local (profondeur 18).

**Limite** : aucun appel réel à l'API Claude n'a pu être effectué pour
cette issue — le fichier `.env` (clé API) est absent de ce worktree. Seule
la vérification par les faits (`--api` non lancé) a donc pu être menée ;
Alain peut relancer `python3 non_regression_coach.py --api --repetitions 5`
lui-même une fois la clé disponible dans ce worktree, pour confirmer le
comportement du vrai coach sur ce nouveau cas.
