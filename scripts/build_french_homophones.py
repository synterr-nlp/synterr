"""Build French Lexique-derived data files for the French PoC handlers.

Reads the local Lexique 3.83 TSV (not vendored into synterr — see
`LEXIQUE_TSV` below) and derives two JSON data files consumed by the French
PoC handlers described in `docs/research/FRENCH_POC_WORKFLOW.md`:

- `src/synterr/data/french/homophones.json`: the 5 grammatical-homophone
  confusion sets used by the `grammatical_homophone` handler
  (a_à, et_est, ce_se, on_ont, son_sont). Each surface form is keyed
  directly (handler-lookup shape) and lists every (POS, lemma, freqfilms2)
  reading Lexique records for it.

- `src/synterr/data/french/verb_ending_slots.json`: for the 2000 most
  frequent 1st-group (-er) verbs, the homophone ending clusters used by the
  `verb_ending_homophony` handler — derived empirically by grouping
  inflected forms sharing the same Lexique `phon` value, restricted to the
  five target slots: infinitive (-er), past participle (-é/-ée/-és/-ées),
  2nd-person plural present/imperative (-ez), 1sg future (-ai), and
  1st/2nd/3rd-singular conditional (-ais/-ait).

Per FRENCH_DESIGN.md §3.1 / §5.2: this is a *derivation* from Lexique's
`phon` and `infover` columns, not a hand-curated list — the confusion sets
and ending clusters fall out of grouping same-pronunciation forms rather
than being hand-typed.

Usage:
    uv run python scripts/build_french_homophones.py

The Lexique TSV lives outside the synterr repo and is never copied in;
`LEXIQUE_TSV` is the one documented path this script reads from.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Lexique 3.83, full column set (26MB). Lives in the local `dico` project,
# not vendored into synterr (per task instructions — read-only external
# source). See FRENCH_DESIGN.md §3.1.
LEXIQUE_TSV = Path.home() / "Projects" / "vibes" / "dico" / "data" / "Lexique383.tsv"

OUT_DIR = Path(__file__).resolve().parent.parent / "src" / "synterr" / "data" / "french"
HOMOPHONES_OUT = OUT_DIR / "homophones.json"
VERB_ENDING_SLOTS_OUT = OUT_DIR / "verb_ending_slots.json"

# The 5 grammatical-homophone confusion sets (FRENCH_POC_WORKFLOW.md #1).
CONFUSION_SETS: dict[str, list[str]] = {
    "a_à": ["a", "à"],
    "et_est": ["et", "est"],
    "ce_se": ["ce", "se"],
    "on_ont": ["on", "ont"],
    "son_sont": ["son", "sont"],
}

# Cap for the most-frequent -er verbs kept in verb_ending_slots.json.
TOP_N_VERBS = 2000


def load_rows(tsv_path: Path) -> list[dict[str, str]]:
    """Load the full Lexique TSV as a list of dict rows."""
    with tsv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def to_float(value: str) -> float:
    """Parse a Lexique frequency field (comma-free, dot-decimal); '' -> 0.0."""
    value = value.strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# 1. Grammatical homophone confusion sets
# ---------------------------------------------------------------------------


def build_homophones(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Derive the 5 confusion sets, keyed by surface form for handler lookup."""
    wanted_forms: set[str] = set()
    for members in CONFUSION_SETS.values():
        wanted_forms.update(members)

    forms: dict[str, dict[str, Any]] = {}
    form_to_set = {
        form: set_name for set_name, members in CONFUSION_SETS.items() for form in members
    }

    for row in rows:
        ortho = row["ortho"]
        if ortho not in wanted_forms:
            continue

        cgram = row["cgram"].strip()
        lemme = row["lemme"].strip()
        if not cgram or not lemme:
            continue

        entry = forms.setdefault(
            ortho,
            {"confusion_set": form_to_set[ortho], "readings": []},
        )
        entry["readings"].append(
            {
                "pos": cgram,
                "lemma": lemme,
                "freqfilms2": to_float(row["freqfilms2"]),
            }
        )

    # Sort readings by descending frequency for deterministic, weight-ready output.
    for entry in forms.values():
        entry["readings"].sort(key=lambda r: r["freqfilms2"], reverse=True)

    return {
        "_meta": {
            "description": (
                "Grammatical homophone confusion sets for the French PoC "
                "grammatical_homophone handler. Keyed by surface form for "
                "direct handler lookup; each form lists every (POS, lemma, "
                "freqfilms2) reading Lexique records for it, so the handler "
                "can gate the swap on POS/lemma/deprel at corrupt time."
            ),
            "source": "Lexique 3.83 (local, ~/Projects/vibes/dico/data/Lexique383.tsv)",
            "confusion_sets": CONFUSION_SETS,
            "generated_by": "scripts/build_french_homophones.py",
        },
        "forms": forms,
    }


# ---------------------------------------------------------------------------
# 2. Verb ending homophone slots (1st-group -er verbs)
# ---------------------------------------------------------------------------


def parse_infover_codes(infover: str) -> list[tuple[str, ...]]:
    """Split a Lexique `infover` field into its ';'-separated mode:tense:person codes.

    Examples:
        "inf;;"              -> [("inf",)]
        "par:pas;"            -> [("par", "pas")]
        "ind:pre:2p;imp:pre:2p;" -> [("ind", "pre", "2p"), ("imp", "pre", "2p")]
    """
    codes = []
    for chunk in infover.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        codes.append(tuple(chunk.split(":")))
    return codes


def code_to_features(code: tuple[str, ...]) -> dict[str, str | None]:
    """Turn a parsed infover code into a small feature dict."""
    if len(code) == 1:
        return {"mood": code[0], "tense": None, "person": None, "number": None}
    if len(code) == 2:
        return {"mood": code[0], "tense": code[1], "person": None, "number": None}
    mood, tense, person_number = code[0], code[1], code[2]
    person = person_number[0] if person_number and person_number[0].isdigit() else None
    number = person_number[1] if len(person_number) > 1 else None
    return {"mood": mood, "tense": tense, "person": person, "number": number}


def match_slot(code: tuple[str, ...]) -> str | None:
    """Classify one parsed infover code into one of the 5 target ending slots."""
    if code == ("inf",):
        return "inf"
    if code[:2] == ("par", "pas"):
        return "participle"
    if len(code) == 3 and code[0] in ("ind", "imp") and code[1] == "pre" and code[2] == "2p":
        return "ez"
    if len(code) == 3 and code[0] == "ind" and code[1] == "fut" and code[2] == "1s":
        return "fut_1s"
    if len(code) == 3 and code[0] == "cnd" and code[1] == "pre" and code[2] in ("1s", "2s", "3s"):
        return "cond"
    return None


# Lexique's `infover` column has occasional mis-tagged rows (e.g. "allier"
# carrying an "ind:pre:2p" code that actually belongs to "allez", not
# "aller"'s own -er/-ez/-é paradigm). A slot match is only trusted if the
# surface form also carries the orthographic ending that slot implies -
# cheap, principled noise filter, not a hand-curated exception list.
SLOT_ORTHO_SUFFIXES: dict[str, tuple[str, ...]] = {
    "inf": ("er",),
    "ez": ("ez",),
    "participle": ("é", "ée", "és", "ées"),
    "fut_1s": ("ai",),
    "cond": ("ais", "ait"),
}


def slot_ortho_is_plausible(slot: str, ortho: str) -> bool:
    """Check the surface form actually ends the way the matched slot implies."""
    return ortho.endswith(SLOT_ORTHO_SUFFIXES[slot])


def build_verb_ending_slots(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Derive homophone ending clusters for the top-N most frequent -er verbs."""
    ver_rows_by_lemma: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["cgram"].strip() != "VER":
            continue
        ver_rows_by_lemma[row["lemme"]].append(row)

    # Candidate 1st-group verbs: lemma ends in "-er" and has its own infinitive
    # row (ortho == lemme, infover contains the bare "inf" code).
    candidates: list[tuple[str, float]] = []
    for lemma, verb_rows in ver_rows_by_lemma.items():
        if not lemma.endswith("er"):
            continue
        for row in verb_rows:
            if row["ortho"] != lemma:
                continue
            codes = parse_infover_codes(row["infover"])
            if ("inf",) in codes:
                candidates.append((lemma, to_float(row["freqfilms2"])))
                break

    candidates.sort(key=lambda pair: pair[1], reverse=True)
    top_verbs = candidates[:TOP_N_VERBS]

    verbs: dict[str, Any] = {}
    for lemma, inf_freq in top_verbs:
        # Collect every (ortho, code, slot) hit across this verb's conjugated forms.
        slot_members: list[dict[str, Any]] = []
        for row in ver_rows_by_lemma[lemma]:
            for code in parse_infover_codes(row["infover"]):
                slot = match_slot(code)
                if slot is None:
                    continue
                if not slot_ortho_is_plausible(slot, row["ortho"]):
                    continue
                features = code_to_features(code)
                slot_members.append(
                    {
                        "ortho": row["ortho"],
                        "phon": row["phon"],
                        "slot": slot,
                        "mood": features["mood"],
                        "tense": features["tense"],
                        "person": features["person"],
                        "number": features["number"],
                        "genre": row["genre"].strip() or None,
                        "freqfilms2": to_float(row["freqfilms2"]),
                        "freqlivres": to_float(row["freqlivres"]),
                    }
                )

        if not slot_members:
            continue

        # Group into homophone clusters by shared `phon` (empirical, not
        # hand-assumed) — this is what actually makes forms confusable.
        by_phon: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for member in slot_members:
            by_phon[member["phon"]].append(member)

        clusters = []
        for phon, members in by_phon.items():
            # Dedupe identical (ortho, slot) pairs that can arise when a form
            # has multiple infover codes matching the same slot (e.g. an
            # ambiguous imp/ind "-ez" reading).
            seen = set()
            deduped = []
            for m in members:
                key = (m["ortho"], m["slot"], m["mood"], m["tense"], m["person"], m["number"])
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(m)

            clusters.append(
                {
                    "phon": phon,
                    "slots": sorted({m["slot"] for m in deduped}),
                    "endings": deduped,
                    "aggregate_freqfilms2": round(
                        sum(m["freqfilms2"] for m in deduped), 4
                    ),
                }
            )

        # Deterministic order: highest-frequency cluster first.
        clusters.sort(key=lambda c: c["aggregate_freqfilms2"], reverse=True)

        verbs[lemma] = {
            "freqfilms2": inf_freq,
            "clusters": clusters,
        }

    return {
        "_meta": {
            "description": (
                "Homophone ending clusters for 1st-group (-er) verbs, for "
                "the French PoC verb_ending_homophony handler. Derived "
                "empirically: forms are grouped by shared Lexique `phon` "
                "value, restricted to 5 target slots (inf, participle, ez, "
                "fut_1s, cond) identified from `infover` mode:tense:person "
                "codes. Capped to the top "
                f"{TOP_N_VERBS} -er verbs by infinitive freqfilms2."
            ),
            "source": "Lexique 3.83 (local, ~/Projects/vibes/dico/data/Lexique383.tsv)",
            "slots": {
                "inf": "infinitive (-er)",
                "participle": "past participle, all genre/number (-é/-ée/-és/-ées)",
                "ez": "2nd-person plural present/imperative (-ez)",
                "fut_1s": "1st-person singular future (-ai)",
                "cond": "1st/2nd/3rd-person singular conditional (-ais/-ait)",
            },
            "generated_by": "scripts/build_french_homophones.py",
            "n_verbs": len(verbs),
        },
        "verbs": verbs,
    }


def main() -> None:
    if not LEXIQUE_TSV.exists():
        print(f"Lexique TSV not found at {LEXIQUE_TSV}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {LEXIQUE_TSV} ...")
    rows = load_rows(LEXIQUE_TSV)
    print(f"  {len(rows)} rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building homophones.json ...")
    homophones = build_homophones(rows)
    HOMOPHONES_OUT.write_text(
        json.dumps(homophones, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    n_forms = len(homophones["forms"])
    print(f"  wrote {HOMOPHONES_OUT} ({n_forms} surface forms)")

    print("Building verb_ending_slots.json ...")
    verb_slots = build_verb_ending_slots(rows)
    VERB_ENDING_SLOTS_OUT.write_text(
        json.dumps(verb_slots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    n_verbs = len(verb_slots["verbs"])
    print(f"  wrote {VERB_ENDING_SLOTS_OUT} ({n_verbs} verbs)")


if __name__ == "__main__":
    main()
