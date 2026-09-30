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

// askCoachAvailable (issue #65 point 5) : reflète au plus près la condition
// de garde de la fonction askCoach correspondante (askFreeCoach and co,
// fichiers de mode), pour que le bouton mutualisé "Demander l'avis du coach"
// soit désactivé et grisé (bouton HTML natif, cf. la règle générale
// "button:disabled { opacity:0.5 }") dès qu'un clic serait un no-op silencieux
// — le cas signalé par Alain (partie terminée ou abandonnée) mais aussi tant
// qu'aucune partie n'est démarrée. Simplification assumée : n'inclut pas les
// courtes fenêtres "*Waiting" (coup adverse en cours de traitement, ~1s) —
// cf. rapport de clôture, limite documentée plutôt que corrigée ici.
const MODE_CAPS = {
  free:      { abandon: () => abandonFreeGame(),         reprendre: null,                            askCoach: () => askFreeCoach(),       askCoachAvailable: () => freePlayActive && !!freeGame && !freeGameOver,           hasComment: false },
  pedagogic: { abandon: () => abandonPedagogicGame(),     reprendre: () => reprendrePedagogicCoup(),  askCoach: () => askPedagogicCoach(),  askCoachAvailable: () => pedagogicActive && !!pedagogicGame && !pedagogicGameOver, hasComment: true  },
  opening:   { abandon: () => abandonOpeningGame(),       reprendre: () => reprendreOpeningCoup(),    askCoach: () => askOpeningCoach(),    askCoachAvailable: () => openingActive && !!openingGame && !openingGameOver,       hasComment: true  },
  finale:    { abandon: () => abandonFinaleGame(),        reprendre: () => reprendreFinaleCoup(),     askCoach: () => askFinaleCoach(),     askCoachAvailable: () => finaleActive && !!finaleGame && !finaleGameOver,          hasComment: true  },
  exercise:  { abandon: null,                             reprendre: () => reprendreExerciceCoup(),   askCoach: () => askExerciseCoach(),   askCoachAvailable: () => !!exerciseGame,                                          hasComment: false },
  // Éditeur de position (issue #16) : pas de partie jouée, donc pas de
  // "reprendre mon coup" ni de coach à la demande — juste un moyen de
  // quitter le panneau via le bouton "Abandonner" mutualisé.
  editor:    { abandon: () => abandonPositionEditor(),    reprendre: null,                            askCoach: null,                       askCoachAvailable: null,                                                           hasComment: false },
};

// Phrase affichée sous les boutons du mode actif (issue #65 point 5) — ce
// que fait concrètement "Demander l'avis du coach" dans ce mode, pour qu'il
// ne reste plus un bouton "mystère" quand il est grisé. Même texte pour
// pedagogic/opening/finale (même mécanique : un commentaire ponctuel de la
// position, hors case "Commenter chaque coup").
const MODE_ASK_COACH_HELP = {
  free:      "Demande au coach un commentaire ponctuel sur la position affichée, sans jouer de coup à sa place.",
  pedagogic: "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  opening:   "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  finale:    "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  exercise:  "Demande un commentaire du coach sur la position affichée, à tout moment de l'exercice (avant ou après le verdict).",
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
  // Masque immédiatement le tableau "Lignes du coach" des modes de partie/
  // revue (issue #68) au passage vers exercice/éditeur, même si des lignes
  // restaient affichées d'un mode précédent pas encore réinitialisé.
  if (typeof renderGameCoachLinesTable === "function") renderGameCoachLinesTable();
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
  // Barre du bas "Reprendre mon coup" / "Nouvel exercice" (issue #63,
  // disposition mobile du mode exercice) : visible uniquement sur cet
  // onglet, sans effet au-dessus de 900px (cf. media query, templates/
  // index.html) — ne duplique aucune logique, ses deux boutons appellent
  // sharedReprendreCoup()/openExercisePhaseSheet() (exercise.js).
  const mobileExerciseBar = document.getElementById("mobile-exercise-bar");
  if (mobileExerciseBar) mobileExerciseBar.classList.toggle("show", tabKey === "exercise");

  // Issue #70 : rafraîchit l'écran de partie mobile (mobile_game.js — plateau
  // fixe/onglets Coach-Lignes-Analyse-Coups pour free/pedagogic/opening/
  // finale) à chaque changement d'onglet de mode ; no-op si mobile_game.js
  // n'est pas chargé (aucune dépendance dure de ce fichier vers lui).
  if (typeof onGameUiRefresh === "function") onGameUiRefresh();
}

// ── Sélecteur de mode en menu déroulant sur mobile (issue #63) ─────────────
// Les boutons d'onglets existants (switchModeTab, ci-dessus) sont déplacés
// tels quels entre leur emplacement d'origine (grand écran, disposition
// inchangée) et #mobile-mode-bar-slot (collé en haut de l'écran, <900px) —
// aucune logique de changement de mode n'est dupliquée ni réécrite, seul cet
// habillage présentationnel est ajouté.
let _modeTabBarHomeParent = null;
let _modeTabBarHomeNextSibling = null;
const _mobileModeBarQuery = window.matchMedia("(max-width: 900px)");

function placeModeTabBarForViewport(isMobile) {
  const bar = document.getElementById("mode-tab-bar");
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (!bar || !slot) return;
  if (isMobile) {
    if (bar.parentElement !== slot) slot.appendChild(bar);
  } else {
    bar.classList.remove("open");
    if (bar.parentElement !== _modeTabBarHomeParent) {
      _modeTabBarHomeParent.insertBefore(bar, _modeTabBarHomeNextSibling);
    }
  }
}

// Un seul bouton (.active) reste visible quand le menu est fermé (cf. media
// query) ; le cliquer l'ouvre. Ouvert, cliquer un bouton (actif ou non)
// laisse switchModeTab() s'exécuter normalement (onclick déjà posé sur
// chaque bouton) puis referme le menu — délégation d'événement plutôt que
// modifier les 7 boutons, pour ne toucher à aucun onclick existant.
document.addEventListener("click", (e) => {
  const bar = document.getElementById("mode-tab-bar");
  if (!bar || !_mobileModeBarQuery.matches) return;
  const btn = e.target.closest(".mode-tab-btn");
  if (btn && bar.contains(btn)) {
    // Fermé, seul .active est visible → ce clic l'ouvre. Ouvert, l'onclick=
    // "switchModeTab(...)" du bouton (posé dans templates/index.html) s'est
    // déjà exécuté avant que cet écouteur délégué ne reçoive l'événement à
    // la remontée → il ne reste qu'à refermer le menu.
    bar.classList.toggle("open");
    return;
  }
  if (!bar.contains(e.target)) bar.classList.remove("open");
});

// ── Repositionnement de blocs secondaires sur mobile (issue #69) ───────────
// Même mécanique que placeModeTabBarForViewport ci-dessus (déplacement du
// nœud DOM réel entre son emplacement d'origine et un slot dédié, jamais de
// duplication ni de réécriture de la logique — pgn_library.js/game_analysis.js
// and co. retrouvent leurs éléments par id, peu importe leur parent réel) —
// généralisée ici pour les quelques blocs qui changent de place dans la
// réorganisation mobile de l'issue #69 : ce qui ne sert pas pendant la partie
// (importation PGN, navigation dans la collection, programme d'entraînement)
// vers #mobile-bottom-slot (après l'historique des coups), et le panneau
// d'analyse de partie vers #mobile-analysis-slot (juste après le tableau
// "Lignes du coach", dans le panneau du coach).
const _mobileRelocatables = [];

function _registerMobileRelocatable(id, slotId) {
  const el = document.getElementById(id);
  if (!el) return;
  _mobileRelocatables.push({ id, slotId, homeParent: el.parentElement, homeNextSibling: el.nextSibling });
}

function _placeMobileRelocatablesForViewport(isMobile) {
  _mobileRelocatables.forEach(({ id, slotId, homeParent, homeNextSibling }) => {
    const el = document.getElementById(id);
    const slot = document.getElementById(slotId);
    if (!el || !slot) return;
    if (isMobile) {
      if (el.parentElement !== slot) slot.appendChild(el);
    } else if (el.parentElement !== homeParent) {
      homeParent.insertBefore(el, homeNextSibling);
    }
  });
}

// ── scroll-padding-top dynamique (issue #69 point 5) ────────────────────────
// Le scroll-padding-top statique posé en CSS (calc(--bd-size + 90px), cf.
// templates/index.html) suppose une hauteur "normale" de #board-sticky-wrap —
// mais elle varie aussi avec le bandeau de fin de partie, les boutons
// "Jouer les Blancs/Noirs" du mode pédagogique tant qu'aucune partie n'est en
// cours (issue #65 point 6) et la barre de lecture des lignes du coach
// (issue #69 point 4). Un ResizeObserver la resynchronise sur la hauteur
// RÉELLEMENT rendue en toute circonstance, sans avoir à rappeler cette mise à
// jour à chaque bascule de ces éléments — remplace (déborde, en priorité par
// spécificité de style en ligne) la valeur statique dès que ce fichier
// s'exécute ; celle-ci reste un filet de sécurité pour le tout premier rendu
// ou si ResizeObserver est indisponible.
function _updateStickyScrollPadding() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (!wrap || !_mobileModeBarQuery.matches) {
    document.documentElement.style.scrollPaddingTop = "";
    return;
  }
  document.documentElement.style.scrollPaddingTop = `${Math.ceil(wrap.getBoundingClientRect().height) + 12}px`;
}
document.addEventListener("DOMContentLoaded", () => {
  const wrap = document.getElementById("board-sticky-wrap");
  if (wrap && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(_updateStickyScrollPadding).observe(wrap);
  }
  _updateStickyScrollPadding();
});
_mobileModeBarQuery.addEventListener("change", _updateStickyScrollPadding);

// ── Menu "..." de la rangée de navigation (issue #69 point 2) ──────────────
// "Extraire le FEN" reste un seul bouton (extraireFen(), inchangé) — seul son
// déclencheur diffère selon la largeur d'écran (cf. .review-fen-btn-full/
// .review-more-menu, templates/index.html). Fermeture au clic ailleurs, même
// principe que le menu déroulant du sélecteur de mode ci-dessus.
function toggleReviewMoreMenu() {
  const dd = document.getElementById("review-more-dropdown");
  if (dd) dd.classList.toggle("open");
}
function closeReviewMoreMenu() {
  const dd = document.getElementById("review-more-dropdown");
  if (dd) dd.classList.remove("open");
}
document.addEventListener("click", (e) => {
  const menu = document.getElementById("review-more-menu");
  if (!menu) return;
  if (!menu.contains(e.target)) closeReviewMoreMenu();
});

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
// Précédent/Suivant/Meilleur coup n'ont de sens qu'en revue de bibliothèque
// (activeMode null) — dès qu'un mode interactif tourne, ils sont grisés
// plutôt que de rester cliquables sans effet cohérent.
//
// Issue #34 : "Retourner" en est exclu — contrairement aux trois autres, il
// garde un sens dans n'importe quel mode interactif (voir sa position
// affichée sous un autre angle), donc reste toujours cliquable ; flipBoard()
// (board.js) se charge de cibler la bonne position (mode actif ou revue).
function updateReviewControlsEnabled() {
  const disabled = !!activeMode;
  ["review-prev-btn", "review-next-btn", "review-bestmove-btn"].forEach((id) => {
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
  const askCoachHelp = document.getElementById("shared-ask-coach-help");
  const statusEl     = document.getElementById("shared-mode-status");

  // Issue #65 point 5 : sur mobile, le mode exercice affiche déjà "Reprendre
  // mon coup" dans la barre du bas (#mobile-exercise-bar, visible seulement
  // sur cet onglet) — le garder aussi ici ferait doublon. Les autres modes
  // (pédagogique/ouverture/finales) n'ont pas cette barre du bas, donc y
  // gardent ce bouton normalement, y compris sur mobile.
  if (reprendreBtn) {
    const isMobile = typeof _mobileModeBarQuery !== "undefined" && _mobileModeBarQuery.matches;
    const dupliqueBarreExercice = activeMode === "exercise" && isMobile;
    reprendreBtn.style.display = (caps && caps.reprendre && !dupliqueBarreExercice) ? "" : "none";
  }
  if (abandonBtn)   abandonBtn.style.display   = caps && caps.abandon   ? "" : "none";
  if (commentRow)   commentRow.style.display   = caps && caps.hasComment ? "" : "none";

  // Issue #65 point 5 : "Demander l'avis du coach" ne fait rien quand la
  // partie est terminée/abandonnée (askXCoach des fichiers de mode se
  // contente alors de ne rien faire, sans le moindre retour visuel) — le
  // bouton doit donc être grisé/désactivé dans ce cas plutôt que de rester
  // cliquable en apparence (règle "pas de terracotta pour ce qui n'est pas
  // cliquable" — button:disabled { opacity:0.5 } s'en charge visuellement).
  if (askCoachBtn) {
    const hasAskCoach = !!(caps && caps.askCoach);
    askCoachBtn.style.display = hasAskCoach ? "" : "none";
    askCoachBtn.disabled = hasAskCoach && caps.askCoachAvailable ? !caps.askCoachAvailable() : false;
  }
  if (askCoachHelp) {
    const hasAskCoach = !!(caps && caps.askCoach);
    askCoachHelp.style.display = hasAskCoach ? "" : "none";
    askCoachHelp.textContent = hasAskCoach ? (MODE_ASK_COACH_HELP[activeMode] || "") : "";
  }
  if (statusEl) statusEl.textContent = activeMode ? MODE_LABELS[activeMode] : "Aucun mode interactif actif.";

  // Issue #70 : mêmes points de coupure que ci-dessus (switchModeTab) — cette
  // fonction est déjà appelée par setActiveMode()/les gestionnaires de fin de
  // partie/abandon/reprendre de chaque mode, donc par ricochet à chaque
  // transition pertinente pour la barre d'actions/le bandeau avant-partie du
  // mode jeu mobile.
  if (typeof onGameUiRefresh === "function") onGameUiRefresh();
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

// Partie terminée par un clic sur "Abandonner" (issue #52) plutôt que par
// mat/pat/nulle — utilisé par activeModeGameState() ci-dessous pour signaler
// explicitement ce cas au chat libre du coach (coachBuildContext, board.js).
// Contrairement à _activeModeCampAlain ci-dessus, la partie libre a bien un
// état d'abandon propre (freeAbandonne) même si elle n'a pas de camp_alain.
function _activeModeAbandoned() {
  switch (activeMode) {
    case "free":      return !!freeAbandonne;
    case "pedagogic": return !!pedagogicAbandonne;
    case "opening":   return !!openingAbandonne;
    case "finale":    return !!finaleAbandonne;
    default:          return false;
  }
}

function activeModeGameState() {
  const game = _activeModeGameInstance();
  if (!game) return null;
  // pgn/move (issue #33) : historique réel des coups joués depuis le début
  // de la partie en cours (chess.js game.pgn()/game.history()), pour que le
  // chat libre du coach connaisse les coups déjà joués (ex. un fianchetto au
  // coup 8) et pas seulement l'instantané FEN de la position actuelle.
  const history = game.history();
  return {
    fen: game.fen(),
    campAlain: _activeModeCampAlain(),
    pgn: game.pgn(),
    move: history.length ? history[history.length - 1] : "",
    abandonne: _activeModeAbandoned(),
    // Nombre de coups déjà joués dans cette partie (issue #64 point 3),
    // transmis au contexte du coach comme identifiant de la partie en cours.
    nbCoups: history.length,
  };
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

// ── Historique des coups repliable (issue #63, disposition mobile) ─────────
// Ajout purement présentationnel : #historique et son rendu (renderHistory,
// board.js) sont inchangés, seule la visibilité de la table est togglée.
function toggleHistoriqueCollapsed() {
  const col = document.getElementById("historique-column");
  const chevron = document.querySelector(".historique-toggle-chevron");
  if (!col) return;
  const collapsed = col.classList.toggle("collapsed");
  if (chevron) chevron.textContent = collapsed ? "Déplier ▼" : "Replier ▲";
}

document.addEventListener("DOMContentLoaded", () => {
  updateSharedControlBar();
  updateReviewControlsEnabled();
  switchModeTab("library");

  const bar = document.getElementById("mode-tab-bar");
  if (bar) {
    _modeTabBarHomeParent = bar.parentElement;
    _modeTabBarHomeNextSibling = bar.nextSibling;
    placeModeTabBarForViewport(_mobileModeBarQuery.matches);
  }

  // Issue #69 point 2 : mêmes points de coupure (chargement initial +
  // franchissement du seuil mobile) que le sélecteur de mode ci-dessus, pour
  // les blocs secondaires déplacés sur mobile.
  // board-sticky-wrap -> #app directement (pas un slot dédié) : un sticky a
  // besoin d'un parent aussi haut que toute la page pour rester collé jusqu'en
  // bas (cf. commentaire détaillé dans templates/index.html) — #app, colonne
  // qui contient tout le reste, convient ; son order CSS par défaut (0) le
  // place avant #board-column/#coach-column/etc (order 1-5) quel que soit son
  // rang réel dans le DOM après déplacement.
  _registerMobileRelocatable("board-sticky-wrap", "app");
  _registerMobileRelocatable("single-pgn-import-block", "mobile-bottom-slot");
  _registerMobileRelocatable("pgn-lib-browse-block",    "mobile-bottom-slot");
  _registerMobileRelocatable("training-program-panel",  "mobile-bottom-slot");
  _registerMobileRelocatable("game-analysis-panel",     "mobile-analysis-slot");
  _placeMobileRelocatablesForViewport(_mobileModeBarQuery.matches);
  if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();

  // updateSharedControlBar() en plus de placeModeTabBarForViewport() : issue
  // #65 point 5, le doublon "Reprendre mon coup" en mode exercice ne dépend
  // pas seulement du mode actif mais aussi du franchissement du seuil mobile
  // (rotation d'écran, redimensionnement d'une fenêtre desktop) — sans cet
  // appel, resterait affiché jusqu'au prochain changement de mode.
  _mobileModeBarQuery.addEventListener("change", (e) => {
    placeModeTabBarForViewport(e.matches);
    _placeMobileRelocatablesForViewport(e.matches);
    if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();
    updateSharedControlBar();
  });

  // Replié par défaut sur mobile seulement (issue #63) — sur grand écran,
  // l'historique reste dépliable mais visible d'entrée comme avant. Le
  // libellé statique du gabarit ("Déplier ▼") est resynchronisé ici dans
  // les deux cas, plutôt que de dépendre du texte codé en dur du template.
  const chevron = document.querySelector(".historique-toggle-chevron");
  if (_mobileModeBarQuery.matches) {
    toggleHistoriqueCollapsed();
  } else if (chevron) {
    chevron.textContent = "Replier ▲";
  }
});
