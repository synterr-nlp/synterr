"""Russian punctuation error handlers — comma and dash deletion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult
from synterr.languages.russian.errors._common import (
    FINITE_POS,
    SubtypeGateMixin,
    WeightedSubtypeMixin,
    _is_predicate_token,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# ── Comma classification data ───────────────────────────────────────────────

PARENTHETICAL_WORDS = frozenset(
    {
        "конечно",
        "вероятно",
        "возможно",
        "видимо",
        "очевидно",
        "кажется",
        "пожалуй",
        "впрочем",
        "кстати",
        "наоборот",
        "например",
        "напротив",
        "следовательно",
        "безусловно",
        "несомненно",
        "разумеется",
        "наверное",
        "итак",
        "словом",
        "короче",
        "допустим",
        "предположим",
        "скажем",
    }
)
# "наконец", "действительно", "правда", "значит" REMOVED (audit A15): each
# is a dual-function lexeme whose adverbial reading (§99 пп.5–12) needs no
# comma at all — this closed list is for words that are ALWAYS вводные, and
# the dep-tree parenthetical detection above already catches their genuine
# вводное uses via parataxis/discourse arcs.

# §103 — affirmative / negative / response words; comma typically follows
# when they open a turn or response.
RESPONSE_WORDS = frozenset({"да", "нет"})

# §90 — repeated content-word POS classes that take commas between repetitions
REPEATED_CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})

DASH_CHARS = frozenset({"—", "–", "--"})

# §93/typography: quote characters that can bracket titles/quoted material
# containing an embedded dash (a route, a compound name...). Guards
# _classify_dash against treating that dash as a clause dash (audit A4).
_QUOTE_CHARS = frozenset({"«", "»", '"', "„", "“"})


# ── Dep-tree helpers ─────────────────────────────────────────────────────────

ISOLATION_DEPRELS = frozenset({"acl", "acl:relcl", "advcl"})
CLAUSE_DEPRELS = frozenset({"ccomp", "advcl", "csubj", "csubj:pass"})

# Dep relations that form isolation constructions (Rozental §92–§103).
# `amod` covers adjectival isolation — stanza tags isolated adjectives as amod
# rather than acl when they aren't morphologically participles.
PAIR_DEPRELS = {
    "acl": "pair_participle",  # причастный оборот
    "acl:relcl": "pair_relative",  # relative clause (который...)
    "advcl": "pair_gerund",  # деепричастный оборот (refined to Conv only)
    "parataxis": "pair_parenthetical",  # вводное слово/выражение
    "appos": "pair_apposition",  # приложение
    "amod": "pair_participle",  # isolated adjectival/participial modifier
}

# Speech verbs heading «..., сообщает источник» attribution clauses. A short
# trailing parataxis clause with such a head is a вводное предложение
# (§99–100 parenthetical), not a §116 БСП clause.
SPEECH_VERB_LEMMAS = frozenset(
    {
        "сообщать",
        "сообщить",
        "заявлять",
        "заявить",
        "отмечать",
        "отметить",
        "утверждать",
        "передавать",
        "передать",
        "писать",
        "написать",
        "говорить",
        "сказать",
        "рассказывать",
        "рассказать",
        "уточнять",
        "уточнить",
        "добавлять",
        "добавить",
        "подчеркивать",
        "подчеркнуть",
        "пояснять",
        "пояснить",
        "объявлять",
        "объявить",
        "свидетельствовать",
    }
)


def _get_head(
    tokens: Sequence[AnalyzedToken], tok: AnalyzedToken
) -> AnalyzedToken | None:
    """Follow head_idx to get the head token."""
    if tok.head_idx is not None and 0 <= tok.head_idx < len(tokens):
        return tokens[tok.head_idx]
    return None


def _has_own_subject(tokens: Sequence[AnalyzedToken], verb_idx: int) -> bool:
    """Check if a verb has its own nsubj/nsubj:pass dependent."""
    return any(
        t.head_idx == verb_idx and t.dep_rel in ("nsubj", "nsubj:pass") for t in tokens
    )


def _is_clausal(tokens: Sequence[AnalyzedToken], tok: AnalyzedToken) -> bool:
    """A node heads a clause when it is a finite verb, has its own subject,
    or is the sentence root (covers the nominal one-member clause of a БСП,
    e.g. "Скоро полночь" in "Скоро полночь, никто не спит")."""
    if tok.pos in FINITE_POS and tok.get_feature("VerbForm") not in (
        "Part",
        "Conv",
        "Inf",
    ):
        return True
    if _has_own_subject(tokens, tok.idx):
        return True
    return tok.dep_rel == "root"


def _segment_has_predicate(tokens: Sequence[AnalyzedToken], lo: int, hi: int) -> bool:
    """Any predicate token in tokens[lo:hi]."""
    return any(_is_predicate_token(t) for t in tokens[lo:hi])


def _clause_start(tokens: Sequence[AnalyzedToken], idx: int) -> int:
    """Index of the first token after the last , ; : before `idx` (else 0)."""
    for i in range(idx - 1, -1, -1):
        if tokens[i].pos == "PUNCT" and tokens[i].text in (",", ";", ":"):
            return i + 1
    return 0


def _junction_has_conjunction(
    tokens: Sequence[AnalyzedToken], idx: int, clause_head: AnalyzedToken
) -> bool:
    """A coordinating/subordinating conjunction sits at the clause junction:
    either immediately right of the comma at `idx`, or attached to the
    second clause's head as a `cc` dependent. Distinguishes §104 ССП
    (comma + союз) from §116 БСП (bare comma)."""
    right = tokens[idx + 1] if idx + 1 < len(tokens) else None
    if right is not None and (
        right.pos in ("CCONJ", "SCONJ") or right.dep_rel in ("cc", "mark")
    ):
        return True
    return any(t.head_idx == clause_head.idx and t.dep_rel == "cc" for t in tokens)


def _is_asyndetic_parataxis(
    tokens: Sequence[AnalyzedToken], idx: int, comma_head: AnalyzedToken
) -> bool:
    """§116 БСП clause parsed as parataxis: the comma's head is a finite
    verb whose subtree starts right after the comma and runs to the
    sentence end ("Лес рубят, щепки летят"). Inner parentheticals like
    "..., я думаю, ..." fail the to-sentence-end requirement and stay
    comma_parenthetical."""
    if comma_head.pos not in FINITE_POS or comma_head.get_feature("VerbForm") in (
        "Part",
        "Conv",
        "Inf",
    ):
        return False
    if _junction_has_conjunction(tokens, idx, comma_head):
        return False
    # «..., сообщает РИА «Новости»...» / «..., мать говорила...» — a speech
    # verb head is a вводное предложение-атрибуция when it PRECEDES its own
    # subject (attribution word order); when the subject precedes the verb,
    # it is a genuine §116 БСП clause regardless of span length. Replaces
    # the old span-based ≤5-token cutoff (audit A8), which misfired on
    # short-subject БСП clauses like «мать говорила».
    #
    # Widened (July 2026 review P2): a speech verb with NO nsubj/nsubj:pass
    # child at all is a subjectless/impersonal attribution («..., сообщается
    # в прогнозе»; «..., говорилось в сводке» — reflexive-passive forms
    # stanza lemmatizes to the base speech-verb lemma) — also attribution,
    # not a §116 clause, regardless of word order.
    if comma_head.lemma in SPEECH_VERB_LEMMAS:
        subj = next(
            (
                t
                for t in tokens
                if t.head_idx == comma_head.idx and t.dep_rel in ("nsubj", "nsubj:pass")
            ),
            None,
        )
        if subj is None or comma_head.idx < subj.idx:
            return False
    first_head = _get_head(tokens, comma_head)
    if first_head is None or not _is_clausal(tokens, first_head):
        return False
    span_left, span_right = _get_subtree_span(tokens, comma_head.idx)
    last_content = max((t.idx for t in tokens if t.pos != "PUNCT"), default=-1)
    return span_left == idx + 1 and span_right == last_content


def _is_finite_relative_clause(
    tokens: Sequence[AnalyzedToken], head: AnalyzedToken
) -> bool:
    """The acl/acl:relcl phrase headed by `head` is a finite relative or
    complement clause (который/где/куда…, «утверждение, что…») — СПП, not a
    participial оборот. A participial head never carries its own subject, a
    relative pronoun, or a mark dependent."""
    if head.get_feature("VerbForm") == "Fin":
        return True
    if _has_own_subject(tokens, head.idx):
        return True
    span_left, span_right = _get_subtree_span(tokens, head.idx)
    for i in range(span_left, span_right + 1):
        t = tokens[i]
        if t.get_feature("PronType") == "Rel":
            return True
        if t.head_idx == head.idx and t.dep_rel == "mark":
            return True
    return False


def _route_isolation_or_subordinate(
    tokens: Sequence[AnalyzedToken], candidate: AnalyzedToken
) -> str:
    """Route an ISOLATION_DEPRELS token to comma_isolation or comma_subordinate.

    advcl is isolation only as a gerund (VerbForm=Conv); a finite advcl is a
    fronted subordinate clause. Finite relative/complement clauses parsed as
    acl/acl:relcl are СПП (§107-110), not обособление. Shared by the
    head-based branch and both POS/lemma fallback branches of
    _classify_comma so all three agree (audit A6) — previously only the
    head-based branch applied this routing, so the fallback paths mislabeled
    finite relative/adverbial clauses as comma_isolation.
    """
    if candidate.dep_rel == "advcl" and candidate.get_feature("VerbForm") != "Conv":
        return "comma_subordinate"
    if candidate.dep_rel in (
        "acl",
        "acl:relcl",
    ) and _is_finite_relative_clause(tokens, candidate):
        return "comma_subordinate"
    return "comma_isolation"


def _vocative_boundary(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§101 обращение: the comma at `idx` bounds a token whose dep_rel is
    `vocative` (stanza emits this relation). Covers single sentence-initial/
    final обращения and both commas of the paired mid-sentence case; the
    subtree scan handles multiword обращения ("дорогая Маша")."""
    n = len(tokens)
    for neighbor_idx in (idx - 1, idx + 1):
        if 0 <= neighbor_idx < n and tokens[neighbor_idx].dep_rel == "vocative":
            return True
    for t in tokens:
        if t.dep_rel != "vocative":
            continue
        span_left, span_right = _get_subtree_span(tokens, t.idx)
        if idx == span_left - 1 or idx == span_right + 1:
            return True
    return False


# §90 repetition arcs: the second occurrence repeats the first's slot.
_REPETITION_DEPRELS = frozenset({"conj", "parataxis", "discourse", "appos", "fixed"})


def _is_repetition_construction(
    tokens: Sequence[AnalyzedToken],
    left: AnalyzedToken,
    right: AnalyzedToken,
) -> bool:
    """§90 repeated words fill ONE syntactic slot ("он ехал, ехал"): the
    second occurrence is conj/parataxis-linked to the first, or both attach
    to the same head with the same relation. Accidental same-form adjacency
    across a clause boundary ("…любят сказки, сказки развивают…" — obj of
    clause 1 vs nsubj of clause 2) must fall through to the dep tree."""
    if right.head_idx == left.idx and right.dep_rel in _REPETITION_DEPRELS:
        return True
    if left.head_idx == right.idx and left.dep_rel in _REPETITION_DEPRELS:
        return True
    if (
        left.head_idx is not None
        and left.head_idx == right.head_idx
        and left.dep_rel == right.dep_rel
    ):
        return True
    # No dep info on either side (backend without depparse): keep the old
    # surface-only behaviour rather than silently disabling §90.
    return (
        left.head_idx is None
        and right.head_idx is None
        and left.dep_rel is None
        and right.dep_rel is None
    )


def _is_split_conjunction_comma(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """The comma at `idx` splits a compound subordinating conjunction
    («после того, как…» / «до того, как…» / «для того, чтобы…») — a §108
    junction. Deleting just this comma alone yields the equally-normative
    unsplit variant («после того как…»), so it must never be generated as a
    standalone comma_delete error, nor treated as a paired-isolation
    boundary (audit A16).

    Narrowed (July 2026 review P1): the surface лемма-only check also
    caught CORRELATIVE constructions where a demonstrative is a bare
    argument of the main-clause verb («гордился тем, что выиграл», «дело в
    том, что…») — there the comma is OBLIGATORY and deleting it is a
    genuine, frequent error, not a splittable junction. A genuine compound
    conjunction is ADP-led: the demonstrative sits within an ADP's
    prepositional phrase (после/до/для/из-за/ввиду/несмотря на + того/то),
    so require an ADP within 2 tokens to the left of the demonstrative.
    """
    n = len(tokens)
    right = tokens[idx + 1] if idx + 1 < n else None
    left = tokens[idx - 1] if idx > 0 else None
    if (
        right is None
        or left is None
        or (right.lemma or right.text).lower() not in ("как", "пока", "чтобы", "что")
        or (left.lemma or left.text).lower()
        not in ("тот", "то", "тем", "того", "этот", "это", "весь")
    ):
        return False
    return any(tokens[j].pos == "ADP" for j in range(max(0, left.idx - 2), left.idx))


def _find_comma_partner(
    tokens: Sequence[AnalyzedToken], idx: int
) -> tuple[int, str] | None:
    """Detect a PAIRED isolation construction whose OPENING comma is at `idx`.

    Returns (partner_idx, subtype) or None. Both commas must exist: a
    sentence-edge phrase with a single comma («Высушенные, они...») belongs
    to single-comma handlers (comma_delete:comma_isolation), so this
    handler always deletes exactly two commas.

    Approach: iterate over every token whose dep_rel is in PAIR_DEPRELS,
    compute its non-punct subtree span, and check whether `idx` is the
    phrase's opening boundary comma (immediately left of the span). This is
    robust to stanza's habit of attaching opening and closing commas of a
    pair to different heads in complex sentences.
    """
    comma = tokens[idx]
    if comma.text != "," or comma.pos != "PUNCT":
        return None

    n = len(tokens)

    # «после того, как…» / «до тех пор, пока…»: the comma splits a compound
    # subordinating conjunction — a §108 junction, never a paired isolation.
    if _is_split_conjunction_comma(tokens, idx):
        return None

    # Collect every PAIR_DEPRELS head whose boundary comma touches `idx`, then
    # prefer the largest enclosing span and demote bare `amod`. A leading
    # attributive adjective (also tagged amod) otherwise shadows the real
    # appos/acl head whose subtree *encloses* it, leaving an orphaned closing
    # comma; and a homogeneous list's per-item amod would false-fire.
    candidates: list[tuple[int, int | None, str, bool]] = []
    for head in tokens:
        if head.dep_rel not in PAIR_DEPRELS:
            continue
        # advcl: only the gerund form (VerbForm=Conv) is a pair construction.
        # Full subord clauses (VerbForm=Fin) belong to single comma_delete.
        if head.dep_rel == "advcl" and head.get_feature("VerbForm") != "Conv":
            continue
        # acl/acl:relcl parsed pairs that are finite clauses go to
        # pair_relative via acl:relcl; a finite clause behind bare `acl`
        # («утверждение, что…») is a complement clause, not an оборот.
        if head.dep_rel == "acl" and _is_finite_relative_clause(tokens, head):
            continue

        span_left, span_right = _get_subtree_span(tokens, head.idx)

        # «..., что должно сказаться...» — a parataxis clause opened by
        # «что» is a присоединительное придаточное (§110), not a
        # parenthetical pair.
        if head.dep_rel == "parataxis":
            first_tok = next(
                (
                    tokens[i]
                    for i in range(span_left, span_right + 1)
                    if tokens[i].pos != "PUNCT"
                ),
                None,
            )
            if (
                first_tok is not None
                and (first_tok.lemma or first_tok.text).lower() == "что"
            ):
                continue

        left_comma_idx: int | None = None
        if span_left > 0:
            t = tokens[span_left - 1]
            if t.text == "," and t.pos == "PUNCT":
                left_comma_idx = span_left - 1

        right_comma_idx: int | None = None
        if span_right + 1 < n:
            t = tokens[span_right + 1]
            if t.text == "," and t.pos == "PUNCT":
                right_comma_idx = span_right + 1

        if left_comma_idx is None and right_comma_idx is None:
            continue

        is_amod = head.dep_rel == "amod"
        # A bare amod is an isolated adjective only when bounded by commas on
        # BOTH sides, or preposed at the sentence start with a closing comma.
        # Otherwise it is an ordinary leading attributive (e.g. a list item).
        if is_amod:
            both_sides = left_comma_idx is not None and right_comma_idx is not None
            preposed = span_left == 0 and right_comma_idx is not None
            if not (both_sides or preposed):
                continue

        subtype = PAIR_DEPRELS[head.dep_rel]
        # A "participle" span actually anchored by a gerund («Будучи убеждён
        # в том, ...») is a деепричастный оборот.
        if subtype == "pair_participle" and any(
            tokens[i].get_feature("VerbForm") == "Conv"
            for i in range(span_left, span_right + 1)
        ):
            subtype = "pair_gerund"
        span_size = span_right - span_left

        # Both boundary commas must exist — sentence-edge single-comma
        # isolations belong to comma_delete, and deleting one comma under a
        # pair label breaks the handler's contract.
        if (
            left_comma_idx is not None
            and right_comma_idx is not None
            and idx == left_comma_idx
        ):
            candidates.append((span_size, right_comma_idx, subtype, is_amod))

    if not candidates:
        return None

    # Prefer the largest enclosing span; among equals, prefer non-amod heads.
    best = max(candidates, key=lambda c: (c[0], not c[3]))
    close_idx = best[1]

    # A nested construction whose own comma falls strictly inside this span
    # shares or crosses it («Иван, мой друг, который живёт в Москве,
    # приехал») — deleting the outer pair alone would orphan the inner
    # comma, so skip rather than mangle it (audit A2). The inner
    # construction's own boundary comma (here idx=4, "который...") still
    # gets its own, non-crossing candidate pair.
    if any(
        tokens[j].pos == "PUNCT" and tokens[j].text == ","
        for j in range(idx + 1, close_idx)
    ):
        return None

    return (close_idx, best[2])


def _get_subtree_span(
    tokens: Sequence[AnalyzedToken], root_idx: int
) -> tuple[int, int]:
    """Get (min_idx, max_idx) of the subtree rooted at root_idx."""
    visited = set()
    stack = [root_idx]
    while stack:
        i = stack.pop()
        if i in visited:
            continue
        visited.add(i)
        for t in tokens:
            if t.head_idx == i and t.idx not in visited and t.pos != "PUNCT":
                stack.append(t.idx)
    return (min(visited), max(visited)) if visited else (root_idx, root_idx)


def _is_chem_comparative_boundary(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """The comma at `idx` bounds a «чем»-comparative clause INSERTED
    between an attributive adjective and the noun it modifies («в иных,
    чем указанные в статье 1, формах») — сравнительный оборот, not a
    homogeneous list. Stanza tends to parse the чем-clause as a `conj` of
    the modified adjective, which otherwise wins the generic "conj →
    homogeneous" branch below.

    This is deliberately narrower than "any comma next to «чем»": an
    ordinary comparative clause ("Она умнее, чем он думал.") is already
    correctly comma_subordinate and must not be caught here. The
    discontinuous-NP insertion always has TWO commas — the чем-clause's
    own dep-subtree is immediately followed by a second comma — so that
    is the signal we require for the opening boundary; the closing
    boundary mirrors it (comma immediately follows the чем-clause's own
    subtree). Firing on only one of the pair is a dubious, half-formed
    edit anyway.
    """
    n = len(tokens)

    def _chem_head_span(mark: AnalyzedToken) -> tuple[int, int] | None:
        if (
            (mark.lemma or mark.text).lower() != "чем"
            or mark.head_idx is None
            or not (0 <= mark.head_idx < n)
        ):
            return None
        return _get_subtree_span(tokens, mark.head_idx)

    right = tokens[idx + 1] if idx + 1 < n else None
    if right is not None and (right.pos == "SCONJ" or right.dep_rel == "mark"):
        span = _chem_head_span(right)
        if span is not None:
            _, span_right = span
            if span_right + 1 < n and tokens[span_right + 1].text == ",":
                return True

    for mark in tokens:
        if mark.dep_rel != "mark":
            continue
        span = _chem_head_span(mark)
        if span is not None and idx == span[1] + 1:
            return True
    return False


_VOCATIVE_NAME_FEATURES = frozenset({"Giv", "Sur"})


def _is_bare_person_propn(
    tokens: Sequence[AnalyzedToken], propn: AnalyzedToken
) -> bool:
    """A PROPN candidate for the §101 vocative fallback: a given/surname
    feature if stanza tags it, else a PROPN with no non-punctuation
    dependents of its own (punctuation routinely attaches to a nearby
    content word as its dep-tree head and doesn't count). Excludes
    ordinary PROPN subjects/objects that carry modifiers or coordination
    (e.g. "Зырянов и Денисов искали пути" — "Зырянов" heads a `conj`
    dependent, so it isn't a bare address)."""
    if propn.get_feature("NameType") in _VOCATIVE_NAME_FEATURES:
        return True
    return not any(t.head_idx == propn.idx and t.pos != "PUNCT" for t in tokens)


def _has_person2_verb(tokens: Sequence[AnalyzedToken]) -> bool:
    """A 2nd-person verb anywhere in the sentence — the surface marker of
    direct address that gates the §101 vocative fallback below."""
    return any(t.pos == "VERB" and t.get_feature("Person") == "2" for t in tokens)


def _vocative_fallback_boundary(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§101 fallback: stanza sometimes tags an обращение as `parataxis`
    instead of `vocative` (e.g. a name closing a directly-addressed
    question — "хотите посмотреть, Эдуард?"). Detect a comma immediately
    followed by a bare person-name PROPN that is itself followed by
    another comma or sentence-final `!`/`?`, gated on a 2nd-person verb
    somewhere in the sentence to avoid catching ordinary PROPN subjects
    ("..., Зырянов и Денисов искали пути" has no 2nd-person verb at all).
    """
    n = len(tokens)
    right = tokens[idx + 1] if idx + 1 < n else None
    if right is None or right.pos != "PROPN":
        return False
    after = tokens[right.idx + 1] if right.idx + 1 < n else None
    if after is None or after.text not in (",", "!", "?"):
        return False
    if not _is_bare_person_propn(tokens, right):
        return False
    return _has_person2_verb(tokens)


def _classify_comma(tokens: Sequence[AnalyzedToken], idx: int) -> str:
    """Classify a comma by syntactic context using the dependency tree.

    Uses the comma's own head pointer as the primary signal, with POS/lemma
    fallbacks when dep info is unavailable.
    """
    n = len(tokens)
    comma = tokens[idx]
    right = tokens[idx + 1] if idx + 1 < n else None
    left = tokens[idx - 1] if idx > 0 else None

    # The comma's head in the dep tree is the key signal
    comma_head = _get_head(tokens, comma) if comma.head_idx is not None else None

    # ── 0. Surface-feature overrides (high-specificity rules) ────────────
    # These run before dep-tree classification because they're more specific
    # than the generic conj/punct dep relations that would otherwise win.

    # §101 — Обращение: comma bounds a dep_rel=vocative token/subtree.
    # Runs first: the comma between an INTJ/response word and an обращение
    # ("Привет, Маша") is the §101 boundary. The fallback catches обращения
    # stanza mis-tagged as parataxis (see _vocative_fallback_boundary).
    if _vocative_boundary(tokens, idx) or _vocative_fallback_boundary(tokens, idx):
        return "comma_vocative"

    # Сравнительный оборот («в иных, чем указанные..., формах»): a bare
    # comparative-clause boundary, not a homogeneous list — and this
    # construction always has two commas, so a single-sided delete is
    # dubious regardless. Not a real subtype: weights.get() defaults to 0
    # and set_enabled_subtypes() rejects it (not in self.subtypes), so
    # apply() always skips rather than mislabels. See CommaDeleteHandler.
    if _is_chem_comparative_boundary(tokens, idx):
        return "comma_skip_chem_comparative"

    # §102 — Interjection: INTJ neighbor is a strong signal
    if (left and left.pos == "INTJ") or (right and right.pos == "INTJ"):
        return "comma_interjection"

    # §103 — Affirmative/negative response at sentence start
    if left and left.idx == 0 and left.lemma in RESPONSE_WORDS:
        return "comma_response"

    # §90 — Repeated word: identical surface form + same content-POS on both
    # sides, in a true repetition construction (same syntactic slot). Same-
    # lemma adjacency across a clause boundary falls through to the dep tree.
    if (
        left
        and right
        and left.pos == right.pos
        and left.pos in REPEATED_CONTENT_POS
        and left.text.lower() == right.text.lower()
        and _is_repetition_construction(tokens, left, right)
    ):
        return "comma_repeated"

    # ── 1. Dep-tree based classification (when head info available) ──────

    if comma_head is not None:
        # Parenthetical: comma's head has dep_rel=parataxis or discourse.
        # Exception: stanza also uses parataxis for the second clause of a
        # БСП ("Лес рубят, щепки летят") — a trailing finite clause with no
        # conjunction is §116 asyndetic, not a parenthetical.
        if comma_head.dep_rel in ("parataxis", "discourse"):
            if comma_head.dep_rel == "parataxis" and _is_asyndetic_parataxis(
                tokens, idx, comma_head
            ):
                return "comma_asyndetic"
            return "comma_parenthetical"

        # Isolation: comma's head is an acl/acl:relcl/advcl node.
        # advcl is isolation only as a gerund (VerbForm=Conv); a fronted finite
        # subordinate clause ("Когда…,") is comma_subordinate. Mirrors the
        # _find_comma_partner advcl guard.
        if comma_head.dep_rel in ISOLATION_DEPRELS:
            return _route_isolation_or_subordinate(tokens, comma_head)

        # Приложение (§93): the comma bounds an appos-headed phrase —
        # обособление, not a homogeneous list («с Уго Чавесом, президентом
        # Венесуэлы»).
        if comma_head.dep_rel == "appos":
            return "comma_isolation"

        # Postposed attributive phrase («источников, близких к ТВЦ») —
        # обособленное определение: an amod adjective whose head noun
        # precedes the comma.
        if (
            right is not None
            and right.pos == "ADJ"
            and right.dep_rel == "amod"
            and right.head_idx is not None
            and right.head_idx < idx
        ):
            return "comma_isolation"

        # Subordinate/compound/asyndetic: comma's head is a conj node.
        # Stanza parses conjunction-less clause sequences (БСП) as conj too,
        # so a clause junction is §104 compound only when an actual
        # coordinating conjunction sits at the junction; a bare comma
        # between two clauses is §116 asyndetic.
        if comma_head.dep_rel == "conj":
            conj_head = _get_head(tokens, comma_head)
            second_clausal = comma_head.pos in FINITE_POS and _has_own_subject(
                tokens, comma_head.idx
            )
            first_clausal = conj_head is not None and _is_clausal(tokens, conj_head)
            if second_clausal and first_clausal:
                if _junction_has_conjunction(tokens, idx, comma_head):
                    return "comma_compound"
                return "comma_asyndetic"
            # conj linking non-clausal items → homogeneous
            return "comma_homogeneous"

        # Comma head is a clausal complement (ccomp/advcl) → subordinate
        if comma_head.dep_rel in CLAUSE_DEPRELS:
            return "comma_subordinate"

    # ── 2. POS/lemma fallbacks (when dep tree is absent or unhelpful) ────

    # Parenthetical: opening comma — mirror of the closing-comma left-scan
    # further below (§99–100). Scan right for a parataxis/discourse subtree
    # that STARTS right after this comma and ends just before another comma.
    # Must run before the generic SCONJ/mark subordinate fallback: a
    # parenthetical opened by «как» («как ясно из записи») is tagged
    # dep_rel=mark by stanza and would otherwise win that check (audit A7).
    if right is not None:
        for i in range(idx + 1, min(idx + 15, n)):
            t = tokens[i]
            if t.dep_rel not in ("parataxis", "discourse"):
                continue
            subtree_min, subtree_max = _get_subtree_span(tokens, t.idx)
            if subtree_min != idx + 1:
                continue
            for close_idx in range(subtree_max + 1, min(subtree_max + 3, n)):
                if tokens[close_idx].text == "," and tokens[close_idx].pos == "PUNCT":
                    if all(
                        tokens[j].pos == "PUNCT"
                        for j in range(subtree_max + 1, close_idx)
                    ):
                        return "comma_parenthetical"
                    break

    # Subordinate: next token is SCONJ or has dep_rel=mark
    if right and (right.dep_rel == "mark" or right.pos == "SCONJ"):
        return "comma_subordinate"

    # Compound: CCONJ between clauses
    if right and right.pos == "CCONJ" and right.dep_rel == "cc":
        # Check if the cc's head is a conj verb with its own subject
        cc_head = _get_head(tokens, right)
        if cc_head is not None and cc_head.pos in FINITE_POS:
            if _has_own_subject(tokens, cc_head.idx):
                return "comma_compound"

    # Parenthetical: adjacent word in known list
    if right and right.lemma in PARENTHETICAL_WORDS:
        return "comma_parenthetical"
    if left and left.lemma in PARENTHETICAL_WORDS:
        return "comma_parenthetical"

    # Isolation: adjacent participle/gerund or acl/advcl dep_rel
    for neighbor in (right, left):
        if neighbor is None:
            continue
        if neighbor.dep_rel in ISOLATION_DEPRELS:
            return _route_isolation_or_subordinate(tokens, neighbor)
        if neighbor.get_feature("VerbForm") in ("Part", "Conv"):
            return "comma_isolation"

    # Isolation: closing comma — scan left for a participle whose subtree
    # ends just before this comma (allow a gap of 1-2 PUNCT-only tokens)
    if right is not None:
        for i in range(max(0, idx - 15), idx):
            t = tokens[i]
            if t.dep_rel in ISOLATION_DEPRELS:
                _, subtree_max = _get_subtree_span(tokens, t.idx)
                gap = idx - 1 - subtree_max
                if 0 <= gap <= 2 and all(
                    tokens[j].pos == "PUNCT" for j in range(subtree_max + 1, idx)
                ):
                    return _route_isolation_or_subordinate(tokens, t)

    # Parenthetical: closing comma — symmetric to opening-comma detection
    # in section 1, scan left for a parataxis/discourse subtree ending just
    # before this comma. Catches the closing `,` of "..., по существу, ..."
    # where the comma's own head_idx points at the next content token (not
    # the parataxis), defeating the section-1 head-based check.
    if right is not None:
        for i in range(max(0, idx - 15), idx):
            t = tokens[i]
            if t.dep_rel in ("parataxis", "discourse"):
                _, subtree_max = _get_subtree_span(tokens, t.idx)
                gap = idx - 1 - subtree_max
                if 0 <= gap <= 2 and all(
                    tokens[j].pos == "PUNCT" for j in range(subtree_max + 1, idx)
                ):
                    return "comma_parenthetical"

    # Homogeneous: left and right share the same head (conj siblings)
    if left and right and left.head_idx is not None and right.head_idx is not None:
        if left.head_idx == right.head_idx:
            return "comma_homogeneous"
        # One is conj of the other
        if left.head_idx == right.idx or right.head_idx == left.idx:
            return "comma_homogeneous"

    # ── 3. Fallback ──────────────────────────────────────────────────────
    # Same-POS neighbors without dep info → likely homogeneous (list)
    if left and right and left.pos == right.pos and left.pos != "PUNCT":
        return "comma_homogeneous"
    # Head is a finite verb → likely separating clauses
    if comma_head is not None and comma_head.pos in FINITE_POS:
        return "comma_subordinate"
    # True fallback: subordinate is the most common comma type in Russian
    return "comma_subordinate"


def _inside_unbalanced_quote(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """An odd number of quote characters precede `idx` — the dash sits
    inside an OPEN quotation span (e.g. a title: «Фонд ассоциации
    "Гематологи мира — детям" собрал средства»). That dash is quotation-
    internal typography, not a Rozental clause dash (audit A4).
    """
    return sum(1 for t in tokens[:idx] if t.text in _QUOTE_CHARS) % 2 == 1


_TEMPORAL_ENDPOINT_LEMMAS = frozenset(
    {
        "январь",
        "февраль",
        "март",
        "апрель",
        "май",
        "июнь",
        "июль",
        "август",
        "сентябрь",
        "октябрь",
        "ноябрь",
        "декабрь",
        "зима",
        "весна",
        "лето",
        "осень",
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
        "утро",
        "день",
        "вечер",
        "ночь",
        "год",
        "век",
    }
)


def _is_bare_range_endpoint(
    tokens: Sequence[AnalyzedToken], tok: AnalyzedToken
) -> bool:
    """`tok` is a BARE §82 range endpoint, not a modifier embedded inside a
    larger NP (July 2026 review P3). Two guards:

    - no amod/det dependents of its own — a modified date/period phrase
      ("Первого января — большого праздника") is not a plain endpoint.
    - if `tok` is itself an nmod dependent, its Case must MATCH its head's:
      an apposition-style attachment of a range to a generic container noun
      ("на период январь — март", both Acc) is still a bare endpoint, but a
      genuine genitive modification with a case MISMATCH ("время года",
      Nom—Gen; "месяц года", Nom—Gen — "[noun] OF year") means `tok` is a
      modifier inside a larger NP, not the range endpoint itself. That
      distinguishes the §82 route from the §79 subj-pred dash of "Любимое
      время года — весна." / "Первый месяц года — январь.", where the
      dash-adjacent noun is that genitive modifier.
    """
    if any(t.head_idx == tok.idx and t.dep_rel in ("amod", "det") for t in tokens):
        return False
    if tok.dep_rel == "nmod":
        head = _get_head(tokens, tok)
        if head is not None and head.get_feature("Case") != tok.get_feature("Case"):
            return False
    return True


def _is_connective_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§82 соединительное тире: routes/matches (PROPN—PROPN), ranges
    (NUM—NUM), and temporal-endpoint spans (NOUN—NOUN months/seasons/
    weekdays/day-parts, e.g. "период январь — март"), e.g. "поезд Москва —
    Иркутск". Deleting it is still an error, but it is NOT a §93 apposition
    and a comma there turns a route/range into a list — so it must be
    excluded from dash_apposition / dash_to_comma.
    """
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < len(tokens) else None
    if left is None or right is None:
        return False
    if left.pos == right.pos == "NOUN":
        # Temporal-endpoint route (audit A5): "январь — март", "понедельник
        # — пятница". Both sides must be from the closed lexicon AND be bare
        # range endpoints (P3) — otherwise §79 subj-pred dashes whose
        # subject NP happens to end in a temporal-lexicon genitive
        # modifier ("Любимое время года — весна.") get swallowed here.
        return (
            left.lemma in _TEMPORAL_ENDPOINT_LEMMAS
            and right.lemma in _TEMPORAL_ENDPOINT_LEMMAS
            and _is_bare_range_endpoint(tokens, left)
            and _is_bare_range_endpoint(tokens, right)
        )
    if left.pos != right.pos or left.pos not in ("PROPN", "NUM"):
        return False
    # «столица Исландии — Рейкьявик» is an apposition to the NP head, not a
    # §82 route: a genitive left endpoint disqualifies the route reading
    # («Голицыно — Звенигород» stays connective).
    if left.pos == "PROPN" and left.get_feature("Case") == "Gen":
        return False
    return True


def _has_parallel_pron_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Contrast pattern per §79: parallel pronoun-subject clauses, as in
    "Я — фабрикант, ты — судовладелец" — there the dash IS required."""
    for t in tokens:
        if t.idx == idx or t.pos != "PUNCT" or t.text not in DASH_CHARS:
            continue
        if t.idx == 0:
            continue
        prev = tokens[t.idx - 1]
        if prev.pos == "PRON" and prev.get_feature("PronType") == "Prs":
            return True
    return False


_ESTO_CONNECTOR_LEMMAS = frozenset({"это", "вот"})


def _is_esto_subj_pred_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§79: «Тире ставится перед словами это, это есть, вот, вот значит,
    это значит, присоединяющими сказуемое к подлежащему» — the connector
    configuration is the canonical OBLIGATORY subj-pred dash. All five
    connector variants begin with «это» or «вот», so the first token right
    of the dash decides (bare «значит» is not in the §79 list).

    Guard: the left context must be a subject phrase, not a finite clause —
    in «Дверь открылась — это пришёл отец» the dash joins two clauses
    (§116 asyndetic), not a subject and a predicate.
    """
    n = len(tokens)
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < n else None
    if left is None or right is None:
        return False
    if (right.lemma or right.text).lower() not in _ESTO_CONNECTOR_LEMMAS:
        return False
    # Subject candidate immediately left: nominal, or an infinitive subject
    # («Понять — это счастье», §79 nominative/infinitive combinations).
    left_is_subject = left.pos in ("NOUN", "PROPN", "PRON", "NUM") or (
        left.pos in ("VERB", "AUX") and left.get_feature("VerbForm") == "Inf"
    )
    if not left_is_subject:
        return False
    # No finite verb in the dash's own clause left of the dash → the left
    # side is a subject NP, not a first clause of a БСП. Scan from the last
    # clause boundary, not the sentence start: «..., ведь любовь — это не
    # преступление» has finite verbs only in earlier clauses.
    for t in tokens[_clause_start(tokens, idx) : idx]:
        if t.pos in FINITE_POS and t.get_feature("VerbForm") not in (
            "Part",
            "Conv",
            "Inf",
        ):
            return False
    return True


def _is_apposition_pair(
    tokens: Sequence[AnalyzedToken], open_idx: int, close_idx: int
) -> bool:
    """Dashes at `open_idx`/`close_idx` bound a §93 п.8-в explanatory
    apposition span («Мы — весёлая детвора — шли домой»): the span between
    them is verbless and comma-free, contains a nominal, is anchored to a
    nominal immediately left of the opening dash, and the clause continues
    after the closing dash (a sentence-final dash+NP is the single §93
    п.8-б dash, handled by the appos-arc branch).

    The §79 contrast pattern («Я — фабрикант, ты — судовладелец») has a
    comma + second clause between its two dashes — the no-comma requirement
    excludes it, keeping it dash_subj_pred.
    """
    if open_idx == 0 or close_idx - open_idx < 2:
        return False
    # §82 connective opening (Москва — Казань) is a route, not an apposition.
    if _is_connective_dash(tokens, open_idx):
        return False
    # §79 это/вот connector wins over the paired reading: keep both dashes
    # of «Жизнь — это движение — ...» out of dash_apposition.
    if _is_esto_subj_pred_dash(tokens, open_idx):
        return False
    has_nominal = False
    for i in range(open_idx + 1, close_idx):
        t = tokens[i]
        if t.text == ",":
            return False
        if t.pos in FINITE_POS and t.get_feature("VerbForm") not in (
            "Part",
            "Conv",
            "Inf",
        ):
            return False
        if t.pos in ("NOUN", "PROPN", "PRON"):
            has_nominal = True
    if not has_nominal:
        return False
    # Nominal anchor immediately left of the opening dash.
    if tokens[open_idx - 1].pos not in ("NOUN", "PROPN", "PRON"):
        return False
    # The clause must continue after the closing dash.
    return any(t.idx > close_idx and t.pos != "PUNCT" for t in tokens)


def _paired_apposition_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """The dash at `idx` is the opening or closing dash of a §93 п.8-в
    paired apposition. Detection is structural (POS-based span check against
    the nearest partner dash on each side) rather than arc-based: stanza
    tends to promote the bounded apposition to root with the matrix verb as
    `conj` («детвора» = root, «шли» = conj in «Мы — весёлая детвора — шли
    домой»), so no appos/parataxis arc bridges either dash; when the arc IS
    present, `_appositional_dash_arcs` catches the dash independently.
    """
    dashes = [t.idx for t in tokens if t.pos == "PUNCT" and t.text in DASH_CHARS]
    nxt = next((j for j in dashes if j > idx), None)
    if nxt is not None and _is_apposition_pair(tokens, idx, nxt):
        return True
    prv = next((j for j in reversed(dashes) if j < idx), None)
    return prv is not None and _is_apposition_pair(tokens, prv, idx)


def _is_optional_subj_pred_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """§79 exceptions where the dash is authorial/intonational, so deleting
    it yields normatively CORRECT text (a non-error — must not be generated).
    """
    n = len(tokens)
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < n else None
    if left is None or right is None:
        return False

    # §79: demonstrative subject «это» ("Это — здоровый детина") — the dash
    # is optional emphasis; deletion yields normative text (audit A12).
    # Distinct from the это/вот CONNECTOR («Жизнь — это движение»), where
    # это sits on the RIGHT of the dash and is handled earlier by
    # _is_esto_subj_pred_dash, which always wins first.
    if (left.lemma or left.text).lower() == "это":
        return True

    nominal_left = left.pos in ("NOUN", "PROPN", "PRON")

    # §79: predicate expressed by an adjective/participle (full or short) —
    # the dash is, as a rule, NOT put; its presence marks intonational
    # расчленение only ("Зрачки — кошачьи, длинные"). An amod ADJ is an
    # attributive opening a noun-phrase predicate, not the predicate itself.
    adjectival_right = (right.pos == "ADJ" and right.dep_rel != "amod") or (
        right.pos == "VERB" and right.get_feature("VerbForm") == "Part"
    )
    if nominal_left and adjectival_right:
        return True
    # Same with an adverbial intensifier: "Ночь — очень тёплая."
    if (
        nominal_left
        and right.pos == "ADV"
        and idx + 2 < n
        and tokens[idx + 2].pos == "ADJ"
    ):
        return True

    # §79: personal-pronoun subject — dash is put only при противопоставлении
    # или логическом подчёркивании; otherwise deletion is the norm.
    if (
        left.pos == "PRON"
        and left.get_feature("PronType") == "Prs"
        and right.pos in ("NOUN", "PROPN", "PRON", "ADJ", "DET", "NUM")
        and not _has_parallel_pron_dash(tokens, idx)
    ):
        return True

    return False


def _classify_dash(tokens: Sequence[AnalyzedToken], idx: int) -> str | None:
    """Classify a dash by context. Returns subtype name, or None when the
    dash is not a §79–96 punctuation-rule dash (ranges, direct speech,
    authorial/intonational dashes) so deletion must not be generated."""
    n = len(tokens)
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < n else None

    # Attribution dash of direct speech («..., — сказала Майя») and edge
    # dashes: a dash directly preceded by punctuation is quotation plumbing,
    # not a clause dash.
    if left is None or right is None or left.pos == "PUNCT":
        return None

    # Dashes inside an open quotation span are quotation-internal typography
    # (a title, an embedded quoted phrase), not a Rozental clause dash —
    # skip (audit A4).
    if _inside_unbalanced_quote(tokens, idx):
        return None

    # §82 connective dash — ranges and routes (2004 — 2005, Голицыно —
    # Звенигород). Deleting it is a typography change, not a §79–96
    # punctuation error: skip. Must run before the apposition check because
    # stanza tags "Казань" as appos of "Москва" in "поезд Москва — Казань".
    if _is_connective_dash(tokens, idx):
        return None

    # Clarifying numeric range after the dash («понизить — с 250 метров до
    # 150», «вверх — до 35,75 — 42,75 рубля») — уточнение, not a clause
    # dash; likewise the closing dash of such a range («за семь часов —
    # с 07.00 до 14.00 — выпала...»).
    if right.pos == "ADP" and any(t.pos == "NUM" for t in tokens[idx + 1 : idx + 5]):
        return None
    if left.pos == "NUM" and any(
        t.pos == "PUNCT" and t.text in DASH_CHARS for t in tokens[:idx]
    ):
        return None

    # §80 тире в неполном предложении: the dash's own clause is verbless on
    # both sides, but an earlier parallel clause has a predicate («…могут
    # отдыхать 35 суток, а обычные госслужащие — 30 суток»; «..., а на 90
    # строчке — в самом низу»). A clause opened by a subordinator is СПП
    # («…, что пострадавший — безработный»), not an ellipsis. Must run
    # BEFORE the ADP-adjunct guard below (July 2026 review P4): an ellipsis
    # remainder led by a preposition («в самом низу») was otherwise killed
    # by that guard before ever reaching this check.
    clause_lo = _clause_start(tokens, idx)
    left_clause_pred = _segment_has_predicate(tokens, clause_lo, idx)
    right_any_pred = _segment_has_predicate(tokens, idx + 1, n)
    if (
        clause_lo > 0
        and not left_clause_pred
        and not right_any_pred
        and _segment_has_predicate(tokens, 0, clause_lo - 1)
    ):
        first = next((t for t in tokens[clause_lo:idx] if t.pos != "PUNCT"), None)
        if first is None or not (first.pos == "SCONJ" or first.dep_rel == "mark"):
            return "dash_ellipsis"

    # Authorial adjunct dash before a prepositional phrase with no
    # following predicate («письмо — без лишних слов») — deletion is
    # normative, not an error (audit A11). The numeric-range guards above
    # must run first so genuine ranges ("вверх — до 35,75 — 42,75 рубля")
    # are still covered before this broader ADP check, and the ellipsis
    # check above must ALSO run first so it can still claim ellipsis sites
    # with a preposition-led remainder («в самом низу») — this guard keeps
    # protecting the non-ellipsis case («clause_lo == 0»).
    if right.pos == "ADP" and not _segment_has_predicate(tokens, idx + 1, n):
        return None

    # §79 это/вот predicate connector («Мир — это счастье») — the canonical
    # obligatory subj-pred dash. Must run before the surface-pattern checks:
    # «это» is PRON, so the right-side nominal check below misses it and the
    # dash would leak into dash_other. It also overrides the §79 exception
    # list — the pronoun-subject/adjectival-predicate exceptions cover the
    # bare predicate, not the connector: with это/вот the dash stays
    # required even for «Мы — это будущее страны».
    if _is_esto_subj_pred_dash(tokens, idx):
        return "dash_subj_pred"

    # §93 п.8-в paired dashes bounding an explanatory apposition
    # («Мы — весёлая детвора — шли домой»): deleting only ONE of the two
    # framing dashes mangles the construction, so — unlike a single
    # sentence-final apposition dash (still caught by
    # _appositional_dash_arcs below) — neither dash of a genuine pair may be
    # generated as an error (audit A3). Must run before the subj_pred/
    # contrast logic: the opening dash otherwise matches the surface
    # nominal—NP pattern (or the §79 pronoun-subject exception) and gets
    # mislabeled, and the closing dash surface-matches asyndetic.
    if _paired_apposition_dash(tokens, idx):
        return None

    # Apposition dash (Rozental §93): appos or parataxis arc with both
    # nominal endpoints spans the dash. Must check BEFORE subj_pred because
    # "Соляник — государственный памятник" matches the surface NOUN—ADJ
    # pattern of subj_pred but is structurally an apposition.
    if _appositional_dash_arcs(tokens, idx):
        return "dash_apposition"

    # §79 «значит» connector with an infinitive subject («Понять — значит
    # простить») — the same obligatory subj-pred connector family as
    # это/вот, just with the bare word (audit A9). Compares surface text,
    # not lemma: stanza lemmatizes this discourse-particle use of «значит»
    # to the verb infinitive «значить», so a lemma check would miss it.
    # Must run before the §79 exceptions below: an infinitive left side
    # never matches those anyway.
    if (
        right.text.lower() == "значит"
        and left.pos in ("VERB", "AUX")
        and left.get_feature("VerbForm") == "Inf"
    ):
        return "dash_subj_pred"

    # §79 exceptions: dash deletion yields normative text — skip entirely.
    if _is_optional_subj_pred_dash(tokens, idx):
        return None

    # right_end/right_main_pred/left_any_pred feed only the branches below
    # (subj-pred, asyndetic); clause_lo/left_clause_pred/right_any_pred were
    # already computed above for the §80 ellipsis check (P4) and are reused
    # here as-is.
    right_end = next(
        (
            t.idx
            for t in tokens[idx + 1 :]
            if t.pos == "PUNCT" and (t.text == "," or t.text in DASH_CHARS)
        ),
        n,
    )
    right_main_pred = _segment_has_predicate(tokens, idx + 1, right_end)
    left_any_pred = _segment_has_predicate(tokens, 0, idx)

    # Subject–predicate dash, restricted to the §79 obligatory
    # configurations: nominal — nominal/NUM (an amod/det right neighbor is
    # resolved to its NP head), and Inf — Inf. The §79 dash replaces a
    # copula, so neither side of it may already have a predicate («запускает
    # этим летом — авиакомпанию…» is not subj—pred).
    if not left_clause_pred and not right_main_pred:
        left_ok = left.pos in ("NOUN", "PRON", "PROPN")
        right_eff = right
        if right.pos in ("ADJ", "DET") and right.dep_rel in ("amod", "det"):
            head = _get_head(tokens, right)
            if head is not None and head.idx > idx:
                right_eff = head
        right_ok = right_eff.pos in ("NOUN", "NUM", "PROPN")
        if left_ok and right_ok:
            return "dash_subj_pred"
        # Inf — Inf ("О решённом говорить — только путать")
        if (
            left.pos in ("VERB", "AUX")
            and left.get_feature("VerbForm") == "Inf"
            and right.pos in ("VERB", "AUX")
            and right.get_feature("VerbForm") == "Inf"
        ):
            return "dash_subj_pred"

    # §116–118 БСП: full clauses (predicates) on both sides of the dash
    # («Сергей поднял глаза — такой фразы он не слышал никогда»).
    if left_any_pred and right_any_pred:
        return "dash_asyndetic"

    # Authorial/intonational dash right after a finite verb with no clause
    # following («формируется — арендный план») — deletion is normative.
    if _is_predicate_token(left) and not right_any_pred:
        return None

    return "dash_other"


# ── Handlers ────────────────────────────────────────────────────────────────


class CommaDeleteHandler(WeightedSubtypeMixin):
    """Delete a comma with L2 subtype classification.

    Classification is deterministic (the comma's context decides the
    subtype), so subtype weights act as enable gates rather than sampling
    weights: a preset that zeroes a subtype (e.g. lorugec zeroes
    comma_asyndetic/comma_vocative — not LoRuGEC rules) makes apply()
    return None for commas classifying into it, instead of leaking them
    under the nearest listed label.
    """

    name = "comma_delete"
    subtypes = [
        "comma_subordinate",
        "comma_compound",
        "comma_parenthetical",
        "comma_isolation",
        "comma_homogeneous",
        "comma_interjection",
        "comma_response",
        "comma_repeated",
        "comma_asyndetic",
        "comma_vocative",
    ]
    category = "PUNCT"
    changes_length = True

    DEFAULT_WEIGHTS = {
        "comma_subordinate": 25,
        "comma_compound": 15,
        "comma_parenthetical": 15,
        "comma_isolation": 12,
        "comma_homogeneous": 15,
        "comma_interjection": 5,
        "comma_response": 4,
        "comma_repeated": 5,
        "comma_asyndetic": 8,  # §116 БСП
        "comma_vocative": 5,  # §101 обращения
    }

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        if tokens[idx].pos != "PUNCT" or tokens[idx].text != ",":
            return False
        # §108 split compound conjunction ("после того, как…"): deleting
        # just this comma yields the equally-normative unsplit variant, so
        # it must never be generated as a standalone comma_delete error
        # (audit A16).
        return not _is_split_conjunction_comma(tokens, idx)

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if idx == 0 or tokens[idx].text != ",":
            return None

        if _is_split_conjunction_comma(tokens, idx):
            return None

        subtype = _classify_comma(tokens, idx)

        if self._enabled_subtypes is not None:
            # Explicit targeting (CLI :subtype / SFT) overrides weight gates.
            if subtype not in self._enabled_subtypes:
                return None
        elif self._weights.get(subtype, 0) <= 0:
            # Subtype zeroed by the preset → skip rather than mislabel.
            return None

        del sentence[idx]

        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=",",
            corrupted="",
            fix_tag="$APPEND_,",
        )


class DashDeleteHandler(WeightedSubtypeMixin):
    """Delete a dash (em/en) with L2 subtype classification."""

    name = "dash_delete"
    subtypes = [
        "dash_subj_pred",
        "dash_asyndetic",
        "dash_apposition",
        "dash_ellipsis",
        "dash_other",
    ]
    category = "PUNCT"
    changes_length = True

    # Classification is deterministic, so weights act as enable gates
    # (same as CommaDeleteHandler); relative magnitudes are documentation.
    DEFAULT_WEIGHTS = {
        "dash_subj_pred": 25,
        "dash_asyndetic": 25,
        "dash_apposition": 25,
        "dash_ellipsis": 15,
        "dash_other": 25,
    }

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        if tokens[idx].pos != "PUNCT" or tokens[idx].text not in DASH_CHARS:
            return False
        # None = §79 optional/authorial dash; deletion would be a non-error.
        return _classify_dash(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if idx == 0 or tokens[idx].text not in DASH_CHARS:
            return None

        subtype = _classify_dash(tokens, idx)
        if subtype is None:
            return None

        if self._enabled_subtypes is not None:
            # Explicit targeting (CLI :subtype / SFT) overrides weight gates.
            if subtype not in self._enabled_subtypes:
                return None
        elif self._weights.get(subtype, 0) <= 0:
            # Subtype zeroed by the preset → skip rather than mislabel.
            return None

        dash_char = sentence[idx]
        del sentence[idx]

        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx - 1,
            end_idx=idx - 1,
            original=dash_char,
            corrupted="",
            fix_tag=f"$APPEND_{dash_char}",
        )


_APPOS_DEPRELS = frozenset({"appos", "parataxis"})


def _is_elided_parallel_series(
    tokens: Sequence[AnalyzedToken], head: AnalyzedToken
) -> bool:
    """`head` is itself an `appos` dependent AND its own head (the
    grandparent) is the subject of a verb that is itself coordinated
    (`conj`) with an earlier verb — the signature of a parallel-clause
    series with an elided final predicate ("серебро завоевал Игорь
    Чарторыйский, бронзу — Юрий Гейзенблас": each position gets
    appos-chained to the previous one by stanza because the repeated verb
    is dropped). That is a §80 ellipsis, not a genuine nested apposition
    like "Лиги чемпионов УЕФА «Зенит»" (whose head is not itself the
    subject of a coordinated verb).
    """
    if head.dep_rel != "appos" or head.head_idx is None:
        return False
    gp_idx = head.head_idx
    if not (0 <= gp_idx < len(tokens)):
        return False
    return any(
        t.dep_rel in ("nsubj", "nsubj:pass")
        and t.idx == gp_idx
        and t.head_idx is not None
        and 0 <= t.head_idx < len(tokens)
        and tokens[t.head_idx].dep_rel == "conj"
        for t in tokens
    )


def _appositional_dash_arcs(
    tokens: Sequence[AnalyzedToken], idx: int
) -> list[AnalyzedToken]:
    """Appos/parataxis dependents whose arc bridges the dash at `idx`.

    Stanza's Russian model uses either `appos` (inline apposition) or
    `parataxis` (loose paratactic apposition, especially after dash) for
    Rozental §93 constructions. We accept both, but require both endpoints
    to be nominal (NOUN/PROPN/PRON) to avoid catching parataxis on
    interjections or sentence-level discourse markers. §82 connective arcs
    (PROPN—PROPN routes/matches, NUM—NUM ranges) are excluded — they are
    not appositions. `_is_elided_parallel_series` excludes the specific
    elided-verb-series misparse described above.
    """
    nominal_pos = ("NOUN", "PROPN", "PRON")
    arcs: list[AnalyzedToken] = []
    if _is_connective_dash(tokens, idx):
        return arcs
    for t in tokens:
        if t.dep_rel not in _APPOS_DEPRELS or t.head_idx is None:
            continue
        head_idx = t.head_idx
        if not (0 <= head_idx < len(tokens)):
            continue
        head = tokens[head_idx]
        if t.pos not in nominal_pos or head.pos not in nominal_pos:
            continue
        # §82: соединительное тире between two proper names is a route/match
        # designation, not an apposition.
        if t.pos == "PROPN" and head.pos == "PROPN":
            continue
        if not ((head_idx < idx < t.idx) or (t.idx < idx < head_idx)):
            continue
        if _is_elided_parallel_series(tokens, head):
            continue
        arcs.append(t)
    return arcs


class DashToCommaHandler(SubtypeGateMixin):
    """Replace dash with comma — Rozental §93 apposition L1 error pattern.

    Many L1 errors substitute a comma for the required dash around an
    apposition (e.g., "Самой глубокой является пещера Соляник —
    государственный памятник природы" → "...Соляник, государственный...").
    This handler produces that error by detecting appositional dashes via
    the `appos` dep arc and substituting them with commas.
    """

    name = "dash_to_comma"
    subtypes = ["dash_to_comma_apposition"]
    category = "PUNCT"
    changes_length = False

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        tok = tokens[idx]
        if tok.pos != "PUNCT" or tok.text not in DASH_CHARS:
            return False
        # §93 п.1–2: comma is the sanctioned BASE marking for обособленные
        # приложения, so dash→comma mid-sentence is a non-error. Only the
        # sentence-final apposition (§93 п.8 б — "Я не слишком люблю это
        # дерево — осину") has тире as the standard marking; restrict to it.
        n = len(tokens)
        for arc in _appositional_dash_arcs(tokens, idx):
            head = tokens[arc.head_idx] if arc.head_idx is not None else arc
            right_node = arc if arc.idx > idx else head
            _, span_right = _get_subtree_span(tokens, right_node.idx)
            if all(tokens[j].pos == "PUNCT" for j in range(span_right + 1, n)):
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
        if not self.can_apply(tokens, idx):
            return None

        subtype = "dash_to_comma_apposition"
        if self._enabled_subtypes is not None and subtype not in self._enabled_subtypes:
            return None

        dash_char = sentence[idx]
        sentence[idx] = ","
        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx,
            end_idx=idx,
            original=dash_char,
            corrupted=",",
            fix_tag=f"$REPLACE_{dash_char}",
        )


# =============================================================================
# comma_to_dash — spurious dash at a §116 asyndetic comma junction
# =============================================================================

# §117 п.2 / §118 п.7: a speech/perception/cognition predicate in the first
# clause licenses colon (classically) or dash (изъяснительное) — those
# junctions are not clean comma-only sites. Extends SPEECH_VERB_LEMMAS.
_BSP_COGNITION_LEMMAS = frozenset(
    {
        "видеть",
        "увидеть",
        "смотреть",
        "посмотреть",
        "глядеть",
        "слышать",
        "услышать",
        "понимать",
        "понять",
        "узнать",
        "узнавать",
        "чувствовать",
        "почувствовать",
        "думать",
        "подумать",
        "полагать",
        "считать",
        "посчитать",
        "казаться",
        "показаться",
        "замечать",
        "заметить",
        "помнить",
        "вспомнить",
        "знать",
        # attribution verbs common in news prose (SPEECH_VERB_LEMMAS misses
        # these; first review pass leaked «указал»/«полагают» junctions)
        "указывать",
        "указать",
        "подчеркивать",
        "подчеркнуть",
        "добавлять",
        "добавить",
        "отвечать",
        "ответить",
        "рассказывать",
        "рассказать",
        "напоминать",
        "напомнить",
    }
)

# closing quotes: a comma right after direct speech is the «П», — а
# attribution frame, where the DASH is the correct mark (§ прямая речь)
_BSP_CLOSING_QUOTES = frozenset({"»", '"', "'", "“", "”", "„"})

# §118 п.8 / п.3: a second clause opening with a connective pronoun
# (присоединительное) or a consequence connective (следствие) is exactly
# where the dash IS correct or defensible. «при этом» is caught as a
# bigram in can_apply.
_BSP_CLAUSE2_OPENER_SKIP = frozenset(
    {
        "это",
        "так",
        "таков",
        "такова",
        "таково",
        "таковы",
        "поэтому",
        "значит",
        "следовательно",
        "тогда",
        "однако",
        "зато",
        "впрочем",
    }
)


class CommaToDashHandler(SubtypeGateMixin):
    """Replace the §116 asyndetic comma with a spurious dash.

    Insert-direction mirror of ``dash_delete:dash_asyndetic`` (v5
    bidirectional design): the delete side trains the model to ADD a
    §118 dash; this side trains it to REMOVE a dash from a junction
    where §116 wants a comma («День был серый — небо висело низко»).

    The precision problem is that §118 licenses a dash at the same
    surface shape under dynamic readings (быстрая смена, следствие,
    условие/время, сравнение, изъяснение, присоединение). Those are
    excluded structurally rather than semantically:

    - both clause predicates must be imperfective past/present verbs, or
      copular predicates without a future copula — §118 п.1/3/4/5
      readings ride perfective or future dynamics («Ударил гром —
      задрожали окна», «Будет дождик — будут и грибки»);
    - both clauses need overt subjects — subjectless first clauses are
      the condition/time/comparison shapes of §118 п.4–6 («Победим —…»,
      «Молвит слово —…»);
    - a speech/perception/cognition first predicate is §117 п.2/§118 п.7
      territory (colon/dash licensed) — skipped;
    - a second clause carrying negation is the §118 п.2 contrast shape
      («шныряли по лесу — нет зверя») — skipped on any не/нет in the
      clause (accepted risk: overbroad, drops some valid §116 sites —
      skip > mislabel);
    - a second clause opening with это/так/таков is §118 п.8 — skipped.

    What survives is the §116 descriptive core: two stative clauses in
    tight semantic linkage, where the dash is a clean intonation error.
    """

    name = "comma_to_dash"
    subtypes = ["comma_to_dash_asyndetic"]
    category = "PUNCT"
    changes_length = False

    @staticmethod
    def _predicate_is_stative(
        tokens: Sequence[AnalyzedToken], pred: AnalyzedToken
    ) -> bool:
        """Imperfective past/present verb, or copular predicate with a
        non-future (or absent) copula."""
        if pred.pos in FINITE_POS:
            if pred.get_feature("Aspect") != "Imp":
                return False
            return pred.get_feature("Tense") in ("Past", "Pres")
        # nominal/adjectival predicate: reject only a future copula (§118 п.5)
        for t in tokens:
            if t.head_idx == pred.idx and t.dep_rel == "cop":
                if t.get_feature("Tense") == "Fut":
                    return False
        return True

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0 or idx >= len(tokens) - 1:
            return False
        tok = tokens[idx]
        if tok.pos != "PUNCT" or tok.text != ",":
            return False
        # direct-speech attribution («П», — а): the dash after the closing
        # quote is CORRECT — never corrupt that junction
        if tokens[idx - 1].text in _BSP_CLOSING_QUOTES:
            return False
        if _classify_comma(tokens, idx) != "comma_asyndetic":
            return False
        if tok.head_idx is None or not (0 <= tok.head_idx < len(tokens)):
            return False
        second = tokens[tok.head_idx]
        first = _get_head(tokens, second)
        if first is None:
            return False
        if not _has_own_subject(tokens, first.idx) or not _has_own_subject(
            tokens, second.idx
        ):
            return False
        if not self._predicate_is_stative(tokens, first):
            return False
        if not self._predicate_is_stative(tokens, second):
            return False
        # §117 п.2/§118 п.7: any speech/cognition verb BEFORE the junction —
        # not just the first clause's head — signals the изъяснительное
        # frame («полагают, что достаточно X, АОК требует больше»: the
        # embedding verb governs the whole left context). Overbroad on
        # attribution-heavy news prose by design: skip > mislabel.
        for j in range(idx):
            lem = (tokens[j].lemma or "").lower()
            if lem in SPEECH_VERB_LEMMAS or lem in _BSP_COGNITION_LEMMAS:
                return False
        # ...and a speech/cognition SECOND predicate is the quoteless
        # «П, — а» attribution frame («недоказуем, — замечает корреспондент»)
        # where the dash is correct
        second_lemma = (second.lemma or "").lower()
        if second_lemma in SPEECH_VERB_LEMMAS or second_lemma in _BSP_COGNITION_LEMMAS:
            return False
        # §118 п.2 contrast rides negation on EITHER side of the junction
        # («сведений нет — однако…», «шныряли — нет зверя»); whole-sentence
        # scan, deliberately overbroad
        if any(t.text.lower() in ("не", "нет") for t in tokens):
            return False
        # clause 2 = comma to the end of the second predicate's subtree
        _, second_hi = _get_subtree_span(tokens, second.idx)
        opener_seen = False
        for j in range(idx + 1, min(second_hi + 1, len(tokens))):
            t_lower = tokens[j].text.lower()
            if not opener_seen and tokens[j].pos != "PUNCT":
                if t_lower in _BSP_CLAUSE2_OPENER_SKIP:
                    return False
                # «при этом» — §118 п.8-adjacent connective, caught as bigram
                if (
                    t_lower == "при"
                    and j + 1 < len(tokens)
                    and tokens[j + 1].text.lower() == "этом"
                ):
                    return False
                opener_seen = True
        return True

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if not self.can_apply(tokens, idx):
            return None

        subtype = "comma_to_dash_asyndetic"
        if self._enabled_subtypes is not None and subtype not in self._enabled_subtypes:
            return None

        sentence[idx] = "—"
        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx,
            end_idx=idx,
            original=",",
            corrupted="—",
            fix_tag="$REPLACE_,",
        )


class CommaPairDeleteHandler(SubtypeGateMixin):
    """Delete both commas of a paired construction (обособление).

    Detects constructions where two commas share the same dep-tree head:
    причастный оборот (acl), деепричастный оборот (advcl+Conv),
    relative clause (acl:relcl), parenthetical (parataxis), apposition (appos).

    Only triggers on the FIRST comma of a pair to avoid double processing.
    """

    name = "comma_pair_delete"
    subtypes = [
        "pair_participle",
        "pair_relative",
        "pair_gerund",
        "pair_parenthetical",
        "pair_apposition",
    ]
    category = "PUNCT"
    changes_length = True

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        tok = tokens[idx]
        if tok.pos != "PUNCT" or tok.text != ",":
            return False
        return _find_comma_partner(tokens, idx) is not None

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        if idx == 0 or tokens[idx].text != ",":
            return None

        pair = _find_comma_partner(tokens, idx)
        if pair is None:
            return None

        partner_idx, subtype = pair

        if self._enabled_subtypes is not None and subtype not in self._enabled_subtypes:
            return None

        # Two-comma pair: delete partner first (higher index) to
        # preserve `idx` while modifying the list.
        del sentence[partner_idx]
        del sentence[idx]
        return ErrorResult(
            error_type=subtype,
            category=self.category,
            start_idx=idx - 1,
            end_idx=partner_idx - 1,
            original=", ... ,",
            corrupted="...",
            fix_tag="$APPEND_,",
        )
