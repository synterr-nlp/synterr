"""Russian error handlers for synterr."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import ErrorHandler


def get_all_handlers() -> list[ErrorHandler]:
    """Get all registered Russian error handlers."""
    from synterr.languages.russian.errors.adverb_spelling import (
        AdverbSpellingHandler,
    )
    from synterr.languages.russian.errors.comma_insert import (
        CommaInsertHandler,
    )
    from synterr.languages.russian.errors.compound_spelling import (
        CompoundSpellingHandler,
    )
    from synterr.languages.russian.errors.function_spelling import (
        FunctionSpellingHandler,
    )
    from synterr.languages.russian.errors.lexical import (
        ConjunctionErrorHandler,
        ParonymErrorHandler,
        PrepositionErrorHandler,
    )
    from synterr.languages.russian.errors.morphological import (
        AdjCaseErrorHandler,
        AdjFormErrorHandler,
        AdjGenderErrorHandler,
        AdjNumberErrorHandler,
        DoubleComparativeHandler,
        NounCaseErrorHandler,
        NounCasePrepErrorHandler,
        NounNumberErrorHandler,
        NumeralDeclensionHandler,
        VerbPersonNumberErrorHandler,
        VerbTenseErrorHandler,
    )
    from synterr.languages.russian.errors.orthographic_spelling import (
        OrthographicSpellingHandler,
    )
    from synterr.languages.russian.errors.punctuation import (
        CommaDeleteHandler,
        CommaPairDeleteHandler,
        DashDeleteHandler,
        DashToCommaHandler,
    )
    from synterr.languages.russian.errors.semantics import (
        CollocationHandler,
        PleonasmHandler,
    )
    from synterr.languages.russian.errors.spelling import SpellingErrorHandler
    from synterr.languages.russian.errors.structural import (
        WordInsertionHandler,
        WordOmissionHandler,
    )

    return [
        # Spelling
        SpellingErrorHandler(),
        FunctionSpellingHandler(),
        OrthographicSpellingHandler(),
        CompoundSpellingHandler(),
        AdverbSpellingHandler(),
        # Morphological - Nouns
        NounCaseErrorHandler(),
        NounCasePrepErrorHandler(),
        NounNumberErrorHandler(),
        # Morphological - Adjectives
        AdjCaseErrorHandler(),
        AdjNumberErrorHandler(),
        AdjGenderErrorHandler(),
        AdjFormErrorHandler(),
        DoubleComparativeHandler(),
        # Morphological - Verbs
        VerbPersonNumberErrorHandler(),
        VerbTenseErrorHandler(),
        # Morphological - Numerals
        NumeralDeclensionHandler(),
        # Lexical
        ParonymErrorHandler(),
        PrepositionErrorHandler(),
        ConjunctionErrorHandler(),
        # Semantics
        PleonasmHandler(),
        CollocationHandler(),
        # Punctuation
        CommaDeleteHandler(),
        CommaPairDeleteHandler(),
        CommaInsertHandler(),
        DashDeleteHandler(),
        DashToCommaHandler(),
        # Structural
        WordOmissionHandler(),
        WordInsertionHandler(),
    ]


__all__ = ["get_all_handlers"]
