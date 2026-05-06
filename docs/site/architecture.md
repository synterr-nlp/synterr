# Architecture

The full developer-facing reference lives in
[`CLAUDE.md`](https://github.com/synterr-nlp/synterr/blob/master/CLAUDE.md).
This page is the conceptual orientation.

## The three-layer separation

```
Handlers ──── how to corrupt
    │
    ▼
Schemas ───── what to call the error
    │
    ▼
Configs ───── how often each error fires
```

This separation is the most important thing to internalize. The same
**handler** (e.g. `NounCaseErrorHandler`) can be tagged differently
under different **schemas** (RLC's `Gov`, ERRANT's `NOUN:CASE:R`,
Rozental's `mo_noun_case_other`), and weighted differently under
different **configs** (`rulec`, `gera`, `balanced`).

You add new error logic in handlers. You change the taxonomy in
schemas. You change the distribution in configs. The three rarely
need to be edited together.

## The pipeline

```
clean text
    │
    ▼
analyzer  ─── tokenization, morphological tags, optional dep parse
    │
    ▼
sample handler  ── weighted by config preset
    │
    ▼
handler.can_apply()  ── per-token check (POS, dep_rel, features)
    │
    ▼
handler.apply()  ── return ErrorResult with corrupted form + label
    │
    ▼
formatter  ── GECToR tags / TSV / JSONL / chat / sft
```

## Handler protocol

Every error handler implements this minimal contract:

```python
class MyHandler:
    name = "my_handler"
    subtypes = ["my_subtype"]   # for schema mapping
    category = "OTHER"           # SPELL / MORPH / PUNCT / OTHER
    changes_length = False       # True if adds/deletes tokens

    def can_apply(self, tokens, idx) -> bool:
        ...

    def apply(self, tokens, sentence, idx, modified, rng=None) -> ErrorResult | None:
        ...
```

`changes_length=True` handlers (insertions, deletions) are applied
last so they don't shift token indices for other handlers.

## Dep-tree-driven generation

A distinguishing design choice: handlers that generate **agreement**,
**government**, and **punctuation** errors use dependency-tree
heuristics rather than position heuristics.

- Agreement handlers (`adj_*`) traverse the `amod` arc to the head
  noun and use the head's features as the reference for confusion-matrix
  lookup.
- `VerbPersonNumberHandler` finds the `nsubj` dependent and uses the
  subject's number as reference.
- `NounCaseErrorHandler` only fires on governed positions
  (`obl`, `nmod`, `iobj`, `obj`) — true government errors.
- The punctuation classifier inspects the head's `dep_rel` to
  distinguish subordinate / compound / parenthetical / isolation /
  homogeneous comma contexts.

This requires `use_depparse=True` (slower but linguistically grounded).

## Confusion matrices

Morphological handlers use empirical confusion matrices derived from
RLC (Russian Learner Corpus) for weighted grammeme substitution rather
than uniform random selection. See
[`docs/research/CASE_CONFUSION_PATTERNS.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/research/CASE_CONFUSION_PATTERNS.md)
for the analysis.

## Multiple schemas

Synterr ships three schemas:

| Schema | Granularity | Use case |
|--------|-------------|----------|
| `rlc` | 35 tags | Russian Learner Corpus annotation alignment |
| `rozental` | 8 / 29 / 100 tags (L0/L1/L2 hierarchy) | Rule-grounded error tracing |
| `errant` | ERRANT-style POS:operation tags | Cross-lingual GEC eval alignment |

When generating data, the same corruption gets the right tag for
whichever schema you ask for. This is what makes synterr's output
useful as both training data and evaluation reference.
