# synterr

[![BEA 2026](https://img.shields.io/badge/paper-BEA%202026-b3261e)](https://synterr-nlp.github.io/papers/bea-2026/)
[![License: MIT](https://img.shields.io/badge/license-MIT-7a7a7a)](https://opensource.org/licenses/MIT)

Generate synthetic grammatical errors for training GEC models.

synterr corrupts clean text with realistic learner-like errors, outputting GECToR-compatible training data with error type labels.

## Why

Training GEC models requires parallel data (incorrect → correct). Real learner corpora are small and expensive to annotate. synterr generates unlimited synthetic training data from any clean corpus, with error distributions matching real learner errors.

## Install

Until the first PyPI release lands, install from source:

```bash
pip install "synterr[russian] @ git+https://github.com/synterr-nlp/synterr"
```

### Development (uv)

```bash
git clone https://github.com/synterr-nlp/synterr
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
uv run synterr generate -l ru -i in.txt -o out.edits -e spelling,noun_case --depparse

# Single sentence corruption (for testing)
uv run synterr corrupt -l ru -e spelling "Мама мыла раму."

# Dep-tree-aware errors (noun_case, adj_case) need --depparse
uv run synterr corrupt -l ru -e noun_case --depparse "Книга лежит на столе."
# Original:  Книга лежит на столе .
# Corrupted: Книга лежит на стол .   (wrong case: "лежит на" requires prepositional)
```

Output formats (`-f` flag): `gector` (default), `tsv`, `jsonl`,
`chat` (instruction-tuning), `sft` (`{src, tgt}` JSONL).
(`to_diff()` is available on the Python API but not exposed via CLI.)

Rule-targeted SFT generation (force-apply each LoRuGEC rule, with rule labels):

```bash
uv run synterr generate-targeted -i corpus.txt -o train.jsonl \
    -n 50000 --seed 42 --balance-directions
```

Produces `{"src": corrupted, "tgt": clean, "rule": rule_name}` JSONL
plus a `.dist.json` sidecar of per-rule counts.

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

**v1.0.0** — Paper release. 24 handlers / 63 subtypes covering spelling, morphology, lexical, structural, and punctuation errors. Output formats: GECToR tags, TSV, JSONL (with rule labels), chat (instruction-tuning), SFT.

Active development continues toward future releases; see the `CHANGELOG.md`
for shipped milestones.

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
  url     = {https://github.com/synterr-nlp/synterr},
}
```

Data generation provenance and SHA256 checksums are documented in
[`data/V4_DATA_PROVENANCE.md`](data/V4_DATA_PROVENANCE.md).

## License

MIT
