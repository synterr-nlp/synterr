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
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=3),
        ]

        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is False
        assert self.handler.can_apply(tokens, 2) is False
        assert self.handler.can_apply(tokens, 3) is True

    def test_apply_substitutes_correctly(self):
        """Test PrepositionErrorHandler substitutes prepositions correctly."""
        tokens = [
            AnalyzedToken(text="в", lemma="в", pos="ADP", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=3),
        ]
        sentence = ["в", ".", "вопрос", "от"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 1, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 2, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 3, modified, rng=random.Random(0))
        assert modified == {0, 3}

        # The prepositions were actually replaced, not just flagged as modified.
        assert sentence[0] != "в"
        assert sentence[3] != "от"
        # Replacements must be real single-token prepositions from the lexicon.
        preps = get_preposition_list()
        all_preps = {w for group in preps.values() for w in group}
        for repl in (sentence[0], sentence[3]):
            assert " " not in repl
            assert repl in all_preps

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
            AnalyzedToken(text="дома", lemma="дом", pos="NOUN", features={}, idx=2),
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
        the token/tag stream. Across many seeds the replacement must stay
        single-token.
        """
        for seed in range(100):
            tokens = [
                AnalyzedToken(
                    text="Из-за", lemma="из-за", pos="ADP", features={}, idx=0
                ),
                AnalyzedToken(
                    text="дождя", lemma="дождь", pos="NOUN", features={}, idx=1
                ),
            ]
            sentence = ["Из-за", "дождя"]
            modified = set()
            result = self.handler.apply(
                tokens, sentence, 0, modified, rng=random.Random(seed)
            )
            assert result is not None
            # The replaced token must remain a single surface token.
            assert " " not in sentence[0]
            assert " " not in result.corrupted
            assert result.corrupted != "по причине"

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
                AnalyzedToken(text="дома", lemma="дом", pos="NOUN", features={}, idx=2),
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
