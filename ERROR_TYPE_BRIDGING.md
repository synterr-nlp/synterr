## Zaliznjak's Grammatical Dictionary

**Зализняк А.А. "Грамматический словарь русского языка: Словоизменение"** (1977, 4th ed. 2003)

This is *the* canonical resource for Russian morphology — essentially a machine-readable encoding of every word's full paradigm. It's what powers pymorphy2, OpenCorpora, and most Russian NLP tools.

### Structure

Each entry looks like:
```
дом м 1a
книга ж 1a
море с 2a
любить нсв 4c(любл)
```

The notation encodes:
- **Part of speech** (м = masc, ж = fem, с = neut, нсв/св = verb aspect)
- **Paradigm class** (numbered 1-8 for nouns, 1-16 for verbs, with subclasses a/b/c/etc.)
- **Stress pattern** (a = fixed, b = mobile, c/d/e/f = specific mobility patterns)
- **Stem alternations** in parentheses (любл = stem changes to любл- in 1sg)

### Example: Noun Paradigm Classes

| Class | Pattern | Example | Gen.Sg | Gen.Pl |
|-------|---------|---------|--------|--------|
| 1a | Hard masc | стол | стола | столов |
| 1c | Hard masc, mobile stress | дом | дома | домов |
| 2a | Hard fem -а | книга | книги | книг |
| 3a | Soft masc -ь | гость | гостя | гостей |
| 8a | Neuter -мя | время | времени | времён |

### Why This Matters for Error Generation

If you know a word's Zaliznjak class, you can:

1. **Generate all correct forms** programmatically
2. **Generate plausible errors** by applying the wrong class's endings

```python
# Pseudocode
word = "гость"  # class 3a (soft masc)
correct_gen_pl = "гостей"  # class 3a pattern

# Error: apply class 1a pattern (hard masc) instead
error_gen_pl = "гостов"  # ❌ wrong but morphologically regular
```

### Digital Resources

- **pymorphy2** — Python library built on Zaliznjak + OpenCorpora: https://github.com/pymorphy2/pymorphy2
- **OpenCorpora** — crowdsourced dictionary with Zaliznjak-style markup: http://opencorpora.org/
- **Russian Wiktionary** — paradigm tables derived from Zaliznjak
- **Original dictionary** — scanned PDFs exist, also reprinted by АСТ-Пресс

---

## The Bridging Problem

You're right to be confused — I gave you two things:
1. **RLC taxonomy** = labels for *what kind of error* it is
2. **Rozental rules** = prescriptive norms for *what's correct*

But neither directly tells you **how to generate errors**. The bridge is:

```
RLC Tag  →  Linguistic Rule (from Rozental)  →  Inversion Strategy  →  Generative Function
```

Let me make this explicit:

### Bridge Table: RLC → Rule → Generation

| RLC Tag | Rozental Rule | What It Means | How to Generate Error |
|---------|--------------|---------------|----------------------|
| **Gov** | Управление глаголов: each verb requires specific case ± preposition | "помогать" requires Dat, "ждать" requires Acc/Gen | Look up verb's required case, substitute a different case |
| **AgrGender** | Согласование в роде: adj/verb must match noun's gender | "новый дом" (m+m), "новая книга" (f+f) | Keep noun, change adj/verb ending to wrong gender |
| **AgrCase** | Согласование в падеже: adj must match noun's case | "с новым другом" (Instr+Instr) | Keep noun's case, put adj in different case |
| **AgrNum** | Согласование в числе: adj/verb must match noun's number | "новые дома" (pl+pl) | Mismatch singular/plural between controller and target |
| **Asp** | Вид глагола: context determines which aspect | After "начать" use НСВ | Identify context trigger, use wrong aspect pair member |
| **Infl** | Формообразование: each paradigm class has specific endings | Class 3a masc has Gen.Pl "-ей" | Apply wrong paradigm class's ending |
| **Morph** | Словообразование: derivational affixes have selectional restrictions | Abstract nouns: -ость/-ство/-ние | Use wrong derivational suffix |
| **Prep** | Предлоги: prepositions select specific cases and have semantic constraints | "в" + Prep (location), "в" + Acc (direction) | Swap preposition or use wrong case after preposition |

### Concrete Example: Generating a **Gov** Error

**Rule from Rozental:** 
> Глагол "помогать" требует дательного падежа: помогать кому? — помогать другу.

**Inversion:**
```python
def generate_gov_error(sentence, verb="помогать"):
    # 1. Find the verb's object
    obj = find_object(sentence, verb)  # "другу" (Dat)
    
    # 2. Look up what case is WRONG for this verb
    correct_case = GOV_DICT["помогать"]  # Dat
    wrong_cases = [c for c in ALL_CASES if c != correct_case]  # [Nom, Gen, Acc, Instr, Prep]
    
    # 3. Regenerate object in wrong case
    wrong_case = random.choice(wrong_cases)
    wrong_form = inflect(obj.lemma, wrong_case)  # "друга" (Gen) or "другом" (Instr)
    
    # 4. Return corrupted sentence
    return sentence.replace(obj.form, wrong_form)

# Input: "Я помогаю другу"
# Output: "Я помогаю друга" ❌ (Gen instead of Dat)
```

### Concrete Example: Generating an **Asp** Error

**Rule from Rozental:**
> После глаголов "начать", "продолжать", "кончить" употребляется инфинитив НСВ.

**Inversion:**
```python
ASP_TRIGGERS_NSV = ["начать", "начинать", "продолжать", "кончить", "бросить", "перестать"]
ASP_PAIRS = {
    "читать": "прочитать",
    "писать": "написать",
    "делать": "сделать",
    # ... from aspect pair dictionary
}

def generate_asp_error(sentence):
    # 1. Find trigger verb
    for trigger in ASP_TRIGGERS_NSV:
        if trigger in sentence:
            # 2. Find following infinitive
            inf = find_infinitive_after(sentence, trigger)
            if inf and inf in ASP_PAIRS:
                # 3. It should be НСВ, so substitute СВ
                wrong_form = ASP_PAIRS[inf]  # НСВ → СВ
                return sentence.replace(inf, wrong_form)
    return None

# Input: "Он начал читать книгу"
# Output: "Он начал прочитать книгу" ❌
```

### Concrete Example: Generating an **Infl** Error

**Rule from Zaliznjak:**
> Существительные класса 3a (мягкий согласный) образуют Gen.Pl с окончанием "-ей": гость → гостей.

**Inversion:**
```python
PARADIGM_ENDINGS = {
    "1a": {"gen_pl": "-ов"},   # стол → столов
    "3a": {"gen_pl": "-ей"},   # гость → гостей
    # ...
}

def generate_infl_error(word, target_form="gen_pl"):
    # 1. Get word's correct paradigm class
    correct_class = ZALIZNJAK[word]  # "гость" → "3a"
    
    # 2. Get a different class's ending
    wrong_class = random.choice([c for c in PARADIGM_ENDINGS if c != correct_class])
    wrong_ending = PARADIGM_ENDINGS[wrong_class][target_form]
    
    # 3. Apply wrong ending to stem
    stem = get_stem(word, correct_class)  # "гост-"
    wrong_form = stem + wrong_ending  # "гостов" ❌
    
    return wrong_form

# Input: "гость", target="gen_pl"
# Correct: "гостей"
# Output: "гостов" ❌ (applied class 1a ending instead of 3a)
```

---

## The Full Bridge Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERROR GENERATION PIPELINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Zaliznjak DB │    │  Gov Dict    │    │  Asp Pairs   │       │
│  │ (paradigms)  │    │ (verb→case)  │    │  (НСВ↔СВ)    │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         ▼                   ▼                   ▼                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   RULE LOOKUP LAYER                      │    │
│  │  "What is the correct form/pattern for this context?"    │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   INVERSION LAYER                        │    │
│  │  "Generate a form that violates this rule"               │    │
│  │                                                          │    │
│  │  • Gov: wrong case for this verb                         │    │
│  │  • Agr: mismatch gender/number/case/person               │    │
│  │  • Asp: wrong aspect for this context                    │    │
│  │  • Infl: wrong paradigm class ending                     │    │
│  │  • Morph: wrong derivational affix                       │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   OUTPUT + RLC TAG                       │    │
│  │  Corrupted sentence + error type label                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## What You Actually Need to Build

| Resource | Source | Format | Purpose |
|----------|--------|--------|---------|
| **Paradigm DB** | pymorphy2 / OpenCorpora | Python dict | Generate any inflected form |
| **Government Dict** | Extract from Розенталь "Управление в русском языке" | `{verb: (prep, case)}` | Know correct case for each verb |
| **Aspect Pairs** | RKI textbooks, Wiktionary | `{nsv: sv, sv: nsv}` | Swap aspects |
| **Collocation Dict** | ruscorpora.ru collocations | `{noun: [valid_verbs]}` | Generate collocation errors |
| **Preposition-Case** | Standard grammar | `{prep: [cases]}` | Know which cases each prep takes |
| **Context Triggers** | RKI grammars | `{trigger: required_aspect}` | Identify aspect-selecting contexts |

The **prescriptive grammars** (Rozental, ФИПИ) give you the **rules**. The **computational resources** (Zaliznjak/pymorphy2) give you the **machinery** to generate forms. The **RLC taxonomy** gives you the **labels** to tag your output.

