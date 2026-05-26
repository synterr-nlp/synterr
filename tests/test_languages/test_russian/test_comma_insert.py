"""Tests for CommaInsertHandler."""

from random import Random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.comma_insert import CommaInsertHandler


def _tok(text, pos="NOUN", lemma=None, idx=0):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features={},
        idx=idx,
    )


def _force_subtype(subtype: str) -> CommaInsertHandler:
    h = CommaInsertHandler()
    weights = {s: 0 for s in h.subtypes}
    weights[subtype] = 100
    h.set_subtype_weights(weights)
    return h


class TestProtocol:
    handler = CommaInsertHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "comma_insert"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5


class TestCommaBeforeKak:
    """Insert comma before "как" where it shouldn't be."""

    def test_can_apply_kak_after_verb(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("работал", pos="VERB", idx=0),
            _tok("как", pos="SCONJ", idx=1),
            _tok("экономист", pos="NOUN", idx=2),
        ]
        assert handler.can_apply(tokens, 1)

    def test_cannot_apply_kak_already_preceded_by_comma(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok(",", pos="PUNCT", idx=0),
            _tok("как", pos="SCONJ", idx=1),
        ]
        assert not handler.can_apply(tokens, 1)

    def test_insert_comma_before_kak(self):
        h = _force_subtype("comma_before_kak")
        tokens = [
            _tok("работал", pos="VERB", idx=0),
            _tok("как", pos="SCONJ", idx=1),
            _tok("экономист", pos="NOUN", idx=2),
        ]
        sentence = ["работал", "как", "экономист"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["работал", ",", "как", "экономист"]
        assert result.fix_tag == "$DELETE"

    def test_kak_at_start_not_applicable(self):
        handler = CommaInsertHandler()
        tokens = [_tok("как", pos="SCONJ", idx=0)]
        assert not handler.can_apply(tokens, 0)


class TestCommaInSetPhrase:
    """Insert comma inside repeated conjunction set phrases."""

    def test_can_apply_repeated_ni(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("ни", pos="PART", idx=0),
            _tok("слуху", pos="NOUN", idx=1),
            _tok("ни", pos="PART", idx=2),
            _tok("духу", pos="NOUN", idx=3),
        ]
        assert handler.can_apply(tokens, 0)

    def test_insert_comma_in_ni_ni(self):
        h = _force_subtype("comma_in_set_phrase")
        tokens = [
            _tok("ни", pos="PART", idx=0),
            _tok("слуху", pos="NOUN", idx=1),
            _tok("ни", pos="PART", idx=2),
            _tok("духу", pos="NOUN", idx=3),
        ]
        sentence = ["ни", "слуху", "ни", "духу"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["ни", "слуху", ",", "ни", "духу"]

    def test_insert_comma_in_i_i(self):
        h = _force_subtype("comma_in_set_phrase")
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("стар", pos="ADJ", idx=1),
            _tok("и", pos="CCONJ", idx=2),
            _tok("млад", pos="ADJ", idx=3),
        ]
        sentence = ["и", "стар", "и", "млад"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["и", "стар", ",", "и", "млад"]

    def test_no_repeated_conjunction(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("стар", pos="ADJ", idx=1),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_already_has_comma(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok(",", pos="PUNCT", idx=1),
            _tok("стар", pos="ADJ", idx=2),
            _tok("и", pos="CCONJ", idx=3),
        ]
        # comma already after и → should not apply
        assert not handler.can_apply(tokens, 0)


class TestCommaBetweenConjunctions:
    """Insert comma between adjacent conjunctions."""

    def test_can_apply_i_kogda_with_correlative(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
            _tok("пришли", pos="VERB", idx=3),
            _tok("то", pos="PART", idx=4),
        ]
        assert handler.can_apply(tokens, 0)

    def test_cannot_apply_without_correlative(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_insert_comma_i_kogda(self):
        h = _force_subtype("comma_between_conjunctions")
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
            _tok("пришли", pos="VERB", idx=3),
            _tok("то", pos="PART", idx=4),
        ]
        sentence = ["и", "когда", "мы", "пришли", "то"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["и", ",", "когда", "мы", "пришли", "то"]

    def test_no_when_not_adjacent_conjunctions(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("дом", pos="NOUN", idx=1),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_a_chto_with_correlative(self):
        h = _force_subtype("comma_between_conjunctions")
        tokens = [
            _tok("а", pos="CCONJ", idx=0),
            _tok("что", pos="SCONJ", idx=1),
            _tok("он", pos="PRON", idx=2),
            _tok("так", pos="ADV", idx=3),
        ]
        sentence = ["а", "что", "он", "так"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["а", ",", "что", "он", "так"]


class TestCanApplyEdgeCases:
    handler = CommaInsertHandler()

    def test_non_target_word(self):
        tokens = [_tok("дом", pos="NOUN", idx=0)]
        assert not self.handler.can_apply(tokens, 0)
