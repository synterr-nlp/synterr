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
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=0),
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
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=3),
        ]
        sentence = ["при", ".", "вопрос", "от"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 1, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 2, modified, rng=random.Random(0))
        self.handler.apply(tokens, sentence, 3, modified, rng=random.Random(0))
        assert modified == {0, 3}

        # The prepositions were actually replaced, not just flagged as modified.
        assert sentence[0] != "при"
        assert sentence[3] != "от"
        # Replacements must be real single-token prepositions from the lexicon.
        preps = get_preposition_list()
        all_preps = {w for group in preps.values() for w in group}
        for repl in (sentence[0], sentence[3]):
            assert " " not in repl
            assert repl in all_preps

    def test_no_multiword_replacement(self):
        """A length-preserving $REPLACE must never emit a multi-word token.

        ``около`` shares the ``spatial`` group with the multi-word entry
        ``"рядом с"``. Substituting that into a single token slot would smuggle
        an intra-token space into the GECToR unit and misalign the token/tag
        stream. Across many seeds the replacement must stay single-token.
        """
        for seed in range(100):
            tokens = [
                AnalyzedToken(
                    text="Стоял", lemma="стоять", pos="VERB", features={}, idx=0
                ),
                AnalyzedToken(
                    text="около", lemma="около", pos="ADP", features={}, idx=1
                ),
                AnalyzedToken(text="дома", lemma="дом", pos="NOUN", features={}, idx=2),
            ]
            sentence = ["Стоял", "около", "дома"]
            modified = set()
            result = self.handler.apply(
                tokens, sentence, 1, modified, rng=random.Random(seed)
            )
            assert result is not None
            # The replaced token must remain a single surface token.
            assert " " not in sentence[1]
            assert " " not in result.corrupted
            assert result.corrupted != "рядом с"

    def test_replacement_token_tag_consistent(self):
        """A single $REPLACE must keep token count == tag count.

        The corrupted token list, when joined and re-split on whitespace, must
        have exactly as many surface tokens as the original (one $REPLACE spans
        a single position), and the fix_tag must be one $REPLACE edit.
        """
        for seed in range(100):
            tokens = [
                AnalyzedToken(
                    text="Стоял", lemma="стоять", pos="VERB", features={}, idx=0
                ),
                AnalyzedToken(
                    text="около", lemma="около", pos="ADP", features={}, idx=1
                ),
                AnalyzedToken(text="дома", lemma="дом", pos="NOUN", features={}, idx=2),
            ]
            sentence = ["Стоял", "около", "дома"]
            result = self.handler.apply(
                tokens, sentence, 1, set(), rng=random.Random(seed)
            )
            assert result is not None
            # No element of the corrupted list carries an intra-token space, so
            # joining and re-splitting recovers the same token count.
            assert len(" ".join(sentence).split()) == len(sentence)
            assert result.fix_tag == "$REPLACE_около"
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
            AnalyzedToken(text="и", lemma="и", pos="CCONJ", features={}, idx=0),
            AnalyzedToken(text="но", lemma="но", pos="CCONJ", features={}, idx=1),
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
            AnalyzedToken(text="и", lemma="и", pos="CCONJ", features={}, idx=0),
            AnalyzedToken(text="но", lemma="но", pos="CCONJ", features={}, idx=1),
            AnalyzedToken(
                text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2
            ),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=3),
        ]
        sentence = ["и", "но", "вопрос", "чтобы"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified)
        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 1, 3}
