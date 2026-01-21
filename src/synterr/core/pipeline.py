"""Error generation pipeline for synterr."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken, ErrorResult
from synterr.core.registry import get_language

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from synterr.core.protocol import Analyzer, ErrorHandler, LanguageModule

# Output format constants
TOKEN_SEP = "SEPL|||SEPR"
SENTENCE_START = "$START"

# Detection categories
CATEGORY_CORRECT = "CORRECT"
CATEGORY_SPELL = "SPELL"
CATEGORY_MORPH = "MORPH"
CATEGORY_PUNCT = "PUNCT"
CATEGORY_OTHER = "OTHER"


@dataclass
class GenerationConfig:
    """Configuration for error generation.

    Attributes:
        seed: Random seed for reproducibility
        max_errors_per_sentence: Maximum errors to introduce per sentence
        error_probability: Probability of introducing an error in eligible sentences
        use_depparse: Enable dependency parsing for agreement errors
        label_format: Output label format ('original', 'binary', 'multiclass')
        enabled_errors: Set of error handler names to use (None = all)
        error_weights: Custom weights for error types (overrides language default)
        backend: NLP backend to use (None = language default)
    """

    seed: int = 42
    max_errors_per_sentence: int = 3
    error_probability: float = 0.7
    use_depparse: bool = False
    label_format: str = "multiclass"
    enabled_errors: set[str] | None = None
    error_weights: dict[str, float] | None = None
    backend: str | None = None

    @classmethod
    def from_preset(cls, language: str, preset: str, **overrides) -> GenerationConfig:
        """Create config from a preset.

        Args:
            language: Language code (e.g., 'ru')
            preset: Preset name (e.g., 'rulec', 'gera', 'balanced')
            **overrides: Override specific config values

        Returns:
            GenerationConfig instance
        """
        from synterr.configs import load_preset

        config_data = load_preset(language, preset)
        return cls._from_dict(config_data, **overrides)

    @classmethod
    def from_file(cls, path: str, **overrides) -> GenerationConfig:
        """Create config from a YAML file.

        Args:
            path: Path to YAML config file
            **overrides: Override specific config values

        Returns:
            GenerationConfig instance
        """
        from synterr.configs import load_config

        config_data = load_config(path)
        return cls._from_dict(config_data, **overrides)

    @classmethod
    def _from_dict(cls, data: dict, **overrides) -> GenerationConfig:
        """Create config from dict."""
        config = cls(
            seed=data.get("seed", 42),
            max_errors_per_sentence=data.get("max_errors_per_sentence", 3),
            error_probability=data.get("error_probability", 0.7),
            use_depparse=data.get("use_depparse", False),
            label_format=data.get("label_format", "multiclass"),
            error_weights=data.get("weights"),
            backend=data.get("backend"),
        )

        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config


@dataclass
class GeneratedSentence:
    """Result of error generation for a single sentence.

    Attributes:
        original_tokens: Original sentence tokens
        corrupted_tokens: Tokens after error application
        errors: List of applied errors
        formatted: Formatted output string (GECToR format)
    """

    original_tokens: list[str]
    corrupted_tokens: list[str]
    errors: list[ErrorResult]
    formatted: str = ""


class ErrorPipeline:
    """Pipeline for generating synthetic errors in text."""

    def __init__(
        self,
        language: LanguageModule | str,
        config: GenerationConfig | None = None,
    ) -> None:
        """Initialize the error pipeline.

        Args:
            language: Language module instance or language code
            config: Generation configuration (uses defaults if None)
        """
        if isinstance(language, str):
            language = get_language(language)

        self.language = language
        self.config = config or GenerationConfig()
        self._analyzer: Analyzer | None = None
        self._handlers: list[ErrorHandler] | None = None
        self._distribution: dict[str, float] | None = None
        self._rng = random.Random(self.config.seed)

    @property
    def analyzer(self) -> Analyzer:
        """Get or create analyzer (lazy initialization)."""
        if self._analyzer is None:
            self._analyzer = self.language.get_analyzer(
                use_depparse=self.config.use_depparse,
                backend=self.config.backend,
            )
        return self._analyzer

    @property
    def handlers(self) -> list[ErrorHandler]:
        """Get filtered error handlers."""
        if self._handlers is None:
            all_handlers = self.language.get_error_handlers()
            if self.config.enabled_errors is not None:
                self._handlers = [h for h in all_handlers if h.name in self.config.enabled_errors]
            else:
                self._handlers = all_handlers
        return self._handlers

    @property
    def distribution(self) -> dict[str, float]:
        """Get error distribution weights.

        Priority: config.error_weights > language default
        """
        if self._distribution is None:
            # Use config weights if provided, otherwise language default
            if self.config.error_weights is not None:
                dist = self.config.error_weights.copy()
            else:
                dist = self.language.get_error_distribution()

            # Filter to enabled errors if specified
            if self.config.enabled_errors is not None:
                dist = {k: v for k, v in dist.items() if k in self.config.enabled_errors}

            self._distribution = dist
        return self._distribution

    def _sample_error_type(self) -> ErrorHandler | None:
        """Sample an error type according to distribution."""
        handler_map = {h.name: h for h in self.handlers}
        available = [name for name in self.distribution if name in handler_map]

        if not available:
            return None

        weights = [self.distribution[name] for name in available]
        chosen = self._rng.choices(available, weights=weights, k=1)[0]
        return handler_map[chosen]

    def _find_applicable_indices(
        self,
        handler: ErrorHandler,
        tokens: Sequence[AnalyzedToken],
        modified: set[int],
    ) -> list[int]:
        """Find token indices where handler can be applied."""
        return [i for i in range(len(tokens)) if i not in modified and handler.can_apply(tokens, i)]

    def _format_output(
        self,
        corrupted: list[str],
        errors: list[ErrorResult],
    ) -> str:
        """Format corrupted sentence with GECToR tags.

        Args:
            corrupted: Corrupted token list
            errors: Applied errors

        Returns:
            Formatted string with tags
        """
        # Build error lookup by position
        error_at: dict[int, ErrorResult] = {}
        for err in errors:
            error_at[err.start_idx] = err

        # Build output tokens
        parts = [SENTENCE_START]

        for i, token in enumerate(corrupted):
            if i in error_at:
                err = error_at[i]
                tag = err.fix_tag
                category = self._get_category_label(err.category)
            else:
                tag = "$KEEP"
                category = CATEGORY_CORRECT

            # Format based on label_format
            if self.config.label_format == "binary":
                label = CATEGORY_CORRECT if category == CATEGORY_CORRECT else "INCORRECT"
                parts.append(f"{tag}:{label} {token}")
            elif self.config.label_format == "multiclass":
                parts.append(f"{tag}:{category} {token}")
            else:  # original
                parts.append(f"{tag} {token}")

        return TOKEN_SEP.join(parts)

    def _get_category_label(self, category: str) -> str:
        """Normalize category label."""
        category_upper = category.upper()
        if category_upper in (CATEGORY_SPELL, CATEGORY_MORPH, CATEGORY_PUNCT, CATEGORY_OTHER):
            return category_upper
        return CATEGORY_OTHER

    def generate(self, text: str) -> GeneratedSentence:
        """Generate errors for a single sentence.

        Args:
            text: Input sentence text

        Returns:
            GeneratedSentence with corrupted tokens and errors
        """
        # Analyze sentence
        tokens = self.analyzer.analyze(text)

        if not tokens:
            return GeneratedSentence(
                original_tokens=[],
                corrupted_tokens=[],
                errors=[],
                formatted="",
            )

        # Prepare mutable sentence
        original = [t.text for t in tokens]
        sentence = original.copy()
        modified: set[int] = set()
        errors: list[ErrorResult] = []

        # Decide whether to introduce errors
        if self._rng.random() > self.config.error_probability:
            # No errors - return clean sentence
            formatted = self._format_output(sentence, [])
            return GeneratedSentence(
                original_tokens=original,
                corrupted_tokens=sentence,
                errors=[],
                formatted=formatted,
            )

        # Separate length-changing handlers (applied last to avoid index corruption)
        length_handlers = [h for h in self.handlers if h.changes_length]

        # Apply regular errors first (don't change indices)
        num_errors = self._rng.randint(1, self.config.max_errors_per_sentence)

        for _ in range(num_errors):
            if len(modified) >= len(tokens):
                break

            handler = self._sample_error_type()
            if handler is None or handler.changes_length:
                continue

            applicable = self._find_applicable_indices(handler, tokens, modified)
            if not applicable:
                continue

            idx = self._rng.choice(applicable)
            result = handler.apply(tokens, sentence, idx, modified)

            if result is not None:
                errors.append(result)
                modified.add(idx)

        # Apply length-changing errors last (if any)
        # Note: For simplicity, we only apply one length-changing error per sentence
        if length_handlers and self._rng.random() < 0.3:
            handler = self._rng.choice(length_handlers)
            applicable = self._find_applicable_indices(handler, tokens, modified)
            if applicable:
                idx = self._rng.choice(applicable)
                result = handler.apply(tokens, sentence, idx, modified)
                if result is not None:
                    errors.append(result)

        # Format output
        formatted = self._format_output(sentence, errors)

        return GeneratedSentence(
            original_tokens=original,
            corrupted_tokens=sentence,
            errors=errors,
            formatted=formatted,
        )

    def generate_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 100,
    ) -> Iterator[GeneratedSentence]:
        """Generate errors for multiple sentences.

        Uses batched analysis for efficiency.

        Args:
            texts: Input sentence texts
            batch_size: Number of sentences to analyze together

        Yields:
            GeneratedSentence for each input
        """
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            token_batches = self.analyzer.analyze_batch(batch)

            for _text, tokens in zip(batch, token_batches, strict=False):
                if not tokens:
                    yield GeneratedSentence(
                        original_tokens=[],
                        corrupted_tokens=[],
                        errors=[],
                        formatted="",
                    )
                    continue

                # Process similar to single sentence
                original = [t.text for t in tokens]
                sentence = original.copy()
                modified: set[int] = set()
                errors: list[ErrorResult] = []

                if self._rng.random() <= self.config.error_probability:
                    num_errors = self._rng.randint(1, self.config.max_errors_per_sentence)

                    for _ in range(num_errors):
                        if len(modified) >= len(tokens):
                            break

                        handler = self._sample_error_type()
                        if handler is None or handler.changes_length:
                            continue

                        applicable = self._find_applicable_indices(handler, tokens, modified)
                        if not applicable:
                            continue

                        idx = self._rng.choice(applicable)
                        result = handler.apply(tokens, sentence, idx, modified)

                        if result is not None:
                            errors.append(result)
                            modified.add(idx)

                formatted = self._format_output(sentence, errors)

                yield GeneratedSentence(
                    original_tokens=original,
                    corrupted_tokens=sentence,
                    errors=errors,
                    formatted=formatted,
                )
