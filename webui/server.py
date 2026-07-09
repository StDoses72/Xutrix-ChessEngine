#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "c_engine" / ("xutrix.exe" if os.name == "nt" else "xutrix")
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FILES = "abcdefgh"
DATA_DIR = WEB_ROOT / "data"
RECORD_FILE = DATA_DIR / "record.json"
DEFAULT_RECORD = {
    "wins": 3,
    "draws": 0,
    "losses": 0,
    "rating": 1500,
    "lastDelta": None,
    "lastResult": "",
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def clamp_int(value, low, high, fallback):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def normalize_record(raw):
    if not isinstance(raw, dict):
        raw = {}
    saved_rating = raw.get("rating", raw.get("currentRating", raw.get("opponentRating")))
    last_delta = raw.get("lastDelta")
    try:
        last_delta = int(round(float(last_delta))) if last_delta is not None else None
    except (TypeError, ValueError):
        last_delta = None
    last_result = raw.get("lastResult")
    if last_result not in ("win", "draw", "loss", ""):
        last_result = ""
    return {
        "wins": max(0, clamp_int(raw.get("wins"), 0, 1000000, DEFAULT_RECORD["wins"])),
        "draws": max(0, clamp_int(raw.get("draws"), 0, 1000000, DEFAULT_RECORD["draws"])),
        "losses": max(0, clamp_int(raw.get("losses"), 0, 1000000, DEFAULT_RECORD["losses"])),
        "rating": clamp_int(saved_rating, 100, 3500, DEFAULT_RECORD["rating"]),
        "lastDelta": last_delta,
        "lastResult": last_result,
    }


def read_record():
    if not RECORD_FILE.exists():
        return DEFAULT_RECORD.copy(), False
    try:
        raw = json.loads(RECORD_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(500, f"Could not read record file: {exc}") from exc
    return normalize_record(raw), True


def write_record(record):
    normalized = normalize_record(record)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = RECORD_FILE.with_suffix(".json.tmp")
    payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    try:
        temp.write_text(payload, encoding="utf-8")
        temp.replace(RECORD_FILE)
    except OSError as exc:
        raise ApiError(500, f"Could not write record file: {exc}") from exc
    return normalized


def square_to_coords(square):
    if len(square) != 2 or square[0] not in FILES or square[1] not in "12345678":
        raise ApiError(400, f"Invalid square: {square}")
    return 8 - int(square[1]), FILES.index(square[0])


def coords_to_square(row, col):
    return f"{FILES[col]}{8 - row}"


def parse_fen(fen):
    parts = fen.strip().split()
    if len(parts) < 4:
        raise ApiError(400, "FEN must include board, side, castling and en-passant fields")

    board = []
    rows = parts[0].split("/")
    if len(rows) != 8:
        raise ApiError(400, "FEN board must contain 8 ranks")

    for rank in rows:
        row = []
        for ch in rank:
            if ch.isdigit():
                row.extend([None] * int(ch))
            elif ch in "PNBRQKpnbrqk":
                row.append(ch)
            else:
                raise ApiError(400, f"Invalid FEN piece: {ch}")
        if len(row) != 8:
            raise ApiError(400, "Each FEN rank must contain 8 files")
        board.append(row)

    active = parts[1]
    if active not in ("w", "b"):
        raise ApiError(400, "FEN active color must be w or b")

    castling = parts[2] if parts[2] else "-"
    ep = parts[3] if parts[3] else "-"
    halfmove = int(parts[4]) if len(parts) > 4 else 0
    fullmove = int(parts[5]) if len(parts) > 5 else 1
    return board, active, castling, ep, halfmove, fullmove


def board_to_fen(board, active, castling, ep, halfmove, fullmove):
    ranks = []
    for row in board:
        out = []
        empty = 0
        for piece in row:
            if piece is None:
                empty += 1
            else:
                if empty:
                    out.append(str(empty))
                    empty = 0
                out.append(piece)
        if empty:
            out.append(str(empty))
        ranks.append("".join(out))
    castling = castling if castling and castling != "" else "-"
    return f"{'/'.join(ranks)} {active} {castling} {ep} {halfmove} {fullmove}"


def board_payload(fen):
    board, active, castling, ep, halfmove, fullmove = parse_fen(fen)
    return {
        "fen": board_to_fen(board, active, castling, ep, halfmove, fullmove),
        "board": [["" if piece is None else piece for piece in row] for row in board],
        "turn": "white" if active == "w" else "black",
        "castling": castling,
        "enPassant": ep,
        "halfmove": halfmove,
        "fullmove": fullmove,
    }


def run_engine(args, timeout=30):
    if not ENGINE.exists():
        raise ApiError(500, f"Engine executable not found: {ENGINE}")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [str(ENGINE), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise ApiError(504, f"Engine timed out after {timeout} seconds") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "engine failed").strip()
        raise ApiError(500, detail)
    return proc.stdout.splitlines()


def engine_moves(fen):
    lines = run_engine(["moves", fen], timeout=10)
    return [line.strip() for line in lines if line.strip() and not line.startswith("count ")]


def parse_best_output(lines):
    result = {
        "bestmove": "0000",
        "search": "",
        "threads": None,
        "scoreSide": "",
        "scoreWhite": "",
        "nodes": 0,
        "time": 0.0,
        "raw": lines,
    }
    for line in lines:
        parts = line.split()
        if line.startswith("bestmove ") and len(parts) >= 2:
            result["bestmove"] = parts[1]
        elif line.startswith("search "):
            result["search"] = line[len("search "):]
        elif line.startswith("threads ") and len(parts) >= 2:
            result["threads"] = int(parts[1])
        elif line.startswith("score side "):
            result["scoreSide"] = line[len("score side "):]
        elif line.startswith("score white "):
            result["scoreWhite"] = line[len("score white "):]
        elif line.startswith("nodes ") and len(parts) >= 2:
            result["nodes"] = int(parts[1])
        elif line.startswith("time ") and len(parts) >= 2:
            result["time"] = float(parts[1])
    return result


def engine_best(fen, depth):
    depth = max(1, min(64, int(depth)))
    timeout = max(20, depth * 6)
    return parse_best_output(run_engine(["best", str(depth), fen], timeout=timeout))


def normalize_castling(rights):
    ordered = "".join(ch for ch in "KQkq" if ch in rights)
    return ordered if ordered else "-"


def apply_uci_move(fen, move):
    board, active, castling, ep, halfmove, fullmove = parse_fen(fen)
    if len(move) not in (4, 5):
        raise ApiError(400, f"Invalid UCI move: {move}")

    fr, fc = square_to_coords(move[:2])
    tr, tc = square_to_coords(move[2:4])
    piece = board[fr][fc]
    if piece is None:
        raise ApiError(400, "No piece on source square")

    white = piece.isupper()
    is_pawn = piece.lower() == "p"
    target = board[tr][tc]
    capture = target is not None
    rights = set() if castling == "-" else set(castling)

    if is_pawn and ep != "-" and move[2:4] == ep and fc != tc and target is None:
        capture_row = tr + (1 if white else -1)
        if 0 <= capture_row < 8:
            board[capture_row][tc] = None
            capture = True

    board[fr][fc] = None
    placed = piece
    if is_pawn and len(move) == 5 and tr in (0, 7):
        promo = move[4].lower()
        if promo not in "qrbn":
            raise ApiError(400, f"Invalid promotion piece: {promo}")
        placed = promo.upper() if white else promo
    board[tr][tc] = placed

    if piece.lower() == "k" and abs(tc - fc) == 2:
        if tc == 6:
            board[tr][5] = board[tr][7]
            board[tr][7] = None
        elif tc == 2:
            board[tr][3] = board[tr][0]
            board[tr][0] = None

    if piece == "K":
        rights.discard("K")
        rights.discard("Q")
    elif piece == "k":
        rights.discard("k")
        rights.discard("q")
    elif piece == "R" and move[:2] == "h1":
        rights.discard("K")
    elif piece == "R" and move[:2] == "a1":
        rights.discard("Q")
    elif piece == "r" and move[:2] == "h8":
        rights.discard("k")
    elif piece == "r" and move[:2] == "a8":
        rights.discard("q")

    if target == "R" and move[2:4] == "h1":
        rights.discard("K")
    elif target == "R" and move[2:4] == "a1":
        rights.discard("Q")
    elif target == "r" and move[2:4] == "h8":
        rights.discard("k")
    elif target == "r" and move[2:4] == "a8":
        rights.discard("q")

    new_ep = "-"
    if is_pawn and abs(tr - fr) == 2:
        new_ep = coords_to_square((tr + fr) // 2, fc)

    new_halfmove = 0 if is_pawn or capture else halfmove + 1
    new_fullmove = fullmove + (1 if active == "b" else 0)
    new_active = "b" if active == "w" else "w"
    return board_to_fen(board, new_active, normalize_castling(rights), new_ep, new_halfmove, new_fullmove)


def choose_legal_move(requested, legal_moves):
    if requested in legal_moves:
        return requested
    if len(requested) == 4:
        promotions = [move for move in legal_moves if move.startswith(requested)]
        if promotions:
            for move in promotions:
                if move.endswith("q"):
                    return move
            return promotions[0]
    raise ApiError(400, f"Illegal move: {requested}")


def terminal_status(fen, legal_moves):
    if legal_moves:
        return {"state": "playing", "label": "playing"}
    result = engine_best(fen, 1)
    raw = "\n".join(result["raw"])
    if "terminal checkmate" in raw:
        return {"state": "checkmate", "label": "checkmate"}
    if "terminal stalemate" in raw:
        return {"state": "stalemate", "label": "stalemate"}
    return {"state": "terminal", "label": "terminal"}


def state_response(fen, legal_moves=None):
    if legal_moves is None:
        legal_moves = engine_moves(fen)
    payload = board_payload(fen)
    payload["legalMoves"] = legal_moves
    payload["status"] = terminal_status(fen, legal_moves)
    return payload


class XutrixHandler(BaseHTTPRequestHandler):
    server_version = "XutrixWeb/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(400, "Invalid JSON body") from exc

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.send_json(200, {"ok": True, "engine": str(ENGINE), "startFen": START_FEN})
                return
            if parsed.path == "/api/record":
                record, exists = read_record()
                self.send_json(200, {"record": record, "exists": exists, "path": str(RECORD_FILE)})
                return
            self.serve_static(parsed.path)
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            body = self.read_json()
            if parsed.path == "/api/record":
                record = write_record(body.get("record", body))
                self.send_json(200, {"record": record, "path": str(RECORD_FILE)})
                return
            if parsed.path == "/api/legal":
                fen = body.get("fen") or START_FEN
                self.send_json(200, state_response(fen))
                return
            if parsed.path == "/api/move":
                fen = body.get("fen") or START_FEN
                requested = (body.get("move") or "").strip().lower()
                legal = engine_moves(fen)
                move = choose_legal_move(requested, legal)
                next_fen = apply_uci_move(fen, move)
                payload = state_response(next_fen)
                payload["move"] = move
                self.send_json(200, payload)
                return
            if parsed.path == "/api/engine":
                fen = body.get("fen") or START_FEN
                depth = int(body.get("depth") or 12)
                started = time.perf_counter()
                best = engine_best(fen, depth)
                elapsed = time.perf_counter() - started
                payload = {"engine": best, "elapsed": elapsed, "fenBefore": fen}
                move = best["bestmove"]
                if move != "0000":
                    payload["move"] = move
                    payload.update(state_response(apply_uci_move(fen, move)))
                else:
                    payload.update(state_response(fen))
                self.send_json(200, payload)
                return
            raise ApiError(404, "Unknown API endpoint")
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def serve_static(self, path):
        if path == "/":
            path = "/index.html"
        rel = unquote(path).lstrip("/")
        target = (WEB_ROOT / rel).resolve()
        if WEB_ROOT not in target.parents and target != WEB_ROOT:
            raise ApiError(403, "Forbidden")
        if not target.exists() or not target.is_file():
            raise ApiError(404, "Not found")
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def choose_port(preferred):
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No free local port found")


def main():
    parser = argparse.ArgumentParser(description="Run the Xutrix local web UI")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    port = choose_port(args.port)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), XutrixHandler)
    print(f"Xutrix Web UI: http://127.0.0.1:{port}", flush=True)
    print(f"Engine: {ENGINE}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
