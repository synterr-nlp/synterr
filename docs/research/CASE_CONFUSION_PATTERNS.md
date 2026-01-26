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

## Implementation Recommendations

### 1. Never substitute FROM Nominative
Nominative is the default case. Learners don't make errors where Nom is correct.

### 2. Weight substitutions by acquisition difficulty
- Easy cases (Acc, Prep) → fewer errors
- Hard cases (Dat, Ins) → more errors

### 3. Consider animacy for Acc/Gen
The animacy rule should influence Acc↔Gen confusion rates:
- Animate masculine: higher Gen→Acc and Acc→Gen confusion
- Inanimate: lower confusion

### 4. Make weights configurable
Like spelling subtypes, case confusion weights should be in presets so they can be tuned with empirical data from RLC or RULEC.

## Data Sources for Validation

To validate/refine these weights, we could:

1. **Russian Learner Corpus (RLC)** — http://www.web-corpora.net/RLC/stats/
   - 2M+ tokens, error-annotated
   - Distinguishes heritage vs. L2 learners

2. **RULEC-GEC** — Already used for handler weights
   - Could extract case-specific error patterns

3. **REALEC** — Russian Error-Annotated Learner English Corpus
   - Different direction but similar methodology

## References

1. Rubinstein, G. (1995). On case errors made in oral speech by American learners of Russian. *Slavic and East European Journal*, 39(3), 408–429.

2. Kempe, V., & MacWhinney, B. (1998). The acquisition of case marking by adult learners of Russian and German. *Studies in Second Language Acquisition*, 20(4), 543–587.

3. Polinsky, M., & Kagan, O. (2007). Heritage languages: In the 'wild' and in the classroom. *Language and Linguistics Compass*, 1(5), 368–395.

4. Brill Heritage Language Journal (2018). Representational and Processing Constraints on the Acquisition of Case and Gender by Heritage and L2 Learners of Russian.

5. Sabia, I. (2003). Case-marking errors in L2 Russian and production rules. Master's thesis, University of Georgia.

## Appendix: Proposed Code Structure

```python
# In configs/russian/rulec.yaml
case_confusion:
  # P(error_case | correct_case)
  Nom: {}  # No errors from Nominative
  Acc: {Nom: 0.35, Gen: 0.40, Dat: 0.15, Ins: 0.10}
  Gen: {Acc: 0.50, Nom: 0.30, Dat: 0.10, Ins: 0.10}
  Dat: {Acc: 0.60, Nom: 0.20, Gen: 0.10, Ins: 0.10}
  Ins: {Acc: 0.30, Gen: 0.30, Nom: 0.25, Dat: 0.15}
  Loc: {Acc: 0.40, Nom: 0.30, Gen: 0.20, Dat: 0.10}
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
