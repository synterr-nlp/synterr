# Changelog

All notable changes to synterr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.1] — 2026-05-14

Documentation cleanup pass.

## [1.0.0] — 2026-05-01

BEA 2026 release.

### Added

- **Government errors are now arc-aware.** `NounCaseHandler` only fires on
  governed dependents (`obl`, `nmod`, `iobj`, `obj`). True government errors
  rather than blanket case corruption.
- **v4 reproducibility pack**: `data/V4_DATA_PROVENANCE.md` pins generation
  commit `898814d`, `data/v4_checksums.txt` records SHA256 for all v4
  artifacts, `scripts/verify_v4.py` checks them.
- **CLI**: `synterr corrupt` accepts `--depparse` for dep-aware error types.
- **`docs/research/LORUGEC_COVERAGE.md`** — verified LoRuGEC rule coverage
  map (36/48 FULL, 12/48 PARTIAL, 0 NONE).
- **Lint/type CI**: ruff at 88-char line length plus mypy on
  `src/synterr/core` and `src/synterr/schemas`.

### Fixed

- `LanguageModule.get_analyzer` Protocol signature now declares the
  `backend` parameter that the Russian implementation already accepted.

## [0.3.4] — 2026-03-07

### Added
- Wired Rozental L2 schema into generation: 100 fine-grained tags loaded;
  JSONL output includes `schema_tag` (L1) + `schema_l2_tag` (L2).
- Unified morpheme + stress dictionary (115k entries, Zaliznyak primary +
  russtress fallback, Tikhonov primary + Morphberta-K fallback).
- Morpheme-position-aware spelling handlers (skip root-internal patterns).

### Fixed
- 11 critical handler bugs surfaced by morpheme-dict + word-validation audit.
- Subtype extraction for multi-prefix handler names
  (`orthographic_spelling_*`, `function_spelling_*`).

## [0.3.3] — 2026-03-06

### Added
- `CommaInsertHandler` — extra commas before *как*, in set phrases,
  between conjunctions.

## [0.3.2] — 2026-03-06

### Added
- `OrthographicSpellingHandler` — 9 subtypes covering пре/при, ы/и after
  prefixes, suffixes, participles, vowels after ц / sibilants.

## [0.3.1] — 2026-03-06

### Added
- `FunctionSpellingHandler` — не/ни attachment, conjunction split/merge,
  -таки hyphen.

## [0.3.0] — 2026-03-05

### Added
- Confusion-matrix-driven grammeme substitution. Empirical matrices from
  RLC (N=2,760 case, 917 gender, 942 number) replace uniform random.
- Dep-tree agreement: adjective handlers traverse `amod` to head noun;
  `VerbPersonNumberHandler` finds `nsubj` for reference number.

## [0.2.0] — 2026-03-04

### Added
- Lexical handlers: paronym, preposition, conjunction.
- Structural handlers: `WordOmissionHandler`, `WordInsertionHandler`.
- Punctuation handlers: `CommaDeleteHandler` (5 subtypes),
  `CommaPairDeleteHandler` (5 subtypes), `DashDeleteHandler` (2 subtypes).
- Rozental schema (8 L0 / 29 L1 / 99 L2).
- Dep-tree-driven punctuation classifier.

## [0.1.2] — 2026-01-26

### Added
- Subtype filtering on the CLI (`-e spelling:vowel_reduction`).
- Backend benchmarks, performance numbers in README.
- Documentation organization under `docs/`.

## [0.1.1] — 2026-01-24

### Fixed
- Critical bugs in early error generation pipeline.

## [0.1.0] — 2026-01-24

### Added
- Pluggable linguistic schema architecture (RLC, ERRANT).
- Tagged corruption API: `apply_error()` and `synterr corrupt` CLI.
- Capitalization preserved during morphological inflection.

## [0.0.1-alpha] — 2026-01-21

Initial release. Russian morphological + spelling errors. RLC schema.
Configurable error distributions. Pluggable NLP backends
(stanza, natasha, spacy).
