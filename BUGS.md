# synterr Bug Report

Generated: 2026-01-24

## Critical Bugs

### 1. Global `random` breaks reproducibility

**Files:**
- `src/synterr/languages/russian/errors/morphological.py` (lines 76, 131, 185, 238, 297, 356, 364, 424)
- `src/synterr/languages/russian/errors/spelling.py` (lines 258, 321, 323, 398, 417, 431)

**Problem:** Handlers use `random.choice()` and `random.random()` from global module while pipeline has `self._rng = random.Random(self.config.seed)`. Breaks reproducibility.

**Fix:** Pass `rng` to handlers or use a shared seeded RNG.

```python
# Current (BAD):
target_case = random.choice(other_cases)

# Should be:
target_case = rng.choice(other_cases)
```

---

### 2. Batch processing misalignment with empty strings

**File:** `src/synterr/languages/russian/backends/stanza_backend.py` (lines 84-111)

**Problem:** Empty strings cause sentence misalignment in batch processing.

```python
texts = ['', 'Мама.']
# Result:
#   Sentence 0: ['Мама', '.']  # WRONG - should be []
#   Sentence 1: []              # WRONG - should be ['Мама', '.']
```

**Fix:** Handle empty inputs explicitly before stanza processing.

---

## High Priority

### 3. VerbPersonNumber logic error

**File:** `src/synterr/languages/russian/errors/morphological.py` (lines 356-367)

**Problem:** Past tense verbs (have Number, no Person) fail ~50% due to random check order.

```python
if token.has_feature("Number") and random.random() < 0.5:
    # change number
elif token.has_feature("Person"):
    # change person
# Past tense: has Number, no Person -> 50% returns None unnecessarily
```

**Fix:** Check Person first, or handle past-tense-only case.

---

## Medium Priority

### 4. Case bugs in spelling handler

**File:** `src/synterr/languages/russian/errors/spelling.py`

**4a. `_double_consonant` (lines 392-400):** Inserts lowercase char into uppercase words.
```
"КИНО" -> "КИнНО"  (should be "КИННО")
```

**4b. `_cluster` (lines 365-378):** Only capitalizes first letter of replacement.
```
"ЧЕСТНЫЙ" -> "ЧЕСнЫЙ"  (should be "ЧЕСНЫЙ")
```

**Fix:** Match case of each character individually.

---

### 5. Inconsistent `end_idx` in ErrorResult

**Files:**
- `src/synterr/languages/russian/errors/spelling.py` line 247: `end_idx=idx` (WRONG)
- `src/synterr/languages/russian/errors/morphological.py` line 91: `end_idx=idx+1` (correct)

**Fix:** Change spelling.py to `end_idx=idx+1`.

---

## Low Priority

### 6. Soft sign deletion produces empty string

**File:** `src/synterr/languages/russian/errors/spelling.py` (lines 436-441)

```python
handler._soft_sign("ь")  # Returns corrupted=''
```

**Fix:** Check word length > 1 before applying.

---

### 7. Schema mapping converts None to 'None'

**File:** `src/synterr/schemas/loader.py` (line 287)

```python
mappings[subtype] = SubtypeMapping(primary=str(mapping_info))  # str(None) = 'None'
```

**Fix:** Handle None explicitly.

---

### 8. Mixed case not preserved

**File:** `src/synterr/languages/russian/inflector.py` (lines 59-76)

```
"МаМа" -> "Мамы"  (loses internal caps)
```

**Fix:** Preserve per-character capitalization pattern.

---

### 9. Verb tense inflection silently fails

**File:** `src/synterr/languages/russian/errors/morphological.py` (lines 404-443)

Some verbs can't inflect to certain tenses (e.g., "идти" -> future requires "буду идти").

**Fix:** Try alternative tenses or skip gracefully.

---

### 10. Error collision in _format_output

**File:** `src/synterr/core/pipeline.py` (lines 251-254)

```python
for err in errors:
    error_at[err.start_idx] = err  # Later overwrites earlier
```

Protected by `modified` set in practice, but API could be misused.

---

## Summary

| # | Bug | Severity | File |
|---|-----|----------|------|
| 1 | Global random | **Critical** | morphological.py, spelling.py |
| 2 | Batch misalign | **Critical** | stanza_backend.py |
| 3 | VerbPersonNumber | **High** | morphological.py |
| 4 | Case in spelling | **Medium** | spelling.py |
| 5 | end_idx inconsistent | **Medium** | spelling.py |
| 6 | Empty soft sign | Low | spelling.py |
| 7 | None to 'None' | Low | loader.py |
| 8 | Mixed case | Low | inflector.py |
| 9 | Tense inflection | Low | morphological.py |
| 10 | Error collision | Low | pipeline.py |
