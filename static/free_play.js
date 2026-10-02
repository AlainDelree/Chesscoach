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
let freeGameOver       = false; // partie terminée (mat ou abandon, issue #52) : coups bloqués
let freeAbandonne      = false; // terminée spécifiquement par "Abandonner" (issue #52, cf. coachBuildContext)

function freeSquareIdToAlgebraic(id) {
  const [file, rank] = id.split("-").map(Number);
  return "abcdefgh"[file] + (rank + 1);
}

function freeAlgebraicToSquareId(square) {
  const file = "abcdefgh".indexOf(square[0]);
  const rank = parseInt(square[1], 10) - 1;
  return `${file}-${rank}`;
}

// Issue #52 : "Abandonner" ne remet plus le plateau à zéro — la partie
// atteinte reste affichée (plateau, historique, bannière de fin comme pour
// un mat/pat/nulle), coups suivants bloqués via freeGameOver, pour que le
// chat libre puisse continuer à en discuter (coachBuildContext lit
// activeModeGameState(), qui reste alimenté par freeGame tant qu'il n'est
// pas réinitialisé). Le plateau ne redevient vierge qu'au démarrage explicite
// d'une nouvelle partie (startFreeGameFromFen) ou à un changement de mode
// (ensureModeSwitchClean, qui appelle cette même fonction puis le panneau du
// nouveau mode réinitialise son propre affichage).
function abandonFreeGame() {
  if (!freePlayActive || freeGameOver) return;
  freeGameOver       = true;
  freeAbandonne      = true;
  freeSelectedSquare = null;
  freeWaitingEngine  = false;
  const boardEl = document.getElementById("board");
  if (boardEl) boardEl.onclick = null;
  const statusEl = document.getElementById("free-play-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée.";
  showGameOverBanner({ gagnant: null, message: "Partie abandonnée." }, null, () => analyserPartieDepuisPgn(_freeGamePgnForAnalysis()), undefined, true);
  // Issue #65 point 5 : "Demander l'avis du coach" doit se griser dès que la
  // partie est terminée (askFreeCoach devient un no-op) — updateSharedControlBar()
  // relit MODE_CAPS.free.askCoachAvailable (controls.js), qui teste freeGameOver.
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
}

function startFreeGame() {
  startFreeGameFromFen();
}

// Variante de startFreeGame() démarrant depuis une position donnée plutôt
// que la position de départ standard (issue #41, point 3 : "rejouer un coup
// flagué avec Stockfish" du rapport d'analyse de partie — réutilise le mode
// partie libre tel quel, sans construire de nouveau mode dédié, plutôt que
// toujours repartir de la position initiale). `fen` omis = comportement
// inchangé de startFreeGame().
function startFreeGameFromFen(fen) {
  ensureModeSwitchClean("free");
  // Nouvelle partie (issue #64, vidage complet depuis l'issue #95 point 7) :
  // l'historique du chat envoyé à l'API repart de zéro ET l'affichage est
  // intégralement vidé — comme un nouvel exercice (coachClear(), cf.
  // exercise.js startExercise) plutôt qu'un simple trait séparateur
  // (coachNewSegment) qui laissait l'ancien commentaire visible sans rien
  // indiquer qu'il datait d'avant, sous un trait "Nouvelle partie" placé en
  // dessous de lui (rapport de tests GSM d'Alain).
  if (typeof coachClear === "function") coachClear();
  // coachClear() (contrairement à coachNewSegment() utilisé auparavant ici)
  // ne vide pas lui-même le tableau "Lignes du coach" du mode partie
  // (gameCoachLinesReset, game_coach_lines.js) — appel explicite pour
  // conserver ce même effet au démarrage d'une nouvelle partie.
  if (typeof gameCoachLinesReset === "function") gameCoachLinesReset();
  // Issue #71 point 6 : le rapport d'analyse affiché (Bibliothèque/Revue)
  // n'a plus de rapport avec la partie qui démarre.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  hideGameOverBanner();
  freeGame           = fen ? new Chess(fen) : new Chess();
  freePlayActive     = true;
  freeSelectedSquare = null;
  freeLastMove        = null;
  freeWaitingEngine  = false;
  freeGameOver       = false;
  freeAbandonne      = false;

  const autoCb = document.getElementById("free-auto-stockfish");
  freeAutoStockfish = !!(autoCb && autoCb.checked);
  setActiveMode("free");

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
  renderHistory();
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
  if (!freePlayActive || !freeGame || freeWaitingEngine || freeGameOver) return;
  // Une ligne du coach est affichée sur le plateau (issue #68, avant/pendant/
  // après sa lecture) : coups bloqués jusqu'au retour explicite ("Revenir à
  // la partie").
  if (typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive) return;
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

// PGN de la partie libre en cours, avec des en-têtes minimaux (issue #41,
// point d'entrée "Analyser cette partie" depuis la bannière de fin de
// partie) — freeGame n'a jamais d'en-têtes définis en temps normal (les deux
// camps peuvent être joués par Alain), donc générique plutôt que de deviner
// qui a joué quoi.
function _freeGamePgnForAnalysis() {
  if (!freeGame) return "";
  freeGame.header("White", "Partie libre (Blancs)", "Black", "Partie libre (Noirs)");
  return freeGame.pgn();
}

// "Demander l'avis du coach" en mode partie libre (issue #41, point 3 :
// requis dans le contexte d'exploration d'un coup flagué du rapport
// d'analyse, qui réutilise ce mode tel quel) — jusqu'ici jamais câblé
// (MODE_CAPS.free.askCoach à null, controls.js), la partie libre n'ayant
// pas de camp_alain propre (les deux camps peuvent être joués librement) :
// askCoachOnDemand() accepte déjà un camp_alain vide (contexte générique).
function askFreeCoach() {
  if (!freePlayActive || !freeGame || freeWaitingEngine || freeGameOver) return;
  askCoachOnDemand(freeGame.fen(), null, null);
}

function requestStockfishMove() {
  if (!freePlayActive || !freeGame || freeWaitingEngine) return;
  if (freeGame.game_over()) return;
  freeWaitingEngine = true;
  updateFreePlayStatus();
  socket.emit("free_play_stockfish_move", { fen: freeGame.fen() });
}

// ── Enregistrer la position courante comme finale (issue #13) ──────────────
// Sauvegarde la FEN courante de la partie libre (camp au trait comme
// camp_alain) dans data/finales.json, avec un nom/une description saisis
// par Alain — elle apparaît ensuite immédiatement dans le sélecteur du mode
// "Travail de finales" (finaleList/populateFinaleSelect de finales.js).

function saveFreeGameAsFinale() {
  const statusEl = document.getElementById("free-play-status");
  if (!freePlayActive || !freeGame) {
    if (statusEl) statusEl.textContent = "Démarrez d'abord une partie libre.";
    return;
  }
  const nomEl  = document.getElementById("free-finale-nom");
  const descEl = document.getElementById("free-finale-description");
  const nom = nomEl ? nomEl.value.trim() : "";
  const description = descEl ? descEl.value.trim() : "";
  if (!nom) {
    if (statusEl) statusEl.textContent = "Indiquez un nom pour cette finale avant d'enregistrer.";
    return;
  }
  const campAlain = freeGame.turn() === "w" ? "blancs" : "noirs";
  pendingFinaleAddSource = "free";
  socket.emit("finale_add", { fen: freeGame.fen(), camp_alain: campAlain, nom, description });
}

if (typeof socket !== "undefined") {
  socket.on("finale_add_response", (data) => {
    if (pendingFinaleAddSource !== "free") return;
    pendingFinaleAddSource = null;
    const statusEl = document.getElementById("free-play-status");
    if (!data || data.error) {
      if (statusEl) statusEl.textContent = "Impossible d'enregistrer cette finale (nom ou position invalide).";
      return;
    }
    if (statusEl) statusEl.textContent = `Finale "${data.nom}" enregistrée — disponible dans le mode "Travail de finales".`;
    const nomEl  = document.getElementById("free-finale-nom");
    const descEl = document.getElementById("free-finale-description");
    if (nomEl)  nomEl.value  = "";
    if (descEl) descEl.value = "";
    if (data.finales) {
      finaleList = data.finales;
      if (typeof populateFinaleSelect === "function") populateFinaleSelect();
    }
  });
}

if (typeof socket !== "undefined") {
  socket.on("free_play_stockfish_move_response", (data) => {
    freeWaitingEngine = false;
    if (!freePlayActive || !freeGame) return;

    // Issue #34 : un data.uci peut accompagner un game_over (mat délivré par
    // le coup de Stockfish lui-même) — appliquer le coup d'abord pour que le
    // plateau affiche la position finale avant la bannière de fin de partie.
    if (data && data.uci) {
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
    }

    if (data && data.game_over) {
      freeGameOver = true;
      const statusEl = document.getElementById("free-play-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, null, () => analyserPartieDepuisPgn(_freeGamePgnForAnalysis()));
      // Issue #65 point 5 : mat/pat/nulle détecté côté serveur — même
      // rafraîchissement du bouton "Demander l'avis du coach" qu'un abandon.
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      return;
    }

    if (!data || data.error || !data.uci) {
      console.warn("[partie libre] Stockfish n'a pas retourné de coup :", data && data.error);
    }
    updateFreePlayStatus();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const autoCb = document.getElementById("free-auto-stockfish");
  if (autoCb) autoCb.addEventListener("change", () => { freeAutoStockfish = autoCb.checked; });
});
