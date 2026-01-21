# Label Schema Reference

This document defines the mapping between linguistic error taxonomies, synterr handlers, and GECToR output format.

## Three-Layer Schema

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RLC TAXONOMY (38 tags)                          │
│   Linguistic classification of error causes                         │
│   Gov, AgrCase, AgrNum, Asp, Infl, Lex, Miss, Extra, ...           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ maps to
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SYNTERR HANDLERS                                  │
│   Implementation modules                                            │
│   spelling, noun_case, paronym, word_omission, ...                 │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ outputs
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   GECTOR FORMAT                                     │
│   Detection label + Fix tag                                         │
│   SPELL/MORPH/OTHER + $REPLACE/$TRANSFORM/$APPEND/$DELETE          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## RLC Taxonomy → synterr Handler Mapping

### Orthography

| RLC Tag | Description | synterr Handler | Status |
|---------|-------------|-----------------|--------|
| `Ortho` | Spelling/orthography | `spelling` | ✅ |
| `Misspell` | Typos | `spelling` | ✅ |
| `Graph` | Script confusion (е/ё) | `spelling` | ✅ |
| `Hyphen` | Hyphenation errors | — | ❌ |
| `Space` | Word boundary errors | — | ❌ |

### Inflection (Paradigm Errors)

| RLC Tag | Description | synterr Handler | Status |
|---------|-------------|-----------------|--------|
| `Infl` | Wrong inflectional ending | `noun_case`, `noun_number`, `adj_*`, `verb_*` | ✅ |
| `Num` | Number marking | `noun_number`, `adj_number` | ✅ |
| `Gender` | Gender marking | `adj_gender` | ✅ |

### Agreement

| RLC Tag | Description | synterr Handler | Requires |
|---------|-------------|-----------------|----------|
| `AgrCase` | Case agreement | `agr_case` | depparse |
| `AgrNum` | Number agreement | `agr_number` | depparse |
| `AgrGender` | Gender agreement | `agr_gender` | depparse |
| `AgrPers` | Person agreement | `agr_person` | depparse |

### Government

| RLC Tag | Description | synterr Handler | Requires |
|---------|-------------|-----------------|----------|
| `Gov` | Verb/prep case government | `government` | depparse + GOV_DICT |

### Verbal Categories

| RLC Tag | Description | synterr Handler | Requires |
|---------|-------------|-----------------|----------|
| `Asp` | Aspect confusion | `aspect` | ASP_PAIRS dict |
| `Tense` | Tense errors | `verb_tense` | ✅ |
| `Refl` | Reflexive -ся/-сь | `reflexive` | ❌ |
| `Brev` | Short/long adjective | `short_adj` | ❌ |
| `Passive` | Voice errors | `voice` | ❌ |
| `Mode` | Mood (conditional) | — | ❌ |

### Lexical/Semantic

| RLC Tag | Description | synterr Handler | Requires |
|---------|-------------|-----------------|----------|
| `Lex` | Lexical choice | `paronym` | paronyms.json ✅ |
| `Prep` | Preposition choice | `preposition` | PREP_GROUPS |
| `Conj` | Conjunction choice | `conjunction` | CONJ_PAIRS |
| `Aux` | Auxiliary verbs | — | ❌ |
| `Ref` | Pronoun reference | — | ❌ |

### Structural

| RLC Tag | Description | synterr Handler | Length-changing |
|---------|-------------|-----------------|-----------------|
| `Miss` | Missing word | `word_omission` | YES |
| `Extra` | Extra word | `word_insertion` | YES |
| `WO` | Word order | `word_order` | NO (swap) |

### Other RLC Tags (Not Prioritized)

| RLC Tag | Description | Notes |
|---------|-------------|-------|
| `Morph` | Derivational morphology | Complex, low frequency |
| `Altern` | Stem alternation | Covered by pymorphy3 |
| `Constr` | Constructional | Requires deep syntax |
| `Idiom` | Idiomatic expressions | Requires idiom database |
| `CS` | Code-switching | L2-specific |
| `Transfer` | L1 transfer | L1-dependent |

---

## GECToR Output Format

### Detection Labels

| Label | Description | Error Types |
|-------|-------------|-------------|
| `CORRECT` | No error at this position | — |
| `SPELL` | Orthographic/spelling error | `Ortho`, `Misspell`, `Graph` |
| `MORPH` | Morphological error | `Infl`, `Agr*`, `Gov`, `Asp`, `Tense` |
| `PUNCT` | Punctuation error | (not implemented) |
| `OTHER` | Lexical, structural, other | `Lex`, `Prep`, `Conj`, `Miss`, `Extra`, `WO` |

### Fix Tags

| Tag Pattern | Description | When Used |
|-------------|-------------|-----------|
| `$KEEP` | Token is correct | No error |
| `$DELETE` | Delete this token | `Extra` (inserted filler) |
| `$REPLACE_word` | Replace with word | `Lex`, `Prep`, `Conj` |
| `$TRANSFORM_CASE_X` | Change case to X | `Infl` (case), `AgrCase`, `Gov` |
| `$TRANSFORM_NUM_X` | Change number to X | `Infl` (number), `AgrNum` |
| `$TRANSFORM_GENDER_X` | Change gender to X | `AgrGender` |
| `$TRANSFORM_TENSE_X` | Change tense to X | `Tense` |
| `$TRANSFORM_PERSON_X` | Change person to X | `AgrPers` |
| `$APPEND_word` | Append word after | `Miss` (omitted word) |
| `$MERGE_word` | Merge with next token | (rare) |

### Output Line Format

```
$STARTSEPL|||SEPR$KEEP:CORRECT ПервоеСловоSEPL|||SEPR$REPLACE_верное:SPELL ашибкаSEPL|||SEPR...
```

Structure:
- `$START` — sentence start marker
- `SEPL|||SEPR` — token separator
- `$TAG:CATEGORY word` — fix tag, detection category, corrupted token

---

## Length-Changing Errors

### The Problem

Most errors are **token-preserving**: they corrupt a word but don't change the token count.

```
Original:  [Я] [иду] [в] [школу]     # 4 tokens
Corrupted: [Я] [иду] [в] [школы]     # 4 tokens (case error on школу→школы)
```

**Length-changing errors** add or remove tokens:

```
# Omission (Miss): delete a token
Original:  [Я] [иду] [в] [школу]     # 4 tokens
Corrupted: [Я] [иду] [школу]         # 3 tokens (preposition deleted)

# Insertion (Extra): add a token
Original:  [Он] [читает] [книгу]     # 3 tokens
Corrupted: [Он] [вот] [читает] [книгу]  # 4 tokens (filler inserted)
```

### Index Corruption Problem

If we delete token at index 2, all subsequent indices shift:

```
Before:  [0:Я] [1:иду] [2:в] [3:школу]
Delete idx 2
After:   [0:Я] [1:иду] [2:школу]  # "школу" moved from 3→2!
```

If we've already recorded that there's an error at index 3, that's now wrong.

### Solution: Apply Length-Changing Errors Last

The pipeline:
1. First applies all **token-preserving** errors (spelling, case, etc.)
2. Then applies **length-changing** errors (omission, insertion)
3. Only one length-changing error per sentence (to keep it simple)

### Handler Declaration

Handlers must declare if they change length:

```python
class WordOmissionHandler:
    name = "word_omission"
    category = "OTHER"
    changes_length = True   # ← Required for Miss/Extra

class SpellingErrorHandler:
    name = "spelling"
    category = "SPELL"
    changes_length = False  # ← Default, can omit
```

### Fix Tags for Length-Changing Errors

**Omission (`Miss`)**: The fix is to APPEND the missing word

```python
# "Я иду школу" ← missing "в"
# The token BEFORE where "в" should be gets the fix tag
# Token "иду" gets: $APPEND_в:OTHER

ErrorResult(
    error_type="word_omission",
    category="OTHER",
    start_idx=1,          # index of "иду" (word before gap)
    end_idx=1,
    original="в",         # what was deleted
    corrupted="",         # nothing (it's gone)
    fix_tag="$APPEND_в",  # fix = append "в" after this position
)
```

**Insertion (`Extra`)**: The fix is to DELETE the inserted word

```python
# "Он вот читает книгу" ← "вот" is extra
# The inserted token gets: $DELETE:OTHER

ErrorResult(
    error_type="word_insertion",
    category="OTHER",
    start_idx=1,          # index of inserted "вот"
    end_idx=1,
    original="",          # nothing was there
    corrupted="вот",      # what was inserted
    fix_tag="$DELETE",    # fix = delete this token
)
```

### What Can Be Omitted/Inserted

**Omission targets** (function words that learners often forget):
- Prepositions: в, на, с, к, из, от, по, за, о, у
- Particles: бы, ли, же, не, ни
- Conjunctions: и, а, но, что, чтобы, если, когда
- Reflexive: -ся (as separate token after vowel)

**Insertion targets** (fillers/hedges that learners overuse):
- Discourse markers: вот, ну, так, ведь, же
- Hedges: как бы, типа, значит, это
- Repetitions: duplicate adjacent word

---

## Category Assignment Logic

```python
def get_category(handler_name: str) -> str:
    """Map handler to detection category."""

    SPELL_HANDLERS = {"spelling"}

    MORPH_HANDLERS = {
        "noun_case", "noun_number",
        "adj_case", "adj_number", "adj_gender",
        "verb_person_number", "verb_tense",
        "agr_case", "agr_number", "agr_gender", "agr_person",
        "government", "aspect", "reflexive", "voice",
    }

    PUNCT_HANDLERS = {"punctuation"}  # not implemented

    # Everything else is OTHER
    # Includes: paronym, preposition, conjunction,
    #           word_omission, word_insertion, word_order

    if handler_name in SPELL_HANDLERS:
        return "SPELL"
    elif handler_name in MORPH_HANDLERS:
        return "MORPH"
    elif handler_name in PUNCT_HANDLERS:
        return "PUNCT"
    else:
        return "OTHER"
```

---

## References

- **RLC Taxonomy**: Kosakin et al. (2024) "Russian Learner Corpus: Towards Error-Cause Annotation" — https://aclanthology.org/2024.lrec-main.1241/
- **RULEC-GEC**: Rozovskaya & Roth (2019) "Grammar Error Correction in Morphologically Rich Languages" — https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251
- **GECToR Format**: Omelianchuk et al. (2020) "GECToR – Grammatical Error Correction: Tag, Not Rewrite"
