#!/usr/bin/env python3

"""
Script qui génère des puzzles d'échecs à partir d'un historique de parties

1) Le script va chercher les parties au format PGN grâce à l'API publique de chess.com
2) Il génère un fichier PGN par partie trouvée
3) Il analyse chaque PGN en cherchant des pics dans les évaluations pour trouver des erreurs
4) Il retourne une position au format FEN avec l'erreur la plus critique pour chaque partie
5) On peut ensuite copier cette position sur n'importe quel moteur d'échecs pour la rejouer
"""

import requests
import chess
import chess.pgn
import chess.engine
from io import StringIO
import os

STOCKFISH_PATH = "stockfish"
DEPTH = 14

BLUNDER_THRESHOLD = 1.5       # Perte minimale pour considérer une erreur
MIN_ADVANTAGE_BEFORE = 0.8    # Avantage minimal avant le coup
MAX_ADVANTAGE_AFTER = 4.0     # Pas grave de rater une tactique si l'avantage est encore au moins à +4 après
MATE_SCORE = 900             


# ------------------------------------------------
# UTILITAIRES
# ------------------------------------------------

def to_pawns(score_obj, pov_white: bool) -> float:
    """
    Convertit un PovScore en valeur en pions du point de vue des blancs.
    Les mats sont capés pour éviter les délires arithmétiques.
    """
    if score_obj.is_mate():
        mate_in = score_obj.white().mate()
        return MATE_SCORE if mate_in > 0 else -MATE_SCORE
    return score_obj.white().score() / 100.0


def score_for_player(score_pawns: float, is_white: bool) -> float:
    """Retourne le score du point de vue du joueur actif."""
    return score_pawns if is_white else -score_pawns


def puzzle_quality(score_before_player: float, loss: float, score_after_player: float) -> float:
    """
    Score de 'qualité de puzzle' :
    - une perte significative dans l'évaluation
    - un avantage clair AVANT
    - un résultat clairement détérioré APRÈS
    - on pénalise les positions où c'est encore très gagnant après le coup
    """
    if score_before_player < MIN_ADVANTAGE_BEFORE:
        return -1.0  # Position pas assez avantageuse donc pas une tactique ratée

    # Pénalité si la position reste très confortable après le coup
    comfort_penalty = max(0, score_after_player - 1.5) * 0.5

    # Bonus si on rate depuis une position clairement gagnante
    tactical_bonus = min(score_before_player, 8.0) * 0.3

    return loss - comfort_penalty + tactical_bonus


# ------------------------------------------------
# 1) RÉCUPÉRATION ET SAUVEGARDE DES PGN
# ------------------------------------------------

def fetch_and_save(username, year, month):
    url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}/pgn"
    print("Fetching PGN...")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    pgn_text = r.text
    pgn_io = StringIO(pgn_text)
    count = 0

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        count += 1
        filename = f"{year}-{month:02d}-{count:03d}.pgn"
        with open(filename, "w") as f:
            exporter = chess.pgn.FileExporter(f)
            game.accept(exporter)

    print(f"{count} parties sauvegardées\n")


# ------------------------------------------------
# 2) ANALYSE DES FICHIERS PGN
# ------------------------------------------------

def analyze_pgn_files(year, month, username):
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    results = []

    files = sorted([
        f for f in os.listdir()
        if f.endswith(".pgn") and f.startswith(f"{year}-{month:02d}")
    ])

    print(f"{len(files)} fichiers PGN trouvés\n")

    for file in files:
        print(f"Analyse de {file} ...")

        with open(file) as f:
            game = chess.pgn.read_game(f)

        if game is None:
            continue

        white_player = game.headers.get("White", "").lower()
        black_player = game.headers.get("Black", "").lower()

        if username.lower() == white_player:
            player_is_white = True
        elif username.lower() == black_player:
            player_is_white = False
        else:
            player_is_white = None

        board = game.board()
        best_candidate = None
        best_quality = -999

        moves = list(game.mainline_moves())

        # On ignore les 5 premiers coups et les 3 derniers
        skip_start = 5
        skip_end = max(0, len(moves) - 3)

        for i, move in enumerate(moves):
            is_white_turn = board.turn == chess.WHITE

            # On n'analyse que les coups du joueur cible
            if player_is_white is not None:
                if is_white_turn != player_is_white:
                    board.push(move)
                    continue

            if i < skip_start or i >= skip_end:
                board.push(move)
                continue

            fen_before = board.fen()

            # Évaluation AVANT
            info_before = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
            score_before_white = to_pawns(info_before["score"], True)
            score_before_player = score_for_player(score_before_white, is_white_turn)

            # Meilleur coup selon le moteur
            best_move = info_before.get("pv", [None])[0]
            best_move_san = board.san(best_move) if best_move else "?"

            # Jouer le coup
            move_san = board.san(move)
            board.push(move)

            # Évaluation APRÈS
            info_after = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
            score_after_white = to_pawns(info_after["score"], True)
            score_after_player = score_for_player(score_after_white, is_white_turn)

            # Perte réelle du joueur
            loss = score_before_player - score_after_player

            if loss < BLUNDER_THRESHOLD:
                continue

            quality = puzzle_quality(score_before_player, loss, score_after_player)

            if quality > best_quality:
                best_quality = quality
                turn_label = "White" if is_white_turn else "Black"

                # Label descriptif
                if score_before_player > 5:
                    label = "Mat ou gain net raté"
                elif score_before_player > 2:
                    label = "Position gagnante ratée"
                elif score_before_player > 0.8:
                    label = "Avantage gaspillé"
                else:
                    label = "Blunder"

                best_candidate = {
                    "file": file,
                    "fen": fen_before,
                    "turn": turn_label,
                    "move_played": move_san,         
                    "best_move": best_move_san,        
                    "score_before": round(score_before_player, 2),
                    "score_after": round(score_after_player, 2),
                    "loss": round(loss, 2),
                    "label": label,
                    "quality": round(quality, 2),
                }

        if best_candidate:
            results.append(best_candidate)
            print(
                f"  ⚠️  Coup {best_candidate['move_played']} | "
                f"Perte: {best_candidate['loss']:+.2f} | {best_candidate['label']}"
            )
        else:
            print("  ✅ Aucune gaffe significative trouvée")

    engine.quit()
    return results


# ------------------------------------------------
# 3) SAUVEGARDE AU FORMAT FEN
# ------------------------------------------------

def save_fens(results, year, month):
    filename = f"FEN-{year}-{month:02d}.txt"
    with open(filename, "w") as f:
        for item in results:
            f.write(
                f"{item['fen']} | "
                f"{item['turn']} to move | "
                f"Joué : {item['move_played']} | "
                f"Meilleur : {item['best_move']} | "
                f"Évaluation avant : {item['score_before']:+.2f} | "
                f"Évaluation : {item['score_after']:+.2f} | "
                f"{item['label']}\n"
            )
    print(f"\n{len(results)} puzzles sauvegardés dans {filename}")


# ------------------------------------------------
# MAIN
# ------------------------------------------------

def main():
    username = input("Nom sur chess.com : ").strip()
    year = int(input("Année : "))
    month = int(input("Mois : "))

    fetch_and_save(username, year, month)

    results = analyze_pgn_files(year, month, username)

    print("\nTactiques ratées (une par partie) :\n")
    for r in results:
        print(f"  📄 {r['file']}")
        print(f"  FEN    : {r['fen']}")
        print(f"  Tour   : {r['turn']} to move")
        print(f"  Joué   : {r['move_played']}")
        print(f"  Évaluation   : {r['score_before']:+.2f} → {r['score_after']:+.2f}  (perte : {r['loss']:+.2f})")
        print(f"  Type   : {r['label']}")
        print()

    if results:
        save_fens(results, year, month)


if __name__ == "__main__":
    main()
