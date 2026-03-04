import pymorphy3

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.lexical import (
    ConjunctionErrorHandler,
    ParonymErrorHandler,
    PrepositionErrorHandler,
)


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
            AnalyzedToken(text="надеть", lemma="надеть", pos="VERB", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text="технического", lemma="технический", pos="ADJF", features={}, idx=3),
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
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
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
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text="от", lemma="от", pos="ADP", features={}, idx=3),
        ]
        sentence = ["при", ".", "вопрос", "от"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified)
        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 3}


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
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
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
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text="чтобы", lemma="чтобы", pos="SCONJ", features={}, idx=3),
        ]
        sentence = ["и", "но", "вопрос", "чтобы"]
        modified = set()

        self.handler.apply(tokens, sentence, 0, modified)
        self.handler.apply(tokens, sentence, 1, modified)
        self.handler.apply(tokens, sentence, 2, modified)
        self.handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 1, 3}
