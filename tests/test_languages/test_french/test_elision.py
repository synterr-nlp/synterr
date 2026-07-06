"""Tests for ElisionApostropheHandler (elision_omit, euphonic_t_drop)."""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken
from synterr.languages.french.errors.elision import ElisionApostropheHandler


class TestProtocol:
    handler = ElisionApostropheHandler()

    def test_implements_protocol_surface(self):
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "subtypes")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")

    def test_identity(self):
        assert self.handler.name == "elision_apostrophe"
        assert self.handler.subtypes == ["elision_omit", "euphonic_t_drop"]
        assert self.handler.category == "SPELL"
        # euphonic_t_drop deletes a token; the protocol's changes_length is
        # one bool per handler, not per subtype (see module docstring).
        assert self.handler.changes_length is True


class TestElisionOmit:
    handler = ElisionApostropheHandler()

    def test_l_apostrophe_before_noun(self, tokens_elided_l):
        """ "L'arbre est grand." -> "Le arbre est grand." — the flagship
        case: fr_sequoia's DET token for "L'" carries no Gender feature of
        its own (see conftest), so resolution must fall back to the
        following noun's Gender."""
        sentence = [t.text for t in tokens_elided_l]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_elided_l, 0) is True

        result = self.handler.apply(tokens_elided_l, sentence, 0, modified)

        assert result is not None
        assert result.error_type == "elision_apostrophe_elision_omit"
        assert result.category == "SPELL"
        assert result.original == "L'"
        assert result.corrupted == "Le"
        assert result.fix_tag == "$REPLACE_L'"
        assert sentence[0] == "Le"
        assert sentence[1] == "arbre"  # untouched — no token added/removed
        assert len(sentence) == len(tokens_elided_l)

    def test_qu_apostrophe_before_pronoun(self, tokens_elided_qu):
        """ "Qu'il vienne bientôt !" -> "Que il vienne bientôt !" —
        que -> qu' is a unique (unambiguous) elision, no gender needed."""
        sentence = [t.text for t in tokens_elided_qu]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_elided_qu, 0) is True

        result = self.handler.apply(tokens_elided_qu, sentence, 0, modified)

        assert result is not None
        assert result.corrupted == "Que"
        assert result.fix_tag == "$REPLACE_Qu'"
        assert sentence == ["Que", "il", "vienne", "bientôt", "!"]

    def test_je_apostrophe_unique_mapping(self):
        """ "J'ai froid." -> "Je ai froid." — j' has no other source word,
        so no disambiguation is needed."""
        tokens = [
            AnalyzedToken(
                text="J'",
                lemma="moi",
                pos="PRON",
                features={"Number": "Sing", "Person": "1"},
                idx=0,
            ),
            AnalyzedToken(
                text="ai",
                lemma="avoir",
                pos="AUX",
                features={
                    "Mood": "Ind",
                    "Number": "Sing",
                    "Person": "1",
                    "Tense": "Pres",
                },
                idx=1,
            ),
            AnalyzedToken(text="froid", lemma="froid", pos="NOUN", features={}, idx=2),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=3),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.corrupted == "Je"
        assert sentence == ["Je", "ai", "froid", "."]

    def test_se_reflexive_pronoun_disambiguation(self):
        """ "Elle s'habille." -> "Elle se habille." — s' before a verb, with
        the eliding token itself tagged PRON (reflexive clitic), resolves to
        "se" rather than "si"."""
        tokens = [
            AnalyzedToken(text="Elle", lemma="lui", pos="PRON", features={}, idx=0),
            AnalyzedToken(
                text="s'",
                lemma="se",
                pos="PRON",
                features={"Reflex": "Yes"},
                idx=1,
            ),
            AnalyzedToken(
                text="habille", lemma="habiller", pos="VERB", features={}, idx=2
            ),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=3),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, modified)

        assert result is not None
        assert result.corrupted == "se"
        assert sentence == ["Elle", "se", "habille", "."]

    def test_si_conjunction_disambiguation_before_il(self):
        """ "S'il pleut, nous resterons." -> "Si il pleut, ..." — s' tagged
        SCONJ and followed by "il" resolves to "si" (elision.json: si only
        elides before il/ils)."""
        tokens = [
            AnalyzedToken(text="S'", lemma="si", pos="SCONJ", features={}, idx=0),
            AnalyzedToken(text="il", lemma="lui", pos="PRON", features={}, idx=1),
            AnalyzedToken(
                text="pleut", lemma="pleuvoir", pos="VERB", features={}, idx=2
            ),
            AnalyzedToken(text=",", lemma=",", pos="PUNCT", features={}, idx=3),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.corrupted == "Si"  # capitalization preserved, not "SI"
        assert sentence[0] == "Si"

    def test_capitalization_preservation_single_letter_elision(self):
        """A single capital letter + apostrophe ("S'", "L'", "J'"...) must
        not be mistaken for an all-caps acronym: str.isupper() ignores the
        apostrophe, so a naive length check would wrongly upper-case the
        whole restored word ("SI" instead of "Si")."""
        tokens = [
            AnalyzedToken(text="D'", lemma="de", pos="ADP", features={}, idx=0),
            AnalyzedToken(text="hiver", lemma="hiver", pos="NOUN", features={}, idx=1),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.corrupted == "De"
        assert result.corrupted != "DE"

    def test_guard_h_aspire_word_never_treated_as_elision_site(self):
        """h-aspiré words must never be counted as elision sites, even if a
        (malformed/unexpected) upstream parse presents an elided token in
        front of one."""
        tokens = [
            AnalyzedToken(
                text="l'",
                lemma="le",
                pos="DET",
                features={},
                idx=0,
            ),
            AnalyzedToken(text="héros", lemma="héros", pos="NOUN", features={}, idx=1),
        ]

        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_punctuation_after_elided_token(self):
        tokens = [
            AnalyzedToken(text="j'", lemma="moi", pos="PRON", features={}, idx=0),
            AnalyzedToken(text="...", lemma="...", pos="PUNCT", features={}, idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_non_elided_token_rejected(self):
        """A plain word (no trailing apostrophe) is never an elision_omit
        site."""
        tokens = [
            AnalyzedToken(text="chat", lemma="chat", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text="noir", lemma="noir", pos="ADJ", features={}, idx=1),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_ambiguous_le_la_without_gender_returns_false(self):
        """l' as a clitic object pronoun directly before a verb, with no
        Gender feature anywhere to resolve le vs la, must not be guessed."""
        tokens = [
            AnalyzedToken(text="Je", lemma="moi", pos="PRON", features={}, idx=0),
            AnalyzedToken(text="l'", lemma="le", pos="PRON", features={}, idx=1),
            AnalyzedToken(text="aime", lemma="aimer", pos="VERB", features={}, idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_apply_returns_none_when_gate_fails(self):
        tokens = [
            AnalyzedToken(text="chat", lemma="chat", pos="NOUN", features={}, idx=0),
        ]
        sentence = ["chat"]
        assert self.handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == ["chat"]  # untouched


class TestEuphonicTDrop:
    handler = ElisionApostropheHandler()

    def test_aime_t_il_positive(self, tokens_t_il_inversion):
        """ "Aime-t-il le chocolat ?" -- drop the -t- token between the
        vowel-final verb "Aime" and the inverted pronoun "-il"."""
        sentence = [t.text for t in tokens_t_il_inversion]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_t_il_inversion, 1) is True

        result = self.handler.apply(tokens_t_il_inversion, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "elision_apostrophe_euphonic_t_drop"
        assert result.original == "-t"
        assert result.corrupted == ""
        assert result.fix_tag == "$APPEND_-t"
        assert sentence == ["Aime", "-il", "le", "chocolat", "?"]

    def test_convaincre_irregular_analogy(self):
        """ "Convainc-t-il son adversaire ?" -- vaincre/convaincre take -t-
        by analogy despite their 3sg form ending in "c", per BDL."""
        tokens = [
            AnalyzedToken(
                text="Convainc",
                lemma="convaincre",
                pos="VERB",
                features={
                    "Mood": "Ind",
                    "Number": "Sing",
                    "Person": "3",
                    "Tense": "Pres",
                },
                idx=0,
            ),
            AnalyzedToken(text="-t", lemma="tui", pos="PRON", features={}, idx=1),
            AnalyzedToken(text="-il", lemma="lui", pos="PRON", features={}, idx=2),
            AnalyzedToken(text="?", lemma="?", pos="PUNCT", features={}, idx=3),
        ]
        assert self.handler.can_apply(tokens, 1) is True

    def test_guard_verb_ending_in_consonant_without_irregular_lemma(self):
        """A verb ending neither in a vowel trigger nor belonging to the
        vaincre/convaincre irregular set must not have its (hypothetical)
        -t- token dropped as a genuine euphonic-t case -- conservative
        refusal on an inconsistent/adversarial parse."""
        tokens = [
            AnalyzedToken(
                text="Prend", lemma="prendre", pos="VERB", features={}, idx=0
            ),
            AnalyzedToken(text="-t", lemma="tui", pos="PRON", features={}, idx=1),
            AnalyzedToken(text="-on", lemma="on", pos="PRON", features={}, idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_guard_pronoun_not_in_trigger_set(self):
        tokens = [
            AnalyzedToken(text="Aime", lemma="aimer", pos="VERB", features={}, idx=0),
            AnalyzedToken(text="-t", lemma="tui", pos="PRON", features={}, idx=1),
            AnalyzedToken(text="-elles", lemma="lui", pos="PRON", features={}, idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_guard_previous_token_not_verb(self):
        tokens = [
            AnalyzedToken(text="table", lemma="table", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text="-t", lemma="tui", pos="PRON", features={}, idx=1),
            AnalyzedToken(text="-il", lemma="lui", pos="PRON", features={}, idx=2),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_guard_modified_anchor_blocks_apply(self, tokens_t_il_inversion):
        """If the verb (idx-1) was already corrupted by another handler,
        the $APPEND anchor at idx-1 would silently clobber its fix tag --
        apply() must refuse."""
        sentence = [t.text for t in tokens_t_il_inversion]
        modified = {0}  # the verb token already modified

        result = self.handler.apply(tokens_t_il_inversion, sentence, 1, modified)

        assert result is None
        assert sentence == [t.text for t in tokens_t_il_inversion]  # untouched

    def test_apply_dispatches_correct_subtype_over_elision(self, tokens_t_il_inversion):
        """apply() at the euphonic-t index must never fall through to the
        elision_omit path (the "-t" token itself never matches the elision
        lexicon, but this pins the dispatch order)."""
        sentence = [t.text for t in tokens_t_il_inversion]
        result = self.handler.apply(tokens_t_il_inversion, sentence, 1, set())
        assert result.error_type == "elision_apostrophe_euphonic_t_drop"
