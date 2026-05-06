# Contributing to synterr

Thanks for your interest. This guide covers everyday development.
For architecture details see [`CLAUDE.md`](CLAUDE.md). The Russian-language
guide ([`docs/CONTRIBUTING.ru.md`](docs/CONTRIBUTING.ru.md)) goes deeper into
adding error handlers.

## Setup

Requirements: Python 3.11+, [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/synterr-nlp/synterr
cd synterr
uv sync --all-extras
```

Quick smoke test:

```bash
uv run synterr corrupt -l ru -e spelling "Мама мыла раму."
uv run pytest
```

## Workflow

Feature branches off `master`, PR back to `master`.

```bash
git checkout -b your-name/short-description
# ... commits ...
git push -u origin your-name/short-description
gh pr create
```

PRs need:
- Tests (every new handler or behavior change)
- `uv run pytest` green
- `uv run ruff check src tests` clean
- `uv run ruff format --check src tests` clean
- `uv run mypy` clean (covers `src/synterr/core` + `src/synterr/schemas`)

CI runs all of the above on every PR.

## Adding an error handler (Russian)

See [`CLAUDE.md`](CLAUDE.md) for the `ErrorHandler` protocol contract. The
short version:

1. Implement the protocol in a new file under
   `src/synterr/languages/russian/errors/`.
2. Register in `src/synterr/languages/russian/errors/__init__.py`.
3. Add a default weight in `src/synterr/configs/russian/rulec.yaml`.
4. Add schema mappings in `src/synterr/schemas/data/rlc.yaml` (and
   `rozental.yaml` if applicable).
5. Add tests under `tests/test_languages/test_russian/`.

The Russian guide has fully-worked examples and idiom-level guidance.

## Code style

- Ruff handles formatting (88 char) and most lint
- Type-annotate public APIs in `core/` and `schemas/`; the rest of the
  codebase is opt-in
- Default to writing no comments unless the *why* is non-obvious

## Reporting bugs

Use [GitHub Issues](https://github.com/synterr-nlp/synterr/issues).
Include:
- A minimal reproducing input sentence
- The handler/subtype/preset involved
- What synterr produced vs. what you expected

For data-pipeline reproduction questions, see
[`data/V4_DATA_PROVENANCE.md`](data/V4_DATA_PROVENANCE.md) first.

## Citing

If you use synterr in research, see the
[Citation section in README](README.md#citation).

---

## Adding a New Language

synterr uses a plugin architecture for language support. Languages are discovered via Python entry points.

### Quick Start

```bash
# Create a new package
mkdir synterr-german && cd synterr-german
uv init

# Add synterr as dependency
uv add synterr
```

### Step 1: Implement the Language Module

```python
# src/synterr_german/__init__.py
from synterr.core.protocol import Analyzer, AnalyzedToken, ErrorHandler, ErrorResult

class GermanLanguage:
    """German language module for synterr."""

    code = "de"
    name = "German"

    def get_analyzer(self, use_depparse: bool = False, backend: str | None = None) -> Analyzer:
        """Return an analyzer that tokenizes and tags German text."""
        return GermanAnalyzer(use_depparse=use_depparse)

    def get_error_handlers(self) -> list[ErrorHandler]:
        """Return all error handlers for German."""
        return [
            NounCaseHandler(),
            VerbConjugationHandler(),
            ArticleHandler(),
            # ...
        ]

    def get_error_distribution(self) -> dict[str, float]:
        """Default weights for error types."""
        return {
            "noun_case": 0.3,
            "verb_conjugation": 0.25,
            "article": 0.2,
            "spelling": 0.25,
        }
```

### Step 2: Implement the Analyzer

The analyzer must return `AnalyzedToken` objects with Universal POS tags and features.

```python
class GermanAnalyzer:
    def __init__(self, use_depparse: bool = False):
        import spacy
        model = "de_core_news_lg" if use_depparse else "de_core_news_sm"
        self.nlp = spacy.load(model)

    def analyze(self, text: str) -> list[AnalyzedToken]:
        doc = self.nlp(text)
        return [
            AnalyzedToken(
                text=token.text,
                lemma=token.lemma_,
                pos=token.pos_,  # Universal POS tag
                features=self._parse_morph(token.morph),
                idx=i,
                dep_rel=token.dep_,
                head_idx=token.head.i,
                extra={"spacy_token": token},  # Language-specific data
            )
            for i, token in enumerate(doc)
        ]

    def analyze_batch(self, texts: list[str]) -> list[list[AnalyzedToken]]:
        return [self.analyze(text) for text in texts]

    def _parse_morph(self, morph) -> dict[str, str]:
        return dict(morph.to_dict())
```

### Step 3: Implement Error Handlers

Each handler must implement the `ErrorHandler` protocol:

```python
import random as random_module
from random import Random

class NounCaseHandler:
    name = "noun_case"
    subtypes = ["noun_case"]  # For schema mapping
    category = "MORPH"
    changes_length = False

    CASES = ["Nom", "Acc", "Dat", "Gen"]

    def can_apply(self, tokens: list[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        return (
            token.pos == "NOUN"
            and token.has_feature("Case")
            and len(token.text) > 2
        )

    def apply(
        self,
        tokens: list[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
        rng: Random | None = None,
    ) -> ErrorResult | None:
        rng = rng if rng is not None else random_module
        token = tokens[idx]
        original = sentence[idx]

        # Get current case and pick a different one
        current_case = token.get_feature("Case")
        other_cases = [c for c in self.CASES if c != current_case]
        target_case = rng.choice(other_cases)

        # Inflect to wrong case (language-specific logic)
        corrupted = self._inflect(token, target_case)
        if corrupted is None or corrupted == original:
            return None

        sentence[idx] = corrupted

        return ErrorResult(
            error_type="noun_case",
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=original,
            corrupted=corrupted,
            fix_tag=f"$TRANSFORM_CASE_{current_case}",
        )

    def _inflect(self, token: AnalyzedToken, case: str) -> str | None:
        # Use language-specific morphology library
        # e.g., DEMorphy, spaCy lemmatizer, etc.
        ...
```

### Step 4: Register via Entry Point

```toml
# pyproject.toml
[project.entry-points."synterr.languages"]
de = "synterr_german:GermanLanguage"
```

After installation, the language is automatically available:

```bash
synterr list-languages
# de: German
# ru: Russian

synterr generate --lang de --input german_corpus.txt --output train.edits
```

### Alternative: Runtime Registration

For testing or single-script usage:

```python
from synterr.core.registry import register_language
from synterr.core.pipeline import ErrorPipeline

register_language(GermanLanguage())

pipeline = ErrorPipeline("de")
result = pipeline.generate("Der Mann liest ein Buch.")
```

---

## Protocol Reference

### AnalyzedToken

```python
@dataclass
class AnalyzedToken:
    text: str                    # Original text: "Bücher"
    lemma: str                   # Lemma: "Buch"
    pos: str                     # Universal POS: "NOUN"
    features: dict[str, str]     # {"Case": "Acc", "Number": "Plur"}
    idx: int                     # Token index
    dep_rel: str | None          # Dependency relation (optional)
    head_idx: int | None         # Head index (optional)
    extra: dict[str, Any]        # Language-specific data
```

Use Universal Dependencies tagset:
- **POS**: https://universaldependencies.org/u/pos/
- **Features**: https://universaldependencies.org/u/feat/

### ErrorHandler

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Unique identifier: `"noun_case"` |
| `subtypes` | `list[str]` | Fine-grained types for schema mapping |
| `category` | `str` | Detection class: `SPELL`, `MORPH`, `PUNCT`, `OTHER` |
| `changes_length` | `bool` | `True` if handler inserts/deletes tokens |

| Method | Description |
|--------|-------------|
| `can_apply(tokens, idx)` | Check if error applicable at position |
| `apply(tokens, sentence, idx, modified, rng)` | Apply error, return `ErrorResult` or `None` |

### ErrorResult

```python
@dataclass
class ErrorResult:
    error_type: str    # "noun_case", "spelling_keyboard"
    category: str      # "MORPH", "SPELL"
    start_idx: int     # Start token index (inclusive)
    end_idx: int       # End token index (exclusive)
    original: str      # "Bücher"
    corrupted: str     # "Bucher"
    fix_tag: str       # "$TRANSFORM_CASE_Acc" or "$REPLACE_Bücher"
```

---

## Adding a Schema for Your Language

Schemas map handler subtypes to linguistic error taxonomies.

```yaml
# src/synterr_german/schemas/deu_gec.yaml
name: deu_gec
version: "1.0"
description: "German GEC error taxonomy"

detection_categories:
  SPELL: "Orthographic errors"
  MORPH: "Morphological errors"
  OTHER: "Other errors"

primary_tags:
  Case:
    description: "Noun/adjective case errors"
    detection_category: MORPH
  Conj:
    description: "Verb conjugation errors"
    detection_category: MORPH
  Art:
    description: "Article errors (der/die/das)"
    detection_category: MORPH
  Ortho:
    description: "Spelling errors"
    detection_category: SPELL

mappings:
  noun_case:
    primary: Case
  verb_conjugation:
    primary: Conj
  article:
    primary: Art
  spelling:
    primary: Ortho
```

---

## Testing Your Language Module

```python
# tests/test_german.py
import pytest
from synterr.core.protocol import LanguageModule, Analyzer, ErrorHandler
from synterr_german import GermanLanguage

class TestGermanLanguage:
    def test_implements_protocol(self):
        lang = GermanLanguage()
        assert isinstance(lang, LanguageModule)
        assert lang.code == "de"

    def test_analyzer(self):
        lang = GermanLanguage()
        analyzer = lang.get_analyzer()
        assert isinstance(analyzer, Analyzer)

        tokens = analyzer.analyze("Der Mann liest.")
        assert len(tokens) == 4
        assert tokens[1].pos == "NOUN"

    def test_handlers(self):
        lang = GermanLanguage()
        handlers = lang.get_error_handlers()
        assert all(isinstance(h, ErrorHandler) for h in handlers)

    def test_pipeline_integration(self):
        from synterr.core.pipeline import ErrorPipeline
        from synterr.core.registry import register_language

        register_language(GermanLanguage())
        pipeline = ErrorPipeline("de")

        result = pipeline.generate("Der Mann liest ein Buch.")
        assert result.original_tokens
```

---

## Checklist

- [ ] `LanguageModule` with `code`, `name`, `get_analyzer()`, `get_error_handlers()`, `get_error_distribution()`
- [ ] `Analyzer` returning `AnalyzedToken` with Universal POS/features
- [ ] At least one `ErrorHandler` implementing the full protocol
- [ ] Entry point in `pyproject.toml`
- [ ] Tests for protocol compliance
- [ ] (Optional) Schema YAML for error taxonomy mapping
