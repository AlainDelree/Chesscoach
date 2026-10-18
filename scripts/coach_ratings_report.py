#!/usr/bin/env python3
"""
coach_ratings_report.py — Rapport sur les notes Claude/Mistral

Script en ligne de commande qui lit data/coach_ratings.jsonl et affiche :
- le total de 1 et de 0 par agent
- la liste des cas où les deux agents divergent (l'un à 1, l'autre à 0)
  avec la position (FEN), le coup joué et le texte des deux avis

Usage :
    python3 scripts/coach_ratings_report.py

Issue #113, point 11.
"""

import json
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour importer config
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

RATINGS_PATH = os.path.join(config.DATA_DIR, "coach_ratings.jsonl")


def load_ratings():
    """Charger toutes les notes depuis le fichier JSONL."""
    ratings = []
    if not os.path.exists(RATINGS_PATH):
        print(f"Aucun fichier de notes trouvé : {RATINGS_PATH}")
        print("Utilisez d'abord l'application pour générer des notes.")
        return ratings
    
    try:
        with open(RATINGS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ratings.append(json.loads(line))
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier : {e}")
        return []
    
    return ratings


def get_coach_calls_log():
    """Charger le fichier coach_calls.log pour récupérer les textes des avis."""
    log_path = config.COACH_CALLS_LOG_PATH
    calls = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        calls.append(json.loads(line))
        except Exception as e:
            print(f"Erreur lors de la lecture de {log_path} : {e}")
    return calls


def get_text_for_log_id(log_id, calls):
    """Récupérer le texte de la réponse pour un log_id donné."""
    for call in calls:
        if call.get("log_id") == log_id:
            return call.get("response", "")
    return ""


def main():
    print("=" * 80)
    print("Rapport des notes Claude/Mistral")
    print("=" * 80)
    print()
    
    ratings = load_ratings()
    if not ratings:
        return
    
    # Compter par agent
    counts = {"claude": {"1": 0, "0": 0}, "mistral": {"1": 0, "0": 0}}
    
    for r in ratings:
        agent = r.get("agent", "").lower()
        rating = r.get("rating")
        if agent in counts and rating in (0, 1):
            counts[agent][str(rating)] += 1
    
    print("Totaux par agent :")
    print("-" * 40)
    for agent in ["claude", "mistral"]:
        total_1 = counts[agent]["1"]
        total_0 = counts[agent]["0"]
        total = total_1 + total_0
        print(f"  {agent.capitalize()} : {total_1} × 1, {total_0} × 0 (total: {total})")
    print()
    
    # Trouver les divergences
    # Regrouper par (fen, coup_propose) pour trouver les cas où les deux agents
    # ont noté la même position/coup
    position_ratings = {}
    for r in ratings:
        key = (r.get("fen"), r.get("coup_propose"))
        if key not in position_ratings:
            position_ratings[key] = {}
        position_ratings[key][r.get("agent", "").lower()] = r
    
    # Charger les logs pour récupérer les textes
    calls = get_coach_calls_log()
    
    # Trouver les divergences
    divergences = []
    for (fen, coup), agents in position_ratings.items():
        if "claude" in agents and "mistral" in agents:
            claude_rating = agents["claude"].get("rating")
            mistral_rating = agents["mistral"].get("rating")
            if claude_rating is not None and mistral_rating is not None:
                if claude_rating != mistral_rating:
                    claude_log_id = agents["claude"].get("log_id", "")
                    mistral_log_id = agents["mistral"].get("log_id", "")
                    
                    claude_text = get_text_for_log_id(claude_log_id, calls)
                    mistral_text = get_text_for_log_id(mistral_log_id, calls)
                    
                    divergences.append({
                        "fen": fen,
                        "coup_propose": coup,
                        "claude_rating": claude_rating,
                        "mistral_rating": mistral_rating,
                        "claude_model": agents["claude"].get("model", ""),
                        "mistral_model": agents["mistral"].get("model", ""),
                        "claude_text": claude_text,
                        "mistral_text": mistral_text,
                    })
    
    if divergences:
        print("Cas divergents (Claude et Mistral en désaccord) :")
        print("-" * 40)
        print()
        
        for i, div in enumerate(divergences, 1):
            print(f"  Cas #{i} :")
            print(f"    Position : {div['fen']}")
            print(f"    Coup : {div['coup_propose']}")
            print(f"    Claude ({div['claude_model']}) : {div['claude_rating']}")
            print(f"    Mistral ({div['mistral_model']}) : {div['mistral_rating']}")
            print()
            print("    Avis de Claude :")
            print(f"      {div['claude_text'][:200]}{'...' if len(div['claude_text']) > 200 else ''}")
            print()
            print("    Avis de Mistral :")
            print(f"      {div['mistral_text'][:200]}{'...' if len(div['mistral_text']) > 200 else ''}")
            print()
            print("    " + "-" * 70)
            print()
    else:
        print("Aucun cas divergent trouvé.")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
