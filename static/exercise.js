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
// Vrai une fois le verdict du coach reçu pour la tentative en cours (issue
// #21) : à partir de là, les clics sur le plateau déplacent librement les
// pièces (n'importe quel camp, comme en partie libre) sans redéclencher de
// commentaire automatique — juste pour visualiser la suite (coup suggéré,
// variante) tout en gardant la conversation déjà affichée.
let exerciseExploring  = false;
// Vrai dès qu'un verdict officiel a été rendu pour l'exercice en cours, et le
// reste quel que soit le nombre de "Reprendre mon coup" utilisés ensuite
// (issue #22) — contrairement à exerciseExploring (remis à false par
// reprendreExerciceCoup avant l'obtention d'un premier verdict), ce drapeau
// ne redevient false qu'au démarrage d'un nouvel exercice, pour empêcher
// "Reprendre mon coup" de rouvrir une attente de réponse officielle une fois
// le verdict déjà rendu.
let exerciseVerdictObtenu = false;
let exerciseLastMove   = null; // { from, to } (cases algébriques) du dernier coup joué/exploré

// État de la tentative en cours, transmis au chat libre pendant l'exercice
// (issue #17) — sans ça, une question de suivi posée dans le chat libre ne
// connaît que la position/le camp (cf. coachBuildContext dans board.js), pas
// le coup proposé ni le verdict Stockfish déjà rendu par le coach.
let exerciseCoupPropose    = null; // SAN du coup proposé pour la tentative en cours
let exerciseVerdictQualite = null; // classification Stockfish du dernier verdict reçu
let exerciseVerdictDeltaCp = null;
let exerciseMeilleurCoup   = null;
let exerciseCoupReel       = null;
// Ligne (PV) réellement calculée par Stockfish pour le coup proposé et pour
// le meilleur coup (issue #20), reçue du serveur avec le verdict — transmise
// au chat libre comme les autres, pour que le coach reste ancré sur cette
// ligne (pas seulement le verdict chiffré) dans une question de suivi.
let exercisePvCoupPropose  = null;
let exercisePvMeilleurCoup = null;
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
  exercisePvCoupPropose  = null;
  exercisePvMeilleurCoup = null;
}

function startExercise() {
  exerciseAnswered  = false;
  exerciseSelected  = null;
  exerciseFenAvant  = null;
  exerciseExploring = false;
  exerciseVerdictObtenu = false;
  exerciseLastMove  = null;
  exerciseJustReprised = false;
  _exerciseResetTentative();
  _exerciseUpdateCoupReelDisplay();
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
  exerciseGame      = new Chess(exerciseFenAvant);
  exerciseAnswered  = false;
  exerciseSelected  = null;
  // Une fois un verdict officiel déjà rendu pour cet exercice, "Reprendre mon
  // coup" ne redemande plus jamais de réponse officielle : le plateau repart
  // directement en exploration libre, quel que soit le nombre de reprises
  // utilisées ensuite (issue #22). Avant tout verdict, le comportement
  // d'origine (issue #13) est inchangé : on repropose bien un premier coup
  // officiel.
  exerciseExploring = exerciseVerdictObtenu;
  exerciseLastMove  = null;
  _exerciseResetTentative();
  exerciseJustReprised = true;
  // La tentative annulée (coup proposé, verdict du coach) ne doit plus
  // induire le coach en erreur dans une question de suivi (issue #17,
  // reprise_recente dans exerciseChatContextExtra) — mais le chat déjà
  // affiché, lui, reste intact (issue #21) : reprendre son coup ne doit pas
  // faire perdre la conversation en cours pour retenter un premier coup.
  _exerciseUpdateCoupReelDisplay();
  renderExerciseBoard();
  if (statusEl) {
    const camp = exerciseCampAlain === "noirs" ? "Noirs" : "Blancs";
    statusEl.textContent = exerciseVerdictObtenu
      ? `Position de départ reprise — déplace librement les pièces pour explorer (${camp}), aucun nouveau verdict ne sera redemandé.`
      : `Coup repris — à toi de rejouer (${camp}).`;
  }
}

function _exerciseUpdateCoupReelDisplay() {
  // Repère visuel permanent (issue #21) du coup qu'Alain avait réellement
  // joué à l'époque dans sa partie d'origine (exerciseCoupReel, connu côté
  // client depuis l'issue #17) — jusque-là seulement mentionné dans la prose
  // du coach, pas affiché en tant que tel dans l'interface.
  const el    = document.getElementById("exercise-coup-reel");
  const valEl = document.getElementById("exercise-coup-reel-value");
  if (!el || !valEl) return;
  if (exerciseCoupReel) {
    valEl.textContent = exerciseCoupReel;
    el.style.display = "block";
  } else {
    el.style.display = "none";
  }
}

function askExerciseCoach() {
  // "Demander l'avis du coach" mutualisé (controls.js/MODE_CAPS), disponible
  // à tout moment pendant l'exercice — y compris pendant l'exploration libre
  // après verdict (issue #21) — pour un commentaire ponctuel sur la position
  // affichée, sans passer par le circuit exercise_answer/exercise_comment.
  if (!exerciseGame) return;
  askCoachOnDemand(exerciseGame.fen(), null, exerciseCampAlain);
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
    pv_coup_propose: exercisePvCoupPropose || "",
    pv_meilleur_coup: exercisePvMeilleurCoup || "",
    reprise_recente: exerciseJustReprised,
  };
}

function renderExerciseBoard() {
  if (!exerciseGame) return;
  const fenBoard = exerciseGame.fen().split(" ")[0];
  const from = exerciseLastMove ? freeAlgebraicToSquareId(exerciseLastMove.from) : null;
  const to   = exerciseLastMove ? freeAlgebraicToSquareId(exerciseLastMove.to)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (exerciseSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(exerciseSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  renderHistory();
}

function onExerciseBoardClick(e) {
  if (!exerciseActive || !exerciseGame) return;
  // Tant que le verdict n'est pas encore revenu pour la tentative en cours,
  // le plateau reste bloqué (le coach réfléchit) ; une fois le verdict rendu,
  // exerciseExploring passe à vrai (cf. socket.on("exercise_comment")) et le
  // plateau redevient jouable librement, sans repasser par ce garde-fou.
  if (exerciseAnswered && !exerciseExploring) return;
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

  exerciseLastMove = { from: move.from, to: move.to };

  if (exerciseExploring) {
    // Exploration libre après verdict (issue #21) : la position bouge, le
    // chat déjà affiché reste tel quel, aucun nouvel appel au coach.
    renderExerciseBoard();
    return;
  }

  renderExerciseBoard();
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
    exerciseExploring = false;
    exerciseVerdictObtenu = false;
    exerciseLastMove  = null;
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
    // Verdict rendu : le plateau devient librement explorable (issue #21),
    // sans plus jamais redéclencher exercise_answer pour cette tentative.
    exerciseExploring = true;
    // Une fois ce premier verdict obtenu pour l'exercice en cours, plus aucun
    // "Reprendre mon coup" ne doit rouvrir une attente de réponse officielle
    // (issue #22) — seul un nouvel exercice remet ce drapeau à false.
    exerciseVerdictObtenu = true;
    const statusEl = document.getElementById("exercise-status");
    if (statusEl) {
      statusEl.textContent = 'Verdict rendu — déplace librement les pièces pour explorer la suite, ou clique sur "Position suivante" pour continuer.';
    }
    // Mémorise le verdict pour l'exposer au chat libre (exerciseChatContextExtra,
    // issue #17) — jamais affiché tel quel côté UI, seulement reformulé par le
    // coach dans `text` ci-dessous.
    exerciseVerdictQualite = (data && data.verdict_qualite) || null;
    exerciseVerdictDeltaCp = (data && typeof data.verdict_delta_cp === "number") ? data.verdict_delta_cp : null;
    exerciseMeilleurCoup   = (data && data.meilleur_coup) || null;
    exerciseCoupReel       = (data && data.coup_reel) || null;
    exercisePvCoupPropose  = (data && data.pv_coup_propose) || null;
    exercisePvMeilleurCoup = (data && data.pv_meilleur_coup) || null;
    _exerciseUpdateCoupReelDisplay();
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
