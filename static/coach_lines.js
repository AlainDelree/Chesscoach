/*
 * coach_lines.js — ChessCoach (issue #58)
 *
 * Composant réutilisable, indépendant du mode : extraction des lignes de
 * coups citées dans un texte libre du coach, résolution de leur position de
 * départ par légalité (pas de devinette), et lecture pas à pas sur
 * l'échiquier. Utilisé par le mode exercice (exercise.js) et, depuis
 * l'issue #68, par les modes partie (libre/pédagogique/ouverture/finales) et
 * la revue de bibliothèque (game_coach_lines.js) via extractCoachGameLines
 * ci-dessous, qui étend extractCoachMoveLines avec la mention de départ
 * fixe demandée au coach dans son system prompt pour ces modes-là
 * (_GAME_LINES_ADDENDUM, llm_coach.py) — une partie avec un historique réel
 * peut en effet citer une ligne alternative qui part d'une position déjà
 * jouée plus tôt, pas forcément de la position actuelle.
 *
 * Dépendance externe : la librairie chess.js exposée en global `Chess`
 * (déjà chargée par la page hôte, cf. board.js).
 */

// Un coup SAN "nu" (numéro de coup et annotations déjà retirés) — pièces
// avec désambiguïsation (Nbd7, R1e2), coups de pion avec capture/promotion,
// roques. Volontairement permissif sur la désambiguïsation : la légalité
// réelle est de toute façon vérifiée ensuite en rejouant le coup avec
// chess.js, ce motif ne fait que repérer les candidats dans le texte.
const _COACH_LINE_SAN_RE = /^(O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?|[a-h]x?[a-h]?[1-8](=[QRBN])?)$/;

// Un chemin de cases séparées par des tirets (c3-d3-e3) n'est PAS un coup —
// à ne pas confondre avec le roque (O-O / O-O-O), seul cas légitime de
// tiret dans un token de coup.
function _coachLineCleanToken(token) {
  let t = token.replace(/^\d+\.(\.\.)?/, ""); // "12." / "12..." en préfixe
  t = t.replace(/[!?]+$/, "");                // annotations de fin ("!", "?", "!?", "?!"...)
  t = t.replace(/[+#]$/, "");                 // échec / mat
  t = t.replace(/[!?]+$/, "");                // au cas où l'ordre était +!? / #?!
  return t;
}

/**
 * Repère dans un texte libre les suites d'au moins deux coups en notation
 * standard, séparés par des espaces (avec ou sans numéros de coups ni
 * annotations !?+#), et les dédoublonne. Ignore tout token qui ne
 * correspond pas à un coup (dont les chemins de cases séparés par des
 * tirets, type c3-d3-e3).
 *
 * Retourne un tableau de lignes, chaque ligne étant un tableau de coups SAN
 * "nus" (ordre de première apparition dans le texte, sans doublon).
 */
function extractCoachMoveLines(text) {
  if (!text) return [];
  const tokens = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let current = [];
  const flush = () => {
    if (current.length >= 2) lines.push(current.slice());
    current = [];
  };
  for (const raw of tokens) {
    if (/^\d+\.(\.\.)?$/.test(raw)) continue; // numéro de coup isolé : ne casse pas la ligne
    const clean = _coachLineCleanToken(raw);
    if (clean && _COACH_LINE_SAN_RE.test(clean)) {
      current.push(clean);
    } else {
      flush();
    }
  }
  flush();

  const seen = new Set();
  const unique = [];
  for (const moves of lines) {
    const key = moves.join(" ");
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(moves);
  }
  return unique;
}

/**
 * Détermine la position de départ d'une ligne par légalité : essaie chaque
 * candidat dans l'ordre fourni (typiquement [position d'avant le coup,
 * position d'après le coup]) et retient le premier où TOUS les coups de la
 * ligne sont légaux. Ne devine jamais — une ligne illégale depuis tous les
 * candidats retourne null.
 *
 * candidates : [{ fen, label }, ...]
 * moves      : tableau de coups SAN "nus" (cf. extractCoachMoveLines)
 *
 * Retourne { label, startFen, steps } où steps est un tableau
 * [{ san, from, to, fen }] (fen = position APRÈS ce coup), ou null.
 */
function resolveCoachLineStart(candidates, moves) {
  for (const candidate of candidates || []) {
    if (!candidate || !candidate.fen) continue;
    let game;
    try {
      game = new Chess(candidate.fen);
    } catch (e) {
      continue;
    }
    const steps = [];
    let ok = true;
    for (const san of moves) {
      const move = game.move(san, { sloppy: true });
      if (!move) { ok = false; break; }
      steps.push({ san: move.san, from: move.from, to: move.to, fen: game.fen() });
    }
    if (ok && steps.length === moves.length) {
      return { label: candidate.label, startFen: candidate.fen, steps };
    }
  }
  return null;
}

/**
 * Joue une suite de coups déjà résolue (steps de resolveCoachLineStart) avec
 * une pause entre chaque, via un callback de rendu fourni par l'appelant
 * (aucune dépendance à un plateau ou un mode particulier ici). Retourne un
 * contrôleur { stop() } pour interrompre la lecture en cours de route.
 *
 * opts :
 *   speedMs    : pause en ms entre deux coups
 *   renderStep(fen, fromSquare, toSquare) : appelé pour chaque coup joué
 *   onDone()   : appelé une fois la ligne entièrement jouée (pas appelé si stop() a été utilisé)
 */
function playCoachLineSequence(steps, opts) {
  const options = opts || {};
  const speedMs = options.speedMs || 1000;
  let idx = 0;
  let stopped = false;
  let timer = null;

  function playNext() {
    if (stopped) return;
    if (idx >= steps.length) {
      if (typeof options.onDone === "function") options.onDone();
      return;
    }
    const step = steps[idx++];
    if (typeof options.renderStep === "function") options.renderStep(step.fen, step.from, step.to);
    timer = setTimeout(playNext, speedMs);
  }

  timer = setTimeout(playNext, speedMs);

  return {
    stop() {
      stopped = true;
      if (timer) clearTimeout(timer);
    },
  };
}

// ── Extraction avec mention de départ (issue #68) ───────────────────────────
// Format fixe demandé au coach pour introduire une ligne qui ne part pas de
// la position actuelle (_GAME_LINES_ADDENDUM, llm_coach.py) : "depuis le
// coup 8... (Noirs)" ou "depuis le coup 12 (Blancs)", immédiatement avant les
// coups de la ligne (éventuellement séparés par ":"/"—"/espaces). Ne devine
// jamais un numéro/camp qui ne serait pas explicitement écrit sous cette
// forme — une ligne sans cette mention reste simplement "sans ancre" (son
// appelant essaiera alors la position actuelle, cf. resolveCoachLineStart).
const _COACH_LINE_ANCHOR_RE = /depuis\s+le\s+coup\s+(\d+)\s*(\.\.\.)?\s*\(\s*(Blancs|Noirs)\s*\)/gi;

/**
 * Comme extractCoachMoveLines, mais conserve pour chaque ligne trouvée la
 * mention de départ ("depuis le coup N... (Camp)") qui la précède
 * immédiatement dans le texte, s'il y en a une.
 *
 * Retourne un tableau de { moves, anchor }, moves étant un tableau de coups
 * SAN "nus" (comme extractCoachMoveLines) et anchor soit
 * { moveNumber, color } (color: "blancs"/"noirs"), soit null si la ligne
 * n'est précédée d'aucune mention de départ reconnaissable.
 */
function extractCoachGameLines(text) {
  if (!text) return [];

  // 1) Repère les lignes de coups en conservant l'indice de caractère du
  //    premier token de chaque ligne (même tokenizer qu'extractCoachMoveLines).
  const tokenRe = /\S+/g;
  const lines = [];
  let current = [];
  let currentStart = -1;
  const flush = () => {
    if (current.length >= 2) lines.push({ moves: current.slice(), startIdx: currentStart });
    current = [];
    currentStart = -1;
  };
  let tm;
  while ((tm = tokenRe.exec(text)) !== null) {
    const raw = tm[0];
    if (/^\d+\.(\.\.)?$/.test(raw)) continue; // numéro de coup isolé : ne casse pas la ligne
    const clean = _coachLineCleanToken(raw);
    if (clean && _COACH_LINE_SAN_RE.test(clean)) {
      if (current.length === 0) currentStart = tm.index;
      current.push(clean);
    } else {
      flush();
    }
  }
  flush();

  // 2) Repère chaque mention "depuis le coup N... (Camp)" et sa position de
  //    fin dans le texte.
  const anchors = [];
  _COACH_LINE_ANCHOR_RE.lastIndex = 0;
  let am;
  while ((am = _COACH_LINE_ANCHOR_RE.exec(text)) !== null) {
    anchors.push({
      moveNumber: parseInt(am[1], 10),
      color: am[3].toLowerCase() === "noirs" ? "noirs" : "blancs",
      endIdx: am.index + am[0].length,
    });
  }

  // 3) Associe chaque ligne (dédoublonnée par son contenu) à la mention la
  //    plus proche qui la précède IMMÉDIATEMENT — seuls des séparateurs de
  //    ponctuation/espaces entre les deux (ex. " : "), jamais un autre coup
  //    ou mot inattendu, sans quoi la ligne reste sans ancre.
  const seen = new Set();
  const result = [];
  for (const line of lines) {
    const key = line.moves.join(" ");
    if (seen.has(key)) continue;
    seen.add(key);
    let anchor = null;
    for (const a of anchors) {
      if (a.endIdx > line.startIdx) continue;
      const gap = text.slice(a.endIdx, line.startIdx);
      if (!/^[\s:–—-]*$/.test(gap)) continue;
      if (!anchor || a.endIdx > anchor.endIdx) anchor = a;
    }
    result.push({
      moves: line.moves,
      anchor: anchor ? { moveNumber: anchor.moveNumber, color: anchor.color } : null,
    });
  }
  return result;
}
