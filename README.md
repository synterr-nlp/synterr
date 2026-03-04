# synterr

Generate synthetic grammatical errors for training GEC models.

synterr corrupts clean text with realistic learner-like errors, outputting GECToR-compatible training data with error type labels.

## Why

Training GEC models requires parallel data (incorrect → correct). Real learner corpora are small and expensive to annotate. synterr generates unlimited synthetic training data from any clean corpus, with error distributions matching real learner errors.

## Install

```bash
pip install synterr[russian]  # includes stanza, pymorphy3
```

### Development (uv)

```bash
git clone https://github.com/mechanicpanic/synterr
cd synterr
uv sync --all-extras   # install all dependencies
```

Run commands with `uv run`:
```bash
uv run synterr --help
uv run synterr list-errors -l ru
uv run pytest  # run tests
```

Or activate the venv:
```bash
source .venv/bin/activate
synterr --help
```

## Usage

```bash
# Generate errors with RULEC-GEC distribution
uv run synterr generate -l ru -i clean.txt -o train.edits --preset rulec

# Use faster backend for large corpora
uv run synterr generate -l ru -i corpus.txt -o out.edits --backend natasha

# Specific error types only
uv run synterr generate -l ru -i in.txt -o out.edits -e spelling,noun_case

# Single sentence corruption (for testing)
uv run synterr corrupt -l ru -e noun_case "Мама мыла раму."
```

Output format (GECToR `.edits`):
```
$STARTSEPL|||SEPR$KEEP:CORRECT ОнSEPL|||SEPR$REPLACE_читает:MORPH читаетSEPL|||SEPR$KEEP:CORRECT книгу
```

## Error Types (Russian)

| Type | Example | Label |
|------|---------|-------|
| Spelling | *ищо* → ещё | SPELL |
| Noun case | *к дому* → к дом | MORPH |
| Adj agreement | *новый книга* → новая книга | MORPH |
| Verb conjugation | *они читает* → они читают | MORPH |
| Paronyms | *одеть* ↔ надеть | LEX |

Full list: `synterr list-errors -l ru`

## Backends

| Backend | Speed (single) | Speed (batch) | Accuracy | Install |
|---------|----------------|---------------|----------|---------|
| stanza (default) | ~75 sent/s | ~500 sent/s | Best | `pip install synterr[russian]` |
| natasha | ~1700 sent/s | ~1700 sent/s | Good | `pip install synterr[natasha]` |
| spacy | ~530 sent/s | ~760 sent/s | Good | `pip install synterr[spacy]` |

*Benchmarked on M4 Pro. Batch mode uses `generate_batch()` / `analyze_batch()`.*

## Presets

Error weights derived from real learner corpora:

- `rulec` — RULEC-GEC L2/heritage learner distribution
- `gera` — GERA German-Russian learner distribution
- `balanced` — Equal weights for all error types

```bash
synterr list-presets -l ru
```

## How It Works

1. **Analyze** clean sentence (stanza/natasha/spacy)
2. **Sample** error type from distribution
3. **Apply** corruption via rule inversion (pymorphy3)
4. **Output** with fix tag + detection label

The "rule inversion" approach: look up what's grammatically correct, then generate something that violates it.

## Status

**v0.1.2** — Russian morphological + spelling errors working. Output formats (TSV, JSONL, diff). Lexical and structural errors in progress.

See [docs/VERSIONING.md](docs/VERSIONING.md) for roadmap.

## References

Based on error taxonomies from:
- [RLC](https://aclanthology.org/2024.lrec-main.1241/) — Russian Learner Corpus (38 error tags)
- [RULEC-GEC](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251) — Rozovskaya & Roth 2019
- [RuBLiMP](https://github.com/RussianNLP/RuBLiMP) — Minimal pairs benchmark (borrowed aspect pairs)

## License

MIT
