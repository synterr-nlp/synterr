"""Tests for synterr.diagnostics — classify-jsonl and audit-jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from synterr.diagnostics import (
    _classify_edit,
    _find_replaced_token,
    _tokenize,
    audit_jsonl,
    classify_jsonl,
)


def test_tokenize_words_and_punct():
    assert _tokenize("Hello, world!") == ["Hello", ",", "world", "!"]
    assert _tokenize("Мама мыла раму.") == ["Мама", "мыла", "раму", "."]


def test_classify_edit_buckets():
    assert _classify_edit(["a", "b"], ["a", "b"]) == "<no_op>"
    assert _classify_edit(["a", "b"], ["a", "c"]) == "<replace>"
    assert _classify_edit(["a"], ["a", "b"]) == "<insert>"
    assert _classify_edit(["a", "b"], ["a"]) == "<delete>"
    # Two adjacent changes coalesce into a single replace span — that's
    # SequenceMatcher's behavior, not a bug.
    assert _classify_edit(["a", "b", "c"], ["x", "y", "c"]) == "<replace>"
    # Genuinely separate changes register as multi_edit.
    assert _classify_edit(["a", "b", "c", "d"], ["x", "b", "c", "y"]) == "<multi_edit>"


def test_find_replaced_token_single_replacement():
    src = ["Они", "книгу", "."]
    tgt = ["Они", "xyzzqq", "."]
    assert _find_replaced_token(src, tgt) == ("книгу", "xyzzqq")


def test_find_replaced_token_returns_none_for_multi_edit():
    src = ["a", "b"]
    tgt = ["c", "d"]
    # Two replaces — not a single replacement
    assert _find_replaced_token(src, tgt) is None


def test_classify_jsonl_with_rules(tmp_path: Path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"src": "a", "tgt": "b", "rule": "rule_x"}),
                json.dumps({"src": "c", "tgt": "d", "rule": "rule_x"}),
                json.dumps({"src": "e", "tgt": "f", "rule": "rule_y"}),
            ]
        )
    )
    result = classify_jsonl(path)
    assert result["total"] == 3
    assert result["has_rule_labels"] is True
    assert result["counts"] == {"rule_x": 2, "rule_y": 1}
    assert result["unique_keys"] == 2


def test_classify_jsonl_without_rules_buckets_by_edit(tmp_path: Path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"src": "Мама мыла", "tgt": "Мама мыла"}),  # no_op
                json.dumps({"src": "Мама мыла", "tgt": "Мама моет"}),  # replace
                json.dumps({"src": "Мама", "tgt": "Мама мыла раму"}),  # insert
            ]
        )
    )
    result = classify_jsonl(path)
    assert result["total"] == 3
    assert result["has_rule_labels"] is False
    assert "<no_op>" in result["counts"]
    assert "<replace>" in result["counts"] or "<multi_edit>" in result["counts"]


def test_audit_jsonl_finds_no_ops(tmp_path: Path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "src": "Молоко стоит на столе.",
                        "tgt": "Молоко стоит на столе.",
                        "rule": "noun_case",
                    }
                ),
                json.dumps({"src": "Книга", "tgt": "Книга", "rule": "noun_case"}),
                json.dumps(
                    {
                        "src": "Молоко стоит.",
                        "tgt": "Молоко течет.",
                        "rule": "noun_case",
                    }
                ),
            ]
        )
    )
    result = audit_jsonl(path, check_morphology=False)
    assert result["total"] == 3
    assert result["issue_counts"]["no_op"] == 2
    assert "non_word" not in result["issue_counts"]
    assert result["per_rule"]["noun_case"]["no_op"] == 2


def test_audit_jsonl_flags_non_words(tmp_path: Path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        json.dumps(
            {
                "src": "Они xyzzqq книгу.",
                "tgt": "Они купили книгу.",
                "rule": "spelling",
            }
        )
    )
    result = audit_jsonl(path)
    # Two replacements in this diff (xyzzqq, купили) — _find_replaced_token
    # only fires on exactly one. So this is a multi-edit, not a single
    # replacement, and the test would not flag. Let's use a single-edit case:
    path.write_text(
        json.dumps(
            {
                "src": "Они xyzzqq.",
                "tgt": "Они книгу.",
                "rule": "spelling",
            }
        )
    )
    result = audit_jsonl(path)
    assert result["total"] == 1
    assert result["issue_counts"].get("non_word", 0) == 1
    assert result["samples"]["non_word"][0]["_flagged_token"] == "xyzzqq"


def test_audit_jsonl_skips_morphology_when_disabled(tmp_path: Path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        json.dumps({"src": "Они xyzzqq.", "tgt": "Они книгу.", "rule": "spelling"})
    )
    result = audit_jsonl(path, check_morphology=False)
    assert "non_word" not in result["issue_counts"]
