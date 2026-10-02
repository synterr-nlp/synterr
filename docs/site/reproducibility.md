# Reproducibility

The paper-release v4 dataset is pinned, checksummed, and verified
byte-identical against the trained-on file. Reproducibility is
**archival, not regenerative**: the checksummed files are the
authoritative objects, and the pipeline below does not re-create them
bit for bit.

1. **The pinned generation commit**: tag `v4-data` (commit `2fd4d78`;
   pinned as `898814d` before the May 2026 history rewrite). Later
   releases change handler behavior — most notably the `noun_case` arc
   gate — so generating against any release tag produces different
   output by design.
2. **The source corpora**: documented in
   [`data/V4_DATA_PROVENANCE.md`](https://github.com/synterr-nlp/synterr/blob/master/data/V4_DATA_PROVENANCE.md).
   The shipped source mix `mixed_sources_v4.txt` was not produced by the
   committed `build_v4_sources.py` and cannot be regenerated from any
   committed script (see the provenance caveat there); it is archived
   and checksummed as-is.
3. **Seed=42** in both `build_v4_sources.py` and `generate_sft.py`.

## Verifying you have the right files

```bash
uv run python scripts/verify_v4.py
```

This checks SHA256 against `data/v4_checksums.txt`. Output should be:

```
8/8 OK, 0 mismatch, 0 missing
```

## Re-running the intended pipeline

```bash
git checkout v4-data

# 1. Mine scarce sentences
uv run python scripts/mine_scarce_sents.py …

# 2. Extract clean rublimp pool
uv run python scripts/extract_rublimp_pool.py …

# 3. Build source mix (150K, 60-40 pool/news split)
uv run python scripts/build_v4_sources.py \
    --output data/mixed_sources_v4.txt \
    --total 150000 --seed 42

# 4. Generate SFT
uv run python scripts/generate_sft.py \
    -i data/mixed_sources_v4.txt \
    -o data/qwen_sft_v4.jsonl \
    -n 50000 --seed 42 --depparse \
    --max-input 150000 --batch-size 128 \
    --balance-directions
```

Full step-by-step (with corpus paths and benchmark exclusions) is in
[`V4_DATA_PROVENANCE.md`](https://github.com/synterr-nlp/synterr/blob/master/data/V4_DATA_PROVENANCE.md).

## What the v4 dataset is

- **39,209 SFT examples** across the synterr handler set
- **Intended source mix**: 54,823 scarce-form-mined sentences + 57,106
  RuBLiMP pool + 38,071 Taiga news, RuBLiMP benchmark items excluded.
  The shipped mix differs: 154,806 non-blank lines, only 107,265 unique,
  so the SFT data likely repeats some source sentences (a documented v4
  limitation)
- **Direction-balanced** for split / merge / insert / delete handlers

## Citing

When citing the dataset specifically (vs. the synterr tool), reference
the paper and the pinned generation commit (tag `v4-data`).
