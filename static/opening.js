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
let openingTheoryEndAnnounced = false; // message "Fin de la théorie" déjà affiché pour cette partie (issue #100, point 2)

// ── Liste déroulante des ouvertures (issue #95, point 4) ────────────────────
// Remplace la saisie libre du nom d'ouverture — même principe que
// finaleList/populateFinaleSelect (finales.js), peuplée depuis
// opening_book.get_known_openings() (app.py on_opening_list).
let openingList = []; // bibliothèque reçue du serveur (opening_list_response)

function populateOpeningSelect() {
  const selectEl = document.getElementById("opening-select");
  if (!selectEl) return;
  const previousValue = selectEl.value;
  selectEl.innerHTML = '<option value="">— Choisir une ouverture —</option>';
  openingList.forEach((nom) => {
    const opt = document.createElement("option");
    opt.value = nom;
    opt.textContent = nom;
    selectEl.appendChild(opt);
  });
  if (previousValue && openingList.includes(previousValue)) selectEl.value = previousValue;
}

// Sélectionne `nom` dans #opening-select, en ajoutant une option temporaire
// si absente de openingList (ex. suggestion rapide "1.Nf3" hors des familles
// nommées ci-dessous, cf. renderOpeningSuggestions) — plutôt que de l'ignorer
// silencieusement.
function _openingSelectSetValue(nom) {
  const selectEl = document.getElementById("opening-select");
  if (!selectEl || !nom) return;
  let opt = Array.from(selectEl.options).find((o) => o.value === nom);
  if (!opt) {
    opt = document.createElement("option");
    opt.value = nom;
    opt.textContent = nom;
    selectEl.appendChild(opt);
  }
  selectEl.value = nom;
}

if (typeof socket !== "undefined") {
  socket.on("opening_list_response", (data) => {
    openingList = (data && data.openings) || [];
    populateOpeningSelect();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof socket !== "undefined") socket.emit("opening_list", {});
});

// ── Boutons "Jouer les Blancs/Noirs" déplacés avant le plateau sur mobile
// (issue #70 point 4, généralise placePedagogicStartButtonsForViewport de
// pedagogic.js au mode ouverture — même choix de camp) ───────────────────
// Contrairement à pedagogic.js, en plus de "mobile + pas de partie en
// cours", ce déplacement exige aussi que l'onglet de mode affiché soit bien
// "opening" (currentModeTab, controls.js) : ces boutons ne doivent apparaître
// dans la bande avant-partie que lorsqu'on regarde vraiment ce mode.
let _openingStartHomeParent      = null;
let _openingStartHomeNextSibling = null;
const _openingMobileQuery = window.matchMedia("(max-width: 900px)");

function placeOpeningStartButtonsForViewport() {
  const btns = document.getElementById("opening-start-buttons");
  const slot = document.getElementById("mobile-opening-start-slot");
  if (!btns || !slot || !_openingStartHomeParent) return;
  const gameEnCours = openingActive && !openingGameOver;
  const onOpeningTab = typeof currentModeTab === "undefined" || currentModeTab === "opening";
  const showInSlot = _openingMobileQuery.matches && onOpeningTab && !gameEnCours;
  if (showInSlot) {
    if (btns.parentElement !== slot) slot.appendChild(btns);
  } else if (btns.parentElement !== _openingStartHomeParent) {
    _openingStartHomeParent.insertBefore(btns, _openingStartHomeNextSibling);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const btns = document.getElementById("opening-start-buttons");
  if (btns) {
    _openingStartHomeParent      = btns.parentElement;
    _openingStartHomeNextSibling = btns.nextSibling;
    placeOpeningStartButtonsForViewport();
  }
  _openingMobileQuery.addEventListener("change", () => placeOpeningStartButtonsForViewport());
});

// ── Suggestions rapides d'ouvertures populaires (issue #27) ────────────────
// Coups les plus pondérés du livre Polyglot gm2001.bin à la position de
// départ (opening_book.get_starting_suggestions côté serveur), en plus de la
// liste déroulante ci-dessus (issue #95, point 4 : remplace l'ancien champ
// texte libre). Un clic sélectionne l'ouverture correspondante dans
// #opening-select (_openingSelectSetValue, ajoute une option temporaire si
// besoin) — le nom reconnu (1.e4/1.d4/1.c4/1.Nf3) pour les quatre familles
// standards, sinon juste le coup lui-même — puis Alain clique "Jouer les
// Blancs/Noirs" comme pour un choix fait directement dans la liste : aucun
// nouveau chemin de démarrage de partie.
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
    btn.onclick = () => _openingSelectSetValue(s.nom || `1.${s.san}`);
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
    () => analyserPartieDepuisPgn(_openingGamePgnForAnalysis()),
    undefined,
    true
  );
  // Issue #65 point 5 : grise "Demander l'avis du coach" (askCoachAvailable,
  // controls.js) dès l'abandon.
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
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
  // Issue #65 point 5 : la partie redevient en cours — réactive "Demander
  // l'avis du coach".
  if (typeof updateSharedControlBar === "function") updateSharedControlBar();
  if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
}

function askOpeningCoach() {
  if (!openingActive || !openingGame || openingGameOver || openingWaiting) return;
  askCoachOnDemand(openingGame.fen(), null, openingCampAlain);
}

function startOpeningGame(camp) {
  const selectEl = document.getElementById("opening-select");
  const openingName = selectEl ? selectEl.value.trim() : "";
  if (!openingName) {
    const statusEl = document.getElementById("opening-status");
    if (statusEl) statusEl.textContent = "Choisissez une ouverture dans la liste.";
    return;
  }
  ensureModeSwitchClean("opening");
  // Nouvelle partie (issue #64) : l'historique du chat envoyé à l'API repart
  // de zéro, séparé à l'écran des échanges de la partie précédente.
  if (typeof coachNewSegment === "function") coachNewSegment("Nouvelle partie");
  // Issue #71 point 6 : le rapport d'analyse affiché (Bibliothèque/Revue)
  // n'a plus de rapport avec la partie qui démarre.
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  hideGameOverBanner();
  openingCampAlain = (camp === "noirs") ? "noirs" : "blancs";
  openingWaiting   = true;
  openingGameOver  = false;
  openingAbandonne = false;
  openingFenAvantCoup    = null;
  openingInBookAvantCoup = false;
  openingTheoryEndAnnounced = false;
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

// Fin de théorie (issue #100, point 2) : le livre d'ouvertures gm2001.bin ne
// connaît plus de coup pour la position atteinte (coup d'Alain absent des
// entrées du livre, ou plus aucune entrée du tout pour la position — y
// compris côté adversaire, qui bascule alors aussi sur Stockfish affaibli,
// cf. app.py on_opening_move) : message bref et unique, dans le chat du coach
// ET la ligne d'état, plutôt qu'un simple changement silencieux du suffixe
// "— dans/hors du livre" de updateOpeningStatus() (facile à manquer). Jamais
// répété pour la même partie (openingTheoryEndAnnounced, remis à faux
// uniquement au démarrage d'une nouvelle partie, startOpeningGame/
// opening_started) — y compris si la partie redevient "hors livre" plusieurs
// fois de suite (ne peut pas arriver, _opening_in_book ne repasse jamais à
// vrai côté serveur, mais la garde reste par prudence si ce invariant
// changeait). extraClass "coach-bubble-announce" (même mécanique que
// l'annonce de démarrage ci-dessus) : ce message vient de l'application, pas
// d'une question d'Alain, il ne doit donc jamais à lui seul déclencher le
// plateau réduit mobile.
const OPENING_THEORY_END_MESSAGE = "Fin de la théorie : le livre d'ouvertures ne connaît plus cette position, la partie continue contre le moteur.";

function _announceOpeningTheoryEnd() {
  if (openingTheoryEndAnnounced) return;
  openingTheoryEndAnnounced = true;
  _coachRenderBubble("assistant", OPENING_THEORY_END_MESSAGE, false, "coach-bubble-announce");
  const statusEl = document.getElementById("opening-status");
  if (statusEl) statusEl.textContent = OPENING_THEORY_END_MESSAGE;
}

function openingIsAlainTurn() {
  if (!openingGame) return false;
  const trait = openingGame.turn() === "w" ? "blancs" : "noirs";
  return trait === openingCampAlain;
}

function onOpeningBoardClick(e) {
  if (!openingActive || !openingGame || openingWaiting || openingGameOver) return;
  // Une ligne du coach est affichée sur le plateau (issue #68, avant/pendant/
  // après sa lecture) : coups bloqués jusqu'au retour explicite ("Revenir à
  // la partie").
  if (typeof gameCoachLinesPreviewActive !== "undefined" && gameCoachLinesPreviewActive) return;
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
  // Masqué dans le chat sur mobile (issue #69 point 3) — purement présentationnel,
  // cf. commentaire de _coachRenderBubble (board.js).
  _coachRenderBubble("user", `Travail d'ouverture — je joue ${move.san}`, false, "coach-bubble-auto-move");
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
    openingTheoryEndAnnounced = false;
    setActiveMode("opening");
    if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();

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
    // extraClass "coach-bubble-announce" (issue #95, point 5) : message
    // d'annonce envoyé par l'application au démarrage, pas une réponse à une
    // demande d'Alain — ne doit jamais à lui seul déclencher le plateau
    // réduit mobile (cf. _coachRenderBubble, board.js).
    _coachRenderBubble("assistant", `Ouverture "${data.opening_name}" : ${moves}. À vous de jouer.`, false, "coach-bubble-announce", null, { mode_origine: "ouverture" });
  });

  socket.on("opening_stockfish_move", (data) => {
    openingWaiting = false;
    if (!openingActive || !openingGame || !data) return;
    // Transition "dans le livre" -> "hors du livre" détectée ici (issue #100,
    // point 2) : wasInBook capturé AVANT d'écraser openingInBook avec la
    // nouvelle valeur reçue — couvre aussi bien un coup d'Alain absent du
    // livre (_opening_in_book basculé côté serveur avant l'éventuelle réponse
    // de l'adversaire) qu'une réponse d'adversaire introuvable dans le livre
    // pour une position où le coup d'Alain, lui, y figurait encore.
    const wasInBook = openingInBook;
    openingInBook = !!data.in_book;
    const sortieDeLivre = wasInBook && !openingInBook;

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
      if (typeof updateSharedControlBar === "function") updateSharedControlBar();
      if (typeof placeOpeningStartButtonsForViewport === "function") placeOpeningStartButtonsForViewport();
      // Peu probable (la partie se termine le même coup que la sortie du
      // livre) mais possible (ex. mat immédiat hors théorie) : le message de
      // fin de théorie reste pertinent même si la partie est déjà terminée.
      if (sortieDeLivre) _announceOpeningTheoryEnd();
      return;
    }
    updateOpeningStatus();
    if (sortieDeLivre) _announceOpeningTheoryEnd();
  });

  socket.on("opening_comment", (data) => {
    let text = stripMarkdownForChat((data && data.text) || "");
    if (data && data.dans_le_livre && data.popularite_pct !== null && data.popularite_pct !== undefined) {
      text += `\n\n(Popularité dans le livre : ${data.popularite_pct}%)`;
    } else if (data && !data.dans_le_livre && data.coup_livre_recommande) {
      text += `\n\n(Coup le plus joué du livre : ${data.coup_livre_recommande})`;
    }
    if (text) {
      _coachRenderBubble("assistant", text, false, undefined, data && data.fiabilite, data && {
        mode_origine: data.mode_origine, fen: data.fen, move: data.coup_propose, log_id: data.log_id,
      });
      // Tableau "Lignes du coach" (issue #68) : alimenté aussi par le
      // commentaire automatique après chaque coup ("Commenter chaque coup"),
      // pas seulement par le chat libre/la demande ponctuelle (board.js).
      if (typeof gameCoachLinesOnCoachText === "function") gameCoachLinesOnCoachText(text);
    }
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
