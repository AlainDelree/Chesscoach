# Lignes calculées et prises en échange (issues #126/#128)

**Longueur d'une ligne calculée (PV)** : une ligne présentée au coach est
limitée à 4 coups, prolongée d'au plus 2 coups supplémentaires tant que le
dernier coup retenu est une capture — pour ne jamais arrêter la ligne au
milieu d'un échange (sinon le solde matériel de fin de ligne serait faux).
Fonction `_couper_pv(board, coups, n, extra=2)` (`engine_stockfish.py`),
appelée pour `pv_coup_propose`/`pv_meilleur_coup` ; même règle appliquée
côté `game_facts.describe_pv_facts` pour les faits python-chess par coup
de la PV.

**« En prise »** : un vrai calcul d'échange sur la case
(`game_facts._gain_capture`), pas une simple présence d'attaquant — tient
compte des clouages (un défenseur cloué sur la case ne compte pas dans le
calcul du gain net de la prise).
