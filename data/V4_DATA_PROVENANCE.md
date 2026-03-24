# v4 Data Provenance

## Pipeline overview

```
[Full corpora on disk]
        │
        ▼
mine_scarce_sents.py ──→ scarce_sents_v4.txt (54.8K, all kept)
        │
        │  Also feeds:
        ▼
build_v4_sources.py ───→ mixed_sources_v4.txt (150K)
        │                   = scarce (37%) + rublimp pool (38%) + news (25%)
        ▼
generate_sft.py ───────→ qwen_sft_v4.jsonl + .dist.json
                            --balance-directions --seed 42
```

## Step 1: Extract full corpora to plain text

All sources quality-filtered (8-25 words, starts uppercase, ends `.!?»"`,
≥60% Cyrillic), deduplicated within source.

| Source | Script | Sentences | Seed | File |
|--------|--------|----------:|------|------|
| RuBLiMP pool | `extract_rublimp_pool.py` | 741,127 | 42 | `rublimp_pool_sents.txt` |
| Taiga Fontanka | `extract_taiga_sents.py --target 0` | 2,455,494 | 42 | `taiga/taiga_fontanka.txt` |
| Taiga Interfax | `extract_taiga_sents.py --target 0` | 189,662 | 42 | `taiga/taiga_interfax.txt` |
| Taiga Lenta | `extract_taiga_sents.py --target 0` | 159,984 | 42 | `taiga/taiga_lenta.txt` |
| Wiki 200K | `extract_wiki_sents.py` | 200,000 | — | `wiki_200k.txt` |
| Articles (Habr/CL/НГ/RT) | extracted on the fly | ~710,000 | — | `ru_kw_eval_datasets/data/*.zip` |

**RuBLiMP pool** = unfiltered scoring pool from RuBLiMP (Taktasheva et al., EMNLP 2024).
1.5M minimal pairs across 47 phenomena, scored by 25 LMs. We extract the grammatical
(`s`) column only, using header-based column lookup (not index). Domain mix: librusec 58%,
wikipedia 22%, wikinews 20%. All 86,655 benchmark sentences excluded.

**Taiga** = Shavrina & Shapovalova 2017. Archives from `retagged_taiga.tar.gz`,
loaded via corus (Korobov 2020). Sentence-split with razdel.

## Step 2: Mine scarce-form sentences

Script: `mine_scarce_sents.py` — exhaustive grep of all 5 sources for patterns
matching underperforming LoRuGEC rules. No reservoir sampling — keeps ALL matches.
Overrepresented categories capped at 5K via seeded shuffle + truncation.

**Scarce patterns** (derived from handler wordlists + LoRuGEC gap analysis):
- Rare solid conjunctions: оттого, отчего, причём/причем, притом
- Separate conjunction forms: что бы, так же, за то, от того, при том/чём/чем
- Numerals: полтора/полторы/полтораста/полутора
- -таки
- Diminutive suffixes: -еньк/-оньк/-иньк
- Place-name adjective suffixes: -инск/-енск (3-5 char stem)
- Neuter diminutive suffixes: -ице/-ицо/-ецо/-еце (short words only)
- пол- with dash
- Compound adjective prefixes: военно-, научно-, торгово-, северо- etc.
- Frozen phraseological pairs: ни слуху ни духу, ни пуха ни пера etc.
- Indivisible expressions: как следует, мало кто, что угодно etc.
- Collocation trigger verbs: загладить, закадычный, одержать etc.

**Output**: `scarce_sents_v4.txt` — 54,823 sentences, seed 42.

**Capped categories** (5K each): insk_ensk, its_ets, conjunctions_solid, compound_adj.

## Step 3: Build source mix

Script: `build_v4_sources.py`

1. Load scarce sents (54,823 — kept in full)
2. Load rublimp pool (741K), remove scarce + benchmark → 729K remaining
3. Load news (taiga fontanka/interfax/lenta + articles) → 3.3M, remove scarce → 3.3M remaining
4. Budget = 150K - 54.8K scarce = 95.2K, split 60/40 pool/news
5. Reservoir sample: 57K pool + 38K news
6. Combine, shuffle with seed 42

**Output**: `mixed_sources_v4.txt` — 150,000 sentences.

**Composition**:
- Scarce enrichment: 54,823 (37%)
- RuBLiMP pool (librusec/wiki/wikinews): 57,106 (38%)
- News (Taiga + articles): 38,071 (25%)
- RuBLiMP benchmark contamination: 0

## Step 4: Generate SFT

Script: `generate_sft.py`

```bash
uv run python scripts/generate_sft.py \
  -i data/mixed_sources_v4.txt \
  -o data/qwen_sft_v4.jsonl \
  -n 50000 --seed 42 --depparse \
  --max-input 150000 --batch-size 128 \
  --balance-directions
```

59 generation rules (mapped from 48 LoRuGEC evaluation rules).
Bidirectional for all split/merge phenomena.
Direction balancing caps overrepresented direction to match underrepresented.
MosesDetokenizer(lang="ru") for output text.

Output: `qwen_sft_v4.jsonl` — 39,209 examples, `{"src": corrupted, "tgt": clean, "rule": rule_name}`
Distribution sidecar: `qwen_sft_v4.dist.json`
40/59 rules at full target. 19 short (scarce forms, narrow syntactic triggers).

**Direction balance in final data**:
- Punct add (comma_delete/dash_delete → model adds): 7,262
- Punct remove (comma_insert → model removes): 2,374
- Ratio: 3:1 add/remove — matches natural L1 error distribution (missing > extra)

## Key fixes in v4 vs v3c

| Issue | v3c | v4 |
|-------|-----|-----|
| RuBLiMP contamination | 1,863 sents | 0 |
| Bidirectional не | attach only | attach + detach |
| Bidirectional adverbs | split only | split + merge |
| Bidirectional conjunctions | unbalanced (682 merge, 6 split for чтобы) | balanced |
| suffix_enk_onk | fired on adjectives (маленький) | NOUN only, е↔о↔и |
| comma_before_kak | inserted on advmod как (60% false positive) | head POS check |
| Rublimp pool column | mixed grammatical + ungrammatical sents | header-based `s` column only |
| Source mix reproducibility | ad-hoc concatenation across sessions | single seeded script |
| Scarce form mining | conjunction-only, inline code | all underperforming patterns, reproducible |

## Reproduction

```bash
# 1. Extract corpora (one-time)
uv run python scripts/extract_rublimp_pool.py ~/Downloads/results.zip \
  --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
  -o data/rublimp_pool_sents.txt --seed 42

uv run python scripts/extract_taiga_sents.py data/taiga/Fontanka.tar.gz \
  --sources fontanka --target 0 --seed 42 -o data/taiga/
# (repeat for Interfax.tar.gz, Lenta.tar.gz)

# 2. Mine scarce forms
uv run python scripts/mine_scarce_sents.py \
  data/rublimp_pool_sents.txt data/taiga/taiga_fontanka.txt \
  data/taiga/taiga_interfax.txt data/taiga/taiga_lenta.txt \
  data/wiki_200k.txt \
  -o data/scarce_sents_v4.txt --seed 42 --cap 5000

# 3. Build source mix
uv run python scripts/build_v4_sources.py \
  --scarce data/scarce_sents_v4.txt \
  --rublimp-pool data/rublimp_pool_sents.txt \
  --news data/taiga/taiga_fontanka.txt data/taiga/taiga_interfax.txt \
         data/taiga/taiga_lenta.txt \
  --articles ~/Projects/research/gector/data/ru_kw_eval_datasets/data \
  --benchmark ~/Projects/research/gector/data/RuBLiMP/datasets \
  --output data/mixed_sources_v4.txt --total 150000 --seed 42

# 4. Generate SFT
uv run python scripts/generate_sft.py \
  -i data/mixed_sources_v4.txt -o data/qwen_sft_v4.jsonl \
  -n 50000 --seed 42 --depparse --max-input 150000 \
  --batch-size 128 --balance-directions
```

## Citations

- **RuBLiMP**: Taktasheva et al. (EMNLP 2024) — pool sentences, benchmark exclusion
- **Taiga**: Shavrina & Shapovalova (2017) — Fontanka, Interfax, Lenta sub-corpora
- **corus**: Korobov (2020) — corpus loading library
- **Articles**: Fedorov (2019) ru_kw_eval_datasets — Habr, CyberLeninka, НГ, RT
- **Wikipedia**: Russian Wikipedia dump (ruwiki-latest-pages-articles.xml.bz2)
