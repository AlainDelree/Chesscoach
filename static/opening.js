/*
 * opening.js — ChessCoach (issue #9)
 *
 * Mode "travail d'ouverture" : reprend la mécanique du mode pédagogique
 * (issue #8, plateau interactif clic-pour-jouer, réponse automatique de
 * l'adversaire, commentaire du coach après chaque coup d'Alain), avec une
 * différence pendant la phase d'ouverture : l'adversaire suit le livre
 * Polyglot réel gm2001.bin plutôt que Stockfish, jusqu'à la sortie du livre
 * (bascule transparente vers le comportement du mode pédagogique, gérée
 * côté serveur — voir app.py on_opening_move).
 *
 * Réutilise buildBoard()/renderBoard() de board.js et
 * freeSquareIdToAlgebraic()/freeAlgebraicToSquareId() de free_play.js, comme
 * pedagogic.js.
 */

let openingGame       = null;  // instance chess.js (mode travail d'ouverture)
let openingActive     = false;
let openingCampAlain  = "blancs";
let openingSelected   = null;  // case algébrique sélectionnée ou null
let openingWaiting    = false; // coup en cours de traitement côté serveur
let openingInBook     = false; // la partie est encore dans le livre Polyglot
let openingGameOver   = false; // fin de partie détectée côté serveur (issue #11) ou abandon (issue #52)
let openingAbandonne  = false; // fin de partie spécifiquement par "Abandonner" (issue #52, cf. coachBuildContext)
let openingFenAvantCoup     = null;  // FEN juste avant le dernier coup d'Alain (issue #13, "Reprendre mon coup")
let openingInBookAvantCoup  = false; // valeur de openingInBook avant ce même coup

// ── Suggestions rapides d'ouvertures populaires (issue #27) ────────────────
// Coups les plus pondérés du livre Polyglot gm2001.bin à la position de
// départ (opening_book.get_starting_suggestions côté serveur), en plus du
// champ texte libre déjà existant. Un clic préremplit ce même champ — le nom
// reconnu (1.e4/1.d4/1.c4/1.Nf3) pour les quatre familles standards, sinon
// juste le coup lui-même — puis Alain clique "Jouer les Blancs/Noirs" comme
// pour un nom saisi à la main : aucun nouveau chemin de démarrage de partie.
function renderOpeningSuggestions(suggestions) {
  const listEl  = document.getElementById("opening-suggestions");
  const labelEl = document.getElementById("opening-suggestions-label");
  if (!listEl) return;
  listEl.innerHTML = "";
  if (!suggestions || !suggestions.length) {
    if (labelEl) labelEl.textContent = "";
    return;
  }
  if (labelEl) labelEl.textContent = "Ouvertures populaires (livre gm2001.bin) :";
  suggestions.forEach((s) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "opening-suggestion-btn";
    const label = s.nom || `1.${s.san}`;
    btn.textContent = s.pct !== null && s.pct !== undefined ? `${label} (${s.pct}%)` : label;
    btn.onclick = () => {
      const nameEl = document.getElementById("opening-name-input");
      if (nameEl) nameEl.value = s.nom || `1.${s.san}`;
    };
    listEl.appendChild(btn);
  });
}

function openingCommenterChaqueCoup() {
  const cb = document.getElementById("shared-auto-comment");
  return !!(cb && cb.checked);
}

// PGN de la partie d'ouverture en cours, avec en-têtes (issue #52, "Analyser
// cette partie" après abandon — mêmes principes que
// _pedagogicGamePgnForAnalysis dans pedagogic.js).
function _openingGamePgnForAnalysis() {
  if (!openingGame) return "";
  const white = openingCampAlain === "noirs" ? "Adversaire" : "Alain";
  const black = openingCampAlain === "noirs" ? "Alain" : "Adversaire";
  openingGame.header("White", white, "Black", black);
  return openingGame.pgn();
}

// Issue #52 : "Abandonner" ne remet plus le plateau à zéro — la partie
// atteinte reste affichée (plateau, historique, bannière de défaite comme
// pour un mat), coups suivants bloqués via openingGameOver (déjà lu par
// onOpeningBoardClick). Le plateau ne redevient vierge qu'au démarrage
// explicite d'une nouvelle partie ou à un changement de mode.
function abandonOpeningGame() {
  if (!openingActive || openingGameOver) return;
  socket.emit("opening_abandon", {});
  openingGameOver  = true;
  openingAbandonne = true;
  openingWaiting   = false;
  openingSelected  = null;
  openingFenAvantCoup    = null;
  openingInBookAvantCoup = false;
  const statusEl = document.getElementById("opening-status");
  if (statusEl) statusEl.textContent = "Partie abandonnée — défaite.";
  const opposant = openingCampAlain === "noirs" ? "blancs" : "noirs";
  showGameOverBanner(
    { gagnant: opposant, message: "Partie abandonnée par Alain — défaite." },
    openingCampAlain,
    () => analyserPartieDepuisPgn(_openingGamePgnForAnalysis())
  );
}

function reprendreOpeningCoup() {
  const statusEl = document.getElementById("opening-status");
  if (!openingActive || openingWaiting || !openingFenAvantCoup) {
    if (statusEl && openingActive && !openingWaiting) statusEl.textContent = "Aucun coup à reprendre.";
    return;
  }
  openingGame      = new Chess(openingFenAvantCoup);
  openingGameOver  = false;
  openingSelected  = null;
  openingInBook    = openingInBookAvantCoup;
  openingFenAvantCoup = null;
  hideGameOverBanner();
  socket.emit("opening_undo", { in_book: openingInBookAvantCoup });
  renderOpeningBoard();
  updateOpeningStatus();
}

function askOpeningCoach() {
  if (!openingActive || !openingGame || openingGameOver || openingWaiting) return;
  askCoachOnDemand(openingGame.fen(), null, openingCampAlain);
}

function startOpeningGame(camp) {
  const nameEl = document.getElementById("opening-name-input");
  const openingName = nameEl ? nameEl.value.trim() : "";
  if (!openingName) {
    const statusEl = document.getElementById("opening-status");
    if (statusEl) statusEl.textContent = "Indiquez le nom d'une ouverture.";
    return;
  }
  ensureModeSwitchClean("opening");
  hideGameOverBanner();
  openingCampAlain = (camp === "noirs") ? "noirs" : "blancs";
  openingWaiting   = true;
  openingGameOver  = false;
  openingAbandonne = false;
  openingFenAvantCoup    = null;
  openingInBookAvantCoup = false;
  const statusEl = document.getElementById("opening-status");
  if (statusEl) statusEl.textContent = `Recherche de la théorie pour "${openingName}"...`;
  socket.emit("opening_start", { camp: openingCampAlain, opening_name: openingName });
}

function renderOpeningBoard(lastFrom, lastTo) {
  if (!openingGame) return;
  const fenBoard = openingGame.fen().split(" ")[0];
  const from = lastFrom ? freeAlgebraicToSquareId(lastFrom) : null;
  const to   = lastTo   ? freeAlgebraicToSquareId(lastTo)   : null;
  renderBoard(fenBoard, from, to, null, null, null, null);
  if (openingSelected) {
    const sq = document.getElementById(`sq-${freeAlgebraicToSquareId(openingSelected)}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  renderHistory();
}

function updateOpeningStatus() {
  const statusEl = document.getElementById("opening-status");
  if (!statusEl || !openingGame) return;
  let text = openingGame.turn() === "w" ? "Trait aux Blancs" : "Trait aux Noirs";
  if (openingGame.in_checkmate())      text = "Échec et mat.";
  else if (openingGame.in_stalemate()) text = "Pat.";
  else if (openingGame.in_draw())      text = "Partie nulle.";
  else if (openingGame.in_check())     text += " (échec)";
  text += openingInBook ? " — dans le livre" : " — hors du livre (Stockfish affaibli)";
  if (openingWaiting) text += " — le coach réfléchit...";
  statusEl.textContent = text;
}

function openingIsAlainTurn() {
  if (!openingGame) return false;
  const trait = openingGame.turn() === "w" ? "blancs" : "noirs";
  return trait === openingCampAlain;
}

function onOpeningBoardClick(e) {
  if (!openingActive || !openingGame || openingWaiting || openingGameOver) return;
  if (!openingIsAlainTurn()) return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const square = freeSquareIdToAlgebraic(sqEl.id.replace("sq-", ""));

  if (!openingSelected) {
    const piece = openingGame.get(square);
    if (piece && piece.color === openingGame.turn()) {
      openingSelected = square;
      renderOpeningBoard();
    }
    return;
  }

  if (openingSelected === square) {
    openingSelected = null;
    renderOpeningBoard();
    return;
  }

  const fenAvant = openingGame.fen();
  const move = openingGame.move({ from: openingSelected, to: square, promotion: "q" });
  openingSelected = null;

  if (!move) {
    const piece = openingGame.get(square);
    if (piece && piece.color === openingGame.turn()) {
      openingSelected = square;
    }
    renderOpeningBoard();
    return;
  }

  renderOpeningBoard(move.from, move.to);
  openingWaiting = true;
  openingFenAvantCoup    = fenAvant;
  openingInBookAvantCoup = openingInBook;
  updateOpeningStatus();
  _coachRenderBubble("user", `Travail d'ouverture — je joue ${move.san}`);
  socket.emit("opening_move", {
    fen_avant: fenAvant,
    uci: move.from + move.to + (move.promotion || ""),
    commenter: openingCommenterChaqueCoup(),
  });
}

if (typeof socket !== "undefined") {
  socket.on("opening_suggestions_response", (data) => {
    renderOpeningSuggestions((data && data.suggestions) || []);
  });

  socket.on("opening_started", (data) => {
    if (!data || !data.fen) return;
    openingGame      = new Chess(data.fen);
    openingActive    = true;
    openingWaiting   = false;
    openingSelected  = null;
    openingGameOver  = false;
    openingAbandonne = false;
    openingCampAlain = data.camp_alain === "noirs" ? "noirs" : "blancs";
    openingInBook    = !!data.in_book;
    setActiveMode("opening");

    _boardFlipped = (openingCampAlain === "noirs");
    buildBoard();
    const boardEl = document.getElementById("board");
    if (boardEl) boardEl.onclick = onOpeningBoardClick;

    let lastFrom = null, lastTo = null;
    if (data.coup_ouverture) {
      lastFrom = data.coup_ouverture.slice(0, 2);
      lastTo   = data.coup_ouverture.slice(2, 4);
    }
    renderOpeningBoard(lastFrom, lastTo);
    updateOpeningStatus();

    const moves = (data.moves_ouverture || []).join(" ");
    _coachRenderBubble("assistant", `Ouverture "${data.opening_name}" : ${moves}. À vous de jouer.`);
  });

  socket.on("opening_stockfish_move", (data) => {
    openingWaiting = false;
    if (!openingActive || !openingGame || !data) return;
    openingInBook = !!data.in_book;

    if (data.uci) {
      const move = openingGame.move({
        from: data.uci.slice(0, 2),
        to: data.uci.slice(2, 4),
        promotion: data.uci.slice(4, 5) || "q",
      });
      if (move) {
        renderOpeningBoard(move.from, move.to);
      }
    }
    if (data.game_over) {
      openingGameOver = true;
      const statusEl = document.getElementById("opening-status");
      if (statusEl) statusEl.textContent = (data.game_over_info && data.game_over_info.message) || "Partie terminée.";
      showGameOverBanner(data.game_over_info, openingCampAlain);
      return;
    }
    updateOpeningStatus();
  });

  socket.on("opening_comment", (data) => {
    let text = stripMarkdownForChat((data && data.text) || "");
    if (data && data.dans_le_livre && data.popularite_pct !== null && data.popularite_pct !== undefined) {
      text += `\n\n(Popularité dans le livre : ${data.popularite_pct}%)`;
    } else if (data && !data.dans_le_livre && data.coup_livre_recommande) {
      text += `\n\n(Coup le plus joué du livre : ${data.coup_livre_recommande})`;
    }
    if (text) _coachRenderBubble("assistant", text);
  });

  socket.on("opening_error", (data) => {
    openingWaiting = false;
    const err = data && data.error;
    if (err === "credit_insuffisant") {
      if (typeof _coachRenderCreditInsuffisant === "function") _coachRenderCreditInsuffisant();
      console.warn("[travail d'ouverture]", "credit_insuffisant", data);
      return;
    }
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : (err === "livre_indisponible")
      ? "Livre d'ouvertures introuvable (data/books/gm2001.bin manquant)."
      : (err === "nom_ouverture_manquant")
      ? "Indiquez le nom d'une ouverture."
      : (err === "ouverture_non_reconnue")
      ? "Ouverture non reconnue par le coach — vérifiez l'orthographe ou essayez un nom plus standard."
      : (err === "sequence_invalide")
      ? "La séquence de coups proposée par le coach pour cette ouverture est invalide."
      : (err === "no_api_key")
      ? "Clé API Claude manquante — configurez-la dans les paramètres."
      : (err === "coup_illegal")
      ? "Coup illégal détecté côté serveur."
      : "Le coach n'a pas pu répondre, réessayez.";
    const statusEl = document.getElementById("opening-status");
    if (statusEl) statusEl.textContent = msg;
    console.warn("[travail d'ouverture]", msg, data);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof socket !== "undefined") socket.emit("opening_suggestions", {});
});
