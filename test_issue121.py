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


def _extract_block(content, start_marker, end_markers):
    """Isole le code d'une fonction entre `start_marker` et le premier des
    `end_markers` rencontré après lui (issue #155 : extraction utilitaire
    partagée par plusieurs tests pour cibler précisément une fonction)."""
    start = content.find(start_marker)
    if start == -1:
        return None
    end = -1
    for marker in end_markers:
        pos = content.find(marker, start + len(start_marker))
        if pos != -1 and (end == -1 or pos < end):
            end = pos
    if end == -1:
        return content[start:]
    return content[start:end]


def test_board_js_signal_button():
    """Test 2 : Vérifier que le bouton Signaler utilise socket.emit

    Issue #122 a remplacé le bouton "Signaler" codé en direct dans
    _coachRenderBubbleWithAgent par une délégation à la fonction partagée
    _coachBuildSignalerUI (classe "coach-signaler-btn", variable locale
    `btn`, champ de justification). Le test vérifie donc la délégation côté
    bulle Claude et le comportement réel (socket.emit + passage à "Signalé")
    côté fonction partagée, au lieu des noms littéraux `signalBtn`/
    "coach-signal-btn" devenus obsolètes.
    """
    print("\nTest 2 : Vérification du bouton Signaler dans _coachRenderBubbleWithAgent...")
    js_file = PROJECT_DIR / "static" / "board.js"
    content = js_file.read_text()

    signaler_ui = _extract_block(
        content, "function _coachBuildSignalerUI", ["function showBoardToast"]
    )
    if signaler_ui is None:
        print("  ✗ _coachBuildSignalerUI non trouvée")
        return False

    # Vérifier que socket.emit est utilisé pour envoyer le signalement
    if "socket.emit(\"signalement_envoyer\"" in signaler_ui:
        print("  ✓ socket.emit('signalement_envoyer') est présent")
    else:
        print("  ✗ socket.emit('signalement_envoyer') non trouvé")
        return False

    # Vérifier que _coachSignalClick n'est plus appelé (ancien gestionnaire
    # pré-issue #122, remplacé par un socket.emit direct)
    if "_coachSignalClick(signalData)" in content:
        print("  ✗ _coachSignalClick est encore appelé")
        return False
    print("  ✓ _coachSignalClick n'est plus appelé")

    # Vérifier que le bouton est marqué comme "Signalé" et désactivé après clic
    if 'btn.textContent = "Signalé"' in signaler_ui and "btn.disabled = true" in signaler_ui:
        print("  ✓ Le bouton est marqué comme 'Signalé' et désactivé après clic")
    else:
        print("  ✗ Le bouton n'est pas marqué comme 'Signalé'/désactivé")
        return False

    # Vérifier que _coachRenderBubbleWithAgent délègue bien à _coachBuildSignalerUI
    bubble_func = _extract_block(
        content,
        "function _coachRenderBubbleWithAgent",
        ["function _coachRenderMistralBubbleWithAgent"],
    )
    if bubble_func and "_coachBuildSignalerUI(bubble" in bubble_func:
        print("  ✓ _coachRenderBubbleWithAgent délègue la construction du bouton à _coachBuildSignalerUI")
        return True
    else:
        print("  ✗ _coachRenderBubbleWithAgent n'appelle plus _coachBuildSignalerUI")
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
    """Test 4 : Vérifier que le bouton Signaler est ajouté sous Mistral

    Issue #122 : le bouton n'est plus construit en direct (classe
    "coach-signal-btn") dans _coachRenderMistralBubbleWithAgent, il est
    délégué à _coachBuildSignalerUI (classe "coach-signaler-btn", champ de
    justification). Le test vérifie donc la délégation avec les bonnes
    métadonnées (fen, coup, log_id) côté bulle Mistral, et le comportement
    réel (bouton "Signaler" + socket.emit) côté fonction partagée.
    """
    print("\nTest 4 : Vérification du bouton Signaler sous Mistral...")
    js_file = PROJECT_DIR / "static" / "board.js"
    content = js_file.read_text()

    func_content = _extract_block(
        content,
        "function _coachRenderMistralBubbleWithAgent",
        ["function _coachRenderMistralErrorWithAgent", "// Issue #113 : Afficher une erreur"],
    )
    if func_content is None:
        print("  ✗ Fonction _coachRenderMistralBubbleWithAgent non trouvée")
        return False

    # Vérifier que la bulle Mistral délègue la construction du bouton Signaler
    # à _coachBuildSignalerUI, avec les métadonnées nécessaires au signalement
    if "_coachBuildSignalerUI(bubble" in func_content and "log_id: logId" in func_content:
        print("  ✓ _coachRenderMistralBubbleWithAgent délègue à _coachBuildSignalerUI avec ses métadonnées")
    else:
        print("  ✗ Bouton Signaler non délégué à _coachBuildSignalerUI dans _coachRenderMistralBubbleWithAgent")
        return False

    # Vérifier que la fonction partagée construit bien un bouton "Signaler"
    # qui envoie le signalement via socket.emit
    signaler_ui = _extract_block(
        content, "function _coachBuildSignalerUI", ["function showBoardToast"]
    )
    if signaler_ui and "Signaler" in signaler_ui and "socket.emit(\"signalement_envoyer\"" in signaler_ui:
        print("  ✓ _coachBuildSignalerUI crée le bouton 'Signaler' et appelle socket.emit")
        return True
    else:
        print("  ✗ _coachBuildSignalerUI ne crée pas le bouton 'Signaler'/n'appelle pas socket.emit")
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
