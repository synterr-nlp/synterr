#!/usr/bin/env python3
"""Batch morpheme segmentation using Morphberta-K.

Requires simpletransformers + transformers<5. Run in a venv with those installed,
or use: uv run --with 'simpletransformers>=0.70.5' --with 'transformers<5' python scripts/batch_morphemes.py ...

Input: one word per line
Output: JSON dict {"word": [["text", "type"], ...], ...}
  Types: R=root, P=prefix, S=suffix, E=ending, L=link

Usage:
    uv run --with 'simpletransformers>=0.70.5' --with 'transformers<5' \
        python scripts/batch_morphemes.py \
        -i scripts/need_morphemes.txt \
        -o scripts/morpheme_results.json \
        --model models/morphberta-k
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Morphberta-K uses BMES tagging scheme for morpheme segmentation:
# B-X = beginning of morpheme type X
# M-X = middle of morpheme type X
# E-X = end of morpheme type X
# S-X = single-char morpheme type X
# Where X is: ROOT, PREF, SUFF, END, LINK, HYPH, POSTFIX

TAG_TO_TYPE = {
    "ROOT": "R",
    "PREF": "P",
    "SUFF": "S",
    "END": "E",
    "LINK": "L",
    "HYPH": "L",
    "POSTFIX": "S",  # -ся, -сь → treat as suffix
}


def parse_bmes_tags(word: str, tags: list[str]) -> list[list[str]]:
    """Convert BMES character tags to morpheme list.

    Args:
        word: the original word (e.g. "приступить")
        tags: per-character BMES tags (e.g. ["B-PREF", "M-PREF", "E-PREF", ...])

    Returns:
        [["при", "P"], ["ступ", "R"], ["и", "S"], ["ть", "E"]]
    """
    if len(tags) != len(word):
        # Fallback: return whole word as root
        return [[word, "R"]]

    morphemes = []
    current_text = ""
    current_type = ""

    for char, tag in zip(word, tags):
        # Parse tag: "B-ROOT" → prefix="B", type="ROOT"
        if "-" in tag:
            prefix, morph_type = tag.split("-", 1)
        else:
            prefix, morph_type = tag, "ROOT"

        mapped_type = TAG_TO_TYPE.get(morph_type, "R")

        if prefix in ("B", "S"):
            # Start of new morpheme — flush previous
            if current_text:
                morphemes.append([current_text, current_type])
            current_text = char
            current_type = mapped_type
        else:
            # Continuation (M, E) or unknown
            current_text += char
            # Keep the type from the B tag

    # Flush last morpheme
    if current_text:
        morphemes.append([current_text, current_type])

    return morphemes


def main():
    parser = argparse.ArgumentParser(description="Batch morpheme segmentation with Morphberta-K")
    parser.add_argument("--input", "-i", required=True, help="Input word list (one per line)")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    parser.add_argument("--model", "-m", default="models/morphberta-k", help="Path to Morphberta-K model")
    parser.add_argument("--batch-size", type=int, default=64, help="Inference batch size")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found at {model_path}", file=sys.stderr)
        print("Download from https://ruscorpora.ru/license-content/neuromodels", file=sys.stderr)
        sys.exit(1)

    # Load words
    with open(args.input, encoding="utf-8") as f:
        words = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(words)} words")

    # Load model
    print(f"Loading Morphberta-K from {model_path}...")
    from simpletransformers.ner import NERModel

    model = NERModel(
        "roberta",
        str(model_path),
        use_cuda=False,
        args={"silent": True, "no_cache": True},
    )
    print("Model loaded.")

    # Process in batches
    # NERModel.predict expects list of sentences, where each "sentence" is a string
    # For single-word morpheme segmentation, each word is a "sentence" of characters
    results = {}
    total = len(words)

    for batch_start in range(0, total, args.batch_size):
        batch_end = min(batch_start + args.batch_size, total)
        batch_words = words[batch_start:batch_end]

        # Format for NER: each word becomes a space-separated string of characters
        sentences = [" ".join(list(w)) for w in batch_words]

        try:
            predictions, _ = model.predict(sentences)

            for word, pred in zip(batch_words, predictions):
                # pred is a list of dicts: [{"char": "tag"}, ...]
                tags = []
                for char_dict in pred:
                    for char, tag in char_dict.items():
                        tags.append(tag)

                morphemes = parse_bmes_tags(word, tags)
                results[word] = morphemes
        except Exception as e:
            print(f"  Error at batch {batch_start}: {e}", file=sys.stderr)
            # Add failed words with null
            for w in batch_words:
                results[w] = [[w, "R"]]

        if (batch_end) % (args.batch_size * 10) == 0 or batch_end == total:
            print(f"  {batch_end}/{total} ({batch_end * 100 // total}%)")

    # Write results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    print(f"Done. {len(results)} words written to {args.output}")


if __name__ == "__main__":
    main()
