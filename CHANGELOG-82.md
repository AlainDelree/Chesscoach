# Changelog — Issue #82

## Alerte visible quand la décomposition d'évaluation Stockfish n'est plus disponible : icône d'état dans l'en-tête et journal

Suite de l'issue #80 (idées du coup basées sur la commande `eval`, retirée par
Stockfish à partir de la 16.1) : `engine_stockfish.py`, `config.py`, `app.py`,
`templates/index.html`, `static/controls.js`.

### Détection (`engine_stockfish.py`)

- `EngineManager._detecter_eval_breakdown()` : appelle
  `get_eval_breakdown()` (issue #80) sur la position de départ (position de
  test simple) et mémorise le résultat dans `_eval_breakdown_disponible`
  (bool) / `_eval_breakdown_version` (texte complet du moteur, ex.
  `"Stockfish 16"`) — exposés en lecture via les propriétés
  `eval_breakdown_disponible` / `eval_breakdown_version`. Jamais retesté à
  chaque exercice : `get_eval_breakdown` reste appelé normalement à chaque
  coup (comportement de l'issue #80 inchangé), seule cette détection d'état
  est mise en cache.
- Appelée une fois à la fin de `_init_engines()` (démarrage de l'appli) et de
  nouveau dans `_appel_protege()` chaque fois que le moteur d'évaluation
  (`_engine_eval`) est relancé avec succès par la reprise automatique (issue
  #79) — comparaison par égalité de méthode liée (`creer ==
  self._creer_moteur_eval`), sans toucher aux relances des trois autres
  instances (play/pédagogique/finales), sans rapport avec cette commande.
- État persisté dans `EVAL_BREAKDOWN_STATE_PATH` (nouveau,
  `data/eval_breakdown_state.json`, `config.py`) pour comparer au démarrage
  suivant : si la disponibilité ou la version a changé depuis le fichier
  précédent, une ligne `WARNING` dédiée est journalisée en plus de la ligne
  `INFO` systématique — toutes deux préfixées `[EVAL_BREAKDOWN]`, faciles à
  retrouver dans le journal applicatif (`logger` standard, pas de nouveau
  fichier de log).
- Testé avec le vrai Stockfish 16 installé (`/usr/games/stockfish`, qui
  supporte encore `eval`) : `disponible=True`, `version='Stockfish 16'`.
  Testé aussi en forçant `get_eval_breakdown` à renvoyer `None` (simulation
  d'un Stockfish 16.1+) après avoir pré-rempli l'état précédent à
  `disponible=True` : la ligne de changement apparaît bien dans le journal,
  le nouvel état est persisté.

### Icône d'état (`templates/index.html`, `static/controls.js`)

- `#eval-status-widget` (bouton texte discret `eval` + panneau de détail au
  survol/clic, même mécanique que `#usage-tokens-widget` existant) posé dans
  `.header-actions` de l'en-tête (grand écran), rendu initial entièrement
  côté serveur (`app.py` `index()`) à partir de
  `engine_manager.eval_breakdown_disponible/_version` — **absent du DOM**
  (pas seulement masqué) si Stockfish est entièrement introuvable
  (`engine_manager is None`, autre panne déjà signalée ailleurs, hors sujet
  ici).
- Déplacé vers `#mobile-mode-bar-slot`, juste après le menu `"..."`
  (`#game-menu-btn`, posé par l'issue #70/#81) sur mobile (<900px, dans tous
  les modes) par `_registerMobileRelocatable` (`controls.js`, même mécanisme
  que les autres blocs déjà déplacés — `#eval-status-widget` n'existe que
  s'il est présent côté serveur, l'enregistrement est un no-op sinon).
- État normal : texte `eval` en gris discret (`--cc-text-muted`). État
  indisponible : classe `.eval-status-alert`, couleur rouge `#cc2200` (déjà
  utilisée ailleurs pour les coups en erreur, `.move-chip.erreur`) — jamais
  le terracotta `--cc-accent`, réservé au cliquable d'après la règle de
  palette existante.
- Message au survol (desktop) ou au tap (bascule d'une classe
  `.eval-status-open`, même recette que `#usage-tokens-widget`) :
  - normal : « Décomposition d'évaluation disponible, Stockfish `<version>`. »
  - indisponible : « Stockfish `<version>` ne fournit plus la décomposition
    d'évaluation : les idées du coup ne sont plus calculées (seules les
    idées mécaniques restent). Une mise à jour de Stockfish est probablement
    la cause. »
  - `<version>` = nom du moteur sans le préfixe `"Stockfish "` s'il est
    présent (`app.py` `_version_stockfish_affichee`), pour éviter de le
    répéter deux fois dans le message.
- Panneau de détail en `position:fixed` sur mobile (ancré dynamiquement sous
  le bouton par JS), même recette que `#usage-detail` (issue #54) — choisie
  pour la même raison : un panneau `position:absolute` déborderait du
  viewport selon la position du widget dans la rangée.

### Vérifications (Playwright, serveur Flask local, vrai Stockfish 16)

- 1280×900, 390×750, 360×750 : icône visible, état normal (gris), message
  correct au clic, **aucun débordement horizontal**
  (`document.documentElement.scrollWidth === clientWidth`) dans les trois
  tailles.
- Même mesures après `app.engine_manager._eval_breakdown_disponible = False`
  (simulation du scénario "Stockfish mis à jour") : classe
  `eval-status-alert`, couleur `rgb(204, 34, 0)` (`#cc2200`), message avec la
  version simulée, toujours aucun débordement horizontal.
- `#eval-status-widget` confirmé replacé dans `#mobile-mode-bar-slot` juste
  après `#game-menu-btn` sur mobile, et toujours visible après passage en
  mode "partie libre" (`body.mobile-game-active`) — l'en-tête `<header>`
  d'origine est bien masqué (`display:none`) comme pour le reste de la
  rangée combinée (issue #81).
- `engine_manager is None` (Stockfish absent) : `<div id="eval-status-widget">`
  bien absent du HTML rendu (vérifié par recherche de la balise elle-même,
  pas d'un simple mot dans un commentaire HTML).

### Limites

- La reprise automatique du moteur d'évaluation (issue #79) n'a pas été
  déclenchée avec un vrai crash de processus dans le cadre de cette tâche
  (aucune manipulation destructrice du Stockfish système demandée) : le
  branchement dans `_appel_protege` est vérifié par lecture de code
  (comparaison de méthode liée `creer == self._creer_moteur_eval`, placée
  après un appel réussi sur la nouvelle instance) plutôt que par un crash
  réel comme l'avait fait le rapport de l'issue #79 elle-même.
- Pas de simulation d'un vrai Stockfish 16.1+ sans la commande `eval` (le
  binaire installé sur cette machine, Stockfish 16, la supporte encore) : la
  détection de l'état "indisponible" est vérifiée en forçant directement le
  résultat (`get_eval_breakdown` monkeypatché / attribut forcé), comme
  suggéré par l'énoncé de l'issue.
- Comportement de repli sur les idées mécaniques (issue #80) strictement
  inchangé : aucune modification de `get_eval_breakdown()` elle-même ni de
  ses appelants (`app.py`), seule une détection d'état en plus, jamais
  consultée par le calcul des idées du coup.
