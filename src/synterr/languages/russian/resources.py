"""Russian language resources - lexical confusions, frequency lists, etc."""

from __future__ import annotations

import json
import pickle
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


@lru_cache(maxsize=1)
def get_morpheme_dict() -> dict[str, list[str]]:
    """Load morpheme dictionary (from morpholog/Tikhonov, 93k entries).

    Returns dict mapping word → list of morpheme strings.
    Convention: 'при-' = prefix, '-к' = suffix, '+а' = ending, bare = root.
    """
    data_path = _get_package_data_path() / "morpheme_dict.pickle"
    if data_path.exists():
        with data_path.open("rb") as f:
            return pickle.load(f)
    return {}


class MorphemeAnalyzer:
    """Morpheme analysis with dictionary lookup + pymorphy3 validation.

    Usage:
        analyzer = get_morpheme_analyzer()
        analyzer.has_prefix("привычка", "при")   # True
        analyzer.has_prefix("природа", "при")    # False (per Tikhonov)
        analyzer.word_is_known("несчастье")       # True
        analyzer.word_is_known("некошка")          # False
    """

    def __init__(self) -> None:
        self._dict: dict[str, list[str]] | None = None
        self._pymorphy = None

    @property
    def morpheme_dict(self) -> dict[str, list[str]]:
        if self._dict is None:
            self._dict = get_morpheme_dict()
        return self._dict

    @property
    def pymorphy(self):
        if self._pymorphy is None:
            self._pymorphy = get_morph_analyzer()
        return self._pymorphy

    def get_morphemes(self, word: str) -> list[tuple[str, str]] | None:
        """Parse morpheme dict entry into [(text, type), ...].

        Returns None if word not in dictionary.
        Types: PREF, ROOT, SUFF, END, LINK, POST.
        """
        entry = self.morpheme_dict.get(word.lower())
        if not entry or not isinstance(entry, list) or entry == [""]:
            return None
        result = []
        for m in entry:
            if not isinstance(m, str) or not m:
                continue
            # Skip garbage entries (raw wikitext)
            if "\n" in m or "=" in m and len(m) > 10:
                return None
            if m.endswith("-") and not m.startswith("-"):
                result.append((m[:-1], "PREF"))
            elif m.startswith("-"):
                result.append((m[1:], "SUFF"))
            elif m.startswith("+"):
                result.append((m[1:], "END"))
            elif "=" in m:
                result.append((m.replace("=", ""), "LINK"))
            else:
                result.append((m, "ROOT"))
        return result if result else None

    def has_prefix(self, word: str, prefix: str) -> bool | None:
        """Check if word has a specific prefix. Returns None if unknown."""
        morphemes = self.get_morphemes(word)
        if morphemes is None:
            return None
        return any(text == prefix and typ == "PREF" for text, typ in morphemes)

    def has_any_prefix(self, word: str) -> bool | None:
        """Check if word has any prefix. Returns None if unknown."""
        morphemes = self.get_morphemes(word)
        if morphemes is None:
            return None
        return any(typ == "PREF" for _, typ in morphemes)

    def has_suffix(self, word: str, suffix: str) -> bool | None:
        """Check if word has a specific suffix. Returns None if unknown."""
        morphemes = self.get_morphemes(word)
        if morphemes is None:
            return None
        return any(text == suffix and typ == "SUFF" for text, typ in morphemes)

    def get_suffixes(self, word: str) -> list[str] | None:
        """Return list of suffixes for a word. Returns None if unknown."""
        morphemes = self.get_morphemes(word)
        if morphemes is None:
            return None
        return [text for text, typ in morphemes if typ == "SUFF"]

    def word_is_known(self, word: str) -> bool:
        """Check if word exists in OpenCorpora dictionary (strict)."""
        return self.pymorphy.word_is_known(word.lower())


@lru_cache(maxsize=1)
def get_morpheme_analyzer() -> MorphemeAnalyzer:
    """Get shared MorphemeAnalyzer instance (cached singleton)."""
    return MorphemeAnalyzer()


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
