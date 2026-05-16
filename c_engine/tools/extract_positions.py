"""Extract FEN positions from PGN games for NNUE data collection.

Requires python-chess:

    pip install -r tools/requirements-training.txt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import chess
    import chess.pgn
except ImportError as exc:  # pragma: no cover - only hit when dependency is missing.
    raise SystemExit(
        "Missing dependency: python-chess. Install with:\n"
        "  pip install -r tools/requirements-training.txt"
    ) from exc


def should_keep_position(board: chess.Board, ply: int, skip_ply: int, sample_every: int) -> bool:
    if ply < skip_ply:
        return False
    if sample_every > 1 and (ply - skip_ply) % sample_every != 0:
        return False
    if board.is_game_over(claim_draw=True):
        return False
    if board.is_checkmate() or board.is_stalemate():
        return False
    return True


def normalize_fen(board: chess.Board) -> str:
    # Keep side-to-move, castling, and en passant information. Drop clocks so
    # the same chess position deduplicates cleanly for evaluator training.
    parts = board.fen(en_passant="fen").split()
    return " ".join(parts[:4] + ["0", "1"])


def extract_positions(
    pgn_path: Path,
    out_path: Path,
    skip_ply: int,
    sample_every: int,
    max_positions_per_game: int,
    max_positions: int | None,
) -> tuple[int, int, int]:
    seen: set[str] = set()
    game_count = 0
    written = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pgn_path.open("r", encoding="utf-8", errors="replace") as pgn_file, out_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as output:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1

            board = game.board()
            kept_for_game = 0
            for ply, move in enumerate(game.mainline_moves(), start=1):
                board.push(move)
                if not should_keep_position(board, ply, skip_ply, sample_every):
                    continue

                fen = normalize_fen(board)
                if fen in seen:
                    continue
                seen.add(fen)

                record = {
                    "fen": fen,
                    "source": "pgn",
                    "game": game_count,
                    "ply": ply,
                    "white": game.headers.get("White", ""),
                    "black": game.headers.get("Black", ""),
                    "result": game.headers.get("Result", ""),
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
                kept_for_game += 1

                if max_positions is not None and written >= max_positions:
                    return game_count, written, len(seen)
                if max_positions_per_game and kept_for_game >= max_positions_per_game:
                    break

    return game_count, written, len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract unique FEN positions from a PGN file.")
    parser.add_argument("--pgn", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--skip-ply", type=int, default=8, help="Skip early opening plies")
    parser.add_argument("--sample-every", type=int, default=4, help="Keep one position every N plies")
    parser.add_argument("--max-per-game", type=int, default=32, help="Maximum positions extracted per game")
    parser.add_argument("--max-positions", type=int, help="Stop after this many positions")
    args = parser.parse_args()

    game_count, written, unique = extract_positions(
        pgn_path=args.pgn,
        out_path=args.out,
        skip_ply=args.skip_ply,
        sample_every=max(1, args.sample_every),
        max_positions_per_game=max(0, args.max_per_game),
        max_positions=args.max_positions,
    )

    print(f"games read: {game_count}")
    print(f"positions written: {written}")
    print(f"unique positions seen: {unique}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
