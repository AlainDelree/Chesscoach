/*
 * mobile_game.js — ChessCoach (issue #70)
 *
 * Écran de partie mobile (plateau fixe, onglets, bande compacte) d'après la
 * maquette Claude Design (design/partie_mobile/) : réorganise l'affichage
 * DÉJÀ existant des modes partie libre/pédagogique/ouverture/finales sur
 * écran étroit (<900px), sans dupliquer ni réécrire la moindre logique de
 * jeu — uniquement des déplacements de nœuds DOM (même principe que
 * placeModeTabBarForViewport/_placeMobileRelocatablesForViewport, déjà
 * présents dans controls.js depuis les issues #63/#69) et des bascules de
 * classes CSS. Le mode exercice, la bibliothèque/revue, l'éditeur de
 * position et le grand écran ne sont jamais touchés par ce fichier : tout
 * est conditionné à isGameUiActive() ci-dessous.
 *
 * Déclenché à chaque changement d'onglet de mode (switchModeTab, controls.js)
 * et à chaque rafraîchissement de la barre d'actions partagée
 * (updateSharedControlBar, controls.js — déjà appelée par tous les modes à
 * chaque démarrage/abandon/reprise/fin de partie) via le hook
 * onGameUiRefresh(), défini ici et appelé depuis controls.js sous réserve
 * qu'il existe (aucune dépendance dure dans l'autre sens).
 */

const GAME_MODES = ["free", "pedagogic", "opening", "finale"];
const _gameUiQuery = window.matchMedia("(max-width: 900px)");

function isGameUiActive() {
  return _gameUiQuery.matches
    && typeof currentModeTab !== "undefined"
    && GAME_MODES.indexOf(currentModeTab) !== -1;
}

// ── Déplacement des blocs existants dans les nouveaux onglets/menu ─────────
// Même principe que _registerMobileRelocatable/_placeMobileRelocatablesForViewport
// (controls.js) : le nœud DOM réel voyage entre son emplacement d'origine
// (grand écran / modes hors jeu, disposition inchangée) et son nouvel
// emplacement (onglet Coach/Lignes/Analyse/Coups, popup de modèle, menu "..."),
// jamais dupliqué — la logique (board.js/game_coach_lines.js/game_analysis.js/
// llm_model.js/usage_tokens.js) retrouve ses éléments par id quel que soit
// leur parent réel.
// Tableau (pas un objet) : l'ORDRE compte pour le groupe ciblant
// #board-sticky-wrap (chaque appendChild ajoute en fin de liste — cf.
// _placeRelocatable) — nav, puis barre d'actions/bandeau avant-partie, puis
// les onglets en dernier, pour que "tout ce qui précède l'onglet actif" reste
// fixe avec le plateau (point 1/5) dans le bon ordre visuel.
const GAME_ALWAYS_RELOCATE = [
  ["coach-drawer-panel",  "game-tab-panel-coach"],
  ["game-coach-lines",    "game-tab-panel-lignes"],
  ["game-analysis-panel", "game-tab-panel-analyse"],
  ["historique",          "game-tab-panel-coups"],
  ["review-controls",              "board-sticky-wrap"],
  ["shared-mode-controls",         "board-sticky-wrap"],
  ["mobile-pedagogic-start-slot",  "board-sticky-wrap"],
  ["mobile-opening-start-slot",    "board-sticky-wrap"],
  ["mobile-finale-start-slot",     "board-sticky-wrap"],
  ["mobile-game-idle-msg",         "board-sticky-wrap"],
  ["mobile-game-over-bar",         "board-sticky-wrap"],
  ["game-tab-bar",                 "board-sticky-wrap"],
];

// Pastille de modèle + compteur de jetons (issue #81 point 4) : rejoignent la
// rangée d'en-tête commune (#game-model-popup/#game-menu-usage) dès qu'on est
// sur mobile, quel que soit le mode affiché — contrairement à
// GAME_ALWAYS_RELOCATE ci-dessus (réservé aux 4 modes de partie), placé/
// restauré uniquement selon le seuil <900px (_gameUiQuery), pas selon
// isGameUiActive(). Mêmes id/logique (llm_model.js/usage_tokens.js), aucune
// duplication.
const HEADER_ALWAYS_RELOCATE = [
  ["llm-model-selector",  "game-model-popup"],
  ["usage-tokens-widget", "game-menu-usage"],
];

// Contrôles propres à chaque mode (issue #70 point 8 — choix retenu : le
// menu "...", le plus simple à mettre en œuvre puisqu'un seul emplacement
// suffit pour les quatre modes, contre un habillage variable en tête de
// l'onglet Coach) — un seul bloc à la fois dans #game-menu-mode-extra,
// celui du mode actuellement affiché (currentModeTab, controls.js).
const GAME_MODE_EXTRA = {
  free:      "free-extra-controls",
  pedagogic: "pedagogic-extra-controls",
  opening:   "opening-extra-controls",
  finale:    "finale-extra-controls",
};

let _gameRelocatablesReady = false;
const _gameRelocatableHomes = {};

function _ensureGameRelocatablesRegistered() {
  if (_gameRelocatablesReady) return;
  const ids = GAME_ALWAYS_RELOCATE.map(([id]) => id)
    .concat(HEADER_ALWAYS_RELOCATE.map(([id]) => id))
    .concat(Object.values(GAME_MODE_EXTRA));
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) _gameRelocatableHomes[id] = { homeParent: el.parentElement, homeNextSibling: el.nextSibling };
  });
  _gameRelocatablesReady = true;
}

function _placeRelocatable(id, targetId) {
  const el = document.getElementById(id);
  const target = document.getElementById(targetId);
  if (!el || !target) return;
  if (el.parentElement !== target) target.appendChild(el);
}

function _restoreRelocatable(id) {
  const entry = _gameRelocatableHomes[id];
  const el = document.getElementById(id);
  if (!el || !entry || !entry.homeParent) return;
  if (el.parentElement !== entry.homeParent) entry.homeParent.insertBefore(el, entry.homeNextSibling);
}

// ── Onglets Coach / Lignes / Analyse / Coups (point 1) ─────────────────────
const GAME_TABS = ["coach", "lignes", "analyse", "coups"];
let _currentGameTab = "coach";

function switchGameTab(tabKey) {
  if (GAME_TABS.indexOf(tabKey) === -1) return;
  _currentGameTab = tabKey;
  GAME_TABS.forEach((key) => {
    const btn = document.getElementById(`game-tab-btn-${key}`);
    const panel = document.getElementById(`game-tab-panel-${key}`);
    const isActive = key === tabKey;
    if (btn) {
      btn.classList.toggle("active", isActive);
      if (isActive) btn.classList.remove("has-novelty");
    }
    if (panel) panel.classList.toggle("active", isActive);
  });
  // Issue #81 point 1 : un onglet dont le contenu dépasse la zone visible
  // (ex. Coups sur une longue partie) passe tout de suite au plateau réduit,
  // plutôt que de laisser Alain découvrir après coup qu'il doit défiler.
  if (typeof _autoCompactForOverflow === "function") _autoCompactForOverflow();
}

// Point de nouveauté (point 7) : appelé depuis game_coach_lines.js/
// game_analysis.js quand du contenu neuf arrive — un point discret (non
// cliquable, donc pas en terracotta, cf. .game-tab-dot) apparaît sur l'onglet
// visé s'il n'est pas déjà affiché, et disparaît à son ouverture
// (switchGameTab ci-dessus).
function _gameTabMarkNovelty(tabKey) {
  if (!isGameUiActive()) return;
  if (_currentGameTab === tabKey) return;
  const btn = document.getElementById(`game-tab-btn-${tabKey}`);
  if (btn) btn.classList.add("has-novelty");
}

// ── Pastille de modèle + menu "..." (point 3) ───────────────────────────────
function gameMenuClose() {
  const dd = document.getElementById("game-menu-dropdown");
  const mp = document.getElementById("game-model-popup");
  if (dd) dd.classList.remove("open");
  if (mp) mp.classList.remove("open");
}

function gameMenuToggleDropdown() {
  const dd = document.getElementById("game-menu-dropdown");
  const mp = document.getElementById("game-model-popup");
  if (mp) mp.classList.remove("open");
  if (dd) dd.classList.toggle("open");
}

function gameMenuToggleModelPopup() {
  const dd = document.getElementById("game-menu-dropdown");
  const mp = document.getElementById("game-model-popup");
  if (dd) dd.classList.remove("open");
  if (mp) mp.classList.toggle("open");
}

// Issue #81 point 4 : le menu est désormais accessible dans tous les modes
// sur mobile (pas seulement les 4 modes de partie) — ferme sur un clic
// extérieur dès que la page est en disposition mobile, plutôt que
// isGameUiActive() (gameMenuClose() est un no-op si le menu n'était pas
// ouvert, sans risque à l'appeler plus largement).
document.addEventListener("click", (e) => {
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (!slot || !_gameUiQuery.matches) return;
  if (!slot.contains(e.target)) gameMenuClose();
});

// ── Plateau plus grand : garantie dynamique du contenu visible (issue #71
// point 3) ───────────────────────────────────────────────────────────────
// --bd-size (<style>) plafonne le plateau des modes de partie à 44% de la
// hauteur d'écran, mais additionné à la rangée d'en-tête collée + matériel
// capturé + ligne d'état + #review-controls + #shared-mode-controls (ses 3
// boutons peuvent passer sur 2 lignes selon la largeur d'écran) + les
// onglets Coach/Lignes/Analyse/Coups, cela peut laisser moins des ~180px de
// contenu visible sous les onglets demandés. --bd-size-game-max (consommée
// par --bd-size, <style>) republie en continu la plus grande taille de
// plateau qui laisse ce minimum, mesurée sur le DOM RÉEL (ResizeObserver sur
// #board-sticky-wrap, même principe que --mobile-header-h/scroll-padding-top
// dans controls.js) plutôt que calculée à la main — l'état exact de ce qui
// entoure le plateau varie trop (boutons de démarrage, bannière de fin de
// partie, repli des boutons partagés) pour un simple calc() statique.
// "chrome" (tout ce qui n'est PAS le plateau lui-même dans #board-sticky-wrap)
// est indépendant de la taille du plateau (aucun des éléments alentour ne
// redimensionne avec --bd-size) : pas de boucle de rétroaction instable
// malgré le ResizeObserver qui s'observe lui-même indirectement.
// 170 (borne haute du plateau réduit, point 4) plutôt qu'une valeur plus
// petite encore : sur les plus petits téléphones en pleine partie (boutons
// "Reprendre/Abandonner/Demander l'avis" sur 2 lignes, cf. rapport de
// clôture), satisfaire les deux cibles à la fois (plateau complet ET la
// garantie de contenu visible ci-dessous) n'est pas possible — mieux vaut y
// perdre un peu de cette garantie que de descendre sous la taille du
// plateau RÉDUIT, qui perdrait alors tout son sens (issue #74 point 1 :
// cette garde reste valable quel que soit le réglage Compact/Normal/Grand).
const GAME_BOARD_MIN_SIZE = 170;

// ── Réglage utilisateur "Taille du plateau" (issue #74) ─────────────────────
// Menu "..." des modes de partie mobile — 3 choix simples. SEUL endroit où
// ces 3 pourcentages et leurs garanties associées sont définis (point 3) : ni
// board.css ni index.html ne redéfinissent ces nombres, --bd-size-game-pct
// (posée par _applyGameBoardSizeChoice ci-dessous) et minVisibleBelowTabs
// (consommée par _updateGameBoardMaxSize) sont l'unique chemin par lequel
// ils atteignent le CSS/le calcul de --bd-size-game-max.
//
// minVisibleBelowTabs distinct par préréglage (issue #81 point 2) : avec une
// seule valeur partagée (180px avant cette issue), Compact et Normal
// retombaient quasi systématiquement sur le MÊME plafond mesuré
// (--bd-size-game-max) sur un téléphone courant — la garantie de contenu
// visible écrasait alors le choix explicite d'Alain, qui constatait une
// taille identique pour les deux réglages (rapport de test GSM). Mesuré avec
// Playwright (free_play, 1 coup joué, chrome au-dessus/en dessous du plateau
// ≈350px à 390×750 et 360×640) : 150/100/60px laissent respectivement Compact
// (32%) et Normal (40%) atteindre leur propre pourcentage SANS être clampés
// au même plafond à 390×750, Grand restant toujours le plus grand des trois
// aux deux largeurs. Grand garde la garantie la plus basse (le choix exprès
// d'un plateau plus grand prime sur elle), Compact la plus haute (il a de
// toute façon le moins besoin d'un grand plateau).
const GAME_BOARD_SIZE_PRESETS = {
  compact: { pct: 32, minVisibleBelowTabs: 150 },
  normal:  { pct: 40, minVisibleBelowTabs: 100 },
  grand:   { pct: 52, minVisibleBelowTabs: 60 },
};
const GAME_BOARD_SIZE_DEFAULT = "normal";
// Propre à l'appareil (localStorage, pas de synchronisation compte/serveur) :
// un GSM et un PC n'ont pas le même compromis taille du plateau / place pour
// le chat et les lignes, cf. issue #74 point 2.
const GAME_BOARD_SIZE_STORAGE_KEY = "chesscoach-mobile-board-size";

function _gameBoardSizeLoad() {
  try {
    const stored = window.localStorage.getItem(GAME_BOARD_SIZE_STORAGE_KEY);
    if (stored && GAME_BOARD_SIZE_PRESETS[stored]) return stored;
  } catch (e) {
    // Stockage indisponible (navigation privée stricte, quota, etc.) : le
    // réglage par défaut s'applique, le choix reste actif pour la session en
    // cours (gameBoardSizeSet n'échoue pas pour autant, cf. _gameBoardSizeSave).
  }
  return GAME_BOARD_SIZE_DEFAULT;
}

function _gameBoardSizeSave(key) {
  try {
    window.localStorage.setItem(GAME_BOARD_SIZE_STORAGE_KEY, key);
  } catch (e) {
    // Stockage indisponible : pas de persistance, mais le choix reste
    // appliqué pour la session en cours (_applyGameBoardSizeChoice déjà
    // appelé par gameBoardSizeSet indépendamment de cette sauvegarde).
  }
}

let _gameBoardSizeChoice = _gameBoardSizeLoad();

function _currentGameBoardSizePreset() {
  return GAME_BOARD_SIZE_PRESETS[_gameBoardSizeChoice] || GAME_BOARD_SIZE_PRESETS[GAME_BOARD_SIZE_DEFAULT];
}

// Familles Exercice/Bibliothèque-Éditeur (issue #81 point 4) : même réglage
// Compact/Normal/Grand que GAME_BOARD_SIZE_PRESETS ci-dessus (une seule
// valeur stockée, "commune aux modes"), mais rapporté à la plage de hauteur
// déjà en place pour chacun de ces modes avant cette issue plutôt qu'à celle
// des 4 modes de partie — Normal reproduit exactement l'ancienne valeur fixe
// (30dvh pour l'Exercice, 58dvh pour Bibliothèque/Éditeur) pour qu'activer ce
// réglage ne change rien par défaut. Pas de garantie de contenu visible ici
// (pas d'onglets Coach/Lignes/Analyse/Coups dans ces modes) : un simple
// pourcentage suffit, bordé par la même largeur d'écran qu'avant (calc(100vw
// - 76px) pour l'Exercice qui garde coordonnées/barre d'éval visibles,
// calc(100vw - 52px) pour Bibliothèque/Éditeur qui les masquent, cf. <style>).
const EXERCISE_BOARD_SIZE_PCT = { compact: 22, normal: 30, grand: 38 };
const WIDE_BOARD_SIZE_PCT     = { compact: 46, normal: 58, grand: 68 };

function _applyGameBoardSizeChoice() {
  const key = _gameBoardSizeChoice;
  document.documentElement.style.setProperty("--bd-size-game-pct", `${_currentGameBoardSizePreset().pct}dvh`);
  document.documentElement.style.setProperty("--bd-size-exercise-pct", `${EXERCISE_BOARD_SIZE_PCT[key] || EXERCISE_BOARD_SIZE_PCT[GAME_BOARD_SIZE_DEFAULT]}dvh`);
  document.documentElement.style.setProperty("--bd-size-wide-pct", `${WIDE_BOARD_SIZE_PCT[key] || WIDE_BOARD_SIZE_PCT[GAME_BOARD_SIZE_DEFAULT]}dvh`);
}

function _refreshGameBoardSizeMenuUI() {
  Object.keys(GAME_BOARD_SIZE_PRESETS).forEach((key) => {
    const btn = document.querySelector(`.game-board-size-btn[data-board-size-choice="${key}"]`);
    if (btn) btn.classList.toggle("active", key === _gameBoardSizeChoice);
  });
}

// onclick des 3 boutons "Compact/Normal/Grand" (#game-menu-dropdown,
// index.html) : application immédiate, sans recharger la page (point 2) —
// _updateGameBoardMaxSize doit être rappelée ici même, le ResizeObserver sur
// #board-sticky-wrap (DOMContentLoaded plus bas) ne se redéclenche QUE si la
// taille réelle du plateau change, pas au moment où --bd-size-game-pct est
// posée (c'est justement ce qui va faire varier --bd-size, donc la taille du
// plateau, mais pas avant le prochain reflow).
function gameBoardSizeSet(key) {
  if (!GAME_BOARD_SIZE_PRESETS[key] || key === _gameBoardSizeChoice) return;
  _gameBoardSizeChoice = key;
  _gameBoardSizeSave(key);
  _applyGameBoardSizeChoice();
  _refreshGameBoardSizeMenuUI();
  _updateGameBoardMaxSize();
}

function _updateGameBoardMaxSize() {
  if (!isGameUiActive()) {
    document.documentElement.style.removeProperty("--bd-size-game-max");
    return;
  }
  const wrap = document.getElementById("board-sticky-wrap");
  const board = document.getElementById("board");
  const tabsColumn = document.getElementById("game-tabs-column");
  if (!wrap || !board || !tabsColumn) return;
  // Pas de mesure pendant l'état réduit (point 4) : --bd-size y est de toute
  // façon ignorée (la règle ".board-compact" impose clamp(150px,42vw,170px)
  // indépendamment de --bd-size-game-max), et le "chrome" y est plus petit
  // (matériel masqué) — mesurer ici fausserait la valeur pour le PROCHAIN
  // affichage en plateau complet. Le ResizeObserver ci-dessous se redéclenche
  // de lui-même dès le retour au plateau complet (la hauteur de
  // #board-sticky-wrap change), pas besoin de rattraper la valeur ici.
  if (wrap.classList.contains("board-compact")) return;
  // Issue #77 : pas de remesure non plus pendant l'affichage du bandeau de
  // fin de partie (#mobile-game-over-bar, désormais dans le "chrome below"
  // mesuré ci-dessous, là où cette zone était vide avant l'issue #77) — sinon
  // sa hauteur réelle (texte + 2 boutons, variable selon la longueur du
  // résultat) fait varier --bd-size-game-max au moment même de l'abandon/du
  // mat, donnant l'impression d'un passage en plateau réduit alors que
  // ".board-compact"/_gameBoardSizeChoice ne changent jamais (cause
  // identifiée lors des tests GSM, cf. rapport de clôture — le réglage de
  // taille lui-même n'est jamais modifié, seul le rendu réel du plateau
  // varie). Garde la dernière valeur mesurée PENDANT la partie jusqu'au
  // retour à une nouvelle partie (hideGameOverBanner, qui retire cette classe
  // et redéclenche par ricochet onGameUiRefresh()/cette fonction).
  if (document.body.classList.contains("game-over-active")) return;
  // Tout ce qui n'est PAS le plateau lui-même : au-dessus (rangée d'en-tête
  // collée + matériel capturé du dessus) via board.top, et en dessous
  // (matériel du dessous, ligne d'état, #review-controls,
  // #shared-mode-controls, les 2 "gap" de #app de part et d'autre de
  // #board-column — désormais vide sur mobile en mode jeu, cf. GAME_ALWAYS_
  // RELOCATE plus haut — jusqu'à #game-tabs-column) via la distance entre le
  // bas du plateau et le haut de #game-tabs-column. Mesuré directement sur
  // ces deux rectangles plutôt que reconstitué à la main (gaps/marges
  // dispersés dans plusieurs fichiers CSS), pour rester exact quel que soit
  // ce qui change autour du plateau.
  const boardRect = board.getBoundingClientRect();
  const chromeAbove = boardRect.top;
  const chromeBelow = tabsColumn.getBoundingClientRect().top - boardRect.bottom;
  const max = window.innerHeight - chromeAbove - chromeBelow - _currentGameBoardSizePreset().minVisibleBelowTabs;
  document.documentElement.style.setProperty("--bd-size-game-max", `${Math.max(GAME_BOARD_MIN_SIZE, Math.floor(max))}px`);
}

// ── Camp jouable en cours (partagé par le point 4 et la barre d'actions) ───
function _isCurrentGameRunning() {
  const tab = typeof currentModeTab !== "undefined" ? currentModeTab : null;
  const runningMap = {
    free:      typeof freePlayActive !== "undefined" && freePlayActive && !freeGameOver,
    pedagogic: typeof pedagogicActive !== "undefined" && pedagogicActive && !pedagogicGameOver,
    opening:   typeof openingActive !== "undefined" && openingActive && !openingGameOver,
    finale:    typeof finaleActive !== "undefined" && finaleActive && !finaleGameOver,
  };
  return !!runningMap[tab];
}

// ── Plateau réduit au défilement (issue #70 point 5, refondu #71 point 4) ──
// Le plateau complet (+ les deux barres de boutons, via #board-full-view)
// rétrécit (--bd-size local, cf. <style>, même nœud DOM, même rendu) quand
// la zone à onglets défile ou que le champ de question a le focus (clavier
// ouvert) — jamais pendant la lecture/preview d'une ligne du coach (le
// plateau doit alors rester affiché en grand, point 6 de l'issue #70), et
// jamais tant qu'aucune partie n'est en cours ou que la page est tout en
// haut (issue #71 point 2 : sans ce garde-fou, arriver dans un mode de
// partie — page pas encore défilée, avant tout coup — pouvait déclencher
// l'état réduit avant même d'avoir vu le plateau complet une seule fois).
// Retour au plateau complet en tapant le plateau réduit (boardCompactExpand
// ci-dessous, remonte en haut de page et enlève le focus du champ) ou en
// remontant en haut par un autre moyen (le scroll y est réévalué en
// continu).
const BOARD_COMPACT_SCROLL_THRESHOLD = 24;

function _linePlaybackActive() {
  return (typeof gameCoachLinesPlayingIdx !== "undefined" && gameCoachLinesPlayingIdx !== null)
    || (typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive);
}

function _updateBoardCompactState() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (!wrap) return;
  if (!isGameUiActive() || _linePlaybackActive() || !_isCurrentGameRunning()) {
    wrap.classList.remove("board-compact");
    return;
  }
  const scrollY = window.scrollY;
  if (scrollY <= 0) {
    wrap.classList.remove("board-compact");
    return;
  }
  const coachInput = document.getElementById("coach-input");
  const focused = !!(coachInput && document.activeElement === coachInput);
  const scrolled = scrollY > BOARD_COMPACT_SCROLL_THRESHOLD;
  wrap.classList.toggle("board-compact", focused || scrolled);
}

// Contenu de l'onglet actif plus haut que la zone visible restante (issue
// #81 point 1) — mesuré depuis sa position RÉELLE à l'écran (scroll courant
// compris), donc vrai aussi bien tout en haut de page (plateau encore
// complet) qu'après défilement. Marge de tolérance (BOARD_COMPACT_SCROLL_
// THRESHOLD, déjà utilisé pour le déclenchement au scroll ci-dessous) : la
// garantie de contenu visible sous les onglets (minVisibleBelowTabs,
// 60-150px selon le préréglage) est déjà volontairement étroite — sans cette
// marge, le simple message d'état vide ("Aucune ligne pour l'instant...",
// mesuré à ~112px) dépasserait de quelques px et basculerait le plateau en
// réduit dès l'ouverture de l'onglet, avant même d'avoir un vrai contenu à
// lire (repéré avec Playwright, cf. rapport de clôture).
function _activeTabContentOverflows() {
  const panel = document.querySelector(".game-tab-panel.active");
  if (!panel) return false;
  return (panel.getBoundingClientRect().top + panel.scrollHeight) > (window.innerHeight + BOARD_COMPACT_SCROLL_THRESHOLD);
}

// Déclenche le plateau réduit quand le contenu de l'onglet actif déborde de
// l'écran (point 1) — appelée seulement aux points de coupure concernés
// (ouverture d'un onglet, arrivée d'une réponse du coach), jamais depuis le
// scroll/focus ci-dessus : ADDITIVE uniquement (ne referme jamais le plateau
// réduit tout seul), pour ne pas annuler un retour au plateau complet
// explicite (boardCompactExpand) si le contenu déborde toujours juste après.
function _autoCompactForOverflow() {
  if (!isGameUiActive() || _linePlaybackActive() || !_isCurrentGameRunning()) return;
  const wrap = document.getElementById("board-sticky-wrap");
  if (!wrap) return;
  if (_activeTabContentOverflows()) wrap.classList.add("board-compact");
}

// Retour au plateau complet forcé (point 1 : coup joué) — plus léger que
// boardCompactExpand() ci-dessous, ne déplace pas le défilement ni le focus
// (jouer un coup ne doit pas faire sauter la page, seulement redonner sa
// taille normale au plateau).
function _forceBoardFull() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (wrap) wrap.classList.remove("board-compact");
}

function boardCompactExpand() {
  if (document.activeElement && typeof document.activeElement.blur === "function") document.activeElement.blur();
  if (typeof window.scrollTo === "function") window.scrollTo({ top: 0, behavior: "smooth" });
  _updateBoardCompactState();
}

// Appelée depuis renderHistory() (board.js, déjà invoquée après chaque coup,
// tous modes confondus) — un coup réellement joué (le compte de coups
// augmente) redonne sa taille complète au plateau (point 1), même si le
// contenu d'un onglet encore affiché déborde toujours de l'écran (ex. rejouer
// juste après avoir consulté l'onglet Coups d'une longue partie).
let _lastLiveMoveCount = 0;
function _mobileGameOnMoveCountChanged(count) {
  if (isGameUiActive() && count > _lastLiveMoveCount) _forceBoardFull();
  _lastLiveMoveCount = count;
}

// Appelée depuis _coachRenderBubble() (board.js) à l'arrivée de chaque
// réponse du coach (point 1) — une réponse longue mérite la place de lecture
// maximale, même si Alain n'a pas encore défilé ni touché le plateau réduit.
function _mobileGameOnCoachMessage() {
  if (typeof _autoCompactForOverflow === "function") _autoCompactForOverflow();
}

// onclick de #board-full-view (issue #71 point 4) : n'agit qu'en état
// réduit (#board-sticky-wrap.board-compact) — les clics sur une case du
// plateau complet (déplacement de pièce) ne doivent jamais être interceptés.
function _boardFullViewClick() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (wrap && wrap.classList.contains("board-compact")) boardCompactExpand();
}

// ── Barre d'actions / bandeau avant-partie (point 4) ────────────────────────
// Pédagogique/ouverture : choix de camp (deux gros boutons, cf.
// #pedagogic-start-buttons/#opening-start-buttons, remplis par
// placePedagogicStartButtonsForViewport/placeOpeningStartButtonsForViewport —
// pedagogic.js/opening.js). Partie libre (les deux camps sont joués
// librement) et travail de finales (le camp est fixé par la position-type,
// "camps inversés" en tient lieu) n'ont pas ce choix : #mobile-game-idle-msg
// les remplace tant qu'aucune partie n'est en cours (écart documenté dans le
// rapport de clôture). Le bandeau de résultat (#game-over-banner) remplace
// le tout en fin de partie (classe "game-over-active" posée par
// showGameOverBanner/hideGameOverBanner, board.js — cf. <style>).
function _updateActionBarState() {
  const shared = document.getElementById("shared-mode-controls");
  const idle = document.getElementById("mobile-game-idle-msg");
  if (!shared || !idle) return;
  const tab = typeof currentModeTab !== "undefined" ? currentModeTab : null;
  const running = _isCurrentGameRunning();
  // finale (issue #77 point 6) : rejoint pedagogic/opening — son propre
  // sélecteur de position-type (#finale-picker-row) remplace désormais aussi
  // #mobile-game-idle-msg, qui ne reste la seule invite que pour partie libre
  // (écart documenté, inchangé).
  const hasOwnStartSlot = tab === "pedagogic" || tab === "opening" || tab === "finale";
  if (running) {
    shared.style.display = "";
    idle.classList.remove("show");
  } else if (hasOwnStartSlot) {
    // Boutons déjà positionnés par pedagogic.js/opening.js/finales.js dans
    // #mobile-pedagogic-start-slot/#mobile-opening-start-slot/
    // #mobile-finale-start-slot.
    shared.style.display = "none";
    idle.classList.remove("show");
  } else {
    shared.style.display = "none";
    idle.classList.add("show");
  }
}

// ── "Nouvelle partie" du bandeau de fin de partie (issue #77 point 4) ──────
// Ramène l'écran à l'état "avant la partie" du mode actif (boutons "Jouer les
// Blancs/Noirs" ou message d'invite à utiliser le menu "...", point 4), sans
// recharger la page. Jusqu'ici aucun moyen n'existait sur mobile une fois une
// partie terminée : la classe "game-over-active" masque #shared-mode-controls/
// .mode-start-slot/#mobile-game-idle-msg (règle <style> ci-dessus) tant
// qu'elle n'est pas retirée, et rien ne l'enlevait avant le démarrage effectif
// d'une nouvelle partie — verrou bloquant repéré lors des tests GSM (rapport
// de clôture). resetBoardToNeutral() (board.js, jusqu'ici réservé à l'éditeur
// de position/l'exercice, cf. editor.js/exercise.js) remet un plateau vierge
// ET appelle hideGameOverBanner(), ce qui lève ce verrou — chaque mode garde
// par ailleurs son propre drapeau "xxxGameOver" à true (aucun besoin d'y
// toucher : _isCurrentGameRunning() ci-dessus le traite déjà comme "aucune
// partie en cours", c'est justement ce qui faisait apparaître ce bandeau).
// Démarrer effectivement une nouvelle partie (clic sur "Jouer les Blancs/
// Noirs" ou équivalent) redéclenche normalement coachNewSegment("Nouvelle
// partie")/la remise à zéro de l'historique du coach, comme pour toute
// nouvelle partie (inchangé, chaque startXxxGame() le fait déjà).
function mobileNewGameFromBanner() {
  // Efface l'instance de partie terminée du mode actif — sinon
  // updateGameStatusLine() (board.js, appelée par renderHistory() plus bas)
  // continue de lire activeModeGameState() dessus et affiche encore "Coup
  // N · <dernier coup>" de la partie qui vient de se terminer sous le
  // plateau pourtant redevenu vierge.
  const mode = typeof activeMode !== "undefined" ? activeMode : null;
  if (mode === "free")      freeGame      = null;
  if (mode === "pedagogic") pedagogicGame = null;
  if (mode === "opening")   openingGame   = null;
  if (mode === "finale")    finaleGame    = null;
  if (typeof resetBoardToNeutral === "function") resetBoardToNeutral();
  if (typeof renderHistory === "function") renderHistory();
  // Issue #77 point 3 : le rapport d'analyse de la partie qui vient de se
  // terminer n'a plus de sens une fois revenu à l'état avant-partie.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
  if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
  if (typeof placeFinaleStartButtonsForViewport === "function") placeFinaleStartButtonsForViewport();
  onGameUiRefresh();
}

// ── Contrôles de partie hors contexte (issue #71 point 6) ──────────────────
// #shared-mode-controls ("Contrôles du mode actif") vit en dehors des
// onglets (issue #15) pour rester utilisable en consultant un autre onglet
// pendant qu'un mode interactif tourne en arrière-plan — utile sur grand
// écran, mais prêtait à confusion sur mobile en Bibliothèque/Exercice/
// Éditeur (activeMode pouvait encore être un mode de partie déjà quitté des
// yeux : contrôles de la partie pédagogique visibles en Bibliothèque, partie
// démarrable sans bouton Abandonner à l'écran, cf. rapport signalé par
// Alain). N'influence jamais le CONTENU du bandeau (toujours piloté par
// activeMode, updateSharedControlBar) : seulement sa visibilité sur mobile,
// et seulement en cas de décalage réel entre activeMode et l'onglet
// consulté — exercice/éditeur gardent leurs propres contrôles partagés
// (reprendre/abandonner/demander l'avis du coach) quand ils sont eux-mêmes
// activeMode.
function _updateModeControlsMismatch() {
  const tab = typeof currentModeTab !== "undefined" ? currentModeTab : null;
  const mismatch = !!activeMode && activeMode !== tab
    && (tab === "library" || tab === "exercise" || tab === "editor");
  document.body.classList.toggle("mode-controls-mismatch", mismatch);
}

// ── Rafraîchissement global (appelé depuis controls.js) ─────────────────────
function onGameUiRefresh() {
  _ensureGameRelocatablesRegistered();
  _updateModeControlsMismatch();

  // Issue #70 point 4 : placePedagogicStartButtonsForViewport (pedagogic.js)/
  // placeOpeningStartButtonsForViewport (opening.js) ne sont normalement
  // appelées que par leur propre fichier (démarrage/abandon/reprise de
  // partie, franchissement du seuil mobile) — ce rafraîchissement central
  // est le seul point qui sait aussi réagir à un simple changement d'onglet
  // de mode (switchModeTab), qu'elles ignorent sinon. Issue #71 : déplacées
  // AVANT le "if (!active) return" ci-dessous — sinon, en quittant un mode
  // de partie vers Bibliothèque/Exercice/Éditeur, ces fonctions n'étaient
  // plus jamais rappelées et les boutons "Jouer les Blancs/Noirs" restaient
  // coincés dans #mobile-pedagogic-start-slot/#mobile-opening-start-slot
  // (visibles sur tous les onglets via #board-column, cf. rapport signalé
  // par Alain) alors que leur propre logique (onPedagogicTab/onOpeningTab)
  // sait déjà correctement les rapatrier dès qu'on n'est plus sur leur
  // onglet.
  if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
  if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
  if (typeof placeFinaleStartButtonsForViewport === "function") placeFinaleStartButtonsForViewport();

  // Pastille de modèle + compteur de jetons (issue #81 point 4) : rejoignent
  // la rangée d'en-tête commune dès qu'on est sur mobile, quel que soit le
  // mode — indépendant de isGameUiActive() ci-dessous (HEADER_ALWAYS_RELOCATE,
  // contrairement à GAME_ALWAYS_RELOCATE, n'est jamais réservé aux 4 modes de
  // partie).
  const mobile = _gameUiQuery.matches;
  HEADER_ALWAYS_RELOCATE.forEach(([id, target]) => {
    if (mobile) _placeRelocatable(id, target); else _restoreRelocatable(id);
  });

  // Issue #81 point 3 : état (grisé + explication) du bouton "Analyser cette
  // partie" — recalculé à chaque rafraîchissement (mode/onglet/coup/fin de
  // partie), que l'écran de jeu mobile soit actif ou non (game_analysis.js).
  if (typeof _updateGameAnalysisAvailability === "function") _updateGameAnalysisAvailability();

  const active = isGameUiActive();
  document.body.classList.toggle("mobile-game-active", active);
  // Issue #71 point 3 : plateau élargi de Bibliothèque/Revue PGN et de
  // l'éditeur de position (cf. règle ".mobile-wide-board", templates/
  // index.html) — mode exercice volontairement exclu.
  document.body.classList.toggle(
    "mobile-wide-board",
    !active && (currentModeTab === "library" || currentModeTab === "editor")
  );
  // Issue #81 point 4 : famille de taille de plateau propre au mode Exercice
  // (coordonnées/barre d'éval gardées visibles, contrairement à
  // "mobile-wide-board" ci-dessus).
  document.body.classList.toggle(
    "mobile-size-exercise-active",
    !active && currentModeTab === "exercise"
  );
  // Issue #81 point 5 : la collection de parties PGN/l'import/le programme
  // d'entraînement (#mobile-bottom-slot) et le panneau d'analyse de partie
  // (#mobile-analysis-slot) ne concernent que la Bibliothèque/Revue PGN —
  // posée pour tous les autres onglets (Exercice/Éditeur ; les 4 modes de
  // partie ont déjà leur propre règle "body.mobile-game-active", <style>).
  document.body.classList.toggle("mobile-non-library-tab", currentModeTab !== "library");

  if (!active) {
    gameMenuClose();
    GAME_ALWAYS_RELOCATE.forEach(([id]) => _restoreRelocatable(id));
    Object.values(GAME_MODE_EXTRA).forEach(_restoreRelocatable);
    const wrap = document.getElementById("board-sticky-wrap");
    if (wrap) wrap.classList.remove("board-compact");
    // Issue #71 point 6 : _updateActionBarState() (plus bas) ne tourne que
    // pour les 4 modes de partie — sans ce reset, #shared-mode-controls
    // garderait le style.display "none" posé par son dernier passage là-bas
    // (ex. un mode sans partie en cours) même en arrivant sur Exercice/
    // Éditeur, où il doit rester utilisable normalement quand il leur
    // appartient (activeMode === l'onglet consulté). La classe
    // "mode-controls-mismatch" (_updateModeControlsMismatch ci-dessus,
    // <style>) reste seule responsable de le masquer quand son contenu
    // appartient à un AUTRE mode.
    const shared = document.getElementById("shared-mode-controls");
    if (shared) shared.style.display = "";
    return;
  }

  GAME_ALWAYS_RELOCATE.forEach(([id, target]) => _placeRelocatable(id, target));

  const tab = currentModeTab;
  Object.entries(GAME_MODE_EXTRA).forEach(([modeKey, id]) => {
    if (modeKey === tab) _placeRelocatable(id, "game-menu-mode-extra");
    else _restoreRelocatable(id);
  });

  switchGameTab(_currentGameTab);
  _updateActionBarState();
  _updateBoardCompactState();
  _updateGameBoardMaxSize();
}

document.addEventListener("DOMContentLoaded", () => {
  // Issue #74 : posée avant onGameUiRefresh() pour que la toute première
  // mesure de _updateGameBoardMaxSize (appelée par onGameUiRefresh) tienne
  // déjà compte du réglage persisté (sinon un choix Compact/Grand enregistré
  // lors d'une session précédente ne s'appliquerait qu'après un second
  // rafraîchissement).
  _applyGameBoardSizeChoice();
  _refreshGameBoardSizeMenuUI();
  onGameUiRefresh();

  const wrap = document.getElementById("board-sticky-wrap");
  if (wrap && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(_updateGameBoardMaxSize).observe(wrap);
  }
  window.addEventListener("resize", _updateGameBoardMaxSize);

  _gameUiQuery.addEventListener("change", () => onGameUiRefresh());
  window.addEventListener("scroll", _updateBoardCompactState, { passive: true });

  const coachInput = document.getElementById("coach-input");
  if (coachInput) {
    coachInput.addEventListener("focus", _updateBoardCompactState);
    coachInput.addEventListener("blur", () => {
      // Laisse le clavier virtuel se refermer (redimensionnement de la
      // fenêtre) avant de réévaluer, sinon window.scrollY peut encore
      // refléter un instant l'état "clavier ouvert".
      setTimeout(_updateBoardCompactState, 50);
    });
  }
});
