# Changelog — Issue #134

## Avis du coach : formule « pour toi » à côté d'un chiffre signé, sens inversé, verdict sous-évalué (suite #128)

- Mesure du 21/10/2026 sur 26 avis réels (2 IA × 13 exercices, 4 côté
  Blancs) de la version #128 : aucune inversion de signe numérique, mais
  trois défauts de formulation persistaient — (1) « pour toi » encore
  accolé à un chiffre signé dans certains avis malgré l'interdiction déjà
  posée par #128 ; (2) sens inversé de « qui est mieux » malgré des
  chiffres corrects (un avis dit « tu restes légèrement mieux » alors que
  l'évaluation, +148 puis +297, favorise les Blancs pendant qu'Alain joue
  les Noirs) ; (3) verdict sous-évalué, ~5 avis sur 26 ouvrant sur
  « imprécision » alors que le verdict officiel est « erreur » ou « gaffe ».
- `llm_coach.py`, `_SYSTEM_PROMPT` : interdiction étendue à « en ta faveur »/
  « tu restes mieux » (en plus de « pour toi »/« pour Alain » déjà interdits
  par #128) à proximité d'un chiffre signé ; obligation de nommer le camp
  mieux placé par sa couleur, chiffre à l'appui tel quel ; deux mini-exemples
  (un côté Blancs, un côté Noirs) ajoutés.
- `llm_coach.py`, `_EXERCISE_SYSTEM_ADDENDUM` : le mot de qualité qui ouvre
  l'avis doit reprendre exactement le verdict officiel fourni, sans
  l'atténuer — nuance permise seulement après ce premier mot.
- `fact_checker.py` : deux contrôles déterministes ajoutés au mécanisme
  d'alertes existant (`fact_checker_alertes`, issue #117), sans appel IA
  supplémentaire — `_verifier_sens_qui_est_mieux` (contradiction entre une
  phrase « qui est mieux » et le signe réel de l'évaluation ramené au camp
  d'Alain, ou formule « pour toi » accolée à un chiffre signé via
  `_verifier_pour_toi_chiffre_colle`) et `_verifier_mot_verdict_premiere_
  phrase` (mot de verdict de la première phrase différent du verdict
  officiel). Effet de bord : les contrôles de cohérence verdict/texte,
  « qui est mieux » et mot de verdict ne dépendent plus de la présence
  d'une position candidate (FEN) dans le contexte.
- Vérification : nouveau fichier `test_issue134.py` — tests unitaires de
  `fact_checker.py` reproduisant les trois défauts avec les valeurs réelles
  citées par l'issue (et les faux positifs déjà repérés : « bon coup » ~
  « bon », « effondrement en faveur des Noirs », « de +278 à +498 en
  faveur des Blancs ») ; tests appelant directement la vraie fonction de
  production `llm_coach.get_coach_response` avec une API Claude simulée ;
  tests via le client de test Flask-SocketIO et l'infrastructure de
  `test_issue128.py` (chemins de données temporaires, aucune donnée
  personnelle touchée) pour les deux camps. Tous passent (voir rapport de
  clôture pour le détail et les limites — notamment l'impossibilité de
  relire le journal réel du jour, situé hors du périmètre strict du
  worktree de cette issue).
- Documentation : `CONTEXTE.md` (paragraphe « Convention de signe Lichess »)
  et `docs/contexte/convention_signe.md` mis à jour en place (pas de
  nouvelle section « issue #134 » séparée) pour refléter la formulation
  étendue et les deux nouveaux contrôles du vérificateur.
