/*
 * game_coach_lines.js — ChessCoach (issue #68)
 *
 * Tableau "Lignes du coach" pour les modes de partie (libre, pédagogique,
 * ouverture, finales) et la revue de bibliothèque — pendant du tableau déjà
 * existant du mode exercice (exercise.js, issue #58), mais réutilisant
 * directement les fonctions mode-agnostiques de coach_lines.js plutôt que de
 * les redupliquer.
 *
 * Différence principale avec le mode exercice : ces modes ont une partie
 * avec un historique réel, donc une ligne alternative du coach peut partir
 * d'une position déjà jouée plus tôt (pas forcément la position actuelle) —
 * voir extractCoachGameLines/_GAME_LINES_ADDENDUM (llm_coach.py) pour le
 * format fixe demandé au coach, et _gameLinesFenForAnchor ci-dessous pour la
 * résolution de cette mention en position réelle par rejeu (jamais par
 * arithmétique de numéro de coup : une position de départ personnalisée
 * (SetUp/FEN, ex. une finale) peut démarrer à un demi-coup impair).
 *
 * La lecture ne touche jamais l'état réel de la partie/de la revue (aucun
 * appel à game.move(), aucun socket.emit) : elle ne fait que RE-DESSINER le
 * plateau (renderBoard) à partir de positions déjà résolues à l'avance —
 * Stop/"Revenir à la partie" n'ont donc jamais besoin de restaurer quoi que
 * ce soit d'autre que l'affichage (position, historique, bandeau de fin
 * compris, puisqu'aucun de ces états n'a été modifié entre-temps).
 */

let gameCoachLines             = [];
let gameCoachLinesPlayingIdx   = null;
let gameCoachLinesController   = null; // contrôleur {stop()} de coach_lines.js, ou null
// Vrai pendant qu'une ligne du coach est affichée sur le plateau (avant/
// pendant/après lecture) plutôt que la position réelle du mode actif ou de
// la revue — bloque les clics du plateau (onFreePlayBoardClick and co.) et
// la navigation de revue (reviewPrev/reviewNext/reviewGoTo) tant qu'on n'est
// pas revenu explicitement à la partie.
let gameCoachLinesPreviewActive = false;

const _GAME_LINES_MODES = ["free", "pedagogic", "opening", "finale"];

function gameLineStopPlayback() {
  if (gameCoachLinesController) gameCoachLinesController.stop();
  gameCoachLinesController = null;
  gameCoachLinesPlayingIdx = null;
}

// Nouvelle partie démarrée, ou autre partie chargée en revue (issue #68,
// appelé depuis coachNewSegment — board.js — mêmes points de coupure que
// l'isolation du chat par partie, issue #64) : le tableau ne doit rien
// conserver de la partie précédente, et toute lecture en cours doit
// s'arrêter proprement sans laisser les clics du plateau bloqués.
function gameCoachLinesReset() {
  gameLineStopPlayback();
  gameCoachLines = [];
  gameCoachLinesPreviewActive = false;
  const restoreBtn = document.getElementById("game-coach-lines-restore-btn");
  if (restoreBtn) restoreBtn.style.display = "none";
  renderGameCoachLinesTable();
}

// ── Contexte de la partie/revue actuellement affichée ───────────────────────

// Rejoue sanMoves[0..ply-1] depuis initialFen (position de départ standard si
// omise) et retourne le FEN atteint — jamais d'arithmétique de numéro de
// coup, pour rester correct même si la partie démarre à un demi-coup impair
// (SetUp/FEN personnalisé, ex. une finale).
function _gameLinesReplayFen(initialFen, sanMoves, ply) {
  let game;
  try { game = initialFen ? new Chess(initialFen) : new Chess(); }
  catch (e) { game = new Chess(); }
  for (let i = 0; i < ply && i < sanMoves.length; i++) {
    if (!game.move(sanMoves[i], { sloppy: true })) return null;
  }
  return game.fen();
}

// Repère, par rejeu (jamais par arithmétique), le FEN juste avant le coup
// numéro/camp visé par une mention "depuis le coup N... (Camp)" — compare à
// chaque demi-coup le numéro/camp affiché par chess.js lui-même (fullmove
// number + turn du FEN courant), qui reste correct même pour une partie
// démarrant à un demi-coup impair. Retourne null si aucun demi-coup de la
// partie ne correspond (numéro hors de la partie, ou camp qui ne joue
// jamais ce numéro-là dans cette partie précise).
function _gameLinesFenForAnchor(initialFen, sanMoves, anchor) {
  let game;
  try { game = initialFen ? new Chess(initialFen) : new Chess(); }
  catch (e) { game = new Chess(); }
  for (let i = 0; i < sanMoves.length; i++) {
    const turnBlancs = game.turn() === "w";
    const fullmove = parseInt(game.fen().split(" ")[5], 10);
    if (fullmove === anchor.moveNumber &&
        ((turnBlancs && anchor.color === "blancs") || (!turnBlancs && anchor.color === "noirs"))) {
      return game.fen();
    }
    if (!game.move(sanMoves[i], { sloppy: true })) return null;
  }
  return null;
}

// Contexte de la partie/revue actuellement affichée : { initialFen,
// sanMoves, plyCurrent, currentFen }, ou null si aucune partie/revue
// applicable (mode exercice/éditeur, ou revue vide). initialFen est null
// quand la partie démarre de la position standard (repli de
// _gameLinesReplayFen/_gameLinesFenForAnchor).
function _gameLinesContext() {
  if (typeof activeMode !== "undefined" && activeMode) {
    if (_GAME_LINES_MODES.indexOf(activeMode) === -1) return null; // exercice/éditeur : non applicable
    if (typeof _activeModeGameInstance !== "function") return null;
    const game = _activeModeGameInstance();
    if (!game) return null;
    const header = (typeof game.header === "function") ? game.header() : {};
    const sanMoves = game.history();
    return {
      initialFen: (header && header.FEN) || null,
      sanMoves,
      plyCurrent: sanMoves.length,
      currentFen: game.fen(),
    };
  }
  // Revue de bibliothèque (activeMode null) : reviewMoves/reviewIdx (board.js).
  if (typeof reviewMoves === "undefined" || !reviewMoves || !reviewMoves.length) return null;
  const sanMoves = reviewMoves.map((m) => m.san);
  const plyCurrent = (typeof reviewIdx === "number") ? reviewIdx : sanMoves.length;
  return {
    initialFen: null,
    sanMoves,
    plyCurrent,
    currentFen: _gameLinesReplayFen(null, sanMoves, plyCurrent),
  };
}

// Candidats de départ pour une ligne donnée, dans l'ordre où ils doivent
// être essayés (issue #68 point 2) : la position juste avant le coup visé
// par la mention "depuis le coup N... (Camp)" si présente et résoluble,
// PUIS la position actuellement affichée — jamais d'autre repli.
function _gameLinesCandidates(ctx, anchor) {
  const candidates = [];
  if (anchor) {
    const fen = _gameLinesFenForAnchor(ctx.initialFen, ctx.sanMoves, anchor);
    if (fen) {
      const campLabel = anchor.color === "noirs" ? "Noirs" : "Blancs";
      const suffixe = anchor.color === "noirs" ? "..." : "";
      candidates.push({ fen, label: `depuis le coup ${anchor.moveNumber}${suffixe} (${campLabel})` });
    }
  }
  if (ctx.currentFen) candidates.push({ fen: ctx.currentFen, label: "depuis la position actuelle" });
  return candidates;
}

// ── Alimentation du tableau ──────────────────────────────────────────────

// Hook générique (cf. board.js, socket.on("coach_response")/
// ("coach_on_demand_response"), et les "*_comment" de pedagogic.js/
// opening.js/finales.js) : toute réponse du coach affichée pendant un mode
// de partie actif (libre/pédagogique/ouverture/finales) ou en revue de
// bibliothèque alimente ce tableau — no-op en mode exercice/éditeur, ou si
// aucune partie/revue n'est chargée.
function gameCoachLinesOnCoachText(text) {
  const ctx = _gameLinesContext();
  if (!ctx || !ctx.currentFen) return;
  const rawLines = extractCoachGameLines(text);
  if (!rawLines.length) return;
  let added = false;
  rawLines.forEach(({ moves, anchor }) => {
    const key = moves.join(" ");
    if (gameCoachLines.some((l) => l.key === key)) return;
    const candidates = _gameLinesCandidates(ctx, anchor);
    const resolved = resolveCoachLineStart(candidates, moves);
    gameCoachLines.push({ key, displayText: key, resolved, special: null });
    added = true;
  });
  if (added) renderGameCoachLinesTable();
}

function _stockfishLineLabel(info) {
  if (!info || !info.coup_plein || !info.camp) return "depuis la position analysée";
  const campLabel = info.camp === "noirs" ? "Noirs" : "Blancs";
  const suffixe = info.camp === "noirs" ? "..." : "";
  return `depuis le coup ${info.coup_plein}${suffixe} (${campLabel})`;
}

// Bonus (issue #68 point 5) : ligne principale déjà calculée par la
// vérification Stockfish du bloc de faits pour cette partie (cf. app.py
// on_coach_ask, data.stockfish_line), transmise avec sa position de départ
// réelle (fen_avant) — jamais recalculée ici. Absente/vide : pas de ligne
// ajoutée (comportement par défaut, aucun appel supplémentaire).
function gameCoachLinesOnStockfishLine(info) {
  if (!info || !info.fen_avant || !info.ligne_principale) return;
  const moveTokens = info.ligne_principale.split(/\s+/).filter(Boolean);
  if (moveTokens.length < 2) return;
  const key = moveTokens.join(" ");
  if (gameCoachLines.some((l) => l.key === key)) return;
  const resolved = resolveCoachLineStart([{ fen: info.fen_avant, label: _stockfishLineLabel(info) }], moveTokens);
  gameCoachLines.unshift({ key, displayText: "Ligne de Stockfish : " + key, resolved, special: "stockfish" });
  renderGameCoachLinesTable();
}

// ── Rendu du tableau ─────────────────────────────────────────────────────

function renderGameCoachLinesTable() {
  const wrap = document.getElementById("game-coach-lines");
  const body = document.getElementById("game-coach-lines-body");
  if (!wrap || !body) return;
  // Non applicable en mode exercice (son propre tableau, exercise.js) ni en
  // mode éditeur (pas de partie) — masqué immédiatement au changement de
  // mode (cf. setActiveMode, controls.js), même si des lignes restaient
  // affichées d'un mode précédent qui n'aurait pas encore été réinitialisé.
  const modeOk = !(typeof activeMode !== "undefined" && activeMode &&
    (activeMode === "exercise" || activeMode === "editor"));
  if (!modeOk || !gameCoachLines.length) {
    wrap.style.display = "none";
    body.innerHTML = "";
    return;
  }
  wrap.style.display = "block";
  body.innerHTML = "";
  gameCoachLines.forEach((line, idx) => {
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
      const playing = gameCoachLinesPlayingIdx === idx;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.id = `game-line-btn-${idx}`;
      btn.className = "coach-line-play-btn" + (playing ? " playing" : "");
      btn.textContent = playing ? "Stop" : "▶ Play";
      btn.onclick = () => gameLineToggle(idx);
      tdBtn.appendChild(btn);
    }
    tr.appendChild(tdBtn);

    body.appendChild(tr);
  });
}

// Redessine le plateau réel du mode actif (ou de la revue) — aucune des
// fonctions ci-dessous ne modifie l'état réel de la partie/de la revue,
// seul l'affichage revient en phase avec lui (Stop, ligne suivante, ou
// retour explicite).
function _gameLinesRerenderCurrentMode() {
  const mode = (typeof activeMode !== "undefined") ? activeMode : null;
  if (mode === "free"      && typeof renderFreePlayBoard  === "function") { renderFreePlayBoard();  return; }
  if (mode === "pedagogic" && typeof renderPedagogicBoard === "function") { renderPedagogicBoard(); return; }
  if (mode === "opening"   && typeof renderOpeningBoard   === "function") { renderOpeningBoard();   return; }
  if (mode === "finale"    && typeof renderFinaleBoard    === "function") { renderFinaleBoard();    return; }
  if (typeof renderReview === "function") renderReview();
}

function gameLineToggle(idx) {
  const line = gameCoachLines[idx];
  if (!line || !line.resolved) return;

  if (gameCoachLinesPlayingIdx === idx) {
    gameLineStopPlayback();
    renderGameCoachLinesTable();
    return;
  }
  gameLineStopPlayback();

  if (!gameCoachLinesPreviewActive) {
    // Première lecture depuis la position réelle (issue #68) : les clics du
    // plateau (et, en revue, la navigation Précédent/Suivant) restent
    // bloqués jusqu'au retour explicite, quel que soit le nombre de lignes
    // rejouées ensuite avant ce retour.
    gameCoachLinesPreviewActive = true;
    const restoreBtn = document.getElementById("game-coach-lines-restore-btn");
    if (restoreBtn) restoreBtn.style.display = "inline-block";
  }

  gameCoachLinesPlayingIdx = idx;
  renderGameCoachLinesTable();

  renderBoard(line.resolved.startFen.split(" ")[0], null, null, null, null, null, null);

  const speedSel = document.getElementById("game-coach-lines-speed");
  const speedMs = speedSel ? parseInt(speedSel.value, 10) : 1000;

  gameCoachLinesController = playCoachLineSequence(line.resolved.steps, {
    speedMs,
    renderStep: (fen, from, to) => {
      renderBoard(fen.split(" ")[0], freeAlgebraicToSquareId(from), freeAlgebraicToSquareId(to), null, null, null, null);
    },
    onDone: () => {
      gameCoachLinesPlayingIdx = null;
      gameCoachLinesController = null;
      renderGameCoachLinesTable();
    },
  });
}

function gameLinesRestore() {
  gameLineStopPlayback();
  gameCoachLinesPreviewActive = false;
  const restoreBtn = document.getElementById("game-coach-lines-restore-btn");
  if (restoreBtn) restoreBtn.style.display = "none";
  renderGameCoachLinesTable();
  _gameLinesRerenderCurrentMode();
}
