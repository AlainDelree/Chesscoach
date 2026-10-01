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
// Dernier coup UCI soumis à exercise_answer (issue #79) — mémorisé pour que
// le bouton "Réessayer" (affiché quand l'analyse Stockfish échoue, cf.
// socket.on("exercise_error") ci-dessous) puisse rejouer exactement le même
// appel sans redemander le coup à Alain (déjà joué sur l'échiquier local).
let exerciseLastSubmittedUci = null;
// Identifiant du minuteur de garde (issue #79, point 3) : si le verdict ne
// revient pas sous ~30s (délai côté interface, indépendant de la reprise
// automatique côté serveur), affiche le message d'indisponibilité et
// débloque le plateau plutôt que de rester bloqué indéfiniment sur "Le
// coach réfléchit...".
let exerciseAnalysisTimeoutId = null;
const EXERCISE_ANALYSIS_TIMEOUT_MS = 30000;
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
// Détail coup par coup de ces deux lignes (description mécanique + solde
// matériel cumulé pour Alain après chaque demi-coup, issue #75 point 3),
// reçu du serveur avec le verdict (game_facts.describe_pv_with_balance/
// format_pv_with_balance) — sans ce détail, une question de suivi dans le
// chat libre perdait l'ancrage sur le bilan matériel réel de la ligne dès le
// tour suivant.
let exercisePvCoupProposeDetail  = null;
let exercisePvMeilleurCoupDetail = null;
// Description mécanique de chacun des trois coups comparés (pièce, case de
// départ/arrivée, capture, défenseurs, solde net — issue #73), reçue du
// serveur avec le verdict (game_facts.describe_move_mechanically, calculée
// sur la position de DÉPART de l'exercice) : sans elles, une question de
// suivi dans le chat libre perdait ce détail dès le tour suivant, et le
// coach ne pouvait répondre qu'à partir du seul nom SAN du coup.
let exerciseCoupProposeDescriptionMecanique    = null;
let exerciseCoupReelDescriptionMecanique       = null;
let exerciseMeilleurCoupDescriptionMecanique   = null;
// Évaluation Stockfish de la position résultant du coup proposé, point de
// vue d'Alain (issue #73 : positif = avantage pour Alain), reçue du serveur
// avec le verdict — transmise au chat libre comme le reste de ce contexte.
let exerciseEvalAlainCp    = null;
let exerciseEvalAlainMat   = null;
// Vrai juste après "Reprendre mon coup", tant qu'aucun nouveau coup n'a été
// reproposé : signale au coach que le coup/verdict discutés plus tôt dans le
// chat libre concernent une tentative annulée, pas l'état réel actuel.
let exerciseJustReprised   = false;

// Phase (catégorie) du dernier exercice tiré, quel que soit le sélecteur de
// phase courant (issue #76, "Exercice suivant") — distincte de
// exercisePhaseFiltre() (lit le <select>/la feuille mobile) : "Exercice
// suivant" doit relancer la MÊME catégorie que l'exercice en cours même si
// Alain a changé le sélecteur entre-temps sans relancer de tirage.
let exerciseCurrentPhase   = "toutes";

// Source du dernier exercice tiré (issue #78 : "mes_erreurs" ou "lichess"),
// même rôle qu'exerciseCurrentPhase ci-dessus — "Exercice suivant" relance
// la même source que l'exercice en cours, pas forcément celle du sélecteur.
let exerciseCurrentSource  = "mes_erreurs";
// Détail du problème Lichess en cours (issue #78), affiché dans
// #exercise-lichess-info — null pour la source "mes erreurs".
let exerciseLichessCategorieLibelle = null;
let exerciseLichessRating           = null;
let exerciseLichessNiveau           = null;
let exerciseLichessThemes           = null; // thèmes Lichess bruts, chaîne séparée par espaces

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

// Source choisie (issue #78) : "mes_erreurs" (défaut) ou "lichess" — même
// rôle que exercisePhaseFiltre() ci-dessus, lit le <select> partagé par le
// desktop et la feuille mobile (source de vérité commune).
function exerciseSourceFiltre() {
  const sel = document.getElementById("exercise-source-select");
  return sel ? sel.value : "mes_erreurs";
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

// Pendant de exercisePhaseSheetPick ci-dessus pour la source (issue #78) —
// pilote le même <select id="exercise-source-select"> que le desktop.
function exerciseSourceSheetPick(source) {
  const sel = document.getElementById("exercise-source-select");
  if (sel && !(source === "lichess" && sel.querySelector('option[value="lichess"]').disabled)) {
    sel.value = source;
  }
  document.querySelectorAll("#exercise-source-options .phase-pill").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.source === (sel ? sel.value : source));
  });
}

function openExercisePhaseSheet() {
  const sel = document.getElementById("exercise-phase-select");
  exercisePhaseSheetPick(sel ? sel.value : "toutes");
  const sourceSel = document.getElementById("exercise-source-select");
  exerciseSourceSheetPick(sourceSel ? sourceSel.value : "mes_erreurs");
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
  exercisePvCoupProposeDetail  = null;
  exercisePvMeilleurCoupDetail = null;
  exerciseCoupProposeDescriptionMecanique  = null;
  exerciseCoupReelDescriptionMecanique     = null;
  exerciseMeilleurCoupDescriptionMecanique = null;
  exerciseEvalAlainCp    = null;
  exerciseEvalAlainMat   = null;
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
  _exerciseUpdateDejaFaitDisplay(null);
  _exerciseUpdateLichessInfoDisplay();
  resetBoardToNeutral();
  setActiveMode(null);
}

function startExercise(phaseOverride, sourceOverride) {
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
  _exerciseUpdateDejaFaitDisplay(null);
  _exerciseUpdateLichessInfoDisplay();
  // Nouvel exercice (issue #64) : l'historique envoyé à l'API repart de
  // zéro (celui de l'exercice précédent n'a plus rien à voir avec la
  // position/le coup en cours), mais reste visible à l'écran, seulement
  // démarqué par un trait discret — coachClear() (bouton "Effacer") reste le
  // seul moyen de vider entièrement l'affichage.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvel exercice");
  // Issue #71 point 6 : le rapport d'analyse affiché (Bibliothèque/Revue)
  // n'a plus de rapport avec l'exercice qui démarre.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "Chargement d'une position...";
  // phaseOverride/sourceOverride (issue #76/#78, startNextExercise
  // ci-dessous) : phase et source de l'exercice en cours plutôt que celles
  // des sélecteurs, quand fournies.
  socket.emit("exercise_new", {
    phase: phaseOverride || exercisePhaseFiltre(),
    source: sourceOverride || exerciseSourceFiltre(),
  });
}

function startNextExercise() {
  // Bouton "Exercice suivant" (issue #76, source conservée depuis l'issue
  // #78) : relance directement un exercice de la même catégorie (phase) ET
  // de la même source que l'exercice en cours, abandonné ou tout juste
  // terminé, sans ouvrir la feuille ni les sélecteurs — à la différence de
  // "Nouvel exercice"/"Autre catégorie", qui repassent par le choix de
  // phase/source. Disponible dans tous les états d'un exercice déjà chargé
  // (réponse donnée, exploration libre après verdict, ou même avant toute
  // réponse — cliquer dessus revient alors à abandonner l'exercice en
  // cours) : comme exercise_new, ce tirage ne laisse aucun état serveur à
  // nettoyer entre deux exercices (cf. _current_exercise, app.py).
  startExercise(exerciseCurrentPhase, exerciseCurrentSource);
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
  //
  // Source "Problèmes Lichess" (issue #78) : exercisePvMeilleurCoup porte
  // alors la solution DÉCLARÉE du problème (pas une ligne recalculée par
  // Stockfish, cf. app.py _on_exercise_answer_lichess), affichée ici avec
  // le libellé "Solution du problème" plutôt que "Ligne de Stockfish" —
  // même mécanisme de Play réutilisé tel quel (issue #78, point 4).
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
  const prefixe = exerciseCurrentSource === "lichess" ? "Solution du problème : " : "Ligne de Stockfish : ";
  exerciseCoachLines.unshift({
    key,
    displayText: prefixe + key,
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
  // pendant l'exploration libre après verdict (issue #21) pour un
  // commentaire ponctuel sur la position affichée, sans passer par le
  // circuit exercise_answer/exercise_comment.
  //
  // Issue #79, point 4a : désactivé et grisé tant qu'aucun verdict n'a été
  // obtenu pour la tentative en cours (cf. MODE_CAPS.exercise.
  // askCoachAvailable, controls.js, qui pilote déjà le disabled du bouton
  // partagé) — ce garde-fou ici est redondant avec le bouton désactivé
  // (qui ne déclenche alors aucun clic), gardé par prudence en défense en
  // profondeur, comme le reste des garde-fous ajoutés par cette issue.
  //
  // Issue #75, point 5 : ce bouton ne transmettait jusqu'ici que la position
  // actuelle et le camp d'Alain (comme les autres modes), sans la position
  // de DÉPART de l'exercice ni les descriptions mécaniques des coups déjà
  // discutés — contrairement à une question posée dans le chat libre
  // pendant le même exercice, qui fusionne déjà exerciseChatContextExtra().
  // On transmet donc ce même contexte enrichi en 4e argument, fusionné
  // côté serveur (app.py on_coach_comment_on_demand) dans le contexte
  // envoyé au coach.
  if (!exerciseGame || !exerciseVerdictObtenu) return;
  askCoachOnDemand(exerciseGame.fen(), null, exerciseCampAlain, exerciseChatContextExtra());
}

function exerciseChatContextExtra() {
  // Contexte enrichi pour le chat libre pendant un exercice actif (issue
  // #17), fusionné dans coachBuildContext() (board.js) : sans ça, une
  // question de suivi ne connaît que la position/le camp, pas le coup
  // proposé ni le verdict Stockfish déjà rendu par le coach (cf.
  // llm_coach._build_context_text côté serveur).
  //
  // fen_depart_exercice (issue #73) : la position de DÉPART de l'exercice,
  // distincte du FEN "actuel" déjà transmis par coachBuildContext() (board.js,
  // state.fen = exerciseGame.fen() — déjà après le coup proposé, ou déplacé
  // par une exploration libre). Sans ce champ séparé, une question de suivi
  // ne transmettait QUE la position actuelle, lue à tort par le coach comme
  // si elle était la position de départ (constat en usage réel : une pièce
  // capturée par le coup proposé niée comme n'ayant jamais existé).
  //
  // Les descriptions mécaniques et l'évaluation point de vue d'Alain
  // (issue #73) complètent ce contexte comme au moment du verdict, pour
  // qu'une question de suivi dispose exactement des mêmes données.
  if (!exerciseActive) return {};
  return {
    mode_exercice: true,
    fen_depart_exercice: exerciseFenAvant || "",
    coup_propose: exerciseCoupPropose || "",
    coup_propose_description_mecanique: exerciseCoupProposeDescriptionMecanique || "",
    coup_reel: exerciseCoupReel || "",
    coup_reel_description_mecanique: exerciseCoupReelDescriptionMecanique || "",
    meilleur_coup: exerciseMeilleurCoup || "",
    meilleur_coup_description_mecanique: exerciseMeilleurCoupDescriptionMecanique || "",
    verdict_qualite: exerciseVerdictQualite || "",
    verdict_delta_cp: exerciseVerdictDeltaCp,
    pv_coup_propose: exercisePvCoupPropose || "",
    pv_meilleur_coup: exercisePvMeilleurCoup || "",
    pv_coup_propose_detail: exercisePvCoupProposeDetail || "",
    pv_meilleur_coup_detail: exercisePvMeilleurCoupDetail || "",
    eval_alain_cp: exerciseEvalAlainCp,
    eval_alain_mat: exerciseEvalAlainMat,
    reprise_recente: exerciseJustReprised,
    // Source "Problèmes Lichess" (issue #78) : absents (undefined, ignorés
    // par llm_coach._build_context_text) pour la source "mes erreurs".
    source_lichess: exerciseCurrentSource === "lichess",
    themes_lichess: exerciseLichessThemes || "",
    rating_probleme: exerciseLichessRating,
    niveau_categorie: exerciseLichessNiveau,
    categorie_libelle: exerciseLichessCategorieLibelle || "",
  };
}

function _exerciseUpdateLichessInfoDisplay() {
  // Ligne d'état dédiée à la source "Problèmes Lichess" (issue #78) :
  // "Problème <note> · ton niveau en <catégorie> <niveau>" — masquée pour la
  // source "mes erreurs" ou tant qu'aucun problème Lichess n'est chargé.
  const el = document.getElementById("exercise-lichess-info");
  if (!el) return;
  if (exerciseCurrentSource !== "lichess" || exerciseLichessRating === null) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  const libelle = exerciseLichessCategorieLibelle || "";
  el.textContent = `Problème ${exerciseLichessRating} · ton niveau en ${libelle} ${exerciseLichessNiveau}`;
  el.style.display = "block";
}

function _exerciseUpdateDejaFaitDisplay(data) {
  // Indicateur "déjà fait" (issue #76) : mention discrète et non cliquable
  // (couleur --cc-text-muted, jamais --cc-accent/terracotta réservé au
  // cliquable — cf. board.css), visible dès l'affichage de la position,
  // absente pour une position jamais proposée (data.deja_fait=false) ou
  // pendant le chargement (data=null). N'empêche jamais de rejouer
  // l'exercice : purement informative, aucun handler de clic.
  const el = document.getElementById("exercise-deja-fait");
  if (!el) return;
  if (!data || !data.deja_fait) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  const nbFois = data.nb_fois || 0;
  const foisTexte = nbFois === 1 ? "1 fois" : `${nbFois} fois`;
  const resultatTexte = data.dernier_resultat === "reussi" ? "réussi"
    : data.dernier_resultat === "rate" ? "raté"
    : "inconnu";
  el.textContent = `Déjà fait · ${foisTexte} · dernier résultat : ${resultatTexte}`;
  el.style.display = "block";
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
  exerciseLastSubmittedUci = move.from + move.to + (move.promotion || "");
  _exerciseStartAnalysisWatchdog();
  socket.emit("exercise_answer", { uci: exerciseLastSubmittedUci });
}

function _exerciseClearAnalysisWatchdog() {
  if (exerciseAnalysisTimeoutId !== null) {
    clearTimeout(exerciseAnalysisTimeoutId);
    exerciseAnalysisTimeoutId = null;
  }
}

function _exerciseStartAnalysisWatchdog() {
  _exerciseClearAnalysisWatchdog();
  exerciseAnalysisTimeoutId = setTimeout(_exerciseShowAnalysisIndisponible, EXERCISE_ANALYSIS_TIMEOUT_MS);
}

function _exerciseShowAnalysisIndisponible() {
  // Issue #79, point 3 : si le verdict n'est pas revenu après ~30s côté
  // interface (indépendant de la reprise automatique côté serveur, qui a
  // son propre délai par appel), remplace "Le coach réfléchit..." par un
  // message clair avec un bouton "Réessayer" — l'exercice reste utilisable
  // (plateau explorable, "Exercice suivant" toujours cliquable) plutôt que
  // bloqué indéfiniment. N'affecte jamais exerciseVerdictObtenu : tant
  // qu'aucun vrai verdict n'est arrivé, le champ de question/les boutons du
  // coach restent désactivés (issue #79, point 4a).
  exerciseAnalysisTimeoutId = null;
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "L'analyse Stockfish est indisponible.";
  const retryBtn = document.getElementById("exercise-retry-btn");
  if (retryBtn) retryBtn.style.display = exerciseLastSubmittedUci ? "inline-block" : "none";
  exerciseExploring = true;
}

function exerciseRetryAnalysis() {
  const retryBtn = document.getElementById("exercise-retry-btn");
  if (retryBtn) retryBtn.style.display = "none";
  if (!exerciseLastSubmittedUci) return;
  const statusEl = document.getElementById("exercise-status");
  if (statusEl) statusEl.textContent = "Le coach réfléchit...";
  // Redevient bloqué pendant cette nouvelle tentative, comme au premier
  // essai — remis à true par exercise_comment (succès) ou par l'échec
  // suivant (exercise_error/watchdog), jamais laissé à false entre-temps.
  exerciseExploring = false;
  _exerciseStartAnalysisWatchdog();
  socket.emit("exercise_answer", { uci: exerciseLastSubmittedUci });
}

function _exerciseUpdateCoachInputGating() {
  // Issue #79, point 4a : champ de question + bouton "Envoyer" du chat
  // libre désactivés et grisés tant qu'aucun verdict n'a été obtenu pour
  // l'exercice en cours (y compris la source « Problèmes Lichess », qui
  // réutilise exactement les mêmes drapeaux) — le bouton partagé "Demander
  // l'avis du coach" est géré séparément par controls.js (MODE_CAPS.exercise.
  // askCoachAvailable). Rappelée au changement de mode (cf. setActiveMode,
  // controls.js) pour ne pas laisser le champ désactivé en quittant
  // l'exercice vers un autre mode.
  const gated = activeMode === "exercise" && exerciseActive && !exerciseVerdictObtenu;
  const input = document.getElementById("coach-input");
  const sendBtn = document.getElementById("coach-send-btn");
  if (input) {
    input.disabled = gated;
    input.placeholder = gated ? "Disponible après le verdict" : "Votre question...";
  }
  if (sendBtn) sendBtn.disabled = gated;
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
    exerciseLastSubmittedUci = null;
    _exerciseClearAnalysisWatchdog();
    const retryBtnReset = document.getElementById("exercise-retry-btn");
    if (retryBtnReset) retryBtnReset.style.display = "none";
    exerciseFenAvant  = data.fen;
    exerciseCampAlain = data.camp_alain;
    exerciseCurrentPhase  = data.phase || "toutes";
    // Source de ce tirage (issue #78) — mémorisée pour "Exercice suivant"
    // (exerciseCurrentSource) et pour l'affichage (libellé "Solution du
    // problème", ligne d'état dédiée).
    exerciseCurrentSource = data.source || "mes_erreurs";
    exerciseLichessCategorieLibelle = data.categorie_libelle || null;
    exerciseLichessRating           = (typeof data.rating === "number") ? data.rating : null;
    exerciseLichessNiveau           = (typeof data.niveau === "number") ? data.niveau : null;
    exerciseLichessThemes           = Array.isArray(data.themes) ? data.themes.join(" ") : null;
    _exerciseResetCoachLines();
    _exerciseUpdateDejaFaitDisplay(data);
    _exerciseUpdateLichessInfoDisplay();
    setActiveMode("exercise");
    _exerciseUpdateCoachInputGating();

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
    // Issue #79 : le verdict est bien arrivé — plus besoin du minuteur de
    // garde ni du bouton "Réessayer" affiché par un échec précédent (ex.
    // panne transitoire suivie d'un "Réessayer" réussi).
    _exerciseClearAnalysisWatchdog();
    const retryBtnOk = document.getElementById("exercise-retry-btn");
    if (retryBtnOk) retryBtnOk.style.display = "none";
    // Verdict rendu : le plateau devient librement explorable (issue #21),
    // sans plus jamais redéclencher exercise_answer pour cette tentative.
    exerciseExploring = true;
    // Une fois ce premier verdict obtenu pour l'exercice en cours, plus aucun
    // "Reprendre mon coup" ne doit rouvrir une attente de réponse officielle
    // (issue #22) — seul un nouvel exercice remet ce drapeau à false.
    exerciseVerdictObtenu = true;
    // Issue #79, point 4a : champ de question/bouton "Envoyer" du chat
    // libre et bouton "Demander l'avis du coach" (ce dernier via
    // updateSharedControlBar, controls.js) redeviennent disponibles.
    _exerciseUpdateCoachInputGating();
    if (typeof updateSharedControlBar === "function") updateSharedControlBar();
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
    exercisePvCoupProposeDetail  = (data && data.pv_coup_propose_detail) || null;
    exercisePvMeilleurCoupDetail = (data && data.pv_meilleur_coup_detail) || null;
    // Descriptions mécaniques et évaluation point de vue d'Alain (issue #73),
    // mémorisées pour être réinjectées dans une question de suivi du chat
    // libre (exerciseChatContextExtra ci-dessous).
    exerciseCoupProposeDescriptionMecanique  = (data && data.coup_propose_description_mecanique) || null;
    exerciseCoupReelDescriptionMecanique     = (data && data.coup_reel_description_mecanique) || null;
    exerciseMeilleurCoupDescriptionMecanique = (data && data.meilleur_coup_description_mecanique) || null;
    exerciseEvalAlainCp  = (data && typeof data.eval_alain_cp === "number") ? data.eval_alain_cp : null;
    exerciseEvalAlainMat = (data && typeof data.eval_alain_mat === "number") ? data.eval_alain_mat : null;
    // Niveau de la catégorie mis à jour après ce résultat (issue #78) — la
    // ligne d'état "Problème <note> · ton niveau en <catégorie> <niveau>"
    // reflète donc le niveau APRÈS ce résultat, pas celui du tirage.
    if (data && typeof data.niveau === "number") exerciseLichessNiveau = data.niveau;
    _exerciseUpdateCoupReelDisplay();
    _exerciseUpdateLichessInfoDisplay();
    // Ligne de Stockfish (bonus, issue #58) : déjà calculée et transmise
    // avec le verdict (pv_meilleur_coup), pas besoin de recalcul côté client.
    _exerciseAddStockfishLine();
    const text = stripMarkdownForChat((data && data.text) || "");
    _exerciseAddCoachLines(text);
    if (text) {
      // Verdict de l'exercice : Alain l'attend, la page doit défiler jusqu'à
      // lui sur mobile (issue #67, comportement voulu par la maquette).
      _coachRenderBubble("assistant", text, true);
      if (typeof _coachHistory !== "undefined") {
        _coachHistory.push({ role: "assistant", content: text });
      }
    }
  });

  socket.on("exercise_error", (data) => {
    _exerciseClearAnalysisWatchdog();
    const statusEl = document.getElementById("exercise-status");
    const err = data && data.error;
    // Issue #79, point 3 : un échec pendant exercise_answer (coup déjà joué
    // sur l'échiquier local) ne doit plus jamais laisser le plateau bloqué
    // sur "Le coach réfléchit..." — le plateau redevient explorable (comme
    // après un verdict normal) et "Réessayer" permet de relancer exactement
    // la même tentative. Ne s'applique qu'après un exercise_answer en
    // attente (exerciseAnswered && !exerciseExploring) : une erreur de
    // tirage (exercise_new, ex. "aucune_erreur_disponible") n'a jamais mis
    // le plateau dans cet état.
    if (exerciseAnswered && !exerciseExploring) {
      exerciseExploring = true;
      const retryBtn = document.getElementById("exercise-retry-btn");
      if (retryBtn) retryBtn.style.display = exerciseLastSubmittedUci ? "inline-block" : "none";
    }
    if (err === "credit_insuffisant") {
      if (typeof _coachRenderCreditInsuffisant === "function") _coachRenderCreditInsuffisant();
      console.warn("[exercice]", "credit_insuffisant", data);
      return;
    }
    const msg = (err === "aucune_erreur_disponible")
      ? (exerciseSourceFiltre() === "lichess"
          ? "Aucun problème Lichess ne correspond à cette phase pour l'instant."
          : "Aucune position d'exercice disponible (lancer build_patterns_erreurs.py).")
      : (err === "lichess_indisponible")
      ? "Source « Problèmes Lichess » indisponible (lancer preparer_puzzles_lichess.py)."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      // pas_de_verdict_exercice (issue #79, point 4b) : le serveur a
      // refusé d'appeler le modèle faute de verdict Stockfish — message
      // cohérent avec celui du minuteur de garde ci-dessus
      // (_exerciseShowAnalysisIndisponible), qu'il arrive avant ou après.
      : (err === "pas_de_verdict_exercice")
      ? "L'analyse Stockfish est indisponible."
      : "Le coach n'a pas pu répondre, réessayez.";
    if (statusEl) statusEl.textContent = msg;
    console.warn("[exercice]", msg, data);
  });
}
