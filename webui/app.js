const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const RECORD_KEY = "xutrix-match-record-v1";
const DEFAULT_RECORD = { wins: 3, draws: 0, losses: 0, rating: 1500, lastDelta: null, lastResult: "" };
const PIECES = {
  K: "\u2654", Q: "\u2655", R: "\u2656", B: "\u2657", N: "\u2658", P: "\u2659",
  k: "\u265A", q: "\u265B", r: "\u265C", b: "\u265D", n: "\u265E", p: "\u265F"
};

const els = {
  board: document.getElementById("board"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
  positionLine: document.getElementById("positionLine"),
  depth: document.getElementById("depth"),
  depthValue: document.getElementById("depthValue"),
  sideWhite: document.getElementById("sideWhite"),
  sideBlack: document.getElementById("sideBlack"),
  autoEngine: document.getElementById("autoEngine"),
  engineMove: document.getElementById("engineMove"),
  undoMove: document.getElementById("undoMove"),
  flipBoard: document.getElementById("flipBoard"),
  newGame: document.getElementById("newGame"),
  bestMove: document.getElementById("bestMove"),
  score: document.getElementById("score"),
  nodes: document.getElementById("nodes"),
  time: document.getElementById("time"),
  recordLine: document.getElementById("recordLine"),
  recordGames: document.getElementById("recordGames"),
  recordRating: document.getElementById("recordRating"),
  recordLastDelta: document.getElementById("recordLastDelta"),
  currentRating: document.getElementById("currentRating"),
  ratingDelta: document.getElementById("ratingDelta"),
  recordWin: document.getElementById("recordWin"),
  recordDraw: document.getElementById("recordDraw"),
  recordLoss: document.getElementById("recordLoss"),
  recordReset: document.getElementById("recordReset"),
  fenInput: document.getElementById("fenInput"),
  loadFen: document.getElementById("loadFen"),
  moveList: document.getElementById("moveList"),
  moveCount: document.getElementById("moveCount"),
  promotionPopover: document.getElementById("promotionPopover")
};

let game = {
  fen: START_FEN,
  board: [],
  legalMoves: [],
  turn: "white",
  selected: null,
  lastMove: null,
  flipped: false,
  humanSide: "white",
  thinking: false,
  history: [],
  fenStack: [START_FEN],
  pendingPromotion: null
};

let record = readLocalRecord();

function clampRating(value, fallback = 1500) {
  const rating = Number(value);
  if (!Number.isFinite(rating)) return fallback;
  return Math.max(100, Math.min(3500, Math.round(rating)));
}

function normalizeRecord(saved, fallback = DEFAULT_RECORD) {
  if (!saved || typeof saved !== "object") return { ...fallback };
  const savedRating = saved.rating ?? saved.currentRating ?? saved.opponentRating;
  const lastDelta = Number(saved.lastDelta);
  const lastResult = ["win", "draw", "loss"].includes(saved.lastResult) ? saved.lastResult : "";
  return {
    wins: Math.max(0, Number(saved.wins) || 0),
    draws: Math.max(0, Number(saved.draws) || 0),
    losses: Math.max(0, Number(saved.losses) || 0),
    rating: clampRating(savedRating, fallback.rating),
    lastDelta: Number.isFinite(lastDelta) ? lastDelta : null,
    lastResult
  };
}

function readLocalRecord() {
  try {
    const saved = JSON.parse(localStorage.getItem(RECORD_KEY) || "null");
    return normalizeRecord(saved);
  } catch {
    return { ...DEFAULT_RECORD };
  }
}

function writeLocalRecord(value) {
  localStorage.setItem(RECORD_KEY, JSON.stringify(value));
}

async function loadRecordFromServer() {
  try {
    const response = await fetch("/api/record");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "record load failed");
    if (data.exists) {
      record = normalizeRecord(data.record, record);
      writeLocalRecord(record);
    } else {
      record = readLocalRecord();
      await saveRecordToServer(record);
    }
    renderRecord();
  } catch {
    record = readLocalRecord();
    renderRecord();
  }
}

async function saveRecordToServer(value) {
  const response = await fetch("/api/record", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record: value })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "record save failed");
  record = normalizeRecord(data.record, record);
  writeLocalRecord(record);
  renderRecord();
}

function saveRecord() {
  writeLocalRecord(record);
  saveRecordToServer(record).catch(() => {
    els.statusText.textContent = "record saved locally";
  });
}

function parseRatingDelta(result) {
  const raw = els.ratingDelta.value.trim();
  els.ratingDelta.classList.remove("invalid");
  if (!raw) return 0;
  if (/^[+-]?\d+$/.test(raw)) {
    return Number(raw);
  }
  if (/^[+-]?\d+(\s*\/\s*[+-]?\d+){1,2}$/.test(raw)) {
    const parts = raw.split("/").map(part => Number(part.trim()));
    if (result === "win") return parts[0];
    if (result === "loss") return parts.length === 2 ? parts[1] : parts[2];
    return parts.length === 3 ? parts[1] : 0;
  }
  {
    els.ratingDelta.classList.add("invalid");
    els.statusText.textContent = "enter +8 or +8 / -8";
    return null;
  }
}

function formatDelta(delta) {
  if (delta === null || delta === undefined) return "-";
  if (delta > 0) return `+${delta}`;
  return String(delta);
}

function updateRecord(result) {
  const ratingDelta = parseRatingDelta(result);
  if (ratingDelta === null) return;
  record.rating = clampRating(els.currentRating.value, record.rating);
  if (result === "win") record.wins += 1;
  if (result === "draw") record.draws += 1;
  if (result === "loss") record.losses += 1;
  record.rating = clampRating(record.rating + ratingDelta, record.rating);
  record.lastDelta = ratingDelta;
  record.lastResult = result;
  els.ratingDelta.value = "";
  saveRecord();
  renderRecord();
}

function resetRecord() {
  record = {
    wins: 0,
    draws: 0,
    losses: 0,
    rating: clampRating(els.currentRating.value, record.rating),
    lastDelta: null,
    lastResult: ""
  };
  saveRecord();
  renderRecord();
}

function renderRecord() {
  const games = record.wins + record.draws + record.losses;
  els.recordLine.textContent = `${record.wins}-${record.draws}-${record.losses}`;
  els.recordGames.textContent = String(games);
  els.recordRating.textContent = String(record.rating);
  els.currentRating.value = String(record.rating);
  els.recordLastDelta.textContent = record.lastResult ? formatDelta(record.lastDelta) : "-";
}

function sideFromPiece(piece) {
  if (!piece) return null;
  return piece === piece.toUpperCase() ? "white" : "black";
}

function filesForView() {
  return game.flipped ? [..."hgfedcba"] : [..."abcdefgh"];
}

function ranksForView() {
  return game.flipped ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
}

function squareToRowCol(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]);
  return [8 - rank, file];
}

function pieceAt(square) {
  const [row, col] = squareToRowCol(square);
  return game.board[row]?.[col] || "";
}

function legalFor(square) {
  return game.legalMoves.filter(move => move.slice(0, 2) === square);
}

function targetMoves(square) {
  if (!game.selected) return [];
  return legalFor(game.selected).filter(move => move.slice(2, 4) === square);
}

function canMoveNow() {
  return !game.thinking && game.turn === game.humanSide && game.status?.state !== "checkmate" && game.status?.state !== "stalemate";
}

async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {})
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setThinking(thinking, label = "") {
  game.thinking = thinking;
  els.statusDot.classList.toggle("thinking", thinking);
  els.statusText.textContent = thinking ? (label || "thinking") : statusLabel();
  document.querySelectorAll("button, input, textarea").forEach(control => {
    if (control.id !== "autoEngine") control.disabled = thinking;
  });
}

function statusLabel() {
  if (game.status?.state === "checkmate") return "checkmate";
  if (game.status?.state === "stalemate") return "stalemate";
  return game.turn === "white" ? "white to move" : "black to move";
}

function updateFromState(data) {
  game.fen = data.fen;
  game.board = data.board;
  game.legalMoves = data.legalMoves || [];
  game.turn = data.turn;
  game.status = data.status;
  els.fenInput.value = game.fen;
  render();
}

function render() {
  els.board.innerHTML = "";
  const ranks = ranksForView();
  const files = filesForView();
  const legalTargets = new Set(game.selected ? legalFor(game.selected).map(move => move.slice(2, 4)) : []);
  const captureTargets = new Set(game.selected ? legalFor(game.selected).filter(move => pieceAt(move.slice(2, 4))).map(move => move.slice(2, 4)) : []);

  for (const rank of ranks) {
    for (const file of files) {
      const square = `${file}${rank}`;
      const [row, col] = squareToRowCol(square);
      const piece = game.board[row]?.[col] || "";
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = `square ${((row + col) % 2 === 0) ? "light" : "dark"}`;
      tile.dataset.square = square;
      tile.setAttribute("aria-label", square);
      if (game.selected === square) tile.classList.add("selected");
      if (legalTargets.has(square)) tile.classList.add("legal");
      if (captureTargets.has(square)) tile.classList.add("capture");
      if (game.lastMove && (game.lastMove.slice(0, 2) === square || game.lastMove.slice(2, 4) === square)) {
        tile.classList.add("last");
      }
      if (piece) {
        const pieceEl = document.createElement("span");
        pieceEl.className = "piece";
        pieceEl.textContent = PIECES[piece] || piece;
        tile.appendChild(pieceEl);
      }
      if ((file === files[0] && rank === ranks[ranks.length - 1]) || (file === files[0] && rank === ranks[0]) || rank === ranks[ranks.length - 1]) {
        const coord = document.createElement("span");
        coord.className = "coord";
        coord.textContent = square;
        tile.appendChild(coord);
      }
      tile.addEventListener("click", () => onSquare(square));
      els.board.appendChild(tile);
    }
  }

  els.positionLine.textContent = game.fen;
  els.statusText.textContent = game.thinking ? "thinking" : statusLabel();
  els.sideWhite.classList.toggle("active", game.humanSide === "white");
  els.sideBlack.classList.toggle("active", game.humanSide === "black");
  els.moveCount.textContent = String(game.history.length);
  els.moveList.innerHTML = game.history.map((item, index) => `<li>${index + 1}. ${item.actor} ${item.move}</li>`).join("");
}

async function onSquare(square) {
  if (!canMoveNow()) return;
  const piece = pieceAt(square);
  const side = sideFromPiece(piece);

  if (!game.selected) {
    if (piece && side === game.turn) {
      game.selected = square;
      render();
    }
    return;
  }

  if (game.selected === square) {
    game.selected = null;
    render();
    return;
  }

  const candidates = targetMoves(square);
  if (candidates.length > 0) {
    if (candidates.length > 1) {
      showPromotion(candidates);
    } else {
      await makeMove(candidates[0], "You");
    }
    return;
  }

  if (piece && side === game.turn) {
    game.selected = square;
    render();
  }
}

function showPromotion(candidates) {
  game.pendingPromotion = candidates;
  els.promotionPopover.classList.remove("hidden");
}

function hidePromotion() {
  game.pendingPromotion = null;
  els.promotionPopover.classList.add("hidden");
}

async function makeMove(move, actor) {
  hidePromotion();
  setThinking(true, "moving");
  let moved = false;
  try {
    const data = await api("/api/move", { fen: game.fen, move });
    game.history.push({ actor, move: data.move });
    game.fenStack.push(data.fen);
    game.lastMove = data.move;
    game.selected = null;
    updateFromState(data);
    moved = true;
  } catch (error) {
    els.statusText.textContent = error.message;
  } finally {
    setThinking(false);
  }
  if (moved) {
    await maybeEngineMove();
  }
}

async function maybeEngineMove() {
  if (!els.autoEngine.checked || game.thinking || game.turn === game.humanSide || game.status?.state !== "playing") {
    return;
  }
  await engineMove();
}

async function engineMove() {
  if (game.thinking || game.status?.state !== "playing") return;
  setThinking(true, "engine");
  try {
    const depth = Number(els.depth.value);
    const data = await api("/api/engine", { fen: game.fen, depth });
    if (data.move) {
      game.history.push({ actor: "Xutrix", move: data.move });
      game.fenStack.push(data.fen);
      game.lastMove = data.move;
    }
    updateFromState(data);
    const engine = data.engine || {};
    els.bestMove.textContent = engine.bestmove || data.move || "-";
    els.score.textContent = engine.scoreSide || "-";
    els.nodes.textContent = typeof engine.nodes === "number" ? engine.nodes.toLocaleString() : "-";
    els.time.textContent = typeof engine.time === "number" ? `${engine.time.toFixed(3)}s` : "-";
  } catch (error) {
    els.statusText.textContent = error.message;
  } finally {
    setThinking(false);
  }
}

async function loadFen(fen, resetHistory = true, allowAuto = true) {
  setThinking(true, "loading");
  try {
    const data = await api("/api/legal", { fen });
    if (resetHistory) {
      game.history = [];
      game.fenStack = [data.fen];
      game.lastMove = null;
    }
    game.selected = null;
    updateFromState(data);
  } catch (error) {
    els.statusText.textContent = error.message;
  } finally {
    setThinking(false);
  }
  if (allowAuto) {
    await maybeEngineMove();
  }
}

function undoMove() {
  if (game.thinking || game.fenStack.length <= 1) return;
  game.fenStack.pop();
  const fen = game.fenStack[game.fenStack.length - 1];
  game.history.pop();
  game.lastMove = game.history.length ? game.history[game.history.length - 1].move : null;
  loadFen(fen, false, false);
}

els.depth.addEventListener("input", () => {
  els.depthValue.textContent = els.depth.value;
});

els.currentRating.addEventListener("change", () => {
  record.rating = clampRating(els.currentRating.value, record.rating);
  saveRecord();
  renderRecord();
});

els.ratingDelta.addEventListener("input", () => {
  els.ratingDelta.classList.remove("invalid");
});

els.recordWin.addEventListener("click", () => updateRecord("win"));
els.recordDraw.addEventListener("click", () => updateRecord("draw"));
els.recordLoss.addEventListener("click", () => updateRecord("loss"));
els.recordReset.addEventListener("click", resetRecord);

els.sideWhite.addEventListener("click", () => {
  game.humanSide = "white";
  render();
});

els.sideBlack.addEventListener("click", async () => {
  game.humanSide = "black";
  render();
  await maybeEngineMove();
});

els.engineMove.addEventListener("click", engineMove);
els.undoMove.addEventListener("click", undoMove);
els.flipBoard.addEventListener("click", () => {
  game.flipped = !game.flipped;
  render();
});
els.newGame.addEventListener("click", () => loadFen(START_FEN, true));
els.loadFen.addEventListener("click", () => loadFen(els.fenInput.value.trim() || START_FEN, true));

els.promotionPopover.addEventListener("click", async event => {
  const promo = event.target?.dataset?.promo;
  if (!promo || !game.pendingPromotion) return;
  const chosen = game.pendingPromotion.find(move => move.endsWith(promo)) || game.pendingPromotion[0];
  await makeMove(chosen, "You");
});

renderRecord();
loadRecordFromServer();
loadFen(START_FEN, true);
