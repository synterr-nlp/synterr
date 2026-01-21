"""Pytest configuration and fixtures for synterr tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_russian_sentences() -> list[str]:
    """Sample Russian sentences for testing."""
    return [
        "Мама мыла раму.",
        "Книга лежит на столе.",
        "Он читает интересную книгу.",
        "Мы пойдём в парк завтра.",
        "Красивая девушка улыбнулась.",
    ]


@pytest.fixture
def sample_tokens():
    """Sample analyzed tokens for testing error handlers."""
    from synterr.core.protocol import AnalyzedToken

    # Simple sentence: "Красивый дом стоит"
    return [
        AnalyzedToken(
            text="Красивый",
            lemma="красивый",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            idx=0,
            extra={},
        ),
        AnalyzedToken(
            text="дом",
            lemma="дом",
            pos="NOUN",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="стоит",
            lemma="стоять",
            pos="VERB",
            features={"Number": "Sing", "Person": "3", "Tense": "Pres"},
            idx=2,
            extra={},
        ),
    ]
