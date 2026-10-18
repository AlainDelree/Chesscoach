#!/usr/bin/env python3
"""
test_fact_checker.py — Script de test pour le vérificateur d'affirmations factuelles (issue #117)

Ce script rejoue le vérificateur hors ligne sur les avis déjà présents dans
les fichiers coach_calls*.log pour valider son fonctionnement.

Usage :
    python3 test_fact_checker.py [--log-dir DOSSIER] [--date AAAA-MM]

Exemples :
    python3 test_fact_checker.py
    python3 test_fact_checker.py --log-dir ~/ChessCoach/data/logs
    python3 test_fact_checker.py --date 2026-10
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path pour importer config et fact_checker
sys.path.insert(0, str(Path(__file__).parent))

import config
import fact_checker


def _get_coach_calls_files(log_dir: Path = None) -> list:
    """Retourne la liste de tous les fichiers coach_calls*.log (y compris archives mensuelles)."""
    if log_dir is None:
        log_dir = Path(config.COACH_CALLS_LOG_PATH).parent
    
    log_base = Path(config.COACH_CALLS_LOG_PATH).name
    # Pattern : coach_calls.log et coach_calls-AAAA-MM.log
    return sorted(log_dir.glob(f"{log_base.stem}*{log_base.suffix}"), key=lambda p: p.name)


def _charger_entrees(fichiers: list) -> list:
    """Charge toutes les entrées des fichiers de log."""
    entrees = []
    for fichier in fichiers:
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                for ligne in f:
                    ligne = ligne.strip()
                    if not ligne:
                        continue
                    try:
                        entrees.append(json.loads(ligne))
                    except (ValueError, TypeError):
                        continue
        except OSError as e:
            print(f"(ignoré, illisible : {fichier} — {e})", file=sys.stderr)
    return entrees


def _filtrer_par_date(entrees: list, date_str: str = None) -> list:
    """Filtre les entrées par date (format AAAA-MM)."""
    if not date_str:
        return entrees
    
    filtered = []
    for entree in entrees:
        horodatage = entree.get("horodatage", "")
        if horodatage.startswith(date_str):
            filtered.append(entree)
    
    return filtered


def _tester_verificateur(entrees: list) -> dict:
    """Teste le vérificateur sur toutes les entrées et retourne les résultats.
    
    Retourne :
    {
        'total_entrees': int,
        'entrees_testees': int,
        'alertes_par_entree': dict,  # {log_id: [alertes]}
        'alertes_attendues_trouvees': dict,  # {description: bool}
        'fausses_alertes': list,  # [(log_id, alerte)]
        'statistiques_par_agent': dict
    }
    """
    resultats = {
        'total_entrees': len(entrees),
        'entrees_testees': 0,
        'alertes_par_entree': {},
        'alertes_attendues_trouvees': {},
        'fausses_alertes': [],
        'statistiques_par_agent': {"claude": {"alertes": 0, "entrees_avec_alertes": 0},
                                   "mistral": {"alertes": 0, "entrees_avec_alertes": 0}}
    }
    
    # Alertes attendues selon l'issue #117
    # Les trois affirmations de pions chez Mistral :
    # - 20:26 : pion noir en d4 qui « attaquerait ta dame et ton cavalier » alors qu'il n'attaque que c3 et e3
    # - 20:34 : tour attaquée par un « pion blanc c4 » alors qu'aucun pion blanc n'est en c4
    # - 20:35 : pion noir en c6 qui « menacerait un fou en b7 » alors qu'il attaque b5 et d5
    # - 20:41 : contradiction « moins précis que le meilleur coup » alors que le coup joué EST le meilleur coup
    # - 20:33 : erreur de verdict de 20:33 chez Mistral (« erreur » pour un coup de verdict « bon »)
    
    alertes_attendues = {
        "mistral_20:26_pion_d4_attaque_dame_cavalier": False,
        "mistral_20:34_pion_blanc_c4": False,
        "mistral_20:35_pion_c6_menace_fou_b7": False,
        "mistral_20:41_moins_precis_meilleur_coup": False,
        "mistral_20:33_erreur_verdict_bon": False,
    }
    
    for entree in entrees:
        # On ne teste que les entrées en mode exercice
        if entree.get("mode_origine") != "exercice":
            continue
        
        resultats['entrees_testees'] += 1
        
        context = entree.get("context", {})
        reponse = entree.get("reponse", "")
        model = entree.get("model", "")
        log_id = entree.get("id", "inconnu")
        horodatage = entree.get("horodatage", "")
        
        # Déterminer l'agent
        if "mistral" in model.lower():
            agent = "mistral"
        elif "claude" in model.lower():
            agent = "claude"
        else:
            agent = "inconnu"
        
        # Exécuter le vérificateur
        try:
            result = fact_checker.verifier_affirmations(
                reponse,
                context,
                agent=agent,
                camp_alain=context.get("camp_alain")
            )
            
            alertes = result.get("alertes", [])
            resultats['alertes_par_entree'][log_id] = alertes
            
            # Mettre à jour les statistiques par agent
            if agent in resultats['statistiques_par_agent']:
                if alertes:
                    resultats['statistiques_par_agent'][agent]['entrees_avec_alertes'] += 1
                resultats['statistiques_par_agent'][agent]['alertes'] += len(alertes)
            
            # Vérifier les alertes attendues
            for alerte in alertes:
                alerte_type = alerte.get("type", "")
                alerte_affirmation = alerte.get("affirmation", "").lower()
                
                # Vérifier les alertes attendues pour Mistral
                if agent == "mistral":
                    # 20:26 : pion noir en d4
                    if "20:26" in horodatage and "pion" in alerte_affirmation and "d4" in alerte_affirmation:
                        alertes_attendues["mistral_20:26_pion_d4_attaque_dame_cavalier"] = True
                    
                    # 20:34 : pion blanc c4
                    if "20:34" in horodatage and "pion" in alerte_affirmation and "c4" in alerte_affirmation:
                        alertes_attendues["mistral_20:34_pion_blanc_c4"] = True
                    
                    # 20:35 : pion c6 menace fou b7
                    if "20:35" in horodatage and "pion" in alerte_affirmation and "c6" in alerte_affirmation:
                        alertes_attendues["mistral_20:35_pion_c6_menace_fou_b7"] = True
                    
                    # 20:41 : moins précis que le meilleur coup
                    if "20:41" in horodatage and alerte_type == "coherence_verdict":
                        alertes_attendues["mistral_20:41_moins_precis_meilleur_coup"] = True
                    
                    # 20:33 : erreur pour un coup bon
                    if "20:33" in horodatage and alerte_type == "coherence_verdict":
                        alertes_attendues["mistral_20:33_erreur_verdict_bon"] = True
            
            # Vérifier les fausses alertes (alertes sur des avis de Claude)
            if agent == "claude" and alertes:
                # Claude ne devrait pas avoir d'alertes sur les données réelles
                for alerte in alertes:
                    resultats['fausses_alertes'].append((log_id, alerte))
                    
        except Exception as e:
            print(f"Erreur lors de la vérification de l'entrée {log_id}: {e}", file=sys.stderr)
    
    resultats['alertes_attendues_trouvees'] = alertes_attendues
    
    return resultats


def _afficher_rapport(resultats: dict):
    """Affiche un rapport complet des résultats du test."""
    print("=" * 80)
    print("Rapport de test du vérificateur d'affirmations factuelles (issue #117)")
    print("=" * 80)
    print()
    
    print(f"Entrées totales dans les logs : {resultats['total_entrees']}")
    print(f"Entrées testées (mode exercice) : {resultats['entrees_testees']}")
    print()
    
    # Statistiques par agent
    print("Statistiques par agent :")
    print("-" * 40)
    for agent, stats in resultats['statistiques_par_agent'].items():
        print(f"  {agent.capitalize()} : {stats['entrees_avec_alertes']} avis avec alerte(s), {stats['alertes']} alerte(s) totale(s)")
    print()
    
    # Alertes attendues
    print("Alertes attendues (selon l'issue #117) :")
    print("-" * 40)
    alertes_attendues = resultats['alertes_attendues_trouvees']
    for description, trouvee in alertes_attendues.items():
        status = "✓ TROUVÉE" if trouvee else "✗ NON TROUVÉE"
        print(f"  {status} : {description}")
    print()
    
    # Fausses alertes
    fausses_alertes = resultats['fausses_alertes']
    if fausses_alertes:
        print("Fausses alertes détectées (à corriger) :")
        print("-" * 40)
        for log_id, alerte in fausses_alertes:
            print(f"  Entrée {log_id} : {alerte.get('affirmation', '?')}")
            print(f"    Type : {alerte.get('type', '?')}")
            print(f"    Détails : {alerte.get('details', '?')}")
        print()
    else:
        print("Aucune fausse alerte détectée.")
        print()
    
    # Liste complète des alertes
    print("Liste complète des alertes produites :")
    print("-" * 40)
    
    for log_id, alertes in resultats['alertes_par_entree'].items():
        if alertes:
            print(f"  Entrée {log_id} :")
            for alerte in alertes:
                print(f"    - [{alerte.get('type', '?')}] {alerte.get('affirmation', '?')}")
                print(f"      Détails : {alerte.get('details', '?')}")
    print()
    
    # Résumé
    print("=" * 80)
    print("Résumé :")
    print("-" * 40)
    
    alertes_trouvees = sum(1 for v in alertes_attendues.values() if v)
    alertes_attendues_total = len(alertes_attendues)
    
    print(f"  Alertes attendues trouvées : {alertes_trouvees}/{alertes_attendues_total}")
    print(f"  Fausses alertes : {len(fausses_alertes)}")
    
    if alertes_trouvees == alertes_attendues_total and len(fausses_alertes) == 0:
        print()
        print("✓ TOUS LES TESTS ONT RÉUSSI")
    else:
        print()
        print("✗ DES TESTS ONT ÉCHOUÉ")
    
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Teste le vérificateur d'affirmations factuelles sur les logs existants."
    )
    parser.add_argument("--log-dir", default=None, help="Dossier des logs (défaut : config.COACH_CALLS_LOG_PATH.parent)")
    parser.add_argument("--date", default=None, help="Filtre par date (format AAAA-MM)")
    args = parser.parse_args()
    
    # Charger les fichiers de log
    log_dir = Path(args.log_dir) if args.log_dir else None
    fichiers = _get_coach_calls_files(log_dir)
    
    if not fichiers:
        print(f"Aucun fichier de log trouvé dans {log_dir or config.COACH_CALLS_LOG_PATH.parent}")
        return 1
    
    print(f"Chargement des logs depuis : {', '.join(str(f) for f in fichiers)}")
    print()
    
    # Charger les entrées
    entrees = _charger_entrees(fichiers)
    
    if not entrees:
        print("Aucune entrée trouvée dans les logs.")
        return 0
    
    # Filtrer par date si nécessaire
    if args.date:
        entrees = _filtrer_par_date(entrees, args.date)
        print(f"Filtre appliqué : {args.date} ({len(entrees)} entrées)")
        print()
    
    # Tester le vérificateur
    resultats = _tester_verificateur(entrees)
    
    # Afficher le rapport
    _afficher_rapport(resultats)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
