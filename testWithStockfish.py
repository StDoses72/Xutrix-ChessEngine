import chess
import chess.engine
import json
import time
from pathlib import Path

ENGINE_PATH = r"D:\Study\ChessEngine\stockfish\stockfish-windows-x86-64.exe"
DEPTH = 10
OUTPUT_DIR = Path("./tables_safe")
OUTPUT_DIR.mkdir(exist_ok=True)
PIECES = ["P", "N", "B", "R", "Q", "K"]
SAFE_KING_PAIRS = [(chess.A1, chess.H8), (chess.A8, chess.H1)]

def kings_are_adjacent(wk, bk):
    wr, wc = divmod(wk, 8)
    br, bc = divmod(bk, 8)
    return abs(wr - br) <= 1 and abs(wc - bc) <= 1

def build_position(piece_symbol, square):
    board = chess.Board.empty()
    rank = chess.square_rank(square)
    if piece_symbol in ["P", "p"] and (rank == 0 or rank == 7):
        return None
    if piece_symbol == "K":
        wk = square
        bk = chess.H8 if not kings_are_adjacent(square, chess.H8) else chess.A8
        board.set_piece_at(wk, chess.Piece.from_symbol("K"))
        board.set_piece_at(bk, chess.Piece.from_symbol("k"))
        return board if board.is_valid() else None
    for wk, bk in SAFE_KING_PAIRS:
        if square in (wk, bk):
            continue
        if kings_are_adjacent(wk, bk):
            continue
        board.clear()
        board.set_piece_at(wk, chess.Piece.from_symbol("K"))
        board.set_piece_at(bk, chess.Piece.from_symbol("k"))
        board.set_piece_at(square, chess.Piece.from_symbol(piece_symbol))
        if board.is_valid():
            return board
    return None

def evaluate_piece_on_square(engine, piece_symbol, square):
    board = build_position(piece_symbol, square)
    if board is None:
        return None
    try:
        info = engine.analyse(board, chess.engine.Limit(depth=DEPTH))
        score = info["score"].pov(chess.WHITE).score(mate_score=100000)
        return score
    except Exception:
        return None

def run_for_piece(engine_path, piece_symbol):
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    table = [[None for _ in range(8)] for _ in range(8)]
    counter = 0
    try:
        for rank in range(8):
            for file in range(8):
                sq = chess.square(file, rank)
                score = evaluate_piece_on_square(engine, piece_symbol, sq)
                table[7 - rank][file] = score
                counter += 1
                if counter % 16 == 0:
                    print(f"{piece_symbol} {counter}/64")
                time.sleep(0.05)
    finally:
        engine.quit()
    outpath = OUTPUT_DIR / f"{piece_symbol.lower()}_table.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({piece_symbol: table}, f, indent=2)
    print(f"{piece_symbol} -> {outpath}")

def main():
    for p in PIECES:
        run_for_piece(ENGINE_PATH, p)
    print("done")

if __name__ == "__main__":
    main()