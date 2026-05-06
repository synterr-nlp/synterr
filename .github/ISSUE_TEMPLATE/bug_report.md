---
name: Bug report
about: Report a handler producing incorrect output, a CLI failure, or unexpected behavior
labels: bug
---

## What happened

<!-- One sentence: what synterr did wrong. -->

## Reproducing

```bash
# Exact command line, or short Python snippet
uv run synterr corrupt -l ru -e <handler> "<sentence>"
```

**Input sentence:** `…`
**Handler / subtype / preset:** `…`

## Expected vs actual

**Expected:** `…`
**Got:** `…`

## Environment

- synterr version: <!-- output of `uv run synterr --version` -->
- Python version:
- OS:
- Backend (if relevant): stanza / natasha / spacy

## Anything else

<!-- Is this a corruption-quality issue (handler generates a non-word /
the wrong form / a tautology), a CLI bug, a regression, etc.? Link
related issues / commits if applicable. -->
