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
    """Replace preposition to another preposition from the same semantic group"""

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
        return tokens[idx].pos == "ADP" and any(
            tokens[idx].lemma in lst for lst in self.prepositions.values()
        )

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

        for v in self.prepositions.values():
            if word.lower() in v:
                candidates = [x for x in v if x != word.lower()]
                if not candidates:
                    return None
                new_word = rng.choice(candidates)
                break
        else:
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
    """Replace conjunction to another conjunction from the same semantic group"""

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
        return tokens[idx].pos in ["CCONJ", "SCONJ"] and any(
            tokens[idx].lemma in lst for lst in self.conjunctions.values()
        )

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

        for v in self.conjunctions.values():
            if word.lower() in v:
                candidates = [x for x in v if x != word.lower()]
                if not candidates:
                    return None
                new_word = rng.choice(candidates)
                break
        else:
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
