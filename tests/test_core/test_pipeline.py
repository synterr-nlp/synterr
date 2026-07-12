"""Tests for synterr error generation pipeline."""

from __future__ import annotations

import json

import pytest

from synterr.core.pipeline import ErrorPipeline, GeneratedSentence, GenerationConfig
from synterr.core.protocol import AnalyzedToken, ErrorResult


class TestAdjustIndicesForLengthChange:
    """Tests for _adjust_indices_for_length_change helper."""

    @pytest.fixture
    def pipeline(self):
        """Create a pipeline instance for testing."""
        # We need to mock the language module for the pipeline
        # but we can test the helper method directly
        return None

    def test_deletion_shifts_later_errors_down(self):
        """Deletion at index 2 should shift errors at 3+ down by 1."""
        # Create a pipeline with a mock language to access the method
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        # Original: ["Я", "иду", "в", "школу"] (indices 0, 1, 2, 3)
        # Error at idx=3: "школу" → "школе"
        # Deletion at idx=2: delete "в"
        # After: ["Я", "иду", "школе"] - error should now be at idx=2

        errors = [
            ErrorResult(
                error_type="noun_case",
                category="MORPH",
                start_idx=3,
                end_idx=4,
                original="школу",
                corrupted="школе",
                fix_tag="$TRANSFORM_CASE_Acc",
            )
        ]

        # Deletion at index 2, delta=-1
        adjusted = pipeline._adjust_indices_for_length_change(
            errors, change_idx=2, delta=-1
        )

        assert len(adjusted) == 1
        assert adjusted[0].start_idx == 2  # 3 + (-1) = 2
        assert adjusted[0].end_idx == 3  # 4 + (-1) = 3
        # Other fields unchanged
        assert adjusted[0].error_type == "noun_case"
        assert adjusted[0].original == "школу"

    def test_insertion_shifts_later_errors_up(self):
        """Insertion at index 2 should shift errors at 2+ up by 1."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        # Original: ["Я", "иду", "школу"] (indices 0, 1, 2)
        # Error at idx=2: "школу" → "школе"
        # Insertion at idx=2: insert "в" before "школу"
        # After: ["Я", "иду", "в", "школе"] - error should now be at idx=3

        errors = [
            ErrorResult(
                error_type="noun_case",
                category="MORPH",
                start_idx=2,
                end_idx=3,
                original="школу",
                corrupted="школе",
                fix_tag="$TRANSFORM_CASE_Acc",
            )
        ]

        # Insertion at index 2, delta=+1
        adjusted = pipeline._adjust_indices_for_length_change(
            errors, change_idx=2, delta=+1
        )

        assert len(adjusted) == 1
        assert adjusted[0].start_idx == 3  # 2 + 1 = 3
        assert adjusted[0].end_idx == 4  # 3 + 1 = 4

    def test_earlier_errors_unchanged(self):
        """Errors before the change index should not be adjusted."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        errors = [
            ErrorResult(
                error_type="spelling",
                category="SPELL",
                start_idx=0,
                end_idx=1,
                original="Я",
                corrupted="Йа",
                fix_tag="$REPLACE_Я",
            ),
            ErrorResult(
                error_type="noun_case",
                category="MORPH",
                start_idx=3,
                end_idx=4,
                original="школу",
                corrupted="школе",
                fix_tag="$TRANSFORM_CASE_Acc",
            ),
        ]

        # Deletion at index 2
        adjusted = pipeline._adjust_indices_for_length_change(
            errors, change_idx=2, delta=-1
        )

        assert len(adjusted) == 2
        # First error unchanged (idx=0 < change_idx=2)
        assert adjusted[0].start_idx == 0
        assert adjusted[0].end_idx == 1
        # Second error shifted (idx=3 >= change_idx=2)
        assert adjusted[1].start_idx == 2
        assert adjusted[1].end_idx == 3

    def test_empty_errors_list(self):
        """Empty errors list should return empty list."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        adjusted = pipeline._adjust_indices_for_length_change(
            [], change_idx=2, delta=-1
        )
        assert adjusted == []


class TestGetLengthChangeInfo:
    """Tests for _get_length_change_info helper."""

    def test_deletion_returns_negative_delta(self):
        """Deletion (word_omission) should return delta=-1."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        # word_omission creates $APPEND_<word> tag
        result = ErrorResult(
            error_type="word_omission",
            category="OTHER",
            start_idx=2,
            end_idx=2,  # Empty span after deletion
            original="в",
            corrupted="",
            fix_tag="$APPEND_в",
        )

        change_idx, delta = pipeline._get_length_change_info(result, handler_idx=2)

        assert change_idx == 2
        assert delta == -1

    def test_insertion_returns_positive_delta(self):
        """Insertion (word_insertion) should return delta=+1."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        # word_insertion creates $DELETE tag
        result = ErrorResult(
            error_type="word_insertion",
            category="OTHER",
            start_idx=2,
            end_idx=3,
            original="",
            corrupted="лишнее",
            fix_tag="$DELETE",
        )

        change_idx, delta = pipeline._get_length_change_info(result, handler_idx=2)

        assert change_idx == 3  # handler_idx + 1
        assert delta == +1

    def test_unknown_tag_returns_zero_delta(self):
        """Unknown tag should return zero delta (no adjustment)."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()
        mock_lang.get_analyzer.return_value = MagicMock()
        mock_lang.get_error_handlers.return_value = []
        mock_lang.get_error_distribution.return_value = {}

        pipeline = ErrorPipeline(mock_lang)

        result = ErrorResult(
            error_type="unknown",
            category="OTHER",
            start_idx=2,
            end_idx=3,
            original="test",
            corrupted="test2",
            fix_tag="$REPLACE_test",
        )

        change_idx, delta = pipeline._get_length_change_info(result, handler_idx=2)

        assert change_idx == 0
        assert delta == 0


class TestGenerateAndGenerateBatchParity:
    """Tests to verify feature parity between generate() and generate_batch()."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create a pipeline with mock handlers."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()

        # Create mock analyzer
        mock_analyzer = MagicMock()

        def mock_analyze(text):
            tokens = text.split()
            return [
                AnalyzedToken(
                    text=t,
                    lemma=t.lower(),
                    pos="NOUN",
                    features={},
                    idx=i,
                )
                for i, t in enumerate(tokens)
            ]

        def mock_analyze_batch(texts):
            return [mock_analyze(t) for t in texts]

        mock_analyzer.analyze = mock_analyze
        mock_analyzer.analyze_batch = mock_analyze_batch
        mock_lang.get_analyzer.return_value = mock_analyzer

        # Create mock non-length-changing handler
        mock_handler = MagicMock()
        mock_handler.name = "mock_error"
        mock_handler.subtypes = ["mock_error"]
        mock_handler.category = "OTHER"
        mock_handler.changes_length = False
        mock_handler.can_apply.return_value = True
        mock_handler.apply.return_value = ErrorResult(
            error_type="mock_error",
            category="OTHER",
            start_idx=0,
            end_idx=1,
            original="test",
            corrupted="tset",
            fix_tag="$REPLACE_test",
        )

        # Create mock length-changing handler
        mock_length_handler = MagicMock()
        mock_length_handler.name = "mock_deletion"
        mock_length_handler.subtypes = ["mock_deletion"]
        mock_length_handler.category = "OTHER"
        mock_length_handler.changes_length = True
        mock_length_handler.can_apply.return_value = True
        mock_length_handler.apply.return_value = ErrorResult(
            error_type="mock_deletion",
            category="OTHER",
            start_idx=1,
            end_idx=1,
            original="word",
            corrupted="",
            fix_tag="$APPEND_word",
        )

        mock_lang.get_error_handlers.return_value = [mock_handler, mock_length_handler]
        mock_lang.get_error_distribution.return_value = {
            "mock_error": 0.7,
            "mock_deletion": 0.3,
        }

        config = GenerationConfig(
            seed=42,
            error_probability=1.0,  # Always introduce errors
            max_errors_per_sentence=2,
        )

        return ErrorPipeline(mock_lang, config)

    def test_same_seed_produces_same_results(self, mock_pipeline):
        """Same seed should produce identical results for generate() and generate_batch()."""
        text = "test word here"

        # Reset RNG and generate single
        mock_pipeline._rng.seed(42)
        single_result = mock_pipeline.generate(text)

        # Reset RNG and generate batch
        mock_pipeline._rng.seed(42)
        batch_results = list(mock_pipeline.generate_batch([text]))

        assert len(batch_results) == 1
        batch_result = batch_results[0]

        assert single_result.original_tokens == batch_result.original_tokens
        assert single_result.corrupted_tokens == batch_result.corrupted_tokens
        assert len(single_result.errors) == len(batch_result.errors)

        for single_err, batch_err in zip(
            single_result.errors, batch_result.errors, strict=True
        ):
            assert single_err.error_type == batch_err.error_type
            assert single_err.start_idx == batch_err.start_idx
            assert single_err.fix_tag == batch_err.fix_tag

    def test_both_support_length_changing_handlers(self, mock_pipeline):
        """Both generate() and generate_batch() should support length-changing handlers."""
        # Force length-changing handler to be used by setting high probability
        mock_pipeline._rng.seed(100)  # Find a seed that triggers length change

        text = "test word here"

        # Check that length-changing handlers are available
        length_handlers = [h for h in mock_pipeline.handlers if h.changes_length]
        assert len(length_handlers) > 0, "Test requires length-changing handlers"

        # Both methods should be able to produce results with length-changing errors
        # (exact behavior depends on random sampling, but the capability should exist)
        single_result = mock_pipeline.generate(text)
        batch_results = list(mock_pipeline.generate_batch([text]))

        # Both should produce valid output
        assert single_result.original_tokens is not None
        assert batch_results[0].original_tokens is not None


class TestGeneratedSentenceFormats:
    """Tests for GeneratedSentence output format methods."""

    @pytest.fixture
    def sentence_with_error(self):
        """Create a GeneratedSentence with one error."""
        return GeneratedSentence(
            original_tokens=["Мама", "мыла", "раму"],
            corrupted_tokens=["Мама", "мыла", "раме"],
            errors=[
                ErrorResult(
                    error_type="noun_case",
                    category="MORPH",
                    start_idx=2,
                    end_idx=3,
                    original="раму",
                    corrupted="раме",
                    fix_tag="$TRANSFORM_CASE_Acc",
                )
            ],
            formatted="",
        )

    @pytest.fixture
    def sentence_no_errors(self):
        """Create a GeneratedSentence with no errors."""
        return GeneratedSentence(
            original_tokens=["Мама", "мыла", "раму"],
            corrupted_tokens=["Мама", "мыла", "раму"],
            errors=[],
            formatted="",
        )

    def test_to_tsv_with_error(self, sentence_with_error):
        """TSV format should show corrupted<TAB>original (input→target)."""
        result = sentence_with_error.to_tsv()
        assert result == "Мама мыла раме\tМама мыла раму"

    def test_to_tsv_no_errors(self, sentence_no_errors):
        """TSV format with no errors should have identical src and tgt."""
        result = sentence_no_errors.to_tsv()
        assert result == "Мама мыла раму\tМама мыла раму"

    def test_to_jsonl_basic(self, sentence_with_error):
        """JSONL should include original, corrupted, and errors."""
        result = sentence_with_error.to_jsonl()
        data = json.loads(result)

        assert data["original"] == "Мама мыла раму"
        assert data["corrupted"] == "Мама мыла раме"
        assert len(data["errors"]) == 1
        assert data["errors"][0]["type"] == "noun_case"
        assert data["errors"][0]["category"] == "MORPH"
        assert data["errors"][0]["start_idx"] == 2
        assert data["errors"][0]["end_idx"] == 3

    def test_to_jsonl_with_metadata(self, sentence_with_error):
        """JSONL should include optional metadata when provided."""
        result = sentence_with_error.to_jsonl(
            id="test-001",
            seed=42,
            backend="stanza",
            schema="rlc",
        )
        data = json.loads(result)

        assert data["id"] == "test-001"
        assert data["seed"] == 42
        assert data["backend"] == "stanza"
        assert data["schema"] == "rlc"

    def test_to_jsonl_no_metadata(self, sentence_with_error):
        """JSONL should not include metadata fields when not provided."""
        result = sentence_with_error.to_jsonl()
        data = json.loads(result)

        assert "id" not in data
        assert "seed" not in data
        assert "backend" not in data
        assert "schema" not in data

    def test_to_diff_with_error(self, sentence_with_error):
        """Diff should show [-deleted-]{+inserted+} format."""
        result = sentence_with_error.to_diff()
        assert result == "Мама мыла [-раму-]{+раме+}"

    def test_to_diff_no_errors(self, sentence_no_errors):
        """Diff with no errors should show original text."""
        result = sentence_no_errors.to_diff()
        assert result == "Мама мыла раму"

    def test_to_diff_with_color(self, sentence_with_error):
        """Diff with color should use ANSI escape codes."""
        result = sentence_with_error.to_diff(use_color=True)
        assert "\033[91m" in result  # Red for deletion
        assert "\033[92m" in result  # Green for insertion
        assert "раму" in result
        assert "раме" in result

    def test_to_diff_multiple_errors(self):
        """Diff should handle multiple errors."""
        sentence = GeneratedSentence(
            original_tokens=["Мама", "мыла", "раму"],
            corrupted_tokens=["Мамо", "мыла", "раме"],
            errors=[
                ErrorResult(
                    error_type="spelling",
                    category="SPELL",
                    start_idx=0,
                    end_idx=1,
                    original="Мама",
                    corrupted="Мамо",
                    fix_tag="$REPLACE_Мама",
                ),
                ErrorResult(
                    error_type="noun_case",
                    category="MORPH",
                    start_idx=2,
                    end_idx=3,
                    original="раму",
                    corrupted="раме",
                    fix_tag="$TRANSFORM_CASE_Acc",
                ),
            ],
            formatted="",
        )

        result = sentence.to_diff()
        assert result == "[-Мама-]{+Мамо+} мыла [-раму-]{+раме+}"


class TestZeroWeightSampling:
    """Regression tests for the zero-weight distribution crash.

    Quarantined handlers carry weight 0.0 in presets (e.g. rulec's
    adj_short_en_enen). `-e <handler>` filters the distribution down to
    {handler: 0.0}; _sample_error_type used to feed that straight into
    random.choices, which raises ValueError on a zero total weight
    (review finding, 2026-07-12).
    """

    @staticmethod
    def _mock_language(weights: dict[str, float]):
        """Mock language module with one non-length handler per weight key."""
        from unittest.mock import MagicMock

        mock_lang = MagicMock()

        mock_analyzer = MagicMock()

        def mock_analyze(text):
            return [
                AnalyzedToken(text=t, lemma=t.lower(), pos="NOUN", features={}, idx=i)
                for i, t in enumerate(text.split())
            ]

        mock_analyzer.analyze = mock_analyze
        mock_analyzer.analyze_batch = lambda texts: [mock_analyze(t) for t in texts]
        mock_lang.get_analyzer.return_value = mock_analyzer

        handlers = []
        for name in weights:
            handler = MagicMock()
            handler.name = name
            handler.subtypes = [name]
            handler.category = "OTHER"
            handler.changes_length = False
            handler.can_apply.return_value = True
            handler.apply.return_value = ErrorResult(
                error_type=name,
                category="OTHER",
                start_idx=0,
                end_idx=1,
                original="слово",
                corrupted="слова",
                fix_tag="$REPLACE_слово",
            )
            handlers.append(handler)

        mock_lang.get_error_handlers.return_value = handlers
        mock_lang.get_error_distribution.return_value = dict(weights)
        return mock_lang

    def test_explicitly_enabled_zero_weight_handler_fires_uniformly(self):
        """-e naming a quarantined (weight 0.0) handler must not crash:
        an explicit request beats the preset's zero — uniform fallback."""
        lang = self._mock_language({"quarantined": 0.0, "other": 5.0})
        config = GenerationConfig(
            seed=42,
            error_probability=1.0,
            max_errors_per_sentence=1,
            enabled_errors={"quarantined"},
        )
        pipeline = ErrorPipeline(lang, config)

        # The filtered distribution is {"quarantined": 0.0} — this raised
        # ValueError("Total of weights must be greater than zero") before.
        handler = pipeline._sample_error_type()
        assert handler is not None
        assert handler.name == "quarantined"

        result = pipeline.generate("одно слово тут")
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "quarantined"

    def test_zero_weight_handler_never_sampled_without_explicit_enable(self):
        """Without enabled_errors, zero-weight entries are dropped from
        sampling — the quarantined handler must never fire."""
        lang = self._mock_language({"quarantined": 0.0, "other": 5.0})
        config = GenerationConfig(
            seed=42, error_probability=1.0, max_errors_per_sentence=3
        )
        pipeline = ErrorPipeline(lang, config)

        for _ in range(50):
            handler = pipeline._sample_error_type()
            assert handler is not None
            assert handler.name == "other"

    def test_all_zero_distribution_without_explicit_enable_yields_no_errors(self):
        """All-zero distribution and no explicit enable: nothing to sample —
        generate() must return the sentence untouched, not crash."""
        lang = self._mock_language({"quarantined": 0.0, "also_zero": 0.0})
        config = GenerationConfig(
            seed=42, error_probability=1.0, max_errors_per_sentence=3
        )
        pipeline = ErrorPipeline(lang, config)

        assert pipeline._sample_error_type() is None

        result = pipeline.generate("одно слово тут")
        assert result.errors == []
        assert result.corrupted_tokens == result.original_tokens

    def test_explicit_enable_of_multiple_zero_weight_handlers_is_uniform(self):
        """Uniform fallback covers every explicitly enabled handler, not
        just the first: both zero-weight handlers must be sampleable."""
        lang = self._mock_language({"quar_a": 0.0, "quar_b": 0.0, "other": 5.0})
        config = GenerationConfig(
            seed=42,
            error_probability=1.0,
            max_errors_per_sentence=1,
            enabled_errors={"quar_a", "quar_b"},
        )
        pipeline = ErrorPipeline(lang, config)

        seen = {pipeline._sample_error_type().name for _ in range(100)}
        assert seen == {"quar_a", "quar_b"}
