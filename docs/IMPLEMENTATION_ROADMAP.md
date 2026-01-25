# Implementation Roadmap for synterr

This document outlines remaining error types to implement, required linguistic resources, and technical considerations.

## Architecture Overview

synterr uses a **rule inversion** approach:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Rule Lookup    │ →   │    Inversion    │ →   │  Output + Tag   │
│  "What's right" │     │ "Make it wrong" │     │  GECToR format  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

Each `ErrorHandler` implements:
- `can_apply(tokens, idx)` — Check if this error type applies at position
- `apply(tokens, sentence, idx, modified)` — Generate the corrupted form

Error categories map to detection labels: `SPELL`, `MORPH`, `PUNCT`, `OTHER`

---

## Currently Implemented

| Handler | RLC Tag | Category | Notes |
|---------|---------|----------|-------|
| `spelling` | `Ortho`, `Misspell` | SPELL | Phonetic confusions, keyboard typos |
| `noun_case` | `Infl` | MORPH | Wrong case ending |
| `noun_number` | `Infl` | MORPH | Singular ↔ plural |
| `adj_case` | `Infl` | MORPH | Adjective case |
| `adj_number` | `Infl` | MORPH | Adjective number |
| `adj_gender` | `Infl` | MORPH | Adjective gender |
| `verb_person_number` | `Infl` | MORPH | Verb conjugation |
| `verb_tense` | `Infl` | MORPH | Past/present/future |

Resources used: **pymorphy3** (paradigm database from Zaliznjak/OpenCorpora)

---

## To Implement

### Priority 1: Lexical Errors (No depparse needed)

#### 1.1 Paronym Confusion (`Lex`)
- **Resource**: `data/russian/paronyms.json` ✅ Already created
- **Category**: OTHER
- **Implementation**: Look up word in paronym dict, substitute confusable pair

```python
# Example
"одеть пальто" → "надеть пальто"  # одеть/надеть confusion
"эффектный приём" → "эффективный приём"  # эффектный/эффективный
```

#### 1.2 Preposition Substitution (`Prep`)
- **Resource needed**: Preposition similarity groups
- **Category**: OTHER
- **Implementation**: Substitute semantically similar prepositions

```python
PREP_GROUPS = {
    "spatial": ["в", "на", "у", "около", "возле"],
    "temporal": ["в", "на", "за", "через"],
    "causal": ["из-за", "благодаря", "вследствие"],
}
# "в комнате" → "на комнате" ❌
```

#### 1.3 Conjunction Substitution (`Conj`)
- **Resource needed**: Conjunction confusion pairs
- **Category**: OTHER

```python
CONJ_CONFUSIONS = {
    "а": ["но", "и"],
    "что": ["чтобы"],
    "потому что": ["поэтому"],  # cause/effect reversal
}
```

#### 1.4 Particle Errors
- **Category**: OTHER
- **Implementation**: Delete particles (бы, ли, же) or insert in wrong position

---

### Priority 2: Agreement Errors (Requires `--depparse`)

These require dependency parsing to find the controller-target relationship.

#### 2.1 Adjective-Noun Agreement (`AgrCase`, `AgrGender`, `AgrNum`)
- **Dependency relation**: `amod` (adjectival modifier)
- **Category**: MORPH
- **Implementation**: Find adjective modifying noun, corrupt adjective to disagree

```python
def can_apply(tokens, idx):
    token = tokens[idx]
    return token.pos == "ADJ" and token.dep_rel == "amod"

def apply(tokens, sentence, idx, modified):
    adj = tokens[idx]
    head_noun = tokens[adj.head_idx]

    # Get noun's features
    noun_case = head_noun.features.get("Case")
    noun_gender = head_noun.features.get("Gender")

    # Generate adjective with WRONG case/gender
    wrong_case = random.choice([c for c in CASES if c != noun_case])
    wrong_form = inflect_adj(adj.lemma, wrong_case, noun_gender, ...)

    return ErrorResult(...)
```

#### 2.2 Subject-Verb Agreement (`AgrNum`, `AgrPers`)
- **Dependency relation**: `nsubj` (nominal subject)
- **Category**: MORPH
- **Implementation**: Find verb's subject, corrupt verb to wrong person/number

```python
# "Дети играют" → "Дети играет" ❌ (pl subject + sg verb)
# "Я читаю" → "Я читает" ❌ (1sg subject + 3sg verb)
```

#### 2.3 Predicate Agreement
- **Dependency relation**: `nsubj` with copula or short adjective
- **Category**: MORPH

```python
# "Книга была интересная" → "Книга была интересное" ❌
```

---

### Priority 3: Government Errors (Requires `--depparse` + resource)

#### 3.1 Verb Government (`Gov`)
- **Resource needed**: `GOV_DICT = {verb_lemma: (preposition, case)}`
- **Dependency relation**: `obj`, `iobj`, `obl`
- **Category**: MORPH

```python
GOV_DICT = {
    "помогать": (None, "Dat"),      # помогать кому
    "ждать": (None, "Gen"),          # ждать кого/чего
    "смотреть": ("на", "Acc"),       # смотреть на кого
    "думать": ("о", "Prep"),         # думать о чём
    "интересоваться": (None, "Ins"), # интересоваться чем
}

# "помогать другу" → "помогать друга" ❌ (Dat → Gen)
```

**Source for GOV_DICT**: Розенталь "Управление в русском языке" or extract from ruscorpora.ru

#### 3.2 Preposition Government (`Prep` + `Gov`)
- **Resource needed**: `PREP_CASE = {prep: [valid_cases]}`
- **Category**: MORPH

```python
PREP_CASE = {
    "в": ["Acc", "Prep"],  # в школу (Acc), в школе (Prep)
    "на": ["Acc", "Prep"],
    "с": ["Gen", "Ins"],   # с горы (Gen), с другом (Ins)
    "за": ["Acc", "Ins"],
    "под": ["Acc", "Ins"],
}

# Use wrong case for preposition's context
# "в школе" (location) → "в школу" ❌ (direction case in location context)
```

---

### Priority 4: Verbal Category Errors

#### 4.1 Aspect Confusion (`Asp`)
- **Resource needed**: `ASP_PAIRS = {impf: perf, perf: impf}`
- **Resource needed**: `ASP_TRIGGERS = {trigger_verb: required_aspect}`
- **Category**: MORPH

```python
ASP_PAIRS = {
    "читать": "прочитать",
    "писать": "написать",
    "делать": "сделать",
    "говорить": "сказать",
    # ... ~2000 pairs from RKI dictionaries
}

ASP_TRIGGERS_NSV = ["начать", "начинать", "продолжать", "кончить", "бросить"]
# After these verbs, infinitive must be imperfective

# "Он начал читать" → "Он начал прочитать" ❌
```

**Source for ASP_PAIRS**: Wiktionary ru, RKI textbooks, academic aspect dictionaries

#### 4.2 Reflexive Errors (`Refl`)
- **Category**: MORPH
- **Implementation**: Add/remove -ся/-сь incorrectly

```python
# "Дверь открылась" → "Дверь открыла" ❌ (missing reflexive)
# "Я мою руки" → "Я моюсь руки" ❌ (incorrect reflexive)
```

#### 4.3 Voice Errors (`Passive`)
- **Category**: MORPH
- **Implementation**: Active ↔ passive confusion

---

### Priority 5: Structural Errors (Length-changing)

These handlers set `changes_length = True` and require special handling in the pipeline.

#### 5.1 Word Omission (`Miss`)
- **Category**: OTHER
- **Implementation**: Delete a function word (preposition, particle, conjunction)
- **Fix tag**: `$APPEND_word`

```python
# "Я иду в школу" → "Я иду школу" ❌
# Fix: $APPEND_в

def apply(tokens, sentence, idx, modified):
    # Delete token at idx
    del sentence[idx]
    return ErrorResult(
        fix_tag=f"$APPEND_{tokens[idx].text}",
        ...
    )
```

#### 5.2 Word Insertion (`Extra`)
- **Category**: OTHER
- **Implementation**: Insert a filler word or duplicate
- **Fix tag**: `$DELETE`

```python
FILLERS = ["вот", "ну", "так", "это", "значит"]

# "Он читает книгу" → "Он вот читает книгу" ❌
# Fix: $DELETE
```

#### 5.3 Word Order (`WO`)
- **Category**: OTHER
- **Implementation**: Swap adjacent words inappropriately
- **Note**: Russian has flexible word order, so this is subtle

---

## Required Resources Summary

| Resource | File | Status | Error Types |
|----------|------|--------|-------------|
| Paronyms | `data/russian/paronyms.json` | ✅ Done | `Lex` |
| Preposition groups | `data/russian/prepositions.json` | ❌ TODO | `Prep` |
| Conjunction pairs | `data/russian/conjunctions.json` | ❌ TODO | `Conj` |
| Verb government | `data/russian/government.json` | ❌ TODO | `Gov` |
| Preposition-case | `data/russian/prep_case.json` | ❌ TODO | `Prep`, `Gov` |
| Aspect pairs | `data/russian/aspect_pairs.json` | ❌ TODO | `Asp` |
| Aspect triggers | `data/russian/aspect_triggers.json` | ❌ TODO | `Asp` |
| Filler words | `data/russian/fillers.json` | ❌ TODO | `Extra` |

### Where to Find Data

| Resource | Sources |
|----------|---------|
| Verb government | Розенталь "Управление в русском языке", ruscorpora.ru |
| Aspect pairs | Russian Wiktionary, RKI textbooks (Лазарева, Чернышов) |
| Preposition-case | Any Russian grammar reference |
| Fillers | Frequency lists, spoken corpus data |

---

## Technical Notes

### Dependency Parsing

Enable with `--depparse` flag. Adds ~40% overhead but required for agreement/government errors.

```bash
synterr generate --lang ru --depparse -i corpus.txt -o out.edits
```

In code:
```python
config = GenerationConfig(use_depparse=True)
# or
config = GenerationConfig.from_preset("ru", "balanced", use_depparse=True)
```

### Length-Changing Handlers

Handlers that add/delete tokens must set `changes_length = True`:

```python
class WordOmissionHandler:
    name = "word_omission"
    category = "OTHER"
    changes_length = True  # Important!
```

The pipeline applies these last to avoid index corruption. After a length-changing error is applied, prior error indices are automatically adjusted via `_adjust_indices_for_length_change()`.

### Span Support and M2 Format

`ErrorResult` has both `start_idx` and `end_idx` to support multi-token spans. Currently:

- **GECToR output** (`_format_output`): Only uses `start_idx`. Spans decompose to per-token tags.
- **M2 output**: Not yet implemented. When added, will use full span information.

**Handler convention**: Always set `end_idx` correctly, even for single-token errors (`end_idx = start_idx + 1`). This ensures span data is preserved for future M2 export.

```python
# Single-token error
ErrorResult(start_idx=2, end_idx=3, ...)

# Multi-token span (e.g., "потому что" → "поскольку")
ErrorResult(start_idx=2, end_idx=4, ...)  # tokens 2-3 inclusive
```

Future M2 formatter will output:
```
A 2 4|||Conj|||поскольку|||REQUIRED|||-NONE-|||0
```

### Handler Registration

Add new handlers to `src/synterr/languages/russian/errors/__init__.py`:

```python
from synterr.languages.russian.errors.lexical import (
    ParonymHandler,
    PrepositionHandler,
)

ALL_HANDLERS = [
    SpellingErrorHandler(),
    NounCaseHandler(),
    # ... existing ...
    ParonymHandler(),      # New
    PrepositionHandler(),  # New
]
```

### Testing

Each handler needs tests in `tests/test_languages/test_russian/`:

```python
class TestParonymHandler:
    def test_implements_protocol(self):
        handler = ParonymHandler()
        assert isinstance(handler, ErrorHandler)

    def test_can_apply_finds_paronyms(self):
        # ...

    def test_apply_substitutes_correctly(self):
        # ...
```

---

## Output Formats

Currently only GECToR token-level tags are implemented. Additional formats to support:

| Format | Use Case | Status | Priority |
|--------|----------|--------|----------|
| **GECToR tags** | Token taggers (GECToR, PIE) | ✅ Done | — |
| **Parallel TSV** | seq2seq training (T5/BART) | ✅ Done | — |
| **Rich JSONL** | Reproducibility, filtering, debugging | ✅ Done | — |
| **Human diff** | Spot-checking, quality inspection | ✅ Done | — |
| **Span edit JSON** | Intermediate for converters | ❌ TODO | Low |
| **M2 (CoNLL GEC)** | ERRANT eval, standard benchmarks | ❌ TODO | Medium |
| **ERRANT JSONL** | Schema-tagged metrics | ❌ TODO | Medium |
| **CoNLL-U + MISC** | UD integration, morph/depparse context | ❌ TODO | Low |

### Format Details

#### Parallel TSV (implemented)
```
src<TAB>tgt
Мама мыла раму	Мама мыла раме
```
Simplest format. Use `GeneratedSentence.to_tsv()`.

#### Rich JSONL (implemented)
```json
{"id": "abc123", "original": "Мама мыла раму", "corrupted": "Мама мыла раме", "errors": [...], "seed": 42}
```
Full metadata for reproducibility. Use `GeneratedSentence.to_jsonl()`.

#### Human Diff (implemented)
```
Мама мыла [-раму-]{+раме+}
```
Quick visual inspection. Use `GeneratedSentence.to_diff()`.

#### M2 Format (TODO)
```
S Мама мыла раме
A 2 3|||MORPH|||раму|||REQUIRED|||-NONE-|||0
```
Standard for GEC evaluation. Requires span support in `_format_output()`.

#### Span Edit JSON (TODO)
```json
{"start": 2, "end": 3, "op": "replace", "original": "раму", "replacement": "раме", "category": "MORPH", "subtype": "noun_case"}
```
Clean intermediate format for downstream converters.

---

## Implementation Order Recommendation

1. **Lexical errors** (paronym, preposition, conjunction) — No depparse, straightforward
2. **Structural errors** (omission, insertion) — Length-changing but simple logic
3. **Agreement errors** — Requires depparse, more complex
4. **Government errors** — Requires depparse + building GOV_DICT
5. **Aspect errors** — Requires building aspect pair dictionary

Start with what has resources ready (paronyms ✅), then build resources as you go.
