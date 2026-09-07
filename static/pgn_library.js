/*
 * pgn_library.js — ChessCoach
 *
 * Panneau de bibliothèque PGN personnelle : liste des collections (issue
 * #2/#3), liste des parties d'une collection, import d'un fichier PGN,
 * chargement d'une partie dans le plateau (délègue à parsePgn de board.js).
 *
 * Dépendances externes : un objet global `socket` déjà connecté, et les
 * fonctions de static/board.js (parsePgn).
 */

let _pgnLibSelectedCollection = null;

function pgnLibRenderCollections(collections) {
  const sel = document.getElementById("pgn-lib-collection-select");
  if (!sel) return;
  const previous = _pgnLibSelectedCollection;
  sel.innerHTML = "";
  collections.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.name} (${c.game_count})`;
    sel.appendChild(opt);
  });
  if (collections.length) {
    _pgnLibSelectedCollection = (previous && collections.some(c => c.id === previous))
      ? previous : collections[0].id;
    sel.value = _pgnLibSelectedCollection;
    socket.emit("pgn_lib_list_games", { collection_id: _pgnLibSelectedCollection });
  } else {
    _pgnLibSelectedCollection = null;
    pgnLibRenderGames([]);
  }
}

function pgnLibRenderGames(games) {
  const list = document.getElementById("pgn-lib-games");
  if (!list) return;
  list.innerHTML = "";
  if (!games.length) {
    const li = document.createElement("li");
    li.style.color = "#778";
    li.textContent = "Aucune partie dans cette collection.";
    list.appendChild(li);
    return;
  }
  games.forEach(g => {
    const li = document.createElement("li");
    li.style.cursor = "pointer";
    li.style.padding = "2px 4px";
    li.textContent = `${g.date} — ${g.white} vs ${g.black} (${g.result})`;
    li.onclick = () => socket.emit("pgn_lib_load_game", {
      collection_id: _pgnLibSelectedCollection,
      index: g.index,
    });
    list.appendChild(li);
  });
}

function pgnLibOnCollectionChange() {
  const sel = document.getElementById("pgn-lib-collection-select");
  if (!sel || !sel.value) return;
  _pgnLibSelectedCollection = sel.value;
  socket.emit("pgn_lib_list_games", { collection_id: _pgnLibSelectedCollection });
}

function pgnLibCreateCollection() {
  const input = document.getElementById("pgn-lib-new-name");
  if (!input || !input.value.trim()) return;
  socket.emit("pgn_lib_create_collection", { name: input.value.trim() });
  input.value = "";
}

function pgnLibImportFile(event) {
  const file = event.target.files[0];
  if (!file || !_pgnLibSelectedCollection) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    socket.emit("pgn_lib_import_pgn", {
      collection_id: _pgnLibSelectedCollection,
      content: e.target.result,
    });
  };
  reader.readAsText(file);
  event.target.value = "";
}

if (typeof socket !== "undefined") {
  socket.on("pgn_lib_collections", (data) => {
    pgnLibRenderCollections((data && data.collections) || []);
  });

  socket.on("pgn_lib_games", (data) => {
    if (data && data.collection_id === _pgnLibSelectedCollection) {
      pgnLibRenderGames(data.games || []);
    }
  });

  socket.on("pgn_lib_game_loaded", (data) => {
    if (!data || !data.pgn) return;
    parsePgn(data.pgn, (info) => {
      const label = document.getElementById("pgn-lib-loaded-label");
      if (label) label.textContent = `Chargée : ${info.white} vs ${info.black} (${info.result})`;
    });
  });

  socket.on("pgn_lib_error", (data) => {
    console.warn("[pgn_lib]", data && data.message);
    alert("Bibliothèque PGN : " + ((data && data.message) || "erreur inconnue"));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof socket !== "undefined") {
    socket.emit("pgn_lib_list_collections", {});
  }
});
