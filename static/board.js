/*
 * board.js — ChessCoach (extrait/adapté de nicsoft/web/static/app.js, AlChess)
 *
 * Rendu d'un échiquier virtuel en mode "analyse de partie" : construction du
 * plateau, affichage d'une position FEN, navigation dans les coups d'une
 * partie PGN chargée, badges de qualité de coup, barre d'évaluation
 * Stockfish, flèches d'annotation SVG, panneau de chat avec le coach.
 *
 * AUCUNE dépendance au hardware Chessnut / driver USB NicLink : ce module ne
 * fait que dessiner un plateau et réagir au clavier/souris/SocketIO.
 *
 * Retiré par rapport à l'original :
 *   - le support i18n (attributs data-i18n, fonction t()) — tous les
 *     libellés ci-dessous sont en français en dur. Réintroduire un i18n
 *     complet si ChessCoach doit être multilingue un jour.
 *   - la synchronisation "plateau physique vs plateau virtuel" (Chessnut) :
 *     _boardOk, laboSyncPhysique, laboRenderBoardWithErrors, etc.
 *   - la sauvegarde vers la bibliothèque de parties AlChess/NicLink
 *     (sauvegarderNicLink, événement save_pgn_externe).
 *   - le flip échiquier avec inversion des noms de joueurs haut/bas (logique
 *     de partie live pédagogique) — flipBoard() ici ne fait que retourner
 *     l'affichage.
 *
 * Dépendances externes attendues dans la page hôte :
 *   - un objet `socket` (client Socket.IO) déjà connecté ;
 *   - la librairie chess.js exposée en global `Chess` (utilisée par parsePgn) ;
 *   - un conteneur `#board` (grille 8x8) + `#coord-rank` / `#coord-file` ;
 *   - un conteneur `#historique` pour la liste des coups ;
 *   - des images de pièces sous `/static/pieces/{w,b}{K,Q,R,B,N,P}.svg`
 *     (adapter BASE_PIECES ci-dessous si l'arborescence diffère).
 *   - pour la barre d'éval : #eval-black / #eval-white / #eval-score ;
 *   - pour les flèches : un <svg id="arrows-svg"> superposé au plateau.
 */

const BASE_PIECES = "/static/pieces/";

const PIECES = {
  'K': `<img src="${BASE_PIECES}wK.svg">`,
  'Q': `<img src="${BASE_PIECES}wQ.svg">`,
  'R': `<img src="${BASE_PIECES}wR.svg">`,
  'B': `<img src="${BASE_PIECES}wB.svg">`,
  'N': `<img src="${BASE_PIECES}wN.svg">`,
  'P': `<img src="${BASE_PIECES}wP.svg">`,
  'k': `<img src="${BASE_PIECES}bK.svg">`,
  'q': `<img src="${BASE_PIECES}bQ.svg">`,
  'r': `<img src="${BASE_PIECES}bR.svg">`,
  'b': `<img src="${BASE_PIECES}bB.svg">`,
  'n': `<img src="${BASE_PIECES}bN.svg">`,
  'p': `<img src="${BASE_PIECES}bP.svg">`,
};

let _boardFlipped = false;

// Discriminant de la réponse finale_add_response (issue #13, mutualisée par
// free_play.js et editor.js issue #16) : plusieurs panneaux peuvent émettre
// finale_add, mais un seul doit réagir à la réponse (mettre à jour son
// propre statut/formulaire) — celui qui a fait la dernière demande.
let pendingFinaleAddSource = null; // "free" | "editor" | null

// ── Échiquier — construction et rendu ───────────────────────────────────────

function buildBoard() {
  const board = document.getElementById("board");
  board.innerHTML = "";

  const rankCoord = document.getElementById("coord-rank");
  if (rankCoord) {
    rankCoord.innerHTML = "";
    const ranks = _boardFlipped ? [0,1,2,3,4,5,6,7] : [7,6,5,4,3,2,1,0];
    ranks.forEach(r => {
      const s = document.createElement("span");
      s.textContent = r + 1;
      rankCoord.appendChild(s);
    });
  }
  const fileCoord = document.getElementById("coord-file");
  if (fileCoord) {
    fileCoord.innerHTML = "";
    const files = _boardFlipped ? "hgfedcba".split("") : "abcdefgh".split("");
    files.forEach(f => {
      const s = document.createElement("span");
      s.textContent = f;
      fileCoord.appendChild(s);
    });
  }

  const rankOrder = _boardFlipped ? [0,1,2,3,4,5,6,7] : [7,6,5,4,3,2,1,0];
  const fileOrder = _boardFlipped ? [7,6,5,4,3,2,1,0] : [0,1,2,3,4,5,6,7];
  for (const rank of rankOrder) {
    for (const file of fileOrder) {
      const sq = document.createElement("div");
      const isLight = (rank + file) % 2 === 1;
      sq.className = `square ${isLight ? 'light' : 'dark'}`;
      sq.id = `sq-${file}-${rank}`;
      board.appendChild(sq);
    }
  }
}

function fenToBoard(fen) {
  const rows = fen.split("/");
  const grid = {};
  for (let rank = 7; rank >= 0; rank--) {
    let file = 0;
    const row = rows[7 - rank];
    for (const ch of row) {
      if (ch >= '1' && ch <= '8') {
        file += parseInt(ch);
      } else {
        grid[`${file}-${rank}`] = ch;
        file++;
      }
    }
  }
  return grid;
}

function renderBoard(fen, from, to, bestFrom, bestTo, feedbackSq, feedbackClass) {
  updateMaterial(fen);
  const grid = fenToBoard(fen);
  for (let rank = 7; rank >= 0; rank--) {
    for (let file = 0; file < 8; file++) {
      const id = `${file}-${rank}`;
      const sq = document.getElementById(`sq-${id}`);
      if (!sq) continue;
      const piece = grid[id];
      sq.innerHTML = piece ? (PIECES[piece] || piece) : "";
      const isLight = (rank + file) % 2 === 1;
      sq.className = `square ${isLight ? 'light' : 'dark'}`;
      if (from     && id === from)     sq.classList.add("last-move-from");
      if (to       && id === to)       sq.classList.add("last-move-to");
      if (bestFrom && id === bestFrom) sq.classList.add("highlight-best-from");
      if (bestTo   && id === bestTo)   sq.classList.add("highlight-best-to");
      if (feedbackSq && id === feedbackSq && feedbackClass)
        sq.classList.add(`feedback-${feedbackClass}`);
    }
  }
}

function uciToCoords(uci) {
  if (!uci || uci.length < 4) return [null, null];
  const files = "abcdefgh";
  const fromFile = files.indexOf(uci[0]);
  const fromRank = parseInt(uci[1]) - 1;
  const toFile   = files.indexOf(uci[2]);
  const toRank   = parseInt(uci[3]) - 1;
  return [`${fromFile}-${fromRank}`, `${toFile}-${toRank}`];
}

function flipBoard() {
  _boardFlipped = !_boardFlipped;
  buildBoard();
  const fen = reviewFens[reviewIdx] || "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
  renderBoard(fen, null, null, null, null, null, null);
}

// ── Matériel capturé ─────────────────────────────────────────────────────────

function updateMaterial(fen) {
  const vals  = { P:1,N:3,B:3,R:5,Q:9, p:1,n:3,b:3,r:5,q:9 };
  const initW = { P:8,N:2,B:2,R:2,Q:1 };
  const initB = { p:8,n:2,b:2,r:2,q:1 };
  const symW  = { P:'wP',N:'wN',B:'wB',R:'wR',Q:'wQ' };
  const symB  = { p:'bP',n:'bN',b:'bB',r:'bR',q:'bQ' };

  const present = {};
  for (const ch of fen.split(' ')[0])
    if (ch in vals) present[ch] = (present[ch] || 0) + 1;

  let scoreW = 0, scoreB = 0;
  for (const [p, n] of Object.entries(present))
    p === p.toUpperCase() ? scoreW += vals[p] * n : scoreB += vals[p] * n;
  const diff = scoreW - scoreB;

  let topHtml = '', botHtml = '';
  for (const [p, init] of Object.entries(initW)) {
    const cap = init - (present[p] || 0);
    const img = `<img src="${BASE_PIECES}${symW[p]}.svg" style="width:18px;height:18px;">`;
    for (let i = 0; i < cap; i++) topHtml += img;
  }
  if (diff < 0) topHtml += `<span class="mat-score">+${Math.abs(diff)}</span>`;

  for (const [p, init] of Object.entries(initB)) {
    const cap = init - (present[p] || 0);
    const img = `<img src="${BASE_PIECES}${symB[p]}.svg" style="width:18px;height:18px;">`;
    for (let i = 0; i < cap; i++) botHtml += img;
  }
  if (diff > 0) botHtml += `<span class="mat-score">+${diff}</span>`;

  const topEl = document.getElementById('material-top');
  const botEl = document.getElementById('material-bottom');
  if (!topEl || !botEl) return;
  if (_boardFlipped) {
    topEl.innerHTML = botHtml || '&nbsp;';
    botEl.innerHTML = topHtml || '&nbsp;';
  } else {
    topEl.innerHTML = topHtml || '&nbsp;';
    botEl.innerHTML = botHtml || '&nbsp;';
  }
}

// ── Badges de qualité de coup ────────────────────────────────────────────────

const QUALITE_GLYPH = {
  "bon":         { sym: "✓",  bg: "#5d8f3f", fg: "#fff" },
  "imprecision": { sym: "?!", bg: "#e6a117", fg: "#fff" },
  "erreur":      { sym: "?",  bg: "#d44b1a", fg: "#fff" },
  "blunder":     { sym: "??", bg: "#8b0086", fg: "#fff" },
};

function qualiteColor(qualite) {
  switch(qualite) {
    case "imprecision": return "#cc7700";
    case "erreur":      return "#cc2200";
    case "blunder":     return "#7b00b0";
    default:            return "#1a2a3a";
  }
}
function qualiteSymbole(qualite) {
  switch(qualite) {
    case "imprecision": return "?!";
    case "erreur":      return "?";
    case "blunder":     return "??";
    default:            return "";
  }
}
function qualiteAnnotation(qualite, delta_cp) {
  const sym = { "bon": "✓", "imprecision": "?!", "erreur": "?", "blunder": "??" };
  const s = sym[qualite] || "✓";
  const cp = delta_cp !== undefined ? ` ${delta_cp}cp` : "";
  return `{ ${s}${cp} }`;
}

function showQualiteGlyph(squareId, qualite) {
  const sq = document.getElementById("sq-" + squareId);
  if (!sq) return;
  removeQualiteGlyph();
  const g = QUALITE_GLYPH[qualite];
  if (!g) return;
  const badge = document.createElement("div");
  badge.id = "qualite-glyph";
  badge.style.position     = "absolute";
  badge.style.top          = "2px";
  badge.style.right        = "2px";
  badge.style.width        = "38%";
  badge.style.height       = "38%";
  badge.style.borderRadius = "50%";
  badge.style.background   = g.bg;
  badge.style.color        = g.fg;
  badge.style.display      = "flex";
  badge.style.alignItems   = "center";
  badge.style.justifyContent = "center";
  badge.style.fontSize     = "clamp(7px, 1.8cqw, 13px)";
  badge.style.fontWeight   = "bold";
  badge.style.lineHeight   = "1";
  badge.style.pointerEvents = "none";
  badge.style.zIndex       = "10";
  badge.style.boxShadow    = "0 1px 4px rgba(0,0,0,0.6)";
  badge.style.letterSpacing = "-0.5px";
  badge.textContent = g.sym;
  sq.appendChild(badge);
}

function removeQualiteGlyph() {
  const old = document.getElementById("qualite-glyph");
  if (old) old.remove();
}

// ── Flèches d'annotation SVG ─────────────────────────────────────────────────

function clearArrows() {
  const svg = document.getElementById("arrows-svg");
  if (!svg) return;
  const defs = svg.querySelector("defs");
  svg.innerHTML = "";
  if (defs) svg.appendChild(defs);
}

function squareCenter(square, size) {
  const file = square.charCodeAt(0) - 97; // 'a' → 0
  const rank = parseInt(square[1], 10) - 1; // '1' → 0
  const col = _boardFlipped ? (7 - file) : file;
  const row = _boardFlipped ? rank : (7 - rank);
  return { x: (col + 0.5) * size, y: (row + 0.5) * size };
}

function drawArrows(arrows) {
  clearArrows();
  const svg = document.getElementById("arrows-svg");
  const board = document.getElementById("board");
  if (!svg || !board || !arrows || !arrows.length) return;
  const size = board.getBoundingClientRect().width / 8;
  if (!size) return;
  const strokeWidth = size * 0.08;
  for (const pair of arrows) {
    if (!pair || pair.length < 2) continue;
    const [from, to] = pair;
    if (!from || !to || from === to) continue;
    const p1 = squareCenter(from, size);
    const p2 = squareCenter(to, size);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", p1.x);
    line.setAttribute("y1", p1.y);
    line.setAttribute("x2", p2.x);
    line.setAttribute("y2", p2.y);
    line.setAttribute("stroke", "rgba(232,69,96,0.75)");
    line.setAttribute("stroke-width", strokeWidth);
    line.setAttribute("stroke-linecap", "round");
    line.setAttribute("marker-end", "url(#arrowhead)");
    svg.appendChild(line);
  }
}

// ── Barre d'évaluation Stockfish ─────────────────────────────────────────────

function updateEvalBar(cp, mate) {
  const barBlack = document.getElementById("eval-black");
  const barWhite = document.getElementById("eval-white");
  const scoreEl  = document.getElementById("eval-score");
  if (!barBlack || !barWhite) return;

  let pctWhite = 50; // % pour les blancs
  let scoreText = "0.0";

  if (mate !== null && mate !== undefined) {
    pctWhite = mate > 0 ? 100 : 0;
    scoreText = mate > 0 ? `M${mate}` : `M${Math.abs(mate)}`;
  } else if (cp !== null && cp !== undefined) {
    // Convertir cp en pourcentage (sigmoid)
    const clamped = Math.max(-1000, Math.min(1000, cp));
    pctWhite = 50 + 50 * (2 / (1 + Math.exp(-0.004 * clamped)) - 1);
    const abs = Math.abs(cp / 100).toFixed(2);
    scoreText = cp >= 0 ? `+${abs}` : `-${abs}`;
  }

  const pctBlack = 100 - pctWhite;
  barBlack.style.height = `${pctBlack}%`;
  barWhite.style.height = `${pctWhite}%`;
  if (scoreEl) {
    scoreEl.textContent = scoreText;
    scoreEl.style.color = cp >= 0 ? "#e0e0e0" : "#aaa";
  }
}

// ── Revue de partie (navigation dans les coups) ──────────────────────────────

let reviewFens     = [];
let reviewMoves    = [];
let reviewIdx      = 0;
let _isAnalysed    = false; // true une fois l'analyse Stockfish terminée

function reviewPrev() {
  if (reviewIdx > 0) { reviewIdx--; renderReview(); }
}
function reviewNext() {
  if (reviewIdx < reviewFens.length - 1) { reviewIdx++; renderReview(); }
}
function reviewGoTo(index) {
  if (index >= 0 && index < reviewFens.length) {
    reviewIdx = index;
    renderReview();
  }
}

function renderHistory(activeIdx) {
  const histEl = document.getElementById("historique");
  if (!histEl) return;

  // En mode interactif (issue #15 point 4), afficher les coups de la partie
  // en cours (activeMode, cf. controls.js) plutôt que ceux de la revue PGN —
  // navigation par clic désactivée dans ce cas, reviewGoTo() n'ayant de sens
  // que pour reviewFens/reviewMoves.
  let moves = reviewMoves;
  let liveMode = false;
  if (typeof activeMode !== "undefined" && activeMode && typeof getActiveModeMoves === "function") {
    const liveMoves = getActiveModeMoves();
    if (liveMoves) { moves = liveMoves; activeIdx = moves.length; liveMode = true; }
  }

  const whites = moves.map((m, i) => ({...m, _idx: i + 1})).filter(m => m.color === "white");
  const blacks = moves.map((m, i) => ({...m, _idx: i + 1})).filter(m => m.color === "black");
  const total  = Math.max(whites.length, blacks.length);
  let html = '<table style="width:100%;border-collapse:collapse;">';
  html += `<tr><th style="color:#1a2a3a;font-weight:600;padding:2px 4px;">Blancs</th><th style="color:#1a2a3a;font-weight:600;padding:2px 4px;">Noirs</th></tr>`;
  for (let i = 0; i < total; i++) {
      const mw   = whites[i];
      const mb   = blacks[i];
      const idxW = mw ? mw._idx : -1;
      const idxB = mb ? mb._idx : -1;
      const activeW = activeIdx === idxW ? "font-weight:bold;" : "";
      const activeB = activeIdx === idxB ? "font-weight:bold;" : "";
      const colorW  = activeIdx === idxW ? "#e94560" : qualiteColor(mw ? mw.qualite : "bon");
      const colorB  = activeIdx === idxB ? "#e94560" : qualiteColor(mb ? mb.qualite : "bon");
      const attrsW  = liveMode
        ? `style="padding:2px 4px;color:${colorW};${activeW}"`
        : `style="padding:2px 4px;cursor:pointer;color:${colorW};${activeW}" onclick="reviewGoTo(${idxW})"`;
      const attrsB  = liveMode
        ? `style="padding:2px 4px;color:${colorB};${activeB}"`
        : `style="padding:2px 4px;cursor:pointer;color:${colorB};${activeB}" onclick="reviewGoTo(${idxB})"`;
      html += `<tr>`;
      html += mw ? `<td ${attrsW}>${i+1}. ${mw.san}${qualiteSymbole(mw.qualite)}</td>` : `<td></td>`;
      html += mb ? `<td ${attrsB}>${mb.san}${qualiteSymbole(mb.qualite)}</td>` : `<td></td>`;
      html += `</tr>`;
  }
  html += '</table>';
  histEl.innerHTML = html;
}

function renderReview() {
  const fen = reviewFens[reviewIdx];
  let from = null, to = null, toSquare = null;
  if (reviewIdx > 0) {
    const m = reviewMoves[reviewIdx - 1];
    if (m && m.uci) {
      [from, to] = uciToCoords(m.uci);
      toSquare = to;
    }
  }
  renderBoard(fen, from, to, null, null, null, null);

  removeQualiteGlyph();
  if (_isAnalysed && reviewIdx > 0 && toSquare) {
    const m = reviewMoves[reviewIdx - 1];
    if (m && m.qualite && m.qualite !== "bon") {
      showQualiteGlyph(toSquare, m.qualite);
    }
  }

  const moveInfo = document.getElementById("review-move-info");
  const moveSan  = document.getElementById("review-move-san");
  if (reviewIdx === 0) {
    if (moveInfo) moveInfo.textContent = "Position initiale";
    if (moveSan)  moveSan.textContent  = "";
  } else {
    const m = reviewMoves[reviewIdx - 1];
    if (moveInfo) moveInfo.textContent = `Coup ${reviewIdx}`;
    if (moveSan)  moveSan.textContent  = m ? m.san : "";
  }
  renderHistory(reviewIdx);
}

function showReviewBestMove() {
  if (reviewIdx === 0 || !_isAnalysed) return;
  const m = reviewMoves[reviewIdx - 1];
  if (!m || !m.best_move) return;
  const [lFrom, lTo] = uciToCoords(m.uci || "");
  const [bFrom, bTo] = uciToCoords(m.best_move);
  renderBoard(reviewFens[reviewIdx], lFrom, lTo, bFrom, bTo, null, null);
  const sanEl = document.getElementById("review-best-move-san");
  if (sanEl) {
    sanEl.textContent = m.best_move;
    sanEl.style.display = "block";
  }
}

// ── Export PGN annoté ─────────────────────────────────────────────────────

function telechargerPgn(white, black, result) {
  let pgn = `[White "${white}"]\n[Black "${black}"]\n[Result "${result}"]\n\n`;
  for (let i = 0; i < reviewMoves.length; i++) {
    const m = reviewMoves[i];
    if (m.color === "white") pgn += `${Math.floor(i/2)+1}. `;
    pgn += m.san;
    if (m.qualite) pgn += ` ${qualiteAnnotation(m.qualite, m.delta_cp)}`;
    pgn += " ";
  }
  pgn += result;
  const blob = new Blob([pgn], { type: "text/plain" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `${white}_vs_${black}_analyse.pgn`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Import PGN (fichier, collé, ou chargé depuis la bibliothèque) ───────────
// Nécessite la librairie chess.js (global `Chess`).

function loadPgnFile(event, onLoaded) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => parsePgn(e.target.result, onLoaded);
  reader.readAsText(file);
}

function parsePgn(pgn, onLoaded) {
  // Charger une partie en revue (fichier local ou bibliothèque PGN) reprend
  // le plateau pour l'usage de la revue — si un mode interactif tournait
  // encore (partie pédagogique, exercice...), le terminer proprement d'abord
  // (issue #23, ensureModeSwitchClean dans controls.js) plutôt que de laisser
  // deux modes "actifs" en même temps sur le même plateau.
  if (typeof ensureModeSwitchClean === "function") ensureModeSwitchClean("library");
  try {
    const chess = new Chess();
    if (!chess.load_pgn(pgn)) {
      alert("PGN non reconnu.");
      return;
    }
    const white  = chess.header().White || "Blancs";
    const black  = chess.header().Black || "Noirs";
    const result = chess.header().Result || "*";
    const history = chess.history({ verbose: true });
    const chess2  = new Chess();
    const fens    = [chess2.fen().split(" ")[0]];
    const moves   = [];

    // Lire d'éventuelles annotations de qualité déjà présentes dans les
    // commentaires PGN (convention héritée d'AlChess : { ✓ / ?! / ? / ?? }).
    const commentRegex = /\{([^}]*)\}/g;
    const allComments = [];
    let cm;
    while ((cm = commentRegex.exec(pgn)) !== null) {
      allComments.push(cm[1].trim());
    }

    for (let i = 0; i < history.length; i++) {
      const m = history[i];
      const comment = allComments[i] || "";
      let qualite = "bon";
      if (comment.includes("!!") || comment.toLowerCase().includes("blunder")) qualite = "blunder";
      else if (comment.includes("!") || comment.toLowerCase().includes("erreur")) qualite = "erreur";
      else if (comment.includes("?") || comment.toLowerCase().includes("imprecision")) qualite = "imprecision";
      moves.push({ san: m.san, uci: m.from + m.to + (m.promotion || ""), color: m.color === "w" ? "white" : "black", qualite });
      chess2.move(m);
      fens.push(chess2.fen().split(" ")[0]);
    }

    reviewFens  = fens;
    reviewMoves = moves;
    reviewIdx   = fens.length - 1;
    _isAnalysed = moves.some(m => m.qualite && m.qualite !== "bon");

    buildBoard();
    renderReview();

    if (typeof onLoaded === "function") {
      onLoaded({ white, black, result, moves, dejaAnalyse: allComments.length === history.length });
    }
  } catch (e) {
    alert("Erreur lors du parsing PGN : " + e.message);
  }
}

// ── Analyse Stockfish (déclenche une passe côté serveur) ────────────────────

function lancerAnalyse(movesUci, seqMoves) {
  socket.emit("analyser_pgn", { moves: movesUci, seq_moves: seqMoves || 3 });
}

// ── Chat avec le coach (conversation multi-tours, cf. llm_coach.py) ─────────

let _coachHistory = [];
let _coachBusy    = false;

function coachBuildContext() {
  // Chat libre pendant un mode interactif en cours (issue #15 point 3) : le
  // coach doit connaître la position réelle du mode actif (activeMode, cf.
  // controls.js), pas la position de la revue PGN qui n'a pas bougé.
  if (typeof activeMode !== "undefined" && activeMode && typeof activeModeGameState === "function") {
    const state = activeModeGameState();
    if (state && state.fen) {
      const ctx = { fen: state.fen, move: "", pgn: "", camp_alain: state.campAlain || "" };
      // Mode exercice (issue #17) : sans ce complément, le chat libre ne
      // connaît que la position/le camp, pas le coup proposé ni le verdict
      // Stockfish déjà rendu par le coach pour cette tentative.
      if (activeMode === "exercise" && typeof exerciseChatContextExtra === "function") {
        return Object.assign(ctx, exerciseChatContextExtra());
      }
      return ctx;
    }
  }

  const fen  = reviewFens[reviewIdx] || "";
  const move = (reviewIdx > 0 && reviewMoves[reviewIdx - 1]) ? (reviewMoves[reviewIdx - 1].san || "") : "";
  let pgn = "";
  for (let i = 0; i < reviewMoves.length; i++) {
    const m = reviewMoves[i];
    if (m.color === "white") pgn += `${Math.floor(i / 2) + 1}. `;
    pgn += `${m.san} `;
  }
  return { fen, move: move.trim(), pgn: pgn.trim() };
}

function stripMarkdownForChat(text) {
  if (!text) return "";
  return text
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/_(.+?)_/g, "$1")
    .replace(/^[ \t]*[-*+]\s+/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function _coachRenderBubble(role, text) {
  const history = document.getElementById("coach-history");
  if (!history) return;
  const empty = document.getElementById("coach-empty");
  if (empty) empty.style.display = "none";
  const bubble = document.createElement("div");
  const isUser = role === "user";
  bubble.style.cssText = `background:${isUser ? "#e8f0f8" : "#dcecdc"}; border-radius:8px; padding:8px 12px; align-self:${isUser ? "flex-end" : "flex-start"}; max-width:88%; font-size:0.85rem; color:#1a2a3a; white-space:pre-wrap;`;
  bubble.textContent = text;
  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

function coachClear() {
  _coachHistory = [];
  const history = document.getElementById("coach-history");
  if (history) history.innerHTML = '<div id="coach-empty" style="color:#778; font-size:0.82rem; text-align:center; padding:20px 8px;">Posez une question sur la position affichée.</div>';
}

function coachSend() {
  if (_coachBusy) return;
  const input = document.getElementById("coach-input");
  if (!input || !input.value.trim()) return;
  const question = input.value.trim();
  input.value = "";
  _coachHistory.push({ role: "user", content: question });
  _coachRenderBubble("user", question);

  _coachBusy = true;
  const sendBtn = document.getElementById("coach-send-btn");
  if (sendBtn) sendBtn.disabled = true;
  const spinner = document.getElementById("coach-spinner");
  if (spinner) spinner.style.display = "flex";

  socket.emit("coach_ask", {
    messages: _coachHistory,
    context: coachBuildContext(),
  });
}

function _coachDone() {
  _coachBusy = false;
  const sendBtn = document.getElementById("coach-send-btn");
  if (sendBtn) sendBtn.disabled = false;
  const spinner = document.getElementById("coach-spinner");
  if (spinner) spinner.style.display = "none";
}

if (typeof socket !== "undefined") {
  socket.on("coach_response", (data) => {
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) {
      _coachHistory.push({ role: "assistant", content: text });
      _coachRenderBubble("assistant", text);
    }
    _coachDone();
  });

  socket.on("coach_error", (data) => {
    const msg = (data && data.error === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : "Le coach n'a pas pu répondre, réessayez.";
    console.warn("[coach]", msg, data);
    _coachDone();
  });
}

// ── Programme d'entraînement (issue #14) ────────────────────────────────────
// Bouton "Établir mon programme d'entraînement" : appel dédié au coach
// (training_program_build côté serveur), réponse structurée stockée dans
// objectifs_courants (coach_memory.json) et affichée dans le panneau dédié.
// Un nouvel appel remplace intégralement la liste affichée (pas d'historique).

function renderTrainingProgram(objectifs) {
  const list = document.getElementById("training-program-list");
  if (!list) return;
  list.innerHTML = "";
  if (!objectifs || !objectifs.length) {
    const li = document.createElement("li");
    li.id = "training-program-empty";
    li.style.cssText = "list-style:none; padding-left:0; color:#778;";
    li.textContent = "Aucun programme établi pour l'instant.";
    list.appendChild(li);
    return;
  }
  objectifs.forEach((objectif) => {
    const li = document.createElement("li");
    li.textContent = objectif;
    list.appendChild(li);
  });
}

function buildTrainingProgram() {
  const btn = document.getElementById("training-program-btn");
  if (btn) btn.disabled = true;
  const status = document.getElementById("training-program-status");
  if (status) status.textContent = "Génération du programme en cours...";
  socket.emit("training_program_build", {});
}

if (typeof socket !== "undefined") {
  socket.on("training_program_response", (data) => {
    const btn = document.getElementById("training-program-btn");
    if (btn) btn.disabled = false;
    const status = document.getElementById("training-program-status");
    if (status) status.textContent = "";
    renderTrainingProgram((data && data.objectifs) || []);
  });

  socket.on("training_program_error", (data) => {
    const btn = document.getElementById("training-program-btn");
    if (btn) btn.disabled = false;
    const err = data && data.error;
    const msg = (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : (err === "donnees_insuffisantes")
      ? "Pas encore assez de données (erreurs/ouvertures) pour établir un programme."
      : "Le programme n'a pas pu être établi, réessayez.";
    const status = document.getElementById("training-program-status");
    if (status) status.textContent = msg;
    console.warn("[programme entrainement]", msg, data);
  });
}

// ── Coach à la demande (issue #11) ──────────────────────────────────────────
// Bouton "Demander l'avis du coach" des modes pédagogique/ouverture/finales
// (visible quand la case "Commenter chaque coup" est décochée) : un seul
// aller-retour SocketIO mode-agnostique (coach_comment_on_demand côté
// serveur), réutilisé par les trois modes plutôt que dupliqué.

function askCoachOnDemand(fen, themeFinale, campAlain) {
  if (!fen) return;
  setCoachOnDemandButtonsDisabled(true);
  socket.emit("coach_comment_on_demand", { fen, theme_finale: themeFinale || "", camp_alain: campAlain || "" });
}

function setCoachOnDemandButtonsDisabled(disabled) {
  const btn = document.getElementById("shared-ask-coach-btn");
  if (btn) btn.disabled = disabled;
}

if (typeof socket !== "undefined") {
  socket.on("coach_on_demand_response", (data) => {
    setCoachOnDemandButtonsDisabled(false);
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("coach_on_demand_error", (data) => {
    setCoachOnDemandButtonsDisabled(false);
    const err = data && data.error;
    const msg = (err === "partie_terminee")
      ? "La partie est terminée."
      : (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : "Le coach n'a pas pu répondre, réessayez.";
    console.warn("[coach à la demande]", msg, data);
  });
}

// ── Retour à un état neutre (bouton "Abandonner", issue #11) ───────────────

function resetBoardToNeutral() {
  _boardFlipped = false;
  buildBoard();
  renderBoard("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR", null, null, null, null, null, null);
  const boardEl = document.getElementById("board");
  if (boardEl) {
    boardEl.onclick = null;
    boardEl.classList.remove("free-play-active");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const inp = document.getElementById("coach-input");
  if (inp) inp.addEventListener("keydown", e => { if (e.key === "Enter") coachSend(); });
});
