# Changelog — Issue #50

## Interface adaptée au GSM (affichage vertical, déplacement des pièces au toucher)

- Constat : aucune balise viewport dans `templates/index.html` — un mobile
  rendait donc la page comme un "layout viewport" de 980px puis la réduisait
  à l'échelle (plateau minuscule, zoom nécessaire pour jouer). La mise en
  page était par ailleurs figée en colonnes fixes (620/240/420/480px) sans
  aucune adaptation aux écrans étroits.
- `templates/index.html` :
  - Ajout de `<meta name="viewport" content="width=device-width,
    initial-scale=1, maximum-scale=1, viewport-fit=cover">`.
  - Nouvelle règle `@media (max-width: 900px)` (aucun effet au-dessus de ce
    seuil, vérifié par capture d'écran diff pixel-à-pixel à 1440px —
    strictement identique avant/après) :
    - `#app` passe en colonne unique (`flex-direction: column`) ; les 4
      colonnes (`#board-column`, `#coach-column`, `#mode-tabs-column`,
      `#historique-column`) passent à `width:100%` et sont réordonnées via
      `order` : plateau, puis chat du coach, puis onglets de mode, puis
      historique des coups (secondaire sur GSM) en dernier.
    - `--bd-size` (taille du plateau, définie dans `board.css`) reçoit une
      borne supplémentaire `calc(100vw - 92px)` pour tenir compte de la
      largeur écran disponible (auparavant seulement `min(70vh, 560px)`,
      indépendant de la largeur — débordait horizontalement sur un
      téléphone en portrait).
    - `.coach-drawer` : `max-height` réduit à `55vh` (au lieu de
      `calc(100vh - 60px)`) pour garder plateau + chat visibles ensemble
      sans trop défiler, comme souhaité par Alain.
    - `.mode-tab-bar` : défilement horizontal (`overflow-x:auto;
      flex-wrap:nowrap`) plutôt que retour à la ligne, comme demandé.
    - `#review-controls` : `flex-wrap:wrap` ajouté (sans quoi la rangée de 5
      boutons Précédent/Suivant/Retourner/Meilleur coup/Extraire le FEN
      dépassait la largeur de l'écran et provoquait un défilement horizontal
      de toute la page).
    - Cibles tactiles agrandies (`button`/`.mode-tab-btn` : `min-height:
      44px`) et police des champs de saisie forcée à `16px` (empêche le
      zoom automatique au focus sur iOS Safari).
- `static/board.css` : `touch-action: manipulation` ajouté sur `.square`
  (neutralise le double-tap-zoom pendant la séquence des deux taps du
  déplacement tactile ; sans effet visuel, donc neutre pour la souris).
- **Déplacement des pièces au toucher** : déjà entièrement fonctionnel sans
  changement de code JS — les 5 modes interactifs visés (partie libre,
  pédagogique, ouverture, finales, exercices) utilisent tous le même
  gestionnaire `boardEl.onclick = on<Mode>BoardClick`, avec le même schéma
  "tap sur la pièce à déplacer puis tap sur la case d'arrivée" que demandé
  dans l'issue — un tap génère un `click` DOM standard, déjà pris en charge
  par ce code. Le point bloquant était uniquement l'absence de balise
  viewport (rendait le plateau minuscule) et le manque de mise en page
  adaptée, tous deux corrigés ci-dessus.
- Note : le mode "Éditeur de position" utilise du drag-and-drop HTML5
  (`draggable`/`ondragstart`/`ondrop`) pour la palette de pièces, non
  compatible tactile — mais ce mode n'est pas dans la liste des 5 modes visés
  par l'issue, donc hors périmètre ici (limite connue, à traiter séparément
  si besoin).
- Vérification (Playwright, Chromium headless, serveur Flask lancé avec un
  `HOME` de test isolé sous le worktree pour ne pas toucher aux données
  réelles sous `~/ChessCoach/data`) :
  - Desktop 1440px : diff pixel-à-pixel avant/après = aucune différence.
  - Bascule de mise en page vérifiée exactement au seuil : 899px → colonne
    unique, 901px → mise en page desktop (`#app` `flex-direction`).
  - Mobile 390×844 (émulation tactile, `has_touch=True`) : aucun débordement
    horizontal de la page (`scrollWidth === clientWidth === 390`), barre
    d'onglets bien scrollable horizontalement (`scrollWidth` 963px pour un
    `clientWidth` de 356px).
  - Déplacement tactile testé avec deux taps successifs (`locator.tap()`) :
    - Mode "Partie libre" : coup e2-e4 joué avec succès (case de départ
      vidée, pion visible en e4, statut passé à "Trait aux Noirs").
    - Mode "Partie pédagogique" (Blancs) : coup d2-d4 joué avec succès,
      réponse automatique de Stockfish (d7-d5) reçue et affichée.
    - Les 3 autres modes visés (ouverture, finales, exercices) partagent
      strictement le même gestionnaire de clic sur case
      (`sqEl = e.target.closest(".square")` puis
      sélection/déplacement identiques) — non exécutés en bout en bout ici
      faute de données de test (livre d'ouverture, tables Syzygy, historique
      d'erreurs, tous gitignorés et absents de l'environnement de test
      isolé), mais le mécanisme est identique à celui validé sur les deux
      modes testés.
- Limites connues :
  - Éditeur de position non adapté au tactile (drag-and-drop HTML5, hors
    périmètre de l'issue).
  - Pas de test sur un appareil physique réel — seulement émulation
    Playwright/Chromium (viewport + événements tactiles synthétiques).
  - Le zoom pincé (pinch-to-zoom) volontaire reste possible
    (`maximum-scale=1` limite mais ne bloque pas totalement selon les
    navigateurs) ; seul le double-tap-zoom accidentel est neutralisé via
    `touch-action: manipulation`, choix délibéré pour ne pas sacrifier
    l'accessibilité (zoom volontaire toujours possible pour lire un texte
    petit) — bon compromis pratique pour rester conforme aux bonnes
    pratiques mobiles actuelles.
