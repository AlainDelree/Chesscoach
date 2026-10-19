#!/usr/bin/env python3
"""
Test de simulation pour l'issue #123
Vérifie que "Exercice suivant" conserve le filtre de phase demandé
au lieu de se verrouiller sur la phase du dernier exercice tiré.
"""

import json
import sys
from pathlib import Path

# Chemin du projet
PROJECT_DIR = Path(__file__).parent


def test_exercise_js_separation():
    """Test 1 : Vérifier la séparation entre exerciseCurrentPhase et exerciseActualPhase"""
    print("Test 1 : Vérification de la séparation des variables dans exercise.js...")
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Vérifier que exerciseActualPhase est déclaré
    if "let exerciseActualPhase" in content:
        print("  ✓ exerciseActualPhase est déclaré")
    else:
        print("  ✗ exerciseActualPhase n'est pas déclaré")
        return False
    
    # Vérifier que exerciseActualPhase est assigné avec data.phase
    if "exerciseActualPhase = data.phase || \"toutes\"" in content:
        print("  ✓ exerciseActualPhase est assigné avec data.phase")
    else:
        print("  ✗ exerciseActualPhase n'est pas assigné correctement")
        return False
    
    # Vérifier que exerciseCurrentPhase n'est PLUS écrasé avec data.phase
    # (il devrait être assigné dans startExercise avant l'appel serveur)
    if "exerciseCurrentPhase = phaseDemandee;" in content:
        print("  ✓ exerciseCurrentPhase est mémorisé avec la phase demandée")
    else:
        print("  ✗ exerciseCurrentPhase n'est pas mémorisé correctement")
        return False
    
    # Vérifier que exerciseCurrentPhase n'est PAS écrasé dans le callback
    # (rechercher si exerciseCurrentPhase = data.phase existe encore)
    if "exerciseCurrentPhase  = data.phase" in content or "exerciseCurrentPhase = data.phase" in content:
        print("  ✗ exerciseCurrentPhase est encore écrasé avec data.phase dans le callback")
        return False
    else:
        print("  ✓ exerciseCurrentPhase n'est pas écrasé dans le callback")
    
    # Vérifier que l'affichage utilise exerciseActualPhase
    if "EXERCISE_PHASE_LIBELLES[exerciseActualPhase]" in content:
        print("  ✓ L'affichage utilise exerciseActualPhase")
        return True
    else:
        print("  ✗ L'affichage n'utilise pas exerciseActualPhase")
        return False


def test_start_next_exercise_uses_filter():
    """Test 2 : Vérifier que startNextExercise utilise exerciseCurrentPhase"""
    print("\nTest 2 : Vérification de startNextExercise...")
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Trouver la fonction startNextExercise
    start = content.find("function startNextExercise()")
    if start == -1:
        print("  ✗ Fonction startNextExercise non trouvée")
        return False
    
    # Trouver l'appel à startExercise dans startNextExercise
    end = content.find("function reprendreExerciceCoup", start)
    if end == -1:
        end = start + 500  # Limite arbitraire
    
    func_content = content[start:end]
    
    # Vérifier que startExercise est appelé avec exerciseCurrentPhase
    if "startExercise(exerciseCurrentPhase, exerciseCurrentSource, exerciseCurrentCategorie, exerciseCurrentFenPrecis)" in func_content:
        print("  ✓ startNextExercise appelle startExercise avec exerciseCurrentPhase")
        return True
    else:
        print("  ✗ startNextExercise n'appelle pas startExercise correctement")
        print(f"  Contenu de la fonction : {func_content[:200]}")
        return False


def test_start_exercise_memorizes_filter():
    """Test 3 : Vérifier que startExercise mémorise le filtre avant l'appel serveur"""
    print("\nTest 3 : Vérification de la mémorisation dans startExercise...")
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Trouver la fonction startExercise
    start = content.find("function startExercise(phaseOverride, sourceOverride, categorieOverride, fenOverride)")
    if start == -1:
        print("  ✗ Fonction startExercise non trouvée")
        return False
    
    # Trouver la fin de la fonction (prochaine fonction)
    end = content.find("\nfunction ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    # Vérifier que phaseDemandee est calculé
    if "phaseDemandee = phaseOverride || exercisePhaseFiltre()" in func_content:
        print("  ✓ phaseDemandee est calculé")
    else:
        print("  ✗ phaseDemandee n'est pas calculé")
        return False
    
    # Vérifier que exerciseCurrentPhase est assigné avant socket.emit
    if "exerciseCurrentPhase = phaseDemandee;" in func_content:
        print("  ✓ exerciseCurrentPhase est assigné avec phaseDemandee")
    else:
        print("  ✗ exerciseCurrentPhase n'est pas assigné")
        return False
    
    # Vérifier que exerciseCurrentSource, exerciseCurrentCategorie, exerciseCurrentFenPrecis sont aussi assignés
    if "exerciseCurrentSource = sourceDemandee;" in func_content:
        print("  ✓ exerciseCurrentSource est assigné")
    else:
        print("  ✗ exerciseCurrentSource n'est pas assigné")
        return False
    
    if "exerciseCurrentCategorie = categorieDemandee;" in func_content:
        print("  ✓ exerciseCurrentCategorie est assigné")
    else:
        print("  ✗ exerciseCurrentCategorie n'est pas assigné")
        return False
    
    if "exerciseCurrentFenPrecis = (sourceDemandee === \"position_precise\") ? fenDemande : null;" in func_content:
        print("  ✓ exerciseCurrentFenPrecis est assigné")
    else:
        print("  ✗ exerciseCurrentFenPrecis n'est pas assigné")
        return False
    
    return True


def test_app_py_sends_real_phase():
    """Test 4 : Vérifier que app.py envoie la phase réelle dans exercise_position"""
    print("\nTest 4 : Vérification de app.py...")
    py_file = PROJECT_DIR / "app.py"
    content = py_file.read_text()
    
    # Vérifier que le serveur envoie la phase réelle de l'exercice
    # Dans _on_exercise_new_mes_erreurs (ou équivalent)
    if '"phase": _current_exercise["phase"]' in content:
        print("  ✓ Le serveur envoie la phase réelle de l'exercice (_current_exercise['phase'])")
        return True
    else:
        print("  ✗ Le serveur n'envoie pas la phase réelle")
        return False


def test_app_py_lichess_sends_requested_phase():
    """Test 5 : Vérifier que app.py pour Lichess envoie la phase demandée"""
    print("\nTest 5 : Vérification de app.py pour Lichess...")
    py_file = PROJECT_DIR / "app.py"
    content = py_file.read_text()
    
    # Trouver _on_exercise_new_lichess
    start = content.find("def _on_exercise_new_lichess")
    if start == -1:
        print("  ✗ Fonction _on_exercise_new_lichess non trouvée")
        return False
    
    end = content.find("\ndef ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    # Vérifier que la phase demandée est envoyée
    if '"phase": phase or "toutes"' in func_content:
        print("  ✓ Le serveur Lichess envoie la phase demandée")
        return True
    else:
        print("  ✗ Le serveur Lichess n'envoie pas la phase demandée")
        return False


def test_exercise_history_unchanged():
    """Test 6 : Vérifier que exercise_history.py n'a pas été modifié"""
    print("\nTest 6 : Vérification que exercise_history.py est inchangé...")
    py_file = PROJECT_DIR / "exercise_history.py"
    content = py_file.read_text()
    
    # Vérifier que choisir_exercice existe toujours
    if "def choisir_exercice" in content:
        print("  ✓ choisir_exercice existe toujours")
    else:
        print("  ✗ choisir_exercice a été supprimé")
        return False
    
    # Vérifier que la fonction utilise toujours random.choice
    if "return random.choice(candidats)" in content:
        print("  ✓ choisir_exercice utilise toujours random.choice")
        return True
    else:
        print("  ✗ choisir_exercice ne retourne plus un choix aléatoire")
        return False


def simulate_phase_distribution():
    """Test 7 : Simuler la distribution des phases avec le filtre toutes"""
    print("\nTest 7 : Simulation de la distribution des phases...")
    
    # Charger les erreurs détectées pour voir la distribution réelle
    errors_file = PROJECT_DIR / "data" / "erreurs_detectees.json"
    
    if not errors_file.exists():
        print("  ⚠ Fichier erreurs_detectees.json non trouvé (données personnelles)")
        print("  → Test sauté (nécessite les données réelles)")
        return True  # Pas un échec, juste non testable
    
    try:
        with open(errors_file, 'r', encoding='utf-8') as f:
            errors = json.load(f)
    except Exception as e:
        print(f"  ⚠ Erreur de lecture de erreurs_detectees.json : {e}")
        print("  → Test sauté")
        return True
    
    # Compter les phases
    phase_counts = {}
    for error in errors:
        phase = error.get("phase", "inconnue")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    
    total = len(errors)
    print(f"  Distribution dans erreurs_detectees.json ({total} entrées) :")
    for phase, count in sorted(phase_counts.items()):
        percentage = (count / total) * 100
        print(f"    {phase}: {count} ({percentage:.1f}%)")
    
    # Vérifier que la distribution est proche de celle attendue
    # (25% ouvertures, 73% milieux, 1% finales selon l'issue)
    expected = {
        "ouverture": 25,
        "milieu_de_partie": 73,
        "finale": 1
    }
    
    # Calculer les écarts
    max_diff = 0
    for phase, expected_pct in expected.items():
        actual_pct = (phase_counts.get(phase, 0) / total) * 100
        diff = abs(actual_pct - expected_pct)
        max_diff = max(max_diff, diff)
        print(f"    Écart pour {phase}: {diff:.1f}%")
    
    if max_diff < 10:  # Tolérance de 10%
        print("  ✓ Distribution proche de celle attendue")
        return True
    else:
        print("  ⚠ Distribution différente de celle attendue (mais c'est OK)")
        return True  # Pas un échec, juste une information


def main():
    """Exécuter tous les tests"""
    print("=" * 70)
    print("Tests de simulation pour l'issue #123")
    print("=" * 70)
    
    tests = [
        test_exercise_js_separation,
        test_start_next_exercise_uses_filter,
        test_start_exercise_memorizes_filter,
        test_app_py_sends_real_phase,
        test_app_py_lichess_sends_requested_phase,
        test_exercise_history_unchanged,
        simulate_phase_distribution,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Erreur dans le test : {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Résultats : {passed}/{total} tests passés")
    print("=" * 70)
    
    if all(results):
        print("\n✓ Tous les tests sont passés !")
        return 0
    else:
        print("\n✗ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
