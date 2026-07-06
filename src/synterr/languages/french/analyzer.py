"""French language analyzer with pluggable backends (PoC).

Available backends:
    - stanza: `fr_sequoia` UD package (only backend in the PoC)

Usage:
    from synterr.languages.french.analyzer import FrenchAnalyzer

    # Default backend (stanza)
    analyzer = FrenchAnalyzer()

    # Analyze
    tokens = analyzer.analyze("Marie mange une pomme.")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synterr.core.protocol import AnalyzedToken
    from synterr.languages.french.backends.base import AnalyzerBackend


class FrenchAnalyzer:
    """French text analyzer with pluggable NLP backends.

    Supports the stanza `fr_sequoia` backend for morphological analysis.
    No inflection engine is attached in the PoC (`token.extra` is always
    empty) - see `synterr.languages.french.backends.stanza_fr`.
    """

    def __init__(
        self,
        backend: str | None = None,
        use_depparse: bool = False,
        use_gpu: bool = True,
    ) -> None:
        """Initialize French analyzer.

        Args:
            backend: Backend name ('stanza') or None for default
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
            from synterr.languages.french.backends import get_backend

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

        Args:
            texts: List of sentence texts

        Returns:
            List of token lists, one per sentence
        """
        return self.backend.analyze_batch(texts)
