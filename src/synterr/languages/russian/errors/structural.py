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

# Bounds the leftward adjacency scan in _repeated_prep_in_coordination so a
# malformed/very long sentence can't make it scan indefinitely.
_REPEATED_PREP_SCAN_CAP = 6

# POS that terminate the leftward scan: past them we've left the coordination
# span this preposition could be repeating within.
_REPEATED_PREP_SCAN_STOP_POS = {"PUNCT", "VERB", "SCONJ"}


def _repeated_prep_in_coordination(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Whether the ADP at ``idx`` repeats a preposition an earlier conjunct in
    the same coordination already carries (C14, 2026-07 audit).

    "по почерку и по количеству" -> deleting the second "по" still yields
    grammatical shared-case coordination ("по почерку и количеству") — a
    non-error, since Russian coordination may share a single governing
    preposition across conjuncts. Dep-tree check: the ADP's head is its
    governed nominal; if that nominal is a ``conj`` dependent of an earlier
    nominal which already has a ``case`` child with the same lemma, the
    preposition is redundant. Adjacency fallback (no dep info): the same
    preposition text appears earlier in the sentence, before a coordinating
    conjunction, within a short scan window.
    """
    token = tokens[idx]
    lemma = (token.lemma or token.text).lower()

    head_idx = token.head_idx
    if head_idx is not None and 0 <= head_idx < len(tokens) and head_idx != idx:
        nominal = tokens[head_idx]
        if nominal.dep_rel == "conj":
            first_idx = nominal.head_idx
            if (
                first_idx is not None
                and 0 <= first_idx < len(tokens)
                and first_idx != head_idx
            ):
                return any(
                    other.head_idx == first_idx
                    and other.dep_rel == "case"
                    and (other.lemma or other.text).lower() == lemma
                    for other in tokens
                )
        return False

    seen_cconj = False
    for j in range(idx - 1, max(-1, idx - 1 - _REPEATED_PREP_SCAN_CAP), -1):
        other = tokens[j]
        if other.pos == "CCONJ":
            seen_cconj = True
            continue
        if other.pos in _REPEATED_PREP_SCAN_STOP_POS:
            break
        if (
            seen_cconj
            and other.pos == "ADP"
            and (other.lemma or other.text).lower() == lemma
        ):
            return True
    return False


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
        # A repeated preposition in shared-case coordination is redundant but
        # grammatical (C14, 2026-07 audit): deleting it doesn't create an
        # error.
        if tokens[idx].pos == "ADP" and _repeated_prep_in_coordination(tokens, idx):
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

        # The $APPEND fix tag anchors at idx-1, a token this handler does not
        # touch. The formatter keeps one fix tag per token index, so if another
        # handler already corrupted idx-1 its $REPLACE tag would be silently
        # overwritten, leaving that corruption labeled $KEEP (uncorrectable).
        if idx - 1 in modified:
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


# Enclitic particles lean on the *preceding* word; a filler must not split
# them from their host ("он [вот] же сказал"). Proclitics (не, ни) lean
# forward and are handled by the prev-token PART check instead.
_ENCLITIC_PARTICLES = {"же", "ж", "ли", "ль", "бы", "б"}


class WordInsertionHandler:
    """Insert a filler word (discourse marker, particle) into the sentence.

    Insertion-point semantics: apply(idx) inserts the filler at position
    ``idx``, i.e. *before* tokens[idx]. idx == 0 is the sentence-initial
    slot — the most frequent filler position in real text. Fillers attach
    at prosodic/clause boundaries, so positions that split a clitic group
    (preposition + complement, particle + host) are refused: no speaker
    writes "пошёл в [вот] школу".
    """

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

    @staticmethod
    def _splits_adp_complement(tokens, idx):
        """True when position idx falls between an ADP and its complement head.

        Catches non-adjacent splits like "в большую [вот] школу" (the ADP
        attaches as `case` child of the downstream noun). Requires depparse;
        with head_idx unset this is a no-op and the adjacent prev-is-ADP
        check still applies.
        """
        for pos_i, tok in enumerate(tokens):
            if (
                tok.pos == "ADP"
                and tok.head_idx is not None
                and pos_i < idx <= tok.head_idx
            ):
                return True
        return False

    def can_apply(self, tokens, idx):
        if idx < 0 or idx >= len(tokens):
            return False
        tok = tokens[idx]
        # Fillers never directly precede punctuation ("раму [вот] .").
        if tok.pos == "PUNCT":
            return False
        # Don't split an enclitic particle from its preceding host.
        if tok.pos == "PART" and (tok.lemma or tok.text).lower() in _ENCLITIC_PARTICLES:
            return False
        if idx == 0:
            return True
        # Don't split a preposition ("в [вот] школу") or a proclitic particle
        # ("не [ну] читает") from the word it leans on.
        if tokens[idx - 1].pos in ("ADP", "PART"):
            return False
        if self._splits_adp_complement(tokens, idx):
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

        rng = rng if rng is not None else random_module

        filler = rng.choice(self.fillers)

        if idx == 0 and sentence and sentence[0][:1].isupper():
            # Sentence-initial fillers are written capitalized. The next
            # word keeps its original capitalization so the single $DELETE
            # on the filler restores the source sentence exactly (one
            # fix_tag per error — lowercasing the next word would leave a
            # residual error with no corresponding edit).
            filler = filler.capitalize()

        sentence.insert(idx, filler)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx,
            original="",
            corrupted=filler,
            fix_tag="$DELETE",
        )
