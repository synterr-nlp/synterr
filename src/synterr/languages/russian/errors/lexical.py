"""Russian lexical error handlers - paronyms, ..."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import AnalyzedToken, ErrorResult
from synterr.languages.russian.errors.morphological import (
    _get_pymorphy_parse,
    inflect_word,
)
from synterr.languages.russian.inflector import (
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
    match_capitalization,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

# Groups whose key starts with this prefix are directed confusions: only the
# first member may be corrupted (e.g. чем→как is an attested error, but
# как→чем is garbage no learner produces).
_DIRECTED_PREFIX = "directed_"


def _confusion_candidates(group_key: str, members: list[str], word: str) -> list[str]:
    """Single-token replacement candidates for ``word`` within one group.

    Returns [] when the word is not a valid corruption source in this group
    (absent, or a non-head member of a directed group). Multi-word entries are
    never offered: a length-preserving $REPLACE cannot emit an intra-token
    space without misaligning the token/tag stream.
    """
    if group_key.startswith(_DIRECTED_PREFIX):
        if word != members[0]:
            return []
        pool = members[1:]
    else:
        if word not in members:
            return []
        pool = members
    return [x for x in pool if x != word and " " not in x]


def _all_confusion_candidates(groups: dict[str, list[str]], word: str) -> list[str]:
    """Union of candidates across every group containing ``word``.

    Collecting from all groups (instead of breaking at the first match)
    means JSON dict ordering can never decide which sense of a polysemous
    word gets corrupted.
    """
    candidates: list[str] = []
    for key, members in groups.items():
        for candidate in _confusion_candidates(key, members, word):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _has_confusion(groups: dict[str, list[str]], word: str) -> bool:
    return bool(_all_confusion_candidates(groups, word))


def _pick_confusion(groups: dict[str, list[str]], word: str, rng: Random) -> str | None:
    candidates = _all_confusion_candidates(groups, word)
    if candidates:
        return rng.choice(candidates)
    return None


# UD features whose pymorphy equivalents must survive a paronym swap intact:
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


# Grammemes that may be transferred from the original word's parse to the
# paronym replacement: POS class plus form-level (inflectional) values.
# Lexeme-level grammemes (Qual, aspect, transitivity, animacy) must stay
# behind — the partner lexeme often lacks them, which would make inflection
# fail spuriously (e.g. практичный is Qual but практический is not).
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
    """Form-level grammemes to carry over to the paronym replacement."""
    grammemes = set(parse.tag.grammemes)
    transfer = grammemes & (_TRANSFER_POS | _TRANSFER_FORM)
    if "accs" in transfer:
        # Accusative surface form depends on animacy; without it pymorphy
        # would pick an arbitrary anim/inan variant.
        transfer |= grammemes & _ANIMACY
    return transfer


class ParonymErrorHandler:
    """Replace word from paronyms list to one from its paronyms"""

    name = "paronym"
    subtypes = ["paronym"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._paronyms = None
        self.__morph = None

    @property
    def _morph(self):
        if self.__morph is None:
            from synterr.languages.russian.resources import get_morph_analyzer

            self.__morph = get_morph_analyzer()
        return self.__morph

    @property
    def paronyms(self):
        if self._paronyms is None:
            from synterr.languages.russian.resources import get_paronyms

            self._paronyms = get_paronyms()
        return self._paronyms

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return tokens[idx].lemma in self.paronyms

    def _disambiguated_parse(self, token: AnalyzedToken, word: str):
        """Pick a pymorphy parse consistent with stanza's features.

        The stored ``pymorphy_parse`` is context-free (e.g. 'цветной' ->
        ADJF femn,sing,gent), so blindly transferring its grammemes breaks
        agreement ('цветной телевизор' -> 'цветастой телевизор'). Trust
        stanza's disambiguation: keep the stored parse only if it carries
        every case/number/gender grammeme stanza assigned, otherwise re-pick
        from all parses; if none is consistent, skip rather than guess.
        """
        parse = _get_pymorphy_parse(token)
        wanted = _context_grammemes(token)
        if not wanted:
            return parse
        if parse is not None and wanted <= set(parse.tag.grammemes):
            return parse
        for candidate in self._morph.parse(word):
            if wanted <= set(candidate.tag.grammemes):
                return candidate
        return None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply paronym error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.lemma not in self.paronyms:
            return None

        parse = self._disambiguated_parse(token, word)
        if parse is None:
            return None

        grammemes = _transfer_grammemes(parse)
        if not grammemes:
            return None

        new_word_lemma = rng.choice(self.paronyms.get(token.lemma))
        new_word_parse = self._morph.parse(new_word_lemma)[0]
        new_word = inflect_word(new_word_parse, grammemes, word)
        if new_word is None:
            return None
        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# Cases each lexicon preposition governs *in the sense its confusion group
# covers* (UD case names). Rozental keeps preposition choice (§199) and case
# government (§200) apart: a swap is a clean Prep error only when original and
# replacement govern the governed noun's observed case. о/об are limited to
# the topic sense (+Loc) so the contact sense (удариться о камень, +Acc) never
# swaps to про; с is limited to the source sense (+Gen) so comitative с+Ins
# (гулял с другом) never swaps to из/от.
_PREP_GOVERNMENT: dict[str, set[str]] = {
    "в": {"Acc", "Loc"},
    "на": {"Acc", "Loc"},
    "из": {"Gen"},
    "с": {"Gen"},
    "от": {"Gen"},
    "о": {"Loc"},
    "об": {"Loc"},
    "обо": {"Loc"},
    "про": {"Acc"},
    "к": {"Dat"},
    "до": {"Gen"},
    "благодаря": {"Dat"},
    "из-за": {"Gen"},
    "по причине": {"Gen"},
}

# POS that terminate the rightward scan for the governed nominal: past them
# we are no longer inside this preposition's phrase.
_GOVERNED_SCAN_STOP_POS = {"PUNCT", "VERB", "ADP", "CCONJ", "SCONJ"}


def _governed_case(tokens: Sequence[AnalyzedToken], idx: int) -> str | None:
    """Case of the nominal governed by the ADP at ``idx``.

    With depparse enabled, the ADP's head *is* its complement (UD ``case``
    relation). Without it, fall back to the first Case-bearing token to the
    right: agreeing determiners/adjectives share the complement's case, so
    the first hit inside the phrase is reliable.
    """
    token = tokens[idx]
    head_idx = token.head_idx
    if head_idx is not None and 0 <= head_idx < len(tokens) and head_idx != idx:
        case = tokens[head_idx].get_feature("Case")
        if case:
            return case
    for other in tokens[idx + 1 : idx + 5]:
        if other.pos in _GOVERNED_SCAN_STOP_POS:
            break
        case = other.get_feature("Case")
        if case:
            return case
    return None


class PrepositionErrorHandler:
    """Replace preposition with an attested confusion from the same group.

    Groups in ``prepositions.json`` are *confusion* sets, not synonym sets:
    every swap must yield a genuine error (attested learner confusion like
    в/на, из/с, or a different-government pair like благодаря/из-за where the
    unreinflected complement exposes the error). Synonymous prepositions with
    identical government (у ~ при ~ около ~ возле, через ~ сквозь — Rozental
    §199) are excluded: swapping them produces correct Russian, which would
    teach a GEC model to rewrite valid text.

    The handler is length-preserving (single ``$REPLACE``), so it only
    substitutes single-token replacements. Multi-word entries in the lexicon
    (e.g. ``"по причине"``) are skipped: writing one into a single token slot
    would smuggle an intra-token space into the GECToR unit and misalign the
    token/tag stream.

    Case government (Rozental §199 vs §200): a swap fires only when both the
    original and the replacement govern the case observed on the dependent
    noun. Different-government swaps (к+Dat -> до+Gen, благодаря+Dat ->
    из-за+Gen) would leave the unreinflected complement as a *second* error
    that RLC annotates Gov, not Prep — a mislabeled double error is worse
    than no error, so those candidates are skipped. When the governed case
    cannot be determined, the handler does not fire.
    """

    name = "preposition"
    subtypes = ["preposition"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._prepositions = None

    @property
    def prepositions(self):
        if self._prepositions is None:
            from synterr.languages.russian.resources import get_preposition_list

            self._prepositions = get_preposition_list()
        return self._prepositions

    def _candidates(
        self, tokens: Sequence[AnalyzedToken], idx: int, word: str
    ) -> list[str]:
        """Same-case-frame replacement candidates for the ADP at ``idx``."""
        case = _governed_case(tokens, idx)
        if case is None:
            return []
        if case not in _PREP_GOVERNMENT.get(word, set()):
            # Sense outside the lexicon's frames (e.g. comitative с+Ins) —
            # the confusion group does not apply here.
            return []
        return [
            candidate
            for candidate in _all_confusion_candidates(self.prepositions, word)
            if case in _PREP_GOVERNMENT.get(candidate, set())
        ]

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos != "ADP":
            return False
        return bool(self._candidates(tokens, idx, tokens[idx].lemma))

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply preposition error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos != "ADP":
            return None

        candidates = self._candidates(tokens, idx, word.lower())
        if not candidates:
            return None
        new_word = rng.choice(candidates)

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


class ConjunctionErrorHandler:
    """Replace conjunction with an attested confusion from the same group.

    Groups in ``conjunctions.json`` are *confusion* sets, not synonym sets:
    pure synonyms (или ~ либо, и ~ да, хотя ~ хоть — equivalent variants in
    Rozental's rules on homogeneous members) are excluded because swapping
    them yields correct Russian. ``directed_*`` groups corrupt only their
    first member (чем→как is an attested error; как→чем is impossible).
    """

    name = "conjunction"
    subtypes = ["conjunction"]
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self._conjunctions = None

    @property
    def conjunctions(self):
        if self._conjunctions is None:
            from synterr.languages.russian.resources import get_conjunction_list

            self._conjunctions = get_conjunction_list()
        return self._conjunctions

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].pos not in ["CCONJ", "SCONJ"]:
            return False
        return _has_confusion(self.conjunctions, tokens[idx].lemma)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply conjunction error"""

        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]

        if token.pos not in ["CCONJ", "SCONJ"]:
            return None

        new_word = _pick_confusion(self.conjunctions, word.lower(), rng)
        if new_word is None:
            return None

        new_word = match_capitalization(word, new_word)

        sentence[idx] = new_word
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
