# Changelog — Issue #105

## Indicateur "Le coach réfléchit..." et délai maximal de réponse avec bouton Réessayer

Tentative 2/3 sur cette issue. La tentative précédente (commit de sauvegarde
`715b001`, vide — `--allow-empty`) avait déjà produit l'essentiel de
l'implémentation, mais ne l'avait jamais committée (809 lignes sur 11
fichiers, encore dans l'arbre de travail au début de cette session,
probablement tuée par le TIMEOUT juste après avoir fini). Le travail a été
relu intégralement fichier par fichier plutôt que refait de zéro, puis testé
en conditions réelles (navigateur piloté par Playwright) — ce qui a permis
de trouver et corriger deux défauts avant de committer, détaillés ci-dessous.

### Indicateur d'attente (point 1 de l'issue)

- Bulle de chat "Le coach réfléchit" + trois points animés
  (`.coach-bubble-thinking`, `static/board.css`), insérée dans
  `#coach-history` à l'endroit où la réponse apparaîtra, retirée dès la
  réponse ou l'erreur. Après 10s (`COACH_WAIT_ELAPSED_SHOW_MS`), le texte
  devient "Le coach réfléchit... N s" (mis à jour chaque seconde).
- Sur mobile, la même information est dupliquée dans `#game-status-move`
  (ligne d'état sous le plateau, seule visible en `body.mobile-game-active`)
  — jamais de réduction du plateau (`board-compact` n'est jamais ajouté/
  retiré par ce mécanisme) ni de bulle centrée sur le plateau (aucun appel à
  `showBoardToast`).
- Mécanisme central partagé : `coachWaitBegin()` (`static/board.js`),
  réutilisé par `coach_ask`, `coach_comment_on_demand` (chat libre,
  pédagogique, ouverture, finales), `training_program_build`,
  `analyse_choisir_coups_decisifs` et `analyse_expliquer_coup`
  (`game_analysis.js`) ; le mode Exercice garde son minuteur de garde dédié
  de 30s (issue #79, couvre tout le recalcul Stockfish) et ne réutilise que
  la partie affichage (`_coachThinkingStart`).
- Double-envoi : `coach-send-btn` est désactivé dès l'envoi (`_coachBusy`),
  vérifié par test — un second clic pendant l'attente n'émet aucun second
  `coach_ask`. Le champ de saisie, lui, reste éditable.

### Délai maximal (point 2)

- Un seul endroit à modifier : `config.py`, `COACH_TIMEOUT_REPONSE_S = 60`
  (question, commentaire, exercice, ouverture/finale/pédagogique à chaque
  coup) et `COACH_TIMEOUT_ANALYSE_S = 150` (sélection des coups décisifs et
  explication à la demande en analyse de partie, programme
  d'entraînement — contexte plus volumineux, latence réelle plus élevée).
  Valeur transmise jusqu'à `llm_coach._call_claude` (paramètre `timeout_s`,
  passé à `urllib.request.urlopen(req, timeout=timeout_s)`) : il s'agit
  d'une vraie coupure réseau côté serveur, pas seulement d'une alerte
  visuelle. **La relance automatique de fiabilité compte dans ce même
  délai** (elle réutilise `timeout_s` tel quel) — un dépassement à ce stade
  peut donc, dans de rares cas, amener le délai total perçu par Alain à
  friser près du double de la valeur configurée avant que le serveur ne
  tranche définitivement ; documenté en commentaire dans `llm_coach.py` et
  `config.py`, pas changé pour cette issue (comportement jugé acceptable :
  la relance ne se déclenche que sur une réponse déjà jugée incohérente,
  cas rare).
- Minuteur de garde navigateur : délai serveur + 15s de marge
  (`COACH_WAIT_GUARD_MARGIN_MS`), lu depuis `window.COACH_SERVER_TIMEOUT_MS`
  (exposé par `templates/index.html`/`app.py index()` à partir des mêmes
  constantes `config.py` — jamais dupliqué en dur côté client). Au
  déclenchement : bulle "Le coach n'a pas répondu à temps." + bouton
  "Réessayer" qui renvoie EXACTEMENT la même demande (payload figé à
  l'envoi), saisie réactivée, plateau inchangé.
- **Bug trouvé et corrigé avant commit** (via test navigateur réel, pas
  seulement relecture) : dans les 7 points d'intégration (`coach_ask`,
  `coach_comment_on_demand`, `training_program_build`,
  `analyse_choisir_coups_decisifs`, `analyse_expliquer_coup`, commentaire
  automatique d'ouverture/finale/pédagogique), le callback `onTimeout`
  remettait la variable de contrôle (ex. `_coachAskWait`) à `null` — ce qui
  empêchait justement le mécanisme "réponse tardive ignorée" de fonctionner
  : une fois nullifiée, la vérification `isTimedOut()` dans
  `coach_response`/`coach_error` était simplement sautée, et une réponse
  arrivant après le délai de garde s'affichait normalement, comme une
  réponse fraîche. Corrigé en ne nullifiant la référence qu'au prochain
  véritable envoi (où elle est de toute façon réécrasée par un nouveau
  contrôleur), jamais dans `onTimeout`. Vérifié par test : une réponse
  déclenchée après le délai de garde (sans nouvel envoi entre-temps)
  n'apparaît plus dans le chat.
- **Limite connue, documentée plutôt que corrigée** (repérée par le même
  test, cas plus rare) : si Alain clique "Réessayer" puis qu'une réponse de
  la demande ORIGINALE abandonnée arrive quand même (serveur lent mais pas
  mort, Socket.IO retardé), elle peut être affichée à la place de la
  réponse du nouvel envoi — le protocole actuel (`coach_ask`/
  `coach_response`) ne transporte aucun identifiant de corrélation
  permettant de distinguer les deux demandes côté client. Corriger ce cas
  précis demanderait d'ajouter un identifiant de requête round-trippé sur
  chaque chemin (8 handlers `app.py` + 6 fichiers JS), hors de portée d'une
  issue de complexité normale ; risque jugé faible en pratique (suppose un
  serveur qui répond quand même très en retard après son propre timeout
  réseau, sur un Flask dev server sans eventlet/gevent installé — requêtes
  normalement traitées en file, pas en parallèle réel).

### Journal et signalements (point 3)

- `llm_coach._erreur_label()` (nouvelle fonction) normalise toute
  `TimeoutError`/`URLError` enveloppant un `TimeoutError` en code `"timeout"`
  stable, utilisé aux 4 points d'appel de `_call_claude` — même format
  d'entrée JSON Lines que les autres erreurs (`coach_calls.log`), vérifié
  avec `lire_journal_coach.py` (affiche "Erreur : timeout" sans
  modification du script).
- Bulle de délai dépassé (`_coachRenderTimeoutBubble`) distincte de
  `_coachRenderBubble` : jamais de bouton "Signaler" en dessous (vérifié
  par test — absent du DOM, contrairement aux réponses normales qui en ont
  un).

### Bug corrigé hors des 3 points ci-dessus

- `templates/index.html` déclarait `const COACH_SERVER_TIMEOUT_MS = {...}`
  dans un `<script>` classique (non-module) : un `const`/`let` de portée
  globale ne devient PAS une propriété de `window`, contrairement à `var`.
  Or `static/board.js` lit explicitement `window.COACH_SERVER_TIMEOUT_MS`
  (plusieurs `<script src>` séparés) — cette lecture retournait donc
  toujours `undefined`, et le minuteur de garde retombait silencieusement
  sur les valeurs de repli codées en dur (60000/150000 ms), qui
  coïncidaient avec les valeurs par défaut de `config.py` au moment du
  test, masquant le bug. Changer plus tard `COACH_TIMEOUT_REPONSE_S`/
  `COACH_TIMEOUT_ANALYSE_S` sans recompiler ces deux valeurs en dur aurait
  désynchronisé le minuteur navigateur du vrai délai serveur, cassant la
  promesse "réglable en un seul endroit". Corrigé en assignant directement
  `window.COACH_SERVER_TIMEOUT_MS = {...}`.

### Tests

Navigateur réel piloté par Playwright (Chromium), harnais autonome limité à
ce worktree (CSS/JS réels chargés via file://, `socket` remplacé par un stub
enregistrant les émissions et permettant de déclencher manuellement les
événements serveur — aucune dépendance réseau ni accès à `DATA_DIR`, hors du
périmètre strict de ce worktree). Délais serveur raccourcis (3s/6s au lieu
de 60s/150s) pour un test rapide, même mécanisme. Scénarios tous vérifiés
avec capture d'écran (desktop 1280×900, mobile 390×750 et 360×640 avec
`has_touch`/`is_mobile`) :
- réponse rapide : bulle apparaît puis disparaît sans décalage de contenu ;
- réponse lente simulée : "Le coach réfléchit... 11 s" affiché après 10s ;
- réponse arrivée après 11s mais avant le délai de garde : affichée
  normalement (pas traitée comme tardive) ;
- délai dépassé simulé : message clair, bouton Réessayer, aucun bouton
  Signaler, saisie réactivée (bouton Envoyer non désactivé) ;
- réponse tardive après expiration (sans nouvel envoi) : ignorée (bug
  ci-dessus corrigé, test repassé au vert après correction) ;
- clic Réessayer : renvoie un nouvel appel avec EXACTEMENT la même question,
  relance l'indicateur ;
- double-envoi : bouton réellement désactivé côté DOM (Playwright lève un
  timeout en tentant de cliquer dessus), un seul appel réseau au total ;
- programme d'entraînement (`kind: "analyse"`, pas de bulle de chat —
  chatBubble:false) : statut dédié affiché ;
- mobile 390×750 et 360×640 : ligne d'état affiche l'indicateur, plateau de
  taille inchangée pendant l'attente, aucune classe `board-compact`
  ajoutée, retour à l'état normal après la réponse.
- Côté serveur (Python, sans navigateur) : `llm_coach._call_claude` testé
  avec un VRAI serveur HTTP local lent (pas un mock de fonction) — avec
  `timeout_s=1`, la connexion est abandonnée après 1.02s mesurées, lève
  `TimeoutError`, classée `"timeout"` par `_erreur_label`. Écriture/lecture
  du journal vérifiées de bout en bout (`_log_coach_call` →
  `lire_journal_coach.py`, fichier temporaire hors `DATA_DIR`).
- `python3 -m py_compile app.py config.py llm_coach.py` → OK ;
  `node --check` sur les 6 fichiers JS modifiés → OK.

### Limites

- **Appel API réel non effectué** : aucune `ANTHROPIC_API_KEY` disponible
  dans le périmètre strict de ce worktree
  (`/home/alain/chesscoach-issue105`) — la clé réelle vit dans
  `~/ChessCoach/.env`, hors périmètre, limitation déjà documentée dans les
  issues #45/#46/#47. Le test "réponse rapide" avec API simulée couvre le
  cas normal ; Alain devra confirmer en conditions réelles que le délai de
  60s/150s est confortable sur son réseau.
- **`DATA_DIR` hors périmètre** : impossible de lancer l'application Flask
  complète (`app.py`) depuis ce worktree sans écrire dans
  `~/ChessCoach/data/` (coach_memory.json, logs, usage_tokens.json), hors
  du périmètre strict — les tests ont donc porté sur un harnais HTML
  autonome chargeant les vrais fichiers `static/board.css`/`board.js`/
  `*.js` modifiés, avec un stub `socket`, plutôt que sur l'application
  entière. Les six modes (question, commentaire, exercice, ouverture,
  finale, analyse) ont été vérifiés par relecture complète du diff plus un
  test direct des primitives partagées (`coachWaitBegin`,
  `_coachThinkingStart`, `_coachRenderTimeoutBubble`) qu'ils réutilisent
  tous sans variation notable — pas par un parcours UI complet de chacun
  des six (aurait nécessité de recréer un état de partie/exercice réaliste
  pour chacun, hors de portée raisonnable pour une vérification
  complémentaire à la relecture de code).
- **Limite résiduelle documentée plus haut** : réponse périmée affichée par
  erreur si elle arrive après qu'un "Réessayer" a déjà renvoyé une nouvelle
  demande (cas rare, nécessiterait un identifiant de corrélation
  round-trippé pour être éliminé complètement).
