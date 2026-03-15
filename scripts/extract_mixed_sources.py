#!/usr/bin/env python3
"""Extract diverse source sentences for SFT generation.

Sources:
  - RuBLiMP (Taktasheva et al. 2024): source_sentence from 45K minimal pairs
    (librusec 71%, wikinews 10%, Wikipedia 19%)
  - ru_kw_eval_datasets (Habr, CyberLeninka, НГ, Russia Today):
    sentence-split article content from JSONL zip archives
  - Wiki: pre-extracted clean Wikipedia sentences
  - Taiga proza (via corus): literary prose from proza.ru

Output: one sentence per line, deduplicated, shuffled with fixed seed.
Saves a .meta.json sidecar with per-source counts.

Usage:
    uv run python scripts/extract_mixed_sources.py \
        --rublimp ~/Projects/research/gector/data/RuBLiMP/datasets \
        --articles ~/Projects/research/gector/data/ru_kw_eval_datasets/data \
        --wiki data/wiki_200k.txt \
        --proza data/taiga/proza_ru.zip \
        --output data/mixed_sources_60k_v3.txt \
        --max-sentences 60000 --seed 42
"""
import argparse
import csv
import json
import os
import random
import re
import zipfile
from pathlib import Path


def is_good_sentence(s: str) -> bool:
    """Quality filter for extracted sentences."""
    s = s.strip()
    words = s.split()
    if len(words) < 8 or len(words) > 25:
        return False
    if not s[0].isupper():
        return False
    if s[-1] not in '.!?\u00bb"':  # .!?»"
        return False
    if any(x in s for x in ['УДК', 'ISBN', 'DOI', 'http', '\u00a9', '@', '{{', '[[', ']]']):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic < len(s.replace(' ', '')) * 0.6:
        return False
    return True


def extract_rublimp(rublimp_dir: str) -> set[str]:
    """Extract correct (source) sentences from RuBLiMP minimal pairs."""
    sents = set()
    for fname in os.listdir(rublimp_dir):
        if not fname.endswith('.csv'):
            continue
        with open(os.path.join(rublimp_dir, fname)) as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = row['source_sentence'].strip()
                if 5 <= len(s.split()) <= 30:
                    sents.add(s)
    return sents


def extract_sentences_from_text(text: str, min_words: int = 8, max_words: int = 25) -> list[str]:
    """Split text into sentences and filter."""
    sents = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for s in sents:
        s = s.strip()
        words = s.split()
        if min_words <= len(words) <= max_words:
            if any(x in s for x in ['http', 'www.', '{', '}', '()', '/**', '//', '==', '&&', '||']):
                continue
            cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
            if cyrillic < len(s.replace(' ', '')) * 0.5:
                continue
            result.append(s)
    return result


def extract_articles(articles_dir: str) -> set[str]:
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
                                for s in extract_sentences_from_text(text):
                                    sents.add(s)
                                    count += 1
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                continue
        except Exception as e:
            print(f"  Error in {zipname}: {e}")
        print(f"  {zipname}: {count} sentences")
    return sents


def extract_wiki(wiki_path: str) -> set[str]:
    """Read pre-extracted wiki sentences."""
    sents = set()
    with open(wiki_path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s and is_good_sentence(s):
                sents.add(s)
    return sents


def extract_taiga_proza(path: str, max_texts: int = 5000) -> set[str]:
    """Extract sentences from Taiga proza via corus."""
    import itertools
    from corus import load_taiga_proza

    sents = set()
    records = load_taiga_proza(path)
    count = 0
    for rec in itertools.islice(records, max_texts):
        text = rec.text if hasattr(rec, 'text') else str(rec)
        for s in extract_sentences_from_text(text):
            if is_good_sentence(s):
                sents.add(s)
                count += 1
    print(f"  Proza: {count} sentences from {max_texts} texts")
    return sents


def main():
    parser = argparse.ArgumentParser(description="Extract mixed source sentences for SFT generation")
    parser.add_argument("--rublimp", help="Path to RuBLiMP/datasets/ directory")
    parser.add_argument("--articles", help="Path to ru_kw_eval_datasets/data/ directory")
    parser.add_argument("--wiki", help="Path to pre-extracted wiki sentences file")
    parser.add_argument("--proza", help="Path to Taiga proza_ru.zip")
    parser.add_argument("--output", required=True, help="Output file (one sentence per line)")
    parser.add_argument("--max-sentences", type=int, default=60000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-proza-texts", type=int, default=5000,
                        help="Max proza texts to scan (full corpus is 1.7M)")
    args = parser.parse_args()

    source_counts = {}

    # RuBLiMP
    rublimp_sents = set()
    if args.rublimp:
        print("=== RuBLiMP ===")
        rublimp_raw = extract_rublimp(args.rublimp)
        rublimp_sents = {s for s in rublimp_raw if is_good_sentence(s)}
        source_counts["rublimp"] = len(rublimp_sents)
        print(f"  {len(rublimp_raw)} raw → {len(rublimp_sents)} filtered")

    # Articles
    articles_sents = set()
    if args.articles:
        print("\n=== Articles ===")
        articles_raw = extract_articles(args.articles)
        articles_sents = {s for s in articles_raw if is_good_sentence(s)}
        source_counts["articles"] = len(articles_sents)
        print(f"  {len(articles_raw)} raw → {len(articles_sents)} filtered")

    # Wiki
    wiki_sents = set()
    if args.wiki:
        print("\n=== Wiki ===")
        wiki_sents = extract_wiki(args.wiki)
        source_counts["wiki"] = len(wiki_sents)
        print(f"  {len(wiki_sents)} sentences")

    # Taiga proza
    proza_sents = set()
    if args.proza:
        print(f"\n=== Taiga Proza (max {args.max_proza_texts} texts) ===")
        proza_sents = extract_taiga_proza(args.proza, max_texts=args.max_proza_texts)
        source_counts["taiga_proza"] = len(proza_sents)

    # Combine, deduplicate, shuffle
    all_sents = sorted(rublimp_sents | articles_sents | wiki_sents | subtitles_sents | proza_sents)
    print(f"\n=== Combined unique: {len(all_sents)} ===")

    rng = random.Random(args.seed)
    rng.shuffle(all_sents)
    output = all_sents[:args.max_sentences]

    # Conjunction form counts in output
    conj_forms = ['что бы', 'так же', 'за то', 'от того', 'при чём', 'при том', 'при чем']
    conj_counts = {p: sum(1 for s in output if p in s) for p in conj_forms}

    lens = [len(s.split()) for s in output]
    print(f"\n=== Output: {len(output)} sentences ===")
    print(f"  Avg: {sum(lens)/len(lens):.1f} words, median: {sorted(lens)[len(lens)//2]}")
    print(f"  Conjunction forms: {conj_counts}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in output:
            f.write(s + '\n')
    print(f"  Written to {output_path}")

    # Save metadata sidecar
    meta_path = output_path.with_suffix('.meta.json')
    meta = {
        "seed": args.seed,
        "max_sentences": args.max_sentences,
        "total_unique": len(all_sents),
        "output_count": len(output),
        "source_counts": source_counts,
        "conjunction_forms_in_output": conj_counts,
    }
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  Metadata: {meta_path}")


if __name__ == '__main__':
    main()
