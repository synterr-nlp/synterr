"""Tests for the sy_-family syntax handlers."""

from random import Random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.syntax import PrepRepeatHandler


def _tok(text, pos, lemma=None, idx=0, dep_rel=None, head_idx=None, features=None):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features=features or {},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )


def _repeating_chain():
    """«Недостачу испытывали и в машинах , и в сырье .» — §207 п.1 shape."""
    return [
        _tok("Недостачу", "NOUN", idx=0, dep_rel="obj", head_idx=1),
        _tok("испытывали", "VERB", idx=1, dep_rel="root"),
        _tok("и", "PART", idx=2, dep_rel="advmod", head_idx=4),
        _tok("в", "ADP", idx=3, dep_rel="case", head_idx=4),
        _tok("машинах", "NOUN", idx=4, dep_rel="obl", head_idx=1),
        _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=8),
        _tok("и", "CCONJ", idx=6, dep_rel="cc", head_idx=8),
        _tok("в", "ADP", idx=7, dep_rel="case", head_idx=8),
        _tok("сырье", "NOUN", idx=8, dep_rel="conj", head_idx=4),
        _tok(".", "PUNCT", idx=9, dep_rel="punct", head_idx=1),
    ]


class TestPrepRepeat:
    handler = PrepRepeatHandler()

    def test_protocol(self):
        assert self.handler.name == "prep_repeat"
        assert self.handler.category == "OTHER"
        assert self.handler.changes_length is True

    def test_fires_on_second_conjunct_preposition(self):
        tokens = _repeating_chain()
        assert self.handler.can_apply(tokens, 7)

    def test_never_touches_first_conjunct_preposition(self):
        tokens = _repeating_chain()
        assert not self.handler.can_apply(tokens, 3)

    def test_apply_deletes_preposition(self):
        tokens = _repeating_chain()
        sentence = [t.text for t in tokens]
        result = self.handler.apply(tokens, sentence, 7, set(), rng=Random(42))
        assert result is not None
        assert result.error_type == "prep_repeat"
        assert result.fix_tag == "$APPEND_в"
        assert sentence == [
            "Недостачу",
            "испытывали",
            "и",
            "в",
            "машинах",
            ",",
            "и",
            "сырье",
            ".",
        ]

    def test_skips_bare_coordination(self):
        # «по почерку и по количеству» — repetition optional (audit C14
        # territory), deleting is a non-error → must not fire
        tokens = [
            _tok("Судили", "VERB", idx=0, dep_rel="root"),
            _tok("по", "ADP", idx=1, dep_rel="case", head_idx=2),
            _tok("почерку", "NOUN", idx=2, dep_rel="obl", head_idx=0),
            _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=5),
            _tok("по", "ADP", idx=4, dep_rel="case", head_idx=5),
            _tok("количеству", "NOUN", idx=5, dep_rel="conj", head_idx=2),
        ]
        assert not self.handler.can_apply(tokens, 4)

    def test_skips_mixed_prepositions(self):
        # «и в машинах, и на складах» — no single repeated preposition
        tokens = _repeating_chain()
        tokens[3] = _tok("на", "ADP", idx=3, dep_rel="case", head_idx=4)
        assert not self.handler.can_apply(tokens, 7)

    def test_skips_without_comma(self):
        # malformed/unpunctuated repeating union — refuse rather than guess
        tokens = _repeating_chain()
        tokens[5] = _tok("же", "PART", idx=5, dep_rel="advmod", head_idx=7)
        assert not self.handler.can_apply(tokens, 7)

    def test_apply_refuses_when_anchor_modified(self):
        tokens = _repeating_chain()
        sentence = [t.text for t in tokens]
        assert self.handler.apply(tokens, sentence, 7, {6}, rng=Random(42)) is None
