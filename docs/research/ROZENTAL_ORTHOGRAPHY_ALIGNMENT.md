# Rozental Orthography Alignment for synterr

A research draft for systematically aligning synterr's spelling error handlers with Rozental's canonical orthography taxonomy.

## Motivation

synterr currently uses ad-hoc spelling subtypes (`vowel_reduction`, `devoicing`, etc.) derived from phonetic principles and common learner errors. While linguistically motivated, this approach:

1. **Lacks standardization** — no reference to established pedagogical taxonomy
2. **Has gaps** — many common error types are not covered
3. **Is hard to evaluate** — can't compare coverage to known rule sets

Rozental's "Справочник по правописанию и стилистике" is THE canonical prescriptive Russian orthography reference. Aligning synterr to Rozental sections would:

1. **Ensure completeness** — systematic coverage of all orthographic rules
2. **Enable comparison** — direct mapping to LORuGEC (which cites Rozental)
3. **Support pedagogy** — errors organized by teaching order
4. **Be publishable** — novel contribution to Russian GEC

## Scope

**In scope:** Sections I–XVIII of Rozental Orthography (§1–§73)
**Out of scope:** Punctuation (requires syntactic analysis, different problem)

## Current Coverage

### Mapped (6 subtypes → 6 sections)

| synterr subtype | Rozental § | Section title | Notes |
|-----------------|------------|---------------|-------|
| `vowel_reduction` | § 1 | Проверяемые безударные гласные | Core phonetic rule |
| `devoicing` | § 8 | Звонкие и глухие согласные | Final devoicing |
| `double_consonant` | § 9 | Двойные согласные | Partial (корень only) |
| `cluster` | § 10 | Непроизносимые согласные | солнце→сонце |
| `soft_sign` | § 29–30 | Разделительные ъ и ь | Partial |
| `prefix_voicing` | § 31 | Приставки на з- | расписать→разписать |

### Unmapped (2 subtypes)

| synterr subtype | Status | Notes |
|-----------------|--------|-------|
| `tsa_confusion` | Phonetic, not in Rozental | цирк→цырк (learner error) |
| `keyboard` | Typo, not orthographic | Not a Rozental rule |

## Gap Analysis

### High Priority (Common errors, pattern-based)

| Rozental § | Title | Feasibility | Notes |
|------------|-------|-------------|-------|
| § 2 | Непроверяемые безударные гласные | Hard | Needs word list |
| § 3 | Чередующиеся гласные | **Easy** | бер/бир, гор/гар — finite set |
| § 4 | Гласные после шипящих | Medium | Context-dependent |
| § 5 | Гласные после ц | **Easy** | Simple rule |
| § 33 | Приставки пре- и при- | **Easy** | High-frequency error |
| § 34 | Гласные ы и и после приставок | **Easy** | Simple rule |
| § 52 | нн и н в причастиях | Medium | Needs POS |
| § 61 | Слитное написание союзов | **Easy** | LORuGEC overlap! |

### § 61 Detail (Direct LORuGEC Alignment)

```
§ 61.1 чтобы     vs  что бы      → LORuGEC rule
§ 61.2 тоже      vs  то же       → LORuGEC rule
§ 61.2 также     vs  так же      → LORuGEC rule
§ 61.3 причём    vs  при чём     → LORuGEC rule
§ 61.3 притом    vs  при том     → LORuGEC rule
§ 61.4 зато      vs  за то       → LORuGEC rule
§ 61.4 отчего    vs  от чего     → LORuGEC rule
§ 61.4 оттого    vs  от того     → LORuGEC rule
§ 61.4 почему    vs  по чему     → LORuGEC rule
§ 61.4 потому    vs  по тому     → LORuGEC rule
§ 61.5 итак      vs  и так       → LORuGEC rule
```

These are lexeme-specific but form a **closed set** — implementable as lookup table.

### Medium Priority (Less common, more complex)

| Rozental § | Title | Feasibility | Notes |
|------------|-------|-------------|-------|
| § 6 | Буквы э-е | Medium | Limited context |
| § 35–36 | о/е после шипящих и ц | Medium | Suffix rules |
| § 37–38 | Окончания/суффиксы сущ. | Hard | Many sub-rules |
| § 40 | Суффиксы прилагательных | Hard | Many sub-rules |
| § 53–58 | Правописание наречий | Hard | Lexical knowledge |
| § 65–72 | не и ни | Medium | Context-dependent |

### Low Priority / Out of Scope

| Rozental § | Title | Why skip |
|------------|-------|----------|
| § 11–28 | Прописные буквы | Proper nouns — not learner errors |
| § 41–44 | Сложные слова | Compound formation — rare errors |
| § 45–46 | Числительные | Rare |
| § 73 | Междометия | Rare |
| § 74 | Иностранные слова | Too specific |

## Proposed Schema Structure

```yaml
# schemas/data/rozental.yaml
name: rozental
version: "1.0"
description: "Rozental orthography taxonomy (§1-§73)"
source: "Розенталь Д.Э. Справочник по правописанию и стилистике"

primary_tags:
  # I. Правописание гласных в корне
  R01_vowel_checked:
    description: "Проверяемые безударные гласные"
    rozental_section: "§ 1"
    detection_category: SPELL
  R02_vowel_unchecked:
    description: "Непроверяемые безударные гласные"
    rozental_section: "§ 2"
    detection_category: SPELL
  R03_vowel_alternating:
    description: "Чередующиеся гласные"
    rozental_section: "§ 3"
    detection_category: SPELL
  # ... etc

  # II. Правописание согласных в корне
  R08_consonant_voicing:
    description: "Звонкие и глухие согласные"
    rozental_section: "§ 8"
    detection_category: SPELL
  R09_consonant_double:
    description: "Двойные согласные"
    rozental_section: "§ 9"
    detection_category: SPELL
  R10_consonant_silent:
    description: "Непроизносимые согласные"
    rozental_section: "§ 10"
    detection_category: SPELL

  # V. Правописание приставок
  R31_prefix_z:
    description: "Приставки на з-"
    rozental_section: "§ 31"
    detection_category: SPELL
  R33_prefix_pre_pri:
    description: "Приставки пре- и при-"
    rozental_section: "§ 33"
    detection_category: SPELL
  R34_prefix_y_i:
    description: "Гласные ы и и после приставок"
    rozental_section: "§ 34"
    detection_category: SPELL

  # XVI. Правописание союзов
  R61_conjunction_spelling:
    description: "Слитное написание союзов"
    rozental_section: "§ 61"
    detection_category: SPELL

mappings:
  # Existing synterr subtypes → Rozental
  vowel_reduction:
    primary: R01_vowel_checked
  devoicing:
    primary: R08_consonant_voicing
  double_consonant:
    primary: R09_consonant_double
  cluster:
    primary: R10_consonant_silent
  prefix_voicing:
    primary: R31_prefix_z
  soft_sign:
    primary: R29_hard_sign  # or R30_soft_sign

  # Future handlers
  alternating_vowel:
    primary: R03_vowel_alternating
  prefix_pre_pri:
    primary: R33_prefix_pre_pri
  conjunction_spelling:
    primary: R61_conjunction_spelling
```

## Implementation Roadmap

### Phase 1: Schema + Mapping (v0.2.x)
- Create `rozental.yaml` schema
- Map existing subtypes to Rozental sections
- Add `rozental_section` field to ErrorResult metadata

### Phase 2: High-Value Handlers (v0.3.x)
1. **§ 3 Чередующиеся гласные**
   - бер/бир, пер/пир, дер/дир, тер/тир, мер/мир
   - гор/гар, зор/зар, клон/клан, твор/твар
   - лаг/лож, кас/кос, раст/рос
   - Finite rule set, needs suffix context

2. **§ 33 пре-/при-**
   - пре- = "очень" or "пере-"
   - при- = приближение, присоединение, неполнота
   - High-frequency learner error

3. **§ 61 Союзы** (LORuGEC alignment)
   - Lexicon-based: {чтобы, тоже, также, причём, притом, зато, итак, ...}
   - Split/merge transformations

### Phase 3: Extended Coverage (v0.4.x)
- § 34 ы/и после приставок
- § 52 нн/н в причастиях
- § 65–71 не/ни rules

## Evaluation Plan

### Coverage Metric
```
Rozental coverage = implemented_sections / total_sections
```

Current: 6/73 = 8.2%
After Phase 2: ~12/73 = 16.4%
Target v1.0: 25/73 = 34% (high-frequency rules)

### LORuGEC Alignment
- Map LORuGEC 48 rules → Rozental sections
- Measure overlap with synterr coverage
- Use LORuGEC as diagnostic evaluation

### Error Distribution Validation
- Compare synterr error distribution to RULEC-GEC/GERA
- Validate that Rozental-aligned errors match real learner patterns

## References

1. Розенталь Д.Э. (1997). Справочник по правописанию и стилистике. Москва: ИК «Комплект».

2. Розенталь Д.Э., Джанджакова Е.В., Кабанова Н.П. (2013). Справочник по русскому языку: правописание, произношение, литературное редактирование. Москва: Айрис-пресс.

3. Nasyrova, R. & Sorokin, A. (2025). LORuGEC: the Linguistically Oriented Rule-annotated corpus for Grammatical Error Correction of Russian. Dialogue 2025.

4. ФИПИ. Демонстрационные варианты ЕГЭ по русскому языку. (Contains orthography rules tested in national exam)

## Appendix: Full Rozental Orthography TOC

```
I. Правописание гласных в корне (§ 1-7)
II. Правописание согласных в корне (§ 8-10)
III. Употребление прописных букв (§ 11-28)
IV. Разделительные ъ и ь (§ 29-30)
V. Правописание приставок (§ 31-34)
VI. Гласные после шипящих и ц в суффиксах и окончаниях (§ 35-36)
VII. Правописание имен существительных (§ 37-38)
VIII. Правописание имен прилагательных (§ 39-40)
IX. Правописание сложных слов (§ 41-44)
X. Правописание имен числительных (§ 45-46)
XI. Правописание местоимений (§ 47)
XII. Правописание глаголов (§ 48-50)
XIII. Правописание причастий (§ 51-52)
XIV. Правописание наречий (§ 53-58)
XV. Правописание предлогов (§ 59-60)
XVI. Правописание союзов (§ 61-62)
XVII. Правописание частиц (§ 63-64)
     Правописание не и ни (§ 65-72)
XVIII. Правописание междометий (§ 73)
XIX. Правописание иностранных слов (§ 74)
```

## Notes

- Punctuation (Розенталь Part 2) is explicitly out of scope
- Proper noun capitalization (§ 11-28) is low-value for GEC
- Focus on high-frequency learner errors, not completeness
- Schema should support partial implementation
