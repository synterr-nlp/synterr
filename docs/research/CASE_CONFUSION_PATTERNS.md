# Russian Case Confusion Patterns in L2 Learners

A literature review to inform linguistically-grounded case error generation in synterr.

## Problem Statement

Current implementation uses random case substitution, which doesn't reflect actual learner error patterns. For example, substituting Nominative with Dative is rare (Nom is the default/unmarked case), while substituting Dative with Accusative is very common.

## Key Findings from Literature

### 1. Acquisition Order

Rubinstein (1995) tested 136 American learners of Russian and found a consistent acquisition order across all proficiency levels:

| Stage | Cases | Notes |
|-------|-------|-------|
| Early | Prepositional, Accusative | Acquired first, highest accuracy |
| Middle | Genitive, Instrumental | Moderate difficulty |
| Late | Dative | Most difficult, lowest accuracy |

This order appears independent of:
- Amount of instruction received
- Order of presentation in curriculum
- Morphological complexity of the forms

**Source:** Rubinstein, G. (1995). "On case errors made in oral speech by American learners of Russian." *Slavic and East European Journal*, 39(3), 408–429.

### 2. Error Rates by Case

Research on advanced L2 learners (41-44 weeks of intensive instruction) shows:

| Case | Accuracy | Notes |
|------|----------|-------|
| Accusative | High | Acquired early |
| Prepositional | High | Acquired early |
| Genitive | Moderate | |
| Instrumental | Moderate | |
| Dative | **18.8%** | Severely difficult |

**Source:** Cited in multiple studies; original data from corpus studies of L2 Russian.

### 3. Default Case Substitution Patterns

#### Nominative as Default (L1 children)
Children aged 2-3 years tend to substitute oblique cases with Nominative forms. This suggests Nominative functions as the unmarked/default case in the Russian system.

#### Accusative as Default (L2 adults)
English-speaking learners tend to treat both direct and indirect objects the same way, using Accusative for both. This is likely L1 transfer — English doesn't distinguish these morphologically.

**Implication:** Errors *into* Nominative/Accusative are common; errors *from* Nominative are rare.

### 4. Accusative-Genitive Confusion

A major source of confusion due to the **animacy rule**:

- Inanimate masculine nouns: Accusative = Nominative form
- Animate masculine nouns: Accusative = Genitive form

This syncretism causes bidirectional confusion:
- Gen used where Acc is needed (and vice versa)
- Particularly problematic for animate masculine nouns

**Example errors:**
```
*Я вижу книги (Gen) → Я вижу книгу (Acc)  [inanimate]
*Я вижу брат (Nom/Acc) → Я вижу брата (Acc=Gen) [animate]
```

### 5. Dative Case Difficulties

Dative shows the lowest accuracy among L2 learners because:

1. **No English equivalent** — English uses word order and prepositions ("to X", "for X")
2. **Competition with Accusative** — Learners treat indirect objects as direct objects
3. **Late acquisition** — Even after extensive instruction, accuracy remains low

**Common error pattern:**
```
*Я дал книгу друг (Acc) → Я дал книгу другу (Dat)
*помогать маму (Acc) → помогать маме (Dat)
```

### 6. Heritage vs. L2 Learner Differences

Research comparing heritage speakers and traditional L2 learners found:

- Heritage learners: Lower overall case error rates
- L2 learners: Higher error rates, especially for Dative

This suggests heritage speakers retain some implicit knowledge of the case system even with limited formal instruction.

**Source:** Brill study on Heritage Language Journal (2018).

## Proposed Confusion Matrix

Based on the literature, we propose the following confusion probabilities:

```
P(substituted_case | correct_case)
```

### Nominative (correct)
Nominative is the unmarked/default case. Errors FROM Nominative are rare.

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| (no errors) | — | Nom is default, rarely substituted |

### Accusative (correct)
Accusative is acquired early but confused with Genitive (animacy) and Nominative (default).

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| Nom | 0.35 | Unmarked default |
| Gen | 0.40 | Animacy rule confusion |
| Dat | 0.15 | Rare |
| Ins | 0.10 | Rare |

### Genitive (correct)
Genitive is confused with Accusative (animacy) and occasionally Nominative.

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| Acc | 0.50 | Animacy rule, main confusion |
| Nom | 0.30 | Default substitution |
| Dat | 0.10 | |
| Ins | 0.10 | |

### Dative (correct)
Dative is the most difficult case. Learners default to Accusative.

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| Acc | 0.60 | Main substitution (L1 transfer) |
| Nom | 0.20 | Default |
| Gen | 0.10 | |
| Ins | 0.10 | |

### Instrumental (correct)
Instrumental is late-acquired. Various substitutions occur.

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| Acc | 0.30 | |
| Gen | 0.30 | с + Gen as alternative |
| Nom | 0.25 | Default |
| Dat | 0.15 | |

### Prepositional/Locative (correct)
Prepositional is acquired early but can be confused when preposition government is unclear.

| Substitution | Probability | Rationale |
|--------------|-------------|-----------|
| Acc | 0.40 | в школу vs в школе confusion |
| Nom | 0.30 | Default |
| Gen | 0.20 | |
| Dat | 0.10 | |

## Empirical Confusion Matrices (2026-03-05)

Extracted from RLC annotations.csv using `scripts/extract_confusion_matrices.py`.
RULEC is a subcorpus of RLC (academic writing, Portland State University,
Kisselev & Alsufieva). Our two data sources overlap in source essays but were
**annotated independently** (Kosakin et al. 2024, fn. 2: "Sentences from RULEC
have been annotated for RLC and RULEC-GEC independently"):
- **RLC-GEC** (`rlc-annotated/`): 31,519 sents, 41,410 annots, error-cause tags
- **RULEC-GEC** (`rulec-gec/`): Rozovskaya & Roth 2019, M2 format, POS-based tags
Near-identical confusion distributions from independent annotations strengthen
the empirical signal. Raw data: `docs/research/confusion_matrices.json`.

### Case Confusion — Empirical (RLC, N=2,760)

P(learner substitution | correct case). Rows = correct case, columns = what the learner wrote.

|  Correct | → Nom | → Acc | → Gen | → Dat | → Ins | → Loc | N |
|----------|------:|------:|------:|------:|------:|------:|----:|
| **Nom**  |   --- |    9% |  **52%** |    8% |   14% |   16% | 297 |
| **Acc**  |  34%  |   --- |   32% |   14% |    5% |   14% | 415 |
| **Gen**  | **53%** |  22% |   --- |    6% |    7% |   12% | 943 |
| **Dat**  |  35%  |  22%  |   27% |   --- |    8% |    9% | 265 |
| **Ins**  | **43%** |  15% |   26% |    8% |   --- |    8% | 425 |
| **Loc**  |  37%  |  17%  |   31% |    6% |    8% |   --- | 415 |

### Gender Confusion — Empirical (RLC, N=917)

| Correct | → Masc | → Fem | → Neut | N |
|---------|-------:|------:|-------:|----:|
| **Masc** |   --- | **62%** |   38% | 208 |
| **Fem**  | **68%** |   --- |   32% | 456 |
| **Neut** |   42% | **58%** |   --- | 253 |

### Number Confusion — Empirical (RLC, N=942)

| Correct | → Sing | → Plur | N |
|---------|-------:|-------:|----:|
| **Sing** |   --- | 100% | 330 |
| **Plur** | 100% |   --- | 612 |

Plur → Sing errors are ~2x more frequent than Sing → Plur.

### Key Divergences from Literature

1. **Nominative IS corrupted.** Literature (Rubinstein 1995) predicted "no errors
   from Nom." Empirical data shows 297 errors, primarily to Gen (52%). This likely
   reflects Gen-Nom syncretism in plural and Acc-Nom syncretism for inanimates.

2. **Nominative is the #1 substitution, not Accusative.** Literature predicted Acc
   as the default substitution (L1 transfer from English). Empirically, Nom is the
   #1 target for Gen (53%), Ins (43%), Loc (37%), Dat (35%). Acc is #1 only for
   itself (trivially). This aligns better with the L1-children pattern (Nom as
   unmarked default) than with the L2-adult pattern from Rubinstein.

3. **Genitive is a massive attractor.** Gen is #1 or #2 substitution for every
   case. Nom → Gen (52%) is the single largest cell. Literature underestimated
   this — likely because Gen has multiple syntactic functions (possession,
   negation, partitive, quantifier, preposition government).

4. **Dat → Acc is not dominant.** Literature predicted 60% Dat → Acc. Empirically:
   Dat → Nom (35%), Dat → Gen (27%), Dat → Acc (22%). Acc is only third.

5. **Locative is a real substitution target.** Literature matrix had no Loc column.
   Empirically Loc captures 8-16% of substitutions from every case, likely driven
   by preposition confusion (в + Acc vs в + Loc).

### Possible Explanations for Divergence

- **Population**: Rubinstein studied 136 American learners (oral speech). RLC has
  diverse L1 backgrounds (not just English) and written production.
- **Syncretism inflation**: pymorphy may assign Nom to forms that are syncretic
  with Acc (inanimate masc/neut). This would inflate Nom substitution counts.
- **Proficiency level**: RLC spans beginner to advanced. Rubinstein focused on
  specific instruction levels.
- **Written vs oral**: Written production allows more monitoring, possibly
  different error patterns than spontaneous speech.

### Revised Confusion Matrix for synterr

Based on empirical data, normalized to probabilities:

```yaml
# In configs/russian/rulec.yaml (or new empirical preset)
case_confusion:
  Nom: {Gen: 0.52, Loc: 0.16, Ins: 0.14, Acc: 0.09, Dat: 0.08}
  Acc: {Nom: 0.34, Gen: 0.32, Dat: 0.14, Loc: 0.14, Ins: 0.05}
  Gen: {Nom: 0.53, Acc: 0.22, Loc: 0.12, Ins: 0.07, Dat: 0.06}
  Dat: {Nom: 0.35, Gen: 0.27, Acc: 0.22, Dat: 0.09, Ins: 0.08}
  Ins: {Nom: 0.43, Gen: 0.26, Acc: 0.15, Dat: 0.08, Loc: 0.08}
  Loc: {Nom: 0.37, Gen: 0.31, Acc: 0.17, Ins: 0.08, Dat: 0.06}
```

## Implementation Recommendations

### 1. ~~Never substitute FROM Nominative~~ (REVISED)
Literature said Nom is never corrupted. Empirical data shows 297 Nom errors,
mainly to Gen (52%). **Do corrupt Nom, but at lower weight than oblique cases.**

### 2. Weight substitutions by empirical frequency
Genitive has the most errors (943), followed by Ins (425), Loc (415), Acc (415),
Sing→Plur (330), Dat (265), Nom (297). Weight error generation accordingly.

### 3. Consider animacy for Acc/Gen
The animacy rule should influence Acc↔Gen confusion rates:
- Animate masculine: higher Gen→Acc and Acc→Gen confusion
- Inanimate: lower confusion

### 4. Make weights configurable
Like spelling subtypes, case confusion weights should be in presets so they can be tuned with empirical data from RLC or RULEC.

## Data Sources

### Used for empirical matrices

1. **RLC-GEC** (`../gector/data/rlc-annotated/`) — Partial dump of RLC.
   31,519 sentences, 41,410 error annotations, error-cause tagset.
   Released by Kosakin et al. (2024).

2. **RULEC-GEC** (`../gector/data/rulec-gec/`) — RULEC subcorpus in M2 format.
   Rozovskaya & Roth (2019). POS-based morphological tags.
   Source essays overlap with RLC-GEC but annotated independently.

### Related tools

3. **RLC-ERRANT** — Rule-based auto-annotator for RLC error types.
   GitHub: `github.com/Russian-Learner-Corpus/annotator`.
   Uses pymorphy3 + Natasha, no dep tree. Key classification logic for case:
   - `wrong_case()` → case differs between learner/correct, same lemma
   - `noun_case()` → if NOUN/PRON/PROPN → "Gov" (or "Nominative" if correct is Nom)
   - else → "AgrCase" (adjective/det agreement error)
   Classification priority: WO > CS > Brev > Tense > Passive > Num > Gender >
   **Nominative/Gov/AgrCase** > AgrNum > AgrPers > AgrGender > Refl > Asp > ...
   Precision/recall on RLC-Test: Gov 0.91/0.75, Prep 0.97/0.78, Conj 0.77/0.87.

   Relevance to synterr: RLC-ERRANT *classifies* errors, synterr *generates* them.
   Could use RLC-ERRANT to evaluate synterr output quality. Also: synterr's dep-tree
   approach can distinguish Gov from AgrCase structurally (via dep_rel), whereas
   RLC-ERRANT uses POS heuristics.

## References

1. Rubinstein, G. (1995). On case errors made in oral speech by American learners of Russian. *Slavic and East European Journal*, 39(3), 408–429.

2. Kempe, V., & MacWhinney, B. (1998). The acquisition of case marking by adult learners of Russian and German. *Studies in Second Language Acquisition*, 20(4), 543–587.

3. Polinsky, M., & Kagan, O. (2007). Heritage languages: In the 'wild' and in the classroom. *Language and Linguistics Compass*, 1(5), 368–395.

4. Brill Heritage Language Journal (2018). Representational and Processing Constraints on the Acquisition of Case and Gender by Heritage and L2 Learners of Russian.

5. Sabia, I. (2003). Case-marking errors in L2 Russian and production rules. Master's thesis, University of Georgia.

6. Kosakin, D., Obiedkov, S., Rakhilina, E., Smirnov, I., Vyrenkova, A., & Zalivina, E. (2024). Russian Learner Corpus: Towards Error-Cause Annotation for L2 Russian. *LREC-COLING 2024*, pages 14240–14258.

7. Rozovskaya, A., & Roth, D. (2019). Grammar error correction in morphologically rich languages: The case of Russian. *TACL*, 7:1–17.

## Appendix: Proposed Code Structure

```yaml
# In configs/russian/rulec.yaml — EMPIRICAL (from RLC, N=2760)
case_confusion:
  Nom: {Gen: 0.52, Loc: 0.16, Ins: 0.14, Acc: 0.09, Dat: 0.08}
  Acc: {Nom: 0.34, Gen: 0.32, Dat: 0.14, Loc: 0.14, Ins: 0.05}
  Gen: {Nom: 0.53, Acc: 0.22, Loc: 0.12, Ins: 0.07, Dat: 0.06}
  Dat: {Nom: 0.35, Gen: 0.27, Acc: 0.22, Loc: 0.09, Ins: 0.08}
  Ins: {Nom: 0.43, Gen: 0.26, Acc: 0.15, Dat: 0.08, Loc: 0.08}
  Loc: {Nom: 0.37, Gen: 0.31, Acc: 0.17, Ins: 0.08, Dat: 0.06}
```

```python
# In morphological.py
class NounCaseHandler:
    DEFAULT_CONFUSION = { ... }

    def set_case_confusion(self, matrix: dict) -> None:
        """Set case confusion matrix from config."""
        self._confusion = matrix

    def _sample_wrong_case(self, correct_case: str, rng) -> str:
        """Sample a wrong case based on confusion probabilities."""
        if correct_case not in self._confusion:
            return None  # No errors for this case (e.g., Nom)
        weights = self._confusion[correct_case]
        cases = list(weights.keys())
        probs = list(weights.values())
        return rng.choices(cases, weights=probs, k=1)[0]
```
