# French Support for Synterr — Design Spec

*Drafted 2026-07-06 from a four-track research pass (codebase portability map, French GEC
data landscape, French NLP tooling, French error taxonomy). Status: **proposal, not scheduled**.*

## 1. Why French

- **French is absent from the modern multilingual GEC landscape.** MultiGEC-2025 covers 12
  languages (incl. Russian) — no French. OmniGEC (silver, 11 languages) — no French. No
  ERRANT port for French exists (the 2025 multilingual ERRANT reimplementation covers
  en/de/cs/ko/zh). This is a citable gap, not an inference.
- **Prior French synthetic-error work is shallow.** The only found precedent
  (InstaCorrect / `maximedb/artificial_errors_generation`, ~13M sentences) is regex
  substitution (`-er`→`-é`) with no parse awareness. Nothing dep-tree-grounded or
  confusion-weighted exists for French — synterr's exact niche.
- **French error structure is a good fit for synterr's approach.** The flagship French error
  classes (grammatical homophony, past-participle agreement) are precisely the kind that
  need POS/lemma/dep-tree gating to corrupt *correctly* — regex can't do them, synterr can.
- **Architecture is ready.** `core/` has no Russian leaks; languages register via entry
  points (`pyproject.toml` `[project.entry-points."synterr.languages"]`,
  `core/registry.py:26-48`). A `languages/french/` package is additive.

## 2. Prerequisite core refactors (language-neutral, do first)

These benefit Russian too and should land before any French code:

| # | Change | Where | Why |
|---|--------|-------|-----|
| R1 | Rename `token.extra["pymorphy_parse"]` → `extra["morph_parse"]` behind a minimal `MorphParse` protocol (`.inflect(features) -> str\|None`, `.tag` accessors) | all 3 backends (`stanza_backend.py:66-72,145-155` + natasha/spacy), `inflector.py`, every morph/lexical handler | The single load-bearing leak: all backends bake pymorphy3 into token construction under a pymorphy-named key. Without this, French handlers fork the token contract. |
| R2 | Fix `discovery.py:66` hardcoded `backend="stanza"` → respect the lang module's default | `discovery.py` | Silent wrong behavior for any non-stanza-default language |
| R3 | Generalize `cmd_list_backends` (`cli.py:200-217`, `if lang == "ru"` branch) → `LanguageModule.list_backends()` protocol method | `cli.py`, `core/protocol.py` | Only CLI command that hard-branches on language |
| R4 | Generalize `diagnostics.py:104-110` `_is_known_russian_word` (pymorphy-only) → per-language word-validity hook | `diagnostics.py` | `audit_jsonl` presents as generic but is Russian-only |
| R5 | Add `"fr": "french"` to `_normalize_language()` and a French entry to `get_default_preset()` | `configs/__init__.py:112-123` | Works today by lowercase fallback, but implicit |

R1 is the big one — it touches every morphological handler call site
(`inflect_word(parse, grammemes, original)` is called 13+ times) but is a mechanical rename
plus one protocol definition. `sample_confused_grammeme` and `match_capitalization`
(`inflector.py:59-79,82`) are already language-agnostic and move to a shared module.

## 3. Resource stack

| Need | Resource | License | Notes |
|------|----------|---------|-------|
| Parsing (default backend) | **stanza `fr_sequoia`** | Apache 2.0 / treebank CC | Best UFeats (97.9) + LAS (91.6) combo among stanza FR packages; drop-in for the stanza-first architecture. spaCy `fr_dep_news_trf` has better LAS but much worse lemmas (91.7 vs 98.5) — lemma is our dictionary key, so no. |
| Noun/adj inflection | **Lefff** (primary) + **Morphalou 3.1** (cross-check + phonetics) | both LGPL-LR | No pymorphy equivalent exists; build a lookup-table generator indexed (lemma, POS, features) → form. |
| Verb conjugation | **verbecc** (proven locally, see §3.1) + **mlconjug3** (fallback) | LGPL-3.0 / MIT | verbecc pipeline already validated on 7,010 verbs in `~/Projects/vibes/dico`; rebuild with full moods + participles. |
| Phonemic lexicon (homophone engine) | **Lexique 3.83** (already local, see §3.1) + **Flexique** (optional cross-check) | verify (Lexique "GNU-like"/CC-BY per docs; Flexique CNRS "research") | Replaces the Zaliznyak stress dict's role entirely. Lexique's `phon` column per inflected form lets us *derive* homophone sets (chanté/chanter/chantez → same phonemic form) instead of hand-curating; `infover` supplies per-form verb features, `nbhomoph`/`nbhomogr` pre-count confusability. |
| Morpheme boundaries | **MorphoLex-FR** (38.8k, PRS segmentation) + **Démonette-2** (CC BY 4.0) + affix-regex fallback | verify / CC BY 4.0 | Weakest link vs Tikhonov's 93k — but far fewer French handlers need morpheme boundaries (mainly double_consonant), so the gap is tolerable. |
| Verb valency / preposition government | **Lefff subcat frames** (already in stack) + hand-curated top-100 verb list | LGPL-LR | For preposition handler and pronominal-participle agreement (phase 2). |
| Paronyms, pleonasms | **BDL (OQLF)** lists + UQTR paronym portal, hand-compiled | Québec gov., verify reuse | ~100 paronym pairs, ~90 pleonasms — same scale as our Russian JSON files. |
| Real-error corpus (calibration) | **WiCoPaCo** v2 (409k French Wikipedia corrections, categorized incl. real-word confusions) | GFDL | The RLC substitute — see §7. |
| Native school errors | **Scoledit** (1,883 texts, L1 orthographic errors by category) | academic, inquire | Optional second calibration source, L1-flavored. |

### 3.1 Local assets already on disk (`~/Projects/vibes/dico`, verified 2026-07-06)

Anna's `dico` CLI project already vendors a chunk of the phase-1 resource layer:

| Asset | Contents | Reuse for synterr |
|---|---|---|
| `data/Lexique383.tsv` (26MB, full) | All 30+ Lexique columns incl. **`phon`** (phonemic transcription per inflected form), **`infover`** (mode:tense:person per verb form), **`nbhomoph`/`nbhomogr`**, `genre`, `nombre`, `cgram`, `islem`, film/book frequencies | The homophone engine's complete data source. `GROUP BY phon` → confusion sets; `infover` → verb-slot features for verb_ending_homophony; frequency columns → weighting. |
| `data/lexique.db` (16MB SQLite) | Slimmed index: 142,694 forms (ortho, deaccented, lemme, cgram, genre, nombre, freqs) | Schema template; rebuild for synterr keeping `phon` + `infover` (the dico build drops them — `build_lexique.py:63-65`). Covers noun_gender lexicon need. |
| `data/conjugations.db` (14MB) | 7,010 verbs via **verbecc**, 7 tenses (présent, PC, imparfait, futur, conditionnel, subjonctif, impératif) as person-lists; `forms` reverse index (153,689 conjugated forms → infinitive) | Proves the verbecc pipeline end-to-end (`build_conjugations.py`). **Insufficient as-is**: no participles stored (pp_agreement and -é/-er handlers need them), compound tenses skipped. Rebuild with full verbecc output. |
| `data/multitran.db` (923MB) | ru↔fr translation dictionary | Not relevant to synterr. |

Consequence: the phase-1 estimate's long pole (resource layer) shrinks — Lexique ingestion
and verb conjugation are download-free and pipeline-proven; remaining resource work is the
Lefff index (noun/adj paradigms beyond what Lexique's flat form list gives), the h-aspiré
list, and the curated JSON files.

**No stress dictionary.** French has no mobile lexical stress; the entire
vowel-reduction mechanism has no counterpart. Its role (phonology → misspelling) is taken
over by the homophone engine (Flexique phonemic matching) plus categorical rules
(cédille, elision, euphonic -t-).

**No RLC-scale confusion matrices exist for French** (FRIDA is inaccessible; CEFLE is
ELRA-paywalled and unannotated for edits). Plan: ship with literature-informed priors,
then mine WiCoPaCo for empirical frequencies (§7) — the same trajectory Russian took
before the RLC extraction.

## 4. Inflector: `languages/french/inflector.py`

Keep the Russian call signature — `inflect_word(parse, features: set, original=None) -> str|None`
— so handler code stays structurally identical. Internals:

- `parse` is a `FrenchParse` (implements the R1 `MorphParse` protocol): a thin object over
  Lefff paradigm rows for the token's lemma, constructed by the backend at analysis time
  (same place the Russian backends call pymorphy).
- Nouns/adjectives: paradigm lookup by (lemma, target Gender/Number). French nominal
  inflection is regular enough that a rule layer (`+s`/`+e`/`-eux→-euse`…) backstops
  lexicon gaps.
- Verbs: verbecc-built lookup table keyed by (lemma, Mood, Tense, Person, Number) —
  pipeline already proven in `~/Projects/vibes/dico/build_conjugations.py` (§3.1), rebuilt
  to include participles and all moods; mlconjug3 as fallback for out-of-table lemmas.
- UD ↔ lexicon feature mapping tables replace `ud_case_to_pymorphy` etc. No case axis;
  add Mood (Ind/Sub/Cnd/Imp) which Russian's inflector lacks.
- `match_capitalization` reused verbatim; extend with elision awareness (inflected form
  after `l'`/`d'` must keep the apostrophe context valid — new French-only concern).

## 5. Handler inventory

### 5.1 What does NOT port (kill list — record so nobody re-litigates)

| Russian handler/subtype | Reason |
|---|---|
| noun_case_* (all 3 + prep_e_u), adj_case, numeral_declension, adj_short_full | French has no nominal case, no declining numerals, no short/full adjective split. ~18% of the Russian roster and much of MORPH weight simply vanishes; replaced by French-specific classes (participle agreement, gender assignment, contraction). |
| spelling: vowel_reduction, devoicing, prefix_voicing, tsa_confusion, cluster, soft_sign | Slavic phonology/orthography. |
| orthographic_spelling: all 10 subtypes | Russian suffix/prefix letter rules (ы/и, н/нн, ц/sibilant vowels…). |
| function_spelling: taki_hyphen, neg_pronoun_ne_ni, ne_attachment | No French counterpart particles/concord alternation. |
| compound_spelling: pol_spelling | пол- + genitive; French demi- is invariant. |
| PUNCT: comma_isolation, pair_participle/gerund/relative *as-is* | Russian обособление is restrictiveness-blind; French commas ARE the restrictive/non-restrictive signal. Blind port = wrong training data. Replaced by the restrictive/explicative handler (§5.3). |
| PUNCT: comma_asyndetic, dash_asyndetic | Codified-correct Russian БСП = comma-splice *fault* in French. Corrupting toward it would be inserting a different error than labeled. |
| PUNCT: dash_subj_pred | Exists only because Russian drops the present copula; French "être" is obligatory. |
| PUNCT: comma_after_odnako | **Inverted**: French sentence-initial "cependant" conventionally takes the comma the Russian rule forbids. |
| lexical: preposition *guard* | The precision guard checks governed case (`lexical.py:259-301`); French prepositions govern no case. Handler concept survives, guard is redesigned (valency lexicon). |

### 5.2 Proposed French handlers (≈19 handlers, phased)

Naming follows Russian conventions where the concept is shared (reuses errant.yaml
mappings wholesale); French-specific classes get new names.

| Handler | Subtypes | Cat. | Mechanism / gate | Resources | Phase |
|---|---|---|---|---|---|
| **verb_ending_homophony** | inf_to_participle (manger→mangé), participle_to_inf (mangé→manger), ez_confusion, fut_cond_1sg (-ai/-ais) | SPELL | Pure UD features: VerbForm/Mood/Tense/Person slot determines which homophonous ending is wrong here. Zero lexicon. **Highest-frequency native French error; flagship handler #1.** | parser only | 1 |
| **grammatical_homophone** | a_à, et_est, ce_se, on_ont, son_sont, la_là_l'a, leur_leurs, ces_ses_c'est_s'est, quel_qu'elle, peu_peut, quand_quant, ni_n'y, si_s'y | SPELL | POS/lemma/deprel-gated token swap (e.g. leur: iobj clitic = invariable vs det:poss agrees with possessum). Confusion sets seeded by hand, extended via Flexique phonemic matching. | Flexique/Lexique 3 | 1 |
| **pp_agreement** | avoir_cod_anteposé (strip/add agreement when obj linearly precedes participle & aux=avoir), etre_subject, avoir_postposed_overagreement | MORPH | Dep-tree: aux lemma + linear position of `obj` dependent (clitic le/la/les, relative que, fronted quel). **Flagship handler #2 — fully mechanical, the most-discussed French rule.** | parser only | 1 |
| pp_agreement_pronominal | se_cod vs se_coi (invariable) | MORPH | Needs valency: is `se` direct or indirect for this verb? | Lefff subcat + essentially-pronominal verb list | 2 |
| **adj_gender** | adj_gender | MORPH | Same `amod`→head mechanism as Russian; 2-way matrix (no neuter). Strongest direct port. | inflector, confusion matrix | 1 |
| **adj_number** | adj_number | MORPH | Direct port; strip the dead case-preservation code. | inflector | 1 |
| **noun_number** | noun_number | MORPH | Direct port; French -s/-x plural, invariant-word exception list rebuilt. | inflector | 1 |
| **verb_person_number** | basic, relative_qui_attraction (agree with qui's antecedent: c'est moi qui l'**ai** fait), inversion | MORPH | nsubj resolution incl. acl:relcl antecedent hop — extends the Russian dep-tree pattern; qui-attraction is a French-specific subtype with no Russian analog. | inflector | 1 |
| **article_contraction** | a_le (au→à le), de_le (du→de le), neg_de (pas de→pas du) | MORPH | Fully categorical, zero exceptions, changes_length varies. L2-flagship. | none | 1 |
| **noun_gender** | noun_gender (det+adj cascade flip) | MORPH | Lexical gender from Lefff, flip determiner and agreeing adjectives together. L2-dominant — weight ≈0 in native presets, high in FLE preset. | Lefff | 2 |
| **mood_subjunctive** | apres_que (native! subj→ind and ind→subj), trigger_verbs, trigger_conjunctions | MORPH | Closed trigger lexicon (~50 items) + Mood swap on ccomp/advcl verb. après_que is the rare citable *native* error here. | trigger list, inflector | 2 |
| **elision_apostrophe** | elision_omit (l'arbre→le arbre), elision_overapply (le héros→l'héros), euphonic_t (aime-t-il→aime-il), est_ce_que_hyphen | SPELL | Categorical vowel-adjacency rules; overapply needs h-aspiré lexicon (small, closed). | h-aspiré list | 1 |
| **accent_spelling** | accent_drop (problème→probleme), e_accent_swap (é/è), cedilla (commençons→commencons) | SPELL | Diacritic lexicon lookup; cédille is pure rule (c+a/o/u, /s/). Circumflex handled under norm_1990 only. | Lefff/Lexique | 1 |
| **double_consonant** | double_consonant | SPELL | Port of Russian handler with French lexicon (appartement, adresse…); morpheme-boundary check via MorphoLex-FR. | MorphoLex-FR | 2 |
| **keyboard** | keyboard | SPELL | Port with AZERTY adjacency map. | AZERTY map | 1 |
| **paronym** | paronym | OTHER | Direct port of swap logic; grammeme-transfer layer rewritten for French features. BDL list (~100 pairs: éminent/imminent, collision/collusion…). | paronyms_fr.json | 1 |
| **pleonasm** | pleonasm | OTHER | Direct port; BDL list (monter en haut, prévoir à l'avance, voire même…). Watch adjective postposition in insertion sites. | pleonasms_fr.json | 2 |
| **preposition** | preposition (pallier à, se rappeler de, penser à/de, anglicism preps) | OTHER | Valency-lexicon gate (replaces the Russian case-government guard). Insert/delete/swap governed preposition. | Lefff subcat + curated top-100 | 2 |
| **clitic_placement** | clitic_postverbal (je te vois→je vois toi), imperative_order | OTHER | Reorder obj/iobj clitic relative to head verb. L2-only, no Russian analog — high distinctiveness. | none | 3 |
| **word_omission / word_insertion** | as Russian | OTHER | Most portable handlers in the codebase; filler list → French (donc, alors, en fait…), enclitic guard drops out. | fillers_fr.json | 1 |

### 5.3 PUNCT family (phase 2, audit-driven — do not blind-port)

The dep-tree *architecture* (comma classification by own-head deprel, pair detection via
shared head_idx) is fully reusable; the *rules* need re-derivation against French norms
(BDL / Grevisse). Proposed:

| Handler | Subtypes | Signal | Notes |
|---|---|---|---|
| comma_delete_fr | fronted_advcl (Quand il pleut**,** je reste), coordination_mais_car_or_donc, incise/parenthetical (parataxis/discourse), vocative, apposition_pair, explicative_relative_pair | same deprels as Russian, **plus linear-position check** (advcl comma only when clause precedes its head — a boolean over token indices Russian never needed) | fronted_advcl and coordination are near-ports; explicative pair see below |
| comma_insert_fr | before_restrictive_relative, before_que_complement, subj_pred, before_et_binary | negative-constraint guards (`mark`=que → no comma) inverted into insertion errors | France-typical hypercorrection commas |
| **relative_comma (restrictive/explicative)** | delete pair around explicative; insert pair around restrictive | `acl:relcl` + **antecedent-definiteness heuristic**: proper noun / personal pronoun / uniquely-referring definite NP antecedent → explicative (comma pair); bare/indefinite common noun → restrictive (none). | UD does not encode restrictiveness — this heuristic layer is the **novel methodological contribution** of the French PUNCT arm, the analog of the Russian dep-tree punct heuristics claim. |
| dash_to_comma / dash_parenthetical | incise dashes ↔ commas | appos/parataxis | Verify prevalence; French favors commas/parentheses over dashes more than Russian. |

Explicitly excluded: espaces insécables before `;:!?` (typographic tooling convention,
not writer competence), ne-drop (register variation, not error — same judgment as Russian
informal register).

## 6. Package layout, configs, schemas

```
src/synterr/languages/french/
├── __init__.py          # FrenchLanguage (code="fr") — entry point in pyproject.toml
├── backends/            # stanza_fr.py (fr_sequoia; generic UD code factored out of
│                        #   the Russian stanza backend post-R1), spacy_fr.py optional
├── inflector.py         # §4
├── resources.py         # LefffLexicon, PhonemicLexicon (Flexique), MorphemeAnalyzerFr
└── errors/              # homophony.py, agreement.py, determiners.py, spelling.py,
                         #   lexical.py, structural.py, punctuation.py
src/synterr/data/french/ # lefff index (build artifact), flexique index, paronyms_fr.json,
                         #   pleonasms_fr.json, h_aspire.json, fillers_fr.json, azerty.json
src/synterr/configs/french/
├── balanced.yaml        # default (uniform-ish, native-flavored)
├── wicopaco.yaml        # native preset, weights calibrated on WiCoPaCo (§7)
└── fle.yaml             # L2 preset (noun_gender, article, clitic, subjunctive up-weighted)
tests/test_languages/test_french/   # mirrors the 14-file Russian tree + conftest fixtures
                                    # + weight-invariant suite pointed at configs/french/
```

- **Norm flag**: a preset-level `orthographic_norm: traditional|1990` gates
  circumflex/compound-soudure handlers — under the wrong norm these corruptions are not
  errors at all.
- **Schemas**: `errant.yaml` tag taxonomy reused wholesale (it's language-agnostic by
  design); add French entries to its `mappings:`. New `fr_norm.yaml` schema mapping
  subtypes → **BDL article IDs + 1990-rectification rule numbers** (both free and
  citable). Le Bon Usage §§ get the Rozental treatment: cite for academic legitimacy,
  never distribute or generate from the text. There is no free §-numbered comprehensive
  French grammar — accept the hybrid.
- **L2 tags**: FRIDA's 3-tier taxonomy is the published French L2 scheme; wire it the way
  rozental-L2 is wired, even though the corpus itself is inaccessible (the taxonomy is
  published).

## 7. Calibration & evaluation

**Confusion frequencies.** No RLC equivalent → two-step plan:
1. Ship literature-informed priors (Projet Voltaire frequency claims, Catach-typology
   distributions, acquisition literature for L2 gender).
2. Mine **WiCoPaCo v2** (GFDL, 409k categorized Wikipedia self-corrections): its
   real-word-confusion category yields empirical homophone-pair frequencies, and its
   diacritics category calibrates accent_spelling. Script:
   `scripts/extract_wicopaco_matrices.py`, same shape as
   `scripts/extract_confusion_matrices.py`. This gives *native* frequencies; for FLE
   weights, fall back to priors (FRIDA numbers exist in publications even if the corpus
   doesn't circulate).

**Evaluation.** There is no standard French GEC benchmark (the gap is the point). Options,
in order of preference:
1. Hold out WiCoPaCo corrections as a native-error test set (mine (src, tgt) pairs).
2. Lang-8 French (12.4k sentences) as a small L2 dev set.
3. `akufeldt/fr-gec-dataset` (66.5k) exists but is itself synthetic — usable only as a
   sanity check, not as evidence.
4. Longer-term: a LoRuGEC-style curated benchmark from BDL example sentences would be a
   contribution in its own right (BDL is free, unlike Rozental).

**Diagnostics.** `audit_jsonl`'s word-validity check (post-R4) uses Lefff membership as
the French `word_is_known`.

## 8. Phasing & rough effort

| Phase | Content | Size |
|---|---|---|
| 0 | Core refactors R1–R5 + Russian regression (all 686 tests green, byte-identical output on a pinned corpus) | ~1 wk |
| 1 | Backend (fr_sequoia) + Lefff/Flexique resource layer + inflector + 11 phase-1 handlers + balanced.yaml + errant mappings + test tree | ~3–4 wk (resource layer is half of it) |
| 2 | PUNCT family incl. restrictive/explicative heuristic + subjunctive + preposition + pleonasm + pronominal pp + fle.yaml | ~2–3 wk |
| 3 | WiCoPaCo mining → wicopaco.yaml + evaluation set construction + clitic_placement + norm_1990 handlers | ~2 wk |

Handlers-by-phase leaves French at ≈19 handlers / ≈45 subtypes after phase 2 — smaller
than Russian's 28/84, which is correct: French concentrates its error mass in fewer,
higher-frequency classes.

## 9. Open questions & risks

1. **License verifications before anything ships**: Lexique 3 ("GNU-like" — verify exact
   terms), Flexique (CNRS research-use), MorphoLex-FR (check data-availability statement),
   CollFrEn (no LICENSE in repo), BDL reuse terms (Québec gov. content). Lefff/Morphalou
   (LGPL-LR) and Démonette-2 (CC BY 4.0) and WiCoPaCo (GFDL) are safe.
2. **Which orthographic norm is "correct"?** Must be decided per generated corpus
   (traditional vs 1990); affects circumflex, soudure, and even pp agreement of pronominal
   verbs (laisser + inf). Recommendation: default `traditional`, both supported.
3. **Lemma quality on learner-like text**: fr_sequoia is trained on edited text — fine for
   corruption input (we corrupt clean text), but verify feature reliability on the specific
   clean corpora chosen (French Wikipedia dumps? Europarl?). Choose the French `lenta_50k`
   equivalent early.
4. **Restrictive/explicative heuristic precision** needs a validation pass (the Artem
   pattern): sample N=200 classified relatives, human-verify before trusting the handler.
5. **Register traps**: c'est/ce sont, tense concordance, ne-drop are accepted-variation
   minefields — deliberately excluded or deferred; revisit only with register-gated configs.
6. **Paper positioning**: "first dep-tree-grounded, confusion-calibrated synthetic error
   generator for French; French missing from MultiGEC-2025/OmniGEC/ERRANT" is the novelty
   frame. The restrictive/explicative definiteness heuristic extends the punct-heuristics
   claim beyond a port.

## 10. Source reports

Full subagent research reports (codebase portability map with file:line citations, data
landscape with URLs, tooling survey, error taxonomy with per-class generatability
judgments) are preserved in the session transcript of 2026-07-06; key facts are inlined
above. Primary external references: MultiGEC-2025 (aclanthology 2025.nlp4call-1.1),
WiCoPaCo (wicopaco.limsi.fr), Lefff (almanach.inria.fr), Flexique (LLF/CNRS), MorphoLex-FR
(Behav Res Methods 2019), Démonette-2 (ANR Démonext), BDL
(vitrinelinguistique.oqlf.gouv.qc.ca), rectifications 1990 (academie-francaise.fr),
Grammalecte (grammalecte.net, GPLv3), FRETA-D (PMC9878594), Catach's plurisystème
typology, Projet Voltaire error rankings.
