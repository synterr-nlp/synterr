"""Tests for FunctionSpellingHandler."""

from random import Random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.function_spelling import (
    FunctionSpellingHandler,
)


def _tok(text, pos="NOUN", lemma=None, idx=0, **kw):
    return AnalyzedToken(
        text=text, lemma=lemma or text.lower(), pos=pos, features={}, idx=idx, **kw
    )


class TestFunctionSpellingProtocol:
    handler = FunctionSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "function_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5

    def test_set_subtype_weights(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_attachment": 100})
        assert h._weights["ne_attachment"] == 100
        assert h._weights["conjunction_split"] == 25  # default preserved


class TestConjunctionSplit:
    handler = FunctionSpellingHandler()

    def test_can_apply_solid_conjunction(self):
        tokens = [_tok("чтобы", pos="SCONJ", idx=0)]
        assert self.handler.can_apply(tokens, 0)

    def test_split_chtoby(self):
        tokens = [_tok("чтобы", pos="SCONJ", idx=0)]
        sentence = ["чтобы"]
        # Force conjunction_split by giving it all weight
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["что", "бы"]
        assert result.error_type == "function_spelling_conjunction_split"
        assert result.original == "чтобы"

    def test_split_takzhe(self):
        tokens = [
            _tok("Я", pos="PRON", idx=0),
            _tok("также", pos="ADV", idx=1),
        ]
        sentence = ["Я", "также"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Я", "так", "же"]

    def test_split_preserves_capitalization(self):
        tokens = [_tok("Чтобы", pos="SCONJ", idx=0)]
        sentence = ["Чтобы"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Что", "бы"]

    def test_split_zato(self):
        tokens = [_tok("зато", pos="SCONJ", idx=0)]
        sentence = ["зато"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["за", "то"]

    def test_split_prichem(self):
        tokens = [_tok("причём", pos="ADV", idx=0)]
        sentence = ["причём"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["при", "чём"]

    def test_split_ottogo(self):
        tokens = [_tok("оттого", pos="ADV", idx=0)]
        sentence = ["оттого"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["от", "того"]


class TestConjunctionMerge:
    def test_can_apply_split_pair(self):
        handler = FunctionSpellingHandler()
        tokens = [
            _tok("что", pos="SCONJ", idx=0),
            _tok("бы", pos="PART", idx=1),
        ]
        assert handler.can_apply(tokens, 0)

    def test_merge_chto_by(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_merge": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_split": 0, "taki_hyphen": 0})
        tokens = [
            _tok("что", pos="SCONJ", idx=0),
            _tok("бы", pos="PART", idx=1),
            _tok("пойти", pos="VERB", idx=2),
        ]
        sentence = ["что", "бы", "пойти"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["чтобы", "пойти"]
        assert result.error_type == "function_spelling_conjunction_merge"

    def test_merge_preserves_capitalization(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_merge": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_split": 0, "taki_hyphen": 0})
        tokens = [
            _tok("Что", pos="SCONJ", idx=0),
            _tok("бы", pos="PART", idx=1),
        ]
        sentence = ["Что", "бы"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Чтобы"]

    def test_merge_tak_zhe(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_merge": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_split": 0, "taki_hyphen": 0})
        tokens = [
            _tok("так", pos="ADV", idx=0),
            _tok("же", pos="PART", idx=1),
        ]
        sentence = ["так", "же"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["также"]


class TestNeAttachment:
    def test_can_apply_ne_before_noun(self):
        handler = FunctionSpellingHandler()
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("счастье", pos="NOUN", idx=1),
        ]
        assert handler.can_apply(tokens, 0)

    def test_cannot_apply_ne_before_verb(self):
        """не before VERB is not attachable (не is always separate with verbs)."""
        handler = FunctionSpellingHandler()
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("пришёл", pos="VERB", idx=1),
        ]
        # VERB is not in NE_ATTACHABLE_POS
        assert not handler.can_apply(tokens, 0)

    def test_attach_ne_to_noun(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_attachment": 100, "ne_detachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("счастье", pos="NOUN", idx=1),
        ]
        sentence = ["не", "счастье"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["несчастье"]
        assert result.error_type == "function_spelling_ne_attachment"

    def test_attach_ne_to_adj(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_attachment": 100, "ne_detachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("большой", pos="ADJ", idx=1),
        ]
        sentence = ["не", "большой"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["небольшой"]

    def test_attach_preserves_capitalization(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_attachment": 100, "ne_detachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [
            _tok("Не", pos="PART", idx=0),
            _tok("правда", pos="NOUN", idx=1),
        ]
        sentence = ["Не", "правда"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Неправда"]


class TestNeDetachment:
    def test_can_apply_ne_prefix_word(self):
        handler = FunctionSpellingHandler()
        tokens = [_tok("несчастье", pos="NOUN", idx=0)]
        assert handler.can_apply(tokens, 0)

    def test_detach_ne_from_noun(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_detachment": 100, "ne_attachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [_tok("несчастье", pos="NOUN", idx=0)]
        sentence = ["несчастье"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["не", "счастье"]
        assert result.error_type == "function_spelling_ne_detachment"

    def test_detach_ne_from_adj(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_detachment": 100, "ne_attachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [_tok("небольшой", pos="ADJ", idx=0)]
        sentence = ["небольшой"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["не", "большой"]

    def test_detach_preserves_capitalization(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"ne_detachment": 100, "ne_attachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [_tok("Неправда", pos="NOUN", idx=0)]
        sentence = ["Неправда"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Не", "правда"]

    def test_short_ne_word_rejected(self):
        """Words like 'нет' (len 3) should not be split."""
        h = FunctionSpellingHandler()
        tokens = [_tok("нет", pos="PART", idx=0)]
        assert not h.can_apply(tokens, 0)  # len("нет") == 3, not > 3


class TestTakiHyphen:
    def test_can_apply_taki_in_word(self):
        handler = FunctionSpellingHandler()
        tokens = [_tok("всё-таки", pos="PART", idx=0)]
        assert handler.can_apply(tokens, 0)

    def test_remove_taki_hyphen(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"taki_hyphen": 100, "ne_attachment": 0, "ne_detachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0})
        tokens = [_tok("всё-таки", pos="PART", idx=0)]
        sentence = ["всё-таки"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["всё", "таки"]
        assert result.error_type == "function_spelling_taki_hyphen"

    def test_remove_opjat_taki(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"taki_hyphen": 100, "ne_attachment": 0, "ne_detachment": 0,
                                "conjunction_split": 0, "conjunction_merge": 0})
        tokens = [_tok("опять-таки", pos="ADV", idx=0)]
        sentence = ["опять-таки"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["опять", "таки"]


class TestCanApplyEdgeCases:
    handler = FunctionSpellingHandler()

    def test_non_matching_word(self):
        tokens = [_tok("дом", pos="NOUN", idx=0)]
        assert not self.handler.can_apply(tokens, 0)

    def test_ne_at_end_of_sentence(self):
        """не at the last position has no next token."""
        tokens = [_tok("не", pos="PART", idx=0)]
        assert not self.handler.can_apply(tokens, 0)

    def test_ne_before_punct(self):
        """не before punctuation is not attachable."""
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok(",", pos="PUNCT", idx=1),
        ]
        assert not self.handler.can_apply(tokens, 0)


class TestWeightedSubtypeSelection:
    def test_ambiguous_token_respects_weights(self):
        """A word like 'также' can both split and be ne-detached (starts with 'та' not 'не').
        With conjunction_split weight=100, it should always split."""
        h = FunctionSpellingHandler()
        h.set_subtype_weights({"conjunction_split": 100, "ne_detachment": 0,
                                "ne_attachment": 0, "conjunction_merge": 0, "taki_hyphen": 0})
        tokens = [_tok("также", pos="ADV", idx=0)]
        sentence = ["также"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert result.error_type == "function_spelling_conjunction_split"
        assert sentence == ["так", "же"]
