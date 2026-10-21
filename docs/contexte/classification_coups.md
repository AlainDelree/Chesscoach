# Classification des coups (issue #125)

### Méthode officielle Lichess

La classification des coups utilise désormais la **méthode officielle Lichess** comme
référence (issue #125). Cette méthode ne repose pas sur des seuils fixes en
centipions, mais sur la **variation des chances de gain** du joueur qui vient de
jouer.

**Formule** :
```
chances = 2 / (1 + exp(-0.00368208 × cp)) - 1
```

Où `cp` est l'évaluation en centipawns, plafonnée à ±1000 cp.

**Seuils de classification** (sur la chute de chances de gain) :
- **bon** : chute < 0.1
- **imprécision** : chute ≥ 0.1
- **erreur** : chute ≥ 0.2
- **gaffe** : chute ≥ 0.3

**Conséquence importante** : la perte minimale en centipions pour atteindre un
seuil augmente avec l'avantage déjà acquis. Par exemple :
- Depuis une position égale (0 cp) : ~55 cp (imprécision), ~111 cp (erreur), ~169 cp (gaffe)
- Depuis +500 cp : ~101 cp (imprécision), ~183 cp (erreur), ~253 cp (gaffe)
- Depuis +800 cp : ~204 cp (imprécision), ~329 cp (erreur), ~424 cp (gaffe)

### Distinction sélection/exercice vs verdict affiché

**La sélection des exercices** (fichier `erreurs_detectees.json`, scripts
`build_patterns_erreurs.py`) utilise toujours des **seuils fixes en centipions**
(SEUIL_ERREUR = 300 cp, SEUIL_IMPRECISION = 100 cp dans `engine_stockfish.py`).
Cela permet de conserver une cohérence historique avec les exercices déjà
créés.

**Le verdict affiché et transmis au coach** utilise la **méthode officielle
Lichess** basée sur la chute de probabilité de gain. Cela signifie qu'une
position peut être sélectionnée comme exercice (parce que la perte en
centipions dépasse le seuil fixe) et recevoir, selon la méthode officielle,
un verdict différent (par exemple, une perte de 170 cp depuis une position
égale est une "gaffe" pour Lichess mais une "erreur" avec l'ancienne méthode).

**Champs transmis au coach** (issue #125, convention de signe mise à jour
par l'issue #128, voir fiche `convention_signe`) :
- `verdict_qualite` : verdict officiel Lichess ("bon", "imprecision", "erreur", "gaffe")
- `verdict_qualite_ancien` : verdict avec l'ancienne méthode (pour comparaison/journal)
- `verdict_delta_cp` : perte en centipions (ancienne méthode) — reste un
  montant **positif** perdu par le joueur qui vient de jouer, jamais signé
  Blancs/Noirs (inchangé par l'issue #128)
- `eval_before_cp` : évaluation AVANT le coup, **convention Lichess** :
  + = avantage Blancs, − = avantage Noirs
- `eval_after_cp` : évaluation APRÈS le coup, même convention
- `win_prob_drop` : chute de probabilité de gain (méthode Lichess), toujours
  positive, du point de vue du joueur qui vient de jouer (inchangé)

**Journalisation** : les entrées de journal contiennent à la fois l'étiquette
officielle et l'ancienne étiquette, ainsi que les évaluations avant/après, pour
mesurer l'écart entre les deux méthodes sur les exercices réels.
