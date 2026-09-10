/*
 * controls.js — ChessCoach (issue #15)
 *
 * État centralisé du "mode actif" (aucun mode / partie libre / pédagogique /
 * ouverture / finale / exercice — un seul actif à la fois) et barre de
 * contrôle mutualisée qui agit dessus. Les boutons "Reprendre mon coup" /
 * "Abandonner" / "Demander l'avis du coach" et la case "Commenter chaque
 * coup", auparavant dupliqués dans chaque panneau (issue #10), redirigent
 * ici vers les fonctions déjà existantes de chaque mode
 * (abandon.../reprendre.../coachOnDemand des fichiers free_play.js/
 * pedagogic.js/opening.js/finales.js/exercise.js) plutôt que d'être récrites.
 *
 * Sert aussi de point d'accès unique à l'état du mode actif pour :
 *   - coachBuildContext() (board.js), pour que le chat libre du coach
 *     connaisse la position/le camp du mode en cours (issue #15 point 3) ;
 *   - renderHistory() (board.js), pour peupler l'historique des coups
 *     pendant une partie interactive plutôt que seulement en revue PGN
 *     (issue #15 point 4).
 *
 * Chargé en dernier (après tous les fichiers de mode) dans templates/
 * index.html — les fonctions ci-dessous ne sont invoquées qu'au clic, une
 * fois tous les scripts de la page chargés, mais le placement en fin de
 * liste garde la lecture du fichier simple.
 */

let activeMode = null; // null | "free" | "pedagogic" | "opening" | "finale" | "exercise" | "editor"

const MODE_CAPS = {
  free:      { abandon: () => abandonFreeGame(),         reprendre: null,                            askCoach: null,                       hasComment: false },
  pedagogic: { abandon: () => abandonPedagogicGame(),     reprendre: () => reprendrePedagogicCoup(),  askCoach: () => askPedagogicCoach(),  hasComment: true  },
  opening:   { abandon: () => abandonOpeningGame(),       reprendre: () => reprendreOpeningCoup(),    askCoach: () => askOpeningCoach(),    hasComment: true  },
  finale:    { abandon: () => abandonFinaleGame(),        reprendre: () => reprendreFinaleCoup(),     askCoach: () => askFinaleCoach(),     hasComment: true  },
  exercise:  { abandon: null,                             reprendre: () => reprendreExerciceCoup(),   askCoach: () => askExerciseCoach(),   hasComment: false },
  // Éditeur de position (issue #16) : pas de partie jouée, donc pas de
  // "reprendre mon coup" ni de coach à la demande — juste un moyen de
  // quitter le panneau via le bouton "Abandonner" mutualisé.
  editor:    { abandon: () => abandonPositionEditor(),    reprendre: null,                            askCoach: null,                       hasComment: false },
};

const MODE_LABELS = {
  free:      "Partie libre en cours.",
  pedagogic: "Partie pédagogique en cours.",
  opening:   "Travail d'ouverture en cours.",
  finale:    "Travail de finales en cours.",
  exercise:  "Exercice en cours.",
  editor:    "Éditeur de position actif.",
};

function setActiveMode(mode) {
  activeMode = mode;
  updateSharedControlBar();
  updateReviewControlsEnabled();
  renderHistory(reviewIdx);
}

// ── Onglets par mode (issue #23) ────────────────────────────────────────────
// Remplace l'empilement vertical des panneaux spécifiques à chaque mode :
// un seul panneau de contrôles visible à la fois (celui de l'onglet cliqué).
// Naviguer entre onglets est de la pure consultation — ne passe jamais par
// ensureModeSwitchClean ci-dessous, qui ne s'exécute qu'au moment où un
// panneau démarre effectivement une nouvelle partie/exercice/revue.
const MODE_TABS = ["library", "free", "pedagogic", "opening", "finale", "exercise", "editor"];
let currentModeTab = "library";

function switchModeTab(tabKey) {
  if (MODE_TABS.indexOf(tabKey) === -1) return;
  currentModeTab = tabKey;
  MODE_TABS.forEach((key) => {
    const btn   = document.getElementById(`tab-btn-${key}`);
    const panel = document.getElementById(`tab-panel-${key}`);
    const isActive = key === tabKey;
    if (btn)   btn.classList.toggle("active", isActive);
    if (panel) panel.classList.toggle("active", isActive);
  });
}

// ── Bascule propre entre modes (issue #23) ──────────────────────────────────
// Si un mode interactif est déjà actif (activeMode) et qu'un autre onglet
// démarre une nouvelle partie/exercice/revue, termine proprement l'ancien
// d'abord — réutilise les fonctions abandon* déjà existantes de chaque
// fichier de mode (abandonExerciseGame étant le seul ajout, cf. exercise.js,
// exercise n'ayant jusqu'ici aucun état serveur à abandonner) — pour éviter
// deux modes "actifs" en même temps. "library" représente la revue de
// bibliothèque/PGN, qui ne fait pas partie de MODE_CAPS/activeMode.
const MODE_SWITCH_CLEANUP = {
  free:      () => abandonFreeGame(),
  pedagogic: () => abandonPedagogicGame(),
  opening:   () => abandonOpeningGame(),
  finale:    () => abandonFinaleGame(),
  exercise:  () => abandonExerciseGame(),
  editor:    () => abandonPositionEditor(),
};

function ensureModeSwitchClean(newMode) {
  if (!activeMode || activeMode === newMode) return;
  const cleanup = MODE_SWITCH_CLEANUP[activeMode];
  if (cleanup) cleanup();
}

// ── Désactivation des boutons de revue hors contexte (issue #23) ───────────
// Précédent/Suivant/Retourner/Meilleur coup n'ont de sens qu'en revue de
// bibliothèque (activeMode null) — dès qu'un mode interactif tourne, ils
// sont grisés plutôt que de rester cliquables sans effet cohérent.
function updateReviewControlsEnabled() {
  const disabled = !!activeMode;
  ["review-prev-btn", "review-next-btn", "review-flip-btn", "review-bestmove-btn"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = disabled;
  });
}

function updateSharedControlBar() {
  const caps = MODE_CAPS[activeMode] || null;
  const reprendreBtn = document.getElementById("shared-reprendre-btn");
  const abandonBtn   = document.getElementById("shared-abandon-btn");
  const commentRow   = document.getElementById("shared-comment-row");
  const askCoachBtn  = document.getElementById("shared-ask-coach-btn");
  const statusEl     = document.getElementById("shared-mode-status");

  if (reprendreBtn) reprendreBtn.style.display = caps && caps.reprendre  ? "" : "none";
  if (abandonBtn)   abandonBtn.style.display   = caps && caps.abandon   ? "" : "none";
  if (commentRow)   commentRow.style.display   = caps && caps.hasComment ? "" : "none";
  if (askCoachBtn)  askCoachBtn.style.display  = caps && caps.askCoach  ? "" : "none";
  if (statusEl) statusEl.textContent = activeMode ? MODE_LABELS[activeMode] : "Aucun mode interactif actif.";
}

function sharedReprendreCoup() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.reprendre) caps.reprendre();
}

function sharedAbandonMode() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.abandon) caps.abandon();
}

function sharedAskCoach() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.askCoach) caps.askCoach();
}

// ── État de la partie du mode actif (chat libre + historique des coups) ────

function _activeModeGameInstance() {
  switch (activeMode) {
    case "free":      return freeGame;
    case "pedagogic": return pedagogicGame;
    case "opening":   return openingGame;
    case "finale":    return finaleGame;
    case "exercise":  return exerciseGame;
    default:          return null;
  }
}

function _activeModeCampAlain() {
  switch (activeMode) {
    case "pedagogic": return pedagogicCampAlain;
    case "opening":   return openingCampAlain;
    case "finale":    return finaleCampAlain;
    case "exercise":  return exerciseCampAlain;
    default:          return null;
  }
}

function activeModeGameState() {
  const game = _activeModeGameInstance();
  if (!game) return null;
  return { fen: game.fen(), campAlain: _activeModeCampAlain() };
}

function getActiveModeMoves() {
  const game = _activeModeGameInstance();
  if (!game) return null;
  return game.history({ verbose: true }).map((m) => ({
    san: m.san,
    uci: m.from + m.to + (m.promotion || ""),
    color: m.color === "w" ? "white" : "black",
    qualite: "bon",
  }));
}

// ── Extraire le FEN de la position affichée (issue #21) ────────────────────
// Mutualisé ici plutôt que dupliqué par mode : réutilise activeModeGameState()
// ci-dessus pour un mode interactif en cours, ou reviewFens/reviewIdx (revue
// PGN, board.js) sinon — même logique de repli que coachBuildContext(). Le
// mode éditeur (pas de partie chess.js) construit son FEN autrement
// (editorBuildFen(), editor.js), d'où le cas particulier.

function extraireFen() {
  const statusEl = document.getElementById("fen-extract-status");
  let fen = null;
  if (activeMode === "editor" && typeof editorBuildFen === "function") {
    fen = editorBuildFen();
  } else if (activeMode) {
    const state = activeModeGameState();
    if (state && state.fen) fen = state.fen;
  }
  if (!fen) fen = reviewFens[reviewIdx] || null;

  if (!fen) {
    if (statusEl) statusEl.textContent = "Aucune position affichée.";
    return;
  }
  if (statusEl) statusEl.textContent = fen;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(fen).catch(() => {});
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateSharedControlBar();
  updateReviewControlsEnabled();
  switchModeTab("library");
});
