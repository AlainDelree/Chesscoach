# Changelog — Issue #101

## Coach : bénéficiaire d'un qualificatif d'échange fiabilisé, listes explicites d'attaques après la réponse adverse

Constat sur une série de 20 appels réels après la fusion des issues #94 à
#100 (cas re3 : 3 relances sur 5 ; cas bxh7 : 1 relance sur 5, dont un faux
positif). Deux correctifs déterministes, sans toucher au modèle lui-même.

### 1. Bénéficiaire de « favorable »/« défavorable » (coach_reliability.py)

`detecter_echanges_mal_qualifies` associait le camp bénéficiaire par simple
PROXIMITÉ textuelle (mot de camp le plus proche dans une fenêtre de 30
caractères) — faux positif réel : « ... en plus de forcer l'échange
favorable Bxg6 hxg6 si les Blancs s'y risquent » associait à tort
« favorable » aux Blancs, simplement cités dans une proposition
HYPOTHÉTIQUE introduite par « si », alors que l'échange est en réalité
favorable aux Noirs (lecture unique, -2 pour les Blancs).

Nouvelle fonction `_resoudre_beneficiaire_qualificatif` : un camp n'est
retenu que par une tournure EXPLICITEMENT liée au qualificatif —
attachement direct (« favorable aux Blancs », « favorable pour toi »,
« défavorable pour les Noirs », « défavorable à ton adversaire »,
immédiatement après le qualificatif, sans suite de coups ni proposition
intercalée), ou sujet sans ambiguïté dans la même proposition (« les
Blancs y gagnent » → Blancs bénéficiaire ; « les Blancs y perdent » →
Noirs bénéficiaire, l'inverse), à condition qu'aucune proposition
hypothétique ou subordonnée (si/que/qui/dont/où/alors que/bien que/parce
que/puisque) ne soit interposée entre le qualificatif et ce sujet. Sans
tournure explicite, le camp reste indéterminé et le qualificatif n'est
simplement pas vérifié (faux négatif assumé, même philosophie que le reste
du module). La vérification de « équilibré » (symétrique, aucun camp
nécessaire) est inchangée. `detecter_echanges_mal_qualifies` reçoit
désormais `camp_alain` (propagé depuis `evaluer_fiabilite`) pour résoudre
« toi »/« ton adversaire ».

### 2. Listes explicites d'attaques après la réponse adverse (game_facts.py)

Cas réel (position Re3, après Be5) : la donnée correcte existait déjà
(`_statut_attaque_case`, issue #87 — « Tour blanche en e3 n'est PAS
attaquée par ce coup »), mais noyée en fin d'une phrase mécanique par
ailleurs longue — le coach a quand même affirmé, 3 fois sur 5, que le fou
attaquait cette tour.

Deux ajouts dans `describe_pv_with_balance` (donc pour les trois sources
du mode Exercice, qui partagent toutes cette fonction), pour la réponse
adverse immédiate du coup proposé ET pour la première réponse après le
meilleur coup :
  - `_toutes_pieces_attaquees` : TOUTES les pièces des deux camps attaquées
    après ce coup (case, pièce, défenseur éventuel), tronqué à 6 pour
    rester court ;
  - `describe_attaques_liste` : bloc séparé combinant les cibles de la
    pièce qui vient de jouer et cette liste complète, avec une phrase
    explicite négative si la pièce du demi-coup précédent n'est PAS
    attaquée. Exemple réel (Re3 Be5) :
    « Après Be5, le fou noir en e5 attaque : Pion h2 ; il n'attaque PAS la
    tour blanche en e3 »
    « Pièces attaquées après ce coup (les deux camps) : Pion blanc en h2
    attaqué(e) par Fou e5 (Roi h1); ... »

### 3. Prompt (llm_coach.py)

Nouvelle consigne courte dans `_REPONSE_STRUCTUREE_ADDENDUM` (mode
Exercice) : ne jamais affirmer qu'une pièce en attaque une autre si cette
attaque ne figure pas explicitement dans les listes fournies ; en cas de
doute, ne pas parler d'attaque.

### 4. Cas de test

- `tests/cas_coach/re3.case` : nouveau motif interdit
  `fou\s+.{0,60}?attaque.{0,20}?tour` (variante sans « noir »/« adverse »,
  constatée dans 3 des 5 premières réponses), en plus de l'ancien motif ;
  trois `texte_contient` vérifiant la présence des nouvelles listes.
- `tests/cas_coach/bxh7_coup_interroge.case` : la phrase exacte de l'issue
  (« favorable ... si les Blancs s'y risquent ») reste verte ;
  « favorable aux Blancs » et « défavorable pour toi » (faux ici, camp_alain
  = noirs) sont désormais signalées ; « favorable pour toi » reste verte.

### Limites

- Aucun appel API réel n'a été possible dans ce worktree (pas de clé LLM
  configurée, `config.LLM_API_KEY` vide) — tous les tests ci-dessus
  passent par les vérifications déterministes (`reponse_simulee_verte`/
  `reponse_simulee_signalee`, `texte_contient`), jamais par un vrai appel
  au modèle. Impossible donc de mesurer un nombre de relances avant/après
  sur les 5 essais par cas demandés — seule la correction des contrôles
  déterministes sous-jacents a pu être vérifiée.
- Modes partie/analyse/ouverture inchangés et non concernés : `describe_
  pv_with_balance` (listes d'attaques) n'est appelé que par les deux sites
  du mode Exercice dans app.py ; `detecter_echanges_mal_qualifies` reste
  appelé pour tous les modes via `evaluer_fiabilite`, sans changement de
  comportement pour les textes qui ne contiennent aucune tournure
  explicite de bénéficiaire (faux négatif inchangé).
- `python3 non_regression_coach.py` (les 4 cas existants, faits
  déterministes uniquement, sans `--api`) : OK.
