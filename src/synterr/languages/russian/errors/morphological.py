"""Russian morphological error handlers - case, number, gender, tense errors."""

from __future__ import annotations

import json
import random as random_module
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.inflector import (
    CASES,
    GENDERS,
    PERSONS,
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_NUMBER,
    UD_TO_PYMORPHY_PERSON,
    UD_TO_PYMORPHY_TENSE,
    inflect_word,
    match_capitalization,
    sample_confused_grammeme,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


def _is_adj_or_participle(token: AnalyzedToken) -> bool:
    """Check if token is adjective or participle (VerbForm=Part).

    Participles agree with head nouns in case/number/gender just like adjectives.
    Stanza may tag them as ADJ (SynTagRus) or VERB with VerbForm=Part.
    """
    if token.pos == "ADJ":
        return True
    return bool(token.pos == "VERB" and token.get_feature("VerbForm") == "Part")


# dep_rels used by participles/adjectives pointing at their head noun
_MODIFIER_DEPRELS = {"amod", "acl", "acl:relcl"}

# UD Animacy → pymorphy grammeme. The inflector has no animacy map, but the
# Acc slot of masc-singular and plural adjectives is animacy-ambiguous
# (взрывотехнический/взрывотехнического), so agreement handlers must pin it.
_UD_TO_PYMORPHY_ANIMACY = {"Anim": "anim", "Inan": "inan"}

# dep_rels where the head governs the noun's case (government relation)
_GOVERNED_DEPRELS = {"obl", "nmod", "iobj", "obj"}

# Subject dep_rels. Shared by NounCaseErrorHandler (subject-case subtype) and
# NounNumberErrorHandler (predicate agreement evidence).
_SUBJECT_DEPRELS = {"nsubj", "nsubj:pass"}


def _get_pymorphy_parse(token: AnalyzedToken):
    """Get pymorphy parse object from token."""
    return token.extra.get("pymorphy_parse")


def _get_token_safe(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """Safely get token by index, returning None if out of bounds."""
    if 0 <= idx < len(tokens):
        return tokens[idx]
    return None


def _find_dependent(
    tokens: Sequence[AnalyzedToken], head_idx: int, dep_rel: str
) -> AnalyzedToken | None:
    """Find first token that depends on head_idx with given dep_rel."""
    for token in tokens:
        if token.head_idx == head_idx and token.dep_rel == dep_rel:
            return token
    return None


# Small hand-curated lexicons for §150/§154/§155 handlers, bundled under
# synterr/data/russian/ alongside the other language resources (paronyms,
# collocations, ...). Loaded lazily and cached: these files are tiny and
# rarely change, so a process-lifetime cache is appropriate.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "russian"


def _load_json_resource(filename: str) -> dict:
    """Load a bundled JSON data file, or {} if it is missing."""
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _gen_partitive_lexicon() -> frozenset[str]:
    """Masculine mass nouns with a colloquial partitive genitive in -у/-ю."""
    return frozenset(_load_json_resource("gen_partitive_nouns.json").get("nouns", []))


@lru_cache(maxsize=1)
def _instr_pl_lexicon() -> dict[str, dict]:
    """Nouns with a norm/marked instrumental-plural variant (-ями vs -ьми)."""
    return _load_json_resource("instr_pl_variants.json").get("lexemes", {})


@lru_cache(maxsize=1)
def _gen_pl_nonstandard_lexicon() -> dict[str, dict]:
    """Nouns with a frequent nonstandard genitive-plural variant."""
    return _load_json_resource("gen_pl_nonstandard.json").get("lexemes", {})


class NounCaseErrorHandler:
    """Change noun case to create morphological error.

    Arc-aware subtypes (phase 2 of the dep-arc plan): the noun's own dep_rel
    deterministically decides the subtype, so subtype weights act as enable
    gates rather than sampling weights (same as CommaDeleteHandler) — a
    preset that zeroes a subtype makes the handler skip nouns classifying
    into it instead of leaking them under another label.

    - ``noun_case_governed``: head governs the case (obl/nmod/iobj/obj) —
      textbook government errors ("ждать автобуса")
    - ``noun_case_subject``: subject position (nsubj/nsubj:pass) — learner
      errors putting the subject in an oblique case (RLC 'Nominative')
    - ``noun_case_other``: any other dep-attached noun (appos, conj, root, …)

    No dep info → no fire: without an arc there is no classification
    evidence, and pre-split behavior was already dep-gated.
    """

    name = "noun_case"
    subtypes = ["noun_case_governed", "noun_case_subject", "noun_case_other"]
    category = "MORPH"
    changes_length = False

    # Enable gates, not sampling weights (classification is deterministic);
    # magnitudes document the attestation split: government is the
    # well-attested RLC class.
    DEFAULT_WEIGHTS = {
        "noun_case_governed": 70,
        "noun_case_subject": 20,
        "noun_case_other": 10,
    }

    def __init__(self) -> None:
        self._confusion_matrices: dict | None = None
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self._enabled_subtypes: set[str] | None = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        """Restrict to specific subtypes (used by targeted SFT / CLI :subtype)."""
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    @staticmethod
    def _classify(token: AnalyzedToken) -> str | None:
        """Classify the case-error subtype from the noun's dep arc."""
        if not token.dep_rel:
            return None
        if token.dep_rel in _GOVERNED_DEPRELS:
            return "noun_case_governed"
        if token.dep_rel in _SUBJECT_DEPRELS:
            return "noun_case_subject"
        return "noun_case_other"

    def _subtype_allowed(self, subtype: str) -> bool:
        if self._enabled_subtypes is not None:
            # Explicit targeting (CLI :subtype / SFT) overrides weight gates.
            return subtype in self._enabled_subtypes
        return self._weights.get(subtype, 0) > 0

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if noun case error can be applied.

        Requires a dep arc (subtype classification evidence) and an enabled
        subtype for that arc; see class docstring for the arc → subtype map.
        """
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        subtype = self._classify(token)
        if subtype is None or not self._subtype_allowed(subtype):
            return False
        parse = _get_pymorphy_parse(token)
        return parse is not None and token.has_feature("Case")

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply noun case error."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        subtype = self._classify(token)
        if subtype is None or not self._subtype_allowed(subtype):
            return None

        current_case_ud = token.get_feature("Case")
        current_case = UD_TO_PYMORPHY_CASE.get(current_case_ud)

        # Use confusion matrix for weighted target selection
        target_case = None
        if self._confusion_matrices and "case" in self._confusion_matrices:
            target_ud = sample_confused_grammeme(
                current_case_ud, self._confusion_matrices["case"], rng
            )
            if target_ud:
                target_case = UD_TO_PYMORPHY_CASE.get(target_ud)

        # Fallback: random case
        if target_case is None:
            other_cases = [c for c in CASES if c != current_case]
            target_case = rng.choice(other_cases)

        new_word = inflect_word(parse, {target_case}, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            original_case = token.get_feature("Case", "Nom")
            return ErrorResult(
                error_type=subtype,
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_CASE_{original_case}",
            )

        return None


# Dependents whose form visibly agrees with the noun in number — required
# evidence for a recoverable number error. Without them the flip is a free
# semantic choice ("купил книгу"/"купил книги" are both correct → non-error).
_NUMBER_AGREEING_DEPRELS = {"det", "amod"}

# Invariant possessives: their Number feature reflects the possessor, not the
# head noun ("его книга" / "его книги"), so they constrain nothing.
_INVARIANT_POSSESSIVES = {"его", "её", "ее", "их"}

# Predicate POS that agree with an nsubj subject in number.
# Nominal predicates need not agree ("Книги — лучший подарок" is correct).
_NUMBER_PREDICATE_POS = {"VERB", "AUX", "ADJ"}


class NounNumberErrorHandler:
    """Change noun number (singular ↔ plural).

    Only fires when some other word is number-agreed with the noun (det/amod,
    participle modifier, numeral, or a number-marked predicate for subjects):
    the agreeing word stays untouched and serves as recoverable evidence.
    """

    name = "noun_number"
    subtypes = ["noun_number"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if noun number error can be applied."""
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or not token.has_feature("Number"):
            return False
        return self._has_number_evidence(tokens, idx)

    @staticmethod
    def _has_number_evidence(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """True when the noun's number is constrained by an agreeing word."""
        token = tokens[idx]
        for i, t in enumerate(tokens):
            if i == idx or t.head_idx != idx:
                continue
            dep_rel = t.dep_rel or ""
            # Numerals constrain the noun's form ("пять книг" → "пять книги").
            if dep_rel.startswith("nummod"):
                return True
            if (
                dep_rel in _NUMBER_AGREEING_DEPRELS
                and t.has_feature("Number")
                and t.text.lower() not in _INVARIANT_POSSESSIVES
            ):
                return True
            # Participle modifiers agree like adjectives (прочитанная книга);
            # finite acl:relcl verbs agree with their own subject, not the noun.
            if (
                dep_rel.startswith("acl")
                and t.get_feature("VerbForm") == "Part"
                and t.has_feature("Number")
            ):
                return True
        if token.dep_rel in _SUBJECT_DEPRELS and token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if (
                head is not None
                and head.pos in _NUMBER_PREDICATE_POS
                and head.has_feature("Number")
            ):
                return True
        return False

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply noun number error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        # Flip number
        target_num = "plur" if token.get_feature("Number") == "Sing" else "sing"
        new_word = inflect_word(parse, {target_num}, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            original_number = token.get_feature("Number", "Sing")
            return ErrorResult(
                error_type="noun_number",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
            )

        return None


def _amod_head_noun(tokens: Sequence[AnalyzedToken], idx: int) -> AnalyzedToken | None:
    """The adjective's amod head, when dep info points at a NOUN/PROPN."""
    token = tokens[idx]
    if token.dep_rel == "amod" and token.head_idx is not None:
        head = _get_token_safe(tokens, token.head_idx)
        if head is not None and head.pos in {"NOUN", "PROPN"}:
            return head
    return None


def _passes_adj_agreement_guards(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Precision guards for adj_gender/adj_number (native-annotation pass).

    - pymorphy Apro (pronominal adjectives: иного, данный, другим) — their
      flips read as lexical substitutions, not agreement errors
    - PRTF/PRTS parses (participles, often stanza-mistagged ADJ: вызванного)
      — their agreement is licensed by the verbal frame, and short forms
      inflect into non-words (убеждённы)
    - with dep info present, only amod modifiers of a NOUN/PROPN head fire:
      predicatives (нужно, очевидно, должен) and substantivized idioms
      (пойти на попятную) carry no amod arc and corrupting them is a
      non-error
    """
    token = tokens[idx]
    parse = _get_pymorphy_parse(token)
    if parse is None:
        return False
    tag = str(parse.tag)
    if "Apro" in tag or "PRTF" in tag or "PRTS" in tag:
        return False
    if token.dep_rel:
        return _amod_head_noun(tokens, idx) is not None
    return True


def _noun_gender_grammeme(noun: AnalyzedToken) -> str | None:
    """Noun's gender as a pymorphy grammeme.

    UD feature first; plural nouns carry no UD Gender, so fall back to the
    noun's own pymorphy tag (неполадок → femn).
    """
    gender_ud = noun.get_feature("Gender")
    if gender_ud:
        return UD_TO_PYMORPHY_GENDER.get(gender_ud)
    parse = _get_pymorphy_parse(noun)
    if parse is not None:
        return getattr(parse.tag, "gender", None)
    return None


def _animacy_grammeme(token: AnalyzedToken, head: AnalyzedToken | None) -> str | None:
    """Animacy grammeme for Acc agreement, from the head noun or the token."""
    for source in (head, token):
        if source is None:
            continue
        animacy = _UD_TO_PYMORPHY_ANIMACY.get(source.get_feature("Animacy"))
        if animacy is None:
            parse = _get_pymorphy_parse(source)
            animacy = getattr(parse.tag, "animacy", None) if parse else None
        if animacy:
            return animacy
    return None


def _preserved_case_grammemes(
    token: AnalyzedToken,
    head: AnalyzedToken | None,
    *,
    target_gender: str | None,
    target_number: str | None,
) -> set[str] | None:
    """Grammemes pinning the token's original case through the inflection.

    Without an explicit case pymorphy drifts to whatever paradigm slot comes
    first (взрывотехническую + masc → animate-Acc/Gen взрывотехнического).
    The Acc slot is animacy-ambiguous for masc-singular and plural targets,
    so those also carry an animacy grammeme; unknown animacy there → None
    (precision-first skip). Fem/neut Acc forms carry no animacy in pymorphy,
    so adding one would make the inflection fail — it is omitted.
    """
    case_ud = token.get_feature("Case")
    py_case = UD_TO_PYMORPHY_CASE.get(case_ud) if case_ud else None
    if py_case is None:
        return set()
    grammemes = {py_case}
    if case_ud == "Acc" and (target_number == "plur" or target_gender == "masc"):
        animacy = _animacy_grammeme(token, head)
        if animacy is None:
            return None
        grammemes.add(animacy)
    return grammemes


class AdjCaseErrorHandler:
    """Change adjective/participle case."""

    name = "adj_case"
    subtypes = ["adj_case"]
    category = "MORPH"
    changes_length = False
    _confusion_matrices = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective/participle case error can be applied."""
        token = tokens[idx]
        if not _is_adj_or_participle(token):
            return False
        parse = _get_pymorphy_parse(token)
        return parse is not None and token.has_feature("Case")

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply adjective case error."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        # Reference case: prefer head noun's case (dep tree) if available
        ref_case_ud = token.get_feature("Case")
        if token.dep_rel in _MODIFIER_DEPRELS and token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if head and head.has_feature("Case"):
                ref_case_ud = head.get_feature("Case")

        current_case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))

        # Use confusion matrix for weighted target selection
        target_case = None
        if self._confusion_matrices and "case" in self._confusion_matrices:
            target_ud = sample_confused_grammeme(
                ref_case_ud, self._confusion_matrices["case"], rng
            )
            if target_ud:
                candidate = UD_TO_PYMORPHY_CASE.get(target_ud)
                if candidate != current_case:
                    target_case = candidate

        # Fallback: random case
        if target_case is None:
            other_cases = [c for c in CASES if c != current_case]
            target_case = rng.choice(other_cases)

        new_word = inflect_word(parse, {target_case}, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            original_case = token.get_feature("Case", "Nom")
            return ErrorResult(
                error_type="adj_case",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_CASE_{original_case}",
            )

        return None


class AdjNumberErrorHandler:
    """Change adjective/participle number.

    Precision guards (native-annotation pass): pronominal adjectives (Apro),
    participle parses (PRTF/PRTS) and non-amod tokens are skipped — see
    ``_passes_adj_agreement_guards``. Pl→Sg additionally requires the head
    noun's gender (plural adjectives carry none, and pymorphy would default
    the singular to masculine), and the original case (with animacy for Acc)
    is pinned through the inflection.
    """

    name = "adj_number"
    subtypes = ["adj_number"]
    category = "MORPH"
    changes_length = False
    _confusion_matrices = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective/participle number error can be applied."""
        token = tokens[idx]
        if not _is_adj_or_participle(token):
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or not token.has_feature("Number"):
            return False
        if not _passes_adj_agreement_guards(tokens, idx):
            return False
        return not self._head_is_indeclinable(tokens, idx)

    @staticmethod
    def _head_is_indeclinable(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Indeclinable heads (интервью, кафе: pymorphy Fixd) license both
        modifier numbers ("в эксклюзивных интервью" is correct) — a number
        flip against them is a non-error."""
        head = _amod_head_noun(tokens, idx)
        if head is None:
            return False
        head_parse = _get_pymorphy_parse(head)
        return head_parse is not None and "Fixd" in str(head_parse.tag)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply adjective number error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None
        if not _passes_adj_agreement_guards(tokens, idx):
            return None
        if self._head_is_indeclinable(tokens, idx):
            return None

        head = _amod_head_noun(tokens, idx)

        # Reference number: prefer head noun's number (dep tree) if available
        ref_number_ud = token.get_feature("Number")
        if head is not None and head.has_feature("Number"):
            ref_number_ud = head.get_feature("Number")

        target_num = "plur" if ref_number_ud == "Sing" else "sing"
        grammemes = {target_num}

        target_gender = None
        if target_num == "sing":
            # Plural adjectives carry no gender, so the singular must take
            # the head noun's (технических неполадок → технической, not the
            # pymorphy-default masc технического). No gender evidence → skip.
            target_gender = _noun_gender_grammeme(head) if head is not None else None
            if target_gender is None:
                return None
            grammemes.add(target_gender)

        case_grammemes = _preserved_case_grammemes(
            token, head, target_gender=target_gender, target_number=target_num
        )
        if case_grammemes is None:
            return None
        grammemes |= case_grammemes

        new_word = inflect_word(parse, grammemes, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            original_number = token.get_feature("Number", "Sing")
            return ErrorResult(
                error_type="adj_number",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_NUMBER_{original_number}",
            )

        return None


class AdjGenderErrorHandler:
    """Change adjective/participle gender.

    Precision guards (native-annotation pass): pronominal adjectives (Apro),
    participle parses (PRTF/PRTS) and non-amod tokens are skipped — see
    ``_passes_adj_agreement_guards``. The original case (with animacy for
    Acc) is pinned through the inflection so a gender flip cannot drift into
    a case error (взрывотехническую → взрывотехнический, not the animate-Acc
    взрывотехнического).
    """

    name = "adj_gender"
    subtypes = ["adj_gender"]
    category = "MORPH"
    changes_length = False
    _confusion_matrices = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective/participle gender error can be applied."""
        token = tokens[idx]
        if not _is_adj_or_participle(token):
            return False
        parse = _get_pymorphy_parse(token)
        # Gender only applies to singular adjectives/participles
        if (
            parse is None
            or not token.has_feature("Gender")
            or token.get_feature("Number") != "Sing"
        ):
            return False
        return _passes_adj_agreement_guards(tokens, idx)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply adjective gender error."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None
        if not _passes_adj_agreement_guards(tokens, idx):
            return None

        head = _amod_head_noun(tokens, idx)

        # Reference gender: prefer head noun's gender (dep tree) if available
        ref_gender_ud = token.get_feature("Gender")
        if head is not None and head.has_feature("Gender"):
            ref_gender_ud = head.get_feature("Gender")

        current_gender = UD_TO_PYMORPHY_GENDER.get(token.get_feature("Gender"))

        # Use confusion matrix for weighted target selection
        target_gender = None
        if self._confusion_matrices and "gender" in self._confusion_matrices:
            target_ud = sample_confused_grammeme(
                ref_gender_ud, self._confusion_matrices["gender"], rng
            )
            if target_ud:
                candidate = UD_TO_PYMORPHY_GENDER.get(target_ud)
                if candidate != current_gender:
                    target_gender = candidate

        # Fallback: random gender
        if target_gender is None:
            other_genders = [g for g in GENDERS if g != current_gender]
            target_gender = rng.choice(other_genders)

        grammemes = {target_gender}
        case_grammemes = _preserved_case_grammemes(
            token, head, target_gender=target_gender, target_number=None
        )
        if case_grammemes is None:
            return None
        grammemes |= case_grammemes

        new_word = inflect_word(parse, grammemes, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            original_gender = token.get_feature("Gender", "Masc")
            return ErrorResult(
                error_type="adj_gender",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_GENDER_{original_gender}",
            )

        return None


_SUBJECT_NSUBJ_DEPRELS = {"nsubj", "nsubj:pass"}

# Subject lemmas with which Rozental §183–184 explicitly permit both singular
# and plural predicates (большинство студентов пришло/пришли, ряд делегатов
# участвовал/участвовали) — flipping the predicate's number there is a
# non-error, so such subjects are skipped entirely.
_COLLECTIVE_QUANTIFIER_LEMMAS = {
    "большинство",
    "меньшинство",
    "множество",
    "масса",
    "ряд",
    "часть",
    "половина",
    "много",
    "немало",
    "мало",
    "несколько",
    "сколько",
    "столько",
    "тысяча",
    "миллион",
    "миллиард",
}


def _find_overt_subject(
    tokens: Sequence[AnalyzedToken], verb_idx: int
) -> tuple[int, AnalyzedToken] | None:
    """Find the verb's overt subject (nsubj / nsubj:pass) with its position."""
    for i, token in enumerate(tokens):
        if token.head_idx == verb_idx and token.dep_rel in _SUBJECT_NSUBJ_DEPRELS:
            return i, token
    return None


class VerbPersonNumberErrorHandler:
    """Change verb person or number.

    Requires an overt subject: Russian pro-drop makes subjectless flips
    grammatical ("Иду сюда" / "Идите сюда" are correct sentences), so only a
    visible nsubj controller turns the flip into a recoverable error.
    """

    name = "verb_person_number"
    subtypes = ["verb_person_number"]
    category = "MORPH"
    changes_length = False
    _confusion_matrices = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if verb person/number error can be applied."""
        token = tokens[idx]
        if token.pos not in {"VERB", "AUX"}:
            return False
        parse = _get_pymorphy_parse(token)
        # Must have either person or number feature
        if parse is None or not (
            token.has_feature("Person") or token.has_feature("Number")
        ):
            return False
        subject = _find_overt_subject(tokens, idx)
        if subject is None:
            return False
        # §183–184: collective/quantified subjects license both numbers.
        return not self._is_variant_subject(tokens, *subject)

    @staticmethod
    def _is_variant_subject(
        tokens: Sequence[AnalyzedToken], subj_idx: int, subject: AnalyzedToken
    ) -> bool:
        """True for subjects where Sing/Plur predicates are both normative.

        Covers collective/quantifier lemmas (большинство, ряд, часть, ...) and
        counting phrases — a numeral nsubj or an nsubj carrying a nummod
        dependent ("пять студентов пришло/пришли", §184).
        """
        if (subject.lemma or "").lower() in _COLLECTIVE_QUANTIFIER_LEMMAS:
            return True
        if subject.pos == "NUM":
            return True
        for t in tokens:
            if t.head_idx == subj_idx and (t.dep_rel or "").startswith("nummod"):
                return True
        return False

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply verb person/number error."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        # Overt subject is required (pro-drop guard, see can_apply).
        found = _find_overt_subject(tokens, idx)
        if found is None or self._is_variant_subject(tokens, *found):
            return None
        subject = found[1]

        new_word = None
        transform_type = None
        original_value = None

        has_number = token.has_feature("Number")
        has_person = token.has_feature("Person")

        # Choose what to change based on available features
        if has_person and has_number:
            # Both available - randomly choose
            if rng.random() < 0.5:
                # Reference number: prefer subject's number if available
                ref_number = token.get_feature("Number")
                if subject and subject.has_feature("Number"):
                    ref_number = subject.get_feature("Number")
                target_num = "plur" if ref_number == "Sing" else "sing"
                new_word = inflect_word(parse, {target_num}, word)
                transform_type = "NUMBER"
                original_value = token.get_feature("Number", "Sing")
            else:
                current_person = UD_TO_PYMORPHY_PERSON.get(token.get_feature("Person"))
                other_persons = [p for p in PERSONS if p != current_person]
                target_person = rng.choice(other_persons)
                new_word = inflect_word(parse, {target_person}, word)
                transform_type = "PERSON"
                original_value = token.get_feature("Person", "3")
        elif has_number:
            # Only number (past tense verbs) - always change number
            ref_number = token.get_feature("Number")
            if subject and subject.has_feature("Number"):
                ref_number = subject.get_feature("Number")
            target_num = "plur" if ref_number == "Sing" else "sing"
            new_word = inflect_word(parse, {target_num}, word)
            transform_type = "NUMBER"
            original_value = token.get_feature("Number", "Sing")
        elif has_person:
            # Only person - change person
            current_person = UD_TO_PYMORPHY_PERSON.get(token.get_feature("Person"))
            other_persons = [p for p in PERSONS if p != current_person]
            target_person = rng.choice(other_persons)
            new_word = inflect_word(parse, {target_person}, word)
            transform_type = "PERSON"
            original_value = token.get_feature("Person", "3")

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            return ErrorResult(
                error_type="verb_person_number",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_{transform_type}_{original_value}",
            )

        return None


# Deictic temporal adverbs and the verb tenses they license. A tense flip is
# a recoverable error only when the target tense falls outside the licensed
# set of an anchor modifying the verb. pres stays licensed everywhere it can
# read as correct: praesens historicum after past anchors ("Вчера иду я по
# улице...") and scheduled present after future anchors ("Завтра она читает
# доклад"). Anchors compatible with all tenses (сегодня, сейчас, теперь,
# скоро, вскоре) are deliberately absent — flips against them are non-errors.
_TEMPORAL_ANCHORS: dict[str, frozenset[str]] = {
    "вчера": frozenset({"past", "pres"}),
    "позавчера": frozenset({"past", "pres"}),
    "недавно": frozenset({"past", "pres"}),
    "завтра": frozenset({"futr", "pres"}),
    "послезавтра": frozenset({"futr", "pres"}),
}

# When the verb is a copula/auxiliary the anchor hangs off the predicate head
# instead ("Вчера он был дома": вчера → дома, был = cop).
_COPULA_DEPRELS = {"cop", "aux", "aux:pass"}


class VerbTenseErrorHandler:
    """Change verb tense.

    Tense is contextually licensed: an isolated flip yields a grammatical
    sentence with a different meaning (non-error). Only fires when a deictic
    temporal anchor (вчера, завтра, ...) modifies the verb, and only flips to
    tenses the anchor does not license, so the anchor stays as evidence.
    """

    name = "verb_tense"
    subtypes = ["verb_tense"]
    category = "MORPH"
    changes_length = False

    TENSES = ["past", "pres", "futr"]

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if verb tense error can be applied."""
        token = tokens[idx]
        if token.pos not in {"VERB", "AUX"}:
            return False
        if not self._is_finite(token):
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or not token.has_feature("Tense"):
            return False
        return self._licensed_tenses(tokens, idx) is not None

    @staticmethod
    def _is_finite(token: AnalyzedToken) -> bool:
        """Finite forms only: participles/converbs carry Tense too (stanza
        tags them VERB), but flipping them into finite forms destroys voice
        (сообщено → сообщит, уволившийся → уволится)."""
        verb_form = token.get_feature("VerbForm")
        return verb_form is None or verb_form == "Fin"

    @staticmethod
    def _licensed_tenses(
        tokens: Sequence[AnalyzedToken], idx: int
    ) -> frozenset[str] | None:
        """Union of tenses licensed by temporal anchors on this verb.

        Returns None when the verb has no anchor — in that context any tense
        is correct and a flip would poison training data.
        """
        token = tokens[idx]
        anchor_heads = {idx}
        if token.dep_rel in _COPULA_DEPRELS and token.head_idx is not None:
            anchor_heads.add(token.head_idx)
        licensed: set[str] = set()
        found = False
        for i, t in enumerate(tokens):
            if i == idx or t.head_idx not in anchor_heads:
                continue
            allowed = _TEMPORAL_ANCHORS.get(t.text.lower())
            if allowed:
                licensed |= allowed
                found = True
        return frozenset(licensed) if found else None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        """Apply verb tense error."""
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None or not self._is_finite(token):
            return None

        current_tense = UD_TO_PYMORPHY_TENSE.get(token.get_feature("Tense"))
        if current_tense is None:
            return None

        licensed = self._licensed_tenses(tokens, idx)
        if licensed is None:
            return None

        # Subject (nsubj) supplies the agreement features the verb itself lacks:
        # past forms carry no Person, pres/futr forms carry no Gender.
        subject = _find_dependent(tokens, idx, "nsubj")

        # Only flip to tenses the anchor rules out — the anchor is the evidence
        # that makes the corruption an error rather than a meaning change.
        other_tenses = [
            t for t in self.TENSES if t != current_tense and t not in licensed
        ]
        if not other_tenses:
            return None
        rng.shuffle(other_tenses)

        # Try each candidate tense, carrying the original agreement features, and
        # take the first that inflects to a genuinely different real form. A
        # constrained .inflect() returning None means that tense is unreachable
        # (e.g. perfective verb → present) — skip it rather than emit a
        # person/gender-mismatched form from an unconstrained call.
        for target_tense in other_tenses:
            grammemes = self._target_grammemes(target_tense, token, subject)
            new_word = inflect_word(parse, grammemes, word)
            if new_word and new_word != word:
                sentence[idx] = new_word
                modified.add(idx)

                original_tense = token.get_feature("Tense", "Pres")
                return ErrorResult(
                    error_type="verb_tense",
                    category=self.category,
                    start_idx=idx,
                    end_idx=idx + 1,
                    original=word,
                    corrupted=new_word,
                    fix_tag=f"$TRANSFORM_TENSE_{original_tense}",
                )

        return None

    @staticmethod
    def _target_grammemes(
        target_tense: str,
        token: AnalyzedToken,
        subject: AnalyzedToken | None,
    ) -> set[str]:
        """Build the constrained grammeme set for a tense change.

        Carries Number always, plus Person (pres/futr targets) or Gender
        (past targets), preferring the verb's own features and falling back to
        the subject's. Without these constraints pymorphy defaults to 1st
        person / masculine, producing agreement errors instead of tense errors.
        """
        grammemes = {target_tense}

        number = token.get_feature("Number")
        if number is None and subject is not None:
            number = subject.get_feature("Number")
        py_number = UD_TO_PYMORPHY_NUMBER.get(number) if number else None
        if py_number:
            grammemes.add(py_number)

        if target_tense == "past":
            # Gender only matters in the singular; plural past has no gender.
            if py_number != "plur":
                gender = token.get_feature("Gender")
                if gender is None and subject is not None:
                    gender = subject.get_feature("Gender")
                py_gender = UD_TO_PYMORPHY_GENDER.get(gender) if gender else None
                if py_gender:
                    grammemes.add(py_gender)
        else:
            person = token.get_feature("Person")
            if person is None and subject is not None:
                person = subject.get_feature("Person")
            py_person = UD_TO_PYMORPHY_PERSON.get(person) if person else "3per"
            grammemes.add(py_person)

        return grammemes


# =============================================================================
# Second-locative → standard-locative error (в лесу → в лесе)
# =============================================================================

# Prepositions that govern the second locative (-у) form.
_PREP_E_U_TRIGGERS = {"в", "во", "на"}

# Nouns where the standard -е locative is an acceptable literary variant, so
# corrupting -у → -е does not reliably produce an error. Skip these.
# (pymorphy marks loc2 for many nouns whose -е form is normative: в мозге,
# в аэропорте, в ряде случаев, во льде, в мёде, в соке, в стоге сена...)
_PREP_E_U_STOPLIST = {
    "цех",
    "чай",
    "отпуск",
    "ветер",
    "дом",
    "снег",
    "пар",
    "жир",
    "холод",
    "дым",
    "круг",
    "строй",
    "клей",
    "спирт",
    "год",
    "мозг",
    "аэропорт",
    "гроб",
    "стог",
    "тыл",
    "лёд",
    "лед",
    "мёд",
    "мед",
    "сок",
    "ряд",
}


class NounCasePrepErrorHandler:
    """Replace the second locative (-у) with the standard locative (-е).

    Nouns like лес/берег/снег take a special second-locative ("местный")
    ending -у after в/на (в лесу, на берегу). Substituting the standard -е
    locative (в лесе, на берегу→берегe) is a real error for these nouns.
    """

    name = "noun_case_prep"
    subtypes = ["noun_case_prep_e_u"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        # Homograph guard: require stanza-confirmed locative case (берегу is
        # also a Dat noun form and a present-tense form of беречь).
        if token.get_feature("Case") != "Loc":
            return False
        if token.lemma.lower() in _PREP_E_U_STOPLIST:
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or "loc2" not in str(parse.tag):
            return False
        # Require an immediately preceding в/во/на.
        prev = _get_token_safe(tokens, idx - 1)
        return prev is not None and prev.text.lower() in _PREP_E_U_TRIGGERS

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

        new_word = inflect_word(parse, {"loct"}, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="noun_case_prep_e_u",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Short ↔ full adjective error (мы готовы → мы готовые)
# =============================================================================

# Government adjectives whose short form is predicative and takes an oblique /
# PP complement. The full (nominative) form cannot govern that complement, so
# short → full is reliably wrong. рад is excluded: it has no full form.
_ADJ_GOVERNMENT_LEMMAS = {
    "способный",
    "готовый",
    "склонный",
    "согласный",
    "намеренный",
    "должный",
    "виноватый",
    "похожий",
}

# dep_rels marking a predicate (root or copular predicate complement).
_PREDICATE_DEPRELS = {"root", "parataxis"}

# dep_rels of a complement the short adjective governs.
_ADJ_COMPLEMENT_DEPRELS = {"obl", "iobj", "nmod", "obj"}


class AdjFormErrorHandler:
    """Inflect a predicative short adjective to its full form.

    Short adjectives (готов, способен) act as predicates and can govern an
    oblique/PP complement; the full nominative form (готовый, способный)
    cannot, so the substitution is a genuine error.
    """

    name = "adj_form"
    subtypes = ["adj_short_full"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if not self._is_short_adj(token):
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or "ADJS" not in str(parse.tag):
            return False
        # §159: the full nominative form "такой способностью не обладает"
        # (cannot govern) only when a complement is actually present. Without
        # one, full vs short predicate is a stylistic choice ("Он очень
        # способный" is correct), so a governed complement is always required.
        if not self._has_complement(tokens, idx):
            return False
        # Predicate position → reliably wrong; otherwise fall back to the
        # closed set of government adjectives (widens dep_rel only).
        if token.dep_rel in _PREDICATE_DEPRELS:
            return True
        return token.lemma.lower() in _ADJ_GOVERNMENT_LEMMAS

    @staticmethod
    def _is_short_adj(token: AnalyzedToken) -> bool:
        if token.pos == "ADJ" and token.get_feature("Variant") == "Short":
            return True
        parse = _get_pymorphy_parse(token)
        return parse is not None and "ADJS" in str(parse.tag)

    @staticmethod
    def _has_complement(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        for t in tokens:
            if t.head_idx != idx:
                continue
            if t.dep_rel in _ADJ_COMPLEMENT_DEPRELS:
                return True
            # Infinitive complements ("должен уйти", "готов помочь") are
            # governed too: the full form cannot take them either.
            if t.dep_rel == "xcomp" and t.get_feature("VerbForm") == "Inf":
                return True
        return False

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

        new_word = inflect_word(parse, {"ADJF", "nomn"}, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="adj_short_full",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Pleonastic double comparative (интереснее → более интереснее)
# =============================================================================

# Comparative markers that already precede a comparative — inserting another
# «более» would just duplicate an existing (correct) construction.
_DOUBLE_COMP_BLOCKERS = {"более", "менее", "самый", "наиболее", "наименее"}


class DoubleComparativeHandler:
    """Insert a pleonastic «более» before a synthetic comparative.

    Russian forms the comparative either synthetically (интереснее) or
    analytically (более интересный). Combining them (более интереснее) is a
    classic pleonasm. Adds one token, so ``changes_length=True``.
    """

    name = "adj_double_comparative"
    subtypes = ["adj_double_comparative"]
    category = "MORPH"
    changes_length = True

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        parse = _get_pymorphy_parse(token)
        if parse is None or "COMP" not in str(parse.tag):
            return False
        prev = _get_token_safe(tokens, idx - 1)
        if prev is not None and prev.text.lower() in _DOUBLE_COMP_BLOCKERS:
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
        word = sentence[idx]
        if word[:1].isupper():
            # Sentence-initial/capitalized comparative: inserting «более»
            # would either read unnaturally (более Раньше) or require a
            # second capitalization edit beyond the single $DELETE fix — skip
            return None
        sentence.insert(idx, "более")
        modified.add(idx)
        return ErrorResult(
            error_type="adj_double_comparative",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=f"более {word}",
            fix_tag="$DELETE",
        )


# =============================================================================
# Numeral declension errors
# =============================================================================

# полтора (masc/neut), полторы (fem) → use "полтора" in oblique cases (should be "полутора")
# полтораста → "полутораста" in oblique cases
# Genitive/Dative/Instrumental/Prepositional all use "полутора"/"полутораста".
# LoRuGEC rules: "Склонение числительных полтора, полторы, полтораста"
#                "Склонение количественных числительных"

# Surface form → wrong substitutions. Keyed by form (not lemma) because the
# oblique "полутора" is shared by the masc/neut (полтора) and fem (полторы)
# paradigms — a lemma-keyed lookup silently overwrote one direction. For
# "полутора" the citation-form replacement is gender-ambiguous and resolved
# against the governed noun's gender at apply time (§164).
_POLTORA_SUBSTITUTIONS: dict[str, list[str]] = {
    "полтора": ["полутора"],  # Nom/Acc → oblique form (rare error direction)
    "полторы": ["полутора"],  # Nom/Acc fem → oblique
    "полутора": ["полтора", "полторы"],  # Oblique → Nom/Acc (common L2 error)
    "полтораста": ["полутораста"],  # Nom/Acc → oblique
    "полутораста": ["полтораста"],  # Oblique → Nom/Acc
}


# Oblique UD cases for which a general cardinal must inflect both elements.
# Failing to decline → leaving the numeral in its Nom/Acc citation form.
_OBLIQUE_CASES = {"Gen", "Dat", "Ins", "Loc"}


class NumeralDeclensionHandler:
    """Corrupt numeral declension.

    Two error families:

    - полтора/полторы/полтораста: two-form declension (Nom/Acc vs oblique).
      Common L2 error: using the Nom/Acc form in oblique position or vice
      versa. Rozental §164. Subtype ``numeral_poltora``.
    - general cardinals (пятьдесят, двести, триста, пятьсот, …): all parts
      decline. The canonical L2 error is failing to decline — leaving the
      numeral in its citation (Nom/Acc) form in an oblique slot
      ("о пятьдесят книгах" for "о пятидесяти книгах"). We reproduce it by
      inflecting an oblique cardinal back to nominative. Subtype
      ``numeral_declension``. Rozental §164.
    """

    name = "numeral_declension"
    subtypes = ["numeral_poltora", "numeral_declension"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if tokens[idx].text.lower() in _POLTORA_SUBSTITUTIONS:
            return True
        return self._general_cardinal_target(tokens, idx) is not None

    def _general_cardinal_target(
        self, tokens: Sequence[AnalyzedToken], idx: int
    ) -> str | None:
        """If token is an oblique general cardinal, return its Nom/Acc form.

        Returns None when the token is not a declinable cardinal, is not in an
        oblique case, or already equals its nominative form (indeclinable
        numerals like сорок/девяносто/сто share their oblique/nominative
        surface forms and so produce no error).
        """
        token = tokens[idx]
        if token.get_feature("Case") not in _OBLIQUE_CASES:
            return None
        # §164: distributive по + Dat (по пяти раз) has an accusative variant
        # identical to the citation form (по пять раз) that Rozental calls
        # predominant — nominativizing such a dative yields a permitted
        # variant, not an error.
        if token.get_feature("Case") == "Dat" and self._governed_by_po(tokens, idx):
            return None
        parse = _get_pymorphy_parse(token)
        if parse is None or getattr(parse.tag, "POS", None) != "NUMR":
            return None
        nom = inflect_word(parse, {"nomn"}, token.text)
        if nom and nom != token.text:
            return nom
        return None

    @staticmethod
    def _governed_by_po(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """True when the numeral's dative is governed by distributive по."""
        prev = _get_token_safe(tokens, idx - 1)
        if prev is not None and prev.text.lower() == "по":
            return True
        # по may attach as a case dependent of the numeral or its head noun.
        heads = {idx}
        if tokens[idx].head_idx is not None:
            heads.add(tokens[idx].head_idx)
        for t in tokens:
            if (
                t.head_idx in heads
                and (t.dep_rel or "") == "case"
                and t.text.lower() == "по"
            ):
                return True
        return False

    @staticmethod
    def _polutora_citation_form(
        tokens: Sequence[AnalyzedToken], idx: int, rng: Random
    ) -> str:
        """Pick полтора/полторы for ambiguous «полутора» by the noun's gender.

        The governed noun is the numeral's dep head (nummod) or, failing that,
        the nearest following noun; Fem → полторы, Masc/Neut → полтора. With
        no gender evidence (e.g. pluralia tantum суток) either citation form
        is a genuine error — pick randomly.
        """
        token = tokens[idx]
        noun = None
        if token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if head is not None and head.pos in {"NOUN", "PROPN"}:
                noun = head
        if noun is None:
            for t in tokens[idx + 1 :]:
                if t.pos in {"NOUN", "PROPN"}:
                    noun = t
                    break
        gender = noun.get_feature("Gender") if noun is not None else None
        if gender == "Fem":
            return "полторы"
        if gender in {"Masc", "Neut"}:
            return "полтора"
        return rng.choice(["полтора", "полторы"])

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        word = sentence[idx]
        text_lower = word.lower()

        if text_lower in _POLTORA_SUBSTITUTIONS:
            if text_lower == "полутора":
                new_lower = self._polutora_citation_form(tokens, idx, rng)
            else:
                new_lower = rng.choice(_POLTORA_SUBSTITUTIONS[text_lower])
            new_word = (
                new_lower[0].upper() + new_lower[1:] if word[0].isupper() else new_lower
            )

            # §164 groups полтораста with полтора/полторы (two-form declension),
            # so the whole family carries the numeral_poltora subtype.
            subtype = "numeral_poltora"
        else:
            new_word = self._general_cardinal_target(tokens, idx)
            if new_word is None:
                return None
            subtype = "numeral_declension"

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type=f"numeral_declension_{subtype}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Genitive partitive -у/-ю error (история народа -> история народу, §150)
# =============================================================================

# Heads that license a genuine partitive/quantitative genitive: quantity
# nouns/adverbs and verbs that take a partitive object. Corrupting the
# standard -а/-я genitive to -у/-ю under one of these heads would land on an
# accepted (if colloquial) variant rather than an error, so such contexts are
# skipped — only the residual, non-partitive government contexts fire
# ("история народа" -> "история народу").
_PARTITIVE_QUANTITY_HEADS = {
    "стакан",
    "чашка",
    "кружка",
    "ложка",
    "кусок",
    "ломоть",
    "литр",
    "килограмм",
    "грамм",
    "банка",
    "бутылка",
    "пачка",
    "горсть",
    "щепотка",
    "капля",
    "глоток",
    "немного",
    "много",
    "мало",
    "немало",
    "чуть",
    "чуточка",
    "сколько",
    "столько",
}
_PARTITIVE_VERB_HEADS = {
    "выпить",
    "налить",
    "добавить",
    "насыпать",
    "подсыпать",
    "долить",
    "плеснуть",
    "хлебнуть",
    "глотнуть",
    "отведать",
    "попробовать",
}
_PARTITIVE_CONTEXT_LEMMAS = _PARTITIVE_QUANTITY_HEADS | _PARTITIVE_VERB_HEADS


class NounCaseGenPartitiveHandler:
    """Corrupt the standard genitive -а/-я into the colloquial partitive -у/-ю.

    A closed set of masculine mass nouns (чай, сахар, народ, ...) accepts a
    colloquial partitive genitive in -у/-ю (Rozental §150) alongside the
    standard -а/-я form. That variant is only licensed in a genuine partitive
    context (a quantity head or a partitive-taking verb); everywhere else the
    -у/-ю form reads as a case error.
    """

    name = "noun_case_gen_partitive"
    subtypes = ["noun_case_gen_partitive"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        if token.get_feature("Case") != "Gen" or token.get_feature("Number") != "Sing":
            return False
        if token.lemma.lower() not in _gen_partitive_lexicon():
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return False
        return not self._is_partitive_context(tokens, idx)

    @staticmethod
    def _is_partitive_context(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """True when a quantity/partitive-verb head licenses the -у/-ю form."""
        token = tokens[idx]
        if token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if head is None:
                return False
            head_lemma = (head.lemma or head.text or "").lower()
            return head_lemma in _PARTITIVE_CONTEXT_LEMMAS
        # No dep info: fall back to scanning the 1-2 preceding tokens (covers
        # both an adjacent quantity noun and a verb separated by a dative
        # reflexive, e.g. "налил себе чая").
        for back in (1, 2):
            prev = _get_token_safe(tokens, idx - back)
            if prev is None:
                break
            prev_lemma = (prev.lemma or prev.text or "").lower()
            if prev_lemma in _PARTITIVE_CONTEXT_LEMMAS:
                return True
        return False

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
        if self._is_partitive_context(tokens, idx):
            return None

        new_word = inflect_word(parse, {"gen2"}, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="noun_case_gen_partitive",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Instrumental plural -ями/-(ь)ми variant (дверями <-> дверьми, §155)
# =============================================================================


class NounCaseInstrPlHandler:
    """Corrupt the instrumental-plural -ями/-(ь)ми variant (Rozental §155).

    A small set of third-declension nouns (дверь, лошадь, дочь, плеть, кость)
    alternate between a neutral -ями instrumental plural and a stylistically
    marked -(ь)ми form. Substituting the marked form in neutral prose reads as
    an error (дверями -> дверьми); for кость the polarity flips inside the
    fixed idiom "лечь костьми", where -ьми is itself the norm and -ями is the
    error — encoded per-lexeme via the ``idiom_reversed``/``idiom_triggers``
    fields in the data file.
    """

    name = "noun_case_instr_pl"
    subtypes = ["noun_case_instr_pl"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        if token.get_feature("Case") != "Ins" or token.get_feature("Number") != "Plur":
            return False
        entry = _instr_pl_lexicon().get(token.lemma.lower())
        if entry is None:
            return False
        return self._target_form(tokens, idx, entry) is not None

    @staticmethod
    def _target_form(
        tokens: Sequence[AnalyzedToken], idx: int, entry: dict
    ) -> str | None:
        """Corrupted surface form for this token, or None if the token's
        surface text does not match either known variant."""
        word_lower = tokens[idx].text.lower()
        norm, marked = entry["norm"], entry["marked"]
        if entry.get("idiom_reversed"):
            prev = _get_token_safe(tokens, idx - 1)
            prev_lemma = (prev.lemma or prev.text or "").lower() if prev else ""
            in_idiom = prev_lemma in entry.get("idiom_triggers", [])
            if word_lower == marked and in_idiom:
                return norm
            if word_lower == norm and not in_idiom:
                return marked
            return None
        if word_lower == norm:
            return marked
        return None

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
        entry = _instr_pl_lexicon().get(token.lemma.lower())
        if entry is None:
            return None
        target = self._target_form(tokens, idx, entry)
        if target is None:
            return None

        new_word = match_capitalization(word, target)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="noun_case_instr_pl",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Genitive-plural nonstandard variant (пять апельсинов -> пять апельсин, §154)
# =============================================================================


class NounNumberGenPlHandler:
    """Corrupt a genitive-plural noun to its frequent nonstandard variant.

    Rozental §154 catalogs a closed confusion set of two competing patterns:
    nouns that take -ов/-ев in the genitive plural but are frequently
    zero-ended by analogy (апельсинов -> апельсин), and nouns that take a
    zero ending but are frequently hypercorrected with -ов (мест -> местов,
    чулок -> чулков) — the classic "пять носков, но пять чулок" confusion.
    """

    name = "noun_number_gen_pl"
    subtypes = ["noun_number_gen_pl"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        if token.get_feature("Case") != "Gen" or token.get_feature("Number") != "Plur":
            return False
        entry = _gen_pl_nonstandard_lexicon().get(token.lemma.lower())
        if entry is None:
            return False
        return token.text.lower() == entry["norm"]

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
        entry = _gen_pl_nonstandard_lexicon().get(token.lemma.lower())
        if entry is None or word.lower() != entry["norm"]:
            return None

        new_word = match_capitalization(word, entry["error"])
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="noun_number_gen_pl",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Genitive vs accusative under negation (не читал книги / не читал книгу, §201)
# =============================================================================

_NEG_PARTICLE_TEXT = "не"


def _has_neg_particle(tokens: Sequence[AnalyzedToken], head_idx: int) -> bool:
    """True when the verb at head_idx has an overt «не» (PART, advmod) child."""
    for t in tokens:
        if (
            t.head_idx == head_idx
            and t.pos == "PART"
            and (t.dep_rel or "") == "advmod"
            and t.text.lower() == _NEG_PARTICLE_TEXT
        ):
            return True
    return False


def _neg_genitive_needs_animacy(token: AnalyzedToken) -> bool:
    """Acc is animacy-ambiguous for masc singular and any plural target."""
    number = token.get_feature("Number")
    if number == "Plur":
        return True
    return number == "Sing" and token.get_feature("Gender") == "Masc"


class NegGenitiveErrorHandler:
    """Flip Acc<->Gen on the direct object of a negated verb (Rozental §201).

    Under negation Russian allows both the genitive ("не читал книги") and
    the accusative ("не читал книгу") for a transitive verb's direct object;
    the choice is governed by aspect/definiteness factors a learner often
    gets backwards. Requires dep info: without an ``obj`` arc whose head verb
    has an overt «не» dependent there is no evidence a case flip is
    recoverable as an error, so both ``can_apply`` and ``apply`` return
    False/None when depparse is unavailable.
    """

    name = "neg_genitive"
    subtypes = ["neg_genitive"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        parse = _get_pymorphy_parse(tokens[idx])
        if parse is None:
            return False
        return self._target_grammemes(tokens, idx) is not None

    @staticmethod
    def _target_grammemes(
        tokens: Sequence[AnalyzedToken], idx: int
    ) -> tuple[str, set[str]] | None:
        """(original_case_ud, target_grammemes) for a qualifying negated
        direct object, or None if this token doesn't qualify."""
        token = tokens[idx]
        if token.pos != "NOUN":
            return None
        if token.dep_rel != "obj" or token.head_idx is None:
            return None
        head = _get_token_safe(tokens, token.head_idx)
        if head is None or head.pos not in {"VERB", "AUX"}:
            return None
        if not _has_neg_particle(tokens, token.head_idx):
            return None

        case = token.get_feature("Case")
        if case == "Acc":
            return "Acc", {"gent"}
        if case == "Gen":
            if _neg_genitive_needs_animacy(token):
                animacy = _animacy_grammeme(token, None)
                if animacy is None:
                    return None
                return "Gen", {"accs", animacy}
            return "Gen", {"accs"}
        return None

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

        found = self._target_grammemes(tokens, idx)
        if found is None:
            return None
        original_case, grammemes = found

        new_word = inflect_word(parse, grammemes, word)
        if not new_word or new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="neg_genitive",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$TRANSFORM_CASE_{original_case}",
        )


@lru_cache(maxsize=1)
def _morph():
    """Lazily build a shared pymorphy3 analyzer (heavy to instantiate).

    Same idiom as errors/semantics.py's ``_morph()``: the token-attached
    ``pymorphy_parse`` extra only covers the word actually in the sentence,
    but the three handlers below need to re-parse a *candidate* corrupted
    surface (not yet in any token) to confirm pymorphy still recognizes it.
    """
    import pymorphy3

    return pymorphy3.MorphAnalyzer()


# =============================================================================
# Iterative-suffix о/а variant (обусловливать <-> обуславливать, §172.2)
# =============================================================================

# Lexeme-inherent flags stripped before comparing two parses' grammeme
# profiles: aspect/transitivity are guaranteed identical within a norm/marked
# pair by construction (both curated as the same-aspect iterative verb), but
# a heuristic (non-dictionary) parse of an out-of-vocabulary marked form can
# still guess the wrong transitivity/adjectivization flag even when the verb
# form itself is a legitimate, well-formed word — comparing on those flags
# would produce false negatives, not false positives, so stripping them only
# trades recall for precision in this handler's favor.
_VERB_TAG_IGNORED_GRAMMEMES = {"tran", "intr", "perf", "impf", "Adjx"}


def _verb_grammeme_profile(tag) -> frozenset[str]:
    """Grammemes relevant to surface-form validity (POS plus case/number/
    gender/person/tense/mood/voice), stripping the lexeme-inherent flags in
    ``_VERB_TAG_IGNORED_GRAMMEMES``."""
    return frozenset(g for g in tag.grammemes if g not in _VERB_TAG_IGNORED_GRAMMEMES)


@lru_cache(maxsize=1)
def _verb_iterative_lexicon() -> dict[str, dict]:
    """Norm lemma -> {"marked_lemma", "swap_index", "norm_char",
    "target_char"} for the closed о/а iterative-suffix variant set
    (Rozental §172.2).

    The swap index/chars are derived from the single-character diff between
    the norm and marked infinitives in the data file; that offset is a fixed
    distance from the start of the word (inside the root, before the
    invariant -ива-/-ыва- suffix that is present across the verb's whole
    paradigm), so the same offset applies unchanged to every inflected
    surface form of the lexeme. Entries whose norm/marked pair doesn't
    reduce to exactly one о<->а diff are dropped defensively.
    """
    raw = _load_json_resource("verb_iterative_variants.json").get("lexemes", {})
    lexicon: dict[str, dict] = {}
    for norm_lemma, entry in raw.items():
        marked_lemma = entry.get("marked")
        if not marked_lemma or len(marked_lemma) != len(norm_lemma):
            continue
        diffs = [
            i
            for i, (a, b) in enumerate(zip(norm_lemma, marked_lemma, strict=True))
            if a != b
        ]
        if len(diffs) != 1:
            continue
        pos = diffs[0]
        norm_char, marked_char = norm_lemma[pos], marked_lemma[pos]
        if {norm_char, marked_char} != {"о", "а"}:
            continue
        lexicon[norm_lemma] = {
            "marked_lemma": marked_lemma,
            "swap_index": pos,
            "norm_char": norm_char,
            "target_char": marked_char,
        }
    return lexicon


class VerbIterativeSuffixHandler:
    """Corrupt the о/а alternation in iterative-suffix imperfective verbs
    (Rozental §172.2).

    A closed set of -ивать/-ывать imperfectives has a contested root vowel.
    Some (обусловливать, узаконивать, приурочивать, ...) resist the
    otherwise-productive о->а alternation, so keeping 'o' is the
    prescriptive norm and the colloquial overgeneralization to 'a'
    (обуславливать) is the marked variant. Others (затрагивать, опаздывать,
    ...) undergo the alternation as the prescriptive norm, so *failing* to
    alternate (затрогивать, опоздывать) is itself the marked, hypercorrected
    form. Both directions are folded into one lexicon keyed by the standard
    lemma (see ``verb_iterative_variants.json``'s ``family`` field), with the
    corruption always going norm -> marked.

    The alternating vowel sits at a fixed character offset from the start of
    the word, so the same offset applies unchanged across the verb's entire
    paradigm; each candidate corruption is validated per-token by checking
    that pymorphy recognizes the corrupted surface with the same verb
    grammeme profile as the original token (case/number/person/tense/voice),
    which catches transposition mistakes even for lexemes pymorphy's
    dictionary does not itself register under the marked lemma.
    """

    name = "verb_iterative_suffix"
    subtypes = ["verb_iterative_suffix"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "VERB":
            return False
        entry = _verb_iterative_lexicon().get(token.lemma.lower())
        if entry is None:
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return False
        return self._target_form(token.text, entry, parse) is not None

    @staticmethod
    def _target_form(word: str, entry: dict, parse) -> str | None:
        """Corrupted surface for ``word`` under ``entry``, or None if the
        swap position doesn't hold or pymorphy rejects the result."""
        swap_idx = entry["swap_index"]
        if swap_idx >= len(word):
            return None
        current = word[swap_idx]
        if current.lower() != entry["norm_char"]:
            return None

        target_char = (
            entry["target_char"].upper() if current.isupper() else entry["target_char"]
        )
        new_word = word[:swap_idx] + target_char + word[swap_idx + 1 :]
        if new_word == word:
            return None

        wanted_profile = _verb_grammeme_profile(parse.tag)
        for candidate in _morph().parse(new_word):
            if _verb_grammeme_profile(candidate.tag) == wanted_profile:
                return new_word
        return None

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
        entry = _verb_iterative_lexicon().get(token.lemma.lower())
        if entry is None:
            return None
        parse = _get_pymorphy_parse(token)
        if parse is None:
            return None

        new_word = self._target_form(word, entry, parse)
        if new_word is None:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="verb_iterative_suffix",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Possessive-adjective oblique declension variant (маминого <-> мамина, §162)
# =============================================================================

# UD cases where -ин possessives have a competing full/short oblique ending.
_POSS_OBLIQUE_UD_CASES = {"Gen", "Dat"}


def _poss_lexeme_variant(
    parse, pm_case: str, pm_gender: str, pm_number: str
) -> tuple[str, str] | None:
    """(norm_word, marked_word) sharing (case, gender, number) in this
    parse's lexeme paradigm, or None if this lexeme/slot has no attested
    pymorphy ``Infr`` (colloquial short-oblique) sibling.

    -ов/-ев possessives (отцов, дедов) never produce a match here: pymorphy's
    dictionary only has the short-oblique form for them (no competing
    ``Infr``-flagged pair), so they are excluded automatically rather than
    needing a hand-curated exclusion list.
    """
    norm_word = None
    marked_word = None
    for form in parse.lexeme:
        ftag = form.tag
        if ftag.case != pm_case or ftag.gender != pm_gender or ftag.number != pm_number:
            continue
        if "Infr" in ftag:
            marked_word = form.word
        elif norm_word is None:
            norm_word = form.word
    if norm_word is None or marked_word is None:
        return None
    return norm_word, marked_word


class AdjPossessiveFormHandler:
    """Corrupt possessive-adjective oblique declension (Rozental §162):
    full pronominal ending -> short colloquial ending (маминого -> мамина,
    маминому -> мамину).

    -ин possessive adjectives (мамин, папин, бабушкин, ...) have two
    competing declension patterns in the masc/neut genitive and dative
    singular: the modern-standard 'full' pronominal ending (-ого, -ому) and
    an older, colloquial 'short' ending (-а, -у). pymorphy3's own dictionary
    paradigm tags the short variant with the ``Infr`` (informal) grammeme, so
    both the trigger and the corruption target are read directly off the
    lexeme's paradigm — no hand-curated lexicon is needed for this handler.
    -ов/-ев possessives (отцов, дедов) are excluded automatically: their
    pymorphy paradigm has no competing ``Infr`` form at all.
    """

    name = "adj_possessive_form"
    subtypes = ["adj_possessive_form"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "ADJ":
            return False
        if token.get_feature("Case") not in _POSS_OBLIQUE_UD_CASES:
            return False
        parse = _get_pymorphy_parse(token)
        if parse is None or "Poss" not in parse.tag:
            return False
        return self._target(token, parse) is not None

    @staticmethod
    def _target(token: AnalyzedToken, parse) -> str | None:
        pm_case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))
        pm_gender = UD_TO_PYMORPHY_GENDER.get(token.get_feature("Gender"))
        pm_number = UD_TO_PYMORPHY_NUMBER.get(token.get_feature("Number")) or "sing"
        if pm_case is None or pm_gender is None:
            return None

        variant = _poss_lexeme_variant(parse, pm_case, pm_gender, pm_number)
        if variant is None:
            return None
        norm_word, marked_word = variant
        if token.text.lower() != norm_word:
            return None
        return marked_word

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

        target = self._target(token, parse)
        if target is None:
            return None

        new_word = match_capitalization(word, target)
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="adj_possessive_form",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Short-form masc -ен/-енен variant (свойствен <-> свойственен, §160)
# =============================================================================

_ADJ_SHORT_MASC_UD = {"Gender": "Masc", "Number": "Sing", "Variant": "Short"}


@lru_cache(maxsize=1)
def _adj_short_en_enen_lexicon() -> dict[str, dict]:
    """Adjective lemma -> {"norm", "marked"} masc-short-form pair for the
    closed -ен/-енен variant set (Rozental §160)."""
    return _load_json_resource("adj_short_en_enen.json").get("lexemes", {})


class AdjShortEnEnenHandler:
    """Corrupt the masc short-form -ен/-енен variant (Rozental §160):
    свойствен -> свойственен.

    A closed set of -ственный/-твенный quality adjectives has two competing
    masculine short-form endings: the modern-standard contracted '-ен'
    (свойствен) and a heavier, marked '-енен' (свойственен). The corruption
    direction is always norm ('-ен') -> marked ('-енен'). pymorphy3 is used
    defensively to confirm the marked target is at least recognizable as an
    ADJS masc-sing form — a dictionary hit for most entries in the data
    file, and suffix-heuristic recognition for the rest (see the data
    file's ``бессмысленный`` note).
    """

    name = "adj_short_en_enen"
    subtypes = ["adj_short_en_enen"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if token.pos != "ADJ":
            return False
        if not all(token.get_feature(k) == v for k, v in _ADJ_SHORT_MASC_UD.items()):
            return False
        entry = _adj_short_en_enen_lexicon().get(token.lemma.lower())
        if entry is None:
            return False
        if token.text.lower() != entry["norm"]:
            return False
        return self._is_valid_marked_form(entry["marked"])

    @staticmethod
    def _is_valid_marked_form(marked: str) -> bool:
        for candidate in _morph().parse(marked):
            tag = candidate.tag
            if tag.POS == "ADJS" and "masc" in tag and "sing" in tag:
                return True
        return False

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
        entry = _adj_short_en_enen_lexicon().get(token.lemma.lower())
        if entry is None or word.lower() != entry["norm"]:
            return None
        if not self._is_valid_marked_form(entry["marked"]):
            return None

        new_word = match_capitalization(word, entry["marked"])
        if new_word == word:
            return None

        sentence[idx] = new_word
        modified.add(idx)
        return ErrorResult(
            error_type="adj_short_en_enen",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
