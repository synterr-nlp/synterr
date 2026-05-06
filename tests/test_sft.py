"""Smoke tests for synterr.sft — rule-targeted SFT generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synterr.sft import (
    _balance_directions,
    _compute_targets,
    _group_by_subtype,
    _read_input,
    generate_targeted,
)


def test_compute_targets_scales_to_total():
    targets = _compute_targets(1000)
    # Every rule gets at least 1 (the floor)
    assert all(t >= 1 for t in targets.values())
    # Total is roughly equal to requested (rounding may produce slight drift)
    assert abs(sum(targets.values()) - 1000) <= len(targets)


def test_group_by_subtype_collapses_word_filter_variants():
    targets = _compute_targets(1000)
    groups, group_targets = _group_by_subtype(targets)
    # Group keys are (handler, subtype, word_filter|None)
    assert all(isinstance(k, tuple) and len(k) == 3 for k in groups)
    # Group target = sum of member rule targets
    for key, rules in groups.items():
        assert group_targets[key] == sum(targets[r] for r in rules)


def test_read_input_caps_at_max(tmp_path: Path):
    path = tmp_path / "in.txt"
    path.write_text("\n".join(f"sentence {i}" for i in range(200)) + "\n")
    sents = _read_input(path, max_input=50)
    assert len(sents) == 50
    assert sents[0] == "sentence 0"


def test_read_input_skips_blanks(tmp_path: Path):
    path = tmp_path / "in.txt"
    path.write_text("a\n\nb\n\n\nc\n")
    assert _read_input(path, max_input=10) == ["a", "b", "c"]


def test_balance_directions_caps_to_floor():
    import random

    examples = [
        {"src": f"s{i}", "tgt": f"t{i}", "rule": 'Правописание "чтобы" [split]'}
        for i in range(200)
    ] + [
        {"src": f"s{i}", "tgt": f"t{i}", "rule": 'Правописание "чтобы" [merge]'}
        for i in range(40)
    ]
    counts = {
        'Правописание "чтобы" [split]': 200,
        'Правописание "чтобы" [merge]': 40,
    }
    dropped = _balance_directions(examples, counts, random.Random(0))
    # min(200, 40) = 40, but floor is 50, so cap = max(40, 50) = 50
    assert counts['Правописание "чтобы" [split]'] == 50
    assert counts['Правописание "чтобы" [merge]'] == 40  # below floor untouched
    assert dropped == 150


@pytest.mark.slow
def test_generate_targeted_smoke(tmp_path: Path):
    """End-to-end: tiny corpus, no depparse, ensure output shape is correct."""
    in_path = tmp_path / "in.txt"
    in_path.write_text(
        "Молоко стоит на столе.\n"
        "Мама мыла раму.\n"
        "Привет всем друзьям.\n"
        "Я положил книгу на столе.\n"
    )
    out_path = tmp_path / "out.jsonl"

    dist = generate_targeted(
        input_path=in_path,
        output_path=out_path,
        total=50,
        seed=42,
        depparse=False,
        max_input=10,
        batch_size=4,
        balance_directions=False,
    )

    assert out_path.exists()
    assert dist["seed"] == 42
    assert dist["target"] == 50
    assert "rules" in dist

    # Sidecar exists and matches return value
    sidecar = out_path.with_suffix(".dist.json")
    assert sidecar.exists()
    assert json.loads(sidecar.read_text()) == dist

    # Each output record has the expected shape
    if out_path.read_text().strip():
        for line in out_path.read_text().splitlines():
            rec = json.loads(line)
            assert set(rec.keys()) == {"src", "tgt", "rule"}
            assert rec["src"] != rec["tgt"]
