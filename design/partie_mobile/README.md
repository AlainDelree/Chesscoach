# Maquette mobile — modes de partie (Claude Design)

Quatorze écrans de 390 x 750 px, dessinés avec Claude Design pour l'interface mobile des modes de partie
(partie pédagogique, et par extension libre, ouverture, finales). Ce dossier est une référence de
DISPOSITION et de COMPORTEMENT, pas du code à copier.

## Contenu
- png/ : capture de chaque écran (ordre de lecture recommandé = ordre des numéros).
  Les captures sont rendues sans accès à Internet : les polices Caprasimo et Figtree ne sont donc pas
  chargées (polices de secours) et les pièces sont des symboles. Se fier à la mise en page, pas à la typographie.
- *.dc.html : sources des écrans (gabarits à expressions {{ ... }}, rendus par support.js).
- support.js : moteur de rendu des gabarits (ne sert qu'à afficher la maquette).
- canvas.json : titres et ordre des écrans.

## Afficher la maquette
Servir ce dossier avec un serveur statique (par exemple `python3 -m http.server 8000`) puis ouvrir
`http://localhost:8000/Main.dc.html` (ou un autre écran) dans un navigateur de taille 390 x 750.
L'ouverture directe d'un fichier n'est pas fiable.

## À NE PAS reprendre
- Couleurs et polices de la maquette (rouille #a8461f, plateau brun, Spectral / Work Sans ou variantes) :
  l'appli a déjà son style (variables --cc-*, polices Caprasimo et Figtree, plateau vert et beige,
  terracotta réservé à ce qui est cliquable).
- Contenu d'exemple : partie, lignes, analyse, compteur de jetons, textes du coach.
- Notation française éventuelle : l'appli est en notation anglaise.
- Compteur de progression de l'analyse (« 7 / 11 demi-coups ») : l'appli n'en a pas.
