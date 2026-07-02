#!/usr/bin/env python3
"""Build the docs-site demo viewer: stock viewer + embedded sample data.

Curates a small cross-section of examples from tools/review/*.jsonl and
emits docs/site/demo/viewer.html — the unmodified public viewer with a
demo banner and preloaded data (via the SYNTERR_DEMO_DATA hook).

Usage:
    uv run python scripts/build_demo_viewer.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
REVIEW = ROOT / "tools" / "review"
OUT_DIR = ROOT / "docs" / "site" / "demo"

# handler file → number of examples to take (spread across subtypes)
PICKS = {
    "review_comma_insert.jsonl": 8,
    "review_comma_delete.jsonl": 4,
    "review_dash_delete.jsonl": 2,
    "review_dash_to_comma.jsonl": 1,
    "review_noun_case.jsonl": 3,
    "review_noun_case_prep.jsonl": 2,
    "review_adj_double_comparative.jsonl": 1,
    "review_spelling.jsonl": 3,
    "review_orthographic_spelling.jsonl": 2,
    "review_paronym.jsonl": 1,
    "review_preposition.jsonl": 1,
    "review_adverb_spelling.jsonl": 1,
    "review_compound_spelling.jsonl": 1,
}

BANNER = """
<div style="background:#1a66b3;color:#fff;padding:10px 16px;font:14px/1.5
-apple-system,'Segoe UI',sans-serif;display:flex;gap:14px;align-items:center;
flex-wrap:wrap;">
  <strong>Interactive demo</strong>
  <span>~30 preloaded synthetic errors — try the annotation flow
  (<kbd style="background:#ffffff33;padding:1px 6px;border-radius:4px">1</kbd>–<kbd
  style="background:#ffffff33;padding:1px 6px;border-radius:4px">4</kbd>,
  <kbd style="background:#ffffff33;padding:1px 6px;border-radius:4px">?</kbd> for help).</span>
  <a href="https://github.com/synterr-nlp/synterr" style="color:#cde3ff;margin-left:auto">
  Get the tool on GitHub →</a>
</div>
"""


def spread_subtypes(lines: list[str], n: int) -> list[str]:
    """Pick up to n records, maximizing subtype diversity."""
    by_type: dict[str, list[str]] = {}
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        errs = rec.get("errors") or []
        if not errs:
            continue
        by_type.setdefault(errs[0].get("type", "?"), []).append(line)
    picked: list[str] = []
    while len(picked) < n and any(by_type.values()):
        for t in sorted(by_type):
            if by_type[t] and len(picked) < n:
                picked.append(by_type[t].pop(0))
    return picked


def main() -> int:
    sample_lines: list[str] = []
    for fname, n in PICKS.items():
        path = REVIEW / fname
        if not path.exists():
            print(f"  SKIP {fname}: not found")
            continue
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        got = spread_subtypes(lines, n)
        sample_lines.extend(got)
        print(f"  {fname}: {len(got)}")

    if not sample_lines:
        raise SystemExit("no sample records found — run generate_review.py first")

    jsonl = "\n".join(sample_lines)
    viewer = (ROOT / "tools" / "diff_viewer.html").read_text(encoding="utf-8")

    data_tag = (
        "<script>window.SYNTERR_DEMO_DATA = "
        + json.dumps({"name": "demo_examples.jsonl", "jsonl": jsonl}, ensure_ascii=False)
        + ";</script>\n"
    )
    # banner right after <body>, data before the main script consumes it
    html = viewer.replace("<body>", "<body>" + BANNER, 1)
    html = html.replace("<script>", data_tag + "<script>", 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "viewer.html").write_text(html, encoding="utf-8")
    (OUT_DIR / "sample.jsonl").write_text(jsonl + "\n", encoding="utf-8")
    print(f"\n{len(sample_lines)} examples → {OUT_DIR / 'viewer.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
