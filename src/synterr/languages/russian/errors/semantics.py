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
def _morph():
    """Lazily build a shared pymorphy3 analyzer (heavy to instantiate)."""
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


# Grammeme categories copied from the original token onto the replacement,
# in priority order. We try the full set first, then drop trailing categories
# until pymorphy can inflect — so a verb keeps tense+number+gender+person but
# degrades gracefully if a combination is invalid.
_INFLECT_ATTRS = ("tense", "number", "gender", "person", "case", "mood", "aspect")


def _inflect_to_match(wrong_lemma: str, original_parse) -> str | None:
    """Inflect `wrong_lemma` (a citation form) to match original_parse's
    grammemes. Returns the inflected surface form, or None if inflection
    failed at every fallback level."""
    if original_parse is None:
        return None

    target_tag = original_parse.tag
    grammemes: list[str] = []
    for attr in _INFLECT_ATTRS:
        val = getattr(target_tag, attr, None)
        if val is not None:
            grammemes.append(val)

    parses = _morph().parse(wrong_lemma)
    if not parses:
        return None
    new_parse = parses[0]

    # Try full grammeme set, then progressively shorter prefixes.
    for k in range(len(grammemes), 0, -1):
        result = new_parse.inflect(set(grammemes[:k]))
        if result is not None:
            return result.word
    return None


@lru_cache(maxsize=1)
def _load_pleonasms() -> dict[str, list[dict[str, str]]]:
    path = _data_path() / "pleonasms.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def _lemmatize(word: str) -> str:
    """Normal form of `word`, lowercased. Falls back to the lowercased word."""
    try:
        parses = _morph().parse(word)
        if parses:
            return parses[0].normal_form.lower()
    except Exception:
        pass
    return word.lower()


@lru_cache(maxsize=1)
def _load_collocations() -> dict[str, list[dict[str, str]]]:
    path = _data_path() / "collocations.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    # The data file keeps collocates human-readable (often inflected, e.g.
    # "победу", "реакцию"), but the matcher compares against token *lemmas*.
    # Normalize collocate values to their lemma at load time so inflected
    # entries fire instead of becoming dead no-ops.
    collocations: dict[str, list[dict[str, str]]] = {}
    for verb, entries in data.items():
        if verb.startswith("_"):
            continue
        collocations[verb] = [
            {**entry, "collocate": _lemmatize(entry["collocate"])} for entry in entries
        ]
    return collocations


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

    @staticmethod
    def _redundant_present(
        tokens: Sequence[AnalyzedToken], idx: int, redundant: str, pos: str
    ) -> bool:
        """Whether the redundant word is already adjacent to the core word.

        Inserting "своя" before "автобиографию" in "написал свою
        автобиографию" would produce "свою своя автобиографию" — a repetition,
        not a pleonasm. The data stores citation forms ("своя") while the text
        has inflected forms ("свою"), so we compare at the lemma level.
        """
        red = redundant.lower()
        # Lemmatize the redundant word (first token if it's a phrase) so an
        # inflected occurrence in the text still matches.
        red_first = red.split()[0] if red else red
        red_lemmas = {red_first}
        try:
            for p in _morph().parse(red_first):
                red_lemmas.add(p.normal_form.lower())
        except Exception:
            pass

        def matches(t: AnalyzedToken) -> bool:
            if t.text.lower() == red or t.text.lower() == red_first:
                return True
            return bool(t.lemma and t.lemma.lower() in red_lemmas)

        if pos == "before":
            window = range(max(0, idx - 2), idx)
        else:
            window = range(idx + 1, min(len(tokens), idx + 3))
        return any(matches(tokens[j]) for j in window)

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        lemma = token.lemma.lower() if token.lemma else token.text.lower()
        if lemma not in self.pleonasms:
            return False
        # At least one entry must not already be present adjacently.
        entries = self.pleonasms.get(lemma) or []
        return any(
            not self._redundant_present(tokens, idx, e["word"], e.get("pos", "before"))
            for e in entries
        )

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

        # Only consider entries whose redundant word isn't already adjacent.
        usable = [
            e
            for e in entries
            if not self._redundant_present(
                tokens, idx, e["word"], e.get("pos", "before")
            )
        ]
        if not usable:
            return None

        entry = rng.choice(usable)
        redundant = entry["word"]
        pos = entry.get("pos", "before")

        # Agreement: a single-word adjectival/pronoun modifier inserted before
        # a noun should agree with it in case/number/gender ("своя" →
        # "свою автобиографию"). Only attempt for single tokens; fixed phrases
        # ("из армии", "первый раз") and adverbs stay as-is.
        if pos == "before" and " " not in redundant:
            core_parse = token.extra.get("pymorphy_parse") if token.extra else None
            if core_parse is not None and core_parse.tag.POS in (
                "NOUN",
                "NPRO",
            ):
                agreed = _inflect_to_match(redundant, core_parse)
                if agreed:
                    redundant = agreed

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

        # Inflect the replacement to match the original token's morphology so
        # "принял решение" → "сделал решение" (not the bare infinitive
        # "сделать решение"). Falls back to the citation form if pymorphy
        # can't inflect.
        original_parse = token.extra.get("pymorphy_parse") if token.extra else None
        inflected = _inflect_to_match(wrong_word, original_parse)
        if inflected:
            wrong_word = inflected

        # Match capitalization of the original word
        if word[:1].isupper():
            wrong_word = wrong_word[:1].upper() + wrong_word[1:]

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
