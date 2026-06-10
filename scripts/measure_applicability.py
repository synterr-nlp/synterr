#!/usr/bin/env python3
"""Measure per-subtype fire rates for all handlers over a text corpus.

For every sentence and every token index, tries every registered handler
(can_apply + apply on a throwaway copy) and counts emissions by error_type.
The output ranks subtypes by emissions per 1k sentences so starving error
classes can be targeted by pool mining (mine_semgrex.py / mine_scarce_sents.py).

Usage:
    uv run python scripts/measure_applicability.py -i lenta_50k.txt -n 2000 \
        -o data/applicability_report.json [--tries 3] [--starving-below 5]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", type=Path, required=True,
                    help="text file, one sentence per line")
    ap.add_argument("-n", "--limit", type=int, default=2000)
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="JSON report path (optional)")
    ap.add_argument("--tries", type=int, default=3,
                    help="apply() attempts per applicable index (multi-subtype "
                         "handlers pick a random subtype per attempt)")
    ap.add_argument("--starving-below", type=float, default=5.0,
                    help="flag subtypes emitting fewer than this per 1k sentences")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    sentences = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and len(line.split()) >= 5:
                sentences.append(line)
                if len(sentences) >= args.limit:
                    break
    if not sentences:
        print("no usable sentences", file=sys.stderr)
        return 1
    print(f"read {len(sentences)} sentences from {args.input}", file=sys.stderr)

    from synterr.core.registry import get_language
    from synterr.languages.russian.errors import get_all_handlers

    lang = get_language("ru")
    analyzer = lang.get_analyzer(use_depparse=True, backend="stanza")
    handlers = get_all_handlers()
    rng = random.Random(args.seed)

    emissions: Counter[str] = Counter()           # error_type -> count
    handler_sentences: Counter[str] = Counter()   # handler.name -> sentences with >=1 applicable idx
    handler_attempts: Counter[str] = Counter()
    handler_successes: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    n_done = 0
    for start in range(0, len(sentences), args.batch_size):
        batch = sentences[start : start + args.batch_size]
        for tokens in analyzer.analyze_batch(batch):
            n_done += 1
            if n_done % 500 == 0:
                print(f"  {n_done}/{len(sentences)}", file=sys.stderr)
            original = [t.text for t in tokens]
            for handler in handlers:
                applicable = [i for i in range(len(tokens))
                              if handler.can_apply(tokens, i)]
                if not applicable:
                    continue
                handler_sentences[handler.name] += 1
                for idx in applicable:
                    for _ in range(args.tries):
                        sentence = original.copy()
                        handler_attempts[handler.name] += 1
                        try:
                            result = handler.apply(tokens, sentence, idx, set(),
                                                   rng=rng)
                        except Exception as exc:  # noqa: BLE001 — survey must finish
                            emissions[f"{handler.name}:EXCEPTION:{type(exc).__name__}"] += 1
                            continue
                        if result is None:
                            continue
                        handler_successes[handler.name] += 1
                        emissions[result.error_type] += 1
                        if len(examples[result.error_type]) < 2:
                            examples[result.error_type].append(
                                f"{result.original} -> {result.corrupted} | {' '.join(original)[:120]}"
                            )

    per_1k = {et: round(c * 1000 / n_done, 2) for et, c in emissions.items()}

    # every declared subtype, including ones that never fired
    declared = {}
    for h in handlers:
        for st in getattr(h, "subtypes", [h.name]):
            declared[f"{h.name}:{st}" if st != h.name else h.name] = h.name

    print(f"\n=== emissions per 1k sentences (n={n_done}, tries={args.tries}) ===")
    for et, rate in sorted(per_1k.items(), key=lambda kv: -kv[1]):
        print(f"{rate:9.2f}  {et}  ({emissions[et]})")

    fired_types = set(emissions)
    starving = sorted(
        et for et in per_1k if per_1k[et] < args.starving_below
    )
    never = sorted(
        d for d in declared
        if not any(ft == d or ft.startswith(d.split(':')[-1]) or d.split(':')[-1] in ft
                   for ft in fired_types)
    )
    print(f"\n=== starving (< {args.starving_below}/1k) ===")
    for et in starving:
        print(f"  {et}  ({per_1k[et]}/1k)")
    print("\n=== declared but never fired ===")
    for d in never:
        print(f"  {d}")

    if args.output:
        report = {
            "input": str(args.input),
            "n_sentences": n_done,
            "tries": args.tries,
            "seed": args.seed,
            "emissions": dict(emissions),
            "per_1k": per_1k,
            "handler_sentence_coverage": {
                h: round(c * 1000 / n_done, 1)
                for h, c in handler_sentences.items()
            },
            "handler_success_rate": {
                h: round(handler_successes[h] / handler_attempts[h], 3)
                for h in handler_attempts
            },
            "starving": starving,
            "never_fired": never,
            "examples": dict(examples),
        }
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"\nwrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
