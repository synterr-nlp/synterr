#!/usr/bin/env python3
"""Batch stress annotation using russtress.

Run with the gector stress_venv (Python 3.10):
    /Users/aleph/Projects/research/gector/stress_venv/bin/python3 scripts/batch_stress.py \
        --input /tmp/need_stress.txt --output /tmp/stress_results.json

Input: one word per line
Output: JSON dict {"word": stress_char_index, ...}
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True, help="Input word list (one per line)")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    parser.add_argument("--batch-size", type=int, default=1000, help="Progress reporting interval")
    args = parser.parse_args()

    from russtress import Accent
    accentor = Accent()

    with open(args.input, encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]

    print(f"Processing {len(words)} words...")
    results = {}
    errors = 0

    for i, word in enumerate(words):
        if (i + 1) % args.batch_size == 0:
            print(f"  {i + 1}/{len(words)}...")

        try:
            stressed = accentor.put_stress(word)
            # Find stress position: russtress inserts ' after the stressed vowel
            # e.g. "церемо'ния" → stress on char 5 (the 'о')
            pos = stressed.find("'")
            if pos > 0:
                results[word] = pos - 1  # char before the apostrophe
            else:
                results[word] = -1
        except Exception:
            results[word] = -1
            errors += 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    print(f"Done. {len(results)} words, {errors} errors. Written to {args.output}")


if __name__ == "__main__":
    main()
