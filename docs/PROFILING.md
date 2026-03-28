# Synterr Profiling Guide

## Setup

```bash
pip install hyperfine  # or: brew install hyperfine / cargo install hyperfine
cd ~/Projects/research/synterr

# Prepare input samples at different sizes
head -500 data/mixed_sources_v4.txt > /tmp/bench_500.txt
head -2000 data/mixed_sources_v4.txt > /tmp/bench_2000.txt
head -10000 data/mixed_sources_v4.txt > /tmp/bench_10000.txt
head -50000 data/mixed_sources_v4.txt > /tmp/bench_50000.txt
```

## Test matrix

### A. Analysis phase (backend × depparse × input size)

This is the most expensive part. Measures tokenization + POS + morphology + (optionally) depparse.

**NOTE:** `-n` in `synterr generate` = max sentences to process (NOT examples to generate).
So `-n 100 -i /tmp/bench_10000.txt` processes 100 sentences from the file.
Use `-n` to control input size, not the input file.

```bash
# Stanza GPU, with depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   -n {size} -i /tmp/bench_10000.txt -o /dev/null'

# Stanza CPU, with depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'CUDA_VISIBLE_DEVICES="" uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   -n {size} -i /tmp/bench_10000.txt -o /dev/null'

# Stanza GPU, WITHOUT depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'uv run synterr generate -l ru --preset balanced --backend stanza \
   -n {size} -i /tmp/bench_10000.txt -o /dev/null'

# Natasha (CPU only, no depparse support)
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000,50000 \
  'uv run synterr generate -l ru --preset balanced --backend natasha \
   -n {size} -i /tmp/bench_50000.txt -o /dev/null'
```

Fill in:

Preset: balanced.

| Backend | Depparse | 500 sents | 1K sents | 2K sents | 10K sents | 50K sents |
|---------|----------|----------|-----------|----------|-----------|-----------|
| stanza GPU | yes   | 11.429 s ±  0.144 s  | 14.366 s ±  0.144 s   | 20.715 s ±  0.210 s  | 71.601 s ±  1.398 s   | — |
| stanza GPU | no    | 9.904 s ±  0.187 s  | 12.146 s ±  0.218 s   | 16.406 s ±  0.261 s  | 51.063 s ±  0.468 s   | — |
| stanza CPU | yes   | 28.872 s ±  1.274 s  | 45.926 s ±  0.718 s   | 77.091 s ±  0.619 s  | 348.440 s ±  6.017 s   | — |
| stanza CPU | no    |   |   |   |    | — |
| natasha    | no    | 3.404 s ±  0.205 s  | 5.359 s ±  0.578 s   | 8.672 s ±  0.989 s  | 37.329 s ±  1.573 s   |  192.854 s ± 17.352 s |
| spacy      | no    | 6.957 s ±  0.090 s  | 9.210 s ±  0.074 s   | 13.966 s ±  0.030 s | 50.872 s ±  0.044 s | — |

Preset: lorugec.


| Backend | Depparse | 500 sents | 1K sents | 2K sents | 10K sents | 50K sents |
|---------|----------|----------|-----------|----------|-----------|-----------|
| stanza GPU | yes   | 11.066 s ±  0.095 s  | 13.933 s ±  0.156 s   | 19.577 s ±  0.057 s  | 66.890 s ±  0.348 s   | — |
| stanza GPU | no    | 9.853 s ±  0.140 s  | 12.137 s ±  0.262 s | 16.058 s ±  0.107 s  | 50.713 s ±  0.358 s   | — |
| stanza CPU | yes   | 26.590 s ±  0.483 s  | 43.846 s ±  1.072 s   | 76.133 s ±  0.551 s | 340.459 s ±  2.759 s   | — |
| stanza CPU | no    |   |   |   |    | — |
| natasha    | no    | 3.260 s ±  0.040 s | 5.393 s ±  0.771 s   | 8.700 s ±  0.794 s  | 35.549 s ±  1.387 s   | 204.431 s ± 13.493 s |
| spacy      | no    | 6.864 s ±  0.030 s  | 9.172 s ±  0.109 s   | 13.582 s ±  0.044 s | 50.395 s ±  0.286 s  | — |

### B. Batch size sweep (stanza only)

```bash
hyperfine --warmup 1 --runs 3 --parameter-list bs 32,64,128,256,512 \
  'uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   --batch-size {bs} -n 1 -i /tmp/bench_2000.txt -o /dev/null'
```

Fill in:

| Batch size | Time (s) | Sent/s | Peak GPU mem, MiB |
|------------|----------|--------|-------------|
| 32 | 21.953 s ±  0.116 s | 91 | 1059 |
| 64 | 20.623 s ±  0.334 s | 97 | 1443 |
| 128 | 20.038 s ±  0.086 s | 100 | 1975 |
| 256 | 19.761 s ±  0.099 s | 101 | 3443 |
| 512 | 19.421 s ±  0.225 s | 103 | 3541 |

### C. Handler tier profiling

Uses the `profile_*` presets to isolate handler categories.
Run with 2K sentences, stanza GPU, depparse on.

```bash
# Spelling tier (no depparse needed, but include for fair comparison)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_spelling --depparse \
   -i /tmp/bench_2000.txt -o /dev/null'

# Morphological tier
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_morph --depparse \
   -i /tmp/bench_2000.txt -o /dev/null'

# Punctuation tier (depparse-dependent)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_punct --depparse \
   -i /tmp/bench_2000.txt -o /dev/null'

# Structural/lexical tier
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_structural --depparse \
   -i /tmp/bench_2000.txt -o /dev/null'

# Full balanced (reference)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset balanced --depparse \
   -i /tmp/bench_2000.txt -o /dev/null'
```

Fill in:

| Preset | Time (s) | Sent/s | Error yield | Notes |
|--------|----------|--------|-------------|-------|
| profile_spelling | 19.562 s ±  0.207 s | 102 | ___% | no inflection |
| profile_morph | 19.559 s ±  0.084 s | 102 | ___% | pymorphy3 heavy |
| profile_punct | 19.775 s ±  0.015 s | 101 | ___% | dep tree traversal |
| profile_structural | 19.548 s ±  0.130 s | 102 | ___% | insert/delete tokens |
| balanced (full) | 20.404 s ±  0.727 s | 98 | ___% | reference |

### D. Force-apply mode (generate-bea-paper)

```bash
hyperfine --warmup 1 --runs 1 --parameter-list size 2000,10000 \
  'uv run synterr generate-bea-paper \
   -i /tmp/bench_{size}.txt -o /dev/null -n 5000 --max-input {size}'
```

| Size  | Time (s)            |
|-------|---------------------|
| 500   | 11.966 s ±  0.157 s |
| 1000  | 15.646 s ±  0.015 s |
| 2000  | 23.095 s ±  0.729 s |
| 10000 | 78.605 s ±  0.682 s |

### E. Memory profiling

On Linux:
```bash
/usr/bin/time -v uv run synterr generate -l ru --preset balanced --depparse \
  -i /tmp/bench_10000.txt -o /dev/null 2>&1 | grep "Maximum resident"
```

On Mac:
```bash
/usr/bin/time -l uv run synterr generate -l ru --preset balanced --depparse \
  -i /tmp/bench_10000.txt -o /dev/null 2>&1 | grep "maximum resident"
```

Fill in:

| Config              | 500 sents  | 1K sents | 2K sents  | 10K sents | 50K sents |
|---------------------|------------|----------|-----------|-----------|-----------|
| stanza GPU depparse | 1727 MB    | 1736 MB  | 1765 MB   | 1743 MB   | -         |
| stanza CPU depparse | 1706 MB    | 1735 MB  | 1730 MB   | 1799 MB   | -         |
| natasha             | 409 MB     | 408 MB   | 409 MB    | 413 MB    | 425 MB    |
| spacy               | 1114 MB    | 1116 MB  | 1119 MB   | 1130 MB   | -         |

### F. Natasha degradation investigation

If natasha chokes on large inputs, find the cliff:

```bash
for n in 1000 2000 5000 10000 20000 50000; do
  echo "=== $n sentences ==="
  head -$n data/mixed_sources_v4.txt > /tmp/bench_natasha.txt
  /usr/bin/time -l uv run synterr generate -l ru --preset balanced --backend natasha \
    -i /tmp/bench_natasha.txt -o /dev/null 2>&1 | grep -E "real|maximum resident"
done
```

## Notes

- First run includes model download (stanza ~500MB). Use `--warmup 1` in hyperfine.
- `-n` in `synterr generate` = max sentences to process (analysis + generation). Use this to control input size.
- `-o /dev/null`: skips file I/O.
- Stanza GPU memory: check with `nvidia-smi` during run.
- All profiling presets set `error_probability: 1.0` and `max_errors_per_sentence: 1` for consistent error yield measurement.
