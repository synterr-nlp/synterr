"""Russian compound word spelling handler.

Covers LoRuGEC rules:
- Rule 17: Дефис в составе сложных слов (number/letter + adjective compounds)
- Rule 36: Правописание сложных прилагательных (compound adjectives: merge vs hyphen)
- Rule 44: Правописание числительного пол- (пол- prefix spelling)

Rozental §41-44 (Part I, Chapter IX).
"""

from __future__ import annotations

import random as random_module
import re
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# Rule 17: Number/letter/symbol + adjective → requires dash
# Pattern: "25-процентный", "Z-образный", "5-го"
# Error direction: DELETE the dash (correct → error)
# =============================================================================

# Regex: digit(s) + dash + Cyrillic adjective/ordinal suffix
_NUM_DASH_ADJ_RE = re.compile(
    r"^(\d[\d\s/]*)-([а-яёА-ЯЁ]{3,})$"
)

# Regex: Latin letter(s) + dash + Cyrillic word
_LETTER_DASH_CYRILLIC_RE = re.compile(
    r"^([A-Za-zα-ωΑ-Ω]+)-([а-яёА-ЯЁ]{3,})$"
)

# Ordinal suffixes for numeral compounds: "5-го", "70-й", "35-м"
_ORDINAL_SUFFIX_RE = re.compile(
    r"^(\d+)-((?:го|й|я|е|х|м|му|ми|ю))$"
)


# =============================================================================
# Rule 44: пол- prefix
# пол + consonant (not л) → merged: полвека
# пол + vowel/л/proper noun → dash: пол-лимона, пол-яблока, пол-Москвы
# Error: swap between merged/dashed/separate forms
# =============================================================================

_VOWELS_LOWER = set("аеёиоуыэюя")

_POL_DASH_RE = re.compile(r"^пол-([а-яёА-ЯЁ]{2,})$", re.IGNORECASE)
_POL_MERGED_RE = re.compile(r"^пол([а-яё]{2,})$", re.IGNORECASE)


# =============================================================================
# Rule 36: Compound adjective merge/hyphen
# Subordinate (one part governs the other) → merged: железнодорожный
# Coordinate (both parts equal) → hyphenated: торгово-промышленный
# Error: swap merge↔hyphen
# =============================================================================

# Common compound adjectives that should be HYPHENATED (coordinate structure)
# Error direction: remove the dash (merge them incorrectly)
_HYPHENATED_COMPOUNDS: set[str] = {
    "военно-полевой", "военно-морской", "военно-воздушный",
    "торгово-промышленный", "торгово-экономический",
    "научно-исследовательский", "научно-технический", "научно-практический",
    "учебно-тренировочный", "учебно-методический", "учебно-воспитательный",
    "молочно-растительный", "молочно-кислый",
    "народно-хозяйственный", "народно-демократический",
    "социально-экономический", "социально-политический",
    "общественно-политический", "общественно-полезный",
    "культурно-массовый", "культурно-просветительный",
    "массово-политический", "мясо-молочный",
    "плодово-ягодный", "плодово-овощной",
    "ремонтно-строительный", "ремонтно-механический",
    "сердечно-сосудистый", "кожно-венерический",
    "отчётно-выборный", "партийно-комсомольский",
    "русско-немецкий", "англо-русский", "франко-прусский",
    "северо-западный", "северо-восточный", "юго-западный", "юго-восточный",
}


class CompoundSpellingHandler:
    """Corrupt compound word spelling: dashes, пол-, compound adjectives.

    Subtypes:
    - num_dash: Remove dash in number+adjective compounds (25-процентный → 25процентный)
    - pol_spelling: Corrupt пол- prefix spelling (полвека → пол-века or vice versa)
    - compound_adj: Swap merge/hyphen in compound adjectives
    """

    name = "compound_spelling"
    subtypes = [
        "num_dash",
        "pol_spelling",
        "compound_adj",
    ]
    category = "SPELL"
    changes_length = False  # We modify the token in place (merge/split within token)

    DEFAULT_WEIGHTS = {
        "num_dash": 35,
        "pol_spelling": 40,
        "compound_adj": 25,
    }

    def __init__(self):
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        text = tokens[idx].text

        # Rule 17: number-adjective or letter-adjective with dash
        if _NUM_DASH_ADJ_RE.match(text) or _LETTER_DASH_CYRILLIC_RE.match(text):
            return True
        if _ORDINAL_SUFFIX_RE.match(text):
            return True

        # Rule 44: пол- compounds
        text_lower = text.lower()
        if _POL_DASH_RE.match(text_lower) or _POL_MERGED_RE.match(text_lower):
            return True

        # Rule 36: hyphenated compound adjective
        if "-" in text and text_lower.rstrip("а-яё") == "":
            # Check if it's a known hyphenated compound
            if text_lower in _HYPHENATED_COMPOUNDS:
                return True
            # Check inflected forms: strip common endings and check
            for compound in _HYPHENATED_COMPOUNDS:
                if text_lower.startswith(compound[:compound.index("-") + 1]):
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
        text = sentence[idx]
        text_lower = text.lower()

        candidates: list[tuple[str, float]] = []

        # Check each subtype
        if (_NUM_DASH_ADJ_RE.match(text) or _LETTER_DASH_CYRILLIC_RE.match(text)
                or _ORDINAL_SUFFIX_RE.match(text)):
            candidates.append(("num_dash", self._weights["num_dash"]))

        if _POL_DASH_RE.match(text_lower) or _POL_MERGED_RE.match(text_lower):
            candidates.append(("pol_spelling", self._weights["pol_spelling"]))

        if "-" in text:
            for compound in _HYPHENATED_COMPOUNDS:
                if text_lower.startswith(compound[:compound.index("-") + 1]):
                    candidates.append(("compound_adj", self._weights["compound_adj"]))
                    break

        if not candidates:
            return None

        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "num_dash":
            return self._corrupt_num_dash(sentence, idx)
        elif chosen == "pol_spelling":
            return self._corrupt_pol(sentence, idx, rng)
        elif chosen == "compound_adj":
            return self._corrupt_compound_adj(sentence, idx)

        return None

    def _corrupt_num_dash(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Remove dash from number/letter-adjective compound: 25-процентный → 25процентный."""
        text = sentence[idx]
        if "-" not in text:
            return None

        # Remove first dash
        corrupted = text.replace("-", "", 1)
        if corrupted == text:
            return None

        # For ordinals, could also produce space: "5-го" → "5 го"
        # But removing dash is more common error
        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_num_dash",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )

    def _corrupt_pol(
        self, sentence: list[str], idx: int, rng: Random
    ) -> ErrorResult | None:
        """Corrupt пол- prefix spelling."""
        text = sentence[idx]
        text_lower = text.lower()

        dash_match = _POL_DASH_RE.match(text_lower)
        merged_match = _POL_MERGED_RE.match(text_lower)

        if dash_match:
            # пол-лимона → поллимона (remove dash = merge incorrectly)
            rest = text[4:]  # after "пол-"
            corrupted = text[:3] + rest  # "пол" + rest (no dash)
            # Preserve original case
            if text[0].isupper():
                corrupted = corrupted[0].upper() + corrupted[1:]
        elif merged_match:
            # полвека → пол-века (add dash = incorrectly hyphenate)
            rest = text[3:]  # after "пол"
            corrupted = text[:3] + "-" + rest
            if text[0].isupper():
                corrupted = corrupted[0].upper() + corrupted[1:]
        else:
            return None

        if corrupted == text:
            return None

        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_pol_spelling",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )

    def _corrupt_compound_adj(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Remove dash from compound adjective: военно-полевой → военнополевой."""
        text = sentence[idx]
        if "-" not in text:
            return None

        corrupted = text.replace("-", "", 1)
        if corrupted == text:
            return None

        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_compound_adj",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )
