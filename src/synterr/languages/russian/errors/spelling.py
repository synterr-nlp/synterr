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

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    'о': ['а'],
    'а': ['о'],
    'е': ['и'],
    'и': ['е'],
    'я': ['е', 'и'],
    'э': ['е', 'и'],
}

VOWEL_REDUCTION_UPPER = {
    'О': ['А'],
    'А': ['О'],
    'Е': ['И'],
    'И': ['Е'],
    'Я': ['Е', 'И'],
    'Э': ['Е', 'И'],
}

VOWELS = set('аеёиоуыэюяАЕЁИОУЫЭЮЯ')

# =============================================================================
# CONSONANT DEVOICING
# Voiced consonants become voiceless at word end or before voiceless
# =============================================================================

VOICED_VOICELESS_PAIRS = {
    'б': 'п', 'п': 'б',
    'в': 'ф', 'ф': 'в',
    'г': 'к', 'к': 'г',
    'д': 'т', 'т': 'д',
    'ж': 'ш', 'ш': 'ж',
    'з': 'с', 'с': 'з',
    'Б': 'П', 'П': 'Б',
    'В': 'Ф', 'Ф': 'В',
    'Г': 'К', 'К': 'Г',
    'Д': 'Т', 'Т': 'Д',
    'Ж': 'Ш', 'Ш': 'Ж',
    'З': 'С', 'С': 'З',
}

# =============================================================================
# CLASSIC SPELLING CONFUSIONS
# =============================================================================

# -тся/-ться confusion (most common Russian spelling error)
TSA_PATTERNS = {
    'ться': 'тся',   # infinitive written as 3rd person
    'тся': 'ться',   # 3rd person written as infinitive
}

# Consonant cluster simplification/confusion
CLUSTER_CONFUSIONS = {
    'сч': 'щ',       # счастье → щастье
    'зч': 'щ',       # возчик → вощик
    'сш': 'ш',       # сшить → шить (hypercorrection)
    'зж': 'ж',       # изжога → ижога
    'стн': 'сн',     # честный → чесный (silent consonant)
    'стл': 'сл',     # счастливый → счасливый
    'здн': 'зн',     # поздний → позний
    'рдц': 'рц',     # сердце → серце
    'лнц': 'нц',     # солнце → сонце
}

# Double consonant errors (common in borrowed words)
DOUBLE_CONSONANTS = {
    'нн': 'н',
    'сс': 'с',
    'лл': 'л',
    'мм': 'м',
    'пп': 'п',
    'рр': 'р',
    'тт': 'т',
    'фф': 'ф',
    'кк': 'к',
}

# =============================================================================
# ЙЦУКЕН KEYBOARD LAYOUT - explicit adjacency map
# Accounts for staggered rows on physical keyboard
# =============================================================================

KEYBOARD_ADJACENT = {
    # Top row: ё й ц у к е н г ш щ з х ъ
    'ё': ['й', '1'],
    'й': ['ё', 'ц', 'ф', 'ы'],
    'ц': ['й', 'у', 'ы', 'в'],
    'у': ['ц', 'к', 'в', 'а'],
    'к': ['у', 'е', 'а', 'п'],
    'е': ['к', 'н', 'п', 'р'],
    'н': ['е', 'г', 'р', 'о'],
    'г': ['н', 'ш', 'о', 'л'],
    'ш': ['г', 'щ', 'л', 'д'],
    'щ': ['ш', 'з', 'д', 'ж'],
    'з': ['щ', 'х', 'ж', 'э'],
    'х': ['з', 'ъ', 'э'],
    'ъ': ['х'],
    # Middle row: ф ы в а п р о л д ж э
    'ф': ['й', 'ц', 'ы', 'я'],
    'ы': ['й', 'ц', 'у', 'ф', 'в', 'я', 'ч'],
    'в': ['ц', 'у', 'к', 'ы', 'а', 'ч', 'с'],
    'а': ['у', 'к', 'е', 'в', 'п', 'с', 'м'],
    'п': ['к', 'е', 'н', 'а', 'р', 'м', 'и'],
    'р': ['е', 'н', 'г', 'п', 'о', 'и', 'т'],
    'о': ['н', 'г', 'ш', 'р', 'л', 'т', 'ь'],
    'л': ['г', 'ш', 'щ', 'о', 'д', 'ь', 'б'],
    'д': ['ш', 'щ', 'з', 'л', 'ж', 'б', 'ю'],
    'ж': ['щ', 'з', 'х', 'д', 'э', 'ю'],
    'э': ['з', 'х', 'ж'],
    # Bottom row: я ч с м и т ь б ю
    'я': ['ф', 'ы', 'ч'],
    'ч': ['ы', 'в', 'я', 'с'],
    'с': ['в', 'а', 'ч', 'м'],
    'м': ['а', 'п', 'с', 'и'],
    'и': ['п', 'р', 'м', 'т'],
    'т': ['р', 'о', 'и', 'ь'],
    'ь': ['о', 'л', 'т', 'б'],
    'б': ['л', 'д', 'ь', 'ю'],
    'ю': ['д', 'ж', 'б'],
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

    # Error type weights (based on corpus analysis)
    ERROR_WEIGHTS = {
        'vowel_reduction': 30,
        'devoicing': 15,
        'tsa_confusion': 25,
        'cluster': 10,
        'double_consonant': 10,
        'keyboard': 5,
        'soft_sign': 5,
    }

    def __init__(self):
        self._stress_dict: dict[str, int] | None = None
        self._keyboard_upper: dict[str, list[str]] | None = None

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
    ) -> ErrorResult | None:
        """Apply spelling error."""
        word = sentence[idx]

        result = self._corrupt(word)
        if result is None or result.corrupted == word:
            return None

        sentence[idx] = result.corrupted

        return ErrorResult(
            error_type=f"spelling_{result.error_subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx,
            original=word,
            corrupted=result.corrupted,
            fix_tag=f"$REPLACE_{word}",
        )

    def _corrupt(self, word: str) -> PhoneticError | None:
        """Corrupt a word with a spelling error."""
        methods = list(self.ERROR_WEIGHTS.keys())

        # Weighted shuffle - sort by random * weight for probabilistic ordering
        random.shuffle(methods)
        methods.sort(key=lambda m: random.random() * self.ERROR_WEIGHTS[m], reverse=True)

        for method_name in methods:
            result = self._apply_method(word, method_name)
            if result and result.corrupted != word:
                return result

        return None

    def _apply_method(self, word: str, method: str) -> PhoneticError | None:
        """Apply specific error method."""
        if method == 'vowel_reduction':
            return self._vowel_reduction(word)
        elif method == 'devoicing':
            return self._devoicing(word)
        elif method == 'tsa_confusion':
            return self._tsa_confusion(word)
        elif method == 'cluster':
            return self._cluster(word)
        elif method == 'double_consonant':
            return self._double_consonant(word)
        elif method == 'keyboard':
            return self._keyboard_typo(word)
        elif method == 'soft_sign':
            return self._soft_sign(word)
        return None

    def _vowel_reduction(self, word: str) -> PhoneticError | None:
        """Apply vowel reduction error in unstressed syllables.

        Requires stress_dict to know which vowels are unstressed.
        """
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

        pos = random.choice(positions)
        char = word[pos]
        replacement = random.choice(vowel_map[char])
        corrupted = word[:pos] + replacement + word[pos + 1:]

        return PhoneticError(word, corrupted, 'vowel_reduction', pos)

    def _devoicing(self, word: str) -> PhoneticError | None:
        """Apply consonant devoicing error at word end."""
        if len(word) < 2:
            return None

        last_char = word[-1]

        # Skip if word ends in vowel or soft sign
        if last_char in 'аеёиоуыэюяьъАЕЁИОУЫЭЮЯЬЪ':
            # Check second-to-last if last is soft sign
            if last_char in 'ьъЬЪ' and len(word) > 2:
                check_pos = -2
                last_char = word[-2]
            else:
                return None
        else:
            check_pos = -1

        if last_char in VOICED_VOICELESS_PAIRS:
            replacement = VOICED_VOICELESS_PAIRS[last_char]
            if check_pos == -1:
                corrupted = word[:-1] + replacement
            else:
                corrupted = word[:-2] + replacement + word[-1]

            return PhoneticError(word, corrupted, 'devoicing', len(word) + check_pos)

        return None

    def _tsa_confusion(self, word: str) -> PhoneticError | None:
        """Apply -тся/-ться confusion."""
        for pattern, replacement in TSA_PATTERNS.items():
            if word.endswith(pattern):
                corrupted = word[:-len(pattern)] + replacement
                return PhoneticError(word, corrupted, 'tsa_confusion', len(word) - len(pattern))
        return None

    def _cluster(self, word: str) -> PhoneticError | None:
        """Apply consonant cluster simplification."""
        word_lower = word.lower()
        for pattern, replacement in CLUSTER_CONFUSIONS.items():
            if pattern in word_lower:
                pos = word_lower.find(pattern)
                # Preserve case of first letter
                if word[pos].isupper():
                    repl = replacement[0].upper() + replacement[1:] if len(replacement) > 1 else replacement.upper()
                else:
                    repl = replacement
                corrupted = word[:pos] + repl + word[pos + len(pattern):]
                return PhoneticError(word, corrupted, 'cluster', pos)
        return None

    def _double_consonant(self, word: str) -> PhoneticError | None:
        """Add or remove double consonants."""
        word_lower = word.lower()

        # Try to remove double
        for double, single in DOUBLE_CONSONANTS.items():
            if double in word_lower:
                pos = word_lower.find(double)
                corrupted = word[:pos] + single + word[pos + 2:]
                return PhoneticError(word, corrupted, 'double_consonant', pos)

        # Try to add double (only for certain consonants mid-word)
        for i, char in enumerate(word_lower[1:-1], 1):
            can_double = (
                char in 'нслмпрткф'
                and word_lower[i - 1] != char
                and word_lower[i + 1] != char
            )
            if can_double and random.random() < 0.3:
                corrupted = word[:i] + char + word[i:]
                return PhoneticError(word, corrupted, 'double_consonant', i)

        return None

    def _keyboard_typo(self, word: str) -> PhoneticError | None:
        """Generate keyboard adjacency typo."""
        if len(word) < 2:
            return None

        positions = []
        for i, char in enumerate(word):
            if char.lower() in self.keyboard_adjacent or char in self.keyboard_adjacent:
                positions.append(i)

        if not positions:
            return None

        pos = random.choice(positions)
        char = word[pos]

        if char in self.keyboard_adjacent:
            neighbors = self.keyboard_adjacent[char]
        elif char.lower() in self.keyboard_adjacent:
            neighbors = [n.upper() if char.isupper() else n for n in self.keyboard_adjacent[char.lower()]]
        else:
            return None

        neighbors = [n for n in neighbors if n.isalpha()]
        if not neighbors:
            return None

        replacement = random.choice(neighbors)
        corrupted = word[:pos] + replacement + word[pos + 1:]

        return PhoneticError(word, corrupted, 'keyboard', pos)

    def _soft_sign(self, word: str) -> PhoneticError | None:
        """Soft sign deletion or ъ→ь confusion."""
        if 'ь' in word:
            pos = word.find('ь')
            corrupted = word[:pos] + word[pos + 1:]
            return PhoneticError(word, corrupted, 'soft_sign', pos)

        if 'ъ' in word:
            pos = word.find('ъ')
            corrupted = word[:pos] + 'ь' + word[pos + 1:]
            return PhoneticError(word, corrupted, 'soft_sign', pos)

        return None
