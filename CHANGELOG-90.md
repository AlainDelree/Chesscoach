# Changelog — Issue #90

## Coach : fiabilité 3 — le contrôle des coups cités ne signale plus à tort une suite légale, et `lire_signalements.py` affiche la pastille et sa raison

Cas réel ayant motivé cette issue (signalement d'Alain, 2 octobre 2026) :
exercice « Mes erreurs », FEN
`r1b1kbnr/pp3ppp/1qn1p3/1Bpp4/3PP3/2PQ1P2/PP4PP/RNB1K1NR b KQkq - 4 6`, coup
proposé c4 (imprécision), meilleur coup Nf6. La réponse du coach était
correcte (Stockfish confirme Nf6 ≈ +1,3, c4 ≈ +0,6 pour les Noirs, toutes
les lignes citées sont légales), mais la pastille est passée au rouge :
« coup cité "bxc6" illégal... », déclenchant une relance automatique
inutile. Cause : le contrôle introduit par l'issue #87 testait chaque coup
cité ISOLÉMENT sur la position de départ puis la position actuelle (trait
inversé compris) — alors que le coach cite des SUITES ("Bxc6+ bxc6", "Qc2
Nf6 Ne2"...), dont chaque coup ne devient jouable qu'après les précédents
de la même suite.

### 1. Suivi des suites de coups cités (`coach_reliability.py`)

- `_extraire_suites(texte)` (remplace l'ancienne extraction coup par coup) :
  regroupe les coups cités en SAN consécutifs dans le texte en suites —
  séparés uniquement par un espace, une virgule, un numéro de coup
  ("12."/"12..."/"6...") ou une annotation (!, ?, !?, ?!) ; tout autre texte
  interrompt la suite en cours (ex. "Après Nf6 Ne2 c4 ... la ligne continue
  Bxc6+ Qxc6" produit deux suites distinctes). Détecte aussi les suites
  "douteuses" : coup cité entre parenthèses, ou introduit par "si"
  (hypothèse jamais vérifiée, point 2).
- `_construire_candidats(...)` : construit, dans l'ordre demandé, les
  positions depuis lesquelles essayer de jouer une suite — position de
  départ, position actuelle, après le coup proposé, après le coup
  réellement joué, après le meilleur coup, puis CHAQUE position
  intermédiaire des lignes (PV) calculées par le moteur pour le coup
  proposé et pour le meilleur coup (en reprenant la suite à chacune de
  leurs étapes), et enfin le trait inversé des deux positions de référence
  directes (conservé de l'issue #87, pour un coup isolé cité du point de
  vue de l'adversaire).
- `_tenter_suite(coups, board)` : rejoue une suite coup par coup sur une
  COPIE de la position candidate, en distinguant trois issues :
  `chess.IllegalMoveError` (coup syntaxiquement valide mais impossible —
  seul cas qui compte comme un échec réel), et `chess.AmbiguousMoveError`/
  `chess.InvalidMoveError` (notation ambiguë ou invalide — jamais traitée
  comme une preuve d'illégalité, point 2).
- `detecter_suites_illegales(texte, candidats)` : une suite n'est signalée
  QUE si elle est injouable depuis TOUTES les positions candidates ET que
  cet échec n'est, sur aucune d'elles, une simple ambiguïté/notation
  invalide, ET qu'elle n'a pas été marquée "douteuse" à l'extraction. Les
  alertes portent désormais `coups_cites` et `positions_essayees` (liste
  des libellés essayés, dans l'ordre), pour le journal (point 3).
- `evaluer_fiabilite` accepte 5 nouveaux paramètres optionnels
  (`coup_propose`, `coup_reel`, `meilleur_coup`, `pv_coup_propose`,
  `pv_meilleur_coup`, tous `""` par défaut) transmis par l'appelant — sans
  eux, le contrôle se limite comme avant aux deux positions de référence.
- **Correctif annexe sur `_SAN_RE`** : la frontière de fin `\b` échouait
  silencieusement sur un coup se terminant par "+"/"#" suivi d'un espace
  (deux caractères non-mot consécutifs ne forment jamais une frontière
  `\b`) — "a8=Q+" était tronqué en "a8=Q", que python-chess rejette ensuite
  (il exige la notation d'échec exacte). Remplacé par une anticipation
  négative `(?!\w)`, qui accepte correctement tout caractère suivant non
  alphanumérique (espace, virgule, fin de texte) — nécessaire pour "gérer
  correctement les échecs et mats notés avec + ou #" (cahier des charges,
  point 2).

### 2. Prudence (point 2)

En cas de doute (coup isolé non rattachable à une suite résolue, notation
ambiguë/invalide, coup entre parenthèses ou introduit par "si"), rien n'est
signalé : pas de pastille orange ni rouge, pas de relance. Seule une suite
dont TOUS les points de départ essayés la rendent franchement illégale (pas
une ambiguïté) déclenche encore une alerte — donc toujours la relance
automatique UNIQUE existante (issue #87, point 4, non modifiée).

### 3. Journal (`llm_coach.py`)

- Les deux appels à `coach_reliability.evaluer_fiabilite` (réponse initiale
  et relance) transmettent désormais `coup_propose`/`coup_reel`/
  `meilleur_coup`/`pv_coup_propose`/`pv_meilleur_coup`, relus tels quels
  depuis `context` (déjà présents pour construire le texte de contexte
  envoyé au coach — rien de recalculé).
- Chaque alerte (`coup_illegal`) porte désormais `coups_cites` et
  `positions_essayees` — écrits tels quels dans l'entrée du journal
  (`fiabilite.alertes`, champ déjà journalisé par `_log_coach_call` depuis
  l'issue #87) : permet de juger après coup un éventuel faux positif sans
  deviner quelles positions ont été essayées.

### 4. `lire_signalements.py` (commande `sigcoach`)

- `_charger_index_journal()` : index `{id: entrée}` de tout
  `coach_calls.log` (toutes archives comprises), construit UNE SEULE FOIS
  par exécution plutôt que rescanné à chaque signalement affiché.
- `_trouver_entree_journal` accepte désormais cet index en paramètre
  optionnel (repli sur un chargement à la volée si omis — compatible avec
  l'usage existant dans `_texte_pret_a_coller`).
- `_lignes_pastille(journal)` (nouveau) : affiche la pastille (couleur +
  raison), l'avertissement éventuel (avant relance) et les contrôles
  déclenchés (type, détail, positions essayées) relus dans l'entrée du
  journal reliée par `log_id` — une seule ligne dédiée si cette entrée est
  introuvable (log_id absent ou archive déjà purgée), au lieu de rien
  afficher du tout. Câblé dans `_afficher_resume` (listing `--n`) ET
  `_texte_pret_a_coller` (`--dernier`).

### Tests effectués

- **Reproduction exacte du cas réel** (FEN de l'issue, textes calqués sur
  les passages cités : "Bxc6+ bxc6, un échange équilibré", "la suite Qc2
  Nf6 Ne2", "Après Nf6 Ne2 c4 ... la ligne continue Bxc6+ Qxc6") :
  `evaluer_fiabilite` → vert, aucune alerte. Vérifié aussi de bout en bout
  via `llm_coach.get_coach_response` avec `_call_claude` simulé (réponse
  fixe) : **1 seul appel API, aucune relance**, pastille verte — contre 2
  appels et une pastille rouge avant ce correctif (reproduit sur le code
  d'avant modification avant de corriger, pour confirmer le faux positif).
- **Casse jamais confondue** : `bxc6` (pion) isolé reste détecté illégal
  (rouge) sur la position de départ seule ; `Bxc6+` (fou) isolé reste
  légal (vert) — comportement identique avec ou sans la casse, aucune
  normalisation ne touche à la casse à aucune étape.
- **Suite légale citée depuis le coup réel/meilleur coup** : vérifié via le
  cas réel ci-dessus (suite "Nf6 Ne2 c4 Bxc6+ Qxc6" entière, point de départ
  = position de départ ; suite "Qc2 Nf6 Ne2", point de départ = position
  intermédiaire de `pv_coup_propose`).
- **Coup réellement illégal** (`Nxe3`, régression du cas Re3 de l'issue
  #87, FEN `Q7/ppkq3p/2p3n1/2Pp1p2/1P6/2b5/P5PP/4R2K w - - 9 35`) : toujours
  détecté, rouge, confirmé aussi de bout en bout (2 appels API, 1 relance,
  pastille rouge si la relance ne corrige pas).
- **Suite partiellement ambiguë** (position fictive à deux cavaliers
  pouvant tous deux rejoindre la même case, `Ne6` ambigu — confirmé
  `chess.AmbiguousMoveError` isolément) : rien signalé, pastille verte.
- **Coup entre parenthèses** ("si Txh8 les Noirs gagnent une pièce" entre
  parenthèses) et **coup hypothétique introduit par "si"** ("Si Dxd5
  alors...") : rien signalé dans les deux cas, pastille verte.
- **Roque, promotion, échec, mat, annotations, numéros de coup** : "12.
  O-O-O! et après ... Rb8" et "1. b8=Q+ et le roi noir est en échec" →
  vert dans les deux cas (le second a aussi servi à révéler puis corriger
  le bug de frontière `\b`/`(?!\w)` ci-dessus).
- **Non-régression** : texte neutre sur la position de l'exercice h4
  (`1r1r2k1/4Qpbp/2Bp1n2/3Pp2q/2P1P1p1/2N3PP/PP3PK1/R1B2R2 w - - 0 23`,
  issue #80) → vert, aucun faux positif.
- **`lire_signalements.py`** testé avec des fichiers factices (jamais les
  fichiers réels d'Alain, écrits dans `/tmp` puis supprimés) : listing
  (`--n`) et `--dernier` affichent la pastille, l'avertissement et les
  contrôles déclenchés (avec positions essayées) d'une entrée existante ;
  une entrée introuvable (`log_id` inconnu) produit une ligne dédiée sans
  erreur.
- **Appel API réel** : non effectué — aucune `ANTHROPIC_API_KEY` ni fichier
  `.env` dans ce worktree isolé (`/home/alain/chesscoach-issue90`), conforme
  à la consigne de ne jamais lire ce fichier hors de l'usage normal de
  l'application. `_call_claude` simulé à la place (textes fixes calqués sur
  le cas réel), comme pour l'issue #87.
- `py_compile` sur `coach_reliability.py`/`llm_coach.py`/
  `lire_signalements.py` : OK.

### Limites assumées (documentées dans `coach_reliability.py`)

- Une ligne hypothétique qui ne part d'AUCUN des points de départ essayés
  (position de départ/actuelle, après coup proposé/réel/meilleur, étapes
  des deux PV) reste hors de portée — faux négatif assumé, jamais remplacé
  par une supposition sur une position non transmise.
- La détection "douteuse" (parenthèses, "si") est une heuristique textuelle
  simple (fenêtre de ~20 caractères avant/après le coup cité) — une
  tournure très différente exprimant la même prudence peut échapper à la
  détection et être vérifiée comme une affirmation normale.
- Ces contrôles ne vérifient toujours QUE des faits bruts (légalité,
  existence de pièce) — jamais la justesse stratégique ou tactique de
  l'explication.
