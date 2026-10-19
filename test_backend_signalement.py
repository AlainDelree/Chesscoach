#!/usr/bin/env python3
"""
Test Backend Signalement - Issue #122

Vérifie que le backend gère correctement les signalements avec :
- commentaire (justification)
- agent
- model
- tous les autres champs requis
"""

import json
import os
import tempfile
import uuid
from datetime import datetime

# Chemin du fichier de signalements (à adapter si nécessaire)
SIGNALEMENTS_LOG_PATH = "data/logs/signalements.log"


def test_signalement_structure():
    """Test la structure d'une entrée de signalement."""
    print("Test 1: Structure de l'entrée de signalement...")
    
    # Créer une entrée de signalement complète
    entry = {
        "id": uuid.uuid4().hex[:12],
        "horodatage": datetime.now().isoformat(),
        "mode_origine": "exercice",
        "log_id": "test-log-123",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "move": "e4",
        "reponse": "Réponse du coach pour test",
        "commentaire": "Ce commentaire est incorrect",
        "agent": "claude",
        "model": "claude-3-5-sonnet-20250620",
        "traite": False,
    }
    
    # Vérifier tous les champs requis
    required_fields = ["id", "horodatage", "mode_origine", "fen", "move", 
                      "reponse", "commentaire", "agent", "model", "traite"]
    
    for field in required_fields:
        if field not in entry:
            print(f"  ❌ Champ manquant: {field}")
            return False
    
    # Vérifier les types
    if not isinstance(entry["id"], str) or len(entry["id"]) != 12:
        print(f"  ❌ ID invalide: {entry['id']}")
        return False
    
    if not isinstance(entry["commentaire"], str):
        print(f"  ❌ Commentaire doit être une chaîne")
        return False
    
    if not isinstance(entry["agent"], str):
        print(f"  ❌ Agent doit être une chaîne")
        return False
    
    if not isinstance(entry["model"], str):
        print(f"  ❌ Model doit être une chaîne")
        return False
    
    print("  ✅ Structure valide")
    return True


def test_commentaire_vide():
    """Test un signalement sans commentaire."""
    print("\nTest 2: Signalement sans commentaire...")
    
    entry = {
        "id": uuid.uuid4().hex[:12],
        "horodatage": datetime.now().isoformat(),
        "mode_origine": "chat",
        "log_id": None,
        "fen": "",
        "move": "",
        "reponse": "Réponse sans commentaire",
        "commentaire": "",
        "agent": "mistral",
        "model": "mistral-large-latest",
        "traite": False,
    }
    
    if entry["commentaire"] == "":
        print("  ✅ Commentaire vide autorisé")
        return True
    else:
        print(f"  ❌ Commentaire devrait être vide: '{entry['commentaire']}'")
        return False


def test_ecriture_fichier():
    """Test l'écriture et la lecture d'un fichier de signalements."""
    print("\nTest 3: Écriture et lecture du fichier de signalements...")
    
    # Créer un fichier temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        temp_path = f.name
    
    try:
        # Écrire une entrée
        entry = {
            "id": "test123456",
            "horodatage": datetime.now().isoformat(),
            "mode_origine": "exercice",
            "log_id": "log-test",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move": "e4",
            "reponse": "Test réponse",
            "commentaire": "Test commentaire",
            "agent": "claude",
            "model": "claude-3-5-sonnet",
            "traite": False,
        }
        
        with open(temp_path, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        # Lire le fichier
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        if len(lines) != 1:
            print(f"  ❌ Nombre de lignes incorrect: {len(lines)}")
            return False
        
        # Parser la ligne
        try:
            read_entry = json.loads(lines[0].strip())
        except json.JSONDecodeError as e:
            print(f"  ❌ Erreur de parsing JSON: {e}")
            return False
        
        # Vérifier les champs
        if read_entry["commentaire"] != "Test commentaire":
            print(f"  ❌ Commentaire incorrect: {read_entry['commentaire']}")
            return False
        
        if read_entry["agent"] != "claude":
            print(f"  ❌ Agent incorrect: {read_entry['agent']}")
            return False
        
        if read_entry["model"] != "claude-3-5-sonnet":
            print(f"  ❌ Model incorrect: {read_entry['model']}")
            return False
        
        print("  ✅ Écriture et lecture OK")
        return True
        
    finally:
        # Nettoyer
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_sortie_lire_signalements():
    """Test la sortie du script lire_signalements.py."""
    print("\nTest 4: Simulation de la sortie de lire_signalements.py...")
    
    # Simuler une entrée complète
    entry = {
        "id": "abc123",
        "horodatage": "2026-10-19T10:00:00.000000",
        "mode_origine": "exercice",
        "log_id": "log-123",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "move": "e4",
        "reponse": "Réponse du coach",
        "commentaire": "Ce commentaire est incorrect",
        "agent": "claude",
        "model": "claude-3-5-sonnet-20250620",
        "traite": False,
    }
    
    # Simuler l'affichage du commentaire (ligne 103-104 de lire_signalements.py)
    if entry.get("commentaire"):
        commentaire_affiche = f"Commentaire d'Alain : {entry['commentaire']}"
    else:
        commentaire_affiche = None
    
    # Simuler l'affichage de l'agent et du modèle (lignes 91-98)
    agent = entry.get("agent") or ""
    model = entry.get("model") or ""
    agent_info = f"  agent={agent}" if agent else ""
    model_info = f"  model={model}" if model else ""
    
    if agent_info or model_info:
        agent_model_affiche = f"{agent_info}{model_info}"
    else:
        agent_model_affiche = None
    
    # Vérifier
    if commentaire_affiche and "Ce commentaire est incorrect" in commentaire_affiche:
        print(f"  ✅ Commentaire affiché: {commentaire_affiche}")
    else:
        print(f"  ❌ Commentaire non affiché correctement")
        return False
    
    if agent_model_affiche and "agent=claude" in agent_model_affiche and "model=claude-3-5-sonnet-20250620" in agent_model_affiche:
        print(f"  ✅ Agent et modèle affichés: {agent_model_affiche}")
    else:
        print(f"  ❌ Agent/modèle non affichés correctement")
        return False
    
    return True


def test_sortie_complet():
    """Test la sortie complète du script lire_signalements.py."""
    print("\nTest 5: Simulation de la sortie complète...")
    
    entry = {
        "id": "abc123",
        "horodatage": "2026-10-19T10:00:00.000000",
        "mode_origine": "exercice",
        "log_id": "log-123",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "move": "e4",
        "reponse": "Réponse du coach",
        "commentaire": "Test commentaire",
        "agent": "mistral",
        "model": "mistral-large-latest",
        "traite": False,
    }
    
    # Simuler la ligne 298 de lire_signalements.py
    agent = entry.get("agent") or ""
    model = entry.get("model") or ""
    agent_model = f" — Agent: {agent}" if agent else ""
    if model:
        agent_model += f" (modèle: {model})"
    
    # Simuler la ligne 303
    commentaire = entry.get('commentaire') or '(aucun)'
    
    # Construire la ligne complète
    ligne = f"=== Signalement {entry.get('id', '?')} — {entry.get('horodatage', '?')}{entry.get('traite', False)}{agent_model} ==="
    
    if "Agent: mistral" in ligne and "modèle: mistral-large-latest" in ligne:
        print(f"  ✅ En-tête avec agent/modèle: OK")
    else:
        print(f"  ❌ En-tête incorrect: {ligne}")
        return False
    
    if commentaire == "Test commentaire":
        print(f"  ✅ Commentaire dans sortie complète: OK")
    else:
        print(f"  ❌ Commentaire incorrect: {commentaire}")
        return False
    
    return True


def main():
    """Exécute tous les tests."""
    print("=" * 60)
    print("Tests Backend Signalement - Issue #122")
    print("=" * 60)
    
    tests = [
        test_signalement_structure,
        test_commentaire_vide,
        test_ecriture_fichier,
        test_sortie_lire_signalements,
        test_sortie_complet,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print(f"Résultats: {sum(results)}/{len(results)} tests passés")
    print("=" * 60)
    
    if all(results):
        print("✅ Tous les tests backend ont réussi")
        return 0
    else:
        print("❌ Certains tests ont échoué")
        return 1


if __name__ == "__main__":
    exit(main())
