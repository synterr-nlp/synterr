"""French error handlers for synterr.

Exposes the five validated PoC handlers (docs/research/FRENCH_POC_WORKFLOW.md,
docs/research/FRENCH_POC_REPORT.md): grammatical_homophone,
verb_ending_homophony, article_contraction, elision_apostrophe, pp_agreement.
Mirrors the shape of ``synterr.languages.russian.errors.get_all_handlers``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import ErrorHandler


def get_all_handlers() -> list[ErrorHandler]:
    """Get all registered (validated) French error handlers."""
    from synterr.languages.french.errors.determiners import (
        ArticleContractionHandler,
    )
    from synterr.languages.french.errors.elision import (
        ElisionApostropheHandler,
    )
    from synterr.languages.french.errors.homophony import (
        GrammaticalHomophoneErrorHandler,
    )
    from synterr.languages.french.errors.pp_agreement import (
        PastParticipleAgreementHandler,
    )
    from synterr.languages.french.errors.verb_endings import (
        VerbEndingHomophonyHandler,
    )

    return [
        # Spelling / homophony
        GrammaticalHomophoneErrorHandler(),
        VerbEndingHomophonyHandler(),
        ElisionApostropheHandler(),
        # Morphological
        ArticleContractionHandler(),
        PastParticipleAgreementHandler(),
    ]


__all__ = ["get_all_handlers"]
