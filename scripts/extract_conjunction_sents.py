#!/usr/bin/env python3
"""Extract sentences containing separate conjunction forms from text dumps.

Targets sentences with "что бы", "так же", "за то", "от того", "при чём/чем/том"
where the words are genuinely separate (not part of the solid conjunction).

Uses reservoir sampling for unbiased, reproducible selection.

Usage:
    uv run python scripts/extract_conjunction_sents.py \
        ~/Projects/research/gector/ruwiki-latest-pages-articles.xml.bz2 \
        -o data/conjunction_sents.txt --target 500 --seed 42

    # Plain text input (librusec, etc.):
    uv run python scripts/extract_conjunction_sents.py \
        --plain librusec_sents.txt \
        -o data/conjunction_librusec.txt --target 500 --seed 42
"""

from __future__ import annotations

import argparse
import bz2
import json
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import mwparserfromhell
from razdel import sentenize


# Patterns: separate forms
TARGETS = {
    "что бы": re.compile(r'\bчто бы\b(?!\w)'),
    "так же": re.compile(r'\bтак же\b'),
    "за то": re.compile(r'\bза то\b'),
    "от того": re.compile(r'\bот того\b'),
    "при том": re.compile(r'\bпри том\b'),
    "при чём": re.compile(r'\bпри чём\b'),
    "при чем": re.compile(r'\bпри чем\b'),
}

# False positive: "что бы" followed by verb forms = not the particle
CHTO_BY_FALSE = re.compile(r'\bчто бы(л[аоие]?|ва[елт]|вш)\b')


def clean_wikitext(raw: str) -> str:
    wikicode = mwparserfromhell.parse(raw)
    text = wikicode.strip_code()
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\u0301', '')
    return text.strip()


def is_good_sentence(s: str) -> bool:
    if len(s) < 20 or len(s) > 500:
        return False
    if not re.match(r'^[А-ЯЁ«"]', s):
        return False
    if not re.search(r'[.!?»"]$', s):
        return False
    cyrillic = sum(1 for c in s if '\u0400' <= c <= '\u04ff')
    if cyrillic / max(len(s), 1) < 0.5:
        return False
    if '|' in s or '{{' in s or '[[' in s:
        return False
    if re.search(r'\(\s*\)', s):
        return False
    return True


def _match_sentence(s: str) -> str | None:
    """Return the matched target key, or None."""
    for key, pattern in TARGETS.items():
        if pattern.search(s):
            if key == "что бы" and CHTO_BY_FALSE.search(s):
                continue
            return key
    return None


def _reservoir_add(
    reservoirs: dict[str, list[str]],
    seen: dict[str, int],
    key: str,
    sentence: str,
    target: int,
    rng: random.Random,
) -> None:
    """Reservoir sampling: maintain a uniform random sample of size `target`."""
    seen[key] += 1
    n = seen[key]
    if n <= target:
        reservoirs[key].append(sentence)
    else:
        # Replace with probability target/n
        j = rng.randint(0, n - 1)
        if j < target:
            reservoirs[key][j] = sentence


def iter_wiki_sentences(dump_path: str):
    """Yield sentences from a MediaWiki XML dump (.xml.bz2)."""
    ns_tag = '{http://www.mediawiki.org/xml/export-0.11/}'
    articles = 0
    with bz2.open(dump_path, 'rt', encoding='utf-8') as f_in:
        for event, elem in ET.iterparse(f_in, events=('end',)):
            if not elem.tag.endswith('}page') and elem.tag != 'page':
                continue

            text_elem = elem.find(f'.//{ns_tag}text')
            if text_elem is None:
                text_elem = elem.find('.//text')
            if text_elem is None or not text_elem.text:
                elem.clear()
                continue

            raw = text_elem.text
            if raw.strip().upper().startswith('#REDIRECT') or \
               raw.strip().upper().startswith('#ПЕРЕНАПРАВЛЕНИЕ'):
                elem.clear()
                continue

            articles += 1
            if articles % 50000 == 0:
                print(f"  articles: {articles}", flush=True)

            # Quick check before expensive parsing
            raw_lower = raw.lower()
            has_any = any(k in raw_lower for k in TARGETS)
            if not has_any:
                elem.clear()
                continue

            text = clean_wikitext(raw)
            for sent in sentenize(text):
                s = sent.text.strip()
                if is_good_sentence(s):
                    yield s

            elem.clear()

    print(f"  total articles scanned: {articles}")


def iter_plain_sentences(path: str):
    """Yield sentences from a plain text file (one per line)."""
    count = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s:
                yield s
                count += 1
                if count % 500000 == 0:
                    print(f"  lines: {count}", flush=True)
    print(f"  total lines: {count}")


def iter_taiga_sentences(taiga_path: str, source: str):
    """Yield sentences from a Taiga corpus via corus.

    source: one of 'fontanka', 'interfax', 'lenta'
    """
    from razdel import sentenize

    if source == "fontanka":
        from corus import load_taiga_fontanka as loader
    elif source == "interfax":
        from corus import load_taiga_interfax as loader
    elif source == "lenta":
        from corus import load_taiga_lenta as loader
    else:
        raise ValueError(f"Unknown Taiga source: {source}")

    count = 0
    for rec in loader(taiga_path):
        text = rec.text if hasattr(rec, 'text') else str(rec)
        for sent in sentenize(text):
            s = sent.text.strip()
            if is_good_sentence(s):
                yield s
                count += 1
        if count % 10000 == 0 and count > 0:
            print(f"  {source}: {count} sentences", flush=True)
    print(f"  {source}: {count} total")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", nargs="?", help="Wiki XML dump (.xml.bz2)")
    parser.add_argument("--plain", nargs="*", help="Plain text files (one sentence per line)")
    parser.add_argument("--taiga", help="Path to retagged_taiga.tar.gz")
    parser.add_argument("--taiga-sources", nargs="*", default=["fontanka", "interfax", "lenta"],
                        help="Which Taiga sub-corpora to use (default: fontanka interfax lenta)")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--target", type=int, default=500,
                        help="Target sentences per conjunction form")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.dump and not args.plain and not args.taiga:
        parser.error("Provide at least one source: wiki dump, --plain files, or --taiga")

    rng = random.Random(args.seed)
    reservoirs: dict[str, list[str]] = {k: [] for k in TARGETS}
    seen: dict[str, int] = {k: 0 for k in TARGETS}

    # Collect from all sources
    if args.dump:
        print(f"Scanning wiki dump: {args.dump}")
        for s in iter_wiki_sentences(args.dump):
            key = _match_sentence(s)
            if key:
                _reservoir_add(reservoirs, seen, key, s, args.target, rng)

    if args.plain:
        for path in args.plain:
            print(f"Scanning plain text: {path}")
            for s in iter_plain_sentences(path):
                key = _match_sentence(s)
                if key:
                    _reservoir_add(reservoirs, seen, key, s, args.target, rng)

    if args.taiga:
        for source in args.taiga_sources:
            print(f"Scanning Taiga/{source}: {args.taiga}")
            for s in iter_taiga_sentences(args.taiga, source):
                key = _match_sentence(s)
                if key:
                    _reservoir_add(reservoirs, seen, key, s, args.target, rng)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_sents = []
    for key in TARGETS:
        all_sents.extend(reservoirs[key])

    # Shuffle with seed for reproducibility
    rng.shuffle(all_sents)

    with output_path.open('w', encoding='utf-8') as f:
        for s in all_sents:
            f.write(s + '\n')

    # Save metadata sidecar
    meta_path = output_path.with_suffix('.meta.json')
    meta = {
        "seed": args.seed,
        "target_per_form": args.target,
        "sources": ([args.dump] if args.dump else [])
                   + (args.plain or [])
                   + ([f"taiga:{s}" for s in args.taiga_sources] if args.taiga else []),
        "seen": dict(seen),
        "sampled": {k: len(v) for k, v in reservoirs.items()},
        "total_sentences": len(all_sents),
    }
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nResults:")
    for key in TARGETS:
        print(f"  {key:>10s}: {seen[key]:6d} seen, {len(reservoirs[key]):4d} sampled")
    print(f"\nTotal: {len(all_sents)} sentences → {output_path}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
