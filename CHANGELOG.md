# Changelog

All notable changes to synterr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **21 new handlers / 22 new subtypes since 1.0.1** — now 46 handlers /
  106 subtypes, 68/101 Rozental L2 tags generation-reachable:
  - Subject–verb agreement family (§183–190): collective, counting,
    approximate, compound (кто/comitative/acronym), coordinated — dep-arc
    gated with word-order and value-class guards.
  - Modifier–noun agreement (§193–197): toponym appositions, hyphenated
    compounds, два/три/четыре adjective-form crossover — case detection via
    pymorphy inflection round-trips (stanza Case features are unreliable on
    OOV proper nouns).
  - Noun form variants: partitive genitive §150, instrumental plural §155,
    nonstandard genitive plural §154; negation genitive §201 (Acc↔Gen under
    negated verbs, dep-arc).
  - Pronouns: свой↔personal possessive §167, себя↔personal §168,
    н-augment after prepositions §169–170.
  - Verb/adjective variants: о/а iterative suffix §172.2, possessive-adj
    oblique forms §162, short-form -ен/-енен §160.
  - Spelling roots: alternating roots §3, unchecked vowels §2 (curated
    lexicons with homograph denylists), root vowels after sibilants/ц §5,
    -ем/-им adjective endings; пол- compounds gated by morpheme boundaries.
  - Punctuation: dash_ellipsis subtype (§80, тире в неполном предложении);
    six insert-direction comma subtypes + `gera_bidir` preset closing the
    delete:insert asymmetry; sentence-initial restriction for compound-
    conjunction splits (§108).
- **`synterr minimal-pairs`** — phenomenon-labeled contrast-pair emitter:
  one corruption per record with L1/L2 tags, Rozental paragraphs, and
  native/learner applicability.
- **`synterr survey` / `synterr mine-pools`** — per-subtype fire-rate
  measurement and lexicon-derived candidate-pool mining.
- **French PoC**: 5 inflection-free handlers on stanza fr_sequoia.
- Weight-invariant test suite; annotation-derived regression tests
  (~2,700-item native-speaker verification pass: 98.4% corruption validity,
  91.6% intended-type precision; all identified failure classes fixed).

### Fixed

- Adjective agreement corruption pins case/animacy and takes singular
  gender from the amod head noun; pronominal adjectives, participles, and
  bare predicatives are skipped.
- verb_tense fires on finite forms only (participle voice preserved).
- Collocation swaps transfer the full grammatical form (voice, participle
  class, case) and skip when inflection fails.
- Punctuation subtype classifiers reworked on dep-tree evidence: finite
  relative clauses route to subordinate; pair deletion always removes
  exactly two commas; ranges, direct speech, and authorial dashes are
  skipped; speech-verb attributions are parentheticals.
- Inflection preserves source е/ё spelling and single-capital titlecasing.
- CLI/preset config binding: None-valued CLI defaults no longer clobber
  explicit YAML values (`--depparse` is tri-state).

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
- **`docs/research/LORUGEC_COVERAGE.md`** — LoRuGEC rule handler-mapping
  map (36/48 mapped FULL). NOTE: this is a handler-claim map, not a
  verified-works map; see the doc's Known-broken section.
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
