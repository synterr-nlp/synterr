"""Tests for Russian error handlers."""

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


class TestMorphologicalErrorHandlers:
    """Tests for Russian morphological error handlers."""

    def test_noun_case_handler_protocol(self):
        """Test NounCaseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "noun_case"
        assert handler.category == "MORPH"

    def test_noun_number_handler_protocol(self):
        """Test NounNumberErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import NounNumberErrorHandler

        handler = NounNumberErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "noun_number"
        assert handler.category == "MORPH"

    def test_adj_case_handler_protocol(self):
        """Test AdjCaseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import AdjCaseErrorHandler

        handler = AdjCaseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "adj_case"

    def test_verb_tense_handler_protocol(self):
        """Test VerbTenseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import VerbTenseErrorHandler

        handler = VerbTenseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "verb_tense"

    def test_can_apply_checks_pos(self):
        """Test that handlers check correct POS tags."""
        from synterr.languages.russian.errors.morphological import (
            AdjCaseErrorHandler,
            NounCaseErrorHandler,
            VerbTenseErrorHandler,
        )

        noun_handler = NounCaseErrorHandler()
        adj_handler = AdjCaseErrorHandler()
        verb_handler = VerbTenseErrorHandler()

        # Create mock tokens
        tokens = [
            AnalyzedToken(
                text="книга",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom"},
                idx=0,
                extra={"pymorphy_parse": "mock"},
            ),
            AnalyzedToken(
                text="красивая",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Nom"},
                idx=1,
                extra={"pymorphy_parse": "mock"},
            ),
            AnalyzedToken(
                text="стоит",
                lemma="стоять",
                pos="VERB",
                features={"Tense": "Pres"},
                idx=2,
                extra={"pymorphy_parse": "mock"},
            ),
        ]

        # Noun handler should only apply to nouns
        assert noun_handler.can_apply(tokens, 0) is True
        assert noun_handler.can_apply(tokens, 1) is False
        assert noun_handler.can_apply(tokens, 2) is False

        # Adj handler should only apply to adjectives
        assert adj_handler.can_apply(tokens, 0) is False
        assert adj_handler.can_apply(tokens, 1) is True
        assert adj_handler.can_apply(tokens, 2) is False

        # Verb handler should only apply to verbs
        assert verb_handler.can_apply(tokens, 0) is False
        assert verb_handler.can_apply(tokens, 1) is False
        assert verb_handler.can_apply(tokens, 2) is True


class TestGetAllHandlers:
    """Tests for get_all_handlers function."""

    def test_returns_all_handlers(self):
        """Test that get_all_handlers returns all registered handlers."""
        from synterr.languages.russian.errors import get_all_handlers

        handlers = get_all_handlers()

        assert len(handlers) >= 8  # At least 8 handlers
        assert all(isinstance(h, ErrorHandler) for h in handlers)

        # Check all expected handlers are present
        names = {h.name for h in handlers}
        assert "spelling" in names
        assert "noun_case" in names
        assert "noun_number" in names
        assert "adj_case" in names
        assert "adj_number" in names
        assert "adj_gender" in names
        assert "verb_person_number" in names
        assert "verb_tense" in names
