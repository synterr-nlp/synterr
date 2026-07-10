# Dep-Tree Morphological Error Handlers — Design Notes

Future upgrade path for morphological handlers. Currently all morph handlers are
"dep-blind" — they pick a random token and flip a random grammeme. The dep tree
(already parsed by stanza for punct handlers) enables linguistically motivated errors.

## Current State

All handlers in `morphological.py` do:
```python
current_case = token.get_feature("Case")
other_cases = [c for c in CASES if c != current_case]
target_case = rng.choice(other_cases)  # random!
```

No awareness of syntactic role, governing verb, or agreement target.

## Upgrade 1: Confusion-Matrix-Driven Case Substitution

Replace random grammeme selection with empirical confusion matrices extracted
from learner corpora (RLC + RULEC-GEC).

Literature-based matrix already in `CASE_CONFUSION_PATTERNS.md`. Empirical
matrix to be extracted via `scripts/extract_confusion_matrices.py`.

### Implementation

```python
class NounCaseErrorHandler:
    # Loaded from config preset
    CONFUSION = {
        "Nom": {},  # No errors from Nom
        "Acc": {"Nom": 0.35, "Gen": 0.40, "Dat": 0.15, "Ins": 0.10},
        "Gen": {"Acc": 0.50, "Nom": 0.30, "Dat": 0.10, "Ins": 0.10},
        # ...
    }

    def _sample_wrong_case(self, correct_case, rng):
        if correct_case not in self.CONFUSION:
            return None
        weights = self.CONFUSION[correct_case]
        return rng.choices(list(weights.keys()), list(weights.values()))[0]
```

### Key insight: Never corrupt FROM Nominative
Learners don't make errors where Nom is correct — it's the default/unmarked case.

## Upgrade 2: Dep-Tree-Aware Agreement Errors

Use `head_idx` and `dep_rel` to find agreement pairs and break them.

### Adjective Agreement (amod)

```
"красивый дом" → dep tree: красивый --amod--> дом
```

- Follow `amod` link to find the noun
- Know the noun's Case/Gender/Number
- Change the adjective to *disagree* with that specific noun
- Use confusion matrix for which grammeme to substitute

Handlers: AdjCaseErrorHandler, AdjGenderErrorHandler, AdjNumberErrorHandler

### Subject-Verb Agreement (nsubj)

```
"студенты пришли" → dep tree: студенты --nsubj--> пришли
```

- Follow `nsubj`/`nsubj:pass` to find the subject
- Change verb number/person to disagree with subject
- Especially valuable for long-distance agreement:
  "Группа студентов, которые сдали экзамен, *пришёл* на лекцию"

Handler: VerbPersonNumberErrorHandler

### Prepositional Government (case + obl)

```
"в школе" → dep tree: в --case--> школе, школе --obl--> [verb]
```

- Find `case` dep_rel (preposition → noun)
- Know which preposition governs which case
- Change noun to a case the preposition doesn't take
- Use preposition-specific confusion data (в + Acc vs в + Prep)

Handler: NounCaseErrorHandler (with dep context)

## Upgrade 3: New Handler Types (dep-tree only)

### Relative Pronoun Agreement

```
"студентка, которая пришла" → dep tree: которая --nsubj--> пришла, пришла --acl:relcl--> студентка
```

- Find `acl:relcl` nodes
- The relative pronoun (который/которая/которое) should agree with antecedent
- Change gender/number to disagree
- Very common L2 error

### Determiner Agreement (det)

```
"этот дом" → dep tree: этот --det--> дом
```

- Change demonstrative gender/number/case to disagree with noun
- Similar to adjective agreement but separate POS

### Long-Distance Agreement

- Find `nsubj` pairs separated by subordinate clauses
- Break agreement across clause boundaries
- Produces realistic errors that learners actually make

## Data Sources for Confusion Matrices

### RLC (Russian Learner Corpus) — `../gector/data/rlc-annotated/`
- annotations.csv: ~7,270 agreement/gov examples
- Tags: agrcase (1,291), agrnum (1,163), agrgender (1,092), agrpers (297), gov (3,426)
- Has quote (learner form) + correction (target form)

### RULEC-GEC — `../gector/data/rulec-gec/`
- M2 format, finer tags (Noun:Case vs Adj:Case, etc.)
- ~3,224 morphological examples across dev/train/test
- Noun:Case (1,521), Adj:Case (388), Noun:Number (287), Verb:Num/Pers (285)

### Extraction pipeline
1. Take (quote, correction) pairs
2. Run both through pymorphy → get grammemes
3. Build P(learner_grammeme | correct_grammeme) per error type
4. Compare with literature-based matrix in CASE_CONFUSION_PATTERNS.md

## Comparison with RLC-ERRANT

RLC-ERRANT (`github.com/Russian-Learner-Corpus/annotator`, Kosakin et al. 2024)
is a rule-based error *classifier* (original+correction → error tag). It
complements synterr which is an error *generator* (clean → corrupted).

RLC-ERRANT's case classification (classifier.py lines 194-198):
```python
if wrong_case(o_toks, c_toks):       # case differs, same lemma
    if noun_case(o_toks, c_toks):     # NOUN/PRON/PROPN present?
        return "Nominative" if nominative(c_toks) else "Gov"
    else:
        return "Agrcase"              # adj/det = agreement error
```

Key difference: RLC-ERRANT distinguishes Gov vs AgrCase by **POS** (noun → Gov,
adj → AgrCase). synterr can do it by **dep_rel** (obj/obl → Gov, amod/det →
AgrCase), which is more precise for multi-word constructions.

RLC-ERRANT uses no dep tree at all — pymorphy3 + Natasha POS only. synterr's
dep-tree approach could:
1. More accurately distinguish Gov from agreement errors
2. Target specific syntactic positions for corruption
3. Generate long-distance agreement errors (across clause boundaries)

Potential use: run RLC-ERRANT on synterr output to evaluate whether generated
errors are classified correctly (round-trip validation).

## Priority Order

1. **Confusion matrices** — DONE. Extracted from RLC + RULEC, compared with literature.
   See `CASE_CONFUSION_PATTERNS.md` and `confusion_matrices.json`.
2. **NounCaseErrorHandler** — add confusion matrix + dep_rel context (obj vs obl)
3. **AdjCase/Gender/NumberErrorHandler** — follow amod to disagree with head noun
4. **VerbPersonNumberErrorHandler** — follow nsubj to disagree with subject
5. **New: RelativePronounHandler** — acl:relcl + который agreement
6. **New: LongDistanceAgreementHandler** — nsubj across clause boundaries
