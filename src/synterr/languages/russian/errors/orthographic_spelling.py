"""Russian orthographic spelling handler — morpheme-level spelling rules.

Covers Rozental suffix/prefix spelling rules that depend on morpheme structure,
POS, or conjugation class — distinct from the phonetic spelling handler.

10 subtypes covering 10 LoRuGEC rules:
- pre_pri: пре-/при- prefix confusion (§31–32)
- y_i_after_prefix: ы/и after consonant-ending prefix (§34)
- suffix_enk_onk: -еньк/-оньк in nouns (§38)
- suffix_insk_ensk: -инск/-енск in adjectives (§40)
- suffix_its_ets: -иц/-ец in neuter nouns (§38)
- suffix_ek_ik: -ек/-ик in nouns (§38)
- participle_suffix: conjugation-dependent participle suffixes (§51)
- vowel_after_ts: vowels after ц (§35)
- vowel_after_sibilant: ё/о/ю after ш,щ,ж,ч (§35)
- nn_suffix: н/нн in adjective/participle suffixes (§39–40)
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
    from synterr.languages.russian.resources import MorphemeAnalyzer


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


# =============================================================================
# н/нн in adjective/participle suffixes (§39-40)
# =============================================================================

# Regex to find нн in word (candidate for нн→н reduction)
_NN_RE = re.compile(r"нн")

# Regex to find suffix patterns where single н may need doubling
# -ан-/-ян-/-ин- suffixes that should have 1н (error = adding 2нн)
_SINGLE_N_SUFFIX_RE = re.compile(r"(ан|ян|ин)([а-яё]*[ыоеи]й|[а-яё]*[аяое][яе]?)$")

# Exception words that have НН despite -ян- suffix
_NN_EXCEPTIONS = {"деревянный", "оловянный", "стеклянный"}

# Words that must keep single н (exception to general rules)
_SINGLE_N_EXCEPTIONS = {
    "багряный", "пряный", "пьяный", "рдяный", "румяный",
    "ветреный", "зелёный", "зеленый", "юный", "свиной",
    "синий",
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
        "nn_suffix",
    ]
    category = "SPELL"
    changes_length = False

    DEFAULT_WEIGHTS = {
        "pre_pri": 13,
        "y_i_after_prefix": 13,
        "suffix_enk_onk": 8,
        "suffix_insk_ensk": 8,
        "suffix_its_ets": 7,
        "suffix_ek_ik": 8,
        "participle_suffix": 10,
        "vowel_after_ts": 8,
        "vowel_after_sibilant": 8,
        "nn_suffix": 17,
    }

    def __init__(self):
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self._analyzer = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            self._analyzer = get_morpheme_analyzer()
        return self._analyzer

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
        if token.pos != "PROPN" and ("инск" in text_lower or "енск" in text_lower):
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
        if token.pos == "ADJ" and _can_nn_swap(text_lower):
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

        if token.pos != "PROPN" and _can_insk_ensk(text_lower):
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

        if token.pos == "ADJ" and _can_nn_swap(text_lower):
            candidates.append(("nn_suffix", self._weights["nn_suffix"]))

        if not candidates:
            return None

        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        # Look up stress: try exact form first, then lemma
        analyzer = self.analyzer
        lemma = token.lemma.lower() if token.lemma else text_lower
        stress_pos = analyzer.get_stress(text_lower)
        if stress_pos < 0:
            stress_pos = analyzer.get_stress(lemma)
            if stress_pos >= 0:
                stressed_syllable = _stressed_syllable(lemma, stress_pos)
            else:
                stressed_syllable = -1
        else:
            stressed_syllable = _stressed_syllable(text_lower, stress_pos)

        corrupted = _apply_subtype(chosen, word, text_lower, stressed_syllable, analyzer, lemma)
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


def _can_insk_ensk(text_lower: str) -> bool:
    """Check if word has -инск-/-енск- as a real suffix (not root-internal)."""
    if "инск" not in text_lower and "енск" not in text_lower:
        return False
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return False
    # Morpheme dict segments as ["ин", "ск"] or ["ен-", "ск"] — check for
    # suffix chain containing ин/ен + ск
    clean = [s.strip("-") for s in suffixes]
    has_sk = "ск" in clean
    has_in_en = any(s in ("ин", "ен") for s in clean)
    return has_sk and has_in_en


def _can_its_ets(text_lower: str) -> bool:
    # Nouns with -ице/-ецо/-ица/-еца patterns — only if suffix contains иц/ец
    if not re.search(r"[ие]ц[еиоа]", text_lower):
        return False
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return False  # Unknown word — skip to avoid false positives
    return any(s in ("иц", "ец", "ице", "ица", "ецо", "еца") for s in suffixes)


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

_VOWELS_LOWER = set("аеёиоуыэюя")


def _stressed_syllable(word: str, stress_pos: int) -> int:
    """Return 0-indexed syllable number of the stressed vowel."""
    syllable = -1
    for i, c in enumerate(word.lower()):
        if c in _VOWELS_LOWER:
            syllable += 1
            if i >= stress_pos:
                return syllable
    return syllable


def _syllable_at_pos(word: str, char_pos: int) -> int:
    """Return 0-indexed syllable number for a character position."""
    syllable = -1
    for i, c in enumerate(word.lower()):
        if c in _VOWELS_LOWER:
            syllable += 1
        if i >= char_pos:
            return syllable
    return syllable


def _apply_subtype(
    subtype: str, word: str, text_lower: str,
    stressed_syllable: int = -1, analyzer: MorphemeAnalyzer | None = None,
    lemma: str | None = None,
) -> str | None:
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
        return _swap_ts_vowel(word, text_lower, stressed_syllable, analyzer, lemma)
    elif subtype == "vowel_after_sibilant":
        return _swap_sibilant_vowel(word, text_lower, stressed_syllable, analyzer, lemma)
    elif subtype == "nn_suffix":
        return _swap_nn(word, text_lower)
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
    # Verify suffix contains иц/ец via morpheme dict
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return None
    has_suffix = any(s in ("иц", "ец", "ице", "ица", "ецо", "еца") for s in suffixes)
    if not has_suffix:
        return None
    # Find ц preceded by и/е and swap
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


def _swap_ts_vowel(
    word: str, text_lower: str, stressed_syllable: int = -1,
    analyzer: MorphemeAnalyzer | None = None, lemma: str | None = None,
) -> str | None:
    """Swap vowel after ц.

    §35: After ц, о under stress / е without stress (suffixes/endings).
    Skip swap if:
    - the target vowel is stressed (unambiguous)
    - both ц and the vowel are inside the root (not a suffix/ending rule)
    """
    for i, c in enumerate(text_lower):
        if c == "ц" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _TS_VOWEL_SWAPS:
                pos = i + 1
                # Skip if this vowel is on the stressed syllable
                if stressed_syllable >= 0:
                    vowel_syllable = _syllable_at_pos(text_lower, pos)
                    if vowel_syllable == stressed_syllable:
                        continue
                # Skip if both ц and the vowel are in the root
                # §35 applies to suffixes/endings only (цирк is root, not target)
                if analyzer is not None:
                    ts_type = analyzer.char_in_morpheme_type(text_lower, i, "ROOT", lemma)
                    vowel_type = analyzer.char_in_morpheme_type(text_lower, pos, "ROOT", lemma)
                    if ts_type is True and vowel_type is True:
                        continue  # Both in root — skip (церемония, цирк)
                new_c = _TS_VOWEL_SWAPS[next_c]
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1:]
    return None


def _swap_sibilant_vowel(
    word: str, text_lower: str, stressed_syllable: int = -1,
    analyzer: MorphemeAnalyzer | None = None, lemma: str | None = None,
) -> str | None:
    """Swap vowel after sibilant (ш,щ,ж,ч).

    §35: After sibilants, о/ё are distinguished by morpheme position:
    - suffix/ending: о under stress (девчонка, горячо)
    - root: ё (шёпот, жёлтый) — but learners confuse freely
    Skip when both sibilant and vowel are in the root AND the vowel is
    unstressed (no real confusion — e.g., "шоколад" is just the root).
    Allow when sibilant is in root but vowel crosses into suffix/ending.
    """
    for i, c in enumerate(text_lower):
        if c in "шщжч" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _SIBILANT_VOWEL_SWAPS:
                pos = i + 1
                # Skip if both sibilant and vowel are deep in the root
                # (шоколад, жокей — no ё/о confusion)
                # But allow root-boundary cases (шёпот — ё in root IS confused)
                if analyzer is not None:
                    sib_in_root = analyzer.char_in_morpheme_type(text_lower, i, "ROOT", lemma)
                    vowel_in_root = analyzer.char_in_morpheme_type(text_lower, pos, "ROOT", lemma)
                    if sib_in_root is True and vowel_in_root is True:
                        # Both in root — only allow if vowel is stressed
                        # (stressed root ё/о IS a real confusion: шёпот↔шопот)
                        if stressed_syllable >= 0:
                            vowel_syllable = _syllable_at_pos(text_lower, pos)
                            if vowel_syllable != stressed_syllable:
                                continue  # Unstressed root vowel — skip
                new_c = _SIBILANT_VOWEL_SWAPS[next_c]
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1:]
    return None


def _can_nn_swap(text_lower: str) -> bool:
    """Check if word has нн that can be reduced or н that can be doubled."""
    if text_lower in _SINGLE_N_EXCEPTIONS:
        return False
    # Has нн → can reduce to н
    if _NN_RE.search(text_lower):
        return True
    # Has suffix pattern with single н → can double
    if _SINGLE_N_SUFFIX_RE.search(text_lower):
        return True
    return False


def _swap_nn(word: str, text_lower: str) -> str | None:
    """Swap н↔нн in adjective suffix.

    Direction 1 (67%): нн→н (государственный → государственый)
    Direction 2 (33%): н→нн (кожаный → кожанный)
    """
    analyzer = get_morpheme_analyzer()

    # Direction 1: reduce нн→н
    m = _NN_RE.search(text_lower)
    if m:
        pos = m.start()
        # Verify via morpheme dict that нн is in a suffix (not root)
        suffixes = analyzer.get_suffixes(text_lower)
        if suffixes is not None:
            has_nn_suffix = any("нн" in s or s == "н" for s in suffixes)
            if not has_nn_suffix:
                # нн might be at morpheme boundary (root-н + suffix-н)
                # Still a valid target for corruption
                pass
        # Remove one н
        corrupted = word[:pos] + word[pos + 1:]
        if corrupted != word:
            return corrupted

    # Direction 2: double н→нн
    suffix_m = _SINGLE_N_SUFFIX_RE.search(text_lower)
    if suffix_m:
        # Don't double exception words
        if text_lower in _SINGLE_N_EXCEPTIONS:
            return None
        # Find the single н in the suffix and double it
        suffix_start = suffix_m.start()
        suffix_text = suffix_m.group(1)  # "ан", "ян", or "ин"
        # The н is at suffix_start + len(suffix_text) - 1
        n_pos = suffix_start + len(suffix_text) - 1
        corrupted = word[:n_pos + 1] + "н" + word[n_pos + 1:]
        if corrupted != word:
            return corrupted

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
