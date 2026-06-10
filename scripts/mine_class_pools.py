#!/usr/bin/env python3
"""Mine per-error-class sentence pools for starving/never-fired subtypes.

Driven by data/applicability_report.json (scripts/measure_applicability.py):
each starving class gets a surface pattern, derived from the handler lexicons
where possible (imports the live word lists, so pools cannot drift from the
handlers). Output: data/pools/<class>.txt + data/pools/pools.meta.json.

Usage:
    uv run python scripts/mine_class_pools.py \
        -s data/taiga/taiga_fontanka.txt data/taiga/taiga_interfax.txt \
           data/taiga/taiga_lenta.txt data/rublimp_pool_sents.txt \
        -o data/pools --cap 2000 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path


def build_patterns() -> dict[str, re.Pattern]:
    """One compiled regex per starving/never-fired class.

    Lexicon-derived where the handler exposes a word list; hand-written
    surface heuristics otherwise. Patterns are recall-oriented: the pool
    only needs to contain *candidates* — the handler's can_apply does the
    precise filtering at generation time.
    """
    from synterr.languages.russian.errors.adverb_spelling import (
        _SEPARATE_TO_HYPHEN,
        _TRIGRAM_SEPARATE_TO_HYPHEN,
    )
    from synterr.languages.russian.errors.comma_insert import (
        _FROZEN_PHRASES,
        _INDIVISIBLE_FIXED,
        _INDIVISIBLE_KAK,
        _INDIVISIBLE_PRONOUN,
    )

    def alt(phrases: list[str]) -> str:
        return "|".join(re.escape(p) for p in sorted(set(phrases), key=len, reverse=True))

    sep_hyph = [" ".join(k) for k in _SEPARATE_TO_HYPHEN] + [
        " ".join(k) for k in _TRIGRAM_SEPARATE_TO_HYPHEN
    ]
    set_phrases = [" ".join(t) for ts in _FROZEN_PHRASES.values() for t in ts]
    indivisible = [
        " ".join(t)
        for group in (_INDIVISIBLE_KAK, _INDIVISIBLE_PRONOUN, _INDIVISIBLE_FIXED)
        for t in group
    ]
    # second-locative nouns commonly governed by в/на (loc2 forms)
    loc2 = (
        "лесу снегу порту шкафу углу берегу мосту саду краю бою строю тылу "
        "плену аду раю быту виду носу боку году часу ряду полу мелу льду "
        "пруду долгу цеху отпуску аэропорту"
    ).split()

    pats = {
        # never-fired (dialogue/colloquial/genre-bound)
        "comma_interjection": r"(?:^|[.!?…]\s+)(?:Ах|Ох|Эх|Ой|Увы|Ура|Ну и ну|Боже)\s*,",
        "comma_response": r"(?:^|[.!?…]\s+)(?:Да|Нет)\s*,",
        "comma_repeated": r"\b([А-Яа-яЁё]{3,})\s*,\s*\1\b",
        "comma_in_set_phrase": rf"\b(?:{alt(set_phrases)})\b",
        "comma_between_conjunctions": r",\s+(?:и|но|а|однако)\s+(?:если|когда|хотя|чтобы|пока)\b",
        "adverb_separate_to_hyphen": rf"\b(?:{alt(sep_hyph)})\b",
        "suffix_enk_onk": r"\b[А-Яа-яЁё]{3,}(?:енька|енько|енькой|еньку|онька|онько|онькой|оньку)\b",
        "suffix_insk_ensk": r"\b[А-Яа-яЁё]{3,}(?:инский|инская|инское|инские|енский|енская|енское|енские)\b",
        # starving
        "comma_in_indivisible": rf"\b(?:{alt(indivisible)})\b",
        "comma_vocative": r",\s*(?:дорог(?:ой|ая|ие)\s+)?[А-ЯЁ][а-яё]{2,}\s*[,!?]",
        "taki_hyphen": r"\b[А-Яа-яЁё]+-таки\b",
        "suffix_its_ets": r"\b[А-Яа-яЁё]{3,}(?:ица|ице|ицей|ицу|ицы)\b",
        "dash_contexts": r"\s—\s",
        "verb_tense_anchor": r"\b(?:вчера|позавчера|завтра|послезавтра|недавно)\b",
        "noun_case_prep_e_u": rf"\b(?:в|на)\s+(?:{'|'.join(loc2)})\b",
        "numeral_poltora": r"\b(?:полтора|полторы|полутора|полтораста)\b",
    }
    return {name: re.compile(p, re.IGNORECASE if name not in
                             ("comma_interjection", "comma_response", "comma_vocative")
                             else 0) for name, p in pats.items()}


def good(s: str) -> bool:
    w = s.split()
    return 5 <= len(w) <= 60 and not re.search(r"[<>{}\[\]|@#$%^*_=~`]", s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-s", "--sources", type=Path, nargs="+", required=True)
    ap.add_argument("-o", "--outdir", type=Path, default=Path("data/pools"))
    ap.add_argument("--cap", type=int, default=2000, help="max sentences per class")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    patterns = build_patterns()
    rng = random.Random(args.seed)
    # reservoir sampling per class so all sources contribute fairly
    reservoirs: dict[str, list[str]] = defaultdict(list)
    seen_counts: dict[str, int] = defaultdict(int)
    seen_sents: dict[str, set[int]] = defaultdict(set)

    for src in args.sources:
        print(f"scanning {src} …", flush=True)
        with src.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s or not good(s):
                    continue
                for name, pat in patterns.items():
                    if not pat.search(s):
                        continue
                    h = hash(s)
                    if h in seen_sents[name]:
                        continue
                    seen_sents[name].add(h)
                    seen_counts[name] += 1
                    r = reservoirs[name]
                    if len(r) < args.cap:
                        r.append(s)
                    else:
                        j = rng.randrange(seen_counts[name])
                        if j < args.cap:
                            r[j] = s

    args.outdir.mkdir(parents=True, exist_ok=True)
    meta = {"seed": args.seed, "cap": args.cap,
            "sources": [str(s) for s in args.sources],
            "seen": dict(seen_counts),
            "sampled": {k: len(v) for k, v in reservoirs.items()}}
    for name, sents in sorted(reservoirs.items()):
        out = args.outdir / f"{name}.txt"
        out.write_text("\n".join(sents) + "\n", encoding="utf-8")
        print(f"{name:32s} seen={seen_counts[name]:>7}  pooled={len(sents)}")
    (args.outdir / "pools.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {args.outdir}/pools.meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
