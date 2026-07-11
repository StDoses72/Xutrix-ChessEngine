"""Merge and deduplicate extracted FEN position JSONL files."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def read_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            fen = record.get("fen")
            if isinstance(fen, str) and fen:
                records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge position JSONL files by unique FEN")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-positions", type=int, help="Keep at most this many merged positions")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle before optional truncation")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    merged: dict[str, dict[str, Any]] = {}
    read_count = 0
    duplicate_count = 0
    for path in args.inputs:
        for record in read_records(path):
            read_count += 1
            fen = record["fen"]
            if fen in merged:
                duplicate_count += 1
                continue
            merged[fen] = record

    records = list(merged.values())
    if args.shuffle:
        random.Random(args.seed).shuffle(records)
    if args.max_positions is not None:
        records = records[: max(0, args.max_positions)]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"records read: {read_count}")
    print(f"duplicates skipped: {duplicate_count}")
    print(f"records written: {len(records)}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
