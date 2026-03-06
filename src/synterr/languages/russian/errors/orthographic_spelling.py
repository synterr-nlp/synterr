"""Russian orthographic spelling handler — morpheme-level spelling rules.

Covers Rozental suffix/prefix spelling rules that depend on morpheme structure,
POS, or conjugation class — distinct from the phonetic spelling handler.

9 subtypes covering 9 LoRuGEC rules:
- pre_pri: пре-/при- prefix confusion (§31–32)
- y_i_after_prefix: ы/и after consonant-ending prefix (§34)
- suffix_enk_onk: -еньк/-оньк in nouns (§38)
- suffix_insk_ensk: -инск/-енск in adjectives (§40)
- suffix_its_ets: -иц/-ец in neuter nouns (§38)
- suffix_ek_ik: -ек/-ик in nouns (§38)
- participle_suffix: conjugation-dependent participle suffixes (§51)
- vowel_after_ts: vowels after ц (§35)
- vowel_after_sibilant: ё/о/ю after ш,щ,ж,ч (§35)
"""

from __future__ import annotations

import re
import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.resources import get_morpheme_analyzer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# пре-/при- prefix confusion
# =============================================================================

_PRE_PRI_RE = re.compile(r'^(пре|при)', re.IGNORECASE)


# =============================================================================
# ы/и after prefix
# Russian prefixes: after consonant ending, и→ы (except меж-, сверх-, foreign)
# Foreign prefixes: keep и (error = using ы)
# =============================================================================

# Russian prefixes where и→ы is correct (error = keeping и)
_RU_PREFIXES_YI = [
    "без", "вз", "из", "над", "об", "от", "под", "пред", "раз", "с", "через",
]
# Prefixes where и stays (error = using ы)
_FOREIGN_PREFIXES_I = [
    "сверх", "меж",  # Russian exceptions
    "транс", "контр", "пост", "суб", "супер", "дез", "пан",  # Foreign
    "спорт", "фин", "гос", "полит",  # Compound abbreviations
    "двух", "трёх", "трех", "четырёх", "четырех",  # Numeral prefixes
]

_ALL_PREFIXES_YI = _RU_PREFIXES_YI + _FOREIGN_PREFIXES_I


# =============================================================================
# Participle suffix swaps (conjugation-dependent)
# =============================================================================

_PARTICIPLE_SWAPS = [
    # Active present: 1st conj ↔ 2nd conj (both directions)
    ("ущ", "ащ"),
    ("ащ", "ущ"),
    ("ющ", "ящ"),
    ("ящ", "ющ"),
    # Passive present: 1st conj ↔ 2nd conj (both directions)
    ("ем", "им"),
    ("им", "ем"),
    # Past passive: swap vowel before нн/н (both directions)
    ("енн", "янн"),
    ("янн", "енн"),
    ("анн", "енн"),
]

# =============================================================================
# Vowels after ц
# =============================================================================

_TS_VOWEL_SWAPS = {
    "о": "е", "е": "о",  # stressed о, unstressed е
    "и": "ы", "ы": "и",  # и in root/suffix, ы in -ын/endings
    "ё": "о", # ё→о after ц
}

# =============================================================================
# Vowels after sibilants (ш, щ, ж, ч)
# =============================================================================

_SIBILANTS = set("шщжчШЩЖЧ")

_SIBILANT_VOWEL_SWAPS = {
    "ё": "о", "о": "ё",
    # ю↔у removed: only applies to 3 loanwords (жюри, брошюра, парашют)
    # and produces impossible errors on native words (чудо→чюдо, шутка→шютка)
}


class OrthographicSpellingHandler:
    """Morpheme-level spelling errors: suffixes, prefixes, post-sibilant vowels.

    Unlike the phonetic SpellingErrorHandler, these errors depend on
    morpheme boundaries, POS, or conjugation class.
    """

    name = "orthographic_spelling"
    subtypes = [
        "pre_pri",
        "y_i_after_prefix",
        "suffix_enk_onk",
        "suffix_insk_ensk",
        "suffix_its_ets",
        "suffix_ek_ik",
        "participle_suffix",
        "vowel_after_ts",
        "vowel_after_sibilant",
    ]
    category = "SPELL"
    changes_length = False

    DEFAULT_WEIGHTS = {
        "pre_pri": 15,
        "y_i_after_prefix": 15,
        "suffix_enk_onk": 10,
        "suffix_insk_ensk": 10,
        "suffix_its_ets": 8,
        "suffix_ek_ik": 10,
        "participle_suffix": 12,
        "vowel_after_ts": 10,
        "vowel_after_sibilant": 10,
    }

    def __init__(self):
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if not token.text.isalpha() or len(token.text) < 3:
            return False
        text_lower = token.text.lower()

        # Quick checks for any applicable subtype
        if _PRE_PRI_RE.match(text_lower) and len(text_lower) > 4:
            return True
        for pfx in _ALL_PREFIXES_YI:
            if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
                after = text_lower[len(pfx)]
                if after in ("и", "ы"):
                    return True
        if "еньк" in text_lower or "оньк" in text_lower:
            return True
        if "инск" in text_lower or "енск" in text_lower:
            return True
        if _can_its_ets(text_lower):
            return True
        if _can_ek_ik(text_lower):
            return True
        if token.pos in ("VERB", "ADJ") and _has_participle_pattern(text_lower):
            return True
        if "ц" in text_lower:
            return True
        if any(c in text_lower for c in "шщжч"):
            return True
        return False

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        text_lower = word.lower()

        # Collect applicable subtypes
        candidates: list[tuple[str, float]] = []

        if _PRE_PRI_RE.match(text_lower) and len(text_lower) > 4:
            candidates.append(("pre_pri", self._weights["pre_pri"]))

        if _can_yi_swap(text_lower):
            candidates.append(("y_i_after_prefix", self._weights["y_i_after_prefix"]))

        if "еньк" in text_lower or "оньк" in text_lower:
            candidates.append(("suffix_enk_onk", self._weights["suffix_enk_onk"]))

        if "инск" in text_lower or "енск" in text_lower:
            candidates.append(("suffix_insk_ensk", self._weights["suffix_insk_ensk"]))

        if _can_its_ets(text_lower):
            candidates.append(("suffix_its_ets", self._weights["suffix_its_ets"]))

        if _can_ek_ik(text_lower):
            candidates.append(("suffix_ek_ik", self._weights["suffix_ek_ik"]))

        if token.pos in ("VERB", "ADJ") and _has_participle_pattern(text_lower):
            candidates.append(("participle_suffix", self._weights["participle_suffix"]))

        if _can_ts_vowel(text_lower):
            candidates.append(("vowel_after_ts", self._weights["vowel_after_ts"]))

        if _can_sibilant_vowel(text_lower):
            candidates.append(("vowel_after_sibilant", self._weights["vowel_after_sibilant"]))

        if not candidates:
            return None

        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        corrupted = _apply_subtype(chosen, word, text_lower)
        if corrupted is None or corrupted == word:
            return None

        sentence[idx] = corrupted
        return ErrorResult(
            error_type=f"orthographic_spelling_{chosen}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Subtype applicability checks
# =============================================================================

def _can_yi_swap(text_lower: str) -> bool:
    for pfx in _ALL_PREFIXES_YI:
        if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
            after = text_lower[len(pfx)]
            if after in ("и", "ы"):
                return True
    return False


def _can_its_ets(text_lower: str) -> bool:
    # Nouns with -ице/-ецо/-ица/-еца patterns (ц only, not ч)
    return bool(re.search(r"[ие]ц[еиоа]", text_lower))


def _can_ek_ik(text_lower: str) -> bool:
    return bool(re.search(r"[еи]к[аеуоиы]?$", text_lower))


def _can_ts_vowel(text_lower: str) -> bool:
    for i, c in enumerate(text_lower):
        if c == "ц" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _TS_VOWEL_SWAPS:
                return True
    return False


def _can_sibilant_vowel(text_lower: str) -> bool:
    for i, c in enumerate(text_lower):
        if c in "шщжч" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _SIBILANT_VOWEL_SWAPS:
                return True
    return False


_PARTICIPLE_ENDING_RE = re.compile(
    r"(ущ|ющ|ащ|ящ)(ий|ая|ее|ие|его|ей|ему|им|их|ими|ем)(ся)?$"  # active present
    r"|(ем|им)(ый|ая|ое|ые|ого|ой|ому|ым|ых|ыми|ом)$"  # passive present
    r"|(енн|янн|анн)(ый|ая|ое|ые|ого|ой|ому|ым|ых|ыми|ом)$"  # passive past
)


def _has_participle_pattern(text_lower: str) -> bool:
    if not _PARTICIPLE_ENDING_RE.search(text_lower):
        return False
    # Verify via morpheme dict: the matched suffix must be a real suffix
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return True  # Unknown word — allow (could be a rare participle)
    # Check if any participle suffix is present in the morpheme analysis
    participle_suffixes = {"ущ", "ющ", "ащ", "ящ", "ем", "им", "енн", "янн", "анн", "нн"}
    return bool(participle_suffixes & set(suffixes))


# =============================================================================
# Corruption logic per subtype
# =============================================================================

def _apply_subtype(subtype: str, word: str, text_lower: str) -> str | None:
    if subtype == "pre_pri":
        return _swap_pre_pri(word, text_lower)
    elif subtype == "y_i_after_prefix":
        return _swap_yi_prefix(word, text_lower)
    elif subtype == "suffix_enk_onk":
        return _swap_enk_onk(word, text_lower)
    elif subtype == "suffix_insk_ensk":
        return _swap_insk_ensk(word, text_lower)
    elif subtype == "suffix_its_ets":
        return _swap_its_ets(word, text_lower)
    elif subtype == "suffix_ek_ik":
        return _swap_ek_ik(word, text_lower)
    elif subtype == "participle_suffix":
        return _swap_participle(word, text_lower)
    elif subtype == "vowel_after_ts":
        return _swap_ts_vowel(word, text_lower)
    elif subtype == "vowel_after_sibilant":
        return _swap_sibilant_vowel(word, text_lower)
    return None


def _swap_pre_pri(word: str, text_lower: str) -> str | None:
    """Swap пре↔при prefix — only if morpheme dict confirms a real prefix."""
    m = _PRE_PRI_RE.match(text_lower)
    if not m:
        return None
    prefix_lower = word[:3].lower()
    # Check morpheme dict: only swap if the word actually has пре-/при- prefix
    analyzer = get_morpheme_analyzer()
    has_pfx = analyzer.has_prefix(text_lower, prefix_lower)
    if has_pfx is False:
        return None  # Not a prefix (природа, прекрасный)
    if has_pfx is None:
        # Unknown word in morpheme dict — skip to avoid gibberish (президент etc.)
        return None
    prefix = word[:3]
    if prefix_lower == "пре":
        new_prefix = _match_case("при", prefix)
    elif prefix_lower == "при":
        new_prefix = _match_case("пре", prefix)
    else:
        return None
    return new_prefix + word[3:]


def _swap_yi_prefix(word: str, text_lower: str) -> str | None:
    """Swap и↔ы after prefix boundary — verified via morpheme dict."""
    analyzer = get_morpheme_analyzer()
    for pfx in sorted(_ALL_PREFIXES_YI, key=len, reverse=True):
        if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
            pos = len(pfx)
            char = word[pos]
            char_lower = char.lower()
            if char_lower not in ("и", "ы"):
                continue
            # Verify this is a real prefix, not part of the root
            has_pfx = analyzer.has_prefix(text_lower, pfx)
            if has_pfx is False:
                continue  # Not a prefix (сирень, обида)
            if has_pfx is None and len(pfx) <= 2:
                continue  # Short prefix (с, об, из) on unknown word — too risky
            if char_lower == "и":
                new_char = "Ы" if char.isupper() else "ы"
            else:
                new_char = "И" if char.isupper() else "и"
            return word[:pos] + new_char + word[pos + 1:]
    return None


def _swap_enk_onk(word: str, text_lower: str) -> str | None:
    """Swap -еньк↔-оньк."""
    for pattern, replacement in [("еньк", "оньк"), ("оньк", "еньк")]:
        idx = text_lower.find(pattern)
        if idx >= 0:
            # Swap the vowel before ньк
            orig_vowel = word[idx]
            new_vowel = replacement[0]
            if orig_vowel.isupper():
                new_vowel = new_vowel.upper()
            return word[:idx] + new_vowel + word[idx + 1:]
    return None


def _swap_insk_ensk(word: str, text_lower: str) -> str | None:
    """Swap -инск↔-енск."""
    for pattern, replacement_vowel in [("инск", "е"), ("енск", "и")]:
        idx = text_lower.find(pattern)
        if idx >= 0:
            orig_vowel = word[idx]
            new_vowel = replacement_vowel.upper() if orig_vowel.isupper() else replacement_vowel
            return word[:idx] + new_vowel + word[idx + 1:]
    return None


def _swap_its_ets(word: str, text_lower: str) -> str | None:
    """Swap vowel before ц in suffix patterns: -ице↔-ецо, -ица↔-еца, -ьице↔-ьеце."""
    # Find ц and check the vowel before it
    for i, c in enumerate(text_lower):
        if c == "ц" and i > 0:
            prev = text_lower[i - 1]
            if prev == "и":
                new_v = "Е" if word[i - 1].isupper() else "е"
                return word[:i - 1] + new_v + word[i:]
            elif prev == "е":
                new_v = "И" if word[i - 1].isupper() else "и"
                return word[:i - 1] + new_v + word[i:]
    return None


def _swap_ek_ik(word: str, text_lower: str) -> str | None:
    """Swap -ек↔-ик in diminutive suffixes — verified via morpheme dict."""
    m = re.search(r"[еи]к[аеуоиы]?$", text_lower)
    if not m:
        return None
    # Verify -ик/-ек is a real suffix, not part of the root (человек, кулик)
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is not None and "ик" not in suffixes and "ек" not in suffixes and "к" not in suffixes:
        return None  # No matching suffix (человек, парик, кулик)
    if suffixes is None:
        # Unknown word — skip to avoid false positives
        return None
    pos = m.start()
    orig_vowel = word[pos]
    orig_lower = orig_vowel.lower()
    if orig_lower == "е":
        new_vowel = "И" if orig_vowel.isupper() else "и"
    elif orig_lower == "и":
        new_vowel = "Е" if orig_vowel.isupper() else "е"
    else:
        return None
    return word[:pos] + new_vowel + word[pos + 1:]


def _swap_participle(word: str, text_lower: str) -> str | None:
    """Swap conjugation-dependent participle suffix vowels."""
    for orig, target in _PARTICIPLE_SWAPS:
        idx = text_lower.find(orig)
        if idx >= 0:
            # Build replacement preserving case
            replacement = ""
            for j, ch in enumerate(target):
                src_ch = word[idx + j] if idx + j < len(word) else ch
                replacement += ch.upper() if src_ch.isupper() else ch
            return word[:idx] + replacement + word[idx + len(orig):]
    return None


def _swap_ts_vowel(word: str, text_lower: str) -> str | None:
    """Swap vowel after ц."""
    for i, c in enumerate(text_lower):
        if c == "ц" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _TS_VOWEL_SWAPS:
                new_c = _TS_VOWEL_SWAPS[next_c]
                pos = i + 1
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1:]
    return None


def _swap_sibilant_vowel(word: str, text_lower: str) -> str | None:
    """Swap vowel after sibilant (ш,щ,ж,ч)."""
    for i, c in enumerate(text_lower):
        if c in "шщжч" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _SIBILANT_VOWEL_SWAPS:
                new_c = _SIBILANT_VOWEL_SWAPS[next_c]
                pos = i + 1
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1:]
    return None


def _match_case(target: str, source: str) -> str:
    """Match case pattern of source to target."""
    result = []
    for i, ch in enumerate(target):
        if i < len(source) and source[i].isupper():
            result.append(ch.upper())
        else:
            result.append(ch)
    return "".join(result)
