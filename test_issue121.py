#!/usr/bin/env python3
"""
Test de simulation pour l'issue #121
Vérifie que les corrections apportées résolvent les 4 défauts signalés.
"""

import json
import sys
from pathlib import Path

# Chemin du projet
PROJECT_DIR = Path(__file__).parent


def test_css_rating_button():
    """Test 1 : Vérifier que le bouton 0 sélectionné est lisible"""
    print("Test 1 : Vérification CSS du bouton 0 sélectionné...")
    css_file = PROJECT_DIR / "static" / "board.css"
    content = css_file.read_text()
    
    # Vérifier que la règle contient color: white
    if ".rating-btn.rating-0.selected" in content:
        # Trouver le bloc
        start = content.find(".rating-btn.rating-0.selected")
        end = content.find("}", start)
        block = content[start:end+1]
        
        if "color: white;" in block or "color:white;" in block:
            print("  ✓ Le bouton 0 sélectionné a color: white")
            return True
        else:
            print("  ✗ Le bouton 0 sélectionné n'a pas color: white")
            print(f"  Bloc trouvé : {block}")
            return False
    else:
        print("  ✗ Règle .rating-btn.rating-0.selected non trouvée")
        return False


def test_board_js_signal_button():
    """Test 2 : Vérifier que le bouton Signaler utilise socket.emit"""
    print("\nTest 2 : Vérification du bouton Signaler dans _coachRenderBubbleWithAgent...")
    js_file = PROJECT_DIR / "static" / "board.js"
    content = js_file.read_text()
    
    # Vérifier que socket.emit est utilisé
    if "socket.emit(\"signalement_envoyer\"" in content:
        print("  ✓ socket.emit('signalement_envoyer') est présent")
        
        # Vérifier que _coachSignalClick n'est plus appelé
        if "_coachSignalClick(signalData)" in content:
            print("  ✗ _coachSignalClick est encore appelé")
            return False
        else:
            print("  ✓ _coachSignalClick n'est plus appelé")
        
        # Vérifier que le bouton est marqué comme "Signalé"
        if 'signalBtn.textContent = "Signalé"' in content:
            print("  ✓ Le bouton est marqué comme 'Signalé' après clic")
            return True
        else:
            print("  ✗ Le bouton n'est pas marqué comme 'Signalé'")
            return False
    else:
        print("  ✗ socket.emit('signalement_envoyer') non trouvé")
        return False


def test_mistral_bubble_agent():
    """Test 3 : Vérifier que _coachRenderMistralBubbleWithAgent accepte l'agent"""
    print("\nTest 3 : Vérification de _coachRenderMistralBubbleWithAgent...")
    js_file = PROJECT_DIR / "static" / "board.js"
    content = js_file.read_text()
    
    # Vérifier la signature de la fonction
    if "function _coachRenderMistralBubbleWithAgent(text, model, exerciseId, logId, fen, coupPropose, factCheckerAlertes, agent = \"mistral\")" in content:
        print("  ✓ La fonction accepte le paramètre agent")
    else:
        # Vérifier une variante
        if "function _coachRenderMistralBubbleWithAgent" in content and "agent" in content:
            print("  ✓ La fonction semble accepter agent")
        else:
            print("  ✗ La fonction ne semble pas accepter agent")
            return False
    
    # Vérifier que l'agent est utilisé dans l'en-tête
    if 'agentSpan.textContent = agent === "claude" ? "Claude" : "Mistral"' in content:
        print("  ✓ L'agent est utilisé dynamiquement dans l'en-tête")
        return True
    else:
        print("  ✗ L'agent n'est pas utilisé dynamiquement")
        return False


def test_mistral_signal_button():
    """Test 4 : Vérifier que le bouton Signaler est ajouté sous Mistral"""
    print("\nTest 4 : Vérification du bouton Signaler sous Mistral...")
    js_file = PROJECT_DIR / "static" / "board.js"
    content = js_file.read_text()
    
    # Trouver la fonction _coachRenderMistralBubbleWithAgent
    start = content.find("function _coachRenderMistralBubbleWithAgent")
    if start == -1:
        print("  ✗ Fonction _coachRenderMistralBubbleWithAgent non trouvée")
        return False
    
    # Trouver la fin de la fonction
    end = content.find("function _coachRenderMistralErrorWithAgent", start)
    if end == -1:
        end = content.find("// Issue #113 : Afficher une erreur", start)
    
    func_content = content[start:end]
    
    # Vérifier que le bouton Signaler est créé
    if "coach-signal-btn" in func_content and "Signaler" in func_content:
        print("  ✓ Bouton Signaler est créé dans _coachRenderMistralBubbleWithAgent")
        
        # Vérifier que socket.emit est appelé
        if "socket.emit(\"signalement_envoyer\"" in func_content:
            print("  ✓ socket.emit est appelé pour le signalement")
            return True
        else:
            print("  ✗ socket.emit n'est pas appelé")
            return False
    else:
        print("  ✗ Bouton Signaler non trouvé dans _coachRenderMistralBubbleWithAgent")
        return False


def test_exercise_js_parameters():
    """Test 5 : Vérifier l'ordre des paramètres dans exercise.js"""
    print("\nTest 5 : Vérification des paramètres dans exercise.js...")
    js_file = PROJECT_DIR / "static" / "exercise.js"
    content = js_file.read_text()
    
    # Vérifier que l'appel à _coachRenderBubbleWithAgent a le bon ordre
    if "_coachRenderBubbleWithAgent(\"assistant\", text, true, data && data.fiabilite, data && {" in content:
        print("  ✓ L'appel a data.fiabilite comme 5ème paramètre")
        
        # Vérifier que agent est passé comme 7ème paramètre
        if ", agent, model, exerciseId)" in content:
            print("  ✓ agent est passé comme 7ème paramètre")
            return True
        else:
            print("  ✗ agent n'est pas passé correctement")
            return False
    else:
        print("  ✗ L'appel n'a pas le bon ordre de paramètres")
        return False


def test_app_py_agent_field():
    """Test 6 : Vérifier que le serveur envoie le champ agent pour Mistral"""
    print("\nTest 6 : Vérification du champ agent dans app.py...")
    py_file = PROJECT_DIR / "app.py"
    content = py_file.read_text()
    
    # Vérifier dans exercise_mistral_comment
    if '"agent": "mistral"' in content:
        print("  ✓ Le serveur envoie agent: 'mistral' dans exercise_mistral_comment")
        return True
    else:
        print("  ✗ Le serveur n'envoie pas agent: 'mistral'")
        return False


def main():
    """Exécuter tous les tests"""
    print("=" * 70)
    print("Tests de simulation pour l'issue #121")
    print("=" * 70)
    
    tests = [
        test_css_rating_button,
        test_board_js_signal_button,
        test_mistral_bubble_agent,
        test_mistral_signal_button,
        test_exercise_js_parameters,
        test_app_py_agent_field,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Erreur dans le test : {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print(f"Résultats : {sum(results)}/{len(results)} tests passés")
    print("=" * 70)
    
    if all(results):
        print("\n✓ Tous les tests sont passés !")
        return 0
    else:
        print("\n✗ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    sys.exit(main())
