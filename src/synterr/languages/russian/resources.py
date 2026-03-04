"""Russian language resources - lexical confusions, frequency lists, etc."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def get_paronyms() -> dict[str, list[str]]:
    """Load paronyms dictionary.

    Sources:
        - ЕГЭ (Russian standardized exam) paronym list
        - О.В. Вишнякова "Словарь паронимов русского языка" (1984)
        - Claude AI generated based on linguistic patterns

    Returns:
        Dict mapping correct words to their common confusions
    """
    data_path = _get_package_data_path() / "paronyms.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)
            # Remove metadata key
            return {k: v for k, v in data.items() if not k.startswith("_")}

    # Fallback to external data directory
    data_path = _get_data_path() / "lexical_confusions.json"
    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)

    return {}


# Alias for backwards compatibility
get_lexical_confusions = get_paronyms


@lru_cache(maxsize=1)
def get_conjunction_list() -> dict[str, list[str]]:
    """Get list of frequent Russian conjunctions."""
    data_path = _get_package_data_path() / "conjunctions.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)
            # Remove metadata key
            return {k: v for k, v in data.items() if not k.startswith("_")}

    return {}


@lru_cache(maxsize=1)
def get_preposition_list() -> dict[str, list[str]]:
    """Get list of frequent Russian prepositions."""
    data_path = _get_package_data_path() / "prepositions.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)
            # Remove metadata key
            return {k: v for k, v in data.items() if not k.startswith("_")}

    return {}


@lru_cache(maxsize=1)
def get_filler_list() -> list[str]:
    """Get list of filler words for word insertion errors."""
    data_path = _get_package_data_path() / "fillers.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            data = json.load(f)
            return data.get("fillers", [])

    return []


@lru_cache(maxsize=1)
def get_morph_analyzer():
    """Get shared pymorphy3 MorphAnalyzer instance (cached singleton)."""
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=1)
def get_stress_dict() -> dict[str, int]:
    """Load stress dictionary for vowel reduction.

    The dictionary maps words to the 0-indexed position of the stressed vowel.
    Built from 50k frequency list using russtress (Python 3.10 + TensorFlow).

    Returns:
        Dict mapping word to stress position (-1 if unknown)
    """
    data_path = _get_package_data_path() / "stress_dict.json"

    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)

    # Return empty dict if not found (vowel reduction will be skipped)
    return {}


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


def _get_package_data_path() -> Path:
    """Get path to package data directory (src/synterr/data/russian)."""
    # Try package resources first (works in installed package)
    try:
        pkg_files = resources.files("synterr.data.russian")
        # Convert to Path if possible
        if hasattr(pkg_files, "_path"):
            return Path(pkg_files._path)
    except (TypeError, ModuleNotFoundError):
        pass

    # Fall back to relative path (for development)
    # __file__ = src/synterr/languages/russian/resources.py
    # parent.parent.parent = src/synterr/
    # + data/russian = src/synterr/data/russian
    return Path(__file__).parent.parent.parent / "data" / "russian"


def _get_data_path() -> Path:
    """Get path to external data directory (data/russian in project root)."""
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
