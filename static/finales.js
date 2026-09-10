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
let finaleGameOver   = false; // fin de partie détectée côté serveur (issue #11)
let finaleList       = [];    // bibliothèque reçue du serveur (finale_list_response)
let finaleFenAvantCoup = null; // FEN juste avant le dernier coup d'Alain (issue #13, "Reprendre mon coup")
let finaleDemoActive  = false; // démonstration en cours (issue #28) : Stockfish joue les deux camps
let finaleKingRestrictedSquares = []; // cases algébriques hachurées (issue #28)
let finaleDemoCoupsJoues = 0; // nombre de demi-coups joués dans la démonstration en cours (issue #29, contexte coach)

function finaleCommenterChaqueCoup() {
  const cb = document.getElementById("shared-auto-comment");
  return !!(cb && cb.checked);
}

function abandonFinaleGame() {
  if (!finaleActive) return;
  socket.emit("finale_abandon", {});
  finaleActive    = false;
  finaleGame      = null;
  finaleWaiting   = false;
  finaleSelected  = null;
  finaleGameOver  = false;
  finaleFenAvantCoup = null;
  finaleDemoActive = false;
  finaleDemoCoupsJoues = 0;
  finaleKingRestrictedSquares = [];
  updateFinaleDemoNextButton();
  resetBoardToNeutral();
  setActiveMode(null);
  const statusEl = document.getElementById("finale-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée.";
  const descEl = document.getElementById("finale-description");
  if (descEl) descEl.textContent = "";
  const selectEl = document.getElementById("finale-select");
  if (selectEl) selectEl.value = "";
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
  const descEl = document.getElementById("finale-description");
  if (!selectEl) return;
  const id = selectEl.value;
  if (!id) {
    if (descEl) descEl.textContent = "";
    return;
  }
  const entry = finaleList.find((f) => f.id === id);
  if (descEl) descEl.textContent = entry ? entry.description : "";

  ensureModeSwitchClean("finale");
  hideGameOverBanner();
  finaleWaiting  = true;
  finaleGameOver = false;
  finaleFenAvantCoup = null;
  finaleDemoActive = false;
  updateFinaleDemoNextButton();
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
  hideGameOverBanner();
  finaleWaiting  = true;
  finaleGameOver = false;
  finaleFenAvantCoup = null;
  finaleDemoActive = true;
  finaleDemoCoupsJoues = 0;
  updateFinaleDemoNextButton();
  if (statusEl) statusEl.textContent = "Chargement de la démonstration...";
  socket.emit("finale_demo_start", { id });
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
  updateFinaleStatus();
  _coachRenderBubble("user", `Travail de finales — je joue ${move.san}`);
  socket.emit("finale_move", {
    fen_avant: fenAvant,
    uci: move.from + move.to + (move.promotion || ""),
    commenter: finaleCommenterChaqueCoup(),
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
    finaleDemoActive = false;
    finaleCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    updateFinaleDemoNextButton();
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

    _coachRenderBubble("assistant", `Finale "${data.nom}" chargée. ${data.description || ""}`);
  });

  socket.on("finale_demo_started", (data) => {
    finaleWaiting = false;
    if (!data || !data.fen) return;
    finaleGame      = new Chess(data.fen);
    finaleActive    = true;
    finaleSelected  = null;
    finaleGameOver  = false;
    finaleDemoActive = true;
    finaleDemoCoupsJoues = 0;
    finaleCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    finaleKingRestrictedSquares = data.king_restricted_squares || [];
    updateFinaleDemoNextButton();
    setActiveMode("finale");

    const descEl = document.getElementById("finale-description");
    if (descEl && data.description) descEl.textContent = data.description;

    _boardFlipped = (finaleCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onFinaleBoardClick;

    renderFinaleBoard();
    updateFinaleStatus();

    _coachRenderBubble("assistant", `Démonstration "${data.nom}" chargée — Stockfish joue les deux camps, un demi-coup à la fois ("Coup suivant"). ${data.description || ""}`);
  });

  socket.on("finale_stockfish_move", (data) => {
    finaleWaiting = false;
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
      return;
    }
    updateFinaleStatus();
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
      return;
    }
    updateFinaleStatus();
  });

  socket.on("finale_comment", (data) => {
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("finale_error", (data) => {
    finaleWaiting = false;
    const err = data && data.error;
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
