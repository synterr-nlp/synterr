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
        assert len(self.handler.subtypes) == 8

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


# ── DashDeleteHandler ───────────────────────────────────────────────────────


class TestDashDeleteHandler:
    handler = DashDeleteHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "dash_delete"
        assert self.handler.category == "PUNCT"
        assert self.handler.changes_length is True
        assert len(self.handler.subtypes) == 4

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

    def test_subj_pred_pron_adj(self):
        tokens = [
            _tok("Он", "PRON", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("хороший", "ADJ", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_subj_pred"

    def test_asyndetic_verb_verb(self):
        tokens = [
            _tok("пришёл", "VERB", idx=0),
            _tok("—", "PUNCT", idx=1),
            _tok("увидел", "VERB", idx=2),
        ]
        assert _classify_dash(tokens, 1) == "dash_asyndetic"

    def test_other_at_end(self):
        tokens = [
            _tok("слово", "NOUN", idx=0),
            _tok("—", "PUNCT", idx=1),
        ]
        assert _classify_dash(tokens, 1) == "dash_other"


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

    # ── Single-comma at sentence boundary (post-fix) ───────────────────────

    def test_sentence_start_preposed_participle_single_comma(self):
        # "Высушенные, они становятся синеватыми." — preposed adj/participle
        # at sentence start. Only ONE comma exists (the closing one); stanza
        # tags isolated adjectives as amod.
        tokens = [
            _tok("Высушенные", "ADJ", idx=0, dep_rel="amod", head_idx=2),
            _tok(",", "PUNCT", idx=1, dep_rel="punct", head_idx=0),
            _tok("они", "PRON", idx=2, dep_rel="nsubj", head_idx=3),
            _tok("становятся", "VERB", idx=3, dep_rel="root", head_idx=None),
            _tok("синеватыми", "ADJ", idx=4, dep_rel="obl", head_idx=3),
        ]
        result = _find_comma_partner(tokens, 1)
        assert result == (None, "pair_participle")

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
