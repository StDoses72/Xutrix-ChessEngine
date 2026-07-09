# Xutrix Web UI

Local browser interface for the Xutrix chess engine.

## Run

From the repository root:

```powershell
python webui\server.py
```

Open the printed local URL, usually:

```text
http://127.0.0.1:8765
```

The server calls `c_engine\xutrix.exe`, so rebuild the engine after C changes:

```powershell
powershell -ExecutionPolicy Bypass -File c_engine\build.ps1
```

The match record is saved as JSON at:

```text
webui\data\record.json
```

## Features

- Click-to-move chessboard with legal move highlights.
- Automatic engine reply using `xutrix.exe best <depth>`.
- Human side selector for playing as White or Black.
- Depth slider, FEN loading, flip board, undo, and new game.
- Engine readout for best move, score, nodes, and time.
- Match record counter with file-backed, manually editable Chess.com rating changes.
