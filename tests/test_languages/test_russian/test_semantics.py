"""Tests for semantic handlers (pleonasm, collocation).

These are unit-level using hand-built AnalyzedToken lists, but the inflection
paths exercise the real pymorphy3 analyzer, so they catch the citation-form
bugs found in the 2026-05-27 audit.
"""

import pymorphy3
import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.semantics import (
    CollocationHandler,
    PleonasmHandler,
)

_morph = pymorphy3.MorphAnalyzer()


def _tok(text, pos="NOUN", lemma=None, idx=0):
    """Build a token with a real pymorphy parse in extra (matches backend)."""
    parses = _morph.parse(text)
    parse = parses[0] if parses else None
    return AnalyzedToken(
        text=text,
        lemma=lemma or (parse.normal_form if parse else text.lower()),
        pos=pos,
        features={},
        idx=idx,
        extra={"pymorphy_parse": parse},
    )


class TestPleonasmHandler:
    handler = PleonasmHandler()

    def test_protocol(self):
        assert self.handler.name == "pleonasm"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is True

    def test_inserts_and_agrees(self):
        # "прочитал автобиографию" → insert "свою" agreeing in case (accs/femn)
        tokens = [
            _tok("прочитал", pos="VERB", idx=0),
            _tok("автобиографию", lemma="автобиография", idx=1),
        ]
        sentence = ["прочитал", "автобиографию"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        # Inserted modifier should agree (свою), not be the citation form своя
        assert "свою" in sentence
        assert sentence == ["прочитал", "свою", "автобиографию"]

    def test_skips_when_redundant_already_present_inflected(self):
        # "написал свою автобиографию" — "свою" (lemma свой) already there.
        # The data's redundant form is "своя"; lemma-level guard must catch it.
        tokens = [
            _tok("написал", pos="VERB", idx=0),
            _tok("свою", pos="NPRO", lemma="свой", idx=1),
            _tok("автобиографию", lemma="автобиография", idx=2),
        ]
        assert self.handler.can_apply(tokens, 2) is False
        sentence = ["написал", "свою", "автобиографию"]
        assert self.handler.apply(tokens, sentence, 2, set()) is None

    def test_no_apply_for_unknown_word(self):
        tokens = [_tok("стол", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False


class TestCollocationHandler:
    handler = CollocationHandler()

    def test_protocol(self):
        assert self.handler.name == "collocation"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is False

    def test_replacement_is_inflected_not_citation(self):
        # "принял решение" → "сделал решение" (finite past), NOT "сделать"
        tokens = [
            _tok("принял", pos="VERB", lemma="принять", idx=0),
            _tok("решение", lemma="решение", idx=1),
        ]
        if not self.handler.can_apply(tokens, 0):
            pytest.skip("collocation lexicon does not contain принять/решение pair")
        sentence = ["принял", "решение"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        # Must not be the bare infinitive
        assert sentence[0] != "сделать"
        # Should be a past-tense finite form
        assert sentence[0].endswith("л") or sentence[0].endswith("ла")

    def test_inflected_collocate_entry_fires_oderzhat(self):
        # Lexicon stores the accusative collocate "победу"; the noun token's
        # lemma is "победа". Load-time lemmatization must make these match so
        # this previously-dead verb fires.
        tokens = [
            _tok("одержала", pos="VERB", lemma="одержать", idx=0),
            _tok("победу", lemma="победа", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["одержала", "победу"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] != "одержала"
        # Inflected to match the past feminine original, not a bare infinitive.
        assert not sentence[0].endswith("ть")

    def test_inflected_collocate_entry_fires_vyzvat(self):
        # "вызвало реакцию" — collocate stored as accusative "реакцию".
        tokens = [
            _tok("вызвало", pos="VERB", lemma="вызвать", idx=0),
            _tok("реакцию", lemma="реакция", idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is True
        sentence = ["вызвало", "реакцию"]
        result = self.handler.apply(tokens, sentence, 0, set())
        assert result is not None
        assert sentence[0] != "вызвало"
        assert not sentence[0].endswith("ть")
