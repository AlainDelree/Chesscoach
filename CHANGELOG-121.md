# Issue #121 : Suite #120 — Correction des bulles de coach Claude/Mistral

## Problèmes corrigés

### 1. Bulle de Claude étiquetée « Mistral »
**Cause** : Dans `static/exercise.js`, l'appel à `_coachRenderBubbleWithAgent` avait les paramètres dans le mauvais ordre. Le 5ème paramètre (`fiabilite`) était passé comme `undefined`, et le 6ème paramètre (l'objet `signalData`) était interprété comme `agent`. Ainsi, la variable `agent` dans la fonction recevait un objet au lieu de la chaîne "claude", et la condition `agent === "claude"` (ligne 1306 de board.js) échouait, affichant "Mistral" par défaut.

**Correction** : 
- Dans `static/exercise.js` ligne 1273 : correction de l'ordre des paramètres pour passer `data.fiabilite` comme 5ème paramètre et l'objet signalData comme 6ème
- Dans `static/board.js` ligne 1306 : la logique existante `agent === "claude" ? "Claude" : "Mistral"` fonctionne maintenant correctement

### 2. Boutons de note 1/0 absents sous la bulle de Claude
**Cause** : Le problème 1 empêchait aussi l'affichage correct des boutons. Avec `agent` étant un objet au lieu de "claude", la condition `agent && (agent === "claude" || agent === "mistral")` (ligne 1313 de board.js) échouait, donc les boutons de notation n'étaient pas créés.

**Correction** : Résolu par la correction du problème 1. Les boutons sont maintenant affichés sous chaque avis (Claude et Mistral).

### 3. Bouton 0 illisible quand sélectionné
**Cause** : Dans `static/board.css`, la règle `.rating-btn.rating-0.selected` définissait `background: var(--cc-error)` (brun foncé #8c491a) et `border-color: var(--cc-error)`, mais n'avait pas de propriété `color`. La règle `.rating-btn.rating-0` définissait `color: var(--cc-error)`, et comme les sélecteurs CSS plus spécifiques l'emportent, le texte restait brun foncé sur fond brun foncé.

**Correction** : Ajout de `color: white;` dans `.rating-btn.rating-0.selected` (ligne 581 de board.css) pour garantir un contraste suffisant.

### 4. Bouton « Signaler » muet sous la bulle de Claude
**Cause** : Dans `static/board.js` ligne 1386, le gestionnaire onclick du bouton Signaler appelait `_coachSignalClick(signalData)`, mais cette fonction n'était jamais définie. Le bouton était créé mais sans action fonctionnelle.

**Correction** : 
- Remplacement de l'appel à `_coachSignalClick` par un appel direct à `socket.emit("signalement_envoyer", ...)` comme dans `_coachBuildSignalerUI`
- Ajout du marquage visuel "Signalé" et désactivation du bouton après clic
- Transmission des champs `agent` et `model` dans les données du signalement

### 5. Bouton « Signaler » absent sous la bulle de Mistral
**Cause** : La fonction `_coachRenderMistralBubbleWithAgent` dans `static/board.js` ne créait pas de bouton Signaler, contrairement à `_coachRenderBubbleWithAgent`.

**Correction** : 
- Ajout du bouton Signaler dans `_coachRenderMistralBubbleWithAgent` avec la même logique que pour Claude
- Ajout du paramètre `agent` (avec valeur par défaut "mistral") pour uniformiser avec `_coachRenderBubbleWithAgent`
- Construction de `signalData` à partir des paramètres existants
- Mise à jour des appels dans `static/exercise.js` pour passer l'agent explicitement
- Ajout du champ `agent: "mistral"` dans les émissions serveur `exercise_mistral_comment` (app.py)

## Fichiers modifiés

- `static/board.css` : Correction style bouton 0 sélectionné, bouton 1 sélectionné lisible, boutons plus grands
- `static/board.js` : Correction bouton Signaler, ajout paramètre agent, ajout bouton Signaler sous Mistral
- `static/exercise.js` : Correction ordre paramètres, passage de l'agent pour Mistral
- `app.py` : Ajout champ agent dans exercise_mistral_comment, ajout champs agent/model dans on_signalement_envoyer
- `lire_signalements.py` : Affichage de l'agent et du modèle dans les résumés de signalements

## Vérification

Les corrections ont été vérifiées par analyse de code :
- L'en-tête des bulles affiche maintenant l'agent correct (Claude ou Mistral)
- Les boutons 1/0 sont présents sous les deux types de bulles
- Le bouton 0 sélectionné a un texte blanc sur fond brun
- Le bouton 1 sélectionné a un texte blanc sur fond vert
- Les boutons ont une taille confortable (min-width/height: 2.5rem, padding augmenté)
- Le bouton Signaler est présent et fonctionnel sous les deux bulles
- Les signalements incluent l'agent et le modèle dans les données envoyées et enregistrées
- La fonction `sigcoach` (lire_signalements.py) affiche maintenant l'agent et le modèle dans le résumé

**À vérifier par Alain sur GSM** :
- L'affichage visuel des bulles avec les bons auteurs
- Le fonctionnement des boutons de notation (enregistrement dans coach_ratings.jsonl avec le bon agent)
- Le fonctionnement du bouton Signaler (enregistrement dans data/logs/signalements.log avec le bon agent)
- La lisibilité des boutons 0 et 1 sélectionnés
- La fonction `sigcoach` affiche correctement le dernier signalement avec l'agent et le modèle
