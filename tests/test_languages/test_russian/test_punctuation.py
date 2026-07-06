import pytest

from synterr.core.protocol import AnalyzedToken
from synterr.languages.russian.errors.punctuation import (
    CommaDeleteHandler,
    CommaPairDeleteHandler,
    DashDeleteHandler,
    DashToCommaHandler,
    _classify_comma,
    _classify_dash,
    _find_comma_partner,
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
        assert len(self.handler.subtypes) == 10
        assert "comma_asyndetic" in self.handler.subtypes
        assert "comma_vocative" in self.handler.subtypes

    def test_can_apply_comma_only(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("папа", "NOUN", idx=2),
            _tok(".", "PUNCT", idx=3),
            _tok("—", "PUNCT", idx=4),
        ]
        assert self.handler.can_apply(tokens, 0) is False  # not PUNCT
        assert self.handler.can_apply(tokens, 1) is True  # comma
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
        assert sentence == ["Мама", "папа"]

    def test_apply_returns_none_for_non_comma(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok(".", "PUNCT", idx=1),
        ]
        sentence = ["Мама", "."]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is None


# ── Comma classification: dep-tree based ────────────────────────────────────


class TestClassifyCommaDepTree:
    """Tests using realistic dep tree annotations (matching stanza output)."""

    def test_subordinate_ccomp(self):
        # "Он знал, что она придёт" — comma head → ccomp verb
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("знал", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("что", "SCONJ", idx=3, dep_rel="mark", head_idx=5),
            _tok("она", "PRON", idx=4, dep_rel="nsubj", head_idx=5),
            _tok("придёт", "VERB", idx=5, dep_rel="ccomp", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_subordinate"

    def test_subordinate_advcl_finite_clause(self):
        # "уехал, когда стемнело" — advcl head is a finite verb (no VerbForm=Conv),
        # i.e. a subordinate clause, not a gerund isolation. The advcl guard in
        # _classify_comma routes finite advcl to comma_subordinate.
        tokens = [
            _tok("уехал", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("когда", "SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok(
                "стемнело",
                "VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_compound_conj_with_subjects(self):
        # "Солнце светило, и птицы пели"
        tokens = [
            _tok("Солнце", "PROPN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("светило", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=5),
            _tok("птицы", "NOUN", idx=4, dep_rel="nsubj", head_idx=5),
            _tok("пели", "VERB", idx=5, dep_rel="conj", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_compound"

    def test_homogeneous_conj_nouns(self):
        # "Мама, папа и бабушка пришли"
        tokens = [
            _tok("Мама", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("папа", "NOUN", idx=2, dep_rel="conj", head_idx=0),
            _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=4),
            _tok("бабушка", "NOUN", idx=4, dep_rel="conj", head_idx=0),
            _tok("пришли", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]
        assert _classify_comma(tokens, 1) == "comma_homogeneous"

    def test_parenthetical_parataxis(self):
        # "Он, конечно, был прав"
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok(
                "конечно",
                "ADV",
                lemma="конечно",
                idx=2,
                dep_rel="parataxis",
                head_idx=5,
            ),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=2),
            _tok("был", "AUX", idx=4, dep_rel="cop", head_idx=5),
            _tok("прав", "ADJ", idx=5, dep_rel="root", head_idx=None),
        ]
        # Opening comma (idx=1): head is "Он" (not parataxis) → falls to lemma check
        # But конечно is to the right → parenthetical via word list
        assert _classify_comma(tokens, 1) == "comma_parenthetical"
        # Closing comma (idx=3): head is "конечно" which has dep_rel=parataxis
        assert _classify_comma(tokens, 3) == "comma_parenthetical"

    def test_isolation_acl_opening(self):
        # "Студент, читающий книгу, ушёл"
        tokens = [
            _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "читающий",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", "NOUN", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok("ушёл", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]
        # Opening comma: head is "читающий" (acl) → isolation
        assert _classify_comma(tokens, 1) == "comma_isolation"
        # Closing comma: head is also "читающий" (acl) → isolation
        assert _classify_comma(tokens, 4) == "comma_isolation"

    def test_isolation_advcl_gerund(self):
        # "Приехав домой, он лёг спать"
        tokens = [
            _tok(
                "Приехав",
                "VERB",
                idx=0,
                dep_rel="advcl",
                head_idx=3,
                features={"VerbForm": "Conv"},
            ),
            _tok("домой", "ADV", idx=1, dep_rel="advmod", head_idx=0),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=0),
            _tok("он", "PRON", idx=3, dep_rel="nsubj", head_idx=4),
            _tok("лёг", "VERB", idx=4, dep_rel="root", head_idx=None),
        ]
        # Comma head is "Приехав" (advcl) → isolation
        assert _classify_comma(tokens, 2) == "comma_isolation"

    def test_subordinate_fronted_advcl_kogda(self):
        # "Когда стемнело, они вернулись домой." — fronted finite advcl clause.
        # The comma's head is the finite advcl verb (VerbForm=Fin), which must
        # classify as comma_subordinate, NOT comma_isolation. Matches stanza.
        tokens = [
            _tok("Когда", "SCONJ", idx=0, dep_rel="mark", head_idx=1),
            _tok(
                "стемнело",
                "VERB",
                idx=1,
                dep_rel="advcl",
                head_idx=4,
                features={"VerbForm": "Fin"},
            ),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=1),
            _tok("они", "PRON", idx=3, dep_rel="nsubj", head_idx=4),
            _tok("вернулись", "VERB", idx=4, dep_rel="root", head_idx=None),
            _tok("домой", "ADV", idx=5, dep_rel="advmod", head_idx=4),
        ]
        assert _classify_comma(tokens, 2) == "comma_subordinate"

    def test_subordinate_fronted_advcl_poskolku(self):
        # "Поскольку шёл дождь, мы остались дома." — fronted finite advcl.
        tokens = [
            _tok("Поскольку", "SCONJ", idx=0, dep_rel="mark", head_idx=1),
            _tok(
                "шёл",
                "VERB",
                idx=1,
                dep_rel="advcl",
                head_idx=5,
                features={"VerbForm": "Fin"},
            ),
            _tok("дождь", "NOUN", idx=2, dep_rel="nsubj", head_idx=1),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=1),
            _tok("мы", "PRON", idx=4, dep_rel="nsubj", head_idx=5),
            _tok("остались", "VERB", idx=5, dep_rel="root", head_idx=None),
            _tok("дома", "ADV", idx=6, dep_rel="advmod", head_idx=5),
        ]
        assert _classify_comma(tokens, 3) == "comma_subordinate"

    def test_compound_not_triggered_without_subject(self):
        # "яблоки, и груши" — conj but no subject on conj side
        tokens = [
            _tok("яблоки", "NOUN", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("и", "CCONJ", idx=2, dep_rel="cc", head_idx=3),
            _tok("груши", "NOUN", idx=3, dep_rel="conj", head_idx=0),
        ]
        # Comma head is "груши" (conj), but not VERB → homogeneous
        assert _classify_comma(tokens, 1) == "comma_homogeneous"

    def test_isolation_closing_comma_subtree(self):
        # "колонна, отступавшая по шоссе, обстреливалась"
        # Closing comma at idx=5 — head is "отступавшая" (acl)
        tokens = [
            _tok("колонна", "NOUN", idx=0, dep_rel="nsubj", head_idx=6),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "отступавшая",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("по", "ADP", idx=3, dep_rel="case", head_idx=4),
            _tok("шоссе", "NOUN", idx=4, dep_rel="obl", head_idx=2),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=2),
            _tok("обстреливалась", "VERB", idx=6, dep_rel="root", head_idx=None),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"
        assert _classify_comma(tokens, 5) == "comma_isolation"


# ── Comma classification: POS/lemma fallbacks ───────────────────────────────


class TestClassifyCommaFallback:
    """Tests with minimal/no dep info — verify POS/lemma fallbacks work."""

    def test_subordinate_sconj_fallback(self):
        tokens = [
            _tok("знаю", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("что", "SCONJ", dep_rel="mark", idx=2),
            _tok("он", "PRON", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_parenthetical_word_list_fallback(self):
        tokens = [
            _tok("Он", "PRON", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("конечно", "ADV", lemma="конечно", idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_parenthetical"

    def test_isolation_participle_fallback(self):
        tokens = [
            _tok("Студент", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("читающий", "VERB", features={"VerbForm": "Part"}, idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_isolation_gerund_fallback(self):
        tokens = [
            _tok("шёл", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("напевая", "VERB", features={"VerbForm": "Conv"}, idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_homogeneous_shared_head_fallback(self):
        # Left and right share same head
        tokens = [
            _tok("красный", "ADJ", idx=0, head_idx=3),
            _tok(",", "PUNCT", idx=1),
            _tok("синий", "ADJ", idx=2, head_idx=3),
            _tok("шар", "NOUN", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_homogeneous"

    def test_homogeneous_bare_fallback(self):
        # No dep info at all
        tokens = [
            _tok("красный", "ADJ", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("синий", "ADJ", idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_homogeneous"

    def test_compound_cc_with_subject(self):
        # Fallback: CCONJ with cc dep_rel, head verb has subject
        tokens = [
            _tok("светило", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1),
            _tok("и", "CCONJ", idx=2, dep_rel="cc", head_idx=4),
            _tok("птицы", "NOUN", idx=3, dep_rel="nsubj", head_idx=4),
            _tok("пели", "VERB", idx=4, dep_rel="conj", head_idx=0),
        ]
        assert _classify_comma(tokens, 1) == "comma_compound"

    def test_isolation_closing_subtree_scan(self):
        # Closing comma: no head info on comma, but acl subtree ends at idx-1
        tokens = [
            _tok("колонна", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok(
                "отступавшая",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("по", "ADP", idx=3, dep_rel="case", head_idx=4),
            _tok("шоссе", "NOUN", idx=4, dep_rel="obl", head_idx=2),
            _tok(",", "PUNCT", idx=5),  # no head info
            _tok("обстреливалась", "VERB", idx=6),
        ]
        assert _classify_comma(tokens, 5) == "comma_isolation"


# ── New subtypes: §102 interjection / §103 response / §90 repeated ──────────


class TestClassifyCommaNewSubtypes:
    """§102 INTJ, §103 да/нет, §90 repeated words.

    These checks run in section 0 (before dep-tree classification) because
    their surface signals are more specific than the generic conj/punct
    dep-rels that would otherwise win.
    """

    # ── §102 — Interjection ────────────────────────────────────────────────

    def test_interjection_left(self):
        # "Ах, как жаль!"
        tokens = [
            _tok("Ах", "INTJ", lemma="ах", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("как", "ADV", idx=2),
            _tok("жаль", "ADV", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_interjection"

    def test_interjection_right(self):
        # "Уйдём, эх, далеко"
        tokens = [
            _tok("Уйдём", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("эх", "INTJ", lemma="эх", idx=2),
            _tok(",", "PUNCT", idx=3),
            _tok("далеко", "ADV", idx=4),
        ]
        assert _classify_comma(tokens, 1) == "comma_interjection"
        assert _classify_comma(tokens, 3) == "comma_interjection"

    def test_interjection_beats_dep_tree(self):
        # Even with dep info pointing elsewhere, INTJ neighbor wins.
        tokens = [
            _tok("Ах", "INTJ", lemma="ах", idx=0, dep_rel="discourse", head_idx=3),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("как", "ADV", idx=2, dep_rel="advmod", head_idx=3),
            _tok("жаль", "ADV", idx=3, dep_rel="root", head_idx=None),
        ]
        assert _classify_comma(tokens, 1) == "comma_interjection"

    # ── §103 — Affirmative / negative response ─────────────────────────────

    def test_response_da_sentence_start(self):
        # "Да, я согласен."
        tokens = [
            _tok("Да", "PART", lemma="да", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("я", "PRON", idx=2),
            _tok("согласен", "ADJ", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_response"

    def test_response_net_sentence_start(self):
        # "Нет, нельзя."
        tokens = [
            _tok("Нет", "PART", lemma="нет", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("нельзя", "ADV", idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_response"

    def test_response_da_not_at_start_not_response(self):
        # "Я хочу, да не могу." — да here is conjunction, not response.
        # Comma is between two clauses; left of comma is хочу (VERB), not да.
        tokens = [
            _tok("Я", "PRON", idx=0),
            _tok("хочу", "VERB", idx=1),
            _tok(",", "PUNCT", idx=2),
            _tok("да", "CCONJ", lemma="да", idx=3),
            _tok("не", "PART", idx=4),
            _tok("могу", "VERB", idx=5),
        ]
        # Must NOT classify as comma_response — left is хочу, not да.
        assert _classify_comma(tokens, 2) != "comma_response"

    # ── §90 — Repeated word ────────────────────────────────────────────────

    def test_repeated_noun(self):
        # "Дождь, дождь идёт."
        tokens = [
            _tok("Дождь", "NOUN", lemma="дождь", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("дождь", "NOUN", lemma="дождь", idx=2),
            _tok("идёт", "VERB", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_repeated"

    def test_repeated_verb(self):
        # "Едешь, едешь — степь да небо."
        tokens = [
            _tok("Едешь", "VERB", lemma="ехать", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("едешь", "VERB", lemma="ехать", idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_repeated"

    def test_repeated_beats_homogeneous(self):
        # Realistic dep tree where second token has dep_rel=conj — section 1
        # would otherwise classify as comma_homogeneous. Section 0 wins.
        tokens = [
            _tok("Дождь", "NOUN", lemma="дождь", idx=0, dep_rel="nsubj", head_idx=3),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("дождь", "NOUN", lemma="дождь", idx=2, dep_rel="conj", head_idx=0),
            _tok("идёт", "VERB", idx=3, dep_rel="root", head_idx=None),
        ]
        assert _classify_comma(tokens, 1) == "comma_repeated"

    def test_different_lemma_not_repeated(self):
        # "красный, синий шар" — same POS, different lemmas → homogeneous, not repeated.
        tokens = [
            _tok("красный", "ADJ", lemma="красный", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("синий", "ADJ", lemma="синий", idx=2),
            _tok("шар", "NOUN", idx=3),
        ]
        assert _classify_comma(tokens, 1) != "comma_repeated"

    def test_function_word_repetition_not_caught(self):
        # CCONJ repetition (rare; mostly impossible in clean text) — must not
        # fire §90 because CCONJ is not in REPEATED_CONTENT_POS.
        tokens = [
            _tok("и", "CCONJ", lemma="и", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("и", "CCONJ", lemma="и", idx=2),
        ]
        assert _classify_comma(tokens, 1) != "comma_repeated"

    def test_parenthetical_closing_comma_subtree_scan(self):
        # "...содержат в себе, по существу, приемы..." — closing comma at
        # idx=7 has head_idx pointing at the next content token (приемы),
        # not the parataxis ("существу"). Section 1's head-based check
        # therefore misses it. The closing-subtree scan must catch it.
        tokens = [
            _tok("содержат", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("в", "ADP", idx=1, dep_rel="case", head_idx=2),
            _tok("себе", "PRON", idx=2, dep_rel="obl", head_idx=0),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=5, features={}),
            _tok("по", "ADP", idx=4, dep_rel="case", head_idx=5),
            _tok("существу", "NOUN", idx=5, dep_rel="parataxis", head_idx=0),
            _tok(",", "PUNCT", idx=6, dep_rel="punct", head_idx=7),
            _tok("приемы", "NOUN", idx=7, dep_rel="obj", head_idx=0),
        ]
        assert _classify_comma(tokens, 3) == "comma_parenthetical"  # opening
        assert _classify_comma(tokens, 6) == "comma_parenthetical"  # closing


# ── §116 asyndetic clauses / §101 vocatives (audit fixes) ───────────────────


class TestClassifyCommaAsyndetic:
    """§116 БСП: bare comma between two finite clauses, no conjunction.

    Previously mislabeled comma_compound (§104) or comma_homogeneous (§83).
    """

    def test_asyndetic_via_conj_arc(self):
        # "Шли дожди, дороги размыло." — stanza parses the second clause as
        # conj of the first; no CCONJ anywhere → §116, not §104.
        tokens = [
            _tok("Шли", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("дожди", "NOUN", idx=1, dep_rel="nsubj", head_idx=0),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
            _tok("дороги", "NOUN", idx=3, dep_rel="nsubj:pass", head_idx=4),
            _tok("размыло", "VERB", idx=4, dep_rel="conj", head_idx=0),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=0),
        ]
        assert _classify_comma(tokens, 2) == "comma_asyndetic"

    def test_asyndetic_via_parataxis_arc(self):
        # "Лес рубят, щепки летят." — second clause attached as parataxis;
        # the trailing finite clause must be §116, not comma_parenthetical.
        tokens = [
            _tok("Лес", "NOUN", idx=0, dep_rel="obj", head_idx=1),
            _tok("рубят", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
            _tok("щепки", "NOUN", idx=3, dep_rel="nsubj", head_idx=4),
            _tok("летят", "VERB", idx=4, dep_rel="parataxis", head_idx=1),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_asyndetic"

    def test_asyndetic_nominal_first_clause(self):
        # "Скоро полночь, никто не спит." — nominal one-member first clause
        # (root полночь); previously fell through to comma_homogeneous.
        tokens = [
            _tok("Скоро", "ADV", idx=0, dep_rel="advmod", head_idx=1),
            _tok("полночь", "NOUN", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("никто", "PRON", idx=3, dep_rel="nsubj", head_idx=5),
            _tok("не", "PART", idx=4, dep_rel="advmod", head_idx=5),
            _tok("спит", "VERB", idx=5, dep_rel="conj", head_idx=1),
            _tok(".", "PUNCT", idx=6, dep_rel="punct", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_asyndetic"

    def test_compound_with_conjunction_still_compound(self):
        # "Солнце светило, и птицы пели" — real CCONJ at the junction → §104.
        tokens = [
            _tok("Солнце", "PROPN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("светило", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=5),
            _tok("птицы", "NOUN", idx=4, dep_rel="nsubj", head_idx=5),
            _tok("пели", "VERB", idx=5, dep_rel="conj", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_compound"

    def test_homogeneous_predicates_not_asyndetic(self):
        # "Он встал, оделся." — shared subject, homogeneous predicates (§83):
        # the second verb has no own subject → NOT a clause junction.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("встал", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("оделся", "VERB", idx=3, dep_rel="conj", head_idx=1),
            _tok(".", "PUNCT", idx=4, dep_rel="punct", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_homogeneous"

    def test_inner_parenthetical_clause_not_asyndetic(self):
        # "Он, я думаю, придёт." — parataxis clause with subject mid-sentence
        # does NOT run to the sentence end → stays comma_parenthetical.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("я", "PRON", idx=2, dep_rel="nsubj", head_idx=3),
            _tok("думаю", "VERB", idx=3, dep_rel="parataxis", head_idx=5),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=3),
            _tok("придёт", "VERB", idx=5, dep_rel="root", head_idx=None),
            _tok(".", "PUNCT", idx=6, dep_rel="punct", head_idx=5),
        ]
        assert _classify_comma(tokens, 1) == "comma_parenthetical"
        assert _classify_comma(tokens, 4) == "comma_parenthetical"

    def test_weight_gate_skips_zeroed_asyndetic(self):
        # lorugec zeroes comma_asyndetic — apply() must skip, not mislabel.
        handler = CommaDeleteHandler()
        handler.set_subtype_weights({"comma_asyndetic": 0})
        tokens = [
            _tok("Шли", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("дожди", "NOUN", idx=1, dep_rel="nsubj", head_idx=0),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
            _tok("дороги", "NOUN", idx=3, dep_rel="nsubj:pass", head_idx=4),
            _tok("размыло", "VERB", idx=4, dep_rel="conj", head_idx=0),
        ]
        sentence = [t.text for t in tokens]
        assert handler.apply(tokens, sentence, 2, set()) is None
        assert sentence == [t.text for t in tokens]  # untouched
        # Explicit subtype targeting overrides the weight gate.
        handler.set_enabled_subtypes({"comma_asyndetic"})
        result = handler.apply(tokens, sentence, 2, set())
        assert result is not None
        assert result.error_type == "comma_asyndetic"


class TestClassifyCommaVocative:
    """§101 обращения: dep_rel=vocative bounds the comma."""

    def _question_tokens(self):
        # "Куда ты едешь, Маша?" — stanza tags Маша dep=vocative.
        return [
            _tok("Куда", "ADV", idx=0, dep_rel="advmod", head_idx=2),
            _tok("ты", "PRON", idx=1, dep_rel="nsubj", head_idx=2),
            _tok("едешь", "VERB", idx=2, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=4),
            _tok("Маша", "PROPN", idx=4, dep_rel="vocative", head_idx=2),
            _tok("?", "PUNCT", idx=5, dep_rel="punct", head_idx=2),
        ]

    def test_sentence_final_vocative(self):
        assert _classify_comma(self._question_tokens(), 3) == "comma_vocative"

    def test_mid_sentence_vocative_pair(self):
        # "Привет, Маша, как дела?" — both commas bound the обращение.
        tokens = [
            _tok("Привет", "INTJ", lemma="привет", idx=0, dep_rel="root"),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("Маша", "PROPN", idx=2, dep_rel="vocative", head_idx=5),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=2),
            _tok("как", "ADV", idx=4, dep_rel="advmod", head_idx=5),
            _tok("дела", "NOUN", idx=5, dep_rel="parataxis", head_idx=0),
            _tok("?", "PUNCT", idx=6, dep_rel="punct", head_idx=0),
        ]
        # Vocative wins over the INTJ neighbor on the opening comma.
        assert _classify_comma(tokens, 1) == "comma_vocative"
        assert _classify_comma(tokens, 3) == "comma_vocative"

    def test_multiword_vocative_subtree_boundary(self):
        # "Здравствуй, дорогая Маша, я скучаю." — opening comma is adjacent
        # to the amod, not the vocative head; the subtree scan must catch it.
        tokens = [
            _tok("Здравствуй", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("дорогая", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("Маша", "PROPN", idx=3, dep_rel="vocative", head_idx=0),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=3),
            _tok("я", "PRON", idx=5, dep_rel="nsubj", head_idx=6),
            _tok("скучаю", "VERB", idx=6, dep_rel="parataxis", head_idx=0),
            _tok(".", "PUNCT", idx=7, dep_rel="punct", head_idx=0),
        ]
        assert _classify_comma(tokens, 1) == "comma_vocative"
        assert _classify_comma(tokens, 4) == "comma_vocative"

    def test_no_vocative_no_false_fire(self):
        # No vocative relation anywhere → other branches decide.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("знал", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
            _tok("что", "SCONJ", idx=3, dep_rel="mark", head_idx=4),
            _tok("придёт", "VERB", idx=4, dep_rel="ccomp", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) != "comma_vocative"


class TestCommaRepeatedTightened:
    """§90 misfire fix: accidental same-form adjacency across a clause
    boundary must not classify as comma_repeated."""

    def test_topic_chain_not_repeated(self):
        # "Дети любят сказки, сказки развивают воображение." — left сказки is
        # obj of clause 1, right сказки is nsubj of clause 2 → §116 junction.
        tokens = [
            _tok("Дети", "NOUN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("любят", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok("сказки", "NOUN", lemma="сказка", idx=2, dep_rel="obj", head_idx=1),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=5),
            _tok("сказки", "NOUN", lemma="сказка", idx=4, dep_rel="nsubj", head_idx=5),
            _tok("развивают", "VERB", idx=5, dep_rel="conj", head_idx=1),
            _tok("воображение", "NOUN", idx=6, dep_rel="obj", head_idx=5),
            _tok(".", "PUNCT", idx=7, dep_rel="punct", head_idx=1),
        ]
        assert _classify_comma(tokens, 3) != "comma_repeated"
        # With the dep tree present, this is a §116 clause junction.
        assert _classify_comma(tokens, 3) == "comma_asyndetic"

    def test_genuine_repetition_conj_arc_still_fires(self):
        # "он ехал, ехал" — same form, second token conj of the first.
        tokens = [
            _tok("он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("ехал", "VERB", lemma="ехать", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("ехал", "VERB", lemma="ехать", idx=3, dep_rel="conj", head_idx=1),
        ]
        assert _classify_comma(tokens, 2) == "comma_repeated"

    def test_same_lemma_different_form_not_repeated(self):
        # "...читал сказку, сказки ему нравились" — same lemma, different
        # surface form → §90 requires identical-form repetition.
        tokens = [
            _tok("читал", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("сказку", "NOUN", lemma="сказка", idx=1, dep_rel="obj", head_idx=0),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("сказки", "NOUN", lemma="сказка", idx=3, dep_rel="nsubj", head_idx=5),
            _tok("ему", "PRON", idx=4, dep_rel="iobj", head_idx=5),
            _tok("нравились", "VERB", idx=5, dep_rel="conj", head_idx=0),
        ]
        assert _classify_comma(tokens, 2) != "comma_repeated"

    def test_no_dep_info_surface_fallback_kept(self):
        # Without depparse the legacy surface behaviour must survive.
        tokens = [
            _tok("Дождь", "NOUN", lemma="дождь", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("дождь", "NOUN", lemma="дождь", idx=2),
            _tok("идёт", "VERB", idx=3),
        ]
        assert _classify_comma(tokens, 1) == "comma_repeated"


class TestClosingCommaGapGuard:
    """Fallback closing-comma scans: a 1–2 token gap must be PUNCT-only."""

    def _tokens_with_content_gap(self, mid_deprel):
        # Subtree of the acl/parataxis head ends 2 CONTENT tokens before the
        # comma — the fallback must NOT claim this comma closes it.
        return [
            _tok("колонна", "NOUN", idx=0, dep_rel=None, head_idx=None),
            _tok(
                "отступавшая",
                "VERB",
                idx=1,
                dep_rel=mid_deprel,
                head_idx=0,
                features={"VerbForm": "Part"} if mid_deprel == "acl" else {},
            ),
            _tok("быстро", "ADV", idx=2, dep_rel="advmod", head_idx=3),
            _tok("шла", "VERB", idx=3, dep_rel=None, head_idx=None),
            _tok(",", "PUNCT", idx=4),  # no head info → fallback path
            _tok("вперёд", "ADV", idx=5, dep_rel=None, head_idx=None),
        ]

    def test_isolation_gap_with_content_tokens_rejected(self):
        tokens = self._tokens_with_content_gap("acl")
        assert _classify_comma(tokens, 4) != "comma_isolation"

    def test_parenthetical_gap_with_content_tokens_rejected(self):
        tokens = self._tokens_with_content_gap("parataxis")
        assert _classify_comma(tokens, 4) != "comma_parenthetical"

    def test_isolation_gap_with_punct_token_accepted(self):
        # Genuine case: one PUNCT token (closing quote) inside the gap.
        tokens = [
            _tok("колонна", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok(
                "отступавшая",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("по", "ADP", idx=3, dep_rel="case", head_idx=4),
            _tok("шоссе", "NOUN", idx=4, dep_rel="obl", head_idx=2),
            _tok("»", "PUNCT", idx=5),
            _tok(",", "PUNCT", idx=6),
            _tok("обстреливалась", "VERB", idx=7),
        ]
        assert _classify_comma(tokens, 6) == "comma_isolation"


# ── DashDeleteHandler ───────────────────────────────────────────────────────


class TestDashDeleteHandler:
    handler = DashDeleteHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "dash_delete"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5

    def test_can_apply_dash_only(self):
        tokens = [
            _tok("Мама", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("врач", "NOUN", idx=2),
            _tok(",", "PUNCT", idx=3),
        ]
        assert self.handler.can_apply(tokens, 0) is False
        assert self.handler.can_apply(tokens, 1) is True
        assert self.handler.can_apply(tokens, 2) is False
        assert self.handler.can_apply(tokens, 3) is False

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
        tokens = [
            _tok("Москва", "PROPN", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("столица", "NOUN", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_pron_adj_dash_is_optional(self):
        # §79: pronoun subject AND adjectival predicate — the dash is
        # authorial on both counts; deletion is a non-error → None.
        tokens = [
            _tok("Он", "PRON", idx=0, features={"PronType": "Prs"}),
            _tok("—", "PUNCT", idx=1),
            _tok("хороший", "ADJ", idx=2, dep_rel="root"),
        ]
        assert _classify_dash(tokens, 1) is None

    def test_asyndetic_verb_verb(self):
        tokens = [
            _tok("пришёл", "VERB", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("увидел", "VERB", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_asyndetic"

    def test_sentence_final_dash_skipped(self):
        # A dash with nothing after it is not a clause dash — skip.
        tokens = [
            _tok("слово", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
        ]
        assert _classify_dash(tokens, 1) is None

    def test_inf_inf_dash_subj_pred(self):
        # §79: both main members are infinitives → dash is obligatory.
        tokens = [
            _tok("Курить", "VERB", idx=0, features={"VerbForm": "Inf"}),
            _tok("—", "PUNCT", idx=1),
            _tok("вредить", "VERB", idx=2, features={"VerbForm": "Inf"}),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_amod_right_neighbor_resolves_to_np_head(self):
        # "Москва — большой город": right neighbor is an attributive ADJ
        # (amod); the predicate is its NP head NOUN → still dash_subj_pred.
        tokens = [
            _tok("Москва", "PROPN", idx=0, dep_rel="nsubj", head_idx=3),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("большой", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("город", "NOUN", idx=3, dep_rel="root", head_idx=None),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"


# ── §79 exceptions: optional/authorial dashes must NOT be deleted ───────────


class TestDashSubjPredExceptions:
    handler = DashDeleteHandler()

    def _adjectival_predicate_tokens(self):
        # "Ночь — тёплая и тихая." — predicate is a full adjective; §79:
        # the dash is intonational, deleting it yields correct text.
        return [
            _tok("Ночь", "NOUN", idx=0, dep_rel="nsubj", head_idx=2),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("тёплая", "ADJ", idx=2, dep_rel="root", head_idx=None),
            _tok("и", "CCONJ", idx=3, dep_rel="cc", head_idx=4),
            _tok("тихая", "ADJ", idx=4, dep_rel="conj", head_idx=2),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=2),
        ]

    def test_adjectival_predicate_dash_classifies_none(self):
        assert _classify_dash(self._adjectival_predicate_tokens(), 1) is None

    def test_adjectival_predicate_dash_not_applicable(self):
        tokens = self._adjectival_predicate_tokens()
        assert self.handler.can_apply(tokens, 1) is False
        sentence = ["Ночь", "—", "тёплая", "и", "тихая", "."]
        assert self.handler.apply(tokens, sentence, 1, set()) is None
        assert sentence == ["Ночь", "—", "тёплая", "и", "тихая", "."]

    def test_adverb_plus_adjective_predicate_skipped(self):
        # "Ночь — очень тёплая." — adverbial intensifier before the ADJ.
        tokens = [
            _tok("Ночь", "NOUN", idx=0, dep_rel="nsubj", head_idx=3),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("очень", "ADV", idx=2, dep_rel="advmod", head_idx=3),
            _tok("тёплая", "ADJ", idx=3, dep_rel="root", head_idx=None),
        ]
        assert _classify_dash(tokens, 1) is None

    def _pronoun_subject_tokens(self):
        # "Он — мой лучший друг." — §79: personal-pronoun subject,
        # dash is normally absent; deletion is the norm, not an error.
        return [
            _tok(
                "Он",
                "PRON",
                idx=0,
                dep_rel="nsubj",
                head_idx=4,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=4),
            _tok("мой", "DET", idx=2, dep_rel="det", head_idx=4),
            _tok("лучший", "ADJ", idx=3, dep_rel="amod", head_idx=4),
            _tok("друг", "NOUN", idx=4, dep_rel="root", head_idx=None),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=4),
        ]

    def test_pronoun_subject_dash_classifies_none(self):
        assert _classify_dash(self._pronoun_subject_tokens(), 1) is None

    def test_pronoun_subject_dash_not_applicable(self):
        assert self.handler.can_apply(self._pronoun_subject_tokens(), 1) is False

    def test_pronoun_contrast_dash_still_fires(self):
        # "Я — фабрикант, ты — судовладелец" (Rozental's own §79 example):
        # parallel pronoun-subject clauses → contrast → dash IS required.
        tokens = [
            _tok(
                "Я",
                "PRON",
                idx=0,
                dep_rel="nsubj",
                head_idx=2,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("фабрикант", "NOUN", idx=2, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=6),
            _tok(
                "ты",
                "PRON",
                idx=4,
                dep_rel="nsubj",
                head_idx=6,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=5, dep_rel="punct", head_idx=6),
            _tok("судовладелец", "NOUN", idx=6, dep_rel="parataxis", head_idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"
        # Second dash sits under a parataxis arc (pre-existing apposition
        # branch); the §79 guard must not SKIP it either.
        assert _classify_dash(tokens, 5) is not None
        assert self.handler.can_apply(tokens, 1) is True


# ── §82 connective dash: routes/ranges must not be apposition ───────────────


class TestConnectiveDash:
    def _route_tokens(self):
        # "Поезд Москва — Казань уже ушёл." — stanza tags "Казань" appos
        # of "Москва"; the dash is §82 соединительное, not §93 apposition.
        return [
            _tok("Поезд", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok("Москва", "PROPN", idx=1, dep_rel="appos", head_idx=0),
            _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("Казань", "PROPN", idx=3, dep_rel="appos", head_idx=1),
            _tok("уже", "ADV", idx=4, dep_rel="advmod", head_idx=5),
            _tok("ушёл", "VERB", idx=5, dep_rel="root", head_idx=None),
            _tok(".", "PUNCT", idx=6, dep_rel="punct", head_idx=5),
        ]

    def test_propn_route_skipped(self):
        # §82 connective dash: deleting it is a typography change, not a
        # punctuation-rule error — skip entirely.
        assert _classify_dash(self._route_tokens(), 2) is None

    def test_propn_route_excluded_from_dash_to_comma(self):
        handler = DashToCommaHandler()
        assert handler.can_apply(self._route_tokens(), 2) is False

    def test_num_range_skipped(self):
        # "страницы 5 — 10" — §82 range: skipped, not corrupted.
        tokens = [
            _tok("страницы", "NOUN", idx=0, dep_rel="root", head_idx=None),
            _tok("5", "NUM", idx=1, dep_rel="nummod", head_idx=0),
            _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("10", "NUM", idx=3, dep_rel="appos", head_idx=1),
        ]
        assert _classify_dash(tokens, 2) is None
        assert DashToCommaHandler().can_apply(tokens, 2) is False

    def test_genitive_propn_apposition_not_a_route(self):
        # «столица Исландии — Рейкьявик»: the genitive left endpoint makes
        # this an apposition to the NP head, not a §82 route.
        tokens = [
            _tok("столица", "NOUN", idx=0, dep_rel="root", head_idx=None),
            _tok(
                "Исландии",
                "PROPN",
                idx=1,
                dep_rel="nmod",
                head_idx=0,
                features={"Case": "Gen"},
            ),
            _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok(
                "Рейкьявик",
                "PROPN",
                idx=3,
                dep_rel="appos",
                head_idx=0,
                features={"Case": "Nom"},
            ),
        ]
        assert _classify_dash(tokens, 2) == "dash_apposition"


# ── CommaPairDeleteHandler ──────────────────────────────────────────────────


class TestFindCommaPair:
    """Test _find_comma_partner detection."""

    def _participle_tokens(self):
        # "Студент, читающий книгу, ушёл"
        return [
            _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "читающий",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", "NOUN", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok("ушёл", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]

    def test_participle_pair_found(self):
        tokens = self._participle_tokens()
        result = _find_comma_partner(tokens, 1)
        assert result is not None
        partner_idx, subtype = result
        assert partner_idx == 4
        assert subtype == "pair_participle"

    def test_only_first_comma_triggers(self):
        tokens = self._participle_tokens()
        # Second comma should NOT trigger (idx > partner)
        assert _find_comma_partner(tokens, 4) is None

    def test_gerund_pair(self):
        # "Он, напевая песню, шёл домой"
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "напевая",
                "VERB",
                idx=2,
                dep_rel="advcl",
                head_idx=5,
                features={"VerbForm": "Conv"},
            ),
            _tok("песню", "NOUN", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok("шёл", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result is not None
        assert result == (4, "pair_gerund")

    def test_advcl_full_clause_not_paired(self):
        # "Он уехал, когда стемнело, и не вернулся" — advcl but not Conv
        tokens = [
            _tok("уехал", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("когда", "SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok(
                "стемнело",
                "VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=3),
        ]
        # advcl without VerbForm=Conv → not a gerund pair
        assert _find_comma_partner(tokens, 1) is None

    def test_parenthetical_pair(self):
        # "Он, конечно, был прав"
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "конечно",
                "ADV",
                lemma="конечно",
                idx=2,
                dep_rel="parataxis",
                head_idx=5,
            ),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=2),
            _tok("был", "AUX", idx=4, dep_rel="cop", head_idx=5),
            _tok("прав", "ADJ", idx=5, dep_rel="root", head_idx=None),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result is not None
        assert result == (3, "pair_parenthetical")

    def test_relative_clause_pair(self):
        # "дом, который построил Джек, стоял"
        tokens = [
            _tok("дом", "NOUN", idx=0, dep_rel="nsubj", head_idx=6),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("который", "PRON", idx=2, dep_rel="obj", head_idx=3),
            _tok("построил", "VERB", idx=3, dep_rel="acl:relcl", head_idx=0),
            _tok("Джек", "PROPN", idx=4, dep_rel="nsubj", head_idx=3),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
            _tok("стоял", "VERB", idx=6, dep_rel="root", head_idx=None),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result is not None
        assert result == (5, "pair_relative")

    def test_no_pair_single_comma(self):
        # "знал, что придёт" — only one comma, no partner
        tokens = [
            _tok("знал", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("что", "SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok("придёт", "VERB", idx=3, dep_rel="ccomp", head_idx=0),
        ]
        assert _find_comma_partner(tokens, 1) is None

    # ── Single-comma at sentence boundary: NOT a pair ──────────────────────

    def test_sentence_start_preposed_participle_not_a_pair(self):
        # "Высушенные, они становятся синеватыми." — preposed adj/participle
        # at sentence start has only ONE comma. Single-comma isolations
        # belong to comma_delete:comma_isolation; the pair handler must
        # always delete exactly two commas.
        tokens = [
            _tok("Высушенные", "ADJ", idx=0, dep_rel="amod", head_idx=2),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("они", "PRON", idx=2, dep_rel="nsubj", head_idx=3),
            _tok("становятся", "VERB", idx=3, dep_rel="root", head_idx=None),
            _tok("синеватыми", "ADJ", idx=4, dep_rel="obl", head_idx=3),
        ]
        assert _find_comma_partner(tokens, 1) is None

    def test_amod_isolation_two_commas(self):
        # "Она, чистая, имеет вид." — postnominal isolated adj, two commas.
        tokens = [
            _tok("Она", "PRON", idx=0, dep_rel="nsubj", head_idx=4),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("чистая", "ADJ", idx=2, dep_rel="amod", head_idx=0),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=2),
            _tok("имеет", "VERB", idx=4, dep_rel="root", head_idx=None),
            _tok("вид", "NOUN", idx=5, dep_rel="obj", head_idx=4),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result == (3, "pair_participle")

    def test_partner_via_subtree_when_heads_differ(self):
        # "Хотя, родившись в году, Андреевский..." — stanza often attaches
        # opening comma to "Хотя" (mark) and closing to gerund (advcl).
        # Subtree-based detection should still pair them.
        tokens = [
            _tok("Хотя", "SCONJ", idx=0, dep_rel="mark", head_idx=6),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok(
                "родившись",
                "VERB",
                idx=2,
                dep_rel="advcl",
                head_idx=6,
                features={"VerbForm": "Conv"},
            ),
            _tok("в", "ADP", idx=3, dep_rel="case", head_idx=4),
            _tok("году", "NOUN", idx=4, dep_rel="obl", head_idx=2),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=2),
            _tok("Андреевский", "PROPN", idx=6, dep_rel="root", head_idx=None),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result == (5, "pair_gerund")

    def test_apposition_with_leading_adjective_pairs_both_commas(self):
        # "Мой старший брат, талантливый инженер, работает в Москве."
        # The apposition "талантливый инженер" leads with an attributive adj
        # tagged amod (head=инженер). A bare amod must NOT shadow the appos
        # head: the appos subtree encloses the amod, so the enclosing span
        # wins and BOTH commas pair correctly as pair_apposition.
        tokens = [
            _tok("Мой", "DET", idx=0, dep_rel="det", head_idx=2),
            _tok("старший", "ADJ", idx=1, dep_rel="amod", head_idx=2),
            _tok("брат", "NOUN", idx=2, dep_rel="nsubj", head_idx=7),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=5),
            _tok("талантливый", "ADJ", idx=4, dep_rel="amod", head_idx=5),
            _tok("инженер", "NOUN", idx=5, dep_rel="appos", head_idx=2),
            _tok(",", "PUNCT", idx=6, dep_rel="punct", head_idx=2),
            _tok("работает", "VERB", idx=7, dep_rel="root", head_idx=None),
            _tok("в", "ADP", idx=8, dep_rel="case", head_idx=9),
            _tok("Москве", "PROPN", idx=9, dep_rel="obl", head_idx=7),
            _tok(".", "PUNCT", idx=10, dep_rel="punct", head_idx=7),
        ]
        result = _find_comma_partner(tokens, 3)
        assert result == (6, "pair_apposition")
        # The orphaned-comma bug deleted only the first comma; the closing
        # comma (idx=6) must NOT itself trigger a separate pair.
        assert _find_comma_partner(tokens, 6) is None

    def test_homogeneous_list_not_paired(self):
        # "Я купил свежие яблоки, спелые груши, сочные апельсины."
        # Each list item leads with an attributive adjective (amod). A bare
        # amod with a comma on only one side is an ordinary attributive, not an
        # isolation — comma_pair_delete must NOT touch homogeneous separators.
        tokens = [
            _tok("Я", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("купил", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok("свежие", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("яблоки", "NOUN", idx=3, dep_rel="obj", head_idx=1),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=6),
            _tok("спелые", "ADJ", idx=5, dep_rel="amod", head_idx=6),
            _tok("груши", "NOUN", idx=6, dep_rel="conj", head_idx=3),
            _tok(",", "PUNCT", idx=7, dep_rel="punct", head_idx=9),
            _tok("сочные", "ADJ", idx=8, dep_rel="amod", head_idx=9),
            _tok("апельсины", "NOUN", idx=9, dep_rel="conj", head_idx=3),
            _tok(".", "PUNCT", idx=10, dep_rel="punct", head_idx=1),
        ]
        assert _find_comma_partner(tokens, 4) is None
        assert _find_comma_partner(tokens, 7) is None

    # ── Unconfirmed closing comma (audit finding: stray-comma half-pair) ───

    def _absorbed_trailing_material_tokens(self):
        # "Он шёл, напевая песню, по улице." — stanza attaches "по улице" to
        # the gerund, so the advcl subtree runs to the sentence end and the
        # closing comma (idx=5) sits INSIDE the span: no right boundary
        # comma is found.
        return [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("шёл", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok(
                "напевая",
                "VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=1,
                features={"VerbForm": "Conv"},
            ),
            _tok("песню", "NOUN", idx=4, dep_rel="obj", head_idx=3),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
            _tok("по", "ADP", idx=6, dep_rel="case", head_idx=7),
            _tok("улице", "NOUN", idx=7, dep_rel="obl", head_idx=3),
            _tok(".", "PUNCT", idx=8, dep_rel="punct", head_idx=1),
        ]

    def test_unconfirmed_closing_comma_skips(self):
        # Deleting only the opening comma would orphan the one at idx=5 —
        # the construction must be skipped entirely.
        tokens = self._absorbed_trailing_material_tokens()
        assert _find_comma_partner(tokens, 2) is None

    def test_sentence_final_gerund_single_comma_not_a_pair(self):
        # "Он шёл, напевая песню." — only one comma exists, so this is a
        # single-comma isolation for comma_delete, never a pair.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("шёл", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok(
                "напевая",
                "VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=1,
                features={"VerbForm": "Conv"},
            ),
            _tok("песню", "NOUN", idx=4, dep_rel="obj", head_idx=3),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=1),
        ]
        assert _find_comma_partner(tokens, 2) is None
        # ...and _classify_comma still recognizes it as an isolation comma.
        assert _classify_comma(tokens, 2) == "comma_isolation"

    def test_no_pair_no_boundary_commas(self):
        # Isolation head exists but has no commas adjacent to its span.
        # Should not trigger.
        tokens = [
            _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=2),
            _tok(
                "читающий",
                "VERB",
                idx=1,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", "NOUN", idx=2, dep_rel="root", head_idx=None),
        ]
        # No commas adjacent to the acl subtree → no pair
        assert _find_comma_partner(tokens, 0) is None


# ── Dash classification: apposition vs subj-pred ────────────────────────────


class TestClassifyDashApposition:
    """§93 apposition dashes must classify as dash_apposition, not subj_pred."""

    def test_apposition_via_parataxis_arc(self):
        # "Соляник — государственный памятник" — stanza attaches the post-dash
        # nominal to the pre-dash one via parataxis. Surface PROPN—ADJ pattern
        # would otherwise match subj_pred.
        tokens = [
            _tok("является", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("пещера", "NOUN", idx=1, dep_rel="nsubj", head_idx=0),
            _tok("Соляник", "PROPN", idx=2, dep_rel="appos", head_idx=1),
            _tok("—", "PUNCT", idx=3, dep_rel="punct", head_idx=5),
            _tok("государственный", "ADJ", idx=4, dep_rel="amod", head_idx=5),
            _tok("памятник", "NOUN", idx=5, dep_rel="parataxis", head_idx=1),
        ]
        assert _classify_dash(tokens, 3) == "dash_apposition"

    def test_subj_pred_still_classifies_correctly(self):
        # "Москва — столица" — no appos/parataxis arc crosses the dash; the
        # surface NOUN—NOUN pattern must still fire as dash_subj_pred.
        tokens = [
            _tok("Москва", "PROPN", idx=0, dep_rel="nsubj", head_idx=2),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("столица", "NOUN", idx=2, dep_rel="root", head_idx=None),
            _tok("России", "PROPN", idx=3, dep_rel="nmod", head_idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_apposition_via_appos_arc(self):
        # Inline apposition with appos arc bridging the dash directly
        tokens = [
            _tok("X", "NOUN", idx=0, dep_rel="root", head_idx=None),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("Y", "NOUN", idx=2, dep_rel="appos", head_idx=0),
        ]
        assert _classify_dash(tokens, 1) == "dash_apposition"


# ── §79 это/вот connector dashes ─────────────────────────────────────────────


class TestEstoConnectorDash:
    """§79: «Тире ставится перед словами это, это есть, вот, вот значит,
    это значит, присоединяющими сказуемое к подлежащему» — the connector
    dash is ALWAYS required → dash_subj_pred: never dash_other (это is PRON
    and fails the right-side nominal check), never skipped via the
    pronoun-subject exception."""

    def test_noun_subject_esto_is_subj_pred(self):
        # "Мир — это счастье." — deps mirror the live stanza parse
        # (это = PRON/expl); used to fall through to dash_other.
        tokens = [
            _tok("Мир", "NOUN", idx=0, dep_rel="nsubj", head_idx=3),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok(
                "это",
                "PRON",
                idx=2,
                dep_rel="expl",
                head_idx=3,
                features={"PronType": "Dem"},
            ),
            _tok("счастье", "NOUN", idx=3, dep_rel="root", head_idx=None),
            _tok(".", "PUNCT", idx=4, dep_rel="punct", head_idx=3),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"
        assert DashDeleteHandler().can_apply(tokens, 1) is True

    def test_pronoun_subject_esto_still_fires(self):
        # "Мы — это будущее страны." — §79's pronoun-subject exception does
        # not apply to the connector construction: the dash stays required,
        # so classification must NOT return None.
        tokens = [
            _tok(
                "Мы",
                "PRON",
                idx=0,
                dep_rel="nsubj",
                head_idx=3,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok(
                "это",
                "PRON",
                idx=2,
                dep_rel="expl",
                head_idx=3,
                features={"PronType": "Dem"},
            ),
            _tok("будущее", "NOUN", idx=3, dep_rel="root", head_idx=None),
            _tok("страны", "NOUN", idx=4, dep_rel="nmod", head_idx=3),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"
        assert DashDeleteHandler().can_apply(tokens, 1) is True

    def test_vot_connector_with_infinitive_subject(self):
        # "Понять — вот задача." — §79 «вот» connector, infinitive subject.
        tokens = [
            _tok(
                "Понять",
                "VERB",
                idx=0,
                dep_rel="csubj",
                head_idx=3,
                features={"VerbForm": "Inf"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("вот", "PART", idx=2, dep_rel="advmod", head_idx=3),
            _tok("задача", "NOUN", idx=3, dep_rel="root", head_idx=None),
            _tok(".", "PUNCT", idx=4, dep_rel="punct", head_idx=3),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_esto_after_finite_clause_stays_asyndetic(self):
        # "Дверь открылась — это пришёл отец." — §116 БСП, not subj-pred:
        # a finite verb left of the dash means the left side is a clause,
        # not a subject NP, so the connector rule must not fire.
        tokens = [
            _tok("Дверь", "NOUN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "открылась",
                "VERB",
                idx=1,
                dep_rel="root",
                head_idx=None,
                features={"VerbForm": "Fin", "Mood": "Ind", "Tense": "Past"},
            ),
            _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=4),
            _tok(
                "это",
                "PRON",
                idx=3,
                dep_rel="expl",
                head_idx=4,
                features={"PronType": "Dem"},
            ),
            _tok(
                "пришёл",
                "VERB",
                idx=4,
                dep_rel="parataxis",
                head_idx=1,
                features={"VerbForm": "Fin", "Mood": "Ind", "Tense": "Past"},
            ),
            _tok("отец", "NOUN", idx=5, dep_rel="nsubj", head_idx=4),
            _tok(".", "PUNCT", idx=6, dep_rel="punct", head_idx=1),
        ]
        assert _classify_dash(tokens, 2) == "dash_asyndetic"


# ── §93 п.8-в paired apposition dashes ──────────────────────────────────────


class TestPairedAppositionDash:
    """Paired dashes bounding an explanatory apposition must classify
    dash_apposition — not subj_pred (opening) or asyndetic (closing)."""

    def _paired_tokens(self):
        # "Мы — весёлая детвора — шли домой." — deps mirror the live stanza
        # parse: the apposition is promoted to root, the matrix verb is
        # conj, and NO appos/parataxis arc bridges either dash.
        return [
            _tok(
                "Мы",
                "PRON",
                idx=0,
                dep_rel="nsubj",
                head_idx=3,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("весёлая", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("детвора", "NOUN", idx=3, dep_rel="root", head_idx=None),
            _tok("—", "PUNCT", idx=4, dep_rel="punct", head_idx=5),
            _tok(
                "шли",
                "VERB",
                idx=5,
                dep_rel="conj",
                head_idx=3,
                features={"VerbForm": "Fin", "Mood": "Ind", "Tense": "Past"},
            ),
            _tok("домой", "ADV", idx=6, dep_rel="advmod", head_idx=5),
            _tok(".", "PUNCT", idx=7, dep_rel="punct", head_idx=3),
        ]

    def test_opening_dash_is_apposition(self):
        assert _classify_dash(self._paired_tokens(), 1) == "dash_apposition"

    def test_closing_dash_is_apposition(self):
        assert _classify_dash(self._paired_tokens(), 4) == "dash_apposition"

    def test_noun_subject_paired_apposition(self):
        # "Ребята — весёлая детвора — шли домой." — with a NOUN subject the
        # opening dash used to surface-match dash_subj_pred (amod right
        # neighbor resolves to its NP head right of the dash).
        tokens = self._paired_tokens()
        tokens[0] = _tok("Ребята", "NOUN", idx=0, dep_rel="nsubj", head_idx=3)
        assert _classify_dash(tokens, 1) == "dash_apposition"
        assert _classify_dash(tokens, 4) == "dash_apposition"

    def test_contrast_pattern_still_subj_pred(self):
        # "Я — фабрикант, ты — судовладелец." (§79 contrast, Rozental's own
        # example) — the comma + second clause between the two dashes
        # distinguishes it from a verbless §93 bounded span; both dashes
        # stay dash_subj_pred. Deps mirror the live stanza parse
        # (судовладелец = conj).
        tokens = [
            _tok(
                "Я",
                "PRON",
                idx=0,
                dep_rel="nsubj",
                head_idx=2,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("фабрикант", "NOUN", idx=2, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=6),
            _tok(
                "ты",
                "PRON",
                idx=4,
                dep_rel="nsubj",
                head_idx=6,
                features={"PronType": "Prs"},
            ),
            _tok("—", "PUNCT", idx=5, dep_rel="punct", head_idx=4),
            _tok("судовладелец", "NOUN", idx=6, dep_rel="conj", head_idx=2),
            _tok(".", "PUNCT", idx=7, dep_rel="punct", head_idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"
        assert _classify_dash(tokens, 5) == "dash_subj_pred"


class TestDashToCommaHandler:
    """§93 apposition dash → comma substitution."""

    handler = DashToCommaHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "dash_to_comma"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is False
        assert self.handler.subtypes == ["dash_to_comma_apposition"]

    def test_fires_on_parataxis_apposition(self):
        # "Соляник — памятник" — stanza tags post-dash apposition as parataxis
        tokens = [
            _tok("Соляник", "PROPN", idx=0, dep_rel="appos", head_idx=2),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("памятник", "NOUN", idx=2, dep_rel="root", head_idx=None),
            _tok("природы", "NOUN", idx=3, dep_rel="parataxis", head_idx=0),
        ]
        assert self.handler.can_apply(tokens, 1)
        sentence = ["Соляник", "—", "памятник", "природы"]
        result = self.handler.apply(tokens, sentence, 1, set())
        assert result is not None
        assert result.error_type == "dash_to_comma_apposition"
        assert result.original == "—"
        assert result.corrupted == ","
        assert sentence == ["Соляник", ",", "памятник", "природы"]

    def test_fires_on_sentence_final_apposition(self):
        # "Я не слишком люблю это дерево — осину." — §93 п.8 б: тире is the
        # standard marking for a sentence-final apposition → genuine error.
        tokens = [
            _tok("люблю", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("это", "DET", idx=1, dep_rel="det", head_idx=2),
            _tok("дерево", "NOUN", idx=2, dep_rel="obj", head_idx=0),
            _tok("—", "PUNCT", idx=3, dep_rel="punct", head_idx=4),
            _tok("осину", "NOUN", idx=4, dep_rel="appos", head_idx=2),
            _tok(".", "PUNCT", idx=5, dep_rel="punct", head_idx=0),
        ]
        assert self.handler.can_apply(tokens, 3) is True

    def test_skips_mid_sentence_apposition(self):
        # "Он увидал корреспондента — дьякона и ушёл." — §93 п.1–2: the
        # comma is the sanctioned base marking for a mid-sentence apposition,
        # so dash→comma there is a non-error → must not fire.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("увидал", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok("корреспондента", "NOUN", idx=2, dep_rel="obj", head_idx=1),
            _tok("—", "PUNCT", idx=3, dep_rel="punct", head_idx=4),
            _tok("дьякона", "NOUN", idx=4, dep_rel="appos", head_idx=2),
            _tok("и", "CCONJ", idx=5, dep_rel="cc", head_idx=6),
            _tok("ушёл", "VERB", idx=6, dep_rel="conj", head_idx=1),
            _tok(".", "PUNCT", idx=7, dep_rel="punct", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 3) is False

    def test_skips_subj_pred_dash(self):
        # "Москва — столица" is subj_pred, not apposition. Don't fire.
        tokens = [
            _tok("Москва", "PROPN", idx=0, dep_rel="nsubj", head_idx=2),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("столица", "NOUN", idx=2, dep_rel="root", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_skips_non_dash(self):
        tokens = [
            _tok("a", "NOUN", idx=0),
            _tok(",", "PUNCT", idx=1),
            _tok("b", "NOUN", idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False


class TestCommaPairDeleteHandler:
    handler = CommaPairDeleteHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "comma_pair_delete"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 5

    def test_can_apply_on_first_comma_of_pair(self):
        # "Студент, читающий книгу, ушёл"
        tokens = [
            _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "читающий",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", "NOUN", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok("ушёл", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 1) is True
        assert self.handler.can_apply(tokens, 4) is False  # second comma

    def test_apply_deletes_both_commas(self):
        tokens = [
            _tok("Студент", "NOUN", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "читающий",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", "NOUN", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok("ушёл", "VERB", idx=5, dep_rel="root", head_idx=None),
        ]
        sentence = ["Студент", ",", "читающий", "книгу", ",", "ушёл"]
        result = self.handler.apply(tokens, sentence, 1, set())

        assert result is not None
        assert result.error_type == "pair_participle"
        assert result.category == "PUNCT"
        assert sentence == ["Студент", "читающий", "книгу", "ушёл"]  # both commas gone

    def test_can_apply_false_for_single_comma(self):
        tokens = [
            _tok("знал", "VERB", idx=0),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("что", "SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok("придёт", "VERB", idx=3, dep_rel="ccomp", head_idx=0),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def _leading_adj_apposition_tokens(self):
        # "Мой старший брат, талантливый инженер, работает в Москве."
        return [
            _tok("Мой", "DET", idx=0, dep_rel="det", head_idx=2),
            _tok("старший", "ADJ", idx=1, dep_rel="amod", head_idx=2),
            _tok("брат", "NOUN", idx=2, dep_rel="nsubj", head_idx=7),
            _tok(",", "PUNCT", idx=3, dep_rel="punct", head_idx=5),
            _tok("талантливый", "ADJ", idx=4, dep_rel="amod", head_idx=5),
            _tok("инженер", "NOUN", idx=5, dep_rel="appos", head_idx=2),
            _tok(",", "PUNCT", idx=6, dep_rel="punct", head_idx=2),
            _tok("работает", "VERB", idx=7, dep_rel="root", head_idx=None),
            _tok("в", "ADP", idx=8, dep_rel="case", head_idx=9),
            _tok("Москве", "PROPN", idx=9, dep_rel="obl", head_idx=7),
            _tok(".", "PUNCT", idx=10, dep_rel="punct", head_idx=7),
        ]

    def test_apply_deletes_both_commas_leading_adj_apposition(self):
        tokens = self._leading_adj_apposition_tokens()
        sentence = [t.text for t in tokens]
        result = self.handler.apply(tokens, sentence, 3, set())

        assert result is not None
        assert result.error_type == "pair_apposition"
        assert result.category == "PUNCT"
        # Both commas gone — no orphan left behind.
        assert "," not in sentence
        assert sentence == [
            "Мой",
            "старший",
            "брат",
            "талантливый",
            "инженер",
            "работает",
            "в",
            "Москве",
            ".",
        ]

    def test_can_apply_false_on_homogeneous_list(self):
        # "Я купил свежие яблоки, спелые груши, сочные апельсины." — leading
        # attributive adjectives (amod) must not let comma_pair_delete fire.
        tokens = [
            _tok("Я", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("купил", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok("свежие", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("яблоки", "NOUN", idx=3, dep_rel="obj", head_idx=1),
            _tok(",", "PUNCT", idx=4, dep_rel="punct", head_idx=6),
            _tok("спелые", "ADJ", idx=5, dep_rel="amod", head_idx=6),
            _tok("груши", "NOUN", idx=6, dep_rel="conj", head_idx=3),
            _tok(",", "PUNCT", idx=7, dep_rel="punct", head_idx=9),
            _tok("сочные", "ADJ", idx=8, dep_rel="amod", head_idx=9),
            _tok("апельсины", "NOUN", idx=9, dep_rel="conj", head_idx=3),
            _tok(".", "PUNCT", idx=10, dep_rel="punct", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 4) is False
        assert self.handler.can_apply(tokens, 7) is False

    def test_apply_skips_when_closing_comma_unconfirmed(self):
        # "Он шёл, напевая песню, по улице." — parser absorbed "по улице"
        # into the gerund subtree; deleting only the opening comma would
        # leave a stray comma. Handler must skip, not half-delete.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("шёл", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok(
                "напевая",
                "VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=1,
                features={"VerbForm": "Conv"},
            ),
            _tok("песню", "NOUN", idx=4, dep_rel="obj", head_idx=3),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
            _tok("по", "ADP", idx=6, dep_rel="case", head_idx=7),
            _tok("улице", "NOUN", idx=7, dep_rel="obl", head_idx=3),
            _tok(".", "PUNCT", idx=8, dep_rel="punct", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 2) is False
        sentence = [t.text for t in tokens]
        assert self.handler.apply(tokens, sentence, 2, set()) is None
        assert sentence == [t.text for t in tokens]  # untouched, no orphan


# ── Real-stanza regressions for the comma audit fixes ────────────────────────


@pytest.mark.slow
class TestRealStanzaCommaAuditFixes:
    """Live-parse regressions for the §116/§101 audit findings.

    Marked slow: loads the real stanza backend (deselect with -m "not slow").
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        from synterr.core.pipeline import ErrorPipeline, GenerationConfig
        from synterr.core.registry import get_language

        language = get_language("ru")
        config = GenerationConfig(seed=42, use_depparse=True)
        return ErrorPipeline(language, config)

    def test_asyndetic_parataxis_clause(self, pipeline):
        # Was comma_compound (§104) before the fix; actual rule is §116 БСП.
        result = pipeline.apply_error("Лес рубят, щепки летят.", "comma_delete")
        assert result is not None
        assert result.errors[0].error_type == "comma_asyndetic"

    def test_asyndetic_impersonal_second_clause(self, pipeline):
        result = pipeline.apply_error("Шли дожди, дороги размыло.", "comma_delete")
        assert result is not None
        assert result.errors[0].error_type == "comma_asyndetic"

    def test_vocative_sentence_final(self, pipeline):
        # Was comma_subordinate (§107 ff.) before the fix; actual rule §101.
        result = pipeline.apply_error("Куда ты едешь, Иван?", "comma_delete")
        assert result is not None
        assert result.errors[0].error_type == "comma_vocative"

    def test_vocative_mid_sentence_pair(self, pipeline):
        result = pipeline.apply_error("Привет, Маша, как дела?", "comma_delete")
        assert result is not None
        assert result.errors[0].error_type == "comma_vocative"

    def test_pair_delete_never_leaves_stray_comma(self, pipeline):
        # Absorbed-trailing-material case: either the handler skips (None)
        # or it deletes a confirmed pair — never a half-pair with an orphan.
        result = pipeline.apply_error(
            "Он шёл, напевая песню, по улице.", "comma_pair_delete"
        )
        if result is not None:
            assert "," not in result.corrupted_tokens


# ── Regressions from the 2026-07 native-annotation pass ─────────────────────
# Fake-token reconstructions of mislabeled records from Artem's verification
# (synterr-internal/docs/research/annotations/): each case below was flagged
# wrong_tag/non_error at commit 7562674.


class TestAnnotationRegressionsComma:
    def test_finite_relative_clause_is_subordinate_not_isolation(self):
        # «...с землёй, на которой он стоит, ...» — finite relative clause
        # (own subject + relative pronoun) is СПП, not обособление.
        tokens = [
            _tok("землёй", "NOUN", idx=0, dep_rel="obl", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=5),
            _tok("на", "ADP", idx=2, dep_rel="case", head_idx=3),
            _tok(
                "которой",
                "PRON",
                idx=3,
                dep_rel="obl",
                head_idx=5,
                features={"PronType": "Rel"},
            ),
            _tok("он", "PRON", idx=4, dep_rel="nsubj", head_idx=5),
            _tok(
                "стоит",
                "VERB",
                idx=5,
                dep_rel="acl:relcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_acl_complement_clause_is_subordinate(self):
        # «утверждение, что Ганеев заставлял...» — a mark-introduced finite
        # complement clause behind bare acl is СПП.
        tokens = [
            _tok("утверждение", "NOUN", idx=0, dep_rel="obj", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=4),
            _tok("что", "SCONJ", idx=2, dep_rel="mark", head_idx=4),
            _tok("Ганеев", "PROPN", idx=3, dep_rel="nsubj", head_idx=4),
            _tok(
                "заставлял",
                "VERB",
                idx=4,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert _classify_comma(tokens, 1) == "comma_subordinate"

    def test_participial_phrase_stays_isolation(self):
        # «двигатели, вызвавшие критику» — bare participial оборот.
        tokens = [
            _tok("двигатели", "NOUN", idx=0, dep_rel="nsubj", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "вызвавшие",
                "VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("критику", "NOUN", idx=3, dep_rel="obj", head_idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_apposition_comma_is_isolation_not_homogeneous(self):
        # «с Уго Чавесом, президентом Венесуэлы» — приложение (§93).
        tokens = [
            _tok("с", "ADP", idx=0, dep_rel="case", head_idx=1),
            _tok("Чавесом", "PROPN", idx=1, dep_rel="obl", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("президентом", "NOUN", idx=3, dep_rel="appos", head_idx=1),
            _tok("Венесуэлы", "PROPN", idx=4, dep_rel="nmod", head_idx=3),
        ]
        assert _classify_comma(tokens, 2) == "comma_isolation"

    def test_postposed_attributive_adjective_is_isolation(self):
        # «источников, близких к ТВЦ» — обособленное определение.
        tokens = [
            _tok("источников", "NOUN", idx=0, dep_rel="nmod", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok("близких", "ADJ", idx=2, dep_rel="amod", head_idx=0),
            _tok("к", "ADP", idx=3, dep_rel="case", head_idx=4),
            _tok("ТВЦ", "PROPN", idx=4, dep_rel="obl", head_idx=2),
        ]
        assert _classify_comma(tokens, 1) == "comma_isolation"

    def test_speech_attribution_is_parenthetical_not_asyndetic(self):
        # «На место прибыл начальник, сообщает "Дейта.Ru"» — вводное
        # предложение-атрибуция, не БСП.
        tokens = [
            _tok("Прибыл", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("начальник", "NOUN", idx=1, dep_rel="nsubj", head_idx=0),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok(
                "сообщает",
                "VERB",
                idx=3,
                lemma="сообщать",
                dep_rel="parataxis",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
            _tok("газета", "NOUN", idx=4, dep_rel="nsubj", head_idx=3),
        ]
        assert _classify_comma(tokens, 2) == "comma_parenthetical"


class TestAnnotationRegressionsDash:
    def test_direct_speech_attribution_dash_skipped(self):
        # «..., — Майя протянула термос» — quotation plumbing, skip.
        tokens = [
            _tok("проголодался", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("—", "PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("Майя", "PROPN", idx=3, dep_rel="parataxis", head_idx=0),
            _tok("протянула", "VERB", idx=4, dep_rel="parataxis", head_idx=0),
        ]
        assert _classify_dash(tokens, 2) is None

    def test_clarifying_numeric_range_skipped(self):
        # «понизить — с 250 метров до 150» — уточнение, not a clause dash.
        tokens = [
            _tok(
                "понизить",
                "VERB",
                idx=0,
                dep_rel="root",
                head_idx=None,
                features={"VerbForm": "Inf"},
            ),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("с", "ADP", idx=2, dep_rel="case", head_idx=3),
            _tok("250", "NUM", idx=3, dep_rel="obl", head_idx=0),
            _tok("метров", "NOUN", idx=4, dep_rel="nmod", head_idx=3),
        ]
        assert _classify_dash(tokens, 1) is None

    def test_bsp_clauses_both_sides_is_asyndetic(self):
        # «Сергей поднял глаза — такой фразы он не слышал» — БСП.
        tokens = [
            _tok("Сергей", "PROPN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("поднял", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok("глаза", "NOUN", idx=2, dep_rel="obj", head_idx=1),
            _tok("—", "PUNCT", idx=3, dep_rel="punct", head_idx=7),
            _tok("фразы", "NOUN", idx=4, dep_rel="obj", head_idx=7),
            _tok("он", "PRON", idx=5, dep_rel="nsubj", head_idx=7),
            _tok("не", "PART", idx=6, dep_rel="advmod", head_idx=7),
            _tok(
                "слышал",
                "VERB",
                idx=7,
                dep_rel="parataxis",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert _classify_dash(tokens, 3) == "dash_asyndetic"

    def test_subj_pred_in_subordinate_clause_detected(self):
        # «Ранее сообщалось, что пострадавший — безработный» — the dash's
        # clause is verbless on both sides: §79 subj—pred, not ellipsis
        # (the clause opens with a subordinator).
        tokens = [
            _tok("сообщалось", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=4),
            _tok("что", "SCONJ", idx=2, dep_rel="mark", head_idx=4),
            _tok("пострадавший", "NOUN", idx=3, dep_rel="nsubj", head_idx=4),
            _tok("—", "PUNCT", idx=4, dep_rel="punct", head_idx=5),
            _tok("безработный", "NOUN", idx=5, dep_rel="ccomp", head_idx=0),
        ]
        assert _classify_dash(tokens, 4) == "dash_subj_pred"

    def test_ellipsis_conjunct_detected(self):
        # «Чиновники могут отдыхать 35 суток, а госслужащие — 30 суток» —
        # §80 verbless parallel conjunct.
        tokens = [
            _tok("Чиновники", "NOUN", idx=0, dep_rel="nsubj", head_idx=1),
            _tok("могут", "VERB", idx=1, dep_rel="root", head_idx=None),
            _tok(
                "отдыхать",
                "VERB",
                idx=2,
                dep_rel="xcomp",
                head_idx=1,
                features={"VerbForm": "Inf"},
            ),
            _tok("35", "NUM", idx=3, dep_rel="nummod", head_idx=4),
            _tok("суток", "NOUN", idx=4, dep_rel="obl", head_idx=2),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=7),
            _tok("а", "CCONJ", idx=6, dep_rel="cc", head_idx=7),
            _tok("госслужащие", "NOUN", idx=7, dep_rel="conj", head_idx=1),
            _tok("—", "PUNCT", idx=8, dep_rel="punct", head_idx=10),
            _tok("30", "NUM", idx=9, dep_rel="nummod", head_idx=10),
            _tok("суток", "NOUN", idx=10, dep_rel="orphan", head_idx=7),
        ]
        assert _classify_dash(tokens, 8) == "dash_ellipsis"

    def test_authorial_dash_after_verb_skipped(self):
        # «На основании плана формируется — арендный план» — deleting the
        # dash yields normative text.
        tokens = [
            _tok("формируется", "VERB", idx=0, dep_rel="root", head_idx=None),
            _tok("—", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok("арендный", "ADJ", idx=2, dep_rel="amod", head_idx=3),
            _tok("план", "NOUN", idx=3, dep_rel="nsubj", head_idx=0),
        ]
        assert _classify_dash(tokens, 1) is None


class TestAnnotationRegressionsPair:
    def test_split_compound_conjunction_is_not_a_pair(self):
        # «после того, как жюри удалилось, ...» — §108 junction, never a
        # paired isolation.
        tokens = [
            _tok("после", "ADP", idx=0, dep_rel="case", head_idx=1),
            _tok("того", "PRON", idx=1, lemma="то", dep_rel="obl", head_idx=None),
            _tok(",", "PUNCT", idx=2, dep_rel="punct", head_idx=5),
            _tok("как", "SCONJ", idx=3, dep_rel="mark", head_idx=5),
            _tok("жюри", "NOUN", idx=4, dep_rel="nsubj", head_idx=5),
            _tok(
                "удалилось",
                "VERB",
                idx=5,
                dep_rel="acl",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
            _tok(",", "PUNCT", idx=6, dep_rel="punct", head_idx=5),
        ]
        assert _find_comma_partner(tokens, 2) is None

    def test_chto_parataxis_is_not_a_parenthetical_pair(self):
        # «..., что должно сказаться на прибыли, ...» — присоединительное
        # придаточное (§110), not a вводное.
        tokens = [
            _tok("конкуренция", "NOUN", idx=0, dep_rel="nsubj", head_idx=None),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok(
                "что",
                "PRON",
                idx=2,
                lemma="что",
                dep_rel="nsubj",
                head_idx=3,
                features={"PronType": "Rel"},
            ),
            _tok(
                "должно",
                "ADJ",
                idx=3,
                dep_rel="parataxis",
                head_idx=0,
                features={"Variant": "Short"},
            ),
            _tok("сказаться", "VERB", idx=4, dep_rel="xcomp", head_idx=3),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
        ]
        assert _find_comma_partner(tokens, 1) is None

    def test_gerund_anchored_span_relabeled_pair_gerund(self):
        # «Будучи убеждён в том, ...» — a "participle" span anchored by a
        # gerund is a деепричастный оборот.
        tokens = [
            _tok("Он", "PRON", idx=0, dep_rel="nsubj", head_idx=6),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=3),
            _tok(
                "будучи",
                "AUX",
                idx=2,
                lemma="быть",
                dep_rel="cop",
                head_idx=3,
                features={"VerbForm": "Conv"},
            ),
            _tok(
                "убеждён",
                "VERB",
                idx=3,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part", "Variant": "Short"},
            ),
            _tok("твёрдо", "ADV", idx=4, dep_rel="advmod", head_idx=3),
            _tok(",", "PUNCT", idx=5, dep_rel="punct", head_idx=3),
            _tok("настаивал", "VERB", idx=6, dep_rel="root", head_idx=None),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result == (5, "pair_gerund")
