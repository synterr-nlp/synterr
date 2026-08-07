"""Syntax-level handlers (sy_ family, Rozental Part III §176–213).

First inhabitants of the SYNT block: the generator historically stopped at
morphology/punctuation, leaving the sy_ tags annotation-only. General word
order (§178–182) stays out deliberately — Russian word order is free and
§178–182 describe *default* orders with inversion as a legitimate device,
so blanket reordering would emit marked-but-grammatical variants (the
«marked variant ≠ error» trap). Only mechanically decidable norms live
here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
    inflect_word,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# §207 п.1(1): the repeating-conjunction markers whose presence makes
# preposition repetition OBLIGATORY across conjuncts.
_REPEATING_CONJ_TEXTS = frozenset({"и", "ни"})


def _conjunct_family(tokens: Sequence[AnalyzedToken], first_idx: int) -> set[int]:
    """First conjunct + all its conj dependents."""
    family = {first_idx}
    family.update(
        t.idx for t in tokens if t.head_idx == first_idx and t.dep_rel == "conj"
    )
    return family


def _repeating_conj_count(tokens: Sequence[AnalyzedToken], family: set[int]) -> int:
    """«и»/«ни» tokens attached anywhere in the conj chain.

    The leading conjunction of «и X и Y» is often tagged PART/advmod by
    stanza rather than cc (same finding as comma_insert's §87 guard), so
    text membership decides and any dep_rel attached to a family member
    counts.
    """
    return sum(
        1
        for t in tokens
        if t.head_idx in family and t.text.lower() in _REPEATING_CONJ_TEXTS
    )


class PrepRepeatHandler:
    """Drop an obligatory repeated preposition (§207 п.1).

    With repeating conjunctions the preposition must repeat before every
    conjunct: «недостачу испытывали и в машинах, и в сырье». Dropping it
    from a non-first conjunct («и в машинах, и сырье») is the error this
    handler produces.

    The complementary case is already guarded elsewhere: in BARE
    coordination («по почерку и по количеству») the repetition is
    optional, so deleting it yields grammatical shared-case coordination —
    word_omission explicitly refuses those sites (audit C14). This handler
    fires only when a repeating «и»/«ни» pattern makes the repetition
    obligatory, and additionally requires the comma before this conjunct's
    conjunction (the correctly-written §87 repeating-union shape), so the
    two handlers partition the preposition-coordination space cleanly.
    """

    name = "prep_repeat"
    subtypes = ["prep_repeat"]
    category = "OTHER"
    changes_length = True

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "ADP" or token.dep_rel != "case":
            return False
        if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
            return False
        nominal = tokens[token.head_idx]
        # non-first conjunct only: the first conjunct's preposition anchors
        # the shared case and must survive
        if nominal.dep_rel != "conj":
            return False
        first_idx = nominal.head_idx
        if first_idx is None or not (0 <= first_idx < len(tokens)):
            return False
        prep_lemma = (token.lemma or token.text).lower()
        # the first conjunct must carry the SAME preposition (§207 describes
        # repetition of one preposition, not mixed-preposition chains)
        if not any(
            t.head_idx == first_idx
            and t.dep_rel == "case"
            and (t.lemma or t.text).lower() == prep_lemma
            for t in tokens
        ):
            return False
        family = _conjunct_family(tokens, first_idx)
        if _repeating_conj_count(tokens, family) < 2:
            return False
        # the conjunct's own conjunction, preceded by the §87 comma:
        # «…, и в сырье» — scan left past the conjunction to the comma
        j = idx - 1
        if j >= 0 and tokens[j].text.lower() in _REPEATING_CONJ_TEXTS:
            j -= 1
        else:
            return False
        return j >= 0 and tokens[j].text == ","

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if not self.can_apply(tokens, idx):
            return None
        if self._enabled_subtypes is not None and "prep_repeat" not in (
            self._enabled_subtypes
        ):
            return None
        # $APPEND anchors at idx-1 (same constraint as word_omission)
        if idx - 1 in modified:
            return None

        deleted = sentence[idx]
        del sentence[idx]
        return ErrorResult(
            error_type="prep_repeat",
            category=self.category,
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=deleted,
            corrupted="",
            fix_tag=f"$APPEND_{deleted}",
        )


# =============================================================================
# parallel_mix (§211–212): причастный оборот coordinated with который-clause
# =============================================================================

_RELCL_DEPRELS = frozenset({"acl:relcl", "acl"})


def _active_participle_for(
    v_token: AnalyzedToken, noun_token: AnalyzedToken
) -> str | None:
    """Active-participle form of ``v_token`` agreeing with ``noun_token``.

    None when the norm provides no form (present participles exist only
    for imperfectives) or when pymorphy cannot build/inflect it — the
    handler skips rather than guesses.
    """
    parse = v_token.extra.get("pymorphy_parse")
    if parse is None:
        return None
    tense = {"Pres": "pres", "Past": "past"}.get(v_token.get_feature("Tense"))
    if tense is None:
        return None
    if tense == "pres" and v_token.get_feature("Aspect") != "Imp":
        return None

    prtf = None
    for form in parse.lexeme:
        tag = form.tag
        if "PRTF" in tag and "actv" in tag and tense in tag:
            prtf = form
            break
    if prtf is None:
        return None

    grammemes: set[str] = set()
    case = UD_TO_PYMORPHY_CASE.get(noun_token.get_feature("Case"))
    if case is None:
        return None
    grammemes.add(case)
    number = UD_TO_PYMORPHY_NUMBER.get(noun_token.get_feature("Number"))
    if number is None:
        return None
    grammemes.add(number)
    if number == "sing":
        gender = UD_TO_PYMORPHY_GENDER.get(noun_token.get_feature("Gender"))
        if gender is None:
            return None
        grammemes.add(gender)
    if case == "accs":
        animacy = {"Anim": "anim", "Inan": "inan"}.get(
            noun_token.get_feature("Animacy")
        )
        if animacy:
            grammemes.add(animacy)
    return inflect_word(prtf, grammemes)


class ParallelMixHandler:
    """Mix a причастный оборот into a который-coordination (§211–212).

    Rozental's parallel-construction norm: coordinated attributive
    clauses must keep one form — two который-clauses or two participial
    phrases, never one of each. The attested error coordinates them
    («книга, лежащая на столе и которую я взял»). This handler produces
    it from the correct two-который shape: «N, который V1 …, и который
    V2 …» → «N, V1-щий …, и который V2 …».

    Gates: the first «который» must be the nominative subject of its
    relative clause (only that configuration converts to an ACTIVE
    participle without argument surgery), adjacent to its verb (MVP —
    intervening adverbs would need reordering), V1 present-imperfective
    or past (the norm has no present-perfective participle, §211.1), a
    second который-clause coordinated via conj on V1, and a real
    participle obtainable from pymorphy with full agreement (case,
    number, gender, accusative animacy) against the head noun. Any
    failure skips.
    """

    name = "parallel_mix"
    subtypes = ["parallel_mix"]
    category = "OTHER"
    changes_length = True

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def _site(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[AnalyzedToken, AnalyzedToken] | None:
        """(V1, head noun) when idx is a convertible «который», else None."""
        token = tokens[idx]
        if (token.lemma or "").lower() != "который" or token.dep_rel != "nsubj":
            return None
        if idx == 0 or tokens[idx - 1].text != ",":
            return None
        if token.head_idx is None or token.head_idx != idx + 1:
            return None  # MVP: который directly before its verb
        v1 = tokens[idx + 1]
        if v1.pos != "VERB" or v1.dep_rel not in _RELCL_DEPRELS:
            return None
        if v1.head_idx is None or not (0 <= v1.head_idx < len(tokens)):
            return None
        noun = tokens[v1.head_idx]
        if noun.pos not in ("NOUN", "PROPN"):
            return None
        # the coordinated second который-clause that creates the mixing
        second = False
        for t in tokens:
            if (
                t.head_idx == v1.idx
                and t.dep_rel == "conj"
                and any(
                    (k.lemma or "").lower() == "который" and k.head_idx == t.idx
                    for k in tokens
                )
            ):
                second = True
                break
        if not second:
            return None
        return v1, noun

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        site = self._site(tokens, idx)
        if site is None:
            return False
        v1, noun = site
        return _active_participle_for(v1, noun) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        site = self._site(tokens, idx)
        if site is None:
            return None
        if self._enabled_subtypes is not None and "parallel_mix" not in (
            self._enabled_subtypes
        ):
            return None
        v1, noun = site
        participle = _active_participle_for(v1, noun)
        if participle is None:
            return None

        original_1 = sentence[idx]
        original_2 = sentence[idx + 1]
        sentence[idx] = participle
        del sentence[idx + 1]
        return ErrorResult(
            error_type="parallel_mix",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=f"{original_1} {original_2}",
            corrupted=participle,
            fix_tag=f"$SPLIT_{original_1}_{original_2}",
        )
