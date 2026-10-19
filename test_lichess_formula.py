"""
Test de la formule Lichess pour la classification des coups.

Formule : chances = 2 / (1 + exp(-0.00368208 * cp)) - 1
Seuils : 
  - imprécision : chute >= 0.1
  - erreur : chute >= 0.2
  - gaffe : chute >= 0.3

Évaluations plafonnées à ±1000 cp.
"""

import math


def cp_to_win_probability(cp: int) -> float:
    """Convertit une évaluation en centipawns en probabilité de gain.
    
    Formule Lichess : chances = 2 / (1 + exp(-0.00368208 * cp)) - 1
    Plafond à ±1000 cp.
    """
    # Plafond à ±1000 cp
    cp_clamped = max(-1000, min(1000, cp))
    return 2 / (1 + math.exp(-0.00368208 * cp_clamped)) - 1


def classify_move_lichess(cp_before: int, cp_after: int, player_color: str) -> str:
    """Classe un coup selon la méthode Lichess.
    
    Args:
        cp_before: évaluation AVANT le coup (du point de vue des Blancs)
        cp_after: évaluation APRÈS le coup (du point de vue des Blancs)
        player_color: couleur du joueur qui a joué ('white' ou 'black')
    
    Returns:
        'bon', 'imprecision', 'erreur', ou 'gaffe'
    """
    # Convertir les évaluations du point de vue des Blancs au point de vue du joueur
    if player_color == 'white':
        eval_before = cp_before
        eval_after = cp_after
    else:  # black
        eval_before = -cp_before
        eval_after = -cp_after
    
    # Calculer les probabilités de gain
    prob_before = cp_to_win_probability(eval_before)
    prob_after = cp_to_win_probability(eval_after)
    
    # Calculer la chute de chances de gain
    drop = prob_before - prob_after
    
    # Classifier selon les seuils Lichess
    if drop >= 0.3:
        return 'gaffe'
    elif drop >= 0.2:
        return 'erreur'
    elif drop >= 0.1:
        return 'imprecision'
    else:
        return 'bon'


def test_exemples_lichess():
    """Test les 6 exemples annotés par Lichess."""
    # Format: (cp_before, cp_after, player_color, expected_classification)
    # Évaluations en pions du point de vue des Blancs, camp qui a joué entre parenthèses
    
    exemples = [
        # 0,27 → 0,96 (Noirs) imprécision
        (0.27 * 100, 0.96 * 100, 'black', 'imprecision'),
        
        # 0,00 → −0,65 (Blancs) imprécision
        (0.00 * 100, -0.65 * 100, 'white', 'imprecision'),
        
        # −0,02 → −1,24 (Blancs) erreur
        (-0.02 * 100, -1.24 * 100, 'white', 'erreur'),
        
        # 1,82 → 0,64 (Blancs) erreur
        (1.82 * 100, 0.64 * 100, 'white', 'erreur'),
        
        # 4,27 → 0,10 (Blancs) gaffe
        (4.27 * 100, 0.10 * 100, 'white', 'gaffe'),
        
        # −2,88 → −0,21 (Noirs) gaffe
        (-2.88 * 100, -0.21 * 100, 'black', 'gaffe'),
    ]
    
    print("Test des exemples Lichess :")
    print("=" * 80)
    
    all_passed = True
    for cp_before, cp_after, player_color, expected in exemples:
        result = classify_move_lichess(cp_before, cp_after, player_color)
        passed = result == expected
        all_passed = all_passed and passed
        
        # Calculer les détails pour l'affichage
        if player_color == 'white':
            eval_before = cp_before
            eval_after = cp_after
        else:
            eval_before = -cp_before
            eval_after = -cp_after
        
        prob_before = cp_to_win_probability(eval_before)
        prob_after = cp_to_win_probability(eval_after)
        drop = prob_before - prob_after
        
        status = "✓" if passed else "✗"
        print(f"{status} {cp_before/100:+.2f} → {cp_after/100:+.2f} ({player_color}) ")
        print(f"  Éval joueur avant: {eval_before/100:+.2f}, après: {eval_after/100:+.2f}")
        print(f"  Prob avant: {prob_before:.4f}, après: {prob_after:.4f}, chute: {drop:.4f}")
        print(f"  Résultat: {result}, attendu: {expected}")
        print()
    
    return all_passed


def test_cas_limites():
    """Test des cas limites."""
    print("\nTest des cas limites :")
    print("=" * 80)
    
    # Cas 1: Position très avantageuse où une perte importante reste une simple imprécision
    # Exemple: +800 cp avant, +600 cp après (perte de 200 cp)
    cp_before = 800
    cp_after = 600
    result = classify_move_lichess(cp_before, cp_after, 'white')
    
    # Calculer les détails
    prob_before = cp_to_win_probability(800)
    prob_after = cp_to_win_probability(600)
    drop = prob_before - prob_after
    
    print(f"Cas 1: +8.00 → +6.00 (Blancs)")
    print(f"  Prob avant: {prob_before:.4f}, après: {prob_after:.4f}, chute: {drop:.4f}")
    print(f"  Résultat: {result} (attendu: imprécision ou erreur selon la chute)")
    print()
    
    # Cas 2: Évaluation de mat (très grand nombre)
    # Mat en 1 pour les Blancs: +10000 cp
    # Après le coup: mat en 2 pour les Noirs: -10000 cp
    # Du point de vue des Blancs qui jouent: avant = +10000, après = -10000
    # Du point de vue du joueur (Blancs): avant = +10000, après = -10000
    # Plafonnés à ±1000: avant = +1000, après = -1000
    cp_before = 10000
    cp_after = -10000
    result = classify_move_lichess(cp_before, cp_after, 'white')
    
    prob_before = cp_to_win_probability(1000)
    prob_after = cp_to_win_probability(-1000)
    drop = prob_before - prob_after
    
    print(f"Cas 2: Mat en 1 → Mat en 2 contre (Blancs)")
    print(f"  Éval avant: +1000 (plafonné), après: -1000 (plafonné)")
    print(f"  Prob avant: {prob_before:.4f}, après: {prob_after:.4f}, chute: {drop:.4f}")
    print(f"  Résultat: {result} (attendu: gaffe)")
    print()
    
    # Cas 3: Perte nulle
    cp_before = 50
    cp_after = 50
    result = classify_move_lichess(cp_before, cp_after, 'white')
    
    prob_before = cp_to_win_probability(50)
    prob_after = cp_to_win_probability(50)
    drop = prob_before - prob_after
    
    print(f"Cas 3: +0.50 → +0.50 (Blancs)")
    print(f"  Prob avant: {prob_before:.4f}, après: {prob_after:.4f}, chute: {drop:.4f}")
    print(f"  Résultat: {result} (attendu: bon)")
    print()
    
    # Cas 4: Coup qui améliore l'évaluation
    cp_before = -50
    cp_after = 50
    result = classify_move_lichess(cp_before, cp_after, 'white')
    
    prob_before = cp_to_win_probability(-50)
    prob_after = cp_to_win_probability(50)
    drop = prob_before - prob_after
    
    print(f"Cas 4: -0.50 → +0.50 (Blancs)")
    print(f"  Prob avant: {prob_before:.4f}, après: {prob_after:.4f}, chute: {drop:.4f}")
    print(f"  Résultat: {result} (attendu: bon, car drop est négatif)")
    print()


def test_seuils_centipions():
    """Test pour vérifier les équivalences en centipions."""
    print("\nTest des équivalences en centipions :")
    print("=" * 80)
    
    # Depuis une position égale (0 cp)
    print("Depuis une position égale (0 cp) :")
    for threshold in [0.1, 0.2, 0.3]:
        # Trouver le delta_cp qui donne exactement cette chute
        # prob_before = cp_to_win_probability(0) = 0.5
        # prob_after = 0.5 - threshold
        # cp_after = inverse de cp_to_win_probability(0.5 - threshold)
        prob_target = 0.5 - threshold
        # Résoudre: prob_target = 2 / (1 + exp(-0.00368208 * cp)) - 1
        # => prob_target + 1 = 2 / (1 + exp(-0.00368208 * cp))
        # => (prob_target + 1) / 2 = 1 / (1 + exp(-0.00368208 * cp))
        # => 2 / (prob_target + 1) = 1 + exp(-0.00368208 * cp)
        # => exp(-0.00368208 * cp) = 2 / (prob_target + 1) - 1
        # => -0.00368208 * cp = ln(2 / (prob_target + 1) - 1)
        # => cp = -ln(2 / (prob_target + 1) - 1) / 0.00368208
        
        ratio = 2 / (prob_target + 1)
        cp_needed = -math.log(ratio - 1) / 0.00368208
        
        print(f"  Seuil {threshold} (chute de probabilité): delta_cp ≈ {cp_needed:.1f}")
    
    print()
    
    # Depuis +500 cp
    print("Depuis +500 cp (position avantageuse) :")
    prob_before = cp_to_win_probability(500)
    for threshold in [0.1, 0.2, 0.3]:
        prob_target = prob_before - threshold
        ratio = 2 / (prob_target + 1)
        cp_after = -math.log(ratio - 1) / 0.00368208
        delta_cp = 500 - cp_after
        
        print(f"  Seuil {threshold} (chute de probabilité): delta_cp ≈ {delta_cp:.1f}")
    
    print()
    
    # Depuis +800 cp
    print("Depuis +800 cp (position très avantageuse) :")
    prob_before = cp_to_win_probability(800)
    for threshold in [0.1, 0.2, 0.3]:
        prob_target = prob_before - threshold
        ratio = 2 / (prob_target + 1)
        cp_after = -math.log(ratio - 1) / 0.00368208
        delta_cp = 800 - cp_after
        
        print(f"  Seuil {threshold} (chute de probabilité): delta_cp ≈ {delta_cp:.1f}")


if __name__ == "__main__":
    print("Test de la formule Lichess pour la classification des coups")
    print()
    
    # Test des exemples Lichess
    all_passed = test_exemples_lichess()
    
    # Test des cas limites
    test_cas_limites()
    
    # Test des équivalences
    test_seuils_centipions()
    
    print()
    if all_passed:
        print("✓ Tous les tests des exemples Lichess ont passé !")
    else:
        print("✗ Certains tests ont échoué !")
