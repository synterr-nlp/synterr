from __future__ import annotations

from synterr.core.protocol import AnalyzedToken, ErrorHandler


class TestSpellingErrorHandler:
    """Tests for Russian spelling error handler."""

    def test_implements_protocol(self):
        """Test that handler implements ErrorHandler protocol."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "spelling"
        assert handler.category == "SPELL"
        assert handler.changes_length is False

    def test_can_apply(self):
        """Test can_apply checks for alphabetic tokens."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        tokens = [
            AnalyzedToken(text="книга", lemma="книга", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="a", lemma="a", pos="X", features={}, idx=2
            ),  # too short
        ]

        assert handler.can_apply(tokens, 0) is True  # alphabetic, len >= 2
        assert handler.can_apply(tokens, 1) is False  # not alphabetic
        assert handler.can_apply(tokens, 2) is False  # too short

    def test_tsa_confusion(self):
        """Test тся/ться confusion errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        # Test ться → тся
        result = handler._tsa_confusion("учиться")
        assert result is not None
        assert result.corrupted == "учится"
        assert result.error_subtype == "tsa_confusion"

        # Test тся → ться
        result = handler._tsa_confusion("учится")
        assert result is not None
        assert result.corrupted == "учиться"

    def test_vowel_reduction(self):
        """Test vowel reduction errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._vowel_reduction("молоко")
        assert result is not None
        # Should change о to а or е to и
        assert result.corrupted != "молоко"
        assert result.error_subtype == "vowel_reduction"

    def test_keyboard_typo(self):
        """Test keyboard typo errors."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        result = handler._keyboard_typo("книга")
        assert result is not None
        assert result.corrupted != "книга"
        assert len(result.corrupted) == len("книга")
        assert result.error_subtype == "keyboard"

    def test_prefix_voicing_skips_root_initial(self):
        """Root-initial из/ис/раз/... is not a prefix — no swap (§31 прим. 1).

        Regression: prefix_voicing used to produce non-words like *изтории,
        *разти, *восле by matching any word starting with a prefix string.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        root_initial = [
            ("искра", "искра"),
            ("история", "история"),
            ("истории", "история"),  # inflected → lemma fallback
            ("испанский", "испанский"),
            ("расти", "расти"),
            ("растения", "растение"),
            ("возле", "возле"),
            ("изюм", "изюм"),
            ("низина", "низина"),
            ("воск", "воск"),
        ]
        for word, lemma in root_initial:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_skips_unknown_words(self):
        """OOV words (not in morpheme dict) are skipped — can't verify prefix."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        assert handler._prefix_voicing("изквронт") is None

    def test_prefix_voicing_real_prefixes(self):
        """Genuine з-/с- prefixes still get the wrong-form swap."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("исправить", "исправить", "изправить"),
            ("разбить", "разбить", "расбить"),
            ("бесполезный", "бесполезный", "безполезный"),
            ("расписание", "расписание", "разписание"),
            ("разбили", "разбить", "расбили"),  # inflected → lemma fallback
        ]
        for word, lemma, expected in cases:
            result = handler._prefix_voicing(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "prefix_voicing"

    def test_prefix_voicing_skips_before_vowel_and_hard_sign(self):
        """No з→с swap before vowels or ъ — voiced form is categorical there (§31).

        Regression: prefix_voicing used to produce *расузнать / *расъезд,
        modeling a devoicing that never happens before vowels.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("разузнать", "разузнать"),  # раз- is PREF, next char у (vowel)
            ("разъезд", "разъезд"),  # next char ъ
            ("разахаться", "разахаться"),  # next char а (vowel)
        ]
        for word, lemma in cases:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_vz_vs_pair(self):
        """§31 lists воз-(вз-): the вз-/вс- pair generates errors too."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("вспомнить", "вспомнить", "взпомнить"),
            ("взлететь", "взлететь", "вслететь"),
        ]
        for word, lemma, expected in cases:
            result = handler._prefix_voicing(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected

        # вс/вз at the start of unprefixed words is not touched
        for word, lemma in [("всегда", "всегда"), ("вселенная", "вселенная")]:
            assert handler._prefix_voicing(word, lemma=lemma) is None, word

    def test_prefix_voicing_cheres_maps_to_cherez(self):
        """черес- swaps to modern через- (черезчур), never archaic чрез-."""
        from synterr.languages.russian.errors.spelling import (
            PREFIX_VOICELESS_TO_VOICED,
        )

        assert PREFIX_VOICELESS_TO_VOICED["черес"] == "через"

    def test_cluster_skips_word_initial_ssh(self):
        """Word-initial сш is prefix с- + root (§32) — deleting с yields a real
        verb of different aspect (сшить → шить), a non-error.

        Regression: cluster turned 'Она решила сшить платье' into perfectly
        grammatical 'Она решила шить платье'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._cluster("сшить") is None
        assert handler._cluster("сшил") is None
        assert handler._cluster("Сшить") is None

        # Word-internal сш still produces a non-word error
        result = handler._cluster("высший")
        assert result is not None
        assert result.corrupted == "выший"

    def test_cluster_rejects_real_word_results(self):
        """Cluster output that is itself a known word is a non-error: костный
        → косный ('inert') would be a grammatical substitution."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        assert handler._cluster("костный") is None
        # Normal cases still fire (results are non-words)
        assert handler._cluster("счастье").corrupted == "щастье"
        assert handler._cluster("честный").corrupted == "чесный"

    def test_soft_sign_rejects_real_word_results(self):
        """ь deletion must not yield a known word — мать→мат, быть→быт etc.
        are grammatical sentences, not errors.

        Regression: 'Мать всегда поможет' became 'Мат всегда поможет'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["мать", "быть", "весь", "есть", "уголь", "пыль", "ель"]:
            assert handler._soft_sign(word) is None, word

        # учиться→учится is a known word AND would duplicate tsa_confusion
        assert handler._soft_sign("учиться") is None

    def test_soft_sign_still_fires_on_nonword_results(self):
        """Genuine ь omissions (results are non-words) still generate."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("помощь", "помощ"),
            ("делаешь", "делаеш"),
            ("только", "толко"),
            ("письмо", "писмо"),
            ("подъезд", "подьезд"),  # ъ→ь branch
        ]
        for word, expected in cases:
            result = handler._soft_sign(word)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "soft_sign"

    def test_double_consonant_skips_suffix_nn(self):
        """Suffix -нн- (participles/adjectives) is §52 territory, owned by
        orthographic_spelling:nn_suffix — double_consonant (mapped to root
        doubles, §9) must not fire on it.

        Regression: 'Сделанная работа' → 'Сделаная работа' tagged as a root
        double.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        suffix_nn = [
            ("сделанная", "сделанный"),
            ("длинный", "длинный"),
            ("осенний", "осенний"),
        ]
        for word, lemma in suffix_nn:
            assert handler._double_consonant(word, lemma=lemma) is None, word

    def test_double_consonant_root_doubles_still_fire(self):
        """Root-internal doubles (§9) keep generating: ванна, аппарат, коллега."""
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        cases = [
            ("ванна", "ванна", "вана"),  # root-internal нн
            ("ванну", "ванна", "вану"),  # inflected → lemma fallback
            ("аппарат", "аппарат", "апарат"),
            ("коллега", "коллега", "колега"),
        ]
        for word, lemma, expected in cases:
            result = handler._double_consonant(word, lemma=lemma)
            assert result is not None, word
            assert result.corrupted == expected
            assert result.error_subtype == "double_consonant"

    def test_vowel_reduction_skips_stress_homographs(self):
        """Stress homographs (замо́к/за́мок) have one stress-dict reading; the
        other reading's STRESSED vowel would be corrupted, violating §1
        (reduction is unstressed-only).

        Regression: 'Тяжёлый замок висел на двери' → 'замак'.
        """
        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()

        for word in ["замок", "Замок", "мука", "орган", "дорогой", "хлопок"]:
            assert handler._vowel_reduction(word) is None, word

        # Unambiguous words still reduce
        assert handler._vowel_reduction("молоко") is not None

    def test_corrupt_first_draw_respects_weights(self):
        """The first sampled subtype is a true weighted draw, so when all
        enabled subtypes apply, emission fractions track configured weights.

        Regression: the old weighted shuffle gave keyboard ~0.17 instead of
        the configured 0.25 in this setup (fallback reshaping distribution).
        """
        from random import Random

        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        handler.set_enabled_subtypes({"tsa_confusion", "keyboard"})
        handler.set_subtype_weights({"tsa_confusion": 75, "keyboard": 25})

        rng = Random(42)
        n = 600
        counts = {"tsa_confusion": 0, "keyboard": 0}
        # Both subtypes always apply to "учится", so no fallback occurs and
        # emission == first draw.
        for _ in range(n):
            result = handler._corrupt("учится", rng)
            counts[result.error_subtype] += 1

        keyboard_frac = counts["keyboard"] / n
        assert 0.21 < keyboard_frac < 0.29, counts

    def test_corrupt_falls_back_when_first_draw_inapplicable(self):
        """If the drawn subtype can't apply, remaining methods still cascade."""
        from random import Random

        from synterr.languages.russian.errors.spelling import SpellingErrorHandler

        handler = SpellingErrorHandler()
        # vowel_reduction can never apply to an OOV word (no stress entry);
        # keyboard always can.
        handler.set_enabled_subtypes({"vowel_reduction", "keyboard"})
        handler.set_subtype_weights({"vowel_reduction": 99, "keyboard": 1})

        rng = Random(7)
        for _ in range(20):
            result = handler._corrupt("брзкворт", rng)
            assert result is not None
            assert result.error_subtype == "keyboard"
