from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.punctuation import (
    CommaDeleteHandler,
    DashDeleteHandler,
    _classify_comma,
    _classify_dash,
)


# ── Helper to build tokens quickly ──────────────────────────────────────────

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


# ── CommaDeleteHandler ─────────────────────────────────────────────────────

class TestCommaDeleteHandler:
    handler = CommaDeleteHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "comma_delete"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5

    def test_can_apply_comma_only(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("папа", "NOUN", idx=2),
            _tok(".", "PUNCT", idx=3),
            _tok("—", "PUNCT", idx=4),
        ]
        assert self.handler.can_apply(tokens, 0) is False  # not PUNCT
        assert self.handler.can_apply(tokens, 1) is True   # comma
        assert self.handler.can_apply(tokens, 2) is False  # NOUN
        assert self.handler.can_apply(tokens, 3) is False  # period, not comma
        assert self.handler.can_apply(tokens, 4) is False  # dash, not comma

    def test_can_apply_rejects_first_token(self):
        tokens = [_tok(",", "PUNCT", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False

    def test_apply_deletes_comma(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("папа", "NOUN", idx=2),
        ]
        sentence = ["Мама", ",", "папа"]
        result = self.handler.apply(tokens, sentence, 1, set())

        assert result is not None
        assert result.fix_tag == "$APPEND_,"
        assert result.original == ","
        assert result.corrupted == ""
        assert result.category == "PUNCT"
        assert sentence == ["Мама", "папа"]  # comma deleted

    def test_apply_returns_none_for_non_comma(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok(".", "PUNCT", idx=1),
        ]
        sentence = ["Мама", "."]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None


# ── Comma classification ────────────────────────────────────────────────────

class TestClassifyComma:
    def test_subordinate_before_sconj(self):
        # "Я знаю, что он пришёл"
        tokens = [
            _tok("знаю", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("что", "SCONJ", idx=2),
            _tok("он", "PRON", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_subordinate_before_когда(self):
        tokens = [
            _tok("ушёл", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("когда", "SCONJ", idx=2),
            _tok("стемнело", "VERB", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_compound_before_cconj_with_verbs(self):
        # "Мама мыла, а папа читал"
        tokens = [
            _tok("мыла", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("а", "CCONJ", idx=2),
            _tok("папа", "NOUN", idx=3),
            _tok("читал", "VERB", idx=4),
        ]
        assert _classify_comma(tokens, 1) == "comma_compound"

    def test_cconj_without_verbs_falls_through(self):
        # "яблоки, и груши" (homogeneous, no verb on right)
        tokens = [
            _tok("яблоки", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("и", "CCONJ", idx=2),
            _tok("груши", "NOUN", idx=3),
        ]
        # No finite verb on right side → not compound → falls to homogeneous
        assert _classify_comma(tokens, 1) == "comma_homogeneous"

    def test_parenthetical_right(self):
        tokens = [
            _tok("Он", "PRON", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("конечно", "ADV", lemma="конечно", idx=2),
            _tok(",", "PUNCT", idx=3),
            _tok("прав", "ADJ", idx=4),
        ]
        assert _classify_comma(tokens, 1) == "comma_parenthetical"

    def test_parenthetical_left(self):
        tokens = [
            _tok("Он", "PRON", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("конечно", "ADV", lemma="конечно", idx=2),
            _tok(",", "PUNCT", idx=3),
            _tok("прав", "ADJ", idx=4),
        ]
        # The closing comma after "конечно"
        assert _classify_comma(tokens, 3) == "comma_parenthetical"

    def test_isolation_participle(self):
        # "Студент, читающий книгу, ушёл"
        tokens = [
            _tok("Студент", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("читающий", "VERB", features={"VerbForm": "Part"}, idx=2),
            _tok("книгу", "NOUN", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_isolation_gerund(self):
        tokens = [
            _tok("шёл", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("напевая", "VERB", features={"VerbForm": "Conv"}, idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_isolation_advcl(self):
        tokens = [
            _tok("работал", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("пока", "SCONJ", dep_rel="advcl", idx=2),
        ]
        # advcl wins over subordinate because we check dep_rel...
        # Actually subordinate check comes first in priority. Let's verify.
        # "пока" is SCONJ → subordinate wins.
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_isolation_by_dep_rel_acl(self):
        tokens = [
            _tok("дом", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("построенный", "VERB", dep_rel="acl", features={"VerbForm": "Part"}, idx=2),
        ]
        # "построенный" is not SCONJ, not CCONJ, not parenthetical → isolation via dep_rel
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_isolation_closing_comma_participle_phrase(self):
        # "колонна, отступавшая по шоссе, обстреливалась"
        # The closing comma (idx=5) should be isolation, not homogeneous.
        tokens = [
            _tok("колонна", "NOUN", idx=0, dep_rel="nsubj", head_idx=6),
            _tok(",", "PUNCT", idx=1),
            _tok("отступавшая", "VERB", features={"VerbForm": "Part"}, idx=2,
                 dep_rel="acl", head_idx=0),
            _tok("по", "ADP", idx=3),
            _tok("шоссе", "NOUN", idx=4),
            _tok(",", "PUNCT", idx=5),
            _tok("обстреливалась", "VERB", idx=6),
        ]
        assert _classify_comma(tokens, 5) == "comma_isolation"

    def test_isolation_closing_comma_gerund_phrase(self):
        # "приблизившись к крепости, начал борьбу"
        tokens = [
            _tok("приблизившись", "VERB", features={"VerbForm": "Conv"}, idx=0,
                 dep_rel="advcl", head_idx=3),
            _tok("к", "ADP", idx=1),
            _tok("крепости", "NOUN", idx=2),
            _tok(",", "PUNCT", idx=3),
            _tok("начал", "VERB", idx=4),
        ]
        # Opening comma is at idx=3, gerund is at idx=0 with head_idx=4 (>= comma idx)
        # Wait, head_idx=3 which is the comma... let me fix: head should be "начал" = idx 4
        tokens[0] = _tok("приблизившись", "VERB", features={"VerbForm": "Conv"}, idx=0,
                         dep_rel="advcl", head_idx=4)
        assert _classify_comma(tokens, 3) == "comma_isolation"

    def test_homogeneous_fallback(self):
        # "красный, синий, зелёный"
        tokens = [
            _tok("красный", "ADJ", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("синий", "ADJ", idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_homogeneous"


# ── DashDeleteHandler ───────────────────────────────────────────────────────

class TestDashDeleteHandler:
    handler = DashDeleteHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "dash_delete"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 2

    def test_can_apply_dash_only(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("врач", "NOUN", idx=2),
            _tok(",", "PUNCT", idx=3),
        ]
        assert self.handler.can_apply(tokens, 0) is False  # NOUN
        assert self.handler.can_apply(tokens, 1) is True   # em-dash
        assert self.handler.can_apply(tokens, 2) is False  # NOUN
        assert self.handler.can_apply(tokens, 3) is False  # comma

    def test_can_apply_en_dash(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok("–", "PUNCT", idx=1),
            _tok("врач", "NOUN", idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is True

    def test_can_apply_rejects_first_token(self):
        tokens = [_tok("—", "PUNCT", idx=0)]
        assert self.handler.can_apply(tokens, 0) is False

    def test_apply_deletes_dash(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("врач", "NOUN", idx=2),
        ]
        sentence = ["Мама", "—", "врач"]
        result = self.handler.apply(tokens, sentence, 1, set())

        assert result is not None
        assert result.fix_tag == "$APPEND_—"
        assert result.category == "PUNCT"
        assert sentence == ["Мама", "врач"]


# ── Dash classification ─────────────────────────────────────────────────────

class TestClassifyDash:
    def test_subj_pred_noun_noun(self):
        # "Москва — столица"
        tokens = [
            _tok("Москва", "PROPN", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("столица", "NOUN", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_subj_pred_pron_adj(self):
        tokens = [
            _tok("Он", "PRON", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("хороший", "ADJ", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_other_verb_verb(self):
        tokens = [
            _tok("пришёл", "VERB", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("увидел", "VERB", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_other"

    def test_other_at_end(self):
        tokens = [
            _tok("слово", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
        ]
        assert _classify_dash(tokens, 1) == "dash_other"
