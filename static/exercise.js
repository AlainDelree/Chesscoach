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

// Position juste après le coup proposé par Alain pour la tentative en cours
// (issue #58) — second candidat de départ possible pour une ligne citée par
// le coach, essayé seulement si la position d'avant son coup (exerciseFenAvant)
// ne rend pas la ligne légale. Remise à null à chaque nouvel exercice/reprise.
let exerciseFenApresCoup   = null;

// Tableau des lignes de coups citées par le coach pour l'exercice en cours
// (issue #58), vidé à chaque nouvel exercice. Chaque entrée :
// { key, displayText, resolved: {label, startFen, steps} | null, special }
// — resolved est null quand la ligne n'est légale depuis aucune des
// positions de départ candidates ("ligne non jouable").
let exerciseCoachLines        = [];
let exerciseStockfishLineAdded = false; // une seule ligne Stockfish par exercice
let exercisePlayingIdx        = null;   // index dans exerciseCoachLines en cours de lecture, ou null
let exercisePlaybackController = null;  // contrôleur {stop()} de coach_lines.js, ou null
// Vrai pendant qu'une ligne du coach est affichée sur le plateau (avant/après
// lecture) plutôt que la position réelle de l'exercice — bloque les clics du
// plateau (onExerciseBoardClick) tant qu'on n'est pas revenu à l'exercice.
let exerciseLinesPreviewActive = false;
let exercisePreviewSnapshot    = null;  // { fen, lastMove, selected } sauvegardés avant la 1re lecture

function exercisePhaseFiltre() {
  const sel = document.getElementById("exercise-phase-select");
  return sel ? sel.value : "toutes";
}

// ── Feuille "Nouvel exercice" (mobile, issue #63) ───────────────────────────
// Pilote le <select id="exercise-phase-select"> existant (source de vérité,
// lu par exercisePhaseFiltre() ci-dessus) au lieu de dupliquer le filtre de
// phase ; "Lancer l'exercice" appelle startExercise() sans le réécrire.
// Sans effet visuel au-dessus de 900px (cf. media query, templates/
// index.html) — la sélection/bouton d'origine dans l'onglet Exercice reste
// utilisable en toutes circonstances.

function exercisePhaseSheetPick(phase) {
  const sel = document.getElementById("exercise-phase-select");
  if (sel) sel.value = phase;
  document.querySelectorAll("#exercise-phase-options .phase-pill").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.phase === phase);
  });
}

function openExercisePhaseSheet() {
  const sel = document.getElementById("exercise-phase-select");
  exercisePhaseSheetPick(sel ? sel.value : "toutes");
  const sheet = document.getElementById("exercise-phase-sheet");
  const backdrop = document.getElementById("exercise-phase-sheet-backdrop");
  if (sheet) sheet.classList.add("open");
  if (backdrop) backdrop.classList.add("open");
}

function closeExercisePhaseSheet() {
  const sheet = document.getElementById("exercise-phase-sheet");
  const backdrop = document.getElementById("exercise-phase-sheet-backdrop");
  if (sheet) sheet.classList.remove("open");
  if (backdrop) backdrop.classList.remove("open");
}

function launchExerciseFromSheet() {
  closeExercisePhaseSheet();
  startExercise();
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

function exerciseLineStopPlayback() {
  // Interrompt la lecture en cours (bouton Stop, ou changement de ligne/
  // d'exercice) sans toucher à exerciseGame ni à l'historique du chat.
  if (exercisePlaybackController) exercisePlaybackController.stop();
  exercisePlaybackController = null;
  exercisePlayingIdx = null;
}

function _exerciseResetCoachLines() {
  // Nouvel exercice, reprise, ou abandon (issue #58) : le tableau "Lignes du
  // coach" ne doit rien conserver de la tentative précédente, et toute
  // lecture en cours doit s'arrêter proprement.
  exerciseLineStopPlayback();
  exerciseCoachLines         = [];
  exerciseStockfishLineAdded = false;
  exerciseFenApresCoup       = null;
  exerciseLinesPreviewActive = false;
  exercisePreviewSnapshot    = null;
  const restoreBtn = document.getElementById("exercise-lines-restore-btn");
  if (restoreBtn) restoreBtn.style.display = "none";
  renderExerciseCoachLinesTable();
}

// Pas d'événement serveur "exercise_abandon" : contrairement aux autres
// modes, exercise_new ne laisse aucun état serveur à nettoyer entre deux
// exercices (cf. _current_exercise, app.py, simplement remplacé au prochain
// tirage) — juste l'état client à réinitialiser avant de basculer vers un
// autre mode (issue #23, ensureModeSwitchClean dans controls.js). Pas
// exposée dans MODE_CAPS.exercise.abandon (inchangé, toujours null) : le
// bouton "Abandonner" partagé reste absent en mode exercice comme avant.
function abandonExerciseGame() {
  if (!exerciseActive) return;
  exerciseActive    = false;
  exerciseGame      = null;
  exerciseSelected  = null;
  exerciseAnswered  = false;
  exerciseExploring = false;
  exerciseVerdictObtenu = false;
  exerciseLastMove  = null;
  _exerciseResetTentative();
  _exerciseResetCoachLines();
  _exerciseUpdateCoupReelDisplay();
  resetBoardToNeutral();
  setActiveMode(null);
}

function startExercise() {
  ensureModeSwitchClean("exercise");
  exerciseAnswered  = false;
  exerciseSelected  = null;
  exerciseFenAvant  = null;
  exerciseExploring = false;
  exerciseVerdictObtenu = false;
  exerciseLastMove  = null;
  exerciseJustReprised = false;
  _exerciseResetTentative();
  _exerciseResetCoachLines();
  _exerciseUpdateCoupReelDisplay();
  // Nouvel exercice (issue #64) : l'historique envoyé à l'API repart de
  // zéro (celui de l'exercice précédent n'a plus rien à voir avec la
  // position/le coup en cours), mais reste visible à l'écran, seulement
  // démarqué par un trait discret — coachClear() (bouton "Effacer") reste le
  // seul moyen de vider entièrement l'affichage.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvel exercice");
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
  // "Reprendre mon coup" doit rendre le plateau immédiatement rejouable —
  // si une ligne du coach était en cours d'affichage/lecture (issue #58),
  // on en sort sans vider le tableau (qui reste valable pour cet exercice).
  exerciseLineStopPlayback();
  exerciseLinesPreviewActive = false;
  exercisePreviewSnapshot    = null;
  const linesRestoreBtn = document.getElementById("exercise-lines-restore-btn");
  if (linesRestoreBtn) linesRestoreBtn.style.display = "none";
  renderExerciseCoachLinesTable();
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

// ── Tableau "Lignes du coach" (issue #58) ───────────────────────────────────
// Extraction/résolution/lecture réutilisables via coach_lines.js — ici,
// seule la mécanique propre au mode exercice (quand alimenter le tableau,
// quelles positions candidates, où le dessiner).

function exerciseOnCoachText(text) {
  // Hook générique (cf. board.js, socket.on("coach_response")/
  // ("coach_on_demand_response")) : toute réponse du coach affichée pendant
  // un exercice actif (verdict, ou question de suivi posée dans le chat
  // libre pendant l'exploration après verdict) alimente aussi le tableau.
  if (!exerciseActive) return;
  _exerciseAddCoachLines(text);
}

function _exerciseAddCoachLines(text) {
  if (!exerciseFenAvant) return;
  const rawLines = extractCoachMoveLines(text);
  if (!rawLines.length) return;
  const candidates = [{ fen: exerciseFenAvant, label: "depuis la position de départ" }];
  if (exerciseFenApresCoup && exerciseFenApresCoup !== exerciseFenAvant) {
    candidates.push({ fen: exerciseFenApresCoup, label: "depuis la position après ton coup" });
  }
  let added = false;
  rawLines.forEach((moves) => {
    const key = moves.join(" ");
    if (exerciseCoachLines.some((l) => l.key === key)) return;
    const resolved = resolveCoachLineStart(candidates, moves);
    exerciseCoachLines.push({ key, displayText: key, resolved, special: null });
    added = true;
  });
  if (added) renderExerciseCoachLinesTable();
}

function _exerciseAddStockfishLine() {
  // Bonus (issue #58) : la ligne du meilleur coup déjà calculée par
  // Stockfish et transmise au coach (exercisePvMeilleurCoup, issue #20) —
  // toujours depuis exerciseFenAvant (cf. engine_stockfish._pv_to_san,
  // appelé depuis la position d'avant le coup proposé). Une seule fois par
  // exercice, même si plusieurs verdicts successifs se succèdent.
  if (exerciseStockfishLineAdded) return;
  if (!exerciseFenAvant || !exercisePvMeilleurCoup) return;
  const moveTokens = exercisePvMeilleurCoup.split(/\s+/).filter(Boolean);
  if (!moveTokens.length) return;
  exerciseStockfishLineAdded = true;
  const key = moveTokens.join(" ");
  // Même clé que celle utilisée par _exerciseAddCoachLines (le texte brut
  // des coups, sans le préfixe d'affichage) : si le coach cite ensuite
  // exactement la même ligne dans sa prose, elle ne doit pas apparaître une
  // deuxième fois sous forme de doublon.
  if (exerciseCoachLines.some((l) => l.key === key)) return;
  const resolved = resolveCoachLineStart(
    [{ fen: exerciseFenAvant, label: "depuis la position de départ" }],
    moveTokens
  );
  exerciseCoachLines.unshift({
    key,
    displayText: "Ligne de Stockfish : " + key,
    resolved,
    special: "stockfish",
  });
  renderExerciseCoachLinesTable();
}

function renderExerciseCoachLinesTable() {
  const wrap = document.getElementById("exercise-coach-lines");
  const body = document.getElementById("exercise-coach-lines-body");
  if (!wrap || !body) return;
  if (!exerciseCoachLines.length) {
    wrap.style.display = "none";
    body.innerHTML = "";
    return;
  }
  wrap.style.display = "block";
  body.innerHTML = "";
  exerciseCoachLines.forEach((line, idx) => {
    const tr = document.createElement("tr");

    const tdText = document.createElement("td");
    tdText.className = "coach-line-text";
    tdText.textContent = line.displayText;
    tr.appendChild(tdText);

    const tdLabel = document.createElement("td");
    tdLabel.className = "coach-line-label" + (line.resolved ? "" : " unresolved");
    tdLabel.textContent = line.resolved ? line.resolved.label : "ligne non jouable";
    tr.appendChild(tdLabel);

    const tdBtn = document.createElement("td");
    tdBtn.className = "coach-line-btn-cell";
    if (line.resolved) {
      const playing = exercisePlayingIdx === idx;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.id = `exercise-line-btn-${idx}`;
      btn.className = "coach-line-play-btn" + (playing ? " playing" : "");
      btn.textContent = playing ? "Stop" : "▶ Play";
      btn.onclick = () => exerciseLineToggle(idx);
      tdBtn.appendChild(btn);
    }
    tr.appendChild(tdBtn);

    body.appendChild(tr);
  });
}

function exerciseLineToggle(idx) {
  const line = exerciseCoachLines[idx];
  if (!line || !line.resolved) return;

  if (exercisePlayingIdx === idx) {
    exerciseLineStopPlayback();
    renderExerciseCoachLinesTable();
    return;
  }
  exerciseLineStopPlayback();

  if (!exerciseLinesPreviewActive) {
    // Première lecture depuis la position réelle de l'exercice (issue #58) :
    // on la mémorise pour pouvoir y revenir, quel que soit le nombre de
    // lignes rejouées ensuite avant le retour explicite.
    exercisePreviewSnapshot = {
      fen: exerciseGame.fen(),
      lastMove: exerciseLastMove,
      selected: exerciseSelected,
    };
    exerciseLinesPreviewActive = true;
    exerciseSelected = null;
    const restoreBtn = document.getElementById("exercise-lines-restore-btn");
    if (restoreBtn) restoreBtn.style.display = "inline-block";
  }

  exercisePlayingIdx = idx;
  renderExerciseCoachLinesTable();

  renderBoard(line.resolved.startFen.split(" ")[0], null, null, null, null, null, null);

  const speedSel = document.getElementById("exercise-lines-speed");
  const speedMs = speedSel ? parseInt(speedSel.value, 10) : 1000;

  exercisePlaybackController = playCoachLineSequence(line.resolved.steps, {
    speedMs,
    renderStep: (fen, from, to) => {
      renderBoard(fen.split(" ")[0], freeAlgebraicToSquareId(from), freeAlgebraicToSquareId(to), null, null, null, null);
    },
    onDone: () => {
      exercisePlayingIdx = null;
      exercisePlaybackController = null;
      renderExerciseCoachLinesTable();
    },
  });
}

function exerciseLinesRestore() {
  exerciseLineStopPlayback();
  renderExerciseCoachLinesTable();
  if (exercisePreviewSnapshot) {
    exerciseGame     = new Chess(exercisePreviewSnapshot.fen);
    exerciseLastMove = exercisePreviewSnapshot.lastMove;
    exerciseSelected = exercisePreviewSnapshot.selected;
  }
  exerciseLinesPreviewActive = false;
  exercisePreviewSnapshot    = null;
  const restoreBtn = document.getElementById("exercise-lines-restore-btn");
  if (restoreBtn) restoreBtn.style.display = "none";
  renderExerciseBoard();
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
  // Le plateau affiche une ligne du coach (issue #58, avant/pendant/après sa
  // lecture) plutôt que la position réelle de l'exercice : les clics sont
  // bloqués jusqu'au retour explicite à l'exercice ("Revenir à la position
  // de l'exercice"), pour ne jamais mélanger les deux positions.
  if (exerciseLinesPreviewActive) return;
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
  // Second candidat de départ pour une ligne citée par le coach (issue #58,
  // cf. resolveCoachLineStart) : la position juste après le coup qu'Alain
  // vient de proposer, essayée si la ligne n'est pas légale depuis
  // exerciseFenAvant (position d'avant son coup).
  exerciseFenApresCoup = exerciseGame.fen();
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
    _exerciseResetCoachLines();
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
      statusEl.textContent = 'Verdict rendu — déplace librement les pièces pour explorer la suite, ou clique sur "Nouvel exercice" pour continuer.';
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
    // Ligne de Stockfish (bonus, issue #58) : déjà calculée et transmise
    // avec le verdict (pv_meilleur_coup), pas besoin de recalcul côté client.
    _exerciseAddStockfishLine();
    const text = stripMarkdownForChat((data && data.text) || "");
    _exerciseAddCoachLines(text);
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
    if (err === "credit_insuffisant") {
      if (typeof _coachRenderCreditInsuffisant === "function") _coachRenderCreditInsuffisant();
      console.warn("[exercice]", "credit_insuffisant", data);
      return;
    }
    const msg = (err === "aucune_erreur_disponible")
      ? "Aucune position d'exercice disponible (lancer build_patterns_erreurs.py)."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : "Le coach n'a pas pu répondre, réessayez.";
    if (statusEl) statusEl.textContent = msg;
    console.warn("[exercice]", msg, data);
  });
}
