# RuBLiMP vs synterr Comparison

## Overview

| | **RuBLiMP** | **synterr** |
|---|---|---|
| **Purpose** | Evaluate LM grammatical knowledge | Generate training data for GEC |
| **Method** | Minimal pairs (grammatical vs ungrammatical) | Realistic learner-like errors |
| **Output** | Score/probability comparison | GECToR format with fix tags |
| **Use case** | Probing: "Does model know X is wrong?" | Training: "Generate error X for training" |

## Complementary, Not Competing

RuBLiMP and synterr serve different purposes:

- **RuBLiMP**: Creates contrastive test cases for evaluating models
- **synterr**: Creates corrupted training data for training models

However, RuBLiMP's **perturbation rules** and **linguistic resources** are directly useful for synterr.

---

## Phenomena Coverage Comparison

### Agreement (RuBLiMP: 29 phenomena, synterr: partial)

| Phenomenon | RuBLiMP | synterr | Notes |
|------------|---------|---------|-------|
| NP agreement (case/gender/number) | ✅ | ❌ TODO | Requires depparse |
| Subject-predicate agreement | ✅ | ❌ TODO | Requires depparse |
| Anaphor agreement | ✅ | ❌ TODO | Relative clauses |
| Floating quantifier agreement | ✅ | ❌ | Low priority |
| Attractors/interveners | ✅ | ❌ | Complex |

### Government (RuBLiMP: 5 phenomena, synterr: none)

| Phenomenon | RuBLiMP | synterr | Notes |
|------------|---------|---------|-------|
| Preposition case government | ✅ | ❌ TODO | Has `ADP_CASES` dict |
| Verb case government (Acc/Gen/Ins) | ✅ | ❌ TODO | Needs `GOV_DICT` |

### Morphology (RuBLiMP: 6 phenomena, synterr: 8 handlers)

| Phenomenon | RuBLiMP | synterr | Notes |
|------------|---------|---------|-------|
| Noun declension | ✅ | ✅ `noun_case`, `noun_number` | |
| Verb conjugation | ✅ | ✅ `verb_person_number`, `verb_tense` | |
| Adjective inflection | ✅ | ✅ `adj_*` | |
| Word formation (suffixes/prefixes) | ✅ | ❌ | Derivational, complex |

### Aspect/Tense (RuBLiMP: 10 phenomena, synterr: partial)

| Phenomenon | RuBLiMP | synterr | Notes |
|------------|---------|---------|-------|
| Aspect with duration/repetition | ✅ | ❌ TODO | Has 2716 aspect pairs! |
| Tense agreement | ✅ | ✅ `verb_tense` | |

### Lexical/Other

| Phenomenon | RuBLiMP | synterr | Notes |
|------------|---------|---------|-------|
| Spelling errors | ❌ | ✅ `spelling` | Not relevant for LM probing |
| Paronyms | ❌ | ✅ `paronym` (planned) | Learner-specific |
| Omission/Insertion | ❌ | ❌ TODO | Structural errors |

---

## Reusable Resources from RuBLiMP

### 1. Aspect Pairs (`src/data/aspect_pair_zal.csv`)
- **2716 imperfective↔perfective pairs** from Zaliznjak
- Format: `Imp,Perf` columns
- Can directly use for synterr's `aspect` handler

### 2. Preposition-Case Mapping (`src/phenomena/government/constants.py`)
```python
ADP_CASES = {
    "в": ("accs", "loct"),      # direction vs location
    "на": ("accs", "loct"),
    "с": ("gent", "accs", "ablt"),
    "за": ("accs", "ablt"),
    "под": ("accs", "ablt"),
    # ... 19 prepositions total
}
```
Can use for synterr's preposition government errors.

### 3. Frequency Dictionary (`src/data/freqrnc2011.csv`)
- From Russian National Corpus
- Useful for weighted sampling

### 4. Morphological Constants
- POS mappings between UD and pymorphy2
- Feature value sets
- Agreement relation types

---

## What RuBLiMP Doesn't Do (synterr's Niche)

1. **Spelling errors** — Not relevant for LM grammaticality probing
2. **Learner-specific errors** — Paronyms, L1 transfer, overgeneralization
3. **Structural errors** — Omissions, insertions, word order (Miss/Extra)
4. **Training data format** — No GECToR-compatible output
5. **Error distribution modeling** — No learner corpus statistics

---

## Recommendations

### Import from RuBLiMP:
1. Copy `aspect_pair_zal.csv` → `synterr/data/russian/aspect_pairs.csv`
2. Copy `ADP_CASES` → `synterr/data/russian/prep_case.json`
3. Reference their agreement code for depparse-based handlers

### Keep separate:
1. Spelling generation (synterr-specific)
2. Learner error distribution (from RULEC-GEC/GERA analysis)
3. Output formatting (GECToR format)

---

## Integration Plan

1. **Phase 1**: Copy aspect pairs, preposition-case data
2. **Phase 2**: Implement `aspect` handler using RuBLiMP pairs
3. **Phase 3**: Implement agreement handlers (study RuBLiMP's approach)
4. **Phase 4**: Implement government handlers using their constants

This allows synterr to leverage RuBLiMP's linguistic resources while maintaining its distinct purpose (GEC training data generation).
