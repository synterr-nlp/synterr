"""Tests for Russian subject-verb agreement error handlers (§183-190)."""

from __future__ import annotations

import random

import pymorphy3

from synterr.core.protocol import AnalyzedToken, ErrorHandler
from synterr.languages.russian.errors.agreement_sv import (
    AgrSvApproximateErrorHandler,
    AgrSvCollectiveErrorHandler,
    AgrSvCompoundErrorHandler,
    AgrSvCoordinatedErrorHandler,
    AgrSvCountingErrorHandler,
)

morph = pymorphy3.MorphAnalyzer()


class _SameWordResult:
    """Mimics a pymorphy InflectionResult whose word never changes."""

    def __init__(self, word: str) -> None:
        self.word = word


class _SyncreticParse:
    """Fake parse whose inflect() always returns the SAME surface form,
    forcing the handlers' syncretism-skip branch regardless of grammemes."""

    def __init__(self, word: str) -> None:
        self._word = word

    def inflect(self, grammemes):
        return _SameWordResult(self._word)


class _FailingParse:
    """Fake parse whose inflect() always fails (simulates an unreachable
    paradigm slot)."""

    def inflect(self, grammemes):
        return None


_UNSET = object()


def _verb_token(
    text: str,
    lemma: str,
    idx: int,
    *,
    features: dict[str, str],
    dep_rel: str | None = "root",
    head_idx=_UNSET,
    parse=None,
) -> AnalyzedToken:
    """Build a VERB AnalyzedToken. ``head_idx`` defaults to ``idx`` (root
    convention); pass ``head_idx=None`` explicitly (together with
    ``dep_rel=None``) to build a token with no dep info at all."""
    if parse is None:
        parse = morph.parse(text)[0]
    resolved_head_idx = idx if head_idx is _UNSET else head_idx
    return AnalyzedToken(
        text=text,
        lemma=lemma,
        pos="VERB",
        features=features,
        idx=idx,
        dep_rel=dep_rel,
        head_idx=resolved_head_idx,
        extra={"pymorphy_parse": parse},
    )


def _plain_token(
    text: str,
    lemma: str,
    pos: str,
    idx: int,
    *,
    features: dict[str, str],
    dep_rel: str | None = None,
    head_idx: int | None = None,
) -> AnalyzedToken:
    return AnalyzedToken(
        text=text,
        lemma=lemma,
        pos=pos,
        features=features,
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )


# =============================================================================
# Protocol conformance
# =============================================================================


class TestAgreementSvProtocol:
    HANDLER_CLASSES = [
        AgrSvCollectiveErrorHandler,
        AgrSvCountingErrorHandler,
        AgrSvApproximateErrorHandler,
        AgrSvCompoundErrorHandler,
        AgrSvCoordinatedErrorHandler,
    ]
    EXPECTED_NAMES = [
        "agr_sv_collective",
        "agr_sv_counting",
        "agr_sv_approximate",
        "agr_sv_compound",
        "agr_sv_coordinated",
    ]

    def test_implements_protocol(self):
        for cls in self.HANDLER_CLASSES:
            handler = cls()
            assert isinstance(handler, ErrorHandler)

    def test_names_and_subtypes(self):
        for cls, name in zip(self.HANDLER_CLASSES, self.EXPECTED_NAMES, strict=True):
            handler = cls()
            assert handler.name == name
            assert handler.subtypes == [name]

    def test_category_and_length(self):
        for cls in self.HANDLER_CLASSES:
            handler = cls()
            assert handler.category == "MORPH"
            assert handler.changes_length is False


# =============================================================================
# agr_sv_collective (§183)
# =============================================================================


class TestAgrSvCollective:
    def _tokens(self, *, with_gen_plural_dependent: bool):
        extra = []
        verb_idx = 2 if with_gen_plural_dependent else 1
        if with_gen_plural_dependent:
            extra.append(
                _plain_token(
                    "студентов",
                    "студент",
                    "NOUN",
                    1,
                    features={"Case": "Gen", "Number": "Plur"},
                    dep_rel="nmod",
                    head_idx=0,
                )
            )
        subj = _plain_token(
            "Большинство",
            "большинство",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Neut"},
            dep_rel="nsubj",
            head_idx=verb_idx,
        )
        verb = _verb_token(
            "закончилось",
            "закончиться",
            verb_idx,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
        )
        return [subj, *extra, verb], verb_idx

    def test_bare_collective_subject_fires(self):
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=False)
        assert handler.can_apply(tokens, verb_idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, verb_idx, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "agr_sv_collective"
        assert result.category == "MORPH"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Sing"
        assert sentence[verb_idx] == "закончились"

    def test_short_participle_predicate_fires(self):
        """Short-form participle predicates ("приглашено") count as
        predicates too, not just finite verbs."""
        handler = AgrSvCollectiveErrorHandler()
        subj = _plain_token(
            "Большинство",
            "большинство",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Neut"},
            dep_rel="nsubj",
            head_idx=1,
        )
        verb = _verb_token(
            "приглашено",
            "пригласить",
            1,
            features={
                "VerbForm": "Part",
                "Variant": "Short",
                "Number": "Sing",
                "Gender": "Neut",
            },
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is True
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[1] == "приглашены"

    def test_gen_plural_dependent_blocks(self):
        """§183: «большинство студентов» licenses both numbers — skip."""
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=True)
        assert handler.can_apply(tokens, verb_idx) is False
        sentence = [t.text for t in tokens]
        assert (
            handler.apply(tokens, sentence, verb_idx, set(), rng=random.Random(0))
            is None
        )

    def test_non_collective_lemma_does_not_fire(self):
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=False)
        tokens[0] = _plain_token(
            "Компания",
            "компания",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nsubj",
            head_idx=verb_idx,
        )
        assert handler.can_apply(tokens, verb_idx) is False

    def test_no_dep_info_blocks(self):
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=False)
        verb = tokens[verb_idx]
        tokens[verb_idx] = AnalyzedToken(
            text=verb.text,
            lemma=verb.lemma,
            pos=verb.pos,
            features=verb.features,
            idx=verb.idx,
            dep_rel=None,
            head_idx=None,
            extra=verb.extra,
        )
        assert handler.can_apply(tokens, verb_idx) is False

    def test_syncretism_skip(self):
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=False)
        verb = tokens[verb_idx]
        verb.extra["pymorphy_parse"] = _SyncreticParse(verb.text)
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, verb_idx, set(), rng=random.Random(0))
        assert result is None
        assert sentence[verb_idx] == verb.text

    def test_inflection_failure_skip(self):
        handler = AgrSvCollectiveErrorHandler()
        tokens, verb_idx = self._tokens(with_gen_plural_dependent=False)
        tokens[verb_idx].extra["pymorphy_parse"] = _FailingParse()
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, verb_idx, set(), rng=random.Random(0))
        assert result is None


# =============================================================================
# agr_sv_counting (§184)
# =============================================================================


class TestAgrSvCounting:
    def test_two_four_class_fires(self):
        """«Два студента пришли» -> «Два студента пришло» (impersonal neut)."""
        handler = AgrSvCountingErrorHandler()
        num = _plain_token(
            "Два",
            "два",
            "NUM",
            0,
            features={"Case": "Nom"},
            dep_rel="nummod:gov",
            head_idx=1,
        )
        subj = _plain_token(
            "студента",
            "студент",
            "NOUN",
            1,
            features={"Case": "Gen", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=2,
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            2,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],  # plur/past, not the imperative homograph
        )
        tokens = [num, subj, verb]
        assert handler.can_apply(tokens, 2) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "agr_sv_counting"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Plur"
        assert sentence[2] == "пришло"

    def test_value_class_5plus_is_skipped(self):
        """5+ licenses both numbers about equally — deliberately unimplemented."""
        handler = AgrSvCountingErrorHandler()
        num = _plain_token(
            "Пять",
            "пять",
            "NUM",
            0,
            features={"Case": "Nom"},
            dep_rel="nummod:gov",
            head_idx=1,
        )
        subj = _plain_token(
            "студентов",
            "студент",
            "NOUN",
            1,
            features={"Case": "Gen", "Number": "Plur"},
            dep_rel="nsubj",
            head_idx=2,
        )
        verb = _verb_token(
            "пришло",
            "прийти",
            2,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
        )
        tokens = [num, subj, verb]
        assert handler.can_apply(tokens, 2) is False

    def test_large_count_noun_gender_mismatch_fires(self):
        """«Тысяча человек пришла» -> gender-mismatched «пришло»."""
        handler = AgrSvCountingErrorHandler()
        subj = _plain_token(
            "Тысяча",
            "тысяча",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nsubj",
            head_idx=1,
        )
        verb = _verb_token(
            "пришла",
            "прийти",
            1,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "agr_sv_counting"
        assert result.fix_tag == "$TRANSFORM_GENDER_Fem"
        assert sentence[1] == "пришло"

    def test_large_count_noun_without_gender_feature_blocks(self):
        """Present tense has no Gender feature — nothing to mismatch."""
        handler = AgrSvCountingErrorHandler()
        subj = _plain_token(
            "Тысяча",
            "тысяча",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nsubj",
            head_idx=1,
        )
        verb = _verb_token(
            "приходит",
            "приходить",
            1,
            features={"Tense": "Pres", "Number": "Sing", "Person": "3"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is False

    def test_no_dep_info_blocks(self):
        handler = AgrSvCountingErrorHandler()
        verb = _verb_token(
            "пришла",
            "прийти",
            0,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
            dep_rel=None,
            head_idx=None,
        )
        tokens = [verb]
        assert handler.can_apply(tokens, 0) is False

    def test_syncretism_skip(self):
        handler = AgrSvCountingErrorHandler()
        subj = _plain_token(
            "Тысяча",
            "тысяча",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nsubj",
            head_idx=1,
        )
        verb = _verb_token(
            "пришла",
            "прийти",
            1,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
            parse=_SyncreticParse("пришла"),
        )
        tokens = [subj, verb]
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence[1] == "пришла"


# =============================================================================
# agr_sv_approximate (§185)
# =============================================================================


class TestAgrSvApproximate:
    def _tokens(self, verb_text: str, verb_features: dict[str, str], *, parse=None):
        quant = _plain_token(
            "Около", "около", "ADV", 0, features={}, dep_rel="case", head_idx=1
        )
        num = _plain_token(
            "ста",
            "сто",
            "NUM",
            1,
            features={"Case": "Gen"},
            dep_rel="nummod:gov",
            head_idx=2,
        )
        subj = _plain_token(
            "человек",
            "человек",
            "NOUN",
            2,
            features={"Case": "Gen", "Number": "Plur"},
            dep_rel="nsubj",
            head_idx=3,
        )
        verb = _verb_token(verb_text, "прийти", 3, features=verb_features, parse=parse)
        return [quant, num, subj, verb]

    def test_sg_to_pl_fires(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришло", {"Tense": "Past", "Number": "Sing", "Gender": "Neut"}
        )
        assert handler.can_apply(tokens, 3) is True
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is not None
        assert result.error_type == "agr_sv_approximate"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Sing"
        assert sentence[3] == "пришли"

    def test_pl_to_sg_fires(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришли",
            {"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        assert handler.can_apply(tokens, 3) is True
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is not None
        assert result.fix_tag == "$TRANSFORM_NUMBER_Plur"
        assert sentence[3] == "пришло"

    def test_no_quantifier_blocks(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришло", {"Tense": "Past", "Number": "Sing", "Gender": "Neut"}
        )
        # Drop the "около" token -> no quantifier marker anywhere.
        tokens = tokens[1:]
        # re-index heads: num idx0, subj idx1 (head 2->1... need consistent set)
        tokens = [
            _plain_token(
                "ста",
                "сто",
                "NUM",
                0,
                features={"Case": "Gen"},
                dep_rel="nummod:gov",
                head_idx=1,
            ),
            _plain_token(
                "человек",
                "человек",
                "NOUN",
                1,
                features={"Case": "Gen", "Number": "Plur"},
                dep_rel="nsubj",
                head_idx=2,
            ),
            _verb_token(
                "пришло",
                "прийти",
                2,
                features={"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
            ),
        ]
        assert handler.can_apply(tokens, 2) is False

    def test_non_genitive_subject_blocks(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришло", {"Tense": "Past", "Number": "Sing", "Gender": "Neut"}
        )
        tokens[2] = _plain_token(
            "человек",
            "человек",
            "NOUN",
            2,
            features={"Case": "Nom", "Number": "Plur"},
            dep_rel="nsubj",
            head_idx=3,
        )
        assert handler.can_apply(tokens, 3) is False

    def test_no_dep_info_blocks(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришло", {"Tense": "Past", "Number": "Sing", "Gender": "Neut"}
        )
        verb = tokens[3]
        tokens[3] = AnalyzedToken(
            text=verb.text,
            lemma=verb.lemma,
            pos=verb.pos,
            features=verb.features,
            idx=verb.idx,
            dep_rel=None,
            head_idx=None,
            extra=verb.extra,
        )
        assert handler.can_apply(tokens, 3) is False

    def test_syncretism_skip(self):
        handler = AgrSvApproximateErrorHandler()
        tokens = self._tokens(
            "пришло",
            {"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
            parse=_SyncreticParse("пришло"),
        )
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is None


# =============================================================================
# agr_sv_compound (§186-189)
# =============================================================================


class TestAgrSvCompound:
    def test_koto_clause_sg_to_pl_fires(self):
        """§187: «кто пришёл» is correct; corrupting to «пришли» is the
        real error of agreeing with a plural antecedent instead."""
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "кто", "кто", "PRON", 0, features={}, dep_rel="nsubj", head_idx=1
        )
        verb = _verb_token(
            "пришёл",
            "прийти",
            1,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is not None
        assert result.error_type == "agr_sv_compound"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Sing"
        assert sentence[1] == "пришли"

    def test_koto_already_plural_blocks(self):
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "кто", "кто", "PRON", 0, features={}, dep_rel="nsubj", head_idx=1
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            1,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is False

    def test_comitative_does_not_fire(self):
        """§186 licenses BOTH agreements for comitative subjects («Брат с
        сестрой пришли») -- the collapse-to-singular branch was REMOVED
        (audit, 2026-07-07) because it produced correct Russian, not an
        error. Regression test: this shape must never trigger the handler."""
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "Брат",
            "брат",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=3,
        )
        marker = _plain_token(
            "с", "с", "ADP", 1, features={}, dep_rel="case", head_idx=2
        )
        companion = _plain_token(
            "сестрой",
            "сестра",
            "NOUN",
            2,
            features={"Case": "Ins", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nmod",
            head_idx=0,
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            3,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        tokens = [subj, marker, companion, verb]
        assert handler.can_apply(tokens, 3) is False

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is None
        assert sentence[3] == "пришли"

    def test_comitative_already_singular_blocks(self):
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "Брат",
            "брат",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=3,
        )
        marker = _plain_token(
            "с", "с", "ADP", 1, features={}, dep_rel="case", head_idx=2
        )
        companion = _plain_token(
            "сестрой",
            "сестра",
            "NOUN",
            2,
            features={"Case": "Ins", "Number": "Sing", "Gender": "Fem"},
            dep_rel="nmod",
            head_idx=0,
        )
        verb = _verb_token(
            "пришёл",
            "прийти",
            3,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
        )
        tokens = [subj, marker, companion, verb]
        assert handler.can_apply(tokens, 3) is False

    def test_acronym_gender_flip_fires(self):
        """«МГУ объявил» -> flipped to a different, wrong gender."""
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "МГУ", "мгу", "PROPN", 0, features={}, dep_rel="nsubj", head_idx=1
        )
        verb = _verb_token(
            "объявил",
            "объявить",
            1,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is not None
        assert result.fix_tag == "$TRANSFORM_GENDER_Masc"
        assert sentence[1] == "объявило"

    def test_acronym_without_past_tense_blocks(self):
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "МГУ", "мгу", "PROPN", 0, features={}, dep_rel="nsubj", head_idx=1
        )
        verb = _verb_token(
            "объявляет",
            "объявлять",
            1,
            features={"Tense": "Pres", "Number": "Sing", "Person": "3"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is False

    def test_lowercase_propn_is_not_acronym(self):
        """A capitalized ordinary name (Иван) must not trigger the acronym
        branch just because it starts with an uppercase letter."""
        handler = AgrSvCompoundErrorHandler()
        subj = _plain_token(
            "Иван", "иван", "PROPN", 0, features={}, dep_rel="nsubj", head_idx=1
        )
        verb = _verb_token(
            "объявил",
            "объявить",
            1,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
        )
        tokens = [subj, verb]
        assert handler.can_apply(tokens, 1) is False

    def test_no_dep_info_blocks(self):
        handler = AgrSvCompoundErrorHandler()
        verb = _verb_token(
            "пришёл",
            "прийти",
            0,
            features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
            dep_rel=None,
            head_idx=None,
        )
        tokens = [verb]
        assert handler.can_apply(tokens, 0) is False


# =============================================================================
# agr_sv_coordinated (§190)
# =============================================================================


class TestAgrSvCoordinated:
    def test_preposed_coordinated_subjects_fire(self):
        """«Брат и сестра пришли» -> proximity-agreement «пришла»."""
        handler = AgrSvCoordinatedErrorHandler()
        brat = _plain_token(
            "Брат",
            "брат",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=3,
        )
        cc = _plain_token("и", "и", "CCONJ", 1, features={}, dep_rel="cc", head_idx=2)
        sestra = _plain_token(
            "сестра",
            "сестра",
            "NOUN",
            2,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="conj",
            head_idx=0,
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            3,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        tokens = [brat, cc, sestra, verb]
        assert handler.can_apply(tokens, 3) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is not None
        assert result.error_type == "agr_sv_coordinated"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Plur"
        # Proximity agreement: nearer conjunct (сестра, Fem) wins.
        assert sentence[3] == "пришла"

    def test_postposed_verb_order_blocks(self):
        """Verb-first order licenses singular — the ordering guard must
        prevent firing there."""
        handler = AgrSvCoordinatedErrorHandler()
        verb = _verb_token(
            "Пришли",
            "прийти",
            0,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        brat = _plain_token(
            "брат",
            "брат",
            "NOUN",
            1,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=0,
        )
        cc = _plain_token("и", "и", "CCONJ", 2, features={}, dep_rel="cc", head_idx=3)
        sestra = _plain_token(
            "сестра",
            "сестра",
            "NOUN",
            3,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="conj",
            head_idx=1,
        )
        tokens = [verb, brat, cc, sestra]
        assert handler.can_apply(tokens, 0) is False

    def test_or_coordination_blocks(self):
        """«или» is not «и» — no obligatory plural, so skip."""
        handler = AgrSvCoordinatedErrorHandler()
        brat = _plain_token(
            "Брат",
            "брат",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=3,
        )
        cc = _plain_token(
            "или", "или", "CCONJ", 1, features={}, dep_rel="cc", head_idx=2
        )
        sestra = _plain_token(
            "сестра",
            "сестра",
            "NOUN",
            2,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="conj",
            head_idx=0,
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            3,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
        )
        tokens = [brat, cc, sestra, verb]
        assert handler.can_apply(tokens, 3) is False

    def test_no_dep_info_blocks(self):
        handler = AgrSvCoordinatedErrorHandler()
        verb = _verb_token(
            "пришли",
            "прийти",
            0,
            features={"Tense": "Past", "Number": "Plur"},
            parse=morph.parse("пришли")[1],
            dep_rel=None,
            head_idx=None,
        )
        tokens = [verb]
        assert handler.can_apply(tokens, 0) is False

    def test_syncretism_skip(self):
        handler = AgrSvCoordinatedErrorHandler()
        brat = _plain_token(
            "Брат",
            "брат",
            "NOUN",
            0,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            dep_rel="nsubj",
            head_idx=3,
        )
        cc = _plain_token("и", "и", "CCONJ", 1, features={}, dep_rel="cc", head_idx=2)
        sestra = _plain_token(
            "сестра",
            "сестра",
            "NOUN",
            2,
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            dep_rel="conj",
            head_idx=0,
        )
        verb = _verb_token(
            "пришли",
            "прийти",
            3,
            features={"Tense": "Past", "Number": "Plur"},
            parse=_SyncreticParse("пришли"),
        )
        tokens = [brat, cc, sestra, verb]
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
        assert result is None
