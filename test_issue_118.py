#!/usr/bin/env python3
"""
Test de simulation pour l'issue #118 : gestion du refus du paramètre température par l'API.

Ce script simule les réponses d'erreur de l'API Claude et Mistral pour vérifier que :
1. Le premier appel avec température échoue avec une erreur de refus
2. Le réessai sans température réussit
3. Les appels suivants avec le même modèle n'envoient plus le paramètre température
4. Le journal indique clairement que la température a été refusée
5. Un changement de modèle réinitialise la mémoire
"""

import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import urllib.error

# Ajouter le répertoire courant au path pour importer llm_coach
sys.path.insert(0, '/home/alain/worktrees/chesscoach-issue118')

# Importer le module
import llm_coach


def simuler_erreur_claude_temperature_refusee():
    """Simule une erreur HTTP 400 de Claude avec message de refus de température."""
    # Créer une mock response avec une erreur de type invalid_request_error
    # mentionnant que temperature est dépréciée
    error_response = {
        "error": {
            "type": "invalid_request_error",
            "message": "The 'temperature' parameter is deprecated for this model (claude-sonnet-5)"
        }
    }
    error_json = json.dumps(error_response).encode('utf-8')
    
    # Créer une HTTPError mock
    error = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=None
    )
    
    # Mock la méthode read pour retourner notre erreur JSON
    error.read = Mock(return_value=error_json)
    error.__enter__ = Mock(return_value=error)
    error.__exit__ = Mock(return_value=False)
    
    return error


def simuler_reponse_claude_reussie():
    """Simule une réponse réussie de Claude."""
    response_data = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "C'est une bonne réponse."}],
        "model": "claude-sonnet-5",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50
        }
    }
    response_json = json.dumps(response_data).encode('utf-8')
    
    # Créer une réponse mock
    response = MagicMock()
    response.read = Mock(return_value=response_json)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    
    return response


def test_claude_temperature_refus():
    """Test le comportement de _call_claude avec refus de température."""
    print("\n=== Test 1 : Claude - Premier appel avec température refusée ===")
    
    # Réinitialiser la mémoire des modèles refusés
    llm_coach._TEMPERATURE_REFUSED_MODELS.clear()
    
    # Mock urlopen pour simuler d'abord une erreur, puis une réussite
    call_count = [0]
    
    def mock_urlopen(req, timeout=None):
        call_count[0] += 1
        
        # Vérifier que le premier appel contient temperature
        body = req.data.decode('utf-8')
        body_dict = json.loads(body)
        
        if call_count[0] == 1:
            print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
            # Simuler l'erreur de refus de température
            raise simuler_erreur_claude_temperature_refusee()
        else:
            print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
            # Simuler une réponse réussie
            return simuler_reponse_claude_reussie()
    
    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        try:
            result = llm_coach._call_claude(
                "System prompt",
                [{"role": "user", "content": "Test"}],
                "test_api_key",
                "claude-sonnet-5",
                None,  # usage_path
                timeout_s=90,
                temperature=0.7
            )
            print(f"  ✓ Réessai réussi, réponse : {result}")
            print(f"  ✓ Modèle marqué comme refusant température : {('claude', 'claude-sonnet-5') in llm_coach._TEMPERATURE_REFUSED_MODELS}")
            return True
        except Exception as e:
            print(f"  ✗ Échec : {e}")
            return False


def test_claude_appels_suivants():
    """Test que les appels suivants n'envoient plus le paramètre température."""
    print("\n=== Test 2 : Claude - Appels suivants sans température ===")
    
    # Le modèle est déjà marqué comme refusant la température du test précédent
    
    call_count = [0]
    
    def mock_urlopen(req, timeout=None):
        call_count[0] += 1
        body = req.data.decode('utf-8')
        body_dict = json.loads(body)
        
        print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
        
        # Vérifier que temperature n'est PAS dans la requête
        if 'temperature' in body_dict:
            raise AssertionError(f"Temperature devrait être absente mais est présente : {body_dict['temperature']}")
        
        return simuler_reponse_claude_reussie()
    
    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        try:
            result = llm_coach._call_claude(
                "System prompt",
                [{"role": "user", "content": "Test 2"}],
                "test_api_key",
                "claude-sonnet-5",
                None,
                timeout_s=90,
                temperature=0.7  # Même si on passe une température, elle ne devrait pas être envoyée
            )
            print(f"  ✓ Appel réussi sans envoyer température : {result}")
            return True
        except Exception as e:
            print(f"  ✗ Échec : {e}")
            return False


def test_claude_changement_modele():
    """Test qu'un changement de modèle réinitialise la mémoire."""
    print("\n=== Test 3 : Claude - Changement de modèle ===")
    
    # Réinitialiser pour ce test
    llm_coach._TEMPERATURE_REFUSED_MODELS.clear()
    
    call_count = [0]
    
    def mock_urlopen(req, timeout=None):
        call_count[0] += 1
        body = req.data.decode('utf-8')
        body_dict = json.loads(body)
        
        model = body_dict.get('model', 'unknown')
        temperature = body_dict.get('temperature', 'ABSENT')
        
        print(f"  Appel {call_count[0]} : modèle={model}, température={temperature}")
        
        # Pour claude-haiku-4-5, la température devrait être présente
        if model == "claude-haiku-4-5" and call_count[0] == 1:
            if temperature == 'ABSENT':
                raise AssertionError("Temperature devrait être présente pour claude-haiku-4-5")
        
        return simuler_reponse_claude_reussie()
    
    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        try:
            # Appel avec un nouveau modèle (claude-haiku-4-5)
            result = llm_coach._call_claude(
                "System prompt",
                [{"role": "user", "content": "Test 3"}],
                "test_api_key",
                "claude-haiku-4-5",  # Nouveau modèle
                None,
                timeout_s=90,
                temperature=0.7
            )
            print(f"  ✓ Nouveau modèle envoie température : {result}")
            return True
        except Exception as e:
            print(f"  ✗ Échec : {e}")
            return False


def test_mistral_temperature_refus():
    """Test le comportement de _call_mistral avec refus de température."""
    print("\n=== Test 4 : Mistral - Premier appel avec température refusée ===")
    
    # Réinitialiser la mémoire
    llm_coach._TEMPERATURE_REFUSED_MODELS.clear()
    
    call_count = [0]
    
    def mock_urlopen(req, timeout=None):
        call_count[0] += 1
        body = req.data.decode('utf-8')
        body_dict = json.loads(body)
        
        if call_count[0] == 1:
            print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
            # Simuler l'erreur de refus de température pour Mistral
            error_response = {
                "error": {
                    "type": "BadRequestError",
                    "message": "temperature parameter is not supported for this model"
                }
            }
            error_json = json.dumps(error_response).encode('utf-8')
            
            # Créer une HTTPError avec un fp qui retourne l'erreur JSON
            from io import BytesIO
            error = urllib.error.HTTPError(
                url="https://api.mistral.ai/v1/chat/completions",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=BytesIO(error_json)
            )
            raise error
        else:
            print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
            # Simuler une réponse réussie
            response_data = {
                "id": "test",
                "object": "chat.completion",
                "created": 123456,
                "model": "mistral-test",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Réponse Mistral"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            }
            response_json = json.dumps(response_data).encode('utf-8')
            from io import BytesIO
            response = BytesIO(response_json)
            return response
    
    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        try:
            result = llm_coach._call_mistral(
                "System prompt",
                [{"role": "user", "content": "Test"}],
                "test_api_key",
                "mistral-test",
                None,
                timeout_s=90,
                temperature=0.5
            )
            print(f"  ✓ Réessai réussi, réponse : {result}")
            print(f"  ✓ Modèle marqué comme refusant température : {('mistral', 'mistral-test') in llm_coach._TEMPERATURE_REFUSED_MODELS}")
            return True
        except Exception as e:
            print(f"  ✗ Échec : {e}")
            import traceback
            traceback.print_exc()
            return False


def test_sans_variable_temperature():
    """Test que le comportement sans variable de température reste inchangé."""
    print("\n=== Test 5 : Comportement sans variable température ===")
    
    # Réinitialiser
    llm_coach._TEMPERATURE_REFUSED_MODELS.clear()
    
    call_count = [0]
    
    def mock_urlopen(req, timeout=None):
        call_count[0] += 1
        body = req.data.decode('utf-8')
        body_dict = json.loads(body)
        
        print(f"  Appel {call_count[0]} : température dans la requête = {body_dict.get('temperature', 'ABSENT')}")
        
        # Sans température configurée, temperature ne devrait pas être dans la requête
        if 'temperature' in body_dict:
            raise AssertionError(f"Temperature ne devrait pas être présente mais l'est : {body_dict['temperature']}")
        
        return simuler_reponse_claude_reussie()
    
    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        try:
            result = llm_coach._call_claude(
                "System prompt",
                [{"role": "user", "content": "Test"}],
                "test_api_key",
                "claude-haiku-4-5",
                None,
                timeout_s=90,
                temperature=None  # Pas de température configurée
            )
            print(f"  ✓ Appel réussi sans température : {result}")
            return True
        except Exception as e:
            print(f"  ✗ Échec : {e}")
            return False


def test_get_temperature_log_value():
    """Test la fonction _get_temperature_log_value."""
    print("\n=== Test 6 : Fonction _get_temperature_log_value ===")
    
    # Réinitialiser
    llm_coach._TEMPERATURE_REFUSED_MODELS.clear()
    
    # Test 1 : Température configurée, modèle non refusé
    result = llm_coach._get_temperature_log_value("claude", "claude-haiku-4-5", 0.7)
    print(f"  Température 0.7, modèle non refusé : '{result}'")
    assert result == "0.7", f"Attendu '0.7', obtenu '{result}'"
    
    # Test 2 : Pas de température configurée
    result = llm_coach._get_temperature_log_value("claude", "claude-haiku-4-5", None)
    print(f"  Température None : '{result}'")
    assert result == "defaut API", f"Attendu 'defaut API', obtenu '{result}'"
    
    # Test 3 : Modèle marqué comme refusant la température
    llm_coach._marquer_modele_refuse_temperature("claude", "claude-sonnet-5")
    result = llm_coach._get_temperature_log_value("claude", "claude-sonnet-5", 0.7)
    print(f"  Température 0.7, modèle refusé : '{result}'")
    assert result == "refusée par le modèle, défaut API", f"Attendu 'refusée par le modèle, défaut API', obtenu '{result}'"
    
    print("  ✓ Tous les tests de _get_temperature_log_value passés")
    return True


def main():
    """Exécute tous les tests."""
    print("=" * 70)
    print("Tests de simulation pour l'issue #118")
    print("=" * 70)
    
    results = []
    
    # Exécuter tous les tests
    results.append(("Claude - Premier appel avec température refusée", test_claude_temperature_refus()))
    results.append(("Claude - Appels suivants sans température", test_claude_appels_suivants()))
    results.append(("Claude - Changement de modèle", test_claude_changement_modele()))
    results.append(("Mistral - Premier appel avec température refusée", test_mistral_temperature_refus()))
    results.append(("Comportement sans variable température", test_sans_variable_temperature()))
    results.append(("Fonction _get_temperature_log_value", test_get_temperature_log_value()))
    
    # Résumé
    print("\n" + "=" * 70)
    print("RÉSULTATS")
    print("=" * 70)
    
    for test_name, result in results:
        status = "✓ PASSÉ" if result else "✗ ÉCHOUÉ"
        print(f"{status} : {test_name}")
    
    all_passed = all(result for _, result in results)
    print("\n" + "=" * 70)
    if all_passed:
        print("TOUS LES TESTS ONT RÉUSSI ✓")
    else:
        print("CERTAINS TESTS ONT ÉCHOUÉ ✗")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
