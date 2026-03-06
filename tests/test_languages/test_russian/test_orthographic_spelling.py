"""Tests for OrthographicSpellingHandler — morpheme-level spelling rules."""

from random import Random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.orthographic_spelling import (
    OrthographicSpellingHandler,
)


def _tok(text, pos="NOUN", lemma=None, idx=0):
    return AnalyzedToken(
        text=text, lemma=lemma or text.lower(), pos=pos, features={}, idx=idx,
    )


def _force_subtype(subtype: str) -> OrthographicSpellingHandler:
    """Create handler with only one subtype active (weight=100, rest=0)."""
    h = OrthographicSpellingHandler()
    weights = {s: 0 for s in h.subtypes}
    weights[subtype] = 100
    h.set_subtype_weights(weights)
    return h


class TestProtocol:
    handler = OrthographicSpellingHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "orthographic_spelling"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is False
        assert len(self.handler.subtypes) == 9

    def test_set_subtype_weights(self):
        h = OrthographicSpellingHandler()
        h.set_subtype_weights({"pre_pri": 100})
        assert h._weights["pre_pri"] == 100
        assert h._weights["suffix_ek_ik"] == 10  # default


class TestPrePri:
    """пре-/при- prefix confusion."""

    def test_pre_to_pri(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("пребывает", pos="VERB")]
        sentence = ["пребывает"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence[0] == "прибывает"

    def test_pri_to_pre(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("приступить", pos="VERB")]
        sentence = ["приступить"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "преступить"

    def test_preserves_case(self):
        h = _force_subtype("pre_pri")
        tokens = [_tok("Препрыгивая", pos="VERB")]
        sentence = ["Препрыгивая"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Припрыгивая"

    def test_short_word_rejected(self):
        h = OrthographicSpellingHandler()
        tokens = [_tok("при", pos="ADP")]
        assert not h.can_apply(tokens, 0)  # too short


class TestYiAfterPrefix:
    """ы/и after consonant-ending prefix."""

    def test_i_to_y_russian_prefix(self):
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("безинициативных", pos="ADJ")]
        sentence = ["безинициативных"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "безынициативных"

    def test_y_to_i_foreign_prefix(self):
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("трансыранский", pos="ADJ")]
        sentence = ["трансыранский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "трансиранский"

    def test_sverkh_keeps_i(self):
        """сверх- is exception: и stays. Error = using ы."""
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("сверхындустриализации")]
        sentence = ["сверхындустриализации"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "сверхиндустриализации"

    def test_podytog(self):
        h = _force_subtype("y_i_after_prefix")
        tokens = [_tok("подитожила", pos="VERB")]
        sentence = ["подитожила"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "подытожила"


class TestSuffixEnkOnk:
    """-еньк/-оньк swap."""

    def test_onk_to_enk(self):
        h = _force_subtype("suffix_enk_onk")
        tokens = [_tok("душонька")]
        sentence = ["душонька"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "душенька"

    def test_enk_to_onk(self):
        h = _force_subtype("suffix_enk_onk")
        tokens = [_tok("рыбенька")]
        sentence = ["рыбенька"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "рыбонька"


class TestSuffixInskEnsk:
    """-инск/-енск swap."""

    def test_ensk_to_insk(self):
        h = _force_subtype("suffix_insk_ensk")
        tokens = [_tok("сестренский", pos="ADJ")]
        sentence = ["сестренский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "сестринский"

    def test_insk_to_ensk(self):
        h = _force_subtype("suffix_insk_ensk")
        tokens = [_tok("Сходнинский", pos="ADJ")]
        sentence = ["Сходнинский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Сходненский"


class TestSuffixItsEts:
    """-иц/-ец swap in neuter nouns."""

    def test_ets_to_its(self):
        h = _force_subtype("suffix_its_ets")
        tokens = [_tok("маслеце")]
        sentence = ["маслеце"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "маслице"

    def test_its_to_ets(self):
        h = _force_subtype("suffix_its_ets")
        tokens = [_tok("письмицо")]
        sentence = ["письмицо"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "письмецо"


class TestSuffixEkIk:
    """-ек/-ик swap."""

    def test_ik_to_ek(self):
        h = _force_subtype("suffix_ek_ik")
        tokens = [_tok("овражик")]
        sentence = ["овражик"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "овражек"

    def test_ek_to_ik(self):
        h = _force_subtype("suffix_ek_ik")
        tokens = [_tok("кирпичек")]
        sentence = ["кирпичек"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "кирпичик"

    def test_ik_at_end_after_yo(self):
        h = _force_subtype("suffix_ek_ik")
        tokens = [_tok("василёчик")]
        sentence = ["василёчик"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        # ик→ек at the end (ё is not in the suffix)
        assert sentence[0] == "василёчек"


class TestParticipleSuffix:
    """Conjugation-dependent participle suffix swaps."""

    def test_ushch_to_ashch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("ищущую", pos="ADJ")]
        sentence = ["ищущую"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "ищащую"

    def test_ashch_to_ushch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("граничащее", pos="ADJ")]
        sentence = ["граничащее"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "граничущее"

    def test_em_to_im(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("изучаемого", pos="ADJ")]
        sentence = ["изучаемого"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "изучаимого"

    def test_im_to_em(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("мыслимый", pos="ADJ")]
        sentence = ["мыслимый"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "мыслемый"

    def test_yushch_to_yashch(self):
        h = _force_subtype("participle_suffix")
        tokens = [_tok("колющей", pos="ADJ")]
        sentence = ["колющей"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "колящей"


class TestVowelAfterTs:
    """Vowel swaps after ц."""

    def test_o_to_e(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("герцога")]
        sentence = ["герцога"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "герцега"

    def test_i_to_y(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("циганский", pos="ADJ")]
        sentence = ["циганский"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "цыганский"

    def test_y_to_i(self):
        h = _force_subtype("vowel_after_ts")
        tokens = [_tok("цыновками")]
        sentence = ["цыновками"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "циновками"


class TestVowelAfterSibilant:
    """Vowel swaps after ш, щ, ж, ч."""

    def test_o_to_yo(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("Девчонка")]
        sentence = ["Девчонка"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "Девчёнка"

    def test_yo_to_o(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("шёвинист")]
        sentence = ["шёвинист"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "шовинист"

    def test_yu_to_u(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("жюри")]
        sentence = ["жюри"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "жури"

    def test_u_to_yu(self):
        h = _force_subtype("vowel_after_sibilant")
        tokens = [_tok("брошура")]
        sentence = ["брошура"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence[0] == "брошюра"


class TestCanApplyEdgeCases:
    handler = OrthographicSpellingHandler()

    def test_non_alpha_rejected(self):
        tokens = [_tok(",", pos="PUNCT")]
        assert not self.handler.can_apply(tokens, 0)

    def test_short_word_rejected(self):
        tokens = [_tok("да", pos="PART")]
        assert not self.handler.can_apply(tokens, 0)
