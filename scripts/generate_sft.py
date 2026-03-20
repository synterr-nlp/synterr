#!/usr/bin/env python3
"""Generate SFT training data — force-apply per LoRuGEC rule (48 rules).

Maps each of the 48 LoRuGEC rules to a handler+subtype, then force-applies
with the same distribution as the benchmark.

Usage:
    uv run python scripts/generate_sft.py \
        -n 50000 --depparse \
        -i lenta_50k.txt -o data/qwen_sft_50k.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from synterr.lorugec import (
    LORUGEC_RULES,
    extract_subtype as _extract_subtype_fn,
    get_lorugec_distribution,
)


def main():
    parser = argparse.ArgumentParser(description="Generate SFT data per LoRuGEC rule")
    parser.add_argument("-i", "--input", required=True, help="Input sentences file")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL file")
    parser.add_argument("-n", "--total", type=int, default=50000, help="Total examples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--depparse", action="store_true", help="Enable dep parsing")
    parser.add_argument("--max-input", type=int, default=60000, help="Max input sentences")
    parser.add_argument("--batch-size", type=int, default=128, help="Stanza batch size")
    parser.add_argument("--balance-directions", action="store_true",
                        help="Cap split/merge pairs to min(split, merge) count")
    args = parser.parse_args()

    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    # Read LoRuGEC distribution
    rule_counts = get_lorugec_distribution()
    total_lorugec = sum(rule_counts.values())

    # Compute target per rule, scaled to args.total
    targets: dict[str, int] = {}
    for rule, count in rule_counts.items():
        targets[rule] = max(1, round(count / total_lorugec * args.total))

    # Group rules by (handler, subtype, word_filter) to avoid redundant scanning
    # Rules with different word_filters get their own group even if handler+subtype match
    from collections import defaultdict
    subtype_groups: dict[tuple[str, str, str | None], list[str]] = defaultdict(list)
    for rule, mapping in LORUGEC_RULES.items():
        handler_name, subtype = mapping[0], mapping[1]
        word_filter = mapping[2] if len(mapping) > 2 else None
        if rule in targets:
            subtype_groups[(handler_name, subtype, word_filter)].append(rule)

    # Total target per group = sum of all rules mapping to it
    subtype_targets: dict[tuple[str, str, str | None], int] = {}
    for key, rules in subtype_groups.items():
        subtype_targets[key] = sum(targets[r] for r in rules)

    print(f"LoRuGEC rules mapped: {len(LORUGEC_RULES)}")
    print(f"Unique (handler, subtype) pairs: {len(subtype_targets)}")
    print(f"Target total: {sum(subtype_targets.values())}")

    # Read input sentences
    sentences = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(line)
                if len(sentences) >= args.max_input:
                    break
    print(f"Input: {len(sentences)} sentences")

    # Set up pipeline
    config = GenerationConfig(
        seed=args.seed,
        schema="rozental",
        use_depparse=args.depparse,
    )
    pipeline = ErrorPipeline("ru", config)

    # Batch-analyze all sentences
    print(f"\nAnalyzing {len(sentences)} sentences (batch_size={args.batch_size})...")
    t0 = time.time()
    all_tokens = []
    for i in range(0, len(sentences), args.batch_size):
        batch = sentences[i : i + args.batch_size]
        token_batches = pipeline.analyzer.analyze_batch(batch)
        all_tokens.extend(token_batches)
        done = min(i + args.batch_size, len(sentences))
        if done % 8000 == 0 or done == len(sentences):
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            print(f"  {done}/{len(sentences)} ({rate:.0f} sent/s)", flush=True)
    print(f"Analysis done in {time.time() - t0:.1f}s\n", flush=True)

    # For each (handler, subtype): scan sentences, force-apply, filter by subtype
    rng = random.Random(args.seed)
    all_examples: list[dict] = []
    results_per_rule: dict[str, int] = {r: 0 for r in LORUGEC_RULES}

    for (handler_name, subtype, word_filter), target in subtype_targets.items():
        handler = pipeline._get_handler_by_name(handler_name)
        if handler is None:
            print(f"  SKIP {handler_name}/{subtype}: handler not found")
            continue

        # For word-filtered rules, prioritize sentences containing the word
        # so conjunction_merge can find "что бы" without scanning 60k sentences
        indices = list(range(len(sentences)))
        if word_filter is not None:
            import re
            # For merge subtypes, search for the SEPARATE form in source text
            # (e.g., "от того" not "оттого"), since merge needs separate tokens
            search_terms = [word_filter]
            if subtype == "conjunction_merge" or (isinstance(subtype, tuple) and "conjunction_merge" in subtype):
                from synterr.languages.russian.errors.function_spelling import SOLID_TO_SPLIT
                parts = SOLID_TO_SPLIT.get(word_filter)
                if parts:
                    search_terms.append(" ".join(parts))
            pattern_str = "|".join(r'\b' + re.escape(t) + r'\b' for t in search_terms)
            wf_pattern = re.compile(pattern_str, re.IGNORECASE)
            matching = [i for i in indices if wf_pattern.search(sentences[i])]
            non_matching = [i for i in indices if i not in set(matching)]
            rng.shuffle(matching)
            rng.shuffle(non_matching)
            indices = matching + non_matching
        else:
            rng.shuffle(indices)

        count = 0
        for idx in indices:
            if count >= target:
                break

            tokens = all_tokens[idx]
            if not tokens:
                continue

            original = [t.text for t in tokens]
            sentence = original.copy()
            modified: set[int] = set()

            # Find applicable positions
            applicable = [
                i for i in range(len(tokens))
                if handler.can_apply(tokens, i)
            ]
            if not applicable:
                continue

            # Try positions in random order until we get the right subtype
            positions = applicable.copy()
            rng.shuffle(positions)

            applied = False
            for pos in positions:
                if applied:
                    break
                # Reset sentence for each attempt
                sentence = original.copy()
                modified = set()
                result = handler.apply(tokens, sentence, pos, modified, rng=rng)
                if result is None:
                    continue

                # Check subtype matches (subtype can be str or tuple of strs)
                result_subtype = _extract_subtype_fn(result.error_type, handler_name)
                if isinstance(subtype, tuple):
                    if result_subtype not in subtype:
                        continue
                elif result_subtype != subtype:
                    continue

                # Check word filter (for conjunction-specific rules)
                if word_filter is not None:
                    orig_lower = result.original.lower() if result.original else ""
                    corr_lower = result.corrupted.lower() if result.corrupted else ""
                    if word_filter not in orig_lower and word_filter not in corr_lower:
                        continue

                src = _detokenize(sentence)
                tgt = _detokenize(original)
                if src == tgt:
                    continue

                # Assign rule via round-robin across rules in this group
                group_rules = subtype_groups[(handler_name, subtype, word_filter)]
                assigned_rule = group_rules[count % len(group_rules)]

                record = {"src": src, "tgt": tgt, "rule": assigned_rule}
                all_examples.append(record)
                results_per_rule[assigned_rule] = results_per_rule.get(assigned_rule, 0) + 1
                count += 1
                applied = True

        label = f"{handler_name}/{subtype}"
        if word_filter:
            label += f"[{word_filter}]"
        print(f"  {label}: {count}/{target}")

    # Balance split/merge directions: cap the larger to match the smaller.
    # Only applies when both directions produced enough data (>= floor).
    # Prevents bidirectional learning (e.g., model learns также↔так же
    # as interchangeable instead of directional).
    if args.balance_directions:
        BALANCE_FLOOR = 50  # don't cap below this — too few examples to train on

        split_rules = {r for r in LORUGEC_RULES if "[split]" in r}
        merge_rules = {r for r in LORUGEC_RULES if "[merge]" in r}

        pairs = []
        for sr in split_rules:
            base = sr.replace(" [split]", "")
            mr = base + " [merge]"
            if mr in merge_rules:
                pairs.append((sr, mr))

        dropped = 0
        for split_rule, merge_rule in pairs:
            split_count = results_per_rule.get(split_rule, 0)
            merge_count = results_per_rule.get(merge_rule, 0)
            cap = max(min(split_count, merge_count), BALANCE_FLOOR)

            for rule, count in [(split_rule, split_count), (merge_rule, merge_count)]:
                if count > cap:
                    indices = [i for i, ex in enumerate(all_examples) if ex["rule"] == rule]
                    rng.shuffle(indices)
                    to_remove = set(indices[cap:])
                    n_remove = len(to_remove)
                    all_examples = [ex for i, ex in enumerate(all_examples) if i not in to_remove]
                    results_per_rule[rule] = cap
                    dropped += n_remove
                    print(f"  Balance: {rule}: {count} → {cap} (dropped {n_remove})")

        if dropped:
            print(f"  Total dropped for balance: {dropped}")

    # Shuffle and write
    rng.shuffle(all_examples)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    total = len(all_examples)
    elapsed = time.time() - t0
    print(f"\nDone: {total} examples in {elapsed:.1f}s")
    print(f"Output: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Save per-rule distribution as JSON sidecar
    dist_path = output_path.with_suffix(".dist.json")
    dist = {
        "total": total,
        "target": args.total,
        "seed": args.seed,
        "source": str(Path(args.input).name),
        "rules": {r: {"got": results_per_rule.get(r, 0), "want": targets.get(r, 0)}
                  for r in sorted(LORUGEC_RULES.keys())},
    }
    with dist_path.open("w", encoding="utf-8") as f:
        json.dump(dist, f, ensure_ascii=False, indent=2)
    print(f"Distribution: {dist_path}")

    # Show per-rule results
    print(f"\n{'Rule':<65s} {'Got':>5s} {'Want':>5s}")
    print("-" * 80)
    for rule in sorted(LORUGEC_RULES.keys()):
        got = results_per_rule.get(rule, 0)
        want = targets.get(rule, 0)
        marker = " ***" if got < want * 0.5 else ""
        print(f"  {rule:<63s} {got:5d} {want:5d}{marker}")

    # Shortfalls
    shortfalls = {r: targets[r] - results_per_rule.get(r, 0)
                  for r in LORUGEC_RULES
                  if results_per_rule.get(r, 0) < targets[r]}
    if shortfalls:
        short_total = sum(shortfalls.values())
        print(f"\nTotal shortfall: {short_total} examples across {len(shortfalls)} rules")


from sacremoses import MosesDetokenizer as _MD
_moses = _MD(lang="ru")


def _detokenize(tokens: list[str]) -> str:
    return _moses.detokenize(tokens)


if __name__ == "__main__":
    main()
