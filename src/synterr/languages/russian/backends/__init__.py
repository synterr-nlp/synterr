"""Pluggable NLP backends for Russian language analysis.

Available backends:
    - stanza: Stanford NLP stanza (default, best accuracy)
    - natasha: Natasha/Slovnet (fastest, lightweight)
    - spacy: spaCy with Russian model (balanced)

Usage:
    from synterr.languages.russian.backends import get_backend

    # Get default backend (stanza)
    backend = get_backend()

    # Get specific backend
    backend = get_backend("natasha")

    # Analyze text
    tokens = backend.analyze("Мама мыла раму.")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.languages.russian.backends.base import AnalyzerBackend

# Available backends
BACKENDS = {
    "stanza": "synterr.languages.russian.backends.stanza_backend:StanzaBackend",
    "natasha": "synterr.languages.russian.backends.natasha_backend:NatashaBackend",
    "spacy": "synterr.languages.russian.backends.spacy_backend:SpacyBackend",
}

DEFAULT_BACKEND = "stanza"


def get_backend(
    name: str | None = None,
    use_depparse: bool = False,
    use_gpu: bool = True,
) -> AnalyzerBackend:
    """Get an analyzer backend by name.

    Args:
        name: Backend name ('stanza', 'natasha', 'spacy') or None for default
        use_depparse: Enable dependency parsing
        use_gpu: Use GPU acceleration (if available)

    Returns:
        Configured backend instance

    Raises:
        ValueError: If backend name is unknown
        ImportError: If backend dependencies are not installed
    """
    name = name or DEFAULT_BACKEND

    if name not in BACKENDS:
        available = ", ".join(BACKENDS.keys())
        raise ValueError(f"Unknown backend '{name}'. Available: {available}")

    # Lazy import backend class
    module_path, class_name = BACKENDS[name].rsplit(":", 1)

    try:
        import importlib

        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)
    except ImportError as e:
        raise ImportError(
            f"Backend '{name}' requires additional dependencies. "
            f"Install with: pip install synterr[{name}]"
        ) from e

    return backend_class(use_depparse=use_depparse, use_gpu=use_gpu)


def list_backends() -> dict[str, str]:
    """List available backends with their status.

    Returns:
        Dict mapping backend names to availability status
    """
    result = {}
    for name in BACKENDS:
        try:
            get_backend(name)
            result[name] = "available"
        except ImportError:
            result[name] = "not installed"
    return result


__all__ = ["BACKENDS", "DEFAULT_BACKEND", "get_backend", "list_backends"]
