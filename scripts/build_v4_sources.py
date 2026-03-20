#!/usr/bin/env python3
"""Build v4 source sentences — one reproducible script.

Replaces the ad-hoc v3c pipeline with a single seeded run.
NO RuBLiMP benchmark sentences (clean for eval). NO wiki_200k. NO Taiga proza.

Sources:
  1. Articles (Habr/CyberLeninka/НГ/RT) — bulk
  2. Rare conjunctions (Fontanka/Interfax/Lenta) — ~7K (reuse existing files)
  3. Conjunction sents (wiki dump reservoir) — ~3.5K (reuse existing file)
  4. RuBLiMP pool (results.zip, benchmark-excluded) — scarce form mining

Usage:
    uv run python scripts/build_v4_sources.py \
        --articles ~/Projects/research/gector/data/ru_kw_eval_datasets/data \
        --rare-conjunctions data/rare_conjunctions_fontanka.txt \
                           data/rare_conjunctions_interfax.txt \
                           data/rare_conjunctions_lenta.txt \
        --conjunction-sents data/conjunction_sents.txt \
        --rublimp-pool data/rublimp_pool_sents.txt \
        --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
        --output data/mixed_sources_v4.txt \
        --seed 42
"""

from __future__ import annotations

import argparse
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
    if not s[0].isupper():
        return False
    if s[-1] not in '.!?\u00bb"':
        return False
    if any(x in s for x in ['УДК', 'ISBN', 'DOI', 'http', '\u00a9', '@']):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic < len(s.replace(' ', '')) * 0.6:
        return False
    return True


def extract_sentences_from_text(text: str) -> list[str]:
    sents = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for s in sents:
        s = s.strip()
        words = s.split()
        if 8 <= len(words) <= 25:
            if any(x in s for x in ['http', 'www.', '{', '}', '()', '/**', '//', '==', '&&', '||']):
                continue
            cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
            if cyrillic < len(s.replace(' ', '')) * 0.5:
                continue
            result.append(s)
    return result


def load_articles(articles_dir: str) -> set[str]:
    sents = set()
    for zipname in sorted(os.listdir(articles_dir)):
        if not zipname.endswith('.zip'):
            continue
        path = os.path.join(articles_dir, zipname)
        count = 0
        try:
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        for line in f:
                            try:
                                obj = json.loads(line)
                                text = obj.get('content', '') or ''
                                for s in extract_sentences_from_text(text):
                                    if is_good_sentence(s):
                                        sents.add(s)
                                        count += 1
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue
        except Exception as e:
            print(f"    Error in {zipname}: {e}")
        print(f"    {zipname}: {count}")
    return sents


def load_plain(paths: list[str]) -> set[str]:
    sents = set()
    for path in paths:
        with open(path, encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s:
                    sents.add(s)
        print(f"    {Path(path).name}: {len(sents)} cumulative")
    return sents


SCARCE_PATTERNS = re.compile(
    r'полтора|полторы|полтораста|полутора|полутораста'
    r'|\bтаки\b'
    r'|инск[а-яё]*\b|енск[а-яё]*\b'
    r'|пол-[а-яё]'
    r'|еньк[а-яё]*\b|оньк[а-яё]*\b'
    r'|ице\b|ицо\b|ецо\b|еце\b',
    re.IGNORECASE,
)


def load_benchmark(benchmark_dir: str) -> set[str]:
    """Load all sentences from the RuBLiMP benchmark to exclude."""
    import csv
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


def main():
    parser = argparse.ArgumentParser(description="Build v4 source sentences")
    parser.add_argument("--articles", required=True, help="Path to ru_kw_eval_datasets/data/")
    parser.add_argument("--rare-conjunctions", nargs='+', required=True,
                        help="Paths to rare_conjunctions_*.txt files")
    parser.add_argument("--conjunction-sents", required=True,
                        help="Path to conjunction_sents.txt")
    parser.add_argument("--rublimp-pool", help="Path to rublimp_pool_sents.txt")
    parser.add_argument("--benchmark", help="Path to RuBLiMP/datasets/ (for exclusion)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Load benchmark exclusion set
    benchmark = set()
    if args.benchmark:
        print("=== Benchmark exclusion set ===")
        benchmark = load_benchmark(args.benchmark)
        print(f"  {len(benchmark)} sentences to exclude")

    def exclude(sents: set[str]) -> set[str]:
        if not benchmark:
            return sents
        removed = len(sents & benchmark)
        if removed:
            print(f"  Excluded {removed} benchmark sentences")
        return sents - benchmark

    # 1. Articles
    print("\n=== Articles ===")
    articles = load_articles(args.articles)
    articles_filtered = exclude({s for s in articles if is_good_sentence(s)})
    print(f"  {len(articles)} raw → {len(articles_filtered)} filtered")

    # 2. Rare conjunctions (Fontanka/Interfax/Lenta)
    print("\n=== Rare conjunctions ===")
    rare_conj = exclude(load_plain(args.rare_conjunctions))
    print(f"  {len(rare_conj)} total")

    # 3. Conjunction sents (wiki reservoir)
    print("\n=== Conjunction sents ===")
    conj_sents = exclude(load_plain([args.conjunction_sents]))
    print(f"  {len(conj_sents)} total")

    # 4. RuBLiMP pool — mine scarce forms only (not bulk)
    scarce_sents: set[str] = set()
    if args.rublimp_pool:
        print("\n=== RuBLiMP pool (scarce form mining) ===")
        pool = exclude(load_plain([args.rublimp_pool]))
        # Only keep sentences with scarce morphological forms
        already = articles_filtered | rare_conj | conj_sents
        for s in pool:
            if s not in already and SCARCE_PATTERNS.search(s):
                scarce_sents.add(s)
        print(f"  {len(pool)} pool → {len(scarce_sents)} scarce-form sentences")

    # Combine: keep ALL enrichment sentences, sample articles to fit budget
    # Enrichment = rare_conj + conj_sents + scarce (must all be included)
    enrichment = (rare_conj | conj_sents | scarce_sents) - articles_filtered
    enrichment_list = sorted(enrichment)

    # Budget for articles: total target minus enrichment
    # Default target ~105K to match --max-input in generate_sft.py
    target_total = 105000
    article_budget = max(0, target_total - len(enrichment_list))

    articles_list = sorted(articles_filtered - enrichment)
    rng.shuffle(articles_list)
    articles_sampled = articles_list[:article_budget]

    all_sents = sorted(set(articles_sampled) | enrichment)
    rng.shuffle(all_sents)

    print(f"\n=== Assembly ===")
    print(f"  Enrichment (kept all): {len(enrichment_list)}")
    print(f"  Articles (sampled): {len(articles_sampled)}/{len(articles_list)}")
    print(f"  Combined unique: {len(all_sents)}")

    # Shuffle with seed
    rng.shuffle(all_sents)

    # Conjunction form counts
    conj_forms = ['что бы', 'так же', 'за то', 'от того', 'при чём', 'при том', 'при чем']
    conj_counts = {p: sum(1 for s in all_sents if p in s) for p in conj_forms}

    # Write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in all_sents:
            f.write(s + '\n')

    # Metadata sidecar
    meta = {
        "seed": args.seed,
        "output_count": len(all_sents),
        "source_counts": {
            "articles_sampled": len(articles_sampled),
            "articles_total": len(articles_filtered),
            "rare_conjunctions": len(rare_conj),
            "conjunction_sents": len(conj_sents),
            "rublimp_pool_scarce": len(scarce_sents),
            "enrichment_total": len(enrichment_list),
        },
        "benchmark_excluded": len(benchmark),
        "conjunction_forms": conj_counts,
        "note": "NO RuBLiMP benchmark, NO wiki_200k, NO Taiga proza. Pool used for scarce mining only.",
    }
    meta_path = output_path.with_suffix('.meta.json')
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nOutput: {len(all_sents)} sentences → {output_path}")
    print(f"Source mix: {meta['source_counts']}")
    print(f"Conjunction forms: {conj_counts}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
