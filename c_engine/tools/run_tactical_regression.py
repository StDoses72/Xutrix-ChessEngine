#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
ENGINE = ROOT / ("xutrix.exe" if sys.platform.startswith("win") else "xutrix")
DEFAULT_FIXTURES = ROOT / "data" / "regression" / "tactics.json"


def parse_bestmove(output):
    result = {
        "bestmove": "0000",
        "score": "",
        "nodes": "",
        "time": "",
        "raw": output,
    }
    for line in output.splitlines():
        if line.startswith("bestmove "):
            result["bestmove"] = line.split()[1]
        elif line.startswith("score side "):
            result["score"] = line[len("score side "):]
        elif line.startswith("nodes "):
            result["nodes"] = line.split()[1]
        elif line.startswith("time "):
            result["time"] = line.split()[1]
    return result


def run_case(case, engine):
    depth = str(case.get("depth", 12))
    fen = case["fen"]
    completed = subprocess.run(
        [str(engine), "best", depth, fen],
        cwd=str(REPO),
        text=True,
        capture_output=True,
        timeout=max(30, int(depth) * 8),
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return parse_bestmove(completed.stdout)


def main():
    parser = argparse.ArgumentParser(description="Run Xutrix tactical regression fixtures")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--engine", type=Path, default=ENGINE)
    args = parser.parse_args()

    cases = json.loads(args.fixtures.read_text(encoding="utf-8"))
    failed = 0
    for case in cases:
        result = run_case(case, args.engine)
        expected = set(case.get("expected_bestmoves", []))
        ok = result["bestmove"] in expected
        status = "ok" if ok else "FAIL"
        print(
            f"{status} {case['id']} depth={case.get('depth')} "
            f"bestmove={result['bestmove']} score={result['score']} "
            f"nodes={result['nodes']} time={result['time']}"
        )
        if not ok:
            print(f"  expected one of: {', '.join(sorted(expected))}")
            print(f"  reference: {case.get('reference', '')}")
            failed += 1

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
