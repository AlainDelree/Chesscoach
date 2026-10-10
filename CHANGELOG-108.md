# Changelog — Issue #108

## Coach : fiabilité 13 — lignes Stockfish numérotées, interdiction de donner raison sans vérifier, contrôle des lignes citées

Signalement d'Alain (10 octobre 2026, mode Exercice, « je ne comprends pas
cette ligne ») : la ligne du meilleur coup (« bxa6 Nxc4 Qa4+ Bd7 Qxc4 Qb8 »)
part de la position AVANT le coup d'Alain (Blancs au trait), alors que
l'échiquier affiché montre déjà la position APRÈS son coup proposé O-O
(Noirs au trait). Sans numéro de coup ni camp explicite dans les données
transmises au coach, Alain a objecté à tort que Qa4+ ne pouvait pas être sa
dame — le coach lui a donné raison sans vérifier, a mélangé les deux lignes
fournies en une suite illégale (« bxa6 Nxc4 Nxc4 puis Qa4+ »), a avoué ne
pas connaître l'ordre exact (« je ne veux pas improviser ») et a inventé un
solde matériel absent des données, sans qu'aucune pastille de fiabilité ne
se déclenche.

### 1. Lignes numérotées avec camp et position de départ (`game_facts.py`, `llm_coach.py`)

- `game_facts.describe_pv_numerotee(fen_depart, pv_text, camp_alain)` :
  reformate une ligne (PV) Stockfish en ajoutant la numérotation des coups
  et le camp de chacun entre crochets (`[toi]`/`[adversaire]`) — retourne
  `{"ligne": str, "camp_depart": "Blancs"|"Noirs", "numero_depart": int}`,
  `{}` si `fen_depart`/`pv_text` sont vides ou illisibles.
- `game_facts.describe_trait_camp(fen)` : camp au trait sur `fen`
  ("Blancs"/"Noirs"), `""` si illisible.
- `llm_coach._build_context_text` utilise ces deux fonctions pour :
  - remplacer la notation brute de `pv_coup_propose`/`pv_meilleur_coup` par
    la ligne numérotée, précédée d'une phrase qui nomme explicitement la
    position de départ et le camp au trait, ex. : « Ligne du meilleur
    coup, à partir de la position AVANT ton coup (Blancs au trait, coup
    10), numérotée avec le camp de chaque coup entre crochets
    ([toi]/[adversaire])... : 10. bxa6 [toi] Nxc4 [adversaire] 11. Qa4+
    [toi] Bd7 [adversaire] 12. Qxc4 [toi] Qb8 [adversaire] » ;
  - étendre la phrase déjà existante sur la différence position de
    départ/position actuelle par la précision explicite des camps au
    trait : « L'échiquier montre la position après ton coup proposé
    (Noirs au trait) ; les lignes du coup proposé et du meilleur coup
    ci-dessous partent, elles, de la position de DÉPART, AVANT ce coup
    (Blancs au trait) — ne confonds jamais le trait de l'une avec celui de
    l'autre. »
  - fallback silencieux sur l'ancien texte brut si `fen_depart_exercice`
    est absent ou si la ligne échoue à se rejouer entièrement (jamais de
    ligne numérotée partiellement tronquée).
- Ces deux blocs passent par le point d'assemblage UNIQUE partagé par les
  trois sources du mode Exercice (« mes erreurs », problèmes Lichess,
  position précise) : aucune modification nécessaire côté `app.py`.
- `coup_reel` et les réponses adverses (`reponse_adverse_*_texte`) ne sont
  PAS concernés : ce sont des coups/descriptions isolés, jamais une ligne
  de plusieurs coups susceptible d'être confondue avec une autre.

### 2. Consignes de prompt (`llm_coach._ANTI_INVENTION_ADDENDUM`)

Trois nouveaux paragraphes (partagés par le mode Exercice et tout autre
mode qui transmet un verdict/une PV) :

- **(a)** recopier une ligne citée TELLE QUE fournie, sans mélanger les
  coups de deux lignes différentes, en précisant de quelle position elle
  part et qui joue son premier coup — un coup étiqueté `[toi]` reste un
  coup d'Alain même si l'échiquier affiché montre l'autre camp au trait ;
- **(b)** vérifier une objection d'Alain sur le trait, un coup ou une ligne
  contre les lignes numérotées et le camp au trait fournis AVANT de lui
  répondre ; ne jamais commencer par « tu as raison » sans cette
  vérification ; corriger poliment si Alain se trompe ;
- **(c)** dire en une phrase qu'une information demandée n'est pas dans les
  données plutôt que de l'inventer ou de demander à Alain de « se fier » à
  un résultat non fourni — et utiliser directement une donnée déjà fournie
  (ligne numérotée...) plutôt que d'avouer ne pas la connaître.

### 3. Contrôle « ligne citée absente des lignes fournies » (`coach_reliability.py`)

- `detecter_ligne_absente_lignes_fournies(texte, candidats, pv_coup_propose, pv_meilleur_coup)`
  (nouveau, câblé dans `evaluer_fiabilite`) : pour toute suite d'AU MOINS
  TROIS coups citée par le coach (hors suite introduite par « si »),
  vérifie qu'elle correspond à une portion continue d'une des deux lignes
  réellement fournies par Stockfish (en ignorant `+`/`#`/`!`/`?` et les
  numéros de coup) — sinon alerte orange « ligne citée absente des lignes
  fournies », avec relance automatique qui demande de recopier une ligne
  fournie telle quelle.
- Lectures tolérées, et AUCUNE AUTRE (délibérément plus strict que le
  contrôle de légalité existant `detecter_suites_illegales`, qui accepte
  encore un demi-coup caché quelconque) : la suite telle que citée, et,
  si un coup a été cité juste avant elle dans le texte, la même suite
  précédée de ce coup. **Aucun demi-coup caché quelconque n'est jamais
  toléré ici**, y compris pour une suite de seulement trois coups — c'est
  précisément ce mécanisme, employé par `detecter_suites_illegales`, qui
  avait laissé passer la suite mélangée « bxa6 Nxc4 Nxc4 Qa4+ » du
  signalement.
- Prudence : une suite qui correspond à une ligne fournie jusqu'à SA FIN
  puis ajoute un ou deux coups légaux au-delà n'est jamais signalée
  (prolongement légal toléré, `_PROLONGEMENT_LIGNE_FOURNIE_MAX_COUPS = 2`,
  réglable) ; en cas d'ambiguïté sur ces coups supplémentaires, rien n'est
  signalé non plus.
- Hors de portée par construction (faux négatif assumé) : désactivé si
  aucune ligne n'est fournie (`pv_coup_propose`/`pv_meilleur_coup` vides,
  cas des modes hors exercice) ; une suite partant d'une position
  différente des deux lignes fournies reste hors de portée.

### 4. Aveux d'incertitude (`coach_reliability._MARQUEURS_REPRISE`)

- La liste réglable `_MARQUEURS_REPRISE` (issue #103) gagne un champ
  `categorie` (`"reprise"` pour les marqueurs existants, `"aveu_incertitude"`
  pour les nouveaux) et quatre nouveaux motifs, avec la même prudence que
  les autres (tournures assez univoques pour ne pas se déclencher sur un
  usage courant sans rapport) : « je ne veux pas improviser », « que je ne
  te donne pas avec certitude », « je ne suis pas sûr de l'ordre », « fie-toi
  au fait que ».
- `detecter_reprises_phrase` reporte désormais ce champ `categorie` dans
  chaque alerte ; `llm_coach.get_coach_response` l'utilise pour cibler sa
  consigne de relance automatique : une reprise de phrase se corrige en
  « n'écris pas de brouillon suivi d'une correction », un aveu
  d'incertitude se corrige en « relis les lignes numérotées fournies et
  utilise-les directement, l'information y figure déjà ».
- Relance ciblée également ajoutée pour le nouveau type d'alerte
  `ligne_absente_lignes_fournies` (point 3).

### 5. Cas de non-régression (`tests/cas_coach/qa4_ligne_depart.case`)

Nouveau cas, position et coups du signalement, question de suivi simulée
(« ça ne peut pas être ma dame, c'est aux noirs de jouer ») :

- faits attendus (vérifiés sans appel API, vrai Stockfish) : présence de la
  ligne du meilleur coup numérotée avec sa position de départ explicite, et
  de la phrase sur la position affichée vs la position de départ ;
- motifs interdits (dont `motifs_interdits_stricts` pour « tu as raison ») :
  « tu as raison » en début de réponse, la séquence « Nxc4 Nxc4 ... Qa4+ »,
  « je ne veux pas improviser » ;
- motifs attendus : référence à la position avant le coup (« avant ton
  coup »/« position de départ »/« Blancs au trait »), et « ta dame »/« ton
  coup » à propos de Qa4+ ;
- pastille attendue : vert.

### Tests

- `python3 non_regression_coach.py` (sans `--api`, vrai Stockfish) : les 6
  cas existants + le nouveau passent (« Faits : OK ») — confirmé qu'aucune
  régression n'a été introduite, y compris sur `bxh7_coup_interroge`
  (suite « Nxh7 Nxh7 Kxh7 » avec coup précédent cité, toujours verte).
- Vérification directe (hors harnais, car `reponse_simulee_verte`/
  `reponse_simulee_signalee` de `non_regression_coach.py` ne transmettent
  volontairement PAS `pv_coup_propose`/`pv_meilleur_coup` — sinon le
  nouveau contrôle aurait signalé à tort la suite de `bxh7_coup_interroge`,
  qui n'a aucun rapport avec les lignes réelles de ce cas-là) :
  - la phrase fautive du signalement (« bxa6 Nxc4 Nxc4 puis Qa4+ » + « je
    ne veux pas improviser ») déclenche bien les deux nouvelles alertes
    (`ligne_absente_lignes_fournies` et `reprise_phrase`/`aveu_incertitude`) ;
  - la recopie exacte d'une ligne fournie reste verte ;
  - une ligne fournie prolongée de deux coups légaux reste verte ;
  - une suite de trois coups ou plus, légale mais sans rapport avec les
    lignes fournies, est signalée orange ;
  - les quatre nouveaux marqueurs d'aveu ne se déclenchent pas sur des
    phrases neutres sans rapport (pas de faux positif sur « je ne suis pas
    sûr que ce plan fonctionne », « cette ligne illustre un ordre naturel
    des coups »...).
- `py_compile` sur `game_facts.py`, `llm_coach.py`, `coach_reliability.py`,
  `non_regression_coach.py`, `app.py` : OK.

### Limites

- Aucun appel API réel à Claude n'a été effectué (pas de clé configurée
  dans ce worktree, `.env` absent et non modifié) : les motifs interdits/
  attendus et la pastille du nouveau cas, qui ne peuvent être vérifiés
  qu'avec une vraie réponse du coach (`--api`, cf.
  `tests/cas_coach/README.md`), n'ont PAS été exécutés contre le modèle
  réel — seuls les faits transmis au coach (lignes numérotées, phrase sur
  la position affichée) ont été vérifiés avec un vrai Stockfish. Dès qu'une
  clé API est disponible, relancer `python3 non_regression_coach.py --api
  --repetitions 5 --verbose` pour valider le comportement réel du modèle
  sur ce cas et sur les six cas existants.
- Le contrôle de lignes citées (point 3) ne compare qu'aux lignes du coup
  proposé et du meilleur coup (les seules transmises en tant que "ligne"
  de plusieurs coups) — une suite partant d'une autre position (ex. une
  hypothèse sur un coup jamais proposé) reste hors de portée, comme pour
  les autres contrôles du module.
- `reponse_simulee_verte`/`reponse_simulee_signalee` (harnais de non-
  régression) ne permettent pas de tester le nouveau contrôle de lignes
  citées sans API : il dépend des lignes (PV) réellement calculées, que ce
  harnais ne transmet volontairement pas à ces deux directives (cf. point
  "Tests" ci-dessus) — vérifié directement par des appels Python ad hoc à
  `coach_reliability.evaluer_fiabilite` à la place.
