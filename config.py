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

# Mode debug Flask/Werkzeug (débogueur interactif + rechargement automatique
# du code) — désactivé par défaut (issue #51) car le débogueur expose une
# console web joignable avant le filtre d'accès distant. Réactivable pour le
# développement local via cette variable ; app.py force alors l'écoute sur
# 127.0.0.1 uniquement, jamais sur 0.0.0.0.
DEBUG_DEV = os.environ.get("CHESSCOACH_DEBUG_DEV", "") == "1"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SYZYGY_PATH.mkdir(parents=True, exist_ok=True)
