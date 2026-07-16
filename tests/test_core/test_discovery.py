"""Unit tests for synterr.discovery (survey + pool mining).

Pattern tests pin recall on curated positive/negative sentences per class;
mine_pools tests pin the reservoir/dedup/cap behavior and — regression for
the 2026-07-14 finding — that a targeted re-run over a pattern subset no
longer orphans the provenance of untouched pools in pools.meta.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from synterr.discovery import (
    _good_sentence,
    build_class_patterns,
    mine_pools,
    read_sentences,
    survey,
)

# ---------------------------------------------------------------------------
# read_sentences / _good_sentence
# ---------------------------------------------------------------------------


def test_read_sentences_skips_short_and_respects_limit(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text(
        "Коротко .\n"
        "Первое достаточно длинное предложение для отбора .\n"
        "\n"
        "Второе достаточно длинное предложение для отбора .\n"
        "Третье достаточно длинное предложение для отбора .\n",
        encoding="utf-8",
    )
    assert len(read_sentences(src)) == 3
    assert len(read_sentences(src, limit=2)) == 2
    assert all(len(s.split()) >= 5 for s in read_sentences(src))


def test_good_sentence_bounds_and_markup() -> None:
    assert _good_sentence("Пять слов тут ровно есть .")
    assert not _good_sentence("Мало слов .")
    assert not _good_sentence("Плохой <markup> внутри длинного предложения тут .")
    assert not _good_sentence("х " * 61)


# ---------------------------------------------------------------------------
# build_class_patterns
# ---------------------------------------------------------------------------

# (class, should-match, should-not-match) — recall-oriented, so the negative
# side only pins the *documented* exclusions, not general precision.
PATTERN_CASES = [
    (
        "agr_sv_collective",
        "Большинство проголосовало за принятие закона .",
        "Большинство депутатов проголосовало за принятие закона .",
    ),
    (
        "agr_sv_collective",
        "Подавляющее меньшинство осталось при своём мнении .",
        "Большинство из них уже уехали домой .",
    ),
    (
        "agr_mn_apposition",
        "Делегация прибыла в город Москву на переговоры .",
        "Он вырос в большом городе на юге страны .",
    ),
    (
        "agr_mn_compound_term",
        "Пассажиры обедали в вагоне-ресторане поезда дальнего следования .",
        "Он ехал в вагоне метро по кольцевой линии .",
    ),
    (
        "verb_iterative_suffix",
        "Компании успешно осваивают новые рынки сбыта .",
        "Освоение новых рынков идёт медленно и трудно .",
    ),
    (
        "taki_hyphen",
        "Он всё-таки успел на последний поезд .",
        "Так и не успел на последний поезд .",
    ),
    (
        "comma_x_ne_x",
        "Праздник не праздник , а работать надо .",
        "Праздник не отменяется даже в дождь .",
    ),
]


def test_patterns_compile_and_cover_expected_classes() -> None:
    patterns = build_class_patterns()
    for name in (
        "agr_sv_collective",
        "agr_mn_apposition",
        "agr_mn_compound_term",
        "verb_iterative_suffix",
    ):
        assert name in patterns, f"night-wave class {name} missing from patterns"
    assert all(isinstance(p, re.Pattern) for p in patterns.values())


@pytest.mark.parametrize(("name", "positive", "negative"), PATTERN_CASES)
def test_pattern_recall_and_documented_exclusions(
    name: str, positive: str, negative: str
) -> None:
    pat = build_class_patterns()[name]
    assert pat.search(positive), f"{name} must match: {positive}"
    assert not pat.search(negative), f"{name} must not match: {negative}"


def test_apposition_pattern_requires_capitalized_name() -> None:
    pat = build_class_patterns()["agr_mn_apposition"]
    assert pat.search("Мы жили тогда на реке Волге у самого берега .")
    assert not pat.search("Мы жили тогда на реке возле старой мельницы .")


# ---------------------------------------------------------------------------
# mine_pools
# ---------------------------------------------------------------------------

TAKI = "Он всё-таки успел на последний поезд сегодня вечером ."
POLTORA = "Прошло полтора часа до начала концерта в парке ."


def _write_source(tmp_path: Path, lines: list[str], name: str = "src.txt") -> Path:
    src = tmp_path / name
    src.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return src


def test_mine_pools_writes_pools_dedups_and_caps(tmp_path: Path) -> None:
    src = _write_source(tmp_path, [TAKI, TAKI, POLTORA, "Мало слов ."])
    outdir = tmp_path / "pools"
    meta = mine_pools([src], outdir, cap=1, seed=42)

    assert (outdir / "taki_hyphen.txt").read_text(encoding="utf-8").strip() == TAKI
    assert meta["seen"]["taki_hyphen"] == 1  # exact duplicate collapsed
    assert meta["sampled"]["numeral_poltora"] == 1

    many = [f"Он таки-{i} опять всё-таки успел на поезд номер {i} ." for i in range(9)]
    meta2 = mine_pools([_write_source(tmp_path, many, "b.txt")], outdir, cap=3, seed=1)
    assert meta2["seen"]["taki_hyphen"] == 9
    assert meta2["sampled"]["taki_hyphen"] == 3


def test_mine_pools_targeted_rerun_preserves_other_provenance(tmp_path: Path) -> None:
    outdir = tmp_path / "pools"
    mine_pools([_write_source(tmp_path, [TAKI, POLTORA])], outdir, cap=10, seed=42)

    only_poltora = {"numeral_poltora": build_class_patterns()["numeral_poltora"]}
    mine_pools(
        [_write_source(tmp_path, [POLTORA], "b.txt")],
        outdir,
        cap=5,
        seed=7,
        patterns=only_poltora,
    )

    meta = json.loads((outdir / "pools.meta.json").read_text(encoding="utf-8"))
    classes = meta["classes"]
    # untouched class keeps its original run's record
    assert classes["taki_hyphen"]["sampled"] == 1
    assert classes["taki_hyphen"]["seed"] == 42
    # targeted class carries the new run's parameters
    assert classes["numeral_poltora"]["seed"] == 7
    assert classes["numeral_poltora"]["cap"] == 5
    # the pool file itself was never deleted
    assert (outdir / "taki_hyphen.txt").exists()


def test_mine_pools_migrates_old_flat_meta(tmp_path: Path) -> None:
    outdir = tmp_path / "pools"
    outdir.mkdir()
    (outdir / "pools.meta.json").write_text(
        json.dumps(
            {
                "seed": 99,
                "cap": 2000,
                "sources": ["old.txt"],
                "seen": {"comma_x_ne_x": 62},
                "sampled": {"comma_x_ne_x": 62},
            }
        ),
        encoding="utf-8",
    )
    mine_pools(
        [_write_source(tmp_path, [TAKI])],
        outdir,
        cap=10,
        seed=42,
        patterns={"taki_hyphen": build_class_patterns()["taki_hyphen"]},
    )
    classes = json.loads((outdir / "pools.meta.json").read_text(encoding="utf-8"))[
        "classes"
    ]
    assert classes["comma_x_ne_x"] == {
        "seed": 99,
        "cap": 2000,
        "sources": ["old.txt"],
        "seen": 62,
        "sampled": 62,
    }
    assert classes["taki_hyphen"]["seed"] == 42


# ---------------------------------------------------------------------------
# survey (stub language module — no stanza)
# ---------------------------------------------------------------------------


class _Tok:
    def __init__(self, text: str) -> None:
        self.text = text


class _StubAnalyzer:
    def analyze_batch(self, batch: list[str]) -> list[list[_Tok]]:
        return [[_Tok(w) for w in s.split()] for s in batch]


class _FiringHandler:
    """Fires on every token equal to 'сработай'."""

    name = "stub_fire"
    subtypes = ["stub_fire"]

    def can_apply(self, tokens, idx):
        return tokens[idx].text == "сработай"

    def apply(self, tokens, sentence, idx, modified, rng=None):
        from synterr.core.protocol import ErrorResult

        return ErrorResult(
            error_type="stub_fire",
            category="OTHER",
            start_idx=idx,
            end_idx=idx + 1,
            original=sentence[idx],
            corrupted="XX",
            fix_tag="$STUB",
        )


class _SilentHandler:
    name = "stub_silent"
    subtypes = ["stub_silent"]

    def can_apply(self, tokens, idx):
        return False

    def apply(self, tokens, sentence, idx, modified, rng=None):
        return None


class _StubLang:
    def get_analyzer(self, use_depparse: bool, backend: str) -> _StubAnalyzer:
        return _StubAnalyzer()

    def get_error_handlers(self) -> list:
        return [_FiringHandler(), _SilentHandler()]


def test_survey_reports_rates_starving_and_never_fired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("synterr.core.registry.get_language", lambda lang: _StubLang())
    sentences = ["пожалуйста сработай один раз здесь"] + [
        f"обычное предложение номер {i} без триггера" for i in range(9)
    ]
    report = survey(sentences, tries=1, seed=0, batch_size=4)

    assert report["n_sentences"] == 10
    assert report["emissions"]["stub_fire"] == 1
    assert report["per_1k"]["stub_fire"] == 100.0
    assert report["handler_success_rate"]["stub_fire"] == 1.0
    assert "stub_silent" in report["never_fired"]
    assert "stub_fire" not in report["never_fired"]
    # 100/1k is above the default starving threshold of 5
    assert "stub_fire" not in report["starving"]
    assert report["examples"]["stub_fire"]


def test_empty_lexicon_alternation_is_dropped_not_match_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing lexicon file must drop its pattern, not match everything."""
    monkeypatch.setattr(
        "synterr.languages.russian.errors.agreement_mn._hyphen_compound_lexicon",
        frozenset,
    )
    patterns = build_class_patterns()
    assert "agr_mn_compound_term" not in patterns
    assert not any(
        p.search("Обычное предложение без всяких паттернов тут .")
        for p in patterns.values()
    )


def test_numeral_declension_pattern_targets_oblique_forms() -> None:
    pat = build_class_patterns()["numeral_declension"]
    for pos in (
        "Речь шла о пятидесяти новых школах района .",
        "Он ограничился двумя короткими фразами в ответ .",
        "Из девяноста заявок отобрали лишь семь лучших .",
        "Штраф составил около трёхсот тысяч рублей сразу .",
    ):
        assert pat.search(pos), pos
    for neg in (
        "Пять человек пришли на собрание вчера вечером .",
        "Пятьдесят делегатов проголосовали за резолюцию единогласно .",
        "Сто лет прошло с того памятного дня .",
    ):
        assert not pat.search(neg), neg
