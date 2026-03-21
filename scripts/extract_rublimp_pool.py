#!/usr/bin/env python3
"""Extract source sentences from RuBLiMP results pool (1.5M pairs).

Extracts unique grammatical (source) sentences from the scored TSV files
in results.zip, EXCLUDING sentences that appear in the final RuBLiMP
benchmark (45k pairs in datasets/*.csv) to avoid data contamination.

Usage:
    uv run python scripts/extract_rublimp_pool.py \
        ~/Downloads/results.zip \
        --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
        -o data/rublimp_pool_sents.txt --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import subprocess
import zipfile
from pathlib import Path


def load_benchmark_sentences(benchmark_dir: str) -> set[str]:
    """Load all source sentences from the final RuBLiMP benchmark CSVs."""
    sents = set()
    for fname in os.listdir(benchmark_dir):
        if not fname.endswith('.csv'):
            continue
        with open(os.path.join(benchmark_dir, fname)) as f:
            reader = csv.DictReader(f)
            for row in reader:
                sents.add(row['source_sentence'].strip())
                sents.add(row['target_sentence'].strip())
    return sents


def is_good_sentence(s: str) -> bool:
    """Quality filter."""
    words = s.split()
    if len(words) < 8 or len(words) > 30:
        return False
    if not s or not s[0].isupper():
        return False
    if s[-1] not in '.!?»"':
        return False
    if any(x in s for x in ['УДК', 'ISBN', 'DOI', 'http', '©', '@']):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic < len(s.replace(' ', '')) * 0.6:
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_zip", help="Path to results.zip from RuBLiMP")
    parser.add_argument("--benchmark", required=True, help="Path to RuBLiMP/datasets/ directory")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-sentences", type=int, default=0, help="Max sentences (0=all)")
    args = parser.parse_args()

    # Load benchmark sentences to exclude
    print("Loading benchmark sentences to exclude...")
    benchmark = load_benchmark_sentences(args.benchmark)
    print(f"  Benchmark sentences: {len(benchmark)}")

    # Find one TSV per phenomenon (mdeberta-scored preferred, fallback to any)
    print("\nListing TSV files in results.zip...")
    with zipfile.ZipFile(args.results_zip) as z:
        all_tsvs = [n for n in z.namelist() if n.endswith('.tsv') and not n.startswith('__MACOSX')]

    # Group by phenomenon, pick one file per phenomenon
    phenom_files: dict[str, str] = {}
    for fname in all_tsvs:
        phenom = re.sub(r'_50_50000.*', '', fname.replace('results/', ''))
        if phenom not in phenom_files or 'mdeberta' in fname:
            phenom_files[phenom] = fname

    print(f"  {len(phenom_files)} phenomena, {len(all_tsvs)} total TSVs")

    # Extract unique source sentences
    print("\nExtracting source sentences...")
    all_sents = set()
    excluded = 0

    with zipfile.ZipFile(args.results_zip) as z:
        for phenom, fname in sorted(phenom_files.items()):
            count_before = len(all_sents)
            with z.open(fname) as f:
                header_line = f.readline().decode('utf-8', errors='replace')
                columns = header_line.strip().split('\t')
                # Find the 's' column (grammatical sentence) by name
                try:
                    s_idx = columns.index('s')
                except ValueError:
                    print(f"    SKIP {phenom}: no 's' column in header: {columns[:5]}")
                    continue
                for line in f:
                    parts = line.decode('utf-8', errors='replace').split('\t')
                    if len(parts) > s_idx:
                        sent = parts[s_idx].strip()
                        if sent in benchmark:
                            excluded += 1
                            continue
                        if sent and is_good_sentence(sent):
                            all_sents.add(sent)
            added = len(all_sents) - count_before
            print(f"  {phenom}: +{added} (total: {len(all_sents)})")

    print(f"\nTotal unique sentences: {len(all_sents)} (excluded {excluded} benchmark)")

    # Shuffle and optionally limit
    rng = random.Random(args.seed)
    sents_list = sorted(all_sents)  # sort for reproducibility before shuffle
    rng.shuffle(sents_list)
    if args.max_sentences > 0:
        sents_list = sents_list[:args.max_sentences]

    # Count conjunction forms
    conj_forms = ['что бы', 'так же', 'за то', 'от того', 'при чём', 'при том', 'при чем']
    conj_counts = {p: sum(1 for s in sents_list if p in s) for p in conj_forms}

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in sents_list:
            f.write(s + '\n')

    # Save metadata
    meta_path = output_path.with_suffix('.meta.json')
    meta = {
        "seed": args.seed,
        "source": "RuBLiMP results pool (results.zip)",
        "phenomena": len(phenom_files),
        "total_unique": len(all_sents),
        "output_count": len(sents_list),
        "benchmark_excluded": excluded,
        "conjunction_forms": conj_counts,
    }
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {len(sents_list)} sentences → {output_path}")
    print(f"Conjunction forms: {conj_counts}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
