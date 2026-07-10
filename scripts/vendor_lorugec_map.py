#!/usr/bin/env python3
"""Freeze the rozental-side LORuGEC knowledge into a synterr-local snapshot.

The canonical rule names, their categories/definitions/examples, and the
hand-built rule→§§ mapping live in the `rozental` sibling repo — which is
going stale and which synterr should NOT depend on at build time. This script
reads rozental ONCE and writes a self-contained snapshot into synterr's data
dir. Rerun it only when rozental's RULE_TO_PARAS or lorugec.jsonl change.

  uv run python scripts/vendor_lorugec_map.py

Downstream, `build_lorugec_join.py` reads the snapshot — never rozental.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

SYN = Path(__file__).resolve().parents[1]            # .../synterr
ROZ = SYN.parent / "rozental"                          # sibling (may be absent later)
LORUGEC_JSONL = ROZ / "data" / "lorugec.jsonl"
EVIDENCE_SCRIPT = ROZ / "scripts" / "build_lorugec_evidence.py"
OUT = SYN / "data" / "lorugec_rule_map.json"


def parse_paras(seq) -> list[int]:
    return sorted(seq)


def load_rule_to_paras() -> dict[str, list[int]]:
    src = EVIDENCE_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r"RULE_TO_PARAS.*?\n\}", src, re.S).group(0)
    ns: dict = {}
    exec("RULE_TO_PARAS=" + m.split("=", 1)[1], ns)
    return ns["RULE_TO_PARAS"]


def main() -> None:
    if not LORUGEC_JSONL.exists():
        raise SystemExit(
            f"rozental not reachable at {ROZ} — snapshot is already vendored at "
            f"{OUT.relative_to(SYN)}; nothing to re-vendor.")

    benchmark: dict[str, dict] = {}
    for line in LORUGEC_JSONL.open(encoding="utf-8"):
        o = json.loads(line)
        nm = o["rule"]
        if nm not in benchmark:
            benchmark[nm] = {
                "category": o.get("grammar_section", ""),
                "definition": o.get("rule_definition", ""),
                "example_src": o.get("src", ""),
                "example_tgt": o.get("tgt", ""),
            }
    r2p = load_rule_to_paras()

    rules = {}
    for nm in sorted(benchmark):
        rules[nm] = {**benchmark[nm], "paras": sorted(r2p.get(nm, []))}

    missing_paras = [nm for nm in benchmark if nm not in r2p]
    snapshot = {
        "_meta": {
            "description": "Vendored snapshot of rozental-side LORuGEC knowledge "
                           "(canonical names, categories, definitions, examples, rule→§§). "
                           "Self-contained input for build_lorugec_join.py.",
            "vendored_from": ["rozental/data/lorugec.jsonl",
                              "rozental/scripts/build_lorugec_evidence.py:RULE_TO_PARAS"],
            "n_rules": len(rules),
            "regenerate_with": "uv run python scripts/vendor_lorugec_map.py",
        },
        "rules": rules,
    }
    OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ vendored {len(rules)} rules → {OUT.relative_to(SYN)}")
    if missing_paras:
        print(f"  ⚠ no §§ mapping for: {missing_paras}")


if __name__ == "__main__":
    main()
