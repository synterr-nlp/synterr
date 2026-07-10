# Synthetic Data Generation for GEC — Research Landscape

Survey of approaches to generating synthetic training data for Grammatical Error Correction, with focus on relevance to synterr.

## Approaches

### 1. Random Noise (2014–2018)

Random token deletion, insertion, swap. Aspell-based confusion sets for spelling errors. No linguistic modeling whatsoever.

Works for English because morphology is simple — most errors are word-choice or spelling. Transformers generalize from noisy→clean even when the noise is unrealistic.

### 2. Back-Translation (2019)

Train a clean→noisy seq2seq model on real learner data, then generate new errors.

- **Kiyono et al. (2019)**: "Massive Exploration of Pseudo Data for Grammatical Error Correction." Showed back-translation + character noise outperforms random errors for pretraining.
- **Grundkiewicz et al. (2019)**: Combined aspell confusion sets with back-translation for English, Russian, and German.

Better than random, but a black box — no control over error type distribution. Output skews toward whatever the training corpus had.

### 3. Tagged Corruption (2021–2024)

Give a model a clean sentence + an error type tag (from ERRANT), generate a corrupted version with that specific error. Enables **controlling error distribution** to match a target domain.

- **Stahlberg & Kumar (2021)**: "Synthetic Data Generation for Grammatical Error Correction with Tagged Corruption Models." BEA Workshop at ACL. Created the [C4_200M dataset](https://github.com/google-research-datasets/C4_200M-synthetic-dataset-for-grammatical-error-correction) — 200M synthetic examples for English.
- **Stahlberg & Kumar (2024)**: Extended to low-resource languages (Russian, German, Romanian, Spanish) using PaLM 2. 2.5M examples per language. Consistent gains, especially for small models and low-resource settings. BEA Workshop at NAACL.

This is the closest existing work to synterr's approach, but uses a neural model for corruption instead of linguistic rules.

### 4. LLM-Based (2023+)

Prompt GPT-4/Llama/etc. to "write like a learner" or introduce specific errors.

- **"To Err Is Human, but Llamas Can Learn It Too" (2024)**: Systematic evaluation of LLM-based error generation.
- Expensive, hard to control precisely, tends to produce LLM-natural errors (not learner errors).
- For smaller generative models, using API calls to SOTA models for data generation may be more practical than rule-based approaches.

## Russian GEC Specifically

The landscape is thin compared to English:

- **Rozovskaya & Roth (2019)**: "Grammar Error Correction in Morphologically Rich Languages: The Case of Russian." TACL. Created RULEC-GEC — first serious Russian GEC dataset. Notes morphological complexity challenges but doesn't propose synthetic generation.
- **Trinh & Rozovskaya (2021)**: RU-Lang8 dataset.
- **Sorokin et al. (2016)**: GERA corpus — Russian school texts, heavily skewed toward punctuation errors (42.5%).
- **RuGECToR (2024)**: "Rule-Based Neural Network Model for Russian Language Grammatical Error Correction." Programming and Computer Software. Compiled correction rules dictionary and generated synthetic data. Closest to synterr's approach, but published details are sparse.
- **LORuGEC**: Recent Russian GEC effort with broader coverage.

Most Russian GEC work uses RULEC + RU-Lang8 as-is without synthetic augmentation.

## Where synterr Fits

synterr is unusual in combining:
1. **Rule-based** corruption (not neural)
2. **Linguistically grounded** error taxonomy (Rozental § references)
3. **Morphologically rich language** (Russian)
4. **Dependency-tree heuristics** for punctuation (novel — no precedent found)

### Open questions

- **Does linguistic precision matter for downstream training?** Tagged corruption folks argue neural models learn good enough patterns from data. But for Russian agreement/government errors that depend on specific morphological features, explicit modeling may produce more realistic training data — especially for rare error types.
- **Hard classifiers vs. generative models**: For GECToR-style tagging, synterr's precision may be marginal. For smaller generative models (e.g., 1B Gemma QLoRA), linguistically typed errors could teach the model "when I see this dep structure, this comma matters" in ways a hard classifier can't learn.
- **Rozental copyright**: The schema (§ numbers, tag hierarchy) is publishable as a classification system. The source text is copyrighted — can't publish that Rozental was used as training data for QLoRA, which limits explainability.

## Key References

| Paper | Year | Venue | Relevance |
|-------|------|-------|-----------|
| Bryant et al. "GEC: A Survey of the State of the Art" | 2023 | Computational Linguistics | Comprehensive survey |
| Stahlberg & Kumar "Tagged Corruption Models" | 2021 | BEA @ ACL | Closest to synterr (neural) |
| Stahlberg & Kumar "Low-Resource Tagged Corruption" | 2024 | BEA @ NAACL | Extension to Russian |
| Rozovskaya & Roth "GEC in MRLs: Russian" | 2019 | TACL | RULEC-GEC dataset |
| Kiyono et al. "Massive Exploration of Pseudo Data" | 2019 | ACL | Back-translation baseline |
| RuGECToR | 2024 | Prog. & Comp. Software | Rule-based Russian GEC |
| GEC for Low-Resource Languages Survey | 2025 | PeerJ CS | Recent comprehensive review |

Paper collection: [github.com/gotutiyan/GEC-Info](https://github.com/gotutiyan/GEC-Info)
