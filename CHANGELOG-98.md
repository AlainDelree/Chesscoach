# Changelog — Issue #98

## Coach : phrases d'attaque/défense, relances justifiées dans le script de non-régression, motifs interdits insensibles aux emplois non affirmatifs

Cas réel (20 appels réels, script de non-régression, 4 cas x 5 essais,
Sonnet, après la fusion des issues #94 à #97) : re3 3/5. Essai 5, pastille
orange — alerte `echange_type_incoherent` correcte sur « échange de dame »
accolé à « Qxe8 Qxe8 », corrigée par la relance automatique (orange
mérité, le script la comptait pourtant comme un échec faute d'attendre du
vert) ; la réponse finale contenait malgré tout encore une erreur non
détectée : « après Be5, ton fou adverse attaque la tour », alors que le
fou noir en e5 n'attaque pas la tour en e3 (vérifié python-chess : il
attaque a1, b2, c3, c7, d4, d6, f4, f6, g3, g7, h2, h8). Essai 3 : échec du
motif interdit « équilibre matériel » sur la phrase correcte « l'équilibre
matériel reste nettement en ta défaveur » (emploi non affirmatif).

### 1. Nouveau contrôle déterministe : phrases d'attaque/défense (`coach_reliability.py`)

- `detecter_attaque_defense_incoherente` : reconnaît une phrase simple,
  active (« le fou attaque la tour », « la dame défend le pion g3 ») ou
  passive (« le cavalier est attaqué par le fou »), et la compare à la
  géométrie réelle (python-chess, `Board.attacks`) — une « défense » exige
  en outre que les deux pièces soient du même camp.
- Identification des deux pièces (type + couleur + case si possible) :
  couleur résolue via « adverse » (camp opposé à `camp_alain`), « noir(e)
  (s) »/« blanc(he)(s) » (couleur absolue), « ton »/« ta »/« tes » (camp
  d'Alain) — « adverse » l'emporte sur « ton »/« ta » si les deux sont
  accolés à la même pièce (« ton fou adverse »). Une case citée juste après
  la pièce (avec ou sans « en »/« sur ») est AUTORITAIRE : elle complète ou
  vérifie la couleur directement depuis la position. Sans case ni couleur,
  la pièce n'est identifiée que si elle est la SEULE de ce type, toutes
  couleurs confondues, sur la position essayée — sinon la phrase entière
  n'est jamais signalée (prudence explicitement demandée).
- Position(s) essayée(s) : si la phrase est précédée d'une citation
  « après `<coup(s)>` » dans la même proposition, SEULES les positions
  obtenues en y jouant ce(s) coup(s) depuis chacune des positions
  candidates habituelles sont essayées ; sinon, toutes les positions
  candidates habituelles (position de départ/actuelle, après coup proposé/
  réel/meilleur, lignes PV...) le sont. Une incohérence n'est signalée que
  si TOUTES les lectures valides contredisent l'affirmation.
- Négation (« le fou n'attaque pas la tour ») : la négation française place
  « ne »/« n' » directement avant le verbe, ce qui empêche structurellement
  les regex de reconnaître la forme verbale attendue (adjacence stricte
  pièce+espace+verbe) — aucune règle de négation dédiée n'est nécessaire.
  Hypothèse (« si le fou attaque la tour ») : exclue explicitement (même
  `_SI_HYPOTHETIQUE_RE` que le reste du module), car la forme verbale
  reconnue (présent de l'indicatif) apparaît aussi sous « si ».
- Gravité « orange » par défaut, « rouge » si un connecteur de justification
  de verdict (« donc », « c'est pourquoi »...) suit à proximité ou si la
  même affirmation (même pièces+couleurs+relation) se répète dans le texte
  — heuristique volontairement approximative, documentée comme telle.
- `evaluer_fiabilite` accepte un nouveau paramètre optionnel `camp_alain`
  ("blancs"/"noirs", "" par défaut) transmis à ce contrôle ; `llm_coach.
  get_coach_response` le fournit désormais depuis `context["camp_alain"]`
  aux deux appels (réponse initiale et après relance).
- Non détecté (limites assumées, documentées en tête du contrôle) : une
  tournure plus élaborée que la forme simple reconnue (relative,
  énumération...), une pièce non identifiable sans ambiguïté, une
  affirmation « centrale » sans connecteur explicite (reste alors
  « orange » au lieu de « rouge »).

### 2. Script de non-régression (`non_regression_coach.py`)

- `llm_coach.get_coach_response` enrichit désormais le dict `fiabilite`
  (clés ajoutées en fin de dict, aucun impact sur un lecteur existant —
  `app.py`/`board.js` ne lisent que `couleur`/`raison`) de
  `relance_effectuee`, `relance_corrigee` et `premiere_reponse_texte` dès
  qu'une relance automatique de fiabilité a eu lieu.
- `verifier_reponse` : une pastille « orange » obtenue parce qu'une
  relance automatique a corrigé une première réponse fautive
  (`fiabilite["relance_corrigee"]`) est désormais comptée comme un essai
  RÉUSSI quand `pastille_attendue: vert` (plutôt qu'un échec de pastille)
  — une pastille rouge, ou orange SANS relance justifiée (ex. analyse
  indisponible), reste un échec inchangé.
- Nouveau bloc `motifs_interdits_stricts` (fichier `.case`) : comme
  `motifs_interdits`, mais vérifié EN PLUS sur la toute PREMIÈRE réponse du
  coach (`fiabilite["premiere_reponse_texte"]`) si une relance a eu lieu —
  pour les motifs jugés trop graves pour tolérer qu'ils aient seulement été
  corrigés après coup.
- Nouvelle colonne « Relances » dans le tableau récapitulatif (ex. `1/5
  relance(s) corrigée(s)`), distincte de la colonne « API réussites » et
  du détail des échecs.

### 3. Cas de test (`tests/cas_coach/re3.case`, `h4.case`)

- `re3.case` : le motif interdit `équilibre matériel` est remplacé par
  `regex:\béquilibre\s+mat[ée]riel\b(?!.{0,25}?(?:faveur|nettement))` — ne
  se déclenche plus quand l'expression est suivie, dans les 25 caractères,
  de « défaveur », « faveur » ou « nettement » (couvre la phrase correcte
  ayant motivé ce correctif).
- `re3.case` : nouveau motif interdit `regex:fou\s+(?:noir\w*|adverse\w*)
  .{0,60}?attaque.{0,20}?tour` — reconnaît directement, sur le texte, la
  phrase fausse ayant motivé le contrôle 1 ci-dessus (seconde vérification
  indépendante de la pastille).
- `re3.case`/`h4.case` : `reponse_simulee_verte` ajouté pour « l'équilibre
  matériel reste nettement en ta défaveur » (non signalé), et
  `reponse_simulee_signalee` ajouté sur `re3.case` pour « après Be5, ton
  fou adverse attaque la tour » (signalé).

### Tests effectués

- Suite complète sans `--api` (faits + Stockfish réel) : 4/4 cas OK,
  inchangé (bxh7, c4, h4, re3).
- `coach_reliability.detecter_attaque_defense_incoherente`, testé
  isolément et via `evaluer_fiabilite` sur la position réelle (Re3 Be5) :
  phrase fausse → orange (rouge si connecteur de verdict ou répétition),
  « Re3 attaque le fou en c3 » (sujet non reconnu comme pièce) → rien,
  « le fou noir attaque ton pion h2 » → rien (vrai), deux fous possibles
  sans case/couleur → rien, négation → rien, hypothèse → rien. Testé aussi
  sur des positions synthétiques pour la relation « défend » (vrai, faux
  par géométrie, faux par couleur différente) et la forme passive.
- `verifier_reponse`/`executer_cas` : scénarios simulés (fiabilite
  construits à la main, sans appel API réel) couvrant orange+relance
  corrigée (succès, motif strict détecté dans la première réponse),
  orange sans relance (échec), rouge (échec) — comptage `n_ok`/`relances`
  vérifié sur une séquence de 5 tentatives simulées.
- Appel API réel IMPOSSIBLE dans cet environnement : `config.LLM_API_KEY`
  (`ANTHROPIC_API_KEY`) est absent de ce worktree — vérifié (`python3 -c
  "import config; print(bool(config.LLM_API_KEY))"` → `False`), `.env` non
  touché. À relancer manuellement avec `python3 non_regression_coach.py
  --api --repetitions 5` depuis un environnement où la clé est disponible.
