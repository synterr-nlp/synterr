"""Russian spelling error handler using phonetic rules."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synterr.core.protocol import AnalyzedToken


# Cyrillic character sets
CYRILLIC_VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
CYRILLIC_CONSONANTS = "бвгджзйклмнпрстфхцчшщБВГДЖЗЙКЛМНПРСТФХЦЧШЩ"
CYRILLIC_LETTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"

# ЙЦУКЕН keyboard layout adjacency for typo simulation
KEYBOARD_ADJACENT = {
    "й": "цуф",
    "ц": "йуыв",
    "у": "цыкае",
    "к": "уеапв",
    "е": "кнаро",
    "н": "егпит",
    "г": "нрошь",
    "ш": "горлб",
    "щ": "шлдю",
    "з": "щджэ",
    "х": "зжэъ",
    "ъ": "хэ",
    "ф": "ыйя",
    "ы": "фцвуч",
    "в": "ыуакс",
    "а": "впекм",
    "п": "акенри",
    "р": "пнгоит",
    "о": "ргншл",
    "л": "ошщьд",
    "д": "лщзюж",
    "ж": "дзхэб",
    "э": "жхъ",
    "я": "фч",
    "ч": "яысм",
    "с": "чвати",
    "м": "саекь",
    "и": "мпрнт",
    "т": "иронь",
    "ь": "толбш",
    "б": "ьлдю",
    "ю": "бдж",
}

# Vowel reduction rules (аканье/иканье)
VOWEL_REDUCTION = {
    "о": "а",  # unstressed о → а
    "а": "о",  # reverse for errors
    "е": "и",  # unstressed е → и
    "и": "е",  # reverse
    "я": "е",  # unstressed я → [и]/е
}

# Consonant devoicing pairs
VOICING_PAIRS = {
    "б": "п",
    "в": "ф",
    "г": "к",
    "д": "т",
    "ж": "ш",
    "з": "с",
    "п": "б",
    "ф": "в",
    "к": "г",
    "т": "д",
    "ш": "ж",
    "с": "з",
}

# Double consonants that are often simplified
DOUBLE_CONSONANTS = ["лл", "мм", "нн", "рр", "сс", "жж", "кк", "пп", "тт"]


@dataclass
class CorruptionResult:
    """Result of word corruption."""

    original: str
    corrupted: str
    error_subtype: str


class SpellingErrorHandler:
    """Russian spelling error handler using phonetic rules.

    Implements realistic Russian spelling errors:
    - Vowel reduction (аканье/иканье) in unstressed syllables
    - Consonant devoicing at word boundaries
    - тся/ться confusion (very common)
    - Consonant cluster simplification
    - Double consonant errors
    - Keyboard typos (ЙЦУКЕН layout)
    """

    name = "spelling"
    category = "SPELL"
    changes_length = False

    # Error type weights (based on corpus analysis)
    ERROR_WEIGHTS = {
        "vowel_reduction": 0.30,
        "tsa_confusion": 0.25,
        "devoicing": 0.15,
        "double_consonant": 0.10,
        "keyboard": 0.15,
        "random_char": 0.05,
    }

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if spelling error can be applied at token index."""
        token = tokens[idx]
        # Only apply to alphabetic tokens with at least 2 characters
        return token.text.isalpha() and len(token.text) >= 2

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        """Apply spelling error."""
        word = sentence[idx]

        result = self._corrupt(word)
        if result is None or result.corrupted == word:
            return None

        sentence[idx] = result.corrupted
        modified.add(idx)

        return ErrorResult(
            error_type=f"spelling_{result.error_subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=result.corrupted,
            fix_tag=f"$REPLACE_{word}",
        )

    def _corrupt(self, word: str) -> CorruptionResult | None:
        """Corrupt a word with a spelling error.

        Args:
            word: Original word

        Returns:
            CorruptionResult or None if corruption failed
        """
        # Sample error type according to weights
        error_types = list(self.ERROR_WEIGHTS.keys())
        weights = list(self.ERROR_WEIGHTS.values())
        error_type = random.choices(error_types, weights=weights, k=1)[0]

        # Try the selected error type first, then fall back to others
        attempts = [error_type] + [t for t in error_types if t != error_type]

        for attempt in attempts:
            result = self._apply_error_type(word, attempt)
            if result is not None:
                return result

        return None

    def _apply_error_type(self, word: str, error_type: str) -> CorruptionResult | None:
        """Apply specific error type to word."""
        if error_type == "vowel_reduction":
            return self._vowel_reduction(word)
        elif error_type == "tsa_confusion":
            return self._tsa_confusion(word)
        elif error_type == "devoicing":
            return self._devoicing(word)
        elif error_type == "double_consonant":
            return self._double_consonant(word)
        elif error_type == "keyboard":
            return self._keyboard_typo(word)
        elif error_type == "random_char":
            return self._random_char(word)
        return None

    def _vowel_reduction(self, word: str) -> CorruptionResult | None:
        """Apply vowel reduction error (аканье/иканье)."""
        word_lower = word.lower()

        # Find vowels that can be reduced
        for i, char in enumerate(word_lower):
            if char in VOWEL_REDUCTION:
                # Apply reduction
                replacement = VOWEL_REDUCTION[char]

                # Preserve case
                if word[i].isupper():
                    replacement = replacement.upper()

                corrupted = word[:i] + replacement + word[i + 1 :]
                if corrupted != word:
                    return CorruptionResult(word, corrupted, "vowel_reduction")

        return None

    def _tsa_confusion(self, word: str) -> CorruptionResult | None:
        """Apply тся/ться confusion (very common Russian error)."""
        if word.endswith("ться"):
            # Remove soft sign: ться → тся
            corrupted = word[:-4] + "тся"
            return CorruptionResult(word, corrupted, "tsa_confusion")
        elif word.endswith("тся"):
            # Add soft sign: тся → ться
            corrupted = word[:-3] + "ться"
            return CorruptionResult(word, corrupted, "tsa_confusion")
        return None

    def _devoicing(self, word: str) -> CorruptionResult | None:
        """Apply consonant devoicing error at word end."""
        if len(word) < 2:
            return None

        last_char = word[-1].lower()
        if last_char in VOICING_PAIRS:
            replacement = VOICING_PAIRS[last_char]
            if word[-1].isupper():
                replacement = replacement.upper()
            corrupted = word[:-1] + replacement
            return CorruptionResult(word, corrupted, "devoicing")

        return None

    def _double_consonant(self, word: str) -> CorruptionResult | None:
        """Apply double consonant error (add or remove doubling)."""
        word_lower = word.lower()

        # Check for existing double consonants to simplify
        for double in DOUBLE_CONSONANTS:
            if double in word_lower:
                idx = word_lower.index(double)
                corrupted = word[:idx] + word[idx + 1 :]
                return CorruptionResult(word, corrupted, "double_consonant")

        # Otherwise, try to double a consonant
        for i, char in enumerate(word_lower):
            if char in CYRILLIC_CONSONANTS.lower() and i < len(word) - 1:
                corrupted = word[: i + 1] + word[i:]  # Double the consonant
                return CorruptionResult(word, corrupted, "double_consonant")

        return None

    def _keyboard_typo(self, word: str) -> CorruptionResult | None:
        """Apply keyboard typo using ЙЦУКЕН adjacency."""
        if len(word) < 2:
            return None

        # Pick a random position
        positions = list(range(len(word)))
        random.shuffle(positions)

        for pos in positions:
            char = word[pos].lower()
            if char in KEYBOARD_ADJACENT:
                adjacent = KEYBOARD_ADJACENT[char]
                replacement = random.choice(adjacent)
                if word[pos].isupper():
                    replacement = replacement.upper()
                corrupted = word[:pos] + replacement + word[pos + 1 :]
                return CorruptionResult(word, corrupted, "keyboard")

        return None

    def _random_char(self, word: str) -> CorruptionResult | None:
        """Replace a random character with another Cyrillic character."""
        if len(word) < 2:
            return None

        pos = random.randint(0, len(word) - 1)
        char = word[pos]

        # Get same character set (vowel/consonant)
        if char.lower() in CYRILLIC_VOWELS.lower():
            choices = CYRILLIC_VOWELS.lower()
        else:
            choices = CYRILLIC_CONSONANTS.lower()

        replacement = random.choice(choices)
        while replacement == char.lower():
            replacement = random.choice(choices)

        if char.isupper():
            replacement = replacement.upper()

        corrupted = word[:pos] + replacement + word[pos + 1 :]
        return CorruptionResult(word, corrupted, "random_char")
