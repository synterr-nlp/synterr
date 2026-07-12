"""Modifier-noun agreement error handlers (Rozental §191-197 grab-bag).

Three narrow, high-precision cases carved out of the §191-197 range (the rest
is deferred — see module docstrings below for the exact scope of each):

- ``AgrMnAppositionErrorHandler`` (subtype ``ag_mn_apposition``, §195-196):
  declinable toponym appositions — "в городе Москве" -> "в городе Москва".
  Russian city/village/river names normally agree in case with the governing
  common noun; corrupting the apposition back to its citation (nominative)
  form recreates the classic non-agreement error, restricted to a small
  agreeing-class lexicon (город/село/деревня/хутор/река) so the un-corrupted
  sentence is unambiguously "correct per the rule".
- ``AgrMnCompoundTermErrorHandler`` (subtype ``ag_mn_compound_term``, §197):
  hyphenated noun-noun compounds ("в вагоне-ресторане" -> "в вагоне-ресторан")
  where stanza's tokenizer splits the compound into NOUN + PUNCT("-") + NOUN
  and the second noun is dep-attached (appos/parataxis) to the first; both
  halves should decline together, and the corruption freezes the second half
  in the nominative.
- ``AgrMnNumeralAdjErrorHandler`` (subtype ``ag_mn_special``, §193): the
  два/три/четыре + adjective + noun construction, where the adjective
  between the numeral and the noun takes the genitive plural for masc/neut
  nouns ("два новых дома") but the nominative plural for feminine nouns
  ("две новые книги"). The corruption swaps the adjective's form to the
  *other* norm, producing the classic learner cross-over error.

All three require dependency-parse info (``use_depparse=True`` on the
analyzer); with no dep arc there is no classification evidence at all, so
``can_apply`` is unconditionally False. Precision-first throughout: every
handler skips on syncretism, unknown/indeclinable words, composite names, and
any morphological ambiguity rather than emit a doubtful example (see each
class's docstring for its specific accepted-risk notes).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.inflector import inflect_word
from synterr.languages.russian.resources import get_morpheme_analyzer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# Shared helpers (duplicated from morphological.py by design — one-agent-one-
# -file-lane; see MEDIUM_WAVE_SPEC.md §0).
# =============================================================================


def _get_pymorphy_parse(token: AnalyzedToken):
    """Get pymorphy parse object from token."""
    return token.extra.get("pymorphy_parse")


def _get_token_safe(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Safely get token by index, returning None if out of bounds."""
    if 0 <= idx < len(tokens):
        return tokens[idx]
    return None


def _has_any_dependent(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """True when some other token attaches to idx.

    Used as a composite-name guard: a single-word toponym/compound-element
    normally has no dependents of its own in this position. A hit here means
    idx is itself the head of further structure (e.g. "Нижний" amod-attached
    to "Новгород" in "город Нижний Новгород", or a "flat" chain continuing a
    multi-word name) — Rozental explicitly calls out composite/multi-word
    names as *not* agreeing, so such tokens are skipped rather than risk
    corrupting only part of a name.
    """
    return any(t.head_idx == idx for t in tokens)


# UD cases that are not nominative — "oblique" in the sense used throughout
# this file (a broader set than morphological.py's numeral-declension helper,
# which excludes Acc for reasons specific to that handler).
_OBLIQUE_CASES = {"Gen", "Dat", "Acc", "Ins", "Loc"}

# Bundled lexicon directory, alongside the other language resources
# (paronyms, collocations, ...). Kept local to this file (not imported from
# morphological.py) by the one-agent-one-file-lane convention noted above.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "russian"


def _normalize_lemma(lemma: str) -> str:
    """Lowercase and fold ё->е for lexicon lookups.

    pymorphy's ``normal_form`` always spells ё, but stanza's own lemmatizer
    usually spells е (see inflector.py's е/ё gotcha) — folding both sides to
    е keeps the lexicon lookup below from silently missing entries over a
    spelling difference that carries no lexical information here.
    """
    return lemma.lower().replace("ё", "е")


@lru_cache(maxsize=1)
def _hyphen_compound_lexicon() -> frozenset[tuple[str, str]]:
    """Curated allowlist of §197 both-halves-decline hyphenated compounds.

    Fallback for ``AgrMnCompoundTermErrorHandler``'s fused-dictionary gate:
    pymorphy3's strict dictionary lacks most real hyphenated compound nouns
    even when both halves independently decline (инженер-строитель,
    диван-кровать, словарь-справочник, ... all fail
    ``word_is_known(fused)`` — audit finding, 2026-07-12). Data file is
    ``synterr/data/russian/hyphen_compounds.json``; entries are
    (head_lemma, second_half_lemma) pairs, normalized via
    ``_normalize_lemma``. Missing file yields an empty lexicon rather than
    raising, matching this module's skip-over-crash precision stance.
    """
    path = _DATA_DIR / "hyphen_compounds.json"
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return frozenset(
        (_normalize_lemma(head), _normalize_lemma(second))
        for head, second in data.get("pairs", [])
    )


# =============================================================================
# ag_mn_apposition (§195-196): declinable toponym appositions
# =============================================================================

# Head-noun classes that Rozental §197 documents as *requiring* case
# agreement with their toponym apposition. Deliberately narrow and only the
# classes explicitly attested as agreeing:
#   - город/село/деревня/хутор: "в городе Москве", "в селе Горюхине"
#   - река: "на реке Днепре"
# Explicitly EXCLUDED (§197 lists these as normally NOT agreeing, so treating
# them as agreeing would create a false "error" out of correct text):
#   озеро, залив, пролив, канал, бухта, остров, полуостров, гора, хребет,
#   пустыня, станция, порт, республика (gender-conditioned, too fiddly),
#   штат, провинция, департамент, княжество, улица (mixed by gender), etc.
_GEO_AGREEING_HEAD_LEMMAS = frozenset({"город", "село", "деревня", "хутор", "река"})

# dep_rels observed (real stanza backend) attaching a toponym apposition to
# its head noun. "appos" is the textbook UD relation; "nmod" turns up when
# the parser reads a genitive-genitive pair ("у города Смоленска") as a
# nominal-modifier instead — accepted here since the real-vs-nmod-government
# distinction is already covered by the other guards (agreeing head-lemma
# allowlist, round-trip declined-form check). "flat"/"flat:name" cover
# multi-word chains (filtered separately, see ``_has_any_dependent``).
_APPOS_DEPRELS = frozenset({"appos", "nmod", "flat", "flat:name"})


class AgrMnAppositionErrorHandler:
    """Corrupt a declinable toponym apposition to its citation (Nom) form.

    "в городе Москве" -> "в городе Москва": the governing common noun
    (город/село/деревня/хутор/река) is oblique and the toponym currently
    agrees with it in case (evidence that agreement is actually required
    here, not just tolerated) — corrupting the toponym to nominative breaks
    that agreement.

    Guards (precision-first):
    - head lemma restricted to the small agreeing-class allowlist above;
    - toponym lemma must not end in "-о" (Пушкино/Кирово-type names are
      conventionally left undeclined even though pymorphy happily inflects
      them — §197's explicit exception);
    - toponym must have no dependents of its own (composite/multi-word name
      guard, e.g. "Нижний Новгород");
    - pymorphy parse must exist, be dictionary-confirmed (``parse.is_known``)
      rather than a suffix-based guess, tag as NOUN, and not be marked
      ``Fixd`` (catches indeclinable foreign/rare names: Сочи, Баку,
      Токио, ...);
    - the toponym's own surface form must currently differ from its
      nominative form (a pymorphy inflection round-trip) — i.e. it really is
      declined right now, evidence that agreement is actually in force here.

    The round-trip check is used instead of comparing the UD ``Case``
    features of the toponym and its head: against the real stanza backend,
    rare/OOV proper nouns frequently get the *wrong* UD ``Case`` (e.g. a
    genuinely declined "Зеленогорске" tagged ``Case=Nom`` despite its own
    pymorphy parse correctly reading ``loct``), so requiring the two Case
    features to match silently drops good examples. ``parse.is_known`` is
    the compensating precision guard: without it, an OOV toponym for which
    pymorphy has to *guess* a paradigm by suffix (e.g. "Мзымта" analyzed as
    genitive of a fictitious "Мзымт") could round-trip into a bogus
    correction; requiring a dictionary-confirmed parse (which covers the
    large majority of real city/river names — even fairly obscure ones are
    typically in OpenCorpora's Geox/Name lexicon) keeps that class of error
    out.

    Accepted risk: §197 also excludes "малоизвестные" (obscure/rare) city and
    especially river names from agreement on frequency grounds the handler
    cannot judge from pymorphy alone (a genuinely rare-but-dictionary-known
    river name will still fire). Expect a validity ceiling below 100% on
    this subtype for such toponyms — same caveat as the AGR-SV
    collective/counting families.
    """

    name = "agr_mn_apposition"
    subtypes = ["ag_mn_apposition"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "PROPN":
            return False
        if (token.dep_rel or "") not in _APPOS_DEPRELS:
            return False
        if token.head_idx is None:
            return False
        head = _get_token_safe(tokens, token.head_idx)
        if head is None or head.pos != "NOUN":
            return False
        if (head.lemma or "").lower() not in _GEO_AGREEING_HEAD_LEMMAS:
            return False
        if head.get_feature("Case") not in _OBLIQUE_CASES:
            return False
        lemma = (token.lemma or token.text).lower()
        if lemma.endswith("о"):
            return False
        # Compound toponyms (Усть-Джегута, Южно-Сахалинск) mostly resist
        # declension per §196, and per-segment capitalization does not
        # survive inflection round-trips — skip them (audit, 2026-07-07).
        if "-" in token.text:
            return False
        if _has_any_dependent(tokens, idx):
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return False
        tag = str(parse.tag)
        if "Fixd" in tag or "NOUN" not in tag:
            return False
        if not getattr(parse, "is_known", True):
            return False
        word = token.text
        nomn_form = inflect_word(parse, {"nomn"}, word)
        if not nomn_form or nomn_form.lower() == word.lower():
            return False
        return True

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return None

        new_word = inflect_word(parse, {"nomn"}, word)
        if not new_word or new_word.lower() == word.lower():
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_case = token.get_feature("Case", "Loc")
        return ErrorResult(
            error_type="ag_mn_apposition",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_CASE_{original_case}",
        )


# =============================================================================
# ag_mn_compound_term (§197): hyphenated compound-noun agreement
# =============================================================================

# dep_rels observed (real stanza backend) attaching the second half of a
# hyphenated compound noun to the first when the tokenizer splits the
# compound into three tokens (NOUN, "-", NOUN): "appos" (вагоне-ресторане)
# and "parataxis" (диване-кровати) both occur for what is linguistically the
# same construction, so both are accepted.
_COMPOUND_SECOND_HALF_DEPRELS = frozenset({"appos", "parataxis", "flat", "flat:name"})


class AgrMnCompoundTermErrorHandler:
    """Freeze the second half of a hyphenated compound noun to Nom.

    "в вагоне-ресторане" -> "в вагоне-ресторан": both halves of a
    сложносоставное наименование should decline together; freezing the
    second half creates the common learner error of only inflecting the
    first part.

    Scope note: stanza's tokenizer is inconsistent about whether a given
    hyphenated compound is one token or three (compared "вагон-ресторан",
    which splits into NOUN + PUNCT("-") + NOUN in context, against
    "купе-люкс", which stays fused as a single token whose pymorphy parse is
    ambiguous about where the compound boundary falls). Only the three-token
    shape is handled here — it has an unambiguous dep arc (the second NOUN's
    head is exactly the first NOUN, two positions back across the hyphen
    PUNCT) and both halves are independently checked against the pymorphy
    dictionary. The single-token fused shape is out of scope: pymorphy has
    no reliable way to say which half of a fused hyphenated lexeme carries
    the corrupted ending, so attempting it would trade precision for a
    modest coverage gain.

    Guards: both halves must be dictionary-known words (``word_is_known``,
    strict — rejects indeclinable brand names spelled with a hyphen); both
    halves POS-tagged NOUN (not PROPN, so brand/product names tagged as
    proper nouns are excluded); head must be in an oblique case; the fused
    surface must either be a dictionary-known hyphenated lexeme itself
    (вагон-ресторан, школа-интернат) or the head/second-half lemma pair must
    be in a curated allowlist of common §197 both-halves-decline compounds
    (``synterr/data/russian/hyphen_compounds.json`` — инженер-строитель,
    диван-кровать, кресло-качалка, ...), since pymorphy's strict dictionary
    lacks most real hyphenated compounds even when both halves independently
    decline (audit finding, 2026-07-12); the second half's own surface form
    must currently differ from its nominative form (pymorphy round-trip —
    same rationale as the apposition handler above: the UD ``Case`` feature
    on the second half is occasionally the wrong member of a syncretic case
    set for 3rd-declension feminine nouns, e.g. "кровати" tagged ``Gen``
    when it is actually the identically-spelled ``Loc``, so comparing UD
    Case features directly would under-fire).
    """

    name = "agr_mn_compound_term"
    subtypes = ["ag_mn_compound_term"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        if (token.dep_rel or "") not in _COMPOUND_SECOND_HALF_DEPRELS:
            return False
        if token.head_idx is None or token.head_idx != idx - 2:
            return False
        hyphen = _get_token_safe(tokens, idx - 1)
        if hyphen is None or hyphen.pos != "PUNCT" or hyphen.text != "-":
            return False
        head = _get_token_safe(tokens, token.head_idx)
        if head is None or head.pos != "NOUN":
            return False
        if head.get_feature("Case") not in _OBLIQUE_CASES:
            return False

        analyzer = get_morpheme_analyzer()
        if not analyzer.word_is_known(head.text) or not analyzer.word_is_known(
            token.text
        ):
            return False
        # The three-token NOUN "-" NOUN shape also matches an explanatory
        # dash typed as ASCII hyphen («работе - поиску пострадавших»), which
        # is not a §197 compound. Require either the fused surface to be a
        # dictionary-known hyphenated lexeme (вагоне-ресторане ✓ — audit,
        # 2026-07-07), or the lemma pair to be in the curated §197
        # both-halves-decline allowlist (pymorphy's strict dictionary lacks
        # most real compounds — инженер-строитель, диван-кровать,
        # словарь-справочник, ... — audit finding, 2026-07-12); compounds
        # missing from both are skipped — precision over recall.
        fused_known = analyzer.word_is_known(f"{head.text}-{token.text}")
        if not fused_known:
            lemma_pair = (
                _normalize_lemma(head.lemma or head.text),
                _normalize_lemma(token.lemma or token.text),
            )
            if lemma_pair not in _hyphen_compound_lexicon():
                return False

        parse = _get_pymorphy_parse(token)
        if parse is None:
            return False
        tag = str(parse.tag)
        if "Fixd" in tag or "NOUN" not in tag:
            return False
        word = token.text
        nomn_form = inflect_word(parse, {"nomn"}, word)
        if not nomn_form or nomn_form.lower() == word.lower():
            return False
        return True

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return None

        target = {"nomn"}
        number_ud = token.get_feature("Number")
        if number_ud == "Plur":
            target.add("plur")
        else:
            target.add("sing")

        new_word = inflect_word(parse, target, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_case = token.get_feature("Case", "Loc")
        return ErrorResult(
            error_type="ag_mn_compound_term",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_CASE_{original_case}",
        )


# =============================================================================
# ag_mn_special (§193): два/три/четыре + adjective + noun
# =============================================================================

_NUM_ADJ_LEMMAS = frozenset({"два", "две", "три", "четыре"})
_NUM_ADJ_DIGITS = frozenset({"2", "3", "4"})


def _numeral_adj_noun_head(
    tokens: Sequence[AnalyzedToken], idx: int
) -> AnalyzedToken | None:
    """If idx is an amod adjective in a NUM(2-4)+ADJ+NOUN chain, return the noun.

    Both the adjective and the numeral must attach (via amod / nummod*) to
    the *same* noun. The numeral's own dep_rel varies unpredictably between
    "nummod" and "nummod:gov" for what is the identical construction (both
    forms observed against the real stanza backend for masc/neut and fem
    examples alike), so both are accepted via a startswith check; the
    numeral value is what actually gates the construction (only 2/3/4,
    including bare-digit surface forms, trigger the genitive-singular-noun
    construction this handler targets).
    """
    token = tokens[idx]
    if token.pos != "ADJ" or token.dep_rel != "amod" or token.head_idx is None:
        return None
    noun = _get_token_safe(tokens, token.head_idx)
    if noun is None or noun.pos != "NOUN":
        return None

    for other in tokens:
        if other.head_idx != token.head_idx or other.pos != "NUM":
            continue
        if not (other.dep_rel or "").startswith("nummod"):
            continue
        lemma = (other.lemma or other.text).lower()
        if lemma in _NUM_ADJ_LEMMAS or other.text in _NUM_ADJ_DIGITS:
            return noun
    return None


class AgrMnNumeralAdjErrorHandler:
    """Swap the two-way adjective agreement in два/три/четыре + ADJ + NOUN.

    Per §193, the adjective sandwiched between a 2-4 numeral and its governed
    (genitive-singular) noun takes:

    - genitive plural when the noun is masc/neut: "два новых дома";
    - nominative plural when the noun is feminine: "две новые книги".

    The corruption swaps the adjective to the *other* form against the same
    noun ("два новых дома" -> "два новые дома"; "две новые книги" -> "две
    новых книги"), producing the classic cross-over error.

    Detection deliberately keys off the adjective's *surface form* via a
    pymorphy inflection round-trip (does the current word equal its own
    genitive-plural or nominative-plural inflection?) rather than the
    dep-parse UD ``Case`` feature or the pymorphy parse's own case grammeme.
    Both are unreliable here against the real stanza backend: the UD feature
    reflects the numeral phrase's *syntactic* case (e.g. "Acc" for a direct
    object) rather than the adjective's written ending, and the pymorphy
    parse's case grammeme is itself frequently syncretic ("-ых"/"-их" is
    simultaneously genitive-plural, locative-plural, and animate-accusative-
    plural for most adjectives, so the specific grammeme the backend
    happened to attach is close to arbitrary). Comparing surface forms
    sidesteps all of that: a numeral phrase in a genuinely oblique case
    (e.g. Instrumental "двумя новыми домами") produces an adjective form
    that equals *neither* target inflection and is correctly excluded
    without any separate case check on the numeral itself.

    Guards: adjective must be plural, non-syncretic with its target, and not
    a pronominal (Apro), participle (PRTF/PRTS), or possessive (Poss on -ин/
    -ов, which per §193 stays genitive-plural regardless of the noun's
    gender — including it in the fem branch would flip a form that is
    already correct).

    Accepted risk / deferred: the feminine-noun stress-shift exception
    (гора/слеза and similar, where fem nouns take genitive-plural despite
    the general fem rule) is handled with a small denylist of the two nouns
    Rozental names explicitly; it is not exhaustive. Common-gender nouns,
    ordinal-adjective agreement (третий), and postposed/preposed-definition
    word-order variants (§193's other sub-rules) are out of scope, per the
    capsule spec ("ship ONLY the clean §193 case").
    """

    name = "agr_mn_numeral_adj"
    subtypes = ["ag_mn_special"]
    category = "MORPH"
    changes_length = False

    # Rozental names these two nouns explicitly as the stress-shift
    # exception (nominative-plural spelling coincides with genitive-singular,
    # so genitive-plural is preferred for the adjective despite fem gender).
    _FEM_STRESS_SHIFT_DENYLIST = frozenset({"гора", "слеза"})

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        noun = _numeral_adj_noun_head(tokens, idx)
        if noun is None:
            return False
        token = tokens[idx]
        if token.get_feature("Number") != "Plur":
            return False

        gender = noun.get_feature("Gender")
        if gender not in {"Masc", "Neut", "Fem"}:
            return False
        if gender == "Fem" and (noun.lemma or "").lower() in (
            self._FEM_STRESS_SHIFT_DENYLIST
        ):
            return False

        parse = _get_pymorphy_parse(token)
        if parse is None:
            return False
        tag = str(parse.tag)
        if "Apro" in tag or "PRTF" in tag or "PRTS" in tag or "Poss" in tag:
            return False

        word = token.text
        nomn_form = inflect_word(parse, {"nomn", "plur"}, word)
        gent_form = inflect_word(parse, {"gent", "plur"}, word)
        if not nomn_form or not gent_form:
            return False
        is_gent_like = word == gent_form and word != nomn_form
        is_nomn_like = word == nomn_form and word != gent_form
        if gender in {"Masc", "Neut"}:
            return is_gent_like
        return is_nomn_like

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        noun = _numeral_adj_noun_head(tokens, idx)
        if noun is None:
            return None
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return None

        gender = noun.get_feature("Gender")
        target = {"nomn", "plur"} if gender in {"Masc", "Neut"} else {"gent", "plur"}

        new_word = inflect_word(parse, target, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        original_case = token.get_feature("Case", "Gen")
        return ErrorResult(
            error_type="ag_mn_special",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_CASE_{original_case}",
        )
