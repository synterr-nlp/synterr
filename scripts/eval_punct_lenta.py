#!/usr/bin/env python3
"""Evaluate punctuation handlers on Lenta news data.

Reads plain text (one sentence per line), runs comma_delete and dash_delete
handlers via stanza, groups results by L2 subtype, and outputs examples.

Usage:
    uv run python scripts/eval_punct_lenta.py --input lenta.txt [--limit 5000] [--per-tag 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Example:
    original: str
    corrupted: str
    subtype: str
    fix_tag: str


def make_diff(original_tokens: list[str], corrupted_tokens: list[str]) -> str:
    """Simple diff: show original with deleted token marked."""
    # Find the deleted token by comparing lists
    if len(original_tokens) == len(corrupted_tokens):
        return " ".join(corrupted_tokens)

    # Length changed — find where
    diff_parts = []
    j = 0
    for i, tok in enumerate(original_tokens):
        if j < len(corrupted_tokens) and tok == corrupted_tokens[j]:
            diff_parts.append(tok)
            j += 1
        else:
            diff_parts.append(f"[-{tok}-]")
    return " ".join(diff_parts)


def main():
    parser = argparse.ArgumentParser(description="Evaluate punct handlers on text data")
    parser.add_argument("--input", "-i", required=True, help="Input text file (one sentence per line)")
    parser.add_argument("--limit", "-n", type=int, default=5000, help="Max sentences to process")
    parser.add_argument("--per-tag", type=int, default=5, help="Min examples per L2 tag to collect")
    parser.add_argument("--output", "-o", help="Output JSONL file (optional)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    # Read sentences
    sentences = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and len(line.split()) >= 5:  # skip very short
                sentences.append(line)
                if len(sentences) >= args.limit:
                    break

    print(f"Read {len(sentences)} sentences from {input_path}")

    # Filter to sentences with commas or dashes
    punct_sentences = [s for s in sentences if "," in s or "—" in s or "–" in s]
    print(f"Filtered to {len(punct_sentences)} sentences with commas/dashes")

    if not punct_sentences:
        print("No sentences with punctuation found.", file=sys.stderr)
        sys.exit(1)

    # Lazy imports
    from synterr.core.registry import get_language
    from synterr.languages.russian.errors.punctuation import CommaDeleteHandler, DashDeleteHandler

    lang = get_language("ru")
    analyzer = lang.get_analyzer(use_depparse=True, backend="stanza")

    comma_handler = CommaDeleteHandler()
    dash_handler = DashDeleteHandler()

    # Collect examples by subtype — call handlers directly on every comma/dash
    examples: dict[str, list[Example]] = defaultdict(list)
    total_processed = 0
    total_errors = 0

    print("\nProcessing with stanza (depparse=True)...")
    for batch_start in range(0, len(punct_sentences), 64):
        batch = punct_sentences[batch_start : batch_start + 64]
        token_batches = analyzer.analyze_batch(batch)

        for tokens in token_batches:
            total_processed += 1
            if total_processed % 500 == 0:
                print(f"  {total_processed}/{len(punct_sentences)} sentences...", file=sys.stderr)

            original = [t.text for t in tokens]

            # Try every comma and dash in the sentence
            for idx in range(len(tokens)):
                for handler in (comma_handler, dash_handler):
                    if not handler.can_apply(tokens, idx):
                        continue

                    sentence = original.copy()
                    result = handler.apply(tokens, sentence, idx, set())
                    if result is None:
                        continue

                    total_errors += 1
                    ex = Example(
                        original=" ".join(original),
                        corrupted=" ".join(sentence),
                        subtype=result.error_type,
                        fix_tag=result.fix_tag,
                    )
                    examples[result.error_type].append(ex)

    # Output JSONL if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            for subtype, exs in sorted(examples.items()):
                for ex in exs:
                    f.write(json.dumps({
                        "subtype": ex.subtype,
                        "original": ex.original,
                        "corrupted": ex.corrupted,
                        "fix_tag": ex.fix_tag,
                    }, ensure_ascii=False) + "\n")
        print(f"\nWrote {sum(len(v) for v in examples.values())} examples to {output_path}")

    # Print summary table
    all_subtypes = [
        "comma_subordinate", "comma_compound", "comma_parenthetical",
        "comma_isolation", "comma_homogeneous",
        "dash_subj_pred", "dash_other",
    ]

    print(f"\n{'='*80}")
    print(f"Results: {total_errors}/{total_processed} sentences corrupted")
    print(f"{'='*80}\n")

    for subtype in all_subtypes:
        exs = examples.get(subtype, [])
        status = "OK" if len(exs) >= args.per_tag else "LOW"
        print(f"[{status:3s}] {subtype:25s}  ({len(exs)} examples)")

        # Show up to per_tag examples
        for ex in exs[:args.per_tag]:
            diff = make_diff(ex.original.split(), ex.corrupted.split())
            print(f"      {diff}")
        if not exs:
            print("      (no examples)")
        print()

    # Warn about low-count subtypes
    low = [s for s in all_subtypes if len(examples.get(s, [])) < args.per_tag]
    if low:
        print(f"WARNING: {len(low)} subtypes below {args.per_tag} examples: {', '.join(low)}")
    else:
        print(f"All subtypes have >= {args.per_tag} examples.")


if __name__ == "__main__":
    main()
