"""Russian punctuation error handlers — comma and dash deletion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# ── Comma classification data ───────────────────────────────────────────────

SUBORDINATE_CONJUNCTIONS = frozenset(
    {
        "что",
        "чтобы",
        "когда",
        "если",
        "потому",
        "хотя",
        "пока",
        "как",
        "чем",
        "ибо",
        "поскольку",
        "пускай",
        "будто",
        "словно",
        "точно",
        "раз",
        "лишь",
        "едва",
        "прежде",
        "который",
        "где",
        "куда",
        "откуда",
        "после",
        "перед",
    }
)

COMPOUND_CONJUNCTIONS = frozenset(
    {
        "и",
        "а",
        "но",
        "или",
        "да",
        "однако",
        "зато",
        "же",
        "либо",
    }
)

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
        "наконец",
        "наоборот",
        "например",
        "напротив",
        "следовательно",
        "безусловно",
        "несомненно",
        "разумеется",
        "действительно",
        "правда",
        "наверное",
        "значит",
        "итак",
        "словом",
        "короче",
        "допустим",
        "предположим",
        "скажем",
    }
)

# §103 — affirmative / negative / response words; comma typically follows
# when they open a turn or response.
RESPONSE_WORDS = frozenset({"да", "нет"})

# §90 — repeated content-word POS classes that take commas between repetitions
REPEATED_CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV"})

FINITE_POS = frozenset({"VERB", "AUX"})

DASH_CHARS = frozenset({"—", "–", "--"})


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


def _find_comma_partner(
    tokens: Sequence[AnalyzedToken], idx: int
) -> tuple[int | None, str] | None:
    """Detect an isolation construction whose boundary comma is at `idx`.

    Returns (partner_idx_or_None, subtype) or None.

    `partner_idx is None` indicates a sentence-boundary case: the
    construction's phrase touches the sentence edge so only ONE comma exists
    (e.g., "Высушенные, они..." has only a closing comma).

    Approach: iterate over every token whose dep_rel is in PAIR_DEPRELS,
    compute its non-punct subtree span, and check whether `idx` is one of
    the phrase's boundary commas (immediately left or right of the span).
    This is robust to stanza's habit of attaching opening and closing
    commas of a pair to different heads in complex sentences.

    Triggers only at the LEFTMOST boundary comma of the construction.
    """
    comma = tokens[idx]
    if comma.text != "," or comma.pos != "PUNCT":
        return None

    n = len(tokens)
    for head in tokens:
        if head.dep_rel not in PAIR_DEPRELS:
            continue
        # advcl: only the gerund form (VerbForm=Conv) is a pair construction.
        # Full subord clauses (VerbForm=Fin) belong to single comma_delete.
        if head.dep_rel == "advcl" and head.get_feature("VerbForm") != "Conv":
            continue

        span_left, span_right = _get_subtree_span(tokens, head.idx)

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

        subtype = PAIR_DEPRELS[head.dep_rel]

        if left_comma_idx is not None and idx == left_comma_idx:
            return (right_comma_idx, subtype)
        if (
            left_comma_idx is None
            and right_comma_idx is not None
            and idx == right_comma_idx
        ):
            return (None, subtype)

    return None


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

    # §102 — Interjection: INTJ neighbor is a strong signal
    if (left and left.pos == "INTJ") or (right and right.pos == "INTJ"):
        return "comma_interjection"

    # §103 — Affirmative/negative response at sentence start
    if left and left.idx == 0 and left.lemma in RESPONSE_WORDS:
        return "comma_response"

    # §90 — Repeated word: same lemma + same content-POS on both sides
    if (
        left
        and right
        and left.pos == right.pos
        and left.pos in REPEATED_CONTENT_POS
        and left.lemma == right.lemma
    ):
        return "comma_repeated"

    # ── 1. Dep-tree based classification (when head info available) ──────

    if comma_head is not None:
        # Parenthetical: comma's head has dep_rel=parataxis or discourse
        if comma_head.dep_rel in ("parataxis", "discourse"):
            return "comma_parenthetical"

        # Isolation: comma's head is an acl/acl:relcl/advcl node
        if comma_head.dep_rel in ISOLATION_DEPRELS:
            return "comma_isolation"

        # Subordinate/compound: comma's head is a conj or clausal node
        if comma_head.dep_rel == "conj":
            # conj linking two clauses (both have subjects) → compound
            conj_head = _get_head(tokens, comma_head)
            if (
                comma_head.pos in FINITE_POS
                and conj_head is not None
                and conj_head.pos in FINITE_POS
                and _has_own_subject(tokens, comma_head.idx)
            ):
                return "comma_compound"
            # conj linking non-clausal items → homogeneous
            return "comma_homogeneous"

        # Comma head is a clausal complement (ccomp/advcl) → subordinate
        if comma_head.dep_rel in CLAUSE_DEPRELS:
            return "comma_subordinate"

    # ── 2. POS/lemma fallbacks (when dep tree is absent or unhelpful) ────

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
            return "comma_isolation"
        if neighbor.get_feature("VerbForm") in ("Part", "Conv"):
            return "comma_isolation"

    # Isolation: closing comma — scan left for a participle whose subtree
    # ends just before this comma (allow gap of 1-2 for skipped PUNCT tokens)
    if right is not None:
        for i in range(max(0, idx - 15), idx):
            t = tokens[i]
            if t.dep_rel in ISOLATION_DEPRELS:
                _, subtree_max = _get_subtree_span(tokens, t.idx)
                gap = idx - 1 - subtree_max
                if 0 <= gap <= 2:
                    return "comma_isolation"

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
                if 0 <= gap <= 2:
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


def _classify_dash(tokens: Sequence[AnalyzedToken], idx: int) -> str:
    """Classify a dash by context. Returns subtype name."""
    n = len(tokens)
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < n else None

    # Apposition dash (Rozental §93): appos or parataxis arc with both
    # nominal endpoints spans the dash. Must check BEFORE subj_pred because
    # "Соляник — государственный памятник" matches the surface NOUN—ADJ
    # pattern of subj_pred but is structurally an apposition.
    if _is_appositional_dash(tokens, idx):
        return "dash_apposition"

    # Subject–predicate dash: NOUN/PRON — NOUN/ADJ/NUM
    if left and right:
        left_ok = left.pos in ("NOUN", "PRON", "PROPN")
        right_ok = right.pos in ("NOUN", "ADJ", "NUM", "PROPN")
        if left_ok and right_ok:
            return "dash_subj_pred"

    # Asyndetic dash: immediate neighbors are finite verbs or clause-final/initial
    # Rozental §116-118: бессоюзное сложное предложение
    # Heuristic: left neighbor is VERB (clause end) or right neighbor is VERB (clause start)
    if left and right:
        left_is_verb = left.pos in ("VERB", "AUX") and left.get_feature(
            "VerbForm"
        ) not in ("Part", "Conv", "Inf")
        right_is_verb = right.pos in ("VERB", "AUX") and right.get_feature(
            "VerbForm"
        ) not in ("Part", "Conv", "Inf")
        # At least one side is a finite verb — strong signal for asyndetic
        if left_is_verb or right_is_verb:
            return "dash_asyndetic"

    return "dash_other"


# ── Handlers ────────────────────────────────────────────────────────────────


class CommaDeleteHandler:
    """Delete a comma with L2 subtype classification."""

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
    ]
    category = "PUNCT"
    changes_length = True

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        """Restrict to specific subtypes (used by targeted SFT / CLI :subtype).

        When set, apply() returns None for commas that classify into any
        subtype not in this set — letting the pipeline try the next comma
        instead of producing a mislabeled error.
        """
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        return tokens[idx].pos == "PUNCT" and tokens[idx].text == ","

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

        subtype = _classify_comma(tokens, idx)

        if self._enabled_subtypes is not None and subtype not in self._enabled_subtypes:
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


class DashDeleteHandler:
    """Delete a dash (em/en) with L2 subtype classification."""

    name = "dash_delete"
    subtypes = [
        "dash_subj_pred",
        "dash_asyndetic",
        "dash_apposition",
        "dash_other",
    ]
    category = "PUNCT"
    changes_length = True

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        return tokens[idx].pos == "PUNCT" and tokens[idx].text in DASH_CHARS

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

        if self._enabled_subtypes is not None and subtype not in self._enabled_subtypes:
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


def _is_appositional_dash(tokens: Sequence[AnalyzedToken], idx: int) -> bool:
    """Whether a dash at `idx` bridges an appositional construction.

    Stanza's Russian model uses either `appos` (inline apposition) or
    `parataxis` (loose paratactic apposition, especially after dash) for
    Rozental §93 constructions. We accept both, but require both endpoints
    to be nominal (NOUN/PROPN/PRON) to avoid catching parataxis on
    interjections or sentence-level discourse markers.
    """
    nominal_pos = ("NOUN", "PROPN", "PRON")
    for t in tokens:
        if t.dep_rel not in _APPOS_DEPRELS or t.head_idx is None:
            continue
        head_idx = t.head_idx
        if not (0 <= head_idx < len(tokens)):
            continue
        head = tokens[head_idx]
        if t.pos not in nominal_pos or head.pos not in nominal_pos:
            continue
        if (head_idx < idx < t.idx) or (t.idx < idx < head_idx):
            return True
    return False


class DashToCommaHandler:
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

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        if idx == 0:
            return False
        tok = tokens[idx]
        if tok.pos != "PUNCT" or tok.text not in DASH_CHARS:
            return False
        return _is_appositional_dash(tokens, idx)

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


class CommaPairDeleteHandler:
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

    def __init__(self) -> None:
        self._enabled_subtypes: set[str] | None = None

    def set_enabled_subtypes(self, subtypes: set[str] | None) -> None:
        if subtypes is not None:
            invalid = subtypes - set(self.subtypes)
            if invalid:
                raise ValueError(f"Unknown subtypes: {invalid}. Valid: {self.subtypes}")
        self._enabled_subtypes = subtypes

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

        if partner_idx is None:
            # Sentence-boundary single-comma case (phrase at sentence start
            # has no opening comma; trigger comma here is the closing one).
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

        # Standard two-comma pair: delete partner first (higher index) to
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
