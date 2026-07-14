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

## Workstreams

- **W1 (#48, in flight)** — finish bidirectional commas. Done: однородные
  придаточные + СПП с общей частью (f5a8355). Remaining: «пары» rule needs an
  NP-level insert subtype (comma_clause_junction requires clausal head; «и день
  и ночь» doesn't trigger). §87 read during the schema walk — incl. the §114
  цельные-выражения exceptions; ready to implement.
- **W2 (#49)** — asyndetic clause-clause dash (§116–118, mainly §118), both
  directions.
- **W3 (#50)** — pool rebuild with dedup (seeded) + host mining for the three
  thin rules (Taiga 2.8M + RuBLiMP pool 741K + wiki 200K have the hosts; v4
  never searched deliberately).
- **W4 (stretch, non-blocking)** — §169–170 pronoun handlers (honest gaps found
  by the v1.1 walk). Take only if W1–W3 finish early; else v6.
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
