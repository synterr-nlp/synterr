"""GEC SFT dataset diagnostics: classify (distribution) and audit (quality).

Two entry points:

* :func:`classify_jsonl` — count examples by rule (or by edit type if no
  rule labels are present). Output for human reports.
* :func:`audit_jsonl` — flag low-quality examples: no-op corruptions,
  src=tgt records, and corrupted tokens that aren't valid Russian words.

Both consume any GEC-style SFT JSONL with at minimum ``src`` and ``tgt``
fields. Synterr's own output adds a ``rule`` field; without it,
:func:`classify_jsonl` falls back to bucketing by edit type.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _read_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _classify_edit(src_tokens: list[str], tgt_tokens: list[str]) -> str:
    """Bucket a (src, tgt) pair by edit type when no rule label is given."""
    if src_tokens == tgt_tokens:
        return "<no_op>"
    matcher = SequenceMatcher(None, src_tokens, tgt_tokens, autojunk=False)
    ops = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if len(ops) == 1:
        kind = ops[0][0]  # 'replace' / 'insert' / 'delete'
        return f"<{kind}>"
    return "<multi_edit>"


def _find_replaced_token(
    src_tokens: list[str], tgt_tokens: list[str]
) -> tuple[str, str] | None:
    """Find a single replaced token, if the diff is exactly one replacement."""
    matcher = SequenceMatcher(None, src_tokens, tgt_tokens, autojunk=False)
    replaces = [
        (i1, i2, j1, j2)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag == "replace" and (i2 - i1) == 1 and (j2 - j1) == 1
    ]
    other = [op for op in matcher.get_opcodes() if op[0] not in ("equal", "replace")]
    if len(replaces) == 1 and not other:
        i1, _i2, j1, _j2 = replaces[0]
        return src_tokens[i1], tgt_tokens[j1]
    return None


def classify_jsonl(path: Path | str) -> dict:
    """Count records by rule (or edit type if no rule labels).

    Args:
        path: Path to a JSONL file with ``src``/``tgt`` per record.

    Returns:
        Dict with ``total``, ``has_rule_labels``, ``counts`` (Counter
        with rules or edit-type buckets), and ``unique_keys``.
    """
    path = Path(path)
    counts: Counter[str] = Counter()
    has_rule = False
    total = 0
    for rec in _read_jsonl(path):
        total += 1
        if rec.get("rule"):
            has_rule = True
            counts[rec["rule"]] += 1
        else:
            src_t = _tokenize(rec.get("src", ""))
            tgt_t = _tokenize(rec.get("tgt", ""))
            counts[_classify_edit(src_t, tgt_t)] += 1
    return {
        "total": total,
        "has_rule_labels": has_rule,
        "counts": dict(counts),
        "unique_keys": len(counts),
    }


def _is_known_russian_word(word: str) -> bool:
    """Cheap word-existence check via pymorphy3."""
    from pymorphy3 import MorphAnalyzer

    if not hasattr(_is_known_russian_word, "_morph"):
        _is_known_russian_word._morph = MorphAnalyzer()  # type: ignore[attr-defined]
    morph: MorphAnalyzer = _is_known_russian_word._morph  # type: ignore[attr-defined]
    parses = morph.parse(word)
    if not parses:
        return False
    return any(p.is_known for p in parses)


def audit_jsonl(
    path: Path | str,
    *,
    sample_flagged: int = 3,
    check_morphology: bool = True,
) -> dict:
    """Quality-check a GEC SFT JSONL: flag no-ops and non-word corruptions.

    Issue types reported:
      * ``no_op`` — src == tgt (handler didn't actually corrupt)
      * ``non_word`` — single-token replacement where the corrupted form
        is not in pymorphy3's dictionary (typos / formed by mistake)

    Args:
        path: Path to JSONL file with ``src``/``tgt`` per record.
        sample_flagged: Max number of sample records per issue type
            to keep in the output.
        check_morphology: If False, skip the non-word check (no
            pymorphy3 dependency at audit time).

    Returns:
        Dict with ``total``, ``issue_counts`` (per type), ``per_rule``
        (issues split by rule, when rule labels present), and
        ``samples`` (small sample of flagged records per issue type).
    """
    path = Path(path)
    issues: dict[str, list] = defaultdict(list)
    per_rule_issues: dict[str, Counter[str]] = defaultdict(Counter)
    total = 0

    for rec in _read_jsonl(path):
        total += 1
        src = rec.get("src", "")
        tgt = rec.get("tgt", "")
        rule = rec.get("rule", "<no_rule>")

        if src.strip() == tgt.strip():
            issues["no_op"].append(rec)
            per_rule_issues[rule]["no_op"] += 1
            continue

        if not check_morphology:
            continue

        src_t = _tokenize(src)
        tgt_t = _tokenize(tgt)
        replaced = _find_replaced_token(src_t, tgt_t)
        if replaced is None:
            continue
        corrupted_form, _correct_form = replaced
        # Skip non-alphabetic edits (punctuation, numbers, etc.)
        if not corrupted_form.isalpha():
            continue
        if not _is_known_russian_word(corrupted_form):
            issues["non_word"].append({**rec, "_flagged_token": corrupted_form})
            per_rule_issues[rule]["non_word"] += 1

    return {
        "total": total,
        "issue_counts": {k: len(v) for k, v in issues.items()},
        "per_rule": {r: dict(c) for r, c in per_rule_issues.items()},
        "samples": {k: v[:sample_flagged] for k, v in issues.items()},
    }
