"""Data discovery for error classes: fire-rate surveys and pool mining.

The discovery loop turns "which error classes can this corpus feed?" into
two reusable steps:

1. ``survey()`` — run every handler's can_apply/apply over a sample of
   the corpus and report per-subtype emissions per 1k sentences, plus
   starving and never-fired classes.
2. ``mine_pools()`` — for the starving classes, sweep large text sources
   with surface patterns (derived from the live handler lexicons where
   possible, so they cannot drift) and reservoir-sample per-class
   candidate pools. The handler's own can_apply does the precise
   filtering at generation time; pools only need recall.

Exposed on the CLI as ``synterr survey`` and ``synterr mine-pools``.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable


def read_sentences(path: Path, limit: int | None = None, min_words: int = 5) -> list[str]:
    """Read one-sentence-per-line text, skipping very short lines."""
    sentences = []
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and len(line.split()) >= min_words:
                sentences.append(line)
                if limit is not None and len(sentences) >= limit:
                    break
    return sentences


# ---------------------------------------------------------------------------
# Survey
# ---------------------------------------------------------------------------


def survey(
    sentences: list[str],
    lang: str = "ru",
    tries: int = 3,
    seed: int = 42,
    batch_size: int = 64,
    starving_below: float = 5.0,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Measure per-subtype fire rates for all handlers over sentences.

    Returns a JSON-serializable report dict (see keys below). ``tries``
    controls apply() attempts per applicable index — multi-subtype
    handlers pick a random subtype per attempt.
    """
    from synterr.core.registry import get_language

    lang_module = get_language(lang)
    analyzer = lang_module.get_analyzer(use_depparse=True, backend="stanza")
    handlers = lang_module.get_error_handlers()
    rng = random.Random(seed)

    emissions: Counter[str] = Counter()
    handler_sentences: Counter[str] = Counter()
    handler_attempts: Counter[str] = Counter()
    handler_successes: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)

    n_done = 0
    for start in range(0, len(sentences), batch_size):
        batch = sentences[start : start + batch_size]
        for tokens in analyzer.analyze_batch(batch):
            n_done += 1
            if progress and n_done % 500 == 0:
                progress(f"  {n_done}/{len(sentences)}")
            original = [t.text for t in tokens]
            for handler in handlers:
                applicable = [
                    i for i in range(len(tokens)) if handler.can_apply(tokens, i)
                ]
                if not applicable:
                    continue
                handler_sentences[handler.name] += 1
                for idx in applicable:
                    for _ in range(tries):
                        sentence = original.copy()
                        handler_attempts[handler.name] += 1
                        try:
                            result = handler.apply(
                                tokens, sentence, idx, set(), rng=rng
                            )
                        except Exception as exc:  # noqa: BLE001 — survey must finish
                            emissions[
                                f"{handler.name}:EXCEPTION:{type(exc).__name__}"
                            ] += 1
                            continue
                        if result is None:
                            continue
                        handler_successes[handler.name] += 1
                        emissions[result.error_type] += 1
                        if len(examples[result.error_type]) < 2:
                            examples[result.error_type].append(
                                f"{result.original} -> {result.corrupted} | "
                                f"{' '.join(original)[:120]}"
                            )

    per_1k = {et: round(c * 1000 / n_done, 2) for et, c in emissions.items()}

    declared = {}
    for h in handlers:
        for st in getattr(h, "subtypes", [h.name]):
            declared[f"{h.name}:{st}" if st != h.name else h.name] = h.name

    fired_types = set(emissions)
    starving = sorted(et for et in per_1k if per_1k[et] < starving_below)
    never = sorted(
        d
        for d in declared
        if not any(
            ft == d or ft.startswith(d.split(":")[-1]) or d.split(":")[-1] in ft
            for ft in fired_types
        )
    )

    return {
        "n_sentences": n_done,
        "tries": tries,
        "seed": seed,
        "starving_below": starving_below,
        "emissions": dict(emissions),
        "per_1k": per_1k,
        "handler_sentence_coverage": {
            h: round(c * 1000 / n_done, 1) for h, c in handler_sentences.items()
        },
        "handler_success_rate": {
            h: round(handler_successes[h] / handler_attempts[h], 3)
            for h in handler_attempts
        },
        "starving": starving,
        "never_fired": never,
        "examples": dict(examples),
    }


# ---------------------------------------------------------------------------
# Pool mining
# ---------------------------------------------------------------------------


def build_class_patterns() -> dict[str, re.Pattern]:
    """One compiled surface regex per starving/never-fired class.

    Lexicon-derived where the handler exposes a word list; hand-written
    surface heuristics otherwise. Recall-oriented by design.
    """
    from synterr.languages.russian.errors.adverb_spelling import (
        _SEPARATE_TO_HYPHEN,
        _TRIGRAM_SEPARATE_TO_HYPHEN,
    )
    from synterr.languages.russian.errors.comma_insert import (
        _COMPOUND_SCONJ,
        _FROZEN_PHRASES,
        _INDIVISIBLE_FIXED,
        _INDIVISIBLE_KAK,
        _INDIVISIBLE_PRONOUN,
    )

    def alt(phrases: list[str]) -> str:
        return "|".join(
            re.escape(p) for p in sorted(set(phrases), key=len, reverse=True)
        )

    sep_hyph = [" ".join(k) for k in _SEPARATE_TO_HYPHEN] + [
        " ".join(k) for k in _TRIGRAM_SEPARATE_TO_HYPHEN
    ]
    set_phrases = [" ".join(t) for ts in _FROZEN_PHRASES.values() for t in ts]
    indivisible = [
        " ".join(t)
        for group in (_INDIVISIBLE_KAK, _INDIVISIBLE_PRONOUN, _INDIVISIBLE_FIXED)
        for t in group
    ]
    compound_sconj = [" ".join(compound) for compound, _pos in _COMPOUND_SCONJ]
    # second-locative nouns commonly governed by в/на (loc2 forms)
    loc2 = (
        "лесу снегу порту шкафу углу берегу мосту саду краю бою строю тылу "
        "плену аду раю быту виду носу боку году часу ряду полу мелу льду "
        "пруду долгу цеху отпуску аэропорту"
    ).split()

    pats = {
        # never-fired on news (dialogue/colloquial/genre-bound)
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
        "comma_x_ne_x": r"\b([А-Яа-яЁё]{3,})\s+не\s+\1\b",
        "comma_compound_conj_split": rf"\b(?:{alt(compound_sconj)})\b",
        "verb_tense_anchor": r"\b(?:вчера|позавчера|завтра|послезавтра|недавно)\b",
        "noun_case_prep_e_u": rf"\b(?:в|на)\s+(?:{'|'.join(loc2)})\b",
        "numeral_poltora": r"\b(?:полтора|полторы|полутора|полтораста)\b",
    }
    case_sensitive = {"comma_interjection", "comma_response", "comma_vocative"}
    return {
        name: re.compile(p, 0 if name in case_sensitive else re.IGNORECASE)
        for name, p in pats.items()
    }


def _good_sentence(s: str) -> bool:
    w = s.split()
    return 5 <= len(w) <= 60 and not re.search(r"[<>{}\[\]|@#$%^*_=~`]", s)


def mine_pools(
    sources: list[Path],
    outdir: Path,
    cap: int = 2000,
    seed: int = 42,
    patterns: dict[str, re.Pattern] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Sweep text sources; write per-class pools to outdir. Returns meta."""
    patterns = patterns or build_class_patterns()
    rng = random.Random(seed)
    reservoirs: dict[str, list[str]] = defaultdict(list)
    seen_counts: dict[str, int] = defaultdict(int)
    seen_sents: dict[str, set[int]] = defaultdict(set)

    for src in sources:
        if progress:
            progress(f"scanning {src} …")
        with src.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s or not _good_sentence(s):
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
                    if len(r) < cap:
                        r.append(s)
                    else:
                        j = rng.randrange(seen_counts[name])
                        if j < cap:
                            r[j] = s

    outdir.mkdir(parents=True, exist_ok=True)
    meta = {
        "seed": seed,
        "cap": cap,
        "sources": [str(s) for s in sources],
        "seen": dict(seen_counts),
        "sampled": {k: len(v) for k, v in reservoirs.items()},
    }
    for name, sents in sorted(reservoirs.items()):
        (outdir / f"{name}.txt").write_text(
            "\n".join(sents) + "\n", encoding="utf-8"
        )
    (outdir / "pools.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return meta
