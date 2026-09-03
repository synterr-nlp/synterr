"""Pytest fixtures shared across synterr tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from unittest.mock import MagicMock

import pytest

from synterr.core.protocol import (
    AnalyzedToken,
    ErrorHandler,
    ErrorResult,
    LanguageModule,
)


@pytest.fixture
def mock_handler() -> Callable[..., ErrorHandler]:
    """Factory for a single-subtype MagicMock handler.

    ``result`` is what ``apply()`` returns (None = never fires);
    ``can_apply`` is the constant ``can_apply()`` answer.
    """

    def make(
        name: str,
        *,
        result: ErrorResult | None = None,
        changes_length: bool = False,
        can_apply: bool = True,
    ) -> ErrorHandler:
        handler = MagicMock()
        handler.name = name
        handler.subtypes = [name]
        handler.category = "OTHER"
        handler.changes_length = changes_length
        handler.can_apply.return_value = can_apply
        handler.apply.return_value = result
        return handler

    return make


@pytest.fixture
def mock_language() -> Callable[..., LanguageModule]:
    """Factory for a MagicMock language module with a whitespace analyzer.

    Every token comes back as a NOUN with no features, so pipeline tests
    can run without an NLP backend.
    """

    def analyze(text: str) -> list[AnalyzedToken]:
        return [
            AnalyzedToken(text=t, lemma=t.lower(), pos="NOUN", features={}, idx=i)
            for i, t in enumerate(text.split())
        ]

    def make(
        handlers: Iterable[ErrorHandler] = (),
        distribution: dict[str, float] | None = None,
    ) -> LanguageModule:
        analyzer = MagicMock()
        analyzer.analyze = analyze
        analyzer.analyze_batch = lambda texts: [analyze(t) for t in texts]
        lang = MagicMock()
        lang.get_analyzer.return_value = analyzer
        lang.get_error_handlers.return_value = list(handlers)
        lang.get_error_distribution.return_value = dict(distribution or {})
        return lang

    return make
