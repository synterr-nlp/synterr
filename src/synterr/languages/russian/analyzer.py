"""Russian language analyzer with pluggable backends.

Available backends:
    - stanza: Best accuracy, slower (~92 sent/s)
    - natasha: Fastest (~500 sent/s), lightweight
    - spacy: Balanced, good depparse

Usage:
    from synterr.languages.russian.analyzer import RussianAnalyzer

    # Default backend (stanza)
    analyzer = RussianAnalyzer()

    # Specific backend
    analyzer = RussianAnalyzer(backend="natasha")

    # Analyze
    tokens = analyzer.analyze("Мама мыла раму.")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synterr.core.protocol import AnalyzedToken
    from synterr.languages.russian.backends.base import AnalyzerBackend


class RussianAnalyzer:
    """Russian text analyzer with pluggable NLP backends.

    Supports multiple backends for morphological analysis:
    - stanza: Stanford NLP (default, best accuracy)
    - natasha: Natasha/Slovnet (fastest, lightweight)
    - spacy: spaCy with Russian models (balanced)

    All backends use pymorphy3 for inflection capabilities.
    """

    def __init__(
        self,
        backend: str | None = None,
        use_depparse: bool = False,
        use_gpu: bool = True,
    ) -> None:
        """Initialize Russian analyzer.

        Args:
            backend: Backend name ('stanza', 'natasha', 'spacy') or None for default
            use_depparse: Enable dependency parsing
            use_gpu: Use GPU acceleration (if supported by backend)
        """
        self.backend_name = backend
        self.use_depparse = use_depparse
        self.use_gpu = use_gpu
        self._backend: AnalyzerBackend | None = None

    @property
    def backend(self) -> AnalyzerBackend:
        """Get or create backend (lazy initialization)."""
        if self._backend is None:
            from synterr.languages.russian.backends import get_backend

            self._backend = get_backend(
                name=self.backend_name,
                use_depparse=self.use_depparse,
                use_gpu=self.use_gpu,
            )
        return self._backend

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence.

        Args:
            text: Input sentence text

        Returns:
            List of analyzed tokens with POS, lemma, features
        """
        return self.backend.analyze(text)

    def analyze_batch(self, texts: Sequence[str]) -> list[list[AnalyzedToken]]:
        """Analyze multiple sentences.

        Efficiency depends on backend - stanza has native batching (~7x speedup).

        Args:
            texts: List of sentence texts

        Returns:
            List of token lists, one per sentence
        """
        return self.backend.analyze_batch(texts)
