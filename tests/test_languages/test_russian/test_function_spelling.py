"""Tests for FunctionSpellingHandler."""

from random import Random

import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.function_spelling import (
    FunctionSpellingHandler,
)


def _tok(text, pos="NOUN", lemma=None, idx=0, features=None, **kw):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features=features or {},
        idx=idx,
        **kw,
    )


def _neg_pronoun_handler():
    h = FunctionSpellingHandler()
    h.set_enabled_subtypes({"neg_pronoun_ne_ni"})
    return h


class TestFunctionSpellingProtocol:
    handler = FunctionSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "function_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 6

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
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
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
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Я", "так", "же"]

    def test_split_preserves_capitalization(self):
        tokens = [_tok("Чтобы", pos="SCONJ", idx=0)]
        sentence = ["Чтобы"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Что", "бы"]

    def test_split_zato(self):
        tokens = [_tok("зато", pos="SCONJ", idx=0)]
        sentence = ["зато"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["за", "то"]

    def test_split_prichem(self):
        tokens = [_tok("причём", pos="ADV", idx=0)]
        sentence = ["причём"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["при", "чём"]

    def test_split_ottogo(self):
        tokens = [_tok("оттого", pos="ADV", idx=0)]
        sentence = ["оттого"]
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
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
        h.set_subtype_weights(
            {
                "conjunction_merge": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "taki_hyphen": 0,
            }
        )
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
        h.set_subtype_weights(
            {
                "conjunction_merge": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [
            _tok("Что", pos="SCONJ", idx=0),
            _tok("бы", pos="PART", idx=1),
        ]
        sentence = ["Что", "бы"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Чтобы"]

    def test_merge_tak_zhe(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "conjunction_merge": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [
            _tok("так", pos="ADV", idx=0),
            _tok("же", pos="PART", idx=1),
        ]
        sentence = ["так", "же"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["также"]


class TestNeAttachment:
    def test_can_apply_ne_before_noun(self):
        handler = FunctionSpellingHandler()
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("счастье", pos="NOUN", idx=1),
        ]
        assert handler.can_apply(tokens, 0)

    def test_can_apply_ne_before_verb(self):
        """не before VERB IS attachable (LoRuGEC rule 25: не хочу → нехочу)."""
        handler = FunctionSpellingHandler()
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("пришёл", pos="VERB", idx=1),
        ]
        # VERB is in NE_ATTACHABLE_POS since LoRuGEC rule 25
        assert handler.can_apply(tokens, 0)

    def test_attach_ne_to_noun(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "ne_attachment": 100,
                "ne_detachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
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
        h.set_subtype_weights(
            {
                "ne_attachment": 100,
                "ne_detachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [
            _tok("не", pos="PART", idx=0),
            _tok("большой", pos="ADJ", idx=1),
        ]
        sentence = ["не", "большой"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["небольшой"]

    def test_attach_preserves_capitalization(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "ne_attachment": 100,
                "ne_detachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [
            _tok("Не", pos="PART", idx=0),
            _tok("правда", pos="NOUN", idx=1),
        ]
        sentence = ["Не", "правда"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["Неправда"]


class TestNeDetachment:
    def test_can_apply_ne_prefix_word(self):
        handler = FunctionSpellingHandler()
        tokens = [_tok("несчастье", pos="NOUN", idx=0)]
        assert handler.can_apply(tokens, 0)

    def test_detach_ne_from_noun(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "ne_detachment": 100,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [_tok("несчастье", pos="NOUN", idx=0)]
        sentence = ["несчастье"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["не", "счастье"]
        assert result.error_type == "function_spelling_ne_detachment"

    def test_detach_ne_from_adj(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "ne_detachment": 100,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [_tok("небольшой", pos="ADJ", idx=0)]
        sentence = ["небольшой"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["не", "большой"]

    def test_detach_preserves_capitalization(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "ne_detachment": 100,
                "ne_attachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [_tok("Неправда", pos="NOUN", idx=0)]
        sentence = ["Неправда"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
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
        h.set_subtype_weights(
            {
                "taki_hyphen": 100,
                "ne_attachment": 0,
                "ne_detachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
            }
        )
        tokens = [_tok("всё-таки", pos="PART", idx=0)]
        sentence = ["всё-таки"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["всё", "таки"]
        assert result.error_type == "function_spelling_taki_hyphen"

    def test_remove_opjat_taki(self):
        h = FunctionSpellingHandler()
        h.set_subtype_weights(
            {
                "taki_hyphen": 100,
                "ne_attachment": 0,
                "ne_detachment": 0,
                "conjunction_split": 0,
                "conjunction_merge": 0,
            }
        )
        tokens = [_tok("опять-таки", pos="ADV", idx=0)]
        sentence = ["опять-таки"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["опять", "таки"]


class TestNegPronounNeNi:
    """§47: не↔ни confusion in negative pronouns (некого ↔ никого)."""

    def test_can_apply_neg_pronoun(self):
        h = FunctionSpellingHandler()
        tokens = [_tok("некого", pos="PRON", idx=0)]
        assert h.can_apply(tokens, 0)

    def test_no_negated_verb_corrupts_ne_to_ni(self):
        """Impersonal/infinitive 'Мне некого спросить' → correct is НЕ-,
        so the error is НЕ→НИ: 'Мне никого спросить'."""
        h = _neg_pronoun_handler()
        tokens = [
            _tok("Мне", pos="PRON", idx=0),
            _tok("некого", pos="PRON", idx=1),
            _tok("спросить", pos="VERB", idx=2, features={"VerbForm": "Inf"}),
            _tok(".", pos="PUNCT", idx=3),
        ]
        sentence = ["Мне", "некого", "спросить", "."]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "function_spelling_neg_pronoun_ne_ni"
        assert sentence == ["Мне", "никого", "спросить", "."]
        assert result.original == "некого"
        assert result.corrupted == "никого"

    def test_negated_finite_verb_corrupts_ni_to_ne(self):
        """'Я никого не видел' has a negated finite verb → correct is НИ-,
        so the error is НИ→НЕ: 'Я некого не видел'."""
        h = _neg_pronoun_handler()
        tokens = [
            _tok("Я", pos="PRON", idx=0),
            _tok("никого", pos="PRON", idx=1),
            _tok("не", pos="PART", idx=2),
            _tok("видел", pos="VERB", idx=3, features={"VerbForm": "Fin"}),
            _tok(".", pos="PUNCT", idx=4),
        ]
        sentence = ["Я", "никого", "не", "видел", "."]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "function_spelling_neg_pronoun_ne_ni"
        assert sentence == ["Я", "некого", "не", "видел", "."]
        assert result.original == "никого"
        assert result.corrupted == "некого"

    def test_length_preserving_single_token(self):
        h = _neg_pronoun_handler()
        tokens = [
            _tok("нечего", pos="PRON", idx=0),
            _tok("терять", pos="VERB", idx=1, features={"VerbForm": "Inf"}),
        ]
        sentence = ["нечего", "терять"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert len(sentence) == 2
        assert sentence == ["ничего", "терять"]
        assert result.end_idx == result.start_idx + 1

    def test_preserves_capitalization(self):
        h = _neg_pronoun_handler()
        tokens = [
            _tok("Некому", pos="PRON", idx=0),
            _tok("работать", pos="VERB", idx=1, features={"VerbForm": "Inf"}),
        ]
        sentence = ["Некому", "работать"]
        h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert sentence == ["Никому", "работать"]

    def test_wrong_direction_declines(self):
        """A ни- pronoun in a clause WITHOUT a negated finite verb cannot be
        'corrupted' in the не→ни direction — the gate must decline rather than
        emit a no-op or mislabeled error."""
        h = _neg_pronoun_handler()
        tokens = [
            _tok("никого", pos="PRON", idx=0),
            _tok("спросить", pos="VERB", idx=1, features={"VerbForm": "Inf"}),
        ]
        sentence = ["никого", "спросить"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == ["никого", "спросить"]

    def test_ni_with_negated_verb_only_at_idx(self):
        """A не- pronoun sitting in a clause that DOES have a negated finite
        verb is the correct spelling there, so it cannot be corrupted via the
        ни→не direction and the не→ni direction is suppressed by the gate."""
        h = _neg_pronoun_handler()
        tokens = [
            _tok("некого", pos="PRON", idx=0),
            _tok("не", pos="PART", idx=1),
            _tok("видел", pos="VERB", idx=2, features={"VerbForm": "Fin"}),
        ]
        sentence = ["некого", "не", "видел"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence == ["некого", "не", "видел"]


@pytest.mark.slow
class TestNegPronounNeNiRealBackend:
    """End-to-end with the real stanza backend so VerbForm/POS are genuine."""

    @pytest.fixture(scope="class")
    def backend(self):
        from synterr.languages.russian.backends.stanza_backend import StanzaBackend

        return StanzaBackend(use_depparse=True, use_gpu=False)

    def test_infinitive_clause_ne_to_ni(self, backend):
        h = _neg_pronoun_handler()
        tokens = backend.analyze("Мне некого спросить.")
        idx = next(i for i, t in enumerate(tokens) if t.text.lower() == "некого")
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, idx, set(), rng=Random(0))
        assert result is not None
        assert result.original.lower() == "некого"
        assert result.corrupted.lower() == "никого"

    def test_negated_finite_clause_ni_to_ne(self, backend):
        h = _neg_pronoun_handler()
        tokens = backend.analyze("Я никого не видел.")
        idx = next(i for i, t in enumerate(tokens) if t.text.lower() == "никого")
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, idx, set(), rng=Random(0))
        assert result is not None
        assert result.original.lower() == "никого"
        assert result.corrupted.lower() == "некого"


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
        h.set_subtype_weights(
            {
                "conjunction_split": 100,
                "ne_detachment": 0,
                "ne_attachment": 0,
                "conjunction_merge": 0,
                "taki_hyphen": 0,
            }
        )
        tokens = [_tok("также", pos="ADV", idx=0)]
        sentence = ["также"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert result.error_type == "function_spelling_conjunction_split"
        assert sentence == ["так", "же"]


class TestAllCapsCapitalization:
    """Regression (audit B10): an all-caps source token must produce
    all-caps segments on every split/merge subtype, not just a capitalized
    first letter — "ЧТОБЫ" -> "Что бы" silently destroyed the caps-lock
    shape ("НЕКОГО СПРОСИТЬ" -> "НиКОГО СПРОСИТЬ")."""

    def _force(self, subtype):
        h = FunctionSpellingHandler()
        weights = dict.fromkeys(
            [
                "ne_attachment",
                "ne_detachment",
                "conjunction_split",
                "conjunction_merge",
                "taki_hyphen",
                "neg_pronoun_ne_ni",
            ],
            0,
        )
        weights[subtype] = 100
        h.set_subtype_weights(weights)
        return h

    def test_conjunction_split_all_caps(self):
        h = self._force("conjunction_split")
        tokens = [_tok("ЧТОБЫ", pos="SCONJ", idx=0)]
        sentence = ["ЧТОБЫ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["ЧТО", "БЫ"]

    def test_conjunction_merge_all_caps(self):
        h = self._force("conjunction_merge")
        tokens = [
            _tok("ЧТО", pos="SCONJ", idx=0),
            _tok("БЫ", pos="PART", idx=1),
        ]
        sentence = ["ЧТО", "БЫ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["ЧТОБЫ"]

    def test_ne_attachment_all_caps(self):
        h = self._force("ne_attachment")
        tokens = [
            _tok("НЕ", pos="PART", idx=0),
            _tok("ПРАВДА", pos="NOUN", idx=1),
        ]
        sentence = ["НЕ", "ПРАВДА"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["НЕПРАВДА"]

    def test_ne_detachment_all_caps(self):
        h = self._force("ne_detachment")
        tokens = [_tok("НЕСЧАСТЬЕ", pos="NOUN", idx=0)]
        sentence = ["НЕСЧАСТЬЕ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["НЕ", "СЧАСТЬЕ"]

    def test_taki_hyphen_all_caps(self):
        h = self._force("taki_hyphen")
        tokens = [_tok("ВСЁ-ТАКИ", pos="PART", idx=0)]
        sentence = ["ВСЁ-ТАКИ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["ВСЁ", "ТАКИ"]

    def test_neg_pronoun_all_caps(self):
        h = self._force("neg_pronoun_ne_ni")
        tokens = [
            _tok("НЕКОГО", pos="PRON", idx=0),
            _tok("СПРОСИТЬ", pos="VERB", idx=1, features={"VerbForm": "Inf"}),
        ]
        sentence = ["НЕКОГО", "СПРОСИТЬ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence == ["НИКОГО", "СПРОСИТЬ"]

    def test_title_case_still_only_capitalizes_first_letter(self):
        """Regression guard: title-case source must not be over-corrected
        into all-caps parts."""
        h = self._force("conjunction_split")
        tokens = [_tok("Чтобы", pos="SCONJ", idx=0)]
        sentence = ["Чтобы"]
        h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert sentence == ["Что", "бы"]


class TestEnabledSubtypes:
    """set_enabled_subtypes restricts which subtype apply() may emit."""

    def test_filter_forces_split_on_solid_conjunction(self):
        """Solid 'чтобы' only offers conjunction_split; the filter must emit
        exactly that subtype regardless of seed."""
        h = FunctionSpellingHandler()
        h.set_enabled_subtypes({"conjunction_split"})
        for seed in range(10):
            sentence = ["чтобы"]
            result = h.apply(
                [_tok("чтобы", pos="SCONJ", idx=0)],
                sentence,
                0,
                set(),
                rng=Random(seed),
            )
            assert result is not None
            assert result.error_type == "function_spelling_conjunction_split"
            assert sentence == ["что", "бы"]

    def test_filter_returns_none_for_unavailable_subtype(self):
        """conjunction_merge cannot apply to a solid 'чтобы' (no two-word
        sequence) — the handler must decline rather than fall back to split."""
        h = FunctionSpellingHandler()
        h.set_enabled_subtypes({"conjunction_merge"})
        sentence = ["чтобы"]
        result = h.apply(
            [_tok("чтобы", pos="SCONJ", idx=0)], sentence, 0, set(), rng=Random(0)
        )
        assert result is None
        assert sentence == ["чтобы"]

    def test_filter_allows_merge_on_two_word_sequence(self):
        h = FunctionSpellingHandler()
        h.set_enabled_subtypes({"conjunction_merge"})
        tokens = [_tok("что", pos="SCONJ", idx=0), _tok("бы", pos="PART", idx=1)]
        sentence = ["что", "бы"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "function_spelling_conjunction_merge"
        assert sentence == ["чтобы"]

    def test_none_means_all(self):
        h = FunctionSpellingHandler()
        h.set_enabled_subtypes({"conjunction_split"})
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_invalid_subtype_raises(self):
        h = FunctionSpellingHandler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            h.set_enabled_subtypes({"not_a_subtype"})
