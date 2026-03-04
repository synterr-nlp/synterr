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
            AnalyzedToken(text="a", lemma="a", pos="X", features={}, idx=2),  # too short
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
