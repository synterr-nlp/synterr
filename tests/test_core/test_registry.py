"""Tests for synterr language registry."""

from __future__ import annotations

import pytest

from synterr.core.registry import (
    _LANGUAGES,
    get_language,
    is_language_available,
    list_languages,
    register_language,
)


class MockLanguage:
    """Mock language for testing."""

    code = "mock"
    name = "Mock Language"

    def get_analyzer(self, use_depparse=False):
        return None

    def get_error_handlers(self):
        return []

    def get_error_distribution(self):
        return {}


class TestRegistry:
    """Tests for language registry functions."""

    def test_register_language(self):
        """Test registering a language module."""
        mock = MockLanguage()
        register_language(mock)

        assert "mock" in _LANGUAGES
        assert _LANGUAGES["mock"] is mock

    def test_get_language(self):
        """Test getting a registered language."""
        mock = MockLanguage()
        register_language(mock)

        result = get_language("mock")
        assert result is mock

    def test_get_language_not_found(self):
        """Test getting a non-existent language raises KeyError."""
        with pytest.raises(KeyError, match="Language 'nonexistent' not found"):
            get_language("nonexistent")

    def test_list_languages(self):
        """Test listing available languages."""
        mock = MockLanguage()
        register_language(mock)

        languages = list_languages()
        assert "mock" in languages
        assert languages["mock"] == "Mock Language"

    def test_is_language_available(self):
        """Test checking language availability."""
        mock = MockLanguage()
        register_language(mock)

        assert is_language_available("mock")
        assert not is_language_available("nonexistent")
