"""Russian spelling error handler using phonetic rules.

Ported from gector/code/synthetic_dataset_generation/phonetic_errors.py

Error types:
1. Vowel reduction (аканье/иканье) - unstressed vowel confusion (requires stress_dict)
2. Consonant devoicing - voiced/voiceless confusion at word boundaries
3. тся/ться confusion - most common Russian spelling error
4. Consonant cluster simplification - сч→щ, стн→сн, etc.
5. Double consonant errors
6. Soft sign errors - deletion, ъ→ь confusion
7. Keyboard typos - ЙЦУКЕН layout adjacency
"""

from __future__ import annotations

import random as random_module
from dataclasses import dataclass
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


@dataclass
class PhoneticError:
    """Result of phonetic corruption."""

    original: str
    corrupted: str
    error_subtype: str
    position: int = -1


# =============================================================================
# VOWEL REDUCTION (аканье/иканье)
# In unstressed syllables, vowels reduce and become confusable
# =============================================================================

VOWEL_REDUCTION = {
    "о": ["а"],
    "а": ["о"],
    "е": ["и"],
    "и": ["е"],
    "я": ["е", "и"],
    "э": ["е", "и"],
}

VOWEL_REDUCTION_UPPER = {
    "О": ["А"],
    "А": ["О"],
    "Е": ["И"],
    "И": ["Е"],
    "Я": ["Е", "И"],
    "Э": ["Е", "И"],
}

VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")

# =============================================================================
# CONSONANT DEVOICING
# Voiced consonants written as voiceless at word-final position.
# This reflects the Russian phonetic rule where final voiced consonants
# are pronounced voiceless (город → [горот]), leading to spelling errors.
# Note: Only voiced → voiceless direction. The reverse (voicing) is rare.
# =============================================================================

VOICED_TO_VOICELESS = {
    "б": "п",
    "в": "ф",
    "г": "к",
    "д": "т",
    "ж": "ш",
    "з": "с",
    "Б": "П",
    "В": "Ф",
    "Г": "К",
    "Д": "Т",
    "Ж": "Ш",
    "З": "С",
}

# =============================================================================
# CLASSIC SPELLING CONFUSIONS
# =============================================================================

# -тся/-ться confusion (most common Russian spelling error)
TSA_PATTERNS = {
    "ться": "тся",  # infinitive written as 3rd person
    "тся": "ться",  # 3rd person written as infinitive
}

# Consonant cluster simplification/confusion
CLUSTER_CONFUSIONS = {
    "сч": "щ",  # счастье → щастье
    "зч": "щ",  # возчик → вощик
    "сш": "ш",  # сшить → шить (hypercorrection)
    "зж": "ж",  # изжога → ижога
    "стн": "сн",  # честный → чесный (silent consonant)
    "стл": "сл",  # счастливый → счасливый
    "здн": "зн",  # поздний → позний
    "рдц": "рц",  # сердце → серце
    "лнц": "нц",  # солнце → сонце
}

# =============================================================================
# PREFIX VOICING
# Prefixes ending in з/с follow spelling rules based on the following consonant:
# - из-, раз-, без-, воз-, низ-, чрез- before voiced consonants and vowels
# - ис-, рас-, бес-, вос-, нис-, черес- before voiceless consonants
# Learners often use the wrong form.
# =============================================================================

# Voiced prefix → voiceless prefix (used before voiceless consonants)
PREFIX_VOICED_TO_VOICELESS = {
    "из": "ис",
    "раз": "рас",
    "без": "бес",
    "воз": "вос",
    "низ": "нис",
    "чрез": "черес",
    # Uppercase variants
    "Из": "Ис",
    "Раз": "Рас",
    "Без": "Бес",
    "Воз": "Вос",
    "Низ": "Нис",
    "Чрез": "Черес",
}

# Voiceless prefix → voiced prefix (used before voiced consonants/vowels)
PREFIX_VOICELESS_TO_VOICED = {v: k for k, v in PREFIX_VOICED_TO_VOICELESS.items()}

# Consonants that trigger voiceless prefix form
VOICELESS_CONSONANTS = set("пфктшсхцчщПФКТШСХЦЧЩ")

# Double consonant errors (common in borrowed words)
DOUBLE_CONSONANTS = {
    "нн": "н",
    "сс": "с",
    "лл": "л",
    "мм": "м",
    "пп": "п",
    "рр": "р",
    "тт": "т",
    "фф": "ф",
    "кк": "к",
}

# =============================================================================
# ЙЦУКЕН KEYBOARD LAYOUT - explicit adjacency map
# Accounts for staggered rows on physical keyboard
# =============================================================================

KEYBOARD_ADJACENT = {
    # Top row: ё й ц у к е н г ш щ з х ъ
    "ё": ["й", "1"],
    "й": ["ё", "ц", "ф", "ы"],
    "ц": ["й", "у", "ы", "в"],
    "у": ["ц", "к", "в", "а"],
    "к": ["у", "е", "а", "п"],
    "е": ["к", "н", "п", "р"],
    "н": ["е", "г", "р", "о"],
    "г": ["н", "ш", "о", "л"],
    "ш": ["г", "щ", "л", "д"],
    "щ": ["ш", "з", "д", "ж"],
    "з": ["щ", "х", "ж", "э"],
    "х": ["з", "ъ", "э"],
    "ъ": ["х"],
    # Middle row: ф ы в а п р о л д ж э
    "ф": ["й", "ц", "ы", "я"],
    "ы": ["й", "ц", "у", "ф", "в", "я", "ч"],
    "в": ["ц", "у", "к", "ы", "а", "ч", "с"],
    "а": ["у", "к", "е", "в", "п", "с", "м"],
    "п": ["к", "е", "н", "а", "р", "м", "и"],
    "р": ["е", "н", "г", "п", "о", "и", "т"],
    "о": ["н", "г", "ш", "р", "л", "т", "ь"],
    "л": ["г", "ш", "щ", "о", "д", "ь", "б"],
    "д": ["ш", "щ", "з", "л", "ж", "б", "ю"],
    "ж": ["щ", "з", "х", "д", "э", "ю"],
    "э": ["з", "х", "ж"],
    # Bottom row: я ч с м и т ь б ю
    "я": ["ф", "ы", "ч"],
    "ч": ["ы", "в", "я", "с"],
    "с": ["в", "а", "ч", "м"],
    "м": ["а", "п", "с", "и"],
    "и": ["п", "р", "м", "т"],
    "т": ["р", "о", "и", "ь"],
    "ь": ["о", "л", "т", "б"],
    "б": ["л", "д", "ь", "ю"],
    "ю": ["д", "ж", "б"],
}


class SpellingErrorHandler:
    """Russian spelling error handler using phonetic rules.

    Implements realistic Russian spelling errors based on actual phonetic
    and orthographic patterns. Requires stress dictionary for accurate
    vowel reduction.
    """

    name = "spelling"
    category = "SPELL"
    changes_length = False

    # Handler subtypes - mapped to schema tags via schema YAML
    subtypes = [
        "vowel_reduction",
        "devoicing",
        "prefix_voicing",
        "tsa_confusion",
        "cluster",
        "double_consonant",
        "keyboard",
        "soft_sign",
    ]

    # Default subtype weights (used if not overridden by config)
    DEFAULT_WEIGHTS = {
        "vowel_reduction": 30,
        "devoicing": 10,
        "prefix_voicing": 15,
        "tsa_confusion": 25,
        "cluster": 10,
        "double_consonant": 5,
        "keyboard": 3,
        "soft_sign": 2,
    }

    def __init__(self):
        self._stress_dict: dict[str, int] | None = None
        self._keyboard_upper: dict[str, list[str]] | None = None
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self._enabled_subtypes: set[str] | None = None  # None = all subtypes

    @property
    def weights(self) -> dict[str, float]:
        """Get current subtype weights."""
        return self._weights

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        """Set custom subtype weights from config.

        Args:
            weights: Dict mapping subtype names to weights.
                     Missing subtypes keep their default weights.
        """
        # Start with defaults, then override with provided weights
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        """Restrict handler to only use specific subtypes.

        Args:
            subtypes: Set of subtype names to enable, or None for all.
                      Example: {"vowel_reduction", "devoicing"}
        """
        if subtypes is not None:
            # Validate subtypes
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    @property
    def enabled_subtypes(self) -> set[str]:
        """Get currently enabled subtypes."""
        if self._enabled_subtypes is None:
            return set(self.subtypes)
        return self._enabled_subtypes

    @property
    def stress_dict(self) -> dict[str, int]:
        """Lazy-load stress dictionary."""
        if self._stress_dict is None:
            from synterr.languages.russian.resources import get_stress_dict

            self._stress_dict = get_stress_dict()
        return self._stress_dict

    @property
    def keyboard_adjacent(self) -> dict[str, list[str]]:
        """Get keyboard adjacency map with uppercase variants."""
        if self._keyboard_upper is None:
            self._keyboard_upper = dict(KEYBOARD_ADJACENT)
            for char, neighbors in list(KEYBOARD_ADJACENT.items()):
                if char.isalpha():
                    self._keyboard_upper[char.upper()] = [
                        n.upper() for n in neighbors if n.isalpha()
                    ]
        return self._keyboard_upper

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if spelling error can be applied at token index."""
        token = tokens[idx]
        return token.text.isalpha() and len(token.text) >= 2

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply spelling error."""
        rng = rng if rng is not None else random_module
        word = sentence[idx]

        result = self._corrupt(word, rng)
        if result is None or result.corrupted == word:
            return None

        sentence[idx] = result.corrupted

        return ErrorResult(
            error_type=f"spelling_{result.error_subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,  # Fixed: was idx, should be idx+1 for consistency
            original=word,
            corrupted=result.corrupted,
            fix_tag=f"$REPLACE_{word}",
        )

    def _corrupt(self, word: str, rng: Random | None = None) -> PhoneticError | None:
        """Corrupt a word with a spelling error."""
        rng = rng if rng is not None else random_module

        # Filter to enabled subtypes only
        methods = [m for m in self.weights if m in self.enabled_subtypes]
        if not methods:
            return None

        # Weighted shuffle - sort by random * weight for probabilistic ordering
        rng.shuffle(methods)
        methods.sort(key=lambda m: rng.random() * self.weights[m], reverse=True)

        for method_name in methods:
            result = self._apply_method(word, method_name, rng)
            if result and result.corrupted != word:
                return result

        return None

    def _apply_method(
        self, word: str, method: str, rng: Random | None = None
    ) -> PhoneticError | None:
        """Apply specific error method."""
        rng = rng if rng is not None else random_module
        if method == "vowel_reduction":
            return self._vowel_reduction(word, rng)
        elif method == "devoicing":
            return self._devoicing(word)
        elif method == "prefix_voicing":
            return self._prefix_voicing(word)
        elif method == "tsa_confusion":
            return self._tsa_confusion(word)
        elif method == "cluster":
            return self._cluster(word)
        elif method == "double_consonant":
            return self._double_consonant(word, rng)
        elif method == "keyboard":
            return self._keyboard_typo(word, rng)
        elif method == "soft_sign":
            return self._soft_sign(word)
        return None

    def _vowel_reduction(self, word: str, rng: Random | None = None) -> PhoneticError | None:
        """Apply vowel reduction error in unstressed syllables.

        Requires stress_dict to know which vowels are unstressed.
        """
        rng = rng if rng is not None else random_module
        vowel_map = {**VOWEL_REDUCTION, **VOWEL_REDUCTION_UPPER}

        # Get stress position
        word_lower = word.lower()
        stress_pos = self.stress_dict.get(word_lower, -1)

        # Without stress info, skip vowel reduction
        if stress_pos < 0:
            return None

        # Monosyllabic words have no reduction
        vowel_count = sum(1 for c in word_lower if c in VOWELS)
        if vowel_count <= 1:
            return None

        # Find positions with reducible vowels
        positions = []
        for i, char in enumerate(word):
            if char in vowel_map:
                # Skip last character (overlaps with case endings)
                if i == len(word) - 1:
                    continue
                # Skip the stressed vowel
                if i == stress_pos:
                    continue
                positions.append(i)

        if not positions:
            return None

        pos = rng.choice(positions)
        char = word[pos]
        replacement = rng.choice(vowel_map[char])
        corrupted = word[:pos] + replacement + word[pos + 1 :]

        return PhoneticError(word, corrupted, "vowel_reduction", pos)

    def _devoicing(self, word: str) -> PhoneticError | None:
        """Apply consonant devoicing error at word end.

        Simulates the common spelling error where word-final voiced consonants
        are written as voiceless (as they are pronounced). E.g., город → *горот.
        Only applies to words ending in voiced consonants.
        """
        if len(word) < 2:
            return None

        last_char = word[-1]

        # Skip if word ends in vowel or soft sign
        if last_char in "аеёиоуыэюяьъАЕЁИОУЫЭЮЯЬЪ":
            # Check second-to-last if last is soft sign
            if last_char in "ьъЬЪ" and len(word) > 2:
                check_pos = -2
                last_char = word[-2]
            else:
                return None
        else:
            check_pos = -1

        # Only devoice voiced consonants (not the reverse)
        if last_char in VOICED_TO_VOICELESS:
            replacement = VOICED_TO_VOICELESS[last_char]
            if check_pos == -1:
                corrupted = word[:-1] + replacement
            else:
                corrupted = word[:-2] + replacement + word[-1]

            return PhoneticError(word, corrupted, "devoicing", len(word) + check_pos)

        return None

    def _prefix_voicing(self, word: str) -> PhoneticError | None:
        """Apply prefix voicing/devoicing error.

        Russian prefixes из-/ис-, раз-/рас-, без-/бес-, etc. follow spelling rules:
        - Voiced form (з) before voiced consonants and vowels: разбить, избежать
        - Voiceless form (с) before voiceless consonants: расписать, исправить

        This simulates the common error of using the wrong prefix form:
        - *изправить (should be исправить)
        - *расбить (should be разбить)
        """
        word_lower = word.lower()

        # Try voiced prefixes (из-, раз-, etc.) - should be voiceless before voiceless
        for voiced_prefix, voiceless_prefix in PREFIX_VOICED_TO_VOICELESS.items():
            if word_lower.startswith(voiced_prefix.lower()):
                prefix_len = len(voiced_prefix)
                if prefix_len >= len(word):
                    continue

                # Get the consonant after the prefix
                next_char = word[prefix_len]

                # If next char is voiceless, this is actually correct usage
                # Error: using voiced prefix before voiceless consonant (which is wrong)
                # But we want to CREATE errors, so we swap to wrong form
                if next_char in VOICELESS_CONSONANTS:
                    # Word correctly uses voiced prefix before voiceless - no error possible
                    # (this would be a correct word that we shouldn't corrupt this way)
                    continue
                else:
                    # Word has voiced prefix before voiced/vowel (correct)
                    # Create error: swap to voiceless prefix (wrong)
                    # Match case of original prefix
                    if word.startswith(voiced_prefix):
                        new_prefix = voiceless_prefix
                    elif word.startswith(voiced_prefix.capitalize()):
                        new_prefix = voiceless_prefix.capitalize()
                    else:
                        new_prefix = voiceless_prefix.lower()

                    corrupted = new_prefix + word[prefix_len:]
                    return PhoneticError(word, corrupted, "prefix_voicing", 0)

        # Try voiceless prefixes (ис-, рас-, etc.) - should be voiced before voiced
        for voiceless_prefix, voiced_prefix in PREFIX_VOICELESS_TO_VOICED.items():
            if word_lower.startswith(voiceless_prefix.lower()):
                prefix_len = len(voiceless_prefix)
                if prefix_len >= len(word):
                    continue

                next_char = word[prefix_len]

                if next_char not in VOICELESS_CONSONANTS:
                    # Would be wrong usage (voiceless before voiced) - skip
                    continue
                else:
                    # Word has voiceless prefix before voiceless (correct)
                    # Create error: swap to voiced prefix (wrong)
                    if word.startswith(voiceless_prefix):
                        new_prefix = voiced_prefix
                    elif word.startswith(voiceless_prefix.capitalize()):
                        new_prefix = voiced_prefix.capitalize()
                    else:
                        new_prefix = voiced_prefix.lower()

                    corrupted = new_prefix + word[prefix_len:]
                    return PhoneticError(word, corrupted, "prefix_voicing", 0)

        return None

    def _tsa_confusion(self, word: str) -> PhoneticError | None:
        """Apply -тся/-ться confusion."""
        for pattern, replacement in TSA_PATTERNS.items():
            if word.endswith(pattern):
                corrupted = word[: -len(pattern)] + replacement
                return PhoneticError(word, corrupted, "tsa_confusion", len(word) - len(pattern))
        return None

    def _cluster(self, word: str) -> PhoneticError | None:
        """Apply consonant cluster simplification."""
        word_lower = word.lower()
        for pattern, replacement in CLUSTER_CONFUSIONS.items():
            if pattern in word_lower:
                pos = word_lower.find(pattern)
                orig_segment = word[pos : pos + len(pattern)]
                # Preserve case pattern
                if orig_segment.isupper():
                    repl = replacement.upper()
                elif orig_segment[0].isupper():
                    repl = (
                        replacement[0].upper() + replacement[1:]
                        if len(replacement) > 1
                        else replacement.upper()
                    )
                else:
                    repl = replacement
                corrupted = word[:pos] + repl + word[pos + len(pattern) :]
                return PhoneticError(word, corrupted, "cluster", pos)
        return None

    def _double_consonant(self, word: str, rng: Random | None = None) -> PhoneticError | None:
        """Remove one consonant from a double pair.

        Only reduces existing doubles (аппарат→апарат, коллега→колега).
        Adding doubles to words that don't have them produces gibberish
        (парки→паррки) and is not a real error pattern.
        """
        word_lower = word.lower()

        for double, single in DOUBLE_CONSONANTS.items():
            if double in word_lower:
                pos = word_lower.find(double)
                # Preserve case of retained character
                retained_char = single.upper() if word[pos].isupper() else single
                corrupted = word[:pos] + retained_char + word[pos + 2 :]
                return PhoneticError(word, corrupted, "double_consonant", pos)

        return None

    def _keyboard_typo(self, word: str, rng: Random | None = None) -> PhoneticError | None:
        """Generate keyboard adjacency typo."""
        rng = rng if rng is not None else random_module
        if len(word) < 2:
            return None

        positions = []
        for i, char in enumerate(word):
            if char.lower() in self.keyboard_adjacent or char in self.keyboard_adjacent:
                positions.append(i)

        if not positions:
            return None

        pos = rng.choice(positions)
        char = word[pos]

        if char in self.keyboard_adjacent:
            neighbors = self.keyboard_adjacent[char]
        elif char.lower() in self.keyboard_adjacent:
            neighbors = [
                n.upper() if char.isupper() else n for n in self.keyboard_adjacent[char.lower()]
            ]
        else:
            return None

        neighbors = [n for n in neighbors if n.isalpha()]
        if not neighbors:
            return None

        replacement = rng.choice(neighbors)
        corrupted = word[:pos] + replacement + word[pos + 1 :]

        return PhoneticError(word, corrupted, "keyboard", pos)

    def _soft_sign(self, word: str) -> PhoneticError | None:
        """Soft sign deletion or ъ→ь confusion."""
        if "ь" in word:
            # Don't delete if it would create empty string
            if len(word) < 2:
                return None
            pos = word.find("ь")
            corrupted = word[:pos] + word[pos + 1 :]
            return PhoneticError(word, corrupted, "soft_sign", pos)

        if "ъ" in word:
            pos = word.find("ъ")
            corrupted = word[:pos] + "ь" + word[pos + 1 :]
            return PhoneticError(word, corrupted, "soft_sign", pos)

        return None
