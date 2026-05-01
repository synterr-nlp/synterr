"""Russian semantic error handlers — pleonasms and collocation violations.

Covers LoRuGEC rules:
- Rule 34: Лексическая сочетаемость слов (collocation errors)
- Rule 35: Плеоназмы (redundant word combinations)

Rozental §139–143 (Part III, Stylistics).
"""

from __future__ import annotations

import json
import random as random_module
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


def _data_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / "data" / "russian"


@lru_cache(maxsize=1)
def _load_pleonasms() -> dict[str, list[dict[str, str]]]:
    path = _data_path() / "pleonasms.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


@lru_cache(maxsize=1)
def _load_collocations() -> dict[str, list[dict[str, str]]]:
    path = _data_path() / "collocations.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


class PleonasmHandler:
    """Insert redundant words to create pleonasm errors.

    Example: "автобиография" → "своя автобиография" (insert redundant modifier).
    """

    name = "pleonasm"
    subtypes = ["pleonasm"]
    category = "OTHER"
    changes_length = True

    def __init__(self):
        self._pleonasms: dict[str, list[dict[str, str]]] | None = None

    @property
    def pleonasms(self) -> dict[str, list[dict[str, str]]]:
        if self._pleonasms is None:
            self._pleonasms = _load_pleonasms()
        return self._pleonasms

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        lemma = token.lemma.lower() if token.lemma else token.text.lower()
        return lemma in self.pleonasms

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
        lemma = token.lemma.lower() if token.lemma else token.text.lower()

        entries = self.pleonasms.get(lemma)
        if not entries:
            return None

        entry = rng.choice(entries)
        redundant = entry["word"]
        pos = entry.get("pos", "before")

        if pos == "before":
            # Insert redundant word before the core word
            sentence.insert(idx, redundant)
            return ErrorResult(
                error_type="pleonasm_pleonasm",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original="",
                corrupted=redundant,
                fix_tag="$DELETE",
            )
        else:
            # Insert redundant word after the core word
            insert_idx = idx + 1
            sentence.insert(insert_idx, redundant)
            return ErrorResult(
                error_type="pleonasm_pleonasm",
                category=self.category,
                start_idx=insert_idx,
                end_idx=insert_idx + 1,
                original="",
                corrupted=redundant,
                fix_tag="$DELETE",
            )


class CollocationHandler:
    """Replace correct verb/adjective with wrong collocate.

    Example: "принять решение" → "сделать решение" (wrong verb for this noun).
    """

    name = "collocation"
    subtypes = ["collocation"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._collocations: dict[str, list[dict[str, str]]] | None = None

    @property
    def collocations(self) -> dict[str, list[dict[str, str]]]:
        if self._collocations is None:
            self._collocations = _load_collocations()
        return self._collocations

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        lemma = token.lemma.lower() if token.lemma else token.text.lower()
        if lemma not in self.collocations:
            return False

        # Check if any collocate noun is nearby (within ±5 tokens)
        entries = self.collocations[lemma]
        collocate_lemmas = {e["collocate"] for e in entries}

        for j in range(max(0, idx - 5), min(len(tokens), idx + 6)):
            if j == idx:
                continue
            other_lemma = (
                tokens[j].lemma.lower() if tokens[j].lemma else tokens[j].text.lower()
            )
            for cl in collocate_lemmas:
                if other_lemma == cl:
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
        lemma = token.lemma.lower() if token.lemma else token.text.lower()
        word = sentence[idx]

        entries = self.collocations.get(lemma)
        if not entries:
            return None

        # Find which collocate is actually present nearby
        matching_entries = []
        for entry in entries:
            cl = entry["collocate"]
            for j in range(max(0, idx - 5), min(len(tokens), idx + 6)):
                if j == idx:
                    continue
                other_lemma = tokens[j].lemma.lower() if tokens[j].lemma else ""
                if other_lemma == cl:
                    matching_entries.append(entry)
                    break

        if not matching_entries:
            return None

        entry = rng.choice(matching_entries)
        wrong_word = entry["wrong"]

        # Try to preserve the original word's inflection
        # Simple approach: if original is capitalized, capitalize replacement
        if word[0].isupper():
            wrong_word = wrong_word[0].upper() + wrong_word[1:]

        sentence[idx] = wrong_word

        return ErrorResult(
            error_type="collocation_collocation",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=wrong_word,
            fix_tag=f"$REPLACE_{word}",
        )
