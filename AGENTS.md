# synterr
Rule-based synthetic error generator for Russian GEC: corrupts clean text into §-labeled errors (GECToR / seq2seq / minimal-pair benchmark data).

## What this project is
- **Nature**: production. Public pip-installable releases (v1.x = BEA 2026 release), cited, and the planned RozentalBench generator — wrong output becomes wrong training data and wrong benchmark items downstream.
- **NKS realm**: `synterr` (r70, verified 2026-07-12) — every session starts with `nks_orient` here. Realm is near-empty: structure bootstrap pending; the open fix-queue lives as vimarsha #1.
- **Focus holon**: focus: realm root.
- **Stack**: Python 3.11+ / uv; stanza (parses) + pymorphy3 (inflection); ruff + scoped mypy; mkdocs-material site.
- **Production statement**: ships as a PyPI-style package and a public docs site; consumed by GEC researchers for training data and (planned) model benchmarking. Cost of breakage: silently invalid corruptions poison training corpora and benchmark validity — precision beats recall everywhere.

## Persistence rules
State lives in the **repo**, in **synterr-internal** (private repo: journal, specs, annotations), or in **NKS** — nowhere else. Local agent memory, conversation summaries, `/tmp`, machine-local files are **forbidden for project state**.
- **Repo**: code, configs, conventions, code-level gotchas — the artifact itself.
- **synterr-internal**: lab journal (`journal/` — append an entry every work session), research specs, annotation data, anything referencing the copyrighted Rozental raw text.
- **NKS**: design decisions, open questions, plans (once the realm is live).
- **Fetch state; never reconstruct it from memory.**
- Global *user* preferences (language, working style, mascot lore) are agent-scoped and persist separately — this rule is about *project* state.

## Session lifecycle
- **Start of session:** orient — `git log --oneline -15` on both repos, latest `synterr-internal/journal/` entry, NKS realm when connected.
- **Before every write phase:** `git rev-parse --abbrev-ref HEAD` + `git status --short`. Parallel sessions may share this checkout; unexplained files or a changed branch = stop and investigate. Prefer one `git worktree` per session lane.
- **Every push:** update the journal (what + why, not SHAs); update NKS when connected; after a green push re-read your diff for bugs, fragile guards, missing tests — fix in the same branch or state plainly nothing surfaced.
- **After agent fan-outs:** check `git stash list` and `git status` for unmerged entries — prompt constraints are not enforcement.

## Working principles
1. **Think before coding.** Fetch, don't recall; hit the live pipeline before trusting a doc or a memory. State assumptions; push back on false premises.
2. **Simplicity first.** Minimum code; no speculative abstractions.
3. **Surgical changes.** Touch only what the task needs; the linter is authoritative on style.
4. **Goal-driven execution.** Bugs: pin with a failing test before patching. Handler changes: verify end-to-end through `ErrorPipeline` on real sentences (`lenta_sents.txt`), not just unit fixtures.
5. **Precision first.** A handler that skips is fine; one that emits correct-Russian "errors" or mangled labels poisons data. Skip > mislabel, always.

## Commands
| task | command |
|---|---|
| tests (fast) | `uv run pytest -q` |
| tests (+slow stanza) | `uv run pytest -q -m ""` |
| lint / format | `uv run ruff check src tests` / `uv run ruff format src tests` |
| types (scoped) | `uv run mypy` (core + schemas only; see gate note) |
| docs | `uv run mkdocs build --strict` |
| corrupt one sentence | `uv run synterr corrupt -l ru -e <handler[:subtype]> "…"` |
| generate corpus | `uv run synterr generate -l ru --preset rulec -i in.txt -o out.edits` |
| minimal pairs | `uv run synterr minimal-pairs -l ru -i sents.txt -o pairs.jsonl` |
| coverage / inventory | `uv run synterr coverage --lang ru --schema rlc` / `uv run synterr list-errors -l ru` |
Pipe pytest through `tail` only with `set -o pipefail` — a pipe swallows the exit code.

## Project structure
- `src/synterr/core/` — pipeline, protocol, registry (language-agnostic)
- `src/synterr/schemas/` — taxonomies: rlc (35 tags), rozental (8 L0 / 29 L1 / 103 L2 + `l2_applicability` speaker annotation), errant
- `src/synterr/configs/russian/` — presets (weights + subtype_weights); rulec = default distribution
- `src/synterr/languages/russian/` — backends (stanza default), `errors/` handlers, `inflector.py`, `data/` lexicons
- `src/synterr/languages/french/` — 5-handler PoC (fr_sequoia)
- `tools/`, `docs/site/`, `scripts/` — viewer, mkdocs content, join/build utilities
- Handler inventory: `synterr list-errors -l ru` is authoritative (46 handlers / 106 subtypes at bootstrap); per-handler table lives in docs, not here.

## Code conventions
- Handler protocol: `name, subtypes, category, changes_length, can_apply(), apply()`; new handlers register in `errors/__init__.py`, map in `schemas/data/*.yaml`, weight in `configs/russian/rulec.yaml`.
- **Test discipline**: unit (fake-token fixtures) + real-backend integration (`@pytest.mark.slow`); every audit/annotation finding becomes a regression test; full fast suite green before push.
- **Commit style**: imperative summary, describes end-state (never what was scrubbed); explicit paths only — **never `git add -A`** (untracked corpora/secrets in tree); end with the `Co-Authored-By` trailer per user rule.
- **Copyright rule**: Rozental § numbers are facts and fine; the raw text (at `../rozental/data/raw/`) must never be quoted in code, docs, or public commits. Anything referencing the dump lives in synterr-internal.
- **Gotchas** (each has bitten us):
  - Inflection: always `inflect_word(parse, grammemes, original)` — transfers capitalization and е/ё; single capitals titlecase (not ALL-CAPS); full-caps sources must uppercase every produced segment of splits/merges.
  - pymorphy *prediction* parses garbage: gate remainders/candidates with `word_is_known`; the stored parse is UD-disambiguated at the backend — don't re-pick `parse[0]`.
  - stanza UD features lie: Case on OOV proper nouns, participles as VERB+Tense, no Gender on plural adjectives — verify with pymorphy round-trips; pin non-target features in inflect targets.
  - Config binding: subtype weights are enable gates; unlisted subtypes inherit handler `DEFAULT_WEIGHTS` — explicitly zero non-benchmark subtypes in `lorugec.yaml`. Handlers absent from a preset's `weights:` never fire; `enabled_errors` + all-zero weights crashes `random.choices` (open finding).
  - Lexicon entries need normative provenance: "marked variant" ≠ error (gramota-check each pair); loader assertions guard positions.
  - `resources.py` `morpheme_at_char` counts annotation chars (`-`, `j`) — OPEN upstream bug; spelling.py works around it locally, orthographic_spelling's suffix-boundary check currently regresses ~175 compound adjectives (see review findings 2026-07-12).
  - Corpora (`lenta_sents.txt`, pools) and `tools/review/` are gitignored — regenerable; don't track.
  - Stress dict required for vowel_reduction; morpheme data from `unified_dict.json`.
- **Quality gate** (measured 2026-07-12): ruff `E,F,I,N,UP,B,SIM,RUF` (E501/RUF001-Cyrillic ignores are deliberate); mypy scoped to core+schemas — `--strict` there costs 11 errors, full-src costs 114; tightening is a decided follow-up branch, not ambient drift.

## What to update when
- `AGENTS.md` — commands, structure, conventions, gate, or gotchas change.
- `synterr-internal/journal/YYYY-MM.md` — every work session (append-only).
- `CHANGELOG.md` — user-visible changes, under `[Unreleased]` until a tag.
- NKS — every push, once the realm is connected.

## Git workflow
- Direct pushes to `master` with the full fast suite green locally; CI (lint+format+mypy+tests) must stay green — check `gh run list` after push.
- Risky/parallel work: separate branch in its **own worktree**; one branch through to merge.
- **Definition of done**: pushed to `origin/master`, CI green, journal entry written, regression tests cover the change.
- **Never** `--no-verify`, `--force`, `git reset --hard`, or stash pops in shared checkouts without explicit user instruction.
