"""Label FEN positions with Stockfish centipawn evaluations.

Input JSONL:

    {"fen": "...", ...}

Default output JSONL, intentionally clean for PyTorch:

    {"fen": "...", "score": 37}

Use --include-meta if you want trace fields such as source, ply, and label depth.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

try:
    import chess
    import chess.engine
except ImportError as exc:  # pragma: no cover - only hit when dependency is missing.
    raise SystemExit(
        "Missing dependency: python-chess. Install with:\n"
        "  pip install -r tools/requirements-training.txt"
    ) from exc


def find_stockfish(explicit_path: str | None) -> str:
    candidates: list[str] = []
    if explicit_path:
        candidates.append(explicit_path)
    env_path = os.environ.get("STOCKFISH_EXE")
    if env_path:
        candidates.append(env_path)

    path_hit = shutil.which("stockfish")
    if path_hit:
        candidates.append(path_hit)

    common_paths = [
        str(Path(__file__).resolve().parent / "stockfish" / "stockfish.exe"),
        r"C:\stockfish\stockfish.exe",
        r"C:\Program Files\Stockfish\stockfish.exe",
        r"C:\Program Files\stockfish\stockfish.exe",
        r"C:\Tools\stockfish\stockfish.exe",
    ]
    candidates.extend(common_paths)

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))

    raise SystemExit(
        "Could not find Stockfish.\n"
        "Pass --stockfish C:\\path\\to\\stockfish.exe or set STOCKFISH_EXE.\n"
        "Example:\n"
        "  python tools/label_with_stockfish.py --positions data/positions/in.jsonl "
        "--out data/labeled/out.jsonl --stockfish C:\\stockfish\\stockfish.exe"
    )


def load_existing_fens(path: Path) -> set[str]:
    if not path.exists():
        return set()
    fens: set[str] = set()
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            fen = record.get("fen")
            if isinstance(fen, str):
                fens.add(fen)
    return fens


def score_to_cp(score: chess.engine.PovScore, clamp: int, mate_score: int, skip_mate: bool) -> int | None:
    white_score = score.white()
    if skip_mate and white_score.is_mate():
        return None

    cp = white_score.score(mate_score=mate_score)
    if cp is None:
        return None
    if cp > clamp:
        return clamp
    if cp < -clamp:
        return -clamp
    return int(cp)


def make_output_record(
    source_record: dict[str, Any],
    score: int,
    include_meta: bool,
    depth: int | None,
    movetime_ms: int | None,
) -> dict[str, Any]:
    out = {
        "fen": source_record["fen"],
        "score": score,
    }
    if include_meta:
        out.update(
            {
                "source": source_record.get("source", ""),
                "game": source_record.get("game", ""),
                "ply": source_record.get("ply", ""),
                "result": source_record.get("result", ""),
                "labeler": "stockfish",
                "depth": depth,
                "movetime_ms": movetime_ms,
            }
        )
    return out


def label_positions(
    positions_path: Path,
    out_path: Path,
    stockfish_path: str,
    depth: int | None,
    movetime_ms: int | None,
    clamp: int,
    mate_score: int,
    skip_mate: bool,
    include_meta: bool,
    threads: int | None,
    hash_mb: int | None,
    max_positions: int | None,
    resume: bool,
) -> tuple[int, int, int]:
    if depth is None and movetime_ms is None:
        depth = 10

    already_done = load_existing_fens(out_path) if resume else set()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mode = "a" if resume else "w"
    processed = 0
    written = 0
    skipped = 0

    limit = chess.engine.Limit(
        depth=depth,
        time=(movetime_ms / 1000.0 if movetime_ms is not None else None),
    )

    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine, positions_path.open(
        "r", encoding="utf-8"
    ) as positions, out_path.open(mode, encoding="utf-8", newline="\n") as output:
        options: dict[str, Any] = {}
        if threads is not None:
            options["Threads"] = threads
        if hash_mb is not None:
            options["Hash"] = hash_mb
        if options:
            engine.configure(options)

        for line in positions:
            line = line.strip()
            if not line:
                continue
            source_record = json.loads(line)
            fen = source_record.get("fen")
            if not isinstance(fen, str) or not fen:
                skipped += 1
                continue
            if fen in already_done:
                skipped += 1
                continue

            try:
                board = chess.Board(fen)
            except ValueError:
                skipped += 1
                continue
            if board.is_game_over(claim_draw=True):
                skipped += 1
                continue

            info = engine.analyse(board, limit)
            pov_score = info.get("score")
            if not isinstance(pov_score, chess.engine.PovScore):
                skipped += 1
                continue

            cp = score_to_cp(pov_score, clamp=clamp, mate_score=mate_score, skip_mate=skip_mate)
            if cp is None:
                skipped += 1
                continue

            output_record = make_output_record(
                source_record,
                score=cp,
                include_meta=include_meta,
                depth=depth,
                movetime_ms=movetime_ms,
            )
            output.write(json.dumps(output_record, ensure_ascii=False) + "\n")
            written += 1
            processed += 1
            if written % 100 == 0:
                output.flush()
                print(f"labeled {written} positions")
            if max_positions is not None and written >= max_positions:
                break

    return processed, written, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Label FEN positions with Stockfish.")
    parser.add_argument("--positions", required=True, type=Path, help="Input positions JSONL")
    parser.add_argument("--out", required=True, type=Path, help="Output labeled JSONL")
    parser.add_argument("--stockfish", help="Path to stockfish.exe. Defaults to STOCKFISH_EXE or PATH lookup.")
    parser.add_argument("--depth", type=int, default=10, help="Fixed Stockfish search depth")
    parser.add_argument("--movetime-ms", type=int, help="Use fixed analysis time instead of depth")
    parser.add_argument("--clamp", type=int, default=1000, help="Clamp cp score to [-clamp, clamp]")
    parser.add_argument("--mate-score", type=int, default=100000, help="Mate score used if --keep-mates")
    parser.add_argument("--keep-mates", action="store_true", help="Convert mate scores instead of skipping them")
    parser.add_argument("--include-meta", action="store_true", help="Include source metadata in output")
    parser.add_argument("--threads", type=int, help="Stockfish Threads option")
    parser.add_argument("--hash-mb", type=int, help="Stockfish Hash option in MB")
    parser.add_argument("--max-positions", type=int, help="Stop after writing this many labels")
    parser.add_argument("--no-resume", action="store_true", help="Overwrite output instead of appending missing FENs")
    args = parser.parse_args()

    stockfish_path = find_stockfish(args.stockfish)
    depth = None if args.movetime_ms is not None else args.depth
    processed, written, skipped = label_positions(
        positions_path=args.positions,
        out_path=args.out,
        stockfish_path=stockfish_path,
        depth=depth,
        movetime_ms=args.movetime_ms,
        clamp=args.clamp,
        mate_score=args.mate_score,
        skip_mate=not args.keep_mates,
        include_meta=args.include_meta,
        threads=args.threads,
        hash_mb=args.hash_mb,
        max_positions=args.max_positions,
        resume=not args.no_resume,
    )

    print(f"stockfish: {stockfish_path}")
    print(f"processed: {processed}")
    print(f"written: {written}")
    print(f"skipped: {skipped}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
