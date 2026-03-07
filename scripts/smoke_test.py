#!/usr/bin/env python3
"""Smoke test: generate errors and show human-readable diffs for manual inspection.

Usage:
    uv run python scripts/smoke_test.py --handler compound_spelling --n 50
    uv run python scripts/smoke_test.py --all --n 30
    uv run python scripts/smoke_test.py --handler spelling -i lenta_sents.txt --n 100

Outputs colored diffs so bad outputs are immediately visible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def get_sentences(path: str | None = None, n: int = 200) -> list[str]:
    if path:
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()][:n]
    lenta = Path(__file__).parent.parent / "lenta_sents.txt"
    if lenta.exists():
        with lenta.open(encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()][:n]
    return [
        "Студенты приехали на конференцию по лингвистике.",
        "Военно-морской флот провёл учения в Баренцевом море.",
        "Преподаватель превысил допустимое количество ошибок.",
        "Деревянный забор покрасили в зелёный цвет.",
        "Он кивнул головой и вышел из комнаты.",
        "Полвека назад здесь стояла деревянная церковь.",
        "Кожаный портфель лежал на письменном столе.",
        "Когда мы пришли, то увидели странную картину.",
        "Она работала как следует и получила премию.",
        "Не хочу идти в школу сегодня.",
        "Невзлюбил он этого человека с первого взгляда.",
        "Принять решение оказалось непросто.",
        "Памятный сувенир привезли из поездки.",
        "Пол-лимона лежало на столе рядом с чашкой.",
        "25-процентный раствор использовали в эксперименте.",
        "Научно-исследовательский институт опубликовал отчёт.",
        "Государственный служащий подал заявление об увольнении.",
        "Серебряная ложка блестела при свете свечи.",
        "Безынициативных работников отправили на курсы повышения квалификации.",
        "Приступить к выполнению задания следовало немедленно.",
    ]


def run_handler_test(handler_name: str, sentences: list[str], seed: int = 42) -> dict:
    from synterr.languages.russian import RussianLanguage
    from synterr.languages.russian.analyzer import RussianAnalyzer

    lang = RussianLanguage()
    analyzer = lang.get_analyzer(backend="stanza", use_depparse=True)
    handlers = lang.get_error_handlers()

    handler = None
    for h in handlers:
        if h.name == handler_name:
            handler = h
            break

    if handler is None:
        print(f"Handler '{handler_name}' not found.")
        print(f"Available: {[h.name for h in handlers]}")
        return {"checked": 0, "applied": 0, "results": []}

    rng = Random(seed)
    results = []
    applied = 0
    checked = 0

    for sent in sentences:
        tokens = analyzer.analyze(sent)
        sentence_words = [t.text for t in tokens]

        for idx in range(len(tokens)):
            if handler.can_apply(tokens, idx):
                checked += 1
                sent_copy = list(sentence_words)
                modified = set()
                result = handler.apply(tokens, sent_copy, idx, modified, rng=rng)
                if result:
                    applied += 1
                    results.append({
                        "original": " ".join(sentence_words),
                        "corrupted": " ".join(sent_copy),
                        "word_original": result.original,
                        "word_corrupted": result.corrupted,
                        "error_type": result.error_type,
                        "token_pos": tokens[idx].pos,
                    })

    return {"checked": checked, "applied": applied, "results": results}


def print_results(handler_name: str, data: dict) -> None:
    RED = "\033[91m"
    GREEN = "\033[92m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}{handler_name}{RESET}  |  checked={data['checked']}  applied={data['applied']}")
    print(f"{'=' * 70}")

    for r in data["results"]:
        print(f"  {DIM}{r['error_type']} ({r['token_pos']}){RESET}")
        print(f"  {RED}{r['word_original']}{RESET} → {GREEN}{r['word_corrupted']}{RESET}")

    if not data["results"]:
        print(f"  {DIM}(no errors generated){RESET}")


def main():
    parser = argparse.ArgumentParser(description="Smoke test error handlers")
    parser.add_argument("--handler", "-e", help="Handler name to test")
    parser.add_argument("--all", action="store_true", help="Test all handlers")
    parser.add_argument("--n", type=int, default=50, help="Number of sentences")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--input", "-i", help="Input file")
    args = parser.parse_args()

    sentences = get_sentences(args.input, args.n)

    ALL_HANDLERS = [
        "spelling", "orthographic_spelling", "function_spelling",
        "noun_case", "noun_number",
        "adj_case", "adj_number", "adj_gender",
        "verb_person_number", "verb_tense",
        "paronym", "preposition", "conjunction",
        "word_omission", "word_insertion",
        "comma_delete", "comma_pair_delete", "comma_insert", "dash_delete",
        "compound_spelling", "pleonasm", "collocation",
    ]

    if args.all:
        for h in ALL_HANDLERS:
            data = run_handler_test(h, sentences, args.seed)
            print_results(h, data)
    elif args.handler:
        data = run_handler_test(args.handler, sentences, args.seed)
        print_results(args.handler, data)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
