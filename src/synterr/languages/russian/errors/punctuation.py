"""Russian punctuation error handlers — comma and dash deletion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from synterr.core.protocol import ErrorResult

if TYPE_CHECKING:
    from collections.abc import Sequence
    from random import Random

    from synterr.core.protocol import AnalyzedToken

# ── Comma classification data ───────────────────────────────────────────────

SUBORDINATE_CONJUNCTIONS = frozenset({
    "что", "чтобы", "когда", "если", "потому", "хотя", "пока", "как",
    "чем", "ибо", "поскольку", "пускай", "будто", "словно", "точно",
    "раз", "лишь", "едва", "прежде", "который", "где", "куда", "откуда",
    "пока", "после", "перед",
})

COMPOUND_CONJUNCTIONS = frozenset({
    "и", "а", "но", "или", "да", "однако", "зато", "же", "либо",
})

PARENTHETICAL_WORDS = frozenset({
    "конечно", "вероятно", "возможно", "видимо", "очевидно",
    "кажется", "пожалуй", "впрочем", "кстати", "наконец",
    "наоборот", "например", "напротив", "следовательно",
    "безусловно", "несомненно", "разумеется", "действительно",
    "правда", "наверное", "значит", "итак", "словом",
    "короче", "допустим", "предположим", "скажем",
})

FINITE_POS = frozenset({"VERB", "AUX"})

DASH_CHARS = frozenset({"—", "–", "--"})


# ── Dep-tree helpers ─────────────────────────────────────────────────────────

ISOLATION_DEPRELS = frozenset({"acl", "acl:relcl", "advcl"})
CLAUSE_DEPRELS = frozenset({"ccomp", "advcl", "csubj", "csubj:pass"})


def _get_head(tokens: Sequence[AnalyzedToken], tok: AnalyzedToken) -> AnalyzedToken | None:
    """Follow head_idx to get the head token."""
    if tok.head_idx is not None and 0 <= tok.head_idx < len(tokens):
        return tokens[tok.head_idx]
    return None


def _has_own_subject(tokens: Sequence[AnalyzedToken], verb_idx: int) -> bool:
    """Check if a verb has its own nsubj/nsubj:pass dependent."""
    return any(
        t.head_idx == verb_idx and t.dep_rel in ("nsubj", "nsubj:pass")
        for t in tokens
    )


def _get_subtree_span(tokens: Sequence[AnalyzedToken], root_idx: int) -> tuple[int, int]:
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
            if (comma_head.pos in FINITE_POS
                    and conj_head is not None and conj_head.pos in FINITE_POS
                    and _has_own_subject(tokens, comma_head.idx)):
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
    # ends just before this comma
    if right is not None:
        for i in range(max(0, idx - 15), idx):
            t = tokens[i]
            if t.dep_rel in ISOLATION_DEPRELS:
                _, subtree_max = _get_subtree_span(tokens, t.idx)
                # Comma sits right after the subtree → closing comma
                if subtree_max == idx - 1:
                    return "comma_isolation"

    # Homogeneous: left and right share the same head (conj siblings)
    if left and right and left.head_idx is not None and right.head_idx is not None:
        if left.head_idx == right.head_idx:
            return "comma_homogeneous"
        # One is conj of the other
        if left.head_idx == right.idx or right.head_idx == left.idx:
            return "comma_homogeneous"

    # ── 3. Fallback ──────────────────────────────────────────────────────
    return "comma_homogeneous"


def _classify_dash(tokens: Sequence[AnalyzedToken], idx: int) -> str:
    """Classify a dash by context. Returns subtype name."""
    n = len(tokens)
    left = tokens[idx - 1] if idx > 0 else None
    right = tokens[idx + 1] if idx + 1 < n else None

    # Subject–predicate dash: NOUN/PRON — NOUN/ADJ/NUM
    if left and right:
        left_ok = left.pos in ("NOUN", "PRON", "PROPN")
        right_ok = right.pos in ("NOUN", "ADJ", "NUM", "VERB", "PROPN")
        if left_ok and right_ok:
            return "dash_subj_pred"

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
    ]
    category = "PUNCT"
    changes_length = True

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
        "dash_other",
    ]
    category = "PUNCT"
    changes_length = True

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
