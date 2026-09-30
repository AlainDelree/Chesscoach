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

  // Issue #34 : le bouton "Retourner" (hérité du mode revue PGN) doit
  // retourner l'échiquier du mode interactif actif (partie libre,
  // pédagogique, ouverture, finales, exercice, éditeur) s'il y en a un,
  // plutôt que de toujours réafficher la position de revue — même repli
  // que extraireFen() (controls.js).
  if (activeMode === "editor" && typeof renderEditorBoard === "function") {
    renderEditorBoard();
    return;
  }
  if (activeMode && typeof activeModeGameState === "function") {
    const state = activeModeGameState();
    if (state && state.fen) {
      renderBoard(state.fen.split(" ")[0], null, null, null, null, null, null);
      return;
    }
  }

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
// En-têtes PGN White/Black de la partie chargée en revue (issue #56) — pour
// que game_analysis.js puisse déduire le camp d'Alain (pseudo athanatos123
// ou nom "Alain", cf. game_facts.camp_alain_from_pgn_headers côté serveur)
// sans redemander le PGN complet à chaque appel au coach.
let reviewWhite    = "";
let reviewBlack    = "";

// Bloqués pendant la lecture d'une ligne du coach (issue #68,
// gameCoachLinesPreviewActive — game_coach_lines.js) : naviguer dans la
// revue pendant qu'une ligne est affichée sur le plateau mélangerait la
// position réellement affichée (celle de la ligne) avec la navigation
// réelle (reviewIdx), sans qu'aucune des deux ne s'y retrouve — mêmes clics
// bloqués que sur les plateaux interactifs (onFreePlayBoardClick and co.).
function _reviewBlockedByLinePreview() {
  return typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive;
}

function reviewPrev() {
  if (_reviewBlockedByLinePreview()) return;
  if (reviewIdx > 0) { reviewIdx--; renderReview(); }
}
function reviewNext() {
  if (_reviewBlockedByLinePreview()) return;
  if (reviewIdx < reviewFens.length - 1) { reviewIdx++; renderReview(); }
}
function reviewGoTo(index) {
  if (_reviewBlockedByLinePreview()) return;
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

  if (typeof updateGameStatusLine === "function") updateGameStatusLine();
}

// ── Ligne d'état compacte du mode jeu mobile (issue #70 point 1/5) ─────────
// "Coup N · coup" (même convention de numérotation que review-move-info,
// c-à-d le nombre de demi-coups joués — pas le numéro de coup plein de la
// maquette, pour rester cohérent avec le reste de l'appli plutôt que
// d'introduire une seconde numérotation) + matériel capturé condensé (une
// pastille de la couleur en avance, "=" en cas d'égalité) + camp au trait.
// Alimente à la fois la ligne d'état sous le plateau complet et la bande
// compacte (#board-compact-strip) — sans effet tant que ces éléments sont
// absents/masqués (grand écran, modes hors jeu). Appelée depuis
// renderHistory() (déjà invoquée après chaque coup, tous modes confondus).
function _materialDiffFromFenBoard(fenBoard) {
  const vals = { p: 1, n: 3, b: 3, r: 5, q: 9 };
  let scoreW = 0, scoreB = 0;
  for (const ch of fenBoard) {
    const lower = ch.toLowerCase();
    if (!(lower in vals)) continue;
    if (ch === lower) scoreB += vals[lower]; else scoreW += vals[lower];
  }
  return scoreW - scoreB;
}

function updateGameStatusLine() {
  const moveEl  = document.getElementById("game-status-move");
  const rightEl = document.getElementById("game-status-right");
  const compactMoveEl = document.getElementById("board-compact-move");
  const compactMatEl  = document.getElementById("board-compact-material");
  if (!moveEl && !compactMoveEl) return;

  let nbCoups = 0, lastSan = "", fenBoard = "", turnBlancs = true;
  if (typeof activeMode !== "undefined" && activeMode && typeof activeModeGameState === "function") {
    const state = activeModeGameState();
    if (state && state.fen) {
      nbCoups = state.nbCoups || 0;
      lastSan = state.move || "";
      fenBoard = state.fen.split(" ")[0];
      turnBlancs = state.fen.split(" ")[1] !== "b";
    }
  } else if (typeof reviewFens !== "undefined" && reviewFens && reviewFens.length) {
    nbCoups = reviewIdx;
    fenBoard = reviewFens[reviewIdx] || "";
    lastSan = (reviewIdx > 0 && reviewMoves[reviewIdx - 1]) ? reviewMoves[reviewIdx - 1].san : "";
    turnBlancs = (reviewIdx % 2) === 0;
  } else {
    return;
  }

  const moveText = nbCoups > 0 ? `Coup ${nbCoups} · ${lastSan}` : "Position initiale";
  if (moveEl) moveEl.textContent = moveText;
  if (compactMoveEl) compactMoveEl.textContent = moveText;

  const diff = fenBoard ? _materialDiffFromFenBoard(fenBoard) : 0;
  const turnText = turnBlancs ? "Trait aux Blancs" : "Trait aux Noirs";
  let materialText;
  if (diff === 0) {
    materialText = "=";
  } else {
    materialText = (diff > 0 ? "Blancs" : "Noirs") + " +" + Math.abs(diff);
  }
  if (rightEl) {
    rightEl.innerHTML = "";
    if (diff !== 0) {
      const dot = document.createElement("span");
      dot.className = "game-status-dot " + (diff > 0 ? "white" : "black");
      rightEl.appendChild(dot);
    }
    const matSpan = document.createElement("span");
    matSpan.textContent = materialText;
    rightEl.appendChild(matSpan);
    const turnSpan = document.createElement("span");
    turnSpan.textContent = turnText;
    rightEl.appendChild(turnSpan);
  }
  if (compactMatEl) compactMatEl.textContent = `${materialText} · ${turnText}`;
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
  // Issue #68 : un mode de partie (libre/pédagogique/ouverture/finales) ne
  // remet jamais lui-même activeMode à null après une fin de partie (seuls
  // exercice/éditeur le font, cf. abandonExerciseGame/abandonPositionEditor)
  // — sans ce retour explicite, charger une partie en revue juste après en
  // avoir joué une laisserait coachBuildContext()/gameCoachLinesOnCoachText
  // continuer à lire l'ancienne partie interactive (activeModeGameState())
  // au lieu de celle qu'on vient de charger.
  if (typeof setActiveMode === "function") setActiveMode(null);
  // Autre partie chargée en revue de bibliothèque (issue #64) : l'historique
  // du chat envoyé à l'API repart de zéro, séparé à l'écran des échanges de
  // la partie précédemment revue.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvelle partie");
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
    reviewWhite = white;
    reviewBlack = black;
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

// Isolation de l'historique envoyé à l'API d'une partie/exercice à l'autre
// (issue #64) : _coachHistory garde tous les messages affichés à l'écran
// depuis le dernier clic sur "Effacer" (coachClear), mais seuls ceux depuis
// _coachSegmentStart sont renvoyés à l'API par coachSend() — sans cette
// coupure, le modèle recevait encore les questions/réponses d'une partie
// terminée en même temps que le contexte (PGN/faits) de la partie suivante,
// et mélangeait les deux (constat en usage réel, GSM/Haiku, deux parties
// jouées à la suite sans effacer le chat). _coachSegmentStartedAt (issue #64
// point 3) donne au coach une heure de début pour la partie/l'exercice
// actuellement discuté(e), transmise dans le contexte (coachBuildContext).
let _coachSegmentStart      = 0;
let _coachSegmentStartedAt  = null;

// Correspondance activeMode (controls.js) → mode_origine attendu côté
// serveur pour le logging coach_calls.log (issue #26, part. 3) — partagée
// entre coachBuildContext() et askCoachOnDemand() ci-dessous.
const _MODE_ORIGINE_LABELS = {
  pedagogic: "pedagogique",
  opening: "ouverture",
  finale: "finales",
  exercise: "exercice",
};

// Rapproche le rapport mécanique de la dernière analyse "Analyser cette
// partie" (_gameAnalysisResults, game_analysis.js — reste en mémoire tant
// que la page n'est pas rechargée, quel que soit l'onglet actif depuis) de
// la partie réellement en cours dans le mode interactif actif, coup à coup
// (même longueur, mêmes SAN dans le même ordre) : une correspondance
// partielle ou une partie différente ne doit jamais être transmise comme si
// elle décrivait la partie en cours (issue #55 point 4). Retourne [] si
// aucune analyse en mémoire ou si elle ne correspond pas à cette partie.
//
// fen_avant/best_move (issue #57 point 2) : transmis en plus des champs
// d'affichage historiques pour que le serveur (app.py
// _cached_stockfish_eval) puisse reconnaître une position déjà analysée par
// Stockfish cette session et éviter un nouvel appel moteur pour la
// vérification ciblée du chat coach — matché côté serveur sur fen_avant
// exact, jamais sur le seul numéro de coup.
function _coachAnalysisFlaggedMoves() {
  if (typeof _gameAnalysisResults === "undefined" || !_gameAnalysisResults.length) return [];
  if (typeof getActiveModeMoves !== "function") return [];
  const liveMoves = getActiveModeMoves();
  if (!liveMoves || liveMoves.length !== _gameAnalysisResults.length) return [];
  for (let i = 0; i < liveMoves.length; i++) {
    if (liveMoves[i].san !== _gameAnalysisResults[i].san) return [];
  }
  return _gameAnalysisResults
    .filter(m => m.qualite && m.qualite !== "bon")
    .map(m => ({
      coup_plein: m.coup_plein,
      san: m.san,
      camp: m.color === "white" ? "blancs" : "noirs",
      delta_cp: m.delta_cp,
      qualite: m.qualite,
      fen_avant: m.fen_avant,
      best_move: m.best_move,
    }));
}

function coachBuildContext() {
  // Chat libre pendant un mode interactif en cours (issue #15 point 3) : le
  // coach doit connaître la position réelle du mode actif (activeMode, cf.
  // controls.js), pas la position de la revue PGN qui n'a pas bougé.
  if (typeof activeMode !== "undefined" && activeMode && typeof activeModeGameState === "function") {
    const state = activeModeGameState();
    if (state && state.fen) {
      const modeOrigine = _MODE_ORIGINE_LABELS[activeMode] || "chat_libre";
      // Historique des coups (pgn/move, issue #33, étendu à "free" par
      // l'issue #52) : pertinent pour les parties libre/pédagogique/
      // ouverture/finale (une vraie partie en cours), pas pour le mode
      // exercice qui porte sur une position isolée par nature (hors
      // périmètre issue #33, cf. exerciseChatContextExtra qui fournit déjà
      // son propre contexte dédié).
      const avecHistorique = activeMode === "pedagogic" || activeMode === "opening" || activeMode === "finale" || activeMode === "free";
      const ctx = {
        fen: state.fen,
        move: avecHistorique ? (state.move || "") : "",
        pgn: avecHistorique ? (state.pgn || "") : "",
        camp_alain: state.campAlain || "",
        mode_origine: modeOrigine,
        // Identification de la partie/l'exercice en cours (issue #64 point
        // 3) : donne au coach de quoi distinguer explicitement cette
        // partie-ci d'une autre mentionnée plus tôt dans la conversation
        // affichée, en plus de l'isolation de l'historique côté coachSend().
        nb_coups: state.nbCoups || 0,
        debut_partie: _coachSegmentStartedAt || "",
      };
      // Coups flagués par une analyse mécanique Stockfish déjà effectuée
      // cette session (bouton "Analyser cette partie", issue #55 point 4) :
      // transmis au bloc de faits calculés côté serveur (game_facts.py) s'ils
      // correspondent bien à LA partie en cours (mêmes coups, même ordre) —
      // jamais ceux d'une autre partie analysée plus tôt dans la session.
      if (avecHistorique) {
        const flagges = _coachAnalysisFlaggedMoves();
        if (flagges && flagges.length) ctx.analyse_mecanique_flags = flagges;
      }
      // Partie terminée par abandon (issue #52) : sans ce signal explicite,
      // le chat libre sollicité juste après ne sait pas que la partie est
      // finie — voir _build_context_text (llm_coach.py).
      if (state.abandonne) {
        ctx.partie_terminee = true;
        ctx.resultat_partie = "Alain a abandonné cette partie.";
      }
      // Mode exercice (issue #17) : sans ce complément, le chat libre ne
      // connaît que la position/le camp, pas le coup proposé ni le verdict
      // Stockfish déjà rendu par le coach pour cette tentative.
      if (activeMode === "exercise" && typeof exerciseChatContextExtra === "function") {
        return Object.assign(ctx, exerciseChatContextExtra());
      }
      // Mode "Travail de finales" en démonstration (issue #29) : sans ce
      // complément, le coach ne peut pas distinguer une position atteinte
      // par une démonstration Stockfish-contre-Stockfish d'une partie
      // réellement jouée par Alain (voir finales.js finaleChatContextExtra).
      if (activeMode === "finale" && typeof finaleChatContextExtra === "function") {
        return Object.assign(ctx, finaleChatContextExtra());
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
  return {
    fen, move: move.trim(), pgn: pgn.trim(), mode_origine: "chat_libre",
    // Identification de la partie en revue (issue #64 point 3), même
    // logique que la branche mode interactif ci-dessus.
    nb_coups: reviewMoves.length,
    debut_partie: _coachSegmentStartedAt || "",
  };
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

// Révèle un nouveau message du chat coach, que #coach-history défile en
// interne (bureau, ou mobile si jamais le CSS venait à réintroduire un
// overflow-y:auto — repli robuste) ou non (mobile, issue #65 point 3 : plus
// de zone à défilement interne, cf. board.css/templates/index.html — c'est
// la PAGE qui défile). Détection au comportement (scrollHeight >
// clientHeight) plutôt qu'à la largeur d'écran : n'importe quel media query
// peut faire varier ce point, ce test reste vrai dans tous les cas.
// `toStart` reprend la logique de l'issue #53 : true pour placer le DÉBUT de
// l'élément en haut de la zone visible (réponse du coach), false pour
// afficher sa fin (message d'Alain, séparateur, erreur).
// `allowPageScroll` (issue #67) : sur mobile (branche "page qui défile"),
// seuls les cas où Alain attend effectivement la réponse doivent faire
// défiler la PAGE (réponse à une question tapée, réponse à "Demander l'avis
// du coach", verdict d'exercice) — tous les autres messages automatiques
// (coup joué, commentaire "Commenter chaque coup", info, erreur, séparateur)
// restent silencieux pour ne pas faire sortir le plateau de l'écran à chaque
// coup. Le défilement interne (bureau) n'est lui jamais concerné par ce
// paramètre : comportement grand écran inchangé.
function _coachScrollReveal(history, el, toStart, allowPageScroll) {
  const internallyScrollable = history.scrollHeight > history.clientHeight + 1;
  if (internallyScrollable) {
    if (toStart) {
      // getBoundingClientRect() plutôt que bubble.offsetTop : #coach-history
      // n'a pas de position définie, donc ses enfants n'ont pas cette div
      // comme offsetParent (le navigateur remonte jusqu'à <body>) —
      // offsetTop serait alors faux ici. Si la réponse est courte, le
      // navigateur borne scrollTop à la valeur max possible, ce qui revient
      // à tout afficher sans espace vide — pas de cas particulier à gérer
      // pour les réponses courtes.
      const historyRect = history.getBoundingClientRect();
      const elRect = el.getBoundingClientRect();
      history.scrollTop += elRect.top - historyRect.top;
    } else {
      history.scrollTop = history.scrollHeight;
    }
  } else if (allowPageScroll) {
    el.scrollIntoView({ block: toStart ? "start" : "end" });
  }
}

// `allowPageScroll` (issue #67, défaut false) : à ne passer à true que pour
// les réponses qu'Alain attend activement (réponse à une question tapée,
// réponse à "Demander l'avis du coach") — pas pour les messages automatiques
// ("je joue ...", commentaires, info, erreur). Cf. _coachScrollReveal.
// `extraClass` (issue #69 point 3, optionnel) : classe CSS ajoutée à la bulle
// — sert à "coach-bubble-auto-move" (message "je joue ..." des modes
// pédagogique/ouverture/finales, masqué dans le chat sur mobile par CSS
// uniquement, cf. templates/index.html) sans dupliquer ni changer les données
// envoyées à l'API (cette fonction ne touche jamais _coachHistory/socket.emit).
function _coachRenderBubble(role, text, allowPageScroll, extraClass) {
  const history = document.getElementById("coach-history");
  if (!history) return;
  const empty = document.getElementById("coach-empty");
  if (empty) empty.style.display = "none";
  const bubble = document.createElement("div");
  const isUser = role === "user";
  bubble.className = "coach-bubble " + (isUser ? "user" : "assistant") + (extraClass ? " " + extraClass : "");
  bubble.textContent = text;
  history.appendChild(bubble);
  // Message d'Alain : comportement inchangé, on descend tout en bas (voir
  // son message envoyé). Réponse du coach : afficher le DÉBUT de la réponse
  // en haut de la zone plutôt que sa fin (issue #53).
  _coachScrollReveal(history, bubble, !isUser, allowPageScroll);
}

// Même lien que le "Coût API" de l'en-tête (issue #54) — la Console est
// aussi l'endroit où Alain recharge son crédit, pas seulement où il le
// consulte.
const CONSOLE_API_URL = "https://platform.claude.com/cost";

// Message dédié pour l'erreur "crédit épuisé" (issue #54) : un texte clair
// dans le chat du coach plutôt qu'une erreur technique générique, avec un
// lien direct vers la Console pour recharger. Rendu à part de
// _coachRenderBubble (texte brut) car il faut un lien cliquable — seul cas
// du chat coach ayant besoin de plus que du texte simple.
function _coachRenderCreditInsuffisant() {
  const history = document.getElementById("coach-history");
  if (!history) return;
  const empty = document.getElementById("coach-empty");
  if (empty) empty.style.display = "none";
  const bubble = document.createElement("div");
  bubble.className = "coach-bubble error";
  const p = document.createElement("div");
  p.textContent = "Le crédit de l'API Claude est épuisé — le coach ne peut plus répondre pour le moment.";
  bubble.appendChild(p);
  const a = document.createElement("a");
  a.href = CONSOLE_API_URL;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  a.textContent = "Recharger sur la Console";
  bubble.appendChild(a);
  history.appendChild(bubble);
  _coachScrollReveal(history, bubble, false);
}

// Point de coupure d'un nouveau segment de conversation (issue #64) : appelé
// au démarrage effectif d'une nouvelle partie/exercice (partie libre,
// pédagogique, ouverture, finales, exercice) ou au chargement d'une autre
// partie en revue de bibliothèque — jamais lors d'une simple navigation
// entre onglets. `label` est affiché comme séparateur discret ("Nouvelle
// partie"/"Nouvel exercice") uniquement s'il y a déjà des messages dans le
// segment précédent — pas de séparateur vide au tout premier segment, ni de
// séparateurs empilés si aucune question n'a été posée depuis le précédent.
function coachNewSegment(label) {
  if (_coachHistory.length > _coachSegmentStart) {
    const history = document.getElementById("coach-history");
    if (history) {
      const sep = document.createElement("div");
      sep.className = "coach-separator";
      sep.textContent = label || "Nouvelle partie";
      history.appendChild(sep);
      _coachScrollReveal(history, sep, false);
    }
  }
  _coachSegmentStart     = _coachHistory.length;
  _coachSegmentStartedAt = new Date().toISOString();
  // Tableau "Lignes du coach" des modes de partie/revue (issue #68) : vidé
  // aux mêmes points de coupure que l'isolation du chat par partie
  // (coachNewSegment est appelé au démarrage de chaque nouvelle partie/
  // exercice et au chargement d'une autre partie en revue) — no-op en mode
  // exercice (garde son propre tableau, exercise.js/_exerciseResetCoachLines).
  if (typeof gameCoachLinesReset === "function") gameCoachLinesReset();
}

function coachClear() {
  _coachHistory = [];
  _coachSegmentStart     = 0;
  _coachSegmentStartedAt = null;
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
    // Seuls les messages du segment courant (issue #64) — pas tout
    // _coachHistory, qui garde à l'écran les échanges des parties/exercices
    // précédents jusqu'au prochain "Effacer".
    messages: _coachHistory.slice(_coachSegmentStart),
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
      // Réponse à une question tapée par Alain : il l'attend, la page doit
      // défiler jusqu'à elle sur mobile (issue #67).
      _coachRenderBubble("assistant", text, true);
      // Alimente le tableau "Lignes du coach" du mode exercice (issue #58)
      // quand cette réponse arrive pendant un exercice actif — no-op pour
      // tout autre mode (fonction absente, ou exerciseActive faux).
      if (typeof exerciseOnCoachText === "function") exerciseOnCoachText(text);
      // Idem pour le tableau des modes de partie/revue (issue #68) — no-op
      // en mode exercice/éditeur ou si aucune partie/revue n'est chargée
      // (cf. gameCoachLinesOnCoachText, game_coach_lines.js).
      if (typeof gameCoachLinesOnCoachText === "function") gameCoachLinesOnCoachText(text);
    }
    // Bonus (issue #68 point 5) : ligne principale déjà calculée par la
    // vérification Stockfish du bloc de faits pour cette partie (cf. app.py
    // on_coach_ask/_enrich_context_with_game_facts), transmise avec sa
    // position de départ réelle — jamais recalculée côté client, jamais
    // ajoutée si absente/vide.
    if (data && data.stockfish_line && typeof gameCoachLinesOnStockfishLine === "function") {
      gameCoachLinesOnStockfishLine(data.stockfish_line);
    }
    _coachDone();
  });

  socket.on("coach_error", (data) => {
    const err = data && data.error;
    if (err === "credit_insuffisant") {
      _coachRenderCreditInsuffisant();
    } else {
      const msg = (err === "no_api_key")
        ? "Clé API Claude manquante — configurez-la dans les paramètres."
        : "Le coach n'a pas pu répondre, réessayez.";
      console.warn("[coach]", msg, data);
    }
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
    const msg = (err === "credit_insuffisant")
      ? "Crédit de l'API Claude épuisé — rechargez sur la Console (lien \"Coût API\" en haut de la page)."
      : (err === "no_api_key")
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
  const modeOrigine = (typeof activeMode !== "undefined" && _MODE_ORIGINE_LABELS[activeMode]) || "chat_libre";
  socket.emit("coach_comment_on_demand", {
    fen, theme_finale: themeFinale || "", camp_alain: campAlain || "", mode_origine: modeOrigine,
  });
}

function setCoachOnDemandButtonsDisabled(disabled) {
  const btn = document.getElementById("shared-ask-coach-btn");
  if (btn) btn.disabled = disabled;
}

if (typeof socket !== "undefined") {
  socket.on("coach_on_demand_response", (data) => {
    setCoachOnDemandButtonsDisabled(false);
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) {
      // Réponse au bouton "Demander l'avis du coach" : Alain l'attend, la
      // page doit défiler jusqu'à elle sur mobile (issue #67).
      _coachRenderBubble("assistant", text, true);
      if (typeof exerciseOnCoachText === "function") exerciseOnCoachText(text);
      if (typeof gameCoachLinesOnCoachText === "function") gameCoachLinesOnCoachText(text);
    }
  });

  socket.on("coach_on_demand_error", (data) => {
    setCoachOnDemandButtonsDisabled(false);
    const err = data && data.error;
    if (err === "credit_insuffisant") {
      _coachRenderCreditInsuffisant();
      return;
    }
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
  hideGameOverBanner();
}

// ── Bannière de fin de partie (issue #31) ───────────────────────────────────
// Rend le résultat (mat/pat/nulle, cf. app.py _game_over_info) nettement plus
// visible que la ligne de statut discrète des panneaux de mode : bandeau
// au-dessus de l'échiquier, texte plus grand et gras, couleur de fond selon
// le résultat. `campAlain` ("blancs"/"noirs"), quand connu par l'appelant,
// permet de distinguer victoire/défaite ; omis (démonstration, partie libre)
// il retombe sur une couleur neutre "mat" plutôt que de deviner un camp.
//
// `onAnalyser` (issue #41, point d'entrée "Analyser cette partie" depuis une
// partie pédagogique/libre qui vient de se terminer) : callback optionnel,
// ajouté sous forme de bouton dans la bannière quand fourni par l'appelant
// (pedagogic.js/free_play.js uniquement — pas opening.js/finales.js, hors
// périmètre de l'issue #41).

function showGameOverBanner(gameOverInfo, campAlain, onAnalyser) {
  const el = document.getElementById("game-over-banner");
  if (!el || !gameOverInfo) return;
  let categorie = "nulle";
  if (gameOverInfo.gagnant) {
    categorie = campAlain
      ? (gameOverInfo.gagnant === campAlain ? "victoire" : "defaite")
      : "mat";
  }
  el.className = "game-over-banner game-over-banner--" + categorie;
  el.innerHTML = "";
  const msg = document.createElement("span");
  msg.textContent = gameOverInfo.message;
  el.appendChild(msg);
  if (typeof onAnalyser === "function") {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "game-over-banner-analyse-btn";
    btn.textContent = "Analyser cette partie";
    btn.onclick = onAnalyser;
    el.appendChild(btn);
  }
  el.style.display = "block";
  // Classe sur <body> (issue #70 point 4) : permet au CSS du mode jeu mobile
  // de masquer la barre d'actions/le bandeau avant-partie pendant que ce
  // bandeau de résultat est affiché, sans dépendre d'un sélecteur d'attribut
  // fragile sur le style inline ci-dessus.
  document.body.classList.add("game-over-active");
}

function hideGameOverBanner() {
  const el = document.getElementById("game-over-banner");
  if (el) el.style.display = "none";
  document.body.classList.remove("game-over-active");
}

document.addEventListener("DOMContentLoaded", () => {
  const inp = document.getElementById("coach-input");
  if (inp) inp.addEventListener("keydown", e => { if (e.key === "Enter") coachSend(); });
});
