/*
 * controls.js — ChessCoach (issue #15)
 *
 * État centralisé du "mode actif" (aucun mode / partie libre / pédagogique /
 * ouverture / finale / exercice — un seul actif à la fois) et barre de
 * contrôle mutualisée qui agit dessus. Les boutons "Reprendre mon coup" /
 * "Abandonner" / "Demander l'avis du coach" et la case "Commenter chaque
 * coup", auparavant dupliqués dans chaque panneau (issue #10), redirigent
 * ici vers les fonctions déjà existantes de chaque mode
 * (abandon.../reprendre.../coachOnDemand des fichiers free_play.js/
 * pedagogic.js/opening.js/finales.js/exercise.js) plutôt que d'être récrites.
 *
 * Sert aussi de point d'accès unique à l'état du mode actif pour :
 *   - coachBuildContext() (board.js), pour que le chat libre du coach
 *     connaisse la position/le camp du mode en cours (issue #15 point 3) ;
 *   - renderHistory() (board.js), pour peupler l'historique des coups
 *     pendant une partie interactive plutôt que seulement en revue PGN
 *     (issue #15 point 4).
 *
 * Chargé en dernier (après tous les fichiers de mode) dans templates/
 * index.html — les fonctions ci-dessous ne sont invoquées qu'au clic, une
 * fois tous les scripts de la page chargés, mais le placement en fin de
 * liste garde la lecture du fichier simple.
 */

let activeMode = null; // null | "free" | "pedagogic" | "opening" | "finale" | "exercise" | "editor"

// askCoachAvailable (issue #65 point 5) : reflète au plus près la condition
// de garde de la fonction askCoach correspondante (askFreeCoach and co,
// fichiers de mode), pour que le bouton mutualisé "Demander l'avis du coach"
// soit désactivé et grisé (bouton HTML natif, cf. la règle générale
// "button:disabled { opacity:0.5 }") dès qu'un clic serait un no-op silencieux
// — le cas signalé par Alain (partie terminée ou abandonnée) mais aussi tant
// qu'aucune partie n'est démarrée. Simplification assumée : n'inclut pas les
// courtes fenêtres "*Waiting" (coup adverse en cours de traitement, ~1s) —
// cf. rapport de clôture, limite documentée plutôt que corrigée ici.
const MODE_CAPS = {
  free:      { abandon: () => abandonFreeGame(),         reprendre: null,                            askCoach: () => askFreeCoach(),       askCoachAvailable: () => freePlayActive && !!freeGame && !freeGameOver,           hasComment: false },
  // hasComment: false (issue #95, point 3) : la case "Commenter chaque coup"
  // est retirée du mode pédagogique — bouton "Commenter la partie" (fin de
  // partie) et "Demander l'avis du coach" (en cours) suffisent. Toujours
  // présente dans les modes opening/finale ci-dessous, hors périmètre de ce
  // point.
  pedagogic: { abandon: () => abandonPedagogicGame(),     reprendre: () => reprendrePedagogicCoup(),  askCoach: () => askPedagogicCoach(),  askCoachAvailable: () => pedagogicActive && !!pedagogicGame && !pedagogicGameOver, hasComment: false },
  opening:   { abandon: () => abandonOpeningGame(),       reprendre: () => reprendreOpeningCoup(),    askCoach: () => askOpeningCoach(),    askCoachAvailable: () => openingActive && !!openingGame && !openingGameOver,       hasComment: true  },
  finale:    { abandon: () => abandonFinaleGame(),        reprendre: () => reprendreFinaleCoup(),     askCoach: () => askFinaleCoach(),     askCoachAvailable: () => finaleActive && !!finaleGame && !finaleGameOver,          hasComment: true  },
  // askCoachAvailable (issue #79, point 4a) : exige désormais un verdict
  // déjà rendu pour la tentative en cours (exerciseVerdictObtenu), en plus
  // d'un exercice chargé — avant ce correctif, un contexte sans verdict
  // (ex. moteur en panne) pouvait quand même interroger le coach, qui
  // inventait alors un verdict faute d'en recevoir un réel (constat réel,
  // cf. rapport de clôture).
  exercise:  { abandon: null,                             reprendre: () => reprendreExerciceCoup(),   askCoach: () => askExerciseCoach(),   askCoachAvailable: () => !!exerciseGame && exerciseVerdictObtenu,                 hasComment: false },
  // Éditeur de position (issue #16) : pas de partie jouée, donc pas de
  // "reprendre mon coup" ni de coach à la demande — juste un moyen de
  // quitter le panneau via le bouton "Abandonner" mutualisé.
  editor:    { abandon: () => abandonPositionEditor(),    reprendre: null,                            askCoach: null,                       askCoachAvailable: null,                                                           hasComment: false },
};

// Phrase affichée sous les boutons du mode actif (issue #65 point 5) — ce
// que fait concrètement "Demander l'avis du coach" dans ce mode, pour qu'il
// ne reste plus un bouton "mystère" quand il est grisé. Même texte pour
// pedagogic/opening/finale (même mécanique : un commentaire ponctuel de la
// position, hors case "Commenter chaque coup").
const MODE_ASK_COACH_HELP = {
  free:      "Demande au coach un commentaire ponctuel sur la position affichée, sans jouer de coup à sa place.",
  pedagogic: "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  opening:   "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  finale:    "Demande un commentaire ponctuel sur la position actuelle — surtout utile si « Commenter chaque coup » est décoché.",
  exercise:  "Demande un commentaire du coach sur la position affichée, à tout moment de l'exercice (avant ou après le verdict).",
};

const MODE_LABELS = {
  free:      "Partie libre en cours.",
  pedagogic: "Partie pédagogique en cours.",
  opening:   "Travail d'ouverture en cours.",
  finale:    "Travail de finales en cours.",
  exercise:  "Exercice en cours.",
  editor:    "Éditeur de position actif.",
};

function setActiveMode(mode) {
  activeMode = mode;
  updateSharedControlBar();
  updateReviewControlsEnabled();
  renderHistory(reviewIdx);
  // Masque immédiatement le tableau "Lignes du coach" des modes de partie/
  // revue (issue #68) au passage vers exercice/éditeur, même si des lignes
  // restaient affichées d'un mode précédent pas encore réinitialisé.
  if (typeof renderGameCoachLinesTable === "function") renderGameCoachLinesTable();
  // Issue #79, point 4a : le champ de question/bouton "Envoyer" du chat
  // libre, désactivés pendant un exercice sans verdict, redeviennent
  // disponibles dès qu'on quitte le mode exercice vers un autre mode — sans
  // cet appel ici, quitter un exercice non répondu laissait le champ grisé
  // même dans un mode qui n'a pas cette restriction.
  if (typeof _exerciseUpdateCoachInputGating === "function") _exerciseUpdateCoachInputGating();
}

// ── Onglets par mode (issue #23) ────────────────────────────────────────────
// Remplace l'empilement vertical des panneaux spécifiques à chaque mode :
// un seul panneau de contrôles visible à la fois (celui de l'onglet cliqué).
// Naviguer entre onglets est de la pure consultation — ne passe jamais par
// ensureModeSwitchClean ci-dessous, qui ne s'exécute qu'au moment où un
// panneau démarre effectivement une nouvelle partie/exercice/revue.
const MODE_TABS = ["library", "free", "pedagogic", "opening", "finale", "exercise", "editor"];
let currentModeTab = "library";

function switchModeTab(tabKey) {
  if (MODE_TABS.indexOf(tabKey) === -1) return;
  // Issue #86 point 4 : la conversation du coach (affichage ET historique
  // envoyé à l'API, coachClear() — board.js) est propre à chaque mode. Avant
  // ce correctif, elle restait affichée en changeant de mode (partagée par
  // toute la page, cf. #coach-history) et ne se vidait qu'au prochain clic
  // sur "Effacer" ou au démarrage d'un nouvel exercice/d'une nouvelle partie
  // (coachNewSegment) — les messages d'un exercice restaient donc visibles en
  // lançant une Partie pédagogique, par exemple (rapport signalé par Alain).
  // Condition sur un VRAI changement (tabKey !== l'ancien currentModeTab) :
  // re-cliquer l'onglet déjà actif (ou le réappel via le menu déroulant
  // mobile) ne doit rien effacer tant qu'on reste dans le même mode.
  if (tabKey !== currentModeTab && typeof coachClear === "function") coachClear();
  currentModeTab = tabKey;
  // Issue #71 point 2 : remonter tout en haut à chaque changement de mode —
  // sans ça, la position de défilement laissée par le mode précédent reste
  // active et peut immédiatement déclencher l'état "plateau réduit" du
  // nouveau mode jeu (cf. _updateBoardCompactState, mobile_game.js) avant
  // même d'avoir vu une seule fois le plateau complet/les boutons de
  // démarrage. Immédiat (pas "smooth") : un changement de mode doit être
  // instantané, pas animé.
  if (typeof window.scrollTo === "function") window.scrollTo(0, 0);
  // Issue #71 point 6 : le rapport d'analyse affiché ne correspond plus au
  // nouvel onglet consulté (cf. _clearGameAnalysisDisplay, game_analysis.js
  // — ne touche que l'affichage, pas le cache utilisé par la réutilisation
  // automatique de l'issue #59).
  if (typeof _clearGameAnalysisDisplay === "function") _clearGameAnalysisDisplay();
  // Issue #77 point 3 : le bandeau de fin de partie (résultat + "Analyser
  // cette partie") n'a de sens que dans le mode de la partie qui vient de se
  // terminer (activeMode, posé au démarrage par setActiveMode — pas remis à
  // null par une fin de partie normale, cf. pedagogic.js/opening.js/
  // finales.js/free_play.js) — jusqu'ici rien ne le masquait en changeant
  // d'onglet, il restait visible en Bibliothèque/Revue PGN/Exercice/Éditeur
  // et dans les autres modes de partie (rapport signalé par Alain).
  if (activeMode && tabKey !== activeMode
      && document.body.classList.contains("game-over-active")
      && typeof hideGameOverBanner === "function") {
    hideGameOverBanner();
  }
  MODE_TABS.forEach((key) => {
    const btn   = document.getElementById(`tab-btn-${key}`);
    const panel = document.getElementById(`tab-panel-${key}`);
    const isActive = key === tabKey;
    if (btn)   btn.classList.toggle("active", isActive);
    if (panel) panel.classList.toggle("active", isActive);
  });
  // Barre du bas "Reprendre mon coup" / "Nouvel exercice" (issue #63,
  // disposition mobile du mode exercice) : visible uniquement sur cet
  // onglet, sans effet au-dessus de 900px (cf. media query, templates/
  // index.html) — ne duplique aucune logique, ses deux boutons appellent
  // sharedReprendreCoup()/openExercisePhaseSheet() (exercise.js).
  const mobileExerciseBar = document.getElementById("mobile-exercise-bar");
  if (mobileExerciseBar) mobileExerciseBar.classList.toggle("show", tabKey === "exercise");

  // Issue #70 : rafraîchit l'écran de partie mobile (mobile_game.js — plateau
  // fixe/onglets Coach-Lignes-Analyse-Coups pour free/pedagogic/opening/
  // finale) à chaque changement d'onglet de mode ; no-op si mobile_game.js
  // n'est pas chargé (aucune dépendance dure de ce fichier vers lui).
  if (typeof onGameUiRefresh === "function") onGameUiRefresh();
}

// ── Sélecteur de mode en menu déroulant sur mobile (issue #63) ─────────────
// Les boutons d'onglets existants (switchModeTab, ci-dessus) sont déplacés
// tels quels entre leur emplacement d'origine (grand écran, disposition
// inchangée) et #mobile-mode-bar-slot (collé en haut de l'écran, <900px) —
// aucune logique de changement de mode n'est dupliquée ni réécrite, seul cet
// habillage présentationnel est ajouté.
let _modeTabBarHomeParent = null;
let _modeTabBarHomeNextSibling = null;
const _mobileModeBarQuery = window.matchMedia("(max-width: 900px)");

function placeModeTabBarForViewport(isMobile) {
  const bar = document.getElementById("mode-tab-bar");
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (!bar || !slot) return;
  if (isMobile) {
    if (bar.parentElement !== slot) slot.appendChild(bar);
  } else {
    bar.classList.remove("open");
    if (bar.parentElement !== _modeTabBarHomeParent) {
      _modeTabBarHomeParent.insertBefore(bar, _modeTabBarHomeNextSibling);
    }
  }
}

// Un seul bouton (.active) reste visible quand le menu est fermé (cf. media
// query) ; le cliquer l'ouvre. Ouvert, cliquer un bouton (actif ou non)
// laisse switchModeTab() s'exécuter normalement (onclick déjà posé sur
// chaque bouton) puis referme le menu — délégation d'événement plutôt que
// modifier les 7 boutons, pour ne toucher à aucun onclick existant.
document.addEventListener("click", (e) => {
  const bar = document.getElementById("mode-tab-bar");
  if (!bar || !_mobileModeBarQuery.matches) return;
  const btn = e.target.closest(".mode-tab-btn");
  if (btn && bar.contains(btn)) {
    // Fermé, seul .active est visible → ce clic l'ouvre. Ouvert, l'onclick=
    // "switchModeTab(...)" du bouton (posé dans templates/index.html) s'est
    // déjà exécuté avant que cet écouteur délégué ne reçoive l'événement à
    // la remontée → il ne reste qu'à refermer le menu.
    bar.classList.toggle("open");
    return;
  }
  if (!bar.contains(e.target)) bar.classList.remove("open");
});

// ── Repositionnement de blocs secondaires sur mobile (issue #69) ───────────
// Même mécanique que placeModeTabBarForViewport ci-dessus (déplacement du
// nœud DOM réel entre son emplacement d'origine et un slot dédié, jamais de
// duplication ni de réécriture de la logique — pgn_library.js/game_analysis.js
// and co. retrouvent leurs éléments par id, peu importe leur parent réel) —
// généralisée ici pour les quelques blocs qui changent de place dans la
// réorganisation mobile de l'issue #69 : ce qui ne sert pas pendant la partie
// (importation PGN, navigation dans la collection, programme d'entraînement)
// vers #mobile-bottom-slot (après l'historique des coups), et le panneau
// d'analyse de partie vers #mobile-analysis-slot (juste après le tableau
// "Lignes du coach", dans le panneau du coach).
const _mobileRelocatables = [];

function _registerMobileRelocatable(id, slotId) {
  const el = document.getElementById(id);
  if (!el) return;
  _mobileRelocatables.push({ id, slotId, homeParent: el.parentElement, homeNextSibling: el.nextSibling });
}

function _placeMobileRelocatablesForViewport(isMobile) {
  _mobileRelocatables.forEach(({ id, slotId, homeParent, homeNextSibling }) => {
    const el = document.getElementById(id);
    const slot = document.getElementById(slotId);
    if (!el || !slot) return;
    if (isMobile) {
      if (el.parentElement !== slot) slot.appendChild(el);
    } else if (el.parentElement !== homeParent) {
      homeParent.insertBefore(el, homeNextSibling);
    }
  });
}

// ── scroll-padding-top dynamique (issue #69 point 5) ────────────────────────
// Le scroll-padding-top statique posé en CSS (calc(--bd-size + 90px), cf.
// templates/index.html) suppose une hauteur "normale" de #board-sticky-wrap —
// mais elle varie aussi avec le bandeau de fin de partie, les boutons
// "Jouer les Blancs/Noirs" du mode pédagogique tant qu'aucune partie n'est en
// cours (issue #65 point 6) et la barre de lecture des lignes du coach
// (issue #69 point 4). Un ResizeObserver la resynchronise sur la hauteur
// RÉELLEMENT rendue en toute circonstance, sans avoir à rappeler cette mise à
// jour à chaque bascule de ces éléments — remplace (déborde, en priorité par
// spécificité de style en ligne) la valeur statique dès que ce fichier
// s'exécute ; celle-ci reste un filet de sécurité pour le tout premier rendu
// ou si ResizeObserver est indisponible.
function _updateStickyScrollPadding() {
  const wrap = document.getElementById("board-sticky-wrap");
  if (!wrap || !_mobileModeBarQuery.matches) {
    document.documentElement.style.scrollPaddingTop = "";
    return;
  }
  // + la hauteur de #mobile-mode-bar-slot (issue #71 point 1, désormais
  // sticky au-dessus de #board-sticky-wrap lui-même, cf. _updateMobileHeaderHeight
  // ci-dessous) : sans elle, une cible visée par scrollIntoView se
  // retrouverait masquée par CE sélecteur en plus du plateau.
  const slot = document.getElementById("mobile-mode-bar-slot");
  const headerH = slot ? Math.ceil(slot.getBoundingClientRect().height) : 0;
  document.documentElement.style.scrollPaddingTop = `${Math.ceil(wrap.getBoundingClientRect().height) + headerH + 12}px`;
}
document.addEventListener("DOMContentLoaded", () => {
  const wrap = document.getElementById("board-sticky-wrap");
  if (wrap && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(_updateStickyScrollPadding).observe(wrap);
  }
  _updateStickyScrollPadding();
});
_mobileModeBarQuery.addEventListener("change", _updateStickyScrollPadding);

// ── Hauteur de la rangée d'en-tête collée (issue #71 point 1) ──────────────
// #mobile-mode-bar-slot est désormais lui-même sticky top:0 dans tous les
// modes (cf. templates/index.html) — #board-sticky-wrap (également sticky)
// doit donc se coller JUSTE EN DESSOUS de lui plutôt que se superposer au
// même niveau. Sa hauteur réelle varie (un seul bouton replié hors mode jeu,
// pastille de modèle + menu "..." en mode jeu) : ce ResizeObserver la
// republie dans --mobile-header-h, consommée par #board-sticky-wrap (règle
// "top: var(--mobile-header-h, 0px)", même principe que
// _updateStickyScrollPadding ci-dessus).
function _updateMobileHeaderHeight() {
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (!slot || !_mobileModeBarQuery.matches) {
    document.documentElement.style.setProperty("--mobile-header-h", "0px");
    return;
  }
  document.documentElement.style.setProperty("--mobile-header-h", `${Math.ceil(slot.getBoundingClientRect().height)}px`);
}
document.addEventListener("DOMContentLoaded", () => {
  const slot = document.getElementById("mobile-mode-bar-slot");
  if (slot && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(_updateMobileHeaderHeight).observe(slot);
  }
  _updateMobileHeaderHeight();
});
_mobileModeBarQuery.addEventListener("change", _updateMobileHeaderHeight);

// ── Bascule propre entre modes (issue #23) ──────────────────────────────────
// Si un mode interactif est déjà actif (activeMode) et qu'un autre onglet
// démarre une nouvelle partie/exercice/revue, termine proprement l'ancien
// d'abord — réutilise les fonctions abandon* déjà existantes de chaque
// fichier de mode (abandonExerciseGame étant le seul ajout, cf. exercise.js,
// exercise n'ayant jusqu'ici aucun état serveur à abandonner) — pour éviter
// deux modes "actifs" en même temps. "library" représente la revue de
// bibliothèque/PGN, qui ne fait pas partie de MODE_CAPS/activeMode.
const MODE_SWITCH_CLEANUP = {
  free:      () => abandonFreeGame(),
  pedagogic: () => abandonPedagogicGame(),
  opening:   () => abandonOpeningGame(),
  finale:    () => abandonFinaleGame(),
  exercise:  () => abandonExerciseGame(),
  editor:    () => abandonPositionEditor(),
};

function ensureModeSwitchClean(newMode) {
  if (!activeMode || activeMode === newMode) return;
  const cleanup = MODE_SWITCH_CLEANUP[activeMode];
  if (cleanup) cleanup();
}

// ── Désactivation des boutons de revue hors contexte (issue #23) ───────────
// Précédent/Suivant/Meilleur coup n'ont de sens qu'en revue de bibliothèque
// (activeMode null) — dès qu'un mode interactif tourne, ils sont grisés
// plutôt que de rester cliquables sans effet cohérent.
//
// Issue #34 : "Retourner" en est exclu — contrairement aux trois autres, il
// garde un sens dans n'importe quel mode interactif (voir sa position
// affichée sous un autre angle), donc reste toujours cliquable ; flipBoard()
// (board.js) se charge de cibler la bonne position (mode actif ou revue).
function updateReviewControlsEnabled() {
  const disabled = !!activeMode;
  ["review-prev-btn", "review-next-btn", "review-bestmove-btn"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = disabled;
  });
}

function updateSharedControlBar() {
  const caps = MODE_CAPS[activeMode] || null;
  const reprendreBtn = document.getElementById("shared-reprendre-btn");
  const abandonBtn   = document.getElementById("shared-abandon-btn");
  const commentRow   = document.getElementById("shared-comment-row");
  const askCoachBtn  = document.getElementById("shared-ask-coach-btn");
  const askCoachHelp = document.getElementById("shared-ask-coach-help");
  const statusEl     = document.getElementById("shared-mode-status");

  // Issue #65 point 5 : sur mobile, le mode exercice affiche déjà "Reprendre
  // mon coup" dans la barre du bas (#mobile-exercise-bar, visible seulement
  // sur cet onglet) — le garder aussi ici ferait doublon. Les autres modes
  // (pédagogique/ouverture/finales) n'ont pas cette barre du bas, donc y
  // gardent ce bouton normalement, y compris sur mobile.
  if (reprendreBtn) {
    const isMobile = typeof _mobileModeBarQuery !== "undefined" && _mobileModeBarQuery.matches;
    const dupliqueBarreExercice = activeMode === "exercise" && isMobile;
    reprendreBtn.style.display = (caps && caps.reprendre && !dupliqueBarreExercice) ? "" : "none";
  }
  if (abandonBtn)   abandonBtn.style.display   = caps && caps.abandon   ? "" : "none";
  if (commentRow)   commentRow.style.display   = caps && caps.hasComment ? "" : "none";

  // Issue #65 point 5 : "Demander l'avis du coach" ne fait rien quand la
  // partie est terminée/abandonnée (askXCoach des fichiers de mode se
  // contente alors de ne rien faire, sans le moindre retour visuel) — le
  // bouton doit donc être grisé/désactivé dans ce cas plutôt que de rester
  // cliquable en apparence (règle "pas de terracotta pour ce qui n'est pas
  // cliquable" — button:disabled { opacity:0.5 } s'en charge visuellement).
  if (askCoachBtn) {
    const hasAskCoach = !!(caps && caps.askCoach);
    askCoachBtn.style.display = hasAskCoach ? "" : "none";
    askCoachBtn.disabled = hasAskCoach && caps.askCoachAvailable ? !caps.askCoachAvailable() : false;
  }
  if (askCoachHelp) {
    const hasAskCoach = !!(caps && caps.askCoach);
    askCoachHelp.style.display = hasAskCoach ? "" : "none";
    // Issue #79, point 4a : "Disponible après le verdict" remplace l'aide
    // habituelle en mode exercice tant qu'aucun verdict n'a été rendu pour
    // la tentative en cours — sans ça, le bouton grisé restait accompagné
    // du texte "à tout moment de l'exercice", devenu faux pour ce mode.
    const indisponibleAvantVerdict = activeMode === "exercise" && typeof exerciseVerdictObtenu !== "undefined" && !exerciseVerdictObtenu;
    askCoachHelp.textContent = !hasAskCoach ? "" : indisponibleAvantVerdict ? "Disponible après le verdict." : (MODE_ASK_COACH_HELP[activeMode] || "");
  }
  if (statusEl) statusEl.textContent = activeMode ? MODE_LABELS[activeMode] : "Aucun mode interactif actif.";

  // Issue #70 : mêmes points de coupure que ci-dessus (switchModeTab) — cette
  // fonction est déjà appelée par setActiveMode()/les gestionnaires de fin de
  // partie/abandon/reprendre de chaque mode, donc par ricochet à chaque
  // transition pertinente pour la barre d'actions/le bandeau avant-partie du
  // mode jeu mobile.
  if (typeof onGameUiRefresh === "function") onGameUiRefresh();
}

function sharedReprendreCoup() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.reprendre) caps.reprendre();
}

function sharedAbandonMode() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.abandon) caps.abandon();
}

function sharedAskCoach() {
  const caps = MODE_CAPS[activeMode];
  if (caps && caps.askCoach) caps.askCoach();
}

// ── État de la partie du mode actif (chat libre + historique des coups) ────

function _activeModeGameInstance() {
  switch (activeMode) {
    case "free":      return freeGame;
    case "pedagogic": return pedagogicGame;
    case "opening":   return openingGame;
    case "finale":    return finaleGame;
    case "exercise":  return exerciseGame;
    default:          return null;
  }
}

function _activeModeCampAlain() {
  switch (activeMode) {
    case "pedagogic": return pedagogicCampAlain;
    case "opening":   return openingCampAlain;
    case "finale":    return finaleCampAlain;
    case "exercise":  return exerciseCampAlain;
    default:          return null;
  }
}

// Partie terminée par un clic sur "Abandonner" (issue #52) plutôt que par
// mat/pat/nulle — utilisé par activeModeGameState() ci-dessous pour signaler
// explicitement ce cas au chat libre du coach (coachBuildContext, board.js).
// Contrairement à _activeModeCampAlain ci-dessus, la partie libre a bien un
// état d'abandon propre (freeAbandonne) même si elle n'a pas de camp_alain.
function _activeModeAbandoned() {
  switch (activeMode) {
    case "free":      return !!freeAbandonne;
    case "pedagogic": return !!pedagogicAbandonne;
    case "opening":   return !!openingAbandonne;
    case "finale":    return !!finaleAbandonne;
    default:          return false;
  }
}

function activeModeGameState() {
  const game = _activeModeGameInstance();
  if (!game) return null;
  // pgn/move (issue #33) : historique réel des coups joués depuis le début
  // de la partie en cours (chess.js game.pgn()/game.history()), pour que le
  // chat libre du coach connaisse les coups déjà joués (ex. un fianchetto au
  // coup 8) et pas seulement l'instantané FEN de la position actuelle.
  const history = game.history();
  return {
    fen: game.fen(),
    campAlain: _activeModeCampAlain(),
    pgn: game.pgn(),
    move: history.length ? history[history.length - 1] : "",
    abandonne: _activeModeAbandoned(),
    // Nombre de coups déjà joués dans cette partie (issue #64 point 3),
    // transmis au contexte du coach comme identifiant de la partie en cours.
    nbCoups: history.length,
  };
}

function getActiveModeMoves() {
  const game = _activeModeGameInstance();
  if (!game) return null;
  return game.history({ verbose: true }).map((m) => ({
    san: m.san,
    uci: m.from + m.to + (m.promotion || ""),
    color: m.color === "w" ? "white" : "black",
    qualite: "bon",
  }));
}

// Position de départ réelle de la partie en cours du mode actif (issue #77) —
// chess.js pose automatiquement l'en-tête "FEN" dès qu'une instance est
// construite avec new Chess(fen) sur une position non standard (pedagogic.js/
// opening.js/finales.js, quand Stockfish a déjà joué un ou plusieurs coups
// avant qu'Alain ne commence, ou pour une position-type de finale) — null si
// la partie démarre de la position standard. Consommé par
// analyserPartieCourante() (game_analysis.js) pour que l'analyse "en place"
// (issue #72) rejoue les coups depuis la bonne position côté serveur.
function getActiveModeStartFen() {
  const game = _activeModeGameInstance();
  if (!game || typeof game.header !== "function") return null;
  const h = game.header();
  return (h && h.FEN) ? h.FEN : null;
}

// ── Extraire le FEN de la position affichée (issue #21) ────────────────────
// Mutualisé ici plutôt que dupliqué par mode : réutilise activeModeGameState()
// ci-dessus pour un mode interactif en cours, ou reviewFens/reviewIdx (revue
// PGN, board.js) sinon — même logique de repli que coachBuildContext(). Le
// mode éditeur (pas de partie chess.js) construit son FEN autrement
// (editorBuildFen(), editor.js), d'où le cas particulier.

function extraireFen() {
  const statusEl = document.getElementById("fen-extract-status");
  let fen = null;
  if (activeMode === "editor" && typeof editorBuildFen === "function") {
    fen = editorBuildFen();
  } else if (activeMode) {
    const state = activeModeGameState();
    if (state && state.fen) fen = state.fen;
  }
  if (!fen) fen = reviewFens[reviewIdx] || null;

  if (!fen) {
    if (statusEl) statusEl.textContent = "Aucune position affichée.";
    return;
  }
  if (statusEl) statusEl.textContent = fen;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(fen).catch(() => {});
  }
}

// ── Historique des coups repliable (issue #63, disposition mobile) ─────────
// Ajout purement présentationnel : #historique et son rendu (renderHistory,
// board.js) sont inchangés, seule la visibilité de la table est togglée.
function toggleHistoriqueCollapsed() {
  const col = document.getElementById("historique-column");
  const chevron = document.querySelector(".historique-toggle-chevron");
  if (!col) return;
  const collapsed = col.classList.toggle("collapsed");
  if (chevron) chevron.textContent = collapsed ? "Déplier ▼" : "Replier ▲";
}

// ── Icône d'état "décomposition d'évaluation" (issue #82) ──────────────────
// Rendu initial entièrement côté serveur (app.py index()) — ce widget n'est
// jamais mis à jour en direct (contrairement à #usage-tokens-widget, qui
// suit chaque appel au coach) : l'état ne change qu'au prochain démarrage de
// l'appli ou à la prochaine relance du moteur. Même bascule clic/tap que
// #usage-tokens-widget (usage_tokens.js) : le survol (CSS :hover) suffit sur
// desktop, le clic/tap bascule un état persistant pour le tactile.
function _initEvalStatusWidget() {
  const widget = document.getElementById("eval-status-widget");
  const toggleBtn = document.getElementById("eval-status-toggle");
  const detail = document.getElementById("eval-status-detail");
  if (!widget || !toggleBtn) return;
  toggleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const opening = !widget.classList.contains("eval-status-open");
    widget.classList.toggle("eval-status-open");
    // Même calcul que #usage-detail (usage_tokens.js) : sur mobile, le
    // détail passe en position:fixed (CSS) et a donc besoin d'un "top"
    // explicite ancré au bouton, quelle que soit sa position réelle dans
    // la rangée d'en-tête (desktop vs #mobile-mode-bar-slot).
    if (opening && detail && _mobileModeBarQuery.matches) {
      const rect = toggleBtn.getBoundingClientRect();
      detail.style.top = Math.round(rect.bottom + 6) + "px";
    } else if (detail) {
      detail.style.top = "";
    }
  });
  document.addEventListener("click", (e) => {
    if (!widget.contains(e.target)) widget.classList.remove("eval-status-open");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  updateSharedControlBar();
  updateReviewControlsEnabled();
  switchModeTab("library");
  _initEvalStatusWidget();

  const bar = document.getElementById("mode-tab-bar");
  if (bar) {
    _modeTabBarHomeParent = bar.parentElement;
    _modeTabBarHomeNextSibling = bar.nextSibling;
    placeModeTabBarForViewport(_mobileModeBarQuery.matches);
  }

  // Issue #69 point 2 : mêmes points de coupure (chargement initial +
  // franchissement du seuil mobile) que le sélecteur de mode ci-dessus, pour
  // les blocs secondaires déplacés sur mobile.
  // board-sticky-wrap -> #app directement (pas un slot dédié) : un sticky a
  // besoin d'un parent aussi haut que toute la page pour rester collé jusqu'en
  // bas (cf. commentaire détaillé dans templates/index.html) — #app, colonne
  // qui contient tout le reste, convient ; son order CSS par défaut (0) le
  // place avant #board-column/#coach-column/etc (order 1-5) quel que soit son
  // rang réel dans le DOM après déplacement.
  _registerMobileRelocatable("board-sticky-wrap", "app");
  _registerMobileRelocatable("single-pgn-import-block", "mobile-bottom-slot");
  _registerMobileRelocatable("pgn-lib-browse-block",    "mobile-bottom-slot");
  _registerMobileRelocatable("training-program-panel",  "mobile-bottom-slot");
  _registerMobileRelocatable("game-analysis-panel",     "mobile-analysis-slot");
  // Icône d'état "décomposition d'évaluation" (issue #82) : à côté du menu
  // "..." sur mobile (#mobile-mode-bar-slot, collé dans tous les modes depuis
  // l'issue #81), dans .header-actions sur grand écran (emplacement d'origine
  // dans templates/index.html) — absente du DOM si Stockfish n'est pas
  // installé du tout (cf. app.py index()), _registerMobileRelocatable est
  // alors un no-op (élément introuvable).
  _registerMobileRelocatable("eval-status-widget", "mobile-mode-bar-slot");
  _placeMobileRelocatablesForViewport(_mobileModeBarQuery.matches);
  if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();

  // updateSharedControlBar() en plus de placeModeTabBarForViewport() : issue
  // #65 point 5, le doublon "Reprendre mon coup" en mode exercice ne dépend
  // pas seulement du mode actif mais aussi du franchissement du seuil mobile
  // (rotation d'écran, redimensionnement d'une fenêtre desktop) — sans cet
  // appel, resterait affiché jusqu'au prochain changement de mode.
  _mobileModeBarQuery.addEventListener("change", (e) => {
    placeModeTabBarForViewport(e.matches);
    _placeMobileRelocatablesForViewport(e.matches);
    if (typeof _updateBoardLinesCommandBar === "function") _updateBoardLinesCommandBar();
    updateSharedControlBar();
  });

  // Replié par défaut sur mobile seulement (issue #63) — sur grand écran,
  // l'historique reste dépliable mais visible d'entrée comme avant. Le
  // libellé statique du gabarit ("Déplier ▼") est resynchronisé ici dans
  // les deux cas, plutôt que de dépendre du texte codé en dur du template.
  const chevron = document.querySelector(".historique-toggle-chevron");
  if (_mobileModeBarQuery.matches) {
    toggleHistoriqueCollapsed();
  } else if (chevron) {
    chevron.textContent = "Replier ▲";
  }
});
