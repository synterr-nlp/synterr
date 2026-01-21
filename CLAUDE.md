# CLAUDE.md

Project guidance for Claude Code when working with this repository.

## Project Overview

**synterr** - Reproducible error generation for Grammatical Error Correction (GEC).

A language-agnostic framework for generating synthetic training data for GEC models. Russian is the first supported language.

## Architecture

### Core Module (`src/synterr/core/`)

- `protocol.py` - Key abstractions: `AnalyzedToken`, `ErrorResult`, `ErrorHandler` Protocol, `LanguageModule` Protocol
- `registry.py` - Language discovery via entry points (`synterr.languages`)
- `pipeline.py` - `ErrorPipeline` orchestrates error generation with configurable sampling

### Language Modules (`src/synterr/languages/`)

Languages implement the `LanguageModule` protocol and register via entry points in pyproject.toml:

```toml
[project.entry-points."synterr.languages"]
russian = "synterr.languages.russian:RussianLanguage"
```

### Russian Module (`src/synterr/languages/russian/`)

Two-stage morphological processing:
1. **stanza** - Contextual analysis (POS, lemma, features, depparse)
2. **pymorphy3** - Inflection (generating corrupted word forms)

Error handlers in `errors/`:
- `spelling.py` - Phonetic errors (vowel reduction, тся/ться, devoicing, keyboard typos)
- `morphological.py` - Case, number, gender, tense errors for nouns, adjectives, verbs

## Common Commands

```bash
# Development setup
uv sync --all-extras

# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Run tests
uv run pytest -v

# CLI usage
uv run synterr list-languages
uv run synterr list-errors --lang ru
uv run synterr generate --lang ru -i corpus.txt -o errors.edits
uv run synterr analyze --lang ru "Мама мыла раму"
```

## Output Format

GECToR-compatible edit format with detection labels:

```
$STARTSEPL|||SEPR$KEEP:CORRECT wordSEPL|||SEPR$REPLACE_original:SPELL ...
```

Detection categories: `CORRECT`, `SPELL`, `MORPH`, `PUNCT`, `OTHER`

## Adding New Error Types

1. Create handler class implementing `ErrorHandler` protocol in `errors/`
2. Add to `get_all_handlers()` in `errors/__init__.py`
3. Add weight to `get_error_distribution()` in language module

## Adding New Languages

1. Create `languages/<lang>/` directory with:
   - `__init__.py` - `<Lang>Language` class implementing `LanguageModule`
   - `analyzer.py` - Language-specific analyzer
   - `errors/` - Error handlers
2. Register entry point in pyproject.toml
3. Add optional dependencies for language-specific packages

## Related Projects

- **gector** (`~/Projects/research/gector/`) - Parent project with GECToR training code
- Original error generation in `gector/code/synthetic_dataset_generation/`

## Key Dependencies

- `click` - CLI framework
- `stanza` - Neural NLP pipeline (Russian model: SynTagRus)
- `pymorphy3` - Russian morphological analyzer
- `razdel` - Russian tokenization
