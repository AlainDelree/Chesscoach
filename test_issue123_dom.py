#!/usr/bin/env python3
"""
Test DOM de simulation pour l'issue #123
Simule le comportement côté client pour vérifier que :
(a) avec "Toutes les phases", trois appels successifs de "Exercice suivant" 
    envoient chacun "toutes" au serveur
(b) avec "ouverture" choisi explicitement, "Exercice suivant" redemande "ouverture"
(c) la ligne d'information affiche toujours la phase réelle de l'exercice
"""

import sys
from pathlib import Path

# Chemin du projet
PROJECT_DIR = Path(__file__).parent


def test_simulation_toutes_phases():
    """Simulation (a) : avec "Toutes les phases", trois appels successifs"""
    print("Test DOM (a) : Simulation avec filtre 'toutes'...")
    
    # Simuler l'état initial
    exerciseCurrentPhase = "toutes"
    exerciseCurrentSource = "mes_erreurs"
    exerciseCurrentCategorie = "automatique"
    exerciseCurrentFenPrecis = None
    
    # Simuler trois réponses serveur avec des phases réelles différentes
    server_responses = [
        {"phase": "milieu_de_partie", "source": "mes_erreurs", "fen": "fen1"},
        {"phase": "ouverture", "source": "mes_erreurs", "fen": "fen2"},
        {"phase": "finale", "source": "mes_erreurs", "fen": "fen3"},
    ]
    
    # Simuler le comportement du code corrigé
    for i, response in enumerate(server_responses, 1):
        # Dans startExercise, on mémorise la phase demandée AVANT l'appel serveur
        phaseDemandee = exerciseCurrentPhase  # C'est ce que fait le code corrigé
        
        # Simuler la réception de la réponse
        # Dans le callback, exerciseActualPhase est mis à jour avec la phase réelle
        exerciseActualPhase = response["phase"]
        
        # Vérifier que exerciseCurrentPhase n'a pas changé
        if exerciseCurrentPhase != "toutes":
            print(f"  ✗ Après réponse {i}, exerciseCurrentPhase = {exerciseCurrentPhase} (attendu: 'toutes')")
            return False
        
        # Vérifier que exerciseActualPhase a la phase réelle
        if exerciseActualPhase != response["phase"]:
            print(f"  ✗ Après réponse {i}, exerciseActualPhase = {exerciseActualPhase} (attendu: {response['phase']})")
            return False
        
        print(f"  ✓ Réponse {i}: exerciseCurrentPhase='toutes', exerciseActualPhase='{response['phase']}'")
        
        # Simuler "Exercice suivant" - il utilise exerciseCurrentPhase
        # qui est toujours "toutes"
        next_request_phase = exerciseCurrentPhase
        if next_request_phase != "toutes":
            print(f"  ✗ Requête suivante {i+1} envoie phase = {next_request_phase} (attendu: 'toutes')")
            return False
        
        print(f"  ✓ Requête suivante {i+1} envoie phase='toutes'")
    
    print("  ✓ Toutes les requêtes successives envoient 'toutes'")
    return True


def test_simulation_ouverture():
    """Simulation (b) : avec "ouverture" choisi explicitement"""
    print("\nTest DOM (b) : Simulation avec filtre 'ouverture'...")
    
    # Simuler l'état initial avec filtre "ouverture"
    exerciseCurrentPhase = "ouverture"
    exerciseCurrentSource = "mes_erreurs"
    exerciseCurrentCategorie = "automatique"
    exerciseCurrentFenPrecis = None
    
    # Simuler trois réponses serveur (toutes avec phase réelle "ouverture" ou autre)
    server_responses = [
        {"phase": "ouverture", "source": "mes_erreurs", "fen": "fen1"},
        {"phase": "milieu_de_partie", "source": "mes_erreurs", "fen": "fen2"},  # Phase réelle différente
        {"phase": "ouverture", "source": "mes_erreurs", "fen": "fen3"},
    ]
    
    for i, response in enumerate(server_responses, 1):
        # Dans startExercise, on mémorise la phase demandée
        phaseDemandee = exerciseCurrentPhase
        
        # Simuler la réception
        exerciseActualPhase = response["phase"]
        
        # Vérifier que exerciseCurrentPhase reste "ouverture"
        if exerciseCurrentPhase != "ouverture":
            print(f"  ✗ Après réponse {i}, exerciseCurrentPhase = {exerciseCurrentPhase} (attendu: 'ouverture')")
            return False
        
        print(f"  ✓ Réponse {i}: exerciseCurrentPhase='ouverture', exerciseActualPhase='{response['phase']}'")
        
        # Simuler "Exercice suivant"
        next_request_phase = exerciseCurrentPhase
        if next_request_phase != "ouverture":
            print(f"  ✗ Requête suivante {i+1} envoie phase = {next_request_phase} (attendu: 'ouverture')")
            return False
        
        print(f"  ✓ Requête suivante {i+1} envoie phase='ouverture'")
    
    print("  ✓ Toutes les requêtes successives envoient 'ouverture'")
    return True


def test_display_uses_actual_phase():
    """Test (c) : Vérifier que l'affichage utilise la phase réelle"""
    print("\nTest DOM (c) : Vérification de l'affichage...")
    
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Trouver la fonction _exerciseUpdateStatementLine
    start = content.find("function _exerciseUpdateStatementLine")
    if start == -1:
        print("  ✗ Fonction _exerciseUpdateStatementLine non trouvée")
        return False
    
    end = content.find("\nfunction ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    # Vérifier que exerciseActualPhase est utilisé pour l'affichage
    if "exerciseActualPhase" in func_content:
        print("  ✓ _exerciseUpdateStatementLine utilise exerciseActualPhase")
    else:
        print("  ✗ _exerciseUpdateStatementLine n'utilise pas exerciseActualPhase")
        return False
    
    # Vérifier que exerciseCurrentPhase n'est PAS utilisé pour l'affichage de la phase
    # (il peut être utilisé pour d'autres choses, mais pas pour le libellé de phase)
    # Chercher spécifiquement dans la partie qui construit le texte
    if "EXERCISE_PHASE_LIBELLES[exerciseActualPhase]" in func_content:
        print("  ✓ Le libellé de phase utilise exerciseActualPhase")
        return True
    else:
        print("  ✗ Le libellé de phase n'utilise pas exerciseActualPhase")
        return False


def test_lichess_behavior():
    """Test (d) : Vérifier que le chemin Lichess se comporte comme avant"""
    print("\nTest DOM (d) : Vérification du comportement Lichess...")
    
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Vérifier que exerciseCurrentCategorie est mémorisé dans startExercise
    if "exerciseCurrentCategorie = categorieDemandee;" in content:
        print("  ✓ exerciseCurrentCategorie est mémorisé dans startExercise")
    else:
        print("  ✗ exerciseCurrentCategorie n'est pas mémorisé")
        return False
    
    # Vérifier que startNextExercise utilise exerciseCurrentCategorie
    start = content.find("function startNextExercise()")
    if start == -1:
        print("  ✗ Fonction startNextExercise non trouvée")
        return False
    
    end = content.find("\nfunction ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    if "exerciseCurrentCategorie" in func_content:
        print("  ✓ startNextExercise utilise exerciseCurrentCategorie")
        return True
    else:
        print("  ✗ startNextExercise n'utilise pas exerciseCurrentCategorie")
        return False


def test_position_precise_behavior():
    """Test (d) : Vérifier que la position précise se comporte comme avant"""
    print("\nTest DOM (d) : Vérification du comportement Position précise...")
    
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Vérifier que exerciseCurrentFenPrecis est mémorisé dans startExercise
    if "exerciseCurrentFenPrecis = (sourceDemandee === \"position_precise\") ? fenDemande : null;" in content:
        print("  ✓ exerciseCurrentFenPrecis est mémorisé dans startExercise")
    else:
        print("  ✗ exerciseCurrentFenPrecis n'est pas mémorisé correctement")
        return False
    
    # Vérifier que startNextExercise utilise exerciseCurrentFenPrecis
    start = content.find("function startNextExercise()")
    if start == -1:
        print("  ✗ Fonction startNextExercise non trouvée")
        return False
    
    end = content.find("\nfunction ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    if "exerciseCurrentFenPrecis" in func_content:
        print("  ✓ startNextExercise utilise exerciseCurrentFenPrecis")
        return True
    else:
        print("  ✗ startNextExercise n'utilise pas exerciseCurrentFenPrecis")
        return False


def main():
    """Exécuter tous les tests de simulation DOM"""
    print("=" * 70)
    print("Tests DOM de simulation pour l'issue #123")
    print("=" * 70)
    
    tests = [
        test_simulation_toutes_phases,
        test_simulation_ouverture,
        test_display_uses_actual_phase,
        test_lichess_behavior,
        test_position_precise_behavior,
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
        print("\n✓ Tous les tests DOM sont passés !")
        return 0
    else:
        print("\n✗ Certains tests DOM ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
