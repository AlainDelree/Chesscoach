/*
 * free_play.js — ChessCoach (issue #6)
 *
 * Mode "partie libre" : indépendant du mode revue de bibliothèque
 * (board.js / reviewFens / reviewMoves, laissé inchangé). Position de
 * départ standard, déplacement manuel de n'importe quelle pièce (Alain
 * contrôle les deux camps) validé côté client par chess.js, bouton
 * "Coup Stockfish" (aller-retour SocketIO avec app.py) et case "Stockfish
 * joue auto" qui enchaîne automatiquement après chaque coup manuel.
 *
 * Réutilise buildBoard()/renderBoard() de board.js pour le dessin du
 * plateau — seule la source de la position (freeGame, un objet chess.js)
 * et la gestion des clics diffèrent du mode revue.
 */

let freeGame           = null;  // instance chess.js (mode partie libre)
let freePlayActive     = false;
let freeSelectedSquare = null;  // case algébrique sélectionnée ("e2") ou null
let freeLastMove       = null;  // { from, to } (cases algébriques) du dernier coup joué
let freeAutoStockfish  = false;
let freeWaitingEngine  = false; // évite les double-clics pendant l'attente de Stockfish

function freeSquareIdToAlgebraic(id) {
  const [file, rank] = id.split("-").map(Number);
  return "abcdefgh"[file] + (rank + 1);
}

function freeAlgebraicToSquareId(square) {
  const file = "abcdefgh".indexOf(square[0]);
  const rank = parseInt(square[1], 10) - 1;
  return `${file}-${rank}`;
}

function startFreeGame() {
  freeGame           = new Chess();
  freePlayActive     = true;
  freeSelectedSquare = null;
  freeLastMove        = null;
  freeWaitingEngine  = false;

  const autoCb = document.getElementById("free-auto-stockfish");
  freeAutoStockfish = !!(autoCb && autoCb.checked);

  buildBoard();
  const boardEl = document.getElementById("board");
  if (boardEl) {
    boardEl.classList.add("free-play-active");
    boardEl.onclick = onFreePlayBoardClick;
  }
  renderFreePlayBoard();
  updateFreePlayStatus();
}

function renderFreePlayBoard() {
  if (!freeGame) return;
  const fenBoard = freeGame.fen().split(" ")[0];
  const from = freeLastMove ? freeAlgebraicToSquareId(freeLastMove.from) : null;
  const to   = freeLastMove ? freeAlgebraicToSquareId(freeLastMove.to)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (freeSelectedSquare) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(freeSelectedSquare)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
}

function updateFreePlayStatus() {
  const statusEl = document.getElementById("free-play-status");
  if (!statusEl || !freeGame) return;
  let text = freeGame.turn() === "w" ? "Trait aux Blancs" : "Trait aux Noirs";
  if (freeGame.in_checkmate())      text = "Échec et mat.";
  else if (freeGame.in_stalemate()) text = "Pat.";
  else if (freeGame.in_draw())      text = "Partie nulle.";
  else if (freeGame.in_check())     text += " (échec)";
  if (freeWaitingEngine) text += " — Stockfish réfléchit...";
  statusEl.textContent = text;
}

function onFreePlayBoardClick(e) {
  if (!freePlayActive || !freeGame || freeWaitingEngine) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!freeSelectedSquare) {
    const piece = freeGame.get(square);
    if (piece && piece.color === freeGame.turn()) {
      freeSelectedSquare = square;
      renderFreePlayBoard();
    }
    return;
  }

  if (freeSelectedSquare === square) {
    freeSelectedSquare = null;
    renderFreePlayBoard();
    return;
  }

  const move = freeGame.move({ from: freeSelectedSquare, to: square, promotion: "q" });
  freeSelectedSquare = null;

  if (!move) {
    // Coup illégal : si la case cliquée porte une autre pièce du joueur au
    // trait, la sélectionner à la place plutôt que de ne rien faire.
    const piece = freeGame.get(square);
    if (piece && piece.color === freeGame.turn()) {
      freeSelectedSquare = square;
    }
    renderFreePlayBoard();
    return;
  }

  freeLastMove = { from: move.from, to: move.to };
  renderFreePlayBoard();
  updateFreePlayStatus();

  if (freeAutoStockfish && !freeGame.game_over()) {
    requestStockfishMove();
  }
}

function requestStockfishMove() {
  if (!freePlayActive || !freeGame || freeWaitingEngine) return;
  if (freeGame.game_over()) return;
  freeWaitingEngine = true;
  updateFreePlayStatus();
  socket.emit("free_play_stockfish_move", { fen: freeGame.fen() });
}

if (typeof socket !== "undefined") {
  socket.on("free_play_stockfish_move_response", (data) => {
    freeWaitingEngine = false;
    if (!freePlayActive || !freeGame) return;

    if (!data || data.error || !data.uci) {
      console.warn("[partie libre] Stockfish n'a pas retourné de coup :", data && data.error);
      updateFreePlayStatus();
      return;
    }

    const uci = data.uci;
    const move = freeGame.move({
      from: uci.slice(0, 2),
      to: uci.slice(2, 4),
      promotion: uci.slice(4, 5) || "q",
    });
    if (move) {
      freeLastMove = { from: move.from, to: move.to };
      renderFreePlayBoard();
    }
    updateFreePlayStatus();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const autoCb = document.getElementById("free-auto-stockfish");
  if (autoCb) autoCb.addEventListener("change", () => { freeAutoStockfish = autoCb.checked; });
});
