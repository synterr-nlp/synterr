#!/usr/bin/env python3
"""Extract clean sentences from Taiga corpora via corus.

Extracts quality-filtered sentences from Fontanka, Interfax, and/or Lenta
sub-corpora of the Taiga corpus (retagged_taiga.tar.gz).

Uses reservoir sampling for reproducible, unbiased selection.

Usage:
    uv run python scripts/extract_taiga_sents.py \
        data/taiga/retagged_taiga.tar.gz \
        --sources fontanka interfax lenta \
        --target 50000 --seed 42 \
        -o data/taiga/
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from razdel import sentenize


def is_good_sentence(s: str) -> bool:
    s = s.strip()
    words = s.split()
    if len(words) < 8 or len(words) > 25:
        return False
    if not s or not s[0].isupper():
        return False
    if s[-1] not in '.!?\u00bb"':
        return False
    if any(x in s for x in ['УДК', 'ISBN', 'DOI', 'http', '\u00a9', '@', '{{', '[[', ']]']):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic < len(s.replace(' ', '')) * 0.6:
        return False
    return True


def reservoir_sample(reservoir: list[str], seen: int, sentence: str,
                     target: int, rng: random.Random) -> int:
    """Reservoir sampling: return new seen count."""
    seen += 1
    if seen <= target:
        reservoir.append(sentence)
    else:
        j = rng.randint(0, seen - 1)
        if j < target:
            reservoir[j] = sentence
    return seen


def extract_source(taiga_path: str, source: str, target: int,
                   rng: random.Random) -> tuple[list[str], int]:
    """Extract sentences from one Taiga sub-corpus."""
    if source == "fontanka":
        from corus import load_taiga_fontanka as loader
    elif source == "interfax":
        from corus import load_taiga_interfax as loader
    elif source == "lenta":
        from corus import load_taiga_lenta as loader
    else:
        raise ValueError(f"Unknown source: {source}")

    all_sents: list[str] = []
    seen_set: set[str] = set()
    articles = 0

    for rec in loader(taiga_path):
        articles += 1
        text = rec.text if hasattr(rec, 'text') else str(rec)
        for sent in sentenize(text):
            s = sent.text.strip()
            if is_good_sentence(s) and s not in seen_set:
                seen_set.add(s)
                all_sents.append(s)

        if articles % 10000 == 0:
            print(f"    {source}: {articles} articles, {len(all_sents)} sents",
                  flush=True)

    print(f"    {source}: {articles} articles, {len(all_sents)} sents (final)")

    # If target set, reservoir sample down
    if target > 0 and len(all_sents) > target:
        reservoir = all_sents[:target]
        for i in range(target, len(all_sents)):
            j = rng.randint(0, i)
            if j < target:
                reservoir[j] = all_sents[i]
        return reservoir, len(all_sents)

    return all_sents, len(all_sents)


def main():
    parser = argparse.ArgumentParser(description="Extract Taiga sentences")
    parser.add_argument("taiga_path", help="Path to retagged_taiga.tar.gz")
    parser.add_argument("--sources", nargs='+', default=["fontanka", "interfax", "lenta"],
                        help="Sub-corpora to extract")
    parser.add_argument("--target", type=int, default=0,
                        help="Target sentences per source (0=all)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("-o", "--output-dir", required=True,
                        help="Output directory (one file per source)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_meta = {
        "seed": args.seed,
        "target_per_source": args.target,
        "taiga_path": args.taiga_path,
        "sources": {},
    }

    for source in args.sources:
        print(f"\n=== {source} ===")
        rng = random.Random(args.seed)  # Reset per source for independence
        reservoir, seen = extract_source(args.taiga_path, source, args.target, rng)

        # Shuffle with seed
        rng.shuffle(reservoir)

        # Write
        out_path = output_dir / f"taiga_{source}.txt"
        with out_path.open('w', encoding='utf-8') as f:
            for s in reservoir:
                f.write(s + '\n')

        all_meta["sources"][source] = {
            "seen": seen,
            "sampled": len(reservoir),
            "output": str(out_path),
        }
        print(f"  → {out_path} ({len(reservoir)} sentences)")

    # Save metadata
    meta_path = output_dir / "taiga_extract.meta.json"
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(all_meta, f, ensure_ascii=False, indent=2)
    print(f"\nMetadata: {meta_path}")


if __name__ == '__main__':
    main()
