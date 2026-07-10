# synterr

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20182862-3b82f6)](https://doi.org/10.5281/zenodo.20182862)
[![BEA 2026](https://img.shields.io/badge/paper-BEA%202026-b3261e)](https://synterr-nlp.github.io/papers/bea-2026/)
[![Docs](https://img.shields.io/badge/docs-synterr--nlp.github.io-4c9a2a)](https://synterr-nlp.github.io/synterr/)
[![License: MIT](https://img.shields.io/badge/license-MIT-7a7a7a)](https://opensource.org/licenses/MIT)

**Rule-grounded synthetic error generation for Russian GEC.**
Feed it clean text; get back training pairs where every error names the
rule it violates.

![Tagged corruptions: second locative, double comparative, asyndetic comma](docs/site/assets/fig_corrupt.svg)

## Why synterr

Most synthetic-corruption tools mangle text and hope the noise resembles
human errors. synterr takes the opposite bet — every corruption is the
*inversion of a specific rule*, and it shows its work:

- **Every error has a defensible label.** Corruptions map to a
  hierarchical grammar-reference taxonomy (down to § paragraphs), to
  [RLC](https://aclanthology.org/2024.lrec-main.1241/) tags, or to ERRANT.
  Filter, re-weight, and audit your training data *by rule*.
- **Every error has a syntactic justification.** Government, agreement,
  and punctuation handlers fire on dependency-tree evidence — and
  **refuse to fire** where the "corruption" would produce acceptable
  Russian. A wrong comma is only useful training signal if it's actually
  wrong.
- **Every error is population-aware.** Each fine-grained tag carries an
  `l2_applicability` rating (full / partial / none): does the native
  prescriptive rule describe the error the way L2 learners actually make
  it? One schema, queryable by population, per error, in the output.

## Quickstart

```bash
pip install "synterr[russian] @ git+https://github.com/synterr-nlp/synterr"
```

```bash
# corrupt one sentence (great for inspection)
synterr corrupt -l ru -e noun_case_prep "Мы гуляли в лесу весь день."
# Original:  Мы гуляли в лесу весь день .
# Corrupted: Мы гуляли в лесе весь день .
# Error:     noun_case_prep_e_u @ position 3
# Fix tag:   $REPLACE_лесу

# generate a corpus with a learner-calibrated error distribution
synterr generate -l ru --preset rulec --schema rozental \
    -i clean.txt -o train.jsonl --output-format jsonl --seed 42
```

Development install:

```bash
git clone https://github.com/synterr-nlp/synterr && cd synterr
uv sync --all-extras
uv run synterr --help && uv run pytest
```

## The pipeline

```
clean text ──► 1. survey ──► starving error classes
                                  │
                  2. mine-pools ◄─┘
                        │
   per-class pools ─────┤
   + base corpus  ──────┴──► 3. generate ──► tagged training pairs
```

Stages 1–2 exist because precision-gated handlers only fire where the
error is *recoverable* — and plain news text simply lacks many trigger
contexts. `synterr survey` measures per-subtype fire rates on your
corpus; `synterr mine-pools` sweeps large sources for candidate
sentences per starving class (patterns derive from the live handler
lexicons, so they can't drift). Measured effect: `verb_tense` fires at
10/1k sentences on raw news vs ~1700/1k on its mined pool.

Full contract — every stage, every output field:
**[docs → Pipeline](https://synterr-nlp.github.io/synterr/pipeline/)**.

### Output: two label layers

```jsonc
{ "type": "noun_case_prep_e_u",              // handler-owned: always present
  "fix_tag": "$REPLACE_лесу",
  "schema_tag": "mo_noun_case",              // schema-owned: only with --schema
  "schema_l2_tag": "mo_noun_case_prep_e_u",  //   → §-level taxonomy tag
  "schema_l2_applicability": "partial" }     //   → native↔learner bridge
```

Handler-owned fields are the ground truth of what the corruption did.
Schema-owned fields are opt-in (`--schema rozental|rlc|errant`) and
re-labelable: the mapping lives in schema YAML, not in the corruption —
relabel a corpus under another taxonomy without regenerating it.

## What it generates

46 handlers / 106 subtypes across five categories
(`synterr list-errors -l ru` is authoritative):

| Category | Examples |
|----------|----------|
| Spelling | *молоко → малако*, *учится ↔ учиться*, не/ни, adverb & compound spelling |
| Morphology | case government (*ждали автобуса → автобусу*), agreement, second locative (*в лесу → в лесе*), short/full adjectives, numeral declension |
| Punctuation | dep-tree-classified comma deletion/insertion/pairing (10+11+5 subtypes incl. asyndetic §116 and vocative §101), dash rules (5 subtypes) with §79 exception handling |
| Lexical | paronyms (*одеть ↔ надеть*), preposition/conjunction confusion sets |
| Structural | word omission/insertion with grammaticality guards |

Morphological corruption is driven by **empirical confusion matrices**
extracted from the Russian Learner Corpus (N=2,760 case confusions) —
learners' actual substitution probabilities, not uniform noise.

## Presets: how often each error fires

| Preset | Source |
|--------|--------|
| `rulec` | RULEC-GEC L2/heritage learner essay distribution |
| `gera` | GERA school-text distribution (punctuation-heavy) |
| `gera_bidir` | gera with direction-balanced punctuation (SFT) |
| `lorugec` | uniform over the 48 LoRuGEC benchmark rules |
| `balanced` | flat coverage |

## Backends

| Backend | Speed (single) | Speed (batch) | Accuracy | Install |
|---------|----------------|---------------|----------|---------|
| stanza (default) | ~75 sent/s | ~500 sent/s | Best | `pip install synterr[russian]` |
| natasha | ~1700 sent/s | ~1700 sent/s | Good | `pip install synterr[natasha]` |
| spacy | ~530 sent/s | ~760 sent/s | Good | `pip install synterr[spacy]` |

*Benchmarked on M4 Pro. Batch mode uses `generate_batch()` / `analyze_batch()`.*

## Quality control

Every handler has been audited against the underlying grammar reference,
including live-repro adversarial review of its outputs; the invariant
suite (`tests/test_core/test_weight_invariants.py`) structurally
prevents the "config silently ignored" bug class; per-rule benchmark
coverage is live-verified sentence by sentence
([docs/research/LORUGEC_COVERAGE.md](docs/research/LORUGEC_COVERAGE.md)).
1,300+ tests.

## Status

**v1.0.1** (BEA 2026 paper release) is tagged and archived on Zenodo;
v4 training-data provenance and checksums:
[`data/V4_DATA_PROVENANCE.md`](data/V4_DATA_PROVENANCE.md).
Master moves fast — per-detail history in [`CHANGELOG.md`](CHANGELOG.md),
current state on the [docs site](https://synterr-nlp.github.io/synterr/).

## References

Based on error taxonomies from:
- [RLC](https://aclanthology.org/2024.lrec-main.1241/) — Russian Learner Corpus (38 error tags)
- [RULEC-GEC](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00251) — Rozovskaya & Roth 2019
- [RuBLiMP](https://github.com/RussianNLP/RuBLiMP) — Minimal pairs benchmark (borrowed aspect pairs)

## Third-Party Resources

synterr uses the following external resources for morpheme and stress analysis:

**Morphberta-K** — RuRoBERTa-based morpheme segmentation model (99% F1).
© 2025 НП «Национальный корпус русского языка». Licensed for research and non-commercial use under the [НКРЯ License Agreement](https://ruscorpora.ru/page/license-neuro/).
Citations:
- Morozov D., Garipov T., Lyashevskaya O., Savchuk S., Iomdin B., & Glazkova A. (2024). Automatic Morpheme Segmentation for Russian: Can an Algorithm Replace Experts? *Journal of Language and Education*, 10(4), 71–84. https://doi.org/10.17323/jle.2024.22237
- Morozov D., Astapenka L., Glazkova A., Garipov T., & Lyashevskaya O. (2025). BERT-like Models for Slavic Morpheme Segmentation. In *Proceedings of ACL 2025* (Vol. 1: Long Papers), pp. 6795–6815. https://doi.org/10.18653/v1/2025.acl-long.337

**morpholog** — Tikhonov morpheme dictionary (93k entries), used via pickle.
© [morpholog package](https://pypi.org/project/morpholog/). Based on А.Н. Тихонов, *Морфемно-орфографический словарь*.

**Zaliznyak 2010** — *Грамматический словарь русского языка*, А.А. Зализняк, 6th edition (106k entries with exact stress).
Rights holder: А.А. Зализняк. Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
Source: [gramdict/zalizniak-2010](https://github.com/gramdict/zalizniak-2010). Digitized from proofs prepared by Е.А. Гришина, published by С. Слепов with permission of the rights holder.

**russtress** — Russian word stress prediction (fallback for words not in Zaliznyak).
https://github.com/MashaPo/russtress
Citation: Ponomareva M., Milintsevich K., Chernyak E., & Starostin A. (2017). Automated Word Stress Detection in Russian. In *Proceedings of the First Workshop on Subword and Character Level Models in NLP*, pp. 31–35. https://doi.org/10.18653/v1/W17-4104

## Citation

If you use synterr in your research, please cite:

```bibtex
@inproceedings{smirnova2026aggregate,
  title     = {What Aggregate Scores Hide: Per-Rule Evaluation of Russian Grammatical Error Correction},
  author    = {Smirnova, Anna and Kopan, Artyom and Makeev, Vladislav and Chernishev, George},
  booktitle = {Proceedings of the 21st Workshop on Innovative Use of NLP for Building Educational Applications (BEA)},
  year      = {2026},
  url       = {https://synterr-nlp.github.io/papers/bea-2026/},
}
```

To cite the software release specifically:

```bibtex
@software{synterr_2026,
  title   = {synterr: rule-grounded synthetic error generation for Russian GEC},
  author  = {Smirnova, Anna and Kopan, Artyom and Makeev, Vladislav and Chernishev, George},
  year    = {2026},
  version = {v1.0.1},
  doi     = {10.5281/zenodo.20182862},
  url     = {https://github.com/synterr-nlp/synterr},
}
```

## License

MIT
