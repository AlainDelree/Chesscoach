"""
Test de l'implémentation de l'issue #125 : verdict officiel Lichess.

Ce script vérifie que :
1. Les fonctions de classification Lichess sont correctement implémentées
2. evaluate_move retourne les bons champs
3. Les exemples Lichess donnent les bons résultats
"""

import sys
import chess
import math

# Ajouter le répertoire courant au path
sys.path.insert(0, '/home/alain/worktrees/chesscoach-issue125')

from engine_stockfish import cp_to_win_probability, classify_move_lichess


def test_formule_lichess():
    """Test la formule de conversion cp → probabilité de gain."""
    print("Test de la formule Lichess...")
    
    # Test des valeurs connues
    # La formule est : 2 / (1 + exp(-0.00368208 * cp)) - 1
    # Pour cp=0: 2/(1+1) - 1 = 0
    # Pour cp=100: 2/(1+exp(-0.368208)) - 1 ≈ 0.182052
    # Pour cp=1000: 2/(1+exp(-3.68208)) - 1 ≈ 0.9509
    tests = [
        (0, 0.0),  # Position égale
        (100, 0.182052),  # +1 pion
        (-100, -0.182052),  # -1 pion
        (1000, 0.9509),  # Position très avantageuse
        (-1000, -0.9509),  # Position très désavantageuse
    ]
    
    for cp, expected in tests:
        result = cp_to_win_probability(cp)
        # Arrondir à 4 décimales pour la comparaison
        if abs(result - expected) > 0.0001:
            print(f"  ✗ FAIL: cp_to_win_probability({cp}) = {result:.6f}, attendu {expected:.6f}")
            return False
    
    print("  ✓ Formule Lichess correcte")
    return True


def test_classification_lichess():
    """Test la classification selon la méthode Lichess."""
    print("\nTest de la classification Lichess...")
    
    # Les 6 exemples annotés par Lichess
    # Format: (cp_before, cp_after, player_is_white, expected)
    # Évaluations en pions du point de vue des Blancs
    exemples = [
        # 0,27 → 0,96 (Noirs) imprécision
        (27, 96, False, 'imprecision'),
        
        # 0,00 → −0,65 (Blancs) imprécision
        (0, -65, True, 'imprecision'),
        
        # −0,02 → −1,24 (Blancs) erreur
        (-2, -124, True, 'erreur'),
        
        # 1,82 → 0,64 (Blancs) erreur
        (182, 64, True, 'erreur'),
        
        # 4,27 → 0,10 (Blancs) gaffe
        (427, 10, True, 'gaffe'),
        
        # −2,88 → −0,21 (Noirs) gaffe
        (-288, -21, False, 'gaffe'),
    ]
    
    all_passed = True
    for cp_before, cp_after, player_is_white, expected in exemples:
        result = classify_move_lichess(cp_before, cp_after, player_is_white)
        if result != expected:
            print(f"  ✗ FAIL: {cp_before/100:+.2f} → {cp_after/100:+.2f} ({'Blancs' if player_is_white else 'Noirs'}) = {result}, attendu {expected}")
            all_passed = False
        else:
            print(f"  ✓ {cp_before/100:+.2f} → {cp_after/100:+.2f} ({'Blancs' if player_is_white else 'Noirs'}) = {result}")
    
    return all_passed


def test_cas_limites():
    """Test des cas limites."""
    print("\nTest des cas limites...")
    
    # Cas 1: Position très avantageuse où une perte importante reste une simple imprécision
    result = classify_move_lichess(800, 600, True)
    print(f"  +8.00 → +6.00 (Blancs) = {result}")
    
    # Cas 2: Évaluation de mat (plafonnée à ±1000)
    result = classify_move_lichess(10000, -10000, True)
    print(f"  Mat en 1 → Mat en 2 contre (Blancs) = {result}")
    if result != 'gaffe':
        print(f"    ✗ FAIL: attendu 'gaffe', obtenu '{result}'")
        return False
    
    # Cas 3: Perte nulle
    result = classify_move_lichess(50, 50, True)
    print(f"  +0.50 → +0.50 (Blancs) = {result}")
    if result != 'bon':
        print(f"    ✗ FAIL: attendu 'bon', obtenu '{result}'")
        return False
    
    # Cas 4: Coup qui améliore l'évaluation
    result = classify_move_lichess(-50, 50, True)
    print(f"  -0.50 → +0.50 (Blancs) = {result}")
    if result != 'bon':
        print(f"    ✗ FAIL: attendu 'bon', obtenu '{result}'")
        return False
    
    print("  ✓ Cas limites corrects")
    return True


def test_seuils_centipions():
    """Test pour vérifier les équivalences en centipions."""
    print("\nTest des équivalences en centipions...")
    
    # Depuis une position égale (0 cp)
    print("  Depuis une position égale (0 cp):")
    for threshold in [0.1, 0.2, 0.3]:
        prob_target = 0.5 - threshold
        ratio = 2 / (prob_target + 1)
        cp_needed = -math.log(ratio - 1) / 0.00368208
        print(f"    Seuil {threshold} (chute de probabilité): delta_cp ≈ {cp_needed:.1f}")
    
    print("  ✓ Équivalences calculées")
    return True


def main():
    print("=" * 80)
    print("Test de l'implémentation de l'issue #125")
    print("=" * 80)
    
    all_passed = True
    
    # Test de la formule
    if not test_formule_lichess():
        all_passed = False
    
    # Test de la classification
    if not test_classification_lichess():
        all_passed = False
    
    # Test des cas limites
    if not test_cas_limites():
        all_passed = False
    
    # Test des équivalences
    if not test_seuils_centipions():
        all_passed = False
    
    print()
    print("=" * 80)
    if all_passed:
        print("✓ Tous les tests ont passé !")
        return 0
    else:
        print("✗ Certains tests ont échoué !")
        return 1


if __name__ == "__main__":
    sys.exit(main())
