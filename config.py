"""
config.py — ChessCoach
Configuration centrale : chemins de données et paramètres du coach LLM.
La clé API Claude n'est jamais codée en dur, uniquement lue depuis
l'environnement.
"""

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
LLM_MODEL = os.environ.get("CHESSCOACH_LLM_MODEL", "claude-haiku-4-5")

# Mode debug Flask/Werkzeug (débogueur interactif + rechargement automatique
# du code) — désactivé par défaut (issue #51) car le débogueur expose une
# console web joignable avant le filtre d'accès distant. Réactivable pour le
# développement local via cette variable ; app.py force alors l'écoute sur
# 127.0.0.1 uniquement, jamais sur 0.0.0.0.
DEBUG_DEV = os.environ.get("CHESSCOACH_DEBUG_DEV", "") == "1"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SYZYGY_PATH.mkdir(parents=True, exist_ok=True)
