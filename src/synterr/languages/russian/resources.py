"""Russian language resources - lexical confusions, frequency lists, etc."""

from __future__ import annotations

import json
import pickle
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

# Morpheme strings in unified_dict.json may carry annotation characters
# that are NOT part of the surface spelling: '-' marks a linking-morpheme
# boundary (the "о-" in бел|о-|камен|н|ый), Latin 'j' marks a phantom
# morphophonemic consonant ("церемониj"), and a few entries use "(...)"
# for optional segments. They must be stripped before character offsets
# into the surface word are computed.
_ANNOTATION_CHARS_RE = re.compile(r"[^а-яёА-ЯЁ]")


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
def get_unified_dict() -> dict[str, dict]:
    """Load unified morpheme+stress dictionary.

    Format: {"word": {"s": stress_pos, "m": [["text", "TYPE"], ...]}, ...}
    Keys: "s" = stress char index (-1 = unknown), "m" = morphemes (absent = unknown)
    Morpheme types: R=root, P=prefix, S=suffix, E=ending, L=link

    Merges morpheme_dict.pickle (Tikhonov, 93k) + stress_dict.json (russtress, 49k)
    + Morphberta-K neural segmentation + extended russtress annotations.
    """
    data_path = _get_package_data_path() / "unified_dict.json"
    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)
    return {}


@lru_cache(maxsize=1)
def get_stress_dict() -> dict[str, int]:
    """Load stress dictionary for vowel reduction.

    Reads from unified_dict.json ("s" field), falls back to stress_dict.json.

    Returns:
        Dict mapping word to stress position (-1 if unknown)
    """
    unified = get_unified_dict()
    if unified:
        return {w: entry.get("s", -1) for w, entry in unified.items()}

    data_path = _get_package_data_path() / "stress_dict.json"
    if data_path.exists():
        with data_path.open(encoding="utf-8") as f:
            return json.load(f)

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

    Uses unified_dict.json (preferred) with fallback to morpheme_dict.pickle.

    Usage:
        analyzer = get_morpheme_analyzer()
        analyzer.has_prefix("привычка", "при")   # True
        analyzer.has_prefix("природа", "при")    # False (per Tikhonov)
        analyzer.word_is_known("несчастье")       # True
        analyzer.word_is_known("некошка")          # False
        analyzer.get_stress("церемония")          # 5
        analyzer.morpheme_at_char("церемония", 0) # ("церемони", "ROOT")
    """

    # Unified dict type codes → old-style type names
    _UNIFIED_TYPE_MAP = {"R": "ROOT", "P": "PREF", "S": "SUFF", "E": "END", "L": "LINK"}

    def __init__(self) -> None:
        self._unified: dict[str, dict] | None = None
        self._legacy_dict: dict[str, list[str]] | None = None
        self._pymorphy = None

    @property
    def unified(self) -> dict[str, dict]:
        if self._unified is None:
            self._unified = get_unified_dict()
        return self._unified

    @property
    def legacy_dict(self) -> dict[str, list[str]]:
        if self._legacy_dict is None:
            self._legacy_dict = get_morpheme_dict()
        return self._legacy_dict

    @property
    def pymorphy(self):
        if self._pymorphy is None:
            self._pymorphy = get_morph_analyzer()
        return self._pymorphy

    def get_morphemes(self, word: str) -> list[tuple[str, str]] | None:
        """Parse morphemes into [(text, type), ...].

        Returns None if word not in dictionary.
        Types: PREF, ROOT, SUFF, END, LINK.
        """
        w = word.lower()

        # Try unified dict first
        entry = self.unified.get(w)
        if entry and "m" in entry:
            return [
                (text, self._UNIFIED_TYPE_MAP.get(typ, "ROOT"))
                for text, typ in entry["m"]
            ]

        # Fall back to legacy morpheme_dict.pickle
        legacy = self.legacy_dict.get(w)
        if not legacy or not isinstance(legacy, list) or legacy == [""]:
            return None
        result = []
        for m in legacy:
            if not isinstance(m, str) or not m:
                continue
            if "\n" in m or ("=" in m and len(m) > 10):
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

    def get_stress(self, word: str) -> int:
        """Get stress position for word. Returns -1 if unknown."""
        entry = self.unified.get(word.lower())
        if entry:
            return entry.get("s", -1)
        return -1

    def surface_morpheme_spans(
        self,
        word: str,
    ) -> list[tuple[int, str, str]] | None:
        """Return SURFACE-ALIGNED morpheme spans as [(offset, text, type), ...].

        Dict morpheme strings may contain annotation characters ('-', 'j',
        parentheses) that are not part of the surface spelling — summing
        raw lengths misaligns every morpheme after the first annotated one
        (e.g. the 2-char SUFF "о-" in "белокаменный" shifted the "камен"
        root one position right). Annotation chars are stripped from each
        morpheme, and every span is verified in place against the surface
        word: at the first divergence the remaining spans are dropped,
        since their offsets can no longer be trusted. Divergence happens
        when an entry stores another inflection's morphemes ("цыпочки"
        carries the singular's ending "а") or trailing junk morphemes
        ("цирк" carries a spurious link "и") — the stem spans before the
        divergence are still correctly aligned and kept; callers treat the
        uncovered tail as END. Returns None (unknown) when no span at all
        matches the surface.
        """
        w = word.lower()
        morphemes = self.get_morphemes(w)
        if morphemes is None:
            return None
        spans: list[tuple[int, str, str]] = []
        offset = 0
        for text, typ in morphemes:
            surface_text = _ANNOTATION_CHARS_RE.sub("", text)
            if not surface_text:
                continue
            if w[offset : offset + len(surface_text)] != surface_text:
                break
            spans.append((offset, surface_text, typ))
            offset += len(surface_text)
        return spans or None

    def morpheme_at_char(
        self,
        word: str,
        char_pos: int,
        lemma: str | None = None,
    ) -> tuple[str, str] | None:
        """Return (morpheme_text, type) containing the character at char_pos.

        Tries exact word first, then lemma (morpheme structure of root/prefix
        is stable across inflections — only the ending changes). Offsets are
        surface-aligned (see surface_morpheme_spans); the returned text is
        the surface spelling of the morpheme, annotation chars stripped.

        Returns None if word not in dictionary (or its dict entry cannot be
        aligned to the surface string).
        """
        spans = self.surface_morpheme_spans(word)
        if spans is None and lemma:
            spans = self.surface_morpheme_spans(lemma)
        if spans is None:
            return None
        for offset, text, typ in spans:
            if offset <= char_pos < offset + len(text):
                return (text, typ)
        # char_pos beyond span coverage (inflected ending differs from the
        # lemma's, or a truncated dict entry) — treat as ending
        return (word[char_pos:], "END")

    def char_in_morpheme_type(
        self,
        word: str,
        char_pos: int,
        morph_type: str,
        lemma: str | None = None,
    ) -> bool | None:
        """Check if char at position is inside a morpheme of given type.

        Returns None if word not in dictionary, True/False otherwise.
        """
        result = self.morpheme_at_char(word, char_pos, lemma)
        if result is None:
            return None
        return result[1] == morph_type

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
