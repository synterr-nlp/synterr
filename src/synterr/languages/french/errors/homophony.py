"""French grammatical-homophone error handler (PoC).

Implements ``grammatical_homophone`` from the French PoC handler roster
(docs/research/FRENCH_POC_WORKFLOW.md, row #1; docs/research/FRENCH_DESIGN.md
§5.2). Five subtypes, each a single-token swap between the two members of a
French grammatical-homophone pair:

    a_à       a (AUX/VERB avoir, 3sg pres)   <-> à (ADP)
    et_est    et (CCONJ)                     <-> est (AUX/VERB être, 3sg pres)
    ce_se     ce (DET/PRON dem)              <-> se (PRON expl/refl on VERB)
    on_ont    on (PRON nsubj)                <-> ont (AUX avoir, 3pl pres)
    son_sont  son (DET poss)                 <-> sont (AUX/VERB être, 3pl pres)

Every gate is a POS/lemma/deprel check on the UD parse (no lexicon-driven
inflection needed - a pure string rewrite, per the PoC's "inflection-free
handlers only" scope trick). Precision over recall: an ambiguous or
internally-inconsistent parse (e.g. a governed verb whose own Number feature
contradicts the subject/auxiliary being corrupted) makes the gate return
False rather than guess - a corruption that reads as accidentally correct
(or mislabels a different error) is worse than no corruption at all.

Confusion-pair surface forms are sourced from
``src/synterr/data/french/homophones.json`` (built from Lexique 3.83, see
that file's ``_meta``) rather than hardcoded, so the pairing data and the
syntactic gates stay separately editable.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken, ErrorResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from random import Random

# ---------------------------------------------------------------------------
# Capitalization helper
#
# Duplicated (not imported) from
# synterr.languages.russian.inflector.match_capitalization: it is a pure,
# language-agnostic string utility, but importing across language packages
# would create an unwanted Russian<->French coupling ahead of the planned R1
# shared-module extraction (FRENCH_DESIGN.md §4). Keep semantics identical.
# ---------------------------------------------------------------------------


def _match_capitalization(original: str, new: str) -> str:
    """Match the capitalization pattern of ``original`` onto ``new``."""
    if not original or not new:
        return new
    if original.isupper() and len(original) > 1:
        return new.upper()
    if original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

# Mirrors homophones.json's "_meta.confusion_sets" - used only if the data
# file is missing so the handler degrades gracefully instead of raising at
# collection time.
_FALLBACK_PAIRS: dict[str, tuple[str, str]] = {
    "a_à": ("a", "à"),
    "et_est": ("et", "est"),
    "ce_se": ("ce", "se"),
    "on_ont": ("on", "ont"),
    "son_sont": ("son", "sont"),
}


def _get_package_data_path() -> Path:
    """Path to the package data directory (src/synterr/data/french)."""
    try:
        pkg_files = resources.files("synterr.data.french")
        if hasattr(pkg_files, "_path"):
            return Path(pkg_files._path)
    except (TypeError, ModuleNotFoundError):
        pass
    # __file__ = src/synterr/languages/french/errors/homophony.py
    return Path(__file__).parent.parent.parent.parent / "data" / "french"


@lru_cache(maxsize=1)
def _load_confusion_pairs() -> dict[str, tuple[str, str]]:
    """Load subtype -> (form_a, form_b) surface-form pairs.

    Order matters: ``form_a`` is the first JSON list element and pairs with
    the "first" gate in ``_GATES`` for that subtype, ``form_b`` with the
    second (see the module docstring table).
    """
    data_path = _get_package_data_path() / "homophones.json"
    if not data_path.exists():
        return dict(_FALLBACK_PAIRS)
    with data_path.open(encoding="utf-8") as f:
        data = json.load(f)
    sets = data.get("_meta", {}).get("confusion_sets", {})
    pairs = {
        subtype: (members[0], members[1])
        for subtype, members in sets.items()
        if len(members) == 2
    }
    return pairs or dict(_FALLBACK_PAIRS)


# ---------------------------------------------------------------------------
# Shared gate helpers
# ---------------------------------------------------------------------------


def _head(tokens: Sequence[AnalyzedToken], token: AnalyzedToken) -> AnalyzedToken | None:
    """The dependency head of ``token``, or None if absent/out of range."""
    idx = token.head_idx
    if idx is None or not (0 <= idx < len(tokens)):
        return None
    return tokens[idx]


def _number_compatible(
    tokens: Sequence[AnalyzedToken], token: AnalyzedToken, required: str
) -> bool:
    """True unless the governed verb's own Number feature contradicts ``required``.

    Used by the on/ont gates ("check governed verb number" in the spec): the
    governed verb is only consulted when it is itself a verb form; an
    explicit Number value that disagrees with the subject/auxiliary being
    corrupted blocks the swap (looks like an inconsistent parse - safer not
    to fire). A missing Number feature, or a non-verbal head, is not treated
    as a conflict.
    """
    head = _head(tokens, token)
    if head is None or head.pos not in {"VERB", "AUX"}:
        return True
    number = head.get_feature("Number")
    return number is None or number == required


# ---------------------------------------------------------------------------
# Per-subtype gates. Each subtype maps to (gate_form_a, gate_form_b): a gate
# returns True when the token at ``idx`` is a legitimate corruption site for
# that surface form (i.e. the *other* member of the pair would be the
# error). Gates never look at token.text for the POS/lemma/deprel checks
# themselves - the text match against the JSON-sourced form is done once in
# GrammaticalHomophoneErrorHandler._match, keeping the confusion-pair data
# and the syntactic conditions independently editable.
# ---------------------------------------------------------------------------


def _gate_a_is_avoir(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return (
        token.pos in {"AUX", "VERB"}
        and token.lemma == "avoir"
        and token.get_feature("Person") == "3"
        and token.get_feature("Number") == "Sing"
    )


def _gate_à_is_adp(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    return tokens[idx].pos == "ADP"


def _gate_et_is_cconj(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return token.pos == "CCONJ" and token.lemma == "et"


def _gate_est_is_etre(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return (
        token.pos in {"AUX", "VERB"}
        and token.lemma == "être"
        and token.get_feature("Person") == "3"
        and token.get_feature("Number") == "Sing"
        and token.get_feature("Tense") == "Pres"
    )


def _gate_ce_is_dem(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    head = _head(tokens, token)
    if head is None:
        return False
    if token.pos == "DET" and token.dep_rel == "det" and head.pos == "NOUN":
        return True
    return bool(
        token.pos == "PRON" and token.dep_rel == "nsubj" and head.lemma == "être"
    )


# UD deprels marking "se" as an expletive/reflexive clitic of its verb.
_SE_REFLEXIVE_DEPRELS = {"expl", "expl:comp", "expl:pass", "expl:subj", "obj", "iobj"}


def _gate_se_is_reflexive(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    if token.pos != "PRON" or token.lemma != "se":
        return False
    if token.dep_rel not in _SE_REFLEXIVE_DEPRELS:
        return False
    head = _head(tokens, token)
    return head is not None and head.pos in {"VERB", "AUX"}


def _gate_on_is_nsubj(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return (
        token.pos == "PRON"
        and token.lemma == "on"
        and token.dep_rel == "nsubj"
        and _number_compatible(tokens, token, "Sing")
    )


def _gate_ont_is_avoir_3pl(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return (
        token.pos == "AUX"
        and token.lemma == "avoir"
        and token.get_feature("Person") == "3"
        and token.get_feature("Number") == "Plur"
        and _number_compatible(tokens, token, "Plur")
    )


def _gate_son_is_poss_det(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    head = _head(tokens, token)
    return (
        token.pos == "DET"
        and token.lemma == "son"
        and token.dep_rel == "det"
        and head is not None
        and head.pos == "NOUN"
    )


def _gate_sont_is_etre_3pl(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    token = tokens[idx]
    return (
        token.pos in {"AUX", "VERB"}
        and token.lemma == "être"
        and token.get_feature("Person") == "3"
        and token.get_feature("Number") == "Plur"
        and token.get_feature("Tense") == "Pres"
    )


if TYPE_CHECKING:
    _GateFn = Callable[[Sequence[AnalyzedToken], int], bool]

_GATES: dict[str, tuple[_GateFn, _GateFn]] = {
    "a_à": (_gate_a_is_avoir, _gate_à_is_adp),
    "et_est": (_gate_et_is_cconj, _gate_est_is_etre),
    "ce_se": (_gate_ce_is_dem, _gate_se_is_reflexive),
    "on_ont": (_gate_on_is_nsubj, _gate_ont_is_avoir_3pl),
    "son_sont": (_gate_son_is_poss_det, _gate_sont_is_etre_3pl),
}


class GrammaticalHomophoneErrorHandler:
    """Swap members of a French grammatical-homophone pair.

    Subtypes: a_à, et_est, ce_se, on_ont, son_sont (bidirectional - both
    directions are attested learner/native errors for every pair). See the
    module docstring for the gate table and docs/research/FRENCH_DESIGN.md
    §5.2 for the design rationale.
    """

    name = "grammatical_homophone"
    subtypes = ["a_à", "et_est", "ce_se", "on_ont", "son_sont"]
    category = "SPELL"
    changes_length = False

    def _match(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, str] | None:
        """Return (subtype, replacement_form) if ``idx`` is a valid swap site."""
        if idx < 0 or idx >= len(tokens):
            return None
        token = tokens[idx]
        text = token.text.lower()
        for subtype, (form_a, form_b) in _load_confusion_pairs().items():
            gates = _GATES.get(subtype)
            if gates is None:
                continue
            gate_a, gate_b = gates
            if text == form_a.lower() and gate_a(tokens, idx):
                return subtype, form_b
            if text == form_b.lower() and gate_b(tokens, idx):
                return subtype, form_a
        return None

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return self._match(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply the homophone swap and return the ErrorResult."""
        match = self._match(tokens, idx)
        if match is None:
            return None
        subtype, new_form = match

        word = sentence[idx]
        new_word = _match_capitalization(word, new_form)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=f"{self.name}_{subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
