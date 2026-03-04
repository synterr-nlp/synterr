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


# ── Helpers ─────────────────────────────────────────────────────────────────

def _has_finite_verb(tokens: Sequence[AnalyzedToken], start: int, end: int) -> bool:
    """Check if a finite verb exists in tokens[start:end]."""
    for i in range(max(0, start), min(end, len(tokens))):
        tok = tokens[i]
        if tok.pos in FINITE_POS and tok.get_feature("VerbForm") != "Conv":
            return True
    return False


def _classify_comma(tokens: Sequence[AnalyzedToken], idx: int) -> str:
    """Classify a comma by syntactic context. Returns subtype name.

    Priority: subordinate > compound > parenthetical > isolation > homogeneous.
    """
    n = len(tokens)

    # Look at the token after the comma
    right = tokens[idx + 1] if idx + 1 < n else None
    left = tokens[idx - 1] if idx > 0 else None

    # 1. Subordinate clause: comma before SCONJ
    if right and right.pos == "SCONJ" and right.lemma in SUBORDINATE_CONJUNCTIONS:
        return "comma_subordinate"

    # Also check: comma after subordinate clause (SCONJ is to the left somewhere)
    if right and right.pos == "SCONJ":
        return "comma_subordinate"

    # 2. Compound sentence: comma before CCONJ with finite verbs on both sides
    if right and right.pos == "CCONJ" and right.lemma in COMPOUND_CONJUNCTIONS:
        if _has_finite_verb(tokens, 0, idx) and _has_finite_verb(tokens, idx + 1, n):
            return "comma_compound"

    # 3. Parenthetical word adjacent to comma
    if right and right.lemma in PARENTHETICAL_WORDS:
        return "comma_parenthetical"
    if left and left.lemma in PARENTHETICAL_WORDS:
        return "comma_parenthetical"

    # 4. Isolation: participial/gerund phrases, relative clauses
    # Check immediate neighbors for dep_rel
    if right and right.dep_rel in ("acl", "acl:relcl", "advcl"):
        return "comma_isolation"
    if left and left.dep_rel in ("acl", "acl:relcl", "advcl"):
        return "comma_isolation"
    # Participle or gerund immediately adjacent
    if right and right.get_feature("VerbForm") in ("Part", "Conv"):
        return "comma_isolation"
    if left and left.get_feature("VerbForm") in ("Part", "Conv"):
        return "comma_isolation"
    # Closing comma of a participial/gerund phrase: the participle is further left,
    # and the token to the right is the head it modifies (or continues the main clause).
    # Scan left (up to 10 tokens) for a participle/gerund whose head is to the right.
    if right is not None:
        for i in range(max(0, idx - 10), idx):
            t = tokens[i]
            if t.get_feature("VerbForm") in ("Part", "Conv"):
                # Check: participle's head is at or after the comma → closing comma
                if t.head_idx is not None and t.head_idx >= idx:
                    return "comma_isolation"
                # Or: participle has dep_rel acl/advcl
                if t.dep_rel in ("acl", "acl:relcl", "advcl"):
                    return "comma_isolation"

    # 5. Homogeneous members (fallback)
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
