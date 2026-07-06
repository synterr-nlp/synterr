# French PoC — Integration Report

*Companion to `FRENCH_DESIGN.md` and `FRENCH_POC_WORKFLOW.md`. Covers the
**integrate** step: wiring the five validated PoC handlers into synterr,
weighting the `poc` preset, extending `errant.yaml`, full regression, and an
end-to-end 1k-sentence generation run. 2026-07-06.*

## 1. What got wired

Five handlers, all built in the earlier scaffold/resources/handlers phases of
this workflow, exposed via a new `synterr.languages.french.errors.get_all_handlers()`
(mirrors the Russian package's shape) and returned from
`FrenchLanguage.get_error_handlers()`:

| Handler | Subtypes | Category | changes_length |
|---|---|---|---|
| `grammatical_homophone` | a_à, et_est, ce_se, on_ont, son_sont | SPELL | False |
| `verb_ending_homophony` | inf_to_participle, participle_to_inf, fut_cond_1sg | SPELL | False |
| `article_contraction` | au_split, aux_split, du_split | MORPH | True |
| `elision_apostrophe` | elision_omit, euphonic_t_drop | SPELL | True |
| `pp_agreement` | etre_strip, avoir_cod_ante_strip | MORPH | False |

`src/synterr/configs/french/poc.yaml`: `weights` set uniform (0.2 each) across
the five — no native-frequency calibration corpus (a RULEC/RLC analog) exists
yet for French, so an even split is the honest default until WiCoPaCo mining
(`FRENCH_DESIGN.md` §7) can calibrate it. `subtype_weights` is populated only
for `grammatical_homophone` (its five pairs have a direct Lexique 3.83
`freqfilms2` source in `homophones.json`); the other four handlers pick
subtypes deterministically from dep-tree classification rather than sampling
a distribution, so they have no `set_subtype_weights` method and no
comparable per-subtype frequency source in their own data files — the block
is left absent there rather than faked. `use_depparse: true` is set in the
preset, but **the CLI's `--depparse` flag unconditionally overrides the
preset value** (`GenerationConfig._from_dict`'s override loop applies
regardless of the caller passing the flag or not, since `cmd_generate`
always forwards its own `depparse` default), so `--depparse` must be passed
explicitly on the command line — silently omitting it would zero out every
wired handler (all five read `head_idx`/`dep_rel`).

`src/synterr/schemas/data/errant.yaml`: added 15 subtype mappings (one per
handler subtype), reusing existing primary tags rather than inventing a
French-only vocabulary — `SPELL` for the homophone/elision swaps,
`VERB:FORM` for the ending-homophony rewrites, `DET`+`M` for the
contraction splits (the corrupted form is missing the required fused
determiner), `PART`+`M` for the euphonic-t drop, `VERB:GEN` for pp_agreement
(the tag was already purpose-built as "verb gender error (past tense)" —
past-participle agreement is exactly that class, extended here to also cover
the number half of the same rule).

One infrastructure fix beyond the four numbered steps was required to make
step 5 runnable at all: `src/synterr/configs/__init__.py`'s
`_normalize_language()`/`get_default_preset()` had no `"fr" → "french"`
mapping (this is design doc `FRENCH_DESIGN.md` §2's listed prerequisite R5).
Without it, `load_preset("fr", "poc")` resolved to a nonexistent
`configs/fr/` directory and raised `FileNotFoundError`. Added the two-line
mapping (not under `core/` or `languages/russian/`, no test depended on the
old behavior).

## 2. Per-handler validity (verify-phase results, supplied)

| Handler | Validity | Repaired? | Bar (≥90%) |
|---|---|---|---|
| grammatical_homophone | 100% | no | pass |
| elision_apostrophe | 100% | no | pass |
| article_contraction | 97.6% | no | pass |
| verb_ending_homophony | 97.4% | no | pass |
| pp_agreement | 96.4% | no | pass |

All five passed the PoC bar on the first verify pass — no repair round was
triggered for any handler (no pre-repair numbers to report; `repaired: false`
across the board).

## 3. Full regression

`uv run pytest -q` (whole suite): **1048 passed, 5 failed** at time of
writing. All 5 failures are **outside this task's scope and not caused by
this integration**:

- 2 are `tests/test_languages/test_french/test_scaffold.py` placeholder
  assertions (`test_get_error_handlers_empty`,
  `test_get_error_distribution_no_weights_yet`) that literally assert *no
  handlers are wired yet* — the scaffold test's own docstring says "Not
  testing any handlers (there are none yet)". Wiring the five handlers (this
  task's explicit step 1) makes these two assertions false by construction.
  Per this task's hard rule ("never modify... any existing test file") they
  were left untouched rather than updated to match the new wired state; this
  is a direct, unavoidable collision between that rule and the wiring
  requirement, flagged here rather than silently worked around.
- 3 are Russian-side failures (`test_integration_real_backend.py` x2,
  `test_languages/test_russian/test_punctuation.py` x1) in files this task
  never touched (`src/synterr/languages/russian/errors/punctuation.py`
  and friends). `git diff` confirms zero edits by this integration to any
  Russian source or test file. File mtimes on those exact files moved
  forward *during this session* (e.g. `punctuation.py` re-saved at
  `14:58:58`, again observed changing between consecutive `pytest -q` runs
  a few minutes apart, with the failing-test count shifting 4→3 in that
  window) — a **concurrent, unrelated process was actively editing the
  Russian punctuation handler in this same checkout while this integration
  ran**. Re-running the isolated regression gate the workflow doc specifies
  (`tests/test_languages/test_french`) is stable at **125/127 passed** (the
  2 known scaffold-placeholder failures above, nothing else).

All 125 non-placeholder French unit tests (determiners/elision/homophony/
pp_agreement/verb_endings + scaffold fixtures) pass. No Russian test that
this integration could plausibly affect (schema loading, config loading,
handler registry) shows any regression attributable to this diff.

## 4. End-to-end run

`data/french_poc/fra_news_30k.txt` (Leipzig `fra_news_2023_30K`), first 1000
lines → `data/french_poc/poc_1k_input.txt` →

```
uv run synterr generate -l fr --preset poc --depparse \
  -i data/french_poc/poc_1k_input.txt -o data/french_poc/poc_1k.jsonl \
  -f jsonl --schema errant --seed 42
```

Wrote 424/1000 sentences with ≥1 corruption (560 corruptions total, ~1.32 per
corrupted sentence; `error_probability: 0.7`, `max_errors_per_sentence: 3`).
**Every wired handler fired at least once.**

| Handler | Sentences hit (/1000) | Corruptions | Subtype breakdown |
|---|---|---|---|
| grammatical_homophone | 212 (21.2%) | 229 | a_à 143, et_est 57, son_sont 17, ce_se 6, on_ont 6 |
| elision_apostrophe | 139 (13.9%) | 139 | elision_omit 139, euphonic_t_drop 0 |
| verb_ending_homophony | 121 (12.1%) | 127 | participle_to_inf 77, inf_to_participle 50, fut_cond_1sg 0 |
| article_contraction | 63 (6.3%) | 63 | du_split 38, au_split 21, aux_split 4 |
| pp_agreement | 2 (0.2%) | 2 | etre_strip 2, avoir_cod_ante_strip 0 |

Three subtypes never fired in this 1k-sentence sample: `fut_cond_1sg`
(1st-person-singular future/conditional homophony is rare in 3rd-person news
prose), `euphonic_t_drop` (needs a `-t-il/-elle/-on` inversion, mostly a
direct-quote/interrogative construction, rare in declarative news), and
`avoir_cod_ante_strip` (needs a fronted direct object — clitic or relative
`que` — before an `avoir`-participle, a comparatively rare construction). All
three are syntactically real and covered by fixture-level unit tests
(`test_verb_endings.py`, `test_elision.py`, `test_pp_agreement.py`); their
absence here is a corpus-register gap, not a handler defect.

### Example diffs (3 per handler where available; format `[-original-]{+corrupted+}`)

**grammatical_homophone**
```
« 2022 aura été une année sans précédent où la BB-Lomé [-a-]{+à+} su traverser dans les meilleures conditions [-et-]{+est+} elle en sort renforcée », a confié son Directeur général, Thierry Feraud.
[-À-]{+A+} 17h, 31000 clients [-d'-]{+de+} Énergie NB sont privés de courant en raison de bris occasionnés par les mauvaises conditions métérologiques.
A 90 ans, faute d'héritier et de famille proche, la doyenne de l'humanité avait vendu sa maison [-à-]{+a+} [-son-]{+sont+} notaire.
```

**verb_ending_homophony**
```
À 28 ans, depuis le 19 janvier, il ne remportera sans doute pas la Primavera à six autres reprises, mais comme pour Merckx, Milan-Sanremo est [-taillée-]{+tailler+} à la mesure de le fils [-d'-]{+de+} Adrie.
«À 71 ans, elle est [-obligée-]{+obliger+} de continuer à travailler car sa pension est trop faible», fulmine-t-elle, détaillant une somme de petits boulots payés [-au-]{+à le+} le lance-pierre.
À Anderlecht, des feux d'artifice ont [-perturbé-]{+perturber+} le duel face à Genk.
```

**article_contraction**
```
À 2877 mètres d'altitude, c'est aussi le lieu idéal pour admirer la chaîne de les Pyrénées et assister [-au-]{+à le+} le lever ou coucher de le soleil.
«À 71 ans, elle est [-obligée-]{+obliger+} de continuer à travailler car sa pension est trop faible», fulmine-t-elle, détaillant une somme de petits boulots payés [-au-]{+à le+} le lance-pierre.
Aaron Appindangoyé était dans l'équipe type [-du-]{+de le+} le championnat gabonais pour la saison 2013/14.
```

**elision_apostrophe**
```
"10000 personnes sur la Grand-Place, on ne [-s'-]{+se+} y attendait pas"
« 24h avant le voyage, certains candidats ont quitté [-l'-]{+le+} intérieur de le pays.
« 4,3 millions de personnes ont besoin [-d'-]{+de+} une aide humanitaire »
```

**pp_agreement** (only 2 corruptions fired in the 1k run — both shown)
```
À Bordeaux, nous sommes [-passés-]{+passé+} de 2 à 7 millions de visiteurs en quelques années grâce à une telle inscription.
Alors qu'ils pensaient quitter définitivement le célèbre jeu de survie après avoir été éliminés par leurs camarades, deux candidats se [-sont-]{+son+} [-vus-]{+vu+} offrir une seconde chance.
```

### A rendering caveat visible in the diffs above

Several diffs above show untouched spans like "de les Pyrénées" or "de le
soleil"/"à le lance-pierre" where the source text actually reads "des
Pyrénées"/"du soleil"/"au lance-pierre" — **not** a second corruption. Stanza's
`fr_sequoia` MWT processor splits *every* `au`/`du`/`des`/etc. contraction
into two syntactic words before any handler runs (documented for `au`/`du`
in `errors/determiners.py`'s own docstring), and `core/pipeline.py` renders
`sentence = [t.text for t in tokens]` joined with spaces — so **any**
contraction word the corpus contains, whether or not `article_contraction`'s
`du`-gate happens to select it, renders pre-split in both the `original` and
`corrupted` JSONL fields. `des` (de+les, an indefinite/partitive plural) is
not in `article_contraction`'s three subtypes at all, yet still shows up
split because the token-level rendering has already lost the fused spelling
upstream of every handler. This affects roughly a quarter of the corpus (265
of 1000 lines contain a standalone "des") and is a **pre-existing fidelity
gap in the scaffold's tokenizer choice + rendering path**, not introduced by
this integration — see §5 below, it is the top phase-1 fix item.

## 5. Failed handlers

**None.** All five handlers in this PoC's roster passed the ≥90% validity
bar on the first verify pass (§2) — there was no repair round and nothing to
exclude. This is not the same as saying French PoC coverage is complete:
`FRENCH_DESIGN.md` §5.2 lists 14 further phase-1/2/3 handlers (`adj_gender`,
`adj_number`, `noun_number`, `verb_person_number`, `noun_gender`,
`mood_subjunctive`, `accent_spelling`, `double_consonant`, `keyboard`,
`paronym`, `pleonasm`, `preposition`, `clitic_placement`,
`pp_agreement_pronominal`) plus the whole PUNCT family — none of those were
attempted in this PoC round (most are gated on the R1 inflection-engine
refactor), so there is nothing to report as a validity failure for them.

## 6. What phase 1 must fix

1. **MWT-rendering fidelity (highest priority).** Any French contraction
   word not specially reassembled (`des`, and likely `auquel`/`duquel`/
   `desquels`/other MWT-tokenized forms `fr_sequoia` splits) renders as two
   words in *both* `original` and `corrupted` JSONL fields even when no
   handler touches it — corrupting the notion of "clean reference text" for
   ~26% of a news corpus sample. Needs either a rendering-time rejoin pass
   for untouched MWT pairs, or accepting `des`-class contractions into
   `article_contraction`'s scope (with its own partitive-vs-genitive gate,
   mirroring the existing `du` gate) so at least the labeled corruption
   accounts for what changed.
2. **`--depparse` silently overrides the preset.** `poc.yaml` declares
   `use_depparse: true`, but `GenerationConfig._from_dict`'s unconditional
   override means every wired handler goes inert (zero corruptions, no
   error, no warning) if a caller runs `synterr generate -l fr --preset poc`
   without also passing `--depparse`. Worth a CLI-level fix (warn or default
   `--depparse` from the preset when the flag isn't explicitly given) — this
   is core/ behavior shared with Russian, out of this integration's scope to
   change, but a real footgun for anyone following the `rulec`-style example
   in the CLI's own `--help` text.
3. **Corpus-register gaps.** `fut_cond_1sg`, `euphonic_t_drop`, and
   `avoir_cod_ante_strip` never fired in 1k news sentences — all three need
   either a larger sample or a register mix (dialogue/forum text) to get
   calibration-worthy hit rates before any weighting decision.
4. **No empirical subtype calibration beyond one handler.** Only
   `grammatical_homophone`'s subtype_weights are populated (from
   Lexique 3.83 frequencies), and none of the five handlers implements
   `set_subtype_weights` yet, so even that block is inert. WiCoPaCo mining
   (`FRENCH_DESIGN.md` §7) is the intended empirical-frequency source for a
   real preset, same trajectory the RLC extraction took for Russian.
5. **Human validity pass still owed.** The verify-phase numbers in §2 are an
   automated (LLM-judged) 40-sample check per the workflow doc's own
   acceptance bar, not an Artem-style human annotation pass — recommended
   before any of this data is used for real training, per
   `FRENCH_POC_WORKFLOW.md`'s own guardrail note.
6. **R1 refactor still deferred.** No French inflection engine exists
   (`token.extra` stays `{}`), so the phase-1 handler roster items that need
   paradigm generation (`adj_gender`, `noun_gender`, `noun_number`, mood
   swaps) remain blocked until Lefff/verbecc integration lands.
