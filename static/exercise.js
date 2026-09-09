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

// État de la tentative en cours, transmis au chat libre pendant l'exercice
// (issue #17) — sans ça, une question de suivi posée dans le chat libre ne
// connaît que la position/le camp (cf. coachBuildContext dans board.js), pas
// le coup proposé ni le verdict Stockfish déjà rendu par le coach.
let exerciseCoupPropose    = null; // SAN du coup proposé pour la tentative en cours
let exerciseVerdictQualite = null; // classification Stockfish du dernier verdict reçu
let exerciseVerdictDeltaCp = null;
let exerciseMeilleurCoup   = null;
let exerciseCoupReel       = null;
// Vrai juste après "Reprendre mon coup", tant qu'aucun nouveau coup n'a été
// reproposé : signale au coach que le coup/verdict discutés plus tôt dans le
// chat libre concernent une tentative annulée, pas l'état réel actuel.
let exerciseJustReprised   = false;

function exercisePhaseFiltre() {
  const sel = document.getElementById("exercise-phase-select");
  return sel ? sel.value : "toutes";
}

function _exerciseResetTentative() {
  // Réinitialise l'état de la tentative en cours (issue #17), utilisé au
  // démarrage d'un nouvel exercice comme à un "Reprendre mon coup" — sans ça,
  // le coup/verdict d'une tentative précédente ou annulée reste transmis au
  // chat libre comme s'il décrivait l'état réel actuel.
  exerciseCoupPropose    = null;
  exerciseVerdictQualite = null;
  exerciseVerdictDeltaCp = null;
  exerciseMeilleurCoup   = null;
  exerciseCoupReel       = null;
}

function startExercise() {
  exerciseAnswered = false;
  exerciseSelected = null;
  exerciseFenAvant = null;
  exerciseJustReprised = false;
  _exerciseResetTentative();
  // Nouvel exercice : le chat libre repart sans l'historique de l'exercice
  // précédent, qui n'a plus rien à voir avec la position/le coup en cours.
  if (typeof coachClear === "function") coachClear();
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
  _exerciseResetTentative();
  exerciseJustReprised = true;
  // La tentative annulée (coup proposé, verdict du coach) ne doit plus
  // induire le coach en erreur dans le chat libre (issue #17) : on repart
  // d'un historique vide plutôt que de laisser une conversation qui discute
  // d'un coup qui n'a en réalité jamais été joué.
  if (typeof coachClear === "function") coachClear();
  renderExerciseBoard();
  if (statusEl) {
    const camp = exerciseCampAlain === "noirs" ? "Noirs" : "Blancs";
    statusEl.textContent = `Coup repris — à toi de rejouer (${camp}).`;
  }
}

function exerciseChatContextExtra() {
  // Contexte enrichi pour le chat libre pendant un exercice actif (issue
  // #17), fusionné dans coachBuildContext() (board.js) : sans ça, une
  // question de suivi ne connaît que la position/le camp, pas le coup
  // proposé ni le verdict Stockfish déjà rendu par le coach (cf.
  // llm_coach._build_context_text côté serveur).
  if (!exerciseActive) return {};
  return {
    mode_exercice: true,
    coup_propose: exerciseCoupPropose || "",
    coup_reel: exerciseCoupReel || "",
    meilleur_coup: exerciseMeilleurCoup || "",
    verdict_qualite: exerciseVerdictQualite || "",
    verdict_delta_cp: exerciseVerdictDeltaCp,
    reprise_recente: exerciseJustReprised,
  };
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
  exerciseCoupPropose  = move.san;
  exerciseJustReprised = false;
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "Le coach réfléchit...";
  const messageUtilisateur = `Exercice — je joue ${move.san}`;
  _coachRenderBubble("user", messageUtilisateur);
  // Alimente aussi _coachHistory (pas seulement l'affichage), pour qu'une
  // question de suivi posée ensuite dans le chat libre (coachSend(), issue
  // #17) ait la continuité de cet échange plutôt qu'un historique vide qui
  // ignore ce qui vient d'être discuté sur cet exercice.
  if (typeof _coachHistory !== "undefined") {
    _coachHistory.push({ role: "user", content: messageUtilisateur });
  }
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
    // Mémorise le verdict pour l'exposer au chat libre (exerciseChatContextExtra,
    // issue #17) — jamais affiché tel quel côté UI, seulement reformulé par le
    // coach dans `text` ci-dessous.
    exerciseVerdictQualite = (data && data.verdict_qualite) || null;
    exerciseVerdictDeltaCp = (data && typeof data.verdict_delta_cp === "number") ? data.verdict_delta_cp : null;
    exerciseMeilleurCoup   = (data && data.meilleur_coup) || null;
    exerciseCoupReel       = (data && data.coup_reel) || null;
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) {
      _coachRenderBubble("assistant", text);
      if (typeof _coachHistory !== "undefined") {
        _coachHistory.push({ role: "assistant", content: text });
      }
    }
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
