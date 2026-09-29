# Changelog — Issue #47

# Changelog — Issue #51

## Désactivation du mode debug Flask (écoute sur 0.0.0.0 depuis l'issue #49)

- Constat : `socketio.run(...)` (app.py, démarrage) passait `debug=True` en
  dur alors que l'appli écoute sur toutes les interfaces (`0.0.0.0:5000`,
  issue #49) derrière `_FiltreAccesDistant`. Le débogueur interactif
  Werkzeug (console web, protégée seulement par un code PIN) peut être servi
  avant ce filtre WSGI, donc potentiellement joignable depuis le réseau
  local ou un wifi public — inacceptable pour une appli détenant la clé API
  Claude et des données personnelles.
- `config.py` : nouvelle variable `DEBUG_DEV`, lue depuis la variable
  d'environnement `CHESSCOACH_DEBUG_DEV` (`"1"` pour l'activer), `False` par
  défaut.
- `app.py` (bloc `if __name__ == "__main__":`) :
  - `debug=config.DEBUG_DEV` et `use_reloader=config.DEBUG_DEV` au lieu de
    `debug=True` en dur — désactive aussi le rechargement automatique du
    code par défaut.
  - `host` devient conditionnel : `127.0.0.1` si `DEBUG_DEV` est actif,
    `0.0.0.0` sinon (comportement inchangé pour l'usage normal via
    Tailscale). Le débogueur ne peut donc jamais être actif en même temps
    qu'une écoute ouverte sur les autres interfaces.
  - Port 5000, `allow_unsafe_werkzeug=True` et `_FiltreAccesDistant`
    inchangés.
- `CONTEXTE.md` : section « Accès distant » mise à jour — mention explicite
  qu'après une modification du code il faut désormais relancer le coach à la
  main (plus de rechargement automatique), et documentation de
  `CHESSCOACH_DEBUG_DEV=1` pour le développement local.
- Vérifications effectuées (venv temporaire jetable dans `/tmp`, `.env` non
  touché, port 5000 libéré après coup) :
  - Par défaut : log Werkzeug `Debug mode: off`, écoute confirmée sur
    `0.0.0.0:5000`, `GET /` renvoie 200 (page normale), et une requête vers
    la ressource du débogueur
    (`/?__debugger__=yes&cmd=resource&f=debugger.js`) renvoie la page HTML
    normale de l'appli (`Content-Type: text/html`) au lieu de la ressource
    JS du débogueur — la console n'est donc plus servie du tout (le
    middleware `DebuggedApplication` n'est même pas monté).
  - Avec `CHESSCOACH_DEBUG_DEV=1` : log `Debug mode: on`, `Debugger is
    active!` + PIN affiché, rechargeur actif (`Restarting with stat`),
    écoute confirmée **uniquement** sur `127.0.0.1:5000` (absente de
    `0.0.0.0`), et la même requête de ressource renvoie bien
    `Content-Type: text/javascript` (débogueur actif comme attendu en
    développement local).
- Aucune modification du filtre d'accès distant, du port, du mécanisme
  Tailscale ni de `.env`.

# Changelog — Issue #50

## Interface adaptée au GSM (affichage vertical, déplacement des pièces au toucher)

- Constat : aucune balise viewport dans `templates/index.html` — un mobile
  rendait donc la page comme un "layout viewport" de 980px puis la réduisait
  à l'échelle (plateau minuscule, zoom nécessaire pour jouer). La mise en
  page était par ailleurs figée en colonnes fixes (620/240/420/480px) sans
  aucune adaptation aux écrans étroits.
- `templates/index.html` :
  - Ajout de `<meta name="viewport" content="width=device-width,
    initial-scale=1, maximum-scale=1, viewport-fit=cover">`.
  - Nouvelle règle `@media (max-width: 900px)` (aucun effet au-dessus de ce
    seuil, vérifié par capture d'écran diff pixel-à-pixel à 1440px —
    strictement identique avant/après) :
    - `#app` passe en colonne unique (`flex-direction: column`) ; les 4
      colonnes (`#board-column`, `#coach-column`, `#mode-tabs-column`,
      `#historique-column`) passent à `width:100%` et sont réordonnées via
      `order` : plateau, puis chat du coach, puis onglets de mode, puis
      historique des coups (secondaire sur GSM) en dernier.
    - `--bd-size` (taille du plateau, définie dans `board.css`) reçoit une
      borne supplémentaire `calc(100vw - 92px)` pour tenir compte de la
      largeur écran disponible (auparavant seulement `min(70vh, 560px)`,
      indépendant de la largeur — débordait horizontalement sur un
      téléphone en portrait).
    - `.coach-drawer` : `max-height` réduit à `55vh` (au lieu de
      `calc(100vh - 60px)`) pour garder plateau + chat visibles ensemble
      sans trop défiler, comme souhaité par Alain.
    - `.mode-tab-bar` : défilement horizontal (`overflow-x:auto;
      flex-wrap:nowrap`) plutôt que retour à la ligne, comme demandé.
    - `#review-controls` : `flex-wrap:wrap` ajouté (sans quoi la rangée de 5
      boutons Précédent/Suivant/Retourner/Meilleur coup/Extraire le FEN
      dépassait la largeur de l'écran et provoquait un défilement horizontal
      de toute la page).
    - Cibles tactiles agrandies (`button`/`.mode-tab-btn` : `min-height:
      44px`) et police des champs de saisie forcée à `16px` (empêche le
      zoom automatique au focus sur iOS Safari).
- `static/board.css` : `touch-action: manipulation` ajouté sur `.square`
  (neutralise le double-tap-zoom pendant la séquence des deux taps du
  déplacement tactile ; sans effet visuel, donc neutre pour la souris).
- **Déplacement des pièces au toucher** : déjà entièrement fonctionnel sans
  changement de code JS — les 5 modes interactifs visés (partie libre,
  pédagogique, ouverture, finales, exercices) utilisent tous le même
  gestionnaire `boardEl.onclick = on<Mode>BoardClick`, avec le même schéma
  "tap sur la pièce à déplacer puis tap sur la case d'arrivée" que demandé
  dans l'issue — un tap génère un `click` DOM standard, déjà pris en charge
  par ce code. Le point bloquant était uniquement l'absence de balise
  viewport (rendait le plateau minuscule) et le manque de mise en page
  adaptée, tous deux corrigés ci-dessus.
- Note : le mode "Éditeur de position" utilise du drag-and-drop HTML5
  (`draggable`/`ondragstart`/`ondrop`) pour la palette de pièces, non
  compatible tactile — mais ce mode n'est pas dans la liste des 5 modes visés
  par l'issue, donc hors périmètre ici (limite connue, à traiter séparément
  si besoin).
- Vérification (Playwright, Chromium headless, serveur Flask lancé avec un
  `HOME` de test isolé sous le worktree pour ne pas toucher aux données
  réelles sous `~/ChessCoach/data`) :
  - Desktop 1440px : diff pixel-à-pixel avant/après = aucune différence.
  - Bascule de mise en page vérifiée exactement au seuil : 899px → colonne
    unique, 901px → mise en page desktop (`#app` `flex-direction`).
  - Mobile 390×844 (émulation tactile, `has_touch=True`) : aucun débordement
    horizontal de la page (`scrollWidth === clientWidth === 390`), barre
    d'onglets bien scrollable horizontalement (`scrollWidth` 963px pour un
    `clientWidth` de 356px).
  - Déplacement tactile testé avec deux taps successifs (`locator.tap()`) :
    - Mode "Partie libre" : coup e2-e4 joué avec succès (case de départ
      vidée, pion visible en e4, statut passé à "Trait aux Noirs").
    - Mode "Partie pédagogique" (Blancs) : coup d2-d4 joué avec succès,
      réponse automatique de Stockfish (d7-d5) reçue et affichée.
    - Les 3 autres modes visés (ouverture, finales, exercices) partagent
      strictement le même gestionnaire de clic sur case
      (`sqEl = e.target.closest(".square")` puis
      sélection/déplacement identiques) — non exécutés en bout en bout ici
      faute de données de test (livre d'ouverture, tables Syzygy, historique
      d'erreurs, tous gitignorés et absents de l'environnement de test
      isolé), mais le mécanisme est identique à celui validé sur les deux
      modes testés.
- Limites connues :
  - Éditeur de position non adapté au tactile (drag-and-drop HTML5, hors
    périmètre de l'issue).
  - Pas de test sur un appareil physique réel — seulement émulation
    Playwright/Chromium (viewport + événements tactiles synthétiques).
  - Le zoom pincé (pinch-to-zoom) volontaire reste possible
    (`maximum-scale=1` limite mais ne bloque pas totalement selon les
    navigateurs) ; seul le double-tap-zoom accidentel est neutralisé via
    `touch-action: manipulation`, choix délibéré pour ne pas sacrifier
    l'accessibilité (zoom volontaire toujours possible pour lire un texte
    petit) — bon compromis pratique pour rester conforme aux bonnes
    pratiques mobiles actuelles.

# Changelog — Issue #49

## Accès distant via Tailscale, restreint à la machine locale et au réseau Tailscale

- Contexte : Alain veut ouvrir le coach depuis son GSM via Tailscale (déjà
  installé et connecté des deux côtés). L'appli est strictement personnelle
  (parties, mémoire du coach, clé API) et n'a aucun mot de passe : elle ne
  doit donc jamais être joignable par quelqu'un d'autre.
- `app.py` : le serveur écoute désormais sur toutes les interfaces
  (`socketio.run(app, host="0.0.0.0", port=5000, ...)`, avant : bind
  implicite à `127.0.0.1` uniquement), mais un middleware WSGI
  (`_FiltreAccesDistant`, posé devant `app.wsgi_app` — donc devant les
  routes Flask ET le handshake Socket.IO, puisque flask_socketio remplace
  lui-même `app.wsgi_app`) n'accepte que `127.0.0.1`/`::1` et la plage
  Tailscale `100.64.0.0/10` ; toute autre adresse (LAN, wifi public) reçoit
  un `403 Forbidden` explicite avant d'atteindre la moindre route.
- Chat temps réel (Socket.IO) : aucune configuration CORS explicite
  nécessaire. La vérification d'origine par défaut de python-socketio
  (`cors_allowed_origins=None`) compare l'en-tête `Origin` du navigateur au
  `Host` de la requête — elle s'aligne donc automatiquement sur l'adresse
  utilisée pour ouvrir l'appli (locale ou Tailscale), et rejette avec un
  `400 "Not an accepted origin."` toute origine tierce (vérifié par test
  manuel, cf. rapport de clôture de l'issue).
- `CONTEXTE.md` : section ajoutée expliquant l'adresse à utiliser depuis le
  GSM (`http://100.92.48.81:5000`, adresse Tailscale du ThinkPad
  thinkpadcarbon7) et le mécanisme de filtrage.
- Rien ne change côté ThinkPad : l'alias `coach` continue d'ouvrir le
  navigateur en local (127.0.0.1 reste dans la liste blanche), même port
  5000 qu'avant.
- Non touché : `.env`, clé API Claude.

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

