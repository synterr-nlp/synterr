"""Russian compound word spelling handler.

Covers LoRuGEC rules:
- Rule 17: Дефис в составе сложных слов (number/letter + adjective compounds)
- Rule 36: Правописание сложных прилагательных (compound adjectives: merge vs hyphen)
- Rule 44: Правописание числительного пол- (пол- prefix spelling)

Rozental §41-44 (Part I, Chapter IX).
"""

from __future__ import annotations

import random as random_module
import re
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.errors._common import WeightedSubtypeMixin
from synterr.languages.russian.resources import get_morpheme_analyzer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# Rule 17: Number/letter/symbol + adjective → requires dash
# Pattern: "25-процентный", "Z-образный", "5-го"
# Error direction: DELETE the dash (correct → error)
# =============================================================================

# Regex: digit(s) + dash + Cyrillic adjective/ordinal suffix
_NUM_DASH_ADJ_RE = re.compile(r"^(\d[\d\s/]*)-([а-яёА-ЯЁ]{3,})$")

# Regex: Latin letter(s) + dash + Cyrillic word
_LETTER_DASH_CYRILLIC_RE = re.compile(r"^([A-Za-zα-ωΑ-Ω]+)-([а-яёА-ЯЁ]{3,})$")

# Ordinal suffixes for numeral compounds: "5-го", "70-й", "35-м"
_ORDINAL_SUFFIX_RE = re.compile(r"^(\d+)-((?:го|й|я|е|х|м|му|ми|ю))$")


# =============================================================================
# Rule 44: пол- prefix
# пол + consonant (not л) → merged: полвека
# пол + vowel/л/proper noun → dash: пол-лимона, пол-яблока, пол-Москвы
# Error: swap between merged/dashed/separate forms
# =============================================================================

_VOWELS_LOWER = set("аеёиоуыэюя")

_POL_DASH_RE = re.compile(r"^пол-([а-яёА-ЯЁ]{2,})$", re.IGNORECASE)
_POL_MERGED_RE = re.compile(r"^пол([а-яё]{2,})$", re.IGNORECASE)


# =============================================================================
# Rule 36: Compound adjective merge/hyphen
# Subordinate (one part governs the other) → merged: железнодорожный
# Coordinate (both parts equal) → hyphenated: торгово-промышленный
# Error: swap merge↔hyphen
# =============================================================================

# Common compound adjectives that should be HYPHENATED (coordinate structure)
# Error direction: remove the dash (merge them incorrectly)
# NOTE: only coordinate ("X и Y") compounds belong here. Subordinate compounds
# whose normative spelling is SOLID (молочнокислый ← молочная кислота,
# народнохозяйственный ← народное хозяйство, плодоовощной) live in
# _MERGED_COMPOUNDS below — listing them here inverted the error direction.
_HYPHENATED_COMPOUNDS: set[str] = {
    "военно-полевой",
    "военно-морской",
    "военно-воздушный",
    "торгово-промышленный",
    "торгово-экономический",
    "научно-исследовательский",
    "научно-технический",
    "научно-практический",
    "учебно-тренировочный",
    "учебно-методический",
    "учебно-воспитательный",
    "молочно-растительный",
    "молочно-белый",
    "журнально-газетный",
    "народно-демократический",
    "социально-экономический",
    "социально-политический",
    "общественно-политический",
    "общественно-полезный",
    "культурно-массовый",
    "культурно-просветительный",
    "массово-политический",
    "мясо-молочный",
    "плодово-ягодный",
    "ремонтно-строительный",
    "ремонтно-механический",
    "сердечно-сосудистый",
    "кожно-венерический",
    "отчётно-выборный",
    "партийно-комсомольский",
    "русско-немецкий",
    "англо-русский",
    "франко-прусский",
    "северо-западный",
    "северо-восточный",
    "юго-западный",
    "юго-восточный",
}

# Stems for inflected-form matching: strip the 2-char nominative ending
# (военно-полевой → военно-полев). A stem match alone is not enough — the
# remainder must be a real adjectival ending (see _ADJ_ENDINGS), so the
# nouns юго-восток/северо-запад (§43, стороны света) no longer match the
# adjective stems юго-восточн-/северо-западн- and are not mislabeled as
# compound_adj.
_HYPHENATED_COMPOUND_STEMS: frozenset[str] = frozenset(
    compound[:-2] for compound in _HYPHENATED_COMPOUNDS
)

# Compound adjectives whose normative spelling is SOLID (subordinate
# structure: первая часть подчинена второй, §44). Error direction: insert
# a dash at the component boundary (железнодорожный → железно-дорожный).
# Stanza always keeps solid tokens whole, so this direction is robust to
# the tokenizer splitting hyphenated compounds into fragments.
# Stored as (first_component, second_component_stem) — ending stripped.
_MERGED_COMPOUNDS_RAW: list[tuple[str, str]] = [
    ("железно", "дорожн"),  # железная дорога
    ("сельско", "хозяйственн"),  # сельское хозяйство
    ("народно", "хозяйственн"),  # народное хозяйство
    ("машино", "строительн"),  # машиностроение
    ("естественно", "научн"),  # естественные науки
    ("древне", "русск"),  # Древняя Русь
    ("дальне", "восточн"),  # Дальний Восток
    ("западно", "европейск"),  # Западная Европа
    ("восточно", "европейск"),  # Восточная Европа
    ("средне", "азиатск"),  # Средняя Азия
    ("молочно", "кисл"),  # молочная кислота
    ("обще", "образовательн"),  # общее образование
    ("легко", "атлетическ"),  # лёгкая атлетика
    ("хлопчато", "бумажн"),  # хлопчатая бумага
    ("железо", "бетонн"),  # железобетон
]

# solid stem → dash insertion position
_MERGED_COMPOUND_STEMS: dict[str, int] = {
    first + second: len(first) for first, second in _MERGED_COMPOUNDS_RAW
}

# Closed set of Russian adjectival endings. Used to validate the remainder
# after a stem match; rejects derived nouns (железнодорожник: remainder
# "ик" is not an adjective ending).
_ADJ_ENDINGS: frozenset[str] = frozenset(
    {
        "ый", "ий", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
        "ого", "его", "ому", "ему", "ым", "им", "ом", "ем",
        "ей", "ую", "юю", "ых", "их", "ыми", "ими",
    }
)  # fmt: skip


def _match_hyphenated_compound(text_lower: str) -> bool:
    """Token is an (inflected) form of a known hyphenated compound adjective."""
    if "-" not in text_lower:
        return False
    for stem in _HYPHENATED_COMPOUND_STEMS:
        if text_lower.startswith(stem) and text_lower[len(stem) :] in _ADJ_ENDINGS:
            return True
    return False


def _match_merged_compound(text_lower: str) -> int | None:
    """Return dash-insertion boundary if token is a known solid compound adjective."""
    if "-" in text_lower:
        return None
    for stem, boundary in _MERGED_COMPOUND_STEMS.items():
        if text_lower.startswith(stem) and text_lower[len(stem) :] in _ADJ_ENDINGS:
            return boundary
    return None


# Numerals matching ^пол... that pymorphy may tag as Sgtm nouns but which
# are NOT пол- ("half of X") compounds.
_POL_DENYLIST: frozenset[str] = frozenset(
    {
        "полтора",
        "полтораста",
    }
)

# Proper nouns are also Sgtm in pymorphy (Польша, Полтава, Полесье parse as
# NOUN,Sgtm,Geox) but are not пол- compounds — §46 requires пол- + genitive
# common noun, and corrupting them yields non-words (Пол-ьша).
_PROPER_NOUN_GRAMMEMES: frozenset[str] = frozenset(
    {"Geox", "Name", "Surn", "Patr", "Orgn", "Trad", "Abbr"}
)

# High-frequency §46а compounds that fail the Sgtm test: pymorphy parses
# полчаса/полсотни as plain nouns (no Sgtm) and полбеды as PRED. Nominative
# forms only — oblique forms switch to полу- (получаса) and must not match.
_POL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "полчаса",
        "полсотни",
        "полбеды",
    }
)


def _is_pol_compound(text_lower: str) -> bool:
    """Check if word is a real пол- compound (полвека, полдня), not полный/получить.

    Positive test — two cases for "полX":
    - X already lexicalized as a whole word (полвека, полгода, полминуты): real
      пол- compounds are singularia tantum (Sgtm) — "half of X" has no plural —
      so accept only when pymorphy tags it Sgtm with itself as the lemma. This
      rejects ordinary words that merely start with пол (полоса, политика,
      полено, полюс, полночь, полдень). Proper-noun parses (Geox etc.) are
      skipped: toponyms like Польша/Полтава are also Sgtm but not compounds.
    - X not lexicalized (полкниги, полшага): accept when the remainder after
      "пол" is itself a dictionary-known word that parses as a genitive noun
      (книги, шага). Known-ness is strict (word_is_known): pymorphy's
      prediction analyzers would otherwise "parse" garbage remainders as
      genitive nouns (политисполкома → пол + итисполкома, полуторажителей →
      пол + уторажителей) and the corruption emits non-words.

    Before either case, a morpheme gate: §46 пол- attaches to a standalone
    genitive noun, so when the unified dict has a segmentation, "пол" must be
    a morpheme of its own (полвека = пол|век|а). Rejects clipped-stem
    compounds like политисполком (полит|исполком) where "пол" straddles a
    morpheme boundary.

    All cases reject полный, получить, положение, etc.
    """
    m = _POL_MERGED_RE.match(text_lower)
    if not m:
        return False
    if text_lower in _POL_DENYLIST:
        return False
    if text_lower in _POL_ALLOWLIST:
        return True
    remainder = m.group(1)
    analyzer = get_morpheme_analyzer()

    # Morpheme gate (necessary, not sufficient): when a segmentation exists,
    # the first morpheme must be exactly "пол".
    morphemes = analyzer.get_morphemes(text_lower)
    if morphemes is not None and morphemes[0][0] != "пол":
        return False

    if analyzer.word_is_known(text_lower):
        for parse in analyzer.pymorphy.parse(text_lower):
            tag = parse.tag
            if any(g in tag for g in _PROPER_NOUN_GRAMMEMES):
                continue
            if "NOUN" in tag and "Sgtm" in tag and parse.normal_form == text_lower:
                return True
        return False

    # Whole word unknown: the remainder must be a genuine standalone word
    # (strict dictionary lookup, no prediction) inflected as a genitive noun.
    if not analyzer.word_is_known(remainder):
        return False
    for parse in analyzer.pymorphy.parse(remainder):
        tag = parse.tag
        if "NOUN" in tag and "gent" in tag:
            return True
    return False


class CompoundSpellingHandler(WeightedSubtypeMixin):
    """Corrupt compound word spelling: dashes, пол-, compound adjectives.

    Subtypes:
    - num_dash: Remove dash in number+adjective compounds (25-процентный → 25процентный)
    - pol_spelling: Corrupt пол- prefix spelling (полвека → пол-века or vice versa)
    - compound_adj: Swap merge/hyphen in compound adjectives
    """

    name = "compound_spelling"
    subtypes = [
        "num_dash",
        "pol_spelling",
        "compound_adj",
    ]
    category = "SPELL"
    changes_length = False  # We modify the token in place (merge/split within token)

    DEFAULT_WEIGHTS = {
        "num_dash": 35,
        "pol_spelling": 40,
        "compound_adj": 25,
    }

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        text = tokens[idx].text

        # Never corrupt dash fragments: stanza splits hyphenated compounds
        # context-dependently into "военно-"+"полевой" or "военно"+"-"+"полевой".
        # Corrupting a bare fragment poisons both sides of the training pair.
        if text.startswith("-") or text.endswith("-"):
            return False

        # Rule 17: number-adjective or letter-adjective with dash
        if _NUM_DASH_ADJ_RE.match(text) or _LETTER_DASH_CYRILLIC_RE.match(text):
            return True
        if _ORDINAL_SUFFIX_RE.match(text):
            return True

        # Rule 44: пол- compounds
        text_lower = text.lower()
        if _POL_DASH_RE.match(text_lower) or _is_pol_compound(text_lower):
            return True

        # Rule 36: compound adjective — hyphenated (remove dash) or solid
        # (insert dash at component boundary); both are §44 confusions
        if _match_hyphenated_compound(text_lower):
            return True
        if _match_merged_compound(text_lower) is not None:
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
        rng = rng if rng is not None else random_module
        text = sentence[idx]
        text_lower = text.lower()

        # Dash fragments from stanza tokenization ("военно-", "-полевой", "-")
        # must never be corrupted (mirrors the can_apply guard).
        if text.startswith("-") or text.endswith("-"):
            return None

        candidates: list[tuple[str, float]] = []

        # Check each subtype
        if (
            _NUM_DASH_ADJ_RE.match(text)
            or _LETTER_DASH_CYRILLIC_RE.match(text)
            or _ORDINAL_SUFFIX_RE.match(text)
        ):
            candidates.append(("num_dash", self._weights["num_dash"]))

        if _POL_DASH_RE.match(text_lower) or _is_pol_compound(text_lower):
            candidates.append(("pol_spelling", self._weights["pol_spelling"]))

        if (
            _match_hyphenated_compound(text_lower)
            or _match_merged_compound(text_lower) is not None
        ):
            candidates.append(("compound_adj", self._weights["compound_adj"]))

        if self._enabled_subtypes is not None:
            candidates = [c for c in candidates if c[0] in self._enabled_subtypes]

        if not candidates:
            return None

        # weight 0 means excluded — drop before the draw so an all-zero
        # candidate set skips instead of crashing rng.choices
        candidates = [c for c in candidates if c[1] > 0]
        if not candidates:
            return None

        subtypes, weights = zip(*candidates, strict=False)
        chosen = rng.choices(subtypes, weights=weights, k=1)[0]

        if chosen == "num_dash":
            return self._corrupt_num_dash(sentence, idx)
        elif chosen == "pol_spelling":
            return self._corrupt_pol(sentence, idx, rng)
        elif chosen == "compound_adj":
            return self._corrupt_compound_adj(sentence, idx)

        return None

    def _corrupt_num_dash(self, sentence: list[str], idx: int) -> ErrorResult | None:
        """Remove dash from number/letter-adjective compound: 25-процентный → 25процентный."""
        text = sentence[idx]
        if "-" not in text:
            return None

        # Remove first dash
        corrupted = text.replace("-", "", 1)
        if corrupted == text:
            return None

        # For ordinals, could also produce space: "5-го" → "5 го"
        # But removing dash is more common error
        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_num_dash",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )

    def _corrupt_pol(
        self, sentence: list[str], idx: int, rng: Random
    ) -> ErrorResult | None:
        """Corrupt пол- prefix spelling."""
        text = sentence[idx]
        text_lower = text.lower()

        dash_match = _POL_DASH_RE.match(text_lower)
        merged_match = _POL_MERGED_RE.match(text_lower)

        if dash_match:
            # пол-лимона → поллимона (remove dash = merge incorrectly)
            rest = text[4:]  # after "пол-"
            # Proper names after пол- (§46б: пол-Москвы) keep an internal
            # capital; lowercase it on merge — "полмосквы" is a real learner
            # error, "полМосквы" is a tokenizer artifact, not Russian.
            if not text.isupper():
                rest = rest[0].lower() + rest[1:]
            corrupted = text[:3] + rest  # "пол" + rest (no dash)
            # Preserve original case
            if text[0].isupper():
                corrupted = corrupted[0].upper() + corrupted[1:]
        elif merged_match:
            # полвека → пол-века (add dash = incorrectly hyphenate)
            rest = text[3:]  # after "пол"
            corrupted = text[:3] + "-" + rest
            if text[0].isupper():
                corrupted = corrupted[0].upper() + corrupted[1:]
        else:
            return None

        if corrupted == text:
            return None

        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_pol_spelling",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )

    def _corrupt_compound_adj(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Swap merge/hyphen in compound adjectives (§44, both directions).

        Hyphenated (coordinate) → solid: военно-полевой → военнополевой.
        Solid (subordinate) → hyphenated: железнодорожный → железно-дорожный.
        """
        text = sentence[idx]
        text_lower = text.lower()

        if "-" in text:
            if not _match_hyphenated_compound(text_lower):
                return None
            head, _, tail = text.partition("-")
            if not tail:
                return None
            # Capitalized geo compounds (Юго-Восточной) capitalize each
            # segment; on merge the internal capital must drop — learners
            # write "Юговосточной", never camelCase "ЮгоВосточной".
            # Fully-uppercase tokens (ЮГО-ВОСТОЧНОЙ) stay uppercase.
            if not text.isupper():
                tail = tail[0].lower() + tail[1:]
            corrupted = head + tail
        else:
            boundary = _match_merged_compound(text_lower)
            if boundary is None:
                return None
            corrupted = text[:boundary] + "-" + text[boundary:]

        if corrupted == text:
            return None

        sentence[idx] = corrupted

        return ErrorResult(
            error_type="compound_spelling_compound_adj",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{text}",
        )
