"""Russian subject-verb agreement error handlers (Rozental §183-190).

Five handlers, one per RLC/rozental L2 tag (``ag_sv_collective``,
``ag_sv_counting``, ``ag_sv_approximate``, ``ag_sv_compound``,
``ag_sv_coordinated``), all under the ``ag_subject_verb`` L1 tag. They share
one piece of machinery: find the finite predicate (or short-form participle
predicate), find its overt subject (``nsubj``/``nsubj:pass``), check a
trigger precondition on the subject's dep-tree neighborhood, then corrupt the
predicate's Number (or Gender, for the gender-mismatch subcases) via the
pymorphy parse in ``token.extra["pymorphy_parse"]`` while pinning
Tense/Person so the flip cannot drift into an unrelated error.

All five REQUIRE dependency-parse info: without an arc there is no subject to
find and no trigger evidence, so ``can_apply`` is False whenever the
predicate token itself carries no ``dep_rel`` (guards against running with
``use_depparse=False``, mirroring the existing agreement handlers in
``morphological.py``; see ``_has_dep_info`` for why this checks ``dep_rel``
alone and not ``head_idx`` too — root predicates legitimately have no head).

Irreducible ambiguity (see module docstrings below for the per-handler
detail): Russian genuinely allows both singular ("semantic"/notional) and
plural ("grammatical"/formal) agreement with quantity subjects in many
contexts (Rozental documents this explicitly for §183-185). Each handler
below restricts to the sub-case Rozental and descriptive grammars treat as
the *marked*/erroneous variant, skipping the genuinely-optional cases
entirely (precision over recall, matching the project's spelling/punctuation
handlers) — but a residual validity ceiling below 100% should be expected
when this family is annotated, and is treated as an accepted, documented
finding rather than a bug.
"""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.inflector import (
    GENDERS,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_PERSON,
    UD_TO_PYMORPHY_TENSE,
    inflect_word,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# Shared machinery
# =============================================================================

# Finite predicate POS (mirrors punctuation.py's FINITE_POS). Short-form
# participle predicates ("приглашено", "убеждён") are VERB/VerbForm=Part in
# stanza's SynTagRus tagset, so they fall out of _is_predicate_token too.
_FINITE_POS = frozenset({"VERB", "AUX"})

# Subject dep_rels (shared with morphological.py's convention).
_SUBJECT_DEPRELS = frozenset({"nsubj", "nsubj:pass"})


def _get_pymorphy_parse(token: AnalyzedToken):
    """Get pymorphy parse object from token."""
    return token.extra.get("pymorphy_parse")


def _is_predicate_token(token: AnalyzedToken) -> bool:
    """A token that anchors a clause as its predicate: a finite verb/aux, or
    a short participle ("расположены", "убеждён") — the predicative forms.

    Duplicated locally from ``punctuation.py`` per the file-lane rule (this
    module owns no cross-file imports of another handler file's helpers).
    """
    if token.pos not in _FINITE_POS:
        return False
    verb_form = token.get_feature("VerbForm")
    if verb_form in (None, "Fin"):
        return True
    return verb_form == "Part" and token.get_feature("Variant") == "Short"


def _has_dep_info(token: AnalyzedToken) -> bool:
    """No dep arc → no classification evidence → no fire (all five handlers).

    Checks ``dep_rel`` only, not ``head_idx``: the backend leaves both None
    when depparse did not run, but a ROOT predicate legitimately has
    ``dep_rel="root"`` with ``head_idx=None`` (stanza's head==0 sentinel, see
    ``stanza_backend.py``'s ``_word_to_token``) — exactly the common case of
    a main-clause predicate, so gating on head_idx too would make every one
    of these handlers refuse to fire on ordinary root clauses. Same idiom as
    ``NounCaseErrorHandler._classify``'s ``if not token.dep_rel: return None``.
    """
    return token.dep_rel is not None


# POS a genuine subject can have. Guards against a real stanza parsing
# quirk observed on "Более двадцати человек пришли": "более" itself gets
# tagged ADV/nsubj (a second, spurious nsubj on the same predicate)
# alongside the real nominal subject "человек" — without this filter,
# enumeration order would hand back the adverb instead of the noun.
_SUBJECT_POS = frozenset({"NOUN", "PROPN", "PRON", "NUM", "DET"})


def _find_subject(
    tokens: Sequence[AnalyzedToken], predicate_idx: int
) -> tuple[int, AnalyzedToken] | None:
    """Find the predicate's overt subject (nsubj/nsubj:pass) with its index."""
    for i, token in enumerate(tokens):
        if (
            token.head_idx == predicate_idx
            and token.dep_rel in _SUBJECT_DEPRELS
            and token.pos in _SUBJECT_POS
        ):
            return i, token
    return None


def _gender_grammeme(token: AnalyzedToken) -> str | None:
    """Token's gender as a pymorphy grammeme, from its UD Gender feature."""
    gender_ud = token.get_feature("Gender")
    return UD_TO_PYMORPHY_GENDER.get(gender_ud) if gender_ud else None


def _other_gender(current: str | None, rng: Random) -> str:
    """A pymorphy gender grammeme different from ``current`` (random flip)."""
    others = [g for g in GENDERS if g != current]
    return rng.choice(others)


def _corrupt_predicate_number(
    token: AnalyzedToken,
    word: str,
    target_num: str,
    *,
    ref_gender: str | None = None,
) -> str | None:
    """Inflect a predicate to ``target_num`` ("sing"/"plur"), pinning
    Tense/Person so the flip stays a pure number (or, with a fixed
    ``target_num`` equal to the current one, a pure gender) change.

    Past-tense/short-participle singular targets carry Gender but no Person;
    Russian gives no morphological signal for *which* gender belongs there
    (plural forms are gender-neutral), so a singular target requires an
    explicit ``ref_gender`` — without one this returns None (precision-first
    skip, same idiom as ``AdjNumberErrorHandler._head_is_indeclinable``'s
    sibling checks in morphological.py).
    """
    parse = _get_pymorphy_parse(token)
    if parse is None:
        return None

    grammemes = {target_num}

    tense_ud = token.get_feature("Tense")
    py_tense = UD_TO_PYMORPHY_TENSE.get(tense_ud) if tense_ud else None
    if py_tense:
        grammemes.add(py_tense)

    person_ud = token.get_feature("Person")
    py_person = UD_TO_PYMORPHY_PERSON.get(person_ud) if person_ud else None
    if py_person:
        grammemes.add(py_person)
    elif target_num == "sing":
        # No Person means this is a past-tense (or short-participle) form,
        # which needs an explicit gender to land on a real word instead of
        # pymorphy's masculine default.
        if ref_gender is None:
            return None
        grammemes.add(ref_gender)

    new_word = inflect_word(parse, grammemes, word)
    if not new_word or new_word == word:
        return None
    return new_word


# =============================================================================
# ag_sv_collective (§183) — большинство/ряд/часть/множество/меньшинство
# =============================================================================

# Collective-quantifier nouns explicitly covered by §183. Deliberately
# narrower than morphological.py's _COLLECTIVE_QUANTIFIER_LEMMAS (which also
# blocks masса/половина/много/несколько/тысяча/... for VerbPersonNumber's
# purposes) — this handler's trigger is specifically the §183 collective
# class, not every quantity word.
# часть/ряд excluded: their lexical senses (воинская часть, ряд домов "row")
# dominate in text and a lemma test cannot separate them from the §183
# quantifier reading (audit finding, 2026-07-07).
_COLLECTIVE_LEMMAS = frozenset({"большинство", "множество", "меньшинство"})


def _has_gen_plural_dependent(tokens: Sequence[AnalyzedToken], head_idx: int) -> bool:
    """A Gen-plural nmod-family dependent of ``head_idx`` ("большинство
    студентОВ")."""
    for t in tokens:
        if (
            t.head_idx == head_idx
            and (t.dep_rel or "").startswith("nmod")
            and t.get_feature("Case") == "Gen"
            and t.get_feature("Number") == "Plur"
        ):
            return True
    return False


class AgrSvCollectiveErrorHandler:
    """Corrupt subject-verb number agreement with a bare collective subject.

    Both singular ("Большинство проголосовало") and plural ("Большинство
    проголосовали") are normative when the collective noun governs a
    Gen-plural dependent (большинство студентОВ) — Rozental §183 explicitly
    licenses both there, so that configuration is skipped entirely (the
    subject and its dependent stay untouched as evidence would be
    ambiguous). The clean, rule-following error only shows up with a *bare*
    collective subject (no Gen-plural dependent): singular is then the sole
    normative reading, so sg→pl is unambiguously wrong.

    Direction: singular → plural only (bare collective subjects are already
    almost always singular in real text; the reverse would require
    generating a plural collective-subject sentence, which is not attested).
    """

    name = "agr_sv_collective"
    subtypes = ["agr_sv_collective"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if not _is_predicate_token(token) or not _has_dep_info(token):
            return False
        if _get_pymorphy_parse(token) is None:
            return False
        if token.get_feature("Number") != "Sing":
            return False
        found = _find_subject(tokens, idx)
        if found is None:
            return False
        subj_idx, subject = found
        if (subject.lemma or "").lower() not in _COLLECTIVE_LEMMAS:
            return False
        # "Bare" means bare: any nmod dependent (Gen-plural OR otherwise —
        # «часть Паутины») signals a partitive/lexical reading where §183
        # licenses both agreements or does not apply at all.
        if any(
            t.head_idx == subj_idx and (t.dep_rel or "").startswith("nmod")
            for t in tokens
        ):
            return False
        return True

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
        token = tokens[idx]
        word = sentence[idx]

        new_word = _corrupt_predicate_number(token, word, "plur")
        if new_word is None:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_number = token.get_feature("Number", "Sing")
        return ErrorResult(
            error_type="agr_sv_collective",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
        )


# =============================================================================
# ag_sv_counting (§184) — counting phrases ("пять человек пришло/пришли")
# =============================================================================

# Value class 2-4: the numeral's own lemma directly carries the value class
# even in compounds (compounds like "двадцать два" attach via the LAST
# numeral word, which is the nsubj's nummod head — see the "Пять студентов"
# fixture convention already established in morphological.py's tests). The
# normative default here is PLURAL ("два студента пришли"); a singular
# predicate is the attested, marked error — the reverse of the 5+ class.
_COUNTING_2_4_LEMMAS = frozenset({"два", "две", "три", "четыре"})

# тысяча/миллион/миллиард act as the subject's own head noun (not a nummod
# dependent): "Тысяча человек пришла" — the noun itself is grammatically
# fem/masc singular and the predicate must agree in gender. The attested
# marked error is a gender MISMATCH (пришло/пришёл instead of пришла), not a
# number flip — the count noun's own singular number is not in question.
_LARGE_COUNT_NOUN_LEMMAS = frozenset({"тысяча", "миллион", "миллиард"})


def _nummod_child(
    tokens: Sequence[AnalyzedToken], head_idx: int
) -> AnalyzedToken | None:
    """First nummod-family child of ``head_idx`` (numeral modifying a noun)."""
    for t in tokens:
        if t.head_idx == head_idx and (t.dep_rel or "").startswith("nummod"):
            return t
    return None


class AgrSvCountingErrorHandler:
    """Corrupt subject-verb agreement with a counting-phrase subject.

    Value-class aware (§184): a numeral's behavior splits into three
    classes, and only two of them have an unambiguous "clean" error
    direction (the third, 5+/11-14, licenses both singular and plural about
    equally per Rozental and is skipped — same both-acceptable trap as
    §183, restricted here rather than shipped at a validity cost):

    - **1** (один/одна/одно): the noun is a plain grammatical singular, not
      a counting-phrase agreement question at all — not a target.
    - **2-4** (два/две/три/четыре, incl. compounds ending in them —
      "двадцать два", never "-надцать"): plural is the norm, singular is
      the attested marked error. Corrupt plur→sing, forcing the impersonal
      default gender (neuter) rather than the counted noun's own gender —
      "Два студента пришл**и**" → "пришл**о**" (not "пришёл": the singular
      predicate here does not agree with the noun's own gender, it is the
      default impersonal singular, matching §183's «большинство» pattern).
    - **5+** (пять.., 11-14, 0): singular is actually the more common,
      Rozental-preferred form and plural is also fully normative — SKIPPED
      (not implemented; both directions would be a non-error more often
      than not).
    - **тысяча/миллион/миллиард as the subject's own head noun**: gender
      mismatch on the past-tense predicate ("Тысяча человек пришл**а**" →
      "пришл**о**"/"пришё**л**"), keeping singular number fixed.
    """

    name = "agr_sv_counting"
    subtypes = ["agr_sv_counting"]
    category = "MORPH"
    changes_length = False

    def _classify(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, int, AnalyzedToken] | None:
        """Return (branch, subj_idx, subject) or None. branch is
        "two_four" or "large_count"."""
        token = tokens[idx]
        if not _is_predicate_token(token) or not _has_dep_info(token):
            return None
        if _get_pymorphy_parse(token) is None:
            return None
        found = _find_subject(tokens, idx)
        if found is None:
            return None
        subj_idx, subject = found
        subj_lemma = (subject.lemma or "").lower()

        if subj_lemma in _LARGE_COUNT_NOUN_LEMMAS:
            # Require the subject ITSELF to be grammatically singular
            # ("Тысяча человек пришла") — a genitive-plural "тысяч"/
            # "миллионов" inside a larger cardinal ("свыше 500 тысяч
            # долларов") is a different construction (approximate-quantity
            # territory, not this handler's simple count-noun-as-subject
            # trigger) and must not be caught here.
            if (
                subject.get_feature("Number") == "Sing"
                and token.get_feature("Tense") == "Past"
                and token.get_feature("Number") == "Sing"
                and token.has_feature("Gender")
            ):
                return "large_count", subj_idx, subject
            return None

        if token.get_feature("Number") != "Plur":
            return None
        nummod = _nummod_child(tokens, subj_idx)
        if nummod is None or (nummod.lemma or "").lower() not in _COUNTING_2_4_LEMMAS:
            return None
        return "two_four", subj_idx, subject

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._classify(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        classified = self._classify(tokens, idx)
        if classified is None:
            return None
        branch, _subj_idx, _subject = classified
        token = tokens[idx]
        word = sentence[idx]

        if branch == "large_count":
            current_gender = UD_TO_PYMORPHY_GENDER.get(token.get_feature("Gender"))
            target_gender = _other_gender(current_gender, rng)
            new_word = _corrupt_predicate_number(
                token, word, "sing", ref_gender=target_gender
            )
            if new_word is None:
                return None
            sentence[idx] = new_word
            modified.add(idx)
            original_gender = token.get_feature("Gender", "Fem")
            return ErrorResult(
                error_type="agr_sv_counting",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_GENDER_{original_gender}",
            )

        # branch == "two_four": plur -> sing, impersonal default neuter.
        new_word = _corrupt_predicate_number(token, word, "sing", ref_gender="neut")
        if new_word is None:
            return None
        sentence[idx] = new_word
        modified.add(idx)
        original_number = token.get_feature("Number", "Plur")
        return ErrorResult(
            error_type="agr_sv_counting",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
        )


# =============================================================================
# ag_sv_approximate (§185) — около/свыше/более/больше + Gen quantity subject
# =============================================================================

_APPROX_QUANTIFIER_LEMMAS = frozenset({"около", "свыше", "более", "больше"})


def _find_approx_quantifier(
    tokens: Sequence[AnalyzedToken], subj_idx: int, predicate_idx: int
) -> AnalyzedToken | None:
    """An approximate-quantity marker (около/свыше/более/больше) attached to
    the subject, to a nummod dependent of the subject ("около ста человек":
    человек=nsubj, ста=nummod child, около attaches to ста), or directly to
    the predicate — real stanza parses of "более"/"больше" sometimes attach
    it straight to the verb as a second (spurious) nsubj-labeled dependent
    ("Более двадцати человек пришли") rather than into the subject's own
    subtree, so the predicate is included as a candidate head too."""
    candidates = {subj_idx, predicate_idx}
    for i, t in enumerate(tokens):
        if t.head_idx == subj_idx and (t.dep_rel or "").startswith("nummod"):
            candidates.add(i)
    for t in tokens:
        if t.head_idx in candidates and t.text.lower() in _APPROX_QUANTIFIER_LEMMAS:
            return t
    return None


class AgrSvApproximateErrorHandler:
    """Corrupt subject-verb agreement with an approximate-quantity subject.

    §185: около/свыше/более/больше + Gen ("Около ста человек пришло").
    Anchored on the subject being Gen-cased (the quantity-phrase signature)
    with one of the four markers attached somewhere in its immediate
    dependents — a purely positional match would over-fire on unrelated
    Gen-cased subjects, so the marker + Gen-case pairing is required
    together. Bidirectional (sg↔pl), same both-acceptable-variant ceiling
    as §183/§184: the singular target always takes the impersonal default
    neuter gender, never the counted noun's own gender.
    """

    name = "agr_sv_approximate"
    subtypes = ["agr_sv_approximate"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if not _is_predicate_token(token) or not _has_dep_info(token):
            return False
        if _get_pymorphy_parse(token) is None or not token.has_feature("Number"):
            return False
        found = _find_subject(tokens, idx)
        if found is None:
            return False
        subj_idx, subject = found
        if subject.get_feature("Case") != "Gen":
            return False
        return _find_approx_quantifier(tokens, subj_idx, idx) is not None

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
        token = tokens[idx]
        word = sentence[idx]

        current_number = token.get_feature("Number")
        if current_number == "Sing":
            new_word = _corrupt_predicate_number(token, word, "plur")
        else:
            new_word = _corrupt_predicate_number(token, word, "sing", ref_gender="neut")
        if new_word is None:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_number = token.get_feature("Number", "Sing")
        return ErrorResult(
            error_type="agr_sv_approximate",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
        )


# =============================================================================
# ag_sv_compound (§186-189) — special subjects: кто, comitative, acronym
# =============================================================================


_ACRONYM_SUBJECT_POS = frozenset({"NOUN", "PROPN"})


def _is_acronym_subject(token: AnalyzedToken) -> bool:
    """An indeclinable Cyrillic acronym subject (МГУ, ООН, США, ЦРУ, ...):
    all-caps alphabetic token tagged NOUN or PROPN. Requiring both the
    casing and the POS keeps this from over-firing on emphasis-capitalized
    ordinary words; NOUN is included alongside PROPN because real stanza
    output tags some acronyms (e.g. "МГУ") as a common NOUN rather than a
    proper noun — the all-caps signal is doing the real precision work
    here, not the POS split."""
    text = token.text
    return (
        token.pos in _ACRONYM_SUBJECT_POS
        and text.isalpha()
        and text.isupper()
        and len(text) >= 2
    )


class AgrSvCompoundErrorHandler:
    """Corrupt subject-verb agreement for three §186-189 special-subject
    triggers, each independently sufficient (first match wins):

    - **кто-clause** (§187): "те, кто пришёл" — кто always takes a
      singular predicate regardless of its antecedent's number, so the
      singular is *correct*; corrupting it to plural ("те, кто пришли") is
      the real, extremely common learner/native error of agreeing with the
      semantically-plural antecedent instead of the syntactic кто subject.
      Direction: sing → plur.
    The comitative subcase («брат с сестрой пришли» → «пришёл») was REMOVED
    after audit (2026-07-07): §186 licenses BOTH agreements — plural for
    joint agents, singular for the accompaniment reading — so the collapse
    to singular yields correct Russian, and the trigger also over-fired on
    non-agent «с»-modifiers («концерты с участием музыкантов»).
    - **acronym/indeclinable subject** (§189): a past-tense predicate whose
      gender should track the acronym's core-noun gender is instead
      flipped to a different, wrong gender (e.g. МГУ + masc-correct
      "объявил" → neut "объявило"). Number is left untouched.
    """

    name = "agr_sv_compound"
    subtypes = ["agr_sv_compound"]
    category = "MORPH"
    changes_length = False

    def _classify(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, AnalyzedToken] | None:
        token = tokens[idx]
        if not _is_predicate_token(token) or not _has_dep_info(token):
            return None
        if _get_pymorphy_parse(token) is None:
            return None
        found = _find_subject(tokens, idx)
        if found is None:
            return None
        _subj_idx, subject = found

        if (subject.lemma or subject.text or "").lower() == "кто":
            if token.get_feature("Number") == "Sing":
                return "koto", subject
            return None

        if _is_acronym_subject(subject):
            if token.get_feature("Tense") == "Past" and token.has_feature("Gender"):
                return "acronym", subject
            return None

        return None

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._classify(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        classified = self._classify(tokens, idx)
        if classified is None:
            return None
        branch, _subject = classified
        token = tokens[idx]
        word = sentence[idx]

        if branch == "koto":
            new_word = _corrupt_predicate_number(token, word, "plur")
            if new_word is None:
                return None
            sentence[idx] = new_word
            modified.add(idx)
            original_number = token.get_feature("Number", "Sing")
            return ErrorResult(
                error_type="agr_sv_compound",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
            )

        if branch == "acronym":
            current_gender = UD_TO_PYMORPHY_GENDER.get(token.get_feature("Gender"))
            target_gender = _other_gender(current_gender, rng)
            new_word = _corrupt_predicate_number(
                token, word, "sing", ref_gender=target_gender
            )
            if new_word is None:
                return None
            sentence[idx] = new_word
            modified.add(idx)
            original_gender = token.get_feature("Gender", "Masc")
            return ErrorResult(
                error_type="agr_sv_compound",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_GENDER_{original_gender}",
            )

        return None


# =============================================================================
# ag_sv_coordinated (§190) — coordinated preposed subjects ("Брат и сестра")
# =============================================================================


def _find_coordinated_subject(
    tokens: Sequence[AnalyzedToken], subj_idx: int
) -> tuple[int, AnalyzedToken] | None:
    """A second subject coordinated onto ``subj_idx`` via "и" ("Брат И
    сестра"): a ``conj`` child whose own ``cc`` dependent is the lemma и."""
    for i, t in enumerate(tokens):
        if t.head_idx != subj_idx or t.dep_rel != "conj":
            continue
        for cc in tokens:
            if cc.head_idx == i and cc.dep_rel == "cc" and cc.lemma.lower() == "и":
                return i, t
    return None


class AgrSvCoordinatedErrorHandler:
    """Corrupt subject-verb agreement with coordinated preposed subjects.

    §190: "Брат и сестра пришли" — plural is close to obligatory when both
    conjuncts precede the predicate. The ordering guard is the whole trick
    (explicitly required by the capsule spec): if the predicate instead
    precedes the subjects ("Пришли брат и сестра" / "Пришёл брат и сестра"),
    singular becomes acceptable again, so that order is skipped entirely —
    only fires when the predicate follows both conjuncts.

    Direction: plur → sing, with the target gender taken from the *nearer*
    conjunct (the second subject, adjacent to the verb) — proximity
    agreement is the standard account of exactly this error, and is a real
    syntactic gender (unlike the impersonal-neuter default used for the
    quantity-subject handlers above).
    """

    name = "agr_sv_coordinated"
    subtypes = ["agr_sv_coordinated"]
    category = "MORPH"
    changes_length = False

    def _classify(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[AnalyzedToken, AnalyzedToken] | None:
        token = tokens[idx]
        if not _is_predicate_token(token) or not _has_dep_info(token):
            return None
        if _get_pymorphy_parse(token) is None:
            return None
        if token.get_feature("Number") != "Plur":
            return None
        found = _find_subject(tokens, idx)
        if found is None:
            return None
        subj_idx, subject = found
        coordinated = _find_coordinated_subject(tokens, subj_idx)
        if coordinated is None:
            return None
        conj_idx, conj_subject = coordinated
        # Ordering guard: both conjuncts must precede the predicate.
        if not (subj_idx < idx and conj_idx < idx):
            return None
        return subject, conj_subject

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._classify(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        classified = self._classify(tokens, idx)
        if classified is None:
            return None
        subject, conj_subject = classified
        token = tokens[idx]
        word = sentence[idx]

        ref_gender = _gender_grammeme(conj_subject) or _gender_grammeme(subject)
        new_word = _corrupt_predicate_number(token, word, "sing", ref_gender=ref_gender)
        if new_word is None:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_number = token.get_feature("Number", "Plur")
        return ErrorResult(
            error_type="agr_sv_coordinated",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
        )
