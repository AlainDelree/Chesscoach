# Changelog — Issue #58

## Mode exercices : tableau "Lignes du coach", extraction + lecture des lignes citées sur l'échiquier

- Contexte : en mode exercice, le coach cite souvent une ligne de coups
  dans sa prose (ex. « la ligne logique est Kc3 Ke1 Kd3 Kd1 Ke3 Kc2 »),
  qu'Alain devait jusqu'ici rejouer à la main pour la visualiser.
- `static/coach_lines.js` (nouveau, composant réutilisable mode-agnostique,
  ne dépend que de chess.js) :
  - `extractCoachMoveLines(text)` — repère les suites d'au moins deux coups
    en notation standard (numéros de coups et annotations !?+# tolérés et
    retirés), dédoublonne, et ignore les chemins de cases séparés par des
    tirets (`c3-d3-e3`) qui ne sont pas des coups.
  - `resolveCoachLineStart(candidates, moves)` — détermine la position de
    départ par légalité (jamais par déduction) : essaie chaque candidat
    fourni dans l'ordre et retient le premier où tous les coups sont
    légaux ; retourne `null` si aucun candidat ne convient.
  - `playCoachLineSequence(steps, opts)` — lecture pas à pas avec pause
    configurable, callback de rendu fourni par l'appelant, contrôleur
    `{stop()}` pour interrompre en cours de route.
- `static/exercise.js` : nouveau tableau "Lignes du coach" dans le panneau
  du mode exercice, alimenté à chaque réponse du coach reçue pendant
  l'exercice actif (verdict `exercise_comment`, et questions de suivi
  posées dans le chat libre/à la demande pendant l'exploration après
  verdict, via le nouveau hook générique `exerciseOnCoachText`) :
  - Pour chaque ligne, deux candidats de départ sont essayés dans l'ordre :
    la position d'avant le coup d'Alain (`exerciseFenAvant` — couvre aussi
    le cas où la ligne commence par son propre coup), puis la position
    juste après (`exerciseFenApresCoup`, nouvelle variable capturée dans
    `submitExerciseAnswer`). Le tableau affiche laquelle a été retenue
    (« depuis la position de départ » / « depuis la position après ton
    coup »), ou « ligne non jouable » (discret, sans bouton) si aucune des
    deux ne convient.
  - Bonus : la meilleure ligne déjà calculée par Stockfish
    (`exercisePvMeilleurCoup`, transmise avec le verdict depuis l'issue
    #20) est ajoutée en première ligne, étiquetée « Ligne de Stockfish »,
    dédoublonnée contre une ligne identique citée par le coach en prose.
  - Bouton Play/Stop par ligne, sélecteur de vitesse (0,5 s / 1 s, 1 s par
    défaut) partagé par le tableau. Pendant la lecture, le plateau affiche
    la ligne (surlignage du dernier coup comme d'habitude) sans toucher à
    `exerciseGame`, à l'historique de l'exercice ni au chat, et sans
    déclencher de commentaire automatique — un bouton « Revenir à la
    position de l'exercice » (affiché dès la première lecture, masqué
    après usage) restaure la position réelle de l'exercice. Les clics sur
    le plateau sont bloqués tant que cette prévisualisation est active,
    pour ne jamais mélanger les deux positions.
  - Tableau vidé à chaque nouvel exercice (et à l'abandon), conservé lors
    d'un « Reprendre mon coup » (juste sorti du mode prévisualisation).
- `static/board.js` : `coach_response` et `coach_on_demand_response`
  appellent désormais `exerciseOnCoachText(text)` si cette fonction existe
  (no-op hors mode exercice) — mécanisme générique, pas de dépendance
  directe de board.js à exercise.js.
- `llm_coach.py` (`_EXERCISE_SYSTEM_ADDENDUM`) : consigne courte ajoutée au
  prompt du coach en mode exercice pour écrire toute ligne de coups en
  notation standard, coups séparés par des espaces — fiabilise
  l'extraction côté client.
- `templates/index.html` : inclusion de `coach_lines.js` (avant
  `exercise.js`) et nouveau bloc HTML `#exercise-coach-lines` (titre,
  sélecteur de vitesse, tableau, bouton de retour) dans le panneau du mode
  exercice.

### Tests réalisés

- Tests unitaires Node purs (extraction + résolution de légalité, sans
  navigateur) : exemple de l'issue (ligne démarrant par le coup d'Alain,
  résolue « depuis la position de départ »), ligne légale seulement depuis
  la position après le coup, ligne illégale depuis les deux candidats (→
  `null`, aucun bouton), faux positif `c3-d3-e3` (aucune ligne extraite),
  numéros de coups + annotations `!?+#` correctement nettoyés,
  dédoublonnage de lignes identiques.
- Tests bout en bout avec Playwright (Chromium) contre le serveur Flask du
  worktree, **avec de vrais appels à l'API Claude** (clé lue depuis le
  `.env` existant de `~/ChessCoach`, non modifié, seulement exportée dans
  l'environnement du process de test) :
  - Nouvel exercice → coup joué → verdict reçu → tableau peuplé
    correctement, avec une ligne Stockfish bonus et une ligne citée par le
    coach commençant par son propre coup (« depuis la position de
    départ »).
  - Un second essai a naturellement produit le cas « ligne qui ne démarre
    qu'après le coup d'Alain » (résolue « depuis la position après ton
    coup ») avec un vrai texte de coach.
  - Play → lecture animée visible sur le plateau (capture d'écran) → Stop
    en cours de lecture (bouton repasse à "Play", `exerciseGame.fen()`
    inchangé) → « Revenir à la position de l'exercice » restaure bien la
    position réelle et se masque ensuite ; nombre de bulles du chat
    inchangé après lecture/arrêt/retour (aucun commentaire auto, aucun
    effacement).
  - Ligne illégale injectée (`Qxh7 Rxh7` sur une position sans dame ni
    tour disponibles) → affichée « ligne non jouable », sans bouton ; texte
    contenant un chemin `c3-d3-e3` → aucune ligne fantôme créée.
  - Viewport mobile 390×844 (tactile, `page.tap`) : tableau lisible sans
    débordement horizontal, bouton Play ~52×44 px (cible tactile correcte),
    Play/Stop/retour fonctionnels au toucher.
- `python3 -m py_compile` sur les fichiers Python modifiés, `node --check`
  sur les fichiers JS modifiés/créés.
