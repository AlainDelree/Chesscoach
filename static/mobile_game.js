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
  ["llm-model-selector",  "game-model-popup"],
  ["usage-tokens-widget", "game-menu-usage"],
  ["review-controls",              "board-sticky-wrap"],
  ["shared-mode-controls",         "board-sticky-wrap"],
  ["mobile-pedagogic-start-slot",  "board-sticky-wrap"],
  ["mobile-opening-start-slot",    "board-sticky-wrap"],
  ["mobile-game-idle-msg",         "board-sticky-wrap"],
  ["game-tab-bar",                 "board-sticky-wrap"],
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
  const ids = GAME_ALWAYS_RELOCATE.map(([id]) => id).concat(Object.values(GAME_MODE_EXTRA));
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

document.addEventListener("click", (e) => {
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (!slot || !isGameUiActive()) return;
  if (!slot.contains(e.target)) gameMenuClose();
});

// ── Bande compacte du plateau (point 5) ─────────────────────────────────────
// Le plateau complet (+ les deux barres de boutons, via #board-full-view) est
// remplacé par une bande d'état (#board-compact-strip) quand la zone à
// onglets défile ou que le champ de question a le focus (clavier ouvert) —
// jamais pendant la lecture/preview d'une ligne du coach (le plateau doit
// alors rester affiché en grand, point 6). Retour au plateau complet en
// tapant la bande (boardCompactExpand ci-dessous, remonte en haut de page et
// enlève le focus du champ) ou en remontant en haut par un autre moyen (le
// scroll y est réévalué en continu).
const BOARD_COMPACT_SCROLL_THRESHOLD = 24;

function _linePlaybackActive() {
  return (typeof gameCoachLinesPlayingIdx !== "undefined" && gameCoachLinesPlayingIdx !== null)
    || (typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive);
}

function _updateBoardCompactState() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (!wrap) return;
  if (!isGameUiActive() || _linePlaybackActive()) {
    wrap.classList.remove("board-compact");
    return;
  }
  const coachInput = document.getElementById("coach-input");
  const focused = !!(coachInput && document.activeElement === coachInput);
  const scrolled = window.scrollY > BOARD_COMPACT_SCROLL_THRESHOLD;
  wrap.classList.toggle("board-compact", focused || scrolled);
}

function boardCompactExpand() {
  if (document.activeElement && typeof document.activeElement.blur === "function") document.activeElement.blur();
  if (typeof window.scrollTo === "function") window.scrollTo({ top: 0, behavior: "smooth" });
  _updateBoardCompactState();
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
  const runningMap = {
    free:      typeof freePlayActive !== "undefined" && freePlayActive && !freeGameOver,
    pedagogic: typeof pedagogicActive !== "undefined" && pedagogicActive && !pedagogicGameOver,
    opening:   typeof openingActive !== "undefined" && openingActive && !openingGameOver,
    finale:    typeof finaleActive !== "undefined" && finaleActive && !finaleGameOver,
  };
  const running = !!runningMap[tab];
  const hasColorChoice = tab === "pedagogic" || tab === "opening";
  if (running) {
    shared.style.display = "";
    idle.classList.remove("show");
  } else if (hasColorChoice) {
    // Boutons déjà positionnés par pedagogic.js/opening.js dans
    // #mobile-pedagogic-start-slot/#mobile-opening-start-slot.
    shared.style.display = "none";
    idle.classList.remove("show");
  } else {
    shared.style.display = "none";
    idle.classList.add("show");
  }
}

// ── Rafraîchissement global (appelé depuis controls.js) ─────────────────────
function onGameUiRefresh() {
  _ensureGameRelocatablesRegistered();
  const active = isGameUiActive();
  document.body.classList.toggle("mobile-game-active", active);

  if (!active) {
    gameMenuClose();
    GAME_ALWAYS_RELOCATE.forEach(([id]) => _restoreRelocatable(id));
    Object.values(GAME_MODE_EXTRA).forEach(_restoreRelocatable);
    const wrap = document.getElementById("board-sticky-wrap");
    if (wrap) wrap.classList.remove("board-compact");
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

  // Issue #70 point 4 : placePedagogicStartButtonsForViewport (pedagogic.js)/
  // placeOpeningStartButtonsForViewport (opening.js) ne sont normalement
  // appelées que par leur propre fichier (démarrage/abandon/reprise de
  // partie, franchissement du seuil mobile) — ce rafraîchissement central
  // est le seul point qui sait aussi réagir à un simple changement d'onglet
  // de mode (switchModeTab), qu'elles ignorent sinon.
  if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
  if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
}

document.addEventListener("DOMContentLoaded", () => {
  onGameUiRefresh();

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
