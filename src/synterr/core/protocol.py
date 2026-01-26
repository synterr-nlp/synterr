"""Core protocols and dataclasses for synterr error generation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class AnalyzedToken:
    """Language-agnostic token representation with morphological analysis.

    Attributes:
        text: Original token text
        lemma: Lemmatized form
        pos: Universal POS tag (NOUN, VERB, ADJ, etc.)
        features: Morphological features dict (case, number, gender, tense, etc.)
        idx: Token index in sentence
        dep_rel: Dependency relation label (optional, requires depparse)
        head_idx: Index of dependency head (optional, requires depparse)
        extra: Language-specific data (e.g., pymorphy3 parse object)
    """

    text: str
    lemma: str
    pos: str
    features: dict[str, str]
    idx: int = 0
    dep_rel: str | None = None
    head_idx: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def has_feature(self, key: str, value: str | None = None) -> bool:
        """Check if token has a morphological feature.

        Args:
            key: Feature name (e.g., "Case", "Number")
            value: Optional value to match (e.g., "Nom", "Sing")

        Returns:
            True if feature exists (and matches value if provided)
        """
        if key not in self.features:
            return False
        if value is None:
            return True
        return self.features[key] == value

    def get_feature(self, key: str, default: str | None = None) -> str | None:
        """Get morphological feature value."""
        return self.features.get(key, default)


@dataclass
class ErrorResult:
    """Result of applying an error to a token or span.

    Attributes:
        error_type: Specific error identifier (e.g., "noun_case", "spelling_vowel")
        category: Detection category (SPELL, MORPH, PUNCT, OTHER)
        start_idx: Start token index (inclusive)
        end_idx: End token index (exclusive). For single-token errors, end_idx = start_idx + 1.
            Multi-token spans are reserved for future M2 format support.
        original: Original text
        corrupted: Corrupted text
        fix_tag: GECToR correction tag (e.g., "$REPLACE_word", "$TRANSFORM_CASE_Nom")

    Note:
        Currently _format_output() only uses start_idx for GECToR output (token-by-token format).
        Handlers should still set end_idx correctly for future span-aware output formats (M2).
        For multi-token errors, GECToR output decomposes the span into per-token tags.
    """

    error_type: str
    category: str
    start_idx: int
    end_idx: int
    original: str
    corrupted: str
    fix_tag: str


@runtime_checkable
class ErrorHandler(Protocol):
    """Protocol for error handlers.

    Each error handler is responsible for a specific type of error
    (e.g., noun case, spelling, verb tense). Handlers are registered
    with language modules and called by the pipeline.

    Handlers declare their subtypes - fine-grained error types that
    can be mapped to schema tags. For example, SpellingErrorHandler
    has subtypes like 'vowel_reduction', 'keyboard', etc.
    """

    @property
    def name(self) -> str:
        """Error type identifier (e.g., 'noun_case', 'spelling')."""
        ...

    @property
    def subtypes(self) -> list[str]:
        """Fine-grained error subtypes this handler can produce.

        Examples:
            - SpellingHandler: ['vowel_reduction', 'keyboard', 'tsa_confusion', ...]
            - NounCaseHandler: ['noun_case']  # single subtype = handler name

        These subtypes are mapped to schema tags in the schema YAML.
        """
        ...

    @property
    def category(self) -> str:
        """Detection category: SPELL, MORPH, PUNCT, or OTHER.

        Note: When using schemas, the detection category comes from the
        schema mapping, not this property. This is kept for backward
        compatibility and as a fallback.
        """
        ...

    @property
    def changes_length(self) -> bool:
        """Whether this error can add/remove tokens.

        Length-changing errors (insert/delete) are applied last
        to avoid index corruption.
        """
        ...

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if error can be applied at token index.

        Args:
            tokens: Analyzed tokens in sentence
            idx: Token index to check

        Returns:
            True if error can be applied at this position
        """
        ...

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: random.Random | None = None,
    ) -> ErrorResult | None:
        """Apply error and return result.

        Args:
            tokens: Analyzed tokens (for morphological info)
            sentence: Mutable sentence token list (to modify)
            idx: Token index to corrupt
            modified: Set of already-modified indices (to avoid double corruption)
            rng: Random number generator for reproducibility. If None, uses
                 global random module (not recommended for reproducible results).

        Returns:
            ErrorResult with details, or None if error couldn't be applied
        """
        ...


@runtime_checkable
class Analyzer(Protocol):
    """Protocol for language-specific text analyzers."""

    def analyze(self, text: str) -> list[AnalyzedToken]:
        """Analyze a single sentence.

        Args:
            text: Input sentence text

        Returns:
            List of analyzed tokens
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


@runtime_checkable
class LanguageModule(Protocol):
    """Protocol for language support modules.

    Language modules are discovered via entry points and provide
    language-specific analyzers and error handlers.
    """

    @property
    def code(self) -> str:
        """ISO 639-1 language code (e.g., 'ru', 'en')."""
        ...

    @property
    def name(self) -> str:
        """Human-readable language name (e.g., 'Russian', 'English')."""
        ...

    def get_analyzer(self, use_depparse: bool = False) -> Analyzer:
        """Get language-specific analyzer.

        Args:
            use_depparse: Enable dependency parsing (slower but needed for
                         agreement errors)

        Returns:
            Configured analyzer instance
        """
        ...

    def get_error_handlers(self) -> list[ErrorHandler]:
        """Get all registered error handlers for this language."""
        ...

    def get_error_distribution(self) -> dict[str, float]:
        """Get default error type weights.

        Returns:
            Dict mapping error handler names to sampling weights
        """
        ...
