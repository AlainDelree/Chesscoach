"""
coach_ratings.py — ChessCoach, gestion des notes pour la comparaison Claude/Mistral

Module pour enregistrer et analyser les notes (1/0) attribuées aux avis des agents
Claude et Mistral. Les notes sont stockées dans un fichier JSONL sous data/
(hors git, comme les autres journaux).

Fichier de stockage : data/coach_ratings.jsonl
Format : une ligne JSON par note, avec les champs :
  - timestamp : date et heure ISO
  - agent : "claude" ou "mistral"
  - model : modèle utilisé
  - rating : 0, 1 ou null (note supprimée)
  - log_id : identifiant de l'appel dans coach_calls.log
  - fen : FEN de la position
  - coup_propose : coup joué (SAN)
  - mode : mode (ex: "exercice")
  - version_info : dict avec commit_hash, commit_message, modified, last_issue, serie
    (issue #124) — informations de version au moment où l'AVIS a été produit

Issue #113, points 9-11.
Issue #124 : Suite #120 — enregistrer la version du code et une étiquette de série.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import config

RATINGS_PATH = os.path.join(config.DATA_DIR, "coach_ratings.jsonl")


def _get_coach_calls_files():
    """Retourne la liste de tous les fichiers coach_calls*.log (y compris archives mensuelles)."""
    log_dir = Path(config.COACH_CALLS_LOG_PATH).parent
    log_base = Path(config.COACH_CALLS_LOG_PATH)
    # Pattern : coach_calls.log et coach_calls-AAAA-MM.log
    return sorted(log_dir.glob(f"{log_base.stem}*{log_base.suffix}"), key=lambda p: p.name)


def _get_version_info_from_log_id(log_id: str) -> dict:
    """Récupère les informations de version depuis une entrée de journal.
    
    Cherche dans tous les fichiers coach_calls*.log l'entrée avec l'ID donné
    et retourne son champ version_info si présent, sinon un dict avec
    toutes les valeurs à "inconnue"/None.
    
    Args:
        log_id: identifiant de l'appel (champ "id" dans le journal)
        
    Returns:
        Dict avec les clés : commit_hash, commit_message, modified, last_issue, serie
        ou toutes les valeurs à "inconnue"/None si l'entrée n'est pas trouvée.
    """
    log_files = _get_coach_calls_files()
    
    for log_path in log_files:
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entry = json.loads(line)
                            if entry.get("id") == log_id:
                                # Retourner version_info si présent, sinon valeurs par défaut
                                version_info = entry.get("version_info")
                                if version_info is not None:
                                    return version_info
                                else:
                                    # Entrée ancienne sans version_info
                                    return {
                                        "commit_hash": "inconnue",
                                        "commit_message": "inconnue",
                                        "modified": False,
                                        "last_issue": None,
                                        "serie": "",
                                    }
            except Exception:
                # Ignorer les erreurs de lecture et continuer avec le fichier suivant
                continue
    
    # Si aucune entrée n'est trouvée, retourner "inconnue"
    return {
        "commit_hash": "inconnue",
        "commit_message": "inconnue",
        "modified": False,
        "last_issue": None,
        "serie": "",
    }


def _ensure_ratings_dir():
    """S'assurer que le répertoire data/ existe."""
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)


def record_rating(agent, model, rating, log_id, fen, coup_propose, mode="exercice"):
    """Enregistrer une note pour un avis d'agent.
    
    Si une note existe déjà pour le même (agent, log_id), elle est remplacée
    (pas de doublon).
    
    Issue #124 : Les informations de version (commit_hash, commit_message, modified,
    last_issue, serie) sont lues depuis l'entrée de journal correspondante via
    l'identifiant d'appel (log_id). Si l'entrée de journal est introuvable,
    toutes les valeurs sont enregistrées comme "inconnue".
    
    Args:
        agent: "claude" ou "mistral"
        model: modèle utilisé (ex: "claude-3-5-sonnet-20241022", "mistral-large-latest")
        rating: 0, 1 ou None (pour supprimer)
        log_id: identifiant de l'appel dans coach_calls.log
        fen: FEN de la position
        coup_propose: coup joué (SAN)
        mode: mode (ex: "exercice")
    """
    _ensure_ratings_dir()
    
    # Récupérer les informations de version depuis le journal (issue #124)
    version_info = _get_version_info_from_log_id(log_id)
    
    # Lire les notes existantes
    existing_ratings = []
    if os.path.exists(RATINGS_PATH):
        try:
            with open(RATINGS_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        existing_ratings.append(json.loads(line))
        except Exception:
            pass
    
    # Supprimer l'ancienne note pour ce log_id si elle existe
    existing_ratings = [
        r for r in existing_ratings 
        if not (r.get("agent") == agent and r.get("log_id") == log_id)
    ]
    
    # Si rating est None, on ne veut pas enregistrer de note (suppression)
    if rating is None:
        # Écrire les notes restantes
        with open(RATINGS_PATH, "w", encoding="utf-8") as f:
            for r in existing_ratings:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return
    
    # Créer la nouvelle note
    new_rating = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "model": model,
        "rating": rating,
        "log_id": log_id,
        "fen": fen,
        "coup_propose": coup_propose,
        "mode": mode,
        "version_info": version_info,  # Issue #124
    }
    
    # Ajouter la nouvelle note
    existing_ratings.append(new_rating)
    
    # Écrire toutes les notes
    with open(RATINGS_PATH, "w", encoding="utf-8") as f:
        for r in existing_ratings:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def get_all_ratings():
    """Lire toutes les notes depuis le fichier JSONL.
    
    Retourne une liste de dicts.
    """
    _ensure_ratings_dir()
    
    ratings = []
    if os.path.exists(RATINGS_PATH):
        try:
            with open(RATINGS_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        ratings.append(json.loads(line))
        except Exception:
            pass
    return ratings


def get_ratings_summary():
    """Calculer le résumé des notes par agent.
    
    Retourne un dict avec :
      - total_1: nombre total de 1 par agent
      - total_0: nombre total de 0 par agent
      - divergences: liste des cas où les deux agents divergent
    """
    ratings = get_all_ratings()
    
    # Compter par agent
    counts = {"claude": {"1": 0, "0": 0}, "mistral": {"1": 0, "0": 0}}
    
    for r in ratings:
        agent = r.get("agent")
        rating = r.get("rating")
        if agent in counts and rating in counts[agent]:
            counts[agent][str(rating)] += 1
    
    # Trouver les divergences : même log_id ou même (fen, coup_propose) avec des notes différentes
    # On regroupe par (fen, coup_propose) pour trouver les cas où les deux agents
    # ont noté la même position/coup
    position_ratings = {}
    for r in ratings:
        key = (r.get("fen"), r.get("coup_propose"))
        if key not in position_ratings:
            position_ratings[key] = {}
        position_ratings[key][r.get("agent")] = r
    
    # Trouver les divergences
    divergences = []
    for (fen, coup), agents in position_ratings.items():
        if "claude" in agents and "mistral" in agents:
            claude_rating = agents["claude"].get("rating")
            mistral_rating = agents["mistral"].get("rating")
            if claude_rating is not None and mistral_rating is not None:
                if claude_rating != mistral_rating:
                    divergences.append({
                        "fen": fen,
                        "coup_propose": coup,
                        "claude_text": agents["claude"].get("text", ""),
                        "mistral_text": agents["mistral"].get("text", ""),
                        "claude_rating": claude_rating,
                        "mistral_rating": mistral_rating,
                        "claude_model": agents["claude"].get("model", ""),
                        "mistral_model": agents["mistral"].get("model", ""),
                    })
    
    return {
        "counts": counts,
        "divergences": divergences,
    }
