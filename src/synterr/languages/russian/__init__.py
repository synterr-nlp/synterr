"""Russian language support for synterr."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import Analyzer, ErrorHandler


class RussianLanguage:
    """Russian language module for synterr."""

    code = "ru"
    name = "Russian"

    def get_analyzer(
        self,
        use_depparse: bool = False,
        backend: str | None = None,
    ) -> Analyzer:
        """Get Russian analyzer with configurable backend.

        Args:
            use_depparse: Enable dependency parsing
            backend: Backend name ('stanza', 'natasha', 'spacy') or None for default

        Returns:
            RussianAnalyzer instance

        Available backends:
            - stanza: Best accuracy, slower (~92 sent/s) - default
            - natasha: Fastest (~500 sent/s), lightweight
            - spacy: Balanced, good dependency parsing
        """
        from synterr.languages.russian.analyzer import RussianAnalyzer

        return RussianAnalyzer(backend=backend, use_depparse=use_depparse)

    def get_error_handlers(self) -> list[ErrorHandler]:
        """Get all Russian error handlers."""
        from synterr.languages.russian.errors import get_all_handlers

        return get_all_handlers()

    def get_error_distribution(self) -> dict[str, float]:
        """Get default error distribution weights for Russian.

        Loads from the default preset config (rulec.yaml).
        """
        from synterr.configs import get_default_preset, load_preset

        try:
            preset_name = get_default_preset(self.code)
            config = load_preset(self.code, preset_name)
            return config.get("weights", {})
        except FileNotFoundError:
            # Fallback to hard-coded defaults if config not found
            return {
                "spelling": 0.475,
                "noun_case": 0.280,
                "noun_number": 0.053,
                "adj_case": 0.071,
                "adj_number": 0.019,
                "adj_gender": 0.027,
                "verb_person_number": 0.052,
                "verb_tense": 0.023,
            }


# Export for entry point
__all__ = ["RussianLanguage"]
