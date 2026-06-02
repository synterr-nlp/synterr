#!/usr/bin/env python3
"""Build reproducible source text mix for SFT generation.

Pluggable sources, configurable proportions, seeded throughout.
Excludes RuBLiMP benchmark sentences to avoid contamination.
Reservoir-samples scarce forms to enrich conjunction/numeral coverage.

Usage:
    uv run python scripts/build_source_mix.py \
        --articles ~/Projects/research/gector/data/ru_kw_eval_datasets/data \
        --wiki data/wiki_200k.txt \
        --rublimp-pool data/rublimp_pool_sents.txt \
        --conjunction-sents data/conjunction_sents.txt \
        --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
        --output data/mixed_sources_v4.txt \
        --total 150000 --seed 42 \
        --proportions articles=0.30,wiki=0.15,rublimp_pool=0.45,conjunction=0.05,scarce=0.05
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


# ── Quality filter ──────────────────────────────────────────────────────────

def is_good_sentence(s: str) -> bool:
    s = s.strip()
    words = s.split()
    if len(words) < 8 or len(words) > 30:
        return False
    if not s or not s[0].isupper():
        return False
    if s[-1] not in '.!?»"':
        return False
    if any(x in s for x in ['УДК', 'ISBN', 'DOI', 'http', '©', '@', '{{', '[[', ']]']):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic < len(s.replace(' ', '')) * 0.6:
        return False
    return True


# ── Source extractors ───────────────────────────────────────────────────────

def load_articles(articles_dir: str) -> list[str]:
    """Extract sentences from JSONL zip archives (Habr, CyberLeninka, НГ, RT)."""
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
                                for s in _split_sentences(text):
                                    if is_good_sentence(s):
                                        sents.add(s)
                                        count += 1
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue
        except Exception as e:
            print(f"    Error in {zipname}: {e}")
        print(f"    {zipname}: {count}")
    return sorted(sents)


def load_wiki(wiki_path: str) -> list[str]:
    """Load pre-extracted wiki sentences."""
    sents = set()
    with open(wiki_path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s and is_good_sentence(s):
                sents.add(s)
    return sorted(sents)


def load_plain(path: str) -> list[str]:
    """Load a plain text file (one sentence per line), quality-filtered."""
    sents = set()
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s and is_good_sentence(s):
                sents.add(s)
    return sorted(sents)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sents = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for s in sents:
        s = s.strip()
        if any(x in s for x in ['http', 'www.', '{', '}', '()', '/**', '//', '==', '&&', '||']):
            continue
        result.append(s)
    return result


# ── Scarce form mining ──────────────────────────────────────────────────────

SCARCE_PATTERNS = re.compile(
    r'полтора|полторы|полтораста|полутора|полутораста'
    r'|\bтаки\b'
    r'|инск[а-яё]*\b|енск[а-яё]*\b'
    r'|пол-[а-яё]'
    r'|еньк[а-яё]*\b|оньк[а-яё]*\b'
    r'|ице\b|ицо\b|ецо\b|еце\b',
    re.IGNORECASE,
)


def extract_scarce(pool: list[str], existing: set[str]) -> list[str]:
    """Extract sentences containing scarce morphological forms."""
    result = []
    for s in pool:
        if s not in existing and SCARCE_PATTERNS.search(s):
            result.append(s)
    return result


# ── Benchmark exclusion ─────────────────────────────────────────────────────

def load_benchmark(benchmark_dir: str) -> set[str]:
    """Load all sentences from the RuBLiMP benchmark to exclude."""
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


# ── Reservoir sampling ──────────────────────────────────────────────────────

def reservoir_sample(pool: list[str], n: int, rng: random.Random) -> list[str]:
    """Reservoir sample n items from pool."""
    if len(pool) <= n:
        return pool.copy()
    reservoir = pool[:n]
    for i in range(n, len(pool)):
        j = rng.randint(0, i)
        if j < n:
            reservoir[j] = pool[i]
    return reservoir


# ── Main ────────────────────────────────────────────────────────────────────

def parse_proportions(s: str) -> dict[str, float]:
    """Parse 'key=val,key=val,...' into dict."""
    result = {}
    for part in s.split(','):
        k, v = part.strip().split('=')
        result[k.strip()] = float(v.strip())
    return result


DEFAULT_PROPORTIONS = {
    "articles": 0.30,
    "wiki": 0.15,
    "rublimp_pool": 0.40,
    "conjunction": 0.05,
    "scarce": 0.10,
}


def main():
    parser = argparse.ArgumentParser(description="Build reproducible source text mix")
    parser.add_argument("--articles", help="Path to ru_kw_eval_datasets/data/")
    parser.add_argument("--wiki", help="Path to pre-extracted wiki sentences")
    parser.add_argument("--rublimp-pool", help="Path to rublimp_pool_sents.txt")
    parser.add_argument("--conjunction-sents", help="Path to conjunction_sents.txt")
    parser.add_argument("--benchmark", required=True, help="Path to RuBLiMP/datasets/ (for exclusion)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--total", type=int, default=150000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--proportions", type=str, default=None,
                        help="Source proportions: articles=0.30,wiki=0.15,... (default: balanced)")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    props = parse_proportions(args.proportions) if args.proportions else DEFAULT_PROPORTIONS.copy()

    # Normalize proportions
    total_prop = sum(props.values())
    props = {k: v / total_prop for k, v in props.items()}

    print(f"Seed: {args.seed}")
    print(f"Target: {args.total}")
    print(f"Proportions: {props}")

    # Load benchmark exclusion set
    print("\n=== Loading benchmark exclusion set ===")
    benchmark = load_benchmark(args.benchmark)
    print(f"  {len(benchmark)} sentences to exclude")

    def exclude(sents: list[str]) -> list[str]:
        return [s for s in sents if s not in benchmark]

    # Load sources
    sources: dict[str, list[str]] = {}

    if args.articles and "articles" in props:
        print("\n=== Articles ===")
        raw = load_articles(args.articles)
        sources["articles"] = exclude(raw)
        print(f"  {len(raw)} raw → {len(sources['articles'])} after exclusion")

    if args.wiki and "wiki" in props:
        print("\n=== Wiki ===")
        raw = load_wiki(args.wiki)
        sources["wiki"] = exclude(raw)
        print(f"  {len(raw)} raw → {len(sources['wiki'])} after exclusion")

    if args.rublimp_pool and "rublimp_pool" in props:
        print("\n=== RuBLiMP Pool ===")
        raw = load_plain(args.rublimp_pool)
        sources["rublimp_pool"] = exclude(raw)
        print(f"  {len(raw)} raw → {len(sources['rublimp_pool'])} after exclusion")

    if args.conjunction_sents and "conjunction" in props:
        print("\n=== Conjunction sentences ===")
        raw = load_plain(args.conjunction_sents)
        sources["conjunction"] = exclude(raw)
        print(f"  {len(raw)} raw → {len(sources['conjunction'])} after exclusion")

    # Scarce form mining from rublimp pool
    if "scarce" in props and "rublimp_pool" in sources:
        print("\n=== Scarce form mining ===")
        # Collect all sentences already selected
        already = set()
        for name, sents in sources.items():
            if name != "rublimp_pool":
                already.update(sents)
        scarce = extract_scarce(sources["rublimp_pool"], already)
        sources["scarce"] = scarce
        print(f"  {len(scarce)} scarce-form sentences")

    # Sample from each source according to proportions
    print("\n=== Sampling ===")
    selected: list[str] = []
    selected_set: set[str] = set()
    source_counts: dict[str, int] = {}

    for name, proportion in props.items():
        if name not in sources:
            print(f"  {name}: SKIPPED (no data)")
            continue

        pool = sources[name]
        target_n = int(args.total * proportion)
        sampled = reservoir_sample(pool, target_n, rng)

        # Deduplicate against already selected
        deduped = []
        for s in sampled:
            if s not in selected_set:
                deduped.append(s)
                selected_set.add(s)

        selected.extend(deduped)
        source_counts[name] = len(deduped)
        print(f"  {name}: {len(deduped)}/{target_n} (pool: {len(pool)})")

    # Final shuffle
    rng.shuffle(selected)

    # Conjunction form counts
    conj_forms = ['что бы', 'так же', 'за то', 'от того', 'при чём', 'при том', 'при чем']
    conj_counts = {p: sum(1 for s in selected if p in s) for p in conj_forms}

    # Write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in selected:
            f.write(s + '\n')

    # Metadata sidecar
    meta_path = output_path.with_suffix('.meta.json')
    meta = {
        "seed": args.seed,
        "target": args.total,
        "output_count": len(selected),
        "proportions": props,
        "source_counts": source_counts,
        "benchmark_excluded": len(benchmark),
        "conjunction_forms": conj_counts,
    }
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n=== Output: {len(selected)} sentences → {output_path} ===")
    print(f"Source mix: {source_counts}")
    print(f"Conjunction forms: {conj_counts}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
