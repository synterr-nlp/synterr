import random

import pymorphy3

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.lexical import (
    ConjunctionErrorHandler,
    ParonymErrorHandler,
    PrepositionErrorHandler,
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
            "старый", "старинный",
            "целый", "цельный",
            "выбирать", "избирать",
            "народный", "народничий",
            "умелый", "умственный",
            "удобный", "удобоваримый",
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
        for synonym in ("около", "возле", "у", "при", "подле", "сквозь", "через", "после"):
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
            "хотя", "если", "откуда", "изнутри",
            "более", "менее", "приблизительно", "порядка", "из-подо",
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
            AnalyzedToken(text="говорил", lemma="говорить", pos="VERB",
                          features={}, idx=0),
            AnalyzedToken(text="о", lemma="о", pos="ADP", features={}, idx=1),
            AnalyzedToken(text="поездке", lemma="поездка", pos="NOUN",
                          features={"Case": "Loc"}, idx=2),
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
            AnalyzedToken(text="дошли", lemma="дойти", pos="VERB",
                          features={}, idx=0),
            AnalyzedToken(text="до", lemma="до", pos="ADP", features={}, idx=1),
            AnalyzedToken(text="дома", lemma="дом", pos="NOUN",
                          features={"Case": "Gen"}, idx=2),
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
            AnalyzedToken(text="Благодаря", lemma="благодаря", pos="ADP",
                          features={}, idx=0),
            AnalyzedToken(text="дождю", lemma="дождь", pos="NOUN",
                          features={"Case": "Dat"}, idx=1),
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
            AnalyzedToken(text="гулял", lemma="гулять", pos="VERB",
                          features={}, idx=0),
            AnalyzedToken(text="с", lemma="с", pos="ADP", features={}, idx=1),
            AnalyzedToken(text="другом", lemma="друг", pos="NOUN",
                          features={"Case": "Ins"}, idx=2),
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
            AnalyzedToken(text="спешке", lemma="спешка", pos="NOUN",
                          features={}, idx=1),  # no Case feature
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
            AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0,
                          dep_rel="case", head_idx=2),
            AnalyzedToken(text="ближайшую", lemma="ближайший", pos="ADJ",
                          features={}, idx=1),
            AnalyzedToken(text="среду", lemma="среда", pos="NOUN",
                          features={"Case": "Acc"}, idx=2),
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
        """Test ConjunctionErrorHandler finds conjunctions correctly."""
        tokens = [
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(text="чем", lemma="чем", pos="SCONJ", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=3),
        ]

        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is True
        assert self.handler.can_apply(tokens, 2) is False
        assert self.handler.can_apply(tokens, 3) is True

    def test_apply_substitutes_correctly(self):
        """Test ConjunctionErrorHandler substitutes conjunctions correctly."""
        tokens = [
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(text="чем", lemma="чем", pos="SCONJ", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=3),
        ]
        sentence = ["что", "чем", "вопрос", "чтобы"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified)
        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 1, 3}
        assert sentence[0] == "чтобы"  # mood mismatch error
        assert sentence[1] == "как"  # comparative error (directed group)
        assert sentence[3] == "что"

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
        result = self.handler.apply(
            tokens, sentence, 1, set(), rng=random.Random(0)
        )
        assert result is None
        assert sentence[1] == "как"

        result = self.handler.apply(
            tokens, sentence, 0, set(), rng=random.Random(0)
        )
        assert result is not None
        assert result.corrupted == "как"
