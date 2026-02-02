from synterr.languages.russian.errors.lexical import ParonymErrorHandler, PrepositionErrorHandler, ConjunctionErrorHandler
from synterr.core.protocol import AnalyzedToken

class TestParonymErrorHandler:
    def test_implements_protocol(self):
        handler = ParonymErrorHandler()
        assert hasattr(handler, "name")
        assert hasattr(handler, "category")
        assert hasattr(handler, "changes_length")
        assert hasattr(handler, "can_apply")
        assert hasattr(handler, "apply")
        assert handler.name == "paronym"
        assert handler.category == "OTHER"
        assert handler.changes_length is False

    def test_can_apply_finds_paronyms(self):
        handler = ParonymErrorHandler()

        tokens = [
            AnalyzedToken(text="надеть", lemma="надеть", pos="VERB", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text="технического", lemma="технический", pos="ADJF", features={}, idx=3),
        ]

        assert handler.can_apply(tokens, 0) is True
        assert handler.can_apply(tokens, 1) is False
        assert handler.can_apply(tokens, 2) is False
        assert handler.can_apply(tokens, 3) is True

    def test_apply_substitutes_correctly(self):
        handler = ParonymErrorHandler()

        tokens = [
            AnalyzedToken(text="надеть", lemma="надеть", pos="VERB", features={}, idx=0),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=1),
            AnalyzedToken(text="вопрос", lemma="вопрос", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text="технического", lemma="технический", pos="ADJF", features={}, idx=3),
        ]
        sentence = ["надеть", ".", "вопрос", "технического"]
        modified = set()

        print(handler.apply(tokens, sentence, 0, modified))
        handler.apply(tokens, sentence, 1, modified)
        handler.apply(tokens, sentence, 2, modified)
        handler.apply(tokens, sentence, 3, modified)
        assert modified == {0, 3}


class TestPrepositionErrorHandler:
    def test_implements_protocol(self):
        handler = PrepositionErrorHandler()
        assert hasattr(handler, "name")
        assert hasattr(handler, "category")
        assert hasattr(handler, "changes_length")
        assert hasattr(handler, "can_apply")
        assert hasattr(handler, "apply")
        assert handler.name == "preposition"
        assert handler.category == "OTHER"
        assert handler.changes_length is False

    def test_can_apply_finds_prepositions(self):
        ...

    def test_apply_substitutes_correctly(self):
        ...

class TestConjunctionErrorHandler:
    def test_implements_protocol(self):
        handler = ConjunctionErrorHandler()
        assert hasattr(handler, "name")
        assert hasattr(handler, "category")
        assert hasattr(handler, "changes_length")
        assert hasattr(handler, "can_apply")
        assert hasattr(handler, "apply")
        assert handler.name == "conjunction"
        assert handler.category == "OTHER"
        assert handler.changes_length is False

    def test_can_apply_finds_conjunctions(self):
        ...

    def test_apply_substitutes_correctly(self):
        ...