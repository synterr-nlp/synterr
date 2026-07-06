"""Tests for ArticleContractionHandler (au_split, aux_split, du_split)."""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken
from synterr.languages.french.errors.determiners import ArticleContractionHandler


class TestProtocol:
    handler = ArticleContractionHandler()

    def test_implements_protocol_surface(self):
        assert hasattr(self.handler, "name")
        assert hasattr(self.handler, "subtypes")
        assert hasattr(self.handler, "category")
        assert hasattr(self.handler, "changes_length")
        assert hasattr(self.handler, "can_apply")
        assert hasattr(self.handler, "apply")

    def test_identity(self):
        assert self.handler.name == "article_contraction"
        assert self.handler.subtypes == ["au_split", "aux_split", "du_split"]
        assert self.handler.category == "MORPH"
        # The two-token span is already present in the tokenizer's MWT
        # expansion (see module docstring); changes_length is still declared
        # True at the class level per the ErrorHandler protocol (one bool
        # per handler, matching ElisionApostropheHandler's own reasoning).
        assert self.handler.changes_length is True


class TestAuSplit:
    handler = ArticleContractionHandler()

    def test_au_positive(self, tokens_au_contraction):
        """"Il va au marché." -- à+le (unconditional, no partitive reading
        exists for au) splits into "à le"."""
        sentence = [t.text for t in tokens_au_contraction]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_au_contraction, 2) is True

        result = self.handler.apply(tokens_au_contraction, sentence, 2, modified)

        assert result is not None
        assert result.error_type == "article_contraction_au_split"
        assert result.category == "MORPH"
        assert result.original == "au"
        assert result.corrupted == "à le"
        assert result.fix_tag == "$REPLACE_au"
        assert result.start_idx == 2
        assert result.end_idx == 4
        # No token inserted or removed: the span was already split by the
        # tokenizer's MWT expansion.
        assert sentence == [t.text for t in tokens_au_contraction]
        assert len(sentence) == len(tokens_au_contraction)

    def test_capitalization_preservation_sentence_initial(self):
        """"Au marché, ..." -- sentence-initial "Au" must restore with a
        capital A, not lowercase "au"."""
        tokens = [
            AnalyzedToken(
                text="À", lemma="à", pos="ADP", features={},
                idx=0, dep_rel="case", head_idx=2,
            ),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=1, dep_rel="det", head_idx=2,
            ),
            AnalyzedToken(
                text="marché", lemma="marché", pos="NOUN",
                features={"Gender": "Masc", "Number": "Sing"},
                idx=2, dep_rel="obl:arg", head_idx=3,
            ),
        ]
        sentence = [t.text for t in tokens]

        result = self.handler.apply(tokens, sentence, 0, set())

        assert result is not None
        assert result.original == "Au"
        assert result.corrupted == "À le"
        assert result.fix_tag == "$REPLACE_Au"

    def test_guard_wrong_det_gender_la_not_le(self):
        """"à la gare" -- à + la never contracts (au is only à + le,
        masc. sg.); "la" must be rejected."""
        tokens = [
            AnalyzedToken(
                text="à", lemma="à", pos="ADP", features={},
                idx=0, dep_rel="case", head_idx=2,
            ),
            AnalyzedToken(
                text="la", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Fem", "Number": "Sing"},
                idx=1, dep_rel="det", head_idx=2,
            ),
            AnalyzedToken(
                text="gare", lemma="gare", pos="NOUN",
                features={"Gender": "Fem", "Number": "Sing"},
                idx=2, dep_rel="obl:arg", head_idx=3,
            ),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_det_is_clitic_pronoun_not_article(self):
        """"il le voit" -- "le" here is a clitic object PRON (dep_rel=obj),
        not a DET; must never be mistaken for an au/du site."""
        tokens = [
            AnalyzedToken(text="il", lemma="lui", pos="PRON", features={}, idx=0, dep_rel="nsubj", head_idx=2),
            AnalyzedToken(text="à", lemma="à", pos="ADP", features={}, idx=1, dep_rel="case", head_idx=3),
            AnalyzedToken(
                text="le", lemma="le", pos="PRON", features={},
                idx=2, dep_rel="obj", head_idx=0,
            ),
            AnalyzedToken(text="voit", lemma="voir", pos="VERB", features={}, idx=3, dep_rel="root", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_guard_head_idx_mismatch(self):
        """ADP and DET adjacent but attached to different heads -- not a
        genuine contraction pair, coincidental adjacency only."""
        tokens = [
            AnalyzedToken(text="à", lemma="à", pos="ADP", features={}, idx=0, dep_rel="case", head_idx=3),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=1, dep_rel="det", head_idx=2,
            ),
            AnalyzedToken(text="chat", lemma="chat", pos="NOUN", features={}, idx=2, dep_rel="nsubj", head_idx=3),
            AnalyzedToken(text="dort", lemma="dormir", pos="VERB", features={}, idx=3, dep_rel="root", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_idx_at_last_position(self):
        tokens = [
            AnalyzedToken(text="à", lemma="à", pos="ADP", features={}, idx=0, dep_rel="case", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_guard_non_adp_token(self):
        tokens = [
            AnalyzedToken(text="marché", lemma="marché", pos="NOUN", features={}, idx=0, dep_rel="root", head_idx=None),
            AnalyzedToken(text="est", lemma="être", pos="AUX", features={}, idx=1, dep_rel="cop", head_idx=0),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_apply_returns_none_when_gate_fails(self):
        tokens = [
            AnalyzedToken(text="chat", lemma="chat", pos="NOUN", features={}, idx=0, dep_rel="root", head_idx=None),
        ]
        sentence = ["chat"]
        assert self.handler.apply(tokens, sentence, 0, set()) is None
        assert sentence == ["chat"]  # untouched

    def test_guard_modified_index_blocks_apply(self, tokens_au_contraction):
        sentence = [t.text for t in tokens_au_contraction]
        assert self.handler.apply(tokens_au_contraction, sentence, 2, {2}) is None
        assert self.handler.apply(tokens_au_contraction, sentence, 2, {3}) is None


class TestAuxSplit:
    handler = ArticleContractionHandler()

    def _tokens_aux(self) -> list[AnalyzedToken]:
        """"Il pense aux vacances." -- à+les (unconditional plural)."""
        return [
            AnalyzedToken(text="Il", lemma="lui", pos="PRON", features={}, idx=0, dep_rel="nsubj", head_idx=1),
            AnalyzedToken(text="pense", lemma="penser", pos="VERB", features={}, idx=1, dep_rel="root", head_idx=None),
            AnalyzedToken(text="à", lemma="à", pos="ADP", features={}, idx=2, dep_rel="case", head_idx=4),
            AnalyzedToken(
                text="les", lemma="le", pos="DET",
                features={"Definite": "Def", "Number": "Plur"},
                idx=3, dep_rel="det", head_idx=4,
            ),
            AnalyzedToken(
                text="vacances", lemma="vacance", pos="NOUN",
                features={"Gender": "Fem", "Number": "Plur"},
                idx=4, dep_rel="obl:arg", head_idx=1,
            ),
            AnalyzedToken(text=".", lemma=".", pos="PUNCT", features={}, idx=5, dep_rel="punct", head_idx=1),
        ]

    def test_aux_positive(self):
        tokens = self._tokens_aux()
        sentence = [t.text for t in tokens]

        assert self.handler.can_apply(tokens, 2) is True

        result = self.handler.apply(tokens, sentence, 2, set())

        assert result is not None
        assert result.error_type == "article_contraction_aux_split"
        assert result.original == "aux"
        assert result.corrupted == "à les"
        assert result.fix_tag == "$REPLACE_aux"
        assert result.start_idx == 2
        assert result.end_idx == 4
        assert sentence == [t.text for t in tokens]

    def test_guard_de_les_never_matches_aux_or_du(self):
        """"de + les" is the (out-of-scope) des contraction, not one of the
        three subtypes this handler covers; must not be misclassified."""
        tokens = self._tokens_aux()
        tokens[2] = AnalyzedToken(text="de", lemma="de", pos="ADP", features={}, idx=2, dep_rel="case", head_idx=4)
        assert self.handler.can_apply(tokens, 2) is False


class TestDuSplit:
    handler = ArticleContractionHandler()

    def test_du_positive_obl_source_complement(self, tokens_du_contraction):
        """"Elle vient du village." -- de+le with head "village" as an
        obl:arg source complement of the verb (a genitive/source reading,
        not a partitive object): splittable."""
        sentence = [t.text for t in tokens_du_contraction]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_du_contraction, 2) is True

        result = self.handler.apply(tokens_du_contraction, sentence, 2, modified)

        assert result is not None
        assert result.error_type == "article_contraction_du_split"
        assert result.original == "du"
        assert result.corrupted == "de le"
        assert result.fix_tag == "$REPLACE_du"
        assert sentence == [t.text for t in tokens_du_contraction]

    def test_du_positive_nmod(self):
        """"le plat du jour" -- du jour is an nmod complement of the
        definite noun "plat" (BDL's own textbook example): splittable."""
        tokens = [
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=0, dep_rel="det", head_idx=1,
            ),
            AnalyzedToken(text="plat", lemma="plat", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=1, dep_rel="root", head_idx=None),
            AnalyzedToken(text="de", lemma="de", pos="ADP", features={}, idx=2, dep_rel="case", head_idx=4),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=3, dep_rel="det", head_idx=4,
            ),
            AnalyzedToken(text="jour", lemma="jour", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=4, dep_rel="nmod", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 2) is True

    def test_guard_partitive_object_boire_du_cafe(self):
        """"Il boit du café." -- du café is the partitive determiner marking
        an indeterminate quantity as the direct object of "boire"; must
        NEVER be split (no de+le paraphrase exists)."""
        tokens = [
            AnalyzedToken(text="Il", lemma="lui", pos="PRON", features={}, idx=0, dep_rel="nsubj", head_idx=1),
            AnalyzedToken(text="boit", lemma="boire", pos="VERB", features={}, idx=1, dep_rel="root", head_idx=None),
            AnalyzedToken(text="de", lemma="de", pos="ADP", features={}, idx=2, dep_rel="case", head_idx=4),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=3, dep_rel="det", head_idx=4,
            ),
            AnalyzedToken(text="café", lemma="café", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=4, dep_rel="obj", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 2) is False

    def test_guard_partitive_abstract_noun_avoir_du_courage(self):
        """"il faut du courage" -- abstract-noun partitive object: refused."""
        tokens = [
            AnalyzedToken(text="il", lemma="il", pos="PRON", features={}, idx=0, dep_rel="expl:subj", head_idx=1),
            AnalyzedToken(text="faut", lemma="falloir", pos="VERB", features={}, idx=1, dep_rel="root", head_idx=None),
            AnalyzedToken(text="de", lemma="de", pos="ADP", features={}, idx=2, dep_rel="case", head_idx=4),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=3, dep_rel="det", head_idx=4,
            ),
            AnalyzedToken(text="courage", lemma="courage", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=4, dep_rel="obj", head_idx=1),
        ]
        assert self.handler.can_apply(tokens, 2) is False

    def test_guard_head_not_noun(self):
        """de+le whose head isn't even a NOUN (e.g. a pronoun) must never
        pass the du gate, regardless of dep_rel."""
        tokens = [
            AnalyzedToken(text="de", lemma="de", pos="ADP", features={}, idx=0, dep_rel="case", head_idx=2),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=1, dep_rel="det", head_idx=2,
            ),
            AnalyzedToken(text="cela", lemma="cela", pos="PRON", features={}, idx=2, dep_rel="nmod", head_idx=3),
            AnalyzedToken(text="dépend", lemma="dépendre", pos="VERB", features={}, idx=3, dep_rel="root", head_idx=None),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_du_capitalization_preservation(self):
        """"Du courrier est arrivé." with "Du" as a genuine contraction
        (nmod head) preserves its sentence-initial capital."""
        tokens = [
            AnalyzedToken(text="De", lemma="de", pos="ADP", features={}, idx=0, dep_rel="case", head_idx=2),
            AnalyzedToken(
                text="le", lemma="le", pos="DET",
                features={"Definite": "Def", "Gender": "Masc", "Number": "Sing"},
                idx=1, dep_rel="det", head_idx=2,
            ),
            AnalyzedToken(text="bureau", lemma="bureau", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=2, dep_rel="nmod", head_idx=3),
            AnalyzedToken(text="courrier", lemma="courrier", pos="NOUN", features={"Gender": "Masc", "Number": "Sing"}, idx=3, dep_rel="root", head_idx=None),
        ]
        sentence = [t.text for t in tokens]

        result = self.handler.apply(tokens, sentence, 0, set())

        assert result is not None
        assert result.original == "Du"
        assert result.corrupted == "De le"
        assert result.fix_tag == "$REPLACE_Du"
