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


def _get_coach_calls_files():
    """Retourne la liste de tous les fichiers coach_calls*.log (y compris archives mensuelles)."""
    log_dir = Path(config.COACH_CALLS_LOG_PATH).parent
    log_base = Path(config.COACH_CALLS_LOG_PATH).name
    # Pattern : coach_calls.log et coach_calls-AAAA-MM.log
    return sorted(log_dir.glob(f"{log_base.stem}*{log_base.suffix}"), key=lambda p: p.name)


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
    """Charger tous les fichiers coach_calls*.log pour récupérer les textes des avis.
    
    Issue #115 : Lit tous les fichiers (mensuels et archives) comme la fonction
    coachlog d'Alain, sans échouer si le fichier sans suffixe est absent.
    """
    calls = []
    log_files = _get_coach_calls_files()
    
    for log_path in log_files:
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
    """Récupérer le texte de la réponse et la température pour un log_id donné.
    
    Retourne un tuple (texte, temperature) où temperature est une chaîne ou None.
    """
    for call in calls:
        if call.get("id") == log_id:  # Note: le champ est "id", pas "log_id"
            return call.get("reponse", ""), call.get("temperature")
    return "", None


def _afficher_statistiques_fact_checker(calls):
    """Affiche les statistiques des alertes du vérificateur d'affirmations factuelles.
    
    Issue #117 : affiche par agent le nombre d'avis avec au moins une alerte
    et le nombre total d'alertes.
    """
    # Compter les alertes par agent
    stats_par_agent = {"claude": {"avis_avec_alertes": 0, "total_alertes": 0},
                       "mistral": {"avis_avec_alertes": 0, "total_alertes": 0}}
    
    for call in calls:
        # Vérifier si c'est un appel en mode exercice
        if call.get("mode_origine") != "exercice":
            continue
        
        # Récupérer les alertes du vérificateur
        fact_checker_alertes = call.get("fact_checker_alertes", [])
        
        if not fact_checker_alertes:
            continue
        
        # Déterminer l'agent
        model = call.get("model", "")
        if "mistral" in model.lower():
            agent = "mistral"
        elif "claude" in model.lower():
            agent = "claude"
        else:
            # Essayer de deviner à partir du nom du modèle
            if model and "mistral" in model:
                agent = "mistral"
            else:
                agent = "claude"
        
        if agent in stats_par_agent:
            stats_par_agent[agent]["avis_avec_alertes"] += 1
            stats_par_agent[agent]["total_alertes"] += len(fact_checker_alertes)
    
    # Afficher les statistiques
    print("Statistiques des alertes du vérificateur d'affirmations factuelles (issue #117) :")
    print("-" * 80)
    
    total_avis_avec_alertes = 0
    total_alertes = 0
    
    for agent in ["claude", "mistral"]:
        avis_avec_alertes = stats_par_agent[agent]["avis_avec_alertes"]
        total_alertes_agent = stats_par_agent[agent]["total_alertes"]
        total_avis_avec_alertes += avis_avec_alertes
        total_alertes += total_alertes_agent
        
        print(f"  {agent.capitalize()} : {avis_avec_alertes} avis avec alerte(s), {total_alertes_agent} alerte(s) totale(s)")
    
    print(f"  Total : {total_avis_avec_alertes} avis avec alerte(s), {total_alertes} alerte(s) totale(s)")


def main():
    print("=" * 80)
    print("Rapport des notes Claude/Mistral")
    print("=" * 80)
    print()
    
    # Statistiques des alertes du vérificateur d'affirmations factuelles (issue #117)
    _afficher_statistiques_fact_checker(calls)
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
                    
                    claude_text, claude_temp = get_text_for_log_id(claude_log_id, calls)
                    mistral_text, mistral_temp = get_text_for_log_id(mistral_log_id, calls)
                    
                    divergences.append({
                        "fen": fen,
                        "coup_propose": coup,
                        "claude_rating": claude_rating,
                        "mistral_rating": mistral_rating,
                        "claude_model": agents["claude"].get("model", ""),
                        "claude_temperature": claude_temp,
                        "mistral_model": agents["mistral"].get("model", ""),
                        "mistral_temperature": mistral_temp,
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
            claude_temp_str = f" (T={div['claude_temperature']})" if div.get('claude_temperature') else ""
            mistral_temp_str = f" (T={div['mistral_temperature']})" if div.get('mistral_temperature') else ""
            print(f"    Claude ({div['claude_model']}{claude_temp_str}) : {div['claude_rating']}")
            print(f"    Mistral ({div['mistral_model']}{mistral_temp_str}) : {div['mistral_rating']}")
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
