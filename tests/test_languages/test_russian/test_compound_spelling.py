"""Tests for CompoundSpellingHandler — пол-, num/letter dashes, compound adjectives."""

from random import Random

import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.compound_spelling import (
    CompoundSpellingHandler,
    _is_pol_compound,
)


def _tok(text, pos="NOUN", lemma=None, idx=0):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features={},
        idx=idx,
    )


class TestProtocol:
    handler = CompoundSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "compound_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is False
        assert len(self.handler.subtypes) == 3

    def test_set_subtype_weights(self):
        h = CompoundSpellingHandler()
        h.set_subtype_weights({"pol_spelling": 100})
        assert h._weights["pol_spelling"] == 100
        assert h._weights["num_dash"] == 35  # default preserved


class TestPolCompoundDetection:
    """_is_pol_compound: positive genitive-noun test, not word_is_known."""

    @pytest.mark.parametrize(
        "word",
        ["полвека", "полдня", "полгода", "полстакана", "полминуты", "полслова"],
    )
    def test_real_pol_compounds_fire(self, word):
        assert _is_pol_compound(word) is True

    @pytest.mark.parametrize(
        "word",
        [
            "полный",
            "получить",
            "получил",
            "полоса",
            "положение",
            "полдень",
            "полночь",
            "полк",
            "политика",
            "полтора",
            "полтинник",
        ],
    )
    def test_false_positives_rejected(self, word):
        assert _is_pol_compound(word) is False


class TestPolSpelling:
    """pol_spelling corruption direction: merged → dashed and dashed → merged."""

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("полвека", "пол-века"),
            ("полдня", "пол-дня"),
            ("полгода", "пол-года"),
        ],
    )
    def test_merged_to_dashed_fires(self, word, expected):
        """Regression: pymorphy knows полвека/полдня/полгода as whole words,
        so the old word_is_known heuristic blocked them. They must now fire."""
        h = CompoundSpellingHandler()
        tokens = [_tok(word)]
        sentence = [word]
        assert h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_pol_spelling"
        assert sentence[0] == expected

    def test_dashed_to_merged_still_works(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("пол-лимона")]
        sentence = ["пол-лимона"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence[0] == "поллимона"

    def test_preserves_case(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("Полвека")]
        sentence = ["Полвека"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence[0] == "Пол-века"

    def test_false_positive_not_applied(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("полный", pos="ADJ")]
        assert not h.can_apply(tokens, 0)


class TestNumDash:
    def test_remove_dash_from_num_adj(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("25-процентный", pos="ADJ")]
        sentence = ["25-процентный"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_num_dash"
        assert sentence[0] == "25процентный"


class TestCompoundAdj:
    def test_remove_dash_from_compound_adj(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("военно-морской", pos="ADJ")]
        sentence = ["военно-морской"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_compound_adj"
        assert sentence[0] == "военноморской"


class TestEnabledSubtypes:
    """set_enabled_subtypes restricts which subtype apply() may emit."""

    def test_filter_emits_only_requested_subtype(self):
        h = CompoundSpellingHandler()
        h.set_enabled_subtypes({"pol_spelling"})
        for seed in range(10):
            sentence = ["полвека"]
            result = h.apply([_tok("полвека")], sentence, 0, set(), rng=Random(seed))
            assert result is not None
            assert result.error_type == "compound_spelling_pol_spelling"
            assert sentence[0] == "пол-века"

    def test_filter_returns_none_when_subtype_unavailable(self):
        """полвека only offers pol_spelling; requesting num_dash must decline."""
        h = CompoundSpellingHandler()
        h.set_enabled_subtypes({"num_dash"})
        sentence = ["полвека"]
        result = h.apply([_tok("полвека")], sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence[0] == "полвека"

    def test_none_means_all(self):
        h = CompoundSpellingHandler()
        h.set_enabled_subtypes({"pol_spelling"})
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_invalid_subtype_raises(self):
        h = CompoundSpellingHandler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            h.set_enabled_subtypes({"not_a_subtype"})
