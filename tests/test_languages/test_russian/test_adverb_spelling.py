"""Tests for AdverbSpellingHandler — solid/separate/hyphen confusion."""

from random import Random

import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.adverb_spelling import AdverbSpellingHandler


def _tok(text, pos="ADV", lemma=None, idx=0):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features={},
        idx=idx,
    )


class TestProtocol:
    handler = AdverbSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "adverb_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 4

    def test_set_subtype_weights(self):
        h = AdverbSpellingHandler()
        h.set_subtype_weights({"adverb_solid_to_separate": 100})
        assert h._weights["adverb_solid_to_separate"] == 100
        assert h._weights["adverb_separate_to_solid"] == 30  # default preserved


class TestSolidToSeparate:
    def test_split_solid_adverb(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("наверх")]
        sentence = ["наверх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_solid_to_separate"
        assert sentence == ["на", "верх"]


class TestNoSuffixDerivedSplits:
    """Regression: suffix-derived adverbs (довольный → довольно etc.) must
    never be split — they are not §53–58 prep+noun formations, and the cut
    lands inside the root ("до вольно", "на прасно")."""

    NON_SPLITTABLE = ["довольно", "напрасно", "поочерёдно", "попарно", "вполне"]

    @pytest.mark.parametrize("word", NON_SPLITTABLE)
    def test_can_apply_false(self, word):
        h = AdverbSpellingHandler()
        assert h.can_apply([_tok(word)], 0) is False

    @pytest.mark.parametrize("word", NON_SPLITTABLE)
    def test_apply_returns_none(self, word):
        h = AdverbSpellingHandler()
        sentence = [word]
        result = h.apply([_tok(word)], sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == [word]

    def test_reverse_pairs_also_removed(self):
        """Auto-derived merge pairs ("до" + "вольно" → "довольно") must be
        gone too — they would 'correct' text that was never a learner split."""
        h = AdverbSpellingHandler()
        tokens = [_tok("до", pos="ADP"), _tok("вольно", idx=1)]
        assert h.can_apply(tokens, 0) is False
        assert h.apply(tokens, ["до", "вольно"], 0, set(), rng=Random(0)) is None


class TestHyphenToSeparate:
    def test_remove_hyphen(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("по-русски")]
        sentence = ["по-русски"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_hyphen_to_separate"
        assert sentence == ["по", "русски"]


class TestSeparateToSolid:
    def test_merge_prep_noun(self):
        h = AdverbSpellingHandler()
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_solid"
        assert sentence == ["наверх"]


class TestEnabledSubtypes:
    """set_enabled_subtypes restricts which subtype apply() may emit."""

    def test_filter_emits_only_requested_subtype(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        for seed in range(10):
            sentence = ["наверх"]
            result = h.apply([_tok("наверх")], sentence, 0, set(), rng=Random(seed))
            assert result is not None
            assert result.error_type == "adverb_spelling_adverb_solid_to_separate"
            assert sentence == ["на", "верх"]

    def test_filter_returns_none_when_subtype_unavailable(self):
        """A solid adverb cannot be merged (separate_to_solid); requesting that
        subtype must decline rather than fall back to solid_to_separate."""
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        sentence = ["наверх"]
        result = h.apply([_tok("наверх")], sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == ["наверх"]

    def test_filter_allows_merge_on_two_token_sequence(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_separate_to_solid"})
        tokens = [_tok("на", pos="ADP"), _tok("верх", pos="NOUN", idx=1)]
        sentence = ["на", "верх"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "adverb_spelling_adverb_separate_to_solid"
        assert sentence == ["наверх"]

    def test_none_means_all(self):
        h = AdverbSpellingHandler()
        h.set_enabled_subtypes({"adverb_solid_to_separate"})
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_invalid_subtype_raises(self):
        h = AdverbSpellingHandler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            h.set_enabled_subtypes({"not_a_subtype"})
