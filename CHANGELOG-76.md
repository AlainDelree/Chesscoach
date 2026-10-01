# Changelog — Issue #76

## Mode Exercice — variété et historique des positions, indicateur « déjà fait », bouton « Exercice suivant »

- Nouveau module `exercise_history.py` : historique local des exercices
  proposés (donnée personnelle, `config.EXERCICE_HISTORIQUE_PATH` =
  `data/exercice_historique.json`, hors git comme le reste de `data/`),
  indexé par FEN de départ — `{nb_fois, derniere_date, dernier_resultat}`
  par position. `enregistrer_proposition` (appelé au tirage) incrémente
  `nb_fois`/met à jour `derniere_date` sans toucher au résultat ;
  `enregistrer_resultat` (appelé après verdict) enregistre réussi/raté sans
  toucher `nb_fois`/`derniere_date`.
- `choisir_exercice` remplace le tirage uniforme avec remise d'origine
  (issue #7) par un tirage priorisant la variété : (1) positions jamais
  proposées, (2) à défaut positions « dues » pour révision espacée — ratées
  depuis `DELAI_REVISION_RATE_JOURS` (3 jours) ou réussies depuis
  `DELAI_REVISION_REUSSI_JOURS` (14 jours), ces deux constantes réglables en
  un seul endroit du module — (3) catégorie épuisée (ni 1 ni 2) : reprise du
  quart le plus ancien de la phase, délais ignorés. Dans le niveau retenu,
  tirage uniforme (comme l'origine, pas de pondération) en évitant si
  possible de reproposer la même « nature » (`sous_type`
  matériel/positionnel) que le tirage précédent — mémorisée côté serveur
  (`_dernier_sous_type_tire`, app.py), pas persistée entre deux lancements.
- `app.py` (`on_exercise_new`) : lit l'historique avant tirage (pour
  l'indicateur « déjà fait »), appelle `choisir_exercice`, puis
  `enregistrer_proposition` ; transmet au client `deja_fait`/`nb_fois`/
  `dernier_resultat` (état AVANT ce tirage). `on_exercise_answer` :
  enregistre le résultat (réussi = verdict Stockfish « bon », qui couvre
  aussi le cas « coup proposé == meilleur coup » puisqu'un coup identique au
  meilleur coup a toujours un delta_cp de 0, classé « bon » par
  `engine_stockfish.classifier_coup`) dès qu'un verdict a pu être rendu.
- `exercise.js`/`templates/index.html` : indicateur « Déjà fait · N fois ·
  dernier résultat : réussi/raté » dans la ligne d'état de l'exercice,
  couleur `--cc-text-muted` (jamais `--cc-accent`/terracotta, réservé au
  cliquable dans cette appli) — discret, non cliquable, n'empêche jamais de
  rejouer l'exercice, absent pour une position jamais proposée, visible dès
  l'affichage de la position (avant toute réponse). Visible sur mobile et
  grand écran (pas de media query spécifique, hérite du flux normal de la
  colonne du mode exercice).
- Bouton « Exercice suivant » : relance directement un exercice de la même
  catégorie (phase) que l'exercice en cours, sans ouvrir la feuille ni le
  sélecteur de phase (`exerciseCurrentPhase`, mémorisée à chaque tirage,
  indépendante du `<select>`). Grand écran : à côté de « Nouvel exercice »
  dans l'onglet Exercice. Mobile : devient l'action principale
  (`btn-filled`) de la barre du bas à 3 boutons (« Reprendre » / « Exercice
  suivant » / « Autre catégorie » — ex-« Nouvel exercice », renommé pour
  rester clair à 3 boutons côte à côte ; comportement inchangé, ouvre
  toujours la feuille de choix de phase) ; gap/padding/taille de police de
  la barre resserrés pour que les trois restent lisibles sans débordement
  horizontal sur un écran de 390px. Disponible dans tous les états d'un
  exercice déjà chargé (avant réponse, après verdict, en exploration
  libre) — comme `exercise_new`, aucun état serveur à nettoyer entre deux
  tirages.
- Tests : vrai appel socket.io/Stockfish/Flask-SocketIO possible depuis ce
  worktree (venv `~/ChessCoach/venv`, Stockfish 16 réel, les 1051 vraies
  entrées de `~/ChessCoach/data/erreurs_detectees.json`) — utilisé pour
  toute la vérification fonctionnelle, historique redirigé vers un fichier
  temporaire à chaque run pour ne jamais écrire dans les données
  personnelles réelles. Scénarios simulés et vérifiés bout en bout :
  positions réussies récemment → jamais reproposées tant qu'une alternative
  existe ; position ratée ancienne (10 jours) → seule à ressortir face à un
  reste de catégorie « réussi » récent ; catégorie épuisée (tout un pool
  « réussi » récent) → repli sur le quart le plus ancien. Indicateur « déjà
  fait » vérifié par capture d'écran (Playwright/Chromium réel) : absent sur
  une position neuve, texte et couleur (`--cc-text-muted`, pas
  `--cc-accent`) corrects sur une position connue. Plusieurs « Exercice
  suivant » enchaînés en catégorie Finale sans rouvrir la feuille, phase
  inchangée à chaque tirage, vérifié en grand écran ET sur émulation mobile
  390×750 (Playwright) : pas de débordement horizontal
  (`scrollWidth`/`clientWidth`), 3 boutons de la barre du bas lisibles. Pas
  de vrai appel à l'API Claude (pas de `ANTHROPIC_API_KEY` dans
  l'environnement de cette session) : le verdict Stockfish et
  l'enregistrement dans l'historique ne dépendent pas de cet appel (ont lieu
  avant), seul le commentaire du coach échoue proprement (`no_api_key`),
  sans rapport avec l'objet de cette issue.
- Limites connues : le compteur « nombre de fois proposé »/« déjà fait »
  est indexé par FEN de départ exacte — deux erreurs distinctes partageant
  rigoureusement la même position de départ (parties différentes) comptent
  comme un seul exercice du point de vue de l'historique, ce qui est le
  comportement voulu. L'anti-répétition « même nature à la suite »
  (`sous_type`) ne survit pas à un redémarrage de l'appli (mémoire de
  processus, pas de fichier) — jugé sans intérêt à persister pour un simple
  confort de variété à l'intérieur d'une session.
