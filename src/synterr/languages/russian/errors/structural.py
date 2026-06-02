"""Russian structural error handlers - word omission and insertion."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

OMITTABLE_POS = {"ADP", "PART", "CCONJ", "SCONJ"}


class WordOmissionHandler:
    """Delete a function word (preposition, particle, conjunction, punctuation)."""

    name = "word_omission"
    subtypes = ["word_omission"]
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
        if idx == 0 or tokens[idx].pos not in OMITTABLE_POS:
            return None

        deleted_word = sentence[idx]

        del sentence[idx]

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=deleted_word,
            corrupted="",
            fix_tag=f"$APPEND_{deleted_word}",
        )


class WordInsertionHandler:
    """Insert a filler word (discourse marker, particle) into the sentence."""

    name = "word_insertion"
    subtypes = ["word_insertion"]
    category = "OTHER"
    changes_length = True

    def __init__(self):
        self._fillers = None

    @property
    def fillers(self):
        if self._fillers is None:
            from synterr.languages.russian.resources import get_filler_list

            # GECToR output is whitespace-tokenized: one corrupted token = one tag.
            # A filler containing a space would occupy a single corrupted-token slot
            # (one $DELETE) but split into two whitespace tokens downstream, causing
            # an off-by-one tag/token misalignment. Keep only single-token fillers.
            self._fillers = [f for f in get_filler_list() if f and len(f.split()) == 1]
        return self._fillers

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
        if idx >= len(tokens) - 1:
            return None

        rng = rng if rng is not None else random_module

        filler = rng.choice(self.fillers)

        sentence.insert(idx + 1, filler)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx + 1,
            end_idx=idx + 1,
            original="",
            corrupted=filler,
            fix_tag="$DELETE",
        )
