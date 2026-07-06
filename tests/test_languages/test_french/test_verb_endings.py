"""Tests for the French verb_ending_homophony handler (PoC flagship).

Uses hand-built AnalyzedToken fixtures (no live stanza) - reuses the shared
French fixture pack in conftest.py (tokens_modal_infinitive, tokens_avoir_3sg)
plus small locally-built token lists for cases the shared pack doesn't cover
(ADP-governed infinitives, fut/cond forms, negative guards).
"""

from __future__ import annotations

import random

from synterr.core.protocol import AnalyzedToken
from synterr.languages.french.errors.verb_endings import VerbEndingHomophonyHandler


def _handler() -> VerbEndingHomophonyHandler:
    return VerbEndingHomophonyHandler()


# --- Handler identity ---------------------------------------------------


def test_handler_protocol_shape():
    handler = _handler()
    assert handler.name == "verb_ending_homophony"
    assert handler.subtypes == [
        "inf_to_participle",
        "participle_to_inf",
        "fut_cond_1sg",
    ]
    assert handler.category == "SPELL"
    assert handler.changes_length is False


# --- inf_to_participle: positive ----------------------------------------


def test_inf_to_participle_positive_modal_governed(tokens_modal_infinitive):
    """ "Il veut manger une pomme." - manger is xcomp under vouloir (modal)."""
    handler = _handler()
    idx = 2  # "manger"
    assert tokens_modal_infinitive[idx].text == "manger"

    assert handler.can_apply(tokens_modal_infinitive, idx) is True

    sentence = ["Il", "veut", "manger", "une", "pomme", "."]
    modified: set[int] = set()
    result = handler.apply(
        tokens_modal_infinitive, sentence, idx, modified, rng=random.Random(0)
    )

    assert result is not None
    assert result.error_type == "inf_to_participle"
    assert result.category == "SPELL"
    assert result.original == "manger"
    assert result.corrupted == "mangé"
    assert sentence[idx] == "mangé"
    assert idx in modified
    assert result.fix_tag == "$REPLACE_manger"


def test_inf_to_participle_positive_adp_governed():
    """ "Il part sans manger." - manger governed by ADP "sans" (mark)."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="part",
            lemma="partir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="sans",
            lemma="sans",
            pos="ADP",
            features={},
            idx=2,
            dep_rel="mark",
            head_idx=3,
            extra={},
        ),
        AnalyzedToken(
            text="manger",
            lemma="manger",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=3,
            dep_rel="advcl",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=4,
            dep_rel="punct",
            head_idx=1,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 3) is True

    sentence = ["Il", "part", "sans", "manger", "."]
    result = handler.apply(tokens, sentence, 3, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "mangé"
    assert sentence[3] == "mangé"


def test_inf_to_participle_preserves_capitalization():
    """Sentence-initial "Manger" -> "Mangé" (governed by ADP "Pour")."""
    tokens = [
        AnalyzedToken(
            text="Pour",
            lemma="pour",
            pos="ADP",
            features={},
            idx=0,
            dep_rel="mark",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="Manger",
            lemma="manger",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=1,
            dep_rel="advcl",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="vite",
            lemma="vite",
            pos="ADV",
            features={},
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is True
    sentence = ["Pour", "Manger", "vite"]
    result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "Mangé"
    assert sentence[1] == "Mangé"


# --- inf_to_participle: guards -------------------------------------------


def test_inf_to_participle_no_governor_does_not_apply():
    """Bare infinitive with no modal/ADP evidence (e.g. nominal use,
    "Manger est un plaisir.") must not fire - ambiguous licensing."""
    tokens = [
        AnalyzedToken(
            text="Manger",
            lemma="manger",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=0,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="est",
            lemma="être",
            pos="AUX",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="cop",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="agréable",
            lemma="agréable",
            pos="ADJ",
            features={"Number": "Sing"},
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 0) is False


def test_inf_to_participle_non_whitelisted_lemma_does_not_apply():
    """Lemma absent from verb_ending_slots.json (not in the top-2000
    1st-group whitelist) must not fire even with a valid modal governor."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="veut",
            lemma="vouloir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="grenouiller",
            lemma="grenouiller",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=2,
            dep_rel="xcomp",
            head_idx=1,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is False


def test_inf_to_participle_non_homophonous_lemma_does_not_apply():
    """ "aider" IS a whitelisted 1st-group verb, but its infinitive and
    participle land in different phonemic clusters ("ede" vs "Ede") - not a
    genuine homophone pair, so inf_to_participle must not fire."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="veut",
            lemma="vouloir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="aider",
            lemma="aider",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=2,
            dep_rel="xcomp",
            head_idx=1,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is False


def test_inf_to_participle_surface_text_mismatch_does_not_apply():
    """UD features claim VerbForm=Inf but the surface text doesn't end in
    "-er" (parser/fixture noise) - the surface guard must block this."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="veut",
            lemma="vouloir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="mang",
            lemma="manger",
            pos="VERB",  # truncated surface form
            features={"VerbForm": "Inf"},
            idx=2,
            dep_rel="xcomp",
            head_idx=1,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is False


# --- participle_to_inf: positive -----------------------------------------


def test_participle_to_inf_positive_avoir(tokens_avoir_3sg):
    """ "Elle a mangé une pomme." - mangé after avoir."""
    handler = _handler()
    idx = 2  # "mangé"
    assert tokens_avoir_3sg[idx].text == "mangé"

    assert handler.can_apply(tokens_avoir_3sg, idx) is True

    sentence = ["Elle", "a", "mangé", "une", "pomme", "."]
    modified: set[int] = set()
    result = handler.apply(
        tokens_avoir_3sg, sentence, idx, modified, rng=random.Random(0)
    )

    assert result is not None
    assert result.error_type == "participle_to_inf"
    assert result.original == "mangé"
    assert result.corrupted == "manger"
    assert sentence[idx] == "manger"
    assert idx in modified


def test_participle_to_inf_feminine_plural_agreement_form():
    """ "mangées" (fem plur agreement, e.g. after être/COD-fronted avoir) ->
    "manger", stripping -ées not just -é."""
    tokens = [
        AnalyzedToken(
            text="Elles",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Fem",
                "Number": "Plur",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="ont",
            lemma="avoir",
            pos="AUX",
            features={
                "Mood": "Ind",
                "Number": "Plur",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="aux:tense",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="mangées",
            lemma="manger",
            pos="VERB",
            features={
                "Gender": "Fem",
                "Number": "Plur",
                "Tense": "Past",
                "VerbForm": "Part",
            },
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is True
    sentence = ["Elles", "ont", "mangées"]
    result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "manger"


def test_participle_to_inf_preserves_capitalization():
    tokens = [
        AnalyzedToken(
            text="Elle",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Fem",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="A",
            lemma="avoir",
            pos="AUX",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="aux:tense",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="Mangé",
            lemma="manger",
            pos="VERB",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Tense": "Past",
                "VerbForm": "Part",
            },
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    sentence = ["Elle", "A", "Mangé"]
    result = handler.apply(tokens, sentence, 2, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "Manger"


# --- participle_to_inf: guards --------------------------------------------


def test_participle_to_inf_no_aux_does_not_apply(tokens_etre_copula):
    """Participle with no avoir/être aux attached (e.g. a plain adjective
    reading, or a participle used attributively without any compound-tense
    aux in the sentence) must not fire."""
    tokens = [
        AnalyzedToken(
            text="La",
            lemma="le",
            pos="DET",
            features={
                "Definite": "Def",
                "Gender": "Fem",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=0,
            dep_rel="det",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="pomme",
            lemma="pomme",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=1,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="mangée",
            lemma="manger",
            pos="VERB",
            features={
                "Gender": "Fem",
                "Number": "Sing",
                "Tense": "Past",
                "VerbForm": "Part",
            },
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
            # No AUX token anywhere in this sentence points at idx 2.
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is False


def test_participle_to_inf_non_er_lemma_does_not_apply():
    """ "fait" (faire, 3rd group) after avoir - not a 1st-group verb, must not
    fire regardless of aux evidence."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="a",
            lemma="avoir",
            pos="AUX",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="aux:tense",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="fait",
            lemma="faire",
            pos="VERB",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Tense": "Past",
                "VerbForm": "Part",
            },
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 2) is False


# --- fut_cond_1sg: positive -----------------------------------------------


def test_fut_cond_1sg_fut_to_cond_positive():
    """ "Je mangerai." - future 1sg -> conditional (-ai -> -ais)."""
    tokens = [
        AnalyzedToken(
            text="Je",
            lemma="moi",
            pos="PRON",
            features={"Number": "Sing", "Person": "1", "PronType": "Prs"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="mangerai",
            lemma="manger",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Fut",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is True
    sentence = ["Je", "mangerai"]
    result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
    assert result is not None
    assert result.error_type == "fut_cond_1sg"
    assert result.original == "mangerai"
    assert result.corrupted == "mangerais"
    assert sentence[1] == "mangerais"


def test_fut_cond_1sg_cond_to_fut_positive():
    """ "Je mangerais." - conditional 1sg -> future (-ais -> -ai)."""
    tokens = [
        AnalyzedToken(
            text="Je",
            lemma="moi",
            pos="PRON",
            features={"Number": "Sing", "Person": "1", "PronType": "Prs"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="mangerais",
            lemma="manger",
            pos="VERB",
            features={
                "Mood": "Cnd",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is True
    sentence = ["Je", "mangerais"]
    result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "mangerai"
    assert sentence[1] == "mangerai"


def test_fut_cond_1sg_uses_aider_whitelist_entry():
    """ "aider" is not inf/participle-homophonous, but its fut_1s/cond
    cluster IS shared ("aiderai"/"aiderais") - confirms the whitelist gate
    is evaluated per-subtype, not just per-lemma."""
    tokens = [
        AnalyzedToken(
            text="Je",
            lemma="moi",
            pos="PRON",
            features={"Number": "Sing", "Person": "1", "PronType": "Prs"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="aiderai",
            lemma="aider",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Fut",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is True
    sentence = ["Je", "aiderai"]
    result = handler.apply(tokens, sentence, 1, set(), rng=random.Random(0))
    assert result is not None
    assert result.corrupted == "aiderais"


# --- fut_cond_1sg: guards --------------------------------------------------


def test_fut_cond_1sg_third_person_does_not_apply():
    """Spec restricts this subtype to Person=1 Number=Sing; 3rd person future
    ("il mangera") must not fire."""
    tokens = [
        AnalyzedToken(
            text="Il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="mangera",
            lemma="manger",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Fut",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is False


def test_fut_cond_1sg_plural_does_not_apply():
    """1st-person PLURAL future ("nous mangerons") must not fire - the
    homophony pair is specifically the 1sg -ai/-ais ending."""
    tokens = [
        AnalyzedToken(
            text="Nous",
            lemma="moi",
            pos="PRON",
            features={"Number": "Plur", "Person": "1", "PronType": "Prs"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="mangerons",
            lemma="manger",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Plur",
                "Person": "1",
                "Tense": "Fut",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is False


def test_fut_cond_1sg_present_tense_does_not_apply():
    """Plain present-tense finite verb (neither fut nor cond, no inf/part
    form) must not fire at all - no subtype matches."""
    tokens = [
        AnalyzedToken(
            text="Je",
            lemma="moi",
            pos="PRON",
            features={"Number": "Sing", "Person": "1", "PronType": "Prs"},
            idx=0,
            dep_rel="nsubj",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="mange",
            lemma="manger",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=1,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    assert handler.can_apply(tokens, 1) is False


# --- Cross-cutting guards ---------------------------------------------------


def test_non_verb_token_does_not_apply(tokens_etre_copula):
    """ADJ token must never fire (handler only touches VERB-pos tokens)."""
    handler = _handler()
    adj_idx = 2  # "heureuse"
    assert tokens_etre_copula[adj_idx].pos == "ADJ"
    assert handler.can_apply(tokens_etre_copula, adj_idx) is False


def test_apply_returns_none_when_can_apply_would_be_false():
    """apply() re-derives its own gate and must return None (not raise, not
    silently corrupt) when called on a non-applicable index."""
    tokens = [
        AnalyzedToken(
            text="pomme",
            lemma="pomme",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=0,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
    ]
    handler = _handler()
    sentence = ["pomme"]
    assert handler.can_apply(tokens, 0) is False
    result = handler.apply(tokens, sentence, 0, set(), rng=random.Random(0))
    assert result is None
    assert sentence[0] == "pomme"
