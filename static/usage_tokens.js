// usage_tokens.js — Compteur discret de tokens consommés (issue #54)
//
// Affiche dans l'en-tête, près du lien "Coût API", les tokens du dernier
// appel et le total cumulé depuis la date de départ (entrée/sortie séparées),
// avec le détail par modèle au survol (desktop) ou au tap (tactile) — un
// modèle différent n'a pas le même "coût" par token, ce détail doit donc
// rester consultable même si le résumé de l'en-tête ne l'affiche pas.
// Volontairement AUCUN prix ni équivalent en argent nulle part : décision
// d'Alain (pas de table de prix par modèle à maintenir côté ChessCoach), il
// rapproche lui-même ce compteur du solde réel affiché sur la Console.
//
// Données reçues du serveur (llm_coach.get_usage_summary, voir app.py) :
//   { date_debut, dernier_appel: {model, horodatage, input_tokens,
//     output_tokens, cache_creation_input_tokens, cache_read_input_tokens}
//     ou null, par_modele: {modele: {mêmes champs + appels}},
//     total: {mêmes 4 champs, somme tous modèles} }

function _fmtTok(n) {
  n = Number(n) || 0;
  if (n < 1000) return String(n);
  if (n < 1000000) {
    const k = n / 1000;
    return (k >= 10 ? Math.round(k) : k.toFixed(1).replace(".", ",")) + "k";
  }
  const m = n / 1000000;
  return (m >= 10 ? Math.round(m) : m.toFixed(1).replace(".", ",")) + "M";
}

function _fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("fr-FR");
  } catch (e) {
    return "";
  }
}

function _usageRenderDetailBody(data) {
  const body = document.getElementById("usage-detail-body");
  if (!body) return;
  const parModele = (data && data.par_modele) || {};
  const noms = Object.keys(parModele);
  if (!noms.length) {
    body.textContent = "Aucun appel comptabilisé pour l'instant.";
    return;
  }
  let html = `<div style="margin-bottom:4px; color:#556;">Depuis le ${_fmtDate(data.date_debut)} :</div>`;
  html += '<table><tr><td><strong>Modèle</strong></td><td><strong>Entrée</strong></td><td><strong>Sortie</strong></td><td><strong>Cache (écr./lu)</strong></td><td><strong>Appels</strong></td></tr>';
  noms.sort().forEach((modele) => {
    const c = parModele[modele] || {};
    html += `<tr><td>${modele}</td><td>${_fmtTok(c.input_tokens)}</td><td>${_fmtTok(c.output_tokens)}</td>`
      + `<td>${_fmtTok(c.cache_creation_input_tokens)} / ${_fmtTok(c.cache_read_input_tokens)}</td>`
      + `<td>${c.appels || 0}</td></tr>`;
  });
  html += "</table>";
  const dernier = data.dernier_appel;
  if (dernier) {
    html += `<div style="margin-top:6px; color:#556;">Dernier appel (${dernier.model || "?"}) : `
      + `${_fmtTok(dernier.input_tokens)} entrée / ${_fmtTok(dernier.output_tokens)} sortie</div>`;
  }
  body.innerHTML = html;
}

function renderUsageSummary(data) {
  if (!data) return;
  const toggleBtn = document.getElementById("usage-toggle-btn");
  if (toggleBtn) {
    const total = data.total || {};
    const dernier = data.dernier_appel;
    const totalTxt = `${_fmtTok(total.input_tokens)} in / ${_fmtTok(total.output_tokens)} out`;
    const dernierTxt = dernier
      ? `${_fmtTok(dernier.input_tokens)} in / ${_fmtTok(dernier.output_tokens)} out`
      : "—";
    toggleBtn.innerHTML =
      `<span class="usage-full">Dernier appel : ${dernierTxt} · Total depuis le ${_fmtDate(data.date_debut)} : ${totalTxt}</span>`
      + `<span class="usage-compact">Σ ${totalTxt}</span>`;
  }
  _usageRenderDetailBody(data);
}

function usageReset() {
  if (!confirm("Remettre à zéro le compteur de tokens (et sa date de départ) ?")) return;
  socket.emit("usage_reset");
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof USAGE_SUMMARY_INITIAL !== "undefined") {
    renderUsageSummary(USAGE_SUMMARY_INITIAL);
  }

  const widget = document.getElementById("usage-tokens-widget");
  const toggleBtn = document.getElementById("usage-toggle-btn");
  if (widget && toggleBtn) {
    // Le survol (CSS :hover) affiche déjà le détail sur desktop — le clic/tap
    // bascule un état persistant pour le tactile, où il n'y a pas de survol.
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      widget.classList.toggle("usage-detail-open");
    });
    document.addEventListener("click", (e) => {
      if (!widget.contains(e.target)) widget.classList.remove("usage-detail-open");
    });
  }

  const resetBtn = document.getElementById("usage-reset-btn");
  if (resetBtn) resetBtn.addEventListener("click", usageReset);

  if (typeof socket !== "undefined") {
    socket.emit("usage_get");
  }
});

if (typeof socket !== "undefined") {
  socket.on("usage_data", (data) => renderUsageSummary(data));
}
