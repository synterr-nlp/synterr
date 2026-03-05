"""Extract empirical confusion matrices from RLC and RULEC-GEC learner corpora.

Compares with literature-based predictions from CASE_CONFUSION_PATTERNS.md.

Usage:
    uv run python scripts/extract_confusion_matrices.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pymorphy3

GECTOR_DATA = Path(__file__).resolve().parent.parent.parent / "gector" / "data"
RLC_ANNOTATIONS = GECTOR_DATA / "rlc-annotated" / "annotations.csv"
RULEC_DIR = GECTOR_DATA / "rulec-gec"

morph = pymorphy3.MorphAnalyzer()

# pymorphy case tag → human-readable
CASE_LABELS = {
    "nomn": "Nom", "gent": "Gen", "datv": "Dat",
    "accs": "Acc", "ablt": "Ins", "loct": "Loc",
    "voct": "Voc", "gen2": "Gen2", "acc2": "Acc2",
    "loc2": "Loc2",
}
GENDER_LABELS = {"masc": "Masc", "femn": "Fem", "neut": "Neut"}
NUMBER_LABELS = {"sing": "Sing", "plur": "Plur"}
PERSON_LABELS = {"1per": "1", "2per": "2", "3per": "3"}
TENSE_LABELS = {"past": "Past", "pres": "Pres", "futr": "Fut"}

# Canonical cases for the confusion matrix (skip rare Gen2/Loc2/Voc)
CANONICAL_CASES = ["Nom", "Acc", "Gen", "Dat", "Ins", "Loc"]
CANONICAL_GENDERS = ["Masc", "Fem", "Neut"]
CANONICAL_NUMBERS = ["Sing", "Plur"]


def extract_grammeme(word: str, grammeme_set: dict[str, str]) -> str | None:
    """Parse word with pymorphy and extract the first matching grammeme."""
    for p in morph.parse(word):
        for tag, label in grammeme_set.items():
            if tag in p.tag:
                return label
    return None


def extract_case(word: str) -> str | None:
    return extract_grammeme(word, CASE_LABELS)


def extract_gender(word: str) -> str | None:
    return extract_grammeme(word, GENDER_LABELS)


def extract_number(word: str) -> str | None:
    return extract_grammeme(word, NUMBER_LABELS)


# ── RLC extraction ──────────────────────────────────────────────────────────


def load_rlc_annotations() -> list[dict]:
    """Load RLC annotations.csv."""
    rows = []
    with open(RLC_ANNOTATIONS, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def extract_rlc_case_matrix(rows: list[dict]) -> dict:
    """Build case confusion matrix from RLC agrcase + gov tags."""
    matrix = defaultdict(Counter)  # correct_case → Counter(learner_case)
    skipped = 0
    multi_word = 0

    for row in rows:
        tags = {t.strip().lower() for t in row["tag"].split(",")}
        if "agrcase" not in tags and "gov" not in tags:
            continue

        quote = row["quote"].strip()
        correction = row["correction"].strip()

        # Skip multi-word spans (hard to align grammemes)
        if " " in quote or " " in correction:
            multi_word += 1
            continue

        learner_case = extract_case(quote)
        correct_case = extract_case(correction)

        if learner_case and correct_case and learner_case != correct_case:
            matrix[correct_case][learner_case] += 1
        else:
            skipped += 1

    return matrix, skipped, multi_word


def extract_rlc_gender_matrix(rows: list[dict]) -> dict:
    """Build gender confusion matrix from RLC agrgender tags."""
    matrix = defaultdict(Counter)
    skipped = 0

    for row in rows:
        tags = {t.strip().lower() for t in row["tag"].split(",")}
        if "agrgender" not in tags:
            continue

        quote = row["quote"].strip()
        correction = row["correction"].strip()
        if " " in quote or " " in correction:
            continue

        learner_g = extract_gender(quote)
        correct_g = extract_gender(correction)

        if learner_g and correct_g and learner_g != correct_g:
            matrix[correct_g][learner_g] += 1
        else:
            skipped += 1

    return matrix, skipped


def extract_rlc_number_matrix(rows: list[dict]) -> dict:
    """Build number confusion matrix from RLC agrnum tags."""
    matrix = defaultdict(Counter)
    skipped = 0

    for row in rows:
        tags = {t.strip().lower() for t in row["tag"].split(",")}
        if "agrnum" not in tags:
            continue

        quote = row["quote"].strip()
        correction = row["correction"].strip()
        if " " in quote or " " in correction:
            continue

        learner_n = extract_number(quote)
        correct_n = extract_number(correction)

        if learner_n and correct_n and learner_n != correct_n:
            matrix[correct_n][learner_n] += 1
        else:
            skipped += 1

    return matrix, skipped


# ── RULEC-GEC extraction ───────────────────────────────────────────────────


def load_rulec_m2(path: Path) -> list[tuple[str, str, str]]:
    """Parse RULEC M2 file, return (tag, learner_word, correction) triples."""
    triples = []
    current_sent = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("S "):
                current_sent = line[2:].split()
            elif line.startswith("A ") and current_sent:
                parts = line.split("|||")
                if len(parts) < 4:
                    continue
                span = parts[0].split()  # "A start end"
                start, end = int(span[1]), int(span[2])
                tag = parts[1]
                correction = parts[2]
                learner = " ".join(current_sent[start:end])
                triples.append((tag, learner, correction))
    return triples


def extract_rulec_case_matrix(triples: list[tuple]) -> dict:
    """Build case confusion from RULEC Сущ.:Падеж and Прил.:Падеж tags."""
    matrix = defaultdict(Counter)
    skipped = 0
    case_tags = {"Сущ.:Падеж", "Прил.:Падеж"}

    for tag, learner, correction in triples:
        if tag not in case_tags:
            continue
        if " " in learner or " " in correction:
            continue

        learner_case = extract_case(learner)
        correct_case = extract_case(correction)

        if learner_case and correct_case and learner_case != correct_case:
            matrix[correct_case][learner_case] += 1
        else:
            skipped += 1

    return matrix, skipped


def extract_rulec_gender_matrix(triples: list[tuple]) -> dict:
    """Build gender confusion from RULEC Сущ.:Род and Прил.:Род tags."""
    matrix = defaultdict(Counter)
    skipped = 0
    gender_tags = {"Сущ.:Род", "Прил.:Род"}

    for tag, learner, correction in triples:
        if tag not in gender_tags:
            continue
        if " " in learner or " " in correction:
            continue

        learner_g = extract_gender(learner)
        correct_g = extract_gender(correction)

        if learner_g and correct_g and learner_g != correct_g:
            matrix[correct_g][learner_g] += 1
        else:
            skipped += 1

    return matrix, skipped


def extract_rulec_number_matrix(triples: list[tuple]) -> dict:
    """Build number confusion from RULEC Сущ.:Число and Прил.:Число tags."""
    matrix = defaultdict(Counter)
    skipped = 0
    number_tags = {"Сущ.:Число", "Прил.:Число"}

    for tag, learner, correction in triples:
        if tag not in number_tags:
            continue
        if " " in learner or " " in correction:
            continue

        learner_n = extract_number(learner)
        correct_n = extract_number(correction)

        if learner_n and correct_n and learner_n != correct_n:
            matrix[correct_n][learner_n] += 1
        else:
            skipped += 1

    return matrix, skipped


# ── Literature-based predictions ────────────────────────────────────────────

LITERATURE_CASE = {
    "Nom": {},
    "Acc": {"Nom": 0.35, "Gen": 0.40, "Dat": 0.15, "Ins": 0.10},
    "Gen": {"Acc": 0.50, "Nom": 0.30, "Dat": 0.10, "Ins": 0.10},
    "Dat": {"Acc": 0.60, "Nom": 0.20, "Gen": 0.10, "Ins": 0.10},
    "Ins": {"Acc": 0.30, "Gen": 0.30, "Nom": 0.25, "Dat": 0.15},
    "Loc": {"Acc": 0.40, "Nom": 0.30, "Gen": 0.20, "Dat": 0.10},
}


# ── Display ─────────────────────────────────────────────────────────────────


def print_matrix(
    matrix: dict[str, Counter],
    labels: list[str],
    title: str,
    total_skipped: int = 0,
):
    """Print a confusion matrix as a table with percentages."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

    # Header
    header = f"{'correct →':>12s}"
    for label in labels:
        header += f" {label:>7s}"
    header += "   total"
    print(header)
    print("-" * len(header))

    for correct in labels:
        row = matrix.get(correct, Counter())
        total = sum(row.values())
        line = f"{'learner ↓':>12s}" if correct == labels[0] else f"{'':>12s}"
        # Actually, let's do correct as rows
        pass

    # Rows: correct case (what should have been)
    # Columns: learner case (what the learner wrote)
    print(f"  Rows = correct case, Columns = learner substitution")
    print(f"  Read as: P(learner wrote column | correct was row)")
    print()
    header = f"{'correct↓ sub→':>14s}"
    for label in labels:
        header += f" {label:>7s}"
    header += f" {'total':>7s}"
    print(header)
    print("-" * len(header))

    grand_total = 0
    for correct in labels:
        row = matrix.get(correct, Counter())
        total = sum(row.values())
        grand_total += total
        line = f"{correct:>14s}"
        for sub in labels:
            count = row.get(sub, 0)
            if correct == sub:
                line += f" {'---':>7s}"
            elif total > 0:
                pct = count / total * 100
                if count > 0:
                    line += f" {pct:5.1f}% "
                else:
                    line += f" {'':>7s}"
            else:
                line += f" {'':>7s}"
        line += f" {total:>5d}  "
        # Show raw counts too
        raw = " ".join(f"{sub}:{row.get(sub,0)}" for sub in labels if row.get(sub, 0) > 0 and sub != correct)
        line += raw
        print(line)

    print(f"\nTotal confusions: {grand_total}  (skipped: {total_skipped})")


def print_comparison(
    empirical: dict[str, Counter],
    literature: dict[str, dict[str, float]],
    labels: list[str],
    title: str,
):
    """Print side-by-side comparison of empirical vs literature matrices."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    print(f"  Format: empirical% (N) vs literature%")
    print()

    header = f"{'correct↓ sub→':>14s}"
    for label in labels:
        header += f" {label:>14s}"
    print(header)
    print("-" * len(header))

    for correct in labels:
        emp_row = empirical.get(correct, Counter())
        lit_row = literature.get(correct, {})
        emp_total = sum(emp_row.values())
        line = f"{correct:>14s}"

        for sub in labels:
            if correct == sub:
                line += f" {'---':>14s}"
                continue
            emp_count = emp_row.get(sub, 0)
            emp_pct = emp_count / emp_total * 100 if emp_total > 0 else 0
            lit_pct = lit_row.get(sub, 0) * 100

            if emp_count > 0 or lit_pct > 0:
                emp_str = f"{emp_pct:.0f}%({emp_count})" if emp_count > 0 else "0"
                lit_str = f"{lit_pct:.0f}%" if lit_pct > 0 else "0"
                cell = f"{emp_str}v{lit_str}"
                line += f" {cell:>14s}"
            else:
                line += f" {'':>14s}"

        print(line)


def main():
    if not RLC_ANNOTATIONS.exists():
        print(f"ERROR: RLC annotations not found at {RLC_ANNOTATIONS}", file=sys.stderr)
        sys.exit(1)

    print("Loading RLC annotations...")
    rlc_rows = load_rlc_annotations()
    print(f"  {len(rlc_rows)} total annotations")

    # ── RLC Case ────────────────────────────────────────────────────────
    rlc_case, rlc_case_skip, rlc_case_multi = extract_rlc_case_matrix(rlc_rows)
    print_matrix(rlc_case, CANONICAL_CASES, "RLC Case Confusion (agrcase + gov)", rlc_case_skip)
    print(f"  (multi-word spans skipped: {rlc_case_multi})")

    # ── RLC Gender ──────────────────────────────────────────────────────
    rlc_gender, rlc_gender_skip = extract_rlc_gender_matrix(rlc_rows)
    print_matrix(rlc_gender, CANONICAL_GENDERS, "RLC Gender Confusion (agrgender)", rlc_gender_skip)

    # ── RLC Number ──────────────────────────────────────────────────────
    rlc_number, rlc_number_skip = extract_rlc_number_matrix(rlc_rows)
    print_matrix(rlc_number, CANONICAL_NUMBERS, "RLC Number Confusion (agrnum)", rlc_number_skip)

    # ── RULEC-GEC ───────────────────────────────────────────────────────
    print("\nLoading RULEC-GEC M2 files...")
    rulec_triples = []
    for name in ["RULEC-GEC_dev_M2.txt", "RULEC-GEC_train_M2_updated.txt", "RULEC-GEC_test_M2_updated.txt"]:
        path = RULEC_DIR / name
        if path.exists():
            triples = load_rulec_m2(path)
            print(f"  {name}: {len(triples)} annotations")
            rulec_triples.extend(triples)

    rulec_case, rulec_case_skip = extract_rulec_case_matrix(rulec_triples)
    print_matrix(rulec_case, CANONICAL_CASES, "RULEC-GEC Case Confusion (Сущ./Прил.:Падеж)", rulec_case_skip)

    rulec_gender, rulec_gender_skip = extract_rulec_gender_matrix(rulec_triples)
    print_matrix(rulec_gender, CANONICAL_GENDERS, "RULEC-GEC Gender Confusion (Сущ./Прил.:Род)", rulec_gender_skip)

    rulec_number, rulec_number_skip = extract_rulec_number_matrix(rulec_triples)
    print_matrix(rulec_number, CANONICAL_NUMBERS, "RULEC-GEC Number Confusion (Сущ./Прил.:Число)", rulec_number_skip)

    # ── Comparison with literature ──────────────────────────────────────
    print_comparison(rlc_case, LITERATURE_CASE, CANONICAL_CASES,
                     "COMPARISON: RLC empirical vs Literature (case)")
    print_comparison(rulec_case, LITERATURE_CASE, CANONICAL_CASES,
                     "COMPARISON: RULEC empirical vs Literature (case)")

    # ── Export JSON for downstream use ──────────────────────────────────
    out = {
        "rlc_case": {k: dict(v) for k, v in rlc_case.items()},
        "rlc_gender": {k: dict(v) for k, v in rlc_gender.items()},
        "rlc_number": {k: dict(v) for k, v in rlc_number.items()},
        "rulec_case": {k: dict(v) for k, v in rulec_case.items()},
        "rulec_gender": {k: dict(v) for k, v in rulec_gender.items()},
        "rulec_number": {k: dict(v) for k, v in rulec_number.items()},
    }
    out_path = Path(__file__).parent.parent / "docs" / "research" / "confusion_matrices.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nRaw matrices saved to {out_path}")


if __name__ == "__main__":
    main()
