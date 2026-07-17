# v5 data plan (agreed with Anna, 2026-07-14)

First dataset built on schema v1.1. Fixes v4's three known diseases.
Artifact twin (pretty version): claude.ai artifact "SyntErr v5 — Data Plan".
Freeze deadline: **2026-07-31**. v4 baseline: 39,209 ex, seed 42, 150K pool.

## Why (receipts)

| v4 disease | receipt | v5 cure |
|---|---|---|
| Direction mismatch on 3 comma rules: v4 taught ONLY insert-missing-comma (847×3 examples, 100% learn-insert — verified in qwen_sft_v4.jsonl 2026-07-14), while LORuGEC tests them 51/56 in the delete-wrong-comma direction | 10%→0% (the paper's finding, now data-verified) | bidirectional [insert]/[delete] pairs everywhere |
| Thin rules | 8 / 29 / 70 examples (числительные / фразеологизмы / -инск/-енск) | targeted host mining |
| Duplicated source pool | ~47K dups (~31%) | clean seeded pool rebuild |

Direction-mismatch record (Anna's murk, fully resolved 2026-07-14, all
numbers re-measured on qwen_sft_v4.jsonl):

- **Paper's 3.6:1 REPRODUCED**: comma tokens inserted vs deleted by
  corrections dataset-wide = 8,702 : 2,374 = **3.67:1** ✓ (example-level
  = 2.55:1; comma-named rules only = 1.66:1 — same phenomenon, three cuts).
- **The three suppressed rules**: 847×3 examples, 100% learn-insert;
  LORuGEC tests them 51/56 learn-delete. The sharp end of the skew.
- **Timeline**: v4 generated 2026-03-22 → suppression discovered at eval →
  **fix landed 2026-07-01/02, two nights before the talk** (f5a8355 six
  insert-direction subtypes + 1544f0b gera_bidir preset) → published models
  never saw it. v5 is the first dataset that includes the fix.
- The v4 dist tracked fill-rate (847/847 green), not direction — invisible
  by dashboard design; hence gate #5. Host-starvation of comma_insert
  subtypes (0–11% fill) is a separate, coexisting disease.

Free bonuses already in main: July-12 generator fixes (four punctuation sites
freed, compound-term lexicon, morpheme offsets) + schema v1.1 § correctness.

## Status 2026-07-17: W1–W3 COMPLETE (executing session, log in V5_HANDOFF.md)

- **W1 ✓** `e9625af` — `comma_paired_conj` NP-insert subtype (§87 chains,
  «пары» rule gets its [delete]/[insert] twins). The last suppressed rule is
  now bidirectional. 10 unit tests + 93-example review bundle.
- **W2 ✓** `e4d412c` + `bcac56e` — `comma_to_dash_asyndetic` (§116 insert
  mirror, §117–118 exclusions structural; self-review tightened four leak
  classes, yield 77→41 on 10k lenta, every cut dash-defensible).
  «Тире в бессоюзных» split into direction twins. Suite 1409 green.
- **W3 ✓** `a193896` (+merge `71520d5`) — numeral_declension pool (72,579
  seen → 2,000 pooled), set-phrase lexicon completed vs §87.3 (+~20% pool;
  honest note: frozen phrases are intrinsically rare in edited prose — the
  unlock is the unextracted Subtitles/proza shelf), all 22 pools re-mined
  with per-class provenance.
- **W4** — still open stretch (§169–170), unchanged.
- **«47K duplicates» — MYTH, measured**: nothing near 47K anywhere (worst
  real number: 12,502 scarce∩rublimp input overlap, correctly removed by the
  build). REAL finding: on-disk `mixed_sources_v4.txt` (155,073 lines) does
  not match its own .meta.json (149,999) — 5,074 trailing lines with
  truncated fragments + 414 dups in the head; file predates the script or
  was appended to. ~0.4%, harmless for training, but provenance broken ⇒
  **W5 gains a pre-step: rerun `build_v4_sources.py` (seed 42) so v5 sources
  from a file matching its own metadata.** (v4 file itself untouched — it's
  the paper's historical corpus.)

Remaining before freeze: **W5 only** (pool rebuild pre-step → generate →
provenance → gates), pending the call's size decision.

## Workstreams (state corrected 2026-07-16 — much more was already done)

- **W1 (#48, in flight)** — bidirectional commas. Done: однородные придаточные
  + СПП с общей частью (f5a8355) **plus SIX delete-direction subtypes since
  Jul 2** (1544f0b: comma_homogeneous_conj §86, comma_subj_pred,
  comma_pseudo_parenthetical §99, comma_after_odnako §99.7,
  comma_compound_conj_split §108, comma_x_ne_x §90 + gera_bidir preset).
  Remaining: ONLY the «пары» NP-level insert subtype (§87; verified absent
  2026-07-16 — comma_clause_junction still requires a clausal head).
- **W2 (#49)** — asyndetic dash: delete-direction (`dash_asyndetic`) exists;
  remaining = the insert side (spurious dash into asyndetic junctions).
- **W3 (#50)** — LARGELY DONE since Jun 10 / Jul 2 (the plan's "v4 never
  searched deliberately" was written from the stale March report):
  `data/pools/` = 19 seeded per-rule host pools (seed 42, cap 2000, Taiga×3 +
  RuBLiMP; incl. insk_ensk 480KB, enk_onk, poltora, taki, between_conjunctions,
  indivisible, set_phrase) + `mine_class_pools.py`/`mine_semgrex.py`/
  `build_source_mix.py`. Remaining: numeral_declension host pool (only poltora
  exists; the 8-example rule still needs oblique-case numeral hosts),
  comma_in_set_phrase boost (28KB = thinnest pool), and a verification pass
  over pool freshness + the mixed-pool dedup story (build_v4_sources already
  dedupes via set(); confirm where the 47K figure came from before "fixing").
- **W4 (stretch, non-blocking)** — §169–170 pronoun handlers (honest gaps found
  by the v1.1 walk). NB: night-wave handlers (pronoun_n_form, verb_iterative,
  agr_sv/agr_mn families) already exist + review bundles (d35feac) — the
  generator's rule surface is wider than v4's 59 keys; decide at generation
  time which new keys enter v5.
- **W5 (#51)** — generate (`--balance-directions`, seeded), write
  `V5_DATA_PROVENANCE.md` BEFORE freeze, run gates, freeze.

## Freeze gates (all green or no freeze)

1. Every step seeded + reproducible by one command
2. Provenance doc written pre-freeze
3. Contamination vs LORuGEC test = 0 (python sets + normalize; never comm/sort)
4. ≥200 examples per direction-key (61 keys) or documented shortfall
5. `.dist.json` direction balance eyeballed (3.6:1 never again)
6. `git grep -i 'aleph|алеф'` clean in release artifacts

## Timeline

- **Jul 16/17** — team call: Artem takes Track A ownership (v5 = his dataset)
- **Jul 18–24** — W1+W2 (handlers) ∥ W3 (pool+mining)
- **Jul 25–28** — W5 (generate, provenance, gates)
- **≤ Jul 31** — FREEZE (post-freeze change = v5.1 with new provenance, never in-place)
- **Aug** — Artem: recipe ablations (Track A); experiment #46 (bidirectional
  finetune) = the bridge to GEC Gym P2

## Actors

Anna: two call decisions + gate sign-off (~1h). Artem: dataset owner from the
call; W3 mining review; Aug ablations. Claude: all build labor. gandalf:
generation (stanza, CPU-bound); frodo: Aug finetunes.

## Open for the call

1. **Size**: recommend ~60K (growth goes to new directions + thin rules, not
   to already-fat subtypes; ~1000/direction-key).
2. **Format**: v5 stays pure SFT; GEC Gym episodes come from their own
   generator per the pilot spec — no format mixing in one release.

## Appendix: direction-mismatch matrix (measured 2026-07-14)

Only 14 of 59 v4 rule-keys touch commas, and **every one is one-directional
in training** (8 insert-only, 6 delete-only) — the 3.6:1 is the sum of
fourteen one-way streets. Test-split opposite-share vs published qwen35_4b
scores (zero-shot → synterr-only → synterr→lorugec):

| rule | opp-share (test) | zs → syn → cont |
|---|---:|---|
| пары (однородные) | 100% | 8.3 → **0.0** → 83.3 |
| однородные придаточные | 100% | 10.0 → **0.0** → 50.0 |
| СПП с общей частью | 75% | 8.3 → 8.3 → 8.3 |
| **«как»: 3 — NEW, not in the paper** | **53%** | **66.7 → 53.3 → 86.7** |
| «как»: 1 | 33% | 25.0 → 18.8 → 43.8 |
| стык двух союзов | 33% | 8.3 → 58.3 → 66.7 |
| цельные сочетания | 17% | 22.2 → 44.4 → 77.8 |
| деепричастия после союзов | 17% | 30.8 → 7.7 → 46.2 |
| повторяющиеся союзы | 12% | 22.2 → 11.1 → 22.2 |
| вводные слова | 11% | 57.9 → 52.6 → 47.4 |
| опред., оторванные | 0% | 20.0 → 20.0 → 20.0 |
| опред., при личном мест. | 0% | 20.0 → 0.0 → 10.0 |
| «как»: 2 | 0% | 30.0 → 50.0 → 80.0 |
| фразеологизмы (29 train ex!) | 0% | 0.0 → 69.2 → 53.8 |

**Findings.** (1) «как»:3 is a fourth, *partially* suppressed rule —
−13.4 under synterr-only, full recovery under continuation, predicted by its
53% mismatch. (2) Mismatch-share is a risk factor, not a law: стык союзов
gains despite 33% (aligned majority dominates); деепричастия drop without
mismatch (separate disease — investigate in W1). (3) Alignment beats volume:
фразеологизмы reach 69.2 from 29 examples because the direction matches.
**W1 therefore covers all 14 rules, priority = opp-share × N**, not just the
three named culprits. Caveat: N per rule = 10–23, exact-match is noisy.

This matrix is the empirical motivation for GEC Gym's per-rule curriculum:
direction is a controllable generation knob with measurable per-rule causal
effect.
