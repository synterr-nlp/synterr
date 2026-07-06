"""Tests for the French grammatical_homophone handler (PoC).

Fixtures ``tokens_avoir_3sg`` and ``tokens_etre_copula`` come from
conftest.py; the remaining subtypes (ce_se, on_ont, son_sont) plus the
guard/edge scenarios build small hand-authored token lists locally, since
conftest does not carry fixtures for those words specifically.
"""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken
from synterr.languages.french.errors.homophony import GrammaticalHomophoneErrorHandler


def _token(
    text: str,
    lemma: str,
    pos: str,
    features: dict[str, str] | None = None,
    idx: int = 0,
    dep_rel: str | None = None,
    head_idx: int | None = None,
) -> AnalyzedToken:
    return AnalyzedToken(
        text=text,
        lemma=lemma,
        pos=pos,
        features=features or {},
        idx=idx,
        dep_rel=dep_rel,
        head_idx=head_idx,
    )


class TestProtocol:
    handler = GrammaticalHomophoneErrorHandler()

    def test_implements_protocol(self):
        assert self.handler.name == "grammatical_homophone"
        assert self.handler.category == "SPELL"
        assert self.handler.changes_length is False
        assert self.handler.subtypes == [
            "a_à",
            "et_est",
            "ce_se",
            "on_ont",
            "son_sont",
        ]


class TestAA:
    handler = GrammaticalHomophoneErrorHandler()

    def test_a_to_à_swap(self, tokens_avoir_3sg):
        """ "Elle a mangé une pomme." - "a" (AUX avoir 3sg) -> "à"."""
        sentence = [t.text for t in tokens_avoir_3sg]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_avoir_3sg, 1) is True
        result = self.handler.apply(tokens_avoir_3sg, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_a_à"
        assert result.category == "SPELL"
        assert result.original == "a"
        assert result.corrupted == "à"
        assert result.fix_tag == "$REPLACE_a"
        assert sentence[1] == "à"
        assert modified == {1}

    def test_a_guard_non_avoir_reading(self):
        """ "a" tagged NOUN (rare Lexique reading "la lettre a") must not fire."""
        tokens = [
            _token("le", "le", "DET", idx=0, dep_rel="det", head_idx=1),
            _token("a", "a", "NOUN", {"Gender": "Masc", "Number": "Sing"}, idx=1),
        ]
        assert self.handler.can_apply(tokens, 1) is False

    def test_à_to_a_swap(self, tokens_au_contraction):
        """ "Il va au marché." - "à" (ADP, case marker) -> "a"."""
        sentence = [t.text for t in tokens_au_contraction]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_au_contraction, 2) is True
        result = self.handler.apply(tokens_au_contraction, sentence, 2, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_a_à"
        assert result.corrupted == "a"
        assert result.fix_tag == "$REPLACE_à"
        assert sentence[2] == "a"


class TestEtEst:
    handler = GrammaticalHomophoneErrorHandler()

    def _tokens_et(self) -> list[AnalyzedToken]:
        """ "Marie et Paul sont partis." (simplified: only "et" needs a coord head.)"""
        return [
            _token("Marie", "Marie", "PROPN", idx=0, dep_rel="nsubj", head_idx=3),
            _token("et", "et", "CCONJ", idx=1, dep_rel="cc", head_idx=2),
            _token("Paul", "Paul", "PROPN", idx=2, dep_rel="conj", head_idx=0),
            _token(
                "sont",
                "être",
                "AUX",
                {
                    "Mood": "Ind",
                    "Number": "Plur",
                    "Person": "3",
                    "Tense": "Pres",
                    "VerbForm": "Fin",
                },
                idx=3,
                dep_rel="cop",
                head_idx=4,
            ),
            _token("partis", "partir", "VERB", idx=4, dep_rel="root"),
        ]

    def test_et_to_est_swap(self):
        tokens = self._tokens_et()
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_et_est"
        assert result.corrupted == "est"
        assert result.fix_tag == "$REPLACE_et"
        assert sentence[1] == "est"

    def test_et_guard_wrong_pos(self):
        """ "et" mistagged as a non-CCONJ POS must not fire (conservative gate)."""
        tokens = self._tokens_et()
        tokens[1] = _token("et", "et", "ADV", idx=1, dep_rel="cc", head_idx=2)
        assert self.handler.can_apply(tokens, 1) is False

    def test_est_to_et_swap(self, tokens_etre_copula):
        """ "Marie est heureuse." - "est" (AUX être 3sg pres, copula) -> "et"."""
        sentence = [t.text for t in tokens_etre_copula]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens_etre_copula, 1) is True
        result = self.handler.apply(tokens_etre_copula, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_et_est"
        assert result.corrupted == "et"
        assert result.fix_tag == "$REPLACE_est"
        assert sentence[1] == "et"

    def test_est_guard_number_mismatch(self, tokens_etre_copula):
        """ "est" whose own Number feature contradicts 3sg must not fire."""
        tokens = list(tokens_etre_copula)
        tokens[1] = _token(
            "est",
            "être",
            "AUX",
            {"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres"},
            idx=1,
            dep_rel="cop",
            head_idx=2,
        )
        assert self.handler.can_apply(tokens, 1) is False


class TestCeSe:
    handler = GrammaticalHomophoneErrorHandler()

    def test_ce_det_before_noun_to_se(self):
        """ "Ce livre est grand." - "Ce" (DET dem, det->NOUN) -> "se"."""
        tokens = [
            _token(
                "Ce",
                "ce",
                "DET",
                {"Gender": "Masc", "Number": "Sing", "PronType": "Dem"},
                idx=0,
                dep_rel="det",
                head_idx=1,
            ),
            _token(
                "livre",
                "livre",
                "NOUN",
                {"Gender": "Masc", "Number": "Sing"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
            ),
            _token(
                "est",
                "être",
                "AUX",
                {"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres"},
                idx=2,
                dep_rel="cop",
                head_idx=3,
            ),
            _token("grand", "grand", "ADJ", idx=3, dep_rel="root"),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_ce_se"
        assert result.corrupted == "Se"
        assert sentence[0] == "Se"

    def test_ce_pron_subject_of_etre_to_se(self):
        """ "Ce sera formidable." - "Ce" (PRON dem, nsubj of être) -> "se"."""
        tokens = [
            _token(
                "Ce",
                "ce",
                "PRON",
                {"PronType": "Dem"},
                idx=0,
                dep_rel="nsubj",
                head_idx=1,
            ),
            _token(
                "sera",
                "être",
                "AUX",
                {"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Fut"},
                idx=1,
                dep_rel="cop",
                head_idx=2,
            ),
            _token("formidable", "formidable", "ADJ", idx=2, dep_rel="root"),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.corrupted == "Se"

    def test_se_to_ce_swap(self):
        """ "Il se lave." - "se" (PRON expl on VERB) -> "ce"."""
        tokens = [
            _token("Il", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=2),
            _token("se", "se", "PRON", idx=1, dep_rel="expl:comp", head_idx=2),
            _token("lave", "laver", "VERB", idx=2, dep_rel="root"),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_ce_se"
        assert result.corrupted == "ce"
        assert result.fix_tag == "$REPLACE_se"
        assert sentence[1] == "ce"

    def test_se_guard_head_not_verb(self):
        """ "se" with a reflexive-looking deprel but a non-verbal head must not fire."""
        tokens = [
            _token("Il", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=2),
            _token("se", "se", "PRON", idx=1, dep_rel="expl:comp", head_idx=2),
            _token("chat", "chat", "NOUN", idx=2, dep_rel="root"),
        ]
        assert self.handler.can_apply(tokens, 1) is False


class TestOnOnt:
    handler = GrammaticalHomophoneErrorHandler()

    def test_on_to_ont_swap(self):
        """ "On mange." - "on" (PRON nsubj) -> "ont"."""
        tokens = [
            _token("On", "on", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "mange",
                "manger",
                "VERB",
                {"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres"},
                idx=1,
                dep_rel="root",
            ),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_on_ont"
        assert result.corrupted == "Ont"
        assert result.fix_tag == "$REPLACE_On"
        assert sentence[0] == "Ont"

    def test_on_guard_head_number_mismatch(self):
        """ "on" whose governed verb is (inconsistently) plural must not fire."""
        tokens = [
            _token("on", "on", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "mangent",
                "manger",
                "VERB",
                {"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres"},
                idx=1,
                dep_rel="root",
            ),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_ont_to_on_swap(self):
        """ "Ils ont mangé." - "ont" (AUX avoir 3pl) -> "on"."""
        tokens = [
            _token("Ils", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "ont",
                "avoir",
                "AUX",
                {"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres"},
                idx=1,
                dep_rel="aux:tense",
                head_idx=2,
            ),
            _token(
                "mangé",
                "manger",
                "VERB",
                {"Tense": "Past", "VerbForm": "Part"},
                idx=2,
                dep_rel="root",
            ),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_on_ont"
        assert result.corrupted == "on"
        assert result.fix_tag == "$REPLACE_ont"
        assert sentence[1] == "on"

    def test_ont_guard_participle_number_mismatch(self):
        """ "ont" whose governed participle carries a contradicting explicit
        Number (e.g. agreement with a preceding singular direct object, "la
        pomme qu'ils ont mangée") must not fire."""
        tokens = [
            _token("ils", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "ont",
                "avoir",
                "AUX",
                {"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres"},
                idx=1,
                dep_rel="aux:tense",
                head_idx=2,
            ),
            _token(
                "mangée",
                "manger",
                "VERB",
                {
                    "Gender": "Fem",
                    "Number": "Sing",
                    "Tense": "Past",
                    "VerbForm": "Part",
                },
                idx=2,
                dep_rel="acl:relcl",
            ),
        ]
        assert self.handler.can_apply(tokens, 1) is False


class TestSonSont:
    handler = GrammaticalHomophoneErrorHandler()

    def test_son_to_sont_swap(self):
        """ "Son livre est grand." - "Son" (DET poss->NOUN) -> "sont"."""
        tokens = [
            _token(
                "Son",
                "son",
                "DET",
                {"Gender": "Masc", "Number": "Sing", "Poss": "Yes"},
                idx=0,
                dep_rel="det",
                head_idx=1,
            ),
            _token(
                "livre",
                "livre",
                "NOUN",
                {"Gender": "Masc", "Number": "Sing"},
                idx=1,
                dep_rel="nsubj",
                head_idx=2,
            ),
            _token(
                "est",
                "être",
                "AUX",
                {"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres"},
                idx=2,
                dep_rel="cop",
                head_idx=3,
            ),
            _token("grand", "grand", "ADJ", idx=3, dep_rel="root"),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 0) is True
        result = self.handler.apply(tokens, sentence, 0, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_son_sont"
        assert result.corrupted == "Sont"
        assert result.fix_tag == "$REPLACE_Son"
        assert sentence[0] == "Sont"

    def test_son_guard_head_not_noun(self):
        """ "son" DET whose det-arc head is not a NOUN (contrived/inconsistent
        parse) must not fire."""
        tokens = [
            _token(
                "son",
                "son",
                "DET",
                {"Gender": "Masc", "Number": "Sing", "Poss": "Yes"},
                idx=0,
                dep_rel="det",
                head_idx=1,
            ),
            _token("partira", "partir", "VERB", idx=1, dep_rel="root"),
        ]
        assert self.handler.can_apply(tokens, 0) is False

    def test_sont_to_son_swap(self):
        """ "Ils sont arrivés." - "sont" (AUX être 3pl) -> "son"."""
        tokens = [
            _token("Ils", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "sont",
                "être",
                "AUX",
                {"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres"},
                idx=1,
                dep_rel="aux:tense",
                head_idx=2,
            ),
            _token("arrivés", "arriver", "VERB", idx=2, dep_rel="root"),
        ]
        sentence = [t.text for t in tokens]
        modified: set[int] = set()

        assert self.handler.can_apply(tokens, 1) is True
        result = self.handler.apply(tokens, sentence, 1, modified)

        assert result is not None
        assert result.error_type == "grammatical_homophone_son_sont"
        assert result.corrupted == "son"
        assert result.fix_tag == "$REPLACE_sont"
        assert sentence[1] == "son"


class TestCapitalization:
    handler = GrammaticalHomophoneErrorHandler()

    def test_capitalization_preserved(self):
        """Title-case and all-caps surface forms keep their casing pattern."""
        # Title case: "On" -> "Ont" (single leading capital).
        tokens_title = [
            _token("On", "on", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "mange",
                "manger",
                "VERB",
                {"Number": "Sing", "Person": "3"},
                idx=1,
                dep_rel="root",
            ),
        ]
        sentence_title = [t.text for t in tokens_title]
        result_title = self.handler.apply(tokens_title, sentence_title, 0, set())
        assert result_title is not None
        assert sentence_title[0] == "Ont"

        # All-caps: "ONT" -> "ON".
        tokens_upper = [
            _token("Ils", "lui", "PRON", idx=0, dep_rel="nsubj", head_idx=1),
            _token(
                "ONT",
                "avoir",
                "AUX",
                {"Number": "Plur", "Person": "3"},
                idx=1,
                dep_rel="aux:tense",
                head_idx=2,
            ),
            _token("mangé", "manger", "VERB", idx=2, dep_rel="root"),
        ]
        sentence_upper = [t.text for t in tokens_upper]
        result_upper = self.handler.apply(tokens_upper, sentence_upper, 1, set())
        assert result_upper is not None
        assert sentence_upper[1] == "ON"
