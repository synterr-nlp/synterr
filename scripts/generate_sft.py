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


# LoRuGEC rule name → (handler_name, subtype, force_subtype)
# force_subtype: if True, only accept apply() results matching this subtype
LORUGEC_RULES: dict[str, tuple[str, str]] = {
    # === Spelling (24 rules) ===
    # не/ни
    'Правописание частицы "не" с существительными': ("function_spelling", "ne_attachment"),
    'Правописание "не" с прилагательными': ("function_spelling", "ne_attachment"),
    'Правописание "не" с глаголами': ("function_spelling", "ne_detachment"),
    'Правописание частицы "не" с причастиями': ("function_spelling", "ne_attachment"),
    # Conjunctions
    'Правописание "чтобы"': ("function_spelling", "conjunction_merge"),
    'Правописание "причем" и "притом"': ("function_spelling", "conjunction_merge"),
    'Правописание "оттого"': ("function_spelling", "conjunction_merge"),
    'Правописание "зато"': ("function_spelling", "conjunction_merge"),
    'Правописание "также"': ("function_spelling", "conjunction_merge"),
    # -таки
    "Правописание частицы -таки": ("function_spelling", "taki_hyphen"),
    # Orthographic
    'Правописание приставок пре- и при-': ("orthographic_spelling", "pre_pri"),
    'Гласные "ы" и "и" после приставок': ("orthographic_spelling", "y_i_after_prefix"),
    'Правописание суффиксов -еньк, -оньк в существительных. ': ("orthographic_spelling", "suffix_enk_onk"),
    "Правописание суффиксов −инск, −енск в прилагательных": ("orthographic_spelling", "suffix_insk_ensk"),
    "Правописание суффиксов -иц, -ец в существительных среднего рода": ("orthographic_spelling", "suffix_its_ets"),
    "Правописание суффиксов −ек, −ик": ("orthographic_spelling", "suffix_ek_ik"),
    "Правописание гласных в суффиксах причастий": ("orthographic_spelling", "participle_suffix"),
    'Гласные после "ц"': ("orthographic_spelling", "vowel_after_ts"),
    "Гласные после шипящих": ("orthographic_spelling", "vowel_after_sibilant"),
    '"н" и "нн" в суффиксах прилагательных': ("orthographic_spelling", "nn_suffix"),
    'Правописание разделительных "ъ" и "ь"': ("spelling", "soft_sign"),
    # Compounds
    "Правописание числительного пол-": ("compound_spelling", "pol_spelling"),
    "Дефис в составе письменных эквивалентов сложных слов": ("compound_spelling", "num_dash"),
    "Правописание сложных прилагательных": ("compound_spelling", "compound_adj"),
    # Adverbs
    "Слитное, раздельное и дефисное написание наречий": ("adverb_spelling", "adverb_solid_to_separate"),

    # === Grammar (4 rules) ===
    "Нарушение норм управления": ("adj_case", "adj_case"),
    "Согласование причастий с определяемым словом": ("adj_case", "adj_case"),
    'Склонение числительных "полтора", "полторы", "полтораста"': ("numeral_declension", "numeral_poltora"),
    "Склонение количественных числительных": ("numeral_declension", "numeral_declension"),

    # === Semantics (2 rules) ===
    "Плеоназмы": ("pleonasm", "pleonasm"),
    "Лексическая сочетаемость слов": ("collocation", "collocation"),

    # === Punctuation (18 rules) ===
    "Запятая внутри выражений фразеологического характера": ("comma_insert", "comma_in_set_phrase"),
    "Пунктуация в цельных по смыслу (неразложимых) сочетаниях": ("comma_insert", "comma_in_indivisible"),
    "Знаки препинания в предложениях с однородными членами: пары": ("comma_delete", "comma_homogeneous"),
    "Обособление деепричастий после союзов": ("comma_pair_delete", "pair_gerund"),
    "Запятая между частями СПП с общей частью": ("comma_delete", "comma_subordinate"),
    "Запятая перед союзом \"как\": 1": ("comma_insert", "comma_before_kak"),
    "Запятая между однородными придаточными": ("comma_delete", "comma_subordinate"),
    "Обособление согласованных определений, относящихся к личному местоимению": ("comma_pair_delete", "pair_participle"),
    "Обособление согласованных определений, оторванных от определяемого слова": ("comma_pair_delete", "pair_participle"),
    'Запятая перед союзом "как": 2': ("comma_insert", "comma_before_kak"),
    'Запятая перед союзом "как": 3': ("comma_insert", "comma_before_kak"),
    "Пунктуация при повторяющихся союзах": ("comma_delete", "comma_homogeneous"),
    "Пунктуация при вводных словах и конструкциях": ("comma_pair_delete", "pair_parenthetical"),
    "Тире при приложении": ("dash_delete", "dash_other"),
    "Тире между подлежащим и сказуемым": ("dash_delete", "dash_subj_pred"),
    "Тире в бессоюзных предложениях": ("dash_delete", "dash_asyndetic"),
    "Запятая на стыке двух союзов": ("comma_insert", "comma_between_conjunctions"),
    "Обособление согласованных определений, относящихся к личному местоимению": ("comma_pair_delete", "pair_participle"),
}


def main():
    parser = argparse.ArgumentParser(description="Generate SFT data per LoRuGEC rule")
    parser.add_argument("-i", "--input", required=True, help="Input sentences file")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL file")
    parser.add_argument("-n", "--total", type=int, default=50000, help="Total examples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--depparse", action="store_true", help="Enable dep parsing")
    parser.add_argument("--max-input", type=int, default=60000, help="Max input sentences")
    parser.add_argument("--batch-size", type=int, default=128, help="Stanza batch size")
    args = parser.parse_args()

    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    # Read LoRuGEC distribution
    rule_counts = _get_lorugec_distribution()
    total_lorugec = sum(rule_counts.values())

    # Compute target per rule, scaled to args.total
    targets: dict[str, int] = {}
    for rule, count in rule_counts.items():
        targets[rule] = max(1, round(count / total_lorugec * args.total))

    # Group rules by (handler, subtype) to avoid redundant scanning
    # Multiple LoRuGEC rules can map to the same handler+subtype
    from collections import defaultdict
    subtype_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rule, (handler_name, subtype) in LORUGEC_RULES.items():
        if rule in targets:
            subtype_groups[(handler_name, subtype)].append(rule)

    # Total target per (handler, subtype) = sum of all rules mapping to it
    subtype_targets: dict[tuple[str, str], int] = {}
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
    all_examples: list[str] = []
    results_per_rule: dict[str, int] = {r: 0 for r in LORUGEC_RULES}

    for (handler_name, subtype), target in sorted(subtype_targets.items()):
        handler = pipeline._get_handler_by_name(handler_name)
        if handler is None:
            print(f"  SKIP {handler_name}/{subtype}: handler not found")
            continue

        # Shuffle sentence order
        indices = list(range(len(sentences)))
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

                # Check subtype matches
                result_subtype = _extract_subtype(result, handler_name)
                if result_subtype != subtype:
                    continue

                src = _detokenize(sentence)
                tgt = _detokenize(original)
                if src == tgt:
                    continue

                record = {"src": src, "tgt": tgt}
                all_examples.append(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
                applied = True

        # Distribute count across the LoRuGEC rules that map to this subtype
        rules = subtype_groups[(handler_name, subtype)]
        per_rule = count // len(rules)
        leftover = count % len(rules)
        for i, rule in enumerate(rules):
            results_per_rule[rule] = per_rule + (1 if i < leftover else 0)

        print(f"  {handler_name}/{subtype}: {count}/{target}")

    # Shuffle and write
    rng.shuffle(all_examples)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        f.writelines(all_examples)

    total = len(all_examples)
    elapsed = time.time() - t0
    print(f"\nDone: {total} examples in {elapsed:.1f}s")
    print(f"Output: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")

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


def _extract_subtype(result, handler_name: str) -> str | None:
    """Extract the subtype from an ErrorResult."""
    et = result.error_type
    if not et:
        return None
    # error_type is usually "handler_name_subtype" — strip the handler prefix
    prefix = handler_name + "_"
    if et.startswith(prefix):
        return et[len(prefix):]
    # Some handlers set error_type = subtype directly
    return et


def _get_lorugec_distribution() -> dict[str, int]:
    """Read LoRuGEC rule counts from the Excel file."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(
            Path(__file__).parent.parent.parent
            / "gector/data/lorugec-data/LORuGEC.xlsx",
            read_only=True,
        )
        ws = wb["Sheet1"]
        from collections import Counter
        counts = Counter()
        for row in ws.iter_rows(min_row=2, values_only=True):
            rule_name = row[0]
            if rule_name:
                counts[rule_name] += 1
        return dict(counts)
    except Exception:
        # Fallback: uniform 20 per rule
        return {rule: 20 for rule in LORUGEC_RULES}


if __name__ == "__main__":
    main()
