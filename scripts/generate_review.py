#!/usr/bin/env python3
"""Generate JSONL review files per handler for diff_viewer.html.

Usage:
    uv run python scripts/generate_review.py --all -o tools/review/
    uv run python scripts/generate_review.py -e noun_case -o tools/review/
    uv run python scripts/generate_review.py -e spelling -i corpus.txt -n 200

Each handler gets its own JSONL file (e.g. review_noun_case.jsonl).
Open in diff_viewer.html for visual inspection + annotation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

ALL_HANDLERS = [
    "spelling", "orthographic_spelling", "function_spelling",
    "noun_case", "noun_number",
    "adj_case", "adj_number", "adj_gender",
    "verb_person_number", "verb_tense",
    "paronym", "preposition", "conjunction",
    "word_omission", "word_insertion",
    "comma_delete", "comma_pair_delete", "comma_insert", "dash_delete",
    "compound_spelling", "pleonasm", "collocation",
]


def get_sentences(path: str | None = None, n: int = 500) -> list[str]:
    if path:
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()][:n]
    lenta = Path(__file__).parent.parent / "lenta_sents.txt"
    if lenta.exists():
        with lenta.open(encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()][:n]
    print("No input file. Use -i or place lenta_sents.txt in project root.", file=sys.stderr)
    sys.exit(1)


def generate_for_handler(
    handler_name: str,
    sentences: list[str],
    output_dir: Path,
    seed: int = 42,
    schema: str = "rozental",
    max_per_handler: int = 100,
) -> int:
    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    config = GenerationConfig(
        seed=seed,
        schema=schema,
        enabled_errors={handler_name},
        use_depparse=True,
    )
    pipeline = ErrorPipeline("ru", config)

    # Check handler exists
    handler = pipeline._get_handler_by_name(handler_name)
    if handler is None:
        print(f"  SKIP {handler_name}: handler not found")
        return 0

    out_path = output_dir / f"review_{handler_name}.jsonl"
    count = 0
    rng = Random(seed)
    shuffled = list(range(len(sentences)))
    rng.shuffle(shuffled)

    with out_path.open("w", encoding="utf-8") as f:
        for sent_idx in shuffled:
            if count >= max_per_handler:
                break

            sent = sentences[sent_idx]
            result = pipeline.apply_error(sent, handler_name)
            if result and result.errors:
                record = json.loads(
                    result.to_jsonl(
                        id=f"{handler_name}_{count:04d}",
                        seed=seed,
                        backend="stanza",
                        schema=schema,
                    )
                )
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

    if count == 0:
        out_path.unlink(missing_ok=True)
        print(f"  SKIP {handler_name}: 0 errors generated")
    else:
        print(f"  OK   {handler_name}: {count} examples → {out_path.name}")

    return count


def main():
    parser = argparse.ArgumentParser(description="Generate JSONL review data per handler")
    parser.add_argument("-e", "--handler", help="Single handler name")
    parser.add_argument("--all", action="store_true", help="All handlers")
    parser.add_argument("-o", "--output", default="tools/review", help="Output directory")
    parser.add_argument("-i", "--input", help="Input sentences file")
    parser.add_argument("-n", "--max-sentences", type=int, default=500, help="Max input sentences")
    parser.add_argument("--max-per-handler", type=int, default=100, help="Max examples per handler")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--schema", default="rozental", help="Schema name")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    sentences = get_sentences(args.input, args.max_sentences)
    print(f"Loaded {len(sentences)} sentences\n")

    handlers = ALL_HANDLERS if args.all else ([args.handler] if args.handler else [])
    if not handlers:
        parser.print_help()
        return

    total = 0
    for h in handlers:
        total += generate_for_handler(
            h, sentences, output_dir,
            seed=args.seed, schema=args.schema,
            max_per_handler=args.max_per_handler,
        )

    print(f"\nTotal: {total} examples across {len(handlers)} handlers")
    print(f"Output: {output_dir}/")


if __name__ == "__main__":
    main()
