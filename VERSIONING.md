# synterr Versioning Roadmap

## Scope Definition

### Error Coverage Goals

Three reference points for coverage:
1. **RLC Taxonomy**: 38 tags (error-cause focused)
2. **RuBLiMP**: 45 phenomena (grammaticality probing)
3. **Learner Corpora**: Actual error distributions from RULEC-GEC, GERA

**v1.0.0 target**: Cover error types that account for **>90% of errors** in Russian learner corpora.

From our distribution analysis:
| Error Type | RULEC-GEC % | Priority |
|------------|-------------|----------|
| Spelling | ~35% | ✅ Implemented |
| Case (noun/adj) | ~25% | ✅ Implemented |
| Agreement | ~15% | HIGH |
| Lexical | ~10% | HIGH |
| Structural (Miss/Extra) | ~8% | MEDIUM |
| Aspect/Tense | ~5% | MEDIUM |
| Other | ~2% | LOW |

---

## Version Milestones

### v0.0.1-alpha (Current Release)

**Status**: Ready for Artem handoff

**Implemented**:
- [x] Core architecture (protocol, pipeline, registry)
- [x] CLI with presets and config system
- [x] Pluggable backends (stanza/natasha/spacy)
- [x] GECToR output format

**Error handlers** (8 total):
- [x] `spelling` — phonetic confusions, keyboard typos
- [x] `noun_case` — case inflection errors
- [x] `noun_number` — singular/plural
- [x] `adj_case`, `adj_number`, `adj_gender`
- [x] `verb_person_number`, `verb_tense`

**Resources**:
- [x] Paronym dictionary (paronyms.json)
- [x] Preset configs (rulec, gera, balanced)

**Documentation**:
- [x] README, CONTRIBUTING.ru.md
- [x] IMPLEMENTATION_ROADMAP (en/ru)
- [x] LABEL_SCHEMA (en/ru)
- [x] REFERENCES

---

### v0.2.0 — Lexical & Structural Errors

**Artem's scope** (no deep linguistics required):

- [ ] `paronym` handler — uses existing paronyms.json
- [ ] `preposition` handler — substitution from similarity groups
- [ ] `conjunction` handler — substitution from confusion pairs
- [ ] `word_omission` handler — delete function words (Miss)
- [ ] `word_insertion` handler — insert fillers (Extra)

**Resources to create**:
- [ ] `data/russian/prepositions.json` — similarity groups
- [ ] `data/russian/conjunctions.json` — confusion pairs
- [ ] `data/russian/fillers.json` — insertable words

**Tests**: Each handler needs protocol compliance + unit tests

---

### v0.3.0 — Agreement Errors (Requires `--depparse`)

**Expertise required** (Anna's scope):

- [ ] `agr_case` — adjective-noun case agreement via `amod`
- [ ] `agr_number` — subject-verb number agreement via `nsubj`
- [ ] `agr_gender` — adjective/predicate gender agreement
- [ ] `agr_person` — subject-verb person agreement

**Requires understanding of**:
- Universal Dependencies relations
- Russian agreement patterns
- stanza/spacy depparse output

---

### v0.4.0 — Government Errors

**Expertise required**:

- [ ] `verb_government` — verb case requirements
- [ ] `prep_government` — preposition case requirements

**Resources to create** (linguistics expertise):
- [ ] `data/russian/verb_government.json` — {verb: (prep, case)}
- [ ] `data/russian/prep_case.json` — {prep: [valid_cases]}

**Can borrow from**: RuBLiMP `ADP_CASES` (19 prepositions)

---

### v0.5.0 — Aspect Errors

**Mixed scope**:

- [ ] `aspect` handler — swap imperfective ↔ perfective

**Resources**:
- [ ] Import RuBLiMP aspect pairs (2716 pairs from Zaliznjak)
- [ ] `data/russian/aspect_triggers.json` — context verbs requiring specific aspect

---

### v1.0.0 — Full Release

**Criteria**:
- [ ] All handlers from v0.2–v0.5 implemented and tested
- [ ] Coverage of >90% of learner corpus error types
- [ ] Benchmarked against RULEC-GEC test set
- [ ] Documentation complete
- [ ] PyPI release

**Error type coverage at v1.0.0**:

| Category | Handlers | RLC Tags Covered |
|----------|----------|------------------|
| Spelling | `spelling` | Ortho, Misspell, Graph |
| Morphology | `noun_*`, `adj_*`, `verb_*` | Infl, Num, Gender, Tense |
| Agreement | `agr_*` | AgrCase, AgrNum, AgrGender, AgrPers |
| Government | `*_government` | Gov |
| Lexical | `paronym`, `preposition`, `conjunction` | Lex, Prep, Conj |
| Structural | `word_omission`, `word_insertion` | Miss, Extra |
| Aspect | `aspect` | Asp |

**Not in v1.0.0 scope** (complex/low frequency):
- Word formation (Morph — derivational)
- Reflexives (Refl)
- Word order (WO)
- Idioms (Idiom)
- Code-switching (CS)

---

## Task Assignment Summary

### Artem (v0.2.0)
| Task | Difficulty | Dependencies |
|------|------------|--------------|
| `paronym` handler | Easy | paronyms.json ✅ |
| `preposition` handler | Easy | Create prepositions.json |
| `conjunction` handler | Easy | Create conjunctions.json |
| `word_omission` handler | Medium | Understand length-changing |
| `word_insertion` handler | Medium | Create fillers.json |
| Tests for all above | Easy | Follow existing patterns |

### Anna (v0.3.0+)
| Task | Difficulty | Dependencies |
|------|------------|--------------|
| Agreement handlers | Hard | depparse understanding |
| Government handlers | Hard | Linguistic resource curation |
| Aspect handler | Medium | Import RuBLiMP data |
| Review Artem's code | — | — |

---

## External Resources to Integrate

| Resource | Source | Size | For Version |
|----------|--------|------|-------------|
| Aspect pairs | RuBLiMP | 2716 pairs | v0.5.0 |
| Preposition-case | RuBLiMP | 19 preps | v0.4.0 |
| RuBLiMP full data | Google Drive | ~11GB | Research/eval |
| RuERRANT | GitHub | Tool | Evaluation |

---

## Release Checklist

### For each release:
- [ ] All tests pass (`uv run pytest`)
- [ ] Lint passes (`uv run ruff check`)
- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG updated
- [ ] Git tag created (`git tag vX.Y.Z`)
- [ ] GitHub release created
