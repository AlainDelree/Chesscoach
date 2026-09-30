# Changelog — Issue #67

## Mobile : ne plus faire défiler la page vers le chat à chaque coup joué

- Contexte : suite à l'issue #65 (suppression de la zone de défilement
  interne du chat sur mobile), la fonction commune de révélation des
  messages du chat coach s'appuie désormais sur le défilement de la PAGE.
  Or chaque coup joué en partie pédagogique ajoute un message automatique
  d'Alain dans le chat ("Partie pédagogique — je joue ..."), qui déclenchait
  ce défilement — le plateau sortait de l'écran après chaque coup. Constaté
  par Alain sur capture d'écran ; les autres modes de partie (libre,
  ouverture, finales, exercice) présentaient le même défaut pour leurs
  propres messages automatiques (coup joué, commentaire "Commenter chaque
  coup", info, erreur).

### static/board.js

- `_coachScrollReveal(history, el, toStart, allowPageScroll)` : nouveau
  4ᵉ paramètre. La branche "défilement interne" (bureau, ou mobile si un
  CSS venait à réintroduire un `overflow-y:auto`) est strictement
  inchangée — elle défile toujours, quel que soit `allowPageScroll`. La
  branche "page qui défile" (mobile, cas normal depuis l'issue #65) ne
  déclenche `scrollIntoView` que si `allowPageScroll` est vrai.
- `_coachRenderBubble(role, text, allowPageScroll)` : nouveau 3ᵉ paramètre,
  transmis tel quel à `_coachScrollReveal`. Absent (donc `undefined`/faux)
  par défaut sur tous les appels existants — comportement mobile "ne
  défile pas" par défaut.
- Seuls les deux cas où Alain attend activement une réponse passent
  `allowPageScroll = true` explicitement : la réponse du coach à une
  question tapée dans le chat (`coach_response`) et la réponse au bouton
  "Demander l'avis du coach" (`coach_on_demand_response`).
- `_coachRenderCreditInsuffisant` et `coachNewSegment` (séparateur
  "Nouvelle partie") continuent d'appeler `_coachScrollReveal` sans ce
  4ᵉ argument : plus de défilement de page sur mobile pour ces messages
  d'erreur/séparateur, comportement bureau inchangé.

### static/exercise.js

- Verdict d'exercice (`exercise_comment`) : seul appel hors board.js à
  passer `allowPageScroll = true` — comportement voulu par la maquette
  (le début du verdict doit se placer en haut de l'écran).

### Cas qui ne défilent plus la page sur mobile (comportement bureau inchangé)

- Messages automatiques "je joue ..." (pédagogique, ouverture, finales,
  exercice) — `_coachRenderBubble("user", ...)` sans 3ᵉ argument.
- Commentaires "Commenter chaque coup" (`pedagogic_comment`,
  `finale_comment`) et commentaires équivalents d'ouverture
  (`opening_comment`).
- Messages informatifs statiques ("Finale chargée", "Ouverture chargée",
  "Démonstration chargée").
- Messages d'erreur (`_coachRenderCreditInsuffisant`, `no_api_key`, etc.).
- Séparateur "Nouvelle partie"/"Nouvel exercice" (`coachNewSegment`).
- Message d'Alain lui-même envoyé depuis le champ du chat (`coachSend`,
  `_coachRenderBubble("user", question)`) — seule sa réponse déclenche le
  défilement, pas l'envoi de la question.

### Tests effectués

- Lecture complète du code (pas d'environnement mobile réel/émulateur
  tactile disponible dans ce worktree non-interactif ; aucun appel API
  Claude réel effectué — pas de clé/contexte d'exécution serveur monté
  dans cette session). Vérification statique de tous les appelants de
  `_coachRenderBubble`/`_coachScrollReveal` dans board.js, pedagogic.js,
  finales.js, opening.js, exercise.js, free_play.js, llm_model.js :
  chaque site a été classé dans la bonne catégorie (défile / ne défile
  pas) et corrigé en conséquence. `node -c` sur les deux fichiers modifiés
  (syntaxe JS valide) — pas de suite de tests automatisés pour ce module
  front-end dans le dépôt.
- Limite assumée : aucune vérification visuelle réelle (émulation
  tactile 390×844, clic sur les coups, capture d'écran) n'a été faite —
  seule une relecture exhaustive du flux de code garantit le comportement
  attendu. À confirmer par Alain en conditions réelles sur mobile.
