"""Russian error handlers for synterr."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import ErrorHandler


def get_all_handlers() -> list[ErrorHandler]:
    """Get all registered Russian error handlers."""
    from synterr.languages.russian.errors.morphological import (
        AdjCaseErrorHandler,
        AdjGenderErrorHandler,
        AdjNumberErrorHandler,
        NounCaseErrorHandler,
        NounNumberErrorHandler,
        VerbPersonNumberErrorHandler,
        VerbTenseErrorHandler,
    )
    from synterr.languages.russian.errors.spelling import SpellingErrorHandler

    return [
        # Spelling
        SpellingErrorHandler(),
        # Morphological - Nouns
        NounCaseErrorHandler(),
        NounNumberErrorHandler(),
        # Morphological - Adjectives
        AdjCaseErrorHandler(),
        AdjNumberErrorHandler(),
        AdjGenderErrorHandler(),
        # Morphological - Verbs
        VerbPersonNumberErrorHandler(),
        VerbTenseErrorHandler(),
    ]


__all__ = ["get_all_handlers"]
