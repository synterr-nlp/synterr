"""Russian morphological error handlers - case, number, gender, tense errors."""

from __future__ import annotations

import random
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
)

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def _get_pymorphy_parse(token: AnalyzedToken):
    """Get pymorphy parse object from token."""
    return token.extra.get("pymorphy_parse")


class NounCaseErrorHandler:
    """Change noun case to create morphological error."""

    name = "noun_case"
    subtypes = ["noun_case"]
    category = "MORPH"
    changes_length = False

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
    ) -> ErrorResult | None:
        """Apply noun case error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        # Get current case and pick a different one
        current_case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))
        other_cases = [c for c in CASES if c != current_case]
        target_case = random.choice(other_cases)

        new_word = inflect_word(parse, {target_case})

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)

            # Generate transform tag with original case
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
    ) -> ErrorResult | None:
        """Apply noun number error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        # Flip number
        target_num = "plur" if token.get_feature("Number") == "Sing" else "sing"
        new_word = inflect_word(parse, {target_num})

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
    """Change adjective case."""

    name = "adj_case"
    subtypes = ["adj_case"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective case error can be applied."""
        token = tokens[idx]
        if token.pos != "ADJ":
            return False
        parse = _get_pymorphy_parse(token)
        return parse is not None and token.has_feature("Case")

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        """Apply adjective case error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        current_case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))
        other_cases = [c for c in CASES if c != current_case]
        target_case = random.choice(other_cases)

        new_word = inflect_word(parse, {target_case})

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
    """Change adjective number."""

    name = "adj_number"
    subtypes = ["adj_number"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective number error can be applied."""
        token = tokens[idx]
        if token.pos != "ADJ":
            return False
        parse = _get_pymorphy_parse(token)
        return parse is not None and token.has_feature("Number")

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        """Apply adjective number error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        target_num = "plur" if token.get_feature("Number") == "Sing" else "sing"
        new_word = inflect_word(parse, {target_num})

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
    """Change adjective gender."""

    name = "adj_gender"
    subtypes = ["adj_gender"]
    category = "MORPH"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        """Check if adjective gender error can be applied."""
        token = tokens[idx]
        if token.pos != "ADJ":
            return False
        parse = _get_pymorphy_parse(token)
        # Gender only applies to singular adjectives
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
    ) -> ErrorResult | None:
        """Apply adjective gender error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        current_gender = UD_TO_PYMORPHY_GENDER.get(token.get_feature("Gender"))
        other_genders = [g for g in GENDERS if g != current_gender]
        target_gender = random.choice(other_genders)

        new_word = inflect_word(parse, {target_gender})

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
    ) -> ErrorResult | None:
        """Apply verb person/number error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        new_word = None
        transform_type = None
        original_value = None

        # Randomly choose to change number or person
        if token.has_feature("Number") and random.random() < 0.5:
            target_num = "plur" if token.get_feature("Number") == "Sing" else "sing"
            new_word = inflect_word(parse, {target_num})
            transform_type = "NUMBER"
            original_value = token.get_feature("Number", "Sing")
        elif token.has_feature("Person"):
            current_person = UD_TO_PYMORPHY_PERSON.get(token.get_feature("Person"))
            other_persons = [p for p in PERSONS if p != current_person]
            target_person = random.choice(other_persons)
            new_word = inflect_word(parse, {target_person})
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
    ) -> ErrorResult | None:
        """Apply verb tense error."""
        token = tokens[idx]
        word = sentence[idx]
        parse = _get_pymorphy_parse(token)

        if parse is None:
            return None

        current_tense = UD_TO_PYMORPHY_TENSE.get(token.get_feature("Tense"))
        if current_tense is None:
            return None

        other_tenses = [t for t in self.TENSES if t != current_tense]
        target_tense = random.choice(other_tenses)

        new_word = inflect_word(parse, {target_tense})

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
