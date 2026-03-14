#!/usr/bin/env python3
"""Build internal diff viewer with embedded Rozental rule text.

INTERNAL USE ONLY — the output file contains copyrighted text and must NOT
be committed to git. The output is .gitignored.

Usage:
    uv run python scripts/build_internal_viewer.py

Output: tools/diff_viewer_internal.html (gitignored)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Rozental source directory (copyrighted text)
ROZENTAL_DIR = Path(__file__).parent.parent.parent / "rozental" / "data" / "raw"

# Map L2 tags to Rozental source files and §§ to extract.
# Titles are extracted from the actual text, not hardcoded.
# Format: l2_tag → (file, [§ markers])
L2_TO_PARAS: dict[str, tuple[str, list[str]]] = {
    # sp_root children
    "sp_root_checked": ("ortho_i.txt", ["§ 1"]),
    "sp_root_unchecked": ("ortho_i.txt", ["§ 2"]),
    "sp_root_voiced_voiceless": ("ortho_ii.txt", ["§ 8"]),
    "sp_root_double": ("ortho_ii.txt", ["§ 9"]),
    "sp_root_silent": ("ortho_ii.txt", ["§ 10"]),
    # sp_affix children
    "sp_affix_hard_soft_sign": ("ortho_iv.txt", ["§ 29"]),
    "sp_affix_prefix": ("ortho_v.txt", ["§ 31"]),
    # sp_pos children
    "sp_pos_sibilant": ("ortho_vi.txt", ["§ 35"]),
    "sp_noun_endings": ("ortho_vii.txt", ["§ 38"]),
    "sp_adj_endings": ("ortho_viii.txt", ["§ 39"]),
    "sp_adj_suffixes": ("ortho_viii.txt", ["§ 40"]),
    "sp_verb_endings": ("ortho_xii.txt", ["§ 48"]),
    "sp_participle_endings": ("ortho_xiii.txt", ["§ 51"]),
    # sp_function children
    "sp_ne_ni": ("ortho_xvii.txt", ["§ 65"]),
    "sp_conjunction_spelling": ("ortho_xvi.txt", ["§ 61"]),
    "sp_particle_spelling": ("ortho_xvii.txt", ["§ 63"]),
    # pu_comma children
    "pu_comma_homogeneous": ("punct_xxii.txt", ["§ 83"]),
    "pu_comma_isolation": ("punct_xxiv.txt", ["§ 92"]),
    "pu_comma_parenthetical": ("punct_xxvi.txt", ["§ 99"]),
    "pu_comma_clarifying": ("punct_xxv.txt", ["§ 96"]),
    # pu_clause children
    "pu_clause_subordinate": ("punct_xxviii.txt", ["§ 107"]),
    "pu_clause_compound": ("punct_xxvii.txt", ["§ 104"]),
    "pu_clause_comparative": ("punct_xxix.txt", ["§ 114"]),
    # pu_other children
    "pu_combinations": ("punct_xxxiv.txt", ["§ 133"]),
    # pu_dash children
    "pu_dash_subj_pred": ("punct_xxi.txt", ["§ 79"]),
    "pu_dash_other": ("punct_xxi.txt", ["§ 80"]),
    # lx children
    "lx_paronym": ("styli_xxxv.txt", ["§ 139"]),
    # gv children
    "gv_prep_choice": ("styli_xlv.txt", ["§ 199"]),
    # mo children
    "mo_noun_case_other": ("styli_xxxvi.txt", ["§ 144"]),
    "mo_noun_num_nom_pl": ("styli_xxxvi.txt", ["§ 144"]),
    "mo_noun_gender_fluctuation": ("styli_xxxvi.txt", ["§ 144"]),
    # ag children
    "ag_mn_adj_case": ("styli_xliv.txt", ["§ 191"]),
    "ag_mn_adj_number": ("styli_xliv.txt", ["§ 193"]),
    "ag_mn_adj_gender": ("styli_xliv.txt", ["§ 194"]),
    # mo_verb children
    "mo_verb_asp_pair": ("styli_xl.txt", ["§ 172"]),
}


def extract_para(text: str, para_marker: str) -> tuple[str, str]:
    """Extract a single § paragraph from Rozental text.

    Finds the paragraph starting with the marker (e.g. "§ 1") and
    returns (title, body) where title is the first line and body is the rest.
    Truncates body at ~800 chars for viewer display.
    """
    # Find the paragraph
    pattern = re.escape(para_marker) + r"[\.\s]"
    match = re.search(pattern, text)
    if not match:
        # Try without space: "§49." instead of "§ 49."
        alt_marker = para_marker.replace("§ ", "§")
        match = re.search(re.escape(alt_marker) + r"[\.\s]", text)
        if not match:
            return "", ""

    start = match.start()

    # Find next § or end
    next_match = re.search(r"\n§\s*\d+", text[start + len(para_marker):])
    if next_match:
        end = start + len(para_marker) + next_match.start()
    else:
        end = len(text)

    para_text = text[start:end].strip()

    # Split into title (first line) and body
    lines = para_text.split("\n", 1)
    title = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    # Truncate body for display
    if len(body) > 800:
        body = body[:800].rsplit(" ", 1)[0] + " [...]"

    return title, body


def build_rule_texts() -> dict[str, dict[str, str]]:
    """Build L2 tag → {title, text} mapping from Rozental sources."""
    if not ROZENTAL_DIR.exists():
        print(f"Rozental source not found at {ROZENTAL_DIR}", file=sys.stderr)
        print("Expected: ../rozental/data/raw/", file=sys.stderr)
        return {}

    rules = {}

    for l2_tag, (filename, paras) in L2_TO_PARAS.items():
        filepath = ROZENTAL_DIR / filename
        if not filepath.exists():
            print(f"  SKIP {l2_tag}: {filename} not found")
            continue

        text = filepath.read_text(encoding="utf-8")

        # Extract first § — title comes from the text itself
        title, body = extract_para(text, paras[0])
        if title:
            rules[l2_tag] = {"title": title, "text": body}
        else:
            print(f"  SKIP {l2_tag}: {paras[0]} not found in {filename}")

    return rules


def main():
    viewer_path = Path(__file__).parent.parent / "tools" / "diff_viewer.html"
    output_path = Path(__file__).parent.parent / "tools" / "diff_viewer_internal.html"

    if not viewer_path.exists():
        print(f"Base viewer not found: {viewer_path}", file=sys.stderr)
        sys.exit(1)

    print("Extracting Rozental rule texts...")
    rules = build_rule_texts()
    print(f"Extracted {len(rules)} rules from {len(L2_TO_PARAS)} L2 tags\n")

    # Read base viewer
    html = viewer_path.read_text(encoding="utf-8")

    # Replace empty RULE_TEXTS with populated version
    rules_js = json.dumps(rules, ensure_ascii=False, indent=2)
    html = html.replace(
        "const RULE_TEXTS = {};",
        f"const RULE_TEXTS = {rules_js};",
    )

    # Add INTERNAL warning
    html = html.replace(
        "<title>Synterr Diff Viewer</title>",
        "<title>Synterr Diff Viewer (INTERNAL)</title>",
    )
    html = html.replace(
        "<h1>Synterr Diff Viewer</h1>",
        '<h1>Synterr Diff Viewer <span style="color: #dc3545; font-size: 0.7em;">(INTERNAL — DO NOT DISTRIBUTE)</span></h1>',
    )

    output_path.write_text(html, encoding="utf-8")
    size_kb = output_path.stat().st_size / 1024
    print(f"Written to {output_path} ({size_kb:.0f} KB)")
    print("\nWARNING: This file contains copyrighted text. DO NOT commit or distribute.")


if __name__ == "__main__":
    main()
