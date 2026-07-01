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
uv run synterr coverage --lang ru --schema rlc    # see CHANGELOG / docs/research/LORUGEC_COVERAGE.md for current
uv run synterr corrupt -l ru -e noun_case "Мама"  # Tagged corruption
uv run synterr generate -l ru --preset rulec -i in.txt -o out.edits
```

## Handlers → RLC Tags

28 handlers / 77 subtypes. Table below; `synterr list-errors -l ru` is authoritative.

| Handler | Subtypes | RLC Tag | Category |
|---------|----------|---------|----------|
| spelling | vowel_reduction, devoicing, prefix_voicing, tsa_confusion, cluster, double_consonant, keyboard, soft_sign | Ortho, Misspell | SPELL |
| function_spelling | ne_attachment, ne_detachment, conjunction_split, conjunction_merge, taki_hyphen, neg_pronoun_ne_ni | Ortho | SPELL |
| orthographic_spelling | pre_pri, y_i_after_prefix, suffix_enk_onk, suffix_insk_ensk, suffix_its_ets, suffix_ek_ik, participle_suffix, vowel_after_ts, vowel_after_sibilant, nn_suffix | Ortho | SPELL |
| compound_spelling | num_dash, pol_spelling, compound_adj | Ortho, Hyphen | SPELL |
| adverb_spelling | solid_to_separate, separate_to_solid, hyphen_to_separate, separate_to_hyphen | Ortho | SPELL |
| noun_case | noun_case_governed (obl/nmod/iobj/obj), noun_case_subject (nsubj), noun_case_other (appos/conj/…) | Gov, Nominative, Infl | MORPH |
| noun_case_prep | noun_case_prep_e_u (second locative в лесу→в лесе) | Gov | MORPH |
| noun_number | noun_number | Num | MORPH |
| adj_case/number/gender | (3) | AgrCase, AgrNum, AgrGender | MORPH |
| adj_form | adj_short_full (готовы→готовые) | Infl | MORPH |
| adj_double_comparative | adj_double_comparative (insert «более»; changes_length=True) | Infl | MORPH |
| verb_person_number, verb_tense | (2) | AgrPers, Tense | MORPH |
| numeral_declension | numeral_declension, numeral_poltora | Num | MORPH |
| paronym | paronym | Lex | OTHER |
| preposition | preposition | Prep | OTHER |
| conjunction | conjunction | Conj | OTHER |
| pleonasm | pleonasm | Lex | OTHER |
| collocation | collocation | Lex | OTHER |
| word_omission | word_omission | Syntax+Miss | OTHER |
| word_insertion | word_insertion | Syntax+Extra | OTHER |
| comma_delete | 10 subtypes (subordinate, compound, parenthetical, isolation, homogeneous, interjection, response, repeated, asyndetic, vocative) | Syntax+Miss | PUNCT |
| comma_pair_delete | 5 subtypes (participle, relative, gerund, parenthetical, apposition) | Syntax+Miss | PUNCT |
| comma_insert | comma_before_kak, comma_in_set_phrase, comma_between_conjunctions, comma_in_indivisible, comma_clause_junction | Syntax+Extra | PUNCT |
| dash_delete | dash_subj_pred, dash_asyndetic, dash_apposition, dash_other | Syntax+Miss | PUNCT |
| dash_to_comma | dash_to_comma_apposition (substitution; changes_length=False) | Syntax+Miss | PUNCT |

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

**v1.0.1** (May 2026, BEA 2026 release): 25 handlers, 69 subtypes, 290 tests. Schemas: synterr, rlc, rozental, errant. Pinned-commit reproducibility for the v4 SFT data (`data/V4_DATA_PROVENANCE.md`, `data/v4_checksums.txt`, `scripts/verify_v4.py`). Per-detail version history in `CHANGELOG.md`.

**Research notes**: Case confusion matrix (`docs/research/CASE_CONFUSION_PATTERNS.md`), punct heuristics (`docs/research/PUNCT_HEURISTICS.md`), confusion matrices (`docs/research/confusion_matrices.json`), LoRuGEC coverage (`docs/research/LORUGEC_COVERAGE.md`).
