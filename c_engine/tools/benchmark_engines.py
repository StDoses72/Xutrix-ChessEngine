#!/usr/bin/env python3
"""Benchmark Stockfish, Xutrix classic, and Xutrix NNUE on the same FENs.

The script talks UCI directly and measures wall-clock time from `go depth N`
until `bestmove`. Xutrix's built-in opening book is disabled so the benchmark
measures search/evaluation rather than book hits.
"""

from __future__ import annotations

import argparse
import csv
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XUTRIX = ROOT / ("xutrix.exe" if os.name == "nt" else "xutrix")
DEFAULT_STOCKFISH = ROOT / "tools" / "stockfish" / ("stockfish.exe" if os.name == "nt" else "stockfish")
DEFAULT_NNUE = ROOT / "weights" / "mixed_2025_q1_hikaru_d20_15k_h128.nnue"
DEFAULT_OUT = ROOT / "data" / "benchmarks" / "engine_depth_compare.csv"

DEFAULT_POSITIONS = [
    (
        "startpos",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    ),
    (
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    ),
    (
        "sicilian",
        "r1bq1rk1/1p2bppp/p1np1n2/2p1p3/4P3/2NPBN2/PPP1BPPP/R2Q1RK1 w - - 0 9",
    ),
    (
        "tactical",
        "6k1/5ppp/8/5B2/8/8/5PPP/6K1 w - - 0 1",
    ),
]

STAT_KEYS = [
    "tt_probes",
    "tt_hits",
    "tt_cutoffs",
    "qnodes",
    "q_stand_pat_cutoffs",
    "q_see_prunes",
    "q_beta_cutoffs",
    "null_attempts",
    "null_searches",
    "null_cutoffs",
    "lmr_attempts",
    "lmr_reductions",
    "lmr_researches",
    "pvs_researches",
    "beta_cutoffs",
    "aspiration_fail_low",
    "aspiration_fail_high",
    "aspiration_researches",
]


@dataclass
class EngineSpec:
    name: str
    path: Path
    env: dict[str, str] | None = None
    is_xutrix: bool = False


@dataclass
class BenchResult:
    engine: str
    position: str
    depth: int
    bestmove: str
    score: str
    nodes: int | None
    elapsed_ms: float
    nps: float | None
    stats: dict[str, int]


class UciEngine:
    def __init__(self, spec: EngineSpec, threads: int, hash_mb: int, timeout_sec: float) -> None:
        self.spec = spec
        self.timeout_sec = timeout_sec
        env = os.environ.copy()
        if spec.env:
            env.update(spec.env)
        self.proc = subprocess.Popen(
            [str(spec.path)],
            cwd=str(spec.path.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()
        self._send("uci")
        self._read_until("uciok")
        self._send(f"setoption name Threads value {threads}")
        self._send(f"setoption name Hash value {hash_mb}")
        if spec.is_xutrix:
            self._send("setoption name OwnBook value false")
        self._send("isready")
        self._read_until("readyok")

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self._send("quit")
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()

    def _read_stdout(self) -> None:
        if not self.proc.stdout:
            return
        for line in self.proc.stdout:
            self._lines.put(line.rstrip("\r\n"))

    def _send(self, command: str) -> None:
        if not self.proc.stdin:
            raise RuntimeError(f"{self.spec.name}: stdin closed")
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def _read_line(self, deadline: float) -> str:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError(f"{self.spec.name}: timed out waiting for UCI output")
        try:
            return self._lines.get(timeout=remaining)
        except queue.Empty as exc:
            if self.proc.poll() is not None:
                raise RuntimeError(f"{self.spec.name}: exited with {self.proc.returncode}") from exc
            raise TimeoutError(f"{self.spec.name}: timed out waiting for UCI output") from exc

    def _read_until(self, marker: str) -> list[str]:
        deadline = time.perf_counter() + self.timeout_sec
        lines: list[str] = []
        while True:
            line = self._read_line(deadline)
            lines.append(line)
            if line == marker or line.startswith(marker + " "):
                return lines

    def search(self, position_name: str, fen: str, depth: int) -> BenchResult:
        self._send("ucinewgame")
        self._send("isready")
        self._read_until("readyok")
        self._send(f"position fen {fen}")
        start = time.perf_counter()
        self._send(f"go depth {depth}")

        deadline = start + self.timeout_sec
        info_lines: list[str] = []
        bestmove = "0000"
        while True:
            line = self._read_line(deadline)
            if line.startswith("info "):
                info_lines.append(line)
            if line.startswith("bestmove "):
                parts = line.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                break

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        score = parse_score(info_lines)
        nodes = parse_nodes(info_lines)
        stats = parse_stats(info_lines)
        nps = (nodes / (elapsed_ms / 1000.0)) if nodes is not None and elapsed_ms > 0 else None
        return BenchResult(
            engine=self.spec.name,
            position=position_name,
            depth=depth,
            bestmove=bestmove,
            score=score,
            nodes=nodes,
            elapsed_ms=elapsed_ms,
            nps=nps,
            stats=stats,
        )


def parse_score(info_lines: Iterable[str]) -> str:
    for line in reversed(list(info_lines)):
        parts = line.split()
        if "score" not in parts:
            continue
        i = parts.index("score")
        if i + 2 < len(parts):
            return f"{parts[i + 1]} {parts[i + 2]}"
    return ""


def parse_nodes(info_lines: Iterable[str]) -> int | None:
    for line in reversed(list(info_lines)):
        parts = line.split()
        if "nodes" not in parts:
            continue
        i = parts.index("nodes")
        if i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                return None
    return None


def parse_stats(info_lines: Iterable[str]) -> dict[str, int]:
    marker = "info string stats "
    for line in reversed(list(info_lines)):
        if not line.startswith(marker):
            continue
        stats: dict[str, int] = {}
        for token in line[len(marker):].split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            try:
                stats[key] = int(value)
            except ValueError:
                continue
        return stats
    return {}


def parse_positions(path: Path | None) -> list[tuple[str, str]]:
    if path is None:
        return DEFAULT_POSITIONS

    positions: list[tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                raise SystemExit(f"{path}:{line_number}: expected 'name|fen'")
            name, fen = line.split("|", 1)
            positions.append((name.strip(), fen.strip()))
    if not positions:
        raise SystemExit(f"No positions found in {path}")
    return positions


def write_csv(path: Path, results: list[BenchResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["engine", "position", "depth", "bestmove", "score", "nodes", "elapsed_ms", "nps"] + STAT_KEYS,
        )
        writer.writeheader()
        for result in results:
            row = {
                "engine": result.engine,
                "position": result.position,
                "depth": result.depth,
                "bestmove": result.bestmove,
                "score": result.score,
                "nodes": result.nodes if result.nodes is not None else "",
                "elapsed_ms": f"{result.elapsed_ms:.3f}",
                "nps": f"{result.nps:.0f}" if result.nps is not None else "",
            }
            for key in STAT_KEYS:
                row[key] = result.stats.get(key, "")
            writer.writerow(row)


def print_markdown(results: list[BenchResult]) -> None:
    print("| position | depth | engine | bestmove | score | nodes | time ms | nps | null cut | lmr re | q cut | asp re |")
    print("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        nodes = str(result.nodes) if result.nodes is not None else ""
        nps = f"{result.nps:.0f}" if result.nps is not None else ""
        null_cutoffs = result.stats.get("null_cutoffs", "")
        lmr_researches = result.stats.get("lmr_researches", "")
        q_cutoffs = result.stats.get("q_beta_cutoffs", "")
        aspiration_researches = result.stats.get("aspiration_researches", "")
        print(
            f"| {result.position} | {result.depth} | {result.engine} | {result.bestmove} | "
            f"{result.score} | {nodes} | {result.elapsed_ms:.1f} | {nps} | "
            f"{null_cutoffs} | {lmr_researches} | {q_cutoffs} | {aspiration_researches} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Stockfish, Xutrix classic, and Xutrix NNUE timings.")
    parser.add_argument("--xutrix", type=Path, default=DEFAULT_XUTRIX)
    parser.add_argument("--stockfish", type=Path, default=DEFAULT_STOCKFISH)
    parser.add_argument("--nnue", type=Path, default=DEFAULT_NNUE)
    parser.add_argument("--positions", type=Path, help="Optional text file with one 'name|fen' per line")
    parser.add_argument("--depths", nargs="+", type=int, default=[4, 6, 8, 10, 12])
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--hash-mb", type=int, default=128)
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.xutrix.is_file():
        raise SystemExit(f"Missing Xutrix executable: {args.xutrix}")
    if not args.stockfish.is_file():
        raise SystemExit(f"Missing Stockfish executable: {args.stockfish}")
    if not args.nnue.is_file():
        raise SystemExit(f"Missing NNUE weight file: {args.nnue}")

    positions = parse_positions(args.positions)
    specs = [
        EngineSpec("stockfish", args.stockfish),
        EngineSpec("xutrix-classic", args.xutrix, is_xutrix=True),
        EngineSpec("xutrix-nnue", args.xutrix, env={"XUTRIX_NNUE": str(args.nnue)}, is_xutrix=True),
    ]

    results: list[BenchResult] = []
    for spec in specs:
        engine = UciEngine(spec, threads=args.threads, hash_mb=args.hash_mb, timeout_sec=args.timeout_sec)
        try:
            for name, fen in positions:
                for depth in args.depths:
                    try:
                        result = engine.search(name, fen, depth)
                    except TimeoutError:
                        result = BenchResult(
                            engine=spec.name,
                            position=name,
                            depth=depth,
                            bestmove="TIMEOUT",
                            score="",
                            nodes=None,
                            elapsed_ms=args.timeout_sec * 1000.0,
                            nps=None,
                            stats={},
                        )
                        engine.close()
                        engine = UciEngine(spec, threads=args.threads, hash_mb=args.hash_mb, timeout_sec=args.timeout_sec)
                    results.append(result)
                    print(
                        f"{result.engine} {result.position} depth={result.depth} "
                        f"best={result.bestmove} time={result.elapsed_ms:.1f}ms nodes={result.nodes}",
                        flush=True,
                    )
        finally:
            engine.close()

    write_csv(args.out, results)
    print()
    print_markdown(results)
    print()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
