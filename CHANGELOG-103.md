# Changelog — Issue #103

## Fiabilité du coach : contrôle de case étendu aux suites citées, reprises de phrase et possessifs contradictoires

Série de 20 appels réels après la fusion des issues #94 à #102 : les quatre
cas de non-régression passent 5 fois sur 5 (2 relances sur 20 appels), mais
la lecture des premières réponses ayant déclenché ces relances a révélé
trois défauts non couverts par les contrôles existants, tous dans la même
réponse du cas re3, essai 1 : « Le bon coup était Re8 ! Il force Qxe8 ...
et après Qxe8, ta dame en a8 capture la dame noire en e8 », puis « ton
fou... pardon — ton cavalier noir en g6 défend le fou qui vient de se
poser en e5 ».

### 1. Contrôle de case étendu aux positions des suites citées

`detecter_case_piece_incoherente` (`coach_reliability.py`) ne comparait
une case citée (« dame noire en e8 ») qu'à la position de départ et à la
position actuelle — un faux positif réel : « ta dame en a8 capture la
dame noire en e8 » est pourtant vraie dans la position atteinte en jouant
la suite citée « Re8 Qxe8 » (le meilleur coup suivi de la reprise forcée),
jamais dans les deux positions de référence seules.

Le contrôle accepte désormais un paramètre `candidats` (même construction
que les autres contrôles de suites du module, `_construire_candidats`) :
position de départ, position actuelle, après le coup proposé/réel/
meilleur, chaque étape des lignes (PV) fournies au coach, trait inversé
compris. Il ajoute en plus, pour chaque suite de coups CITÉE DANS LE
TEXTE lui-même (`_extraire_suites`), chaque position atteinte en la
rejouant depuis l'une de ces positions (`_rassembler_lectures` — coup
précédent cité et demi-coup caché compris, même tolérance que les
contrôles d'échange). Une case cohérente avec AU MOINS UNE de toutes ces
positions n'est plus jamais signalée ; une case dont la pièce annoncée
n'existe nulle part reste toujours signalée (`evaluer_fiabilite` construit
désormais `candidats_suites` AVANT d'appeler ce contrôle, pour pouvoir le
lui transmettre).

### 2. Reprises de phrase du coach

Nouveau contrôle `detecter_reprises_phrase` : repère une poignée de
marques de reprise/correction en cours de réponse, interdites par la
consigne de prompt — liste courte réglable en un seul endroit
(`_MARQUEURS_REPRISE`) :

- « pardon » et « ou plutôt » — reconnus seulement à proximité immédiate
  de points de suspension (`...`/`…`) ou d'un tiret (`—`), jamais au mot
  seul : ces deux mots ont un usage courant sans aucune correction
  (« sans pardon pour les erreurs », « ou plutôt » au sens de préférence)
  — en cas de doute, rien n'est signalé ;
- « excuse-moi »/« excusez-moi », « je me corrige », « je me reprends » —
  reconnus sans cette prudence (signaux jugés sans ambiguïté) ;
- « enfin, » en début de proposition, « non, » après un tiret ou des
  points de suspension.

Chaque détection donne une alerte `reprise_phrase` de gravité « orange »,
qui journalise le motif détecté et déclenche la relance automatique comme
toute autre alerte (`evaluer_fiabilite`/`llm_coach.get_coach_response` ne
distinguent jamais les alertes par type pour décider de relancer — seule
leur présence compte).

### 3. Possessifs contradictoires

Nouveau contrôle `detecter_possessif_incoherent` : repère « ton »/« ta »/
« tes » directement accolé (ou avec une courte apposition d'un mot) à un
nom de pièce suivi d'une couleur explicite ou du mot « adverse », contredit
par le camp d'Alain (`camp_alain`) :

- « ton cavalier noir » alors qu'Alain joue les Blancs → signalé ;
- « ton cavalier noir » alors qu'Alain joue les Noirs → non signalé
  (cohérent) ;
- « ton fou adverse » → toujours signalé, quel que soit le camp d'Alain
  (contradiction intrinsèque : « ton » désigne par construction une pièce
  d'Alain, jamais celle de son adversaire) ;
- « ton cavalier » seul (sans couleur ni « adverse ») → jamais signalé ;
  « tu »/« te » non concernés (consigne explicite de l'issue).

Sans `camp_alain` connu, seule la combinaison « ton »+« adverse » est
signalée (faux négatif assumé pour une couleur explicite, même philosophie
que le reste du module).

### Relance automatique

`llm_coach.get_coach_response` reprend désormais explicitement, dans le
message de relance, le motif détecté quand une alerte `reprise_phrase`
et/ou `possessif_incoherent` fait partie des alertes de la première
réponse — consignes ciblées ajoutées au rappel générique existant, jamais
à sa place.

### Tests

`tests/cas_coach/re3.case` (camp_alain blancs) et `tests/cas_coach/
c4.case` (camp_alain noirs) reçoivent neuf nouvelles directives
`reponse_simulee_verte`/`reponse_simulee_signalee` :

- la phrase réelle « ta dame en a8 capture la dame noire en e8 » (suite
  « Re8 Qxe8 ») : verte (régression du point 1 ci-dessus) ;
- « ton fou... pardon — c'est une bonne case pour lui » : signalée
  (reprise isolée) ;
- « ton cavalier noir en g6 défend bien sa position » (camp_alain blancs) :
  signalée (possessif isolé) ;
- la phrase réelle combinée (« ton fou... pardon — ton cavalier noir... ») :
  signalée ;
- « sans pardon pour les erreurs passées » : verte (prudence, pas de
  reprise) ;
- « ton cavalier » seul : verte ;
- « ta dame blanche en h4 » (case inexistante dans toutes les positions) :
  toujours signalée ;
- « ton cavalier noir » avec camp_alain noirs : verte (c4.case) ;
- « ton fou adverse » avec camp_alain noirs : signalée (c4.case).

`python3 non_regression_coach.py --verbose` (sans `--api` — aucune clé API
configurée dans ce worktree, `config.LLM_API_KEY` vide, cohérent avec
`RESEAU: non` de l'issue) : les quatre cas (`bxh7_coup_interroge`,
`c4_bxc6_bxc6_reste_verte`, `h4_menace_gxh3_defensif`,
`re3_dame_contre_tour`) restent **OK**, code de sortie 0 — aucune
régression sur les contrôles d'attaque, d'échange, de bilan ou de suites
illégales existants. Vérifications manuelles directes de
`coach_reliability.detecter_reprises_phrase`/`detecter_possessif_
incoherent` sur les variantes « pardon »/« ou plutôt » en emploi normal,
« enfin, », « non, », « excuse-moi », « je me corrige », « je me
reprends ».

### Limites assumées

- une marque de reprise hors de la liste `_MARQUEURS_REPRISE`, ou une
  tournure de reprise sans aucune des ponctuations attendues (points de
  suspension, tiret), échappe au contrôle (faux négatif délibéré,
  préférable à un faux positif sur un emploi courant) ;
- un possessif contradictoire exprimé autrement que « ton »/« ta »/« tes »
  directement accolé à la pièce (ex. une couleur citée plus loin dans la
  phrase) n'est pas détecté, même limite d'adjacence stricte que le reste
  du module ;
- le contrôle de case reste tolérant par construction : une ligne
  hypothétique qui ne part d'aucune position connue (départ, actuelle,
  lignes principales, suites citées) échappe toujours à la détection.

Pas d'appel API réel effectué (clé absente de l'environnement de ce
worktree, `RESEAU: non`) — seules les vérifications locales (faits,
réponses simulées) ont pu être relancées.
