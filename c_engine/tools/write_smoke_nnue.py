"""Write a tiny NNUE smoke-test weight file.

This file is intentionally not a trained chess evaluator. It exists only to
verify that the C engine can load NNUE weights and route evaluation through the
NNUE inference path. Training/export will replace this with real weights.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


FEATURE_COUNT = 12 * 64
MAGIC = b"XNNUE001"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--scale", type=int, default=64)
    args = parser.parse_args()

    hidden = args.hidden
    if not 1 <= hidden <= 512:
        raise SystemExit("hidden must be between 1 and 512")

    header = struct.pack("<8siii", MAGIC, FEATURE_COUNT, hidden, args.scale)
    hidden_bias = [0] * hidden
    feature_weights = [0] * (FEATURE_COUNT * hidden)
    output_weights = [0] * hidden
    output_bias = 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as f:
        f.write(header)
        f.write(struct.pack(f"<{hidden}h", *hidden_bias))
        f.write(struct.pack(f"<{FEATURE_COUNT * hidden}h", *feature_weights))
        f.write(struct.pack(f"<{hidden}h", *output_weights))
        f.write(struct.pack("<i", output_bias))

    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
