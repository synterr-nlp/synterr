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

# Map L2 tags to Rozental §§ and source files
# Format: l2_tag → (title, file_pattern, §§ to extract)
L2_TO_PARAS: dict[str, tuple[str, str, list[str]]] = {
    # sp_root children (ortho_i = §1-2, ortho_ii = §8-10)
    "sp_root_checked": ("§1. Проверяемые безударные гласные", "ortho_i.txt", ["§ 1"]),
    "sp_root_unchecked": ("§2. Непроверяемые безударные гласные", "ortho_i.txt", ["§ 2"]),
    "sp_root_voiced_voiceless": ("§8. Звонкие/глухие согласные", "ortho_ii.txt", ["§ 8"]),
    "sp_root_double": ("§9. Двойные согласные в корне", "ortho_ii.txt", ["§ 9"]),
    "sp_root_silent": ("§10. Непроизносимые согласные", "ortho_ii.txt", ["§ 10"]),
    # sp_affix children (ortho_iv = §29-30, ortho_v = §31-32)
    "sp_affix_hard_soft_sign": ("§29–30. Ъ и Ь знаки", "ortho_iv.txt", ["§ 29", "§ 30"]),
    "sp_affix_prefix": ("§31–32. Приставки на з-/с-", "ortho_v.txt", ["§ 31", "§ 32"]),
    # sp_pos children (ortho_vi = §35-36, ortho_vii = §38, ortho_viii = §39-40)
    "sp_pos_sibilant": ("§35–36. Гласные после шипящих и ц в суффиксах/окончаниях", "ortho_vi.txt", ["§ 35", "§ 36"]),
    "sp_noun_endings": ("§38. Суффиксы имён существительных", "ortho_vii.txt", ["§ 38"]),
    "sp_adj_endings": ("§39–40. Окончания и суффиксы прилагательных", "ortho_viii.txt", ["§ 39", "§ 40"]),
    "sp_verb_endings": ("§48–50. Глагольные окончания и суффиксы", "ortho_xii.txt", ["§ 48", "§ 49", "§ 50"]),
    "sp_participle_endings": ("§51–52. Суффиксы причастий и н/нн", "ortho_xiii.txt", ["§ 51", "§ 52"]),
    # sp_function children (ortho_xvi = §61-62, ortho_xvii = §63-65)
    "sp_ne_ni": ("§65. Не с существительными", "ortho_xvii.txt", ["§ 65"]),
    "sp_conjunction_spelling": ("§61–62. Правописание союзов", "ortho_xvi.txt", ["§ 61", "§ 62"]),
    "sp_particle_spelling": ("§63–64. Правописание частиц", "ortho_xvii.txt", ["§ 63", "§ 64"]),
    # pu_comma children (punct_xxii = §83+, punct_xxiv = §92-93, punct_xxvi = §99+)
    "pu_comma_homogeneous": ("§83–89. Запятая при однородных членах", "punct_xxii.txt", ["§ 83"]),
    "pu_comma_isolation": ("§92–95. Обособление", "punct_xxiv.txt", ["§ 92", "§ 93"]),
    "pu_comma_parenthetical": ("§99–103. Вводные слова и предложения", "punct_xxvi.txt", ["§ 99", "§ 100"]),
    "pu_comma_clarifying": ("§96–98. Уточняющие члены", "punct_xxv.txt", ["§ 96"]),
    # pu_clause children (punct_xxvii = §104, punct_xxviii = §107)
    "pu_clause_subordinate": ("§107–113. Сложноподчинённое предложение", "punct_xxviii.txt", ["§ 107"]),
    "pu_clause_compound": ("§104–106. Сложносочинённое предложение", "punct_xxvii.txt", ["§ 104"]),
    # pu_dash children (punct_xxi = §79-81)
    "pu_dash_subj_pred": ("§79. Тире между подлежащим и сказуемым", "punct_xxi.txt", ["§ 79"]),
    "pu_dash_other": ("§80–82. Тире в других случаях", "punct_xxi.txt", ["§ 80", "§ 81"]),
    # lx children (styli_xxxv = §139-141)
    "lx_paronym": ("§139. Паронимы", "styli_xxxv.txt", ["§ 139"]),
    # gv children (styli_xlv = §198-200)
    "gv_prep_choice": ("§199. Выбор предлога", "styli_xlv.txt", ["§ 199"]),
    # mo children (styli_xxxvi = §144+)
    "mo_noun_case_other": ("§144–155. Падежные формы существительных", "styli_xxxvi.txt", ["§ 144"]),
    "mo_noun_num_nom_pl": ("§144. Колебания в роде", "styli_xxxvi.txt", ["§ 144"]),
    "mo_noun_gender_fluctuation": ("§144–145. Колебания в роде существительных", "styli_xxxvi.txt", ["§ 144"]),
    # ag children (styli_xliv = §191-194)
    "ag_mn_adj_case": ("§191–192. Согласование прилагательного в падеже", "styli_xliv.txt", ["§ 191"]),
    "ag_mn_adj_number": ("§193. Согласование прилагательного в числе", "styli_xliv.txt", ["§ 193"]),
    "ag_mn_adj_gender": ("§194. Согласование прилагательного в роде", "styli_xliv.txt", ["§ 194"]),
    # mo_verb children (styli_xl = §171-173)
    "mo_verb_asp_pair": ("§172. Варианты видовых форм", "styli_xl.txt", ["§ 172"]),
}


def extract_para(text: str, para_marker: str) -> str:
    """Extract a single § paragraph from Rozental text.

    Finds the paragraph starting with the marker (e.g. "§ 1") and
    returns text until the next § marker or end of file.
    Truncates at ~500 chars for viewer display.
    """
    # Find the paragraph
    pattern = re.escape(para_marker) + r"[\.\s]"
    match = re.search(pattern, text)
    if not match:
        # Try without space: "§49." instead of "§ 49."
        alt_marker = para_marker.replace("§ ", "§")
        match = re.search(re.escape(alt_marker) + r"[\.\s]", text)
        if not match:
            return ""

    start = match.start()

    # Find next § or end
    next_match = re.search(r"\n§\s*\d+", text[start + len(para_marker):])
    if next_match:
        end = start + len(para_marker) + next_match.start()
    else:
        end = len(text)

    para_text = text[start:end].strip()

    # Truncate for display
    if len(para_text) > 800:
        para_text = para_text[:800].rsplit(" ", 1)[0] + " [...]"

    return para_text


def build_rule_texts() -> dict[str, dict[str, str]]:
    """Build L2 tag → {title, text} mapping from Rozental sources."""
    if not ROZENTAL_DIR.exists():
        print(f"Rozental source not found at {ROZENTAL_DIR}", file=sys.stderr)
        print("Expected: ../rozental/data/raw/", file=sys.stderr)
        return {}

    rules = {}

    for l2_tag, (title, filename, paras) in L2_TO_PARAS.items():
        filepath = ROZENTAL_DIR / filename
        if not filepath.exists():
            print(f"  SKIP {l2_tag}: {filename} not found")
            continue

        text = filepath.read_text(encoding="utf-8")

        # Extract just the first § for brevity
        para_text = extract_para(text, paras[0])
        if para_text:
            rules[l2_tag] = {"title": title, "text": para_text}
        else:
            print(f"  SKIP {l2_tag}: § not found in {filename}")

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
