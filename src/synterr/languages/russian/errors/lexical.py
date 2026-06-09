"""Russian lexical error handlers - paronyms, ..."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken, ErrorResult
from synterr.languages.russian.errors.morphological import (
    _get_pymorphy_parse,
    inflect_word,
)
from synterr.languages.russian.inflector import match_capitalization

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

# Groups whose key starts with this prefix are directed confusions: only the
# first member may be corrupted (e.g. чем→как is an attested error, but
# как→чем is garbage no learner produces).
_DIRECTED_PREFIX = "directed_"


def _confusion_candidates(group_key: str, members: list[str], word: str) -> list[str]:
    """Single-token replacement candidates for ``word`` within one group.

    Returns [] when the word is not a valid corruption source in this group
    (absent, or a non-head member of a directed group). Multi-word entries are
    never offered: a length-preserving $REPLACE cannot emit an intra-token
    space without misaligning the token/tag stream.
    """
    if group_key.startswith(_DIRECTED_PREFIX):
        if word != members[0]:
            return []
        pool = members[1:]
    else:
        if word not in members:
            return []
        pool = members
    return [x for x in pool if x != word and " " not in x]


def _has_confusion(groups: dict[str, list[str]], word: str) -> bool:
    return any(
        _confusion_candidates(key, members, word)
        for key, members in groups.items()
    )


def _pick_confusion(
    groups: dict[str, list[str]], word: str, rng: Random
) -> str | None:
    for key, members in groups.items():
        candidates = _confusion_candidates(key, members, word)
        if candidates:
            return rng.choice(candidates)
    return None


class ParonymErrorHandler:
    """Replace word from paronyms list to one from its paronyms"""

    name = "paronym"
    subtypes = ["paronym"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._paronyms = None
        self.__morph = None

    @property
    def _morph(self):
        if self.__morph is None:
            from synterr.languages.russian.resources import get_morph_analyzer

            self.__morph = get_morph_analyzer()
        return self.__morph

    @property
    def paronyms(self):
        if self._paronyms is None:
            from synterr.languages.russian.resources import get_paronyms

            self._paronyms = get_paronyms()
        return self._paronyms

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return tokens[idx].lemma in self.paronyms

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply paronym error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None or token.lemma not in self.paronyms:
            return None

        grammemes = set(parse.tag.grammemes)

        new_word_lemma = rng.choice(self.paronyms.get(token.lemma))
        new_word_parse = self._morph.parse(new_word_lemma)[0]
        new_word = inflect_word(new_word_parse, grammemes, word)
        if new_word is None:
            return None
        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


class PrepositionErrorHandler:
    """Replace preposition with an attested confusion from the same group.

    Groups in ``prepositions.json`` are *confusion* sets, not synonym sets:
    every swap must yield a genuine error (attested learner confusion like
    в/на, из/с, or a different-government pair like благодаря/из-за where the
    unreinflected complement exposes the error). Synonymous prepositions with
    identical government (у ~ при ~ около ~ возле, через ~ сквозь — Rozental
    §199) are excluded: swapping them produces correct Russian, which would
    teach a GEC model to rewrite valid text.

    The handler is length-preserving (single ``$REPLACE``), so it only
    substitutes single-token replacements. Multi-word entries in the lexicon
    (e.g. ``"по причине"``) are skipped: writing one into a single token slot
    would smuggle an intra-token space into the GECToR unit and misalign the
    token/tag stream.
    """

    name = "preposition"
    subtypes = ["preposition"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._prepositions = None

    @property
    def prepositions(self):
        if self._prepositions is None:
            from synterr.languages.russian.resources import get_preposition_list

            self._prepositions = get_preposition_list()
        return self._prepositions

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos != "ADP":
            return False
        return _has_confusion(self.prepositions, tokens[idx].lemma)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply preposition error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos != "ADP":
            return None

        new_word = _pick_confusion(self.prepositions, word.lower(), rng)
        if new_word is None:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


class ConjunctionErrorHandler:
    """Replace conjunction with an attested confusion from the same group.

    Groups in ``conjunctions.json`` are *confusion* sets, not synonym sets:
    pure synonyms (или ~ либо, и ~ да, хотя ~ хоть — equivalent variants in
    Rozental's rules on homogeneous members) are excluded because swapping
    them yields correct Russian. ``directed_*`` groups corrupt only their
    first member (чем→как is an attested error; как→чем is impossible).
    """

    name = "conjunction"
    subtypes = ["conjunction"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._conjunctions = None

    @property
    def conjunctions(self):
        if self._conjunctions is None:
            from synterr.languages.russian.resources import get_conjunction_list

            self._conjunctions = get_conjunction_list()
        return self._conjunctions

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos not in ["CCONJ", "SCONJ"]:
            return False
        return _has_confusion(self.conjunctions, tokens[idx].lemma)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply conjunction error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos not in ["CCONJ", "SCONJ"]:
            return None

        new_word = _pick_confusion(self.conjunctions, word.lower(), rng)
        if new_word is None:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
