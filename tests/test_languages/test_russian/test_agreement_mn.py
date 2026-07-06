"""Tests for Russian modifier-noun agreement error handlers (§191-197)."""

from __future__ import annotations

import random

import pymorphy3
import pytest

from synterr.core.protocol import AnalyzedToken, ErrorHandler
from synterr.languages.russian.errors.agreement_mn import (
    AgrMnAppositionErrorHandler,
    AgrMnCompoundTermErrorHandler,
    AgrMnNumeralAdjErrorHandler,
)

morph = pymorphy3.MorphAnalyzer()


class _SameWordResult:
    """Mimics a pymorphy InflectionResult whose word never changes."""

    def __init__(self, word: str) -> None:
        self.word = word


class _SyncreticParse:
    """Fake parse whose inflect() always returns the SAME surface form,
    forcing the handlers' syncretism-skip branch regardless of grammemes."""

    tag = ""  # empty tag: "Apro"/"PRTF"/"PRTS"/"Poss"/"Fixd" substring checks all miss
    is_known = True

    def __init__(self, word: str) -> None:
        self._word = word

    def inflect(self, grammemes):
        return _SameWordResult(self._word)


class _FailingParse:
    """Fake parse whose inflect() always fails (simulates an unreachable
    paradigm slot)."""

    tag = ""
    is_known = True

    def inflect(self, grammemes):
        return None


def _plain_token(
    text: str,
    lemma: str,
    pos: str,
    idx: int,
    *,
    features: dict[str, str],
    dep_rel: str | None = None,
    head_idx: int | None = None,
    parse=None,
) -> AnalyzedToken:
    extra = {}
    if parse is not None:
        extra["pymorphy_parse"] = parse
    elif pos in {"NOUN", "PROPN", "ADJ"}:
        extra["pymorphy_parse"] = morph.parse(text)[0]
    return AnalyzedToken(
        text=text,
        lemma=lemma,
        pos=pos,
        features=features,
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
        extra=extra,
    )


_STANZA_BACKEND = None


def _stanza_backend():
    """Cached real stanza backend with dep parsing (slow to build once)."""
    global _STANZA_BACKEND
    if _STANZA_BACKEND is None:
        from synterr.languages.russian.backends.stanza_backend import StanzaBackend

        _STANZA_BACKEND = StanzaBackend(use_depparse=True, use_gpu=False)
    return _STANZA_BACKEND


# =============================================================================
# Protocol conformance
# =============================================================================


class TestAgreementMnProtocol:
    HANDLER_CLASSES = [
        AgrMnAppositionErrorHandler,
        AgrMnCompoundTermErrorHandler,
        AgrMnNumeralAdjErrorHandler,
    ]
    EXPECTED_NAMES = [
        "agr_mn_apposition",
        "agr_mn_compound_term",
        "agr_mn_numeral_adj",
    ]
    EXPECTED_SUBTYPES = [
        ["ag_mn_apposition"],
        ["ag_mn_compound_term"],
        ["ag_mn_special"],
    ]

    def test_implements_protocol(self):
        for cls in self.HANDLER_CLASSES:
            handler = cls()
            assert isinstance(handler, ErrorHandler)

    def test_names_and_subtypes(self):
        for cls, name, subtypes in zip(
            self.HANDLER_CLASSES,
            self.EXPECTED_NAMES,
            self.EXPECTED_SUBTYPES,
            strict=True,
        ):
            handler = cls()
            assert handler.name == name
            assert handler.subtypes == subtypes

    def test_category_and_length(self):
        for cls in self.HANDLER_CLASSES:
            handler = cls()
            assert handler.category == "MORPH"
            assert handler.changes_length is False


# =============================================================================
# ag_mn_apposition (§195-196)
# =============================================================================


class TestAgrMnApposition:
    """Token layout: [0]=head common noun, [1]=PROPN apposition."""

    def _tokens(self, *, head_lemma="город", head_case="Loc", propn_text="Москве"):
        head = _plain_token(
            "городе" if head_lemma == "город" else head_lemma,
            head_lemma,
            "NOUN",
            0,
            features={"Case": head_case, "Number": "Sing"},
            dep_rel="obl",
            head_idx=0,  # self-loop placeholder; irrelevant to this handler
        )
        propn = _plain_token(
            propn_text,
            morph.parse(propn_text)[0].normal_form,
            "PROPN",
            1,
            features={"Case": head_case, "Number": "Sing"},
            dep_rel="appos",
            head_idx=0,
        )
        return [head, propn]

    def test_positive_fires(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens()
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "ag_mn_apposition"
        assert result.category == "MORPH"
        assert result.fix_tag == "$TRANSFORM_CASE_Loc"
        assert sentence[1] == "Москва"

    def test_skip_non_agreeing_head_class(self):
        """§197: озеро-class heads do not require apposition agreement."""
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens(head_lemma="озеро", propn_text="Байкал")
        # "Байкал" round-trips to itself (already nominative) regardless, but
        # the head-lemma gate must reject this before that even matters.
        assert handler.can_apply(tokens, 1) is False

    def test_skip_o_ending_toponym(self):
        """Пушкино-type -о names conventionally stay undeclined (§197)."""
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens(head_case="Dat", propn_text="Пушкино")
        tokens[0] = _plain_token(
            "городу",
            "город",
            "NOUN",
            0,
            features={"Case": "Dat", "Number": "Sing"},
            dep_rel="obl",
            head_idx=0,
        )
        assert handler.can_apply(tokens, 1) is False

    def test_skip_composite_name(self):
        """A dependent on the toponym (e.g. "Нижний Новгород") means it is
        part of a multi-word name — skip rather than corrupt half of it."""
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens(propn_text="Новгород")
        adj = _plain_token(
            "Нижний",
            "нижний",
            "ADJ",
            2,
            features={"Case": "Loc"},
            dep_rel="amod",
            head_idx=1,
        )
        tokens = [*tokens, adj]
        assert handler.can_apply(tokens, 1) is False

    def test_skip_head_not_oblique(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens(head_case="Nom", propn_text="Москва")
        assert handler.can_apply(tokens, 1) is False

    def test_skip_indeclinable_fixd(self):
        """Foreign indeclinable names (Сочи, Баку, ...) never agree."""
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens(propn_text="Сочи")
        assert handler.can_apply(tokens, 1) is False

    def test_no_dep_info_blocks(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens()
        propn = tokens[1]
        tokens[1] = AnalyzedToken(
            text=propn.text,
            lemma=propn.lemma,
            pos=propn.pos,
            features=propn.features,
            idx=propn.idx,
            dep_rel=None,
            head_idx=None,
            extra=propn.extra,
        )
        assert handler.can_apply(tokens, 1) is False

    def test_syncretism_skip(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens()
        tokens[1].extra["pymorphy_parse"] = _SyncreticParse(tokens[1].text)
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence[1] == tokens[1].text

    def test_inflection_failure_skip(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = self._tokens()
        tokens[1].extra["pymorphy_parse"] = _FailingParse()
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None

    @pytest.mark.slow
    def test_real_backend_gorode_moskve(self):
        handler = AgrMnAppositionErrorHandler()
        tokens = _stanza_backend().analyze("Он живёт в городе Москве.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "Москве")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "Москва"
        assert result.error_type == "ag_mn_apposition"

    @pytest.mark.slow
    def test_real_backend_ozero_baikal_does_not_fire(self):
        """§197: lake names do not require apposition agreement."""
        handler = AgrMnAppositionErrorHandler()
        tokens = _stanza_backend().analyze("Мы гуляли по озеру Байкал.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "Байкал")
        assert handler.can_apply(tokens, idx) is False

    @pytest.mark.slow
    def test_real_backend_pushkino_does_not_fire(self):
        """§197: -о toponyms conventionally stay undeclined."""
        handler = AgrMnAppositionErrorHandler()
        tokens = _stanza_backend().analyze("Поезд подъезжал к городу Пушкино.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "Пушкино")
        assert handler.can_apply(tokens, idx) is False


# =============================================================================
# ag_mn_compound_term (§197)
# =============================================================================


class TestAgrMnCompoundTerm:
    def _tokens(self, *, second_text="ресторане", second_lemma="ресторан", case="Loc"):
        first = _plain_token(
            "вагоне",
            "вагон",
            "NOUN",
            0,
            features={"Case": case, "Number": "Sing"},
            dep_rel="obl",
            head_idx=3,
        )
        hyphen = _plain_token(
            "-",
            "-",
            "PUNCT",
            1,
            features={},
            dep_rel="punct",
            head_idx=2,
        )
        second = _plain_token(
            second_text,
            second_lemma,
            "NOUN",
            2,
            features={"Case": case, "Number": "Sing"},
            dep_rel="appos",
            head_idx=0,
        )
        return [first, hyphen, second]

    def test_positive_fires(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens()
        assert handler.can_apply(tokens, 2) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "ag_mn_compound_term"
        assert result.category == "MORPH"
        assert result.fix_tag == "$TRANSFORM_CASE_Loc"
        assert sentence[2] == "ресторан"

    def test_skip_no_hyphen_between(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens()
        tokens[1] = _plain_token(
            "и", "и", "CCONJ", 1, features={}, dep_rel="cc", head_idx=2
        )
        assert handler.can_apply(tokens, 2) is False

    def test_skip_head_not_oblique(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens(case="Nom")
        assert handler.can_apply(tokens, 2) is False

    def test_skip_unknown_word(self):
        """Brand-like coinages that are not real dictionary nouns are
        rejected via strict ``word_is_known``."""
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens(second_text="ксывзюм", second_lemma="ксывзюм")
        assert handler.can_apply(tokens, 2) is False

    def test_no_dep_info_blocks(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens()
        second = tokens[2]
        tokens[2] = AnalyzedToken(
            text=second.text,
            lemma=second.lemma,
            pos=second.pos,
            features=second.features,
            idx=second.idx,
            dep_rel=None,
            head_idx=None,
            extra=second.extra,
        )
        assert handler.can_apply(tokens, 2) is False

    def test_syncretism_skip(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens()
        tokens[2].extra["pymorphy_parse"] = _SyncreticParse(tokens[2].text)
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
        assert result is None
        assert sentence[2] == tokens[2].text

    def test_inflection_failure_skip(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = self._tokens()
        tokens[2].extra["pymorphy_parse"] = _FailingParse()
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
        assert result is None

    @pytest.mark.slow
    def test_real_backend_vagone_restorane(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = _stanza_backend().analyze("Мы обедали в вагоне-ресторане.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "ресторане")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "ресторан"
        assert result.error_type == "ag_mn_compound_term"

    @pytest.mark.slow
    def test_real_backend_kresle_kachalke(self):
        handler = AgrMnCompoundTermErrorHandler()
        tokens = _stanza_backend().analyze("Дети играли в кресле-качалке.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "качалке")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "качалка"


# =============================================================================
# ag_mn_special (§193)
# =============================================================================


class TestAgrMnNumeralAdj:
    def _tokens(
        self,
        *,
        num_text="два",
        num_lemma="два",
        adj_text="новых",
        noun_text="дома",
        noun_lemma="дом",
        noun_gender="Masc",
    ):
        num = _plain_token(
            num_text,
            num_lemma,
            "NUM",
            0,
            features={"Case": "Nom"},
            dep_rel="nummod:gov",
            head_idx=2,
        )
        adj = _plain_token(
            adj_text,
            "новый",
            "ADJ",
            1,
            features={"Number": "Plur"},
            dep_rel="amod",
            head_idx=2,
        )
        noun = _plain_token(
            noun_text,
            noun_lemma,
            "NOUN",
            2,
            features={"Case": "Gen", "Number": "Sing", "Gender": noun_gender},
            dep_rel="obl",
            head_idx=3,
        )
        return [num, adj, noun]

    def test_masc_neut_norm_fires(self):
        """«два новых дома» -> «два новые дома» (masc/neut takes gen-pl)."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens()
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert result.error_type == "ag_mn_special"
        assert result.category == "MORPH"
        assert sentence[1] == "новые"

    def test_fem_norm_fires(self):
        """«две новые книги» -> «две новых книги» (fem takes nom-pl)."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens(
            num_text="две",
            num_lemma="два",
            adj_text="новые",
            noun_text="книги",
            noun_lemma="книга",
            noun_gender="Fem",
        )
        assert handler.can_apply(tokens, 1) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[1] == "новых"

    def test_digit_form_numeral_fires(self):
        """Bare-digit numeral surface forms (2/3/4) also trigger the chain."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens(num_text="2", num_lemma="2")
        assert handler.can_apply(tokens, 1) is True

    def test_skip_numeral_5plus(self):
        """5+ noun-noun genitive-plural governs regularly — not this rule."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens(num_text="пять", num_lemma="пять")
        assert handler.can_apply(tokens, 1) is False

    def test_skip_possessive_adjective(self):
        """§193: -ин/-ов possessives stay genitive-plural regardless of the
        noun's gender — including them in the fem branch would "correct" an
        already-correct form."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens(
            num_text="две",
            num_lemma="два",
            adj_text="бабушкиных",
            noun_text="подруги",
            noun_lemma="подруга",
            noun_gender="Fem",
        )
        assert handler.can_apply(tokens, 1) is False

    def test_skip_fem_stress_shift_denylist(self):
        """гора/слеза: Rozental names these explicitly as fem exceptions
        where genitive-plural (not nominative-plural) is the norm."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens(
            num_text="две",
            num_lemma="два",
            adj_text="высоких",
            noun_text="горы",
            noun_lemma="гора",
            noun_gender="Fem",
        )
        assert handler.can_apply(tokens, 1) is False

    def test_skip_singular_adjective(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens()
        tokens[1] = _plain_token(
            "новый",
            "новый",
            "ADJ",
            1,
            features={"Number": "Sing"},
            dep_rel="amod",
            head_idx=2,
        )
        assert handler.can_apply(tokens, 1) is False

    def test_no_dep_info_blocks(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens()
        adj = tokens[1]
        tokens[1] = AnalyzedToken(
            text=adj.text,
            lemma=adj.lemma,
            pos=adj.pos,
            features=adj.features,
            idx=adj.idx,
            dep_rel=None,
            head_idx=None,
            extra=adj.extra,
        )
        assert handler.can_apply(tokens, 1) is False

    def test_syncretism_skip(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens()
        tokens[1].extra["pymorphy_parse"] = _SyncreticParse(tokens[1].text)
        assert handler.can_apply(tokens, 1) is False
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence[1] == tokens[1].text

    def test_inflection_failure_skip(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = self._tokens()
        tokens[1].extra["pymorphy_parse"] = _FailingParse()
        assert handler.can_apply(tokens, 1) is False
        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None

    @pytest.mark.slow
    def test_real_backend_dva_novykh_doma(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = _stanza_backend().analyze("Мы видели два новых дома.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "новых")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "новые"
        assert result.error_type == "ag_mn_special"

    @pytest.mark.slow
    def test_real_backend_dve_novye_knigi(self):
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = _stanza_backend().analyze("Он купил две новые книги.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "новые")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "новых"

    @pytest.mark.slow
    def test_real_backend_oblique_context_does_not_fire(self):
        """«двумя новыми домами» (Instrumental) is regular oblique agreement,
        not the 2-4 genitive-singular-noun construction."""
        handler = AgrMnNumeralAdjErrorHandler()
        tokens = _stanza_backend().analyze("Он гордится двумя новыми домами.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "новыми")
        assert handler.can_apply(tokens, idx) is False
