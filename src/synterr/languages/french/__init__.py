"""French language support for synterr (PoC).

Per docs/research/FRENCH_POC_WORKFLOW.md: this PoC deliberately skips the
R1 core refactor (pymorphy_parse -> morph_parse protocol). The French stanza
backend leaves ``token.extra`` empty since none of the five wired PoC
handlers need a morphological-inflection parse object (they are string
rewrites gated by UD features/deprels only). ``get_error_handlers()`` wires
in the five validated PoC handlers (grammatical_homophone,
verb_ending_homophony, article_contraction, elision_apostrophe,
pp_agreement) — see docs/research/FRENCH_POC_REPORT.md for their validity
data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import Analyzer, ErrorHandler


class FrenchLanguage:
    """French language module for synterr (PoC)."""

    code = "fr"
    name = "French"

    def get_analyzer(
        self,
        use_depparse: bool = False,
        backend: str | None = None,
    ) -> Analyzer:
        """Get French analyzer with configurable backend.

        Args:
            use_depparse: Enable dependency parsing
            backend: Backend name ('stanza') or None for default

        Returns:
            FrenchAnalyzer instance

        Available backends:
            - stanza: fr_sequoia model (default, only backend in the PoC)
        """
        from synterr.languages.french.analyzer import FrenchAnalyzer

        return FrenchAnalyzer(backend=backend, use_depparse=use_depparse)

    def get_error_handlers(self) -> list[ErrorHandler]:
        """Get all French error handlers.

        Returns the five validated PoC handlers (grammatical_homophone,
        verb_ending_homophony, article_contraction, elision_apostrophe,
        pp_agreement) — see docs/research/FRENCH_POC_REPORT.md.
        """
        from synterr.languages.french.errors import get_all_handlers

        return get_all_handlers()

    def get_error_distribution(self) -> dict[str, float]:
        """Get default error distribution weights for French.

        Loads from the PoC preset config (poc.yaml).
        """
        from synterr.configs import load_preset

        try:
            config = load_preset("french", "poc")
            return config.get("weights", {}) or {}
        except FileNotFoundError:
            return {}


# Export for entry point
__all__ = ["FrenchLanguage"]
