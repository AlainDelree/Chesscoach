/*
 * exercise.js — ChessCoach (issue #7)
 *
 * Mode "exercice" : positions tirées des erreurs passées d'Alain
 * (data/erreurs_detectees.json, cf. build_patterns_erreurs.py). Réutilise
 * buildBoard()/renderBoard() de board.js pour le dessin du plateau, ainsi
 * que freeSquareIdToAlgebraic()/freeAlgebraicToSquareId() et le mécanisme
 * clic-pour-jouer du mode partie libre (free_play.js) — seule la source de
 * la position (une entrée de erreurs_detectees.json, pas la position de
 * départ) et le traitement après le coup (commentaire du coach au lieu
 * d'un enchaînement Stockfish) diffèrent.
 */

let exerciseGame       = null;  // instance chess.js (position de l'exercice)
let exerciseActive     = false;
let exerciseSelected   = null;  // case algébrique sélectionnée ou null
let exerciseAnswered   = false; // un coup a déjà été proposé pour cet exercice
let exerciseFenAvant   = null;  // FEN de départ de l'exercice (issue #13, "Reprendre mon coup")
let exerciseCampAlain  = null;

function exercisePhaseFiltre() {
  const sel = document.getElementById("exercise-phase-select");
  return sel ? sel.value : "toutes";
}

function startExercise() {
  exerciseAnswered = false;
  exerciseSelected = null;
  exerciseFenAvant = null;
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "Chargement d'une position...";
  socket.emit("exercise_new", { phase: exercisePhaseFiltre() });
}

function reprendreExerciceCoup() {
  const statusEl = document.getElementById("exercise-status");
  if (!exerciseActive || !exerciseFenAvant) {
    if (statusEl) statusEl.textContent = "Aucun coup à reprendre.";
    return;
  }
  exerciseGame     = new Chess(exerciseFenAvant);
  exerciseAnswered = false;
  exerciseSelected = null;
  renderExerciseBoard();
  if (statusEl) {
    const camp = exerciseCampAlain === "noirs" ? "Noirs" : "Blancs";
    statusEl.textContent = `Coup repris — à toi de rejouer (${camp}).`;
  }
}

function renderExerciseBoard() {
  if (!exerciseGame) return;
  const fenBoard = exerciseGame.fen().split(" ")[0];
  renderBoard(fenBoard, null, null, null, null, null, null);
  if (exerciseSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(exerciseSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  renderHistory();
}

function onExerciseBoardClick(e) {
  if (!exerciseActive || !exerciseGame || exerciseAnswered) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!exerciseSelected) {
    const piece = exerciseGame.get(square);
    if (piece && piece.color === exerciseGame.turn()) {
      exerciseSelected = square;
      renderExerciseBoard();
    }
    return;
  }

  if (exerciseSelected === square) {
    exerciseSelected = null;
    renderExerciseBoard();
    return;
  }

  const move = exerciseGame.move({ from: exerciseSelected, to: square, promotion: "q" });
  exerciseSelected = null;

  if (!move) {
    // Coup illégal : si la case cliquée porte une autre pièce du joueur au
    // trait, la sélectionner à la place plutôt que de ne rien faire.
    const piece = exerciseGame.get(square);
    if (piece && piece.color === exerciseGame.turn()) {
      exerciseSelected = square;
    }
    renderExerciseBoard();
    return;
  }

  const fenBoard = exerciseGame.fen().split(" ")[0];
  renderBoard(fenBoard, freeAlgebraicToSquareId(move.from), freeAlgebraicToSquareId(move.to),
    null, null, null, null);
  submitExerciseAnswer(move);
}

function submitExerciseAnswer(move) {
  exerciseAnswered = true;
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "Le coach réfléchit...";
  _coachRenderBubble("user", `Exercice — je joue ${move.san}`);
  socket.emit("exercise_answer", { uci: move.from + move.to + (move.promotion || "") });
}

if (typeof socket !== "undefined") {
  socket.on("exercise_position", (data) => {
    if (!data || !data.fen) return;
    exerciseGame      = new Chess(data.fen);
    exerciseActive    = true;
    exerciseAnswered  = false;
    exerciseSelected  = null;
    exerciseFenAvant  = data.fen;
    exerciseCampAlain = data.camp_alain;
    setActiveMode("exercise");

    _boardFlipped = (data.camp_alain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onExerciseBoardClick;
    renderExerciseBoard();

    const statusEl = document.getElementById("exercise-status");
    if (statusEl) {
      const camp = data.camp_alain === "noirs" ? "Noirs" : "Blancs";
      statusEl.textContent = `À toi de jouer (${camp}) — que joues-tu ?`;
    }
  });

  socket.on("exercise_comment", (data) => {
    const statusEl = document.getElementById("exercise-status");
    if (statusEl) {
      statusEl.textContent = 'Réponse du coach dans le panneau de droite — clique sur "Position suivante" pour continuer.';
    }
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("exercise_error", (data) => {
    const statusEl = document.getElementById("exercise-status");
    const err = data && data.error;
    const msg = (err === "aucune_erreur_disponible")
      ? "Aucune position d'exercice disponible (lancer build_patterns_erreurs.py)."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : "Le coach n'a pas pu répondre, réessayez.";
    if (statusEl) statusEl.textContent = msg;
    console.warn("[exercice]", msg, data);
  });
}
