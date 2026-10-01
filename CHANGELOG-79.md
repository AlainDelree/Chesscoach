# Changelog — Issue #79

## Moteur Stockfish : reprise automatique après une panne, erreur visible, coach honnête sans verdict

- **Cause probable identifiée** : `chess.engine.SimpleEngine` ne se relance
  jamais seul après la mort de sa boucle d'événements (process Stockfish
  tué/crashé, ou appel bloqué indéfiniment) — tout appel suivant échoue en
  boucle (`EngineTerminatedError`/« engine event loop dead ») jusqu'au
  redémarrage complet de l'appli, exactement le symptôme constaté. Les
  verrous par instance (`_lock_play`/`_lock_eval`/...) existaient déjà
  (issues précédentes) : l'accès concurrent entre fils SocketIO n'est donc
  pas la cause principale — en revanche, `evaluate()`/`analyse()` (appels
  bornés en PROFONDEUR, majorité des appels) n'avaient jusqu'ici AUCUN
  timeout côté python-chess (seuls les appels bornés en temps, ex.
  `get_move`, ont un timeout interne) : un moteur silencieux pouvait donc
  bloquer indéfiniment le fil appelant — cause probable retenue et corrigée
  (`TIMEOUT_APPEL_SECONDES = 12s`, via un `ThreadPoolExecutor` dédié).
- `engine_stockfish.py` : reprise automatique générique (`_appel_protege`)
  appliquée à TOUS les appels moteur (`get_move`, `get_move_pedagogique`,
  `get_move_finales`, `evaluate`, `evaluate_move` + son repli MultiPV,
  `get_punishment_line`, `get_multipv`) — détecte la mort du moteur, le
  timeout d'appel ou toute exception UCI, ferme l'instance morte, en relance
  une neuve (capacités/Elo/Syzygy/Hash/Threads reconfigurés) et rejoue
  l'appel une seule fois. Quota partagé de 3 relances par fenêtre glissante
  de 60s avec pause croissante (1 à 5s) avant chaque relance, pour éviter une
  boucle serrée en cas de panne systémique (binaire absent, bibliothèque
  incompatible). `Hash=64 Mo`/`Threads=1` désormais fixés explicitement par
  instance (point 7, par prudence — pas identifiés comme cause de la panne
  observée, aucun processus tué pour mémoire côté système).
- `evaluate()`/`evaluate_move()` distinguent désormais explicitement une
  VRAIE panne moteur (`"indisponible": True`, `qualite=None`) d'une position
  terminale légitime (`cp`/`mate` à `None` mais `indisponible=False`) — avant
  ce correctif, les deux cas étaient indiscernables et `evaluate_move`
  rendait un verdict `"bon"`/0 INVENTÉ en cas de panne totale, transmis tel
  quel au coach (cas réel constaté : Re5, classé « gaffe » alors que
  Stockfish le classe meilleur coup, delta ≈ 0).
- `config.py` : nouveau `MOTEUR_ERREURS_LOG_PATH`
  (`data/logs/moteur_erreurs.log`, donnée personnelle hors git) — heure,
  opération, message d'erreur, code de sortie du processus, dernières lignes
  de stderr Stockfish (capturées via un handler sur le logger
  `chess.engine`) et nombre de relances tentées pour chaque panne.
- `app.py` : nouveau drapeau `analyse_indisponible` propagé par tous les
  chemins qui construisent le contexte du coach (exercices "mes erreurs" et
  "Problèmes Lichess", `coach_ask`/`coach_comment_on_demand`, pédagogique,
  ouverture, finales) ; pour la source Lichess, un coup sans correspondance
  connue (ni solution ni mat) alors que le moteur est indisponible ne reçoit
  plus le verdict "erreur" par défaut (verdict inventé) mais `None`
  (indéterminé).
- `exercise_history.py` : un exercice sans verdict calculable n'est plus
  enregistré dans l'historique (gating `verdict_qualite is not None`/
  `verdict_final is not None` côté `app.py`, déjà en place pour la partie
  "verdict" — complété ici côté tirage) ; une entrée à `dernier_resultat:
  None` (ancienne ou produite malgré tout) est désormais traitée comme
  "ratée" par `choisir_exercice` (révision courte) plutôt que comme
  "réussie" (révision longue, bug de l'ancien `else`) — jamais comptée comme
  un succès.
- `llm_coach.py` : (a) `get_coach_response` refuse l'appel API, SANS
  journaliser ni interroger le modèle, quand `mode_exercice` est vrai et
  qu'aucun `verdict_qualite` n'est présent dans le contexte — message fixe
  `"pas_de_verdict_exercice"`, retourné avant tout accès réseau (vérifié :
  une fausse clé API ne lève aucune exception réseau, donc aucune requête
  n'est tentée) ; couvre aussi bien un rechargement de page qu'un événement
  tardif, puisque c'est le contexte reçu qui est vérifié, pas un état côté
  client. (b) Si une analyse Stockfish manque malgré tout (autres modes, ou
  deuxième ligne de défense), `_build_context_text` écrit explicitement
  "Analyse Stockfish indisponible pour cet exercice/cette position : aucun
  verdict, aucune évaluation, aucun meilleur coup" et un nouvel addendum
  système (`_ANALYSE_INDISPONIBLE_ADDENDUM`) interdit formellement d'inventer
  un verdict/une évaluation/un meilleur coup/une ligne. (c) Données
  partielles (verdict rendu mais évaluation, meilleur coup ou ligne
  principale manquants) signalées champ par champ ("évaluation
  indisponible", "ligne principale indisponible"...) avec interdiction
  explicite de les inventer.
- `static/exercise.js`/`templates/index.html` : minuteur de garde côté
  interface (30s, indépendant du délai serveur) — si le verdict ne revient
  pas, remplace « Le coach réfléchit... » par « L'analyse Stockfish est
  indisponible » avec un bouton « Réessayer » (rejoue le même coup sans
  redemande) ; le plateau reste explorable et « Exercice suivant » reste
  utilisable. Champ de question, bouton « Envoyer » et bouton « Demander
  l'avis du coach » désactivés et grisés (placeholder/texte d'aide
  « Disponible après le verdict ») tant qu'aucun verdict n'est obtenu pour la
  tentative en cours — réactivés dès l'arrivée du verdict ou en quittant le
  mode exercice.
- `static/controls.js`/`static/board.js` : `MODE_CAPS.exercise.
  askCoachAvailable` exige désormais un verdict rendu ; défense en
  profondeur côté `coachSend()` (ignore un envoi programmatique qui
  contournerait l'état `disabled` du DOM) ; messages d'erreur
  `pas_de_verdict_exercice` mappés vers le même texte que le minuteur de
  garde sur les 3 canaux concernés (`coach_ask`, `exercise_answer`,
  `coach_on_demand`).

### Tests effectués (moteur réel `/usr/games/stockfish`, cf. rapport de clôture)

- Mort du moteur pendant l'inactivité puis pendant un appel (`SIGKILL` du
  process sous-jacent) : reprise automatique réussie dans les deux cas,
  verdict réel obtenu après une seule relance (0,2 à 1,8s).
- Panne persistante (reconstruction forcée en échec) : quota de 3 relances
  respecté, jamais de blocage, `indisponible=True` retourné à chaque appel
  au-delà du quota.
- Deux appels concurrents (2 fils) après une mort du moteur : les deux
  aboutissent sans corruption ni blocage (verrou par instance déjà en
  place).
- Fichier `moteur_erreurs.log` : contenu vérifié (heure, opération, message,
  code de sortie, relances, stderr).
- Contexte coach sans verdict : `get_coach_response` refuse l'appel
  (`pas_de_verdict_exercice`) avant toute requête réseau (vérifié avec une
  clé API factice) ; `_build_context_text` produit la mention explicite
  requise sans jamais inventer de verdict ; cas de données partielles
  (verdict "bon" sans évaluation ni ligne, reproduisant le cas réel Rc1)
  vérifié champ par champ.
- Démarrage à froid réel (import de `app.py`, nouvelle instance Stockfish) :
  `get_move`/`evaluate` fonctionnels immédiatement.
- Position réelle du signalement (Re5, `4r2k/5p1p/pp1q1p2/2p2Q2/1PPp4/P6P/
  5PP1/3R2K1 b - - 0 23`) : confirmé avec le vrai moteur que Re5 est
  classé "bon" (delta ≈ 33cp), pas une gaffe — corrobore le constat
  d'Alain.
- Aucun appel API réel effectué (pas de clé configurée dans ce worktree,
  conformément à la consigne de ne pas toucher au `.env`) : vérifié à la
  place le contenu exact du contexte/system prompt transmis en amont de
  l'appel.

### Limites connues

- La cause exacte de la toute première panne réelle (19h25/19h26) reste
  non reproduite à l'identique (pas de cause unique confirmée : le candidat
  retenu — appel bloquant sans timeout — est corrigé par prudence, sans
  certitude absolue qu'il s'agisse de LA cause ; aucune autre cause probable
  trouvée dans le code des issues #75/#76/#77 examiné).
- Le minuteur de garde côté interface (30s) et le délai d'appel moteur
  (12s) + une relance sont indépendants : un cas pathologique pourrait en
  théorie dépasser 30s côté interface tout en restant sous le délai moteur
  cumulé — jugé acceptable (le message « analyse indisponible » reste
  correct dans ce cas, juste potentiellement affiché un peu après que le
  serveur ait déjà résolu la panne de son côté).
