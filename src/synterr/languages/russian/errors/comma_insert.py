"""Russian comma insertion handler — insert commas where they don't belong.

Covers LoRuGEC rules about EXTRA commas (the error = spurious comma):
- Before "как" when it means "в качестве" (no comma per §93 Прим.) or is part of
  idiom (§114). Stanza tags virtually all "как" with dep_rel=mark, so the sense
  is disambiguated by the head's POS: a nominal head with no following finite
  verb ("работал как экономист") is the comma-wrong appositive/comparative sense
  and fires; a verbal head ("как мы встретились") is a subordinate clause where
  the comma is correct and is skipped. advcl/ccomp/csubj/acl/cc are also skipped.
- Inside frozen phraseological expressions: ни слуху ни духу, и стар и млад, etc.
  (§87 п.5). Uses a curated lexicon from Rozental — NOT all repeated conjunctions.
- Between adjacent conjunctions at clause boundaries (§110). Only fires when a
  "то/так/но" correlative follows the subordinate clause (making the comma wrong).
- Inside indivisible (цельные по смыслу) expressions: как ни в чём не бывало,
  куда глаза глядят, мало кто, не иначе как, etc. (§87 п.4, §90, §114 п.1).

Bidirectional (GREEN-tier) subtypes mirroring the "запятая НЕ ставится"
clauses of §§79–116 (see synterr-internal/BIDIRECTIONAL_COMMA_DESIGN.md):
- comma_homogeneous_conj (§86 п.1): comma before a SINGLE и/да/или/либо
  joining two non-clausal homogeneous members ("яблоки, и груши"). Exact
  complement of comma_clause_junction's clausality gate.
- comma_subj_pred (no § licenses it): comma between a heavy subject NP and
  its immediately following predicate ("Прибывшие участники, разместились").
- comma_pseudo_parenthetical (§99 п.2 Прим.): bracketing words from the
  closed never-вводные list ("Он, ведь ничего не знал"). MVP single-comma
  forms: sentence-initial word → comma after; mid-sentence → comma before.
- comma_after_odnako (§99 п.7): sentence-initial «однако» = «но», takes no
  comma; the error inserts one ("Однако, переговоры продолжились").
- comma_compound_conj_split (§108 Прим.): comma inside non-splittable
  compound conjunctions ("в то время, как"). SENTENCE-INITIAL only —
  annotation-driven precision gate (native pass 2026-07, 4/14 real):
  mid-sentence расчленение can be licensed by stress on a correlate.
- comma_x_ne_x (§90 п.4): comma inside «X не X» / «X так X» repetition
  constructions ("работа, не работа").

This handler inserts comma tokens into the sentence (changes_length=True).
"""

from __future__ import annotations

import random as random_module
from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.errors.punctuation import _get_subtree_span

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken


# =============================================================================
# "как" patterns: dep_rel-based filtering
# =============================================================================

# dep_rels where "как" introduces a subordinate clause → comma IS correct.
# We must NOT insert a comma here (it would produce correct punctuation, not an error).
# cc: coordinating "как... так и..." — comma usually correct.
#
# NB: 'mark' is deliberately NOT in this set. Real stanza tags essentially all
# "как" as dep_rel=mark, including the comma-erroneous appositive sense
# ("Дети как цветы жизни" — comma wrong) and the comma-correct clausal sense
# ("Я помню, как мы встретились" — comma correct). 'mark' is disambiguated by
# the head's POS in _is_appositive_kak: nominal head → appositive (fire),
# verbal head → clause (skip).
_KAK_CLAUSE_DEPRELS = {"advcl", "ccomp", "csubj", "acl", "cc"}

# Fallback for tokenizations where quotes/brackets escape the PUNCT tag
_PUNCT_CHARS = frozenset(",;:—–-«»\"'()[]…!?.")

# POS tags of the head of an appositive/comparative "как" (the "в качестве"
# sense, §93 Прим.) where a comma is WRONG: "работал как экономист".
_KAK_APPOSITIVE_HEAD_POS = {"NOUN", "PROPN", "ADJ", "NUM"}

# =============================================================================
# Frozen phraseological expressions from Rozental §87 п.5
# These are the ONLY repeated-conjunction patterns where comma is wrong.
# Format: frozenset of the content words between the conjunctions.
# =============================================================================

_FROZEN_PHRASES: dict[str, list[tuple[str, ...]]] = {
    "и": [
        ("день", "ночь"),
        ("смех", "горе"),
        ("стар", "млад"),
        ("там", "тут"),
        ("так", "сяк"),
        ("то", "другое"),
        ("то", "дело"),
        ("тот", "другой"),
        ("взад", "вперёд"),
        ("туда", "сюда"),
        ("направо", "налево"),
        ("вкривь", "вкось"),
        ("холод", "голод"),
        ("свет", "тьма"),
    ],
    "ни": [
        ("слуху", "духу"),
        ("бе", "ме"),
        ("больше", "меньше"),
        ("рыба", "мясо"),
        ("свет", "заря"),
        ("то", "сё"),
        ("тот", "другой"),
        ("жив", "мёртв"),
        ("себе", "людям"),
        ("туда", "сюда"),
        ("два", "полтора"),
        ("дать", "взять"),
        ("взад", "вперёд"),
        ("там", "тут"),
        ("так", "сяк"),
        ("много", "мало"),
        ("стать", "сесть"),
        ("шатко", "валко"),
        ("пуха", "пера"),
        ("ответа", "привета"),
        ("кола", "двора"),
        ("конца", "краю"),
        ("начала", "конца"),
    ],
}

# =============================================================================
# Adjacent conjunction patterns (§110)
# =============================================================================

_COORDINATING = {"и", "а", "но", "да", "или", "либо", "же", "однако", "зато"}
_SUBORDINATING = {
    "что",
    "когда",
    "если",
    "хотя",
    "чтобы",
    "пока",
    "потому",
    "поскольку",
    "пусть",
    "будто",
    "словно",
    "точно",
}

# Correlative words that follow a subordinate clause and signal NO comma at junction
_CORRELATIVES = {"то", "так", "но"}

# =============================================================================
# Indivisible (цельные по смыслу) expressions (§87 п.4, §90, §114 п.1)
# No comma inside these. Error = inserting a comma.
# Format: tuple of words, comma insertion point (index in tuple where comma goes).
# =============================================================================

# Expressions with "как" that should NOT have a comma before "как"
# (distinct from comma_before_kak which uses dep_rel; these are fixed phrases)
_INDIVISIBLE_KAK: list[tuple[str, ...]] = [
    ("как", "следует"),
    ("как", "попало"),
    ("как", "есть"),
    ("как", "было"),
    ("как", "можно"),
    ("как", "нибудь"),
    ("как", "никогда"),
    ("всё", "равно", "как"),
    ("всё", "равно", "что"),
    ("не", "иначе", "как"),
    ("не", "больше", "чем"),
    ("не", "больше", "как"),
    ("не", "меньше", "чем"),
    ("не", "хуже", "чем"),
    ("не", "раньше", "чем"),
    ("не", "позже", "чем"),
    ("не", "так", "чтобы"),
    ("не", "то", "чтобы"),
    ("не", "то", "что"),
]

# Expressions with pronouns/adverbs that form indivisible units (§87 п.4)
_INDIVISIBLE_PRONOUN: list[tuple[str, ...]] = [
    ("мало", "кто"),
    ("мало", "что"),
    ("мало", "где"),
    ("мало", "куда"),
    ("неизвестно", "кто"),
    ("неизвестно", "что"),
    ("неизвестно", "где"),
    ("неизвестно", "куда"),
    ("неизвестно", "зачем"),
    ("неизвестно", "как"),
    ("неизвестно", "кем"),
    ("неизвестно", "чем"),
    ("неизвестно", "когда"),
    ("неведомо", "кто"),
    ("неведомо", "что"),
    ("неведомо", "где"),
    ("неведомо", "куда"),
    ("неведомо", "как"),
    ("непонятно", "кто"),
    ("непонятно", "что"),
    ("непонятно", "где"),
    ("непонятно", "зачем"),
    ("непонятно", "почему"),
    ("всё", "что"),
    ("кто", "может"),
    ("кто", "хочет"),
    ("где", "нужно"),
    ("где", "попало"),
    ("куда", "глаза", "глядят"),
    ("куда", "попало"),
    ("откуда", "ни", "возьмись"),
    ("что", "угодно"),
    ("кто", "угодно"),
    ("как", "угодно"),
    ("где", "угодно"),
    ("когда", "угодно"),
    ("сколько", "угодно"),
]

# Fixed multi-word expressions with internal structure (§87 п.4, §114)
_INDIVISIBLE_FIXED: list[tuple[str, ...]] = [
    ("как", "ни", "в", "чём", "не", "бывало"),
    ("как", "ни", "в", "чем", "не", "бывало"),
    ("самый", "что", "ни", "на", "есть"),
]

# Build lookup: first word → list of (full_phrase, comma_position)
# comma_position = index before which to insert comma (usually between words 0 and 1)
_INDIVISIBLE_INDEX: dict[str, list[tuple[tuple[str, ...], int]]] = {}

for _phrases, _default_pos in [
    (_INDIVISIBLE_KAK, 0),  # comma before the phrase or within it
    (_INDIVISIBLE_PRONOUN, 0),
    (_INDIVISIBLE_FIXED, 0),
]:
    for _phrase in _phrases:
        _key = _phrase[0]
        # Default comma position: between first and second word
        _comma_pos = 1 if len(_phrase) > 1 else 0
        _INDIVISIBLE_INDEX.setdefault(_key, []).append((_phrase, _comma_pos))


def _matches_frozen_phrase(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Check if tokens starting at idx match a frozen phrase from §87 п.5."""
    conj = tokens[idx].text.lower()
    phrases = _FROZEN_PHRASES.get(conj)
    if not phrases:
        return False
    # Find second occurrence of the same conjunction
    for j in range(idx + 2, min(idx + 5, len(tokens))):
        if tokens[j].text.lower() == conj:
            # No comma already between them
            if any(tokens[k].text == "," for k in range(idx + 1, j)):
                return False
            # Collect content words between the two conjunctions
            between = tuple(
                tokens[k].text.lower()
                for k in range(idx + 1, j)
                if tokens[k].pos != "PUNCT"
            )
            if len(between) != 1:
                continue
            # Collect content word after the second conjunction
            after_words = []
            for k in range(j + 1, min(j + 3, len(tokens))):
                if tokens[k].pos != "PUNCT":
                    after_words.append(tokens[k].text.lower())
                    break
            if not after_words:
                continue
            pair = (between[0], after_words[0])
            if pair in phrases:
                return True
    return False


def _matches_indivisible(
    tokens: Sequence[AnalyzedToken], idx: int
) -> tuple[str, ...] | None:
    """Check if tokens starting at idx match an indivisible expression.

    Returns the matched phrase tuple, or None.
    """
    text_lower = tokens[idx].text.lower()
    candidates = _INDIVISIBLE_INDEX.get(text_lower)
    if not candidates:
        return None

    for phrase, _comma_pos in candidates:
        phrase_len = len(phrase)
        if idx + phrase_len > len(tokens):
            continue
        # Check if all words match (case-insensitive)
        match = True
        for k, expected in enumerate(phrase):
            if tokens[idx + k].text.lower() != expected:
                match = False
                break
        if match:
            # Verify no comma already present inside the phrase
            has_internal_comma = False
            for k in range(idx, idx + phrase_len):
                if tokens[k].text == ",":
                    has_internal_comma = True
                    break
            if not has_internal_comma:
                return phrase
    return None


def _has_finite_verb_after(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Whether a finite verb appears between idx and the clause/sentence end.

    A finite verb after "как" signals a subordinate clause (comma correct),
    so its presence vetoes the appositive insertion.
    """
    for j in range(idx + 1, len(tokens)):
        tok = tokens[j]
        if tok.text in (".", "!", "?", ";", ","):
            break
        if tok.pos in ("VERB", "AUX") and tok.get_feature("VerbForm") == "Fin":
            return True
    return False


def _is_appositive_kak(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Whether "как" at idx is the comma-erroneous appositive/comparative sense.

    Stanza tags almost all "как" with dep_rel=mark regardless of sense, so the
    dep_rel alone cannot separate the comma-wrong appositive "как" (в качестве)
    from the comma-correct subordinate-clause "как". We disambiguate on the
    head's POS plus a no-finite-verb guard:

    - head is a NOUN/PROPN/ADJ/NUM AND no finite verb follows in the clause
      → appositive "работал как экономист" / comparative "стоял как стена"
      → a comma here is an ERROR → fire.
    - head is a VERB/AUX, or a finite verb follows → subordinate clause
      ("как мы встретились") → comma correct → skip.

    PRECISION NOTE: this is a heuristic over stanza output. A handful of
    comparative "как" phrases (e.g. set idioms, "как по маслу") are headed by a
    noun and will fire even though Rozental treats some of them as comma-taking;
    these are rare relative to the dominant в-качестве/comparative cases.
    """
    token = tokens[idx]
    if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
        return False
    head = tokens[token.head_idx]
    if head.pos not in _KAK_APPOSITIVE_HEAD_POS:
        return False
    return not _has_finite_verb_after(tokens, idx)


def _is_clausal_head(token: AnalyzedToken, tokens: Sequence[AnalyzedToken]) -> bool:
    """Whether `token` heads a clause (finite verb, or has nsubj/csubj)."""
    if token.pos == "VERB" and token.get_feature("VerbForm") == "Fin":
        return True
    return any(
        t.head_idx == token.idx
        and t.dep_rel in ("nsubj", "nsubj:pass", "csubj", "csubj:pass")
        for t in tokens
    )


def _can_insert_clause_junction(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Insertion candidate for §104/§109: cc joining two clauses, no comma.

    Triggers when a coordinating conjunction (и/а/но/да/или/либо) sits at
    position `idx`, has dep_rel=cc, its head is a `conj`-attached clausal
    element, and there's no comma immediately before it.

    L1 students often add a spurious comma here. Two cases:
    - §104 exceptions: clauses sharing a minor part (e.g., a leading adverb)
    - §109 clausal-homogeneous: two subord clauses joined by single connective
    """
    if idx == 0:
        return False
    token = tokens[idx]
    if token.text.lower() not in _COORDINATING:
        return False
    if token.dep_rel != "cc":
        return False
    if tokens[idx - 1].text == ",":
        return False
    if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
        return False
    head = tokens[token.head_idx]
    if head.dep_rel != "conj":
        return False
    return _is_clausal_head(head, tokens)


def _has_correlative_after(tokens: Sequence[AnalyzedToken], subord_idx: int) -> bool:
    """Check if a subordinate clause starting at subord_idx is followed by то/так/но.

    Per §110: comma between conjunctions is NOT placed when the subordinate
    clause has a correlative word (то/так/но) after it. So we insert a comma
    (creating an error) only when such a correlative IS present.

    "но" as CCONJ is excluded — it's a regular coordinating conjunction,
    not a correlative. Only "но" as PART qualifies (rare).
    """
    for j in range(subord_idx + 1, min(subord_idx + 15, len(tokens))):
        tok = tokens[j]
        if tok.text in (".", "!", "?", ";"):
            break
        text = tok.text.lower()
        if text in _CORRELATIVES:
            # "но" as CCONJ is a regular conjunction, not a correlative
            if text == "но" and tok.pos == "CCONJ":
                continue
            if tok.pos in ("CCONJ", "PART", "ADV", "SCONJ"):
                return True
    return False


# =============================================================================
# Homogeneous members joined by a single и/да/или/либо (§86 п.1)
# =============================================================================

# §86 п.1: no comma before a SINGLE и/да(=и)/или/либо between homogeneous
# members. Противительные (а, но, да=но) always take the comma and are
# excluded; in clean text a comma-less «да» can only be да=и, so it is safe.
_HOMOGENEOUS_SINGLE_CONJ = {"и", "да", "или", "либо"}

# Conjunctions that form repeated patterns (§87): when TWO of these attach
# inside one coordination, the comma before the second IS correct → skip.
_REPEATABLE_CONJ = {"и", "да", "или", "либо", "ни"}


def _coordination_family(
    tokens: Sequence[AnalyzedToken], conj_head: AnalyzedToken
) -> set[int] | None:
    """Indices of all conjuncts in the coordination containing `conj_head`.

    `conj_head` has dep_rel=conj; its head is the first conjunct, and every
    other conj-dependent of the first conjunct belongs to the same chain.
    """
    first_idx = conj_head.head_idx
    if first_idx is None or not (0 <= first_idx < len(tokens)):
        return None
    family = {first_idx}
    family.update(
        t.idx for t in tokens if t.head_idx == first_idx and t.dep_rel == "conj"
    )
    return family


def _has_repeated_conjunction(
    tokens: Sequence[AnalyzedToken], conj_head: AnalyzedToken
) -> bool:
    """§87 guard: the coordination carries a repeated и/да/или/либо/ни.

    Counts repeatable conjunctions attached anywhere in the conj chain.
    The LEADING conjunction of «и X и Y» is tagged by stanza as PART with
    dep_rel=advmod on the first conjunct (verified on «росли и яблони и
    груши»), not as cc — so «и»/«ни» count regardless of dep_rel as long as
    they attach to a conjunct; или/либо/да count only as cc/cc:preconj.
    Two or more → the comma would be CORRECT (§87, and the modern Lopatin
    norm for two-member «и X и Y») → not an error site.
    """
    family = _coordination_family(tokens, conj_head)
    if family is None:
        return False
    count = 0
    for t in tokens:
        if t.head_idx not in family:
            continue
        text = t.text.lower()
        if text not in _REPEATABLE_CONJ:
            continue
        if t.dep_rel in ("cc", "cc:preconj") or text in ("и", "ни"):
            count += 1
    return count >= 2


def _can_insert_homogeneous_conj(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§86 п.1: single и/да/или/либо joining NON-clausal homogeneous members.

    The clausality gate is the exact inverse of _can_insert_clause_junction:
    clausal conj heads (ССП / homogeneous clauses) belong to
    comma_clause_junction; non-clausal ones (plain homogeneous members)
    belong here. Together the two subtypes partition the cc-space.
    """
    if idx == 0:
        return False
    token = tokens[idx]
    if token.text.lower() not in _HOMOGENEOUS_SINGLE_CONJ:
        return False
    # cc only: cc:preconj marks the LEADING conjunction of a repeated pattern
    if token.dep_rel != "cc":
        return False
    if tokens[idx - 1].text == ",":
        return False
    # и + subordinate conjunction is §110 territory (comma_between_conjunctions)
    if idx + 1 < len(tokens):
        nxt = tokens[idx + 1]
        if nxt.pos == "SCONJ" or nxt.dep_rel == "mark":
            return False
    if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
        return False
    head = tokens[token.head_idx]
    if head.dep_rel != "conj":
        return False
    if _is_clausal_head(head, tokens):
        return False  # ССП/clausal homogeneous → comma_clause_junction (§104/§109)
    # §87: repeated conjunction → the comma would be correct, not an error
    return not _has_repeated_conjunction(tokens, head)


# =============================================================================
# Comma between subject group and predicate (§79-zone; nothing licenses it)
# =============================================================================


def _can_insert_subj_pred(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Pause-comma after a heavy subject NP, before its predicate.

    No § of §§75–138 licenses a single comma at the bare subject–predicate
    junction, so the insertion is optionality-free. Guards:
    - subject head is NOUN/PROPN (PRON subjects are short, never comma'd);
    - subject subtree spans ≥ 2 tokens (the attested heavy-NP pause error);
    - the predicate sits IMMEDIATELY after the span — a closing isolation
      comma at the boundary («[субъект + прич. оборот], сказуемое») is
      legitimate punctuation and vetoes the site;
    - no comma inside the span (a bracketted phrase's partner comma would
      be disturbed).
    """
    token = tokens[idx]
    if token.dep_rel not in ("nsubj", "nsubj:pass"):
        return False
    if token.pos not in ("NOUN", "PROPN"):
        return False
    if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
        return False
    pred = tokens[token.head_idx]
    if pred.idx <= token.idx:
        return False
    span_left, span_right = _get_subtree_span(tokens, token.idx)
    if span_right - span_left < 1:
        return False  # not a heavy NP
    if span_right + 1 >= len(tokens):
        return False
    boundary = tokens[span_right + 1]
    if boundary.text == ",":
        return False  # closing isolation comma already sits at the boundary
    if boundary.idx != pred.idx:
        return False  # material between subject span and predicate
    return not any(tokens[k].text == "," for k in range(span_left, span_right + 1))


# =============================================================================
# Pseudo-parenthetical words (§99 п.2 Примечание — never вводные)
# =============================================================================

# Curated closed list from §99 п.2 Прим. (words that are NOT вводные and
# never take commas). Deliberately DROPS the разнобой-prone words (никак,
# небось, авось, примерно, в довершение) and the dual-function words of
# §99 пп.5–12 (значит, вообще, наконец, однако-mid, главным образом, во
# всяком случае) — those are RED, both punctuations exist.
_PSEUDO_PARENTHETICAL: list[tuple[str, ...]] = [
    ("ведь",),
    ("всё-таки",),
    ("все-таки",),  # е-spelling variant of всё-таки
    ("даже",),
    ("именно",),
    ("как", "раз"),
    ("почти",),
    ("вряд", "ли"),
    ("едва", "ли"),
    ("якобы",),
    ("буквально",),
    ("к", "тому", "же"),
    ("вдобавок",),
    ("как", "будто"),
    ("как", "бы"),
    ("словно",),
    ("между", "тем"),
    ("поэтому",),
    ("просто",),
    ("решительно",),
    ("исключительно",),
]

_PSEUDO_INDEX: dict[str, list[tuple[str, ...]]] = {}
for _phrase in _PSEUDO_PARENTHETICAL:
    _PSEUDO_INDEX.setdefault(_phrase[0], []).append(_phrase)
for _key in _PSEUDO_INDEX:
    _PSEUDO_INDEX[_key].sort(key=len, reverse=True)  # longest match first


# =============================================================================
# Non-splittable compound conjunctions (§108 Примечание)
# =============================================================================

# (phrase, index of the word BEFORE which the erroneous comma goes).
# «потому что» / «для того чтобы» are excluded — their splitting is
# legitimate under §108 п.2 conditions. «так что» is excluded — the comma'd
# degree reading «так, что» is grammatical.
_COMPOUND_SCONJ: list[tuple[tuple[str, ...], int]] = [
    (("в", "то", "время", "как"), 3),
    (("между", "тем", "как"), 2),
    (("тогда", "как"), 1),
    (("словно", "как"), 1),
    (("даже", "если"), 1),
    (("лишь", "когда"), 1),
]

# Continuations after a trailing «как» that signal a fixed как-phrase
# («тогда как раз», «тогда как будто») rather than the compound conjunction.
_KAK_PHRASE_CONTINUATIONS = {"раз", "будто", "бы"}

# Tokens transparent to the sentence-initial check: opening quotes and the
# dialogue dash may precede a sentence-initial compound conjunction.
_SENTENCE_OPENERS = frozenset({"«", "„", "“", '"', "'", "—", "–", "-"})


def _is_sentence_initial(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """`idx` is the sentence's first word (opening quotes/dashes don't count)."""
    return all(tokens[k].text in _SENTENCE_OPENERS for k in range(idx))


def _match_phrase(
    tokens: Sequence[AnalyzedToken], idx: int, phrase: tuple[str, ...]
) -> bool:
    """Contiguous case-insensitive match of `phrase` starting at `idx`."""
    if idx + len(phrase) > len(tokens):
        return False
    return all(tokens[idx + k].text.lower() == word for k, word in enumerate(phrase))


def _match_compound_sconj(
    tokens: Sequence[AnalyzedToken], idx: int
) -> tuple[tuple[str, ...], int] | None:
    """Match a non-splittable compound conjunction starting at `idx`.

    SENTENCE-INITIAL only. Annotation-driven precision gate (native-speaker
    pass 2026-07, 4/14 real): every real_error verdict was sentence-initial
    («Даже, если пуля пройдет…»), while every mid-sentence split after a
    preceding clause + comma («…играть, даже, если бы…») was judged
    ambiguous — mid-sentence, расчленение союза can be licensed by stress
    on the correlate (§108 п.1). Sentence-initially there is no preceding
    correlate, so the split is unambiguously wrong. Shared by detection and
    apply, so the two can never diverge.
    """
    if not _is_sentence_initial(tokens, idx):
        return None
    for compound, comma_pos in _COMPOUND_SCONJ:
        if not _match_phrase(tokens, idx, compound):
            continue
        # «тогда как раз», «словно как будто»: trailing как opens a fixed
        # phrase, not the conjunction → skip
        after = idx + len(compound)
        if (
            compound[-1] == "как"
            and after < len(tokens)
            and tokens[after].text.lower() in _KAK_PHRASE_CONTINUATIONS
        ):
            continue
        return compound, comma_pos
    return None


def _extends_to_compound_sconj(
    tokens: Sequence[AnalyzedToken], idx: int, phrase: tuple[str, ...]
) -> bool:
    """`phrase` at `idx` is the prefix of a compound conjunction (§108).

    «даже если», «словно как», «между тем как»: a comma BEFORE the whole
    conjunction is legitimate clause punctuation, so the pseudo-parenthetical
    subtype must not fire on the prefix word.
    """
    return any(
        len(compound) > len(phrase)
        and compound[: len(phrase)] == phrase
        and _match_phrase(tokens, idx, compound)
        for compound, _pos in _COMPOUND_SCONJ
    )


def _opens_following_clause(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """The word introduces the clause of a head to its right.

    Connective/comparative uses (поэтому, словно, как будто opening a new
    clause or оборот) can legitimately follow a comma, so mid-sentence
    pseudo-parenthetical insertion must skip them: the word attaches
    rightward to a clausal head whose subtree begins at the word itself.
    """
    token = tokens[idx]
    if token.head_idx is None or not (0 <= token.head_idx < len(tokens)):
        return False
    head = tokens[token.head_idx]
    if head.idx <= token.idx:
        return False
    if not _is_clausal_head(head, tokens):
        return False
    span_left, _span_right = _get_subtree_span(tokens, head.idx)
    return span_left == token.idx


def _pseudo_parenthetical_insert_pos(
    tokens: Sequence[AnalyzedToken], idx: int
) -> int | None:
    """Insertion position for the §99 п.2 Прим. error at `idx`, or None.

    MVP single-comma forms:
    - sentence-initial word → comma AFTER it («Ведь, он не знал»);
    - mid-sentence word → comma BEFORE it («Он, ведь ничего не знал»).
    """
    phrases = _PSEUDO_INDEX.get(tokens[idx].text.lower())
    if not phrases:
        return None
    phrase = next((p for p in phrases if _match_phrase(tokens, idx, p)), None)
    if phrase is None:
        return None
    if _extends_to_compound_sconj(tokens, idx, phrase):
        return None  # §108 compound conjunction territory
    end = idx + len(phrase)  # first position after the phrase
    if idx == 0:
        if end >= len(tokens):
            return None
        nxt = tokens[end]
        if nxt.pos == "PUNCT" or nxt.text == ",":
            return None  # fragment, or comma already present
        return end
    prev = tokens[idx - 1]
    if prev.pos == "PUNCT" or prev.text == ",":
        return None
    if prev.pos in ("CCONJ", "SCONJ"):
        return None  # conjunction junctions are other subtypes' territory
    if _opens_following_clause(tokens, idx):
        return None  # connective use — a preceding comma can be legitimate
    return idx


# =============================================================================
# Sentence-initial «однако» (§99 п.7)
# =============================================================================


def _can_insert_after_odnako(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§99 п.7: sentence-initial «однако» = противительный союз «но», no comma.

    The error inserts one (the English-calqued "However," comma). Only
    mid-/end-clause «однако» is вводное — that position is dual-function
    (RED) and never fires. Exception guard: interjection-like «Однако,
    какой ветер!» keeps the comma.
    """
    token = tokens[idx]
    if token.text.lower() != "однако":
        return False
    # sentence-initial, or clause-initial right after a semicolon
    if idx != 0 and tokens[idx - 1].text != ";":
        return False
    if idx + 1 >= len(tokens):
        return False
    nxt = tokens[idx + 1]
    if nxt.pos == "PUNCT" or nxt.text == ",":
        return False
    # «Однако, какой ветер!» — interjection exception
    if nxt.lemma in ("какой", "как") and any(t.text == "!" for t in tokens[idx + 1 :]):
        return False
    # fragment guard: require some clausal content after «однако»
    return sum(1 for t in tokens[idx + 1 :] if t.pos != "PUNCT") >= 2


# =============================================================================
# «X не X» / «X так X» repetition constructions (§90 п.4)
# =============================================================================


def _can_insert_x_ne_x(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§90 п.4: no comma inside «дождь не дождь» / «свадьба так свадьба».

    Detector: identical surface form on both sides of не/так, same POS.
    Mirror of comma_delete's repetition machinery, inverted.
    """
    if idx + 2 >= len(tokens):
        return False
    first, mid, second = tokens[idx], tokens[idx + 1], tokens[idx + 2]
    if mid.text.lower() not in ("не", "так"):
        return False
    text = first.text.lower()
    if text != second.text.lower():
        return False
    if text in ("не", "так"):  # degenerate «не не не» / «так так так»
        return False
    return first.pos != "PUNCT" and first.pos == second.pos


class CommaInsertHandler:
    """Insert spurious commas — creates extra-comma errors.

    Subtypes:
    - comma_before_kak: insert comma before "как" where it shouldn't be
    - comma_in_set_phrase: insert comma inside repeated conjunction phrases
    - comma_between_conjunctions: insert comma between adjacent conjunctions
    - comma_in_indivisible: insert comma inside indivisible expressions
    - comma_clause_junction: insert comma before clause-joining cc (§104/§109)
    - comma_homogeneous_conj: comma before single и between homogeneous members (§86)
    - comma_subj_pred: comma between heavy subject NP and predicate
    - comma_pseudo_parenthetical: bracket never-вводные words (§99 п.2 Прим.)
    - comma_after_odnako: comma after sentence-initial однако (§99 п.7)
    - comma_compound_conj_split: split non-splittable compound conjunctions
      (§108; sentence-initial only)
    - comma_x_ne_x: comma inside «X не X» repetitions (§90)
    """

    name = "comma_insert"
    subtypes = [
        "comma_before_kak",
        "comma_in_set_phrase",
        "comma_between_conjunctions",
        "comma_in_indivisible",
        "comma_clause_junction",
        "comma_homogeneous_conj",
        "comma_subj_pred",
        "comma_pseudo_parenthetical",
        "comma_after_odnako",
        "comma_compound_conj_split",
        "comma_x_ne_x",
    ]
    category = "PUNCT"
    changes_length = True

    # Workhorses (homogeneous_conj, subj_pred, pseudo_parenthetical) carry
    # the direction-balance mass; see BIDIRECTIONAL_COMMA_DESIGN.md §5.
    DEFAULT_WEIGHTS = {
        "comma_before_kak": 30,
        "comma_in_set_phrase": 20,
        "comma_between_conjunctions": 15,
        "comma_in_indivisible": 15,
        "comma_clause_junction": 20,
        "comma_homogeneous_conj": 30,
        "comma_subj_pred": 20,
        "comma_pseudo_parenthetical": 15,
        "comma_after_odnako": 8,
        "comma_compound_conj_split": 8,
        "comma_x_ne_x": 5,
    }

    def __init__(self):
        self._weights: dict[str, float] = self.DEFAULT_WEIGHTS.copy()
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def set_subtype_weights(self, weights: dict[str, float]) -> None:
        self._weights = self.DEFAULT_WEIGHTS.copy()
        for subtype, weight in weights.items():
            if subtype in self._weights:
                self._weights[subtype] = weight

    def _detect_subtypes(self, tokens: Sequence[AnalyzedToken], idx: int) -> list[str]:
        """All subtypes whose trigger fires at `idx`.

        Shared by can_apply and apply so the two can never diverge (the
        subtype-extraction bug class of June 2026).
        """
        token = tokens[idx]
        text_lower = token.text.lower()
        detected: list[str] = []

        # "как" not preceded by ANY punctuation (comma, «, (, dash, colon —
        # inserting after those double-punctuates), and NOT clause-introducing
        if (
            text_lower == "как"
            and idx > 0
            and tokens[idx - 1].pos != "PUNCT"
            and tokens[idx - 1].text not in _PUNCT_CHARS
        ):
            allow = False
            if token.dep_rel in _KAK_CLAUSE_DEPRELS:
                pass  # clause-introducing — comma is correct, don't insert
            elif token.dep_rel == "mark":
                # Stanza tags virtually all "как" as mark. Disambiguate by the
                # head's POS: nominal head + no finite verb → appositive
                # ("работал как экономист", comma wrong) → fire; verbal head
                # → subordinate clause ("как мы встретились") → skip.
                if _is_appositive_kak(tokens, idx):
                    allow = True
            elif token.dep_rel == "advmod" and token.head_idx is not None:
                # advmod как: Stanza mislabels clause-introducing как as advmod
                # ("непонятно, как можно" — comma correct, should skip).
                # If head is a verb → likely clause context → skip.
                # If head is noun/adv → fixed phrase (как минимум) → insert.
                head = (
                    tokens[token.head_idx]
                    if 0 <= token.head_idx < len(tokens)
                    else None
                )
                if head is not None and head.pos not in ("VERB", "AUX"):
                    allow = True
            else:
                allow = True
            if allow:
                detected.append("comma_before_kak")

        # Frozen phrase: conjunction + content words match a known phrase
        if text_lower in _FROZEN_PHRASES and _matches_frozen_phrase(tokens, idx):
            detected.append("comma_in_set_phrase")

        # Adjacent conjunctions: only when "то/так/но" correlative follows
        if text_lower in _COORDINATING and idx + 1 < len(tokens):
            next_lower = tokens[idx + 1].text.lower()
            if next_lower in _SUBORDINATING and _has_correlative_after(tokens, idx + 1):
                detected.append("comma_between_conjunctions")

        # Clause-junction CC (§104 exceptions, §109 clausal homogeneous):
        # cc joining two clauses with no current comma — error is adding one
        if _can_insert_clause_junction(tokens, idx):
            detected.append("comma_clause_junction")

        # Indivisible expressions (цельные по смыслу сочетания)
        if (
            text_lower in _INDIVISIBLE_INDEX
            and _matches_indivisible(tokens, idx) is not None
        ):
            detected.append("comma_in_indivisible")

        # ── Bidirectional GREEN-tier subtypes ────────────────────────────
        if _can_insert_homogeneous_conj(tokens, idx):
            detected.append("comma_homogeneous_conj")

        if _can_insert_subj_pred(tokens, idx):
            detected.append("comma_subj_pred")

        if _pseudo_parenthetical_insert_pos(tokens, idx) is not None:
            detected.append("comma_pseudo_parenthetical")

        if _can_insert_after_odnako(tokens, idx):
            detected.append("comma_after_odnako")

        if _match_compound_sconj(tokens, idx) is not None:
            detected.append("comma_compound_conj_split")

        if _can_insert_x_ne_x(tokens, idx):
            detected.append("comma_x_ne_x")

        return detected

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        return bool(self._detect_subtypes(tokens, idx))

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module

        candidates: list[tuple[str, float]] = [
            (subtype, self._weights[subtype])
            for subtype in self._detect_subtypes(tokens, idx)
        ]
        if not candidates:
            return None

        # Filter by enabled subtypes when the pipeline has restricted us
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

        if chosen == "comma_before_kak":
            return self._insert_before_kak(sentence, idx)
        elif chosen == "comma_in_set_phrase":
            return self._insert_in_set_phrase(sentence, idx, tokens)
        elif chosen == "comma_between_conjunctions":
            return self._insert_between_conjunctions(sentence, idx)
        elif chosen == "comma_clause_junction":
            return self._insert_clause_junction(sentence, idx)
        elif chosen == "comma_in_indivisible":
            return self._insert_in_indivisible(sentence, idx, tokens)
        elif chosen == "comma_homogeneous_conj":
            return self._insert_homogeneous_conj(sentence, idx)
        elif chosen == "comma_subj_pred":
            return self._insert_subj_pred(sentence, idx, tokens)
        elif chosen == "comma_pseudo_parenthetical":
            return self._insert_pseudo_parenthetical(sentence, idx, tokens)
        elif chosen == "comma_after_odnako":
            return self._insert_after_odnako(sentence, idx)
        elif chosen == "comma_compound_conj_split":
            return self._insert_compound_conj_split(sentence, idx, tokens)
        elif chosen == "comma_x_ne_x":
            return self._insert_x_ne_x(sentence, idx)

        return None

    def _insert_before_kak(self, sentence: list[str], idx: int) -> ErrorResult | None:
        """Insert comma before "как": работал как → работал , как."""
        sentence.insert(idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_before_kak",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_in_set_phrase(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """Insert comma in frozen phrase: ни слуху ни духу → ни слуху , ни духу."""
        conj = sentence[idx].lower()
        # Find second occurrence of the conjunction
        for j in range(idx + 2, min(idx + 5, len(tokens))):
            if tokens[j].text.lower() == conj:
                # Insert comma before second conjunction
                sentence.insert(j, ",")
                return ErrorResult(
                    error_type="comma_insert_comma_in_set_phrase",
                    category=self.category,
                    start_idx=j,
                    end_idx=j + 1,
                    original="",
                    corrupted=",",
                    fix_tag="$DELETE",
                )
        return None

    def _insert_between_conjunctions(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Insert comma between adjacent conjunctions: и когда → и , когда."""
        sentence.insert(idx + 1, ",")
        return ErrorResult(
            error_type="comma_insert_comma_between_conjunctions",
            category=self.category,
            start_idx=idx + 1,
            end_idx=idx + 2,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_clause_junction(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """Insert spurious comma before clause-joining cc (§104 / §109).

        "завтрак и мы" → "завтрак , и мы" — extra comma before и that joins
        two coordinated/homogeneous clauses.
        """
        sentence.insert(idx, ",")
        return ErrorResult(
            error_type="comma_clause_junction",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_in_indivisible(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """Insert comma inside indivisible expression: как следует → как , следует."""
        phrase = _matches_indivisible(tokens, idx)
        if phrase is None:
            return None

        # Find the comma insertion point from the index
        candidates = _INDIVISIBLE_INDEX.get(tokens[idx].text.lower(), [])
        comma_pos = 1  # default: between first and second word
        for p, cp in candidates:
            if p == phrase:
                comma_pos = cp
                break

        insert_idx = idx + comma_pos
        if insert_idx >= len(sentence):
            return None

        sentence.insert(insert_idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_in_indivisible",
            category=self.category,
            start_idx=insert_idx,
            end_idx=insert_idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_homogeneous_conj(
        self, sentence: list[str], idx: int
    ) -> ErrorResult | None:
        """§86 п.1: яблоки и груши → яблоки , и груши."""
        sentence.insert(idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_homogeneous_conj",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_subj_pred(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """Heavy subject NP: участники конференции разместились →
        участники конференции , разместились."""
        _span_left, span_right = _get_subtree_span(tokens, idx)
        insert_idx = span_right + 1
        if insert_idx >= len(sentence):
            return None
        sentence.insert(insert_idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_subj_pred",
            category=self.category,
            start_idx=insert_idx,
            end_idx=insert_idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_pseudo_parenthetical(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """§99 п.2 Прим.: Он ведь не знал → Он , ведь не знал;
        Ведь он не знал → Ведь , он не знал."""
        insert_idx = _pseudo_parenthetical_insert_pos(tokens, idx)
        if insert_idx is None or insert_idx > len(sentence):
            return None
        sentence.insert(insert_idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_pseudo_parenthetical",
            category=self.category,
            start_idx=insert_idx,
            end_idx=insert_idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_after_odnako(self, sentence: list[str], idx: int) -> ErrorResult | None:
        """§99 п.7: Однако переговоры → Однако , переговоры."""
        sentence.insert(idx + 1, ",")
        return ErrorResult(
            error_type="comma_insert_comma_after_odnako",
            category=self.category,
            start_idx=idx + 1,
            end_idx=idx + 2,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_compound_conj_split(
        self, sentence: list[str], idx: int, tokens: Sequence[AnalyzedToken]
    ) -> ErrorResult | None:
        """§108 Прим.: в то время как → в то время , как."""
        match = _match_compound_sconj(tokens, idx)
        if match is None:
            return None
        _compound, comma_pos = match
        insert_idx = idx + comma_pos
        if insert_idx >= len(sentence):
            return None
        sentence.insert(insert_idx, ",")
        return ErrorResult(
            error_type="comma_insert_comma_compound_conj_split",
            category=self.category,
            start_idx=insert_idx,
            end_idx=insert_idx + 1,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )

    def _insert_x_ne_x(self, sentence: list[str], idx: int) -> ErrorResult | None:
        """§90 п.4: работа не работа → работа , не работа."""
        sentence.insert(idx + 1, ",")
        return ErrorResult(
            error_type="comma_insert_comma_x_ne_x",
            category=self.category,
            start_idx=idx + 1,
            end_idx=idx + 2,
            original="",
            corrupted=",",
            fix_tag="$DELETE",
        )
