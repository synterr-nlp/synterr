"""Language registry for synterr - discovery and registration of language modules."""

from __future__ import annotations

import warnings
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.core.protocol import LanguageModule

# Global registry of language modules
_LANGUAGES: dict[str, LanguageModule] = {}
_LOADED_ENTRY_POINTS = False


def register_language(language: LanguageModule) -> None:
    """Register a language module.

    Args:
        language: Language module instance implementing LanguageModule protocol
    """
    _LANGUAGES[language.code] = language


def _load_entry_points() -> None:
    """Load language modules from entry points (lazy, called once)."""
    global _LOADED_ENTRY_POINTS
    if _LOADED_ENTRY_POINTS:
        return

    eps = entry_points(group="synterr.languages")

    for ep in eps:
        try:
            language_cls = ep.load()
            language = (
                language_cls() if isinstance(language_cls, type) else language_cls
            )
            register_language(language)
        except Exception as e:
            # one broken optional language must not take the registry down
            warnings.warn(
                f"Failed to load language module '{ep.name}': {e}", stacklevel=2
            )

    _LOADED_ENTRY_POINTS = True


def get_language(code: str) -> LanguageModule:
    """Get a language module by ISO 639-1 code.

    Args:
        code: Language code (e.g., 'ru', 'en')

    Returns:
        Language module instance

    Raises:
        KeyError: If language is not registered
    """
    _load_entry_points()

    if code not in _LANGUAGES:
        available = ", ".join(sorted(_LANGUAGES.keys())) or "(none)"
        raise KeyError(f"Language '{code}' not found. Available: {available}")

    return _LANGUAGES[code]


def list_languages() -> dict[str, str]:
    """List all available languages.

    Returns:
        Dict mapping language codes to human-readable names
    """
    _load_entry_points()
    return {code: lang.name for code, lang in sorted(_LANGUAGES.items())}


def is_language_available(code: str) -> bool:
    """Check if a language module is available.

    Args:
        code: Language code (e.g., 'ru', 'en')

    Returns:
        True if language is registered
    """
    _load_entry_points()
    return code in _LANGUAGES
