#!/usr/bin/env python3
"""Single source of truth joining the four representations of each LORuGEC rule.

For years these lived in separate files with drifting names and no shared key:
  - LORuGEC benchmark      → canonical names + defs + §§   (data/lorugec_rule_map.json,
                                                            vendored from rozental)
  - SyntErr generation map → handler / subtype / direction (synterr.lorugec)
  - Rozental schema        → L2 / L1 / L0 tags             (src/synterr/schemas/data/rozental.yaml)
  - v4 training data       → realized example counts       (data/qwen_sft_v4.jsonl)

This joins them on one canonical key (the benchmark rule name), resolving the
4-entry name drift in the generation map, and emits:
  - data/lorugec_join.csv   (one row per rule, list cells joined by '; ')
  - data/lorugec_join.json  (full detail)

Self-contained: reads ONLY synterr-local files. Generated, not hand-maintained —
rerun whenever any source changes. (To refresh the vendored rozental snapshot:
`uv run python scripts/vendor_lorugec_map.py`.)

  uv run --with pyyaml python scripts/build_lorugec_join.py
"""
from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path

import yaml

SYN = Path(__file__).resolve().parents[1]            # .../synterr
sys.path.insert(0, str(SYN / "src"))
from synterr.lorugec import LORUGEC_RULES            # noqa: E402

RULE_MAP = SYN / "data" / "lorugec_rule_map.json"
SCHEMA_YAML = SYN / "src" / "synterr" / "schemas" / "data" / "rozental.yaml"
V4_JSONL = SYN / "data" / "qwen_sft_v4.jsonl"
OUT_CSV = SYN / "data" / "lorugec_join.csv"
OUT_JSON = SYN / "data" / "lorugec_join.json"

CANONICAL_L2_COUNT = 98  # paper-authoritative; synterr's yaml is pre-cleanup (see diagnostics)

DIR_RE = re.compile(r"\s*\[(split|merge|attach|detach|insert|delete)\]\s*$")
base_name = lambda s: DIR_RE.sub("", s).strip()                       # noqa: E731
direction_of = lambda s: (m.group(1) if (m := DIR_RE.search(s)) else None)  # noqa: E731

# The entire name-drift surface: generation-map name → canonical benchmark name.
GEN_TO_CANON = {
    "Наречия": "Слитное, раздельное и дефисное написание наречий",
    'Правописание "не" с причастиями': 'Правописание частицы "не" с причастиями',
    'Правописание "не" с существительными': 'Правописание частицы "не" с существительными',
    'Правописание "причем"': 'Правописание "причем" и "притом"',
}
canon_from_gen = lambda b: GEN_TO_CANON.get(b, b)                     # noqa: E731


def parse_paras(s) -> set[int]:
    if not s:
        return set()
    out: set[int] = set()
    for tok in re.split(r"[,\s]+", str(s).replace("–", "-").replace("—", "-")):
        tok = tok.replace("§", "").strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-")[:2]
            try:
                out |= set(range(int(a), int(b) + 1))
            except ValueError:
                pass
        else:
            try:
                out.add(int(tok))
            except ValueError:
                pass
    return out


def load_schema():
    d = yaml.safe_load(SCHEMA_YAML.open(encoding="utf-8"))
    fg, pt = d["fine_grained_tags"], d["primary_tags"]
    para2l2: dict[int, list[str]] = {}
    for tag, v in fg.items():
        for p in parse_paras(v.get("paras", "")):
            para2l2.setdefault(p, []).append(tag)
    return fg, pt, para2l2, len(fg)


def load_v4_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    if V4_JSONL.exists():
        for line in V4_JSONL.open(encoding="utf-8"):
            canon = canon_from_gen(base_name(json.loads(line)["rule"]))
            counts[canon] = counts.get(canon, 0) + 1
    return counts


def build():
    rule_map = json.loads(RULE_MAP.read_text(encoding="utf-8"))["rules"]
    fg, pt, para2l2, n_l2 = load_schema()
    v4 = load_v4_counts()

    gen_index: dict[str, list[dict]] = {}
    for key, spec in LORUGEC_RULES.items():
        canon = canon_from_gen(base_name(key))
        gen_index.setdefault(canon, []).append({
            "handler": spec[0],
            "subtype": spec[1] if len(spec) > 1 else None,
            "direction": direction_of(key),
            "word_filter": spec[2] if len(spec) > 2 else None,
        })

    rows, diag = [], {"name_aliases": GEN_TO_CANON, "multi_l2_rules": [],
                      "thin_v4_rules": [], "no_generation": [], "para_miss": [],
                      "schema_l2_count": n_l2}

    for canon in sorted(rule_map, key=lambda r: (rule_map[r]["category"], r)):
        meta = rule_map[canon]
        paras = meta["paras"]

        l2_tags: list[str] = []
        for p in paras:
            if p not in para2l2:
                diag["para_miss"].append((canon, p))
            for t in para2l2.get(p, []):
                if t not in l2_tags:
                    l2_tags.append(t)
        if len(l2_tags) > 1:
            diag["multi_l2_rules"].append((canon, l2_tags))

        l1_fams, l0_cats, applic, l2_desc = [], [], [], []
        for t in l2_tags:
            v = fg.get(t, {})
            l1 = v.get("parent")
            if l1 and l1 not in l1_fams:
                l1_fams.append(l1)
            l0 = pt.get(l1, {}).get("detection_category") if l1 else None
            if l0 and l0 not in l0_cats:
                l0_cats.append(l0)
            applic.append(v.get("l2_applicability", ""))
            l2_desc.append(v.get("description", ""))

        gens = gen_index.get(canon, [])
        n_v4 = v4.get(canon, 0)
        if not gens:
            diag["no_generation"].append(canon)
        elif n_v4 < 200:
            diag["thin_v4_rules"].append((canon, n_v4))

        rows.append({
            "lorugec_rule": canon,
            "category": meta["category"],
            "rozental_paras": ", ".join(f"§{p}" for p in paras),
            "l2_tags": l2_tags,
            "l1_families": l1_fams,
            "l0_categories": l0_cats,
            "l2_applicability": applic,
            "l2_description": l2_desc,
            "synterr_handlers": sorted({g["handler"] for g in gens}),
            "synterr_subtypes": sorted({g["subtype"] for g in gens if g["subtype"]}),
            "directions": sorted({g["direction"] for g in gens if g["direction"]}),
            "generates": bool(gens),
            "v4_examples": n_v4,
            "lorugec_definition": meta.get("definition", ""),
            "example_src": meta.get("example_src", ""),
            "example_tgt": meta.get("example_tgt", ""),
        })
    return rows, diag


def write_outputs(rows):
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    list_cols = {"l2_tags", "l1_families", "l0_categories", "l2_applicability",
                 "l2_description", "synterr_handlers", "synterr_subtypes", "directions"}
    csv_cols = ["lorugec_rule", "category", "rozental_paras", "l2_tags", "l1_families",
                "l0_categories", "l2_applicability", "synterr_handlers",
                "synterr_subtypes", "directions", "generates", "v4_examples", "l2_description"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_cols)
        for r in rows:
            w.writerow(["; ".join(map(str, r[c])) if c in list_cols else r[c] for c in csv_cols])


def main():
    rows, diag = build()
    write_outputs(rows)

    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print(f"✓ {len(rows)} LORuGEC rules joined → {OUT_CSV.name}, {OUT_JSON.name}")
    print("  by category:", dict(sorted(by_cat.items())))
    print(f"  generate: {sum(r['generates'] for r in rows)}/{len(rows)}   "
          f"v4 examples total: {sum(r['v4_examples'] for r in rows):,}")
    print(f"  name aliases resolved: {len(diag['name_aliases'])}   "
          f"rules spanning >1 L2 tag: {len(diag['multi_l2_rules'])}")
    for r, l2 in diag["multi_l2_rules"]:
        print(f"      {r[:46]:46s} → {', '.join(l2)}")
    print(f"  thin v4 coverage (<200 ex): {len(diag['thin_v4_rules'])}")
    for r, n in sorted(diag["thin_v4_rules"], key=lambda x: x[1]):
        print(f"      {n:5d}  {r}")

    n_l2 = diag["schema_l2_count"]
    if n_l2 != CANONICAL_L2_COUNT:
        print(f"\n  ⚠ STALE SCHEMA: synterr's rozental.yaml has {n_l2} L2 tags; "
              f"paper-authoritative is {CANONICAL_L2_COUNT}. The L2 column reflects "
              f"synterr's (pre-cleanup) schema — rerun after the 98-tag cleanup pass.")
    if diag["no_generation"]:
        print(f"  ⚠ no generator: {diag['no_generation']}")
    if diag["para_miss"]:
        print(f"  ⚠ §§ with no L2 tag: {diag['para_miss']}")


if __name__ == "__main__":
    main()
