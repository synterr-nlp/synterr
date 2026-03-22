#!/usr/bin/env python3
"""Build v4 source sentences — one reproducible script.

Flow:
  1. Load scarce sents (kept in full)
  2. Load rublimp pool, REMOVE scarce, REMOVE benchmark → remaining pool
  3. Load articles + taiga news, REMOVE scarce → remaining news
  4. Reservoir sample: remaining pool (50%) + remaining news (50%) to fill budget
  5. Combine: all scarce + sampled pool + sampled news

Usage:
    uv run python scripts/build_v4_sources.py \
        --scarce data/scarce_sents_v4.txt \
        --rublimp-pool data/rublimp_pool_sents.txt \
        --news data/taiga/taiga_fontanka.txt \
              data/taiga/taiga_interfax.txt \
              data/taiga/taiga_lenta.txt \
        --articles ~/Projects/research/gector/data/ru_kw_eval_datasets/data \
        --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
        --output data/mixed_sources_v4.txt \
        --total 105000 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import zipfile
from pathlib import Path


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


def load_plain(path: str) -> set[str]:
    sents = set()
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s:
                sents.add(s)
    return sents


def load_benchmark(benchmark_dir: str) -> set[str]:
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


def load_articles(articles_dir: str) -> set[str]:
    sents = set()
    for zipname in sorted(os.listdir(articles_dir)):
        if not zipname.endswith('.zip'):
            continue
        path = os.path.join(articles_dir, zipname)
        try:
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        for line in f:
                            try:
                                obj = json.loads(line)
                                text = obj.get('content', '') or ''
                                for s in re.split(r'(?<=[.!?])\s+', text):
                                    s = s.strip()
                                    if is_good_sentence(s):
                                        sents.add(s)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue
        except Exception as e:
            print(f"    Error in {zipname}: {e}")
        print(f"    {zipname}: {len(sents)} cumulative")
    return sents


def reservoir_sample(pool: list[str], n: int, rng: random.Random) -> list[str]:
    if len(pool) <= n:
        return pool.copy()
    reservoir = pool[:n]
    for i in range(n, len(pool)):
        j = rng.randint(0, i)
        if j < n:
            reservoir[j] = pool[i]
    return reservoir


def main():
    parser = argparse.ArgumentParser(description="Build v4 source sentences")
    parser.add_argument("--scarce", required=True, help="Mined scarce sents file")
    parser.add_argument("--rublimp-pool", required=True, help="RuBLiMP pool file")
    parser.add_argument("--news", nargs='+', help="Taiga news plain text files")
    parser.add_argument("--articles", help="Path to ru_kw_eval_datasets/data/")
    parser.add_argument("--benchmark", required=True, help="RuBLiMP/datasets/ for exclusion")
    parser.add_argument("--output", required=True)
    parser.add_argument("--total", type=int, default=150000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # 1. Load scarce (kept in full)
    print("=== Scarce sents ===")
    scarce = load_plain(args.scarce)
    print(f"  {len(scarce):,} sentences")

    # 2. Load benchmark exclusion
    print("\n=== Benchmark exclusion ===")
    benchmark = load_benchmark(args.benchmark)
    print(f"  {len(benchmark):,} sentences to exclude")

    # 3. Load rublimp pool, remove scarce + benchmark
    print("\n=== RuBLiMP pool ===")
    pool = load_plain(args.rublimp_pool)
    pool_clean = pool - scarce - benchmark
    print(f"  {len(pool):,} total → {len(pool_clean):,} (removed {len(pool) - len(pool_clean):,} scarce/benchmark)")

    # 4. Load news (taiga + articles), remove scarce
    print("\n=== News sources ===")
    news = set()
    if args.news:
        for path in args.news:
            n_before = len(news)
            news |= load_plain(path)
            print(f"    {Path(path).name}: +{len(news) - n_before:,}")
    if args.articles:
        print("  Articles:")
        n_before = len(news)
        news |= load_articles(args.articles)
        print(f"    articles total: +{len(news) - n_before:,}")
    news_clean = news - scarce - benchmark
    print(f"  {len(news):,} total → {len(news_clean):,} (removed {len(news) - len(news_clean):,} scarce/benchmark)")

    # 5. Budget: total - scarce = remaining, split 60/40 pool/news
    budget = args.total - len(scarce)
    if budget < 0:
        print(f"\nWARNING: scarce ({len(scarce):,}) exceeds total ({args.total:,}), no room for pool/news")
        budget = 0
    pool_budget = int(budget * 0.6)
    news_budget = budget - pool_budget

    print(f"\n=== Assembly (target {args.total:,}) ===")
    print(f"  Scarce (all): {len(scarce):,}")
    print(f"  Pool budget: {pool_budget:,}")
    print(f"  News budget: {news_budget:,}")

    # Reservoir sample
    pool_list = sorted(pool_clean)
    rng.shuffle(pool_list)
    pool_sampled = reservoir_sample(pool_list, pool_budget, rng)

    news_list = sorted(news_clean)
    rng.shuffle(news_list)
    news_sampled = reservoir_sample(news_list, news_budget, rng)

    # Combine + dedupe + shuffle
    all_sents = sorted(set(scarce) | set(pool_sampled) | set(news_sampled))
    rng.shuffle(all_sents)

    print(f"  Pool sampled: {len(pool_sampled):,}/{len(pool_clean):,}")
    print(f"  News sampled: {len(news_sampled):,}/{len(news_clean):,}")
    print(f"  Combined: {len(all_sents):,}")

    # Verify no benchmark
    overlap = len(set(all_sents) & benchmark)
    if overlap:
        print(f"  WARNING: {overlap} benchmark sentences remaining!")

    # Write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in all_sents:
            f.write(s + '\n')

    # Metadata
    meta = {
        "seed": args.seed,
        "total_target": args.total,
        "output_count": len(all_sents),
        "source_counts": {
            "scarce": len(scarce),
            "rublimp_pool_sampled": len(pool_sampled),
            "rublimp_pool_available": len(pool_clean),
            "news_sampled": len(news_sampled),
            "news_available": len(news_clean),
        },
        "benchmark_excluded": len(benchmark),
        "benchmark_overlap": overlap,
    }
    meta_path = output_path.with_suffix('.meta.json')
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {len(all_sents):,} → {output_path}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
