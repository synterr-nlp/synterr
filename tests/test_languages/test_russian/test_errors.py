"""Tests for Russian error handlers."""

from __future__ import annotations

from synterr.core.protocol import ErrorHandler


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
        assert "paronym" in names
        assert "preposition" in names
        assert "conjunction" in names
        assert "word_omission" in names
        assert "word_insertion" in names
