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

LLM_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("CHESSCOACH_LLM_MODEL", "claude-haiku-4-5")

DATA_DIR.mkdir(parents=True, exist_ok=True)
