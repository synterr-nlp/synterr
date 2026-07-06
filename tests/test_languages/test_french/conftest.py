"""Pytest configuration and fixtures for French language tests.

Mirrors the shape of the top-level `tests/conftest.py` (`sample_tokens`):
each fixture below is a hand-built list of `AnalyzedToken` for one French
sentence, standing in for a stanza `fr_sequoia` parse. Values (features,
lemma, dep_rel, head_idx) were cross-checked against a real
`StanzaFrBackend(use_depparse=True)` parse (see
docs/research/FRENCH_POC_WORKFLOW.md / scaffold smoke test) so fixtures track
actual UD output shape, including quirks such as `au`/`du` already being
split into separate ADP + DET tokens by stanza's mwt processor, and the
`-t-il` euphonic inversion tokenizing as two PRON tokens ("-t", "-il").

Per the French PoC scaffold, `extra` is always `{}` - no inflection engine is
attached (see synterr.languages.french.backends.stanza_fr).
"""

from __future__ import annotations

import pytest

from synterr.core.protocol import AnalyzedToken


@pytest.fixture
def sample_french_sentences() -> list[str]:
    """Sample French sentences for testing (analog of sample_russian_sentences)."""
    return [
        "Elle a mangé une pomme.",
        "Marie est heureuse.",
        "Il veut manger une pomme.",
        "Les pommes qu'il a mangées étaient vertes.",
        "L'arbre est grand.",
        "Qu'il vienne bientôt !",
        "Il va au marché.",
        "Elle vient du village.",
        "Aime-t-il le chocolat ?",
        "Quand il pleut, je reste à la maison.",
    ]


@pytest.fixture
def tokens_avoir_3sg() -> list[AnalyzedToken]:
    """ "Elle a mangé une pomme." - avoir, 3sg present, as tense auxiliary."""
    return [
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
            text="mangé",
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
        AnalyzedToken(
            text="une",
            lemma="un",
            pos="DET",
            features={
                "Definite": "Ind",
                "Gender": "Fem",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=3,
            dep_rel="det",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="pomme",
            lemma="pomme",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=4,
            dep_rel="obj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=5,
            dep_rel="punct",
            head_idx=2,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_etre_copula() -> list[AnalyzedToken]:
    """ "Marie est heureuse." - être as copula."""
    return [
        AnalyzedToken(
            text="Marie",
            lemma="Marie",
            pos="PROPN",
            features={"Gender": "Fem", "Number": "Sing"},
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
            text="heureuse",
            lemma="heureux",
            pos="ADJ",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=3,
            dep_rel="punct",
            head_idx=2,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_modal_infinitive() -> list[AnalyzedToken]:
    """ "Il veut manger une pomme." - 1st-group infinitive after modal vouloir."""
    return [
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
            text="manger",
            lemma="manger",
            pos="VERB",
            features={"VerbForm": "Inf"},
            idx=2,
            dep_rel="xcomp",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="une",
            lemma="un",
            pos="DET",
            features={
                "Definite": "Ind",
                "Gender": "Fem",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=3,
            dep_rel="det",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="pomme",
            lemma="pomme",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=4,
            dep_rel="obj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=5,
            dep_rel="punct",
            head_idx=1,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_participle_que_relative() -> list[AnalyzedToken]:
    """ "Les pommes qu'il a mangées étaient vertes."

    Flagship pp_agreement case: avoir + participle with a preceding direct
    object introduced by the relative pronoun "que" (elided to "qu'"); the
    participle "mangées" agrees in gender/number with the antecedent
    "pommes" (fem plur), not with the (masc sing) subject "il".
    """
    return [
        AnalyzedToken(
            text="Les",
            lemma="le",
            pos="DET",
            features={"Definite": "Def", "Number": "Plur", "PronType": "Art"},
            idx=0,
            dep_rel="det",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="pommes",
            lemma="pomme",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Plur"},
            idx=1,
            dep_rel="nsubj",
            head_idx=7,
            extra={},
        ),
        AnalyzedToken(
            text="qu'",
            lemma="que",
            pos="PRON",
            features={"PronType": "Rel"},
            idx=2,
            dep_rel="obj",
            head_idx=5,
            extra={},
        ),
        AnalyzedToken(
            text="il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=3,
            dep_rel="nsubj",
            head_idx=5,
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
            idx=4,
            dep_rel="aux:tense",
            head_idx=5,
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
            idx=5,
            dep_rel="acl:relcl",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="étaient",
            lemma="être",
            pos="AUX",
            features={
                "Mood": "Ind",
                "Number": "Plur",
                "Person": "3",
                "Tense": "Imp",
                "VerbForm": "Fin",
            },
            idx=6,
            dep_rel="cop",
            head_idx=7,
            extra={},
        ),
        AnalyzedToken(
            text="vertes",
            lemma="vert",
            pos="ADJ",
            features={"Gender": "Fem", "Number": "Plur"},
            idx=7,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=8,
            dep_rel="punct",
            head_idx=7,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_elided_l() -> list[AnalyzedToken]:
    """ "L'arbre est grand." - elided definite article "l'" before vowel-initial noun."""
    return [
        AnalyzedToken(
            text="L'",
            lemma="le",
            pos="DET",
            features={"Definite": "Def", "Number": "Sing", "PronType": "Art"},
            idx=0,
            dep_rel="det",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="arbre",
            lemma="arbre",
            pos="NOUN",
            features={"Gender": "Masc", "Number": "Sing"},
            idx=1,
            dep_rel="nsubj",
            head_idx=3,
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
            idx=2,
            dep_rel="cop",
            head_idx=3,
            extra={},
        ),
        AnalyzedToken(
            text="grand",
            lemma="grand",
            pos="ADJ",
            features={"Gender": "Masc", "Number": "Sing"},
            idx=3,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=4,
            dep_rel="punct",
            head_idx=3,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_elided_qu() -> list[AnalyzedToken]:
    """ "Qu'il vienne bientôt !" - elided conjunction/pronoun "qu'" before "il"."""
    return [
        AnalyzedToken(
            text="Qu'",
            lemma="que",
            pos="PRON",
            features={"PronType": "Int"},
            idx=0,
            dep_rel="obj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=1,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="vienne",
            lemma="venir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=2,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="bientôt",
            lemma="bientôt",
            pos="ADV",
            features={},
            idx=3,
            dep_rel="advmod",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="!",
            lemma="!",
            pos="PUNCT",
            features={},
            idx=4,
            dep_rel="punct",
            head_idx=2,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_au_contraction() -> list[AnalyzedToken]:
    """ "Il va au marché." - "au" = à + le contraction (stanza mwt-splits it into
    two tokens; the fused surface form "au" is what article_contraction's
    counterpart corruption would need to re-create from these two tokens).
    """
    return [
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
            text="va",
            lemma="aller",
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
            text="à",
            lemma="à",
            pos="ADP",
            features={},
            idx=2,
            dep_rel="case",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="le",
            lemma="le",
            pos="DET",
            features={
                "Definite": "Def",
                "Gender": "Masc",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=3,
            dep_rel="det",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="marché",
            lemma="marché",
            pos="NOUN",
            features={"Gender": "Masc", "Number": "Sing"},
            idx=4,
            dep_rel="obl:arg",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=5,
            dep_rel="punct",
            head_idx=1,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_du_contraction() -> list[AnalyzedToken]:
    """ "Elle vient du village." - "du" = de + le contraction (mwt-split, nmod-gated)."""
    return [
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
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text="vient",
            lemma="venir",
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
            text="de",
            lemma="de",
            pos="ADP",
            features={},
            idx=2,
            dep_rel="case",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="le",
            lemma="le",
            pos="DET",
            features={
                "Definite": "Def",
                "Gender": "Masc",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=3,
            dep_rel="det",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="village",
            lemma="village",
            pos="NOUN",
            features={"Gender": "Masc", "Number": "Sing"},
            idx=4,
            dep_rel="obl:arg",
            head_idx=1,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=5,
            dep_rel="punct",
            head_idx=1,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_t_il_inversion() -> list[AnalyzedToken]:
    """ "Aime-t-il le chocolat ?" - euphonic -t- + il inversion.

    stanza's sequoia tokenizer splits the hyphenated inversion into two PRON
    tokens ("-t", "-il"); euphonic_t_drop targets the first ("-t").
    """
    return [
        AnalyzedToken(
            text="Aime",
            lemma="aimer",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=0,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="-t",
            lemma="tui",
            pos="PRON",
            features={"Number": "Sing", "Person": "3", "PronType": "Prs"},
            idx=1,
            dep_rel="nsubj",
            head_idx=0,
            extra={},
        ),
        AnalyzedToken(
            text="-il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=2,
            dep_rel="nsubj",
            head_idx=0,
            extra={},
        ),
        AnalyzedToken(
            text="le",
            lemma="le",
            pos="DET",
            features={
                "Definite": "Def",
                "Gender": "Masc",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=3,
            dep_rel="det",
            head_idx=4,
            extra={},
        ),
        AnalyzedToken(
            text="chocolat",
            lemma="chocolat",
            pos="NOUN",
            features={"Gender": "Masc", "Number": "Sing"},
            idx=4,
            dep_rel="obj",
            head_idx=0,
            extra={},
        ),
        AnalyzedToken(
            text="?",
            lemma="?",
            pos="PUNCT",
            features={},
            idx=5,
            dep_rel="punct",
            head_idx=0,
            extra={},
        ),
    ]


@pytest.fixture
def tokens_fronted_advcl() -> list[AnalyzedToken]:
    """ "Quand il pleut, je reste à la maison." - fronted adverbial clause
    (comma_delete_fr's fronted_advcl gate: advcl comma only when the clause
    precedes its head)."""
    return [
        AnalyzedToken(
            text="Quand",
            lemma="quand",
            pos="SCONJ",
            features={},
            idx=0,
            dep_rel="mark",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="il",
            lemma="lui",
            pos="PRON",
            features={
                "Gender": "Masc",
                "Number": "Sing",
                "Person": "3",
                "PronType": "Prs",
            },
            idx=1,
            dep_rel="nsubj",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="pleut",
            lemma="pleuvoir",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "3",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=2,
            dep_rel="advcl",
            head_idx=5,
            extra={},
        ),
        AnalyzedToken(
            text=",",
            lemma=",",
            pos="PUNCT",
            features={},
            idx=3,
            dep_rel="punct",
            head_idx=2,
            extra={},
        ),
        AnalyzedToken(
            text="je",
            lemma="moi",
            pos="PRON",
            features={"Number": "Sing", "Person": "1", "PronType": "Prs"},
            idx=4,
            dep_rel="nsubj",
            head_idx=5,
            extra={},
        ),
        AnalyzedToken(
            text="reste",
            lemma="rester",
            pos="VERB",
            features={
                "Mood": "Ind",
                "Number": "Sing",
                "Person": "1",
                "Tense": "Pres",
                "VerbForm": "Fin",
            },
            idx=5,
            dep_rel="root",
            head_idx=None,
            extra={},
        ),
        AnalyzedToken(
            text="à",
            lemma="à",
            pos="ADP",
            features={},
            idx=6,
            dep_rel="case",
            head_idx=8,
            extra={},
        ),
        AnalyzedToken(
            text="la",
            lemma="le",
            pos="DET",
            features={
                "Definite": "Def",
                "Gender": "Fem",
                "Number": "Sing",
                "PronType": "Art",
            },
            idx=7,
            dep_rel="det",
            head_idx=8,
            extra={},
        ),
        AnalyzedToken(
            text="maison",
            lemma="maison",
            pos="NOUN",
            features={"Gender": "Fem", "Number": "Sing"},
            idx=8,
            dep_rel="obl:arg",
            head_idx=5,
            extra={},
        ),
        AnalyzedToken(
            text=".",
            lemma=".",
            pos="PUNCT",
            features={},
            idx=9,
            dep_rel="punct",
            head_idx=5,
            extra={},
        ),
    ]
