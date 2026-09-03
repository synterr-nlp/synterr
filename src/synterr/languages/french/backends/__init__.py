"""Pluggable NLP backends for French language analysis (PoC).

Available backends:
    - stanza: Stanford NLP stanza, `fr_sequoia` package (default, only backend
      in the PoC)

Usage:
    from synterr.languages.french.backends import get_backend

    # Get default backend (stanza)
    backend = get_backend()

    # Analyze text
    tokens = backend.analyze("Marie mange une pomme.")
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synterr.languages.french.backends.base import AnalyzerBackend

BACKENDS = {
    "stanza": "synterr.languages.french.backends.stanza_fr:StanzaFrBackend",
}

DEFAULT_BACKEND = "stanza"


def get_backend(
    name: str | None = None,
    use_depparse: bool = False,
    use_gpu: bool = True,
) -> AnalyzerBackend:
    """Get an analyzer backend by name.

    Args:
        name: Backend name ('stanza') or None for default
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

    module_path, class_name = BACKENDS[name].rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)
    except ImportError as e:
        raise ImportError(
            f"Backend '{name}' requires additional dependencies. "
            f"Install with: pip install synterr[french]"
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
