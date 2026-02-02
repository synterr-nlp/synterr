import json
import random as random_module
from collections.abc import Sequence
from random import Random

from synterr import AnalyzedToken
from synterr.core.protocol import ErrorResult

OMITTABLE_POS = {"ADP", "PART", "CCONJ", "SCONJ"}


def load_filler_list(filepath: str) -> list[str]:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    fillers = data.get("fillers", [])

    return fillers


class WordOmissionHandler:
    name = "word_omission"
    subtypes = ["word_omission"]  # ~ Syntax+Miss в RLC
    category = "OTHER"
    changes_length = True

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int):
        if idx == 0:
            return False
        return tokens[idx].pos in OMITTABLE_POS

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ):
        deleted_word = sentence[idx]

        del sentence[idx]

        return ErrorResult(
            error_type="word_omission",
            category="STRUCTURAL",
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=deleted_word,
            corrupted="",
            fix_tag=f"$APPEND_{deleted_word}",
        )


class WordInsertionHandler:
    name = "word_insertion"
    subtypes = ["word_insertion"]  # Маппится на Syntax+Extra в RLC
    category = "OTHER"
    changes_length = True

    def __init__(
        self,
        path_to_fillers_dict="src/synterr/data/russian/fillers.json",
    ):
        self.fillers = load_filler_list(path_to_fillers_dict)

    def can_apply(self, tokens, idx):
        return idx < len(tokens) - 1

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ):
        rng = rng if rng is not None else random_module

        filler = rng.choice(self.fillers)

        sentence.insert(idx + 1, filler)

        return ErrorResult(
            error_type="word_insertion",
            category="STRUCTURAL",
            start_idx=idx + 1,
            end_idx=idx + 1,
            original="",
            corrupted=filler,
            fix_tag="$DELETE",
        )
