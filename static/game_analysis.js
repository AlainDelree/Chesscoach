/*
 * game_analysis.js — ChessCoach (issue #41)
 *
 * Bouton "Analyser cette partie" du panneau Bibliothèque/Revue PGN : lance
 * une analyse Stockfish synchrone (un aller-retour SocketIO, "analyser_pgn"
 * côté serveur, déjà émis par lancerAnalyse() dans board.js) sur la partie
 * actuellement chargée en revue (reviewFens/reviewMoves, board.js), affiche
 * un rapport des coups classés par gravité de perte d'évaluation (2-3 pires
 * mis en avant), et enrichit reviewMoves avec qualite/delta_cp/best_move
 * pour que les badges déjà existants de la revue (renderHistory/
 * renderReview/showReviewBestMove, board.js) s'affichent directement.
 *
 * Purement mécanique côté rapport (delta_cp/qualite/numéro de coup) — aucune
 * explication automatique du coach générée ici (issue #41 point 2) :
 * l'objectif du programme d'entraînement (issue #14) est qu'Alain réfléchisse
 * d'abord, le coach restant disponible à la demande une fois un coup flagué
 * rejoué (point 3).
 *
 * Cliquer sur un coup du rapport recharge la position juste avant ce coup
 * dans le mode "partie libre" (startFreeGameFromFen, free_play.js) pour
 * l'explorer librement — "Coup Stockfish" et "Demander l'avis du coach" y
 * restent disponibles, sans construire de nouveau mode dédié (point 3).
 *
 * Point d'entrée depuis la fin d'une partie pédagogique/libre (point 4) :
 * analyserPartieDepuisPgn(), appelée par le bouton de la bannière de fin de
 * partie (board.js showGameOverBanner, câblé dans pedagogic.js/free_play.js).
 */

let _gameAnalysisBusy = false;

function analyserPartieCourante() {
  if (_gameAnalysisBusy) return;
  if (!reviewMoves.length) {
    const status = document.getElementById("game-analysis-status");
    if (status) status.textContent = "Chargez d'abord une partie à analyser.";
    return;
  }
  _gameAnalysisBusy = true;
  const btn = document.getElementById("game-analysis-btn");
  if (btn) btn.disabled = true;
  const status = document.getElementById("game-analysis-status");
  if (status) status.textContent = "Analyse Stockfish en cours (peut prendre une minute)...";
  const report = document.getElementById("game-analysis-report");
  if (report) report.innerHTML = "";

  lancerAnalyse(reviewMoves.map(m => m.uci));
}

function _gameAnalysisQualiteLabel(qualite) {
  switch (qualite) {
    case "blunder":     return "Gaffe";
    case "erreur":      return "Erreur";
    case "imprecision": return "Imprécision";
    default:            return "Bon coup";
  }
}

// Coups classés par gravité de perte d'évaluation, 2-3 pires mis en avant
// (issue #41 point 2) — opère directement sur reviewMoves (déjà fusionné
// avec la réponse serveur par le listener ci-dessous), pour réutiliser san/
// uci/color sans les redemander au serveur.
function renderGameAnalysisReport() {
  const list = document.getElementById("game-analysis-report");
  if (!list) return;
  list.innerHTML = "";

  const flagged = reviewMoves
    .map((m, i) => ({ ...m, _idx: i }))
    .filter(m => m.qualite && m.qualite !== "bon")
    .sort((a, b) => (b.delta_cp || 0) - (a.delta_cp || 0));

  if (!flagged.length) {
    const li = document.createElement("li");
    li.style.color = "#778";
    li.textContent = "Aucune erreur ou gaffe détectée dans cette partie.";
    list.appendChild(li);
    return;
  }

  flagged.forEach((m, rank) => {
    const li = document.createElement("li");
    li.style.cursor = "pointer";
    li.style.padding = "3px 4px";
    li.style.borderRadius = "3px";
    li.style.marginBottom = "2px";
    if (rank < 3) {
      li.style.background = "#fdecea";
      li.style.fontWeight = "bold";
    }
    const coupNum = Math.ceil((m._idx + 1) / 2);
    const camp = m.color === "white" ? "Blancs" : "Noirs";
    const label = _gameAnalysisQualiteLabel(m.qualite);
    li.textContent = `${rank < 3 ? "🔥 " : ""}${coupNum}. (${camp}) ${m.san} — ${label} (-${m.delta_cp}cp)`;
    li.onclick = () => explorerCoupFlagge(m._idx);
    list.appendChild(li);
  });
}

// Point 3 : rejouer un coup flagué du rapport avec Stockfish — charge la
// position juste avant ce coup (reviewFens[idx], cf. board.js parsePgn) en
// mode "partie libre" explorable, plutôt que de construire un mode dédié.
function explorerCoupFlagge(idx) {
  const fen = reviewFens[idx];
  const m = reviewMoves[idx];
  if (!fen) return;
  switchModeTab("free");
  startFreeGameFromFen(fen);
  const status = document.getElementById("free-play-status");
  if (status && m) {
    status.textContent = `Position avant ${m.san} (coup flagué de l'analyse) — explorez librement.`;
  }
}

// Point 4 : point d'entrée depuis la fin d'une partie pédagogique/libre —
// bascule vers l'onglet Bibliothèque/Revue avec la partie qui vient de se
// dérouler déjà chargée (parsePgn, board.js), puis suit le même chemin que
// le bouton "Analyser cette partie" du point 1 (l'analyse elle-même reste un
// geste volontaire, pas automatique).
function analyserPartieDepuisPgn(pgnText) {
  if (!pgnText) return;
  switchModeTab("library");
  parsePgn(pgnText, (info) => {
    const label = document.getElementById("pgn-lib-loaded-label");
    if (label) label.textContent = `Chargée : ${info.white} vs ${info.black} — partie tout juste terminée.`;
  });
}

if (typeof socket !== "undefined") {
  socket.on("analyser_pgn_response", (data) => {
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const status = document.getElementById("game-analysis-status");
    if (!data || !data.moves) {
      if (status) status.textContent = "L'analyse a échoué.";
      return;
    }
    // Fusionne qualite/delta_cp/best_move dans reviewMoves (même ordre que
    // les coups envoyés) pour réutiliser directement les badges existants de
    // la revue (renderHistory/renderReview/showReviewBestMove, board.js).
    data.moves.forEach((m, i) => {
      if (!reviewMoves[i]) return;
      reviewMoves[i].qualite   = m.qualite;
      reviewMoves[i].delta_cp  = m.delta_cp;
      reviewMoves[i].best_move = m.best_move;
    });
    _isAnalysed = true;
    renderGameAnalysisReport();
    renderReview();
    if (status) status.textContent = `Analyse terminée (${data.moves.length} coups examinés).`;
  });

  socket.on("analyser_pgn_error", (data) => {
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const status = document.getElementById("game-analysis-status");
    const err = data && data.error;
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : "L'analyse a échoué.";
    if (status) status.textContent = msg;
    console.warn("[analyse de partie]", msg, data);
  });
}
