# Issue #155 — Tests : remettre au vert test_issue121.py

Deux vérifications statiques de `test_issue121.py` échouaient (4/6) depuis
le commit `4b2cf89` (fix-issue-122) : ce commit a remplacé la construction
en direct du bouton « Signaler » (classe `coach-signal-btn`, variable
`signalBtn`, bouton créé séparément dans `_coachRenderBubbleWithAgent` et
`_coachRenderMistralBubbleWithAgent`) par une délégation à la fonction
partagée `_coachBuildSignalerUI` (classe `coach-signaler-btn`, variable
`btn`, champ de justification). Le comportement voulu par l'issue #121
(bouton « Signaler » → `socket.emit("signalement_envoyer", ...)` →
passage à « Signalé » et désactivation, y compris sous Mistral en mode
Exercice) existe toujours, sous cette autre forme — cas (a) pour les deux
vérifications : rien à voir avec Mistral désactivé dans la config locale,
c'est un refactor de l'issue #122, antérieur à cette tâche.

- `test_board_js_signal_button` (test 2) : cherche désormais la
  délégation `_coachBuildSignalerUI(bubble...)` dans
  `_coachRenderBubbleWithAgent`, et vérifie le comportement réel
  (`socket.emit`, `btn.textContent = "Signalé"`, `btn.disabled = true`)
  dans `_coachBuildSignalerUI` plutôt que les anciens noms littéraux
  `signalBtn`/`coach-signal-btn`.
- `test_mistral_signal_button` (test 4) : vérifie que
  `_coachRenderMistralBubbleWithAgent` délègue bien à
  `_coachBuildSignalerUI` avec ses métadonnées (`log_id: logId`), puis que
  `_coachBuildSignalerUI` crée bien un bouton « Signaler » relié à
  `socket.emit("signalement_envoyer", ...)`.
- Ajout d'un petit utilitaire `_extract_block()` dans le fichier de test
  pour isoler le code d'une fonction entre deux marqueurs (réutilisé par
  les tests 2 et 4).
- Vérifié que les deux vérifications adaptées peuvent toujours échouer
  (régression manuelle : renommer le texte de confirmation fait repasser
  le test à 5/6).

Résultat : `test_issue121.py` seul → 6/6. Suite complète
`scripts/lancer_tests.py --rapide` → 26/26 fichiers OK, 0 échec, 0 expiré.

`docs/contexte/tests.md` : suppression de la mention « test_issue121.py
échoue » dans les limites connues (devenue fausse).
