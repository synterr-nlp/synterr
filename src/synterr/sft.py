"""Rule-targeted SFT data generation.

Force-applies errors per LoRuGEC rule mapping, with direction-balanced
output. Produces ``{src, tgt, rule}`` JSONL plus a ``.dist.json`` sidecar
of per-rule counts.

This is the engine behind ``synterr generate-targeted``. Importable as
a function for programmatic use; ``scripts/generate_sft.py`` is a thin
CLI wrapper for backwards compatibility.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from sacremoses import MosesDetokenizer

from synterr.lorugec import (
    LORUGEC_RULES,
    get_lorugec_distribution,
)
from synterr.lorugec import (
    extract_subtype as _extract_subtype_fn,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Rule pairs whose larger direction gets capped to match the smaller — only
# applies when both directions reach BALANCE_FLOOR. Prevents the model from
# learning split/merge as bidirectionally interchangeable.
_BALANCE_FLOOR = 50


def _detokenize_factory(lang: str) -> Callable[[list[str]], str]:
    md = MosesDetokenizer(lang=lang)
    return lambda tokens: md.detokenize(tokens)


def _compute_targets(total: int) -> dict[str, int]:
    """Scale LoRuGEC's empirical rule distribution to the given total."""
    rule_counts = get_lorugec_distribution()
    grand = sum(rule_counts.values())
    return {
        rule: max(1, round(count / grand * total))
        for rule, count in rule_counts.items()
    }


def _group_by_subtype(
    targets: dict[str, int],
) -> tuple[
    dict[tuple[str, str, str | None], list[str]],
    dict[tuple[str, str, str | None], int],
]:
    """Group rules by (handler, subtype, word_filter) to avoid redundant scans.

    Rules with different word_filters get their own group even if
    handler+subtype match.
    """
    groups: dict[tuple[str, str, str | None], list[str]] = defaultdict(list)
    for rule, mapping in LORUGEC_RULES.items():
        handler_name, subtype = mapping[0], mapping[1]
        word_filter = mapping[2] if len(mapping) > 2 else None
        if rule in targets:
            groups[(handler_name, subtype, word_filter)].append(rule)

    group_targets: dict[tuple[str, str, str | None], int] = {
        key: sum(targets[r] for r in rules) for key, rules in groups.items()
    }
    return groups, group_targets


def _read_input(path: Path, max_input: int) -> list[str]:
    sentences: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(line)
                if len(sentences) >= max_input:
                    break
    return sentences


def _balance_directions(
    examples: list[dict],
    results_per_rule: dict[str, int],
    rng: random.Random,
) -> int:
    """Cap split/merge pairs to min(split, merge), but never below floor.

    Mutates ``examples`` and ``results_per_rule`` in place. Returns total
    number of examples dropped.
    """
    split_rules = {r for r in LORUGEC_RULES if "[split]" in r}
    merge_rules = {r for r in LORUGEC_RULES if "[merge]" in r}

    pairs = []
    for sr in split_rules:
        mr = sr.replace(" [split]", "") + " [merge]"
        if mr in merge_rules:
            pairs.append((sr, mr))

    dropped = 0
    for split_rule, merge_rule in pairs:
        split_count = results_per_rule.get(split_rule, 0)
        merge_count = results_per_rule.get(merge_rule, 0)
        cap = max(min(split_count, merge_count), _BALANCE_FLOOR)

        for rule, count in [(split_rule, split_count), (merge_rule, merge_count)]:
            if count > cap:
                indices = [i for i, ex in enumerate(examples) if ex["rule"] == rule]
                rng.shuffle(indices)
                to_remove = set(indices[cap:])
                n_remove = len(to_remove)
                # Replace examples list in-place
                examples[:] = [
                    ex for i, ex in enumerate(examples) if i not in to_remove
                ]
                results_per_rule[rule] = cap
                dropped += n_remove
                print(f"  Balance: {rule}: {count} → {cap} (dropped {n_remove})")
    return dropped


def generate_targeted(
    input_path: Path | str,
    output_path: Path | str,
    *,
    total: int = 50000,
    seed: int = 42,
    depparse: bool = True,
    max_input: int = 150000,
    batch_size: int = 128,
    balance_directions: bool = True,
    lang: str = "ru",
) -> dict:
    """Generate rule-targeted SFT data.

    Force-applies each LoRuGEC rule's mapped handler+subtype, scaled to
    the empirical LoRuGEC rule distribution. Writes ``{src, tgt, rule}``
    JSONL plus a ``.dist.json`` sidecar.

    Args:
        input_path: Input plain-text file, one sentence per line.
        output_path: Output JSONL path; ``.dist.json`` sidecar is written
            alongside.
        total: Target total examples (rule counts scaled to this).
        seed: Random seed; same seed reproduces the same dataset.
        depparse: Enable dependency parsing (required for noun_case,
            adj_case, and other arc-aware handlers).
        max_input: Maximum input sentences to read.
        batch_size: Stanza analysis batch size.
        balance_directions: Cap split/merge pairs to min(split, merge),
            preventing bidirectional learning.
        lang: Language code (currently only "ru" supported).

    Returns:
        The distribution dict written to the sidecar.
    """
    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    input_path = Path(input_path)
    output_path = Path(output_path)
    detokenize = _detokenize_factory(lang)

    targets = _compute_targets(total)
    subtype_groups, subtype_targets = _group_by_subtype(targets)

    print(f"LoRuGEC rules mapped: {len(LORUGEC_RULES)}")
    print(f"Unique (handler, subtype) pairs: {len(subtype_targets)}")
    print(f"Target total: {sum(subtype_targets.values())}")

    sentences = _read_input(input_path, max_input)
    print(f"Input: {len(sentences)} sentences")

    config = GenerationConfig(seed=seed, schema="rozental", use_depparse=depparse)
    pipeline = ErrorPipeline(lang, config)

    print(f"\nAnalyzing {len(sentences)} sentences (batch_size={batch_size})...")
    t0 = time.time()
    all_tokens = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i : i + batch_size]
        all_tokens.extend(pipeline.analyzer.analyze_batch(batch))
        done = min(i + batch_size, len(sentences))
        if done % 8000 == 0 or done == len(sentences):
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            print(f"  {done}/{len(sentences)} ({rate:.0f} sent/s)", flush=True)
    print(f"Analysis done in {time.time() - t0:.1f}s\n", flush=True)

    rng = random.Random(seed)
    all_examples: list[dict] = []
    results_per_rule: dict[str, int] = {r: 0 for r in LORUGEC_RULES}

    for (handler_name, subtype, word_filter), target in subtype_targets.items():
        handler = pipeline._get_handler_by_name(handler_name)
        if handler is None:
            print(f"  SKIP {handler_name}/{subtype}: handler not found")
            continue

        indices = list(range(len(sentences)))
        if word_filter is not None:
            search_terms = [word_filter]
            if subtype == "conjunction_merge" or (
                isinstance(subtype, tuple) and "conjunction_merge" in subtype
            ):
                from synterr.languages.russian.errors.function_spelling import (
                    SOLID_TO_SPLIT,
                )

                parts = SOLID_TO_SPLIT.get(word_filter)
                if parts:
                    search_terms.append(" ".join(parts))
            pattern_str = "|".join(r"\b" + re.escape(t) + r"\b" for t in search_terms)
            wf_pattern = re.compile(pattern_str, re.IGNORECASE)
            matching = [i for i in indices if wf_pattern.search(sentences[i])]
            non_matching_set = set(matching)
            non_matching = [i for i in indices if i not in non_matching_set]
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
            applicable = [i for i in range(len(tokens)) if handler.can_apply(tokens, i)]
            if not applicable:
                continue

            positions = applicable.copy()
            rng.shuffle(positions)

            for pos in positions:
                sentence = original.copy()
                modified: set[int] = set()
                result = handler.apply(tokens, sentence, pos, modified, rng=rng)
                if result is None:
                    continue

                result_subtype = _extract_subtype_fn(result.error_type, handler_name)
                if isinstance(subtype, tuple):
                    if result_subtype not in subtype:
                        continue
                elif result_subtype != subtype:
                    continue

                if word_filter is not None:
                    orig_lower = result.original.lower() if result.original else ""
                    corr_lower = result.corrupted.lower() if result.corrupted else ""
                    if word_filter not in orig_lower and word_filter not in corr_lower:
                        continue

                src = detokenize(sentence)
                tgt = detokenize(original)
                if src == tgt:
                    continue

                group_rules = subtype_groups[(handler_name, subtype, word_filter)]
                assigned_rule = group_rules[count % len(group_rules)]

                all_examples.append({"src": src, "tgt": tgt, "rule": assigned_rule})
                results_per_rule[assigned_rule] += 1
                count += 1
                break  # successful application; move to next sentence

        label = f"{handler_name}/{subtype}"
        if word_filter:
            label += f"[{word_filter}]"
        print(f"  {label}: {count}/{target}")

    if balance_directions:
        dropped = _balance_directions(all_examples, results_per_rule, rng)
        if dropped:
            print(f"  Total dropped for balance: {dropped}")

    rng.shuffle(all_examples)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    total_written = len(all_examples)
    elapsed = time.time() - t0
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\nDone: {total_written} examples in {elapsed:.1f}s")
    print(f"Output: {output_path} ({size_mb:.1f} MB)")

    dist = {
        "total": total_written,
        "target": total,
        "seed": seed,
        "source": input_path.name,
        "rules": {
            r: {"got": results_per_rule.get(r, 0), "want": targets.get(r, 0)}
            for r in sorted(LORUGEC_RULES.keys())
        },
    }
    dist_path = output_path.with_suffix(".dist.json")
    with dist_path.open("w", encoding="utf-8") as f:
        json.dump(dist, f, ensure_ascii=False, indent=2)
    print(f"Distribution: {dist_path}")

    print(f"\n{'Rule':<65s} {'Got':>5s} {'Want':>5s}")
    print("-" * 80)
    for rule in sorted(LORUGEC_RULES.keys()):
        got = results_per_rule.get(rule, 0)
        want = targets.get(rule, 0)
        marker = " ***" if got < want * 0.5 else ""
        print(f"  {rule:<63s} {got:5d} {want:5d}{marker}")

    shortfalls = {
        r: targets[r] - results_per_rule.get(r, 0)
        for r in LORUGEC_RULES
        if results_per_rule.get(r, 0) < targets[r]
    }
    if shortfalls:
        short_total = sum(shortfalls.values())
        print(
            f"\nTotal shortfall: {short_total} examples across {len(shortfalls)} rules"
        )

    return dist
