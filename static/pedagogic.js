/*
 * pedagogic.js — ChessCoach (issue #8)
 *
 * Mode "partie pédagogique" : combine le mode partie libre (issue #6, plateau
 * interactif clic-pour-jouer, réponse automatique de Stockfish) et le mode
 * exercice (issue #7, appel au coach avec comparaison coup_propose/
 * meilleur_coup). Alain joue un seul camp du début à la fin, Stockfish (force
 * réduite côté serveur, cf. EngineManager.get_move_pedagogique) répond
 * automatiquement à chacun de ses coups, et le coach commente chaque coup
 * d'Alain au fil de la partie.
 *
 * Réutilise buildBoard()/renderBoard() de board.js et
 * freeSquareIdToAlgebraic()/freeAlgebraicToSquareId() de free_play.js — seule
 * la source de la position (une nouvelle partie, pas la revue ni un
 * exercice figé) et le traitement après le coup (commentaire du coach +
 * réponse Stockfish enchaînée) diffèrent.
 */

let pedagogicGame       = null;  // instance chess.js (partie pédagogique)
let pedagogicActive     = false;
let pedagogicCampAlain  = "blancs";
let pedagogicSelected   = null;  // case algébrique sélectionnée ou null
let pedagogicWaiting    = false; // coup en cours de traitement côté serveur
let pedagogicGameOver   = false; // fin de partie détectée côté serveur (issue #11)
let pedagogicFenAvantCoup = null; // FEN juste avant le dernier coup d'Alain (issue #13, "Reprendre mon coup")

function pedagogicCommenterChaqueCoup() {
  const cb = document.getElementById("shared-auto-comment");
  return !!(cb && cb.checked);
}

function startPedagogicGame(camp) {
  ensureModeSwitchClean("pedagogic");
  hideGameOverBanner();
  pedagogicCampAlain = (camp === "noirs") ? "noirs" : "blancs";
  pedagogicWaiting   = true;
  pedagogicGameOver  = false;
  pedagogicFenAvantCoup = null;
  const statusEl = document.getElementById("pedagogic-status");
  if (statusEl) statusEl.textContent = "Démarrage de la partie...";
  socket.emit("pedagogic_start", { camp: pedagogicCampAlain });
}

function abandonPedagogicGame() {
  if (!pedagogicActive) return;
  socket.emit("pedagogic_abandon", {});
  pedagogicActive    = false;
  pedagogicGame      = null;
  pedagogicWaiting   = false;
  pedagogicSelected  = null;
  pedagogicGameOver  = false;
  pedagogicFenAvantCoup = null;
  resetBoardToNeutral();
  setActiveMode(null);
  const statusEl = document.getElementById("pedagogic-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée.";
}

function reprendrePedagogicCoup() {
  const statusEl = document.getElementById("pedagogic-status");
  if (!pedagogicActive || pedagogicWaiting || !pedagogicFenAvantCoup) {
    if (statusEl && pedagogicActive && !pedagogicWaiting) statusEl.textContent = "Aucun coup à reprendre.";
    return;
  }
  pedagogicGame     = new Chess(pedagogicFenAvantCoup);
  pedagogicGameOver = false;
  pedagogicSelected = null;
  pedagogicFenAvantCoup = null;
  hideGameOverBanner();
  renderPedagogicBoard();
  updatePedagogicStatus();
}

function askPedagogicCoach() {
  if (!pedagogicActive || !pedagogicGame || pedagogicGameOver || pedagogicWaiting) return;
  askCoachOnDemand(pedagogicGame.fen(), null, pedagogicCampAlain);
}

function renderPedagogicBoard(lastFrom, lastTo) {
  if (!pedagogicGame) return;
  const fenBoard = pedagogicGame.fen().split(" ")[0];
  const from = lastFrom ? freeAlgebraicToSquareId(lastFrom) : null;
  const to   = lastTo   ? freeAlgebraicToSquareId(lastTo)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (pedagogicSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(pedagogicSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  renderHistory();
}

function updatePedagogicStatus() {
  const statusEl = document.getElementById("pedagogic-status");
  if (!statusEl || !pedagogicGame) return;
  let text = pedagogicGame.turn() === "w" ? "Trait aux Blancs" : "Trait aux Noirs";
  if (pedagogicGame.in_checkmate())      text = "Échec et mat.";
  else if (pedagogicGame.in_stalemate()) text = "Pat.";
  else if (pedagogicGame.in_draw())      text = "Partie nulle.";
  else if (pedagogicGame.in_check())     text += " (échec)";
  if (pedagogicWaiting) text += " — le coach et Stockfish réfléchissent...";
  statusEl.textContent = text;
}

function pedagogicIsAlainTurn() {
  if (!pedagogicGame) return false;
  const trait = pedagogicGame.turn() === "w" ? "blancs" : "noirs";
  return trait === pedagogicCampAlain;
}

function onPedagogicBoardClick(e) {
  if (!pedagogicActive || !pedagogicGame || pedagogicWaiting || pedagogicGameOver) return;
  if (!pedagogicIsAlainTurn()) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!pedagogicSelected) {
    const piece = pedagogicGame.get(square);
    if (piece && piece.color === pedagogicGame.turn()) {
      pedagogicSelected = square;
      renderPedagogicBoard();
    }
    return;
  }

  if (pedagogicSelected === square) {
    pedagogicSelected = null;
    renderPedagogicBoard();
    return;
  }

  const fenAvant = pedagogicGame.fen();
  const move = pedagogicGame.move({ from: pedagogicSelected, to: square, promotion: "q" });
  pedagogicSelected = null;

  if (!move) {
    const piece = pedagogicGame.get(square);
    if (piece && piece.color === pedagogicGame.turn()) {
      pedagogicSelected = square;
    }
    renderPedagogicBoard();
    return;
  }

  renderPedagogicBoard(move.from, move.to);
  pedagogicWaiting = true;
  pedagogicFenAvantCoup = fenAvant;
  updatePedagogicStatus();
  _coachRenderBubble("user", `Partie pédagogique — je joue ${move.san}`);
  socket.emit("pedagogic_move", {
    fen_avant: fenAvant,
    uci: move.from + move.to + (move.promotion || ""),
    commenter: pedagogicCommenterChaqueCoup(),
  });
}

if (typeof socket !== "undefined") {
  socket.on("pedagogic_started", (data) => {
    if (!data || !data.fen) return;
    pedagogicGame      = new Chess(data.fen);
    pedagogicActive    = true;
    pedagogicWaiting   = false;
    pedagogicSelected  = null;
    pedagogicGameOver  = false;
    pedagogicCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    setActiveMode("pedagogic");

    _boardFlipped = (pedagogicCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onPedagogicBoardClick;

    let lastFrom = null, lastTo = null;
    if (data.coup_ouverture) {
      lastFrom = data.coup_ouverture.slice(0, 2);
      lastTo   = data.coup_ouverture.slice(2, 4);
    }
    renderPedagogicBoard(lastFrom, lastTo);
    updatePedagogicStatus();
  });

  socket.on("pedagogic_stockfish_move", (data) => {
    pedagogicWaiting = false;
    if (!pedagogicActive || !pedagogicGame || !data) return;

    if (data.uci) {
      const move = pedagogicGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderPedagogicBoard(move.from, move.to);
      }
    }
    if (data.game_over) {
      pedagogicGameOver = true;
      const statusEl = document.getElementById("pedagogic-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, pedagogicCampAlain);
      return;
    }
    updatePedagogicStatus();
  });

  socket.on("pedagogic_comment", (data) => {
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("pedagogic_error", (data) => {
    pedagogicWaiting = false;
    const err = data && data.error;
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : (err === "coup_illegal")
      ? "Coup illégal détecté côté serveur."
      : "Le coach n'a pas pu répondre, réessayez.";
    const statusEl = document.getElementById("pedagogic-status");
    if (statusEl) statusEl.textContent = msg;
    console.warn("[partie pédagogique]", msg, data);
  });
}
