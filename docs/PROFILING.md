# Synterr Profiling Guide

## Setup

```bash
pip install hyperfine  # or: brew install hyperfine / cargo install hyperfine
cd ~/Projects/research/synterr

# Prepare input samples at different sizes
head -500 data/mixed_sources_v4.txt > /tmp/bench_500.txt
head -2000 data/mixed_sources_v4.txt > /tmp/bench_2k.txt
head -10000 data/mixed_sources_v4.txt > /tmp/bench_10k.txt
head -50000 data/mixed_sources_v4.txt > /tmp/bench_50k.txt
```

## Test matrix

### A. Analysis phase (backend × depparse × input size)

This is the most expensive part. Measures tokenization + POS + morphology + (optionally) depparse.

**NOTE:** `-n` in `synterr generate` = max sentences to process (NOT examples to generate).
So `-n 100 -i /tmp/bench_10k.txt` processes 100 sentences from the file.
Use `-n` to control input size, not the input file.

```bash
# Stanza GPU, with depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   -n {size} -i /tmp/bench_10k.txt -o /dev/null'

# Stanza CPU, with depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'CUDA_VISIBLE_DEVICES="" uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   -n {size} -i /tmp/bench_10k.txt -o /dev/null'

# Stanza GPU, WITHOUT depparse
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000 \
  'uv run synterr generate -l ru --preset balanced --backend stanza \
   -n {size} -i /tmp/bench_10k.txt -o /dev/null'

# Natasha (CPU only, no depparse support)
hyperfine --warmup 1 --runs 3 --parameter-list size 100,500,2000,10000,50000 \
  'uv run synterr generate -l ru --preset balanced --backend natasha \
   -n {size} -i /tmp/bench_50k.txt -o /dev/null'
```

Fill in:

Preset: balanced.

| Backend | Depparse | 500 sents | 1K sents | 2K sents | 10K sents | 50K sents |
|---------|----------|----------|-----------|----------|-----------|-----------|
| stanza GPU | yes   | 11.429 s ±  0.144 s  | 14.366 s ±  0.144 s   | 20.715 s ±  0.210 s  | 71.601 s ±  1.398 s   | — |
| stanza GPU | no    | 9.904 s ±  0.187 s  | 12.146 s ±  0.218 s   | 16.406 s ±  0.261 s  | 51.063 s ±  0.468 s   | — |
| stanza CPU | yes   | 28.872 s ±  1.274 s  | 45.926 s ±  0.718 s   | 77.091 s ±  0.619 s  | 348.440 s ±  6.017 s   | — |
| stanza CPU | no    | ___ s/s  | ___ s/s   | ___ s/s  | ___ s/s   | — |
| natasha    | no    | 3.404 s ±  0.205 s  | 5.359 s ±  0.578 s   | 8.672 s ±  0.989 s  | 37.329 s ±  1.573 s   | ___ s/s |
| spacy      | no    | 6.957 s ±  0.090 s  | 9.210 s ±  0.074 s   | 13.966 s ±  0.030 s | 50.872 s ±  0.044 s | — |

### B. Batch size sweep (stanza only)

```bash
hyperfine --warmup 1 --runs 3 --parameter-list bs 32,64,128,256,512 \
  'uv run synterr generate -l ru --preset balanced --depparse --backend stanza \
   --batch-size {bs} -n 1 -i /tmp/bench_2k.txt -o /dev/null'
```

Fill in:

| Batch size | Time (s) | Sent/s | Peak GPU mem |
|------------|----------|--------|-------------|
| 32 | | | |
| 64 | | | |
| 128 | | | |
| 256 | | | |
| 512 | | | |

### C. Handler tier profiling

Uses the `profile_*` presets to isolate handler categories.
Run with 2K sentences, stanza GPU, depparse on.

```bash
# Spelling tier (no depparse needed, but include for fair comparison)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_spelling --depparse \
   -i /tmp/bench_2k.txt -o /dev/null'

# Morphological tier
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_morph --depparse \
   -i /tmp/bench_2k.txt -o /dev/null'

# Punctuation tier (depparse-dependent)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_punct --depparse \
   -i /tmp/bench_2k.txt -o /dev/null'

# Structural/lexical tier
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset profile_structural --depparse \
   -i /tmp/bench_2k.txt -o /dev/null'

# Full balanced (reference)
hyperfine --warmup 1 --runs 3 \
  'uv run synterr generate -l ru --preset balanced --depparse \
   -i /tmp/bench_2k.txt -o /dev/null'
```

Fill in:

| Preset | Time (s) | Sent/s | Error yield | Notes |
|--------|----------|--------|-------------|-------|
| profile_spelling | | | ___% | no inflection |
| profile_morph | | | ___% | pymorphy3 heavy |
| profile_punct | | | ___% | dep tree traversal |
| profile_structural | | | ___% | insert/delete tokens |
| balanced (full) | | | ___% | reference |

### D. Force-apply mode (generate-bea-paper)

```bash
hyperfine --warmup 1 --runs 1 --parameter-list size 2000,10000 \
  'uv run synterr generate-bea-paper \
   -i /tmp/bench_{size}.txt -o /dev/null -n 5000 --max-input {size}'
```

### E. Memory profiling

On Linux:
```bash
/usr/bin/time -v uv run synterr generate -l ru --preset balanced --depparse \
  -i /tmp/bench_10k.txt -o /dev/null 2>&1 | grep "Maximum resident"
```

On Mac:
```bash
/usr/bin/time -l uv run synterr generate -l ru --preset balanced --depparse \
  -i /tmp/bench_10k.txt -o /dev/null 2>&1 | grep "maximum resident"
```

Fill in:

| Config | 500 sents | 2K sents | 10K sents | 50K sents |
|--------|-----------|----------|-----------|-----------|
| stanza GPU depparse | ___ MB | ___ MB | ___ MB | — |
| stanza CPU depparse | | | | — |
| natasha | | | | ___ MB |

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
