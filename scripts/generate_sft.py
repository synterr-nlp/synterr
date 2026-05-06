#!/usr/bin/env python3
"""Rule-targeted SFT generator — thin CLI wrapper.

The implementation now lives in ``synterr.sft.generate_targeted``. This
script is preserved for backwards-compat with users / docs that invoke
it directly. New code should prefer ``synterr generate-targeted`` (or
import :func:`synterr.sft.generate_targeted` for programmatic use).

Usage (unchanged):
    uv run python scripts/generate_sft.py \\
        -n 50000 --depparse \\
        -i lenta_50k.txt -o data/qwen_sft_50k.jsonl
"""

from __future__ import annotations

import argparse

from synterr.sft import generate_targeted


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SFT data per LoRuGEC rule")
    parser.add_argument("-i", "--input", required=True, help="Input sentences file")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL file")
    parser.add_argument("-n", "--total", type=int, default=50000, help="Total examples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--depparse", action="store_true", help="Enable dep parsing")
    parser.add_argument(
        "--max-input", type=int, default=60000, help="Max input sentences"
    )
    parser.add_argument(
        "--batch-size", type=int, default=128, help="Stanza batch size"
    )
    parser.add_argument(
        "--balance-directions",
        action="store_true",
        help="Cap split/merge pairs to min(split, merge) count",
    )
    parser.add_argument("--lang", default="ru", help="Language code")
    args = parser.parse_args()

    generate_targeted(
        input_path=args.input,
        output_path=args.output,
        total=args.total,
        seed=args.seed,
        depparse=args.depparse,
        max_input=args.max_input,
        batch_size=args.batch_size,
        balance_directions=args.balance_directions,
        lang=args.lang,
    )


if __name__ == "__main__":
    main()
