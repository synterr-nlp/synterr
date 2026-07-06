"""Smoke tests for the French language scaffold (PoC).

Not testing any handlers (there are none yet) - just that the scaffold
satisfies the LanguageModule protocol, is discoverable via the entry point,
and that the fixture pack in conftest.py holds sane parsed-token shapes.
"""

from __future__ import annotations

from synterr.core.protocol import AnalyzedToken, LanguageModule
from synterr.languages.french import FrenchLanguage


def test_french_language_satisfies_protocol():
    fr = FrenchLanguage()
    assert isinstance(fr, LanguageModule)


def test_french_language_identity():
    fr = FrenchLanguage()
    assert fr.code == "fr"
    assert fr.name == "French"


def test_get_error_handlers_wired():
    fr = FrenchLanguage()
    handlers = fr.get_error_handlers()
    assert len(handlers) == 5
    names = {h.name for h in handlers}
    assert names == {
        "grammatical_homophone",
        "verb_ending_homophony",
        "article_contraction",
        "elision_apostrophe",
        "pp_agreement",
    }


def test_get_error_distribution_has_weights():
    fr = FrenchLanguage()
    dist = fr.get_error_distribution()
    assert set(dist) == {h.name for h in fr.get_error_handlers()}
    assert abs(sum(dist.values()) - 1.0) < 1e-6


def test_get_analyzer_returns_french_analyzer():
    from synterr.languages.french.analyzer import FrenchAnalyzer

    fr = FrenchLanguage()
    analyzer = fr.get_analyzer()
    assert isinstance(analyzer, FrenchAnalyzer)


def test_registered_via_entry_point():
    from synterr.core.registry import get_language, list_languages

    assert "fr" in list_languages()
    fr = get_language("fr")
    assert fr.code == "fr"


def test_backend_registry_has_stanza_only():
    from synterr.languages.french.backends import BACKENDS, DEFAULT_BACKEND

    assert DEFAULT_BACKEND == "stanza"
    assert set(BACKENDS.keys()) == {"stanza"}


def test_sample_french_sentences_count(sample_french_sentences):
    assert len(sample_french_sentences) == 10
    assert all(isinstance(s, str) and s for s in sample_french_sentences)


def test_tokens_avoir_3sg_extra_is_empty(tokens_avoir_3sg):
    assert all(t.extra == {} for t in tokens_avoir_3sg)
    aux = tokens_avoir_3sg[1]
    assert aux.lemma == "avoir"
    assert aux.pos == "AUX"
    assert aux.get_feature("Person") == "3"


def test_tokens_etre_copula(tokens_etre_copula):
    cop = tokens_etre_copula[1]
    assert cop.lemma == "être"
    assert cop.dep_rel == "cop"


def test_tokens_modal_infinitive(tokens_modal_infinitive):
    inf = tokens_modal_infinitive[2]
    assert inf.has_feature("VerbForm", "Inf")
    assert inf.dep_rel == "xcomp"


def test_tokens_participle_que_relative_agreement(tokens_participle_que_relative):
    rel_pronoun = tokens_participle_que_relative[2]
    participle = tokens_participle_que_relative[5]
    antecedent = tokens_participle_que_relative[1]
    assert rel_pronoun.text == "qu'"
    assert rel_pronoun.has_feature("PronType", "Rel")
    assert participle.dep_rel == "acl:relcl"
    # participle agrees with the antecedent "pommes" (Fem/Plur), not the
    # (Masc/Sing) subject "il" - the flagship pp_agreement gate.
    assert participle.get_feature("Gender") == antecedent.get_feature("Gender")
    assert participle.get_feature("Number") == antecedent.get_feature("Number")


def test_tokens_elided_l(tokens_elided_l):
    det = tokens_elided_l[0]
    assert det.text == "L'"
    assert det.lemma == "le"


def test_tokens_elided_qu(tokens_elided_qu):
    tok = tokens_elided_qu[0]
    assert tok.text == "Qu'"
    assert tok.lemma == "que"


def test_tokens_au_contraction(tokens_au_contraction):
    adp, det = tokens_au_contraction[2], tokens_au_contraction[3]
    assert adp.pos == "ADP" and adp.lemma == "à"
    assert det.pos == "DET" and det.lemma == "le"
    assert adp.head_idx == det.head_idx  # both attach to the noun


def test_tokens_du_contraction(tokens_du_contraction):
    adp, det = tokens_du_contraction[2], tokens_du_contraction[3]
    assert adp.pos == "ADP" and adp.lemma == "de"
    assert det.pos == "DET" and det.lemma == "le"


def test_tokens_t_il_inversion(tokens_t_il_inversion):
    verb = tokens_t_il_inversion[0]
    euphonic_t = tokens_t_il_inversion[1]
    il = tokens_t_il_inversion[2]
    assert verb.pos == "VERB"
    assert euphonic_t.text == "-t"
    assert il.text == "-il"
    assert euphonic_t.dep_rel == "nsubj"


def test_tokens_fronted_advcl(tokens_fronted_advcl):
    advcl = tokens_fronted_advcl[2]
    comma = tokens_fronted_advcl[3]
    root = tokens_fronted_advcl[5]
    assert advcl.dep_rel == "advcl"
    assert advcl.head_idx == root.idx
    # the advcl clause (idx 0-2) precedes its head (idx 5) - "fronted"
    assert advcl.idx < root.idx
    assert comma.dep_rel == "punct"
