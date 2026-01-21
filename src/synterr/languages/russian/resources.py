"""Russian language resources - lexical confusions, frequency lists, etc."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def get_lexical_confusions() -> dict[str, list[str]]:
    """Load lexical confusions dictionary.

    Returns:
        Dict mapping words to their common confusions/paronyms
    """
    data_path = _get_data_path() / "lexical_confusions.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)

    # Return empty dict if no data file
    return {}


@lru_cache(maxsize=1)
def get_conjunction_list() -> list[str]:
    """Get list of frequent Russian conjunctions."""
    # Frequently used conjunctions from RULEC/corpus analysis
    return [
        "и",
        "а",
        "но",
        "или",
        "что",
        "как",
        "когда",
        "если",
        "чтобы",
        "потому",
        "хотя",
        "однако",
        "либо",
        "тоже",
        "также",
        "зато",
        "притом",
        "причём",
        "поэтому",
        "ведь",
    ]


@lru_cache(maxsize=1)
def get_preposition_list() -> list[str]:
    """Get list of frequent Russian prepositions."""
    return [
        "в",
        "на",
        "с",
        "к",
        "по",
        "за",
        "о",
        "из",
        "у",
        "для",
        "от",
        "до",
        "без",
        "при",
        "над",
        "под",
        "между",
        "через",
        "перед",
        "после",
        "около",
        "вокруг",
        "против",
    ]


@lru_cache(maxsize=1)
def get_pronoun_list() -> list[str]:
    """Get list of frequent Russian pronouns."""
    return [
        "я",
        "ты",
        "он",
        "она",
        "оно",
        "мы",
        "вы",
        "они",
        "себя",
        "кто",
        "что",
        "какой",
        "который",
        "чей",
        "этот",
        "тот",
        "такой",
        "весь",
        "каждый",
        "любой",
        "другой",
        "сам",
        "самый",
    ]


def _get_data_path() -> Path:
    """Get path to data directory."""
    # Try package data first
    try:
        with resources.files("synterr") as pkg_path:
            data_path = Path(pkg_path) / "data" / "russian"
            if data_path.exists():
                return data_path
    except (TypeError, FileNotFoundError):
        pass

    # Fall back to relative path (for development)
    module_dir = Path(__file__).parent.parent.parent.parent.parent
    data_path = module_dir / "data" / "russian"
    if data_path.exists():
        return data_path

    # Create directory if it doesn't exist
    return data_path


def load_resource(name: str) -> Any:
    """Load a named resource file.

    Args:
        name: Resource filename (without path)

    Returns:
        Loaded resource (JSON parsed if .json extension)
    """
    data_path = _get_data_path() / name

    if not data_path.exists():
        raise FileNotFoundError(f"Resource not found: {name}")

    with data_path.open(encoding="utf-8") as f:
        if name.endswith(".json"):
            return json.load(f)
        return f.read()
