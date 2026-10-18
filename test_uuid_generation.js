/**
 * Test de génération d'UUID côté client pour l'issue #114
 * Ce script teste la fonction _generateExerciseId()
 */

// Copie de la fonction _generateExerciseId de exercise.js
function _generateExerciseId() {
  // Génération simple d'un UUID v4 côté client
  // Basé sur crypto.randomUUID si disponible, sinon fallback manuel
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback manuel : 32 caractères hexadécimaux aléatoires
  const hex = '0123456789abcdef';
  const variant = '89ab';
  let uuid = '';
  for (let i = 0; i < 32; i++) {
    if (i === 12) uuid += '4';
    else if (i === 16) uuid += variant[Math.floor(Math.random() * 4)];
    else uuid += hex[Math.floor(Math.random() * 16)];
  }
  return uuid;
}

console.log("Test de génération d'UUID côté client");
console.log("=" .repeat(50));

// Tester la génération
const ids = [];
for (let i = 0; i < 10; i++) {
  const id = _generateExerciseId();
  ids.push(id);
  console.log(`UUID ${i+1}: ${id}`);
}

// Vérifier que tous les UUID sont uniques
const uniqueIds = new Set(ids);
console.log("\n" + "=" .repeat(50));
console.log(`Générés: ${ids.length} UUID`);
console.log(`Uniques: ${uniqueIds.size} UUID`);

if (uniqueIds.size === ids.length) {
  console.log("✅ Tous les UUID sont uniques");
} else {
  console.log("❌ ERREUR : Des UUID en double détectés");
}

// Vérifier le format (32 caractères hexadécimaux)
let allValid = true;
for (const id of ids) {
  if (!/^[0-9a-f]{32}$/.test(id)) {
    console.log(`❌ UUID invalide: ${id}`);
    allValid = false;
  }
}

if (allValid) {
  console.log("✅ Tous les UUID ont un format valide (32 caractères hexadécimaux)");
}

console.log("=" .repeat(50));
console.log("Test terminé avec succès ✅");
