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
