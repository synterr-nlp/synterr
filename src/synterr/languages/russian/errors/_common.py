"""Helpers shared by the Russian handler modules.

Token accessors, the pymorphy grammeme-transfer machinery used by the
lexical-substitution handlers, the bundled-lexicon directory, and the
subtype-gating boilerplate every multi-subtype handler carries.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
)
from synterr.languages.russian.resources import get_morph_analyzer

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from synterr.core.protocol import AnalyzedToken

# Bundled lexicon directory (src/synterr/data/russian), alongside the other
# language resources (paronyms, collocations, ...).
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "russian"

# Finite predicate POS. Short-form participle predicates ("приглашено",
# "убеждён") are VERB/VerbForm=Part in stanza's SynTagRus tagset, so they
# fall out of _is_predicate_token too.
FINITE_POS = frozenset({"VERB", "AUX"})

# UD Animacy → pymorphy grammeme. The inflector has no animacy map, but the
# Acc slot of masc-singular and plural adjectives/possessives is
# animacy-ambiguous in pymorphy (взрывотехнический/взрывотехнического, моего
# vs мой), so agreement and pronoun handlers must pin it — read off the noun
# being modified, since свой/мой/... never carry Animacy themselves.
UD_TO_PYMORPHY_ANIMACY = {"Anim": "anim", "Inan": "inan"}


def _get_pymorphy_parse(token: AnalyzedToken):
    """Get pymorphy parse object from token."""
    return token.extra.get("pymorphy_parse")


def _get_token_safe(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Safely get token by index, returning None if out of bounds."""
    if 0 <= idx < len(tokens):
        return tokens[idx]
    return None


def _is_predicate_token(tok: AnalyzedToken) -> bool:
    """A token that anchors a clause as its predicate: a finite verb/aux, or
    a short participle («расположены», «убеждён») — the predicative forms."""
    if tok.pos not in FINITE_POS:
        return False
    verb_form = tok.get_feature("VerbForm")
    if verb_form in (None, "Fin"):
        return True
    return verb_form == "Part" and tok.get_feature("Variant") == "Short"


# UD features whose pymorphy equivalents must survive a lexical swap intact:
# transferring an undisambiguated parse's case/gender/number stacks a spurious
# agreement error on top of the intended Lex error.
_UD_FEATURE_MAPS = (
    ("Case", UD_TO_PYMORPHY_CASE),
    ("Number", UD_TO_PYMORPHY_NUMBER),
    ("Gender", UD_TO_PYMORPHY_GENDER),
)


def _context_grammemes(token: AnalyzedToken) -> set[str]:
    """pymorphy grammemes implied by stanza's disambiguated features."""
    wanted: set[str] = set()
    for feature, mapping in _UD_FEATURE_MAPS:
        value = token.features.get(feature)
        grammeme = mapping.get(value) if value is not None else None
        if grammeme:
            wanted.add(grammeme)
    return wanted


# Grammemes that may be transferred from the original word's parse to a
# lexical replacement (paronym, collocate): POS class plus form-level
# (inflectional) values. Transferring the POS grammeme (PRTS/PRTF/...) and
# voice (actv/pssv) is what keeps a short passive participle a short passive
# participle: "принято" → "сделано", not the finite "сделало" (2026-07
# annotation pass, 20/73 flagged). Lexeme-level grammemes (Qual, aspect,
# transitivity, animacy) must stay behind — the partner lexeme often lacks
# them, which would make inflection fail spuriously (e.g. практичный is Qual
# but практический is not).
_TRANSFER_POS = {
    "NOUN",
    "ADJF",
    "ADJS",
    "COMP",
    "VERB",
    "INFN",
    "PRTF",
    "PRTS",
    "GRND",
    "NUMR",
    "ADVB",
}
_TRANSFER_FORM = {
    "nomn",
    "gent",
    "datv",
    "accs",
    "ablt",
    "loct",
    "voct",
    "gen2",
    "loc2",
    "sing",
    "plur",
    "masc",
    "femn",
    "neut",
    "1per",
    "2per",
    "3per",
    "past",
    "pres",
    "futr",
    "actv",
    "pssv",
    "indc",
    "impr",
}
_ANIMACY = {"anim", "inan"}


def _transfer_grammemes(parse) -> set[str]:
    """Form-level grammemes to carry over to the lexical replacement."""
    grammemes = set(parse.tag.grammemes)
    transfer = grammemes & (_TRANSFER_POS | _TRANSFER_FORM)
    if "accs" in transfer:
        # Accusative surface form depends on animacy; without it pymorphy
        # would pick an arbitrary anim/inan variant.
        transfer |= grammemes & _ANIMACY
    return transfer


class MorphAnalyzerMixin:
    """Handlers that re-parse candidate surfaces (not attached to any token)
    reach the shared pymorphy3 analyzer as ``self._morph``."""

    @property
    def _morph(self):
        return get_morph_analyzer()


class SubtypeGateMixin:
    """Subtype restriction shared by multi-subtype handlers.

    ``set_enabled_subtypes`` is used by targeted SFT / CLI ``:subtype``. When
    set, ``apply()`` returns None for positions whose subtype falls outside
    the enabled set — letting the pipeline try another position instead of
    emitting a mislabeled error.
    """

    subtypes: ClassVar[list[str]]

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes


class WeightedSubtypeMixin(SubtypeGateMixin):
    """Subtype gate plus per-subtype weights seeded from ``DEFAULT_WEIGHTS``.

    ``set_subtype_weights`` resets to the defaults and then overrides only
    the subtypes the handler actually declares; unknown keys are ignored.
    """

    DEFAULT_WEIGHTS: ClassVar[Mapping[str, float]]

    def __init__(self) -> None:
        super().__init__()
        self._weights: dict[str, float] = dict(self.DEFAULT_WEIGHTS)

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = dict(self.DEFAULT_WEIGHTS)
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight
