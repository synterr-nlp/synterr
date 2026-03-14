"""Russian comma insertion handler — insert commas where they don't belong.

Covers LoRuGEC rules about EXTRA commas (the error = spurious comma):
- Before "как" when it means "в качестве" (no comma per §93 Прим.) or is part of
  idiom (§114). Uses dep-tree: only targets "как" with dep_rel=case/fixed/flat
  (adjunct/apposition sense), NOT advcl/ccomp/mark (subordinate clause).
- Inside frozen phraseological expressions: ни слуху ни духу, и стар и млад, etc.
  (§87 п.5). Uses a curated lexicon from Rozental — NOT all repeated conjunctions.
- Between adjacent conjunctions at clause boundaries (§110). Only fires when a
  "то/так/но" correlative follows the subordinate clause (making the comma wrong).
- Inside indivisible (цельные по смыслу) expressions: как ни в чём не бывало,
  куда глаза глядят, мало кто, не иначе как, etc. (§87 п.4, §90, §114 п.1).

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

# dep_rels where "как" takes a comma (clause/comparative) → comma IS correct
# We must NOT insert a comma here (it would produce correct punctuation, not an error)
# advmod: comparative "как" ("высокий, как отец") — comma correct 60% of the time
# cc: coordinating "как... так и..." — comma usually correct
_KAK_CLAUSE_DEPRELS = {"mark", "advcl", "ccomp", "csubj", "acl", "advmod", "cc"}

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

# =============================================================================
# Indivisible (цельные по смыслу) expressions (§87 п.4, §90, §114 п.1)
# No comma inside these. Error = inserting a comma.
# Format: tuple of words, comma insertion point (index in tuple where comma goes).
# =============================================================================

# Expressions with "как" that should NOT have a comma before "как"
# (distinct from comma_before_kak which uses dep_rel; these are fixed phrases)
_INDIVISIBLE_KAK: list[tuple[str, ...]] = [
    ("как", "следует"),
    ("как", "попало"),
    ("как", "есть"),
    ("как", "было"),
    ("как", "можно"),
    ("как", "нибудь"),
    ("как", "никогда"),
    ("всё", "равно", "как"),
    ("всё", "равно", "что"),
    ("не", "иначе", "как"),
    ("не", "больше", "чем"),
    ("не", "больше", "как"),
    ("не", "меньше", "чем"),
    ("не", "хуже", "чем"),
    ("не", "раньше", "чем"),
    ("не", "позже", "чем"),
    ("не", "так", "чтобы"),
    ("не", "то", "чтобы"),
    ("не", "то", "что"),
]

# Expressions with pronouns/adverbs that form indivisible units (§87 п.4)
_INDIVISIBLE_PRONOUN: list[tuple[str, ...]] = [
    ("мало", "кто"),
    ("мало", "что"),
    ("мало", "где"),
    ("мало", "куда"),
    ("неизвестно", "кто"),
    ("неизвестно", "что"),
    ("неизвестно", "где"),
    ("неизвестно", "куда"),
    ("неизвестно", "зачем"),
    ("неизвестно", "как"),
    ("неизвестно", "кем"),
    ("неизвестно", "чем"),
    ("неизвестно", "когда"),
    ("неведомо", "кто"),
    ("неведомо", "что"),
    ("неведомо", "где"),
    ("неведомо", "куда"),
    ("неведомо", "как"),
    ("непонятно", "кто"),
    ("непонятно", "что"),
    ("непонятно", "где"),
    ("непонятно", "зачем"),
    ("непонятно", "почему"),
    ("всё", "что"),
    ("кто", "может"),
    ("кто", "хочет"),
    ("где", "нужно"),
    ("где", "попало"),
    ("куда", "глаза", "глядят"),
    ("куда", "попало"),
    ("откуда", "ни", "возьмись"),
    ("что", "угодно"),
    ("кто", "угодно"),
    ("как", "угодно"),
    ("где", "угодно"),
    ("когда", "угодно"),
    ("сколько", "угодно"),
]

# Fixed multi-word expressions with internal structure (§87 п.4, §114)
_INDIVISIBLE_FIXED: list[tuple[str, ...]] = [
    ("как", "ни", "в", "чём", "не", "бывало"),
    ("как", "ни", "в", "чем", "не", "бывало"),
    ("самый", "что", "ни", "на", "есть"),
]

# Build lookup: first word → list of (full_phrase, comma_position)
# comma_position = index before which to insert comma (usually between words 0 and 1)
_INDIVISIBLE_INDEX: dict[str, list[tuple[tuple[str, ...], int]]] = {}

for _phrases, _default_pos in [
    (_INDIVISIBLE_KAK, 0),       # comma before the phrase or within it
    (_INDIVISIBLE_PRONOUN, 0),
    (_INDIVISIBLE_FIXED, 0),
]:
    for _phrase in _phrases:
        _key = _phrase[0]
        # Default comma position: between first and second word
        _comma_pos = 1 if len(_phrase) > 1 else 0
        _INDIVISIBLE_INDEX.setdefault(_key, []).append((_phrase, _comma_pos))


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


def _matches_indivisible(tokens: Sequence[AnalyzedToken], idx: int) -> tuple[str, ...] | None:
    """Check if tokens starting at idx match an indivisible expression.

    Returns the matched phrase tuple, or None.
    """
    text_lower = tokens[idx].text.lower()
    candidates = _INDIVISIBLE_INDEX.get(text_lower)
    if not candidates:
        return None

    for phrase, _comma_pos in candidates:
        phrase_len = len(phrase)
        if idx + phrase_len > len(tokens):
            continue
        # Check if all words match (case-insensitive)
        match = True
        for k, expected in enumerate(phrase):
            if tokens[idx + k].text.lower() != expected:
                match = False
                break
        if match:
            # Verify no comma already present inside the phrase
            has_internal_comma = False
            for k in range(idx, idx + phrase_len):
                if tokens[k].text == ",":
                    has_internal_comma = True
                    break
            if not has_internal_comma:
                return phrase
    return None


def _has_correlative_after(tokens: Sequence[AnalyzedToken], subord_idx: int) -> bool:
    """Check if a subordinate clause starting at subord_idx is followed by то/так/но.

    Per §110: comma between conjunctions is NOT placed when the subordinate
    clause has a correlative word (то/так/но) after it. So we insert a comma
    (creating an error) only when such a correlative IS present.

    "но" as CCONJ is excluded — it's a regular coordinating conjunction,
    not a correlative. Only "но" as PART qualifies (rare).
    """
    for j in range(subord_idx + 1, min(subord_idx + 15, len(tokens))):
        tok = tokens[j]
        if tok.text in (".", "!", "?", ";"):
            break
        text = tok.text.lower()
        if text in _CORRELATIVES:
            # "но" as CCONJ is a regular conjunction, not a correlative
            if text == "но" and tok.pos == "CCONJ":
                continue
            if tok.pos in ("CCONJ", "PART", "ADV"):
                return True
    return False


class CommaInsertHandler:
    """Insert spurious commas — creates extra-comma errors.

    Subtypes:
    - comma_before_kak: insert comma before "как" where it shouldn't be
    - comma_in_set_phrase: insert comma inside repeated conjunction phrases
    - comma_between_conjunctions: insert comma between adjacent conjunctions
    - comma_in_indivisible: insert comma inside indivisible expressions
    """

    name = "comma_insert"
    subtypes = [
        "comma_before_kak",
        "comma_in_set_phrase",
        "comma_between_conjunctions",
        "comma_in_indivisible",
    ]
    category = "PUNCT"
    changes_length = True

    DEFAULT_WEIGHTS = {
        "comma_before_kak": 35,
        "comma_in_set_phrase": 25,
        "comma_between_conjunctions": 20,
        "comma_in_indivisible": 20,
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

        # Indivisible expressions (цельные по смыслу сочетания)
        if text_lower in _INDIVISIBLE_INDEX and _matches_indivisible(tokens, idx) is not None:
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

        if text_lower in _INDIVISIBLE_INDEX and _matches_indivisible(tokens, idx) is not None:
            candidates.append(("comma_in_indivisible", self._weights["comma_in_indivisible"]))

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
        elif chosen == "comma_in_indivisible":
            return self._insert_in_indivisible(sentence, idx, tokens)

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

    def _insert_in_indivisible(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """Insert comma inside indivisible expression: как следует → как , следует."""
        phrase = _matches_indivisible(tokens, idx)
        if phrase is None:
            return None

        # Find the comma insertion point from the index
        candidates = _INDIVISIBLE_INDEX.get(tokens[idx].text.lower(), [])
        comma_pos = 1  # default: between first and second word
        for p, cp in candidates:
            if p == phrase:
                comma_pos = cp
                break

        insert_idx = idx + comma_pos
        if insert_idx >= len(sentence):
            return None

        sentence.insert(insert_idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_in_indivisible",
            category=self.category,
            start_idx=insert_idx,
            end_idx=insert_idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )
