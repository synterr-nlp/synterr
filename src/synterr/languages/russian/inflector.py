"""Russian inflector using pymorphy3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# Grammatical constants
CASES = ["nomn", "gent", "datv", "accs", "ablt", "loct"]
GENDERS = ["masc", "femn", "neut"]
NUMBERS = ["sing", "plur"]
PERSONS = ["1per", "2per", "3per"]
TENSES = ["past", "pres", "futr"]

# Universal Dependencies to pymorphy3 feature mapping
UD_TO_PYMORPHY_CASE = {
    "Nom": "nomn",
    "Gen": "gent",
    "Dat": "datv",
    "Acc": "accs",
    "Ins": "ablt",
    "Loc": "loct",
}

UD_TO_PYMORPHY_NUMBER = {
    "Sing": "sing",
    "Plur": "plur",
}

UD_TO_PYMORPHY_GENDER = {
    "Masc": "masc",
    "Fem": "femn",
    "Neut": "neut",
}

UD_TO_PYMORPHY_PERSON = {
    "1": "1per",
    "2": "2per",
    "3": "3per",
}

UD_TO_PYMORPHY_TENSE = {
    "Past": "past",
    "Pres": "pres",
    "Fut": "futr",
}

# Reverse mappings (pymorphy3 to UD)
PYMORPHY_TO_UD_CASE = {v: k for k, v in UD_TO_PYMORPHY_CASE.items()}
PYMORPHY_TO_UD_NUMBER = {v: k for k, v in UD_TO_PYMORPHY_NUMBER.items()}
PYMORPHY_TO_UD_GENDER = {v: k for k, v in UD_TO_PYMORPHY_GENDER.items()}
PYMORPHY_TO_UD_PERSON = {v: k for k, v in UD_TO_PYMORPHY_PERSON.items()}
PYMORPHY_TO_UD_TENSE = {v: k for k, v in UD_TO_PYMORPHY_TENSE.items()}


def sample_confused_grammeme(
    current_ud: str,
    matrix: dict[str, dict[str, float]],
    rng,
) -> str | None:
    """Sample a confused grammeme from an empirical confusion matrix.

    Args:
        current_ud: Current UD feature value (e.g., "Nom", "Masc", "Sing")
        matrix: Confusion matrix {source_ud: {target_ud: weight, ...}, ...}
        rng: Random number generator (random.Random instance or random module)

    Returns:
        Target UD value different from current, or None if not in matrix
    """
    row = matrix.get(current_ud)
    if not row:
        return None
    targets = list(row.keys())
    weights = list(row.values())
    return rng.choices(targets, weights=weights, k=1)[0]


def match_capitalization(original: str, new: str) -> str:
    """Match the capitalization pattern of original to new word.

    Args:
        original: Original word with capitalization to match
        new: New word (typically lowercase from pymorphy3)

    Returns:
        New word with matched capitalization
    """
    if not original or not new:
        return new

    if original.isupper():
        return new.upper()
    elif original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


def inflect_word(parse: Any, grammemes: set[str], original: str | None = None) -> str | None:
    """Inflect word using pymorphy3 parse object.

    Args:
        parse: pymorphy3 parse object
        grammemes: Set of grammemes to inflect to (pymorphy3 format)
        original: Original word to match capitalization (optional)

    Returns:
        Inflected word or None if inflection failed
    """
    if parse is None:
        return None

    result = parse.inflect(grammemes)
    if result is None:
        return None

    word = result.word
    if original:
        word = match_capitalization(original, word)
    return word


def get_random_case(current_case: str | None = None) -> str:
    """Get a random case different from current.

    Args:
        current_case: Current case in pymorphy3 format (optional)

    Returns:
        Random case in pymorphy3 format
    """
    import random

    available = [c for c in CASES if c != current_case]
    return random.choice(available)


def get_random_number(current_number: str | None = None) -> str:
    """Get opposite number (singular ↔ plural)."""
    if current_number == "sing":
        return "plur"
    return "sing"


def get_random_gender(current_gender: str | None = None) -> str:
    """Get a random gender different from current."""
    import random

    available = [g for g in GENDERS if g != current_gender]
    return random.choice(available)


def get_random_person(current_person: str | None = None) -> str:
    """Get a random person different from current."""
    import random

    available = [p for p in PERSONS if p != current_person]
    return random.choice(available)


def get_random_tense(current_tense: str | None = None) -> str:
    """Get a random tense different from current."""
    import random

    available = [t for t in TENSES if t != current_tense]
    return random.choice(available)


def ud_case_to_pymorphy(ud_case: str) -> str | None:
    """Convert UD case to pymorphy3 format."""
    return UD_TO_PYMORPHY_CASE.get(ud_case)


def ud_number_to_pymorphy(ud_number: str) -> str | None:
    """Convert UD number to pymorphy3 format."""
    return UD_TO_PYMORPHY_NUMBER.get(ud_number)


def ud_gender_to_pymorphy(ud_gender: str) -> str | None:
    """Convert UD gender to pymorphy3 format."""
    return UD_TO_PYMORPHY_GENDER.get(ud_gender)


def pymorphy_case_to_ud(pm_case: str) -> str | None:
    """Convert pymorphy3 case to UD format."""
    return PYMORPHY_TO_UD_CASE.get(pm_case)


def pymorphy_number_to_ud(pm_number: str) -> str | None:
    """Convert pymorphy3 number to UD format."""
    return PYMORPHY_TO_UD_NUMBER.get(pm_number)


def pymorphy_gender_to_ud(pm_gender: str) -> str | None:
    """Convert pymorphy3 gender to UD format."""
    return PYMORPHY_TO_UD_GENDER.get(pm_gender)
