"""Core module for synterr - language-agnostic error generation infrastructure."""

from synterr.core.protocol import AnalyzedToken, ErrorHandler, ErrorResult
from synterr.core.registry import get_language, list_languages, register_language

__all__ = [
    "AnalyzedToken",
    "ErrorHandler",
    "ErrorResult",
    "get_language",
    "list_languages",
    "register_language",
]
