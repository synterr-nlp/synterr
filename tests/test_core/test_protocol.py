"""Tests for synterr core protocol definitions."""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken, ErrorHandler, ErrorResult


class TestAnalyzedToken:
    """Tests for AnalyzedToken dataclass."""

    def test_create_token(self):
        """Test creating an analyzed token."""
        token = AnalyzedToken(
            text="книга",
            lemma="книга",
            pos="NOUN",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            idx=0,
        )

        assert token.text == "книга"
        assert token.lemma == "книга"
        assert token.pos == "NOUN"
        assert token.idx == 0

    def test_has_feature(self):
        """Test checking for morphological features."""
        token = AnalyzedToken(
            text="книга",
            lemma="книга",
            pos="NOUN",
            features={"Case": "Nom", "Number": "Sing"},
            idx=0,
        )

        assert token.has_feature("Case")
        assert token.has_feature("Case", "Nom")
        assert not token.has_feature("Case", "Gen")
        assert not token.has_feature("Gender")

    def test_get_feature(self):
        """Test getting feature values."""
        token = AnalyzedToken(
            text="книга",
            lemma="книга",
            pos="NOUN",
            features={"Case": "Nom"},
            idx=0,
        )

        assert token.get_feature("Case") == "Nom"
        assert token.get_feature("Gender") is None
        assert token.get_feature("Gender", "Masc") == "Masc"

    def test_extra_data(self):
        """Test storing extra language-specific data."""
        token = AnalyzedToken(
            text="книга",
            lemma="книга",
            pos="NOUN",
            features={},
            idx=0,
            extra={"pymorphy_parse": "mock_parse"},
        )

        assert token.extra["pymorphy_parse"] == "mock_parse"


class TestErrorResult:
    """Tests for ErrorResult dataclass."""

    def test_create_error_result(self):
        """Test creating an error result."""
        result = ErrorResult(
            error_type="noun_case",
            category="MORPH",
            start_idx=0,
            end_idx=1,
            original="книга",
            corrupted="книги",
            fix_tag="$TRANSFORM_CASE_Nom",
        )

        assert result.error_type == "noun_case"
        assert result.category == "MORPH"
        assert result.original == "книга"
        assert result.corrupted == "книги"


class TestErrorHandlerProtocol:
    """Tests for ErrorHandler protocol compliance."""

    def test_protocol_check(self):
        """Test that a valid handler implements the protocol."""

        class MockHandler:
            name = "mock"
            subtypes = ["mock"]
            category = "OTHER"
            changes_length = False

            def can_apply(self, tokens, idx):
                return True

            def apply(self, tokens, sentence, idx, modified):
                return None

        handler = MockHandler()
        assert isinstance(handler, ErrorHandler)

    def test_protocol_missing_attribute(self):
        """Test that incomplete handler doesn't implement protocol."""

        class IncompleteHandler:
            name = "incomplete"
            # Missing: category, changes_length, can_apply, apply

        handler = IncompleteHandler()
        assert not isinstance(handler, ErrorHandler)
