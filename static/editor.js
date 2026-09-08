/*
 * editor.js — ChessCoach (issue #16)
 *
 * Panneau "Éditeur de position" : échiquier vide au départ, pièces
 * disponibles sur le côté (palette), placement libre par glisser-déposer ou
 * clic-source/clic-destination, pour construire directement une position de
 * finale sans avoir à la faire apparaître par une partie jouée (issue #13).
 *
 * Réutilise buildBoard()/renderBoard() de board.js pour le dessin du
 * plateau, comme les autres modes (free_play.js, finales.js...) — seule la
 * source de la position (editorPosition, une grille {file-rank: pièce} au
 * même format que fenToBoard()) et la gestion des clics/glisser-déposer
 * diffèrent.
 *
 * Contrairement aux autres modes, il n'y a pas de "partie" jouée (pas de
 * chess.js, pas de coup) : la légalité de la position en cours de
 * construction est vérifiée côté serveur via python-chess
 * (Board.status(), voir app.py on_editor_validate) à chaque modification,
 * plutôt que côté client où cette vérification n'est pas disponible.
 *
 * L'enregistrement réutilise l'événement finale_add déjà existant (issue
 * #13, partagé avec free_play.js) — voir pendingFinaleAddSource (déclaré
 * dans board.js) pour éviter qu'une réponse déclenchée par l'éditeur ne
 * mette à jour le panneau "Partie libre" et inversement.
 *
 * Hors périmètre (issue #16) : pas d'utilisation de cet éditeur pour
 * démarrer une partie libre ou un autre mode, pas d'import/export FEN texte.
 */

const EDITOR_PALETTE_PIECES = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"];

let editorPosition      = {};   // grille {"file-rank": pièce}, même format que fenToBoard()
let editorTool          = null; // { type: "piece", piece } | { type: "delete" } | null
let editorBoardSelected = null; // case "file-rank" sélectionnée pour un déplacement clic-source/clic-destination
let editorTrait         = "blancs";
let editorLastValid     = false;

// Camp qu'Alain doit jouer (finale_add) : distinct du trait FEN — comme le
// documente finales.py, la position de référence roi_pion_colonne_e a par
// exemple trait aux Noirs (l'adversaire ouvre) mais camp_alain "blancs".
// Déduit du trait par défaut ; un choix explicite (editorCampAlainTouched)
// le découple ensuite du trait.
let editorCampAlain        = "blancs";
let editorCampAlainTouched = false;

// ── Construction de la FEN à partir de la grille ────────────────────────────
// Pas de droits de roque ni de case en-passant : hors de propos pour des
// positions de finale construites pièce par pièce (comme la position de
// référence de finales.py, qui utilise déjà "-").

function editorGridToFenBoard(grid) {
  const rows = [];
  for (let rank = 7; rank >= 0; rank--) {
    let row = "";
    let empty = 0;
    for (let file = 0; file < 8; file++) {
      const piece = grid[`${file}-${rank}`];
      if (piece) {
        if (empty) { row += empty; empty = 0; }
        row += piece;
      } else {
        empty++;
      }
    }
    if (empty) row += empty;
    rows.push(row);
  }
  return rows.join("/");
}

function editorBuildFen() {
  const board = editorGridToFenBoard(editorPosition);
  const turn = editorTrait === "noirs" ? "b" : "w";
  return `${board} ${turn} - - 0 1`;
}

// ── Rendu ────────────────────────────────────────────────────────────────

function renderEditorBoard() {
  renderBoard(editorGridToFenBoard(editorPosition), null, null, null, null, null, null);
  if (editorBoardSelected) {
    const sq = document.getElementById(`sq-${editorBoardSelected}`);
    if (sq) sq.classList.add("free-play-selected");
  }
  // renderBoard() régénère l'innerHTML de chaque case à chaque appel : le
  // glisser-déposer doit être ré-attaché après coup plutôt que dans board.js
  // (générique, réutilisé par des modes qui n'en ont pas besoin).
  for (let rank = 0; rank < 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const id = `${file}-${rank}`;
      const sq = document.getElementById(`sq-${id}`);
      if (!sq) continue;
      sq.ondragover = (e) => e.preventDefault();
      sq.ondrop = (e) => onEditorSquareDrop(e, id);
      const img = sq.querySelector("img");
      if (img) {
        img.draggable = true;
        img.ondragstart = (e) => e.dataTransfer.setData("text/plain", JSON.stringify({ source: "board", square: id }));
      }
    }
  }
}

function buildEditorPalette() {
  const container = document.getElementById("editor-palette");
  if (!container) return;
  container.innerHTML = "";
  EDITOR_PALETTE_PIECES.forEach((piece) => {
    const cell = document.createElement("div");
    cell.className = "editor-palette-piece";
    cell.dataset.piece = piece;
    cell.draggable = true;
    cell.innerHTML = PIECES[piece] || piece;
    cell.title = piece === piece.toUpperCase() ? "Pièce blanche" : "Pièce noire";
    cell.onclick = () => onEditorPaletteClick(piece);
    cell.ondragstart = (e) => e.dataTransfer.setData("text/plain", JSON.stringify({ source: "palette", piece }));
    container.appendChild(cell);
  });
  const trashCell = document.createElement("div");
  trashCell.className = "editor-palette-piece editor-palette-delete";
  trashCell.textContent = "Supprimer";
  trashCell.title = "Mode suppression : cliquer une pièce posée pour la retirer";
  trashCell.onclick = () => onEditorDeleteToolClick();
  container.appendChild(trashCell);
  renderEditorPaletteSelection();
}

function renderEditorPaletteSelection() {
  const container = document.getElementById("editor-palette");
  if (!container) return;
  container.querySelectorAll(".editor-palette-piece").forEach((cell) => {
    let selected = false;
    if (editorTool && editorTool.type === "piece" && cell.dataset.piece === editorTool.piece) selected = true;
    if (editorTool && editorTool.type === "delete" && cell.classList.contains("editor-palette-delete")) selected = true;
    cell.classList.toggle("selected", selected);
  });
}

// ── Outils (palette / suppression) ──────────────────────────────────────────

function onEditorPaletteClick(piece) {
  editorBoardSelected = null;
  editorTool = (editorTool && editorTool.type === "piece" && editorTool.piece === piece)
    ? null
    : { type: "piece", piece };
  renderEditorPaletteSelection();
  renderEditorBoard();
}

function onEditorDeleteToolClick() {
  editorBoardSelected = null;
  editorTool = (editorTool && editorTool.type === "delete") ? null : { type: "delete" };
  renderEditorPaletteSelection();
  renderEditorBoard();
}

// ── Clic sur l'échiquier (source/destination) ───────────────────────────────

function onEditorBoardClick(e) {
  if (activeMode !== "editor") return;
  const sqEl = e.target.closest(".square");
  if (!sqEl) return;
  const id = sqEl.id.replace("sq-", "");

  if (editorTool && editorTool.type === "delete") {
    if (editorPosition[id]) {
      delete editorPosition[id];
      renderEditorBoard();
      editorValidate();
    }
    return;
  }

  if (editorTool && editorTool.type === "piece") {
    editorPosition[id] = editorTool.piece;
    renderEditorBoard();
    editorValidate();
    return;
  }

  // Aucun outil sélectionné : déplacer une pièce déjà posée (clic-source
  // puis clic-destination), comme le mode "partie libre".
  if (editorBoardSelected === null) {
    if (editorPosition[id]) {
      editorBoardSelected = id;
      renderEditorBoard();
    }
    return;
  }
  if (editorBoardSelected === id) {
    editorBoardSelected = null;
    renderEditorBoard();
    return;
  }
  editorPosition[id] = editorPosition[editorBoardSelected];
  delete editorPosition[editorBoardSelected];
  editorBoardSelected = null;
  renderEditorBoard();
  editorValidate();
}

// ── Glisser-déposer ──────────────────────────────────────────────────────

function onEditorSquareDrop(e, id) {
  e.preventDefault();
  const raw = e.dataTransfer.getData("text/plain");
  if (!raw) return;
  let data;
  try { data = JSON.parse(raw); } catch (err) { return; }

  if (data.source === "palette" && data.piece) {
    editorPosition[id] = data.piece;
  } else if (data.source === "board" && data.square) {
    if (data.square === id) return;
    editorPosition[id] = editorPosition[data.square];
    delete editorPosition[data.square];
  } else {
    return;
  }
  editorBoardSelected = null;
  renderEditorBoard();
  editorValidate();
}

function onEditorTrashDrop(e) {
  e.preventDefault();
  const raw = e.dataTransfer.getData("text/plain");
  if (!raw) return;
  try {
    const data = JSON.parse(raw);
    if (data.source === "board" && data.square) {
      delete editorPosition[data.square];
      renderEditorBoard();
      editorValidate();
    }
  } catch (err) {
    // Glissé depuis la palette (ajout, pas suppression) : rien à faire.
  }
}

// ── Trait / validation ──────────────────────────────────────────────────────

function onEditorTraitChange() {
  const sel = document.querySelector('input[name="editor-trait"]:checked');
  editorTrait = (sel && sel.value === "noirs") ? "noirs" : "blancs";
  if (!editorCampAlainTouched) {
    editorCampAlain = editorTrait;
    const campEl = document.getElementById(editorTrait === "noirs" ? "editor-camp-alain-noirs" : "editor-camp-alain-blancs");
    if (campEl) campEl.checked = true;
  }
  editorValidate();
}

function onEditorCampAlainChange() {
  const sel = document.querySelector('input[name="editor-camp-alain"]:checked');
  editorCampAlain = (sel && sel.value === "noirs") ? "noirs" : "blancs";
  editorCampAlainTouched = true;
}

function editorValidate() {
  socket.emit("editor_validate", { fen: editorBuildFen() });
}

// ── Cycle de vie du panneau ──────────────────────────────────────────────

function startPositionEditor() {
  editorPosition          = {};
  editorTool              = null;
  editorBoardSelected     = null;
  editorTrait             = "blancs";
  editorLastValid         = false;
  editorCampAlain         = "blancs";
  editorCampAlainTouched  = false;

  const traitBlancs = document.getElementById("editor-trait-blancs");
  if (traitBlancs) traitBlancs.checked = true;
  const campBlancs = document.getElementById("editor-camp-alain-blancs");
  if (campBlancs) campBlancs.checked = true;

  setActiveMode("editor");
  _boardFlipped = false;
  buildBoard();
  const boardEl = document.getElementById("board");
  if (boardEl) {
    boardEl.classList.add("free-play-active");
    boardEl.onclick = onEditorBoardClick;
  }
  renderEditorPaletteSelection();
  renderEditorBoard();
  editorValidate();

  const statusEl = document.getElementById("editor-status");
  if (statusEl) statusEl.textContent = "Placez les pièces sur l'échiquier vide.";
}

function clearEditorBoard() {
  if (activeMode !== "editor") return;
  editorPosition = {};
  editorBoardSelected = null;
  renderEditorBoard();
  editorValidate();
}

function abandonPositionEditor() {
  if (activeMode !== "editor") return;
  editorPosition      = {};
  editorTool          = null;
  editorBoardSelected = null;
  renderEditorPaletteSelection();
  resetBoardToNeutral();
  setActiveMode(null);
  const statusEl = document.getElementById("editor-status");
  if (statusEl) statusEl.textContent = "Éditeur fermé.";
  const validationEl = document.getElementById("editor-validation-status");
  if (validationEl) validationEl.textContent = "";
}

// ── Enregistrement comme finale (réutilise finale_add, issue #13) ──────────

function saveEditorPositionAsFinale() {
  const statusEl = document.getElementById("editor-status");
  if (activeMode !== "editor") {
    if (statusEl) statusEl.textContent = "Ouvrez d'abord l'éditeur de position.";
    return;
  }
  if (!editorLastValid) {
    if (statusEl) statusEl.textContent = "Position illégale : corrigez-la avant d'enregistrer.";
    return;
  }
  const nomEl  = document.getElementById("editor-finale-nom");
  const descEl = document.getElementById("editor-finale-description");
  const nom = nomEl ? nomEl.value.trim() : "";
  const description = descEl ? descEl.value.trim() : "";
  if (!nom) {
    if (statusEl) statusEl.textContent = "Indiquez un nom pour cette finale avant d'enregistrer.";
    return;
  }
  pendingFinaleAddSource = "editor";
  socket.emit("finale_add", { fen: editorBuildFen(), camp_alain: editorCampAlain, nom, description });
}

if (typeof socket !== "undefined") {
  socket.on("editor_validate_response", (data) => {
    editorLastValid = !!(data && data.valid);
    const saveBtn = document.getElementById("editor-save-btn");
    if (saveBtn) saveBtn.disabled = !editorLastValid;
    const statusEl = document.getElementById("editor-validation-status");
    if (!statusEl) return;
    if (!data) { statusEl.textContent = ""; return; }
    if (data.valid) {
      statusEl.textContent = "Position légale.";
      statusEl.style.color = "#2f7d32";
    } else {
      statusEl.textContent = "Position illégale : " + (data.problems || []).join(" ");
      statusEl.style.color = "#c0392b";
    }
  });

  socket.on("finale_add_response", (data) => {
    if (pendingFinaleAddSource !== "editor") return;
    pendingFinaleAddSource = null;
    const statusEl = document.getElementById("editor-status");
    if (!data || data.error) {
      if (statusEl) statusEl.textContent = "Impossible d'enregistrer cette finale (nom ou position invalide).";
      return;
    }
    if (statusEl) statusEl.textContent = `Finale "${data.nom}" enregistrée — disponible dans le mode "Travail de finales".`;
    const nomEl  = document.getElementById("editor-finale-nom");
    const descEl = document.getElementById("editor-finale-description");
    if (nomEl)  nomEl.value  = "";
    if (descEl) descEl.value = "";
    if (data.finales) {
      finaleList = data.finales;
      if (typeof populateFinaleSelect === "function") populateFinaleSelect();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  buildEditorPalette();
  const trashEl = document.getElementById("editor-trash");
  if (trashEl) {
    trashEl.ondragover = (e) => e.preventDefault();
    trashEl.ondrop = onEditorTrashDrop;
  }
});
