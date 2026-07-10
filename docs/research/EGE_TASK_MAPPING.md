# ЕГЭ Task Mapping for Synterr

**Paper angle**: Synterr as automatic ЕГЭ preparation material generator.

**Key insight**: ЕГЭ (Unified State Exam) + Правила 1956 = standardized, testable Russian grammar rules. Synterr can generate unlimited practice sentences tagged with ЕГЭ task numbers.

---

## Complete ЕГЭ Task List (2026)

| Task | What It Tests | Synterr Status | Difficulty | Notes |
|------|---------------|----------------|------------|-------|
| **1** | Logical-semantic relations in text | ❌ Not applicable | N/A | Text comprehension |
| **2** | Means of connecting sentences | ❌ Not applicable | N/A | Cohesion analysis |
| **3** | Lexical meaning of words | ❌ Not applicable | N/A | Vocabulary understanding |
| **4** | Orthoepic norms (ударения) | ✅ **Ready** | ✅ Easy | stress_dict.json exists |
| **5** | Paronynms (паронимы) | ✅ **Ready** | ✅ Easy | paronyms.json exists |
| **6** | Lexical errors (плеоназмы, тавтология) | ⚠️ Partial | 🟡 Medium | Pleonasm/tautology handler needed |
| **7** | Morphological norms (word forms) | ✅ **Covered** | ✅ Exists | noun_case, adj_case, verb_* |
| **8** | Syntactic norms (agreement) | ⚠️ Partial | 🔴 Hard | Needs dependency parsing |
| **9** | Vowels/consonants in roots | ✅ **Covered** | ✅ Exists | vowel_reduction, alternation |
| **10** | Prefix spelling (пре-/при-) | ⚠️ Partial | ✅ Easy | prefix_voicing exists, need пре-/при- |
| **11** | Suffix spelling (not н/нн) | ❌ Missing | 🟡 Medium | Suffix variation handler |
| **12** | Verb/participle endings | ✅ **Covered** | ✅ Exists | verb_person_number, verb_tense |
| **13** | НЕ and НИ spelling | ❌ Missing | 🟡 Medium | Negation spelling handler |
| **14** | Compound words, чтобы/тоже/также | ⚠️ Partial | ✅ Easy | Rozental §61 (союзы) |
| **15** | Н and НН in suffixes | ❌ Missing | 🟡 Medium | Double consonant rules |
| **16-21** | Punctuation | ❌ Not in scope | N/A | GEC focuses on orthography/morphology |
| **22** | Means of speech expressiveness | ❌ Not applicable | N/A | Rhetoric analysis |
| **23** | Text integrity | ❌ Not applicable | N/A | Text analysis |
| **24** | Functional-semantic types | ❌ Not applicable | N/A | Text type identification |
| **25** | Lexical meaning in context | ❌ Not applicable | N/A | Vocabulary analysis |
| **26** | Means of connecting sentences | ❌ Not applicable | N/A | Cohesion analysis |
| **27** | Essay | ❌ Not applicable | N/A | Creative writing |

---

## Priority Implementation for Paper

### Tier 1: ✅ Already Working (6 tasks)
These can be **immediately** used for ЕГЭ prep generation:

- **Task 4 (Ударения)**: Use `stress_dict.json` → generate stress error exercises
- **Task 5 (Паронимы)**: Use `paronyms.json` → generate paronym substitution exercises
- **Task 7 (Морфология)**: `noun_case`, `adj_case/number/gender`, `verb_person_number`, `verb_tense`
- **Task 9 (Корни)**: `vowel_reduction` (безударные гласные)
- **Task 10 (Приставки)**: `prefix_voicing` (оглушение/озвончение)
- **Task 12 (Окончания)**: `verb_person_number`, `verb_tense`

### Tier 2: ✅ Easy Wins (15-30 min each)
Implement before paper submission:

1. **Task 10 (пре-/при-)** — 15 min
   - Handler: `prefix_pre_pri.py`
   - Rules: пре- (очень, пере-), при- (приближение, присоединение, неполнота)
   - Rozental §33

2. **Task 14 (союзы)** — 20 min
   - Handler: `conjunction_spelling.py`
   - Mapping: Rozental §61
   ```
   чтобы ↔ что бы
   тоже ↔ то же
   также ↔ так же
   причём ↔ при чём
   притом ↔ при том
   зато ↔ за то
   итак ↔ и так
   ```
   - **Direct LORuGEC overlap!**

3. **Task 4 (stress errors)** — 15 min
   - Handler: `stress_error.py`
   - Already have `stress_dict.json`
   - Generate: звони́т → зво́нит, торты́ → то́рты

### Tier 3: 🟡 Medium (1-2 hours each)
Consider for extended version:

4. **Task 15 (н/нн)** — 1.5 hours
   - Handler: `nn_suffix.py`
   - Rules: прилагательные (-ан-/-ян-/-ин- → 1н, -енн-/-онн- → 2н)
   - Причастия (полные → 2н, краткие → 1н)

5. **Task 6 (Плеоназмы)** — 2 hours
   - Handler: `pleonasm.py`
   - Examples: "своя автобиография", "главная суть", "памятный сувенир"
   - Rozental Stylistics §141

6. **Task 11 (Suffixes)** — 1 hour
   - Handler: `suffix_variation.py`
   - -ова-/-ева- vs -ыва-/-ива-
   - -ирова- patterns

### Tier 4: 🔴 Hard (Not for v0.2.0)
- **Task 8 (Syntactic agreement)**: Requires full dependency parsing
- **Task 13 (НЕ/НИ)**: Complex semantic/syntactic rules

---

## Implementation Roadmap

### For BEA/GEM Paper (March 5/19)

**Target**: 10 ЕГЭ tasks covered (currently 6 covered)

**Add 4 more**:
1. ✅ Task 10: `prefix_pre_pri.py` (15 min)
2. ✅ Task 14: `conjunction_spelling.py` (20 min)
3. ✅ Task 4: `stress_error.py` (15 min)
4. 🟡 Task 15: `nn_suffix.py` (1.5 hours)

**Total implementation time**: ~2.5 hours

**Paper contribution**:
> "Synterr covers 10/27 ЕГЭ tasks, including all morphology tasks (7, 12) and high-frequency orthography errors (9, 10, 14, 15). System generates unlimited ЕГЭ-style practice sentences with gold-standard corrections, enabling automatic training of GEC models as ЕГЭ auto-checkers."

### Output Format Example

```json
{
  "source": "Я хочу что бы ты пришёл вовремя.",
  "target": "Я хочу чтобы ты пришёл вовремя.",
  "error_type": "conjunction_spelling",
  "ege_task": 14,
  "rule": "rozental_61",
  "explanation": "союз 'чтобы' (=для того чтобы) пишется слитно"
}
```

### Evaluation Strategy

1. **Test on LORuGEC**:
   - LORuGEC has 48 rules, many overlap with ЕГЭ
   - Task 14 (союзы) = direct LORuGEC overlap
   - Measure: Can synterr generate errors matching LORuGEC rule distribution?

2. **Test on GERA**:
   - L1 native school essays → closest to ЕГЭ exam population
   - Measure: F0.5 score on GERA test set (1000 sentences)

3. **ЕГЭ Open Bank**:
   - ФИПИ provides open task bank: https://fipi.ru/ege/otkrytyy-bank-zadaniy-ege
   - Can scrape examples for each task
   - Measure: Does synterr distribution match real ЕГЭ error distribution?

---

## Rozental Alignment

| ЕГЭ Task | Rozental Section | Status |
|----------|------------------|--------|
| 4 | Орфоэпический словник ФИПИ | ✅ stress_dict.json |
| 5 | Словарь паронимов ФИПИ | ✅ paronyms.json |
| 9 | §1-18 (Корни) | ✅ vowel_reduction |
| 10 | §33 (пре-/при-), §34-43 | ⚠️ Need §33 |
| 12 | §46-57 (Глаголы, причастия) | ✅ verb_* handlers |
| 14 | §61 (Союзы) | ❌ Need implementation |
| 15 | §67-73 (н/нн) | ❌ Need implementation |
| 6 | Stylistics §141 (Плеоназмы) | ❌ Future work |

---

## Data Sources

### Official ФИПИ Resources

- **Demo versions**: https://fipi.ru/ege/demoversii-specifikacii-kodifikatory
- **Open task bank**: https://fipi.ru/ege/otkrytyy-bank-zadaniy-ege
- **Orthoepic словник**: https://accentonline.ru/ege.html
- **Paronym словник**: Published in ФИПИ navigator

### Training Corpora

- **Lenta.ru** (2M sentences) — Generate ЕГЭ-style errors from news
- **Wikipedia** (5.8GB) — General domain
- **GERA** (4500 train) — L1 school essays (closest to ЕГЭ population)

### Evaluation Corpora

- **LORuGEC** (960 sentences) — 48 grammar rules, evaluation-only
- **GERA** (1000 test sentences) — L1 native errors
- **ЕГЭ Open Bank** — Real exam questions from ФИПИ

---

## Technical Implementation Notes

### Stress Error Handler (Task 4)

```python
class StressErrorHandler:
    """Generate incorrect stress placement."""
    name = "stress_error"
    subtypes = ["stress_shift"]
    category = "SPELL"
    changes_length = False

    def can_apply(self, tokens, idx):
        word = tokens[idx].text.lower()
        return word in self.stress_dict

    def apply(self, tokens, sentence, idx, modified):
        word = tokens[idx].text
        correct_stress = self.stress_dict[word.lower()]  # "звони́т"
        # Generate incorrect: "зво́нит" (shift stress left)
        incorrect = self._shift_stress(word, correct_stress)
        return ErrorResult(
            error_type="stress_error",
            category="SPELL",
            original=word,
            corrupted=incorrect,
            fix_tag=f"$REPLACE_{incorrect}"
        )
```

### Conjunction Handler (Task 14)

```python
class ConjunctionSpellingHandler:
    """Rozental §61: чтобы/тоже/также vs что бы/то же/так же."""
    name = "conjunction_spelling"
    subtypes = ["conjunction_merge", "conjunction_split"]
    category = "SPELL"
    changes_length = True  # Can insert/delete tokens

    CONJUNCTIONS = {
        "чтобы": "что бы",
        "тоже": "то же",
        "также": "так же",
        # ... rest of §61 list
    }

    def can_apply(self, tokens, idx):
        word = tokens[idx].text.lower()
        # Check if conjunction (solid)
        if word in self.CONJUNCTIONS:
            return True
        # Check if could be merged (split form)
        if idx + 1 < len(tokens):
            pair = word + " " + tokens[idx + 1].text.lower()
            return pair in self.CONJUNCTIONS.values()
        return False
```

---

## References

- ФИПИ (2026). "Демоверсия ЕГЭ по русскому языку." https://fipi.ru/ege/demoversii-specifikacii-kodifikatory
- Nasyrova & Sorokin (2025). "LORuGEC: Rule-annotated Russian GEC." https://github.com/ReginaNasyrova/LORuGEC
- Розенталь Д.Э. "Справочник по правописанию и стилистике" (ИК «Комплект», 1997)
- Правила русской орфографии и пунктуации (1956)
