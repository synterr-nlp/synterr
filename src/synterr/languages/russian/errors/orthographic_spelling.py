"""Russian orthographic spelling handler — morpheme-level spelling rules.

Covers Rozental suffix/prefix spelling rules that depend on morpheme structure,
POS, or conjugation class — distinct from the phonetic spelling handler.

12 subtypes:
- pre_pri: пре-/при- prefix confusion (§31–32)
- y_i_after_prefix: ы/и after consonant-ending prefix (§34)
- suffix_enk_onk: -еньк/-оньк in nouns (§38)
- suffix_insk_ensk: -инск/-енск in adjectives (§40)
- suffix_its_ets: -иц/-ец in neuter nouns (§38)
- suffix_ek_ik: -ек/-ик in nouns (§38)
- participle_suffix: conjugation-dependent participle suffixes (§51)
- vowel_after_ts: vowels after ц (§35, suffix/ending position)
- vowel_after_sibilant: ё/о/ю after ш,щ,ж,ч (§35, suffix/ending position)
- nn_suffix: н/нн in adjective/participle suffixes (§39–40)
- root_vowel_after_sibilant: и/ы after ц in ROOTS (§7) — the root-position
  complement of vowel_after_ts, which explicitly skips root position.
  (Sibling rule §4, ё/о after ш,ж,ч,щ in roots, is intentionally NOT
  duplicated here — vowel_after_sibilant's existing stress-aware root
  branch already produces it; see handler docstring note below.)
- adj_ending_vowel: -ем/-им confusion in Ins/Loc singular soft-stem
  adjectives (§39 per task spec — paragraph-mapping caveat: the located §39
  text covers -ый/-ий adjective selection, not this case-ending pair)
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
    from synterr.languages.russian.resources import MorphemeAnalyzer


# =============================================================================
# пре-/при- prefix confusion
# =============================================================================

_PRE_PRI_RE = re.compile(r"^(пре|при)", re.IGNORECASE)


# =============================================================================
# ы/и after prefix
# Russian prefixes: after consonant ending, и→ы (except меж-, сверх-, foreign)
# Foreign prefixes: keep и (error = using ы)
# =============================================================================

# Russian prefixes where и→ы is correct (error = keeping и)
_RU_PREFIXES_YI = [
    "без",
    "вз",
    "из",
    "над",
    "об",
    "от",
    "под",
    "пред",
    "раз",
    "с",
    "через",
]
# Prefixes where и stays (error = using ы)
_FOREIGN_PREFIXES_I = [
    "сверх",
    "меж",  # Russian exceptions
    "транс",
    "контр",
    "пост",
    "суб",
    "супер",
    "дез",
    "пан",  # Foreign
    "спорт",
    "фин",
    "гос",
    "полит",  # Compound abbreviations
    "двух",
    "трёх",
    "трех",
    "четырёх",
    "четырех",  # Numeral prefixes
]

_ALL_PREFIXES_YI = _RU_PREFIXES_YI + _FOREIGN_PREFIXES_I


# =============================================================================
# Participle suffix swaps (conjugation-dependent)
# =============================================================================

_PARTICIPLE_SWAPS = [
    # Active present: 1st conj ↔ 2nd conj (both directions)
    ("ущ", "ащ"),
    ("ащ", "ущ"),
    ("ющ", "ящ"),
    ("ящ", "ющ"),
    # Passive present: 1st conj ↔ 2nd conj (both directions)
    ("ем", "им"),
    ("им", "ем"),
    # Past passive: swap vowel before нн/н (both directions)
    ("енн", "янн"),
    ("янн", "енн"),
    ("анн", "енн"),
]

# =============================================================================
# Vowels after ц
# =============================================================================

_TS_VOWEL_SWAPS = {
    "о": "е",
    "е": "о",  # stressed о, unstressed е
    "и": "ы",
    "ы": "и",  # и in root/suffix, ы in -ын/endings
    "ё": "о",  # ё→о after ц
}

# =============================================================================
# Vowels after sibilants (ш, щ, ж, ч)
# =============================================================================

_SIBILANT_VOWEL_SWAPS = {
    "ё": "о",
    "о": "ё",
    # ю↔у removed: only applies to 3 loanwords (жюри, брошюра, парашют)
    # and produces impossible errors on native words (чудо→чюдо, шутка→шютка)
}


# =============================================================================
# и/ы after ц in ROOTS (§7)
#
# Complement of vowel_after_ts, which explicitly requires suffix/ending
# position. Default: и is correct (цирк, цифра) — error introduces ы.
# Exception family (цыган, цыплёнок, цыпочки, цыц, цыкать + derivatives):
# ы is correct — error introduces и.
#
# Note: the parallel root rule for sibilants (§4: ё/о after ш,ж,ч,щ, e.g.
# чёрный/шёпот vs. шов/крыжовник) is deliberately NOT implemented as part
# of this subtype — vowel_after_sibilant's existing stress-aware root
# branch already produces these exact corrections (verified empirically:
# шов→шёв, крыжовник→крыжёвник, капюшон→капюшён, чёрный→чорный all already
# fire under that subtype). Duplicating it here would create two subtypes
# racing to label the same corruption. See final report for details.
# =============================================================================

_ROOT_TS_VOWEL_SWAPS = {"и": "ы", "ы": "и"}

# The five classic ы-after-ц root exceptions (+ derivatives), matched by
# stem prefix so all inflected surfaces are covered without a lemma round
# trip (none of these five roots have a fleeting-vowel alternation that
# would shift the stem's start).
_ROOT_TS_EXCEPTION_STEMS = (
    "цыган",  # цыган, цыгане, цыганский, цыганка...
    "цыпл",  # цыплёнок, цыплята, цыплячий...
    "цыпоч",  # цыпочки (на цыпочках)
    "цыц",  # цыц (invariable interjection)
    "цык",  # цыкать, цыкнуть...
)


# =============================================================================
# -ем/-им ending confusion in Ins/Loc singular soft-stem adjectives (§39,
# see report caveat on paragraph attribution)
# =============================================================================

# ADPs whose object is unambiguously Loc / Ins (used to confirm the
# adjective's own Case feature is contextually licensed, not to derive it)
_ADJ_ENDING_LOC_PREPS = {"в", "во", "на", "о", "об", "обо", "при"}
_ADJ_ENDING_INS_PREPS = {
    "с",
    "со",
    "за",
    "над",
    "надо",
    "под",
    "подо",
    "перед",
    "передо",
    "между",
    "меж",
}


# =============================================================================
# н/нн in adjective/participle suffixes (§39-40)
# =============================================================================

# Regex to find нн in word (candidate for нн→н reduction)
_NN_RE = re.compile(r"нн")

# Regex to find suffix patterns where single н may need doubling
# -ан-/-ян-/-ин- suffixes that should have 1н (error = adding 2нн)
_SINGLE_N_SUFFIX_RE = re.compile(r"(ан|ян|ин)([а-яё]*[ыоеи]й|[а-яё]*[аяое][яе]?)$")

# Words that must keep single н (exception to general rules)
_SINGLE_N_EXCEPTIONS = {
    "багряный",
    "пряный",
    "пьяный",
    "рдяный",
    "румяный",
    "ветреный",
    "зелёный",
    "зеленый",
    "юный",
    "свиной",
    "синий",
}


class OrthographicSpellingHandler(WeightedSubtypeMixin):
    """Morpheme-level spelling errors: suffixes, prefixes, post-sibilant vowels.

    Unlike the phonetic SpellingErrorHandler, these errors depend on
    morpheme boundaries, POS, or conjugation class.
    """

    name = "orthographic_spelling"
    subtypes = [
        "pre_pri",
        "y_i_after_prefix",
        "suffix_enk_onk",
        "suffix_insk_ensk",
        "suffix_its_ets",
        "suffix_ek_ik",
        "participle_suffix",
        "vowel_after_ts",
        "vowel_after_sibilant",
        "nn_suffix",
        "root_vowel_after_sibilant",
        "adj_ending_vowel",
    ]
    category = "SPELL"
    changes_length = False

    DEFAULT_WEIGHTS = {
        "pre_pri": 13,
        "y_i_after_prefix": 13,
        "suffix_enk_onk": 8,
        "suffix_insk_ensk": 8,
        "suffix_its_ets": 7,
        "suffix_ek_ik": 8,
        "participle_suffix": 10,
        "vowel_after_ts": 8,
        "vowel_after_sibilant": 8,
        "nn_suffix": 17,
        "root_vowel_after_sibilant": 8,
        "adj_ending_vowel": 7,
    }

    def __init__(self) -> None:
        super().__init__()
        self._analyzer = None

    @property
    def analyzer(self):
        if self._analyzer is None:
            self._analyzer = get_morpheme_analyzer()
        return self._analyzer

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        if not token.text.isalpha() or len(token.text) < 3:
            return False
        # All-caps abbreviations (США, ФСБ, ГИБДД...) aren't subject to any
        # of these spelling rules — skip across the whole handler.
        if len(token.text) >= 2 and token.text.isupper():
            return False
        text_lower = token.text.lower()
        lemma = token.lemma.lower() if token.lemma else text_lower

        # Quick checks for any applicable subtype
        if _PRE_PRI_RE.match(text_lower) and len(text_lower) > 4:
            return True
        for pfx in _ALL_PREFIXES_YI:
            if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
                after = text_lower[len(pfx)]
                if after in ("и", "ы"):
                    return True
        if token.pos == "NOUN" and (
            "еньк" in text_lower or "оньк" in text_lower or "иньк" in text_lower
        ):
            return True
        if token.pos != "PROPN" and ("инск" in text_lower or "енск" in text_lower):
            return True
        if _can_its_ets(text_lower):
            return True
        if _can_ek_ik(text_lower):
            return True
        if token.pos in ("VERB", "ADJ") and _has_participle_pattern(text_lower, lemma):
            return True
        if "ц" in text_lower:
            return True
        if token.pos != "PROPN" and any(c in text_lower for c in "шщжч"):
            return True
        if token.pos == "ADJ" and _can_nn_swap(text_lower, lemma):
            return True
        return _can_adj_ending_swap(tokens, idx)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        word = sentence[idx]
        text_lower = word.lower()
        lemma = token.lemma.lower() if token.lemma else text_lower

        # Collect applicable subtypes
        candidates: list[tuple[str, float]] = []

        if _PRE_PRI_RE.match(text_lower) and len(text_lower) > 4:
            candidates.append(("pre_pri", self._weights["pre_pri"]))

        if _can_yi_swap(text_lower):
            candidates.append(("y_i_after_prefix", self._weights["y_i_after_prefix"]))

        if token.pos == "NOUN" and (
            "еньк" in text_lower or "оньк" in text_lower or "иньк" in text_lower
        ):
            candidates.append(("suffix_enk_onk", self._weights["suffix_enk_onk"]))

        if token.pos != "PROPN" and _can_insk_ensk(text_lower):
            candidates.append(("suffix_insk_ensk", self._weights["suffix_insk_ensk"]))

        if _can_its_ets(text_lower):
            candidates.append(("suffix_its_ets", self._weights["suffix_its_ets"]))

        if _can_ek_ik(text_lower):
            candidates.append(("suffix_ek_ik", self._weights["suffix_ek_ik"]))

        if token.pos in ("VERB", "ADJ") and _has_participle_pattern(text_lower, lemma):
            candidates.append(("participle_suffix", self._weights["participle_suffix"]))

        if _can_ts_vowel(text_lower):
            candidates.append(("vowel_after_ts", self._weights["vowel_after_ts"]))

        if token.pos != "PROPN" and _can_sibilant_vowel(text_lower):
            candidates.append(
                ("vowel_after_sibilant", self._weights["vowel_after_sibilant"])
            )

        if token.pos == "ADJ" and _can_nn_swap(text_lower, lemma):
            candidates.append(("nn_suffix", self._weights["nn_suffix"]))

        if token.pos != "PROPN" and _can_root_ts_vowel(text_lower):
            candidates.append(
                (
                    "root_vowel_after_sibilant",
                    self._weights["root_vowel_after_sibilant"],
                )
            )

        if _can_adj_ending_swap(tokens, idx):
            candidates.append(("adj_ending_vowel", self._weights["adj_ending_vowel"]))

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

        # Look up stress: try exact form first, then lemma
        analyzer = self.analyzer
        stress_pos = analyzer.get_stress(text_lower)
        if stress_pos < 0:
            stress_pos = analyzer.get_stress(lemma)
            if stress_pos >= 0:
                stressed_syllable = _stressed_syllable(lemma, stress_pos)
            else:
                stressed_syllable = -1
        else:
            stressed_syllable = _stressed_syllable(text_lower, stress_pos)

        corrupted = _apply_subtype(
            chosen, word, text_lower, stressed_syllable, analyzer, lemma
        )
        if corrupted is None or corrupted == word:
            return None

        sentence[idx] = corrupted
        return ErrorResult(
            error_type=f"orthographic_spelling_{chosen}",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=word,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{word}",
        )


# =============================================================================
# Subtype applicability checks
# =============================================================================


def _can_yi_swap(text_lower: str) -> bool:
    for pfx in _ALL_PREFIXES_YI:
        if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
            after = text_lower[len(pfx)]
            if after in ("и", "ы"):
                return True
    return False


def _can_insk_ensk(text_lower: str) -> bool:
    """Check if word has -инск-/-енск- as a real suffix (not root-internal)."""
    if "инск" not in text_lower and "енск" not in text_lower:
        return False
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return False
    # Morpheme dict segments as ["ин", "ск"] or ["ен-", "ск"] — check for
    # suffix chain containing ин/ен + ск
    clean = [s.strip("-") for s in suffixes]
    has_sk = "ск" in clean
    has_in_en = any(s in ("ин", "ен") for s in clean)
    return has_sk and has_in_en


def _can_its_ets(text_lower: str) -> bool:
    # Nouns with -ице/-ецо/-ица/-еца patterns — only if suffix contains иц/ец
    if not re.search(r"[ие]ц[еиоа]", text_lower):
        return False
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return False  # Unknown word — skip to avoid false positives
    return any(s in ("иц", "ец", "ице", "ица", "ецо", "еца") for s in suffixes)


def _can_ek_ik(text_lower: str) -> bool:
    return bool(re.search(r"[еи]к[аеуоиы]?$", text_lower))


def _can_ts_vowel(text_lower: str) -> bool:
    for i, c in enumerate(text_lower):
        if c == "ц" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _TS_VOWEL_SWAPS:
                return True
    return False


def _can_sibilant_vowel(text_lower: str) -> bool:
    for i, c in enumerate(text_lower):
        if c in "шщжч" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _SIBILANT_VOWEL_SWAPS:
                return True
    return False


_PARTICIPLE_ENDING_RE = re.compile(
    r"(ущ|ющ|ащ|ящ)(ий|ая|ее|ие|его|ей|ему|им|их|ими|ем)(ся)?$"  # active present
    r"|(ем|им)(ый|ая|ое|ые|ого|ой|ому|ым|ых|ыми|ом)$"  # passive present
    r"|(енн|янн|анн)(ый|ая|ое|ые|ого|ой|ому|ым|ых|ыми|ом)$"  # passive past
)


def _is_suffix_boundary(
    text_lower: str,
    pos: int,
    lemma: str | None,
    analyzer: MorphemeAnalyzer | None = None,
) -> bool:
    """True if char position `pos` is confirmed NOT root/prefix-internal —
    i.e. a legitimate suffix/ending edit site — via morpheme dict lookup
    (surface first, lemma fallback, mirroring ``_swap_pre_pri``'s pattern).

    Unverifiable positions (no morpheme data via either surface or lemma)
    return False: precision-first, skip > wrong edit. This is what makes
    the old "unknown word — allow" bypass into a skip.

    Callers with a multi-char match span (participle suffixes, нн/ан/ян/ин)
    should pass the position of the *last* character of that span, not the
    first. Root-final-consonant + single-consonant-suffix words (данный =
    да-ROOT + нн-SUFF; чугунный = чугун-ROOT + н-SUFF) place the *first*
    character of the doubled/vowel-led span on the root side even though
    the span as a whole is a legitimate suffix target — checking the last
    character (which Tikhonov consistently places in the SUFF/END morpheme
    for these families) avoids rejecting them.
    """
    analyzer = analyzer or get_morpheme_analyzer()
    lemma_lower = lemma.lower() if lemma else None
    has_data = analyzer.get_morphemes(text_lower) is not None or (
        lemma_lower is not None and analyzer.get_morphemes(lemma_lower) is not None
    )
    if not has_data:
        return False
    in_root = analyzer.char_in_morpheme_type(text_lower, pos, "ROOT", lemma_lower)
    in_pref = analyzer.char_in_morpheme_type(text_lower, pos, "PREF", lemma_lower)
    return in_root is not True and in_pref is not True


def _participle_match(text_lower: str) -> tuple[int, str] | None:
    """Locate the exact terminal participle-suffix span via the anchored
    ending regex. Returns (start_index, matched_suffix_text) or None.

    Using the anchored match's own group span (rather than re-searching the
    word with ``str.find``) is what prevents picking up a root-internal
    lookalike — e.g. the "ущ" inside "Ущемляющий" (root у-щемл-) instead of
    the real "ющ" suffix right before the "ий" ending.
    """
    m = _PARTICIPLE_ENDING_RE.search(text_lower)
    if not m:
        return None
    for group_idx in (1, 4, 6):
        matched = m.group(group_idx)
        if matched is not None:
            return (m.start(group_idx), matched)
    return None


def _has_participle_pattern(text_lower: str, lemma: str | None = None) -> bool:
    match = _participle_match(text_lower)
    if match is None:
        return False
    start, matched_suffix = match
    return _is_suffix_boundary(text_lower, start + len(matched_suffix) - 1, lemma)


# =============================================================================
# Corruption logic per subtype
# =============================================================================

_VOWELS_LOWER = set("аеёиоуыэюя")


def _stressed_syllable(word: str, stress_pos: int) -> int:
    """Return 0-indexed syllable number of the stressed vowel."""
    syllable = -1
    for i, c in enumerate(word.lower()):
        if c in _VOWELS_LOWER:
            syllable += 1
            if i >= stress_pos:
                return syllable
    return syllable


def _syllable_at_pos(word: str, char_pos: int) -> int:
    """Return 0-indexed syllable number for a character position."""
    syllable = -1
    for i, c in enumerate(word.lower()):
        if c in _VOWELS_LOWER:
            syllable += 1
        if i >= char_pos:
            return syllable
    return syllable


def _apply_subtype(
    subtype: str,
    word: str,
    text_lower: str,
    stressed_syllable: int = -1,
    analyzer: MorphemeAnalyzer | None = None,
    lemma: str | None = None,
) -> str | None:
    if subtype == "pre_pri":
        return _swap_pre_pri(word, text_lower, lemma)
    elif subtype == "y_i_after_prefix":
        return _swap_yi_prefix(word, text_lower, lemma)
    elif subtype == "suffix_enk_onk":
        return _swap_enk_onk(word, text_lower)
    elif subtype == "suffix_insk_ensk":
        return _swap_insk_ensk(word, text_lower)
    elif subtype == "suffix_its_ets":
        return _swap_its_ets(word, text_lower)
    elif subtype == "suffix_ek_ik":
        return _swap_ek_ik(word, text_lower)
    elif subtype == "participle_suffix":
        return _swap_participle(word, text_lower, lemma)
    elif subtype == "vowel_after_ts":
        return _swap_ts_vowel(word, text_lower, stressed_syllable, analyzer, lemma)
    elif subtype == "vowel_after_sibilant":
        return _swap_sibilant_vowel(
            word, text_lower, stressed_syllable, analyzer, lemma
        )
    elif subtype == "nn_suffix":
        return _swap_nn(word, text_lower, lemma)
    elif subtype == "root_vowel_after_sibilant":
        return _swap_root_ts_vowel(word, text_lower, analyzer, lemma)
    elif subtype == "adj_ending_vowel":
        return _swap_adj_ending(word, text_lower)
    return None


def _swap_pre_pri(word: str, text_lower: str, lemma: str | None = None) -> str | None:
    """Swap пре↔при prefix — only if morpheme dict confirms a real prefix."""
    m = _PRE_PRI_RE.match(text_lower)
    if not m:
        return None
    prefix_lower = word[:3].lower()
    # Check morpheme dict: only swap if the word actually has пре-/при- prefix
    analyzer = get_morpheme_analyzer()
    has_pfx = analyzer.has_prefix(text_lower, prefix_lower)
    if has_pfx is None and lemma and lemma.lower() != text_lower:
        # Dict is lemma-keyed; inflected surfaces (пребывает) miss. Prefix
        # structure is stable across inflection, so fall back to the lemma.
        has_pfx = analyzer.has_prefix(lemma.lower(), prefix_lower)
    if has_pfx is False:
        return None  # Not a prefix (природа, прекрасный)
    if has_pfx is None:
        # Unknown word in morpheme dict — skip to avoid gibberish (президент etc.)
        return None
    prefix = word[:3]
    if prefix_lower == "пре":
        new_prefix = _match_case("при", prefix)
    elif prefix_lower == "при":
        new_prefix = _match_case("пре", prefix)
    else:
        return None
    return new_prefix + word[3:]


def _swap_yi_prefix(word: str, text_lower: str, lemma: str | None = None) -> str | None:
    """Swap и↔ы after prefix boundary — verified via morpheme dict, with a
    lemma fallback for inflected surfaces (mirrors ``_swap_pre_pri``).

    Requires ``has_prefix`` to resolve True on the surface or, failing
    that, the lemma — anything else (False, or still unverified/None on
    both) is skipped. Previously, an unverified ("None") result was only
    rejected for prefixes of 2 chars or less, letting longer "prefixes"
    through unchecked (политическому → политыческому, where "полит" is
    actually the ROOT of "политический", not a prefix at all).
    """
    analyzer = get_morpheme_analyzer()
    lemma_lower = lemma.lower() if lemma else None
    for pfx in sorted(_ALL_PREFIXES_YI, key=len, reverse=True):
        if text_lower.startswith(pfx) and len(text_lower) > len(pfx):
            pos = len(pfx)
            char = word[pos]
            char_lower = char.lower()
            if char_lower not in ("и", "ы"):
                continue
            # Verify this is a real prefix, not part of the root
            has_pfx = analyzer.has_prefix(text_lower, pfx)
            if has_pfx is None and lemma_lower and lemma_lower != text_lower:
                has_pfx = analyzer.has_prefix(lemma_lower, pfx)
            if has_pfx is not True:
                continue  # Not confirmed as a real prefix — skip
            if char_lower == "и":
                new_char = "Ы" if char.isupper() else "ы"
            else:
                new_char = "И" if char.isupper() else "и"
            return word[:pos] + new_char + word[pos + 1 :]
    return None


def _swap_enk_onk(word: str, text_lower: str) -> str | None:
    """Swap vowel before -ньк- in noun diminutives: е↔о, и→е.

    LoRuGEC examples: душенька↔душонька, Петенька↔Петинька, заинька↔заенька.
    Primary confusion is е↔о; и→е is secondary.
    """
    # Primary swap: е↔о
    _swap_map = {"е": "о", "о": "е", "и": "е"}
    for suffix in ("еньк", "оньк", "иньк"):
        idx = text_lower.find(suffix)
        if idx >= 0:
            orig = text_lower[idx]
            new_vowel = _swap_map.get(orig)
            if new_vowel is None:
                return None
            if word[idx].isupper():
                new_vowel = new_vowel.upper()
            return word[:idx] + new_vowel + word[idx + 1 :]
    return None


def _swap_insk_ensk(word: str, text_lower: str) -> str | None:
    """Swap -инск↔-енск."""
    for pattern, replacement_vowel in [("инск", "е"), ("енск", "и")]:
        idx = text_lower.find(pattern)
        if idx >= 0:
            orig_vowel = word[idx]
            new_vowel = (
                replacement_vowel.upper() if orig_vowel.isupper() else replacement_vowel
            )
            return word[:idx] + new_vowel + word[idx + 1 :]
    return None


def _swap_its_ets(word: str, text_lower: str) -> str | None:
    """Swap vowel before ц in suffix patterns: -ице↔-ецо, -ица↔-еца, -ьице↔-ьеце."""
    # Verify suffix contains иц/ец via morpheme dict
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if suffixes is None:
        return None
    has_suffix = any(s in ("иц", "ец", "ице", "ица", "ецо", "еца") for s in suffixes)
    if not has_suffix:
        return None
    # Find ц preceded by и/е and swap
    for i, c in enumerate(text_lower):
        if c == "ц" and i > 0:
            prev = text_lower[i - 1]
            if prev == "и":
                new_v = "Е" if word[i - 1].isupper() else "е"
                return word[: i - 1] + new_v + word[i:]
            elif prev == "е":
                new_v = "И" if word[i - 1].isupper() else "и"
                return word[: i - 1] + new_v + word[i:]
    return None


def _swap_ek_ik(word: str, text_lower: str) -> str | None:
    """Swap -ек↔-ик in diminutive suffixes — verified via morpheme dict."""
    m = re.search(r"[еи]к[аеуоиы]?$", text_lower)
    if not m:
        return None
    # Verify -ик/-ек is a real suffix, not part of the root (человек, кулик)
    analyzer = get_morpheme_analyzer()
    suffixes = analyzer.get_suffixes(text_lower)
    if (
        suffixes is not None
        and "ик" not in suffixes
        and "ек" not in suffixes
        and "к" not in suffixes
    ):
        return None  # No matching suffix (человек, парик, кулик)
    if suffixes is None:
        # Unknown word — skip to avoid false positives
        return None
    pos = m.start()
    orig_vowel = word[pos]
    orig_lower = orig_vowel.lower()
    if orig_lower == "е":
        new_vowel = "И" if orig_vowel.isupper() else "и"
    elif orig_lower == "и":
        new_vowel = "Е" if orig_vowel.isupper() else "е"
    else:
        return None
    return word[:pos] + new_vowel + word[pos + 1 :]


def _swap_participle(
    word: str, text_lower: str, lemma: str | None = None
) -> str | None:
    """Swap conjugation-dependent participle suffix vowels.

    Locates the suffix via the anchored terminal regex (``_participle_match``)
    rather than a blind ``str.find`` — that was the bug: find() returns the
    *first* textual occurrence, which can be root-internal (Ущемляющий →
    Ащемляющий edited the root-initial "ущ", not the real "ющ" suffix near
    the end; приемлемый → приимлемый edited the root-final "ем" instead of
    the suffix "ем"). The matched span is then confirmed via the morpheme
    dict (surface first, lemma fallback) to not be root/prefix-internal
    before editing exactly that span.
    """
    match = _participle_match(text_lower)
    if match is None:
        return None
    start, matched_suffix = match
    if not _is_suffix_boundary(text_lower, start + len(matched_suffix) - 1, lemma):
        return None
    target = next(
        (tgt for orig, tgt in _PARTICIPLE_SWAPS if orig == matched_suffix), None
    )
    if target is None:
        return None
    replacement = ""
    for j, ch in enumerate(target):
        src_ch = word[start + j] if start + j < len(word) else ch
        replacement += ch.upper() if src_ch.isupper() else ch
    return word[:start] + replacement + word[start + len(matched_suffix) :]


def _swap_ts_vowel(
    word: str,
    text_lower: str,
    stressed_syllable: int = -1,
    analyzer: MorphemeAnalyzer | None = None,
    lemma: str | None = None,
) -> str | None:
    """Swap vowel after ц.

    §35: After ц, о under stress / е without stress (suffixes/endings).
    Skip swap if:
    - the target vowel is stressed (unambiguous)
    - both ц and the vowel are inside the root (not a suffix/ending rule)
    """
    for i, c in enumerate(text_lower):
        if c == "ц" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _TS_VOWEL_SWAPS:
                pos = i + 1
                # Skip if this vowel is on the stressed syllable
                if stressed_syllable >= 0:
                    vowel_syllable = _syllable_at_pos(text_lower, pos)
                    if vowel_syllable == stressed_syllable:
                        continue
                # Skip if both ц and the vowel are in the root
                # §35 applies to suffixes/endings only (цирк is root, not target)
                if analyzer is not None:
                    ts_type = analyzer.char_in_morpheme_type(
                        text_lower, i, "ROOT", lemma
                    )
                    vowel_type = analyzer.char_in_morpheme_type(
                        text_lower, pos, "ROOT", lemma
                    )
                    if ts_type is True and vowel_type is True:
                        continue  # Both in root — skip (церемония, цирк)
                new_c = _TS_VOWEL_SWAPS[next_c]
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1 :]
    return None


def _swap_sibilant_vowel(
    word: str,
    text_lower: str,
    stressed_syllable: int = -1,
    analyzer: MorphemeAnalyzer | None = None,
    lemma: str | None = None,
) -> str | None:
    """Swap vowel after sibilant (ш,щ,ж,ч).

    §35: After sibilants, о/ё are distinguished by morpheme position:
    - suffix/ending: о under stress (девчонка, горячо)
    - root: ё (шёпот, жёлтый) — but learners confuse freely
    Skip when both sibilant and vowel are in the root AND the vowel is
    unstressed (no real confusion — e.g., "шоколад" is just the root).
    Allow when sibilant is in root but vowel crosses into suffix/ending.
    """
    for i, c in enumerate(text_lower):
        if c in "шщжч" and i + 1 < len(text_lower):
            next_c = text_lower[i + 1]
            if next_c in _SIBILANT_VOWEL_SWAPS:
                pos = i + 1
                # Skip if both sibilant and vowel are deep in the root
                # (шоколад, жокей — no ё/о confusion)
                # But allow root-boundary cases (шёпот — ё in root IS confused)
                if analyzer is not None:
                    sib_in_root = analyzer.char_in_morpheme_type(
                        text_lower, i, "ROOT", lemma
                    )
                    vowel_in_root = analyzer.char_in_morpheme_type(
                        text_lower, pos, "ROOT", lemma
                    )
                    if sib_in_root is True and vowel_in_root is True:
                        # Both in root — only allow if vowel is stressed
                        # (stressed root ё/о IS a real confusion: шёпот↔шопот)
                        if stressed_syllable >= 0:
                            vowel_syllable = _syllable_at_pos(text_lower, pos)
                            if vowel_syllable != stressed_syllable:
                                continue  # Unstressed root vowel — skip
                new_c = _SIBILANT_VOWEL_SWAPS[next_c]
                if word[pos].isupper():
                    new_c = new_c.upper()
                return word[:pos] + new_c + word[pos + 1 :]
    return None


def _can_nn_swap(text_lower: str, lemma: str | None = None) -> bool:
    """Check if word has нн that can be reduced or н that can be doubled.

    Both directions require the matched н/нн to sit at a confirmed
    suffix/root boundary (via morpheme dict, lemma fallback) — not
    root-internal, as in "тоннель" (нн is part of the loanword root) or
    "алюмин" (root-internal "ин", not the "-ин-" adjectival suffix).
    """
    if text_lower in _SINGLE_N_EXCEPTIONS:
        return False
    for m in _NN_RE.finditer(text_lower):
        if _is_suffix_boundary(text_lower, m.end() - 1, lemma):
            return True
    suffix_m = _SINGLE_N_SUFFIX_RE.search(text_lower)
    if suffix_m:
        n_pos = suffix_m.start() + len(suffix_m.group(1)) - 1
        if _is_suffix_boundary(text_lower, n_pos, lemma):
            return True
    return False


def _swap_nn(word: str, text_lower: str, lemma: str | None = None) -> str | None:
    """Swap н↔нн in adjective suffix.

    Direction 1 (67%): нн→н (государственный → государственый)
    Direction 2 (33%): н→нн (кожаный → кожанный)

    Each candidate position is confirmed via the morpheme dict (surface
    first, lemma fallback) to sit at a suffix/root or suffix/suffix
    boundary before being edited — this rejects root-internal нн
    (тоннельный → тонельный edited the root "тоннель") and root-internal
    ан/ян/ин (алюминиевый → алюминниевый doubled inside the root "алюмин").
    """
    # Direction 1: reduce нн→н — first boundary-confirmed occurrence.
    # Boundary check uses the *last* н of the pair — root-final-consonant +
    # single-consonant-suffix words (данный = да-ROOT + нн-SUFF; чугунный =
    # чугун-ROOT + н-SUFF) place the first н on the root side even though
    # the pair as a whole is a legitimate suffix target.
    for m in _NN_RE.finditer(text_lower):
        pos = m.start()
        if not _is_suffix_boundary(text_lower, m.end() - 1, lemma):
            continue
        corrupted = word[:pos] + word[pos + 1 :]
        if corrupted != word:
            return corrupted

    # Direction 2: double н→нн
    if text_lower not in _SINGLE_N_EXCEPTIONS:
        suffix_m = _SINGLE_N_SUFFIX_RE.search(text_lower)
        if suffix_m:
            suffix_text = suffix_m.group(1)  # "ан", "ян", or "ин"
            # The н is at suffix_start + len(suffix_text) - 1
            n_pos = suffix_m.start() + len(suffix_text) - 1
            if _is_suffix_boundary(text_lower, n_pos, lemma):
                corrupted = word[: n_pos + 1] + "н" + word[n_pos + 1 :]
                if corrupted != word:
                    return corrupted

    return None


def _can_root_ts_vowel(text_lower: str) -> bool:
    """Quick check: is there a ц+и/ы sequence anywhere?

    Root/suffix disambiguation and exception-lexicon direction gating both
    happen in ``_swap_root_ts_vowel`` — this is just a cheap pre-filter for
    candidate assembly.
    """
    for i, c in enumerate(text_lower):
        if (
            c == "ц"
            and i + 1 < len(text_lower)
            and text_lower[i + 1] in _ROOT_TS_VOWEL_SWAPS
        ):
            return True
    return False


def _matches_root_ts_exception(text_lower: str, lemma: str | None) -> bool:
    """True if the word belongs to the цыган/цыплёнок/цыпочки/цыц/цыкать family."""
    candidates = [text_lower]
    if lemma:
        candidates.append(lemma.lower())
    return any(
        cand.startswith(stem)
        for cand in candidates
        for stem in _ROOT_TS_EXCEPTION_STEMS
    )


def _swap_root_ts_vowel(
    word: str,
    text_lower: str,
    analyzer: MorphemeAnalyzer | None,
    lemma: str | None = None,
) -> str | None:
    """§7: и/ы after ц in ROOTS — the root-position complement of
    vowel_after_ts (which requires suffix/ending position).

    Default (regular root): и is correct (цирк, цифра) — error introduces ы.
    Exception family (цыган, цыплёнок, цыпочки, цыц, цыкать + derivatives):
    ы is correct — error introduces и.

    Precision guards:
    - both the ц and the target vowel must be confirmed ROOT via the
      unified-dict segmentation (lemma fallback for inflected surfaces);
      words without segmentation are skipped rather than guessed at.
    - the corrupted surface must not itself be a known word.
    """
    if analyzer is None:
        return None
    is_exception = _matches_root_ts_exception(text_lower, lemma)
    for i, c in enumerate(text_lower):
        if c != "ц" or i + 1 >= len(text_lower):
            continue
        next_c = text_lower[i + 1]
        if next_c not in _ROOT_TS_VOWEL_SWAPS:
            continue
        # Only the direction consistent with the word's lexical class
        # applies — regular roots only corrupt и→ы, the exception family
        # only corrupts ы→и.
        if is_exception and next_c != "ы":
            continue
        if not is_exception and next_c != "и":
            continue
        pos = i + 1
        cons_root = analyzer.char_in_morpheme_type(text_lower, i, "ROOT", lemma)
        vowel_root = analyzer.char_in_morpheme_type(text_lower, pos, "ROOT", lemma)
        if cons_root is not True or vowel_root is not True:
            continue  # suffix/ending (vowel_after_ts's turf) or unsegmented
        new_c = _ROOT_TS_VOWEL_SWAPS[next_c]
        if word[pos].isupper():
            new_c = new_c.upper()
        corrupted = word[:pos] + new_c + word[pos + 1 :]
        if analyzer.word_is_known(corrupted):
            continue  # coincides with a real word — skip (precision-first)
        return corrupted
    return None


def _adj_ending_governing_case(tokens: Sequence[AnalyzedToken], idx: int) -> str | None:
    """Scan up to 3 tokens to the left for a governing ADP.

    Returns "Loc" or "Ins" if a case-unambiguous preposition is found in
    range, else None. Does not walk past a sentence-initial boundary.
    """
    for offset in (1, 2, 3):
        j = idx - offset
        if j < 0:
            break
        t = tokens[j]
        if t.pos != "ADP":
            continue
        w = t.text.lower()
        if w in _ADJ_ENDING_LOC_PREPS:
            return "Loc"
        if w in _ADJ_ENDING_INS_PREPS:
            return "Ins"
    return None


def _can_adj_ending_swap(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§39: -ем/-им ending confusion in Ins/Loc singular soft-stem adjectives.

    Gates on: ADJ, singular, masc/neut (fem Ins/Loc adjective endings don't
    have this pattern), Case in {Ins, Loc}, surface ending in -ем/-им, and a
    governing ADP within 3 tokens to the left whose case matches the
    token's own Case feature (context-disambiguation, not case derivation —
    the swap always produces a real form of the same lexeme in the other
    of the two cases, which is exactly the intended error).
    """
    token = tokens[idx]
    if token.pos != "ADJ":
        return False
    if token.get_feature("Number") != "Sing":
        return False
    if token.get_feature("Gender") not in ("Masc", "Neut"):
        return False
    case = token.get_feature("Case")
    if case not in ("Ins", "Loc"):
        return False
    text_lower = token.text.lower()
    if not (text_lower.endswith("ем") or text_lower.endswith("им")):
        return False
    return _adj_ending_governing_case(tokens, idx) == case


def _swap_adj_ending(word: str, text_lower: str) -> str | None:
    """Swap -ем<->-им ending (Ins/Loc confusion in soft-stem adjectives)."""
    if text_lower.endswith("ем"):
        new_suffix = "им"
    elif text_lower.endswith("им"):
        new_suffix = "ем"
    else:
        return None
    orig_suffix = word[-2:]
    replacement = "".join(
        ch.upper() if orig_suffix[i].isupper() else ch
        for i, ch in enumerate(new_suffix)
    )
    corrupted = word[:-2] + replacement
    if corrupted == word:
        return None
    return corrupted


def _match_case(target: str, source: str) -> str:
    """Match case pattern of source to target."""
    result = []
    for i, ch in enumerate(target):
        if i < len(source) and source[i].isupper():
            result.append(ch.upper())
        else:
            result.append(ch)
    return "".join(result)
