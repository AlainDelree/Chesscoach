// llm_model.js — Sélecteur de modèle Claude actif dans l'en-tête (issue #61)
//
// Deux boutons contigus (Haiku (test) / Sonnet (sérieux)) ; le bouton actif
// est mis en évidence. Le clic envoie "set_llm_model" au serveur : effet
// immédiat sur tous les appels suivants (config.LLM_MODEL est relu à chaque
// appel côté serveur, jamais figé au démarrage), persisté localement (hors
// .env), sans redémarrage ni interruption de la partie/du chat en cours. Si
// l'API refuse le modèle choisi lors d'un appel ultérieur, le serveur revient
// seul au choix précédent et prévient ce client via "llm_model_indisponible"
// — ce fichier se contente alors de refléter ce retour en arrière et
// d'afficher un message clair dans le chat, plutôt qu'une erreur brute.

function _llmModelSetActive(modelId) {
  document.querySelectorAll("#llm-model-selector .llm-model-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.model === modelId);
  });
}

function _llmModelSetBusy(busy) {
  document.querySelectorAll("#llm-model-selector .llm-model-btn").forEach((btn) => {
    btn.disabled = busy;
  });
}

// Même style de bulle d'erreur que _coachRenderCreditInsuffisant (board.js,
// issue #54) — pas de dépendance directe à cette fonction (spécifique au
// message crédit épuisé, avec son lien vers la Console), mais le même
// conteneur #coach-history et la même palette, pour rester cohérent avec le
// reste des messages système du chat.
function _llmModelRenderIndisponible(modeleRefuse, nouveauLabel) {
  const history = document.getElementById("coach-history");
  if (!history) return;
  const empty = document.getElementById("coach-empty");
  if (empty) empty.style.display = "none";
  const bubble = document.createElement("div");
  bubble.style.cssText = "background:#f8d7da; border-radius:8px; padding:8px 12px; align-self:flex-start; max-width:88%; font-size:1.05rem; line-height:1.45; color:#5a1a1a;";
  bubble.textContent = `Le modèle "${modeleRefuse}" n'est pas disponible actuellement — retour automatique sur ${nouveauLabel}.`;
  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#llm-model-selector .llm-model-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("active") || btn.disabled) return;
      _llmModelSetBusy(true);
      socket.emit("set_llm_model", { model: btn.dataset.model });
    });
  });
});

if (typeof socket !== "undefined") {
  socket.on("llm_model_changed", (data) => {
    _llmModelSetBusy(false);
    if (data && data.model) _llmModelSetActive(data.model);
  });

  socket.on("llm_model_error", (data) => {
    _llmModelSetBusy(false);
    console.warn("[modèle Claude] changement refusé", data);
  });

  socket.on("llm_model_indisponible", (data) => {
    _llmModelSetBusy(false);
    if (data && data.model) _llmModelSetActive(data.model);
    _llmModelRenderIndisponible(
      (data && data.modele_refuse) || "?",
      (data && data.label) || (data && data.model) || "?"
    );
  });
}
