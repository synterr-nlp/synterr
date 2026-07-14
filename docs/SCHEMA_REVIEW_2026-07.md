# Schema tag-by-tag review — July 2026

*The deferred 98-vs-100(→actually 103) reconciliation. Live document: decisions
get recorded here as Anna rules on them; the merged yaml ships to BOTH repos
at the end, then the LORuGEC join and coverage tables get regenerated.*

**Framing correction (2026-07-11):** "clean vs stale" was wrong. The two yamls
DIVERGED: `rozental/data/rozental_schema.yaml` got the structural 98-tag
cleanup; `synterr/src/synterr/schemas/data/rozental.yaml` (103 tags) kept
receiving content improvements (May semantics fixes: descriptions,
applicability) + 5 structural additions. This is a **merge**, not an overwrite.

**Audit facts (programmatic, 2026-07-11):**
- Counts: rozental 8/29/98 · synterr 8/29/103
- 98-side integrity: 212/213 §§ covered (gap: §172), 2 double-claimed §§
  (§153, §154), 4 §-less tags, no bad parents, no prefix/L0 mismatches
- Ground truth for adjudication: `rozental/data/toc.csv` (693 § titles from
  rosental-book.ru)

## Anomaly clusters & decisions

| # | Cluster | Status | Decision |
|---|---|---|---|
| A | `pu_dash_apposition` broken in the 98: claims §80, but TOC §80 = «Тире в неполном предложении»; appositions = §93. Synterr copy (§93) self-consistent. Same bug suspected in `RULE_TO_PARAS` («Тире при приложении» → [80]) and therefore in the join. | **ACCEPTED 2026-07-14** | Adopt synterr 4-tag `pu_dash`: apposition→§93 (documented cross-family share with the обособление family), ellipsis→§80. Fix `RULE_TO_PARAS` «Тире при приложении» [80]→[93]; regenerate join. Count 98→99 = public "schema v1.1", never silent. |
| B | §39 (adj endings) vs §40 (adj suffixes): the 98 merges into `sp_adj_endings §39–40`; synterr splits (+`sp_adj_suffixes`). Split = faithful to Rozental; merge = preserves published 98. | **ACCEPTED 2026-07-14** | Adopt the split: `sp_adj_endings §39` + `sp_adj_suffixes §40`. Count → 100. |
| C | §153/§154 double-claimed by `mo_noun_case_other` + `mo_noun_num_{nom,gen}_pl`. TOC: both are number-flavored (nom.pl / gen.pl endings). Proposal: give to num tags, narrow case_other. | **ACCEPTED 2026-07-14** | §153→`mo_noun_num_nom_pl`, §154→`mo_noun_num_gen_pl` exclusively; `mo_noun_case_other` narrows to §151, description "Accusative animate/inanimate forms". No count change. |
| D | Verb tangle: §172 L2-gap (aspect children §-less); `mo_verb_tense` claims §172 but TOC §172 = aspect variants; `mo_verb_form` claims §171 which is person-forms. Proposal: form→§173–175, person_num→§171, aspect children→§172, tense→§-less learner-like. | **ACCEPTED 2026-07-14** | `mo_verb_tense`→§-less (learner; no Rozental §); `mo_verb_form`→§173–175 only; `mo_verb_person_num` sole owner of §171; aspect family unchanged. "Gap §172" was a parser artifact: coverage script must credit `§172.1`→§172 (endgame). |
| E | 5 synterr-only tags: `ag_mn_agreement`, `ag_sv_agreement` (coarse duplicates → likely kill), `pu_clause_indivisible` (double-claims §87/§114 → likely kill, check §114 ownership), `pu_dash_ellipsis` (walk with A), `sp_adj_suffixes` (=B). | **ACCEPTED 2026-07-14** (kill-proposals REVERSED on evidence) | Keep all 5. ag_* pair legitimized by 2026-07-10 rework (learner heartland, RLC-driven, frame-paras). `pu_clause_indivisible` = sole owner of §114 (title match); `pu_clause_comparative` narrows §114–115→§115; §87/§90 = documented cross-refs, not claims. Final count **103**. |
| F | Content diffs where synterr is better: `mo_pronoun_forms` (н-augment description), `mo_verb_asp_iterative` (hypercorrection examples), + applicability none→partial on both. Adopt synterr content per-tag. | **ACCEPTED 2026-07-14** (+ new findings F2/F3) | F1: adopt synterr `mo_verb_asp_iterative`. F2: `mo_pronoun_forms` = synterr description + paras **§167** (н-augment verified there); §169–170 become documented gaps (no handler; v5 mining candidates). F3 (found in walk): `mo_pronoun_svoy` §167→**§168.2**, `mo_pronoun_sebya` §168→**§168.1** (both yamls had the shift). Merge base = synterr live yaml. |
| G | Confirm intended: §-less-by-design `lx_word_missing/extra` (learner, per schema design decision 2026-06-03 ✓); atomic L1s `mo_verb_tense`, `mo_verb_person_num` (0 children). | **CONFIRMED 2026-07-14** | All intended. `mo_verb_tense` now also §-less per D. |
| H | **Single source of truth (Anna, 2026-07-14): the rozental-repo copy is retired.** Two copies caused the divergence. | **DECIDED 2026-07-14** | Schema lives ONLY in `synterr/src/synterr/schemas/data/rozental.yaml` (tests + git enforce it). `rozental/data/rozental_schema.yaml` becomes a symlink into synterr (all ~10 pipeline scripts keep working; divergence physically impossible). Accepted trade-off: symlink dangles without the sibling checkout. |

## Walk order

pu_dash (A,E) → sp_pos/sp_affix (B) → mo_noun_* (C) → verb families (D) →
AGR + pu_clause (E) → content-diff tags (F) → fast TOC sweep of quiet families.

## Walk log

*(appended as we go — tag, TOC check, ruling)*

- **2026-07-14 · Cluster A · `pu_dash` family — RULED (Anna: accepted).**
  Evidence: TOC §80 = «Тире в неполном предложении», §93 = «Обособленные
  приложения» (rosental-book.ru toc, 693 titles; verified again today against
  the local master scrape). All 22 LORuGEC «Тире при приложении» items are
  appositions ⇒ the 98's `pu_dash_apposition §80` is a chimera; synterr's
  4-tag `pu_dash` (apposition→§93, ellipsis→§80) is correct. §93 becomes a
  documented cross-family share (dash tag pointing into the обособление
  paragraph). Downstream: `RULE_TO_PARAS` [80]→[93] + join regen (endgame).
  Public count 98→99, announced as "schema v1.1".

- **2026-07-14 · Cluster B · `sp_adj_endings` split — RULED (Anna: accepted).**
  Evidence: §39 = 2 subrules (lexical ending quirks: загородный/иногородний,
  бескрайний/бескрайный); §40 = 14 subrules incl. н/нн (40.10) and
  -инский/-енский (40.11) — verified in the local master scrape. Different
  phenomena (inflectional endings vs derivational suffix spelling); the 98's
  merged description ("endings and suffixes (н/нн)") admits the lump. The
  generator already emits `sp_adj_suffixes` (handler table). Ruling: adopt
  synterr's split — `sp_adj_endings §39`, `sp_adj_suffixes §40`. Count → 100.

- **2026-07-14 · Cluster C · §153/§154 double-claim — RULED (Anna: accepted).**
  Evidence: §151 = «Формы винительного падежа одушевл./неодушевл.» (case);
  §153 = «Окончания им. падежа мн. числа -ы(-и)–-а(-я)»; §154 = «Окончания
  род. падежа мн. числа» — the num tags' descriptions are literally the §
  titles. Bug predates the yaml divergence (identical both sides). Ruling:
  §153/§154 owned exclusively by `mo_noun_num_{nom,gen}_pl`;
  `mo_noun_case_other` narrows to §151 with description "Accusative
  animate/inanimate forms". Handlers unaffected (paras = metadata);
  coverage/cross-ref tables regenerate at endgame. Integrity property
  restored: every § has exactly one owner.

- **2026-07-14 · Cluster D · verb tangle — RULED (Anna: accepted).**
  Evidence: §171 = «Образование некоторых личных форм» (15 subrules, defective
  /variant personal forms — победить-1sg, умерщвлю, выздоровею) = person_num's
  exact job; §172 = «Варианты видовых форм» (aspect, NOT tense); §173/174/175
  = reflexive/participle/gerund = mo_verb_form's children exactly. Bugs
  identical in both yamls (predate divergence). Ruling: `mo_verb_tense` §-less
  with learner l2_note; `mo_verb_form` → §173–175; `mo_verb_person_num` sole
  §171 owner; aspect family untouched. Audit's "coverage gap §172" was a
  tooling artifact — parser doesn't credit `§172.1` subpara refs; fix the
  coverage script at endgame (phantom 212/213 → true 213/213).

- **2026-07-14 · Clusters E, F, G + decision H — RULED (Anna: accepted).**
  E: audit kill-proposals REVERSED on evidence — ag_* pair legitimized by the
  2026-07-10 learner-heartland rework; `pu_clause_indivisible` owns §114 (its
  literal title «Цельные по смыслу выражения»); the over-claimer was
  `pu_clause_comparative` (§114–115→§115); §87/§90 = cross-refs. F: synterr
  content adopted; NEW findings in the pronoun family — н-augment verified in
  §167 (`mo_pronoun_forms` §169–170→§167; §169–170 = honest gaps, v5 mining
  candidates), `mo_pronoun_svoy` §167→§168.2, `mo_pronoun_sebya` §168→§168.1
  (себя/свой subpara split verified). G: §-less learner tags + atomic L1s
  confirmed intended. H (Anna): retire the rozental-repo copy — schema lives
  only in synterr; symlink for the pipeline scripts. Final count **103**
  (98 + 5, each with a receipt), honest coverage 211/213.

- **2026-07-14 · TOC sweep findings S1–S5 — RULED (Anna: all accepted).**
  S1: §49 "???" = toc.csv scrape gap (book has «Употребление буквы ь в
  глагольных формах»); schema untouched. Addendum (viewer build): §33
  (пре-/при-) has an empty rule_text in master.csv — second known scrape
  lacuna; both marked honestly in the viewer panel. S2: `mo_verb_personal` (L2, §171)
  reparented mo_verb_form→`mo_verb_person_num` (D holds: form = §173–175;
  G amended: person_num has 1 child). S3: 正名 — `mo_numeral_oba` renamed
  `mo_numeral_compound` (content/§166 = compound-word numerals; оба lives in
  §164 under cardinal; no handler emits it). S4: ag_mn §§ un-swapped per
  handler code: `ag_mn_apposition` §195–196→§195–197 (toponym handler = §197);
  `ag_mn_compound_term` §197→§148 primary (вагон-ресторан = склонение
  сложносоставных слов) + cross-refs §185.5, §192. S5: `mo_noun_gender_common`
  §148–149-under-gender quirk LOGGED, deliberately untouched in v1.1 (cascades;
  candidate for v1.2).

## Endgame checklist (rewritten per cluster H — single source)

- [x] Structural edits applied to synterr yaml (2026-07-14): C, D, E2, F2, F3,
      S2 (verb_personal reparented), S3 (mo_numeral_oba→mo_numeral_compound),
      S4 (ag_mn un-swap) + pronoun description/note rotation fixed + svoy
      handler docstring §167→§168.2
- [x] `RULE_TO_PARAS` «Тире при приложении» [80]→[93] fixed at source
      (rozental/scripts/build_lorugec_evidence.py) + re-vendored to synterr
- [x] rozental-repo copy retired: symlink live (103 tags visible through old
      path); 98-tag original frozen at rozental_schema_v1.0_98tags_frozen.yaml;
      README + CLAUDE.md updated (99→103, copy→symlink)
- [x] Regenerated: LORuGEC join («Тире при приложении» now §93 →
      pu_comma_isolation; pu_dash_apposition), L2 cross-reference
      (cross_reference_l2.{csv,xlsx}), per-paragraph table (213/213 §§ mapped
      at family level; L2-specific gaps §169–170 documented). Fixed two
      pre-existing breaks: both rozental scripts still read the pre-fb98cd8
      cross_reference.csv path → now cross_reference_l1.csv
- [x] Subpara crediting verified already-correct in parse_para_range
      (172.1→172, frame-prose, ranges) — the phantom gap came from the audit's
      own parser, not the pipeline
- [x] synterr test suite green: 1371 passed (2026-07-14)
- [x] Join script canon updated: CANONICAL_L2_COUNT 98→103 (v1.1)
- [x] Fast TOC sweep done (134 rows incl. L1s; findings S1–S5 ruled)
- [ ] Public story: "schema v1.1" landing-page note (98→103, each addition
      receipted) — pending next site refresh
- [x] Schema Viewer shipped (a391e82): `scripts/build_schema_viewer.py` →
      public `docs/schema_viewer.html` (yaml only) + private build with full
      book text (outside the repo, never committed). yaml `version` → "1.1".
- [x] Identity hygiene (2026-07-14): review-doc attribution uses the official
      name; personal username/name removed from public docs+scripts (1f85009).

**STATUS: WALK + ENDGAME COMPLETE 2026-07-14.** Remaining: landing-page v1.1
note at next site refresh; commits are local — push is the owner's call.
