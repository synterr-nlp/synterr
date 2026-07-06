"""Smoke tests for the minimal-pairs command (RozentalBench emitter)."""

import json

import pytest
from click.testing import CliRunner

from synterr.cli import main


@pytest.mark.slow
def test_minimal_pairs_emits_labeled_records(tmp_path):
    src = tmp_path / "sents.txt"
    src.write_text(
        "Я нашёл свою книгу в шкафу.\nОна не читала эту книгу.\n",
        encoding="utf-8",
    )
    out = tmp_path / "pairs.jsonl"
    result = CliRunner().invoke(
        main,
        [
            "minimal-pairs",
            "-l",
            "ru",
            "-i",
            str(src),
            "-o",
            str(out),
            "-e",
            "pronoun_svoy,neg_genitive",
        ],
    )
    assert result.exit_code == 0, result.output
    records = [
        json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()
    ]
    assert records, "no pairs emitted"
    for r in records:
        assert r["correct"] != r["incorrect"]
        assert r["l2"] in ("mo_pronoun_svoy", "gv_neg_genitive")
        assert r["l2_applicability"] in ("full", "partial", "none")
        assert r["paras"]
        assert r["correct_span"] and r["incorrect_span"]


def test_minimal_pairs_rejects_unknown_handler(tmp_path):
    src = tmp_path / "sents.txt"
    src.write_text("Мама мыла раму.\n", encoding="utf-8")
    result = CliRunner().invoke(
        main,
        [
            "minimal-pairs",
            "-l",
            "ru",
            "-i",
            str(src),
            "-o",
            str(tmp_path / "o.jsonl"),
            "-e",
            "nope",
        ],
    )
    assert result.exit_code != 0
    assert "unknown handlers" in result.output
