# Changelog — Issue #100

## Mobile : sélecteur d'ouvertures/finales qui réapparaît, message de fin de théorie, style des listes, barre de fin de partie sans troncature

Retours d'Alain après tests GSM (390×750) de l'issue #95 : sélecteur
d'ouvertures disparu dès qu'une partie est lancée et jamais revu sans
recharger la page ; pas d'indication de fin de théorie ; listes
déroulantes nues, hors style de l'appli ; boutons de la barre de fin de
partie tronqués (« Anal… »/« Comm… »/« Nouvelle… ») à 360-390px.

### 1. Sélecteur d'ouvertures/finales : cause réelle et correctif

Le sélecteur (et les boutons « Jouer les Blancs/Noirs ») n'était PAS perdu
ni mal replacé : `placeOpeningStartButtonsForViewport`/
`placeFinaleStartButtonsForViewport`/`placePedagogicStartButtonsForViewport`
le replaçaient déjà correctement dans son slot dès la fin de partie
(`XGameOver` passé à vrai). Le vrai coupable était une règle CSS :
`body.game-over-active.mobile-game-active .mode-start-slot { display:none
!important; }` masquait ce slot jusqu'à un clic explicite sur « Nouvelle
partie » (`mobileNewGameFromBanner`) — geste qu'Alain n'a pas identifié
pendant ses tests (boutons tronqués, cf. point 4). Retiré `.mode-start-slot`
de cette règle (`templates/index.html`) : le sélecteur réapparaît
désormais **immédiatement** à la fin de partie (mat, nulle, abandon),
**à côté** du résultat — plus besoin de cliquer « Nouvelle partie » avant
de choisir une autre ouverture/finale/couleur, confirmé par des parties
réelles (mode Finales, moteur Stockfish) jusqu'à l'abandon puis
l'enchaînement direct d'une autre finale, sans recharger la page.

Comportement retenu pour une partie en cours quittée par changement de
mode (onglet) : **préservée**, pas abandonnée — `switchModeTab` ne
déclenche jamais `ensureModeSwitchClean` (qui, seul, abandonne l'ancien
mode), celui-ci n'intervenant qu'au **démarrage effectif** d'une nouvelle
partie dans un autre mode. Revenir sur l'onglet retrouve donc le plateau et
la position exacts (vérifié par test : FEN identique avant/après un
aller-retour d'onglet en cours de partie), sélecteur toujours masqué tant
que la partie n'est pas finie.

Bonus (bug préexistant découvert en vérifiant la non-régression grand
écran) : `.mode-start-slot`/`#mobile-game-idle-msg`/`#mobile-game-over-bar`
n'avaient leur `display:none/contents` par défaut déclaré QUE dans la
media query mobile — sur grand écran (medium query inactive), ces 3
éléments gardaient leur `display` natif et s'affichaient "nus" à côté du
grand bandeau desktop déjà correct. Ajouté une valeur par défaut hors
media query (même pattern que `#mobile-bottom-slot`/
`.board-lines-command-bar` juste au-dessus) — confirmé par capture avant/
après à 1400px.

### 2. Message de fin de théorie (mode Ouvertures)

`opening.js` : transition dans_le_livre→hors_livre détectée côté client
(comparaison de `openingInBook` avant/après chaque `opening_stockfish_move`
— couvre aussi bien un coup d'Alain hors livre qu'une réponse d'adversaire
introuvable). Message « Fin de la théorie : le livre d'ouvertures ne
connaît plus cette position, la partie continue contre le moteur. »
affiché une seule fois (`openingTheoryEndAnnounced`, remis à faux au
démarrage d'une nouvelle partie) dans le chat du coach (bulle
`coach-bubble-announce`, comme l'annonce de démarrage — ne déclenche jamais
le plateau réduit mobile) ET dans la ligne d'état dédiée du mode
(`#opening-status`). Vérifié : non répété à un second coup hors livre,
plateau non réduit (`board-compact` absent après le message).

### 3. Style des listes déroulantes (ouvertures/finales)

Nouvelle classe `.cc-select` (`templates/index.html`) appliquée à
`#opening-select`/`#finale-select` : bordure terracotta 2px, radius pilule,
police Caprasimo, hauteur 44px (cible tactile), `width:100%` +
`box-sizing:border-box` — même famille visuelle que le sélecteur de mode
en haut à gauche. Flèche native du navigateur conservée (pas de flèche
recréée en CSS) : ce <select> reste un contrôle de formulaire standard,
défilement natif pour les 46 ouvertures. Vérifié à 390×750, 360×640 et
1400×900 (captures) : aucun débordement horizontal (mesuré,
`scrollWidth - clientWidth === 0` dans les 4 cas).

### 4. Barre de fin de partie sans troncature

Solution retenue (la plus simple, comme demandé) : deux lignes plutôt
qu'une — résultat seul sur sa ligne compacte (libellé court dérivé du
camp/de l'abandon par `_shortGameOverLabel`, nouveau dans `board.js` : «
Blancs gagnent »/« Noirs gagnent »/« Nulle »/« Défaite par abandon »/« Partie
abandonnée », jamais le message long du grand bandeau desktop), puis les
3 boutons (« Analyser »/« Commenter »/« Nouvelle partie », libellés COMPLETS
inchangés) en pleine largeur sur une seconde ligne. `showGameOverBanner`
gagne un 5ᵉ paramètre `abandon` (répercuté dans les 4 appels d'abandon :
pédagogique/ouverture/finales/partie libre) pour distinguer l'abandon du
mat dans le libellé court. Boutons Précédent/Suivant/Retourner/Meilleur
coup non déplacés (option alternative écartée par Alain elle-même).

Mesuré (Playwright, 360×640, scénario victoire pédagogique) :
- **Avant** : 1 ligne, hauteur 42px, les 3 boutons tronqués avec ellipse
  (`scrollWidth > offsetWidth` pour chacun — ex. "Nouvelle partie"
  offsetWidth=65 vs scrollWidth=97) ET le texte de résultat lui-même
  tronqué (« Échec et mat — les N… »).
- **Après** : 2 lignes, hauteur 69px (+27px), aucune troncature
  (`scrollWidth <= offsetWidth` pour les 3 boutons aux 2 largeurs,
  360px et 390px), résultat court entier lisible (« Noirs gagnent »).

Appliqué aux 4 modes de partie (pédagogique/ouverture/finales/libre) et
aux 4 résultats (abandon/mat/nulle/victoire) — vérifié par simulation
d'événements serveur pour chaque combinaison. Non-régression vérifiée :
onglet Analyse accessible et fonctionnel après un abandon (bascule de
plateau + `board-compact` cohérents), plateau/onglets inchangés en cours
de partie.

### Limites et périmètre non couvert

- Aucune clé API Claude dans cet environnement de test : impossible de
  dérouler le chemin complet `opening_start`→Claude (identification des
  coups caractéristiques d'une ouverture réelle). Le cycle de vie complet
  (démarrage, sortie de théorie, fin de partie, relance) a été vérifié par
  simulation directe des événements SocketIO (`opening_started`/
  `opening_stockfish_move`) que le client traite exactement de la même
  façon qu'un aller-retour serveur réel — mais le tout premier aller-retour
  réel (`opening_start`→`get_opening_moves`) n'a pas pu être rejoué de bout
  en bout. Le mode Finales (pas d'appel LLM pour démarrer, juste
  Stockfish) a lui été testé de bout en bout en conditions réelles
  (moteur réel, clics réels, sans aucune simulation).
- Asymétrie préexistante non corrigée (hors périmètre) : le bouton
  « Analyser » n'apparaît qu'après un abandon pour les modes
  Ouverture/Finales, jamais après un mat/une nulle "naturelle" (seul le
  mode Pédagogique l'a dans les deux cas) — documenté de longue date dans
  `board.js` (issue #41, "hors périmètre"). La nouvelle barre à 2 lignes
  gère correctement 1, 2 ou 3 boutons visibles, donc ne dépend pas de
  cette asymétrie, mais ne la corrige pas non plus (non demandé par cette
  issue).
- Message de fin de théorie non ré-émis après un « Reprendre mon coup »
  qui ramènerait la partie à une position encore dans le livre, puis une
  sortie différente plus tard dans la même partie : `openingTheoryEndAnnounced`
  reste vrai jusqu'à la prochaine partie. Cas marginal (il faudrait annuler
  puis rejouer différemment après l'avoir déjà vu une fois) non couvert,
  l'exigence "ne doit pas être répétée" étant respectée au sens strict.
- Flèche native du `<select>` conservée plutôt que recréée en CSS
  (`appearance:none`) : léger écart d'habillage avec les boutons/feuilles
  du bas de l'appli, choix délibéré pour garder le défilement natif des
  46 ouvertures sans risque de régression multi-navigateurs.
