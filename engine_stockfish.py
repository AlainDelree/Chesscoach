"""
engine_stockfish.py — ChessCoach (extrait de nicsoft/engine/engine_manager.py, AlChess)

Gardé tel quel (ce module était déjà générique UCI, sans dépendance
pédagogique ni hardware) :
  - la classe EngineManager complète (get_move, evaluate, evaluate_move,
    get_punishment_line, get_multipv, analyser_partie, wdl_to_bar) ;
  - find_stockfish() / stockfish_available().

Retiré (spécifique aux adversaires IA d'AlChess, hors sujet pour un coach
d'analyse assistée par Stockfish) :
  - MaiaEngine, RodentEngine et leurs fonctions de détection
    (find_lc0, find_maia_weights, maia_available, find_rodent,
    rodent_available, _ensure_executable, RODENT_*, MAIA_LEVELS).

Seul changement fonctionnel : l'import de ENGINES_DIR, à câbler côté
ChessCoach (voir NOTES_EXPORT.md).
"""

import chess
import chess.engine
import threading
import logging
from pathlib import Path

# ── À câbler côté ChessCoach ─────────────────────────────────────────────────
# Remplacer cet import par le point d'entrée de config du nouveau projet.
# Valeur attendue : un pathlib.Path pointant vers le dossier contenant les
# exécutables moteurs (ex. Path.home() / "ChessCoach" / "engines").
from config import ENGINES_DIR, SYZYGY_PATH

logger = logging.getLogger("EngineManager")

# ── Seuils d'évaluation (centipawns de perte) ────────────────────────────────
SEUIL_BON         =  50   # < 50cp  → bon coup
SEUIL_IMPRECISION = 100   # 50-100  → imprécision
SEUIL_ERREUR      = 300   # 100-300 → erreur
                          # >= 300  → blunder

# Plage Elo supportée par Stockfish via UCI_Elo
ELO_MIN = 1320
ELO_MAX = 3190
ELO_DEFAUT = 1500

# Force de l'adversaire automatique en mode "partie pédagogique" (issue #8).
# Alain progresse autour de 635-822 Elo chess.com, très en dessous du plancher
# UCI_Elo de Stockfish (1320, déjà écrasant) — on utilise donc "Skill Level"
# (0-20, spécifique à Stockfish), qui injecte de vraies imprécisions plutôt
# que de viser un Elo cible, combiné à un temps de réflexion très court pour
# accentuer l'affaiblissement. Valeur choisie à l'appréciation de CCL (pas
# d'interface de réglage demandée) : le niveau le plus faible disponible.
PEDAGOGIQUE_SKILL_LEVEL = 0
PEDAGOGIQUE_THINK_TIME = 0.1

# Profondeur de réévaluation en temps réel du coup proposé et du meilleur
# coup dans le mode "Exercice" (issue #19) : la profondeur 10 utilisée par
# build_patterns_erreurs.py (issue #2) était un choix de vitesse pour traiter
# 280 parties d'un coup, pas pertinent pour une évaluation ponctuelle en
# cours d'exercice. Mesuré sur cette machine (Stockfish 16) : depth=18 reste
# sous la seconde par appel analyse(), y compris en milieu de partie complexe,
# pour un total de l'ordre de 1-2s en cumulant les deux appels internes
# (avant/après coup) d'evaluate_move.
DEPTH_EXERCICE_TEMPS_REEL = 18

# Profondeur du bouton "Analyser cette partie" (issue #41, mode Bibliothèque/
# Revue PGN) : analyse synchrone d'une partie entière (40-90 demi-coups),
# donc plus rapide que DEPTH_EXERCICE_TEMPS_REEL (une seule position) pour
# rester utilisable en pratique, mais nettement plus profonde que la
# profondeur 10 du lot d'amorçage de build_patterns_erreurs.py (choix de
# vitesse pour traiter 280 parties d'un coup, non pertinent ici pour une
# seule partie à la demande). 16 = milieu de la fourchette 14-18 demandée.
DEPTH_ANALYSE_PARTIE = 16

# Seuil de centipawns au-delà duquel une position donnée au joueur évalué
# (EngineManager.evaluate_move) est considérée comme déjà décidée (issue #75,
# point 2b) : un coup qui conserve un avantage supérieur à ce seuil, avant ET
# après le coup, n'est jamais qualifié d'"erreur" ou de "blunder" (ramené à
# "imprecision" au plus) — même valeur que SEUIL_DEJA_DECISIF dans
# build_patterns_erreurs.py, pour rester cohérent avec le même principe déjà
# appliqué côté amorçage des erreurs détectées.
SEUIL_DECIDE = 600

# Plafond générique du delta_cp reporté par evaluate_move (issue #75,
# reprise de la même convention que build_patterns_erreurs.py/
# _analyse_full_game dans app.py) : au-delà, la magnitude exacte perd son
# sens (position très lopsided, pas forcément un mat) — la classification
# qualite (déjà "blunder" à ce niveau) suffit, la valeur numérique précise
# n'apporte plus d'info utile et risquerait d'être citée telle quelle comme
# un nombre de pions par le coach (voir llm_coach._build_context_text /
# game_facts.describe_perte_cp_clause, qui reformulent en mots au-delà de ce
# plafond).
DELTA_CP_PLAFOND = 1000

# Sentinelle dédiée (issue #75, point 2a) pour le cas précis où le coup
# évalué permet un mat forcé contre le joueur qui vient de jouer : volontai-
# rement hors de l'échelle de DELTA_CP_PLAFOND, pour que la couche de
# présentation (game_facts.describe_perte_cp_clause) la détecte sans
# ambiguïté comme une "grande valeur" à décrire en mots — jamais comme un
# delta de centipawns ordinaire. Avant ce correctif, EngineManager.
# evaluate_move renvoyait "bon", 0 dès qu'un score de mat apparaissait après
# le coup, sans vérifier s'il s'agissait d'un mat EN FAVEUR du joueur ou
# CONTRE lui (constat réel : Ra8, qui autorise Rb1+ Kh2 Rh1# contre Alain,
# recevait le verdict "bon").
DELTA_CP_MAT_CONTRE = 9999

# Seuil d'équivalence pour le jugement du premier coup d'un problème « Lichess »
# (issue #78) : plus strict que SEUIL_BON (50cp) ci-dessus, car un problème
# Lichess a par construction un unique coup correct (coups "uniques" de la
# base) — un coup différent du premier coup de la solution n'est accepté
# comme "réussi" que s'il en est très proche (< 30cp) ou si le garde-fou
# "position déjà décidée" (SEUIL_DECIDE, cf. evaluate_move) s'est déclenché,
# ce qui se reconnaît côté appelant à qualite == "imprecision" avec un
# delta_cp >= SEUIL_IMPRECISION (une imprécision "normale", non dégradée par
# ce garde-fou, reste toujours < SEUIL_IMPRECISION par construction de
# classifier_coup).
SEUIL_PUZZLE_EQUIVALENT_CP = 30


def classifier_coup(delta_cp: int) -> str:
    """Classe un coup selon la perte en centipawns."""
    if delta_cp < SEUIL_BON:
        return "bon"
    elif delta_cp < SEUIL_IMPRECISION:
        return "imprecision"
    elif delta_cp < SEUIL_ERREUR:
        return "erreur"
    else:
        return "blunder"


# Barème unique mat/cp (issue #75) : convertit un score de mat vers la même
# échelle que les centipawns, avec la même formule que build_patterns_
# erreurs.py/_analyse_full_game (app.py) — permet de calculer un delta
# correct même quand le coup évalué transforme une position NON mat en
# position de mat, ou inversement, ce que l'ancienne version de
# EngineManager.evaluate_move traitait à tort comme toujours "bon" (elle
# s'arrêtait dès que l'évaluation après coup était un mat, sans regarder de
# quel côté).
MATE_SCORE_SENTINEL = 100000


def _score_valeur_joueur(eval_info: dict) -> int | None:
    """Valeur unique (mat ou cp) du point de vue du joueur au trait dans la
    position évaluée par EngineManager.evaluate — None si ni l'un ni l'autre
    n'est disponible (position terminale sans score, cas limite)."""
    mate = eval_info.get("mate")
    if mate is not None:
        return MATE_SCORE_SENTINEL - mate if mate > 0 else -MATE_SCORE_SENTINEL - mate
    cp = eval_info.get("cp")
    if cp is not None:
        return cp
    return None


def score_to_cp(score: chess.engine.Score, joueur: chess.Color) -> int | None:
    """
    Convertit un Score python-chess en centipawns du point de vue du joueur.
    Retourne None si c'est un mat.
    """
    if score.is_mate():
        return None
    cp = score.white().score()
    if joueur == chess.WHITE:
        return cp
    else:
        return -cp


class EngineManager:
    """
    Gestionnaire universel de moteur UCI (utilisé ici uniquement avec Stockfish).

    Utilise python-chess pour communiquer avec le moteur UCI.
    Instances internes (les deux dernières lancées à la demande) :
      - _engine_play        : pour calculer les coups (Elo limité, optionnel
                               côté ChessCoach — utile surtout pour un mode
                               "rejoue contre le coach", pas indispensable
                               pour l'analyse)
      - _engine_eval         : pour évaluer les positions (pleine force, rapide)
      - _engine_pedagogique  : adversaire automatique affaibli (issue #8)
      - _engine_finales      : mode "travail de finales" (issue #32), pleine
                               force, sans plafond Elo, tables Syzygy si
                               présentes
    """

    def __init__(self, engine_path: str, engine_elo: int = ELO_DEFAUT,
                 analyse_active: bool = True) -> None:
        self._engine_path   = engine_path
        self._engine_elo    = max(ELO_MIN, min(ELO_MAX, engine_elo))
        self._analyse_active = analyse_active
        self._lock_play     = threading.Lock()
        self._lock_eval     = threading.Lock()

        self._engine_play: chess.engine.SimpleEngine | None = None
        self._engine_eval: chess.engine.SimpleEngine | None = None
        # Troisième instance, lancée à la demande (issue #8, mode "partie
        # pédagogique") : adversaire automatique affaibli via l'option UCI
        # "Skill Level", séparée de _engine_play pour ne jamais affecter le
        # bouton "Coup Stockfish"/case "Stockfish joue auto" du mode partie
        # libre (issue #6) ni l'évaluation du mode exercice (issue #7), qui
        # restent à pleine force.
        self._engine_pedagogique: chess.engine.SimpleEngine | None = None
        self._lock_pedagogique = threading.Lock()
        self._supports_skill_level = False

        # Quatrième instance, lancée à la demande (issue #32, mode "travail de
        # finales", jeu normal et démonstration) : jusqu'ici ce mode réutilisait
        # _engine_play (Elo plafonné ~1500 pour le bouton "Coup Stockfish" du
        # mode partie libre), ce qui dégrade les techniques de mat longues et
        # précises. Instance séparée, sans UCI_LimitStrength, avec accès aux
        # tables de finales Syzygy si présentes (cf. _configure_syzygy).
        self._engine_finales: chess.engine.SimpleEngine | None = None
        self._lock_finales = threading.Lock()

        self._supports_wdl     = False
        self._supports_elo_limit = False
        self._supports_syzygy  = False
        self._engine_name      = "Moteur UCI"

        self._init_engines()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_engines(self) -> None:
        """Lance les deux instances du moteur et détecte les capacités."""
        try:
            self._engine_play = chess.engine.SimpleEngine.popen_uci(self._engine_path)
            self._engine_eval = chess.engine.SimpleEngine.popen_uci(self._engine_path)
            self._engine_name = self._engine_play.id.get("name", "Moteur UCI")

            # Détecter les options supportées
            options = self._engine_play.options
            self._supports_elo_limit = (
                "UCI_LimitStrength" in options and "UCI_Elo" in options
            )
            self._supports_wdl = "UCI_ShowWDL" in options
            self._supports_skill_level = "Skill Level" in options
            self._supports_syzygy = "SyzygyPath" in options

            # Configurer le moteur de jeu (Elo limité)
            self._apply_elo(self._engine_play)
            self._configure_syzygy(self._engine_play)

            # Configurer le moteur d'évaluation (pleine force, rapide)
            if self._supports_wdl:
                self._engine_eval.configure({"UCI_ShowWDL": True})
            self._configure_syzygy(self._engine_eval)

            logger.info(f"Moteur : {self._engine_name}")
            logger.info(f"Elo limité : {self._supports_elo_limit} | WDL : {self._supports_wdl} | Syzygy : {self._supports_syzygy}")

        except Exception as e:
            logger.error(f"Impossible de lancer le moteur : {e}")
            raise

    def _apply_elo(self, engine: chess.engine.SimpleEngine) -> None:
        """Applique la limitation de force Elo sur une instance du moteur."""
        if self._supports_elo_limit:
            engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": self._engine_elo,
            })
            if self._supports_wdl:
                engine.configure({"UCI_ShowWDL": True})
        else:
            # Fallback : moteur sans UCI_Elo → pas de limitation de force
            logger.warning(f"{self._engine_name} ne supporte pas UCI_Elo.")

    def _configure_syzygy(self, engine: chess.engine.SimpleEngine) -> None:
        """Configure l'option UCI SyzygyPath sur une instance si des fichiers
        de tables de finales sont présents dans SYZYGY_PATH (issue #32).
        Dégradation gracieuse si le dossier est vide ou absent (même
        pattern que le livre Polyglot, issue #9) : log informatif, pas
        d'erreur — les tables ne sont pas indispensables au fonctionnement."""
        if not self._supports_syzygy:
            return
        try:
            a_des_fichiers = SYZYGY_PATH.is_dir() and any(
                p.is_file() for p in SYZYGY_PATH.iterdir()
            )
        except OSError:
            a_des_fichiers = False
        if a_des_fichiers:
            engine.configure({"SyzygyPath": str(SYZYGY_PATH)})
        else:
            logger.info(f"SyzygyPath vide ou absent ({SYZYGY_PATH}) — tables de finales Syzygy non utilisées.")

    # ── API publique ──────────────────────────────────────────────────────────

    @property
    def engine_name(self) -> str:
        return self._engine_name

    @property
    def engine_elo(self) -> int:
        return self._engine_elo

    @property
    def analyse_active(self) -> bool:
        return self._analyse_active

    @analyse_active.setter
    def analyse_active(self, value: bool) -> None:
        self._analyse_active = value

    def set_elo(self, elo: int) -> None:
        """Change le niveau Elo du moteur de jeu à chaud."""
        self._engine_elo = max(ELO_MIN, min(ELO_MAX, elo))
        with self._lock_play:
            if self._engine_play:
                self._apply_elo(self._engine_play)

    def get_move(self, board: chess.Board, think_time: float = 1.0) -> chess.Move | None:
        """
        Demande le meilleur coup au moteur de jeu (Elo limité).

        Paramètres :
          board      : position actuelle
          think_time : temps de réflexion en secondes

        Retourne le coup ou None en cas d'erreur.
        """
        with self._lock_play:
            if not self._engine_play:
                return None
            try:
                result = self._engine_play.play(
                    board,
                    chess.engine.Limit(time=think_time),
                )
                return result.move
            except Exception as e:
                logger.error(f"Erreur get_move : {e}")
                return None

    def _ensure_engine_pedagogique(self) -> None:
        """Lance à la demande la 3e instance, dédiée à l'adversaire automatique
        du mode "partie pédagogique" (issue #8) — pas de coût tant que ce mode
        n'est pas utilisé."""
        if self._engine_pedagogique:
            return
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self._engine_path)
            if self._supports_skill_level:
                engine.configure({
                    "UCI_LimitStrength": False,
                    "Skill Level": PEDAGOGIQUE_SKILL_LEVEL,
                })
            else:
                logger.warning(f"{self._engine_name} ne supporte pas Skill Level.")
            self._configure_syzygy(engine)
            self._engine_pedagogique = engine
        except Exception as e:
            logger.error(f"Impossible de lancer le moteur pédagogique : {e}")
            self._engine_pedagogique = None

    def get_move_pedagogique(self, board: chess.Board,
                              think_time: float = PEDAGOGIQUE_THINK_TIME) -> chess.Move | None:
        """Demande un coup à l'adversaire automatique affaibli du mode "partie
        pédagogique" (issue #8) — instance séparée de get_move(), qui reste à
        la disposition du mode partie libre à pleine force inchangée."""
        with self._lock_pedagogique:
            self._ensure_engine_pedagogique()
            if not self._engine_pedagogique:
                return None
            try:
                result = self._engine_pedagogique.play(
                    board,
                    chess.engine.Limit(time=think_time),
                )
                return result.move
            except Exception as e:
                logger.error(f"Erreur get_move_pedagogique : {e}")
                return None

    def _ensure_engine_finales(self) -> None:
        """Lance à la demande la 4e instance, dédiée au mode "travail de
        finales" (jeu normal et démonstration, issue #32) — pas de coût tant
        que ce mode n'est pas utilisé. Pleine force, sans UCI_LimitStrength,
        contrairement à _engine_play (Elo plafonné ~1500, dédié au bouton
        "Coup Stockfish" du mode partie libre) que ce mode réutilisait par
        erreur jusqu'ici, dégradant les techniques de mat longues et
        précises."""
        if self._engine_finales:
            return
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self._engine_path)
            if self._supports_elo_limit:
                engine.configure({"UCI_LimitStrength": False})
            if self._supports_wdl:
                engine.configure({"UCI_ShowWDL": True})
            self._configure_syzygy(engine)
            self._engine_finales = engine
        except Exception as e:
            logger.error(f"Impossible de lancer le moteur du mode finales : {e}")
            self._engine_finales = None

    def get_move_finales(self, board: chess.Board, think_time: float = 1.0) -> chess.Move | None:
        """Demande un coup pour le mode "travail de finales" (jeu normal et
        démonstration, issue #32) — instance dédiée à pleine force, plus
        adaptée aux mats techniques longs (ex. cavalier+fou, jusqu'à 33 coups)
        que get_move(), qui reste Elo limité pour le mode partie libre."""
        with self._lock_finales:
            self._ensure_engine_finales()
            if not self._engine_finales:
                return None
            try:
                result = self._engine_finales.play(
                    board,
                    chess.engine.Limit(time=think_time),
                )
                return result.move
            except Exception as e:
                logger.error(f"Erreur get_move_finales : {e}")
                return None

    def evaluate(self, board: chess.Board, depth: int = 8, time_limit: float | None = None) -> dict:
        """
        Évalue une position avec le moteur d'évaluation (pleine force).

        Paramètres :
          depth      : profondeur de recherche (défaut, ignoré si time_limit
                       est fourni).
          time_limit : si fourni (secondes), borne la recherche en temps
                       plutôt qu'en profondeur (issue #57, vérification
                       Stockfish courte et bornée d'un moment clé du chat
                       coach — la profondeur seule ne garantit pas un temps
                       de calcul borné sur une position complexe, alors que
                       Stockfish respecte lui-même un temps de recherche
                       donné via movetime, sans thread de timeout externe).

        Retourne un dict :
          {
            "cp"      : int | None,   # centipawns du point de vue du joueur actif
            "mate"    : int | None,   # coups avant mat (négatif = on se fait mater)
            "wdl"     : (int, int, int) | None,  # (victoire, nulle, défaite) /1000
            "best_move": str | None,  # meilleur coup UCI
          }
        """
        with self._lock_eval:
            if not self._engine_eval:
                return {"cp": None, "mate": None, "wdl": None, "best_move": None}
            try:
                limit = chess.engine.Limit(time=time_limit) if time_limit else chess.engine.Limit(depth=depth)
                info = self._engine_eval.analyse(
                    board,
                    limit,
                    info=chess.engine.INFO_ALL,
                )
                score = info.get("score")
                pv    = info.get("pv", [])

                cp   = None
                mate = None
                wdl  = None

                if score:
                    pov_score = score.pov(board.turn)
                    if pov_score.is_mate():
                        mate = pov_score.mate()
                    else:
                        cp = pov_score.score()
                    # WDL du point de vue du joueur actif
                    if self._supports_wdl and score.wdl():
                        w = score.wdl().pov(board.turn)
                        wdl = (w.wins, w.draws, w.losses)

                best_move = pv[0].uci() if pv else None

                # Ligne complète calculée par le moteur (pas seulement son
                # premier coup), gardée en objets chess.Move bruts — issue #20 :
                # evaluate_move s'en sert pour reconstituer en SAN la suite
                # réellement calculée par Stockfish, à transmettre au coach.
                return {"cp": cp, "mate": mate, "wdl": wdl, "best_move": best_move, "pv": pv}

            except Exception as e:
                logger.error(f"Erreur evaluate : {e}")
                return {"cp": None, "mate": None, "wdl": None, "best_move": None, "pv": []}

    def _pv_to_san(self, board: chess.Board, moves: list[chess.Move]) -> str:
        """Convertit une suite de coups (objets chess.Move, calculés par le
        moteur depuis `board`) en SAN lisible, coups séparés par des espaces
        (issue #20). S'arrête proprement au premier coup qui ne serait plus
        légal (fin de PV, ou décalage lié à la copie du plateau) plutôt que de
        lever une exception."""
        b = board.copy()
        sans = []
        for m in moves:
            if m not in b.legal_moves:
                break
            sans.append(b.san(m))
            b.push(m)
        return " ".join(sans)

    def evaluate_move(self, board: chess.Board, move: chess.Move,
                      depth: int = 8,
                      always_return_best: bool = False,
                      return_pv: bool = False,
                      pv_max_plies: int = 6,
                      time_limit: float | None = None) -> tuple[str, int, str | None]:
        """
        Évalue la qualité d'un coup joué.

        Paramètres :
          time_limit : si fourni (secondes), transmis tel quel aux deux
            appels internes à evaluate() (avant/après coup) à la place de
            depth — même usage que evaluate() (issue #57, vérification
            Stockfish courte et bornée du chat coach).
          always_return_best : si True, le 3e élément retourné est toujours
            le meilleur coup UCI pour la position AVANT le coup, même quand
            il coïncide avec le coup joué (au lieu de None dans ce cas — cf.
            comportement historique ci-dessous, conservé par défaut pour ne
            pas changer le contrat des appelants existants). Utile quand
            l'appelant a besoin du "meilleur coup" affichable pour la
            position, pas seulement d'une alternative à mettre en avant
            (issue #19, mode "Exercice" : meilleur coup et verdict du coup
            proposé doivent provenir du même appel moteur, à la même
            profondeur).
          return_pv : si True, ajoute un 4e élément au tuple retourné (cf.
            ci-dessous) — la ligne (PV) réellement calculée par Stockfish
            pour le coup proposé et pour le meilleur coup, en SAN (issue #20 :
            le coach doit justifier une continuation réellement calculée,
            pas improviser une explication tactique en prose à partir du
            seul verdict chiffré). Désactivé par défaut pour ne pas changer
            le contrat des appelants existants (ex. analyser_partie).
          pv_max_plies : nombre de demi-coups conservés dans chaque ligne
            retournée quand return_pv=True (au-delà, la PV Stockfish à
            depth=18 devient inutilement longue pour un commentaire).

        Retourne (qualite, delta_cp, best_move_uci) ou, si return_pv=True,
        (qualite, delta_cp, best_move_uci, pv_info) où pv_info est
        {"pv_coup_propose": str, "pv_meilleur_coup": str} (SAN, "" si
        indisponible) :
          - qualite    : "bon" / "imprecision" / "erreur" / "blunder"
          - delta_cp   : perte en centipawns (0 = parfait), plafonnée à
            DELTA_CP_PLAFOND — ou DELTA_CP_MAT_CONTRE (sentinelle dédiée,
            hors échelle) quand ce coup permet un mat forcé contre le joueur
            (issue #75, point 2a)
          - best_move  : par défaut, meilleur coup UCI si différent du coup
            joué, sinon None ; toujours le meilleur coup si
            always_return_best=True (cf. ci-dessus)

        Issue #75 : la qualité et le delta sont désormais calculés sur un
        barème unique mat/cp (_score_valeur_joueur, même formule que
        build_patterns_erreurs.py/_analyse_full_game), plutôt que de
        toujours renvoyer "bon"/0 dès que l'évaluation après coup est un
        score de mat — l'ancien code ne distinguait pas un mat EN FAVEUR du
        joueur d'un mat CONTRE lui (constat réel : Ra8, qui autorise
        Rb1+ Kh2 Rh1# contre Alain, recevait le verdict "bon"). Deux
        garde-fous s'ajoutent à ce calcul uniforme :
          - position déjà décidée (point 2b) : un coup qui conserve un
            avantage supérieur à SEUIL_DECIDE, avant ET après le coup, est
            ramené à "imprecision" au plus, même si le delta technique est
            important (ex. Rf6+ dans une finale déjà gagnée) ;
          - mat forcé contre le joueur après ce coup (point 2a) : toujours
            "blunder", y compris quand le garde-fou "position déjà décidée"
            s'appliquerait sinon (un coup qui transforme un mat forcé EN
            FAVEUR du joueur en mat forcé CONTRE lui reste une gaffe,
            jamais relativisée).
        """
        if not self._analyse_active:
            if return_pv:
                return "bon", 0, None, {"pv_coup_propose": "", "pv_meilleur_coup": ""}
            return "bon", 0, None

        try:
            # Évaluation AVANT le coup
            eval_avant = self.evaluate(board, depth=depth, time_limit=time_limit)
            best_move  = eval_avant["best_move"]
            pv_avant   = eval_avant.get("pv") or []
            val_avant  = _score_valeur_joueur(eval_avant)

            # Évaluation APRÈS le coup — toujours calculée (issue #75) :
            # l'ancien raccourci qui la sautait quand la position était déjà
            # "mat forcé" avant le coup (et que return_pv=False) empêchait de
            # détecter qu'un coup, depuis une position déjà gagnante par
            # mat, pouvait transformer ce mat EN FAVEUR du joueur en mat
            # CONTRE lui.
            board_apres = board.copy()
            board_apres.push(move)
            eval_apres = self.evaluate(board_apres, depth=depth, time_limit=time_limit)
            pv_apres   = eval_apres.get("pv") or []
            val_apres_adversaire = _score_valeur_joueur(eval_apres)
            val_apres_joueur = -val_apres_adversaire if val_apres_adversaire is not None else None

            def _finish(qualite_f, delta_f, best_f):
                if return_pv:
                    pv_meilleur = self._pv_to_san(board, pv_avant[:pv_max_plies])
                    pv_propose  = self._pv_to_san(board, [move] + pv_apres[:max(0, pv_max_plies - 1)])
                    return qualite_f, delta_f, best_f, {"pv_coup_propose": pv_propose, "pv_meilleur_coup": pv_meilleur}
                return qualite_f, delta_f, best_f

            if val_avant is None or val_apres_joueur is None:
                # Position terminale ou évaluation indisponible (cas limite,
                # ne devrait pas arriver en pratique sur un coup légal) :
                # repli neutre.
                return _finish("bon", 0, best_move if always_return_best else None)

            delta_brut = max(0, val_avant - val_apres_joueur)
            delta   = min(delta_brut, DELTA_CP_PLAFOND)
            qualite = classifier_coup(delta)

            # Position déjà décidée en faveur du joueur, avant ET après le
            # coup (issue #75, point 2b).
            if qualite in ("erreur", "blunder") and val_avant >= SEUIL_DECIDE and val_apres_joueur >= SEUIL_DECIDE:
                qualite = "imprecision"

            # Mat forcé contre le joueur après ce coup (issue #75, point 2a)
            # : toujours une gaffe, jamais adoucie par le garde-fou
            # ci-dessus — vérifié directement sur le signe du score de mat
            # après coup (plus fiable que la seule magnitude du delta).
            mate_apres_adversaire = eval_apres.get("mate")
            if mate_apres_adversaire is not None and mate_apres_adversaire > 0:
                qualite = "blunder"
                delta   = DELTA_CP_MAT_CONTRE

            best = best_move if best_move and best_move != move.uci() else None

            # Si coup mauvais mais pas de meilleur coup alternatif trouvé,
            # relancer en MultiPV=2 pour obtenir le vrai meilleur coup
            if qualite != "bon" and best is None:
                try:
                    with self._lock_eval:
                        info_mpv = self._engine_eval.analyse(
                            board,
                            chess.engine.Limit(depth=depth),
                            multipv=2,
                        )
                    if isinstance(info_mpv, list):
                        for entry in info_mpv:
                            pv = entry.get("pv", [])
                            if pv and pv[0].uci() != move.uci():
                                best = pv[0].uci()
                                break
                except Exception as e:
                    logger.warning(f"MultiPV fallback échoué : {e}")

            best_final = (best if best is not None else best_move) if always_return_best else best
            return _finish(qualite, delta, best_final)

        except Exception as e:
            logger.error(f"Erreur evaluate_move : {e}")
            if return_pv:
                return "bon", 0, None, {"pv_coup_propose": "", "pv_meilleur_coup": ""}
            return "bon", 0, None

    def get_punishment_line(self, board: chess.Board, move: chess.Move,
                             depth: int = 12, max_moves: int = 3) -> list[str]:
        """
        Retourne la ligne punitive après un coup humain.
        """
        with self._lock_eval:
            if not self._engine_eval:
                return []
            try:
                board_after = board.copy()
                board_after.push(move)
                info = self._engine_eval.analyse(
                    board_after,
                    chess.engine.Limit(depth=depth),
                    info=chess.engine.INFO_PV,
                )
                pv = info.get("pv", [])
                result = [m.uci() for m in pv[:max_moves]]
                logger.debug(f"get_punishment_line: {result}")
                return result
            except Exception as e:
                logger.error(f"Erreur get_punishment_line : {e}")
                return []

    def get_multipv(self, board: chess.Board, n: int = 3,
                    depth: int = 12) -> list[dict]:
        """
        Retourne les n meilleurs coups avec leur évaluation.
        Utile pour l'écran d'analyse.

        Retourne une liste de dict :
          [{"move": str (UCI), "cp": int, "mate": int | None}, ...]
        """
        with self._lock_eval:
            if not self._engine_eval:
                return []
            try:
                infos = self._engine_eval.analyse(
                    board,
                    chess.engine.Limit(depth=depth),
                    multipv=n,
                    info=chess.engine.INFO_ALL,
                )
                result = []
                for info in infos:
                    pv    = info.get("pv", [])
                    score = info.get("score")
                    if not pv:
                        continue
                    move_uci = pv[0].uci()
                    cp   = None
                    mate = None
                    if score:
                        pov = score.pov(board.turn)
                        if pov.is_mate():
                            mate = pov.mate()
                        else:
                            cp = pov.score()
                    result.append({"move": move_uci, "cp": cp, "mate": mate})
                return result
            except Exception as e:
                logger.error(f"Erreur get_multipv : {e}")
                return []

    def analyser_partie(self, moves_uci: list[str],
                        callback=None,
                        seq_moves: int = 3) -> list[dict]:
        """
        Analyse une liste de coups UCI.

        Paramètres :
          moves_uci : liste de coups UCI
          callback  : fonction(idx, total, résultat) appelée après chaque coup
          seq_moves : nombre de coups de la séquence punitive (3-5)

        Retourne une liste de dict :
          [{"qualite": str, "delta_cp": int, "best_move": str | None,
            "punishment_line": list[str], "fen_avant_coup": str}, ...]
        """
        board     = chess.Board()
        resultats = []
        total     = len(moves_uci)

        for idx, uci in enumerate(moves_uci):
            try:
                move = chess.Move.from_uci(uci)
                fen_avant = board.fen()
                qualite, delta, best = self.evaluate_move(board, move, depth=8)
                # Calculer la séquence punitive pour les coups non-bons
                punishment_line = []
                if qualite != "bon" and best:
                    punishment_line = self.get_punishment_line(
                        board, move, depth=12, max_moves=seq_moves
                    )
                res = {
                    "qualite":          qualite,
                    "delta_cp":         delta,
                    "best_move":        best,
                    "punishment_line":  punishment_line,
                    "fen_avant_coup":   fen_avant,
                }
                board.push(move)
            except Exception:
                res = {
                    "qualite":         "bon",
                    "delta_cp":        0,
                    "best_move":       None,
                    "punishment_line": [],
                    "fen_avant_coup":  board.fen(),
                }

            resultats.append(res)
            if callback:
                callback(idx, total, res)

        return resultats

    def wdl_to_bar(self, wdl: tuple[int, int, int] | None) -> dict:
        """
        Convertit un tuple WDL en pourcentages pour la barre d'affichage.

        Retourne :
          {"win": float, "draw": float, "loss": float}
          ou None si WDL non disponible.
        """
        if not wdl:
            return None
        w, d, l = wdl
        total = w + d + l
        if total == 0:
            return None
        return {
            "win":  round(w / total * 100, 1),
            "draw": round(d / total * 100, 1),
            "loss": round(l / total * 100, 1),
        }

    def quit(self) -> None:
        """Arrête proprement les instances du moteur."""
        for engine in [self._engine_play, self._engine_eval, self._engine_pedagogique, self._engine_finales]:
            if engine:
                try:
                    engine.quit()
                except Exception:
                    pass
        self._engine_play = None
        self._engine_eval = None
        self._engine_pedagogique = None
        self._engine_finales = None


# ── Fonction utilitaire ───────────────────────────────────────────────────────

def find_stockfish() -> str | None:
    """
    Cherche l'exécutable Stockfish sur le système.
    Retourne le chemin ou None si introuvable.
    """
    import sys
    import shutil
    # Windows : glob stockfish*.exe dans engines/
    if sys.platform == "win32":
        for p in sorted(ENGINES_DIR.rglob("stockfish*.exe")):
            return str(p)
    candidates = [
        shutil.which("stockfish"),
        str(ENGINES_DIR / "stockfish"),
        "/usr/games/stockfish",
        "/usr/bin/stockfish",
        "/usr/local/bin/stockfish",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def stockfish_available() -> bool:
    """Retourne True si Stockfish est présent sur le système (vérification fichier)."""
    return find_stockfish() is not None
