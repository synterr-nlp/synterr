"""Russian structural error handlers - word omission and insertion."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# PART excluded: particles are syntactically optional, so deleting one yields
# a grammatical sentence (worst case a silent negation flip: "не читает" →
# "читает") — a non-error that poisons training data.
OMITTABLE_POS = {"ADP", "CCONJ", "SCONJ"}
CONJ_POS = {"CCONJ", "SCONJ"}


class WordOmissionHandler:
    """Delete a function word (preposition or conjunction)."""

    name = "word_omission"
    subtypes = ["word_omission"]
    category = "OTHER"
    changes_length = True

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int):
        if idx == 0:
            return False
        if tokens[idx].pos not in OMITTABLE_POS:
            return False
        # Deleting a clause-linking conjunction right after punctuation leaves
        # a valid asyndetic sentence ("Он устал, мы продолжили" — бессоюзное
        # сложное предложение, Rozental §116), i.e. a non-error. Phrase-level
        # coordination without punctuation ("кошки и собаки") stays deletable.
        if tokens[idx].pos in CONJ_POS and tokens[idx - 1].pos == "PUNCT":
            return False
        return True

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ):
        if not self.can_apply(tokens, idx):
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
