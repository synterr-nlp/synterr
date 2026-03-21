#!/usr/bin/env python3
"""Mine ALL sentences containing scarce morphological/spelling forms.

Exhaustive grep across all available sources. No cap — keeps every match.
Deduplicates across sources, records provenance per sentence.

Sources:
  - RuBLiMP pool (rublimp_pool_sents.txt)
  - Taiga Fontanka/Interfax/Lenta (full archives via corus)
  - Wiki dump (ruwiki XML bz2)

Usage:
    uv run python scripts/mine_scarce_sents.py \
        --rublimp-pool data/rublimp_pool_sents.txt \
        --taiga-fontanka data/taiga/Fontanka.tar.gz \
        --taiga-interfax data/taiga/Interfax.tar.gz \
        --taiga-lenta data/taiga/Lenta.tar.gz \
        --wiki ~/Projects/research/gector/data/ruwiki-latest-pages-articles.xml.bz2 \
        -o data/scarce_sents_v4.txt \
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path


# Scarce patterns — tightly scoped to match what handlers actually need.
#
# IMPORTANT: patterns for common words (чтобы, также, администрации)
# are excluded — they appear naturally in any text pool. Only truly
# scarce forms that need enrichment are listed here.

SCARCE_PATTERNS = re.compile(
    # === Truly rare forms (need enrichment) ===
    #
    # Numerals: полтора/полторы/полтораста (all forms)
    r'\bполтора\b|\bполторы\b|\bполтораста\b|\bполутора\b|\bполутораста\b'
    # -таки (any position)
    r'|\bтаки\b'
    # пол- compounds with dash (пол-лимона, пол-Москвы)
    r'|пол-[а-яёА-ЯЁ]'
    #
    # Diminutive suffixes -еньк/-оньк/-иньк (handler targets nouns only,
    # but mining by suffix is okay — маленький etc. won't hurt as source text)
    r'|[а-яё]еньк[а-яё]*\b|[а-яё]оньк[а-яё]*\b|[а-яё]иньк[а-яё]*\b'
    #
    # Separate conjunction forms ONLY (solid forms are common, don't need mining)
    r'|\bчто бы\b|\bтак же\b|\bза то\b|\bот того\b'
    r'|\bпри том\b|\bпри чём\b|\bпри чем\b'
    # Rare solid conjunctions (оттого/причём/притом are genuinely uncommon)
    r'|\bоттого\b|\bотчего\b|\bпричём\b|\bпричем\b|\bпритом\b'
    #
    # -инск/-енск: place-name adjectives where suffix is confusable
    # (керченский↔керчинский, ялтинский↔ялтенский)
    # Short stems (3-5 chars) exclude медицинский, украинский etc.
    r'|[а-яё]{3,5}инск[а-яё]*\b|[а-яё]{3,5}енск[а-яё]*\b'
    #
    # -ице/-ицо/-ецо/-еце: neuter diminutives only
    # Short words (5-8 chars total) exclude администрации, полиции
    r'|\b[а-яё]{3,6}ице\b|\b[а-яё]{3,6}ицо\b|\b[а-яё]{3,6}ецо\b|\b[а-яё]{3,6}еце\b'
    #
    # === Moderately rare (cap-worthy but useful) ===
    #
    # Compound adjectives (hyphenated, from handler wordlist)
    r'|\bвоенно-|\bнаучно-|\bторгово-|\bсоциально-|\bобщественно-'
    r'|\bучебно-|\bкультурно-|\bнародно-|\bмолочно-|\bплодово-'
    r'|\bремонтно-|\bсердечно-|\bкожно-|\bмассово-|\bмясо-'
    r'|\bотчётно-|\bпартийно-|\bрусско-|\bангло-|\bфранко-'
    r'|\bсеверо-|\bюго-'
    #
    # Frozen phraseological pairs (very rare in edited text)
    r'|\bни слуху\b|\bни духу\b|\bни бе\b|\bни ме\b'
    r'|\bни рыба\b|\bни мясо\b|\bни свет\b|\bни заря\b'
    r'|\bни жив\b|\bни мёртв\b|\bни пуха\b|\bни пера\b'
    r'|\bни кола\b|\bни двора\b|\bни шатко\b|\bни валко\b'
    #
    # Indivisible expressions (цельные по смыслу)
    r'|\bкак следует\b|\bкак попало\b|\bмало кто\b|\bмало что\b'
    r'|\bнеизвестно кто\b|\bнеизвестно что\b|\bнеизвестно где\b'
    r'|\bчто угодно\b|\bкто угодно\b|\bгде угодно\b|\bкуда попало\b'
    r'|\bоткуда ни возьмись\b|\bкак ни в чём не бывало\b'
    #
    # Collocations (trigger verbs — rare in the right context)
    r'|\bзагладить\b|\bзакадычный\b|\bодержать\b|\bнанести\b'
    r'|\bпридавать\b|\bвыдвинуть\b',
    re.IGNORECASE,
)


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


def scan_plain(path: str, source_name: str, results: dict[str, str]) -> int:
    """Scan a plain text file. Returns number of new matches."""
    added = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if s and s not in results and SCARCE_PATTERNS.search(s):
                if is_good_sentence(s):
                    results[s] = source_name
                    added += 1
    return added



def main():
    parser = argparse.ArgumentParser(description="Mine all scarce-form sentences")
    parser.add_argument("inputs", nargs="+", help="Plain text files (one sentence per line)")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cap", type=int, default=5000,
                        help="Max sentences per pattern category (0=no cap)")
    args = parser.parse_args()

    # sentence → first source that found it
    results: dict[str, str] = {}

    for path in args.inputs:
        name = Path(path).stem
        print(f"=== {name} ===")
        n = scan_plain(path, name, results)
        print(f"  +{n} new (total: {len(results)})")

    rng = random.Random(args.seed)

    # Cap overrepresented categories via reservoir sampling
    if args.cap > 0:
        CAP_PATTERNS = {
            "insk_ensk": re.compile(r'[а-яё]{3,5}инск|[а-яё]{3,5}енск', re.I),
            "its_ets": re.compile(r'\b[а-яё]{3,6}ице\b|\b[а-яё]{3,6}ицо\b|\b[а-яё]{3,6}ецо\b|\b[а-яё]{3,6}еце\b', re.I),
            "conjunctions_solid": re.compile(r'\bоттого\b|\bотчего\b|\bпричём\b|\bпричем\b|\bпритом\b', re.I),
            "compound_adj": re.compile(r'военно-|научно-|торгово-|социально-|общественно-|северо-|юго-', re.I),
        }

        for cat_name, cat_pat in CAP_PATTERNS.items():
            matching = [s for s in results if cat_pat.search(s)]
            if len(matching) > args.cap:
                # Keep cap via reservoir, remove the rest
                rng.shuffle(matching)
                to_remove = set(matching[args.cap:])
                for s in to_remove:
                    del results[s]
                print(f"  Capped {cat_name}: {len(matching)} → {args.cap}")

    # Sort for reproducibility, then shuffle with seed
    sents_sorted = sorted(results.keys())
    rng.shuffle(sents_sorted)

    # Write sentences
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for s in sents_sorted:
            f.write(s + '\n')

    # Count by source
    from collections import Counter
    source_counts = Counter(results.values())

    # Count by pattern category
    all_sents = list(results.keys())
    pattern_counts = {
        "conjunctions_solid": sum(1 for s in all_sents if re.search(r'\bоттого\b|\bчтобы\b|\bтакже\b|\bзато\b|\bпричём\b|\bпричем\b|\bпритом\b|\bтоже\b|\bотчего\b', s, re.I)),
        "conjunctions_separate": sum(1 for s in all_sents if re.search(r'\bчто бы\b|\bтак же\b|\bза то\b|\bот того\b|\bпри том\b|\bпри чём\b|\bпри чем\b', s, re.I)),
        "poltora": sum(1 for s in all_sents if re.search(r'полтора|полторы|полтораста|полутора|полутораста', s, re.I)),
        "taki": sum(1 for s in all_sents if re.search(r'\bтаки\b', s, re.I)),
        "enk_onk_ink": sum(1 for s in all_sents if re.search(r'еньк|оньк|иньк', s, re.I)),
        "insk_ensk": sum(1 for s in all_sents if re.search(r'инск|енск', s, re.I)),
        "pol_dash": sum(1 for s in all_sents if re.search(r'пол-[а-яё]', s, re.I)),
        "its_ets": sum(1 for s in all_sents if re.search(r'ице\b|ицо\b|ецо\b|еце\b', s, re.I)),
        "compound_adj": sum(1 for s in all_sents if re.search(r'военно-|научно-|торгово-|социально-|общественно-|северо-|юго-', s, re.I)),
        "parenthetical": sum(1 for s in all_sents if re.search(r'\bконечно\b|\bвероятно\b|\bкажется\b|\bпожалуй\b|\bвпрочем\b|\bнаверное\b|\bразумеется\b', s, re.I)),
        "frozen_phrases": sum(1 for s in all_sents if re.search(r'ни слуху|ни пуха|ни кола|ни рыба|и стар', s, re.I)),
        "indivisible": sum(1 for s in all_sents if re.search(r'как следует|как попало|мало кто|что угодно|откуда ни возьмись', s, re.I)),
        "collocations": sum(1 for s in all_sents if re.search(r'\bзагладить\b|\bзакадычный\b|\bодержать\b|\bнанести\b|\bпридавать\b', s, re.I)),
    }

    # Metadata
    meta = {
        "seed": args.seed,
        "total": len(results),
        "source_counts": dict(source_counts.most_common()),
        "pattern_counts": pattern_counts,
    }
    meta_path = output_path.with_suffix('.meta.json')
    with meta_path.open('w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n=== Results ===")
    print(f"Total unique: {len(results)}")
    print(f"By source: {dict(source_counts.most_common())}")
    print(f"By pattern: {pattern_counts}")
    print(f"Output: {output_path}")
    print(f"Metadata: {meta_path}")


if __name__ == '__main__':
    main()
