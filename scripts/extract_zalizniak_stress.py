#!/usr/bin/env python3
"""Extract stress positions from Zaliznyak 2010 grammatical dictionary.

Source: https://github.com/gramdict/zalizniak-2010 (CC BY-NC)
6th edition, ~110k entries with stress marks (U+0301 combining acute accent).

Input: cloned repo at --input path
Output: JSON dict {"word": stress_char_index, ...}

Stress encoding:
- U+0301 (combining acute accent) after vowel = primary stress
- U+0300 (combining grave accent) after vowel = secondary stress (ignored)
- ё = always stressed (used when no explicit U+0301 present)

Usage:
    python scripts/extract_zalizniak_stress.py \
        --input /tmp/zalizniak-2010/dictionary \
        --output scripts/zalizniak_stress.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata


VOWELS = set("аеёиоуыэюя")


def extract_stress(word_raw: str) -> tuple[str, int]:
    """Extract clean word and stress position from accented form.

    Returns (clean_word, stress_char_index) where stress_char_index is
    0-indexed into the clean word. Returns -1 if no stress found.
    """
    # NFC first to recompose ё (е + U+0308 → ё).
    # U+0301 (acute) does NOT compose with Cyrillic in NFC, so it stays.
    nfc = unicodedata.normalize("NFC", word_raw)

    clean_chars = []
    stress_pos = -1

    for c in nfc:
        if c == "\u0301":  # Combining acute accent = primary stress
            if clean_chars:
                stress_pos = len(clean_chars) - 1
        elif c == "\u0300":  # Combining grave accent = secondary stress
            pass  # Skip
        else:
            clean_chars.append(c)

    clean = "".join(clean_chars)

    # If no explicit stress mark, check for ё (always stressed)
    if stress_pos < 0:
        for i, c in enumerate(clean.lower()):
            if c == "ё":
                stress_pos = i
                break

    return clean, stress_pos


def parse_entry_word(line: str) -> str | None:
    """Extract the headword from a Zaliznyak dictionary line.

    Handles numbering prefixes (1/, 2-3/) and returns the first word token.
    """
    line = line.strip()
    if not line:
        return None

    # Strip numbering prefix: "1/", "2-3/", etc.
    m = re.match(r"^[\d/\-]+/", line)
    word_part = line[m.end():] if m else line

    # Word is first whitespace-delimited token
    tokens = word_part.split()
    if not tokens:
        return None

    return tokens[0]


def main():
    parser = argparse.ArgumentParser(
        description="Extract stress from Zaliznyak 2010 dictionary"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to dictionary/ dir from gramdict/zalizniak-2010 repo",
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output JSON file",
    )
    args = parser.parse_args()

    dict_path = args.input
    if not os.path.isdir(dict_path):
        print(f"Not a directory: {dict_path}", file=sys.stderr)
        sys.exit(1)

    results: dict[str, int] = {}
    total = 0
    has_stress = 0
    skipped = 0

    for dirpath, _dirs, files in os.walk(dict_path):
        for fname in sorted(files):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(dirpath, fname)
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    word_raw = parse_entry_word(line)
                    if not word_raw:
                        continue

                    clean, stress_pos = extract_stress(word_raw)
                    total += 1

                    # Skip non-alpha, single-char, or hyphenated words
                    clean_lower = clean.lower()
                    if not clean_lower.isalpha() or len(clean_lower) < 2:
                        skipped += 1
                        continue

                    if stress_pos >= 0:
                        has_stress += 1

                    # Store (prefer first occurrence if duplicates)
                    if clean_lower not in results or (
                        results[clean_lower] < 0 and stress_pos >= 0
                    ):
                        results[clean_lower] = stress_pos

    print(f"Total entries: {total}")
    print(f"Skipped (non-alpha/short/hyphenated): {skipped}")
    print(f"Extracted: {len(results)} unique words")
    print(f"  With stress: {has_stress}")
    print(f"  Without stress: {total - has_stress - skipped}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"\nWritten to {args.output} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
