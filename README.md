# Xutrix Chess Engine

Xutrix is a chess engine project currently being rebuilt around a C core. The
original Python/Cython prototype has been archived, and the active engine now
lives in `c_engine/`.

The current goal is to keep a fast, understandable classical search engine while
adding an NNUE-style evaluation pipeline that can be trained from Stockfish
labels.

## What Works Now

- 64-square mailbox board representation
- FEN loading and board printing
- legal move generation
- castling, en passant, and promotions
- make/undo move stack
- Zobrist hashing
- transposition table
- negamax alpha-beta search
- quiescence search
- killer moves
- history heuristic move ordering
- basic CLI play mode
- basic UCI mode
- perft validation
- optional NNUE inference path
- Chess.com PGN download tools
- PGN-to-FEN extraction
- Stockfish labeling tools for NNUE training data

## Layout

```text
.
+-- c_engine/
|   +-- src/                 C engine source
|   +-- tools/               training/data/helper scripts
|   +-- data/fixtures/       tiny local test fixtures
|   +-- build.ps1            local build script
|   +-- verify.ps1           perft/search verification
|   +-- README.md            C engine details
+-- LICENSE
+-- README.md
```

## Build

From PowerShell:

```powershell
cd D:\doses72Proj\Xutrix-ChessEngine\c_engine
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The build script tries MSVC, `gcc`, `clang`, and the local MSYS2 GCC path. The
compiled executable is:

```text
c_engine\xutrix.exe
```

## Verify

Run the engine regression checks:

```powershell
cd D:\doses72Proj\Xutrix-ChessEngine\c_engine
powershell -ExecutionPolicy Bypass -File .\verify.ps1
```

Current verification covers:

- start position perft depths 1-4
- Kiwipete perft depths 1-3
- a search smoke test

## Run

```powershell
cd D:\doses72Proj\Xutrix-ChessEngine\c_engine

.\xutrix.exe perft 4
.\xutrix.exe best 8
.\xutrix.exe best-direct 8
.\xutrix.exe play 6
.\xutrix.exe eval
.\xutrix.exe uci
```

Double-clicking `xutrix.exe` opens a small interactive menu instead of closing
immediately.

## NNUE Direction

The engine currently supports loading an NNUE-style binary weight file through
the `XUTRIX_NNUE` environment variable. If no NNUE file is configured, Xutrix
falls back to the classical evaluator.

Smoke-test the NNUE loader:

```powershell
cd D:\doses72Proj\Xutrix-ChessEngine\c_engine
python .\tools\write_smoke_nnue.py .\weights\smoke.nnue
$env:XUTRIX_NNUE = "$PWD\weights\smoke.nnue"
.\xutrix.exe eval
```

The smoke network is only for testing the loader. It is not trained.

## Training Data

The current data pipeline is:

```text
Chess.com PGN
  -> extracted FEN positions
  -> Stockfish centipawn labels
  -> clean JSONL for PyTorch
```

Install Python dependencies:

```powershell
cd D:\doses72Proj\Xutrix-ChessEngine\c_engine
python -m pip install -r .\tools\requirements-training.txt
```

Download public Chess.com PGN:

```powershell
python .\tools\download_chesscom_pgn.py `
  --username Hikaru `
  --from 2025-01 `
  --to 2025-12 `
  --out .\data\raw\hikaru_2025.pgn
```

Extract positions:

```powershell
python .\tools\extract_positions.py `
  --pgn .\data\raw\hikaru_2025.pgn `
  --out .\data\positions\hikaru_2025_positions.jsonl `
  --skip-ply 8 `
  --sample-every 4 `
  --max-per-game 32
```

Label with Stockfish:

```powershell
python .\tools\label_with_stockfish.py `
  --positions .\data\positions\hikaru_2025_positions.jsonl `
  --out .\data\labeled\hikaru_2025_labeled.jsonl `
  --depth 8 `
  --threads 4 `
  --hash-mb 512
```

The labeled output is intentionally simple:

```json
{"fen":"...","score":37}
```

## Current Starter Dataset

A first starter dataset has been generated locally:

```text
c_engine\data\labeled\hikaru_2025_labeled_d8_5k.jsonl
```

It contains 4,976 clean `fen + score` records labeled by Stockfish 18 at depth
8. Data files are ignored by git so large/generated training artifacts do not
pollute the repository.

## Legacy Python Backup

The previous Python/Cython version has been moved to:

```text
D:\doses72Proj\Xutrix-ChessEngine-python-backup-20260516
```

That backup includes the original `engine.py`, Cython files, PeSTO tables,
profile data, and old README.
