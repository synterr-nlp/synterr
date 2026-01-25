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
    from synterr.schemas import Schema

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
        schema: Linguistic schema name or path (e.g., 'synterr', 'rlc')
    """

    seed: int = 42
    max_errors_per_sentence: int = 3
    error_probability: float = 0.7
    use_depparse: bool = False
    label_format: str = "multiclass"
    enabled_errors: set[str] | None = None
    error_weights: dict[str, float] | None = None
    backend: str | None = None
    schema: str | None = None

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
            schema=data.get("schema"),
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

    def to_tsv(self) -> str:
        """Format as parallel TSV (src<TAB>tgt) for seq2seq training.

        Returns:
            Tab-separated original and corrupted sentences
        """
        original = " ".join(self.original_tokens)
        corrupted = " ".join(self.corrupted_tokens)
        return f"{original}\t{corrupted}"

    def to_jsonl(
        self,
        id: str | None = None,
        seed: int | None = None,
        backend: str | None = None,
        schema: str | None = None,
    ) -> str:
        """Format as rich JSONL for reproducibility and filtering.

        Args:
            id: Optional unique identifier for this example
            seed: Random seed used for generation
            backend: NLP backend used (stanza, natasha, spacy)
            schema: Schema name used (rlc, synterr, etc.)

        Returns:
            JSON string (single line, no trailing newline)
        """
        import json

        record: dict = {
            "original": " ".join(self.original_tokens),
            "corrupted": " ".join(self.corrupted_tokens),
            "errors": [
                {
                    "type": err.error_type,
                    "category": err.category,
                    "start_idx": err.start_idx,
                    "end_idx": err.end_idx,
                    "original": err.original,
                    "corrupted": err.corrupted,
                    "fix_tag": err.fix_tag,
                }
                for err in self.errors
            ],
        }

        if id is not None:
            record["id"] = id
        if seed is not None:
            record["seed"] = seed
        if backend is not None:
            record["backend"] = backend
        if schema is not None:
            record["schema"] = schema

        return json.dumps(record, ensure_ascii=False)

    def to_diff(self, use_color: bool = False) -> str:
        """Format as human-readable diff for spot-checking.

        Shows deletions as [-text-] and insertions as {+text+}.
        Optionally uses ANSI colors (red for deletions, green for insertions).

        Args:
            use_color: Use ANSI escape codes for terminal colors

        Returns:
            Diff-formatted string
        """
        if use_color:
            del_start, del_end = "\033[91m", "\033[0m"  # Red
            ins_start, ins_end = "\033[92m", "\033[0m"  # Green
        else:
            del_start, del_end = "[-", "-]"
            ins_start, ins_end = "{+", "+}"

        # Build error lookup
        error_at: dict[int, ErrorResult] = {}
        for err in self.errors:
            error_at[err.start_idx] = err

        parts = []
        for i, token in enumerate(self.corrupted_tokens):
            if i in error_at:
                err = error_at[i]
                if err.original != err.corrupted:
                    parts.append(f"{del_start}{err.original}{del_end}{ins_start}{err.corrupted}{ins_end}")
                else:
                    parts.append(token)
            else:
                parts.append(token)

        return " ".join(parts)


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
        self._schema: Schema | None = None
        self._rng = random.Random(self.config.seed)

    @property
    def schema(self) -> Schema | None:
        """Get loaded schema (lazy initialization)."""
        if self._schema is None and self.config.schema is not None:
            from synterr.schemas import load_schema

            self._schema = load_schema(self.config.schema)
        return self._schema

    def get_available_subtypes(self) -> set[str]:
        """Get all subtypes available from registered handlers."""
        subtypes = set()
        for handler in self.handlers:
            subtypes.update(handler.subtypes)
        return subtypes

    def get_schema_coverage(self) -> dict | None:
        """Get schema coverage report if schema is loaded."""
        if self.schema is None:
            return None
        return self.schema.get_coverage_report(self.get_available_subtypes())

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

    def _adjust_indices_for_length_change(
        self,
        errors: list[ErrorResult],
        change_idx: int,
        delta: int,
    ) -> list[ErrorResult]:
        """Adjust error indices after a length-changing operation.

        When a token is inserted or deleted, all errors at or after that
        position need their indices shifted.

        Args:
            errors: List of errors to adjust
            change_idx: Index where the length change occurred
            delta: Change in length (+1 for insertion, -1 for deletion)

        Returns:
            New list of ErrorResults with adjusted indices
        """
        adjusted = []
        for err in errors:
            if err.start_idx >= change_idx:
                adjusted.append(
                    ErrorResult(
                        error_type=err.error_type,
                        category=err.category,
                        start_idx=err.start_idx + delta,
                        end_idx=err.end_idx + delta,
                        original=err.original,
                        corrupted=err.corrupted,
                        fix_tag=err.fix_tag,
                    )
                )
            else:
                adjusted.append(err)
        return adjusted

    def _get_length_change_info(
        self,
        result: ErrorResult,
        handler_idx: int,
    ) -> tuple[int, int]:
        """Determine change_idx and delta from a length-changing error.

        Args:
            result: The ErrorResult from a length-changing handler
            handler_idx: The token index where the handler was applied

        Returns:
            (change_idx, delta) where delta is +1 for insertion, -1 for deletion.
            Returns (0, 0) if the change type cannot be determined.
        """
        # Deletion (word_omission): creates $APPEND_x tag to restore the word
        if result.fix_tag.startswith("$APPEND_"):
            return (handler_idx, -1)

        # Insertion (word_insertion): creates $DELETE tag to remove the word
        if result.fix_tag == "$DELETE":
            return (handler_idx + 1, +1)

        return (0, 0)  # Unknown — no adjustment

    def _apply_errors_to_sentence(
        self,
        tokens: Sequence[AnalyzedToken],
        original: list[str],
    ) -> tuple[list[str], list[ErrorResult]]:
        """Apply errors to a sentence following the generation rules.

        This is the shared logic for both generate() and generate_batch().
        It applies non-length-changing errors first, then optionally one
        length-changing error, adjusting prior error indices as needed.

        Args:
            tokens: Analyzed tokens from the sentence
            original: Original token texts

        Returns:
            (corrupted_sentence, errors) tuple
        """
        sentence = original.copy()
        modified: set[int] = set()
        errors: list[ErrorResult] = []

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
            result = handler.apply(tokens, sentence, idx, modified, rng=self._rng)

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
                result = handler.apply(tokens, sentence, idx, modified, rng=self._rng)
                if result is not None:
                    # Adjust prior error indices for the length change
                    change_idx, delta = self._get_length_change_info(result, idx)
                    if delta != 0:
                        errors = self._adjust_indices_for_length_change(
                            errors, change_idx, delta
                        )
                    errors.append(result)

        return sentence, errors

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
                category = self._get_category_label(err.category, err.error_type)
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

    def _get_category_label(self, category: str, error_type: str | None = None) -> str:
        """Get detection category label.

        If a schema is loaded, uses the schema's detection category for the
        error subtype. Otherwise, uses the handler's category.

        Args:
            category: Handler's default category
            error_type: Error type string (e.g., "spelling_vowel_reduction", "noun_case")

        Returns:
            Detection category (SPELL, MORPH, PUNCT, OTHER)
        """
        # If schema is loaded, try to get category from schema
        if self.schema is not None and error_type is not None:
            # Extract subtype from error_type
            # For spelling: "spelling_vowel_reduction" -> "vowel_reduction"
            # For morphological: "noun_case" -> "noun_case"
            if error_type.startswith("spelling_"):
                subtype = error_type[9:]  # Remove "spelling_" prefix
            else:
                subtype = error_type

            schema_category = self.schema.get_detection_category(subtype)
            if schema_category != "OTHER" or subtype in self.schema.mappings:
                return schema_category

        # Fall back to handler's category
        category_upper = category.upper()
        if category_upper in (CATEGORY_SPELL, CATEGORY_MORPH, CATEGORY_PUNCT, CATEGORY_OTHER):
            return category_upper
        return CATEGORY_OTHER

    def get_handler(self, error_type: str) -> ErrorHandler | None:
        """Get handler by name or schema tag.

        Args:
            error_type: Handler name ('noun_case') or schema tag ('Gov')

        Returns:
            ErrorHandler or None if not found
        """
        # Try direct handler name match
        for handler in self.handlers:
            if handler.name == error_type:
                return handler

        # Try schema tag → subtype → handler mapping
        if self.schema is not None:
            mapping = self.schema.get_mapping(error_type)
            if mapping:
                # error_type is a subtype, find handler with this subtype
                for handler in self.handlers:
                    if error_type in handler.subtypes:
                        return handler

            # Try reverse lookup: schema tag → subtype → handler
            for subtype, m in self.schema.mappings.items():
                if m.primary == error_type:
                    for handler in self.handlers:
                        if subtype in handler.subtypes:
                            return handler

        return None

    def apply_error(
        self,
        text: str,
        error_type: str,
        position: int | None = None,
    ) -> GeneratedSentence | None:
        """Apply a specific error type to a sentence.

        Unlike generate(), this applies exactly one error of the specified type.
        Useful for tagged corruption (à la C4_200M).

        Args:
            text: Input sentence text
            error_type: Handler name ('spelling', 'noun_case') or schema tag ('Gov', 'Ortho')
            position: Optional token index to apply error at (random if None)

        Returns:
            GeneratedSentence with the error applied, or None if error cannot be applied
        """
        handler = self.get_handler(error_type)
        if handler is None:
            return None

        tokens = self.analyzer.analyze(text)
        if not tokens:
            return None

        # Find applicable positions
        applicable = self._find_applicable_indices(handler, tokens, set())
        if not applicable:
            return None

        # Choose position
        if position is not None:
            if position not in applicable:
                return None
            idx = position
        else:
            idx = self._rng.choice(applicable)

        # Apply error
        original = [t.text for t in tokens]
        sentence = original.copy()
        modified: set[int] = set()

        result = handler.apply(tokens, sentence, idx, modified, rng=self._rng)
        if result is None:
            return None

        errors = [result]
        formatted = self._format_output(sentence, errors)

        return GeneratedSentence(
            original_tokens=original,
            corrupted_tokens=sentence,
            errors=errors,
            formatted=formatted,
        )

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

        # Prepare original tokens
        original = [t.text for t in tokens]

        # Decide whether to introduce errors
        if self._rng.random() > self.config.error_probability:
            # No errors - return clean sentence
            formatted = self._format_output(original, [])
            return GeneratedSentence(
                original_tokens=original,
                corrupted_tokens=original.copy(),
                errors=[],
                formatted=formatted,
            )

        # Apply errors using shared helper
        sentence, errors = self._apply_errors_to_sentence(tokens, original)

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

                # Prepare original tokens
                original = [t.text for t in tokens]

                # Decide whether to introduce errors
                if self._rng.random() > self.config.error_probability:
                    # No errors - return clean sentence
                    formatted = self._format_output(original, [])
                    yield GeneratedSentence(
                        original_tokens=original,
                        corrupted_tokens=original.copy(),
                        errors=[],
                        formatted=formatted,
                    )
                    continue

                # Apply errors using shared helper
                sentence, errors = self._apply_errors_to_sentence(tokens, original)

                formatted = self._format_output(sentence, errors)

                yield GeneratedSentence(
                    original_tokens=original,
                    corrupted_tokens=sentence,
                    errors=errors,
                    formatted=formatted,
                )
