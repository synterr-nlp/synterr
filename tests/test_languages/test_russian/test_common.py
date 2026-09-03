"""Tests for the helpers shared across the Russian handler modules."""

import pytest

from synterr.languages.russian.errors._common import (
    SubtypeGateMixin,
    WeightedSubtypeMixin,
    _get_token_safe,
    _is_predicate_token,
)

from .helpers import make_token as _tok


class _Gated(SubtypeGateMixin):
    subtypes = ["a", "b"]


class _Weighted(WeightedSubtypeMixin):
    subtypes = ["a", "b"]
    DEFAULT_WEIGHTS = {"a": 10, "b": 5}


class TestSubtypeGateMixin:
    def test_defaults_to_all_subtypes(self):
        assert _Gated()._enabled_subtypes is None

    def test_accepts_known_subtypes(self):
        h = _Gated()
        h.set_enabled_subtypes({"a"})
        assert h._enabled_subtypes == {"a"}
        h.set_enabled_subtypes(None)
        assert h._enabled_subtypes is None

    def test_rejects_unknown_subtype(self):
        with pytest.raises(ValueError, match="Unknown subtypes"):
            _Gated().set_enabled_subtypes({"zzz"})


class TestWeightedSubtypeMixin:
    def test_seeds_weights_from_defaults(self):
        h = _Weighted()
        assert h._weights == {"a": 10, "b": 5}
        assert h._weights is not _Weighted.DEFAULT_WEIGHTS
        assert h._enabled_subtypes is None

    def test_set_subtype_weights_overrides_and_resets(self):
        h = _Weighted()
        h.set_subtype_weights({"a": 0, "unknown": 99})
        assert h._weights == {"a": 0, "b": 5}
        h.set_subtype_weights({})
        assert h._weights == {"a": 10, "b": 5}


class TestTokenHelpers:
    def test_get_token_safe_bounds(self):
        tokens = [_tok("а"), _tok("б", idx=1)]
        assert _get_token_safe(tokens, 1) is tokens[1]
        assert _get_token_safe(tokens, -1) is None
        assert _get_token_safe(tokens, 2) is None

    @pytest.mark.parametrize(
        ("pos", "features", "expected"),
        [
            ("VERB", {}, True),
            ("AUX", {"VerbForm": "Fin"}, True),
            ("VERB", {"VerbForm": "Part", "Variant": "Short"}, True),
            ("VERB", {"VerbForm": "Part"}, False),
            ("VERB", {"VerbForm": "Inf"}, False),
            ("NOUN", {}, False),
        ],
    )
    def test_is_predicate_token(self, pos, features, expected):
        assert _is_predicate_token(_tok("x", pos, features=features)) is expected
