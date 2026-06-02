from __future__ import annotations

import random

import pymorphy3

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
        ]

        # Noun handler should only apply to nouns
        assert noun_handler.can_apply(tokens, 0) is True
        assert noun_handler.can_apply(tokens, 1) is False
        assert noun_handler.can_apply(tokens, 2) is False

        # Adj handler should only apply to adjectives
        assert adj_handler.can_apply(tokens, 0) is False
        assert adj_handler.can_apply(tokens, 1) is True
        assert adj_handler.can_apply(tokens, 2) is False

        # Verb handler should only apply to verbs
        assert verb_handler.can_apply(tokens, 0) is False
        assert verb_handler.can_apply(tokens, 1) is False
        assert verb_handler.can_apply(tokens, 2) is True

    def test_noun_case_requires_governed_deprel(self):
        """NounCaseErrorHandler only targets governed positions (obl/nmod/iobj/obj)."""
        from synterr.languages.russian.errors.morphological import NounCaseErrorHandler

        handler = NounCaseErrorHandler()
        base = dict(
            lemma="книга",
            pos="NOUN",
            features={"Case": "Nom"},
            extra={"pymorphy_parse": "mock"},
        )

        # Governed dep_rels → should apply
        for dep_rel in ("obl", "nmod", "iobj", "obj"):
            token = AnalyzedToken(text="книга", idx=0, dep_rel=dep_rel, **base)
            assert handler.can_apply([token], 0) is True, f"should apply for {dep_rel}"

        # Non-governed dep_rels → should NOT apply
        for dep_rel in ("nsubj", "conj", "root", "appos", None):
            token = AnalyzedToken(text="книга", idx=0, dep_rel=dep_rel, **base)
            assert handler.can_apply([token], 0) is False, f"should reject {dep_rel}"


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

    def test_verb_person_number_without_dep_tree(self):
        """Test VerbPersonNumberErrorHandler works without dep tree info."""
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
        result = handler.apply(tokens, sentence, 0, modified, rng=rng)

        assert result is not None
        # No nsubj, uses own number (Sing) → target Plur
        assert sentence[0] == "читали"


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
        ]
        sentence = ["Он", "прочитал"]
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
        ]
        sentence = ["Они", "прочитали"]
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
        ]
        for seed in range(10):
            sentence = ["Она", "читает"]
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
        ]
        for seed in range(10):
            sentence = ["написал"]
            result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(seed))
            assert result is not None  # never None despite unreachable present
            assert sentence[0] == "напишет"


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
