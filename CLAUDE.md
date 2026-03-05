# CLAUDE.md

Synterr: rule-based synthetic error generator for Russian GEC. Corrupts clean text → GECToR training data.

## Architecture

```
src/synterr/
├── core/           # Pipeline, protocol, registry (language-agnostic)
├── schemas/        # Taxonomies: RLC (35 tags), rozental (8/29/99), errant
├── configs/        # Presets: rulec, gera, balanced (weights + subtype_weights)
├── languages/russian/
│   ├── backends/   # stanza (default), natasha, spacy
│   ├── errors/     # spelling.py, morphological.py, lexical.py, structural.py, punctuation.py
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
| paronym | paronym | Lex | OTHER |
| preposition | preposition | Prep | OTHER |
| conjunction | conjunction | Conj | OTHER |
| word_omission | word_omission | Syntax+Miss | OTHER |
| word_insertion | word_insertion | Syntax+Extra | OTHER |
| comma_delete | 5 subtypes (subordinate, compound, parenthetical, isolation, homogeneous) | Syntax+Miss | PUNCT |
| comma_pair_delete | 5 subtypes (participle, relative, gerund, parenthetical, apposition) | Syntax+Miss | PUNCT |
| dash_delete | dash_subj_pred, dash_other | Syntax+Miss | PUNCT |

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

## Confusion Matrices & Dep-Tree Agreement

Morph handlers use empirical confusion matrices from RLC (N=2,760 case, 917 gender, 942 number) for weighted grammeme substitution instead of uniform random. Configured in preset YAMLs under `confusion_matrices:` with UD feature names as keys.

Dep-tree agreement (requires `use_depparse: true`):
- **Adj handlers**: Follow `amod` → head noun, use head's features as reference for matrix lookup
- **VerbPersonNumber**: Find `nsubj` dependent → use subject's number as reference
- All handlers fall back to own features when dep tree info unavailable

Pipeline wires matrices via `handler.set_confusion_matrix(matrices)` (same pattern as `set_subtype_weights`).

## Punctuation Heuristics

Dep-tree classifier in `errors/punctuation.py`. See `docs/research/PUNCT_HEURISTICS.md` for full details.

Comma's own `head_idx` in the dep tree is the primary signal:
- `head.dep_rel = parataxis/discourse` → **parenthetical**
- `head.dep_rel ∈ {acl, acl:relcl, advcl}` → **isolation** (обособление)
- `head.dep_rel = conj` + both sides are clauses with subjects → **compound**
- `head.dep_rel = conj` + non-clausal → **homogeneous**
- `head.dep_rel ∈ {ccomp, advcl, csubj}` → **subordinate**

Comma pair detection: find all commas sharing the same `head_idx`, check head's dep_rel against `PAIR_DEPRELS` map. Only first comma triggers. `advcl` pairs require `VerbForm=Conv` (gerunds only, not full clauses).

POS/lemma fallbacks when dep info unavailable. Subtree BFS for closing comma detection.

## Current State

**v0.3.0**: Confusion-matrix-driven morph handlers (5 handlers upgraded), dep-tree-aware agreement errors (adj amod, verb nsubj). 115 tests, 18 handlers.

**v0.2.0**: Lexical handlers (paronym, preposition, conjunction), structural (word_omission, word_insertion), punctuation (comma_delete, comma_pair_delete, dash_delete). Rozental schema (8 L0 / 29 L1 / 99 L2).

**Research**: Case confusion matrix (`docs/research/CASE_CONFUSION_PATTERNS.md`), punct heuristics (`docs/research/PUNCT_HEURISTICS.md`), confusion matrices (`docs/research/confusion_matrices.json`)
