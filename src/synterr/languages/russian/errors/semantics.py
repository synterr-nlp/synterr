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
from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
    inflect_word,
    match_capitalization,
)

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


# Grammemes that may be transferred from the original word's parse to the
# collocate replacement: POS class plus form-level (inflectional) values.
# Mirrors the paronym handler's approach (errors/lexical.py, the 98%-precision
# reference); kept local because that module is separately owned. Transferring
# the POS grammeme (PRTS/PRTF/...) and voice (actv/pssv) is what keeps a short
# passive participle a short passive participle: "принято" → "сделано", not
# the finite "сделало" (2026-07 annotation pass, 20/73 flagged). Lexeme-level
# grammemes (aspect, transitivity, Qual) must stay behind — the replacement
# lexeme often lacks them, which would make inflection fail spuriously.
_TRANSFER_POS = {
    "NOUN",
    "ADJF",
    "ADJS",
    "COMP",
    "VERB",
    "INFN",
    "PRTF",
    "PRTS",
    "GRND",
    "NUMR",
    "ADVB",
}
_TRANSFER_FORM = {
    "nomn",
    "gent",
    "datv",
    "accs",
    "ablt",
    "loct",
    "voct",
    "gen2",
    "loc2",
    "sing",
    "plur",
    "masc",
    "femn",
    "neut",
    "1per",
    "2per",
    "3per",
    "past",
    "pres",
    "futr",
    "actv",
    "pssv",
    "indc",
    "impr",
}
_ANIMACY = {"anim", "inan"}


def _transfer_grammemes(parse) -> set[str]:
    """Form-level grammemes to carry over to the collocate replacement."""
    grammemes = set(parse.tag.grammemes)
    transfer = grammemes & (_TRANSFER_POS | _TRANSFER_FORM)
    if "accs" in transfer:
        # Accusative surface form depends on animacy; without it pymorphy
        # would pick an arbitrary anim/inan variant.
        transfer |= grammemes & _ANIMACY
    return transfer


# UD features whose pymorphy equivalents must survive the swap intact:
# transferring an undisambiguated parse's case/gender/number would stack a
# spurious agreement error on top of the intended Lex error.
_UD_FEATURE_MAPS = (
    ("Case", UD_TO_PYMORPHY_CASE),
    ("Number", UD_TO_PYMORPHY_NUMBER),
    ("Gender", UD_TO_PYMORPHY_GENDER),
)


def _context_grammemes(token: AnalyzedToken) -> set[str]:
    """pymorphy grammemes implied by stanza's disambiguated features."""
    wanted: set[str] = set()
    for feature, mapping in _UD_FEATURE_MAPS:
        value = token.features.get(feature)
        grammeme = mapping.get(value) if value is not None else None
        if grammeme:
            wanted.add(grammeme)
    return wanted


def _consistent_parses(token: AnalyzedToken, word: str) -> list:
    """Parses of ``word`` consistent with stanza's disambiguated features.

    The stored ``pymorphy_parse`` (tried first) is context-free, and some
    wordforms are lexicalized under a different POS than the context uses:
    parse("установленный")[0] is the *adjective*, whose ADJF grammemes no
    verb lexeme can realize. Offering every feature-consistent parse lets the
    caller fall through to the PRTF parse and inflect "завоевать" correctly
    instead of skipping (or worse, guessing).
    """
    wanted = _context_grammemes(token)
    candidates = []
    stored = token.extra.get("pymorphy_parse") if token.extra else None
    if stored is not None:
        candidates.append(stored)
    candidates.extend(_morph().parse(word))
    return [p for p in candidates if wanted <= set(p.tag.grammemes)]


def _inflect_to_match(
    wrong_lemma: str, original_parse, *, same_pos: bool = False
) -> str | None:
    """Inflect `wrong_lemma` (a citation form) to carry original_parse's
    form-level grammemes. Returns the inflected surface form, or None if no
    parse of `wrong_lemma` can realize them — callers must then *skip* the
    corruption rather than fall back to the citation form (precision-first).

    With `same_pos=True`, only parses of `wrong_lemma` in the same coarse POS
    class as the original are considered. pymorphy ranks parses by corpus
    frequency, so parse("дорогой")[0] is the NOUN дорога in instrumental, not
    the adjective — inflecting that produced non-words like "по дороги цене".
    """
    if original_parse is None:
        return None

    grammemes = _transfer_grammemes(original_parse)
    if not grammemes:
        return None

    parses = _morph().parse(wrong_lemma)
    if not parses:
        return None
    target_class = _pos_class(original_parse.tag.POS)
    for new_parse in parses:
        if same_pos and _pos_class(new_parse.tag.POS) != target_class:
            continue
        inflected = inflect_word(new_parse, grammemes)
        if inflected is not None:
            return inflected
    return None


@lru_cache(maxsize=1)
def _load_pleonasms() -> dict[str, list[dict[str, str]]]:
    path = _data_path() / "pleonasms.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def _is_preposition(word: str) -> bool:
    """Whether pymorphy reads ``word`` as a preposition (any parse)."""
    try:
        return any(str(p.tag.POS) == "PREP" for p in _morph().parse(word))
    except Exception:
        return False


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
        # Lemmatize the redundant word so an inflected occurrence in the text
        # still matches. For phrase entries take the first *content* word:
        # "в первый раз" must be keyed on "первый", not on the preposition
        # "в", which co-occurs with nearly everything.
        words = red.split()
        red_first = next(
            (w for w in words if not _is_preposition(w)), words[0] if words else red
        )
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

    # Frozen expressions where the core word cannot take the redundant
    # modifier: "в конечном итоге/счёте" is an adverbial idiom
    # ("eventually"), so "в окончательном конечном итоге" came out as
    # garbage, not as the Rozental §141 pleonasm «окончательный конечный»
    # targets (2026-07 annotation pass). Keyed by core lemma → lemmas of the
    # following word that freeze it.
    _IDIOM_NEXT_LEMMAS = {"конечный": frozenset({"итог", "счёт"})}

    # Nominal POS tags (UD and pymorphy) that read as the start of a noun
    # complement after the core noun.
    _NOMINAL_POS = frozenset({"NOUN", "PROPN", "PRON", "NPRO"})

    @staticmethod
    def _is_numeric(token: AnalyzedToken) -> bool:
        if str(token.pos) in ("NUM", "NUMR"):
            return True
        if any(ch.isdigit() for ch in token.text):
            return True
        try:
            return any(
                str(p.tag.POS) == "NUMR" for p in _morph().parse(token.text.lower())
            )
        except Exception:
            return False

    def _core_blocked(
        self, tokens: Sequence[AnalyzedToken], idx: int, lemma: str
    ) -> bool:
        """Context-level guards on the core word itself (2026-07 pass).

        - PROPN cores are names, not the dictionary word the entry targets:
          the spacecraft "Прогресс М1-11" is not the noun прогресс.
        - Idiom guard: see _IDIOM_NEXT_LEMMAS.
        - "<numeral> с половиной" is a quantity construction ("три с
          половиной процента"); inserting «большей» into it produced
          garbage, while "большая половина зрителей" stays a valid target.
        """
        token = tokens[idx]
        if str(token.pos) == "PROPN":
            return True
        blocked_next = self._IDIOM_NEXT_LEMMAS.get(lemma)
        if blocked_next and idx + 1 < len(tokens):
            nxt = tokens[idx + 1]
            if (nxt.lemma or nxt.text).lower() in blocked_next:
                return True
        if lemma == "половина" and idx >= 2:
            if tokens[idx - 1].text.lower() == "с" and self._is_numeric(
                tokens[idx - 2]
            ):
                return True
        return False

    def _after_insert_blocked(
        self, tokens: Sequence[AnalyzedToken], idx: int, redundant: str
    ) -> bool:
        """Whether inserting `redundant` after the core would sever the core
        noun from its own complement.

        The after-entries for noun cores are bare genitive attributes
        ("народа", "времени"): dropping one between the core and an existing
        nominal complement produced "толпой народу демонстрантов" (2026-07
        annotation pass). Only applies to noun core + noun insert; PP phrases
        and adverbs ("вернуться обратно домой") stay grammatical.
        """
        if " " in redundant:
            return False
        token = tokens[idx]
        if str(token.pos) not in ("NOUN", "PROPN"):
            return False
        parses = _morph().parse(redundant)
        if not parses or str(parses[0].tag.POS) != "NOUN":
            return False
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
        if nxt is not None:
            if str(nxt.pos) in self._NOMINAL_POS:
                return True
            if nxt.get_feature("Case") == "Gen":
                return True
        # Dep fallback: any following nmod dependent of the core noun.
        return any(t.head_idx == idx and t.dep_rel == "nmod" for t in tokens[idx + 1 :])

    def _entry_blocked(
        self, tokens: Sequence[AnalyzedToken], idx: int, entry: dict[str, str]
    ) -> bool:
        word = entry["word"]
        pos = entry.get("pos", "before")
        # C3 (2026-07 audit): a multiword insertion ("в первый раз") lands as
        # a single element of the corrupted-token list carrying one $DELETE
        # tag; re-splitting the joined sentence on whitespace downstream then
        # desyncs the token/tag counts (one tag, three surface tokens). The
        # ErrorResult contract has no span-aware way to emit per-token tags
        # for an insertion (mirrors the single-token filler filter in
        # WordInsertionHandler, structural.py), so these entries are never
        # selected. They stay in pleonasms.json as documentation of the
        # attested pattern but are permanently inert until span-aware output
        # lands.
        if " " in word:
            return True
        if self._redundant_present(tokens, idx, word, pos):
            return True
        if pos == "after" and self._after_insert_blocked(tokens, idx, word):
            return True
        # C2 (2026-07 audit): a sentence-initial capitalized core needs two
        # edits to reconstruct from a corruption that both capitalizes the
        # inserted word and lowercases the core ("Ветеран выступил" ->
        # "Старый ветеран выступил") — but only one $DELETE fix tag is
        # emitted, on the inserted word. Deleting it restores "ветеран
        # выступил" (lowercase), not the original "Ветеран выступил": the
        # core's capitalization is unrecoverable from the single edit. Skip
        # rather than emit an uncorrectable corruption (mirrors
        # DoubleComparativeHandler's `if word[:1].isupper(): return None` in
        # morphological.py).
        if pos == "before" and idx == 0 and tokens[idx].text[:1].isupper():
            return True
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
        if self._core_blocked(tokens, idx, lemma):
            return False
        # At least one entry must not already be present adjacently.
        entries = self.pleonasms.get(lemma) or []
        return any(not self._entry_blocked(tokens, idx, e) for e in entries)

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
        if self._core_blocked(tokens, idx, lemma):
            return None

        # Only consider entries whose redundant word isn't already adjacent
        # and whose insertion point is safe.
        usable = [e for e in entries if not self._entry_blocked(tokens, idx, e)]
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
            # Multiword entries never reach `usable` (_entry_blocked filters
            # them, C3 audit); after-inserts (invariant genitives like
            # "времени") go in as-is.
            if pos == "before":
                candidate = self._prepare_before_insert(candidate, token)
            if candidate is not None:
                redundant = candidate
                break
        if redundant is None:
            return None

        if pos == "before":
            # Sentence-initial capitalized cores are filtered out by
            # _entry_blocked (C2, 2026-07 audit) — a single $DELETE tag can't
            # also restore the core's original capitalization, so entries
            # reaching this branch at idx == 0 always have a lowercase core.
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

        # Inflect the replacement to match the original token's morphology so
        # "принял решение" → "сделал решение" (not the bare infinitive
        # "сделать решение") and "принято решение" → "сделано" (not the
        # finite "сделало"). If no feature-consistent parse of the original
        # can be realized on the replacement lexeme, skip — emitting the
        # citation form stacked a spurious form error on top of the intended
        # Lex error (2026-07 annotation pass). same_pos guards against
        # frequency-ranked homograph parses (parse("дорогой")[0] is the noun
        # дорога).
        wrong_word: str | None = None
        for original_parse in _consistent_parses(token, word):
            wrong_word = _inflect_to_match(
                entry["wrong"], original_parse, same_pos=True
            )
            if wrong_word is not None:
                break
        if wrong_word is None:
            return None

        wrong_word = match_capitalization(word, wrong_word)

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
