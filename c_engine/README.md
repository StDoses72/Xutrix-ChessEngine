# Xutrix C Engine

This is the new C foundation for Xutrix. The old Python/Cython engine is kept at
the repository root for reference while this core becomes stable.

## Build

Windows PowerShell:

```powershell
cd c_engine
.\build.ps1
```

The script tries MSVC `cl`, then `gcc`, then `clang`.

With CMake:

```powershell
cd c_engine
cmake -S . -B build
cmake --build build --config Release
```

## Run

```powershell
.\xutrix.exe perft 3
.\xutrix.exe best 4
.\xutrix.exe best-direct 4
.\xutrix.exe play 4
.\xutrix.exe uci
.\xutrix.exe eval
```

Run the core validation suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify.ps1
```

Commands also accept a FEN after the depth:

```powershell
.\xutrix.exe perft 2 "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
```

## Current Scope

- 64-square mailbox board, `a1 = 0`.
- Legal move generation including castling, en passant, and promotions.
- Make/undo move stack.
- Zobrist hash and transposition table.
- Negamax alpha-beta search with quiescence.
- Material + piece-square evaluation.
- Optional NNUE inference path loaded from `XUTRIX_NNUE`.
- Perft and basic UCI support for validation.

## NNUE Weights

The engine looks for a binary NNUE file in the `XUTRIX_NNUE` environment
variable. If no file is configured, it falls back to the classic evaluator.

Smoke-test the loader with a zero-weight network:

```powershell
python .\tools\write_smoke_nnue.py .\weights\smoke.nnue
$env:XUTRIX_NNUE = "$PWD\weights\smoke.nnue"
.\xutrix.exe eval
```

This smoke network is not trained and should not be used for playing strength.

## Training Data Pipeline

Install the Python dependency used for PGN parsing:

```powershell
python -m pip install -r .\tools\requirements-training.txt
```

Install Stockfish locally into `tools/stockfish/stockfish.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install_stockfish.ps1
```

Download public Chess.com PGNs through the official public API:

```powershell
python .\tools\download_chesscom_pgn.py `
  --username Hikaru `
  --from 2025-01 `
  --to 2025-12 `
  --out .\data\raw\hikaru_2025.pgn
```

Extract unique FEN positions:

```powershell
python .\tools\extract_positions.py `
  --pgn .\data\raw\hikaru_2025.pgn `
  --out .\data\positions\hikaru_2025_positions.jsonl `
  --skip-ply 8 `
  --sample-every 4 `
  --max-per-game 32
```

The output is JSONL. Each line contains a FEN plus metadata:

```json
{"fen":"...","source":"pgn","game":1,"ply":12,"white":"...","black":"...","result":"1-0"}
```

The next stage is Stockfish labeling, which will turn positions into
`{"fen":"...","score":37}` records for PyTorch training.

Label positions with Stockfish:

```powershell
python .\tools\label_with_stockfish.py `
  --positions .\data\positions\hikaru_2025_positions.jsonl `
  --out .\data\labeled\hikaru_2025_labeled.jsonl `
  --depth 10 `
  --threads 4 `
  --hash-mb 512
```

By default, labeled output is intentionally minimal:

```json
{"fen":"...","score":37}
```

Use `--include-meta` if you want source, game, ply, and labeler fields kept for
auditing. Use `--movetime-ms 100` instead of `--depth 10` if you prefer fixed
time per position.

## Next Iterations

- Add perft test fixtures.
- Add time management and iterative deepening.
- Replace or blend evaluation with an NNUE-style evaluator.
- Add a training/export pipeline for neural-network weights.
