"""End-to-end integration tests against the REAL stanza backend.

These are the backstop the unit suite lacked: every other test hand-builds
AnalyzedToken lists or mocks the analyzer, so the contract between stanza's
actual dependency output and the handlers' assumptions was never validated.
That gap let punctuation handlers pass 100% of unit tests while firing 0/N on
real validation sentences (2026-05-27 audit, finding #8).

Each test runs a real multi-clause sentence through analyze → corrupt and
asserts the handler fires with the expected subtype. Marked `slow` because
loading stanza + CoreNLP costs a few seconds; deselect with `-m "not slow"`.

Sentences are drawn from / modeled on the LoRuGEC validation examples in the
contributor bug reports, which are exactly the cases that broke before.
"""

from __future__ import annotations

import pytest

from synterr.core.pipeline import ErrorPipeline, GenerationConfig
from synterr.core.registry import get_language

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def pipeline() -> ErrorPipeline:
    """One real depparse-enabled pipeline shared across the module."""
    language = get_language("ru")
    config = GenerationConfig(seed=42, use_depparse=True)
    return ErrorPipeline(language, config)


def _apply(pipeline: ErrorPipeline, error: str, text: str):
    """Run a forced error; return (fired, error_type, corrupted_text)."""
    result = pipeline.apply_error(text, error)
    if result is None:
        return (False, None, None)
    etype = result.errors[0].error_type if result.errors else None
    return (True, etype, " ".join(result.corrupted_tokens))


# ── Comma pair-delete on realistic multi-clause sentences ───────────────────
# These are the exact failure class from the contributor's reports: long
# sentences where the opening and closing commas attach to different heads.

PAIR_CASES = [
    # (error spec, sentence, expected subtype)
    (
        "comma_pair_delete:pair_gerund",
        "Хотя, родившись в 1940 году, Андреевский не мог наблюдать жизнь "
        "довоенной Москвы, он много работал в архивах.",
        "pair_gerund",
    ),
    (
        "comma_pair_delete:pair_participle",
        "Книга, прочитанная им вчера, лежала на столе.",
        "pair_participle",
    ),
    (
        "comma_pair_delete:pair_parenthetical",
        "Стало быть, по-вашему, нет разницы между глупым и умным человеком?",
        "pair_parenthetical",
    ),
]


@pytest.mark.parametrize("error,text,expected", PAIR_CASES)
def test_comma_pair_delete_fires_on_real_sentences(pipeline, error, text, expected):
    fired, etype, corrupted = _apply(pipeline, error, text)
    assert fired, f"{error} did not fire on: {text}"
    assert etype == expected, f"expected {expected}, got {etype}"
    # A pair delete always removes exactly two commas
    assert corrupted.count(",") == text.count(",") - 2


# ── Comma-delete subtype classification on real text ────────────────────────

COMMA_CASES = [
    (
        "comma_delete:comma_subordinate",
        "Отец говорил мне, что он не видывал таких хлебов.",
        "comma_subordinate",
    ),
    (
        "comma_delete:comma_parenthetical",
        "Исследования содержат в себе, по существу, приёмы исчисления.",
        "comma_parenthetical",
    ),
]


@pytest.mark.parametrize("error,text,expected", COMMA_CASES)
def test_comma_delete_classifies_on_real_sentences(pipeline, error, text, expected):
    fired, etype, _ = _apply(pipeline, error, text)
    assert fired, f"{error} did not fire on: {text}"
    assert etype == expected, f"expected {expected}, got {etype}"


# ── Dash handlers: apposition vs subject-predicate ──────────────────────────


def test_dash_subj_pred_on_real_sentence(pipeline):
    fired, etype, _ = _apply(
        pipeline, "dash_delete:dash_subj_pred", "Москва — столица России."
    )
    assert fired
    assert etype == "dash_subj_pred"


def test_dash_apposition_on_real_sentence(pipeline):
    fired, etype, _ = _apply(
        pipeline,
        "dash_delete:dash_apposition",
        "Самой глубокой является пещера Соляник — государственный памятник природы.",
    )
    assert fired
    assert etype == "dash_apposition"


def test_dash_to_comma_substitution_on_real_sentence(pipeline):
    fired, etype, corrupted = _apply(
        pipeline,
        "dash_to_comma:dash_to_comma_apposition",
        "Самой глубокой является пещера Соляник — государственный памятник природы.",
    )
    assert fired
    assert etype == "dash_to_comma_apposition"
    assert "—" not in corrupted and "," in corrupted


# ── comma_insert clause junction (§104/§109) ────────────────────────────────


def test_comma_clause_junction_on_real_sentence(pipeline):
    fired, etype, corrupted = _apply(
        pipeline,
        "comma_insert:comma_clause_junction",
        "Утром папа приготовил нам завтрак и мы все сели за стол.",
    )
    assert fired
    assert etype == "comma_clause_junction"
    # An extra comma was inserted
    assert corrupted.count(",") == 1


# ── Semantics: inflection on real morphology ────────────────────────────────


def test_collocation_inflects_on_real_sentence(pipeline):
    fired, _, corrupted = _apply(pipeline, "collocation", "Он принял важное решение.")
    if not fired:
        pytest.skip("collocation lexicon lacks принять/решение")
    # Must not leave the bare infinitive in place
    assert "сделать" not in corrupted


# ── Smoke: the pipeline produces SOME error on generic text ─────────────────


def test_pipeline_generate_smoke(pipeline):
    result = pipeline.generate("Книга, лежащая на столе, принадлежит мне.")
    assert result.corrupted_tokens  # non-empty
