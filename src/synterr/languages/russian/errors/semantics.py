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

# Coarse POS classes for matching a replacement's parse to the original
# token. Lexicon citation forms are infinitives (INFN) while tokens in text
# are finite (VERB), so exact-POS comparison would wrongly reject every
# verb pair.
_POS_CLASSES = {
    "VERB": "VERB",
    "INFN": "VERB",
    "PRTF": "VERB",
    "PRTS": "VERB",
    "GRND": "VERB",
    "ADJF": "ADJ",
    "ADJS": "ADJ",
    "COMP": "ADJ",
}


def _pos_class(pos: str | None) -> str | None:
    # str() strips pymorphy's grammeme str-subclass, whose __eq__ raises on
    # comparison with anything outside the OpenCorpora grammeme inventory
    # (like our coarse class names).
    return _POS_CLASSES.get(str(pos), str(pos)) if pos else None


def _inflect_to_match(
    wrong_lemma: str, original_parse, *, same_pos: bool = False
) -> str | None:
    """Inflect `wrong_lemma` (a citation form) to match original_parse's
    grammemes. Returns the inflected surface form, or None if inflection
    failed at every fallback level.

    With `same_pos=True`, only parses of `wrong_lemma` in the same coarse POS
    class as the original are considered. pymorphy ranks parses by corpus
    frequency, so parse("дорогой")[0] is the NOUN дорога in instrumental, not
    the adjective — inflecting that produced non-words like "по дороги цене".
    """
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
    if same_pos:
        target_class = _pos_class(target_tag.POS)
        new_parse = next(
            (p for p in parses if _pos_class(p.tag.POS) == target_class), None
        )
        if new_parse is None:
            return None
    else:
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

    # Clause-level boundaries that end the scan for an already-present
    # redundant word: a verb/punctuation/preposition means we have left the
    # core word's own phrase, where doubling would be visible. Both UD
    # (stanza) and OpenCorpora (pymorphy) POS names are listed.
    _NP_BOUNDARY_POS = frozenset(
        {"VERB", "AUX", "INFN", "GRND", "PUNCT", "ADP", "PREP"}
    )
    _REDUNDANT_SCAN_CAP = 6

    @classmethod
    def _redundant_present(
        cls, tokens: Sequence[AnalyzedToken], idx: int, redundant: str, pos: str
    ) -> bool:
        """Whether the redundant word already occurs in the core word's phrase.

        Inserting "своя" before "автобиографию" in "написал свою
        автобиографию" would produce "свою своя автобиографию" — a repetition,
        not a pleonasm. The data stores citation forms ("своя") while the text
        has inflected forms ("свою"), so we compare at the lemma level.

        The scan covers the whole noun phrase (up to a clause boundary or
        _REDUNDANT_SCAN_CAP tokens), not just adjacent tokens — "свою очень
        подробную автобиографию" must block insertion just like "свою
        автобиографию" (2026-06 audit).
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

        step = -1 if pos == "before" else 1
        j = idx + step
        for _ in range(cls._REDUNDANT_SCAN_CAP):
            if not 0 <= j < len(tokens):
                break
            if matches(tokens[j]):
                return True
            if str(tokens[j].pos) in cls._NP_BOUNDARY_POS:
                break
            j += step
        return False

    # Inserted single words in these POS classes must agree with the core
    # word; anything else (adverbs like "вновь", "заранее") is invariant.
    _DECLINABLE_INSERT_POS = ("ADJF", "PRTF", "NPRO", "NUMR")

    def _prepare_before_insert(
        self, redundant: str, token: AnalyzedToken
    ) -> str | None:
        """Surface form for a single-word `pos=before` insert.

        Declinable modifiers must agree with the core token (2026-06 audit:
        "окончательный конечной остановке", "первым лидировала" were
        agreement garbage). Returns None when agreement is required but
        cannot be established — the caller skips the entry.
        """
        parses = _morph().parse(redundant)
        if not parses:
            return redundant
        red_parse = next(
            (p for p in parses if str(p.tag.POS) in self._DECLINABLE_INSERT_POS),
            parses[0],
        )
        red_pos = str(red_parse.tag.POS)
        if red_pos not in self._DECLINABLE_INSERT_POS and red_pos != "NOUN":
            return redundant  # invariant word (adverb etc.) — insert as-is

        core_parse = token.extra.get("pymorphy_parse") if token.extra else None
        if core_parse is None:
            return None
        tag = core_parse.tag
        core_pos = str(tag.POS)

        if core_pos in ("NOUN", "NPRO", "ADJF", "PRTF"):
            # Modifier agrees with the core in case/number/gender ("своя" →
            # "свою автобиографию", "окончательный" → "окончательной
            # конечной"). A noun insert ("воспоминания мемуары") keeps its
            # own lexical gender — copy only case/number.
            if red_pos == "NOUN":
                wanted = (tag.case, tag.number)
            else:
                wanted = (tag.case, tag.number, tag.gender)
            grams = {g for g in wanted if g is not None}
            if not grams:
                return None
            result = red_parse.inflect(grams)
            return result.word if result else None

        if core_pos in ("VERB", "INFN"):
            # "первым лидировал": the modifier keeps its own case but agrees
            # with the verb in gender/number. Present-tense forms carry no
            # gender — agreement unestablishable, skip.
            if tag.gender is not None and tag.number is not None:
                result = red_parse.inflect({tag.gender, tag.number})
            elif str(tag.number) == "plur":
                result = red_parse.inflect({"plur"})
            else:
                return None
            return result.word if result else None

        return None

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

        # Pick in random order; entries whose modifier can't be made to
        # agree with the core token are skipped, not inserted uninflected.
        entry_order = list(usable)
        rng.shuffle(entry_order)
        redundant: str | None = None
        pos = "before"
        for entry in entry_order:
            candidate = entry["word"]
            pos = entry.get("pos", "before")
            # Fixed phrases ("из армии", "первый раз") and after-inserts
            # (invariant genitives like "времени") go in as-is.
            if pos == "before" and " " not in candidate:
                candidate = self._prepare_before_insert(candidate, token)
            if candidate is not None:
                redundant = candidate
                break
        if redundant is None:
            return None

        if pos == "before":
            # Sentence-initial core: transfer capitalization to the inserted
            # word ("Ветеран выступил" → "Старый ветеран выступил", not
            # "старый Ветеран"). Acronyms/proper nouns are left alone.
            core_word = sentence[idx]
            transfer_cap = (
                idx == 0
                and core_word[:1].isupper()
                and not core_word.isupper()
                and str(token.pos) != "PROPN"
            )
            if transfer_cap:
                redundant = redundant[:1].upper() + redundant[1:]
            sentence.insert(idx, redundant)
            if transfer_cap:
                sentence[idx + 1] = core_word[0].lower() + core_word[1:]
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

    @staticmethod
    def _collocate_linked(tokens: Sequence[AnalyzedToken], idx: int, j: int) -> bool:
        """Whether the collocate at `j` is syntactically tied to the word
        at `idx`.

        A lemma merely co-occurring in the ±5 window is not enough: in
        "принял гостей, обсуждавших решение" the object of "принял" is
        "гостей", and replacing the verb would not instantiate the
        принять+решение collocation (2026-06 audit). With depparse on we
        require a direct dependency arc in either direction (verb→obj, or
        amod adjective→head noun); without dep info, adjacency.
        """
        target, coll = tokens[idx], tokens[j]
        if target.head_idx is not None or coll.head_idx is not None:
            return coll.head_idx == idx or target.head_idx == j
        return abs(idx - j) == 1

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        lemma = token.lemma.lower() if token.lemma else token.text.lower()
        if lemma not in self.collocations:
            return False

        # Check if any collocate noun is nearby (within ±5 tokens) and
        # actually linked to this word
        entries = self.collocations[lemma]
        collocate_lemmas = {e["collocate"] for e in entries}

        for j in range(max(0, idx - 5), min(len(tokens), idx + 6)):
            if j == idx:
                continue
            other_lemma = (
                tokens[j].lemma.lower() if tokens[j].lemma else tokens[j].text.lower()
            )
            for cl in collocate_lemmas:
                if other_lemma == cl and self._collocate_linked(tokens, idx, j):
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

        # Find which collocate is actually present nearby and linked
        matching_entries = []
        for entry in entries:
            cl = entry["collocate"]
            for j in range(max(0, idx - 5), min(len(tokens), idx + 6)):
                if j == idx:
                    continue
                other_lemma = tokens[j].lemma.lower() if tokens[j].lemma else ""
                if other_lemma == cl and self._collocate_linked(tokens, idx, j):
                    matching_entries.append(entry)
                    break

        if not matching_entries:
            return None

        entry = rng.choice(matching_entries)
        wrong_word = entry["wrong"]

        # Inflect the replacement to match the original token's morphology so
        # "принял решение" → "сделал решение" (not the bare infinitive
        # "сделать решение"). Falls back to the citation form if pymorphy
        # can't inflect. same_pos guards against frequency-ranked homograph
        # parses (parse("дорогой")[0] is the noun дорога).
        original_parse = token.extra.get("pymorphy_parse") if token.extra else None
        inflected = _inflect_to_match(wrong_word, original_parse, same_pos=True)
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
