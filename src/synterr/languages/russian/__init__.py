"""Russian language support for synterr."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import Analyzer, ErrorHandler


class RussianLanguage:
    """Russian language module for synterr."""

    code = "ru"
    name = "Russian"

    def get_analyzer(self, use_depparse: bool = False) -> Analyzer:
        """Get Russian analyzer with stanza pipeline.

        Args:
            use_depparse: Enable dependency parsing (~40% slower)

        Returns:
            RussianAnalyzer instance
        """
        from synterr.languages.russian.analyzer import RussianAnalyzer

        return RussianAnalyzer(use_depparse=use_depparse)

    def get_error_handlers(self) -> list[ErrorHandler]:
        """Get all Russian error handlers."""
        from synterr.languages.russian.errors import get_all_handlers

        return get_all_handlers()

    def get_error_distribution(self) -> dict[str, float]:
        """Get default error distribution weights for Russian.

        Based on RULEC-GEC error distribution analysis.
        """
        return {
            # Spelling errors (15%)
            "spelling": 0.15,
            # Morphological errors (40%)
            "noun_case": 0.10,
            "noun_number": 0.05,
            "adj_case": 0.05,
            "adj_number": 0.03,
            "adj_gender": 0.02,
            "verb_person_number": 0.08,
            "verb_tense": 0.07,
            # Lexical errors (10%)
            # "preposition": 0.04,
            # "conjunction": 0.03,
            # "pronoun": 0.03,
            # Structural errors (25%) - TODO: implement
            # "insert": 0.14,
            # "delete": 0.11,
            # Punctuation errors (10%) - TODO: implement
            # "missing_comma": 0.05,
            # "extra_comma": 0.05,
        }


# Export for entry point
__all__ = ["RussianLanguage"]
