"""Russian morphological error handlers - case, number, gender, tense errors."""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.inflector import (
    CASES,
    GENDERS,
    PERSONS,
    UD_TO_PYMORPHY_CASE,
    UD_TO_PYMORPHY_GENDER,
    UD_TO_PYMORPHY_PERSON,
    UD_TO_PYMORPHY_TENSE,
    inflect_word,
    sample_confused_grammeme,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


def _find_tokens_by_pos(
    tokens: Sequence[AnalyzedToken],
    pos: str | set[str],
    modified: set[int],
) -> list[int]:
    """Find token indices with given POS tag(s), excluding modified."""
    if isinstance(pos, str):
        pos = {pos}
    return [t.idx for t in tokens if t.pos in pos and t.idx not in modified]


def _is_adj_or_participle(token: AnalyzedToken) -> bool:
    """Check if token is adjective or participle (VerbForm=Part).

    Participles agree with head nouns in case/number/gender just like adjectives.
    Stanza may tag them as ADJ (SynTagRus) or VERB with VerbForm=Part.
    """
    if token.pos == "ADJ":
        return True
    if token.pos == "VERB" and token.get_feature("VerbForm") == "Part":
        return True
    return False


# dep_rels used by participles/adjectives pointing at their head noun
_MODIFIER_DEPRELS = {"amod", "acl", "acl:relcl"}


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


class NounCaseErrorHandler:
    """Change noun case to create morphological error."""

    name = "noun_case"
    subtypes = ["noun_case"]
    category = "MORPH"
    changes_length = False
    _confusion_matrices = None

    def set_confusion_matrix(self, matrices: dict) -> None:
        self._confusion_matrices = matrices

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if noun case error can be applied."""
        token = tokens[idx]
        if token.pos != "NOUN":
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
                error_type="noun_case",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_CASE_{original_case}",
            )

        return None


class NounNumberErrorHandler:
    """Change noun number (singular ↔ plural)."""

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
        return parse is not None and token.has_feature("Number")

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
    """Change adjective/participle number."""

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
        return parse is not None and token.has_feature("Number")

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

        # Reference number: prefer head noun's number (dep tree) if available
        ref_number_ud = token.get_feature("Number")
        if token.dep_rel in _MODIFIER_DEPRELS and token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if head and head.has_feature("Number"):
                ref_number_ud = head.get_feature("Number")

        target_num = "plur" if ref_number_ud == "Sing" else "sing"
        new_word = inflect_word(parse, {target_num}, word)

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
    """Change adjective/participle gender."""

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
        return (
            parse is not None
            and token.has_feature("Gender")
            and token.get_feature("Number") == "Sing"
        )

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

        # Reference gender: prefer head noun's gender (dep tree) if available
        ref_gender_ud = token.get_feature("Gender")
        if token.dep_rel in _MODIFIER_DEPRELS and token.head_idx is not None:
            head = _get_token_safe(tokens, token.head_idx)
            if head and head.has_feature("Gender"):
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

        new_word = inflect_word(parse, {target_gender}, word)

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


class VerbPersonNumberErrorHandler:
    """Change verb person or number."""

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
        return parse is not None and (token.has_feature("Person") or token.has_feature("Number"))

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

        # Find subject via dep tree (nsubj dependent)
        subject = _find_dependent(tokens, idx, "nsubj")

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


class VerbTenseErrorHandler:
    """Change verb tense."""

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
        parse = _get_pymorphy_parse(token)
        return parse is not None and token.has_feature("Tense")

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

        if parse is None:
            return None

        current_tense = UD_TO_PYMORPHY_TENSE.get(token.get_feature("Tense"))
        if current_tense is None:
            return None

        other_tenses = [t for t in self.TENSES if t != current_tense]
        target_tense = rng.choice(other_tenses)

        new_word = inflect_word(parse, {target_tense}, word)

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


# =============================================================================
# Numeral declension errors
# =============================================================================

# полтора (masc/neut), полторы (fem) → use "полтора" in oblique cases (should be "полутора")
# полтораста → "полутораста" in oblique cases
# Genitive/Dative/Instrumental/Prepositional all use "полутора"/"полутораста".
# LoRuGEC rules: "Склонение числительных полтора, полторы, полтораста"
#                "Склонение количественных числительных"

_POLTORA_FORMS: dict[str, dict[str, list[str]]] = {
    # lemma → {correct_case_form: [wrong_substitutions]}
    "полтора": {
        "полтора": ["полутора"],       # Nom/Acc → oblique form (rare error direction)
        "полутора": ["полтора"],       # Oblique → Nom/Acc form (common L2 error)
    },
    "полторы": {
        "полторы": ["полутора"],       # Nom/Acc fem → oblique
        "полутора": ["полторы"],       # Oblique → Nom/Acc fem
    },
    "полтораста": {
        "полтораста": ["полутораста"],  # Nom/Acc → oblique
        "полутораста": ["полтораста"],  # Oblique → Nom/Acc
    },
}

# Map lowercased surface forms to their lemma
_POLTORA_LOOKUP: dict[str, str] = {}
for _lemma, _forms in _POLTORA_FORMS.items():
    for _form in _forms:
        _POLTORA_LOOKUP[_form] = _lemma


class NumeralDeclensionHandler:
    """Corrupt numeral declension — currently полтора/полторы/полтораста.

    These three words have a two-form declension:
    - Nom/Acc: полтора (m/n), полторы (f), полтораста
    - All oblique: полутора, полутора, полутораста

    Common L2 error: using Nom/Acc form in oblique position or vice versa.
    Rozental §164.
    """

    name = "numeral_declension"
    subtypes = ["numeral_poltora", "numeral_declension"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        text_lower = tokens[idx].text.lower()
        return text_lower in _POLTORA_LOOKUP

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

        if text_lower not in _POLTORA_LOOKUP:
            return None

        lemma = _POLTORA_LOOKUP[text_lower]
        substitutions = _POLTORA_FORMS[lemma].get(text_lower)
        if not substitutions:
            return None

        new_lower = rng.choice(substitutions)

        # Preserve capitalization
        if word[0].isupper():
            new_word = new_lower[0].upper() + new_lower[1:]
        else:
            new_word = new_lower

        subtype = "numeral_poltora" if lemma in ("полтора", "полторы") else "numeral_declension"

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
