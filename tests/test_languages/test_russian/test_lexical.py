import random

import pymorphy3

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.lexical import (
    ConjunctionErrorHandler,
    ParonymErrorHandler,
    PrepositionErrorHandler,
    PronounNFormErrorHandler,
    PronounSebyaErrorHandler,
    PronounSvoyErrorHandler,
    _is_sebya_set_phrase,
)
from synterr.languages.russian.resources import get_preposition_list


class TestParonymErrorHandler:
    morph = pymorphy3.MorphAnalyzer()
    handler = ParonymErrorHandler()

    def test_implements_protocol(self):
        """Test ParonymErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "paronym"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_can_apply_finds_paronyms(self):
        """Test ParonymErrorHandler finds paronyms correctly."""
        tokens = [
            AnalyzedToken(
                text="надеть", lemma="надеть", pos="VERB", features={}, idx=0
            ),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(
                text="технического", lemma="технический", pos="ADJF", features={}, idx=3
            ),
        ]

        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is False
        assert self.handler.can_apply(tokens, 2) is False
        assert self.handler.can_apply(tokens, 3) is True

    def test_apply_substitutes_correctly(self):
        """Test ParonymErrorHandler substitutes paronyms correctly."""
        tokens = [
            AnalyzedToken(
                text="надеть",
                lemma="надеть",
                pos="VERB",
                features={},
                idx=0,
                extra={"pymorphy_parse": self.morph.parse("надеть")[0]},
            ),
            AnalyzedToken(
                text=".",
                lemma=".",
                pos="PUNCT",
                features={},
                idx=1,
                extra={"pymorphy_parse": self.morph.parse(".")[0]},
            ),
            AnalyzedToken(
                text="вопрос",
                lemma="вопрос",
                pos="NOUN",
                features={},
                idx=2,
                extra={"pymorphy_parse": self.morph.parse("вопрос")[0]},
            ),
            AnalyzedToken(
                text="технического",
                lemma="технический",
                pos="ADJF",
                features={},
                idx=3,
                extra={"pymorphy_parse": self.morph.parse("технического")[0]},
            ),
        ]
        sentence = ["надеть", ".", "вопрос", "технического"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified)
        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 3}

    def test_agreement_follows_stanza_features(self):
        """The replacement must agree per stanza's disambiguated features.

        The audit found 'Это цветной телевизор.' -> 'цветастой телевизор'
        (40/40): the stored context-free pymorphy parse of 'цветной' is
        ADJF femn,sing,gent, and blindly transferring its grammemes stacks a
        spurious AgrGender/AgrCase error on the intended Lex error. With
        stanza saying Masc|Nom|Sing the output must be 'цветастый'.
        """
        parses = self.morph.parse("цветной")
        wrong_parse = next(p for p in parses if "femn" in p.tag.grammemes)
        tokens = [
            AnalyzedToken(text="Это", lemma="это", pos="PRON", features={}, idx=0),
            AnalyzedToken(
                text="цветной",
                lemma="цветной",
                pos="ADJ",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=1,
                extra={"pymorphy_parse": wrong_parse},
            ),
            AnalyzedToken(
                text="телевизор",
                lemma="телевизор",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=2,
            ),
        ]
        for seed in range(10):
            sentence = ["Это", "цветной", "телевизор"]
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is not None
            assert result.corrupted == "цветастый"
            assert sentence[1] == "цветастый"

    def test_transfers_only_form_level_grammemes(self):
        """Lexeme-level grammemes must not be forced onto the replacement.

        'практичных' parses as ADJF,Qual but 'практический' is not Qual in
        pymorphy; transferring the full grammeme set made inflection fail for
        every such pair. Only POS + form-level grammemes (case/number/gender
        etc.) transfer, so the Loc-plural frame now yields 'практических'.
        """
        parses = self.morph.parse("практичных")
        stored = next(p for p in parses if "gent" in p.tag.grammemes)
        tokens = [
            AnalyzedToken(text="о", lemma="о", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="практичных",
                lemma="практичный",
                pos="ADJ",
                features={"Case": "Loc", "Number": "Plur"},
                idx=1,
                extra={"pymorphy_parse": stored},
            ),
            AnalyzedToken(
                text="решениях",
                lemma="решение",
                pos="NOUN",
                features={"Case": "Loc", "Number": "Plur"},
                idx=2,
            ),
        ]
        sentence = ["о", "практичных", "решениях"]
        result = self.handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is not None
        assert result.corrupted == "практических"

    def test_skips_when_no_parse_matches_stanza_features(self):
        """No pymorphy parse consistent with stanza features -> skip, not guess.

        'цветной' has no Fem+Nom parse; if stanza (hypothetically) assigned
        those features, transferring any stored grammeme set would produce a
        malformed corruption, so the handler must return None.
        """
        tokens = [
            AnalyzedToken(
                text="цветной",
                lemma="цветной",
                pos="ADJ",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                extra={"pymorphy_parse": self.morph.parse("цветной")[0]},
            ),
        ]
        sentence = ["цветной"]
        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence[0] == "цветной"

    def test_quasi_synonym_and_unattested_pairs_removed(self):
        """Defective lexicon entries from the audit must be gone.

        - quasi-synonyms whose swap is acceptable Russian (Rozental §139
          frames paronyms as differing in 'смысловые оттенки', with each
          member correct in overlapping contexts): старый/старинный,
          целый/цельный, выбирать/избирать ('старинный дом' is standard);
        - the non-word 'народничий' (was dormant only because pymorphy
          cannot inflect it);
        - pairs attested in neither the EGE list nor Vishnyakova:
          умелый/умственный, удобный/удобоваримый.
        """
        for word in (
            "старый",
            "старинный",
            "целый",
            "цельный",
            "выбирать",
            "избирать",
            "народный",
            "народничий",
            "умелый",
            "умственный",
            "удобный",
            "удобоваримый",
        ):
            assert word not in self.handler.paronyms, word
        # And no surviving entry offers one of the removed words as a target.
        all_targets = {t for v in self.handler.paronyms.values() for t in v}
        for non_word in ("народничий", "старинный", "умственный", "удобоваримый"):
            assert non_word not in all_targets, non_word

        tokens = [
            AnalyzedToken(
                text="Старый",
                lemma="старый",
                pos="ADJ",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=0,
                extra={"pymorphy_parse": self.morph.parse("старый")[0]},
            ),
            AnalyzedToken(
                text="дом",
                lemma="дом",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=1,
            ),
        ]
        sentence = ["Старый", "дом"]
        assert self.handler.can_apply(tokens, 0) is False
        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence[0] == "Старый"


class TestPrepositionErrorHandler:
    handler = PrepositionErrorHandler()

    def test_implements_protocol(self):
        """Test PrepositionErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "preposition"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_can_apply_finds_prepositions(self):
        """Test PrepositionErrorHandler finds prepositions correctly."""
        tokens = [
            AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="вопрос",
                lemma="вопрос",
                pos="NOUN",
                features={"Case": "Acc"},
                idx=1,
            ),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=2),
            AnalyzedToken(
                text="друга",
                lemma="друг",
                pos="NOUN",
                features={"Case": "Gen"},
                idx=3,
            ),
        ]

        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is False
        assert self.handler.can_apply(tokens, 2) is True
        assert self.handler.can_apply(tokens, 3) is False

    def test_apply_substitutes_correctly(self):
        """Test PrepositionErrorHandler substitutes prepositions correctly."""
        tokens = [
            AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="вопрос",
                lemma="вопрос",
                pos="NOUN",
                features={"Case": "Acc"},
                idx=1,
            ),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=2),
            AnalyzedToken(
                text="друга",
                lemma="друг",
                pos="NOUN",
                features={"Case": "Gen"},
                idx=3,
            ),
        ]
        sentence = ["в", "вопрос", "от", "друга"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 1, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 2, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 3, modified, rng=random.Random(0))
        assert modified == {0, 2}

        # The prepositions were actually replaced, not just flagged as modified.
        assert sentence[0] != "в"
        assert sentence[2] != "от"
        # Replacements must be real single-token prepositions from the lexicon
        # that govern the same case as the original in this frame.
        assert sentence[0] == "на"  # only same-frame (Acc) candidate for в
        assert sentence[2] in {"из", "с"}  # Gen frame candidates for от

    def test_synonym_prepositions_not_corrupted(self):
        """Same-government synonyms must not be corruption sources.

        Rozental §199 lists у дома – при доме – около дома – возле дома as
        synonymous, and продираться сквозь/через кусты as equivalent. Swapping
        within such sets produces correct Russian (a non-error) that would
        teach a GEC model to rewrite valid text, so these words must not be
        in the confusion lexicon at all.
        """
        preps = get_preposition_list()
        all_preps = {w for group in preps.values() for w in group}
        for synonym in (
            "около",
            "возле",
            "у",
            "при",
            "подле",
            "сквозь",
            "через",
            "после",
        ):
            assert synonym not in all_preps

        # Repro from the audit: 'Мы гуляли около дома.' -> 'возле дома'.
        tokens = [
            AnalyzedToken(text="Мы", lemma="мы", pos="PRON", features={}, idx=0),
            AnalyzedToken(
                text="гуляли", lemma="гулять", pos="VERB", features={}, idx=1
            ),
            AnalyzedToken(text="около", lemma="около", pos="ADP", features={}, idx=2),
            AnalyzedToken(text="дома", lemma="дом", pos="NOUN", features={}, idx=3),
        ]
        sentence = ["Мы", "гуляли", "около", "дома"]
        assert self.handler.can_apply(tokens, 2) is False
        for seed in range(50):
            result = self.handler.apply(
                tokens, sentence, 2, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[2] == "около"

    def test_no_non_prepositions_in_lexicon(self):
        """Non-prepositions must not appear as replacement candidates.

        The audit found 'Вопреки прогнозу' -> 'Хотя прогнозу' (хотя is a
        conjunction, cannot govern a dative NP) and 'из дома' -> 'откуда дома'
        (откуда is an adverb) — impossible strings no learner produces.
        'из-подо' is a phonetic variant restricted to specific clusters
        (из-подо льда), so it cannot be a free replacement either.
        """
        preps = get_preposition_list()
        all_preps = {w for group in preps.values() for w in group}
        for non_prep in (
            "хотя",
            "если",
            "откуда",
            "изнутри",
            "более",
            "менее",
            "приблизительно",
            "порядка",
            "из-подо",
        ):
            assert non_prep not in all_preps

        # вопреки has no valid single-token confusion -> never corrupted.
        tokens = [
            AnalyzedToken(
                text="Вопреки", lemma="вопреки", pos="ADP", features={}, idx=0
            ),
            AnalyzedToken(
                text="прогнозу", lemma="прогноз", pos="NOUN", features={}, idx=1
            ),
        ]
        sentence = ["Вопреки", "прогнозу"]
        assert self.handler.can_apply(tokens, 0) is False
        for seed in range(50):
            result = self.handler.apply(
                tokens, sentence, 0, set(), rng=random.Random(seed)
            )
            assert result is None

        # из stays within its attested confusion set (с, от) — never откуда.
        tokens = [
            AnalyzedToken(text="вышел", lemma="выйти", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="из", lemma="из", pos="ADP", features={}, idx=1),
            AnalyzedToken(
                text="дома",
                lemma="дом",
                pos="NOUN",
                features={"Case": "Gen"},
                idx=2,
            ),
        ]
        for seed in range(50):
            sentence = ["вышел", "из", "дома"]
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is not None
            assert result.corrupted in {"с", "от"}

    def test_no_multiword_replacement(self):
        """A length-preserving $REPLACE must never emit a multi-word token.

        ``из-за`` shares the ``causal_government`` group with the multi-word
        entry ``"по причине"``. Substituting that into a single token slot
        would smuggle an intra-token space into the GECToR unit and misalign
        the token/tag stream — so multi-word entries are never candidates.
        """
        from synterr.languages.russian.errors.lexical import _confusion_candidates

        candidates = _confusion_candidates(
            "causal_government", ["благодаря", "из-за", "по причине"], "из-за"
        )
        assert "по причине" not in candidates
        assert all(" " not in c for c in candidates)

        # Under same-case gating из-за (+Gen) has no candidate at all:
        # благодаря governs Dat, so the swap would be a Prep+Gov double error.
        tokens = [
            AnalyzedToken(text="Из-за", lemma="из-за", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="дождя",
                lemma="дождь",
                pos="NOUN",
                features={"Case": "Gen"},
                idx=1,
            ),
        ]
        sentence = ["Из-за", "дождя"]
        assert self.handler.can_apply(tokens, 0) is False
        for seed in range(50):
            result = self.handler.apply(
                tokens, sentence, 0, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[0] == "Из-за"

    def test_replacement_token_tag_consistent(self):
        """A single $REPLACE must keep token count == tag count.

        The corrupted token list, when joined and re-split on whitespace, must
        have exactly as many surface tokens as the original (one $REPLACE spans
        a single position), and the fix_tag must be one $REPLACE edit.
        """
        for seed in range(100):
            tokens = [
                AnalyzedToken(
                    text="Вышел", lemma="выйти", pos="VERB", features={}, idx=0
                ),
                AnalyzedToken(text="из", lemma="из", pos="ADP", features={}, idx=1),
                AnalyzedToken(
                    text="дома",
                    lemma="дом",
                    pos="NOUN",
                    features={"Case": "Gen"},
                    idx=2,
                ),
            ]
            sentence = ["Вышел", "из", "дома"]
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is not None
            # No element of the corrupted list carries an intra-token space, so
            # joining and re-splitting recovers the same token count.
            assert len(" ".join(sentence).split()) == len(sentence)
            assert result.fix_tag == "$REPLACE_из"
            assert result.start_idx == 1
            assert result.end_idx == 2

    def test_same_case_government_required(self):
        """A swap fires only within the same case frame (Rozental §199/§200).

        The audit found 'о поездке' -> 'про поездке', 'до дома' -> 'к дома',
        'Благодаря дождю' -> 'Из-за дождю': the replacement governs a
        different case, leaving the unreinflected noun as a second (Gov)
        error mislabeled as a single Prep edit.
        """
        # о (+Loc) may only become об (+Loc), never про (+Acc).
        tokens = [
            AnalyzedToken(
                text="говорил", lemma="говорить", pos="VERB", features={}, idx=0
            ),
            AnalyzedToken(text="о", lemma="о", pos="ADP", features={}, idx=1),
            AnalyzedToken(
                text="поездке",
                lemma="поездка",
                pos="NOUN",
                features={"Case": "Loc"},
                idx=2,
            ),
        ]
        for seed in range(30):
            sentence = ["говорил", "о", "поездке"]
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is not None
            assert result.corrupted == "об"

        # до (+Gen) has no same-frame partner (к governs Dat) -> inert.
        tokens = [
            AnalyzedToken(text="дошли", lemma="дойти", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="до", lemma="до", pos="ADP", features={}, idx=1),
            AnalyzedToken(
                text="дома", lemma="дом", pos="NOUN", features={"Case": "Gen"}, idx=2
            ),
        ]
        sentence = ["дошли", "до", "дома"]
        assert self.handler.can_apply(tokens, 1) is False
        for seed in range(30):
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[1] == "до"

        # благодаря (+Dat) has no same-frame partner (из-за governs Gen).
        tokens = [
            AnalyzedToken(
                text="Благодаря", lemma="благодаря", pos="ADP", features={}, idx=0
            ),
            AnalyzedToken(
                text="дождю", lemma="дождь", pos="NOUN", features={"Case": "Dat"}, idx=1
            ),
        ]
        sentence = ["Благодаря", "дождю"]
        assert self.handler.can_apply(tokens, 0) is False
        for seed in range(30):
            result = self.handler.apply(
                tokens, sentence, 0, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[0] == "Благодаря"

    def test_sense_outside_lexicon_frame_skipped(self):
        """Comitative с+Ins must not swap with source-sense из/от (+Gen).

        The audit found 'гулял с другом' -> 'гулял из другом' / 'от другом'.
        The source_iz_s_ot group only covers с in its source sense (+Gen);
        an Ins complement means a different sense, so the handler must skip.
        """
        tokens = [
            AnalyzedToken(text="гулял", lemma="гулять", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="с", lemma="с", pos="ADP", features={}, idx=1),
            AnalyzedToken(
                text="другом", lemma="друг", pos="NOUN", features={"Case": "Ins"}, idx=2
            ),
        ]
        sentence = ["гулял", "с", "другом"]
        assert self.handler.can_apply(tokens, 1) is False
        for seed in range(30):
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[1] == "с"

    def test_unknown_governed_case_skipped(self):
        """No determinable case on the complement -> no swap.

        Guessing the frame risks emitting a double error, which is worse
        than producing no error at all.
        """
        tokens = [
            AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="спешке", lemma="спешка", pos="NOUN", features={}, idx=1
            ),  # no Case feature
        ]
        sentence = ["в", "спешке"]
        assert self.handler.can_apply(tokens, 0) is False
        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence[0] == "в"

    def test_governed_case_via_dep_head(self):
        """With depparse the ADP's head (UD case relation) supplies the frame,
        even when the complement is not adjacent."""
        tokens = [
            AnalyzedToken(
                text="в",
                lemma="в",
                pos="ADP",
                features={},
                idx=0,
                dep_rel="case",
                head_idx=2,
            ),
            AnalyzedToken(
                text="ближайшую", lemma="ближайший", pos="ADJ", features={}, idx=1
            ),
            AnalyzedToken(
                text="среду", lemma="среда", pos="NOUN", features={"Case": "Acc"}, idx=2
            ),
        ]
        sentence = ["в", "ближайшую", "среду"]
        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert result.corrupted == "на"


class TestConjunctionErrorHandler:
    handler = ConjunctionErrorHandler()

    def test_implements_protocol(self):
        """Test ConjunctionErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "conjunction"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_can_apply_finds_conjunctions(self):
        """Test ConjunctionErrorHandler finds conjunctions correctly.

        "что" is preceded by "знаю" (что-only matrix verb, C12 gate) so the
        fallback adjacency governor scan licenses the что -> чтобы swap.
        """
        tokens = [
            AnalyzedToken(text="знаю", lemma="знать", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=1),
            AnalyzedToken(text="чем", lemma="чем", pos="SCONJ", features={}, idx=2),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=3
            ),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=4),
        ]

        assert self.handler.can_apply(tokens, 1) is True
        assert self.handler.can_apply(tokens, 2) is True
        assert self.handler.can_apply(tokens, 3) is False
        assert self.handler.can_apply(tokens, 4) is True

    def test_apply_substitutes_correctly(self):
        """Test ConjunctionErrorHandler substitutes conjunctions correctly.

        "что" is preceded by "знаю" (что-only matrix verb, C12 gate) so the
        fallback adjacency governor scan licenses the что -> чтобы swap.
        """
        tokens = [
            AnalyzedToken(text="знаю", lemma="знать", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=1),
            AnalyzedToken(text="чем", lemma="чем", pos="SCONJ", features={}, idx=2),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=3
            ),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=4),
        ]
        sentence = ["знаю", "что", "чем", "вопрос", "чтобы"]
        modified = set()

        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        self.handler.apply(tokens, sentence, 4, modified)
        assert modified == {1, 2, 4}
        assert sentence[1] == "чтобы"  # mood mismatch error
        assert sentence[2] == "как"  # comparative error (directed group)
        assert sentence[4] == "что"

    def test_synonym_conjunctions_not_corrupted(self):
        """Pure-synonym conjunction swaps are non-errors and must be gone.

        Rozental treats и, да (= «и»), или, либо as equivalent coordinating
        conjunctions, and хоть/ежели/нежели as correct stylistic variants.
        The audit showed 'или' -> 'либо' fired deterministically — a
        guaranteed non-error poisoning training data.
        """
        conjs = self.handler.conjunctions
        all_conjs = {w for group in conjs.values() for w in group}
        for synonym in ("или", "либо", "и", "да", "хотя", "хоть", "нежели", "раз"):
            assert synonym not in all_conjs

        tokens = [
            AnalyzedToken(text="хлеб", lemma="хлеб", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text="или", lemma="или", pos="CCONJ", features={}, idx=1),
            AnalyzedToken(
                text="молоко", lemma="молоко", pos="NOUN", features={}, idx=2
            ),
        ]
        sentence = ["хлеб", "или", "молоко"]
        assert self.handler.can_apply(tokens, 1) is False
        for seed in range(50):
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[1] == "или"

    def test_esli_never_becomes_li(self):
        """'если' must never be corrupted to the clause-initial enclitic 'ли'.

        The audit found 'Если он придёт...' -> 'Ли он придёт...' — 'ли' is an
        interrogative enclitic particle that can never stand clause-initially;
        no learner produces this string. The whole conditional synonym group
        (если ~ раз ~ ежели ~ коли) was also a non-error source, so 'если' is
        not a corruption source at all anymore.
        """
        conjs = self.handler.conjunctions
        all_conjs = {w for group in conjs.values() for w in group}
        assert "ли" not in all_conjs
        assert "если" not in all_conjs

        tokens = [
            AnalyzedToken(text="Если", lemma="если", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(text="он", lemma="он", pos="PRON", features={}, idx=1),
            AnalyzedToken(
                text="придёт", lemma="прийти", pos="VERB", features={}, idx=2
            ),
        ]
        sentence = ["Если", "он", "придёт"]
        assert self.handler.can_apply(tokens, 0) is False
        for seed in range(50):
            result = self.handler.apply(
                tokens, sentence, 0, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[0] == "Если"

    def test_directed_group_only_corrupts_head(self):
        """directed_* groups corrupt only their first member.

        чем→как after a comparative is an attested error; the reverse как→чем
        is garbage no human writes, so 'как' must not be a source.
        """
        tokens = [
            AnalyzedToken(text="чем", lemma="чем", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(text="как", lemma="как", pos="SCONJ", features={}, idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is False

        sentence = ["чем", "как"]
        result = self.handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
        assert result is None
        assert sentence[1] == "как"

        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is not None
        assert result.corrupted == "как"

    def test_chto_chtoby_gated_on_matrix_verb(self):
        """C12 (2026-07 audit): что -> чтобы must fire only under matrix
        predicates that license ONLY что (indicative complement); verbs that
        license both что and чтобы (сказать/попросить/потребовать-class) must
        not be corrupted, since both readings are already grammatical.
        """
        # "Я сказал, что он придёт." -- сказать licenses both что (report of
        # fact) and чтобы (request); swapping corrupts already-correct text.
        tokens = [
            AnalyzedToken(
                text="Я", lemma="я", pos="PRON", features={}, idx=0, head_idx=1
            ),
            AnalyzedToken(
                text="сказал",
                lemma="сказать",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text=",", lemma=",", pos="PUNCT", features={}, idx=2, head_idx=4
            ),
            AnalyzedToken(
                text="что",
                lemma="что",
                pos="SCONJ",
                features={},
                idx=3,
                dep_rel="mark",
                head_idx=4,
            ),
            AnalyzedToken(
                text="придёт",
                lemma="прийти",
                pos="VERB",
                features={},
                idx=4,
                dep_rel="ccomp",
                head_idx=1,
            ),
        ]
        assert self.handler.can_apply(tokens, 3) is False
        sentence = ["Я", "сказал", ",", "что", "придёт"]
        for seed in range(30):
            result = self.handler.apply(
                tokens, sentence, 3, set(), rng=random.Random(seed)
            )
            assert result is None
            assert sentence[3] == "что"

        # "Я знаю, что он придёт." -- знать licenses only что (report of
        # fact, no request reading); the swap is a genuine mood error.
        tokens2 = [
            AnalyzedToken(
                text="Я", lemma="я", pos="PRON", features={}, idx=0, head_idx=1
            ),
            AnalyzedToken(
                text="знаю",
                lemma="знать",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text=",", lemma=",", pos="PUNCT", features={}, idx=2, head_idx=4
            ),
            AnalyzedToken(
                text="что",
                lemma="что",
                pos="SCONJ",
                features={},
                idx=3,
                dep_rel="mark",
                head_idx=4,
            ),
            AnalyzedToken(
                text="придёт",
                lemma="прийти",
                pos="VERB",
                features={},
                idx=4,
                dep_rel="ccomp",
                head_idx=1,
            ),
        ]
        assert self.handler.can_apply(tokens2, 3) is True
        sentence2 = ["Я", "знаю", ",", "что", "придёт"]
        result = self.handler.apply(tokens2, sentence2, 3, set(), rng=random.Random(0))
        assert result is not None
        assert result.corrupted == "чтобы"

    def test_chto_chtoby_no_governor_skipped(self):
        """No determinable matrix governor (no dep info, no preceding verb)
        -> skip rather than guess (precision-first)."""
        tokens = [
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(
                text="случилось", lemma="случиться", pos="VERB", features={}, idx=1
            ),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        sentence = ["что", "случилось"]
        result = self.handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
        assert result is None
        assert sentence[0] == "что"


class TestPronounSvoyErrorHandler:
    handler = PronounSvoyErrorHandler()

    def test_implements_protocol(self):
        """Test PronounSvoyErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "subtypes")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "pronoun_svoy"
        assert self.handler.subtypes == ["pronoun_svoy"]
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_can_apply_requires_svoy_lemma(self):
        """Only свой (DET/PRON) is a corruption source."""
        tokens = [
            AnalyzedToken(text="Я", lemma="я", pos="PRON", features={}, idx=0),
            AnalyzedToken(text="нашёл", lemma="найти", pos="VERB", features={}, idx=1),
            AnalyzedToken(
                text="свою",
                lemma="свой",
                pos="DET",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=2,
                dep_rel="det",
                head_idx=3,
            ),
            AnalyzedToken(
                text="книгу",
                lemma="книга",
                pos="NOUN",
                features={
                    "Animacy": "Inan",
                    "Case": "Acc",
                    "Gender": "Fem",
                    "Number": "Sing",
                },
                idx=3,
                dep_rel="obj",
                head_idx=1,
            ),
        ]
        # nsubj of the root supplies the referent -> свой fires.
        tokens[0] = AnalyzedToken(
            text="Я",
            lemma="я",
            pos="PRON",
            features={"Case": "Nom", "Number": "Sing", "Person": "1"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
        )
        assert self.handler.can_apply(tokens, 0) is False  # я
        assert self.handler.can_apply(tokens, 1) is False  # нашёл
        assert self.handler.can_apply(tokens, 2) is True  # свою
        assert self.handler.can_apply(tokens, 3) is False  # книгу

    def test_apply_first_person_singular(self):
        """'Я нашёл свою книгу.' -> 'Я нашёл мою книгу.' (Rozental §167)."""
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
                text="нашёл",
                lemma="найти",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="свою",
                lemma="свой",
                pos="DET",
                features={
                    "Case": "Acc",
                    "Gender": "Fem",
                    "Number": "Sing",
                    "Poss": "Yes",
                    "PronType": "Prs",
                    "Reflex": "Yes",
                },
                idx=2,
                dep_rel="det",
                head_idx=3,
            ),
            AnalyzedToken(
                text="книгу",
                lemma="книга",
                pos="NOUN",
                features={
                    "Animacy": "Inan",
                    "Case": "Acc",
                    "Gender": "Fem",
                    "Number": "Sing",
                },
                idx=3,
                dep_rel="obj",
                head_idx=1,
            ),
        ]
        sentence = ["Я", "нашёл", "свою", "книгу"]
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.corrupted == "мою"
        assert result.fix_tag == "$REPLACE_свою"
        assert sentence[2] == "мою"

    def _svoy_tokens(self, subject_text, subject_lemma, subject_pos, subject_features):
        """Build 'X <verb> своей работой' with 'X' as the nsubj."""
        return [
            AnalyzedToken(
                text=subject_text,
                lemma=subject_lemma,
                pos=subject_pos,
                features=subject_features,
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="гордится",
                lemma="гордиться",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="своей",
                lemma="свой",
                pos="DET",
                features={"Case": "Ins", "Gender": "Fem", "Number": "Sing"},
                idx=2,
                dep_rel="det",
                head_idx=3,
            ),
            AnalyzedToken(
                text="работой",
                lemma="работа",
                pos="NOUN",
                features={
                    "Animacy": "Inan",
                    "Case": "Ins",
                    "Gender": "Fem",
                    "Number": "Sing",
                },
                idx=3,
                dep_rel="obl",
                head_idx=1,
            ),
        ]

    def test_apply_declinable_persons(self):
        """1st/2nd-person subjects inflect мой/твой/наш/ваш to свой's own
        case/number/gender (here Ins/Fem/Sing, matching 'своей работой')."""
        cases = [
            ("Ты", "ты", {"Case": "Nom", "Number": "Sing", "Person": "2"}, "твоей"),
            ("Мы", "мы", {"Case": "Nom", "Number": "Plur", "Person": "1"}, "нашей"),
        ]
        for subject_text, subject_lemma, feats, expected in cases:
            tokens = self._svoy_tokens(subject_text, subject_lemma, "PRON", feats)
            tokens[2] = AnalyzedToken(
                text="своей",
                lemma="свой",
                pos="DET",
                features={"Case": "Ins", "Gender": "Fem", "Number": "Sing"},
                idx=2,
                dep_rel="det",
                head_idx=3,
            )
            sentence = [subject_text, "гордится", "своей", "работой"]
            result = self.handler.apply(tokens, sentence, 2, set())
            assert result is not None, subject_lemma
            assert result.corrupted == expected, subject_lemma

    def test_apply_invariable_third_person(self):
        """3rd-person subjects (pronoun or noun) map to invariable его/её/их."""
        cases = [
            (
                "Он",
                "он",
                "PRON",
                {"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                "его",
            ),
            (
                "Она",
                "она",
                "PRON",
                {"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                "её",
            ),
            ("Они", "они", "PRON", {"Case": "Nom", "Number": "Plur"}, "их"),
            (
                "Мальчик",
                "мальчик",
                "NOUN",
                {"Case": "Nom", "Gender": "Masc", "Number": "Sing", "Animacy": "Anim"},
                "его",
            ),
            (
                "Девочки",
                "девочка",
                "NOUN",
                {"Case": "Nom", "Gender": "Fem", "Number": "Plur", "Animacy": "Anim"},
                "их",
            ),
        ]
        for subject_text, subject_lemma, pos, feats, expected in cases:
            tokens = self._svoy_tokens(subject_text, subject_lemma, pos, feats)
            sentence = [subject_text, "гордится", "своей", "работой"]
            result = self.handler.apply(tokens, sentence, 2, set())
            assert result is not None, subject_lemma
            assert result.corrupted == expected, subject_lemma
            # Invariable forms never inflect, regardless of свой's own case.
            assert sentence[2] == expected

    def test_idiom_head_noun_skipped(self):
        """'не в своей тарелке' -- свой is lexicalized, not a referential slot."""
        tokens = [
            AnalyzedToken(
                text="Он",
                lemma="он",
                pos="PRON",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=2,
            ),
            AnalyzedToken(
                text="не", lemma="не", pos="PART", features={}, idx=1, head_idx=2
            ),
            AnalyzedToken(
                text="в",
                lemma="в",
                pos="ADP",
                features={},
                idx=2,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="своей",
                lemma="свой",
                pos="DET",
                features={"Case": "Loc", "Gender": "Fem", "Number": "Sing"},
                idx=3,
                dep_rel="det",
                head_idx=4,
            ),
            AnalyzedToken(
                text="тарелке",
                lemma="тарелка",
                pos="NOUN",
                features={"Case": "Loc", "Gender": "Fem", "Number": "Sing"},
                idx=4,
                dep_rel="obl",
                head_idx=2,
            ),
        ]
        sentence = ["Он", "не", "в", "своей", "тарелке"]
        assert self.handler.can_apply(tokens, 3) is False
        result = self.handler.apply(tokens, sentence, 3, set())
        assert result is None
        assert sentence[3] == "своей"

    def test_degenerate_subject_is_own_head_skipped(self):
        """'Свой дом лучше.' -- свой modifies the subject itself: no distinct
        referent to borrow person/number from, so the handler must skip."""
        tokens = [
            AnalyzedToken(
                text="Свой",
                lemma="свой",
                pos="DET",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=0,
                dep_rel="det",
                head_idx=1,
            ),
            AnalyzedToken(
                text="дом",
                lemma="дом",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Masc", "Number": "Sing"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
            ),
            AnalyzedToken(
                text="лучше",
                lemma="хороший",
                pos="ADJ",
                features={},
                idx=2,
                dep_rel="root",
                head_idx=None,
            ),
        ]
        sentence = ["Свой", "дом", "лучше"]
        assert self.handler.can_apply(tokens, 0) is False
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is None
        assert sentence[0] == "Свой"

    def test_no_dep_info_fallback_to_first_second_person(self):
        """Without depparse, fall back to the nearest preceding я/ты/мы/вы."""
        tokens = [
            AnalyzedToken(
                text="Я", lemma="я", pos="PRON", features={"Person": "1"}, idx=0
            ),
            AnalyzedToken(text="читаю", lemma="читать", pos="VERB", features={}, idx=1),
            AnalyzedToken(
                text="свою",
                lemma="свой",
                pos="DET",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=2,
            ),
            AnalyzedToken(text="книгу", lemma="книга", pos="NOUN", features={}, idx=3),
        ]
        sentence = ["Я", "читаю", "свою", "книгу"]
        assert self.handler.can_apply(tokens, 2) is True
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.corrupted == "мою"

    def test_no_dep_info_third_person_not_guessed(self):
        """Without depparse, a 3rd-person antecedent is too ambiguous to
        guess by scanning -- only 1st/2nd person get the no-parse fallback."""
        tokens = [
            AnalyzedToken(
                text="Мальчик", lemma="мальчик", pos="NOUN", features={}, idx=0
            ),
            AnalyzedToken(text="нашёл", lemma="найти", pos="VERB", features={}, idx=1),
            AnalyzedToken(
                text="свою",
                lemma="свой",
                pos="DET",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=2,
            ),
            AnalyzedToken(text="книгу", lemma="книга", pos="NOUN", features={}, idx=3),
        ]
        sentence = ["Мальчик", "нашёл", "свою", "книгу"]
        assert self.handler.can_apply(tokens, 2) is False
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is None
        assert sentence[2] == "свою"

    def test_clause_boundary_not_crossed_for_control_verb(self):
        """'Мама попросила Петю привести своего друга.' -- своего attaches
        inside the xcomp infinitive controlled by Петя (object control), not
        by the matrix subject Мама. Climbing past the xcomp boundary without
        a local nsubj would wrongly resolve to Мама; the handler must skip
        instead of guessing.
        """
        tokens = [
            AnalyzedToken(
                text="Мама",
                lemma="мама",
                pos="NOUN",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="попросила",
                lemma="попросить",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="Петю",
                lemma="Петя",
                pos="PROPN",
                features={"Case": "Acc"},
                idx=2,
                dep_rel="obj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="привести",
                lemma="привести",
                pos="VERB",
                features={"VerbForm": "Inf"},
                idx=3,
                dep_rel="xcomp",
                head_idx=1,
            ),
            AnalyzedToken(
                text="своего",
                lemma="свой",
                pos="DET",
                features={"Case": "Acc", "Gender": "Masc", "Number": "Sing"},
                idx=4,
                dep_rel="det",
                head_idx=5,
            ),
            AnalyzedToken(
                text="друга",
                lemma="друг",
                pos="NOUN",
                features={
                    "Animacy": "Anim",
                    "Case": "Acc",
                    "Gender": "Masc",
                    "Number": "Sing",
                },
                idx=5,
                dep_rel="obj",
                head_idx=3,
            ),
        ]
        sentence = ["Мама", "попросила", "Петю", "привести", "своего", "друга"]
        assert self.handler.can_apply(tokens, 4) is False
        result = self.handler.apply(tokens, sentence, 4, set())
        assert result is None
        assert sentence[4] == "своего"

    def test_replacement_token_tag_consistent(self):
        """Single $REPLACE, one token in, one token out."""
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
                text="люблю",
                lemma="любить",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="свою",
                lemma="свой",
                pos="DET",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=2,
                dep_rel="det",
                head_idx=3,
            ),
            AnalyzedToken(
                text="работу",
                lemma="работа",
                pos="NOUN",
                features={"Case": "Acc", "Gender": "Fem", "Number": "Sing"},
                idx=3,
                dep_rel="obj",
                head_idx=1,
            ),
        ]
        sentence = ["Я", "люблю", "свою", "работу"]
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.fix_tag == "$REPLACE_свою"
        assert result.start_idx == 2
        assert result.end_idx == 3
        assert len(" ".join(sentence).split()) == len(sentence)


class TestPronounSebyaErrorHandler:
    handler = PronounSebyaErrorHandler()

    def test_implements_protocol(self):
        """Test PronounSebyaErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "subtypes")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "pronoun_sebya"
        assert self.handler.subtypes == ["pronoun_sebya"]
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_can_apply_requires_sebya_lemma(self):
        """Only себя (PRON) is a corruption source."""
        tokens = [
            AnalyzedToken(
                text="Она",
                lemma="она",
                pos="PRON",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="довольна",
                lemma="довольный",
                pos="ADJ",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="собой",
                lemma="себя",
                pos="PRON",
                features={"Case": "Ins", "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
                dep_rel="iobj",
                head_idx=1,
            ),
        ]
        assert self.handler.can_apply(tokens, 0) is False  # она
        assert self.handler.can_apply(tokens, 1) is False  # довольна
        assert self.handler.can_apply(tokens, 2) is True  # собой

    def test_apply_reflexive_to_personal_pronoun(self):
        """'Она довольна собой.' -> 'Она довольна ей.' (Rozental §168)."""
        tokens = [
            AnalyzedToken(
                text="Она",
                lemma="она",
                pos="PRON",
                features={"Case": "Nom", "Gender": "Fem", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="довольна",
                lemma="довольный",
                pos="ADJ",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="собой",
                lemma="себя",
                pos="PRON",
                features={"Case": "Ins", "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
                dep_rel="iobj",
                head_idx=1,
            ),
        ]
        sentence = ["Она", "довольна", "собой"]
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.corrupted == "ей"
        assert result.fix_tag == "$REPLACE_собой"
        assert sentence[2] == "ей"

    def _sebya_tokens(
        self, subject_text, subject_lemma, subject_pos, subject_feats, case
    ):
        """Build 'X купил <sebya-form> квартиру' with X as the nsubj of купил."""
        surface = {"Acc": "себя", "Gen": "себя", "Dat": "себе", "Ins": "собой"}[case]
        return [
            AnalyzedToken(
                text=subject_text,
                lemma=subject_lemma,
                pos=subject_pos,
                features=subject_feats,
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="купил",
                lemma="купить",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text=surface,
                lemma="себя",
                pos="PRON",
                features={"Case": case, "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
                dep_rel="iobj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="квартиру",
                lemma="квартира",
                pos="NOUN",
                features={"Case": "Acc"},
                idx=3,
                dep_rel="obj",
                head_idx=1,
            ),
        ], surface

    def test_apply_all_persons_and_cases(self):
        """Subject person/number/gender maps to the matching personal
        pronoun, inflected to себя's own case."""
        cases = [
            ("Я", "я", "PRON", {"Person": "1", "Number": "Sing"}, "Acc", "меня"),
            ("Ты", "ты", "PRON", {"Person": "2", "Number": "Sing"}, "Dat", "тебе"),
            ("Мы", "мы", "PRON", {"Person": "1", "Number": "Plur"}, "Ins", "нами"),
            ("Вы", "вы", "PRON", {"Person": "2", "Number": "Plur"}, "Acc", "вас"),
            ("Он", "он", "PRON", {"Gender": "Masc", "Number": "Sing"}, "Dat", "ему"),
            ("Они", "они", "PRON", {"Number": "Plur"}, "Ins", "ими"),
            (
                "Мальчик",
                "мальчик",
                "NOUN",
                {"Gender": "Masc", "Number": "Sing", "Animacy": "Anim"},
                "Acc",
                "его",
            ),
            (
                "Девочка",
                "девочка",
                "NOUN",
                {"Gender": "Fem", "Number": "Sing", "Animacy": "Anim"},
                "Dat",
                "ей",
            ),
        ]
        for subject_text, subject_lemma, pos, feats, case, expected in cases:
            tokens, surface = self._sebya_tokens(
                subject_text, subject_lemma, pos, feats, case
            )
            sentence = [subject_text, "купил", surface, "квартиру"]
            result = self.handler.apply(tokens, sentence, 2, set())
            assert result is not None, subject_lemma
            assert result.corrupted == expected, (subject_lemma, case)

    def test_set_phrase_helper(self):
        """Direct check of the neighbor-lemma idiom gate."""

        def tok(lemma):
            return AnalyzedToken(text=lemma, lemma=lemma, pos="X", features={}, idx=0)

        # так себе
        assert _is_sebya_set_phrase([tok("так"), tok("себя")], 1) is True
        # само собой
        assert _is_sebya_set_phrase([tok("сам"), tok("себя")], 1) is True
        # сам по себе
        assert _is_sebya_set_phrase([tok("сам"), tok("по"), tok("себя")], 2) is True
        # между собой
        assert _is_sebya_set_phrase([tok("между"), tok("себя")], 1) is True
        # прийти в себя
        assert _is_sebya_set_phrase([tok("прийти"), tok("в"), tok("себя")], 2) is True
        # ordinary usage is not flagged
        assert _is_sebya_set_phrase([tok("он"), tok("любит"), tok("себя")], 2) is False

    def test_set_phrase_skipped_end_to_end(self):
        """'Они гуляли между собой полдня.' -- собой is part of the fixed
        reciprocal idiom, not a referential slot, even though the subject
        (они) would otherwise be resolvable via the dep tree."""
        tokens = [
            AnalyzedToken(
                text="Они",
                lemma="они",
                pos="PRON",
                features={"Number": "Plur"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="гуляли",
                lemma="гулять",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="между",
                lemma="между",
                pos="ADP",
                features={},
                idx=2,
                dep_rel="case",
                head_idx=3,
            ),
            AnalyzedToken(
                text="собой",
                lemma="себя",
                pos="PRON",
                features={"Case": "Ins", "PronType": "Prs", "Reflex": "Yes"},
                idx=3,
                dep_rel="obl",
                head_idx=1,
            ),
        ]
        sentence = ["Они", "гуляли", "между", "собой"]
        assert self.handler.can_apply(tokens, 3) is False
        result = self.handler.apply(tokens, sentence, 3, set())
        assert result is None
        assert sentence[3] == "собой"

    def test_no_subject_skipped_without_dep_info(self):
        """Without depparse, only a *clause-initial* pronoun counts as the
        subject; a non-pronoun sentence-initial noun is not enough."""
        tokens = [
            AnalyzedToken(
                text="Мальчик", lemma="мальчик", pos="NOUN", features={}, idx=0
            ),
            AnalyzedToken(text="любит", lemma="любить", pos="VERB", features={}, idx=1),
            AnalyzedToken(
                text="себя",
                lemma="себя",
                pos="PRON",
                features={"Case": "Acc", "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
            ),
        ]
        sentence = ["Мальчик", "любит", "себя"]
        assert self.handler.can_apply(tokens, 2) is False
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is None
        assert sentence[2] == "себя"

    def test_no_dep_info_clause_initial_fallback(self):
        """Without depparse, a clause-initial personal pronoun is used."""
        tokens = [
            AnalyzedToken(text="Он", lemma="он", pos="PRON", features={}, idx=0),
            AnalyzedToken(text="любит", lemma="любить", pos="VERB", features={}, idx=1),
            AnalyzedToken(
                text="себя",
                lemma="себя",
                pos="PRON",
                features={"Case": "Acc", "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
            ),
        ]
        sentence = ["Он", "любит", "себя"]
        assert self.handler.can_apply(tokens, 2) is True
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.corrupted == "его"

    def test_replacement_token_tag_consistent(self):
        """Single $REPLACE, one token in, one token out."""
        tokens = [
            AnalyzedToken(
                text="Он",
                lemma="он",
                pos="PRON",
                features={"Gender": "Masc", "Number": "Sing"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="взял",
                lemma="брать",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="себе",
                lemma="себя",
                pos="PRON",
                features={"Case": "Dat", "PronType": "Prs", "Reflex": "Yes"},
                idx=2,
                dep_rel="iobj",
                head_idx=1,
            ),
            AnalyzedToken(
                text="выходной",
                lemma="выходной",
                pos="NOUN",
                features={"Case": "Acc"},
                idx=3,
                dep_rel="obj",
                head_idx=1,
            ),
        ]
        sentence = ["Он", "взял", "себе", "выходной"]
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.fix_tag == "$REPLACE_себе"
        assert result.start_idx == 2
        assert result.end_idx == 3
        assert len(" ".join(sentence).split()) == len(sentence)


class TestPronounNFormErrorHandler:
    handler = PronounNFormErrorHandler()

    def test_implements_protocol(self):
        """Test PronounNFormErrorHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "subtypes")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "pronoun_n_form"
        assert self.handler.subtypes == ["pronoun_n_form"]
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def _prep_tokens(self, prep_text, prep_lemma, pron_text, pron_lemma, features):
        """Build '<prep> <pronoun>' with the ADP attached via dep_rel='case'."""
        return [
            AnalyzedToken(
                text=prep_text,
                lemma=prep_lemma,
                pos="ADP",
                features={},
                idx=0,
                dep_rel="case",
                head_idx=1,
            ),
            AnalyzedToken(
                text=pron_text,
                lemma=pron_lemma,
                pos="PRON",
                features=features,
                idx=1,
                dep_rel="obl",
                head_idx=2,
            ),
        ]

    def test_direction_a_drops_n_after_true_preposition(self):
        """'у него' -> 'у его', 'с ней' -> 'с ей', 'к ним' -> 'к им',
        'без неё' -> 'без её' (Rozental §169-170, direction a)."""
        cases = [
            ("у", "у", "него", "он", {"Case": "Gen", "Gender": "Masc"}, "его"),
            ("с", "с", "ней", "она", {"Case": "Ins", "Gender": "Fem"}, "ей"),
            ("к", "к", "ним", "они", {"Case": "Dat", "Number": "Plur"}, "им"),
            ("без", "без", "неё", "она", {"Case": "Gen", "Gender": "Fem"}, "её"),
            ("к", "к", "нему", "он", {"Case": "Dat", "Gender": "Masc"}, "ему"),
        ]
        for prep_text, prep_lemma, pron_text, pron_lemma, feats, expected in cases:
            tokens = self._prep_tokens(
                prep_text, prep_lemma, pron_text, pron_lemma, feats
            )
            sentence = [prep_text, pron_text]
            assert self.handler.can_apply(tokens, 1) is True, pron_text
            result = self.handler.apply(tokens, sentence, 1, set())
            assert result is not None, pron_text
            assert result.corrupted == expected, pron_text
            assert result.fix_tag == f"$REPLACE_{pron_text}"
            assert sentence[1] == expected

    def test_direction_b_adds_n_after_exception_governor(self):
        """'благодаря ему' -> 'благодаря нему', 'согласно ей' -> 'согласно
        ней', 'вопреки им' -> 'вопреки ним' (hyper-correction, direction b)."""
        cases = [
            ("благодаря", "благодаря", "ему", "он", {"Case": "Dat"}, "нему"),
            ("согласно", "согласно", "ей", "она", {"Case": "Dat"}, "ней"),
            ("вопреки", "вопреки", "им", "они", {"Case": "Dat"}, "ним"),
            ("наперекор", "наперекор", "ему", "он", {"Case": "Dat"}, "нему"),
            ("навстречу", "навстречу", "ему", "он", {"Case": "Dat"}, "нему"),
        ]
        for prep_text, prep_lemma, pron_text, pron_lemma, feats, expected in cases:
            tokens = self._prep_tokens(
                prep_text, prep_lemma, pron_text, pron_lemma, feats
            )
            sentence = [prep_text, pron_text]
            assert self.handler.can_apply(tokens, 1) is True, pron_text
            result = self.handler.apply(tokens, sentence, 1, set())
            assert result is not None, pron_text
            assert result.corrupted == expected, pron_text
            assert sentence[1] == expected

    def test_no_governor_skipped(self):
        """Bare/augmented pronoun with no adjacent preposition never fires."""
        tokens = [
            AnalyzedToken(text="Мама", lemma="мама", pos="NOUN", features={}, idx=0),
            AnalyzedToken(
                text="видела",
                lemma="видеть",
                pos="VERB",
                features={},
                idx=1,
                dep_rel="root",
                head_idx=None,
            ),
            AnalyzedToken(
                text="него",
                lemma="он",
                pos="PRON",
                features={"Case": "Acc"},
                idx=2,
                dep_rel="obj",
                head_idx=1,
            ),
        ]
        sentence = ["Мама", "видела", "него"]
        assert self.handler.can_apply(tokens, 2) is False
        result = self.handler.apply(tokens, sentence, 2, set())
        assert result is None
        assert sentence[2] == "него"

    def test_possessive_never_fires_in_direction_b(self):
        """'благодаря его помощи' -- его here is the frozen possessive
        determiner ('his help'), not the Dative personal pronoun that
        благодаря actually governs. Possessive его/её/их are a disjoint
        surface-form set from the Dative bare forms (ему/ей/им) that
        direction (b) targets, so this must never fire; dep_rel='det' is
        checked defensively on top of that.
        """
        tokens = [
            AnalyzedToken(
                text="благодаря",
                lemma="благодаря",
                pos="ADP",
                features={},
                idx=0,
                dep_rel="case",
                head_idx=2,
            ),
            AnalyzedToken(
                text="его",
                lemma="его",
                pos="DET",
                features={"Poss": "Yes", "PronType": "Prs"},
                idx=1,
                dep_rel="det",
                head_idx=2,
            ),
            AnalyzedToken(
                text="помощи",
                lemma="помощь",
                pos="NOUN",
                features={"Case": "Dat"},
                idx=2,
                dep_rel="obl",
                head_idx=3,
            ),
        ]
        sentence = ["благодаря", "его", "помощи"]
        assert self.handler.can_apply(tokens, 1) is False
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None
        assert sentence[1] == "его"

    def test_comparative_neighbor_skipped(self):
        """'лучше него' / 'лучше его' -- both acceptable after a comparative;
        neither direction may fire since no true preposition governs the
        pronoun here (its governor is the comparative itself)."""
        tokens = [
            AnalyzedToken(
                text="Лучше",
                lemma="хорошо",
                pos="ADV",
                features={"Degree": "Cmp"},
                idx=0,
                dep_rel="advmod",
                head_idx=2,
            ),
            AnalyzedToken(
                text="него",
                lemma="он",
                pos="PRON",
                features={"Case": "Gen"},
                idx=1,
                dep_rel="obl",
                head_idx=0,
            ),
            AnalyzedToken(
                text="никто",
                lemma="никто",
                pos="PRON",
                features={},
                idx=2,
                dep_rel="nsubj",
                head_idx=3,
            ),
        ]
        sentence = ["Лучше", "него", "никто"]
        assert self.handler.can_apply(tokens, 1) is False
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None
        assert sentence[1] == "него"

    def test_exception_governor_list_closed(self):
        """Only the five listed secondary prepositions trigger direction (b);
        an ordinary Dative-governing preposition (e.g. 'к') must not."""
        tokens = self._prep_tokens("к", "к", "ему", "он", {"Case": "Dat"})
        sentence = ["к", "ему"]
        assert self.handler.can_apply(tokens, 1) is False
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None
        assert sentence[1] == "ему"

    def test_no_dep_info_fallback_adjacency(self):
        """Without depparse, an immediate-left ADP/exception-lemma neighbor
        still drives both directions."""
        tokens = [
            AnalyzedToken(text="у", lemma="у", pos="ADP", features={}, idx=0),
            AnalyzedToken(
                text="него", lemma="он", pos="PRON", features={"Case": "Gen"}, idx=1
            ),
        ]
        sentence = ["у", "него"]
        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert result.corrupted == "его"

        tokens = [
            AnalyzedToken(
                text="благодаря", lemma="благодаря", pos="ADP", features={}, idx=0
            ),
            AnalyzedToken(
                text="ему", lemma="он", pos="PRON", features={"Case": "Dat"}, idx=1
            ),
        ]
        sentence = ["благодаря", "ему"]
        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert result.corrupted == "нему"

    def test_first_second_person_pronouns_never_fire(self):
        """я/ты/мы/вы have no augmented paradigm at all -- must never fire
        even if adjacent to a preposition."""
        tokens = self._prep_tokens("у", "у", "меня", "я", {"Case": "Gen"})
        sentence = ["у", "меня"]
        assert self.handler.can_apply(tokens, 1) is False
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None
        assert sentence[1] == "меня"

    def test_replacement_token_tag_consistent(self):
        """Single $REPLACE, one token in, one token out."""
        tokens = self._prep_tokens("у", "у", "него", "он", {"Case": "Gen"})
        sentence = ["у", "него"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert result.fix_tag == "$REPLACE_него"
        assert result.start_idx == 1
        assert result.end_idx == 2
        assert len(" ".join(sentence).split()) == len(sentence)

    def test_capitalization_preserved(self):
        """Sentence-initial capitalized pronoun keeps its capitalization."""
        tokens = self._prep_tokens("Без", "без", "Него", "он", {"Case": "Gen"})
        sentence = ["Без", "Него"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert result.corrupted == "Его"
        assert sentence[1] == "Его"
