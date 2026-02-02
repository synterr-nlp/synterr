"""Russian lexical error handlers - paronyms, ..."""

from __future__ import annotations

import json
import random as random_module
from typing import TYPE_CHECKING

import pymorphy3

from synterr.core.protocol import AnalyzedToken, ErrorResult
from synterr.languages.russian.errors.morphological import (
    _get_pymorphy_parse,
    inflect_word,
)
from synterr.languages.russian.inflector import match_capitalization

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random


def load_paronyms_dict(filepath: str) -> dict[str, list[str]]:
    """
    Load paronyms list from JSON file

    Args:
        filepath (str): Path to JSON file with paronyms dictionary

    Returns:
        Dict[str, List[str]]: Dictionary with paronyms mapping
    """

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    paronyms = {key: value for key, value in data.items() if not key.startswith("_")}

    return paronyms


def load_prepositions_dict_from_file(filepath: str) -> dict[str, list[str]]:
    """
    Load prepositions list from JSON file

    Args:
        filepath (str): Path to JSON file with prepositions

    Returns:
        Dict[str, List[str]]: Dictionary of preposition groups
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    prepositions_dict = {}

    for key, value in data.items():
        if key == "_meta":
            continue

        if isinstance(value, list):
            prepositions_dict[key] = value
        else:
            prepositions_dict[key] = []

    return prepositions_dict


class ParonymErrorHandler:
    """Replace word from paronyms list to one from its paronyms"""

    name = "paronym"
    subtypes = ["paronym"]
    category = "OTHER"
    changes_length = False

    def __init__(
        self,
        path_to_paronyms_dict="src/synterr/data/russian/paronyms.json",
    ):
        self.paronyms = load_paronyms_dict(path_to_paronyms_dict)
        self.morph = pymorphy3.MorphAnalyzer()

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

        if parse is None:
            return None

        grammemes = set(parse.tag.grammemes)

        new_word_lemma = rng.choice(self.paronyms.get(token.lemma))
        new_word_token = AnalyzedToken(
            new_word_lemma,
            new_word_lemma,
            parse.tag.POS,
            {},
            extra={"pymorphy_parse": self.morph.parse(new_word_lemma)[0]},
        )
        new_word_parse = _get_pymorphy_parse(new_word_token)
        new_word = inflect_word(new_word_parse, grammemes)
        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type="paronym",
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

    def __init__(
        self,
        path_to_prepositions_dict="src/synterr/data/russian/prepositions.json",
    ):
        self.prepositions = load_paronyms_dict(path_to_prepositions_dict)

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
        """Apply paronym error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos != "ADP":
            return None

        for v in self.prepositions.values():
            if word.lower() in v:
                new_word = rng.choice([x for x in v if x != word.lower()])
                break
        else:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type="preposition",
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

    def __init__(
        self,
        path_to_conjunctions_dict="src/synterr/data/russian/conjunctions.json",
    ):
        self.conjunctions = load_paronyms_dict(path_to_conjunctions_dict)

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
        """Apply paronym error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos not in ["CCONJ", "SCONJ"]:
            return None

        for v in self.conjunctions.values():
            if word.lower() in v:
                new_word = rng.choice([x for x in v if x != word.lower()])
                break
        else:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type="conjunction",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
