# Changelog — Issue #47

# Changelog — Issue #48

## Panneau Coach trop étroit et texte trop petit

- Constat (capture d'écran d'Alain) : sur un écran classique, `#coach-column`
  (largeur fixe 320px) laissait un espace vide important à droite de la
  page (~240px sur un viewport 1920px), alors que le texte des réponses du
  coach (`#coach-history`, réponses souvent longues — analyse de partie
  complète) était rendu en 0.85rem, inconfortable à lire.
- `templates/index.html` : largeur de `#coach-column` portée de `320px` à
  `480px` (+160px, absorbe l'essentiel de l'espace vide constaté sans
  toucher aux largeurs de `#board-column` (620px), `#historique-column`
  (240px) ni `#mode-tabs-column` (420px), qui restent inchangées).
- `static/board.js`, fonction `_coachRenderBubble` : taille de police des
  bulles de réponse (utilisateur et coach) portée de `0.85rem` à `1.05rem`,
  avec `line-height:1.45` ajouté pour l'aération du texte sur les réponses
  longues.
- Vérification via navigateur headless (Playwright) : captures avant/après
  à 1920×1080 confirmant l'élargissement du panneau (320→480px, coin droit
  passant de x=1664 à x=1824, toujours dans le viewport) et
  l'agrandissement du texte des bulles (13.6px → 16.8px). Vérifié aussi à
  1440×900 : le passage à la ligne (`flex-wrap`) du panneau Coach sous les
  autres colonnes existait déjà avant la modification à cette largeur (la
  somme des largeurs fixes dépassait déjà 1440px) — seul le seuil de wrap
  se déplace légèrement, pas de régression introduite.

## Chat libre — réponse vide (bloc thinking seul, sans texte) sur claude-sonnet-5

- Cause confirmée (documentation officielle de l'API Messages) : `_call_claude`
  (`llm_coach.py`) omettait le paramètre `thinking` dans le corps de la
  requête. Sur `claude-haiku-4-5`, cela ne change rien (Haiku ne raisonne
  jamais). Sur `claude-sonnet-5` (modèle d'Alain via
  `CHESSCOACH_LLM_MODEL`), omettre `thinking` active le raisonnement
  adaptatif *par défaut* — contrairement aux modèles Opus 4.7/4.8, où
  l'omettre désactive la réflexion. Ce raisonnement consomme une partie du
  budget `max_tokens` (2048) avant même de commencer à écrire la réponse ;
  sur une question simple, il pouvait consommer la totalité du budget et
  s'arrêter (`stop_reason: "max_tokens"`) après un unique bloc
  `{"type": "thinking", "thinking": ""}`, sans aucun bloc `text` — l'erreur
  observée par Alain (`"Aucun bloc de type 'text' dans la réponse Claude"`),
  levée par le parsing robuste ajouté en issue #46 (qui reste nécessaire et
  n'a pas été modifié).
- `llm_coach.py`, fonction `_call_claude` :
  - Ajout de `"thinking": {"type": "disabled"}` dans le corps de la requête
    — désactive explicitement le raisonnement adaptatif plutôt que de
    simplement lui laisser plus de budget, ce qui élimine la classe de
    problème à la racine (option demandée en priorité par l'issue). Un
    commentaire de coach aux échecs n'a pas besoin d'exposer un raisonnement
    séparé de la réponse ; Haiku, utilisé jusqu'à l'issue #44 pour le même
    usage, ne raisonnait jamais et convenait déjà — pas de régression de
    qualité attendue par rapport au comportement déjà validé.
  - `max_tokens` porté de 2048 à 4096 en complément (deuxième option
    demandée par l'issue), pour laisser une marge large même si un futur
    changement de modèle ou d'API réintroduisait un raisonnement consommant
    une partie du budget.
- Commentaires mis à jour en conséquence (rationale du budget de tokens et
  de la recherche défensive du bloc `text`, qui reste utile même avec
  `thinking` désactivé — au cas où l'API renverrait tout de même un bloc
  `thinking` vide).
- Hors périmètre respecté : aucune modification du parsing du bloc `text`
  ajouté par l'issue #46.
- Vérification : `python3 -m py_compile llm_coach.py` → OK. Simulation
  locale de `urllib.request.urlopen` (aucun appel réseau réel) confirmant
  que le corps de requête envoyé contient bien `"thinking": {"type":
  "disabled"}` et `"max_tokens": 4096`, et que la réponse texte est
  correctement extraite même en présence d'un bloc `thinking` vide en tête
  de `content`.
- **Vérification navigateur headless avec appel API réel demandée par
  l'issue : non effectuée.** Aucune `ANTHROPIC_API_KEY` n'est accessible
  dans le périmètre strict de ce worktree (`/home/alain/chesscoach-issue47`)
  — la clé réelle vit dans `~/ChessCoach/.env`, hors périmètre, et je n'ai
  pas le droit d'y accéder même si la tâche le demande explicitement (même
  limitation déjà rencontrée et documentée en issue #46). Alain devra
  confirmer par un échange réel dans l'interface, avec `claude-sonnet-5`
  configuré, qu'une réponse textuelle réelle est bien reçue en chat libre.

# Changelog — Issue #46

## Chat libre — KeyError('text') lors du parsing de la réponse API, apparu après le passage à Sonnet

- Diagnostic : impossible de retrouver l'entrée réelle dans
  `data/logs/coach_calls.log` — ce fichier vit sous `DATA_DIR`
  (`~/ChessCoach/data/logs/`), hors du périmètre strict de ce worktree
  (`/home/alain/chesscoach-issue46`). Le diagnostic s'appuie donc sur la
  documentation officielle de l'API Messages (comportement confirmé,
  non supposé) : sur `claude-sonnet-5`, quand le paramètre `thinking` est
  omis de la requête, le raisonnement adaptatif s'exécute *par défaut* et
  produit un bloc `{"type": "thinking", ...}` dans la liste `content` de la
  réponse — potentiellement avant le bloc `{"type": "text", ...}`. Sur
  Haiku, qui ne pense jamais, `content[0]` est toujours le bloc texte. La
  requête construite dans `_call_claude` (`llm_coach.py`) n'a jamais fixé le
  paramètre `thinking`, donc ce comportement s'active silencieusement dès
  que `CHESSCOACH_LLM_MODEL=claude-sonnet-5` (config d'Alain).
- `llm_coach.py`, fonction `_call_claude` (ligne ~637) : remplace
  `return data["content"][0]["text"]` (suppose une position fixe) par une
  itération sur `data["content"]` qui retourne le premier bloc dont
  `"type" == "text"`, quelle que soit sa position dans la liste. Lève une
  `ValueError` explicite si aucun bloc texte n'est trouvé (au lieu d'un
  `KeyError`/`IndexError` opaque).
- Hors périmètre respecté : aucune modification du paramètre `thinking`
  côté requête — uniquement le parsing de la réponse, comme demandé.
- Vérification fonctionnelle (aucune `ANTHROPIC_API_KEY` disponible dans
  l'environnement de cette session, et le module `anthropic` n'est pas
  installé — un vrai appel réseau à `claude-sonnet-5` n'a donc pas pu être
  effectué depuis ce worktree) : simulation de `urllib.request.urlopen` avec
  les deux formes de réponse possibles — (1) bloc `text` seul en position 0
  (forme Haiku historique) et (2) bloc `thinking` en position 0 suivi du
  bloc `text` en position 1 (forme Sonnet 5 à l'origine du bug) — confirme
  que `_call_claude` retourne le bon texte dans les deux cas, alors que
  l'ancien code levait `KeyError('text')` sur le cas (2). Alain devra
  confirmer par un échange réel dans l'interface avec `claude-sonnet-5`
  configuré.

# Changelog — Issue #45

## Chat libre — timeout de lecture sur l'appel API Claude

- `llm_coach.py` : le timeout HTTP de l'appel à l'API Claude dans
  `_call_claude` était codé en dur à 15s (`urllib.request.urlopen(req,
  timeout=15)`), devenu insuffisant avec un contexte volumineux
  systématiquement transmis (PGN complet + mémoire de progression complète :
  patterns_erreurs, repertoire_ouvertures, objectifs_courants) et depuis le
  passage de `CHESSCOACH_LLM_MODEL` à claude-sonnet-5. Provoquait "the read
  operation timed out" même sur une question triviale ("dis bonjour") en
  mode Bibliothèque/Revue avec une partie longue chargée. Porté à 90s.
- Vérifié qu'aucun autre timeout intermédiaire ne coupe la requête plus tôt :
  `SocketIO(app)` (app.py) n'a pas de `ping_timeout`/`ping_interval` custom,
  et le serveur Flask dev (`socketio.run`) n'a pas de timeout de requête
  configuré. Le seul timeout applicable au chemin `_call_claude` est bien
  celui de la ligne modifiée.
- Vérification fonctionnelle (sans clé API réelle disponible dans
  l'environnement d'exécution) : simulation d'une latence de 20s côté API
  via mock de `urllib.request.urlopen` — confirme qu'avec le nouveau
  timeout=90 la requête réussit (20s < 90s), alors qu'avec l'ancien
  timeout=15 la même latence aurait levé `TimeoutError`. Une vérification
  E2E via navigateur headless avec un vrai appel API n'a pas pu être
  réalisée : aucune `ANTHROPIC_API_KEY` n'était présente dans
  l'environnement de cette session, et `DATA_DIR` (`~/ChessCoach/data`,
  PGN réels + `coach_memory.json`) se situe hors du périmètre strict de ce
  worktree (`/home/alain/chesscoach-issue45`).

