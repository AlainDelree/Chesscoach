/*
 * pedagogic.js — ChessCoach (issue #8)
 *
 * Mode "partie pédagogique" : combine le mode partie libre (issue #6, plateau
 * interactif clic-pour-jouer, réponse automatique de Stockfish) et le mode
 * exercice (issue #7, appel au coach avec comparaison coup_propose/
 * meilleur_coup). Alain joue un seul camp du début à la fin, Stockfish (force
 * réduite côté serveur, cf. EngineManager.get_move_pedagogique) répond
 * automatiquement à chacun de ses coups, et le coach commente chaque coup
 * d'Alain au fil de la partie.
 *
 * Réutilise buildBoard()/renderBoard() de board.js et
 * freeSquareIdToAlgebraic()/freeAlgebraicToSquareId() de free_play.js — seule
 * la source de la position (une nouvelle partie, pas la revue ni un
 * exercice figé) et le traitement après le coup (commentaire du coach +
 * réponse Stockfish enchaînée) diffèrent.
 */

let pedagogicGame       = null;  // instance chess.js (partie pédagogique)
let pedagogicActive     = false;
let pedagogicCampAlain  = "blancs";
let pedagogicSelected   = null;  // case algébrique sélectionnée ou null
let pedagogicWaiting    = false; // coup en cours de traitement côté serveur
let pedagogicGameOver   = false; // fin de partie détectée côté serveur (issue #11) ou abandon (issue #52)
let pedagogicAbandonne  = false; // fin de partie spécifiquement par "Abandonner" (issue #52, cf. coachBuildContext)
let pedagogicFenAvantCoup = null; // FEN juste avant le dernier coup d'Alain (issue #13, "Reprendre mon coup")

// ── Boutons "Jouer les Blancs/Noirs" déplacés avant le plateau sur mobile
// (issue #65 point 6) ─────────────────────────────────────────────────────
// Sur GSM, ce bloc (#pedagogic-start-buttons, dans le panneau à onglets,
// sous le plateau) était hors de vue tant qu'une partie n'était pas déjà
// lancée. Même mécanique de relocalisation DOM que placeModeTabBarForViewport
// (controls.js) — requête média propre plutôt qu'une dépendance à
// _mobileModeBarQuery (controls.js est chargé après ce fichier, cf. l'ordre
// des <script> dans templates/index.html).
let _pedagogicStartHomeParent      = null;
let _pedagogicStartHomeNextSibling = null;
const _pedagogicMobileQuery = window.matchMedia("(max-width: 900px)");

function placePedagogicStartButtonsForViewport() {
  const btns = document.getElementById("pedagogic-start-buttons");
  const slot = document.getElementById("mobile-pedagogic-start-slot");
  if (!btns || !slot || !_pedagogicStartHomeParent) return;
  // "Aucune partie en cours" = jamais démarrée, ou terminée/abandonnée —
  // dans les deux cas, mettre en avant les boutons pour en (re)lancer une.
  const gameEnCours = pedagogicActive && !pedagogicGameOver;
  const showInSlot = _pedagogicMobileQuery.matches && !gameEnCours;
  if (showInSlot) {
    if (btns.parentElement !== slot) slot.appendChild(btns);
  } else if (btns.parentElement !== _pedagogicStartHomeParent) {
    _pedagogicStartHomeParent.insertBefore(btns, _pedagogicStartHomeNextSibling);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btns = document.getElementById("pedagogic-start-buttons");
  if (btns) {
    _pedagogicStartHomeParent      = btns.parentElement;
    _pedagogicStartHomeNextSibling = btns.nextSibling;
    placePedagogicStartButtonsForViewport();
  }
  _pedagogicMobileQuery.addEventListener("change", () => placePedagogicStartButtonsForViewport());
});

function pedagogicCommenterChaqueCoup() {
  const cb = document.getElementById("shared-auto-comment");
  return !!(cb && cb.checked);
}

function startPedagogicGame(camp) {
  ensureModeSwitchClean("pedagogic");
  // Nouvelle partie (issue #64) : l'historique du chat envoyé à l'API repart
  // de zéro, séparé à l'écran des échanges de la partie précédente.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvelle partie");
  hideGameOverBanner();
  pedagogicCampAlain = (camp === "noirs") ? "noirs" : "blancs";
  pedagogicWaiting   = true;
  pedagogicGameOver  = false;
  pedagogicAbandonne = false;
  pedagogicFenAvantCoup = null;
  const statusEl = document.getElementById("pedagogic-status");
  if (statusEl) statusEl.textContent = "Démarrage de la partie...";
  socket.emit("pedagogic_start", { camp: pedagogicCampAlain });
}

// Issue #52 : "Abandonner" ne remet plus le plateau à zéro — la partie
// atteinte reste affichée (plateau, historique, bannière de défaite comme
// pour un mat), coups suivants bloqués via pedagogicGameOver (déjà lu par
// onPedagogicBoardClick). Le plateau ne redevient vierge qu'au démarrage
// explicite d'une nouvelle partie ou à un changement de mode.
function abandonPedagogicGame() {
  if (!pedagogicActive || pedagogicGameOver) return;
  socket.emit("pedagogic_abandon", {});
  pedagogicGameOver  = true;
  pedagogicAbandonne = true;
  pedagogicWaiting   = false;
  pedagogicSelected  = null;
  pedagogicFenAvantCoup = null;
  const statusEl = document.getElementById("pedagogic-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée — défaite.";
  const opposant = pedagogicCampAlain === "noirs" ? "blancs" : "noirs";
  showGameOverBanner(
    { gagnant: opposant, message: "Partie abandonnée par Alain — défaite." },
    pedagogicCampAlain,
    () => analyserPartieDepuisPgn(_pedagogicGamePgnForAnalysis())
  );
  // Issue #65 point 5 : grise "Demander l'avis du coach" (askCoachAvailable,
  // controls.js) dès l'abandon, et déplace "Jouer les Blancs/Noirs" en haut
  // sur mobile (placePedagogicStartButtonsForViewport) puisqu'aucune partie
  // n'est plus en cours.
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
}

function reprendrePedagogicCoup() {
  const statusEl = document.getElementById("pedagogic-status");
  if (!pedagogicActive || pedagogicWaiting || !pedagogicFenAvantCoup) {
    if (statusEl && pedagogicActive && !pedagogicWaiting) statusEl.textContent = "Aucun coup à reprendre.";
    return;
  }
  pedagogicGame     = new Chess(pedagogicFenAvantCoup);
  pedagogicGameOver = false;
  pedagogicSelected = null;
  pedagogicFenAvantCoup = null;
  hideGameOverBanner();
  renderPedagogicBoard();
  updatePedagogicStatus();
  // Issue #65 point 5 : la partie redevient en cours (pedagogicGameOver
  // retombe à false) — réactive "Demander l'avis du coach" et renvoie
  // "Jouer les Blancs/Noirs" à leur emplacement d'origine sur mobile.
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
}

function askPedagogicCoach() {
  if (!pedagogicActive || !pedagogicGame || pedagogicGameOver || pedagogicWaiting) return;
  askCoachOnDemand(pedagogicGame.fen(), null, pedagogicCampAlain);
}

function renderPedagogicBoard(lastFrom, lastTo) {
  if (!pedagogicGame) return;
  const fenBoard = pedagogicGame.fen().split(" ")[0];
  const from = lastFrom ? freeAlgebraicToSquareId(lastFrom) : null;
  const to   = lastTo   ? freeAlgebraicToSquareId(lastTo)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (pedagogicSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(pedagogicSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  renderHistory();
}

function updatePedagogicStatus() {
  const statusEl = document.getElementById("pedagogic-status");
  if (!statusEl || !pedagogicGame) return;
  let text = pedagogicGame.turn() === "w" ? "Trait aux Blancs" : "Trait aux Noirs";
  if (pedagogicGame.in_checkmate())      text = "Échec et mat.";
  else if (pedagogicGame.in_stalemate()) text = "Pat.";
  else if (pedagogicGame.in_draw())      text = "Partie nulle.";
  else if (pedagogicGame.in_check())     text += " (échec)";
  if (pedagogicWaiting) text += " — le coach et Stockfish réfléchissent...";
  statusEl.textContent = text;
}

// PGN de la partie pédagogique en cours, avec en-têtes (issue #41, point
// d'entrée "Analyser cette partie" depuis la bannière de fin de partie) —
// pedagogicGame n'a pas d'en-têtes par défaut (chess.js).
function _pedagogicGamePgnForAnalysis() {
  if (!pedagogicGame) return "";
  const white = pedagogicCampAlain === "noirs" ? "Stockfish" : "Alain";
  const black = pedagogicCampAlain === "noirs" ? "Alain" : "Stockfish";
  pedagogicGame.header("White", white, "Black", black);
  return pedagogicGame.pgn();
}

function pedagogicIsAlainTurn() {
  if (!pedagogicGame) return false;
  const trait = pedagogicGame.turn() === "w" ? "blancs" : "noirs";
  return trait === pedagogicCampAlain;
}

function onPedagogicBoardClick(e) {
  if (!pedagogicActive || !pedagogicGame || pedagogicWaiting || pedagogicGameOver) return;
  if (!pedagogicIsAlainTurn()) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!pedagogicSelected) {
    const piece = pedagogicGame.get(square);
    if (piece && piece.color === pedagogicGame.turn()) {
      pedagogicSelected = square;
      renderPedagogicBoard();
    }
    return;
  }

  if (pedagogicSelected === square) {
    pedagogicSelected = null;
    renderPedagogicBoard();
    return;
  }

  const fenAvant = pedagogicGame.fen();
  const move = pedagogicGame.move({ from: pedagogicSelected, to: square, promotion: "q" });
  pedagogicSelected = null;

  if (!move) {
    const piece = pedagogicGame.get(square);
    if (piece && piece.color === pedagogicGame.turn()) {
      pedagogicSelected = square;
    }
    renderPedagogicBoard();
    return;
  }

  renderPedagogicBoard(move.from, move.to);
  pedagogicWaiting = true;
  pedagogicFenAvantCoup = fenAvant;
  updatePedagogicStatus();
  _coachRenderBubble("user", `Partie pédagogique — je joue ${move.san}`);
  socket.emit("pedagogic_move", {
    fen_avant: fenAvant,
    uci: move.from + move.to + (move.promotion || ""),
    commenter: pedagogicCommenterChaqueCoup(),
  });
}

if (typeof socket !== "undefined") {
  socket.on("pedagogic_started", (data) => {
    if (!data || !data.fen) return;
    pedagogicGame      = new Chess(data.fen);
    pedagogicActive    = true;
    pedagogicWaiting   = false;
    pedagogicSelected  = null;
    pedagogicGameOver  = false;
    pedagogicAbandonne = false;
    pedagogicCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    setActiveMode("pedagogic");
    // Issue #65 point 6 : la partie démarre — les boutons "Jouer les
    // Blancs/Noirs" reprennent leur emplacement d'origine sur mobile.
    placePedagogicStartButtonsForViewport();

    _boardFlipped = (pedagogicCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onPedagogicBoardClick;

    let lastFrom = null, lastTo = null;
    if (data.coup_ouverture) {
      lastFrom = data.coup_ouverture.slice(0, 2);
      lastTo   = data.coup_ouverture.slice(2, 4);
    }
    renderPedagogicBoard(lastFrom, lastTo);
    updatePedagogicStatus();
  });

  socket.on("pedagogic_stockfish_move", (data) => {
    pedagogicWaiting = false;
    if (!pedagogicActive || !pedagogicGame || !data) return;

    if (data.uci) {
      const move = pedagogicGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderPedagogicBoard(move.from, move.to);
      }
    }
    if (data.game_over) {
      pedagogicGameOver = true;
      const statusEl = document.getElementById("pedagogic-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, pedagogicCampAlain, () => analyserPartieDepuisPgn(_pedagogicGamePgnForAnalysis()));
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      if (typeof placePedagogicStartButtonsForViewport === "function") placePedagogicStartButtonsForViewport();
      return;
    }
    updatePedagogicStatus();
  });

  socket.on("pedagogic_comment", (data) => {
    const text = stripMarkdownForChat((data && data.text) || "");
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("pedagogic_error", (data) => {
    pedagogicWaiting = false;
    const err = data && data.error;
    if (err === "credit_insuffisant") {
      if (typeof _coachRenderCreditInsuffisant === "function") _coachRenderCreditInsuffisant();
      console.warn("[partie pédagogique]", "credit_insuffisant", data);
      return;
    }
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : (err === "coup_illegal")
      ? "Coup illégal détecté côté serveur."
      : "Le coach n'a pas pu répondre, réessayez.";
    const statusEl = document.getElementById("pedagogic-status");
    if (statusEl) statusEl.textContent = msg;
    console.warn("[partie pédagogique]", msg, data);
  });
}
