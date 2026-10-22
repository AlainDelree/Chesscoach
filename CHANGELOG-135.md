# Changelog — Issue #135

## Format standard des avis du coach : sections fixes, règles de rédaction, lecture par l'appli (suite #125)

- Constat : les avis de Claude et de Mistral n'avaient aucune structure
  commune — certains avis de Mistral enchaînaient, dans le MÊME paragraphe,
  « le meilleur coup était... » et « à l'époque, tu avais joué... »,
  rendant la lecture confuse sur téléphone (trois coups différents sont en
  jeu : coup joué, meilleur coup Stockfish, coup de l'époque).
- Nouveau module `avis_format.py` : titres fixes imposés (`## Coup joué` /
  `### Évaluation rapide` / `### Points négatifs` / `### Points positifs` /
  `## Meilleur coup` / `### Explication` / `## Coup de l'époque` /
  `## Conclusion`), `parser_avis(texte)` (découpage déterministe, retourne
  `conforme`/`sections`, jamais d'exception) et `FORMAT_AVIS_VERSION = 2` —
  module partagé par `llm_coach.py`, `app.py` et `fact_checker.py`.
- `llm_coach.py` :
  - `_REPONSE_STRUCTUREE_ADDENDUM` remplacé (ancienne structure en 4
    paragraphes sans titre de l'issue #91) par le format à titres fixes
    ci-dessus, identique pour Claude (`get_coach_response`) et Mistral
    (`get_mistral_response`), avec les règles de rédaction demandées :
    évaluation rapide en une phrase reprenant exactement le verdict
    officiel ; listes « Points négatifs »/« Points positifs » à 3 éléments
    au plus, chacun rattaché à un coup précis ; coups cités numérotés
    (« 31.Re7 »/« 30...Rxb6 ») et nommés avec leur rôle (« ton coup »/« le
    meilleur coup »/« le coup de l'époque ») ; aucune attribution
    d'intention ni prédiction du prochain coup ; tout terme technique
    expliqué à son premier emploi ; « Meilleur coup » dit en une phrase
    quand le coup joué est déjà le meilleur ; « Coup de l'époque » omise en
    entier si identique au coup joué ou si aucune partie d'origine
    n'existe, sinon « non évalué » si son évaluation manque ; conclusion en
    un conseil unique et réutilisable ; tout fait absent → « non vérifié »
    ou silence.
  - `_EXERCISE_LICHESS_ADDENDUM` révisé : ne demande plus une réponse
    « courte, 2 à 4 phrases, sans titre » (contradiction directe avec le
    format ci-dessus) — garde le même format, omet seulement « Coup de
    l'époque ».
  - `_EXERCISE_SYSTEM_ADDENDUM`, point (7) « Mise en page » : renvoie
    désormais au format à titres fixes plutôt que de décrire des
    paragraphes sans titre.
  - `_build_context_text` : nouveau champ calculé `numero_coup_texte`
    (« 31. »/« 30... », lu directement dans le FEN via
    `game_facts.numero_coup_depuis_fen`) préfixé aux citations du coup
    proposé/coup réel/meilleur coup dans le contexte transmis à l'IA —
    les deux IA reprennent ce numéro, elles ne le recalculent jamais.
  - `_log_coach_call` : trois nouveaux champs optionnels
    (`avis_sections`, `avis_format_conforme`, `avis_format_version`),
    écrits dans `coach_calls*.log` pour tout appel en mode exercice (texte
    brut `reponse` toujours conservé en plus, rien n'est perdu même sur un
    format non conforme) ; alimentés par `get_coach_response`/
    `get_mistral_response` via `avis_format.parser_avis`.
- `game_facts.py` : nouvelle fonction publique `numero_coup_depuis_fen`
  (réutilise `_numero_coup` déjà existant) — numéro de coup PGN standard
  déduit directement du FEN (compteur de coup plein + trait), sans calcul
  de partie.
- `fact_checker.py` : `_verifier_mot_verdict_premiere_phrase` lit désormais
  la rubrique « Évaluation rapide » (via `avis_format.parser_avis`) plutôt
  que la première phrase du texte brut entier — sans ce changement, le
  titre « ## Coup joué » (devenu la toute première ligne) aurait
  silencieusement désactivé ce contrôle. Repli sur l'ancien comportement
  (première phrase du texte brut) si le format n'est pas respecté : le
  contrôle continue de s'appliquer sur le texte affiché tel quel, sans
  fausse alerte nouvelle (vérifié par `test_issue134.py`, toujours au
  vert).
- `app.py` : `on_exercise_answer`/`_on_exercise_answer_lichess`/
  `call_mistral_and_emit` découpent la réponse (`avis_format.parser_avis`)
  et ajoutent `avis_sections`/`avis_format_conforme`/`avis_format_version`
  aux événements `exercise_comment`/`exercise_mistral_comment` — en cas de
  format non respecté, `avis_sections` est vide et `text` (texte brut)
  reste transmis intégralement : rien n'est perdu côté client.
- `static/board.js` : nouvelle fonction `_coachRenderAvisContenu` —
  affiche chaque section comme un bloc séparé (intertitre en petites
  majuscules, listes à puces réelles pour « Points négatifs »/« Points
  positifs ») quand le format est conforme ; replie sur le texte brut
  (comportement inchangé) sinon. Branchée dans `_coachRenderBubbleWithAgent`
  (Claude) et `_coachRenderMistralBubbleWithAgent` (Mistral) via deux
  nouveaux paramètres optionnels en fin de signature — étiquette d'auteur,
  boutons de note, bouton « Signaler » et alertes du vérificateur
  inchangés (ajoutés après le contenu, comme avant).
- `static/exercise.js` : transmet `data.avis_sections`/
  `data.avis_format_conforme` aux deux fonctions de rendu ci-dessus.
- `static/board.css` : règles `.coach-avis-section`/`.coach-avis-titre`/
  `.coach-avis-sous`/`.coach-avis-sous-titre` — séparation verticale nette
  entre sections (bordure fine + espacement) et intertitres discrets en
  petites majuscules, pensés pour 360-400px de large.
- Vérification :
  - `pyflakes` sur tous les fichiers Python modifiés (`avis_format.py`,
    `game_facts.py`, `llm_coach.py`, `fact_checker.py`, `app.py`,
    `test_issue135.py`) : aucune nouvelle alerte « undefined name » ni
    redéfinition — les 5 alertes pyflakes restantes (imports `Tuple`/`Set`
    inutilisés, 2 variables locales inutilisées, 1 f-string sans
    placeholder, toutes dans `fact_checker.py`) existaient déjà avant cette
    issue (confirmé par comparaison avant/après).
  - Nouveau fichier `test_issue135.py` (26 tests, tous au vert) :
    - Partie 1 : `avis_format.parser_avis` (conforme avec/sans « Coup de
      l'époque », prose libre non conforme, ordre de titres incorrect,
      sous-rubrique manquante, texte vide, aucune exception).
    - Partie 2 : présence du format imposé dans le prompt système, absence
      de la contradiction « 2 à 4 phrases » dans `_EXERCISE_LICHESS_
      ADDENDUM`, numérotation des coups dans `_build_context_text`.
    - Partie 3 : `fact_checker.py` lit bien la rubrique structurée (et pas
      le titre), avec repli sur l'ancien comportement si non conforme.
    - Partie 4 : `llm_coach.get_coach_response` (la vraie fonction, API
      simulée) écrit bien `avis_format_conforme`/`avis_sections`/
      `avis_format_version` dans le journal, et conserve toujours le texte
      brut même non conforme.
    - Partie 5 (tâche 7b) : exécution du VRAI gestionnaire
      `app.on_exercise_answer`/`_on_exercise_answer_lichess` via le client
      de test Flask-SocketIO (infrastructure de `test_issue128.py`), API
      Claude simulée, pour les sources « Mes erreurs » ET « Problèmes
      Lichess », sur les 4 cas demandés : réponse conforme, réponse non
      conforme (texte brut transmis intégralement), réponse vide, réponse
      d'erreur (aucun `exercise_comment`, un `exercise_error` reçu).
  - Non-régression : `test_issue134.py` (28 tests) et
    `test_issue128.py` (tests `TestExerciseAnswerSocketIO`, 4 tests)
    toujours au vert après ces changements.
  - Non testé en conditions réelles (limite documentée) : le rendu visuel
    du nouveau découpage par section dans un VRAI navigateur mobile
    (360-400px) n'a pas pu être vérifié à l'œil — seule la structure DOM
    générée par `_coachRenderAvisContenu` a été relue manuellement et
    validée par la syntaxe JS (`node --check`) ; de même, aucun appel réel
    aux API Claude/Mistral n'a été fait pour vérifier qu'elles respectent
    effectivement ce nouveau format en pratique (tous les tests utilisent
    une réponse simulée) — à confirmer sur les prochains avis réels, comme
    pour la mesure qui avait motivé l'issue #134.
