"""Train and export Xutrix's starter NNUE evaluator.

The current C inference path uses a compact single-hidden-layer network:

    768 sparse piece-square features -> clipped ReLU hidden layer -> cp score

This script trains a float model with the same topology, then quantizes it into
the binary format loaded by src/nnue.c.
"""

from __future__ import annotations

import argparse
import json
import random
import struct
from dataclasses import dataclass
from pathlib import Path

import chess
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


FEATURE_COUNT = 12 * 64
MAGIC = b"XNNUE001"
MAX_HIDDEN = 512
CLIP = 127.0

PIECE_OFFSETS = {
    chess.Piece(chess.PAWN, chess.WHITE): 0,
    chess.Piece(chess.KNIGHT, chess.WHITE): 1,
    chess.Piece(chess.BISHOP, chess.WHITE): 2,
    chess.Piece(chess.ROOK, chess.WHITE): 3,
    chess.Piece(chess.QUEEN, chess.WHITE): 4,
    chess.Piece(chess.KING, chess.WHITE): 5,
    chess.Piece(chess.PAWN, chess.BLACK): 6,
    chess.Piece(chess.KNIGHT, chess.BLACK): 7,
    chess.Piece(chess.BISHOP, chess.BLACK): 8,
    chess.Piece(chess.ROOK, chess.BLACK): 9,
    chess.Piece(chess.QUEEN, chess.BLACK): 10,
    chess.Piece(chess.KING, chess.BLACK): 11,
}


@dataclass
class LabeledPosition:
    fen: str
    score: float


class XutrixNNUE(nn.Module):
    def __init__(self, hidden: int) -> None:
        super().__init__()
        self.feature = nn.Linear(FEATURE_COUNT, hidden)
        self.output = nn.Linear(hidden, 1)
        nn.init.normal_(self.feature.weight, mean=0.0, std=0.03)
        nn.init.zeros_(self.feature.bias)
        nn.init.normal_(self.output.weight, mean=0.0, std=0.02)
        nn.init.zeros_(self.output.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        hidden = torch.clamp(self.feature(features), min=0.0, max=CLIP)
        return self.output(hidden).squeeze(-1)


def feature_index(piece: chess.Piece, square: chess.Square) -> int:
    return PIECE_OFFSETS[piece] * 64 + square


def fen_to_features(fen: str) -> np.ndarray:
    board = chess.Board(fen)
    features = np.zeros(FEATURE_COUNT, dtype=np.float32)
    for square, piece in board.piece_map().items():
        features[feature_index(piece, square)] = 1.0
    return features


def read_labeled_positions(path: Path, target_clamp: int) -> list[LabeledPosition]:
    positions: list[LabeledPosition] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                fen = item["fen"]
                score = float(item["score"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise SystemExit(f"{path}:{line_number}: invalid labeled record: {exc}") from exc
            score = max(-target_clamp, min(target_clamp, score))
            positions.append(LabeledPosition(fen=fen, score=score))
    if not positions:
        raise SystemExit(f"No labeled positions found in {path}")
    return positions


def build_tensors(positions: list[LabeledPosition]) -> tuple[torch.Tensor, torch.Tensor]:
    features = np.stack([fen_to_features(item.fen) for item in positions])
    scores = np.array([item.score for item in positions], dtype=np.float32)
    return torch.from_numpy(features), torch.from_numpy(scores)


def split_dataset(
    features: torch.Tensor,
    scores: torch.Tensor,
    validation_split: float,
    seed: int,
) -> tuple[TensorDataset, TensorDataset]:
    indices = list(range(features.shape[0]))
    rng = random.Random(seed)
    rng.shuffle(indices)

    validation_count = int(round(len(indices) * validation_split))
    validation_count = max(1, min(validation_count, len(indices) - 1)) if len(indices) > 1 else 0
    validation_indices = indices[:validation_count]
    train_indices = indices[validation_count:]

    train = TensorDataset(features[train_indices], scores[train_indices])
    validation = TensorDataset(features[validation_indices], scores[validation_indices])
    return train, validation


def evaluate_loss(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    if len(loader.dataset) == 0:
        return 0.0
    criterion = nn.SmoothL1Loss(beta=50.0, reduction="sum")
    total = 0.0
    with torch.no_grad():
        for batch_features, batch_scores in loader:
            batch_features = batch_features.to(device)
            batch_scores = batch_scores.to(device)
            total += float(criterion(model(batch_features), batch_scores).item())
    return total / len(loader.dataset)


def clamp_int16(values: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(values), -32768, 32767).astype("<i2")


def export_nnue(model: XutrixNNUE, output: Path, scale: int, activation_scale: float) -> None:
    if not 1 <= model.feature.out_features <= MAX_HIDDEN:
        raise SystemExit(f"hidden must be between 1 and {MAX_HIDDEN}")
    if scale <= 0:
        raise SystemExit("scale must be positive")
    if activation_scale <= 0.0:
        raise SystemExit("activation_scale must be positive")

    model = model.cpu()
    hidden = model.feature.out_features
    feature_weights = clamp_int16(model.feature.weight.detach().numpy().T * activation_scale)
    hidden_bias = clamp_int16(model.feature.bias.detach().numpy() * activation_scale)
    output_weights = clamp_int16(model.output.weight.detach().numpy().reshape(-1) * scale / activation_scale)
    output_bias = int(round(float(model.output.bias.detach().numpy()[0]) * scale))

    header = struct.pack("<8siii", MAGIC, FEATURE_COUNT, hidden, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        f.write(header)
        f.write(hidden_bias.tobytes())
        f.write(feature_weights.tobytes())
        f.write(output_weights.tobytes())
        f.write(struct.pack("<i", output_bias))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export Xutrix starter NNUE weights")
    parser.add_argument("--input", type=Path, required=True, help="JSONL records with fen and score fields")
    parser.add_argument("--out", type=Path, required=True, help="Output .nnue file")
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=0.003)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--target-clamp", type=int, default=1000)
    parser.add_argument("--scale", type=int, default=64)
    parser.add_argument(
        "--activation-scale",
        type=float,
        default=16.0,
        help="Multiplier for quantizing first-layer activations into C accumulator units",
    )
    parser.add_argument("--validation-split", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if not 1 <= args.hidden <= MAX_HIDDEN:
        raise SystemExit(f"--hidden must be between 1 and {MAX_HIDDEN}")
    if args.epochs < 0:
        raise SystemExit("--epochs must be non-negative")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    positions = read_labeled_positions(args.input, args.target_clamp)
    features, scores = build_tensors(positions)
    train_dataset, validation_dataset = split_dataset(features, scores, args.validation_split, args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = XutrixNNUE(args.hidden).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    criterion = nn.SmoothL1Loss(beta=50.0)

    generator = torch.Generator()
    generator.manual_seed(args.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=False)

    print(
        f"loaded {len(positions)} positions: train={len(train_dataset)} "
        f"validation={len(validation_dataset)} device={device}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for batch_features, batch_scores in train_loader:
            batch_features = batch_features.to(device)
            batch_scores = batch_scores.to(device)

            optimizer.zero_grad(set_to_none=True)
            prediction = model(batch_features)
            loss = criterion(prediction, batch_scores)
            loss.backward()
            optimizer.step()
            total += float(loss.item()) * batch_features.shape[0]

        model.eval()
        train_loss = total / len(train_dataset)
        validation_loss = evaluate_loss(model, validation_loader, device)
        print(f"epoch {epoch:03d} train_loss={train_loss:.3f} validation_loss={validation_loss:.3f}")

    export_nnue(model, args.out, args.scale, args.activation_scale)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
