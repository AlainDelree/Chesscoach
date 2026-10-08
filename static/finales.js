/*
 * finales.js — ChessCoach (issue #10)
 *
 * Mode "travail de finales" : bibliothèque curatée de positions-types
 * (finales.py, listée dans le menu déroulant du panneau), adversaire à
 * pleine force côté serveur (engine_manager.get_move, réutilisé du mode
 * partie libre — pas le moteur affaibli des modes pédagogique/ouverture),
 * commentaire du coach tenant compte du thème technique de la position
 * sélectionnée (voir app.py on_finale_move).
 *
 * Contrairement aux modes pédagogique/ouverture, le camp qu'Alain doit
 * jouer est fixé par la position-type elle-même (finales.py), pas un choix
 * libre : pas de boutons "Jouer les Blancs/Noirs" ici, juste la sélection
 * dans le menu déroulant (avec une case "Camps inversés" pour jouer le camp
 * normalement tenu par Stockfish, issue #28).
 *
 * Issue #28 : deux compléments à côté du jeu normal.
 *   - Démonstration ("Voir une démonstration") : Stockfish contrôle les deux
 *     camps, un demi-coup à la fois sur clic "Coup suivant"
 *     (finaleDemoActive) — jamais de commentaire automatique du coach, le
 *     plateau n'accepte aucun clic.
 *   - Cases hachurées autour du roi du camp perdant (celui qui n'a que son
 *     roi, propriété fixe de la finale — voir app.py
 *     _finale_restricted_king_squares) : reçues du serveur à chaque nouvelle
 *     position (finale_started/finale_stockfish_move/finale_demo_started/
 *     finale_demo_move) et appliquées par renderFinaleBoard, dans tous les
 *     contextes (jeu normal, camps inversés, démonstration).
 *
 * Réutilise buildBoard()/renderBoard() de board.js et
 * freeSquareIdToAlgebraic()/freeAlgebraicToSquareId() de free_play.js, comme
 * pedagogic.js/opening.js.
 */

let finaleGame       = null;  // instance chess.js (mode travail de finales)
let finaleActive     = false;
let finaleCampAlain  = "blancs";
let finaleSelected   = null;  // case algébrique sélectionnée ou null
let finaleWaiting    = false; // coup en cours de traitement côté serveur
let finaleGameOver   = false; // fin de partie détectée côté serveur (issue #11) ou abandon (issue #52)
let finaleAbandonne  = false; // fin de partie spécifiquement par "Abandonner" (issue #52, cf. coachBuildContext)
let finaleList       = [];    // bibliothèque reçue du serveur (finale_list_response)
let finaleFenAvantCoup = null; // FEN juste avant le dernier coup d'Alain (issue #13, "Reprendre mon coup")
// Commentaire automatique du coup qui vient d'être joué (issue #105) — voir
// le commentaire équivalent dans opening.js (_openingCommentPending).
// Jamais utilisé pour les coups de démonstration (finale_demo_move/
// finale_demo_stopped, qui n'appellent jamais le coach).
let _finaleCommentPending = false;
let _finaleCommentWait    = null;
let finaleDemoActive  = false; // démonstration en cours (issue #28) : Stockfish joue les deux camps
let finaleKingRestrictedSquares = []; // cases algébriques hachurées (issue #28)
let finaleDemoCoupsJoues = 0; // nombre de demi-coups joués dans la démonstration en cours (issue #29, contexte coach)

function finaleCommenterChaqueCoup() {
  const cb = document.getElementById("shared-auto-comment");
  return !!(cb && cb.checked);
}

// ── Sélecteur de finale déplacé avant le plateau sur mobile (issue #77
// point 6, généralise placeOpeningStartButtonsForViewport d'opening.js) ────
// Contrairement au reste de #finale-extra-controls (recommencer/démo, qui
// n'ont de sens qu'une fois une finale déjà chargée), #finale-picker-row
// (sélecteur de position-type + "Camps inversés") est le seul moyen de
// démarrer ce mode — choisir une finale déclenche directement la partie
// (onFinaleSelectChange). Le laisser enfermé dans le menu "..." (fermé par
// défaut sur mobile, cf. GAME_MODE_EXTRA, mobile_game.js) rendait ce mode
// silencieusement inactif tant qu'on n'avait pas pensé à l'ouvrir (rapport de
// clôture : "l'écran ne réagit à quasi rien").
let _finaleStartHomeParent      = null;
let _finaleStartHomeNextSibling = null;
const _finaleMobileQuery = window.matchMedia("(max-width: 900px)");

function placeFinaleStartButtonsForViewport() {
  const row  = document.getElementById("finale-picker-row");
  const slot = document.getElementById("mobile-finale-start-slot");
  if (!row || !slot || !_finaleStartHomeParent) return;
  const gameEnCours = finaleActive && !finaleGameOver;
  const onFinaleTab = typeof currentModeTab === "undefined" || currentModeTab === "finale";
  const showInSlot = _finaleMobileQuery.matches && onFinaleTab && !gameEnCours;
  if (showInSlot) {
    if (row.parentElement !== slot) slot.appendChild(row);
  } else if (row.parentElement !== _finaleStartHomeParent) {
    _finaleStartHomeParent.insertBefore(row, _finaleStartHomeNextSibling);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const row = document.getElementById("finale-picker-row");
  if (row) {
    _finaleStartHomeParent      = row.parentElement;
    _finaleStartHomeNextSibling = row.nextSibling;
    placeFinaleStartButtonsForViewport();
  }
  _finaleMobileQuery.addEventListener("change", () => placeFinaleStartButtonsForViewport());
});

// PGN de la partie de finale en cours, avec en-têtes (issue #52, "Analyser
// cette partie" après abandon — mêmes principes que
// _pedagogicGamePgnForAnalysis dans pedagogic.js).
function _finaleGamePgnForAnalysis() {
  if (!finaleGame) return "";
  const white = finaleCampAlain === "noirs" ? "Adversaire" : "Alain";
  const black = finaleCampAlain === "noirs" ? "Alain" : "Adversaire";
  finaleGame.header("White", white, "Black", black);
  return finaleGame.pgn();
}

// Issue #52 : "Abandonner" ne remet plus le plateau à zéro — la partie (ou
// démonstration en cours, arrêtée le cas échéant) reste affichée avec sa
// bannière de défaite comme pour un mat, coups suivants bloqués via
// finaleGameOver (déjà lu par onFinaleBoardClick). Le plateau ne redevient
// vierge qu'au chargement explicite d'une autre finale ou à un changement de
// mode — le menu déroulant et la description restent donc affichés tels
// quels, contrairement à l'ancien comportement qui les vidait.
function abandonFinaleGame() {
  if (!finaleActive || finaleGameOver) return;
  socket.emit("finale_abandon", {});
  finaleGameOver  = true;
  finaleAbandonne = true;
  finaleWaiting   = false;
  finaleSelected  = null;
  finaleFenAvantCoup = null;
  finaleDemoActive = false;
  updateFinaleDemoNextButton();
  updateFinaleDemoToggleButton();
  const statusEl = document.getElementById("finale-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée — défaite.";
  const opposant = finaleCampAlain === "noirs" ? "blancs" : "noirs";
  showGameOverBanner(
    { gagnant: opposant, message: "Partie abandonnée par Alain — défaite." },
    finaleCampAlain,
    () => analyserPartieDepuisPgn(_finaleGamePgnForAnalysis()),
    undefined,
    true
  );
  // Issue #65 point 5 : grise "Demander l'avis du coach" (askCoachAvailable,
  // controls.js) dès l'abandon.
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placeFinaleStartButtonsForViewport === "function") placeFinaleStartButtonsForViewport();
}

function updateFinaleDemoNextButton() {
  const btn = document.getElementById("finale-demo-next-btn");
  if (!btn) return;
  btn.style.display = finaleDemoActive ? "" : "none";
  // Issue #29 : grisé (plutôt que simplement laissé cliquable sans effet)
  // dès que la démonstration est terminée (mat, pat ou nulle) — visible
  // immédiatement, pas seulement déduit du texte de statut.
  btn.disabled = finaleGameOver;
}

// Issue #35 : le bouton "Voir une démonstration"/"Coup suivant" reste un
// bouton à bascule unique (finale-demo-toggle-btn) — son libellé suit
// simplement finaleDemoActive, mis à jour en même temps que
// updateFinaleDemoNextButton() partout où celle-ci est appelée.
function updateFinaleDemoToggleButton() {
  const btn = document.getElementById("finale-demo-toggle-btn");
  if (!btn) return;
  btn.textContent = finaleDemoActive ? "Arrêter la démonstration" : "Voir une démonstration";
}

// Issue #40 : la case "Camps inversés" n'est lue qu'au chargement d'une
// finale (loadSelectedFinale) — la cocher/décocher en cours de partie n'a
// aucun effet tant qu'on n'a pas rechargé la finale. Grisée dès qu'Alain a
// joué au moins un coup, pour ne pas laisser croire qu'elle agit en direct ;
// réactivée au chargement (sélection ou "Recommencer cette finale", tous
// deux via loadSelectedFinale).
function setFinaleInverserCampsDisabled(disabled) {
  const cb = document.getElementById("finale-inverser-camps");
  if (cb) cb.disabled = disabled;
}

function reprendreFinaleCoup() {
  const statusEl = document.getElementById("finale-status");
  if (!finaleActive || finaleWaiting || !finaleFenAvantCoup) {
    if (statusEl && finaleActive && !finaleWaiting) statusEl.textContent = "Aucun coup à reprendre.";
    return;
  }
  finaleGame     = new Chess(finaleFenAvantCoup);
  finaleGameOver = false;
  finaleSelected = null;
  finaleFenAvantCoup = null;
  hideGameOverBanner();
  renderFinaleBoard();
  updateFinaleStatus();
  // Issue #65 point 5 : la partie redevient en cours — réactive "Demander
  // l'avis du coach".
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
}

// Complément de contexte pour le chat libre du coach (issue #29,
// coachBuildContext() dans board.js) : sans lui, sollicité pendant ou après
// une démonstration Stockfish-contre-Stockfish (aucun coup d'Alain), le
// coach n'a aucun moyen de savoir que la position affichée ne vient pas
// d'une partie qu'Alain vient de jouer — il a déjà inventé à tort un récit
// l'accusant d'avoir mal joué la finale. mode_demonstration reste vrai même
// après la fin de la démonstration (finaleGameOver), tant qu'une nouvelle
// finale/démonstration n'a pas été chargée : la position affichée reste
// celle de la démonstration.
function finaleChatContextExtra() {
  if (!finaleDemoActive) return {};
  return {
    mode_demonstration: true,
    demo_coups_joues: finaleDemoCoupsJoues,
  };
}

function askFinaleCoach() {
  if (!finaleActive || !finaleGame || finaleGameOver || finaleWaiting) return;
  const descEl = document.getElementById("finale-description");
  askCoachOnDemand(finaleGame.fen(), descEl ? descEl.textContent : "", finaleCampAlain);
}

function populateFinaleSelect() {
  const selectEl = document.getElementById("finale-select");
  if (!selectEl) return;
  selectEl.innerHTML = '<option value="">— Choisir une finale —</option>';
  finaleList.forEach((f) => {
    const opt = document.createElement("option");
    opt.value = f.id;
    opt.textContent = f.nom;
    selectEl.appendChild(opt);
  });
}

function onFinaleSelectChange() {
  const selectEl = document.getElementById("finale-select");
  if (!selectEl) return;
  loadSelectedFinale(selectEl.value);
}

// Issue #37 : bouton "Recommencer cette finale" — un <select> HTML ne
// déclenche pas d'événement "change" quand l'option resélectionnée est déjà
// celle active (comportement standard du navigateur), donc resélectionner la
// même finale dans #finale-select n'exécute jamais onFinaleSelectChange().
// Ce bouton appelle directement loadSelectedFinale() pour l'id actuellement
// affiché dans le menu, en cours de partie comme après une fin de partie.
function restartCurrentFinale() {
  const selectEl = document.getElementById("finale-select");
  if (!selectEl) return;
  loadSelectedFinale(selectEl.value);
}

function loadSelectedFinale(id) {
  const descEl = document.getElementById("finale-description");
  if (!id) {
    if (descEl) descEl.textContent = "";
    return;
  }
  const entry = finaleList.find((f) => f.id === id);
  if (descEl) descEl.textContent = entry ? entry.description : "";

  ensureModeSwitchClean("finale");
  // Nouvelle partie (issue #64) : l'historique du chat envoyé à l'API repart
  // de zéro, séparé à l'écran des échanges de la finale précédente.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvelle partie");
  // Issue #71 point 6 : le rapport d'analyse affiché (Bibliothèque/Revue)
  // n'a plus de rapport avec la partie qui démarre.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  hideGameOverBanner();
  finaleWaiting  = true;
  finaleGameOver = false;
  finaleAbandonne = false;
  finaleFenAvantCoup = null;
  finaleDemoActive = false;
  updateFinaleDemoNextButton();
  updateFinaleDemoToggleButton();
  setFinaleInverserCampsDisabled(false);
  const statusEl = document.getElementById("finale-status");
  if (statusEl) statusEl.textContent = "Chargement de la position...";
  const inverserEl = document.getElementById("finale-inverser-camps");
  socket.emit("finale_start", { id, inverser: !!(inverserEl && inverserEl.checked) });
}

function startFinaleDemo() {
  const selectEl = document.getElementById("finale-select");
  const statusEl = document.getElementById("finale-status");
  const id = selectEl ? selectEl.value : "";
  if (!id) {
    if (statusEl) statusEl.textContent = "Choisissez d'abord une finale dans la liste.";
    return;
  }
  const entry = finaleList.find((f) => f.id === id);
  const descEl = document.getElementById("finale-description");
  if (descEl) descEl.textContent = entry ? entry.description : "";

  ensureModeSwitchClean("finale");
  // Nouvelle démonstration (issue #64) : l'historique du chat envoyé à
  // l'API repart de zéro, séparé à l'écran des échanges précédents.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvelle partie");
  // Issue #71 point 6 : le rapport d'analyse affiché (Bibliothèque/Revue)
  // n'a plus de rapport avec la partie qui démarre.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  hideGameOverBanner();
  finaleWaiting  = true;
  finaleGameOver = false;
  finaleAbandonne = false;
  finaleFenAvantCoup = null;
  finaleDemoActive = true;
  finaleDemoCoupsJoues = 0;
  updateFinaleDemoNextButton();
  updateFinaleDemoToggleButton();
  if (statusEl) statusEl.textContent = "Chargement de la démonstration...";
  // Issue #36 : si une partie est déjà chargée pour cette finale (finaleGame
  // porte la position atteinte après d'éventuels coups joués par Alain et/ou
  // une précédente démonstration), la transmettre au serveur pour que la
  // démonstration reparte de là plutôt que de la position de départ de
  // data/finales.json (voir app.py on_finale_demo_start). Rien n'est envoyé
  // si aucune partie n'est encore en cours — le serveur retombe alors sur la
  // FEN de départ, comportement inchangé.
  const payload = { id };
  if (finaleActive && finaleGame) payload.fen = finaleGame.fen();
  socket.emit("finale_demo_start", payload);
}

// Issue #35 : bouton à bascule "Voir une démonstration"/"Arrêter la
// démonstration" (finale-demo-toggle-btn, voir index.html).
function toggleFinaleDemo() {
  if (finaleDemoActive) {
    stopFinaleDemo();
  } else {
    startFinaleDemo();
  }
}

// Arrête la démonstration en cours et fait de la position atteinte la
// position de jeu normale du mode finales (finale_demo_stop, app.py) — pas
// une réinitialisation : finaleGame garde tout l'historique de la
// démonstration (déjà tenu à jour demi-coup par demi-coup par
// finale_demo_move), donc rien à reconstruire côté client au-delà du dernier
// coup éventuel de l'adversaire automatique si c'était son tour.
function stopFinaleDemo() {
  if (!finaleActive || !finaleDemoActive || finaleWaiting) return;
  finaleWaiting = true;
  finaleDemoActive = false;
  finaleFenAvantCoup = null;
  updateFinaleDemoNextButton();
  updateFinaleDemoToggleButton();
  updateFinaleStatus();
  socket.emit("finale_demo_stop", {});
}

function finaleDemoNext() {
  if (!finaleActive || !finaleDemoActive || !finaleGame || finaleGameOver || finaleWaiting) return;
  finaleWaiting = true;
  updateFinaleStatus();
  // Issue #29 : le plateau de la démonstration est désormais tenu côté
  // serveur (_finale_demo_board, avec l'historique complet) — plus besoin
  // d'envoyer une FEN reconstruite côté client à chaque demi-coup.
  socket.emit("finale_demo_next", {});
}

function renderFinaleBoard(lastFrom, lastTo) {
  if (!finaleGame) return;
  const fenBoard = finaleGame.fen().split(" ")[0];
  const from = lastFrom ? freeAlgebraicToSquareId(lastFrom) : null;
  const to   = lastTo   ? freeAlgebraicToSquareId(lastTo)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (finaleSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(finaleSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  finaleKingRestrictedSquares.forEach((square) => {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(square)}`);
    if (sq) sq.classList.add("finale-king-restricted");
  });
  renderHistory();
}

function updateFinaleStatus() {
  const statusEl = document.getElementById("finale-status");
  if (!statusEl || !finaleGame) return;
  let text = finaleGame.turn() === "w" ? "Trait aux Blancs" : "Trait aux Noirs";
  if (finaleGame.in_checkmate())      text = "Échec et mat.";
  else if (finaleGame.in_stalemate()) text = "Pat.";
  else if (finaleGame.in_draw())      text = "Partie nulle.";
  else if (finaleGame.in_check())     text += " (échec)";
  if (finaleWaiting) {
    text += finaleDemoActive ? " — Stockfish (démonstration) réfléchit..." : " — Stockfish (pleine force) et le coach réfléchissent...";
  }
  statusEl.textContent = text;
}

function finaleIsAlainTurn() {
  if (!finaleGame) return false;
  const trait = finaleGame.turn() === "w" ? "blancs" : "noirs";
  return trait === finaleCampAlain;
}

function onFinaleBoardClick(e) {
  if (finaleDemoActive) return;
  if (!finaleActive || !finaleGame || finaleWaiting || finaleGameOver) return;
  // Une ligne du coach est affichée sur le plateau (issue #68, avant/pendant/
  // après sa lecture) : coups bloqués jusqu'au retour explicite ("Revenir à
  // la partie").
  if (typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive) return;
  if (!finaleIsAlainTurn()) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!finaleSelected) {
    const piece = finaleGame.get(square);
    if (piece && piece.color === finaleGame.turn()) {
      finaleSelected = square;
      renderFinaleBoard();
    }
    return;
  }

  if (finaleSelected === square) {
    finaleSelected = null;
    renderFinaleBoard();
    return;
  }

  const fenAvant = finaleGame.fen();
  const move = finaleGame.move({ from: finaleSelected, to: square, promotion: "q" });
  finaleSelected = null;

  if (!move) {
    const piece = finaleGame.get(square);
    if (piece && piece.color === finaleGame.turn()) {
      finaleSelected = square;
    }
    renderFinaleBoard();
    return;
  }

  renderFinaleBoard(move.from, move.to);
  finaleWaiting = true;
  finaleFenAvantCoup = fenAvant;
  setFinaleInverserCampsDisabled(true);
  updateFinaleStatus();
  // Masqué dans le chat sur mobile (issue #69 point 3) — purement présentationnel,
  // cf. commentaire de _coachRenderBubble (board.js).
  _coachRenderBubble("user", `Travail de finales — je joue ${move.san}`, false, "coach-bubble-auto-move");
  const commenter = finaleCommenterChaqueCoup();
  _finaleCommentPending = commenter;
  socket.emit("finale_move", {
    fen_avant: fenAvant,
    uci: move.from + move.to + (move.promotion || ""),
    commenter,
  });
}

if (typeof socket !== "undefined") {
  socket.on("finale_list_response", (data) => {
    finaleList = (data && data.finales) || [];
    populateFinaleSelect();
  });

  socket.on("finale_started", (data) => {
    finaleWaiting = false;
    if (!data || !data.fen) return;
    finaleGame      = new Chess(data.fen);
    finaleActive    = true;
    finaleSelected  = null;
    finaleGameOver  = false;
    finaleAbandonne = false;
    finaleDemoActive = false;
    _finaleCommentPending = false;
    if (_finaleCommentWait) { _finaleCommentWait.finish(); _finaleCommentWait = null; }
    finaleCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    updateFinaleDemoNextButton();
    updateFinaleDemoToggleButton();
    setActiveMode("finale");

    const descEl = document.getElementById("finale-description");
    if (descEl && data.description) descEl.textContent = data.description;

    _boardFlipped = (finaleCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onFinaleBoardClick;

    let lastFrom = null, lastTo = null;
    if (data.coup_ouverture) {
      lastFrom = data.coup_ouverture.slice(0, 2);
      lastTo   = data.coup_ouverture.slice(2, 4);
    }
    renderFinaleBoard(lastFrom, lastTo);
    updateFinaleStatus();

    // extraClass "coach-bubble-announce" (issue #95, point 5) : message
    // d'annonce envoyé par l'application au démarrage, pas une réponse à une
    // demande d'Alain — ne doit jamais à lui seul déclencher le plateau
    // réduit mobile (cf. _coachRenderBubble, board.js).
    _coachRenderBubble("assistant", `Finale "${data.nom}" chargée. ${data.description || ""}`, false, "coach-bubble-announce", null, { mode_origine: "finales" });
  });

  socket.on("finale_demo_started", (data) => {
    finaleWaiting = false;
    if (!data || !data.fen) return;
    // Issue #36 : ne recréer l'instance chess.js que si aucune partie
    // n'était déjà chargée pour cette finale, ou si la position renvoyée par
    // le serveur diffère de celle transmise (repli sur la position de
    // départ côté serveur, ex. FEN client invalide) — sinon on garde
    // finaleGame tel quel pour préserver tout son historique réel de coups
    // (pgn/move, issue #33), qu'une reconstruction depuis une simple FEN
    // effacerait.
    if (!finaleGame || finaleGame.fen() !== data.fen) {
      finaleGame = new Chess(data.fen);
    }
    finaleActive    = true;
    finaleSelected  = null;
    finaleGameOver  = false;
    finaleAbandonne = false;
    finaleDemoActive = true;
    finaleDemoCoupsJoues = 0;
    finaleCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    updateFinaleDemoNextButton();
    updateFinaleDemoToggleButton();
    setActiveMode("finale");

    const descEl = document.getElementById("finale-description");
    if (descEl && data.description) descEl.textContent = data.description;

    _boardFlipped = (finaleCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onFinaleBoardClick;

    renderFinaleBoard();
    updateFinaleStatus();

    // extraClass "coach-bubble-announce" (issue #95, point 5) : voir
    // commentaire équivalent ci-dessus (finale_started).
    _coachRenderBubble("assistant", `Démonstration "${data.nom}" chargée — Stockfish joue les deux camps, un demi-coup à la fois ("Coup suivant"). ${data.description || ""}`, false, "coach-bubble-announce", null, { mode_origine: "finales" });
  });

  socket.on("finale_stockfish_move", (data) => {
    finaleWaiting = false;
    // Capturé puis effacé ICI (issue #105) — voir le commentaire équivalent
    // dans opening.js, socket.on("opening_stockfish_move").
    const commentPending = _finaleCommentPending;
    _finaleCommentPending = false;
    if (!finaleActive || !finaleGame || !data) return;

    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    if (data.uci) {
      const move = finaleGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderFinaleBoard(move.from, move.to);
      }
    }
    if (data.game_over) {
      finaleGameOver = true;
      const statusEl = document.getElementById("finale-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, finaleCampAlain);
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      return;
    }
    updateFinaleStatus();
    // Indicateur + délai maximal pour le commentaire automatique (issue
    // #105) — voir le commentaire équivalent dans opening.js.
    if (commentPending && typeof coachWaitBegin === "function") {
      const descEl = document.getElementById("finale-description");
      _finaleCommentWait = coachWaitBegin({
        kind: "reponse",
        // NE PAS remettre _finaleCommentWait à null ici — voir le
        // commentaire détaillé équivalent sur _coachAskWait (board.js,
        // _coachSendAsk).
        onTimeout: () => {
          _coachRenderTimeoutBubble(() => askCoachOnDemand(
            finaleGame.fen(), descEl ? descEl.textContent : "", finaleCampAlain,
          ));
        },
      });
    }
  });

  socket.on("finale_demo_move", (data) => {
    finaleWaiting = false;
    if (!finaleActive || !finaleDemoActive || !finaleGame || !data) return;

    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    if (typeof data.coups_joues === "number") finaleDemoCoupsJoues = data.coups_joues;
    if (data.uci) {
      const move = finaleGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderFinaleBoard(move.from, move.to);
      }
    }
    if (data.game_over) {
      // Issue #29 : la démonstration s'arrête ici — plus d'appel à
      // finale_demo_next tant qu'une nouvelle finale/démonstration n'est
      // pas relancée (bouton grisé par updateFinaleDemoNextButton).
      finaleGameOver = true;
      updateFinaleDemoNextButton();
      const statusEl = document.getElementById("finale-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info);
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      return;
    }
    updateFinaleStatus();
  });

  socket.on("finale_demo_stopped", (data) => {
    finaleWaiting = false;
    if (!finaleActive || !finaleGame || !data) return;

    // Issue #35 : finaleGame porte déjà tout l'historique de la
    // démonstration (accumulé demi-coup par demi-coup par finale_demo_move)
    // — pas de reconstruction ici, seulement l'éventuel coup joué
    // immédiatement par l'adversaire automatique si c'était son tour sur la
    // position atteinte (voir app.py on_finale_demo_stop).
    finaleDemoActive = false;
    updateFinaleDemoNextButton();
    updateFinaleDemoToggleButton();

    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    if (data.uci) {
      const move = finaleGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderFinaleBoard(move.from, move.to);
      }
    } else {
      renderFinaleBoard();
    }

    if (data.game_over) {
      finaleGameOver = true;
      const statusEl = document.getElementById("finale-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, finaleCampAlain);
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      return;
    }
    updateFinaleStatus();
  });

  socket.on("finale_comment", (data) => {
    if (_finaleCommentWait) {
      if (_finaleCommentWait.isTimedOut()) {
        console.warn("[travail de finales] commentaire tardif ignoré (délai déjà dépassé)", data);
        _finaleCommentWait = null;
        return;
      }
      _finaleCommentWait.finish();
      _finaleCommentWait = null;
    }
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) {
      _coachRenderBubble("assistant", text, false, undefined, data && data.fiabilite, data && {
        mode_origine: data.mode_origine, fen: data.fen, move: data.coup_propose, log_id: data.log_id,
      });
      // Tableau "Lignes du coach" (issue #68) : alimenté aussi par le
      // commentaire automatique après chaque coup ("Commenter chaque coup"),
      // pas seulement par le chat libre/la demande ponctuelle (board.js).
      if (typeof gameCoachLinesOnCoachText === "function") gameCoachLinesOnCoachText(text);
    }
  });

  socket.on("finale_error", (data) => {
    finaleWaiting = false;
    if (_finaleCommentWait) {
      if (_finaleCommentWait.isTimedOut()) {
        console.warn("[travail de finales] erreur tardive ignorée (délai déjà dépassé)", data);
        _finaleCommentWait = null;
        return;
      }
      _finaleCommentWait.finish();
      _finaleCommentWait = null;
    }
    const err = data && data.error;
    if (err === "credit_insuffisant") {
      if (typeof _coachRenderCreditInsuffisant === "function") _coachRenderCreditInsuffisant();
      console.warn("[travail de finales]", "credit_insuffisant", data);
      return;
    }
    if (err === "timeout") {
      const descEl = document.getElementById("finale-description");
      _coachRenderTimeoutBubble(() => askCoachOnDemand(
        finaleGame.fen(), descEl ? descEl.textContent : "", finaleCampAlain,
      ));
      console.warn("[travail de finales] commentaire échoué (timeout)", data);
      return;
    }
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : (err === "finale_inconnue")
      ? "Position de finale inconnue."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : (err === "coup_illegal")
      ? "Coup illégal détecté côté serveur."
      : "Le coach n'a pas pu répondre, réessayez.";
    const statusEl = document.getElementById("finale-status");
    if (statusEl) statusEl.textContent = msg;
    console.warn("[travail de finales]", msg, data);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof socket !== "undefined") socket.emit("finale_list", {});
});
