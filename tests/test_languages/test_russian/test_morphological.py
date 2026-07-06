from __future__ import annotations

import random

import pymorphy3
import pytest

from synterr.core.protocol import AnalyzedToken, ErrorHandler

morph = pymorphy3.MorphAnalyzer()


class TestMorphologicalErrorHandlers:
    """Tests for Russian morphological error handlers."""

    def test_noun_case_handler_protocol(self):
        """Test NounCaseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "noun_case"
        assert handler.category == "MORPH"

    def test_noun_number_handler_protocol(self):
        """Test NounNumberErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import (
            NounNumberErrorHandler,
        )

        handler = NounNumberErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "noun_number"
        assert handler.category == "MORPH"

    def test_adj_case_handler_protocol(self):
        """Test AdjCaseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import AdjCaseErrorHandler

        handler = AdjCaseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "adj_case"

    def test_verb_tense_handler_protocol(self):
        """Test VerbTenseErrorHandler implements protocol."""
        from synterr.languages.russian.errors.morphological import VerbTenseErrorHandler

        handler = VerbTenseErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "verb_tense"

    def test_can_apply_checks_pos(self):
        """Test that handlers check correct POS tags."""
        from synterr.languages.russian.errors.morphological import (
            AdjCaseErrorHandler,
            NounCaseErrorHandler,
            VerbTenseErrorHandler,
        )

        noun_handler = NounCaseErrorHandler()
        adj_handler = AdjCaseErrorHandler()
        verb_handler = VerbTenseErrorHandler()

        # Create mock tokens
        tokens = [
            AnalyzedToken(
                text="книга",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom"},
                idx=0,
                dep_rel="obl",
                extra={"pymorphy_parse": "mock"},
            ),
            AnalyzedToken(
                text="красивая",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Nom"},
                idx=1,
                extra={"pymorphy_parse": "mock"},
            ),
            AnalyzedToken(
                text="стоит",
                lemma="стоять",
                pos="VERB",
                features={"Tense": "Pres"},
                idx=2,
                extra={"pymorphy_parse": "mock"},
            ),
            # Temporal anchor: verb_tense requires one attached to the verb.
            AnalyzedToken(
                text="завтра",
                lemma="завтра",
                pos="ADV",
                features={},
                idx=3,
                dep_rel="advmod",
                head_idx=2,
            ),
        ]

        # Noun handler should only apply to nouns
        assert noun_handler.can_apply(tokens, 0) is True
        assert noun_handler.can_apply(tokens, 1) is False
        assert noun_handler.can_apply(tokens, 2) is False

        # Adj handler should only apply to adjectives
        assert adj_handler.can_apply(tokens, 0) is False
        assert adj_handler.can_apply(tokens, 1) is True
        assert adj_handler.can_apply(tokens, 2) is False

        # Verb handler should only apply to verbs (with a temporal anchor)
        assert verb_handler.can_apply(tokens, 0) is False
        assert verb_handler.can_apply(tokens, 1) is False
        assert verb_handler.can_apply(tokens, 2) is True
        assert verb_handler.can_apply(tokens, 3) is False

    def test_noun_case_subtypes_declared(self):
        """The arc-aware split declares exactly three subtypes."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        assert NounCaseErrorHandler.subtypes == [
            "noun_case_governed",
            "noun_case_subject",
            "noun_case_other",
        ]

    def test_noun_case_requires_dep_arc(self):
        """No dep info → no fire (classification needs an arc), any arc → fire."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()
        base = dict(
            lemma="книга",
            pos="NOUN",
            features={"Case": "Nom"},
            extra={"pymorphy_parse": "mock"},
        )

        # Dep-attached nouns of every class → should apply (default weights
        # enable all three subtypes)
        for dep_rel in (
            "obl",
            "nmod",
            "iobj",
            "obj",
            "nsubj",
            "nsubj:pass",
            "conj",
            "root",
            "appos",
        ):
            token = AnalyzedToken(text="книга", idx=0, dep_rel=dep_rel, **base)
            assert handler.can_apply([token], 0) is True, f"should apply for {dep_rel}"

        # No dep info → should NOT apply
        for dep_rel in (None, ""):
            token = AnalyzedToken(text="книга", idx=0, dep_rel=dep_rel, **base)
            assert handler.can_apply([token], 0) is False, f"should reject {dep_rel!r}"


class TestNounCaseArcSubtypes:
    """Phase-2 arc-aware split: dep_rel deterministically decides the subtype."""

    CLASSIFICATION = {
        "obl": "noun_case_governed",
        "nmod": "noun_case_governed",
        "iobj": "noun_case_governed",
        "obj": "noun_case_governed",
        "nsubj": "noun_case_subject",
        "nsubj:pass": "noun_case_subject",
        "appos": "noun_case_other",
        "conj": "noun_case_other",
        "root": "noun_case_other",
        "orphan": "noun_case_other",
    }

    def _handler(self):
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        return NounCaseErrorHandler()

    def _token(self, dep_rel):
        parse = morph.parse("книги")[0]  # Gen Sing Fem
        return AnalyzedToken(
            text="книги",
            lemma="книга",
            pos="NOUN",
            features={"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
            idx=0,
            dep_rel=dep_rel,
            extra={"pymorphy_parse": parse},
        )

    def test_apply_emits_subtype_per_deprel(self):
        """error_type is the classified subtype, per dep_rel."""
        handler = self._handler()
        for dep_rel, expected in self.CLASSIFICATION.items():
            tokens = [self._token(dep_rel)]
            sentence = ["книги"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(42))
            assert result is not None, f"apply failed for {dep_rel}"
            assert result.error_type == expected, (
                f"{dep_rel}: expected {expected}, got {result.error_type}"
            )

    def test_no_dep_info_never_fires(self):
        """Dep gate unchanged from phase 1: no arc → apply returns None."""
        handler = self._handler()
        tokens = [self._token(None)]
        result = handler.apply(tokens, ["книги"], 0, set(), rng=random.Random(42))
        assert result is None

    def test_zero_weight_excludes_subtype(self):
        """A zeroed subtype never fires — no leak under another label."""
        handler = self._handler()
        for enabled in handler.subtypes:
            handler.set_subtype_weights(
                {s: (100.0 if s == enabled else 0.0) for s in handler.subtypes}
            )
            for dep_rel, classified in self.CLASSIFICATION.items():
                tokens = [self._token(dep_rel)]
                allowed = classified == enabled
                assert handler.can_apply(tokens, 0) is allowed, (
                    f"enabled={enabled}, dep_rel={dep_rel}"
                )
                result = handler.apply(
                    tokens, ["книги"], 0, set(), rng=random.Random(42)
                )
                if allowed:
                    assert result is not None and result.error_type == enabled
                else:
                    assert result is None, (
                        f"enabled={enabled} but {dep_rel} fired {result.error_type}"
                    )

    def test_enabled_subtypes_overrides_weights(self):
        """set_enabled_subtypes (CLI :subtype path) overrides zero weights."""
        handler = self._handler()
        handler.set_subtype_weights({s: 0.0 for s in handler.subtypes})
        handler.set_enabled_subtypes({"noun_case_subject"})

        subj = [self._token("nsubj")]
        gov = [self._token("obl")]
        assert handler.can_apply(subj, 0) is True
        assert handler.can_apply(gov, 0) is False
        result = handler.apply(subj, ["книги"], 0, set(), rng=random.Random(42))
        assert result is not None and result.error_type == "noun_case_subject"

        handler.set_enabled_subtypes(None)

    def test_enabled_subtypes_rejects_unknown(self):
        handler = self._handler()
        with pytest.raises(ValueError, match="Unknown subtypes"):
            handler.set_enabled_subtypes({"noun_case_bogus"})

    def test_confusion_matrix_applies_to_all_subtypes(self):
        """The RLC matrix machinery is shared: matrix lookup per subtype."""
        handler = self._handler()
        handler.set_confusion_matrix({"case": {"Gen": {"Nom": 1.0}}})
        for dep_rel in ("obl", "nsubj", "appos"):
            tokens = [self._token(dep_rel)]
            sentence = ["книги"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(42))
            assert result is not None
            assert sentence[0] == "книга", f"{dep_rel}: matrix not applied"

    def test_schema_mappings_resolve(self):
        """Every new subtype (and legacy noun_case) resolves in all schemas."""
        from synterr.schemas import load_schema

        expected_rlc = {
            "noun_case": "Gov",  # backward compat for pre-split data
            "noun_case_governed": "Gov",
            "noun_case_subject": "Nominative",
            "noun_case_other": "Infl",
        }
        rlc = load_schema("rlc")
        for subtype, tag in expected_rlc.items():
            assert rlc.get_tag_for_subtype(subtype) == tag
            assert tag in rlc.primary_tags

        rozental = load_schema("rozental")
        assert rozental.get_tag_for_subtype("noun_case_governed") == "gv_government"
        assert rozental.get_l2_tag_for_subtype("noun_case_governed") == "gv_case_choice"
        assert rozental.get_tag_for_subtype("noun_case_subject") == "mo_noun_case"
        assert rozental.get_l2_tag_for_subtype("noun_case_subject") is None
        assert rozental.get_tag_for_subtype("noun_case_other") == "mo_noun_case"
        assert (
            rozental.get_l2_tag_for_subtype("noun_case_other") == "mo_noun_case_other"
        )

        for schema_name in ("errant", "synterr"):
            schema = load_schema(schema_name)
            for subtype in expected_rlc:
                assert schema.get_tag_for_subtype(subtype) is not None, (
                    f"{schema_name} does not map {subtype}"
                )


class TestConfusionMatrixIntegration:
    """Tests for confusion-matrix-driven grammeme substitution."""

    def test_noun_case_uses_confusion_matrix(self):
        """Test NounCaseErrorHandler uses confusion matrix weights."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()

        # Deterministic matrix: Gen always → Nom
        handler.set_confusion_matrix(
            {
                "case": {"Gen": {"Nom": 1.0}},
            }
        )

        parse = morph.parse("книги")[0]  # Gen Sing Fem
        tokens = [
            AnalyzedToken(
                text="книги",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="obl",
                extra={"pymorphy_parse": parse},
            )
        ]

        rng = random.Random(42)
        sentence = ["книги"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        assert result.fix_tag == "$TRANSFORM_CASE_Gen"
        # With {Gen: {Nom: 1.0}}, should inflect to Nom
        assert sentence[0] == "книга"

    def test_noun_case_confusion_matrix_distribution(self):
        """Test that confusion matrix creates biased distribution over many runs."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()

        # Gen → 90% Nom, 10% Acc
        handler.set_confusion_matrix(
            {
                "case": {"Gen": {"Nom": 0.90, "Acc": 0.10}},
            }
        )

        parse = morph.parse("книги")[0]
        counts = {"Nom": 0, "Acc": 0, "other": 0}

        for seed in range(200):
            tokens = [
                AnalyzedToken(
                    text="книги",
                    lemma="книга",
                    pos="NOUN",
                    features={"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
                    idx=0,
                    dep_rel="nmod",
                    extra={"pymorphy_parse": parse},
                )
            ]
            sentence = ["книги"]
            modified = set()
            rng = random.Random(seed)
            result = handler.apply(tokens, sentence, 0, modified, rng=rng)
            if result is None:
                continue
            # Check which case it became
            nom_form = morph.parse("книга")[0].word
            acc_form = morph.parse("книгу")[0].word
            if sentence[0] == nom_form:
                counts["Nom"] += 1
            elif sentence[0] == acc_form:
                counts["Acc"] += 1
            else:
                counts["other"] += 1

        total = counts["Nom"] + counts["Acc"] + counts["other"]
        assert total > 0
        # Nom should be dominant (~90%)
        nom_ratio = counts["Nom"] / total
        assert nom_ratio > 0.75, (
            f"Expected Nom-dominant distribution, got Nom={nom_ratio:.2f}"
        )

    def test_noun_case_fallback_without_matrix(self):
        """Test NounCaseErrorHandler falls back to random without matrix."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()
        # No confusion matrix set

        parse = morph.parse("книги")[0]
        tokens = [
            AnalyzedToken(
                text="книги",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="obj",
                extra={"pymorphy_parse": parse},
            )
        ]

        rng = random.Random(42)
        sentence = ["книги"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        assert sentence[0] != "книги"

    def test_adj_gender_uses_confusion_matrix(self):
        """Test AdjGenderErrorHandler uses gender confusion matrix."""
        from synterr.languages.russian.errors.morphological import AdjGenderErrorHandler

        handler = AdjGenderErrorHandler()

        # Masc → always Fem
        handler.set_confusion_matrix(
            {
                "gender": {"Masc": {"Fem": 1.0}},
            }
        )

        parse = morph.parse("красивый")[0]  # Masc Sing Nom
        tokens = [
            AnalyzedToken(
                text="красивый",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
                idx=0,
                extra={"pymorphy_parse": parse},
            )
        ]

        rng = random.Random(42)
        sentence = ["красивый"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        assert result.fix_tag == "$TRANSFORM_GENDER_Masc"
        # Should become feminine form
        assert sentence[0] == "красивая"

    def test_adj_case_uses_confusion_matrix(self):
        """Test AdjCaseErrorHandler uses case confusion matrix."""
        from synterr.languages.russian.errors.morphological import AdjCaseErrorHandler

        handler = AdjCaseErrorHandler()

        # Gen → always Nom
        handler.set_confusion_matrix(
            {
                "case": {"Gen": {"Nom": 1.0}},
            }
        )

        parse = morph.parse("красивой")[0]  # Gen Sing Fem
        tokens = [
            AnalyzedToken(
                text="красивой",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Gen", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                extra={"pymorphy_parse": parse},
            )
        ]

        rng = random.Random(42)
        sentence = ["красивой"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        assert result.fix_tag == "$TRANSFORM_CASE_Gen"
        assert sentence[0] == "красивая"  # Nom Sing Fem


class TestDepTreeAgreement:
    """Tests for dep-tree-aware agreement error generation."""

    def test_adj_case_follows_head_noun(self):
        """Test AdjCaseErrorHandler follows amod → head noun."""
        from synterr.languages.russian.errors.morphological import AdjCaseErrorHandler

        handler = AdjCaseErrorHandler()

        # Matrix: Dat → always Nom
        handler.set_confusion_matrix(
            {
                "case": {"Dat": {"Nom": 1.0}},
            }
        )

        adj_parse = morph.parse("красивой")[0]  # Dat Sing Fem
        tokens = [
            # adj modifies noun via amod
            AnalyzedToken(
                text="красивой",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Dat", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="amod",
                head_idx=1,
                extra={"pymorphy_parse": adj_parse},
            ),
            # head noun
            AnalyzedToken(
                text="девушке",
                lemma="девушка",
                pos="NOUN",
                features={"Case": "Dat", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="obl",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("девушке")[0]},
            ),
            AnalyzedToken(
                text="дали",
                lemma="дать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Plur"},
                idx=2,
                dep_rel="root",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("дали")[0]},
            ),
        ]

        rng = random.Random(42)
        sentence = ["красивой", "девушке", "дали"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        # Head noun is Dat, matrix says Dat → Nom, so adj should become Nom
        assert sentence[0] == "красивая"  # Nom Sing Fem

    def test_adj_case_without_dep_tree_uses_own_case(self):
        """Test AdjCaseErrorHandler uses own case when no dep tree info."""
        from synterr.languages.russian.errors.morphological import AdjCaseErrorHandler

        handler = AdjCaseErrorHandler()

        # Matrix: Dat → always Nom
        handler.set_confusion_matrix(
            {
                "case": {"Dat": {"Nom": 1.0}},
            }
        )

        adj_parse = morph.parse("красивой")[0]  # Dat Sing Fem
        tokens = [
            AnalyzedToken(
                text="красивой",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Dat", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                extra={"pymorphy_parse": adj_parse},
            ),
        ]

        rng = random.Random(42)
        sentence = ["красивой"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        # No dep tree, uses own case (Dat), matrix says Dat → Nom
        assert sentence[0] == "красивая"

    def test_adj_gender_follows_head_noun(self):
        """Test AdjGenderErrorHandler follows amod → head noun's gender."""
        from synterr.languages.russian.errors.morphological import AdjGenderErrorHandler

        handler = AdjGenderErrorHandler()

        # Fem → always Masc
        handler.set_confusion_matrix(
            {
                "gender": {"Fem": {"Masc": 1.0}},
            }
        )

        adj_parse = morph.parse("красивая")[0]  # Nom Sing Fem
        tokens = [
            AnalyzedToken(
                text="красивая",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="amod",
                head_idx=1,
                extra={"pymorphy_parse": adj_parse},
            ),
            AnalyzedToken(
                text="книга",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("книга")[0]},
            ),
        ]

        rng = random.Random(42)
        sentence = ["красивая", "книга"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        # Head noun is Fem, matrix: Fem → Masc
        assert sentence[0] == "красивый"

    def test_adj_number_follows_head_noun(self):
        """Test AdjNumberErrorHandler follows amod → head noun's number."""
        from synterr.languages.russian.errors.morphological import AdjNumberErrorHandler

        handler = AdjNumberErrorHandler()

        adj_parse = morph.parse("красивая")[0]  # Nom Sing Fem
        tokens = [
            AnalyzedToken(
                text="красивая",
                lemma="красивый",
                pos="ADJ",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="amod",
                head_idx=1,
                extra={"pymorphy_parse": adj_parse},
            ),
            AnalyzedToken(
                text="книга",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("книга")[0]},
            ),
        ]

        rng = random.Random(42)
        sentence = ["красивая", "книга"]
        modified = set()
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        assert result.fix_tag == "$TRANSFORM_NUMBER_Sing"
        # Head is Sing → target Plur
        assert sentence[0] == "красивые"

    def test_verb_person_number_follows_nsubj(self):
        """Test VerbPersonNumberErrorHandler follows nsubj → subject."""
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()

        verb_parse = morph.parse("читала")[0]  # Past Sing Fem
        tokens = [
            AnalyzedToken(
                text="мама",
                lemma="мама",
                pos="NOUN",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("мама")[0]},
            ),
            AnalyzedToken(
                text="читала",
                lemma="читать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="root",
                head_idx=1,
                extra={"pymorphy_parse": verb_parse},
            ),
        ]

        # Seed that picks number change (past tense = has_number only)
        rng = random.Random(42)
        sentence = ["мама", "читала"]
        modified = set()
        result = handler.apply(tokens, sentence, 1, modified, rng=rng)

        assert result is not None
        assert result.fix_tag == "$TRANSFORM_NUMBER_Sing"
        # Subject is Sing → target Plur
        assert sentence[1] == "читали"

    def test_verb_person_number_without_subject_does_not_fire(self):
        """Pro-drop guard: no overt nsubj → flip would be grammatical, skip.

        "Читала книгу" → "Читали книгу" is a correct Russian sentence (pro-drop),
        so without an overt subject there is no recoverable error.
        """
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()

        verb_parse = morph.parse("читала")[0]
        tokens = [
            AnalyzedToken(
                text="читала",
                lemma="читать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="root",
                head_idx=0,
                extra={"pymorphy_parse": verb_parse},
            ),
        ]

        rng = random.Random(42)
        sentence = ["читала"]
        modified = set()

        assert handler.can_apply(tokens, 0) is False
        assert handler.apply(tokens, sentence, 0, modified, rng=rng) is None
        assert sentence[0] == "читала"

    def test_verb_person_number_imperative_does_not_fire(self):
        """Imperatives have no overt subject — Иди/Идите is a free choice."""
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()
        tokens = [
            AnalyzedToken(
                text="Иди",
                lemma="идти",
                pos="VERB",
                features={"Mood": "Imp", "Person": "2", "Number": "Sing"},
                idx=0,
                dep_rel="root",
                head_idx=0,
                extra={"pymorphy_parse": morph.parse("иди")[0]},
            ),
            AnalyzedToken(
                text="сюда",
                lemma="сюда",
                pos="ADV",
                features={},
                idx=1,
                dep_rel="advmod",
                head_idx=0,
            ),
        ]

        assert handler.can_apply(tokens, 0) is False
        sentence = ["Иди", "сюда"]
        assert handler.apply(tokens, sentence, 0, set(), rng=random.Random(0)) is None

    def _collective_subject_tokens(self, subj_text, subj_lemma, extra_tokens=()):
        verb_parse = morph.parse("пришло")[0]
        tokens = [
            AnalyzedToken(
                text=subj_text,
                lemma=subj_lemma,
                pos="NOUN",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Neut"},
                idx=0,
                dep_rel="nsubj",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse(subj_text)[0]},
            ),
            AnalyzedToken(
                text="студентов",
                lemma="студент",
                pos="NOUN",
                features={"Case": "Gen", "Number": "Plur"},
                idx=1,
                dep_rel="nmod",
                head_idx=0,
                extra={"pymorphy_parse": morph.parse("студентов")[0]},
            ),
            AnalyzedToken(
                text="пришло",
                lemma="прийти",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
                idx=2,
                dep_rel="root",
                head_idx=2,
                extra={"pymorphy_parse": verb_parse},
            ),
            *extra_tokens,
        ]
        return tokens

    def test_verb_person_number_collective_subject_does_not_fire(self):
        """§183: большинство/ряд/часть subjects license both numbers — skip."""
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()
        for subj_text, subj_lemma in [
            ("Большинство", "большинство"),
            ("Часть", "часть"),
        ]:
            tokens = self._collective_subject_tokens(subj_text, subj_lemma)
            assert handler.can_apply(tokens, 2) is False, subj_lemma
            sentence = [t.text for t in tokens]
            result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
            assert result is None, subj_lemma

    def test_verb_person_number_quantified_subject_does_not_fire(self):
        """§184: counting-phrase subjects (пять студентов) license both numbers."""
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()
        verb_parse = morph.parse("пришло")[0]
        tokens = [
            AnalyzedToken(
                text="Пять",
                lemma="пять",
                pos="NUM",
                features={"Case": "Nom"},
                idx=0,
                dep_rel="nummod:gov",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("пять")[0]},
            ),
            AnalyzedToken(
                text="студентов",
                lemma="студент",
                pos="NOUN",
                features={"Case": "Gen", "Number": "Plur"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("студентов")[0]},
            ),
            AnalyzedToken(
                text="пришло",
                lemma="прийти",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Neut"},
                idx=2,
                dep_rel="root",
                head_idx=2,
                extra={"pymorphy_parse": verb_parse},
            ),
        ]

        assert handler.can_apply(tokens, 2) is False
        sentence = [t.text for t in tokens]
        assert handler.apply(tokens, sentence, 2, set(), rng=random.Random(0)) is None

    def test_verb_person_number_plain_subject_still_fires(self):
        """Ordinary noun subject (мама) keeps the handler active."""
        from synterr.languages.russian.errors.morphological import (
            VerbPersonNumberErrorHandler,
        )

        handler = VerbPersonNumberErrorHandler()
        tokens = [
            AnalyzedToken(
                text="мама",
                lemma="мама",
                pos="NOUN",
                features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("мама")[0]},
            ),
            AnalyzedToken(
                text="читала",
                lemma="читать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="root",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("читала")[0]},
            ),
        ]
        assert handler.can_apply(tokens, 1) is True


class TestAdjAgreementPrecisionGuards:
    """Precision fixes for adj_gender/adj_number (native-annotation pass).

    Regressions for the failure dump where Pl→Sg lost the head noun's gender
    (технических → технического for fem неполадок), gender flips drifted into
    case errors (взрывотехническую → animate-Acc взрывотехнического), and the
    handlers fired on pronominal adjectives (иного), participles (вызванного)
    and predicatives without an amod arc (нужно, должен).
    """

    def _number_handler(self):
        from synterr.languages.russian.errors.morphological import AdjNumberErrorHandler

        return AdjNumberErrorHandler()

    def _gender_handler(self):
        from synterr.languages.russian.errors.morphological import AdjGenderErrorHandler

        return AdjGenderErrorHandler()

    def _amod_pair(
        self,
        adj_text,
        adj_features,
        noun_text,
        noun_features,
        *,
        noun_parse=True,
    ):
        """adj --amod--> noun, mirroring the real stanza dep tree."""
        noun_extra = {}
        if noun_parse:
            noun_extra["pymorphy_parse"] = morph.parse(noun_text)[0]
        return [
            AnalyzedToken(
                text=adj_text,
                lemma=morph.parse(adj_text)[0].normal_form,
                pos="ADJ",
                features=adj_features,
                idx=0,
                dep_rel="amod",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse(adj_text)[0]},
            ),
            AnalyzedToken(
                text=noun_text,
                lemma=morph.parse(noun_text)[0].normal_form,
                pos="NOUN",
                features=noun_features,
                idx=1,
                dep_rel="obl",
                head_idx=None,
                extra=noun_extra,
            ),
        ]

    def test_pl_to_sg_takes_gender_from_head_noun(self):
        """технических неполадок → технической (fem from head), not the
        pymorphy-default masc технического. Plural nouns carry no UD Gender,
        so the gender comes from the head's pymorphy tag."""
        handler = self._number_handler()
        tokens = self._amod_pair(
            "технических",
            {"Case": "Gen", "Number": "Plur"},
            "неполадок",
            {"Case": "Gen", "Number": "Plur", "Animacy": "Inan"},
        )
        assert handler.can_apply(tokens, 0) is True

        sentence = ["технических", "неполадок"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "технической"
        assert result.fix_tag == "$TRANSFORM_NUMBER_Plur"

    def test_pl_to_sg_without_head_gender_skips(self):
        """No gender evidence on the head → skip (precision-first)."""
        handler = self._number_handler()
        tokens = self._amod_pair(
            "технических",
            {"Case": "Gen", "Number": "Plur"},
            "неполадок",
            {"Case": "Gen", "Number": "Plur"},
            noun_parse=False,
        )
        sentence = ["технических", "неполадок"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence == ["технических", "неполадок"]

    def test_pl_to_sg_without_dep_info_skips(self):
        """Without an amod head there is no gender source for Pl→Sg — skip."""
        handler = self._number_handler()
        tok = AnalyzedToken(
            text="красивые",
            lemma="красивый",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Plur"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("красивые")[0]},
        )
        sentence = ["красивые"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence == ["красивые"]

    def test_gender_change_preserves_accusative_case(self):
        """интересную (Acc fem) → интересный (inan Acc masc), not the
        animate-Acc/Gen интересного — case and animacy are pinned."""
        handler = self._gender_handler()
        handler.set_confusion_matrix({"gender": {"Fem": {"Masc": 1.0}}})
        tokens = self._amod_pair(
            "интересную",
            {"Case": "Acc", "Number": "Sing", "Gender": "Fem"},
            "книгу",
            {"Case": "Acc", "Number": "Sing", "Gender": "Fem", "Animacy": "Inan"},
        )
        assert handler.can_apply(tokens, 0) is True

        sentence = ["интересную", "книгу"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "интересный"
        assert result.fix_tag == "$TRANSFORM_GENDER_Fem"

    def test_gender_change_preserves_oblique_case(self):
        """невысокой (Ins fem) → невысоким (Ins masc), not the Dat drift
        невысокому produced by an unconstrained inflect."""
        handler = self._gender_handler()
        handler.set_confusion_matrix({"gender": {"Fem": {"Masc": 1.0}}})
        tokens = self._amod_pair(
            "невысокой",
            {"Case": "Ins", "Number": "Sing", "Gender": "Fem"},
            "доходностью",
            {"Case": "Ins", "Number": "Sing", "Gender": "Fem", "Animacy": "Inan"},
        )
        sentence = ["невысокой", "доходностью"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "невысоким"

    def test_number_change_preserves_accusative_animacy(self):
        """ручную гранату (Sg→Pl): → ручные (inan Acc), not ручных."""
        handler = self._number_handler()
        tokens = self._amod_pair(
            "ручную",
            {"Case": "Acc", "Number": "Sing", "Gender": "Fem"},
            "гранату",
            {"Case": "Acc", "Number": "Sing", "Gender": "Fem", "Animacy": "Inan"},
        )
        sentence = ["ручную", "гранату"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "ручные"

    def test_apro_pronominal_adjectives_skipped(self):
        """иного/данный parse as pymorphy Apro — flips read as lexical
        substitutions (иного → иной), not agreement errors."""
        number_handler = self._number_handler()
        gender_handler = self._gender_handler()

        # With dep info (amod arc present, guard still rejects on Apro)
        tokens = self._amod_pair(
            "иного",
            {"Case": "Gen", "Number": "Sing", "Gender": "Masc"},
            "плана",
            {"Case": "Gen", "Number": "Sing", "Gender": "Masc", "Animacy": "Inan"},
        )
        assert "Apro" in str(tokens[0].extra["pymorphy_parse"].tag)
        assert number_handler.can_apply(tokens, 0) is False
        assert gender_handler.can_apply(tokens, 0) is False

        # Without dep info the Apro guard still applies
        tok = AnalyzedToken(
            text="данный",
            lemma="данный",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("данный")[0]},
        )
        assert number_handler.can_apply([tok], 0) is False
        assert gender_handler.can_apply([tok], 0) is False

    def test_prtf_participle_skipped(self):
        """вызванного: stanza mistags the participle ADJ, pymorphy says PRTF
        — agreement is licensed by the verbal frame, skip."""
        number_handler = self._number_handler()
        gender_handler = self._gender_handler()
        tokens = self._amod_pair(
            "вызванного",
            {"Case": "Gen", "Number": "Sing", "Gender": "Masc"},
            "дождя",
            {"Case": "Gen", "Number": "Sing", "Gender": "Masc", "Animacy": "Inan"},
        )
        assert "PRTF" in str(tokens[0].extra["pymorphy_parse"].tag)
        assert number_handler.can_apply(tokens, 0) is False
        assert gender_handler.can_apply(tokens, 0) is False

    def test_prts_short_participle_skipped(self):
        """приговорены (PRTS): short participles inflect into non-words
        (убеждённы) — skip even without dep info."""
        handler = self._number_handler()
        tok = AnalyzedToken(
            text="приговорены",
            lemma="приговорить",
            pos="ADJ",
            features={"Number": "Plur", "Variant": "Short"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("приговорены")[0]},
        )
        assert handler.can_apply([tok], 0) is False

    def test_predicative_without_amod_arc_skipped(self):
        """With dep info present, no amod arc → skip: predicatives (нужно,
        должен) and substantivized idioms (пойти на попятную)."""
        number_handler = self._number_handler()
        gender_handler = self._gender_handler()
        for text, dep_rel in [
            ("нужно", "root"),
            ("должен", "root"),
            ("попятную", "obl"),
        ]:
            tok = AnalyzedToken(
                text=text,
                lemma=morph.parse(text)[0].normal_form,
                pos="ADJ",
                features={"Number": "Sing", "Gender": "Neut", "Case": "Acc"},
                idx=0,
                dep_rel=dep_rel,
                head_idx=None,
                extra={"pymorphy_parse": morph.parse(text)[0]},
            )
            assert number_handler.can_apply([tok], 0) is False, text
            assert gender_handler.can_apply([tok], 0) is False, text

    def test_amod_to_non_noun_head_skipped(self):
        """amod pointing at a non-NOUN head is not agreement evidence."""
        handler = self._gender_handler()
        adj = AnalyzedToken(
            text="красивая",
            lemma="красивый",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            idx=0,
            dep_rel="amod",
            head_idx=1,
            extra={"pymorphy_parse": morph.parse("красивая")[0]},
        )
        verb = AnalyzedToken(
            text="стоит",
            lemma="стоять",
            pos="VERB",
            features={"Tense": "Pres", "Number": "Sing"},
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={"pymorphy_parse": morph.parse("стоит")[0]},
        )
        assert handler.can_apply([adj, verb], 0) is False

    def test_without_dep_info_plain_adjective_still_fires(self):
        """No depparse → current behavior retained (plus Apro/PRTF guards)."""
        number_handler = self._number_handler()
        gender_handler = self._gender_handler()
        tok = AnalyzedToken(
            text="красивая",
            lemma="красивый",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Fem"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("красивая")[0]},
        )
        assert number_handler.can_apply([tok], 0) is True
        assert gender_handler.can_apply([tok], 0) is True

        sentence = ["красивая"]
        result = number_handler.apply([tok], sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "красивые"  # Sg→Pl needs no gender source

    def test_indeclinable_head_skips_number_but_not_gender(self):
        """эксклюзивном интервью: интервью is Fixd, both modifier numbers are
        correct → number flip is a non-error; a gender flip still is one."""
        number_handler = self._number_handler()
        gender_handler = self._gender_handler()
        tokens = self._amod_pair(
            "эксклюзивном",
            {"Case": "Loc", "Number": "Sing", "Gender": "Neut"},
            "интервью",
            {"Case": "Loc", "Number": "Sing", "Gender": "Neut", "Animacy": "Inan"},
        )
        assert number_handler.can_apply(tokens, 0) is False
        assert gender_handler.can_apply(tokens, 0) is True


class TestConfusionMatrixConfig:
    """Tests for confusion matrix config loading and pipeline wiring."""

    def test_generation_config_loads_confusion_matrices(self):
        """Test that GenerationConfig loads confusion_matrices from preset."""
        from synterr.core.pipeline import GenerationConfig

        config = GenerationConfig.from_preset("ru", "rulec")
        assert config.confusion_matrices is not None
        assert "case" in config.confusion_matrices
        assert "gender" in config.confusion_matrices
        assert "number" in config.confusion_matrices

        # Verify structure
        case_matrix = config.confusion_matrices["case"]
        assert "Nom" in case_matrix
        assert "Gen" in case_matrix["Nom"]

    def test_generation_config_without_confusion_matrices(self):
        """Test that GenerationConfig works without confusion_matrices."""
        from synterr.core.pipeline import GenerationConfig

        config = GenerationConfig()
        assert config.confusion_matrices is None

    def test_set_confusion_matrix_on_handlers(self):
        """Test that handlers accept and store confusion matrices."""
        from synterr.languages.russian.errors.morphological import (
            AdjCaseErrorHandler,
            AdjGenderErrorHandler,
            AdjNumberErrorHandler,
            NounCaseErrorHandler,
            VerbPersonNumberErrorHandler,
        )

        matrices = {
            "case": {"Nom": {"Gen": 1.0}},
            "gender": {"Masc": {"Fem": 1.0}},
            "number": {"Sing": {"Plur": 1.0}},
        }

        for cls in [
            NounCaseErrorHandler,
            AdjCaseErrorHandler,
            AdjGenderErrorHandler,
            AdjNumberErrorHandler,
            VerbPersonNumberErrorHandler,
        ]:
            handler = cls()
            assert hasattr(handler, "set_confusion_matrix")
            handler.set_confusion_matrix(matrices)
            assert handler._confusion_matrices is matrices


class TestSampleConfusedGrammeme:
    """Tests for the sample_confused_grammeme utility."""

    def test_returns_target_from_matrix(self):
        from synterr.languages.russian.inflector import sample_confused_grammeme

        rng = random.Random(42)
        matrix = {"Nom": {"Gen": 1.0}}
        result = sample_confused_grammeme("Nom", matrix, rng)
        assert result == "Gen"

    def test_returns_none_for_unknown_value(self):
        from synterr.languages.russian.inflector import sample_confused_grammeme

        rng = random.Random(42)
        matrix = {"Nom": {"Gen": 1.0}}
        result = sample_confused_grammeme("Unknown", matrix, rng)
        assert result is None

    def test_respects_weights(self):
        from synterr.languages.russian.inflector import sample_confused_grammeme

        # 99% Gen, 1% Dat — over many runs, Gen should dominate
        matrix = {"Nom": {"Gen": 0.99, "Dat": 0.01}}
        gen_count = 0
        for seed in range(500):
            rng = random.Random(seed)
            result = sample_confused_grammeme("Nom", matrix, rng)
            if result == "Gen":
                gen_count += 1
        ratio = gen_count / 500
        assert ratio > 0.90, f"Expected ~99% Gen, got {ratio:.2%}"


def _verb_tense_handler():
    from synterr.languages.russian.errors.morphological import VerbTenseErrorHandler

    return VerbTenseErrorHandler()


def _anchor_token(text: str, idx: int, head_idx: int) -> AnalyzedToken:
    """Deictic temporal adverb attached to the verb (verb_tense anchor)."""
    return AnalyzedToken(
        text=text,
        lemma=text,
        pos="ADV",
        features={},
        idx=idx,
        dep_rel="advmod",
        head_idx=head_idx,
    )


class TestVerbTensePreservesAgreement:
    """verb_tense must keep person/number/gender across the tense change.

    Regression for the bug where inflect({'futr'}) defaulted to 1st person:
    "Он прочитал" → "Он прочитаю" instead of "прочитает".
    """

    def test_past_to_future_keeps_3rd_person_singular(self):
        handler = _verb_tense_handler()
        # перфектив: present unreachable, so future is the only target.
        verb_parse = morph.parse("прочитал")[0]  # Past Masc Sing
        tokens = [
            AnalyzedToken(
                text="Он",
                lemma="он",
                pos="PRON",
                features={"Number": "Sing", "Person": "3", "Gender": "Masc"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("он")[0]},
            ),
            AnalyzedToken(
                text="прочитал",
                lemma="прочитать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=1,
                dep_rel="root",
                head_idx=1,
                extra={"pymorphy_parse": verb_parse},
            ),
            _anchor_token("вчера", 2, 1),
        ]
        sentence = ["Он", "прочитал", "вчера"]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[1] == "прочитает"  # 3rd person sing, NOT "прочитаю"

    def test_past_to_future_keeps_3rd_person_plural(self):
        handler = _verb_tense_handler()
        verb_parse = morph.parse("прочитали")[0]  # Past Plur
        tokens = [
            AnalyzedToken(
                text="Они",
                lemma="они",
                pos="PRON",
                features={"Number": "Plur", "Person": "3"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("они")[0]},
            ),
            AnalyzedToken(
                text="прочитали",
                lemma="прочитать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Plur"},
                idx=1,
                dep_rel="root",
                head_idx=1,
                extra={"pymorphy_parse": verb_parse},
            ),
            _anchor_token("вчера", 2, 1),
        ]
        sentence = ["Они", "прочитали", "вчера"]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[1] == "прочитают"  # NOT "прочитаем"

    def test_present_to_past_keeps_feminine_gender(self):
        handler = _verb_tense_handler()
        # имперфектив: future is periphrastic (unreachable), so past is the only
        # candidate that inflects — and it must keep feminine gender.
        verb_parse = morph.parse("читает")[0]  # Pres 3 Sing
        tokens = [
            AnalyzedToken(
                text="Она",
                lemma="она",
                pos="PRON",
                features={"Number": "Sing", "Person": "3", "Gender": "Fem"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("она")[0]},
            ),
            AnalyzedToken(
                text="читает",
                lemma="читать",
                pos="VERB",
                features={"Tense": "Pres", "Number": "Sing", "Person": "3"},
                idx=1,
                dep_rel="root",
                head_idx=1,
                extra={"pymorphy_parse": verb_parse},
            ),
            # завтра licenses {futr, pres} ("Завтра она читает доклад" is a
            # correct scheduled present) — past is the only error target.
            _anchor_token("завтра", 2, 1),
        ]
        for seed in range(10):
            sentence = ["Она", "читает", "завтра"]
            result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(seed))
            assert result is not None
            assert sentence[1] == "читала"  # feminine, NOT masculine "читал"

    def test_perfective_past_does_not_no_op(self):
        """morph-2: perfective verb can't go present, but future must fire."""
        handler = _verb_tense_handler()
        verb_parse = morph.parse("написал")[0]  # Past Masc Sing, perfective
        tokens = [
            AnalyzedToken(
                text="написал",
                lemma="написать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=0,
                dep_rel="root",
                head_idx=0,
                extra={"pymorphy_parse": verb_parse},
            ),
            _anchor_token("вчера", 1, 0),
        ]
        for seed in range(10):
            sentence = ["написал", "вчера"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(seed))
            assert result is not None  # never None despite unreachable present
            assert sentence[0] == "напишет"


class TestVerbTenseFiniteOnly:
    """verb_tense must not fire on participles (annotation pass).

    Stanza tags participles VERB with a Tense feature, but flipping them into
    finite forms destroys voice: сообщено → сообщит, уволившийся → уволится.
    Only VerbForm=Fin (or absent) may fire.
    """

    def test_short_passive_participle_does_not_fire(self):
        handler = _verb_tense_handler()
        tokens = [
            _anchor_token("Вчера", 0, 1),
            AnalyzedToken(
                text="сообщено",
                lemma="сообщить",
                pos="VERB",
                features={
                    "Tense": "Past",
                    "VerbForm": "Part",
                    "Voice": "Pass",
                    "Number": "Sing",
                    "Gender": "Neut",
                },
                idx=1,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("сообщено")[0]},
            ),
        ]
        assert handler.can_apply(tokens, 1) is False

        sentence = ["Вчера", "сообщено"]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence == ["Вчера", "сообщено"]

    def test_finite_past_verb_still_fires(self):
        """Explicit VerbForm=Fin must not be caught by the participle guard."""
        handler = _verb_tense_handler()
        tokens = [
            AnalyzedToken(
                text="написал",
                lemma="написать",
                pos="VERB",
                features={
                    "Tense": "Past",
                    "VerbForm": "Fin",
                    "Number": "Sing",
                    "Gender": "Masc",
                },
                idx=0,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("написал")[0]},
            ),
            _anchor_token("вчера", 1, 0),
        ]
        assert handler.can_apply(tokens, 0) is True

        sentence = ["написал", "вчера"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "напишет"


class TestNounNumberRequiresAgreementEvidence:
    """noun_number must not flip number without an agreeing word as evidence.

    Regression for the audit finding where "Я купил книгу ." → "Я купил
    книги ." (fully correct Russian, unrecoverable non-error) fired every run.
    """

    def _handler(self):
        from synterr.languages.russian.errors.morphological import (
            NounNumberErrorHandler,
        )

        return NounNumberErrorHandler()

    def _kupil_tokens(self, det_text: str | None = None):
        """Я купил [det] книгу — mirrors the real stanza dep tree."""
        tokens = [
            AnalyzedToken(
                text="Я",
                lemma="я",
                pos="PRON",
                features={"Case": "Nom", "Number": "Sing", "Person": "1"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="купил",
                lemma="купить",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=1,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("купил")[0]},
            ),
        ]
        noun_idx = 2
        if det_text is not None:
            noun_idx = 3
            tokens.append(
                AnalyzedToken(
                    text=det_text,
                    lemma=det_text,
                    pos="DET",
                    features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                    idx=2,
                    dep_rel="det",
                    head_idx=noun_idx,
                )
            )
        tokens.append(
            AnalyzedToken(
                text="книгу",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=noun_idx,
                dep_rel="obj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("книгу")[0]},
            )
        )
        return tokens, noun_idx

    def test_bare_object_does_not_fire(self):
        """'Я купил книгу' → 'Я купил книги' is correct Russian — skip."""
        handler = self._handler()
        tokens, noun_idx = self._kupil_tokens()
        assert handler.can_apply(tokens, noun_idx) is False

    def test_det_evidence_fires_and_det_stays(self):
        handler = self._handler()
        tokens, noun_idx = self._kupil_tokens(det_text="эту")
        assert handler.can_apply(tokens, noun_idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, noun_idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[noun_idx] == "книги"  # "эту книги" — recoverable error
        assert sentence[2] == "эту"  # the agreeing det is the evidence

    def test_invariant_possessive_is_not_evidence(self):
        """'его книгу' → 'его книги' is correct (его reflects the possessor)."""
        handler = self._handler()
        tokens, noun_idx = self._kupil_tokens(det_text="его")
        assert handler.can_apply(tokens, noun_idx) is False

    def test_nummod_is_evidence(self):
        handler = self._handler()
        tokens = [
            AnalyzedToken(
                text="пять",
                lemma="пять",
                pos="NUM",
                features={"Case": "Nom"},
                idx=0,
                dep_rel="nummod:gov",
                head_idx=1,
            ),
            AnalyzedToken(
                text="книг",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Gen", "Gender": "Fem", "Number": "Plur"},
                idx=1,
                dep_rel="obj",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("книг")[0]},
            ),
        ]
        assert handler.can_apply(tokens, 1) is True

    def test_subject_with_verbal_predicate_fires(self):
        handler = self._handler()
        tokens = [
            AnalyzedToken(
                text="Книга",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("книга")[0]},
            ),
            AnalyzedToken(
                text="лежит",
                lemma="лежать",
                pos="VERB",
                features={"Tense": "Pres", "Number": "Sing", "Person": "3"},
                idx=1,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("лежит")[0]},
            ),
        ]
        assert handler.can_apply(tokens, 0) is True

        sentence = ["Книга", "лежит"]
        result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence == ["Книги", "лежит"]  # number-marked verb = evidence

    def test_subject_with_nominal_predicate_does_not_fire(self):
        """'Книги — лучший подарок' is correct: nominal predicates need not agree."""
        handler = self._handler()
        tokens = [
            AnalyzedToken(
                text="Книги",
                lemma="книга",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Plur"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("книги")[0]},
            ),
            AnalyzedToken(
                text="подарок",
                lemma="подарок",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=1,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("подарок")[0]},
            ),
        ]
        assert handler.can_apply(tokens, 0) is False
        assert handler.can_apply(tokens, 1) is False

    def test_without_depparse_does_not_fire(self):
        """No dep info → no agreement evidence → never fire."""
        handler = self._handler()
        tok = AnalyzedToken(
            text="книгу",
            lemma="книга",
            pos="NOUN",
            features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("книгу")[0]},
        )
        assert handler.can_apply([tok], 0) is False

    @pytest.mark.slow
    def test_real_backend_bare_object_skipped(self):
        handler = self._handler()
        tokens = _stanza_backend().analyze("Я купил книгу.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "книгу")
        assert handler.can_apply(tokens, idx) is False

    @pytest.mark.slow
    def test_real_backend_det_evidence_fires(self):
        handler = self._handler()
        tokens = _stanza_backend().analyze("Я купил эту книгу.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "книгу")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "книги"
        assert "эту" in sentence


class TestVerbTenseRequiresTemporalAnchor:
    """verb_tense must not flip tense without a deictic temporal anchor.

    Regression for the audit finding where "Мама мыла раму ." → "Мама моет
    раму ." and "Он был дома ." → "Он будет дома ." — grammatical sentences
    with a different meaning (non-errors).
    """

    def _myla_tokens(self):
        return [
            AnalyzedToken(
                text="Мама",
                lemma="мама",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("мама")[0]},
            ),
            AnalyzedToken(
                text="мыла",
                lemma="мыть",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Fem"},
                idx=1,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("мыла")[0]},
            ),
        ]

    def test_no_anchor_does_not_fire(self):
        handler = _verb_tense_handler()
        tokens = self._myla_tokens()
        assert handler.can_apply(tokens, 1) is False

        sentence = ["Мама", "мыла"]
        result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence == ["Мама", "мыла"]

    def test_copula_without_anchor_does_not_fire(self):
        """'Он был дома' → 'Он будет дома' is a meaning change, not an error."""
        handler = _verb_tense_handler()
        tokens = [
            AnalyzedToken(
                text="Он",
                lemma="он",
                pos="PRON",
                features={"Number": "Sing", "Person": "3", "Gender": "Masc"},
                idx=0,
                dep_rel="nsubj",
                head_idx=2,
            ),
            AnalyzedToken(
                text="был",
                lemma="быть",
                pos="AUX",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=1,
                dep_rel="cop",
                head_idx=2,
                extra={"pymorphy_parse": morph.parse("был")[0]},
            ),
            AnalyzedToken(
                text="дома",
                lemma="дома",
                pos="ADV",
                features={},
                idx=2,
                dep_rel="root",
                head_idx=None,
            ),
        ]
        assert handler.can_apply(tokens, 1) is False
        result = handler.apply(
            tokens, ["Он", "был", "дома"], 1, set(), rng=random.Random(0)
        )
        assert result is None

    def test_anchor_on_copula_head_fires(self):
        """'Вчера он был дома': вчера attaches to дома (root), был is cop."""
        handler = _verb_tense_handler()
        tokens = [
            _anchor_token("Вчера", 0, 3),
            AnalyzedToken(
                text="он",
                lemma="он",
                pos="PRON",
                features={"Number": "Sing", "Person": "3", "Gender": "Masc"},
                idx=1,
                dep_rel="nsubj",
                head_idx=3,
            ),
            AnalyzedToken(
                text="был",
                lemma="быть",
                pos="AUX",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=2,
                dep_rel="cop",
                head_idx=3,
                extra={"pymorphy_parse": morph.parse("был")[0]},
            ),
            AnalyzedToken(
                text="дома",
                lemma="дома",
                pos="ADV",
                features={},
                idx=3,
                dep_rel="root",
                head_idx=None,
            ),
        ]
        assert handler.can_apply(tokens, 2) is True

        sentence = ["Вчера", "он", "был", "дома"]
        result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[2] == "будет"  # "Вчера он будет дома" — real error

    def test_anchor_never_yields_licensed_tense(self):
        """Past anchor licenses pres (praesens historicum): imperfective past
        has no synthetic future, so with вчера the handler must emit nothing
        rather than the licensed 'Вчера он читает'."""
        handler = _verb_tense_handler()
        tokens = [
            _anchor_token("Вчера", 0, 2),
            AnalyzedToken(
                text="он",
                lemma="он",
                pos="PRON",
                features={"Number": "Sing", "Person": "3", "Gender": "Masc"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
            ),
            AnalyzedToken(
                text="читал",
                lemma="читать",
                pos="VERB",
                features={"Tense": "Past", "Number": "Sing", "Gender": "Masc"},
                idx=2,
                dep_rel="root",
                head_idx=None,
                extra={"pymorphy_parse": morph.parse("читал")[0]},
            ),
        ]
        for seed in range(10):
            sentence = ["Вчера", "он", "читал"]
            result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(seed))
            assert result is None
            assert sentence == ["Вчера", "он", "читал"]

    @pytest.mark.slow
    def test_real_backend_no_anchor_skipped(self):
        handler = _verb_tense_handler()
        tokens = _stanza_backend().analyze("Мама мыла раму.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "мыла")
        assert handler.can_apply(tokens, idx) is False

    @pytest.mark.slow
    def test_real_backend_anchor_fires(self):
        handler = _verb_tense_handler()
        tokens = _stanza_backend().analyze("Он написал письмо вчера.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "написал")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "напишет"  # "напишет письмо вчера" — real error


class TestNumeralDeclensionGeneralCardinals:
    """numeral_declension fires on oblique general cardinals, not only полтора.

    Regression for the bug where can_apply gated solely on _POLTORA_LOOKUP,
    so general cardinals (пятьдесят/двести/триста…) never fired.
    """

    def _handler(self):
        from synterr.languages.russian.errors.morphological import (
            NumeralDeclensionHandler,
        )

        return NumeralDeclensionHandler()

    def _cardinal_token(self, text, case):
        return AnalyzedToken(
            text=text,
            lemma=text,
            pos="NUM",
            features={"Case": case, "NumType": "Card"},
            idx=0,
            dep_rel="nummod",
            head_idx=1,
            extra={"pymorphy_parse": morph.parse(text)[0]},
        )

    def test_oblique_cardinal_can_apply(self):
        handler = self._handler()
        for text, case in [
            ("пятидесяти", "Loc"),
            ("трёхсот", "Gen"),
            ("двумястами", "Ins"),
            ("пятистам", "Dat"),
        ]:
            tok = self._cardinal_token(text, case)
            assert handler.can_apply([tok], 0) is True, text

    def test_oblique_cardinal_loses_declension(self):
        handler = self._handler()
        tok = self._cardinal_token("пятидесяти", "Loc")
        sentence = ["пятидесяти"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[0] == "пятьдесят"  # citation form, fails to decline
        assert result.error_type == "numeral_declension_numeral_declension"

    def test_nominative_cardinal_does_not_fire(self):
        """A Nom/Acc cardinal governing genitive is correct — no error."""
        handler = self._handler()
        tok = self._cardinal_token("пятьдесят", "Acc")
        assert handler.can_apply([tok], 0) is False

    def test_non_numeral_parse_does_not_fire(self):
        """Guard: oblique-cased token whose pymorphy parse is not NUMR is skipped.

        "сто" parses as a NOUN, so even in an oblique slot it must not be
        treated as a declinable cardinal here.
        """
        handler = self._handler()
        tok = self._cardinal_token("сто", "Gen")
        assert handler.can_apply([tok], 0) is False

    def test_poltora_family_still_works(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="полутора",
            lemma="полтора",
            pos="NUM",
            features={"Case": "Gen"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("полутора")[0]},
        )
        sentence = ["полутора"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[0] in {"полтора", "полторы"}
        assert result.error_type == "numeral_declension_numeral_poltora"

    def _polutora_with_noun(self, noun_text, noun_lemma, gender):
        features = {"Case": "Gen", "Number": "Plur"}
        if gender is not None:
            features["Gender"] = gender
        return [
            AnalyzedToken(
                text="полутора",
                lemma="полтора",
                pos="NUM",
                features={"Case": "Gen"},
                idx=0,
                dep_rel="nummod",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse("полутора")[0]},
            ),
            AnalyzedToken(
                text=noun_text,
                lemma=noun_lemma,
                pos="NOUN",
                features=features,
                idx=1,
                dep_rel="obl",
                head_idx=1,
                extra={"pymorphy_parse": morph.parse(noun_text)[0]},
            ),
        ]

    def test_polutora_masc_noun_yields_poltora(self):
        """полутора часов → полтора (masc head noun selects the masc citation
        form). Regression: the old lemma-keyed lookup always emitted полторы."""
        handler = self._handler()
        for seed in range(5):
            tokens = self._polutora_with_noun("часов", "час", "Masc")
            sentence = ["полутора", "часов"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(seed))
            assert result is not None
            assert sentence[0] == "полтора", f"seed {seed}"
            assert result.error_type == "numeral_declension_numeral_poltora"

    def test_polutora_fem_noun_yields_poltory(self):
        """полутора минут → полторы (fem head noun)."""
        handler = self._handler()
        for seed in range(5):
            tokens = self._polutora_with_noun("минут", "минута", "Fem")
            sentence = ["полутора", "минут"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(seed))
            assert result is not None
            assert sentence[0] == "полторы", f"seed {seed}"

    def test_polutora_no_gender_reaches_both_forms(self):
        """Pluralia tantum (суток) carry no gender → random, both reachable."""
        handler = self._handler()
        seen = set()
        for seed in range(20):
            tokens = self._polutora_with_noun("суток", "сутки", None)
            sentence = ["полутора", "суток"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(seed))
            assert result is not None
            seen.add(sentence[0])
        assert seen == {"полтора", "полторы"}

    def test_poltorasta_gets_poltora_subtype(self):
        """§164 groups полтораста with полтора — subtype must be numeral_poltora."""
        handler = self._handler()
        tok = AnalyzedToken(
            text="полутораста",
            lemma="полтораста",
            pos="NUM",
            features={"Case": "Loc"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("полутораста")[0]},
        )
        sentence = ["полутораста"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))

        assert result is not None
        assert sentence[0] == "полтораста"
        assert result.error_type == "numeral_declension_numeral_poltora"

    def test_distributive_po_dative_does_not_fire(self):
        """§164: по пяти раз has the permitted variant по пять раз — skip."""
        handler = self._handler()
        po = AnalyzedToken(
            text="по",
            lemma="по",
            pos="ADP",
            features={},
            idx=0,
            dep_rel="case",
            head_idx=2,
        )
        num = AnalyzedToken(
            text="пяти",
            lemma="пять",
            pos="NUM",
            features={"Case": "Dat", "NumType": "Card"},
            idx=1,
            dep_rel="nummod",
            head_idx=2,
            extra={"pymorphy_parse": morph.parse("пяти")[0]},
        )
        noun = AnalyzedToken(
            text="яблок",
            lemma="яблоко",
            pos="NOUN",
            features={"Case": "Gen", "Number": "Plur"},
            idx=2,
            dep_rel="obj",
            head_idx=2,
            extra={"pymorphy_parse": morph.parse("яблок")[0]},
        )
        tokens = [po, num, noun]
        assert handler.can_apply(tokens, 1) is False
        sentence = ["по", "пяти", "яблок"]
        assert handler.apply(tokens, sentence, 1, set(), rng=random.Random(0)) is None

    def test_non_distributive_dative_still_fires(self):
        """Dat without по keeps firing (к пятистам метрам → к пятьсот)."""
        handler = self._handler()
        k = AnalyzedToken(
            text="к",
            lemma="к",
            pos="ADP",
            features={},
            idx=0,
            dep_rel="case",
            head_idx=2,
        )
        num = AnalyzedToken(
            text="пятистам",
            lemma="пятьсот",
            pos="NUM",
            features={"Case": "Dat", "NumType": "Card"},
            idx=1,
            dep_rel="nummod",
            head_idx=2,
            extra={"pymorphy_parse": morph.parse("пятистам")[0]},
        )
        noun = AnalyzedToken(
            text="метрам",
            lemma="метр",
            pos="NOUN",
            features={"Case": "Dat", "Number": "Plur"},
            idx=2,
            dep_rel="obl",
            head_idx=2,
            extra={"pymorphy_parse": morph.parse("метрам")[0]},
        )
        assert handler.can_apply([k, num, noun], 1) is True


_STANZA_BACKEND = None


def _stanza_backend():
    """Cached real stanza backend with dep parsing (slow to build once)."""
    global _STANZA_BACKEND
    if _STANZA_BACKEND is None:
        from synterr.languages.russian.backends.stanza_backend import StanzaBackend

        _STANZA_BACKEND = StanzaBackend(use_depparse=True, use_gpu=False)
    return _STANZA_BACKEND


class TestNounCasePrepErrorHandler:
    """noun_case_prep_e_u: second locative (-у) → standard locative (-е)."""

    def _handler(self):
        from synterr.languages.russian.errors.morphological import (
            NounCasePrepErrorHandler,
        )

        return NounCasePrepErrorHandler()

    def test_protocol(self):
        handler = self._handler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "noun_case_prep"
        assert handler.subtypes == ["noun_case_prep_e_u"]
        assert handler.category == "MORPH"
        assert handler.changes_length is False

    def test_rejects_non_locative(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="лесу",
            lemma="лес",
            pos="NOUN",
            features={"Case": "Dat"},
            idx=1,
            extra={"pymorphy_parse": morph.parse("лесу")[0]},
        )
        prep = AnalyzedToken(text="к", lemma="к", pos="ADP", features={}, idx=0)
        assert handler.can_apply([prep, tok], 1) is False

    def test_rejects_without_preceding_prep(self):
        handler = self._handler()
        # loc2 noun but no preceding в/на
        loc2 = next(p for p in morph.parse("лесу") if "loc2" in str(p.tag))
        tok = AnalyzedToken(
            text="лесу",
            lemma="лес",
            pos="NOUN",
            features={"Case": "Loc"},
            idx=0,
            extra={"pymorphy_parse": loc2},
        )
        assert handler.can_apply([tok], 0) is False

    def test_rejects_stoplist_lemma(self):
        handler = self._handler()
        loc2 = next(p for p in morph.parse("цехе") if "loct" in str(p.tag))
        # use a genuine loc2 word from stoplist
        cex = next(p for p in morph.parse("цеху") if "loc2" in str(p.tag))
        prep = AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0)
        tok = AnalyzedToken(
            text="цеху",
            lemma="цех",
            pos="NOUN",
            features={"Case": "Loc"},
            idx=1,
            extra={"pymorphy_parse": cex},
        )
        assert handler.can_apply([prep, tok], 1) is False
        assert loc2 is not None  # sanity

    def test_rejects_e_acceptable_lemmas(self):
        """-е locative is standard/acceptable for мозг, аэропорт, ряд, сок...
        (в мозге, в аэропорте, в ряде случаев) — corruption is a non-error."""
        handler = self._handler()
        prep = AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0)
        for text, lemma in [
            ("мозгу", "мозг"),
            ("аэропорту", "аэропорт"),
            ("ряду", "ряд"),
            ("соку", "сок"),
        ]:
            parse = next((p for p in morph.parse(text) if "loc2" in str(p.tag)), None)
            assert parse is not None, f"no loc2 parse for {text}"
            tok = AnalyzedToken(
                text=text,
                lemma=lemma,
                pos="NOUN",
                features={"Case": "Loc"},
                idx=1,
                extra={"pymorphy_parse": parse},
            )
            assert handler.can_apply([prep, tok], 1) is False, lemma

    @pytest.mark.slow
    def test_real_backend_v_lesu(self):
        handler = self._handler()
        tokens = _stanza_backend().analyze("Мы заблудились в лесу.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "лесу")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "лесе"
        assert result.error_type == "noun_case_prep_e_u"
        assert result.fix_tag == "$REPLACE_лесу"


class TestAdjFormErrorHandler:
    """adj_short_full: predicative short adjective → full nominative form."""

    def _handler(self):
        from synterr.languages.russian.errors.morphological import AdjFormErrorHandler

        return AdjFormErrorHandler()

    def test_protocol(self):
        handler = self._handler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "adj_form"
        assert handler.subtypes == ["adj_short_full"]
        assert handler.category == "MORPH"
        assert handler.changes_length is False

    def _sposoben_token(self, dep_rel="advcl"):
        parse = next(p for p in morph.parse("способен") if "ADJS" in str(p.tag))
        return AnalyzedToken(
            text="способен",
            lemma="способный",
            pos="ADJ",
            features={"Variant": "Short", "Gender": "Masc", "Number": "Sing"},
            idx=0,
            dep_rel=dep_rel,
            extra={"pymorphy_parse": parse},
        )

    def test_government_lemma_fallback_requires_complement(self):
        """§159: without a governed complement the full form is correct —
        the lemma fallback must not fire ('Он очень способный' is fine)."""
        handler = self._handler()
        tok = self._sposoben_token()
        assert handler.can_apply([tok], 0) is False

    def test_government_lemma_fallback_applies_with_complement(self):
        handler = self._handler()
        tok = self._sposoben_token()
        complement = AnalyzedToken(
            text="музыке",
            lemma="музыка",
            pos="NOUN",
            features={"Case": "Dat"},
            idx=1,
            dep_rel="obl",
            head_idx=0,
            extra={"pymorphy_parse": morph.parse("музыке")[0]},
        )
        assert handler.can_apply([tok, complement], 0) is True

    def test_xcomp_infinitive_counts_as_complement(self):
        """'должен уйти': the infinitive is governed, full form cannot take it."""
        handler = self._handler()
        parse = next(p for p in morph.parse("должен") if "ADJS" in str(p.tag))
        tok = AnalyzedToken(
            text="должен",
            lemma="должный",
            pos="ADJ",
            features={"Variant": "Short", "Gender": "Masc", "Number": "Sing"},
            idx=0,
            dep_rel="root",
            extra={"pymorphy_parse": parse},
        )
        inf = AnalyzedToken(
            text="уйти",
            lemma="уйти",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=1,
            dep_rel="xcomp",
            head_idx=0,
            extra={"pymorphy_parse": morph.parse("уйти")[0]},
        )
        assert handler.can_apply([tok, inf], 0) is True

    def test_bare_predicate_without_complement_does_not_fire(self):
        """Root short adjective with no complement → stylistic choice, skip."""
        handler = self._handler()
        parse = next(p for p in morph.parse("готовы") if "ADJS" in str(p.tag))
        tok = AnalyzedToken(
            text="готовы",
            lemma="готовый",
            pos="ADJ",
            features={"Variant": "Short", "Number": "Plur"},
            idx=0,
            dep_rel="root",
            extra={"pymorphy_parse": parse},
        )
        assert handler.can_apply([tok], 0) is False

    def test_rejects_full_adjective(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="готовый",
            lemma="готовый",
            pos="ADJ",
            features={"Case": "Nom", "Number": "Sing", "Gender": "Masc"},
            idx=0,
            dep_rel="amod",
            extra={"pymorphy_parse": morph.parse("готовый")[0]},
        )
        assert handler.can_apply([tok], 0) is False

    def test_apply_short_to_full(self):
        handler = self._handler()
        parse = next(p for p in morph.parse("готовы") if "ADJS" in str(p.tag))
        tok = AnalyzedToken(
            text="готовы",
            lemma="готовый",
            pos="ADJ",
            features={"Variant": "Short", "Number": "Plur"},
            idx=0,
            dep_rel="root",
            extra={"pymorphy_parse": parse},
        )
        sentence = ["готовы"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[0] == "готовые"
        assert result.error_type == "adj_short_full"
        assert result.fix_tag == "$REPLACE_готовы"

    @pytest.mark.slow
    def test_real_backend_gotovy(self):
        handler = self._handler()
        tokens = _stanza_backend().analyze("Мы готовы к отъезду.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "готовы")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "готовые"
        assert " ".join(sentence) == "Мы готовые к отъезду ."


class TestDoubleComparativeHandler:
    """adj_double_comparative: insert pleonastic «более» before a comparative."""

    def _handler(self):
        from synterr.languages.russian.errors.morphological import (
            DoubleComparativeHandler,
        )

        return DoubleComparativeHandler()

    def test_protocol(self):
        handler = self._handler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "adj_double_comparative"
        assert handler.subtypes == ["adj_double_comparative"]
        assert handler.category == "MORPH"
        assert handler.changes_length is True

    def test_can_apply_comparative(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="интереснее",
            lemma="интересный",
            pos="ADJ",
            features={"Degree": "Cmp"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("интереснее")[0]},
        )
        assert handler.can_apply([tok], 0) is True

    def test_rejects_when_preceded_by_bolee(self):
        handler = self._handler()
        bolee = AnalyzedToken(
            text="более", lemma="более", pos="ADV", features={}, idx=0
        )
        comp = AnalyzedToken(
            text="интереснее",
            lemma="интересный",
            pos="ADJ",
            features={"Degree": "Cmp"},
            idx=1,
            extra={"pymorphy_parse": morph.parse("интереснее")[0]},
        )
        assert handler.can_apply([bolee, comp], 1) is False

    def test_rejects_non_comparative(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="интересный",
            lemma="интересный",
            pos="ADJ",
            features={"Degree": "Pos"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("интересный")[0]},
        )
        assert handler.can_apply([tok], 0) is False

    def test_apply_inserts_bolee(self):
        handler = self._handler()
        tok = AnalyzedToken(
            text="интереснее",
            lemma="интересный",
            pos="ADJ",
            features={"Degree": "Cmp"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("интереснее")[0]},
        )
        sentence = ["интереснее"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert sentence == ["более", "интереснее"]
        assert result.error_type == "adj_double_comparative"
        assert result.fix_tag == "$DELETE"

    def test_apply_skips_capitalized_comparative(self):
        # Artem's M1.3 report: «Раньше → более Раньше» read unnaturally, and
        # a capitalization transfer would break the single-$DELETE fix — skip
        handler = self._handler()
        tok = AnalyzedToken(
            text="Раньше",
            lemma="рано",
            pos="ADV",
            features={"Degree": "Cmp"},
            idx=0,
            extra={"pymorphy_parse": morph.parse("Раньше")[0]},
        )
        sentence = ["Раньше"]
        result = handler.apply([tok], sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence == ["Раньше"]

    @pytest.mark.slow
    def test_real_backend_interesnee(self):
        handler = self._handler()
        tokens = _stanza_backend().analyze("Эти опыты были интереснее.")
        idx = next(i for i, t in enumerate(tokens) if t.text == "интереснее")
        assert handler.can_apply(tokens, idx) is True

        sentence = [t.text for t in tokens]
        result = handler.apply(tokens, sentence, idx, set(), rng=random.Random(0))
        assert result is not None
        assert sentence[idx] == "более"
        assert sentence[idx + 1] == "интереснее"
        assert " ".join(sentence) == "Эти опыты были более интереснее ."
