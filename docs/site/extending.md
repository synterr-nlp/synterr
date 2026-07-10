# Extending synterr

Synterr has six extension points. Each has a clean protocol contract and
an existing example you can copy. Pick the one that matches what you're
trying to do.

## Decision tree

| You want to… | Extension point | Effort |
|--------------|-----------------|--------|
| Generate a new error type within Russian | New **handler** | Hours |
| Cover a different error taxonomy / corpus annotation | New **schema** | A day |
| Calibrate to a different learner population | New **preset** | An hour |
| Use a different morphological/parsing toolkit | New **backend** | A week |
| Emit a new file format | New **output format** | An hour |
| Support a new language entirely | New **language module** | Weeks |

---

## 1. Add an error handler

The most common extension. You implement the `ErrorHandler` protocol —
two methods (`can_apply`, `apply`) — register it, and add a weight.

```python
class MyHandler:
    name = "my_handler"
    subtypes = ["my_subtype"]
    category = "MORPH"          # SPELL / MORPH / PUNCT / OTHER
    changes_length = False      # True if you add/delete tokens

    def can_apply(self, tokens, idx) -> bool: ...
    def apply(self, tokens, sentence, idx, modified, rng=None) -> ErrorResult | None: ...
```

**Where to copy from:** `src/synterr/languages/russian/errors/spelling.py` is
the simplest non-trivial example. `morphological.py` shows confusion-matrix
+ dep-tree integration. `comma_insert.py` shows length-changing handlers.

**Where the contract lives:** [`CLAUDE.md`](https://github.com/synterr-nlp/synterr/blob/master/CLAUDE.md#adding-a-handler).

**Step-by-step (with worked example, in Russian):**
[`docs/CONTRIBUTING.ru.md` §"Как добавить новый тип ошибки"](https://github.com/synterr-nlp/synterr/blob/master/docs/CONTRIBUTING.ru.md#как-добавить-новый-тип-ошибки).

**Don't forget:**
- Register in `src/synterr/languages/russian/errors/__init__.py`
- Default weight in `src/synterr/configs/russian/rulec.yaml`
- Schema mapping in `src/synterr/schemas/data/rlc.yaml` (and `rozental.yaml` if applicable)
- Tests under `tests/test_languages/test_russian/`

---

## 2. Add a schema

Schemas are YAML files in `src/synterr/schemas/data/`. The structure:

```yaml
name: my_schema
description: "What this schema represents"

primary_tags: [Tag1, Tag2, ...]    # L0 categories
modifiers: [...]                    # optional, for compound tags

# Hierarchical structure (L0 → L1 → L2)
tags:
  Tag1:
    description: "..."
    detection_category: SPELL
    paras: "§reference"
    parent: null

# Map handler subtypes → schema tags
subtype_mappings:
  my_subtype:
    primary: Tag1
    l2_tag: Tag1_specific  # optional fine-grained
```

**Where to copy from:** `src/synterr/schemas/data/rlc.yaml` is the simplest;
`rozental.yaml` is the deepest (3-level hierarchy with §-paragraph traces);
`errant.yaml` shows POS+operation tags for cross-lingual GEC.

**Loading is automatic** — drop the YAML in the right directory and it's
discoverable via `synterr list-schemas`.

---

## 3. Add a preset

Presets are configs in `src/synterr/configs/<language>/`. Format:

```yaml
name: my_preset
description: "Calibrated to ..."

weights:
  spelling: 0.4
  noun_case: 0.2
  # ...

subtype_weights:
  spelling:
    vowel_reduction: 30
    keyboard: 5

confusion_matrices:
  case: {...}      # optional, language-dependent

use_depparse: true
error_probability: 0.7
max_errors_per_sentence: 3
```

**Where to copy from:** `src/synterr/configs/russian/rulec.yaml` has the
full structure with documentation.

**Calibration tip:** if you have a labeled error corpus, run
`scripts/extract_confusion_matrices.py` (or write the equivalent for your
data) to derive matrices empirically. See
[`docs/research/CASE_CONFUSION_PATTERNS.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/research/CASE_CONFUSION_PATTERNS.md)
for how the rulec preset's matrices were derived.

---

## 4. Add an NLP backend

A backend implements the `Analyzer` protocol — basically `analyze(sentence)
→ list[AnalyzedToken]`. Synterr ships three for Russian: stanza (default),
natasha, spacy.

```python
class MyBackend:
    def __init__(self, use_depparse: bool = False): ...
    def analyze(self, sentence: str) -> list[AnalyzedToken]: ...
    def analyze_batch(self, sentences: list[str]) -> list[list[AnalyzedToken]]: ...
```

**Where to copy from:** `src/synterr/languages/russian/backends/stanza_backend.py`
is the canonical example. `natasha_backend.py` is faster but lacks dep parse.

The translation work is: for every token, populate `text`, `lemma`, `pos`
(UD), `features` dict (UD-style), and optionally `dep_rel` + `head_idx`.
Whatever your toolkit calls things, normalize to UD tags here.

**Register your backend:** add to `src/synterr/languages/russian/backends/__init__.py`
and the dispatch in `LanguageModule.get_analyzer()`.

---

## 5. Add an output format

Output formats live in `ErrorPipeline` result objects. The current set:
`gector`, `tsv`, `jsonl`, `chat`, `sft`, `diff`. Adding one means adding
a `to_<format>()` method on the result class and a `--output-format` choice
in the CLI.

**Where to copy from:** `src/synterr/core/pipeline.py` (search for
`to_jsonl`, `to_tsv`, `to_chat`).

This is small enough that it usually lives in a single PR.

---

## 6. Add a new language

The biggest extension. Synterr's architecture is language-agnostic; the
core plus schemas don't know about Russian. To add a language you implement:

- **Language module** (registers the language code, dispatches to backend / handlers)
- **Analyzer** (tokenization + morphology, optionally dep parse)
- **Inflector** (turns paradigm features into surface forms)
- **Error handlers** (per-language; the protocol is universal)
- **Optionally:** language-specific schema mappings, presets, backends

**Where the full procedure lives:** [`CONTRIBUTING.md` §"Adding a New
Language"](https://github.com/synterr-nlp/synterr/blob/master/CONTRIBUTING.md#adding-a-new-language).
Step-by-step with a hypothetical German module as the example.

**Honest take:** this is research-grade work. Russian morphological
infrastructure took months. Don't underestimate the inflection coverage
problem (pymorphy3 is exceptional; equivalent quality for other
languages requires effort). Start with a small handler set
(`spelling`, `paronym`, `comma_delete`) and expand.

**Worked example:** `src/synterr/languages/french/` is a live 5-handler
French proof of concept (elision, article contraction, pp agreement,
verb-ending homophony, grammatical homophones) on the stanza
`fr_sequoia` backend — inflection-free by design, a useful reference for
scoping a first pass on a new language.

---

## What you do *not* need to extend

- **The pipeline core**, `ErrorPipeline` — orchestration is generic
- **The CLI**, mostly — new presets/schemas/handlers are picked up automatically
- **The output format dispatch** for adding a new error type — only when adding a new format

If you're tempted to fork the pipeline, ask first
([Issues](https://github.com/synterr-nlp/synterr/issues)). Usually the
right answer is a more expressive handler protocol, which we'd rather
upstream than fragment.
