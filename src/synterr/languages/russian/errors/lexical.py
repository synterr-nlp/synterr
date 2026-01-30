"""Russian lexical error handlers - paronyms, ..."""

from __future__ import annotations

import json
import random as random_module
from typing import TYPE_CHECKING

import pymorphy3

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.errors.morphological import (
    _get_pymorphy_parse,
    inflect_word,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


def load_paronyms_dict(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    paronyms = {key: value for key, value in data.items() if not key.startswith("_")}

    return paronyms


# TODO: придумать, как не создавать каждый раз MorphAnalyzer
class ParonymErrorHandler:
    """Replace word from paronyms list to one from its paronyms"""

    name = "paronym"
    subtypes = ["paronym"]
    category = "LEX"
    changes_length = False

    def __init__(
        self,
        path_to_paronyms_dict="src/synterr/data/russian/paronyms.json",
    ):
        self.paronyms = load_paronyms_dict(path_to_paronyms_dict)  # dict[str, list[str]]
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
