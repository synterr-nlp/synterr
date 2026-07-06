"""Base protocol for French analyzer backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synterr.core.protocol import AnalyzedToken


@runtime_checkable
class AnalyzerBackend(Protocol):
    """Protocol for French NLP analyzer backends.

    All backends must implement this interface to be used
    with the French language module.
    """

    @property
    def name(self) -> str:
        """Backend name (e.g., 'stanza')."""
        ...

    @property
    def supports_depparse(self) -> bool:
        """Whether this backend supports dependency parsing."""
        ...

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence.

        Args:
            text: Input sentence text

        Returns:
            List of analyzed tokens with POS, lemma, features
        """
        ...

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences (more efficient).

        Args:
            texts: List of sentence texts

        Returns:
            List of token lists, one per sentence
        """
        ...
