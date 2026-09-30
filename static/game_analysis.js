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
 */

let _gameAnalysisBusy = false;
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
  // Indicateur d'attente sans compteur (issue #70 point 4) — no-op hors mode
  // jeu mobile (classe absente, cf. <style>/mobile_game.js).
  const progress = document.getElementById("game-analysis-progress");
  if (progress) progress.classList.add("show");
  const status = document.getElementById("game-analysis-status");
  if (status) status.textContent = "Analyse Stockfish en cours (peut prendre une minute)...";
  const coachStatus = document.getElementById("game-analysis-coach-status");
  if (coachStatus) coachStatus.textContent = "";
  const report = document.getElementById("game-analysis-report");
  if (report) report.innerHTML = "";
  _gameAnalysisResults = [];
  _coachChoixParIdx = {};
  _coachExplicationsParIdx = {};
  _coachExplicationEnCours = {};

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

// Point 4 : point d'entrée depuis la fin d'une partie pédagogique/libre/
// ouverture/finale — bascule vers l'onglet Bibliothèque/Revue avec la partie
// qui vient de se dérouler déjà chargée (parsePgn, board.js), puis lance
// l'analyse automatiquement (issue #59 : un seul clic depuis la bannière de
// fin de partie, plutôt que de contraindre l'utilisateur à recliquer sur le
// bouton de l'onglet, en particulier sur GSM où il est placé sous la liste
// des parties importées, cf. _lancerAnalyseAutoDepuisBanniere ci-dessous).
function analyserPartieDepuisPgn(pgnText) {
  if (!pgnText) return;
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

if (typeof socket !== "undefined") {
  socket.on("analyser_pgn_response", (data) => {
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const progress = document.getElementById("game-analysis-progress");
    if (progress) progress.classList.remove("show");
    const status = document.getElementById("game-analysis-status");
    if (!data || !data.moves) {
      if (status) status.textContent = "L'analyse a échoué.";
      if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
      return;
    }
    // Fusionne qualite/delta_cp/best_move dans reviewMoves (même ordre que
    // les coups envoyés) pour réutiliser directement les badges existants de
    // la revue (renderHistory/renderReview/showReviewBestMove, board.js).
    // _gameAnalysisResults garde le rapport complet (fen_avant/phase inclus)
    // pour le module d'explications narratives (issue #42).
    data.moves.forEach((m, i) => {
      if (!reviewMoves[i]) return;
      reviewMoves[i].qualite   = m.qualite;
      reviewMoves[i].delta_cp  = m.delta_cp;
      reviewMoves[i].best_move = m.best_move;
    });
    _gameAnalysisResults = data.moves;
    _isAnalysed = true;
    renderGameAnalysisReport();
    renderReview();
    if (status) status.textContent = `Analyse terminée (${data.moves.length} coups examinés).`;
    if (typeof _gameTabMarkNovelty === "function") _gameTabMarkNovelty("analyse");
    demanderExplicationsCoach();
    // Analyse lancée depuis la bannière de fin de partie (issue #59) : le
    // rapport vient de grandir (liste des coups flagués), on refait défiler
    // pour le ramener en vue une fois qu'il a vraiment quelque chose à
    // montrer, plutôt que de se fier au seul défilement fait au lancement.
    if (_gameAnalysisScrollApresResultat) { _gameAnalysisScrollApresResultat = false; _scrollVersPanneauAnalyse(); }
  });

  socket.on("analyser_pgn_error", (data) => {
    _gameAnalysisBusy = false;
    const btn = document.getElementById("game-analysis-btn");
    if (btn) btn.disabled = false;
    const progress = document.getElementById("game-analysis-progress");
    if (progress) progress.classList.remove("show");
    const status = document.getElementById("game-analysis-status");
    const err = data && data.error;
    const msg = (err === "stockfish_indisponible")
      ? "Stockfish indisponible sur ce système."
      : "L'analyse a échoué.";
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
