# French PoC — Sonnet 5 Agent Workflow

*Companion to `FRENCH_DESIGN.md`. Drafted 2026-07-06. The runnable script lives at
`.claude/workflows/french-poc.js` — trigger with "run the french-poc workflow".*

## Goal

A working `--lang fr` end-to-end path in synterr: five French handlers, a stanza
`fr_sequoia` backend, a PoC preset, tests, and a judged validity report — implemented by
Sonnet 5 agents, without touching `core/` or `languages/russian/`.

## Scope trick: inflection-free handlers only

The full French plan is gated on the R1 refactor (`pymorphy_parse` → `morph_parse`
protocol) and a Lefff/verbecc inflection engine. The PoC dodges both by picking handlers
whose corruptions are **string rewrites gated by UD features/deprels** — no paradigm
generation anywhere:

| # | Handler | PoC subtypes | Corruption mechanic | Gate |
|---|---------|--------------|--------------------|------|
| 1 | `grammatical_homophone` | a_à, et_est, ce_se, on_ont, son_sont | token swap | POS/lemma/deprel (e.g. `a` = AUX lemma *avoir* → «à»; `se` = PRON expl on VERB → «ce») |
| 2 | `verb_ending_homophony` | inf_to_participle (manger→mangé), participle_to_inf (mangé→manger), fut_cond_1sg (-ai↔-ais) | ending rewrite on 1st-group verbs | VerbForm=Inf slot after modal/ADP; VerbForm=Part after aux; Tense=Fut/Mood=Cnd + Person=1 |
| 3 | `article_contraction` | au→«à le», aux→«à les», du→«de le» (nmod-gated only) | token split (changes_length=True) | ADP+DET fused token; `du` only when unambiguously de+le (nmod of NOUN with definite ref), never partitive |
| 4 | `elision_apostrophe` | elision_omit (l'arbre→«le arbre», qu'il→«que il»), euphonic_t_drop (aime-t-il→«aime il») | apostrophe/hyphen unsplice | elided clitic + vowel-initial next token; -t- between vowel-final verb and il/elle/on |
| 5 | `pp_agreement` | etre_strip (elle est partie→parti), avoir_cod_anteposé_strip (les pommes qu'il a mangées→mangé) | strip final -e(s)/-s from participle | aux lemma + nsubj gender/number (être) or linearly-preceding obj (avoir); **regular -é/-i/-u participles only** |

Stripping agreement (#5) needs no generator — adding it back would. Restoring `au → à le`
is concatenation, not inflection. This is why these five and not, say, `adj_gender`.

Everything is **additive**: new `languages/french/` package, new data/config/test files,
plus exactly one edit to a shared file (`pyproject.toml` entry point:
`french = "synterr.languages.french:FrenchLanguage"`). The French stanza backend leaves
`token.extra` empty — none of the five handlers reads a morph parse, so R1 stays deferred.

## Sources

**Rule sources (what the handlers encode):**
- `FRENCH_DESIGN.md` §5.2 rows for the five handlers — each agent gets its row verbatim.
- **BDL article citations** (free, Québec gov.) as the normative backing per subtype;
  1990-rectifications where relevant. No copyrighted grammar text is needed for these
  five — the PoC is copyright-clean, unlike the Rozental situation.
- **Confusion sets from local Lexique 3.83**: `~/Projects/vibes/dico/data/Lexique383.tsv`
  (`phon` grouping → homophone sets; `infover` → verb-form features; film/book
  frequencies → subtype weights). Derived, not hand-typed.

**Clean text source (the corpus to corrupt — the `lenta_50k.txt` analog):**
- Primary: **Leipzig Corpora Collection, `fra_news_2023_30K`**
  (`downloads.wortschatz-leipzig.de/corpora/fra_news_2023_30K.tar.gz`) — shuffled
  sentence-per-line news, same shape as lenta; research-friendly terms (CC BY).
- Alternates: WMT News Crawl fr (larger), Europarl fr (formal register), French Wikipedia
  sample (matches Sequoia's training domain). For the PoC, 30k news sentences suffice;
  the corpus choice gets revisited at phase 1 proper (spec §9.3).

**Test sentences:** hand-authored fixture pack per handler (agents write these, the
verify phase catches bad ones) + sampled corpus sentences for the e2e run.

## Workflow structure

```
Scaffold (1 agent) ──► Resources (2 parallel) ──► Handlers (pipeline ×5) ──► Integrate (1)
                                                    implement → verify → repair?
```

1. **Scaffold** — `languages/french/` skeleton (`FrenchLanguage`, `backends/stanza_fr.py`
   on `fr_sequoia`, empty `errors/`), pyproject entry point + editable reinstall,
   `configs/french/poc.yaml`, `tests/test_languages/test_french/conftest.py` with French
   `AnalyzedToken` fixtures, corpus download, stanza model download, smoke parse of 5
   sentences. Runs first, alone — everything depends on it.
2. **Resources** (parallel, both read-only outside `src/synterr/data/french/`):
   - *lexique-miner*: derive `homophones.json` (the 5 confusion sets + frequency weights)
     and `verb_ending_slots.json` from the dico TSV; write the extraction as
     `scripts/build_french_homophones.py` so it's reproducible.
   - *tables-curator*: `contractions.json`, `elision.json`, `h_aspire.json` (~100 common
     h-aspiré words), euphonic-t patterns; each with a BDL citation field.
3. **Handlers** (pipeline over the 5 rows; items flow independently — handler 1 can be in
   verify while handler 4 is still implementing):
   - *implement*: one agent per handler writes `errors/<name>.py` + its test module,
     iterates until its own pytest file is green. Owns ONLY those two files.
   - *verify*: a **different** agent corrupts 40 fixture/corpus sentences with the new
     handler and judges each output: (a) is the corrupted sentence actually wrong in
     French? (b) is the error the one the label claims? (c) could the output be read as
     accidentally correct? Returns validity % + concrete failures. This is the Artem
     validity check (98.4% Russian baseline), automated; PoC bar: **≥90%**.
   - *repair*: fires only if validity < 90% — one round, gets the failure list, re-runs
     verify with fresh samples.
4. **Integrate** — wire `get_error_handlers()`, weights in `poc.yaml`, `errant.yaml`
   mappings for the new subtypes; run the FULL pytest suite (Russian must stay green);
   `synterr generate -l fr --preset poc` over 1k corpus sentences → JSONL + diff sample;
   write `docs/research/FRENCH_POC_REPORT.md` with per-handler validity, hit rates, and
   open problems.

## Guardrails (encoded in every agent prompt)

- Never modify `src/synterr/core/`, `src/synterr/languages/russian/`, or any existing
  test. `git status` before finishing; revert anything out of scope.
- Handler agents own exactly two files (their module + their test module); wiring is the
  integrator's job — prevents parallel edits to `errors/__init__.py`.
- All French text produced by generation must come from corrupting corpus/fixture
  sentences, never free-composed by the model into training data.
- `uv run pytest tests/test_core tests/test_languages/test_russian` is the regression
  gate at scaffold time and integrate time.

## Acceptance criteria

1. Russian suite green, untouched (686 tests).
2. French unit tests green (expect ~60–100 new tests).
3. Judged validity ≥90% per handler on 40 samples (post-repair).
4. E2e run on 1k sentences produces ≥1 corruption per handler and valid JSONL/GECToR/diff
   output through the existing formatters.

## Budget & runtime

~14 Sonnet 5 agents (1 scaffold + 2 resources + 5 implement + 5–7 verify/repair + 1
integrate). Estimate 500k–900k tokens, 30–60 min wall-clock (handlers pipeline in
parallel; stanza model download dominates scaffold).

## Known PoC cut corners (deliberate, revisit at phase 1)

- `du` contraction limited to unambiguous nmod contexts (partitive `du` excluded).
- pp_agreement only *strips* agreement (no wrong-direction *addition* — that needs the
  inflection engine) and only regular participles.
- No confusion-matrix weighting beyond Lexique frequencies (WiCoPaCo mining is phase 3).
- `fut_cond_1sg` overlaps conceptually with mood handlers — tagged SPELL here per Catach
  (logogrammique), revisit taxonomy at phase 1.
- Verify agents judge French acceptability themselves — good enough for a PoC bar, but a
  human validity pass (Artem-style) is still required before any generated data is used.
