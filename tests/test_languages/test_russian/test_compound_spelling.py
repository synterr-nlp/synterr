"""Tests for CompoundSpellingHandler — пол-, num/letter dashes, compound adjectives."""

from random import Random

import pytest

from synterr.languages.russian.errors.compound_spelling import (
    CompoundSpellingHandler,
    _is_pol_compound,
)

from .helpers import make_token as _tok


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

    @pytest.mark.parametrize(
        "word",
        ["политисполкома", "полуторажителей"],
    )
    def test_clipped_stem_compounds_rejected(self, word):
        """Regression (native-speaker annotation pass): политисполкома is
        полит+исполком (clipped stem), not пол+итисполкома — pymorphy's
        prediction analyzers parsed the garbage remainder as a genitive noun.
        The remainder must be a strictly dictionary-known genitive noun (and
        any morpheme segmentation must have "пол" as its own morpheme)."""
        assert _is_pol_compound(word) is False

    @pytest.mark.parametrize(
        "word",
        ["польша", "полтава", "полесье", "полтавы", "полесья"],
    )
    def test_toponyms_rejected(self, word):
        """Regression: pymorphy tags toponyms NOUN,Sgtm,Geox, so they passed the
        Sgtm whole-word test and got mangled (Польша → Пол-ьша). §46 пол-
        compounds take a genitive common noun; bare toponyms are not compounds."""
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

    def test_merged_unknown_word_with_known_genitive_remainder_fires(self):
        """поллимона is not in pymorphy's dictionary, but the remainder
        (лимона, gen.) is — the unknown-word branch must still corrupt it."""
        h = CompoundSpellingHandler()
        tokens = [_tok("поллимона")]
        sentence = ["поллимона"]
        assert h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_pol_spelling"
        assert sentence[0] == "пол-лимона"

    @pytest.mark.parametrize("word", ["политисполкома", "полуторажителей"])
    def test_clipped_stem_compound_not_applied(self, word):
        """Regression (annotation pass): политисполкома must never become
        пол-итисполкома — полит- is a clipped stem, not the пол- prefix."""
        h = CompoundSpellingHandler()
        tokens = [_tok(word)]
        sentence = [word]
        assert not h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence[0] == word

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

    @pytest.mark.parametrize("word", ["Польша", "Полтаву", "Полесье"])
    def test_toponym_not_applied(self, word):
        """Regression: Польша must never become Пол-ьша."""
        h = CompoundSpellingHandler()
        tokens = [_tok(word, pos="PROPN")]
        sentence = [word]
        assert not h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence[0] == word

    def test_pol_proper_name_merge_lowercases_internal_capital(self):
        """Regression: пол-Москвы merged must give полмосквы, never the
        camelCase tokenizer artifact полМосквы (§46б)."""
        h = CompoundSpellingHandler()
        tokens = [_tok("пол-Москвы", pos="NOUN")]
        sentence = ["пол-Москвы"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence[0] == "полмосквы"

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("полчаса", "пол-часа"),
            ("полсотни", "пол-сотни"),
            ("полбеды", "пол-беды"),
        ],
    )
    def test_allowlist_high_frequency_pol_words_fire(self, word, expected):
        """Regression: pymorphy parses полчаса/полсотни without Sgtm and
        полбеды as PRED, so the Sgtm gate skipped the most frequent §46а
        targets. The explicit allowlist must admit them."""
        assert _is_pol_compound(word) is True
        h = CompoundSpellingHandler()
        tokens = [_tok(word)]
        sentence = [word]
        assert h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_pol_spelling"
        assert sentence[0] == expected

    def test_oblique_polu_form_not_in_allowlist(self):
        """получаса (oblique of полчаса, полу- variant) must stay rejected:
        пол-учаса would be garbage."""
        assert _is_pol_compound("получаса") is False


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

    def test_capitalized_compound_merge_lowercases_second_segment(self):
        """Regression: Юго-Восточной merged must give Юговосточной, never
        the camelCase non-word ЮгоВосточной."""
        h = CompoundSpellingHandler()
        tokens = [_tok("Юго-Восточной", pos="ADJ")]
        sentence = ["Юго-Восточной"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence[0] == "Юговосточной"

    def test_fully_uppercase_compound_stays_uppercase(self):
        h = CompoundSpellingHandler()
        tokens = [_tok("ЮГО-ВОСТОЧНОЙ", pos="ADJ")]
        sentence = ["ЮГО-ВОСТОЧНОЙ"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert sentence[0] == "ЮГОВОСТОЧНОЙ"

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("железнодорожный", "железно-дорожный"),
            ("сельскохозяйственных", "сельско-хозяйственных"),
            ("молочнокислые", "молочно-кислые"),
        ],
    )
    def test_solid_compound_gets_erroneous_hyphen(self, word, expected):
        """Solid subordinate compounds (§44) are corrupted by inserting a
        dash at the component boundary. Stanza keeps solid tokens whole, so
        this direction gives Rule 36 coverage that survives the tokenizer
        splitting hyphenated compounds into fragments."""
        h = CompoundSpellingHandler()
        tokens = [_tok(word, pos="ADJ")]
        sentence = [word]
        assert h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is not None
        assert result.error_type == "compound_spelling_compound_adj"
        assert sentence[0] == expected

    @pytest.mark.parametrize("word", ["железнодорожник", "железнодорожника"])
    def test_derived_nouns_rejected(self, word):
        """Stem match alone is not enough: железнодорожник is a noun, its
        remainder 'ик' is not an adjectival ending."""
        h = CompoundSpellingHandler()
        assert not h.can_apply([_tok(word, pos="NOUN")], 0)

    @pytest.mark.parametrize(
        "word",
        ["молочно-кислые", "народно-хозяйственный", "плодово-овощной"],
    )
    def test_solid_norm_words_removed_from_hyphenated_list(self, word):
        """Regression: these spellings are themselves errors (norms are solid:
        молочнокислый, народнохозяйственный, плодоовощной). Removing their
        dash would emit the CORRECT form as 'corrupted' — direction inversion."""
        h = CompoundSpellingHandler()
        tokens = [_tok(word, pos="ADJ")]
        sentence = [word]
        assert not h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence[0] == word

    @pytest.mark.parametrize("word", ["юго-восток", "юго-востока", "северо-запад"])
    def test_hyphenated_nouns_not_matched_as_compound_adj(self, word):
        """Regression: юго-восток is a §43 compound noun (стороны света);
        corrupting it under the compound_adj (§44) label misattributes the
        rule. The adjective stems must not prefix-match the nouns."""
        h = CompoundSpellingHandler()
        assert not h.can_apply([_tok(word, pos="NOUN")], 0)

    @pytest.mark.parametrize(
        "fragment", ["военно-", "-полевой", "-", "70-", "-этажный"]
    )
    def test_dash_fragments_never_corrupted(self, fragment):
        """Regression: stanza splits hyphenated compounds into fragments
        ('военно-' + 'полевой' or 'военно' + '-' + 'полевой'); corrupting a
        bare fragment poisons both sides of the training pair."""
        h = CompoundSpellingHandler()
        tokens = [_tok(fragment, pos="ADJ")]
        sentence = [fragment]
        assert not h.can_apply(tokens, 0)
        result = h.apply(tokens, sentence, 0, set(), rng=Random(0))
        assert result is None
        assert sentence[0] == fragment


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
