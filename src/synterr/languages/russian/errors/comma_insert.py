"""Russian comma insertion handler — insert commas where they don't belong.

Covers LoRuGEC rules about EXTRA commas (the error = spurious comma):
- Before "как" when it means "в качестве" (no comma per §93 Прим.) or is part of
  idiom (§114). Uses dep-tree: only targets "как" with dep_rel=case/fixed/flat
  (adjunct/apposition sense), NOT advcl/ccomp/mark (subordinate clause).
- Inside frozen phraseological expressions: ни слуху ни духу, и стар и млад, etc.
  (§87 п.5). Uses a curated lexicon from Rozental — NOT all repeated conjunctions.
- Between adjacent conjunctions at clause boundaries (§110). Only fires when a
  "то/так/но" correlative follows the subordinate clause (making the comma wrong).

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
# "как" patterns: dep_rel-based filtering
# =============================================================================

# dep_rels where "как" introduces a subordinate/comparative clause → comma IS correct
# We must NOT insert a comma here (it would produce correct punctuation, not an error)
_KAK_CLAUSE_DEPRELS = {"mark", "advcl", "ccomp", "csubj", "acl"}

# =============================================================================
# Frozen phraseological expressions from Rozental §87 п.5
# These are the ONLY repeated-conjunction patterns where comma is wrong.
# Format: frozenset of the content words between the conjunctions.
# =============================================================================

_FROZEN_PHRASES: dict[str, list[tuple[str, ...]]] = {
    "и": [
        ("день", "ночь"), ("смех", "горе"), ("стар", "млад"),
        ("там", "тут"), ("так", "сяк"), ("то", "другое"),
        ("то", "дело"), ("тот", "другой"), ("взад", "вперёд"),
        ("туда", "сюда"), ("направо", "налево"), ("вкривь", "вкось"),
        ("холод", "голод"), ("свет", "тьма"),
    ],
    "ни": [
        ("слуху", "духу"), ("бе", "ме"), ("больше", "меньше"),
        ("рыба", "мясо"), ("свет", "заря"), ("то", "сё"),
        ("тот", "другой"), ("жив", "мёртв"), ("себе", "людям"),
        ("туда", "сюда"), ("два", "полтора"), ("дать", "взять"),
        ("взад", "вперёд"), ("там", "тут"), ("так", "сяк"),
        ("много", "мало"), ("стать", "сесть"), ("шатко", "валко"),
        ("пуха", "пера"), ("ответа", "привета"), ("кола", "двора"),
        ("конца", "краю"), ("начала", "конца"),
    ],
}

# =============================================================================
# Adjacent conjunction patterns (§110)
# =============================================================================

_COORDINATING = {"и", "а", "но", "да", "или", "либо", "же", "однако", "зато"}
_SUBORDINATING = {"что", "когда", "если", "хотя", "чтобы", "пока",
                  "потому", "поскольку", "пусть", "будто", "словно", "точно"}

# Correlative words that follow a subordinate clause and signal NO comma at junction
_CORRELATIVES = {"то", "так", "но"}


def _matches_frozen_phrase(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Check if tokens starting at idx match a frozen phrase from §87 п.5."""
    conj = tokens[idx].text.lower()
    phrases = _FROZEN_PHRASES.get(conj)
    if not phrases:
        return False
    # Find second occurrence of the same conjunction
    for j in range(idx + 2, min(idx + 5, len(tokens))):
        if tokens[j].text.lower() == conj:
            # No comma already between them
            if any(tokens[k].text == "," for k in range(idx + 1, j)):
                return False
            # Collect content words between the two conjunctions
            between = tuple(
                tokens[k].text.lower() for k in range(idx + 1, j)
                if tokens[k].pos != "PUNCT"
            )
            if len(between) != 1:
                continue
            # Collect content word after the second conjunction
            after_words = []
            for k in range(j + 1, min(j + 3, len(tokens))):
                if tokens[k].pos != "PUNCT":
                    after_words.append(tokens[k].text.lower())
                    break
            if not after_words:
                continue
            pair = (between[0], after_words[0])
            if pair in phrases:
                return True
    return False


def _has_correlative_after(tokens: Sequence[AnalyzedToken], subord_idx: int) -> bool:
    """Check if a subordinate clause starting at subord_idx is followed by то/так/но.

    Per §110: comma between conjunctions is NOT placed when the subordinate
    clause has a correlative word (то/так/но) after it. So we insert a comma
    (creating an error) only when such a correlative IS present.
    """
    # Scan forward for a correlative, but not too far (within ~15 tokens)
    for j in range(subord_idx + 1, min(subord_idx + 15, len(tokens))):
        tok = tokens[j]
        if tok.text.lower() in _CORRELATIVES and tok.pos in ("CCONJ", "PART", "ADV"):
            return True
        # Stop at sentence-ending punctuation
        if tok.text in (".", "!", "?", ";"):
            break
    return False


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

        # "как" not already preceded by comma, and NOT a clause-introducing "как"
        if text_lower == "как" and idx > 0:
            prev = tokens[idx - 1]
            if prev.text != ",":
                # Use dep_rel to filter: skip if "как" introduces a subordinate clause
                if token.dep_rel not in _KAK_CLAUSE_DEPRELS:
                    return True

        # Frozen phrase: check if conjunction + content words match a known phrase
        if text_lower in _FROZEN_PHRASES and _matches_frozen_phrase(tokens, idx):
            return True

        # Adjacent conjunctions: only when "то/так/но" correlative follows
        if text_lower in _COORDINATING and idx + 1 < len(tokens):
            next_lower = tokens[idx + 1].text.lower()
            if next_lower in _SUBORDINATING:
                if _has_correlative_after(tokens, idx + 1):
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
            if prev.text != "," and token.dep_rel not in _KAK_CLAUSE_DEPRELS:
                candidates.append(("comma_before_kak", self._weights["comma_before_kak"]))

        if text_lower in _FROZEN_PHRASES and _matches_frozen_phrase(tokens, idx):
            candidates.append(("comma_in_set_phrase", self._weights["comma_in_set_phrase"]))

        if text_lower in _COORDINATING and idx + 1 < len(tokens):
            next_lower = tokens[idx + 1].text.lower()
            if next_lower in _SUBORDINATING and _has_correlative_after(tokens, idx + 1):
                candidates.append(("comma_between_conjunctions", self._weights["comma_between_conjunctions"]))

        if not candidates:
            return None

        subtypes, weights = zip(*candidates)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "comma_before_kak":
            return self._insert_before_kak(sentence, idx)
        elif chosen == "comma_in_set_phrase":
            return self._insert_in_set_phrase(sentence, idx, tokens)
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
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """Insert comma in frozen phrase: ни слуху ни духу → ни слуху , ни духу."""
        conj = sentence[idx].lower()
        # Find second occurrence of the conjunction
        for j in range(idx + 2, min(idx + 5, len(tokens))):
            if tokens[j].text.lower() == conj:
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
