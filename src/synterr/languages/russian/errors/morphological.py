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
    UD_TO_PYMORPHY_NUMBER,
    UD_TO_PYMORPHY_PERSON,
    UD_TO_PYMORPHY_TENSE,
    inflect_word,
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

# dep_rels where the head governs the noun's case (government relation)
_GOVERNED_DEPRELS = {"obl", "nmod", "iobj", "obj"}


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
        """Check if noun case error can be applied.

        Only targets governed positions (obl, nmod, iobj, obj) where the head
        determines the noun's case — i.e. true government errors.
        """
        token = tokens[idx]
        if token.pos != "NOUN":
            return False
        if token.dep_rel not in _GOVERNED_DEPRELS:
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


# Dependents whose form visibly agrees with the noun in number — required
# evidence for a recoverable number error. Without them the flip is a free
# semantic choice ("купил книгу"/"купил книги" are both correct → non-error).
_NUMBER_AGREEING_DEPRELS = {"det", "amod"}

# Invariant possessives: their Number feature reflects the possessor, not the
# head noun ("его книга" / "его книги"), so they constrain nothing.
_INVARIANT_POSSESSIVES = {"его", "её", "ее", "их"}

# nsubj dep_rels and predicate POS that agree with the subject in number.
# Nominal predicates need not agree ("Книги — лучший подарок" is correct).
_SUBJECT_DEPRELS = {"nsubj", "nsubj:pass"}
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
        parse = _get_pymorphy_parse(token)
        if parse is None or not token.has_feature("Tense"):
            return False
        return self._licensed_tenses(tokens, idx) is not None

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

        if parse is None:
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
