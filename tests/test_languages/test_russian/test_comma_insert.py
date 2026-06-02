"""Tests for CommaInsertHandler."""

from random import Random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.comma_insert import CommaInsertHandler


def _tok(
    text, pos="NOUN", lemma=None, idx=0, dep_rel=None, head_idx=None, features=None
):
    return AnalyzedToken(
        text=text,
        lemma=lemma or text.lower(),
        pos=pos,
        features=features or {},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )


def _force_subtype(subtype: str) -> CommaInsertHandler:
    h = CommaInsertHandler()
    weights = {s: 0 for s in h.subtypes}
    weights[subtype] = 100
    h.set_subtype_weights(weights)
    return h


class TestProtocol:
    handler = CommaInsertHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "comma_insert"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5


class TestCommaBeforeKak:
    """Insert comma before "как" where it shouldn't be."""

    def test_can_apply_kak_after_verb(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("работал", pos="VERB", idx=0),
            _tok("как", pos="SCONJ", idx=1),
            _tok("экономист", pos="NOUN", idx=2),
        ]
        assert handler.can_apply(tokens, 1)

    def test_cannot_apply_kak_already_preceded_by_comma(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok(",", pos="PUNCT", idx=0),
            _tok("как", pos="SCONJ", idx=1),
        ]
        assert not handler.can_apply(tokens, 1)

    def test_insert_comma_before_kak(self):
        h = _force_subtype("comma_before_kak")
        tokens = [
            _tok("работал", pos="VERB", idx=0),
            _tok("как", pos="SCONJ", idx=1),
            _tok("экономист", pos="NOUN", idx=2),
        ]
        sentence = ["работал", "как", "экономист"]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["работал", ",", "как", "экономист"]
        assert result.fix_tag == "$DELETE"

    def test_kak_at_start_not_applicable(self):
        handler = CommaInsertHandler()
        tokens = [_tok("как", pos="SCONJ", idx=0)]
        assert not handler.can_apply(tokens, 0)

    def test_real_stanza_mark_appositive_fires(self):
        """Real stanza output: appositive «как» is dep_rel=mark with a nominal head.

        "Лес стоял как стена." → stanza tags "как" as mark, head=стена (NOUN),
        no finite verb after «как». A comma here is an error → handler must fire.
        """
        handler = CommaInsertHandler()
        tokens = [
            _tok("Лес", pos="NOUN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "стоял",
                pos="VERB",
                idx=1,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("как", pos="SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok("стена", pos="NOUN", idx=3, dep_rel="advcl", head_idx=1),
            _tok(".", pos="PUNCT", idx=4, dep_rel="punct", head_idx=1),
        ]
        assert handler.can_apply(tokens, 2)

    def test_real_stanza_mark_appositive_after_obj_fires(self):
        """ "Я знаю его как честного человека." — mark, head=человека (NOUN)."""
        handler = CommaInsertHandler()
        tokens = [
            _tok("Я", pos="PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "знаю", pos="VERB", idx=1, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("его", pos="PRON", idx=2, dep_rel="obj", head_idx=1),
            _tok("как", pos="SCONJ", idx=3, dep_rel="mark", head_idx=5),
            _tok("честного", pos="ADJ", idx=4, dep_rel="amod", head_idx=5),
            _tok("человека", pos="NOUN", idx=5, dep_rel="obl", head_idx=1),
            _tok(".", pos="PUNCT", idx=6, dep_rel="punct", head_idx=1),
        ]
        assert handler.can_apply(tokens, 3)

    def test_real_stanza_mark_clause_skips(self):
        """Real stanza output: clausal «как» is dep_rel=mark with a VERBAL head.

        "Я помню, как мы встретились." → "как" is mark, head=встретились (VERB).
        The comma is correct, so the handler must NOT insert a spurious one.
        """
        handler = CommaInsertHandler()
        tokens = [
            _tok("Я", pos="PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "помню", pos="VERB", idx=1, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("как", pos="SCONJ", idx=2, dep_rel="mark", head_idx=4),
            _tok("мы", pos="PRON", idx=3, dep_rel="nsubj", head_idx=4),
            _tok(
                "встретились",
                pos="VERB",
                idx=4,
                dep_rel="ccomp",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
            _tok(".", pos="PUNCT", idx=5, dep_rel="punct", head_idx=1),
        ]
        assert not handler.can_apply(tokens, 2)

    def test_real_stanza_mark_nominal_head_but_finite_verb_after_skips(self):
        """Nominal head but a finite verb follows → subordinate clause → skip.

        Guard against firing when "как" introduces a clause whose nominal subject
        precedes its finite verb (e.g. "..., как небо потемнело"): the trailing
        finite verb vetoes the appositive reading.
        """
        handler = CommaInsertHandler()
        # A leading verb makes idx > 0 so the comma-before-«как» branch is reached.
        tokens = [
            _tok(
                "видел", pos="VERB", idx=0, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("как", pos="SCONJ", idx=1, dep_rel="mark", head_idx=3),
            _tok("небо", pos="NOUN", idx=2, dep_rel="nsubj", head_idx=3),
            _tok(
                "потемнело",
                pos="VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert not handler.can_apply(tokens, 1)

    def test_real_stanza_mark_appositive_inserts_comma(self):
        """End-to-end apply on the mark/nominal-head appositive sense."""
        h = _force_subtype("comma_before_kak")
        tokens = [
            _tok("Лес", pos="NOUN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "стоял",
                pos="VERB",
                idx=1,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("как", pos="SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok("стена", pos="NOUN", idx=3, dep_rel="advcl", head_idx=1),
            _tok(".", pos="PUNCT", idx=4, dep_rel="punct", head_idx=1),
        ]
        sentence = ["Лес", "стоял", "как", "стена", "."]
        result = h.apply(tokens, sentence, 2, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Лес", "стоял", ",", "как", "стена", "."]
        assert result.fix_tag == "$DELETE"


class TestCommaInSetPhrase:
    """Insert comma inside repeated conjunction set phrases."""

    def test_can_apply_repeated_ni(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("ни", pos="PART", idx=0),
            _tok("слуху", pos="NOUN", idx=1),
            _tok("ни", pos="PART", idx=2),
            _tok("духу", pos="NOUN", idx=3),
        ]
        assert handler.can_apply(tokens, 0)

    def test_insert_comma_in_ni_ni(self):
        h = _force_subtype("comma_in_set_phrase")
        tokens = [
            _tok("ни", pos="PART", idx=0),
            _tok("слуху", pos="NOUN", idx=1),
            _tok("ни", pos="PART", idx=2),
            _tok("духу", pos="NOUN", idx=3),
        ]
        sentence = ["ни", "слуху", "ни", "духу"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["ни", "слуху", ",", "ни", "духу"]

    def test_insert_comma_in_i_i(self):
        h = _force_subtype("comma_in_set_phrase")
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("стар", pos="ADJ", idx=1),
            _tok("и", pos="CCONJ", idx=2),
            _tok("млад", pos="ADJ", idx=3),
        ]
        sentence = ["и", "стар", "и", "млад"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["и", "стар", ",", "и", "млад"]

    def test_no_repeated_conjunction(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("стар", pos="ADJ", idx=1),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_already_has_comma(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok(",", pos="PUNCT", idx=1),
            _tok("стар", pos="ADJ", idx=2),
            _tok("и", pos="CCONJ", idx=3),
        ]
        # comma already after и → should not apply
        assert not handler.can_apply(tokens, 0)


class TestCommaBetweenConjunctions:
    """Insert comma between adjacent conjunctions."""

    def test_can_apply_i_kogda_with_correlative(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
            _tok("пришли", pos="VERB", idx=3),
            _tok("то", pos="PART", idx=4),
        ]
        assert handler.can_apply(tokens, 0)

    def test_cannot_apply_without_correlative(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_insert_comma_i_kogda(self):
        h = _force_subtype("comma_between_conjunctions")
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("когда", pos="SCONJ", idx=1),
            _tok("мы", pos="PRON", idx=2),
            _tok("пришли", pos="VERB", idx=3),
            _tok("то", pos="PART", idx=4),
        ]
        sentence = ["и", "когда", "мы", "пришли", "то"]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["и", ",", "когда", "мы", "пришли", "то"]

    def test_no_when_not_adjacent_conjunctions(self):
        handler = CommaInsertHandler()
        tokens = [
            _tok("и", pos="CCONJ", idx=0),
            _tok("дом", pos="NOUN", idx=1),
        ]
        assert not handler.can_apply(tokens, 0)

    def test_a_chto_with_correlative(self):
        h = _force_subtype("comma_between_conjunctions")
        tokens = [
            _tok("а", pos="CCONJ", idx=0),
            _tok("что", pos="SCONJ", idx=1),
            _tok("он", pos="PRON", idx=2),
            _tok("так", pos="ADV", idx=3),
        ]
        sentence = ["а", "что", "он", "так"]
        h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert sentence == ["а", ",", "что", "он", "так"]


class TestCanApplyEdgeCases:
    handler = CommaInsertHandler()

    def test_non_target_word(self):
        tokens = [_tok("дом", pos="NOUN", idx=0)]
        assert not self.handler.can_apply(tokens, 0)
