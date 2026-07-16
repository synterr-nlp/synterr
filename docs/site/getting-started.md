# Getting started

## Install

```bash
pip install "synterr[russian] @ git+https://github.com/synterr-nlp/synterr"
```

This pulls synterr plus stanza and pymorphy3 (Russian backend
dependencies). For development setup, see
[Contributing](contributing.md).

Russian (`ru`) is the production-ready language. A 5-handler French
proof of concept (`fr`, stanza `fr_sequoia` backend) also ships in the
same architecture — run `uv run synterr list-languages` to see both.

## Three ways to use synterr

### 1. Corrupt a single sentence (testing / inspection)

```bash
uv run synterr corrupt -l ru -e spelling "Молоко стоит на столе."
```

For dep-tree-aware errors (`noun_case`, `adj_case`,
`verb_person_number`), pass `--depparse`:

```bash
uv run synterr corrupt -l ru -e noun_case --depparse \
    "Книга лежит на столе."
```

You can target a specific subtype:

```bash
uv run synterr corrupt -l ru -e spelling:vowel_reduction "Молоко стоит на столе."
```

### 2. Generate a corpus of errors

```bash
uv run synterr generate -l ru --preset rulec \
    -i clean.txt -o train.edits
```

Output formats are switched with `-f`:

| Flag | Format |
|------|--------|
| `gector` (default) | GECToR token-level tags |
| `tsv` | parallel `src\ttgt` |
| `jsonl` | rich JSON, includes rule labels and metadata |
| `chat` | instruction-tuning chat format |
| `sft` | `{src, tgt}` JSONL |

Example with rule-labeled JSONL:

```bash
uv run synterr generate -l ru --preset rulec --depparse \
    -i clean.txt -o train.jsonl -f jsonl
```

For **rule-targeted SFT generation** — filling a quota per rule from a
target set (rule name → handler+subtype with relative weights) instead
of sampling a distribution per sentence:

```bash
uv run synterr generate-targeted -i corpus.txt -o train.jsonl \
    -n 50000 --seed 42 --balance-directions
```

This produces `{"src": corrupted, "tgt": clean, "rule": rule_name}`
JSONL plus a `.dist.json` sidecar with per-rule counts. The built-in
target set covers 48 Rozental-derived rules, empirically weighted;
supply your own with `--targets targets.json`. This command built the
training data for our BEA 2026 paper.

### 3. Use the Python API

```python
from synterr.core.pipeline import ErrorPipeline, GenerationConfig
from synterr.core.registry import get_language

config = GenerationConfig(seed=42, use_depparse=True, schema="rozental")
pipeline = ErrorPipeline(get_language("ru"), config)

result = pipeline.generate("Мама мыла раму")
print(result.formatted)   # GECToR tags
print(result.to_jsonl())  # rich JSON with rule labels
```

## Choosing a preset

| Preset | Use when |
|--------|----------|
| `rulec` | Calibrated to RULEC-GEC L2 / heritage learner distribution |
| `gera` | Calibrated to GERA German-Russian learner distribution |
| `balanced` | Equal weights across error types |
| `lorugec` | Coverage-mode, designed for the LoRuGEC benchmark |
| `profile_punct`, `profile_spelling`, `profile_morph` | Single-category isolation, useful for ablations |

```bash
uv run synterr list-presets -l ru
```

## What's next

- The full contract — text in, tagged errors out, including corpus
  surveying and pool mining for rare error classes: [Pipeline](pipeline.md)
- Learn the design: [Architecture](architecture.md)
- See every error type with examples: [Error types](error-types.md)
- Reproduce paper data exactly: [Reproducibility](reproducibility.md)
