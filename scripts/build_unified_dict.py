#!/usr/bin/env python3
"""Build unified morpheme+stress dictionary.

Merges:
1. Existing morpheme_dict.pickle (93k, cleaned)
2. Existing stress_dict.json (49k)
3. New stress annotations from russtress (batch_stress.py output)
4. New morpheme annotations from Morphberta (batch_morphemes.py output)

Output format (JSON):
{
  "церемония": {"s": 5, "m": [["церемониj", "R"], ["я", "E"]]},
  "офицер": {"s": 4, "m": [["офиц", "R"], ["ер", "S"]]},
  ...
}

Keys: "s" = stress char index (-1 = unknown), "m" = morphemes (null = unknown)
Morpheme types: R=root, P=prefix, S=suffix, E=ending, L=link

Usage:
    uv run python scripts/build_unified_dict.py \
        --stress-extra /tmp/stress_results.json \
        --morphemes-extra /tmp/morphberta_results.json \
        --output src/synterr/data/russian/unified_dict.json
"""

import argparse
import json
import pickle
import sys
from pathlib import Path


MORPH_TYPE_MAP = {
    "PREF": "P",
    "ROOT": "R",
    "SUFF": "S",
    "END": "E",
    "LINK": "L",
}


def parse_morpholog_entry(entry: list) -> list[list[str]] | None:
    """Parse morpholog pickle entry into [["text", "type"], ...] format.

    Returns None for garbage entries.
    """
    if not isinstance(entry, list) or entry in [[""], []]:
        return None

    result = []
    for m in entry:
        if not isinstance(m, str) or not m:
            return None
        if "\n" in m or ("=" in m and len(m) > 10):
            # Hit garbage — return what we have so far if substantial
            return result if len(result) >= 2 else None

        if m.endswith("-") and not m.startswith("-"):
            result.append([m[:-1], "P"])
        elif m.startswith("-"):
            result.append([m[1:], "S"])
        elif m.startswith("+"):
            result.append([m[1:], "E"])
        elif "=" in m:
            result.append([m.replace("=", ""), "L"])
        else:
            result.append([m, "R"])

    return result if result else None


def main():
    parser = argparse.ArgumentParser(description="Build unified morpheme+stress dict")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    parser.add_argument("--stress-extra", help="Extra stress results JSON from batch_stress.py")
    parser.add_argument("--morphemes-extra", help="Extra morpheme results JSON from Morphberta")
    args = parser.parse_args()

    src = Path(__file__).parent.parent / "src" / "synterr" / "data" / "russian"

    # Load existing data
    print("Loading existing dictionaries...")
    with open(src / "morpheme_dict.pickle", "rb") as f:
        morph_raw = pickle.load(f)
    with open(src / "stress_dict.json", encoding="utf-8") as f:
        stress_raw = json.load(f)

    # Load extras if provided
    stress_extra = {}
    if args.stress_extra:
        with open(args.stress_extra, encoding="utf-8") as f:
            stress_extra = json.load(f)
        print(f"  Loaded {len(stress_extra)} extra stress annotations")

    morphemes_extra = {}
    if args.morphemes_extra:
        with open(args.morphemes_extra, encoding="utf-8") as f:
            morphemes_extra = json.load(f)
        print(f"  Loaded {len(morphemes_extra)} extra morpheme annotations")

    # Collect all words
    all_words = set()
    all_words.update(w for w in morph_raw if isinstance(w, str) and w.isalpha() and len(w) >= 2)
    all_words.update(w for w in stress_raw if isinstance(w, str) and w.isalpha() and len(w) >= 2)
    all_words.update(stress_extra.keys())
    all_words.update(morphemes_extra.keys())

    print(f"Total words: {len(all_words)}")

    # Build unified dict
    unified = {}
    has_stress = 0
    has_morph = 0

    for word in sorted(all_words):
        entry = {}

        # Stress: prefer existing, then extra
        if word in stress_raw and stress_raw[word] >= 0:
            entry["s"] = stress_raw[word]
            has_stress += 1
        elif word in stress_extra and stress_extra[word] >= 0:
            entry["s"] = stress_extra[word]
            has_stress += 1
        else:
            entry["s"] = -1

        # Morphemes: prefer existing (cleaned), then extra
        morph_parsed = None
        if word in morph_raw:
            morph_parsed = parse_morpholog_entry(morph_raw[word])
        if morph_parsed is None and word in morphemes_extra:
            morph_parsed = morphemes_extra[word]

        if morph_parsed:
            entry["m"] = morph_parsed
            has_morph += 1

        unified[word] = entry

    # Stats
    both = sum(1 for e in unified.values() if e.get("s", -1) >= 0 and e.get("m"))
    print(f"\nUnified dict: {len(unified)} entries")
    print(f"  Has stress: {has_stress} ({has_stress*100//len(unified)}%)")
    print(f"  Has morphemes: {has_morph} ({has_morph*100//len(unified)}%)")
    print(f"  Has both: {both} ({both*100//len(unified)}%)")

    # Write
    output = Path(args.output)
    with output.open("w", encoding="utf-8") as f:
        json.dump(unified, f, ensure_ascii=False)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nWritten to {output} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
