# synterr

Reproducible error generation for Grammatical Error Correction (GEC).

## Features

- Language-agnostic core with pluggable language modules
- Russian language support with stanza-based contextual morphological analysis
- Multiple error types: spelling, morphological, lexical, structural
- GECToR-compatible output format with detection labels
- CLI for batch processing

## Installation

```bash
# Basic installation
pip install synterr

# With Russian language support
pip install synterr[russian]

# Development installation
uv sync --all-extras
```

## Quick Start

```bash
# List available languages
synterr list-languages

# List error types for Russian
synterr list-errors --lang ru

# Generate synthetic errors
synterr generate --lang ru --input corpus.txt --output errors.edits

# With specific error types
synterr generate --lang ru --input corpus.txt --output errors.edits --errors spelling,noun_case
```

## Output Format

The output uses GECToR edit format with detection labels:

```
$STARTSEPL|||SEPR$KEEP:CORRECT wordSEPL|||SEPR$REPLACE_original:SPELL ...
```

Detection classes:
- `CORRECT` - No error
- `SPELL` - Orthographic errors
- `MORPH` - Morphological errors (case, number, gender, tense)
- `PUNCT` - Punctuation errors
- `OTHER` - Lexical/structural errors

## Architecture

The package uses a two-stage morphological processing pipeline:

1. **Analysis** (stanza): Contextual POS tagging, lemmatization, and morphological feature extraction
2. **Inflection** (pymorphy3 for Russian): Generating corrupted word forms

This enables realistic error generation that respects morphological context.

## Supported Error Types (Russian)

### Morphological
- Noun case/number errors
- Adjective case/number/gender errors
- Verb person/number/tense errors

### Spelling
- Vowel reduction (unstressed vowel confusion)
- тся/ться confusion
- Consonant devoicing
- Keyboard typos

### Lexical
- Preposition/conjunction/pronoun substitution
- Paronym confusion

### Structural
- Function word deletion (fix: $APPEND)
- Filler word insertion (fix: $DELETE)

## Adding New Languages

Languages are registered via entry points. Create a module that implements the `LanguageModule` protocol:

```python
from synterr.core.protocol import LanguageModule, ErrorHandler

class MyLanguage(LanguageModule):
    code = "xx"
    name = "My Language"

    def get_analyzer(self, use_depparse=False):
        return MyAnalyzer(use_depparse)

    def get_error_handlers(self) -> list[ErrorHandler]:
        return [...]

    def get_error_distribution(self) -> dict[str, float]:
        return {"spelling": 0.15, "noun_case": 0.10, ...}
```

Register in pyproject.toml:

```toml
[project.entry-points."synterr.languages"]
my_language = "my_package:MyLanguage"
```

## License

MIT
