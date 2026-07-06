"""Tests for the French pp_agreement handler (PoC flagship #2).

Covers both subtypes (``etre_strip``, ``avoir_cod_ante_strip``), the
conservative can_apply guards (no aux, wrong deprel, postposed object,
irregular participle, no agreement marking, wrong POS/VerbForm), and
capitalization preservation via the local ``_match_capitalization`` helper.

Uses the shared conftest fixtures where they already fit the gate
(``tokens_participle_que_relative``, ``tokens_avoir_3sg``,
``tokens_etre_copula``, ``tokens_modal_infinitive``) plus small
hand-built token lists for scenarios not covered by conftest (étre-strip
positives, clitic la/les objects, and each guard's negative case).
"""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken
from synterr.languages.french.errors.pp_agreement import (
    PastParticipleAgreementHandler,
    _match_capitalization,
    _strip_regular_participle,
)


def make_handler() -> PastParticipleAgreementHandler:
    return PastParticipleAgreementHandler()


# ---------------------------------------------------------------------------
# _strip_regular_participle: orthographic stripping + irregular guards
# ---------------------------------------------------------------------------


def test_strip_regular_participle_fem_sing():
    assert _strip_regular_participle("partie", "Fem", "Sing") == "parti"


def test_strip_regular_participle_masc_plur():
    assert _strip_regular_participle("partis", None, "Plur") == "parti"


def test_strip_regular_participle_fem_plur():
    assert _strip_regular_participle("mangées", "Fem", "Plur") == "mangé"


def test_strip_regular_participle_rejects_irregular_fem_sing():
    # mise (mettre) -> stem "mis" ends in a consonant, not a regular vowel.
    assert _strip_regular_participle("mise", "Fem", "Sing") is None


def test_strip_regular_participle_rejects_irregular_fem_plur():
    # prises (prendre) -> stem "pris" ends in a consonant.
    assert _strip_regular_participle("prises", "Fem", "Plur") is None


def test_strip_regular_participle_rejects_masc_plur_blocklist():
    # "mis" (masc plur, invariant) would orthographically look like a
    # regular "-i" stem after stripping the trailing "s" ("mi") - the
    # blocklist catches this false positive that the vowel check alone
    # cannot.
    assert _strip_regular_participle("mis", None, "Plur") is None


def test_strip_regular_participle_rejects_no_marking():
    # Masc singular already - nothing to strip.
    assert _strip_regular_participle("parti", "Masc", "Sing") is None
    assert _strip_regular_participle("parti", None, None) is None


# ---------------------------------------------------------------------------
# _match_capitalization
# ---------------------------------------------------------------------------


def test_match_capitalization_leading_cap():
    assert _match_capitalization("Partie", "parti") == "Parti"


def test_match_capitalization_all_caps():
    assert _match_capitalization("PARTIE", "parti") == "PARTI"


def test_match_capitalization_lowercase_passthrough():
    assert _match_capitalization("partie", "parti") == "parti"


# ---------------------------------------------------------------------------
# etre_strip: positive cases (hand-built - "Elle est partie.", "Ils sont
# partis.")
# ---------------------------------------------------------------------------


def _tokens_etre_partie() -> list[AnalyzedToken]:
    """"Elle est partie." - être + fem-sing subject, regular participle."""
    return [
        AnalyzedToken(
            text="Elle", lemma="lui", pos="PRON",
            features={"Gender": "Fem", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="est", lemma="être", pos="AUX",
            features={"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=1, dep_rel="aux:tense", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="partie", lemma="partir", pos="VERB",
            features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
            idx=2, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text=".", lemma=".", pos="PUNCT", features={},
            idx=3, dep_rel="punct", head_idx=2, extra={},
        ),
    ]


def _tokens_etre_partis() -> list[AnalyzedToken]:
    """"Ils sont partis." - être + masc-plur subject."""
    return [
        AnalyzedToken(
            text="Ils", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Plur", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="sont", lemma="être", pos="AUX",
            features={"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=1, dep_rel="aux:tense", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="partis", lemma="partir", pos="VERB",
            features={"Gender": "Masc", "Number": "Plur", "Tense": "Past", "VerbForm": "Part"},
            idx=2, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text=".", lemma=".", pos="PUNCT", features={},
            idx=3, dep_rel="punct", head_idx=2, extra={},
        ),
    ]


def test_can_apply_etre_strip_fem_sing_positive():
    tokens = _tokens_etre_partie()
    assert make_handler().can_apply(tokens, 2) is True


def test_apply_etre_strip_fem_sing_produces_parti():
    tokens = _tokens_etre_partie()
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 2, modified)
    assert result is not None
    assert result.error_type == "etre_strip"
    assert result.category == "MORPH"
    assert result.original == "partie"
    assert result.corrupted == "parti"
    assert result.fix_tag == "$REPLACE_partie"
    assert sentence[2] == "parti"
    assert 2 in modified


def test_can_apply_etre_strip_masc_plur_positive():
    tokens = _tokens_etre_partis()
    assert make_handler().can_apply(tokens, 2) is True


def test_apply_etre_strip_masc_plur_produces_parti():
    tokens = _tokens_etre_partis()
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 2, modified)
    assert result is not None
    assert result.error_type == "etre_strip"
    assert result.corrupted == "parti"
    assert sentence[2] == "parti"


def test_apply_preserves_capitalization_etre_strip():
    tokens = _tokens_etre_partie()
    tokens[2] = AnalyzedToken(
        text="Partie", lemma="partir", pos="VERB",
        features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
        idx=2, dep_rel="root", head_idx=None, extra={},
    )
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 2, modified)
    assert result is not None
    assert result.corrupted == "Parti"
    assert sentence[2] == "Parti"


# ---------------------------------------------------------------------------
# avoir_cod_ante_strip: positive cases
# ---------------------------------------------------------------------------


def test_can_apply_avoir_cod_ante_strip_relative_que(tokens_participle_que_relative):
    # "Les pommes qu'il a mangées étaient vertes." - flagship conftest case.
    assert make_handler().can_apply(tokens_participle_que_relative, 5) is True


def test_apply_avoir_cod_ante_strip_relative_que_produces_mange(
    tokens_participle_que_relative,
):
    tokens = tokens_participle_que_relative
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 5, modified)
    assert result is not None
    assert result.error_type == "avoir_cod_ante_strip"
    assert result.original == "mangées"
    assert result.corrupted == "mangé"
    assert result.fix_tag == "$REPLACE_mangées"
    assert sentence[5] == "mangé"


def _tokens_avoir_clitic_la() -> list[AnalyzedToken]:
    """"Il l'a mangée." - avoir + anteposed direct-object clitic "l'" (la)."""
    return [
        AnalyzedToken(
            text="Il", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="l'", lemma="le", pos="PRON",
            features={"Gender": "Fem", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=1, dep_rel="obj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="a", lemma="avoir", pos="AUX",
            features={"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=2, dep_rel="aux:tense", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="mangée", lemma="manger", pos="VERB",
            features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
            idx=3, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text=".", lemma=".", pos="PUNCT", features={},
            idx=4, dep_rel="punct", head_idx=3, extra={},
        ),
    ]


def test_can_apply_avoir_cod_ante_strip_clitic_la():
    tokens = _tokens_avoir_clitic_la()
    assert make_handler().can_apply(tokens, 3) is True


def test_apply_avoir_cod_ante_strip_clitic_la_produces_mange():
    tokens = _tokens_avoir_clitic_la()
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 3, modified)
    assert result is not None
    assert result.error_type == "avoir_cod_ante_strip"
    assert result.corrupted == "mangé"


# ---------------------------------------------------------------------------
# Guard cases - must NOT apply
# ---------------------------------------------------------------------------


def test_can_apply_false_no_agreement_marking(tokens_avoir_3sg):
    # "Elle a mangé une pomme." - masc-sing participle, no marking to strip.
    assert make_handler().can_apply(tokens_avoir_3sg, 2) is False


def test_can_apply_false_non_verb_pos(tokens_etre_copula):
    # "Marie est heureuse." - heureuse is ADJ (copula predicate), not a
    # compound-tense participle.
    assert make_handler().can_apply(tokens_etre_copula, 2) is False


def test_can_apply_false_infinitive_verbform(tokens_modal_infinitive):
    # "Il veut manger une pomme." - VerbForm=Inf, not Part.
    assert make_handler().can_apply(tokens_modal_infinitive, 2) is False


def test_can_apply_false_no_aux_found():
    # Adjectival participle with no compound-tense aux dependent at all
    # (e.g. "la porte fermée" - fermée modifies porte directly, not part of
    # a passé composé).
    tokens = [
        AnalyzedToken(
            text="porte", lemma="porte", pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=0, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text="fermée", lemma="fermer", pos="VERB",
            features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
            idx=1, dep_rel="amod", head_idx=0, extra={},
        ),
    ]
    assert make_handler().can_apply(tokens, 1) is False


def test_can_apply_false_iobj_not_obj():
    # Indirect-object clitic "leur" precedes the participle but is iobj,
    # not obj - must not trigger the anteposed-COD gate.
    tokens = [
        AnalyzedToken(
            text="Il", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="leur", lemma="leur", pos="PRON",
            features={"Number": "Plur", "Person": "3", "PronType": "Prs"},
            idx=1, dep_rel="iobj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="a", lemma="avoir", pos="AUX",
            features={"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=2, dep_rel="aux:tense", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="offertes", lemma="offrir", pos="VERB",
            features={"Gender": "Fem", "Number": "Plur", "Tense": "Past", "VerbForm": "Part"},
            idx=3, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text="fleurs", lemma="fleur", pos="NOUN",
            features={"Gender": "Fem", "Number": "Plur"},
            idx=4, dep_rel="obj", head_idx=3, extra={},
        ),
    ]
    assert make_handler().can_apply(tokens, 3) is False


def test_can_apply_false_postposed_object():
    # Direct object follows the participle linearly - agreement is (per the
    # contrived features here) present, but a postposed obj must not
    # satisfy the anteposed-COD gate.
    tokens = [
        AnalyzedToken(
            text="Il", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=1, extra={},
        ),
        AnalyzedToken(
            text="a", lemma="avoir", pos="AUX",
            features={"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=1, dep_rel="aux:tense", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="mangée", lemma="manger", pos="VERB",
            features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
            idx=2, dep_rel="root", head_idx=None, extra={},
        ),
        AnalyzedToken(
            text="pomme", lemma="pomme", pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=3, dep_rel="obj", head_idx=2, extra={},
        ),
    ]
    assert make_handler().can_apply(tokens, 2) is False


def test_can_apply_false_irregular_participle_avoir():
    # "Il l'a mise." - avoir + anteposed clitic, but "mise" (mettre) is
    # irregular - must be skipped even though the gate structure matches.
    tokens = [
        AnalyzedToken(
            text="Il", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="l'", lemma="le", pos="PRON",
            features={"Gender": "Fem", "Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=1, dep_rel="obj", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="a", lemma="avoir", pos="AUX",
            features={"Mood": "Ind", "Number": "Sing", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=2, dep_rel="aux:tense", head_idx=3, extra={},
        ),
        AnalyzedToken(
            text="mise", lemma="mettre", pos="VERB",
            features={"Gender": "Fem", "Number": "Sing", "Tense": "Past", "VerbForm": "Part"},
            idx=3, dep_rel="root", head_idx=None, extra={},
        ),
    ]
    assert make_handler().can_apply(tokens, 3) is False


def test_can_apply_false_irregular_masc_plur_etre():
    # "Ils sont mis." - être + masc-plur subject, but "mis" is the
    # blocklisted invariant irregular form.
    tokens = [
        AnalyzedToken(
            text="Ils", lemma="lui", pos="PRON",
            features={"Gender": "Masc", "Number": "Plur", "Person": "3", "PronType": "Prs"},
            idx=0, dep_rel="nsubj", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="sont", lemma="être", pos="AUX",
            features={"Mood": "Ind", "Number": "Plur", "Person": "3", "Tense": "Pres", "VerbForm": "Fin"},
            idx=1, dep_rel="aux:tense", head_idx=2, extra={},
        ),
        AnalyzedToken(
            text="mis", lemma="mettre", pos="VERB",
            features={"Gender": "Masc", "Number": "Plur", "Tense": "Past", "VerbForm": "Part"},
            idx=2, dep_rel="root", head_idx=None, extra={},
        ),
    ]
    assert make_handler().can_apply(tokens, 2) is False


def test_apply_returns_none_when_gate_fails():
    tokens = _tokens_avoir_clitic_la()
    # Remove the clitic's obj status to break the gate (make it a bare
    # PRON with no dep_rel match) and confirm apply() itself re-validates
    # rather than blindly trusting a stale can_apply result.
    tokens[1] = AnalyzedToken(
        text="l'", lemma="le", pos="PRON",
        features={"Gender": "Fem", "Number": "Sing", "Person": "3", "PronType": "Prs"},
        idx=1, dep_rel="iobj", head_idx=3, extra={},
    )
    sentence = [t.text for t in tokens]
    modified: set[int] = set()
    result = make_handler().apply(tokens, sentence, 3, modified)
    assert result is None
    assert sentence == [t.text for t in tokens]
    assert modified == set()


def test_handler_metadata():
    handler = make_handler()
    assert handler.name == "pp_agreement"
    assert handler.subtypes == ["etre_strip", "avoir_cod_ante_strip"]
    assert handler.category == "MORPH"
    assert handler.changes_length is False
