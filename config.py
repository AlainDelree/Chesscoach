"""
config.py — ChessCoach
Configuration centrale : chemins de données et paramètres du coach LLM.
La clé API Claude n'est jamais codée en dur, uniquement lue depuis
l'environnement.
"""

import json
import os
from pathlib import Path

DATA_DIR = Path.home() / "ChessCoach" / "data"
ENGINES_DIR = Path.home() / "ChessCoach" / "engines"

COACH_MEMORY_PATH = DATA_DIR / "coach_memory.json"
ERREURS_DETECTEES_PATH = DATA_DIR / "erreurs_detectees.json"

# Historique local des exercices proposés (issue #76, mode "Exercice") :
# position (FEN), nombre de fois proposé, date de la dernière proposition,
# résultat de la dernière tentative — sert au tirage à privilégier la
# variété (cf. exercise_history.py) et à l'indicateur "déjà fait" de
# l'interface. Donnée personnelle, sous DATA_DIR donc gitignorée comme le
# reste de data/.
EXERCICE_HISTORIQUE_PATH = DATA_DIR / "exercice_historique.json"

# Source d'exercices « Problèmes Lichess » (issue #78) : pool de problèmes
# préparé hors-ligne par preparer_puzzles_lichess.py à partir du CSV de la
# base ouverte de problèmes Lichess (licence CC0, téléchargé manuellement
# par Alain — jamais par CCL) et niveau Elo-like courant par catégorie de
# thème (lichess_puzzles.py), mis à jour après chaque résultat. Données
# personnelles, sous DATA_DIR donc gitignorées comme le reste de data/.
# L'historique « déjà fait » de cette source réutilise EXERCICE_HISTORIQUE_PATH
# ci-dessus (clé "lichess:<PuzzleId>", jamais en collision avec les FEN
# utilisées comme clé par la source « Mes erreurs »).
LICHESS_PUZZLES_PATH = DATA_DIR / "puzzles_lichess.json"
LICHESS_NIVEAUX_PATH = DATA_DIR / "niveau_exercices_lichess.json"

# Log de chaque appel au coach en mode "Exercice" (issue #18) : horodatage,
# system prompt complet, contexte construit et messages envoyés, en JSON
# Lines — pour diagnostiquer les erreurs factuelles du coach à partir de ce
# qui a été réellement transmis, pas d'une supposition. Sous DATA_DIR, donc
# gitignoré comme le reste des données ; pas de rotation à ce stade.
COACH_CALLS_LOG_PATH = DATA_DIR / "logs" / "coach_calls.log"

# Log des échecs du bouton "Analyser cette partie" (issue #77 point 1) :
# heure, mode d'origine (pedagogic/opening/finale/free/revue) et message
# d'erreur, une ligne par échec — pour diagnostiquer un futur échec ponctuel
# (position de départ non standard, moteur indisponible, etc.) sans avoir à
# le reproduire en direct. Sous DATA_DIR, donc gitignoré comme le reste des
# données ; pas de rotation à ce stade (même pattern que COACH_CALLS_LOG_PATH).
ANALYSE_ERREURS_LOG_PATH = DATA_DIR / "logs" / "analyse_erreurs.log"

# Signalements d'une réponse du coach (issue #89, bouton "Signaler" sous
# chaque réponse) : horodatage, mode d'origine, identifiant de l'entrée
# correspondante de COACH_CALLS_LOG_PATH quand elle est connue (champ "id",
# cf. llm_coach._log_coach_call), FEN/coup/réponse signalée et commentaire
# libre d'Alain — une ligne JSON par signalement. Sous DATA_DIR, donc
# gitignoré comme le reste des données ; pas de rotation à ce stade (même
# pattern que COACH_CALLS_LOG_PATH/ANALYSE_ERREURS_LOG_PATH).
SIGNALEMENTS_LOG_PATH = DATA_DIR / "logs" / "signalements.log"

# Page « club » (issue #142) : compteur d'avis du coach consommés aujourd'hui
# par /api/club/avis ({"date": "AAAA-MM-JJ", "count": int}, remise à zéro
# quand la date ne correspond plus au jour courant) — persisté sur disque
# pour survivre à un redémarrage du serveur, cf. app.py CLUB_MAX_AVIS_PAR_JOUR.
# Jugements portés sur ces avis (bouton à l'étape 4, hors périmètre ici) :
# une ligne JSON par jugement, SÉPARÉ de coach_ratings.jsonl pour ne jamais
# mélanger les notes d'Alain avec celles d'un visiteur du club. Les deux sous
# DATA_DIR, donc gitignorés comme le reste des données.
CLUB_AVIS_COMPTEUR_PATH = DATA_DIR / "club_avis_compteur.json"
CLUB_JUGEMENTS_LOG_PATH = DATA_DIR / "logs" / "club_jugements.log"

# Log des pannes du moteur Stockfish lui-même (issue #79) : heure, opération
# en cours, message d'erreur, code de sortie du processus et dernières
# lignes de son flux d'erreur standard quand ils sont disponibles, nombre de
# relances déjà tentées — distinct d'ANALYSE_ERREURS_LOG_PATH ci-dessus (qui
# trace l'échec du bouton "Analyser cette partie" côté application) : ce
# fichier-ci trace la panne du moteur lui-même (boucle d'événements morte,
# processus Stockfish terminé, délai dépassé), quel que soit le mode qui
# l'utilisait au moment de la panne. Sous DATA_DIR, donc gitignoré comme le
# reste des données ; pas de rotation à ce stade (même pattern que les deux
# logs ci-dessus).
MOTEUR_ERREURS_LOG_PATH = DATA_DIR / "logs" / "moteur_erreurs.log"

# État mémorisé de la décomposition classique de l'évaluation Stockfish
# ("eval", commande retirée à partir de Stockfish 16.1 — issue #80 point 5) :
# disponible ou non, et version du moteur, au moment de la dernière détection
# (une seule fois au démarrage de l'appli, et de nouveau après chaque relance
# du moteur d'évaluation par la reprise automatique, issue #79 — jamais
# retestée à chaque exercice). Sert à repérer un changement entre deux
# démarrages (ex. Stockfish mis à jour en arrière-plan par le système) pour le
# signaler dans le journal (issue #82). Sous DATA_DIR, donc gitignoré comme le
# reste des données.
EVAL_BREAKDOWN_STATE_PATH = DATA_DIR / "eval_breakdown_state.json"

# Compteur cumulé de tokens consommés par l'API Claude (issue #54) — pas de
# notion de prix ni de table de coût par modèle, seulement les tokens bruts
# renvoyés par chaque réponse de l'API, cumulés par modèle depuis une date de
# départ. Sous DATA_DIR, donc gitignoré comme le reste des données.
USAGE_TOKENS_PATH = DATA_DIR / "usage_tokens.json"

# Bibliothèque de positions-types de finales (issue #13) — fichier de
# données modifiable depuis l'interface (bouton "Enregistrer comme finale"
# du mode "Partie libre"), plus une liste figée dans le code (finales.py).
FINALES_PATH = DATA_DIR / "finales.json"

# Livre d'ouvertures Polyglot réel (issue #9, mode "travail d'ouverture") —
# déposé manuellement par Alain, gitignoré comme le reste de data/. Sa
# présence est vérifiée explicitement au démarrage de ce mode plutôt que de
# planter plus loin si le fichier est absent.
BOOK_PATH = DATA_DIR / "books" / "gm2001.bin"

# Tables de finales Syzygy 3-4-5 pièces (issue #32, mode "travail de
# finales") — déposées manuellement par Alain (depuis
# https://tablebase.lichess.ovh/tables/standard/, ~1 Go), gitignoré comme
# le reste d'engines/. Leur présence (dossier non vide) est vérifiée
# explicitement par engine_stockfish.py avant de configurer l'option UCI
# SyzygyPath, plutôt que de supposer qu'elles sont là.
SYZYGY_PATH = ENGINES_DIR / "syzygy"

LLM_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Configuration Mistral (issue #112) — clé API et modèle pour le second avis
# du coach en mode exercice. La clé est lue depuis .env sous MISTRAL_API_KEY,
# le modèle sous CHESSCOACH_MISTRAL_MODEL (défaut : mistral-large-latest).
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
CHESSCOACH_MISTRAL_MODEL = os.environ.get("CHESSCOACH_MISTRAL_MODEL", "mistral-large-latest")

# Température pour les appels LLM (issue #116) — configurable via .env.
# Pour Claude : si CHESSCOACH_CLAUDE_TEMPERATURE est absente ou vide, rien n'est
# envoyé (comportement strictement identique à aujourd'hui, l'API utilise sa
# valeur par défaut). Si elle est renseignée, elle est envoyée avec la requête,
# uniquement pour les appels du mode exercices.
CHESSCOACH_CLAUDE_TEMPERATURE = os.environ.get("CHESSCOACH_CLAUDE_TEMPERATURE", "")

# Pour Mistral : la valeur par défaut reste 0.0 (comportement actuel), mais elle
# devient configurable via CHESSCOACH_MISTRAL_TEMPERATURE. Une valeur invalide
# (non numérique, hors plage acceptée) est ignorée avec un avertissement dans les
# logs de l'appli, et la valeur par défaut s'applique.
CHESSCOACH_MISTRAL_TEMPERATURE = os.environ.get("CHESSCOACH_MISTRAL_TEMPERATURE", "0.0")

# Vérificateur d'affirmations factuelles (issue #117) — activé par défaut.
# Peut être désactivé en mettant CHESSCOACH_FACT_CHECKER_ACTIVATED=0 dans .env.
CHESSCOACH_FACT_CHECKER_ACTIVATED = os.environ.get("CHESSCOACH_FACT_CHECKER_ACTIVATED", "1")

# Les deux modèles Claude choisissables depuis l'interface (issue #61) —
# identifiants canoniques définis ici en un seul endroit, réutilisés par
# app.py (sélecteur de l'en-tête) et par le fallback en cas de refus de
# l'API. Haiku pour les tests économiques, Sonnet pour le jeu sérieux.
LLM_MODEL_HAIKU = "claude-haiku-4-5"
LLM_MODEL_SONNET = "claude-sonnet-5"
LLM_MODEL_CHOICES = {
    LLM_MODEL_HAIKU: "Haiku (test)",
    LLM_MODEL_SONNET: "Sonnet (sérieux)",
}

# Choix de modèle persisté entre deux lancements (issue #61) — fichier séparé
# du .env, jamais modifié par l'appli : {"model": <id>}. Sous DATA_DIR, donc
# gitignoré comme le reste des données personnelles.
LLM_MODEL_CHOICE_PATH = DATA_DIR / "llm_model_choice.json"


def _charger_choix_modele_llm() -> str:
    """Détermine le modèle actif au démarrage (issue #61) : LLM_MODEL_CHOICE_PATH
    prime s'il contient un choix valide (persistance entre deux lancements).
    À défaut (premier lancement, fichier absent ou invalide), reprend
    CHESSCOACH_LLM_MODEL si sa valeur correspond à l'un des deux choix
    connus, sinon Sonnet par défaut (jeu sérieux plutôt que test)."""
    try:
        brut = json.loads(LLM_MODEL_CHOICE_PATH.read_text(encoding="utf-8"))
        choix = brut.get("model")
        if choix in LLM_MODEL_CHOICES:
            return choix
    except (OSError, ValueError, AttributeError):
        pass
    env_model = os.environ.get("CHESSCOACH_LLM_MODEL", "")
    return env_model if env_model in LLM_MODEL_CHOICES else LLM_MODEL_SONNET


LLM_MODEL = _charger_choix_modele_llm()


def set_llm_model(model_id: str) -> bool:
    """Change le modèle actif (issue #61) : effet immédiat sur tous les appels
    suivants — app.py relit l'attribut config.LLM_MODEL à chaque appel, jamais
    une copie figée au démarrage — et persistance dans LLM_MODEL_CHOICE_PATH.
    Le .env n'est jamais modifié. Retourne False sans aucun effet si model_id
    n'est pas l'un des deux choix valides."""
    global LLM_MODEL
    if model_id not in LLM_MODEL_CHOICES:
        return False
    LLM_MODEL = model_id
    try:
        LLM_MODEL_CHOICE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LLM_MODEL_CHOICE_PATH.write_text(
            json.dumps({"model": model_id}, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
    return True

# Délai maximal d'une réponse du coach (issue #105) — valeurs à modifier ICI,
# en un seul endroit, pour changer le comportement de TOUS les appels au
# coach : passées en secondes à urllib.request.urlopen (paramètre timeout=)
# dans llm_coach._call_claude, donc une vraie coupure côté serveur de l'appel
# à l'API Claude, pas une simple alerte visuelle côté interface. Le minuteur
# de garde côté navigateur (static/board.js, coachWaitBegin) reprend ces
# mêmes valeurs (converties en ms et exposées via window.COACH_SERVER_TIMEOUT_MS,
# cf. templates/index.html/app.py index()) en y ajoutant une marge, pour se
# déclencher TOUJOURS après le serveur sauf si celui-ci ne répond plus du
# tout (seul cas où le navigateur tranche alors seul).
#
# La relance automatique de fiabilité (llm_coach.get_coach_response, après
# une première réponse jugée incohérente par coach_reliability) réutilise
# EXACTEMENT ce même délai pour son propre appel à l'API — un délai dépassé
# à ce stade compte donc dans le délai total vu par l'interface, qui peut
# (cas rare) friser près du double de cette valeur avant que le serveur ne
# tranche définitivement.
COACH_TIMEOUT_REPONSE_S = 60

# Délai plus long pour les appels portant sur une partie entière plutôt
# qu'un seul coup (analyse de partie : sélection des coups décisifs et
# explication d'un coup flagué ; programme d'entraînement) — contexte plus
# volumineux transmis à l'API, latence réelle plus élevée que pour une
# réponse ponctuelle.
COACH_TIMEOUT_ANALYSE_S = 150

# Mode debug Flask/Werkzeug (débogueur interactif + rechargement automatique
# du code) — désactivé par défaut (issue #51) car le débogueur expose une
# console web joignable avant le filtre d'accès distant. Réactivable pour le
# développement local via cette variable ; app.py force alors l'écoute sur
# 127.0.0.1 uniquement, jamais sur 0.0.0.0.
DEBUG_DEV = os.environ.get("CHESSCOACH_DEBUG_DEV", "") == "1"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SYZYGY_PATH.mkdir(parents=True, exist_ok=True)
