/*
 * game_analysis.js — ChessCoach (issues #41/#42/#59/#62)
 *
 * Bouton "Analyser cette partie" du panneau Bibliothèque/Revue PGN : lance
 * une analyse Stockfish synchrone (un aller-retour SocketIO, "analyser_pgn"
 * côté serveur, déjà émis par lancerAnalyse() dans board.js) sur la partie
 * actuellement chargée en revue (reviewFens/reviewMoves, board.js), affiche
 * un rapport des coups classés par gravité de perte d'évaluation (2-3 pires
 * mis en avant), et enrichit reviewMoves avec qualite/delta_cp/best_move
 * pour que les badges déjà existants de la revue (renderHistory/
 * renderReview/showReviewBestMove, board.js) s'affichent directement.
 * Purement mécanique côté rapport (delta_cp/qualite/numéro de coup) — aucun
 * changement à ce calcul ici (issue #41, hors périmètre de l'issue #42).
 *
 * Cliquer sur un coup du rapport recharge la position juste avant ce coup
 * dans le mode "partie libre" (startFreeGameFromFen, free_play.js) pour
 * l'explorer librement — "Coup Stockfish" et "Demander l'avis du coach" y
 * restent disponibles, sans construire de nouveau mode dédié.
 *
 * Point d'entrée depuis la fin d'une partie pédagogique/libre/ouverture/
 * finale : analyserPartieDepuisPgn(), appelée par le bouton de la bannière de
 * fin de partie (board.js showGameOverBanner, câblé dans pedagogic.js/
 * free_play.js/opening.js/finales.js). Contrairement au bouton de l'onglet
 * (un clic = un lancement), ce point d'entrée lance l'analyse automatiquement
 * dès la partie chargée en revue, sans second clic — ou réaffiche le rapport
 * déjà en mémoire si cette même partie vient d'être analysée cette session
 * (issue #59, cf. _lancerAnalyseAutoDepuisBanniere plus bas).
 *
 * Explications narratives du coach (issue #42) : une fois le rapport
 * mécanique généré, un seul appel dédié ("analyse_choisir_coups_decisifs")
 * transmet la liste complète des coups flagués au coach, qui choisit jusqu'à
 * 5 coups qu'il juge réellement décisifs (pas forcément les plus gros
 * delta_cp) et fournit une explication en langage naturel pour chacun —
 * affichées directement à côté du coup dans le rapport. Les coups flagués
 * non retenus gardent un bouton "Expliquer ce coup" à la demande
 * ("analyse_expliquer_coup", un appel par clic, pas d'appel automatique).
 *
 * Réfutation calculée (issue #62) : chaque coup transmis au serveur pour
 * une explication (en lot ou à la demande) porte aussi "uci_suivant", le
 * coup suivant réellement joué dans la partie (uci du demi-coup d'après
 * dans _gameAnalysisResults) — le serveur en déduit mécaniquement la
 * conséquence matérielle réelle de ce coup flagué (capture, perte nette,
 * reprise possible), pour que le coach l'explique au lieu de la deviner.
 *
 * Analyse "en place", sans quitter l'écran de partie (issue #72) : pour une
 * partie jouée dans un des 4 modes de partie (libre/pédagogique/ouverture/
 * finale) affichée dans l'écran de jeu mobile (isGameUiActive(),
 * mobile_game.js), l'analyse porte sur les coups réels de ce mode
 * (getActiveModeMoves(), controls.js) au lieu de reviewMoves, et le rapport
 * s'affiche dans l'onglet Analyse déjà en place (switchGameTab) — sans
 * jamais appeler switchModeTab("library")/parsePgn (qui rechargeraient la
 * partie en revue de bibliothèque, remettraient activeMode à null et
 * effaceraient le plateau/l'historique/le bandeau réels du mode en cours).
 * _gameAnalysisEnPlace mémorise, pour la réponse du serveur qui arrive de
 * façon asynchrone, si CETTE analyse a été lancée ainsi — pour ne surtout
 * pas laisser cette réponse muter reviewMoves/appeler renderReview() (qui
 * écraserait le plateau réel avec la position, possiblement obsolète, de la
 * dernière revue de bibliothèque). Hors de ce contexte (grand écran, ou
 * Bibliothèque/Revue PGN elle-même), comportement existant intégralement
 * conservé.
 */

let _gameAnalysisBusy = false;
// Relance automatique unique en cas d'absence de réponse du serveur (issue
// #77 point 1 — "moteur occupé" ou délai dépassé, pistes avancées pour
// l'échec ponctuel signalé par Alain) : _gameAnalysisTimeoutId arme un délai
// à chaque émission de "analyser_pgn", annulé dès qu'une réponse ("analyser_
// pgn_response" ou "analyser_pgn_error") arrive. S'il expire une première
// fois, la même demande est réémise automatiquement (_gameAnalysisRetried
// passe à true) ; s'il expire une seconde fois, on abandonne avec un message
// explicite plutôt que de relancer indéfiniment.
let _gameAnalysisTimeoutId = null;
let _gameAnalysisRetried = false;
const GAME_ANALYSIS_TIMEOUT_MS = 75000;
// Rapport mécanique complet (san/uci/color/coup_plein/delta_cp/qualite/
// best_move/fen_avant/phase), indexé comme reviewMoves — conservé à part de
// reviewMoves pour ne pas alourdir les autres consommateurs de reviewMoves
// (renderReview, badges) avec des champs qu'ils n'utilisent pas.
let _gameAnalysisResults = [];
// idx (position du coup dans _gameAnalysisResults, PAS uci) -> explication
// choisie par le coach à l'étape 1 (issue #42 point 1). Indexé par idx et
// non par uci : un même uci/san peut réapparaître plusieurs fois dans une
// partie (ex. échecs répétés par va-et-vient d'une tour, constaté en
// vérification réelle) — indexer par uci ferait apparaître la même
// explication sur plusieurs coups distincts qui partagent cet uci.
let _coachChoixParIdx = {};
// idx -> explication obtenue à la demande via "Expliquer ce coup" (point 2).
let _coachExplicationsParIdx = {};
// idx en cours de chargement (bouton "Expliquer ce coup" cliqué, réponse pas
// encore arrivée) — évite les doubles clics sur le même coup.
let _coachExplicationEnCours = {};
// true si _gameAnalysisResults provient d'une analyse "en place" (issue #72,
// partie en cours dans l'écran de jeu mobile) plutôt que de la revue de
// bibliothèque — décide, à la réponse du serveur, si reviewMoves/renderReview()
// doivent être touchés (jamais en place) ou pas.
let _gameAnalysisEnPlace = false;
// idx (dans _gameAnalysisResults) du coup flagué actuellement prévisualisé
// sur le plateau réel d'une partie en cours (explorerCoupFlagge, issue #72
// point 2), ou null — cf. _updateBoardLinesCommandBar (game_coach_lines.js),
// qui affiche le bouton de retour correspondant.
let _gameAnalysisFlaggedPreviewIdx = null;

// Vide l'affichage du rapport SANS toucher au cache (_gameAnalysisResults et
// co.) — appelée depuis des points de coupure qui n'invalident pas
// forcément l'analyse en mémoire (changement de mode, chargement d'une autre
// partie, qui peut être réanalysée depuis ce cache sans redemander Stockfish,
// issue #59) mais où le rapport affiché à l'écran ne doit plus rester visible
// tel quel (issue #71 point 6). analyserPartieCourante() ci-dessous continue
// de vider aussi le cache, à part, pour le cas où elle démarre elle-même une
// analyse neuve.
function _clearGameAnalysisDisplay() {
  const list = document.getElementById("game-analysis-report");
  if (list) list.innerHTML = "";
  const status = document.getElementById("game-analysis-status");
  if (status) status.textContent = "";
  const coachStatus = document.getElementById("game-analysis-coach-status");
  if (coachStatus) coachStatus.textContent = "";
  const progress = document.getElementById("game-analysis-progress");
  if (progress) progress.classList.remove("show");
}

// Coups de la partie en cours d'un des 4 modes de partie, affichée dans
// l'écran de jeu mobile (issue #72) — null hors de ce contexte (grand écran,
// Bibliothèque/Revue PGN), pour retomber sur reviewMoves comme avant.
function _gameAnalysisLiveMoves() {
  if (typeof isGameUiActive !== "function" || !isGameUiActive()) return null;
  if (typeof getActiveModeMoves !== "function") return [];
  return getActiveModeMoves() || [];
}

// PGN de la partie actuellement en cours dans le mode actif, via la fonction
// dédiée de chaque mode (_xxxGamePgnForAnalysis) déjà utilisée par le
// bandeau de fin de partie (pedagogic.js/free_play.js/opening.js/finales.js)
// — pour disposer des en-têtes White/Black "Alain" vs "Stockfish"/
// "Adversaire" (issue #56) même quand l'analyse est lancée directement
// depuis le bouton de l'onglet Analyse plutôt que depuis le bandeau.
function _gameAnalysisPgnForActiveMode() {
  const mode = typeof activeMode !== "undefined" ? activeMode : null;
  if (mode === "free"      && typeof _freeGamePgnForAnalysis      === "function") return _freeGamePgnForAnalysis();
  if (mode === "pedagogic" && typeof _pedagogicGamePgnForAnalysis === "function") return _pedagogicGamePgnForAnalysis();
  if (mode === "opening"   && typeof _openingGamePgnForAnalysis   === "function") return _openingGamePgnForAnalysis();
  if (mode === "finale"    && typeof _finaleGamePgnForAnalysis    === "function") return _finaleGamePgnForAnalysis();
  return null;
}

// Extrait White/Black d'un texte PGN dans reviewWhite/reviewBlack SANS les
// autres effets de parsePgn (board.js) — reviewFens/reviewMoves/reviewIdx,
// activeMode, plateau : aucun ne doit changer pendant une analyse en place
// (issue #72). reviewWhite/reviewBlack ne servent qu'à la déduction du camp
// d'Alain côté serveur (demanderExplicationsCoach/demanderExplicationCoup
// ci-dessous) — jamais affichés, donc sans risque à réutiliser ainsi.
function _appliquerEntetesPgn(pgnText) {
  if (!pgnText) return;
  try {
    const chess = new Chess();
    if (!chess.load_pgn(pgnText)) return;
    const h = chess.header();
    reviewWhite = h.White || "";
    reviewBlack = h.Black || "";
  } catch (e) { /* ignore */ }
}

// Disponibilité du bouton "Analyser cette partie" sur l'onglet Analyse mobile
// (issue #81 point 3) — repéré vide/silencieux lors du test GSM tant qu'on
// n'avait pas encore cliqué dessus. "En place" (un des 4 modes de partie
// affichés dans l'écran de jeu mobile, _gameAnalysisLiveMoves() non nul) :
// grisé + phrase d'explication tant que la partie n'est pas terminée
// (analyser un rapport partiel n'a pas de sens) ; hors de ce contexte
// (Bibliothèque/Revue PGN, grand écran ou mobile), une partie chargée en
// revue est par définition terminée — toujours disponible, comportement
// inchangé. Appelée depuis onGameUiRefresh (mobile_game.js), à chaque
// changement d'onglet/mode et après chaque coup/fin de partie.
function _updateGameAnalysisAvailability() {
  const btn = document.getElementById("game-analysis-btn");
  const help = document.getElementById("game-analysis-help");
  const status = document.getElementById("game-analysis-status");
  if (!btn || !help) return;
  if (_gameAnalysisBusy) return; // analyserPartieCourante gère déjà disabled/status pendant l'analyse elle-même.
  const enPlace = _gameAnalysisLiveMoves() !== null;
  const running = enPlace && typeof _isCurrentGameRunning === "function" && _isCurrentGameRunning();
  btn.disabled = running;
  help.textContent = running ? "Disponible quand la partie est terminée." : "";
  if (status && !_gameAnalysisResults.length) {
    status.textContent = "Analyse non lancée.";
  }
}

function analyserPartieCourante() {
  const liveMoves = _gameAnalysisLiveMoves();
  const enPlace = liveMoves !== null;
  // Ouvre l'onglet Analyse même si l'analyse ne démarre pas encore (déjà en
  // cours, ou résultat en cache réaffiché juste après par l'appelant) — le
  // bouton de l'onglet et celui du bandeau de fin de partie doivent tous les
  // deux y amener (issue #72 point 1).
  if (enPlace && typeof switchGameTab === "function") switchGameTab("analyse");
  if (_gameAnalysisBusy) return;
  // Une nouvelle analyse invalide toute prévisualisation de coup flagué en
  // cours (issue #72 point 2) — revient d'abord à la position réelle.
  if (_gameAnalysisFlaggedPreviewIdx !== null && typeof gameAnalysisReturnToPartie === "function") {
    gameAnalysisReturnToPartie();
  }
  const moves = enPlace ? liveMoves : reviewMoves;
  if (!moves.length) {
    const status = document.getElementById("game-analysis-status");
    if (status) {
      status.textContent = enPlace
        ? "Aucun coup n'a encore été joué dans cette partie."
        : "Chargez d'abord une partie à analyser.";
    }
    return;
  }
  _gameAnalysisEnPlace = enPlace;
  _gameAnalysisBusy = true;
  const btn = document.getElementById("game-analysis-btn");
  if (btn) btn.disabled = true;
  // Indicateur d'attente sans compteur (issue #70 point 4) — no-op hors mode
  // jeu mobile (classe absente, cf. <style>/mobile_game.js).
  const progress = document.getElementById("game-analysis-progress");
  if (progress) progress.classList.add("show");
  const status = document.getElementById("game-analysis-status");
  if (status) status.textContent = "Analyse en cours (Stockfish, peut prendre une minute)...";
  const coachStatus = document.getElementById("game-analysis-coach-status");
  if (coachStatus) coachStatus.textContent = "";
  const report = document.getElementById("game-analysis-report");
  if (report) report.innerHTML = "";
  _gameAnalysisResults = [];
  _coachChoixParIdx = {};
  _coachExplicationsParIdx = {};
  _coachExplicationEnCours = {};

  if (enPlace) _appliquerEntetesPgn(_gameAnalysisPgnForActiveMode());

  // startFen (issue #77) : position de départ réelle de la partie si elle
  // n'est pas standard (ex. mode pédagogique avec Alain aux Noirs, où
  // Stockfish a déjà joué un coup, ou travail de finales) — sans elle, le
  // serveur rejouait toujours les coups depuis la position standard et
  // l'analyse échouait systématiquement ("Coup illégal") dès le premier demi-
  // coup. modeLabel : journalisation diagnostique uniquement côté serveur.
  const startFen  = enPlace
    ? (typeof getActiveModeStartFen === "function" ? getActiveModeStartFen() : null)
    : reviewStartFen;
  const modeLabel = enPlace ? (typeof activeMode !== "undefined" ? activeMode : "partie") : "revue";

  _gameAnalysisRetried = false;
  _lancerAnalyseAvecRelance(moves.map(m => m.uci), startFen, modeLabel);
}

function _annulerDelaiAnalyse() {
  if (_gameAnalysisTimeoutId !== null) {
    clearTimeout(_gameAnalysisTimeoutId);
    _gameAnalysisTimeoutId = null;
  }
}

// Émet "analyser_pgn" et arme le délai de relance (issue #77 point 1) —
// movesUci/startFen/modeLabel mémorisés en paramètres de la fonction plutôt
// que dans une variable globale, pour que la relance rejoue exactement la
// même demande même si une autre analyse a entre-temps changé l'état courant.
function _lancerAnalyseAvecRelance(movesUci, startFen, modeLabel) {
  _annulerDelaiAnalyse();
  lancerAnalyse(movesUci, undefined, startFen, modeLabel);
  _gameAnalysisTimeoutId = setTimeout(() => {
    _gameAnalysisTimeoutId = null;
    if (!_gameAnalysisRetried) {
      _gameAnalysisRetried = true;
      const status = document.getElementById("game-analysis-status");
      if (status) status.textContent = "Pas de réponse du moteur — nouvel essai...";
      _lancerAnalyseAvecRelance(movesUci, startFen, modeLabel);
      return;
    }
    // Deuxième délai dépassé : abandonne plutôt que de relancer indéfiniment.
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const progress = document.getElementById("game-analysis-progress");
    if (progress) progress.classList.remove("show");
    const status = document.getElementById("game-analysis-status");
    if (status) status.textContent = "L'analyse a échoué : le moteur n'a pas répondu (délai dépassé).";
    if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
  }, GAME_ANALYSIS_TIMEOUT_MS);
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
// (issue #41 point 2) — opère sur _gameAnalysisResults (rapport mécanique
// complet renvoyé par le serveur, cf. listener "analyser_pgn_response" plus
// bas), pour disposer aussi de coup_plein/fen_avant/phase sans les
// redemander au serveur. Ajoute, pour chaque coup flagué (issue #42) :
// l'explication du coach si ce coup fait partie de sa sélection (point 1)
// ou a déjà été expliqué à la demande (point 2), sinon un bouton "Expliquer
// ce coup".
function renderGameAnalysisReport() {
  const list = document.getElementById("game-analysis-report");
  if (!list) return;
  list.innerHTML = "";

  const flagged = _gameAnalysisResults
    // uci_suivant (issue #62) : le coup suivant réellement joué dans la
    // partie (uci du demi-coup d'après dans _gameAnalysisResults, null s'il
    // n'y en a pas) — transmis au serveur pour calculer mécaniquement la
    // réfutation réelle d'un coup flagué (game_facts.describe_reponse_suivante).
    .map((m, i) => ({ ...m, _idx: i, uci_suivant: (_gameAnalysisResults[i + 1] || {}).uci || null }))
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
    li.style.padding = "3px 4px";
    li.style.borderRadius = "3px";
    li.style.marginBottom = "4px";
    if (rank < 3) {
      li.style.background = "#fdecea";
      li.style.fontWeight = "bold";
    }

    const ligne = document.createElement("div");
    ligne.style.cursor = "pointer";
    const camp = m.color === "white" ? "Blancs" : "Noirs";
    const label = _gameAnalysisQualiteLabel(m.qualite);
    ligne.textContent = `${rank < 3 ? "🔥 " : ""}${m.coup_plein}. (${camp}) ${m.san} — ${label} (-${m.delta_cp}cp)`;
    ligne.onclick = () => explorerCoupFlagge(m._idx);
    li.appendChild(ligne);

    const explication = _coachChoixParIdx[m._idx] || _coachExplicationsParIdx[m._idx];
    if (explication) {
      const p = document.createElement("div");
      p.style.fontWeight = "normal";
      p.style.fontStyle = "italic";
      p.style.color = "#335";
      p.style.margin = "3px 0 0";
      p.textContent = `Coach : ${explication}`;
      li.appendChild(p);
    } else {
      const btn = document.createElement("button");
      const enCours = !!_coachExplicationEnCours[m._idx];
      btn.textContent = enCours ? "Chargement..." : "Expliquer ce coup";
      btn.disabled = enCours;
      btn.style.marginTop = "3px";
      btn.style.fontWeight = "normal";
      btn.style.fontSize = "0.78rem";
      btn.onclick = (evt) => {
        evt.stopPropagation();
        demanderExplicationCoup(m);
      };
      li.appendChild(btn);
    }

    list.appendChild(li);
  });
}

// Étape 1 (issue #42 point 1) : une fois le rapport mécanique généré, un
// seul appel dédié transmet la liste complète des coups flagués au coach,
// qui choisit jusqu'à 5 coups décisifs avec une explication chacun. "idx"
// (position du coup dans _gameAnalysisResults) accompagne chaque coup pour
// que le serveur/coach l'identifie sans ambiguïté (cf. _coachChoixParIdx).
function demanderExplicationsCoach() {
  const coachStatus = document.getElementById("game-analysis-coach-status");
  const flagged = _gameAnalysisResults
    // uci_suivant (issue #62) : voir renderGameAnalysisReport ci-dessus.
    .map((m, i) => ({ ...m, idx: i, uci_suivant: (_gameAnalysisResults[i + 1] || {}).uci || null }))
    .filter(m => m.qualite && m.qualite !== "bon");
  if (!flagged.length) {
    if (coachStatus) coachStatus.textContent = "";
    return;
  }
  if (coachStatus) coachStatus.textContent = "Le coach choisit les coups les plus décisifs...";
  // white/black (issue #56) : en-têtes PGN de la partie en revue (board.js
  // parsePgn), pour que le serveur déduise le camp d'Alain (pseudo
  // athanatos123 ou nom "Alain") — sans cette info, le coach ne sait pas qui
  // est Alain parmi "blancs"/"noirs" et peut attribuer à tort un coup de
  // l'adversaire à Alain.
  socket.emit("analyse_choisir_coups_decisifs", {
    moves: flagged, white: reviewWhite, black: reviewBlack,
  });
}

// Étape 2 (issue #42 point 2) : bouton "Expliquer ce coup" à la demande,
// pour un coup flagué non retenu par le coach à l'étape 1 — un appel par
// clic, pas d'appel automatique.
function demanderExplicationCoup(m) {
  if (_coachExplicationEnCours[m._idx]) return;
  _coachExplicationEnCours[m._idx] = true;
  renderGameAnalysisReport();
  socket.emit("analyse_expliquer_coup", {
    idx: m._idx,
    fen_avant: m.fen_avant,
    san: m.san,
    uci: m.uci,
    color: m.color,
    coup_plein: m.coup_plein,
    delta_cp: m.delta_cp,
    qualite: m.qualite,
    best_move: m.best_move,
    // uci_suivant (issue #62) : voir renderGameAnalysisReport ci-dessus.
    uci_suivant: m.uci_suivant,
    // white/black (issue #56) : mêmes en-têtes PGN que demanderExplicationsCoach()
    // ci-dessus, pour que le serveur déduise le camp d'Alain.
    white: reviewWhite,
    black: reviewBlack,
  });
}

// Point 3/point 2 (issue #72) : rejouer un coup flagué du rapport.
// - Partie en cours affichée dans l'écran de jeu mobile (_gameAnalysisEnPlace,
//   issue #72 point 2) : prévisualise la position AVANT ce coup directement
//   sur le plateau réel de la partie — sans changer de mode, sans le moindre
//   game.move()/socket.emit —, en réutilisant le même mécanisme de blocage/
//   retour que la lecture d'une ligne du coach (gameCoachLinesPreviewActive,
//   game_coach_lines.js, issue #68) : les clics du plateau des 4 modes de
//   partie sont déjà gardés par ce flag, et mobile_game.js suspend déjà sur
//   lui le rétrécissement du plateau au défilement. _updateBoardLinesCommandBar
//   (game_coach_lines.js) affiche le bouton "Revenir à la partie" dès que
//   _gameAnalysisFlaggedPreviewIdx n'est plus null.
// - Bibliothèque/Revue PGN (comportement existant, inchangé) : charge la
//   position (reviewFens[idx]) en mode "partie libre" explorable.
function explorerCoupFlagge(idx) {
  const m = _gameAnalysisResults[idx];
  if (_gameAnalysisEnPlace && m && m.fen_avant) {
    if (typeof gameLineStopPlayback === "function") gameLineStopPlayback();
    gameCoachLinesPreviewActive = true;
    _gameAnalysisFlaggedPreviewIdx = idx;
    renderBoard(m.fen_avant.split(" ")[0], null, null, null, null, null, null);
    if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();
    if (typeof _updateBoardCompactState === "function") _updateBoardCompactState();
    return;
  }
  const fen = reviewFens[idx];
  const rm  = reviewMoves[idx];
  if (!fen) return;
  switchModeTab("free");
  startFreeGameFromFen(fen);
  const status = document.getElementById("free-play-status");
  if (status && rm) {
    status.textContent = `Position avant ${rm.san} (coup flagué de l'analyse) — explorez librement.`;
  }
}

// Retour explicite à la position finale de la partie depuis la
// prévisualisation d'un coup flagué (issue #72 point 2) — ne modifie aucun
// état réel (aucun n'a été touché par explorerCoupFlagge ci-dessus), ne
// fait que redessiner le plateau réel du mode actif, comme gameLinesRestore()
// (game_coach_lines.js) pour la lecture des lignes du coach.
function gameAnalysisReturnToPartie() {
  _gameAnalysisFlaggedPreviewIdx = null;
  gameCoachLinesPreviewActive = false;
  if (typeof _gameLinesRerenderCurrentMode === "function") _gameLinesRerenderCurrentMode();
  if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();
  if (typeof _updateBoardCompactState === "function") _updateBoardCompactState();
}

// Point 4 : point d'entrée depuis la fin d'une partie pédagogique/libre/
// ouverture/finale.
// - Affichée dans l'écran de jeu mobile (isGameUiActive()) : analyse EN
//   PLACE (issue #72), sans changer d'onglet ni charger la partie en revue
//   de bibliothèque — _lancerAnalyseEnPlaceDepuisBanniere ci-dessous.
// - Sinon (grand écran ou déjà en Bibliothèque/Revue) : comportement
//   historique inchangé (issue #59) — bascule vers l'onglet Bibliothèque/
//   Revue avec la partie qui vient de se dérouler déjà chargée (parsePgn,
//   board.js), puis lance l'analyse automatiquement.
function analyserPartieDepuisPgn(pgnText) {
  if (!pgnText) return;
  if (typeof isGameUiActive === "function" && isGameUiActive()) {
    _lancerAnalyseEnPlaceDepuisBanniere();
    return;
  }
  switchModeTab("library");
  parsePgn(pgnText, (info) => {
    const label = document.getElementById("pgn-lib-loaded-label");
    if (label) label.textContent = `Chargée : ${info.white} vs ${info.black} — partie tout juste terminée.`;
    _lancerAnalyseAutoDepuisBanniere();
  });
}

// true entre le lancement d'une analyse déclenchée depuis la bannière de fin
// de partie et l'arrivée de son résultat (ou de son erreur) — sert
// uniquement à décider s'il faut faire défiler la zone d'analyse en vue une
// fois le rapport rendu (issue #59). Ne s'applique jamais à un clic manuel
// sur le bouton de l'onglet Bibliothèque/Revue (analyserPartieCourante seule,
// sans passer par ici), qui garde son comportement actuel sans défilement
// automatique.
let _gameAnalysisScrollApresResultat = false;

function _scrollVersPanneauAnalyse() {
  const panel = document.getElementById("game-analysis-panel");
  if (panel && typeof panel.scrollIntoView === "function") {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

// Lancement automatique de l'analyse depuis la bannière de fin de partie
// (issue #59) : si la partie qui vient d'être chargée correspond coup à coup
// (mêmes SAN, même ordre) au rapport déjà en mémoire (_gameAnalysisResults —
// une analyse "Analyser cette partie" menée plus tôt dans la session, quel
// que soit l'onglet actif depuis), réaffiche directement ce rapport sans
// relancer Stockfish ; sinon lance une analyse normale (analyserPartieCourante,
// qui affiche déjà l'état "en cours" et désactive le bouton pour empêcher un
// double lancement). Fait défiler la zone d'analyse en vue dans les deux cas
// — surtout utile en affichage mobile, où elle est placée sous la longue
// liste de parties importées.
function _lancerAnalyseAutoDepuisBanniere() {
  if (_gameAnalysisResults.length && _gameAnalysisResults.length === reviewMoves.length
      && reviewMoves.every((m, i) => m.san === _gameAnalysisResults[i].san)) {
    // Remis à false explicitement (issue #72) : _gameAnalysisResults en
    // cache peut provenir d'une analyse en place précédente qui correspond,
    // coup à coup, à la partie chargée ici en revue — explorerCoupFlagge()
    // doit alors bien recharger la position en mode "partie libre"
    // explorable (comportement de la revue), pas prévisualiser sur un
    // plateau de mode de partie qui n'est plus affiché.
    _gameAnalysisEnPlace = false;
    reviewMoves.forEach((m, i) => {
      const r = _gameAnalysisResults[i];
      m.qualite   = r.qualite;
      m.delta_cp  = r.delta_cp;
      m.best_move = r.best_move;
    });
    _isAnalysed = true;
    renderGameAnalysisReport();
    renderReview();
    const status = document.getElementById("game-analysis-status");
    if (status) {
      status.textContent = `Analyse déjà disponible (${_gameAnalysisResults.length} coups) — réalisée plus tôt dans la session.`;
    }
    _scrollVersPanneauAnalyse();
    return;
  }
  _gameAnalysisScrollApresResultat = true;
  analyserPartieCourante();
  _scrollVersPanneauAnalyse();
}

// Variante en place de _lancerAnalyseAutoDepuisBanniere ci-dessus (issue #72) :
// depuis la bannière de fin de partie d'un mode de partie affiché dans
// l'écran de jeu mobile — ouvre directement l'onglet Analyse (switchGameTab)
// et compare au cache sur les coups RÉELS du mode actif (getActiveModeMoves)
// plutôt que sur reviewMoves ; ne charge jamais la partie en revue de
// bibliothèque, ne touche jamais reviewFens/reviewMoves/activeMode/le
// plateau. Même comportement de cache/défilement que la variante historique.
function _lancerAnalyseEnPlaceDepuisBanniere() {
  if (typeof switchGameTab === "function") switchGameTab("analyse");
  const liveMoves = _gameAnalysisLiveMoves() || [];
  if (_gameAnalysisResults.length && liveMoves.length && _gameAnalysisResults.length === liveMoves.length
      && liveMoves.every((m, i) => m.san === _gameAnalysisResults[i].san)) {
    _gameAnalysisEnPlace = true;
    renderGameAnalysisReport();
    const status = document.getElementById("game-analysis-status");
    if (status) {
      status.textContent = `Analyse déjà disponible (${_gameAnalysisResults.length} coups) — réalisée plus tôt dans la session.`;
    }
    _scrollVersPanneauAnalyse();
    return;
  }
  _gameAnalysisScrollApresResultat = true;
  analyserPartieCourante();
  _scrollVersPanneauAnalyse();
}

if (typeof socket !== "undefined") {
  socket.on("analyser_pgn_response", (data) => {
    _annulerDelaiAnalyse();
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const progress = document.getElementById("game-analysis-progress");
    if (progress) progress.classList.remove("show");
    const status = document.getElementById("game-analysis-status");
    if (!data || !data.moves) {
      if (status) status.textContent = "L'analyse a échoué : réponse du serveur incomplète.";
      if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
      return;
    }
    _gameAnalysisResults = data.moves;
    if (_gameAnalysisEnPlace) {
      // Issue #72 : partie en cours affichée dans l'écran de jeu mobile — ne
      // touche NI reviewMoves/reviewFens (partie potentiellement différente,
      // chargée ou non en revue de bibliothèque) NI renderReview()/le
      // plateau, qui écraserait la position RÉELLE du mode en cours avec
      // celle, possiblement obsolète, de la dernière revue. Le rapport
      // (renderGameAnalysisReport) est autonome, lui — n'affiche que
      // _gameAnalysisResults.
      renderGameAnalysisReport();
    } else {
      // Comportement existant (Bibliothèque/Revue PGN), inchangé : fusionne
      // qualite/delta_cp/best_move dans reviewMoves (même ordre que les
      // coups envoyés) pour réutiliser directement les badges existants de
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
    }
    if (status) status.textContent = `Analyse terminée (${data.moves.length} coups examinés).`;
    if (typeof _gameTabMarkNovelty === "function") _gameTabMarkNovelty("analyse");
    demanderExplicationsCoach();
    // Analyse lancée depuis la bannière de fin de partie (issue #59) : le
    // rapport vient de grandir (liste des coups flagués), on refait défiler
    // pour le ramener en vue une fois qu'il a vraiment quelque chose à
    // montrer, plutôt que de se fier au seul défilement fait au lancement.
    if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
  });

  // Messages distincts par cause (issue #77 point 1) — auparavant un seul
  // "L'analyse a échoué." générique quelle que soit la cause réelle (déjà
  // journalisée côté serveur dans data/logs/analyse_erreurs.log, cf.
  // app.py/_log_analyse_erreur), ce qui rendait un futur échec impossible à
  // diagnostiquer depuis l'écran seul.
  const GAME_ANALYSIS_ERROR_MESSAGES = {
    stockfish_indisponible: "Stockfish indisponible sur ce système.",
    partie_vide:            "Aucun coup à analyser (partie vide).",
    partie_invalide:        "L'analyse a échoué : un coup de la partie n'a pas pu être rejoué (position de départ ou coups incohérents).",
    fen_invalide:           "L'analyse a échoué : position de départ de la partie invalide.",
    erreur_interne:         "L'analyse a échoué : erreur interne du serveur.",
  };

  socket.on("analyser_pgn_error", (data) => {
    _annulerDelaiAnalyse();
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const progress = document.getElementById("game-analysis-progress");
    if (progress) progress.classList.remove("show");
    const status = document.getElementById("game-analysis-status");
    const err = data && data.error;
    const msg = GAME_ANALYSIS_ERROR_MESSAGES[err] || "L'analyse a échoué (cause inconnue — voir la console).";
    if (status) status.textContent = msg;
    console.warn("[analyse de partie]", msg, data);
    if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
  });

  // Étape 1 (issue #42 point 1) : sélection des coups décisifs par le coach,
  // en un seul appel pour l'ensemble des coups flagués.
  socket.on("analyse_choix_coach_response", (data) => {
    const coachStatus = document.getElementById("game-analysis-coach-status");
    const choix = (data && data.choix) || [];
    _coachChoixParIdx = {};
    choix.forEach((c) => { _coachChoixParIdx[c.idx] = c.explication; });
    if (coachStatus) {
      coachStatus.textContent = choix.length
        ? `Le coach a mis en avant ${choix.length} coup(s) décisif(s) (voir ci-dessous).`
        : "Le coach n'a retenu aucun coup en particulier sur cette partie.";
    }
    renderGameAnalysisReport();
    if (typeof _gameTabMarkNovelty === "function") _gameTabMarkNovelty("analyse");
  });

  socket.on("analyse_choix_coach_error", (data) => {
    const coachStatus = document.getElementById("game-analysis-coach-status");
    const err = data && data.error;
    const msg = (err === "credit_insuffisant")
      ? "Crédit de l'API Claude épuisé — rechargez sur la Console (lien \"Coût API\" en haut de la page)."
      : "Sélection du coach indisponible.";
    if (coachStatus) coachStatus.textContent = msg;
    console.warn("[analyse de partie] sélection du coach échouée", data);
  });

  // Étape 2 (issue #42 point 2) : bouton "Expliquer ce coup" à la demande.
  socket.on("analyse_expliquer_coup_response", (data) => {
    const idx = data && data.idx;
    if (idx === undefined || idx === null) return;
    delete _coachExplicationEnCours[idx];
    _coachExplicationsParIdx[idx] = data.text;
    renderGameAnalysisReport();
  });

  socket.on("analyse_expliquer_coup_error", (data) => {
    const idx = data && data.idx;
    if (idx !== undefined && idx !== null) {
      delete _coachExplicationEnCours[idx];
      if (data && data.error === "credit_insuffisant") {
        _coachExplicationsParIdx[idx] = "Crédit de l'API Claude épuisé — rechargez sur la Console (lien \"Coût API\" en haut de la page).";
      }
    }
    console.warn("[analyse de partie] explication à la demande échouée", data);
    renderGameAnalysisReport();
  });
}
