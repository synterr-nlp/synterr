# CLAUDE.md

Synterr: rule-based synthetic error generator for Russian GEC. Corrupts clean text → GECToR training data.

## Architecture

```
src/synterr/
├── core/           # Pipeline, protocol, registry (language-agnostic)
├── schemas/        # Taxonomies: RLC (35 tags), synterr (14 tags)
├── configs/        # Presets: rulec, gera, balanced (weights per handler)
└── languages/russian/
    ├── backends/   # stanza (default), natasha, spacy
    ├── errors/     # spelling.py (7 subtypes), morphological.py (7 handlers)
    └── inflector.py
```

**Key separation**: Handlers = *how* to corrupt. Schemas = *what to call it*. Configs = *how often*.

## Core Types

```python
AnalyzedToken(text, lemma, pos, features, extra)  # extra["pymorphy_parse"] for inflection
ErrorResult(error_type, category, original, corrupted, fix_tag)
ErrorHandler  # Protocol: name, subtypes, category, changes_length, can_apply(), apply()
Schema        # primary_tags, modifiers, mappings: subtype → tag
```

## Commands

```bash
uv run pytest                                     # Tests
uv run synterr coverage --lang ru --schema rlc    # 9/35 tags covered
uv run synterr corrupt -l ru -e noun_case "Мама"  # Tagged corruption
uv run synterr generate -l ru --preset rulec -i in.txt -o out.edits
```

## Handlers → RLC Tags

| Handler | Subtypes | RLC Tag | Category |
|---------|----------|---------|----------|
| spelling | vowel_reduction, keyboard, devoicing, ... | Ortho, Misspell | SPELL |
| noun_case | noun_case | Gov | MORPH |
| adj_case/number/gender | (3) | AgrCase, AgrNum, AgrGender | MORPH |
| verb_person_number, verb_tense | (2) | AgrPers, Tense | MORPH |

## Adding a Handler

```python
class MyHandler:
    name = "my_handler"
    subtypes = ["my_subtype"]  # For schema mapping
    category = "OTHER"
    changes_length = False     # True if adds/deletes tokens

    def can_apply(self, tokens, idx): ...
    def apply(self, tokens, sentence, idx, modified): ...
```

1. Add to `errors/__init__.py`
2. Add weight to `configs/russian/rulec.yaml`
3. Add mapping to `schemas/data/rlc.yaml`

## Gotchas

- **Capitalization**: Always `inflect_word(parse, grammemes, original)` — pass original word
- **Stress dict**: Required for vowel_reduction (`data/russian/stress_dict.json`)
- **pymorphy_parse**: In `token.extra["pymorphy_parse"]`, needed for inflection
- **changes_length**: Set `True` for insert/delete handlers (applied last)

## Output Format

```
$STARTSEPL|||SEPR$KEEP:CORRECT МамаSEPL|||SEPR$REPLACE_раму:MORPH раме...
```

Tags: `$KEEP`, `$REPLACE_x`, `$TRANSFORM_CASE_x`, `$APPEND_x`, `$DELETE`

## Current State

**v0.1.0**: Schemas, subtypes, `apply_error()` API, stress-based spelling, capitalization fix

**Next (Artem)**: paronym, preposition, conjunction, word_omission, word_insertion → 40% RLC coverage
