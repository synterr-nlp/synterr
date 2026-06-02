from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.structural import (
    WordInsertionHandler,
    WordOmissionHandler,
)


class TestWordOmissionHandler:
    handler = WordOmissionHandler()

    def test_implements_protocol(self):
        """Test WordOmissionHandler implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "word_omission"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is True

    def test_can_apply_detect_index_and_pos_correctly(self):
        """Test WordOmissionHandler check index and detect POS correctly."""
        tokens = [
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=0),
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=1),
            AnalyzedToken(text=",", lemma=".", pos="PUNCT", features={}, idx=2),
            AnalyzedToken(text="не", lemma="не", pos="PART", features={}, idx=3),
            AnalyzedToken(text="и", lemma="и", pos="CCONJ", features={}, idx=4),
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=5),
            AnalyzedToken(
                text="зелёный", lemma="зелёный", pos="ADJF", features={}, idx=6
            ),
            AnalyzedToken(text="пойдёт", lemma="пойти", pos="VERB", features={}, idx=7),
        ]

        assert self.handler.can_apply(tokens, 0) is False
        assert self.handler.can_apply(tokens, 1) is True
        assert (
            self.handler.can_apply(tokens, 2) is False
        )  # PUNCT handled by punct handlers
        assert self.handler.can_apply(tokens, 3) is True
        assert self.handler.can_apply(tokens, 4) is True
        assert self.handler.can_apply(tokens, 5) is True
        assert self.handler.can_apply(tokens, 6) is False
        assert self.handler.can_apply(tokens, 7) is False

    def test_apply_delete_word_correctly(self):
        """Test WordOmissionHandler delete word correctly."""
        tokens = [
            AnalyzedToken(
                text="космический", lemma="космический", pos="ADJF", features={}, idx=0
            ),
            AnalyzedToken(
                text="корабль", lemma="корабль", pos="NOUN", features={}, idx=1
            ),
            AnalyzedToken(text="летит", lemma="лететь", pos="VERB", features={}, idx=2),
            AnalyzedToken(text="на", lemma="на", pos="ADP", features={}, idx=3),
            AnalyzedToken(text="Луну", lemma="Луна", pos="NOUN", features={}, idx=4),
        ]
        sentence = ["космический", "корабль", "летит", "на", "Луну"]
        modified = set()

        assert self.handler.apply(tokens, sentence, 0, modified) is None
        assert self.handler.apply(tokens, sentence, 1, modified) is None
        assert self.handler.apply(tokens, sentence, 2, modified) is None
        assert self.handler.apply(tokens, sentence, 3, modified).fix_tag.startswith(
            "$APPEND"
        )
        assert self.handler.apply(tokens, sentence, 4, modified) is None


class TestWordInsertionError:
    handler = WordInsertionHandler()

    def test_implements_protocol(self):
        """Test WordInsertion implements protocol."""
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")
        assert self.handler.name == "word_insertion"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is True

    def test_can_apply_detect_index_and_pos_correctly(self):
        """Test wordInsertion check index correctly."""
        tokens = [
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=0),
            AnalyzedToken(text="при", lemma="при", pos="ADP", features={}, idx=1),
            AnalyzedToken(text=",", lemma=".", pos="PUNCT", features={}, idx=2),
            AnalyzedToken(text="не", lemma="не", pos="PART", features={}, idx=3),
            AnalyzedToken(text="и", lemma="и", pos="CCONJ", features={}, idx=4),
            AnalyzedToken(text="что", lemma="что", pos="SCONJ", features={}, idx=5),
            AnalyzedToken(
                text="зелёный", lemma="зелёный", pos="ADJF", features={}, idx=6
            ),
            AnalyzedToken(text="пойдёт", lemma="пойти", pos="VERB", features={}, idx=7),
        ]

        assert self.handler.can_apply(tokens, 0) is True
        assert self.handler.can_apply(tokens, 1) is True
        assert self.handler.can_apply(tokens, 2) is True
        assert self.handler.can_apply(tokens, 3) is True
        assert self.handler.can_apply(tokens, 4) is True
        assert self.handler.can_apply(tokens, 5) is True
        assert self.handler.can_apply(tokens, 6) is True
        assert self.handler.can_apply(tokens, 7) is False

    def test_apply_delete_word_correctly(self):
        """Test WordInsertion insert word correctly."""
        tokens = [
            AnalyzedToken(
                text="космический", lemma="космический", pos="ADJF", features={}, idx=0
            ),
            AnalyzedToken(
                text="корабль", lemma="корабль", pos="NOUN", features={}, idx=1
            ),
            AnalyzedToken(text="летит", lemma="лететь", pos="VERB", features={}, idx=2),
            AnalyzedToken(text="на", lemma="на", pos="ADP", features={}, idx=3),
            AnalyzedToken(text="Луну", lemma="Луна", pos="NOUN", features={}, idx=4),
        ]
        sentence = ["космический", "корабль", "летит", "на", "Луну"]
        modified = set()

        assert self.handler.apply(tokens, sentence, 0, modified).fix_tag.startswith(
            "$DELETE"
        )
        assert self.handler.apply(tokens, sentence, 1, modified).fix_tag.startswith(
            "$DELETE"
        )
        assert self.handler.apply(tokens, sentence, 2, modified).fix_tag.startswith(
            "$DELETE"
        )
        assert self.handler.apply(tokens, sentence, 3, modified).fix_tag.startswith(
            "$DELETE"
        )
        assert self.handler.apply(tokens, sentence, 4, modified) is None

    def test_lexicon_has_no_whitespace_fillers(self):
        """All fillers must be single GECToR tokens (no embedded whitespace).

        GECToR output is whitespace-tokenized, so a filler with a space would
        occupy one corrupted-token slot (one $DELETE) yet split into two tokens
        downstream — an off-by-one tag/token misalignment.
        """
        for filler in self.handler.fillers:
            assert filler.split() == [filler], (
                f"multi-word filler {filler!r} would break token/tag alignment"
            )

    def test_guard_filters_multiword_fillers_from_raw_lexicon(self, monkeypatch):
        """A multi-word entry in fillers.json is dropped before reaching apply()."""
        import synterr.languages.russian.resources as resources

        monkeypatch.setattr(
            resources,
            "get_filler_list",
            lambda: ["вот", "как бы", "ну", "   ", ""],
        )
        handler = WordInsertionHandler()
        loaded = handler.fillers

        assert "как бы" not in loaded
        assert all(f.split() == [f] for f in loaded)
        assert loaded == ["вот", "ну"]

    def test_single_filler_insertion_is_token_tag_consistent(self):
        """Each inserted filler yields one corrupted token and exactly one $DELETE."""
        tokens = [
            AnalyzedToken(text="Мама", lemma="мама", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text="мыла", lemma="мыть", pos="VERB", features={}, idx=1),
            AnalyzedToken(text="раму", lemma="рама", pos="NOUN", features={}, idx=2),
        ]
        handler = WordInsertionHandler()

        for filler in handler.fillers:
            sentence = ["Мама", "мыла", "раму"]
            before = len(sentence)
            result = handler.apply(tokens, sentence, 0, set(), rng=_FixedChoice(filler))

            assert result is not None
            # Inserted exactly one corrupted-token slot...
            assert len(sentence) == before + 1
            # ...which is a single whitespace token...
            assert len(" ".join(sentence).split()) == before + 1
            # ...carrying exactly one $DELETE edit.
            assert result.fix_tag == "$DELETE"
            assert result.corrupted == filler
            assert result.corrupted.split() == [result.corrupted]


class _FixedChoice:
    """Minimal rng stub: choice() always returns the configured value."""

    def __init__(self, value):
        self._value = value

    def choice(self, _seq):
        return self._value
