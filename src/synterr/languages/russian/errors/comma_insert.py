"""Russian comma insertion handler — insert commas where they don't belong.

Covers LoRuGEC rules about EXTRA commas (the error = spurious comma):
- Before "как" when it means "в качестве" or is part of idiom (§114-115)
- Inside phraseological/set expressions: ни...ни, и...и, etc. (§101)
- Between adjacent conjunctions at clause boundaries (§133-138)

This handler inserts comma tokens into the sentence (changes_length=True).
"""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# "как" patterns: insert comma before "как" in contexts where it's wrong
# =============================================================================

# POS of words that often precede "как" WITHOUT a comma (в качестве, приравнивание)
_KAK_NO_COMMA_PREV_POS = {"ADP", "VERB", "NOUN", "ADJ", "ADV"}

# =============================================================================
# Phraseological/set expression patterns
# Repeated conjunctions (и...и, ни...ни, или...или, то...то)
# where comma between pair members is incorrect
# =============================================================================

_REPEATED_CONJUNCTIONS = {"и", "ни", "или", "либо", "то"}

# =============================================================================
# Adjacent conjunction patterns
# At junction of two conjunctions: "и когда" → "и , когда"
# =============================================================================

_COORDINATING = {"и", "а", "но", "да", "или", "либо", "же", "однако", "зато"}
_SUBORDINATING = {"что", "когда", "если", "хотя", "чтобы", "пока", "как",
                  "потому", "поскольку", "пусть", "будто", "словно", "точно",
                  "раз", "ибо", "ведь", "коль"}


class CommaInsertHandler:
    """Insert spurious commas — creates extra-comma errors.

    Subtypes:
    - comma_before_kak: insert comma before "как" where it shouldn't be
    - comma_in_set_phrase: insert comma inside repeated conjunction phrases
    - comma_between_conjunctions: insert comma between adjacent conjunctions
    """

    name = "comma_insert"
    subtypes = [
        "comma_before_kak",
        "comma_in_set_phrase",
        "comma_between_conjunctions",
    ]
    category = "PUNCT"
    changes_length = True

    DEFAULT_WEIGHTS = {
        "comma_before_kak": 40,
        "comma_in_set_phrase": 35,
        "comma_between_conjunctions": 25,
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
        text_lower = token.text.lower()

        # "как" not already preceded by comma
        if text_lower == "как" and idx > 0:
            prev = tokens[idx - 1]
            if prev.text != "," and prev.pos in _KAK_NO_COMMA_PREV_POS:
                return True

        # Repeated conjunction: first occurrence of и/ни/или followed later by same
        if text_lower in _REPEATED_CONJUNCTIONS:
            # Check if there's another occurrence of same conjunction later
            for j in range(idx + 2, len(tokens)):
                if tokens[j].text.lower() == text_lower:
                    # And no comma right after current token
                    if idx + 1 < len(tokens) and tokens[idx + 1].text != ",":
                        return True
                    break

        # Adjacent conjunctions: coordinating + subordinating with no comma between
        if text_lower in _COORDINATING and idx + 1 < len(tokens):
            next_lower = tokens[idx + 1].text.lower()
            if next_lower in _SUBORDINATING:
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
        text_lower = token.text.lower()

        candidates: list[tuple[str, float]] = []

        if text_lower == "как" and idx > 0:
            prev = tokens[idx - 1]
            if prev.text != "," and prev.pos in _KAK_NO_COMMA_PREV_POS:
                candidates.append(("comma_before_kak", self._weights["comma_before_kak"]))

        if text_lower in _REPEATED_CONJUNCTIONS:
            for j in range(idx + 2, len(tokens)):
                if tokens[j].text.lower() == text_lower:
                    if idx + 1 < len(tokens) and tokens[idx + 1].text != ",":
                        candidates.append(("comma_in_set_phrase", self._weights["comma_in_set_phrase"]))
                    break

        if text_lower in _COORDINATING and idx + 1 < len(tokens):
            next_lower = tokens[idx + 1].text.lower()
            if next_lower in _SUBORDINATING:
                candidates.append(("comma_between_conjunctions", self._weights["comma_between_conjunctions"]))

        if not candidates:
            return None

        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "comma_before_kak":
            return self._insert_before_kak(sentence, idx)
        elif chosen == "comma_in_set_phrase":
            return self._insert_in_set_phrase(sentence, idx)
        elif chosen == "comma_between_conjunctions":
            return self._insert_between_conjunctions(sentence, idx)

        return None

    def _insert_before_kak(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Insert comma before "как": работал как → работал , как."""
        sentence.insert(idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_before_kak",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_in_set_phrase(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Insert comma after first conjunction in repeated pair: и стар и млад → и стар , и млад."""
        # Find the next word after the conjunction that isn't the same conjunction
        # Insert comma before the second occurrence of the conjunction
        text_lower = sentence[idx].lower()
        # Find second occurrence
        for j in range(idx + 2, len(sentence)):
            if sentence[j].lower() == text_lower:
                # Insert comma before second conjunction
                sentence.insert(j, ",")
                return ErrorResult(
                    error_type="comma_insert_comma_in_set_phrase",
                    category=self.category,
                    start_idx=j,
                    end_idx=j + 1,
                    original="",
                    corrupted=",",
                    fix_tag="$DELETE",
                )
        return None

    def _insert_between_conjunctions(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Insert comma between adjacent conjunctions: и когда → и , когда."""
        sentence.insert(idx + 1, ",")
        return ErrorResult(
            error_type="comma_insert_comma_between_conjunctions",
            category=self.category,
            start_idx=idx + 1,
            end_idx=idx + 2,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )
