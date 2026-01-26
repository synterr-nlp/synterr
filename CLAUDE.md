# CLAUDE.md

Synterr: rule-based synthetic error generator for Russian GEC. Corrupts clean text → GECToR training data.

## Architecture

```
src/synterr/
├── core/           # Pipeline, protocol, registry (language-agnostic)
├── schemas/        # Taxonomies: RLC (35 tags), synterr (14 tags)
├── configs/        # Presets: rulec, gera, balanced (weights + subtype_weights)
├── languages/russian/
│   ├── backends/   # stanza (default), natasha, spacy
│   ├── errors/     # spelling.py (8 subtypes), morphological.py (7 handlers)
│   └── inflector.py
└── tools/          # diff_viewer.html (error inspection UI)
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
| spelling | vowel_reduction, devoicing, prefix_voicing, tsa_confusion, cluster, double_consonant, keyboard, soft_sign | Ortho, Misspell | SPELL |
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

## Output Formats

```python
result = pipeline.generate("Мама мыла раму")
result.formatted      # GECToR tags (default)
result.to_tsv()       # "src\ttgt" for seq2seq
result.to_jsonl()     # Rich JSON with metadata
result.to_diff()      # "Мама мыла [-раму-]{+раме+}"
```

GECToR tags: `$KEEP`, `$REPLACE_x`, `$TRANSFORM_CASE_x`, `$APPEND_x`, `$DELETE`

## Configurable Weights

Handler weights in preset YAML, subtype weights nested:

```yaml
weights:
  spelling: 0.475
  noun_case: 0.280
subtype_weights:
  spelling:
    vowel_reduction: 30
    tsa_confusion: 25
    prefix_voicing: 15
```

## Current State

**v0.1.2**: Output formats, prefix voicing, configurable subtype weights, diff viewer, CI green

**Next (Artem → 0.2.0)**: paronym, preposition, conjunction, word_omission, word_insertion → 40% RLC coverage

**Research**: Case confusion matrix (`docs/research/CASE_CONFUSION_PATTERNS.md`) — linguistically grounded case errors
