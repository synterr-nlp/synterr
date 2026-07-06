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
        assert len(self.handler.subtypes) == 11

    def test_every_subtype_has_default_weight(self):
        assert set(self.handler.DEFAULT_WEIGHTS) == set(self.handler.subtypes)


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

    def test_cannot_apply_kak_after_any_punctuation(self):
        # Artem's M1.3 report: «, (, dashes etc. before «как» must refuse —
        # inserting after them double-punctuates
        handler = CommaInsertHandler()
        for mark in ("«", "(", "—", ":", ";"):
            tokens = [
                _tok("сказал", pos="VERB", idx=0),
                _tok(mark, pos="PUNCT", idx=1),
                _tok("как", pos="SCONJ", idx=2),
                _tok("экономист", pos="NOUN", idx=3),
            ]
            assert not handler.can_apply(tokens, 2), f"fired after {mark!r}"

    def test_cannot_apply_kak_after_mistagged_quote(self):
        # quotes sometimes escape the PUNCT tag — text-level fallback
        handler = CommaInsertHandler()
        tokens = [
            _tok("«", pos="X", idx=0),
            _tok("как", pos="SCONJ", idx=1),
            _tok("дела", pos="NOUN", idx=2),
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


# ── Bidirectional GREEN-tier subtypes ───────────────────────────────────────


def _homogeneous_tokens():
    """«Мама купила яблоки и груши» — single и, non-clausal conjuncts."""
    return [
        _tok("Мама", idx=0, dep_rel="nsubj", head_idx=1),
        _tok("купила", pos="VERB", idx=1, dep_rel="root", features={"VerbForm": "Fin"}),
        _tok("яблоки", idx=2, dep_rel="obj", head_idx=1),
        _tok("и", pos="CCONJ", idx=3, dep_rel="cc", head_idx=4),
        _tok("груши", idx=4, dep_rel="conj", head_idx=2),
    ]


class TestCommaHomogeneousConj:
    """§86 п.1: comma before a single и between non-clausal homogeneous members."""

    def test_detects_single_conj_non_clausal(self):
        handler = CommaInsertHandler()
        assert "comma_homogeneous_conj" in handler._detect_subtypes(
            _homogeneous_tokens(), 3
        )

    def test_apply_inserts_comma_before_conj(self):
        h = _force_subtype("comma_homogeneous_conj")
        tokens = _homogeneous_tokens()
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 3, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Мама", "купила", "яблоки", ",", "и", "груши"]
        assert result.fix_tag == "$DELETE"
        assert result.error_type == "comma_insert_comma_homogeneous_conj"

    def test_refuses_clausal_conjuncts(self):
        """«Солнце светило и птицы пели» — clausal conj = §104 ССП, where the
        comma is correct; that site belongs to comma_clause_junction."""
        tokens = [
            _tok("Солнце", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "светило",
                pos="VERB",
                idx=1,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("и", pos="CCONJ", idx=2, dep_rel="cc", head_idx=4),
            _tok("птицы", idx=3, dep_rel="nsubj", head_idx=4),
            _tok(
                "пели",
                pos="VERB",
                idx=4,
                dep_rel="conj",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
        ]
        detected = CommaInsertHandler()._detect_subtypes(tokens, 2)
        assert "comma_homogeneous_conj" not in detected
        assert "comma_clause_junction" in detected  # exact partition of cc-space
        h = _force_subtype("comma_homogeneous_conj")
        sentence = [t.text for t in tokens]
        assert h.apply(tokens, sentence, 2, set(), rng=Random(42)) is None
        assert sentence == [t.text for t in tokens]

    def test_refuses_repeated_conjunction(self):
        """«и яблони и груши» — repeated и (§87): the comma would be CORRECT."""
        tokens = [
            _tok("и", pos="CCONJ", idx=0, dep_rel="cc", head_idx=1),
            _tok("яблони", idx=1, dep_rel="nsubj", head_idx=4),
            _tok("и", pos="CCONJ", idx=2, dep_rel="cc", head_idx=3),
            _tok("груши", idx=3, dep_rel="conj", head_idx=1),
            _tok(
                "росли", pos="VERB", idx=4, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        assert "comma_homogeneous_conj" not in CommaInsertHandler()._detect_subtypes(
            tokens, 2
        )

    def test_refuses_repeated_conjunction_part_tagging(self):
        """Real stanza output: the leading «и» of «и X и Y» is PART/advmod on
        the first conjunct (verified on «росли и яблони и груши») — the
        repeated-conjunction guard must still catch it."""
        tokens = [
            _tok(
                "росли", pos="VERB", idx=0, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("и", pos="PART", idx=1, dep_rel="advmod", head_idx=2),
            _tok("яблони", idx=2, dep_rel="nsubj", head_idx=0),
            _tok("и", pos="CCONJ", idx=3, dep_rel="cc", head_idx=4),
            _tok("груши", idx=4, dep_rel="conj", head_idx=2),
        ]
        assert "comma_homogeneous_conj" not in CommaInsertHandler()._detect_subtypes(
            tokens, 3
        )

    def test_refuses_existing_comma(self):
        tokens = _homogeneous_tokens()
        tokens[2] = _tok(",", pos="PUNCT", idx=2, dep_rel="punct", head_idx=4)
        assert "comma_homogeneous_conj" not in CommaInsertHandler()._detect_subtypes(
            tokens, 3
        )

    def test_refuses_conj_before_subordinate_clause(self):
        """«и когда...» — §110 territory (comma_between_conjunctions)."""
        tokens = [
            _tok("холодно", pos="ADV", idx=0, dep_rel="root"),
            _tok("и", pos="CCONJ", idx=1, dep_rel="cc", head_idx=3),
            _tok("когда", pos="SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok("темно", pos="ADV", idx=3, dep_rel="conj", head_idx=0),
        ]
        assert "comma_homogeneous_conj" not in CommaInsertHandler()._detect_subtypes(
            tokens, 1
        )

    def test_refuses_adversative_conjunction(self):
        """«а/но» take the comma per §86 п.2 — not in the trigger set."""
        tokens = [
            _tok("мал", pos="ADJ", idx=0, dep_rel="root"),
            _tok("но", pos="CCONJ", idx=1, dep_rel="cc", head_idx=2),
            _tok("удал", pos="ADJ", idx=2, dep_rel="conj", head_idx=0),
        ]
        assert "comma_homogeneous_conj" not in CommaInsertHandler()._detect_subtypes(
            tokens, 1
        )


def _heavy_subject_tokens():
    """«Прибывшие участники конференции разместились» — heavy subject NP."""
    return [
        _tok(
            "Прибывшие",
            pos="VERB",
            idx=0,
            dep_rel="amod",
            head_idx=1,
            features={"VerbForm": "Part"},
        ),
        _tok("участники", idx=1, dep_rel="nsubj", head_idx=3),
        _tok("конференции", idx=2, dep_rel="nmod", head_idx=1),
        _tok(
            "разместились",
            pos="VERB",
            idx=3,
            dep_rel="root",
            features={"VerbForm": "Fin"},
        ),
    ]


class TestCommaSubjPred:
    """Comma between a heavy subject NP and its predicate (no § licenses it)."""

    def test_detects_heavy_subject(self):
        assert "comma_subj_pred" in CommaInsertHandler()._detect_subtypes(
            _heavy_subject_tokens(), 1
        )

    def test_apply_inserts_comma_before_predicate(self):
        h = _force_subtype("comma_subj_pred")
        tokens = _heavy_subject_tokens()
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == [
            "Прибывшие",
            "участники",
            "конференции",
            ",",
            "разместились",
        ]
        assert result.fix_tag == "$DELETE"

    def test_refuses_light_subject(self):
        """Single-token subject: «Мама мыла раму» must never fire."""
        tokens = [
            _tok("Мама", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "мыла", pos="VERB", idx=1, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("раму", idx=2, dep_rel="obj", head_idx=1),
        ]
        assert "comma_subj_pred" not in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_refuses_isolation_comma_at_boundary(self):
        """«Студент, читающий книгу, ушёл» — the closing isolation comma at the
        span boundary is LEGITIMATE punctuation; inserting is a non-error."""
        tokens = [
            _tok("Студент", idx=0, dep_rel="nsubj", head_idx=5),
            _tok(",", pos="PUNCT", idx=1, dep_rel="punct", head_idx=2),
            _tok(
                "читающий",
                pos="VERB",
                idx=2,
                dep_rel="acl",
                head_idx=0,
                features={"VerbForm": "Part"},
            ),
            _tok("книгу", idx=3, dep_rel="obj", head_idx=2),
            _tok(",", pos="PUNCT", idx=4, dep_rel="punct", head_idx=2),
            _tok(
                "ушёл", pos="VERB", idx=5, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        assert "comma_subj_pred" not in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_refuses_pronoun_subject(self):
        tokens = [
            _tok("Они", pos="PRON", idx=0, dep_rel="nsubj", head_idx=2),
            _tok("все", pos="DET", idx=1, dep_rel="det", head_idx=0),
            _tok(
                "ушли", pos="VERB", idx=2, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        assert "comma_subj_pred" not in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_refuses_predicate_not_adjacent(self):
        """Dash (or anything else) between subject span and predicate vetoes."""
        tokens = [
            _tok("Старший", pos="ADJ", idx=0, dep_rel="amod", head_idx=1),
            _tok("брат", idx=1, dep_rel="nsubj", head_idx=3),
            _tok("—", pos="PUNCT", idx=2, dep_rel="punct", head_idx=3),
            _tok("учитель", idx=3, dep_rel="root"),
        ]
        assert "comma_subj_pred" not in CommaInsertHandler()._detect_subtypes(tokens, 1)


class TestCommaPseudoParenthetical:
    """§99 п.2 Прим.: bracketing never-вводные words (single-comma MVP)."""

    def test_mid_sentence_comma_before(self):
        h = _force_subtype("comma_pseudo_parenthetical")
        tokens = [
            _tok("Он", pos="PRON", idx=0, dep_rel="nsubj", head_idx=4),
            _tok("ведь", pos="PART", idx=1, dep_rel="advmod", head_idx=4),
            _tok("ничего", pos="PRON", idx=2, dep_rel="obj", head_idx=4),
            _tok("не", pos="PART", idx=3, dep_rel="advmod", head_idx=4),
            _tok(
                "знал", pos="VERB", idx=4, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 1, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Он", ",", "ведь", "ничего", "не", "знал"]
        assert result.fix_tag == "$DELETE"

    def test_sentence_initial_comma_after(self):
        h = _force_subtype("comma_pseudo_parenthetical")
        tokens = [
            _tok("Ведь", pos="PART", idx=0, dep_rel="advmod", head_idx=3),
            _tok("он", pos="PRON", idx=1, dep_rel="nsubj", head_idx=3),
            _tok("не", pos="PART", idx=2, dep_rel="advmod", head_idx=3),
            _tok(
                "знал", pos="VERB", idx=3, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Ведь", ",", "он", "не", "знал"]

    def test_multiword_phrase_sentence_initial(self):
        """«Между тем, прошло два часа» — comma after the whole phrase."""
        h = _force_subtype("comma_pseudo_parenthetical")
        tokens = [
            _tok("Между", pos="ADP", idx=0, dep_rel="case", head_idx=1),
            _tok("тем", pos="PRON", idx=1, dep_rel="obl", head_idx=2),
            _tok(
                "прошло",
                pos="VERB",
                idx=2,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("два", pos="NUM", idx=3, dep_rel="nummod", head_idx=4),
            _tok("часа", idx=4, dep_rel="nsubj", head_idx=2),
        ]
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Между", "тем", ",", "прошло", "два", "часа"]

    def test_refuses_adjacent_comma(self):
        tokens = [
            _tok("Он", pos="PRON", idx=0, dep_rel="nsubj", head_idx=3),
            _tok(",", pos="PUNCT", idx=1),
            _tok("ведь", pos="PART", idx=2, dep_rel="advmod", head_idx=3),
            _tok(
                "знал", pos="VERB", idx=3, dep_rel="root", features={"VerbForm": "Fin"}
            ),
        ]
        assert (
            "comma_pseudo_parenthetical"
            not in CommaInsertHandler()._detect_subtypes(tokens, 2)
        )

    def test_refuses_compound_conjunction_prefix(self):
        """«даже если» is a §108 compound conjunction — a comma before it is
        legitimate clause punctuation, so pseudo must not fire on «даже»."""
        tokens = [
            _tok(
                "работаю",
                pos="VERB",
                idx=0,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("даже", pos="PART", idx=1, dep_rel="advmod", head_idx=3),
            _tok("если", pos="SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok(
                "устал",
                pos="VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert (
            "comma_pseudo_parenthetical"
            not in CommaInsertHandler()._detect_subtypes(tokens, 1)
        )

    def test_refuses_clause_opening_connective(self):
        """«...устал поэтому ушёл» parse where поэтому opens the following
        clause: a preceding comma can be legitimate → skip."""
        tokens = [
            _tok("Он", pos="PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "устал",
                pos="VERB",
                idx=1,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok("поэтому", pos="ADV", idx=2, dep_rel="advmod", head_idx=3),
            _tok(
                "ушёл",
                pos="VERB",
                idx=3,
                dep_rel="conj",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert (
            "comma_pseudo_parenthetical"
            not in CommaInsertHandler()._detect_subtypes(tokens, 2)
        )


class TestCommaAfterOdnako:
    """§99 п.7: sentence-initial «однако» = «но», takes no comma."""

    def _tokens(self):
        return [
            _tok("Однако", pos="ADV", idx=0, dep_rel="advmod", head_idx=2),
            _tok("переговоры", idx=1, dep_rel="nsubj", head_idx=2),
            _tok(
                "продолжились",
                pos="VERB",
                idx=2,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
            _tok(".", pos="PUNCT", idx=3, dep_rel="punct", head_idx=2),
        ]

    def test_detects_sentence_initial(self):
        assert "comma_after_odnako" in CommaInsertHandler()._detect_subtypes(
            self._tokens(), 0
        )

    def test_apply_inserts_comma_after(self):
        h = _force_subtype("comma_after_odnako")
        tokens = self._tokens()
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["Однако", ",", "переговоры", "продолжились", "."]
        assert result.fix_tag == "$DELETE"

    def test_refuses_mid_sentence(self):
        """Mid-clause однако is dual-function (вводное) — never fires."""
        tokens = [
            _tok("Он", pos="PRON", idx=0, dep_rel="nsubj", head_idx=3),
            _tok("однако", pos="ADV", idx=1, dep_rel="advmod", head_idx=3),
            _tok("не", pos="PART", idx=2, dep_rel="advmod", head_idx=3),
            _tok(
                "пришёл",
                pos="VERB",
                idx=3,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
        ]
        assert "comma_after_odnako" not in CommaInsertHandler()._detect_subtypes(
            tokens, 1
        )

    def test_refuses_existing_comma(self):
        tokens = self._tokens()
        tokens.insert(1, _tok(",", pos="PUNCT", idx=1))
        assert "comma_after_odnako" not in CommaInsertHandler()._detect_subtypes(
            tokens, 0
        )

    def test_refuses_interjection_exception(self):
        """«Однако, какой ветер!» — the comma IS correct here."""
        tokens = [
            _tok("Однако", pos="ADV", idx=0),
            _tok("какой", pos="DET", idx=1, lemma="какой"),
            _tok("ветер", idx=2),
            _tok("!", pos="PUNCT", idx=3),
        ]
        assert "comma_after_odnako" not in CommaInsertHandler()._detect_subtypes(
            tokens, 0
        )

    def test_fires_after_semicolon(self):
        tokens = [
            _tok(
                "шёл", pos="VERB", idx=0, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok(";", pos="PUNCT", idx=1),
            _tok("однако", pos="ADV", idx=2, dep_rel="advmod", head_idx=4),
            _tok("мы", pos="PRON", idx=3, dep_rel="nsubj", head_idx=4),
            _tok(
                "успели",
                pos="VERB",
                idx=4,
                dep_rel="parataxis",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert "comma_after_odnako" in CommaInsertHandler()._detect_subtypes(tokens, 2)


class TestCommaCompoundConjSplit:
    """§108 Прим.: non-splittable compound conjunctions take no internal comma."""

    def _tokens(self):
        return [
            _tok("Он", pos="PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _tok(
                "спал", pos="VERB", idx=1, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok(",", pos="PUNCT", idx=2, dep_rel="punct", head_idx=8),
            _tok("в", pos="ADP", idx=3, dep_rel="case", head_idx=5),
            _tok("то", pos="DET", idx=4, dep_rel="det", head_idx=5),
            _tok("время", idx=5, dep_rel="obl", head_idx=8),
            _tok("как", pos="SCONJ", idx=6, dep_rel="mark", head_idx=8),
            _tok("я", pos="PRON", idx=7, dep_rel="nsubj", head_idx=8),
            _tok(
                "работал",
                pos="VERB",
                idx=8,
                dep_rel="advcl",
                head_idx=1,
                features={"VerbForm": "Fin"},
            ),
        ]

    def test_detects_v_to_vremya_kak(self):
        assert "comma_compound_conj_split" in CommaInsertHandler()._detect_subtypes(
            self._tokens(), 3
        )

    def test_apply_inserts_comma_before_kak(self):
        h = _force_subtype("comma_compound_conj_split")
        tokens = self._tokens()
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 3, set(), rng=Random(42))
        assert result is not None
        assert sentence == [
            "Он",
            "спал",
            ",",
            "в",
            "то",
            "время",
            ",",
            "как",
            "я",
            "работал",
        ]
        assert result.fix_tag == "$DELETE"

    def test_detects_dazhe_esli(self):
        tokens = [
            _tok(
                "приду", pos="VERB", idx=0, dep_rel="root", features={"VerbForm": "Fin"}
            ),
            _tok("даже", pos="PART", idx=1, dep_rel="advmod", head_idx=3),
            _tok("если", pos="SCONJ", idx=2, dep_rel="mark", head_idx=3),
            _tok(
                "устану",
                pos="VERB",
                idx=3,
                dep_rel="advcl",
                head_idx=0,
                features={"VerbForm": "Fin"},
            ),
        ]
        assert "comma_compound_conj_split" in CommaInsertHandler()._detect_subtypes(
            tokens, 1
        )

    def test_refuses_partial_match(self):
        """«в то время» + noun continuation is a plain temporal PP."""
        tokens = [
            _tok("в", pos="ADP", idx=0, dep_rel="case", head_idx=2),
            _tok("то", pos="DET", idx=1, dep_rel="det", head_idx=2),
            _tok("время", idx=2, dep_rel="obl", head_idx=4),
            _tok("года", idx=3, dep_rel="nmod", head_idx=2),
            _tok("холодно", pos="ADV", idx=4, dep_rel="root"),
        ]
        assert "comma_compound_conj_split" not in CommaInsertHandler()._detect_subtypes(
            tokens, 0
        )

    def test_refuses_kak_phrase_continuation(self):
        """«тогда как раз» — trailing как opens a fixed phrase, not the conj."""
        tokens = [
            _tok("тогда", pos="ADV", idx=0, dep_rel="advmod", head_idx=3),
            _tok("как", pos="ADV", idx=1, dep_rel="advmod", head_idx=3),
            _tok("раз", pos="PART", idx=2, dep_rel="fixed", head_idx=1),
            _tok(
                "успели",
                pos="VERB",
                idx=3,
                dep_rel="root",
                features={"VerbForm": "Fin"},
            ),
        ]
        assert "comma_compound_conj_split" not in CommaInsertHandler()._detect_subtypes(
            tokens, 0
        )


class TestCommaXNeX:
    """§90 п.4: «X не X» / «X так X» repetition takes no internal comma."""

    def test_detects_x_ne_x(self):
        tokens = [
            _tok("работа", idx=0),
            _tok("не", pos="PART", idx=1),
            _tok("работа", idx=2),
            _tok(",", pos="PUNCT", idx=3),
            _tok("а", pos="CCONJ", idx=4),
            _tok("мучение", idx=5),
        ]
        assert "comma_x_ne_x" in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_apply_inserts_comma_before_ne(self):
        h = _force_subtype("comma_x_ne_x")
        tokens = [
            _tok("работа", idx=0),
            _tok("не", pos="PART", idx=1),
            _tok("работа", idx=2),
        ]
        sentence = [t.text for t in tokens]
        result = h.apply(tokens, sentence, 0, set(), rng=Random(42))
        assert result is not None
        assert sentence == ["работа", ",", "не", "работа"]
        assert result.fix_tag == "$DELETE"

    def test_detects_x_tak_x(self):
        tokens = [
            _tok("свадьба", idx=0),
            _tok("так", pos="PART", idx=1),
            _tok("свадьба", idx=2),
        ]
        assert "comma_x_ne_x" in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_refuses_different_words(self):
        tokens = [
            _tok("это", pos="PRON", idx=0),
            _tok("не", pos="PART", idx=1),
            _tok("работа", idx=2),
        ]
        assert "comma_x_ne_x" not in CommaInsertHandler()._detect_subtypes(tokens, 0)

    def test_refuses_different_pos(self):
        """Accidental surface repetition across POS must not fire."""
        tokens = [
            _tok("печь", pos="NOUN", idx=0),
            _tok("не", pos="PART", idx=1),
            _tok("печь", pos="VERB", idx=2),
        ]
        assert "comma_x_ne_x" not in CommaInsertHandler()._detect_subtypes(tokens, 0)


class TestZeroWeightExclusion:
    """Zero-weighted new subtypes never fire even when they are the only
    detected candidate at a token."""

    def test_zeroed_workhorse_is_excluded(self):
        h = CommaInsertHandler()
        h.set_subtype_weights({"comma_homogeneous_conj": 0})
        tokens = _homogeneous_tokens()
        sentence = [t.text for t in tokens]
        # Only comma_homogeneous_conj triggers at idx 3 — zero weight → None
        assert h._detect_subtypes(tokens, 3) == ["comma_homogeneous_conj"]
        assert h.apply(tokens, sentence, 3, set(), rng=Random(42)) is None
        assert sentence == [t.text for t in tokens]

    def test_enabled_subtypes_restriction(self):
        h = CommaInsertHandler()
        h.set_enabled_subtypes({"comma_subj_pred"})
        tokens = _homogeneous_tokens()
        sentence = [t.text for t in tokens]
        assert h.apply(tokens, sentence, 3, set(), rng=Random(42)) is None
