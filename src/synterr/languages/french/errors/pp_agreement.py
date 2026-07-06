"""French past-participle agreement error handler (PoC, phase 1 flagship #2).

Two mechanical strip-only subtypes (see FRENCH_DESIGN.md 5.2 and
FRENCH_POC_WORKFLOW.md row 5):

- ``etre_strip``: aux ``être`` + a nsubj marked Fem or Plur → the participle
  currently agrees with the subject (e.g. "elle est partie"); stripping the
  agreement suffix produces the (wrong) invariant masc-sing form ("parti").
- ``avoir_cod_ante_strip``: aux ``avoir`` + a direct object dependent that
  linearly precedes the participle (a clitic la/les/l' or the relative
  pronoun que) → the participle agrees with that fronted object (e.g. "les
  pommes qu'il a mangées"); stripping produces "mangé".

STRIP ONLY. Adding agreement back (the wrong-direction error, e.g. a
postposed avoir object incorrectly triggering agreement) needs the phase-1
inflection engine and is out of scope for the PoC. Only *regular*
participles (masc-sing ending in -é/-i/-u) are touched — the stripped form
is then guaranteed to be a real word. Irregular participles (mise, faite,
prise, mis, pris, assis, dissous, ...) are skipped via an orthographic
vowel-ending check plus a small closed blocklist for the one ambiguous case
that check alone cannot catch (masc-plural forms that are already invariant
and coincidentally end in a "regular-looking" vowel+s, e.g. "mis", "pris").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# Dependency relations stanza/UD uses for the compound-tense auxiliary
# attaching to the participle it governs.
_AUX_DEPRELS = {"aux:tense", "aux", "aux:pass"}

# Vowel a regular masc-sing participle stem may end in (1st group -é, 2nd
# group / regular 3rd group -i, and the many -u participles whose agreement
# is fully regular even though the verb's conjugation is irregular, e.g.
# vu, lu, bu, su, cru, tenu, venu, voulu, connu, vécu, résolu...).
_REGULAR_ENDING_VOWELS = {"é", "i", "u"}

# Masc-plural surface forms that are already invariant (identical to the
# masc-sing form) because the underlying masc-sing participle itself ends in
# a consonant+vowel+s pattern the orthographic check alone cannot tell apart
# from a genuine regular masc-plural (e.g. "mis" vs. "finis"). Closed list —
# extend if a repair pass turns up more false positives.
_INVARIANT_MASC_PLURAL_BLOCKLIST = frozenset(
    {
        "mis",
        "pris",
        "compris",
        "appris",
        "repris",
        "surpris",
        "entrepris",
        "assis",
        "rassis",
        "conquis",
        "acquis",
        "requis",
        "dissous",
        "absous",
        "résous",
    }
)

# Clitic direct-object pronoun lemmas the "avoir" gate accepts (French UD
# treebanks lemmatize la/les/l' object clitics as "le").
_OBJ_CLITIC_LEMMAS = {"le"}


def _match_capitalization(original: str, new: str) -> str:
    """Match the capitalization pattern of ``original`` onto ``new``.

    Self-contained copy of the (language-agnostic) Russian inflector helper
    of the same name — kept local since French does not yet have a shared
    inflector module (R1 refactor, deferred; see FRENCH_DESIGN.md §4).
    """
    if not original or not new:
        return new
    if original.isupper() and len(original) > 1:
        return new.upper()
    if original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


def _strip_regular_participle(
    word: str, gender: str | None, number: str | None
) -> str | None:
    """Return the masc-sing stem if ``word`` is a regular, strippable
    agreement form; ``None`` if there is nothing to strip or the form looks
    irregular.
    """
    if not word:
        return None
    lower = word.lower()

    if gender == "Fem" and number == "Plur":
        if not lower.endswith("es"):
            return None
        stem = word[:-2]
    elif gender == "Fem":
        if not lower.endswith("e"):
            return None
        stem = word[:-1]
    elif number == "Plur":
        if not lower.endswith("s"):
            return None
        if lower in _INVARIANT_MASC_PLURAL_BLOCKLIST:
            return None
        stem = word[:-1]
    else:
        # Masc singular already — no agreement marking to strip.
        return None

    if not stem or stem == word:
        return None
    if stem[-1].lower() not in _REGULAR_ENDING_VOWELS:
        return None
    return stem


def _find_aux(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Find the compound-tense auxiliary governed by the participle at idx."""
    for t in tokens:
        if t.head_idx == idx and t.dep_rel in _AUX_DEPRELS and t.pos == "AUX":
            return t
    return None


def _has_agreeing_subject(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """True if the participle at idx has an nsubj marked Fem or Plur."""
    for t in tokens:
        if t.head_idx == idx and t.dep_rel == "nsubj":
            return t.get_feature("Gender") == "Fem" or t.get_feature("Number") == "Plur"
    return False


def _is_clitic_object(t: AnalyzedToken) -> bool:
    return t.pos == "PRON" and t.lemma.lower() in _OBJ_CLITIC_LEMMAS


def _is_relative_que(t: AnalyzedToken) -> bool:
    return (
        t.pos == "PRON"
        and t.lemma.lower() == "que"
        and t.get_feature("PronType") == "Rel"
    )


def _has_anteposed_direct_object(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """True if the participle at idx has an obj dependent (clitic la/les/l'
    or relative que) that appears *before* it linearly in the sentence.
    """
    for t in tokens:
        if t.head_idx == idx and t.dep_rel == "obj" and t.idx < idx:
            if _is_clitic_object(t) or _is_relative_que(t):
                return True
    return False


class PastParticipleAgreementHandler:
    """Strip past-participle agreement marking (étre/avoir-anteposed COD)."""

    name = "pp_agreement"
    subtypes = ["etre_strip", "avoir_cod_ante_strip"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "VERB" or token.get_feature("VerbForm") != "Part":
            return False

        gender = token.get_feature("Gender")
        number = token.get_feature("Number")
        if gender != "Fem" and number != "Plur":
            # No agreement marking present on the participle itself.
            return False

        aux = _find_aux(tokens, idx)
        if aux is None:
            return False

        if aux.lemma.lower() == "être":
            if not _has_agreeing_subject(tokens, idx):
                return False
        elif aux.lemma.lower() == "avoir":
            if not _has_anteposed_direct_object(tokens, idx):
                return False
        else:
            return False

        return _strip_regular_participle(token.text, gender, number) is not None

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
        gender = token.get_feature("Gender")
        number = token.get_feature("Number")

        aux = _find_aux(tokens, idx)
        if aux is None:
            return None

        if aux.lemma.lower() == "être":
            if not _has_agreeing_subject(tokens, idx):
                return None
            subtype = "etre_strip"
        elif aux.lemma.lower() == "avoir":
            if not _has_anteposed_direct_object(tokens, idx):
                return None
            subtype = "avoir_cod_ante_strip"
        else:
            return None

        stem = _strip_regular_participle(word, gender, number)
        if stem is None:
            return None

        new_word = _match_capitalization(word, stem)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
