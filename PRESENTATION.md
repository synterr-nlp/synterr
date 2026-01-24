# synterr v0.1.0
## Генератор синтетических ошибок для GEC

*Анна Смирнова | Январь 2026*

---

# Проблема

**GEC (Grammatical Error Correction)** требует размеченных данных:

```
Исходное:  Мама мыла ра|му|.
Ошибочное: Мама мыла ра|ме|.
Метка:     $TRANSFORM_CASE_Acc
```

**Проблема**: ручная разметка дорогая, корпуса маленькие

| Корпус | Предложений | Ошибок |
|--------|-------------|--------|
| RULEC-GEC | 12,480 | 11,847 |
| GERA | 6,681 | 5,988 |

**Решение**: синтетическая генерация ошибок из чистого текста

---

# synterr: Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              synterr v0.1.0                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   SCHEMAS   │    │   CONFIGS   │    │  LANGUAGES  │                 │
│  │  (taxonomy) │    │  (weights)  │    │ (handlers)  │                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         │                  │                  │                         │
│         ▼                  ▼                  ▼                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         PIPELINE                                 │   │
│  │  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐  │   │
│  │  │ Analyzer│──▶│ Handlers │──▶│ Formatter│──▶│ GECToR Output │  │   │
│  │  │ (stanza)│   │ (errors) │   │ (tags)   │   │    (.edits)   │  │   │
│  │  └─────────┘   └──────────┘   └──────────┘   └───────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

     SCHEMAS                    CONFIGS                   LANGUAGES
  ┌───────────┐              ┌───────────┐             ┌───────────┐
  │ synterr   │              │ rulec     │             │ russian   │
  │ (14 тегов)│              │ gera      │             │  └─errors/│
  ├───────────┤              │ balanced  │             │    ├─spell│
  │ rlc       │              └───────────┘             │    └─morph│
  │ (35 тегов)│                                        └───────────┘
  └───────────┘
```

---

# Ключевое разделение

## Схемы vs Конфиги vs Обработчики

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   HANDLERS          SCHEMAS              CONFIGS                    │
│   (КАК портить)     (КАК НАЗВАТЬ)        (КАК ЧАСТО)               │
│                                                                     │
│   ┌───────────┐     ┌───────────┐        ┌───────────┐             │
│   │vowel_     │────▶│ Ortho     │        │spelling:  │             │
│   │reduction  │     │           │        │  0.475    │             │
│   └───────────┘     └───────────┘        └───────────┘             │
│                                                                     │
│   ┌───────────┐     ┌───────────┐        ┌───────────┐             │
│   │noun_case  │────▶│ Gov       │        │noun_case: │             │
│   │           │     │           │        │  0.280    │             │
│   └───────────┘     └───────────┘        └───────────┘             │
│                                                                     │
│   ┌───────────┐     ┌───────────┐        ┌───────────┐             │
│   │adj_gender │────▶│ AgrGender │        │adj_gender:│             │
│   │           │     │           │        │  0.027    │             │
│   └───────────┘     └───────────┘        └───────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

# Схемы: RLC (Russian Learner Corpus)

**35 первичных тегов + 3 модификатора**

```yaml
# src/synterr/schemas/data/rlc.yaml

primary_tags:
  # SPELLING (5 тегов)
  Ortho:    "Нарушение орфографии"      # детекция: SPELL
  Misspell: "Сложные орфогр. ошибки"    # детекция: SPELL

  # MORPHOLOGY (14 тегов)
  Gov:      "Управление (выбор падежа)" # детекция: MORPH
  AgrCase:  "Согласование по падежу"    # детекция: MORPH
  AgrGender:"Согласование по роду"      # детекция: MORPH
  Tense:    "Ошибки во времени глагола" # детекция: MORPH

  # LEXICAL (7 тегов)
  Lex:      "Лексические ошибки"        # детекция: OTHER
  Prep:     "Ошибки в предлогах"        # детекция: OTHER
  Conj:     "Ошибки в союзах"           # детекция: OTHER

modifiers:
  Miss:     "Пропуск элемента"          # Ref+Miss, Syntax+Miss
  Extra:    "Лишний элемент"            # Space+Extra
  Transfer: "Интерференция L1"          # Lex+Transfer
```

---

# Схемы: Композиционность

**Модификаторы комбинируются с тегами**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   PRIMARY TAG          +    MODIFIER    =    COMBINED TAG       │
│                                                                 │
│   ┌─────────┐              ┌───────┐        ┌─────────────┐    │
│   │   Ref   │      +       │ Miss  │   =    │  Ref+Miss   │    │
│   │(местоим)│              │(пропущ)│       │             │    │
│   └─────────┘              └───────┘        └─────────────┘    │
│                                                                 │
│   ┌─────────┐              ┌───────┐        ┌─────────────┐    │
│   │ Syntax  │      +       │ Extra │   =    │Syntax+Extra │    │
│   │         │              │(лишний)│       │             │    │
│   └─────────┘              └───────┘        └─────────────┘    │
│                                                                 │
│   ┌─────────┐              ┌────────┐       ┌─────────────┐    │
│   │   Lex   │      +       │Transfer│  =    │Lex+Transfer │    │
│   │         │              │(L1)    │       │             │    │
│   └─────────┘              └────────┘       └─────────────┘    │
│                                                                 │
│   35 primary × 3 modifiers = до 57+ комбинаций в корпусе       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# Маппинг: Подтипы → Теги схемы

```yaml
# src/synterr/schemas/data/rlc.yaml

mappings:
  # SpellingErrorHandler subtypes
  vowel_reduction:
    primary: Ortho           # "карова" → SPELL
  devoicing:
    primary: Ortho           # "гриб" → "грип"
  keyboard:
    primary: Misspell        # опечатки

  # Morphological handlers
  noun_case:
    primary: Gov             # управление падежом
  adj_case:
    primary: AgrCase         # согласование по падежу
  adj_gender:
    primary: AgrGender       # согласование по роду

  # Artem's future handlers
  word_omission:
    primary: Syntax
    modifier: Miss           # → Syntax+Miss
  word_insertion:
    primary: Syntax
    modifier: Extra          # → Syntax+Extra
```

---

# Обработчики: Протокол

```python
# src/synterr/core/protocol.py

class ErrorHandler(Protocol):
    """Протокол обработчика ошибок."""

    name: str                    # "spelling", "noun_case"
    subtypes: list[str]          # ["vowel_reduction", "keyboard", ...]
    category: str                # "SPELL", "MORPH", "OTHER"
    changes_length: bool         # True для insert/delete

    def can_apply(
        self,
        tokens: Sequence[AnalyzedToken],
        idx: int
    ) -> bool:
        """Можно ли применить к токену idx?"""
        ...

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        """Применить ошибку, вернуть результат."""
        ...
```

---

# Обработчики: SpellingErrorHandler

```python
# src/synterr/languages/russian/errors/spelling.py

class SpellingErrorHandler:
    name = "spelling"
    subtypes = [
        "vowel_reduction",   # карова → корова (редукция)
        "devoicing",         # гриб → грип (оглушение)
        "tsa_confusion",     # цыган → циган (ц/ци)
        "cluster",           # солнце → сонце (непроизн.)
        "double_consonant",  # касса → каса
        "soft_sign",         # мышь → мыш
        "keyboard",          # привет → прмвет
    ]
    category = "SPELL"
    changes_length = False

    def apply(self, tokens, sentence, idx, modified):
        token = tokens[idx]

        # Выбираем тип ошибки с весами
        error_type = self._sample_error_type()

        if error_type == "vowel_reduction":
            corrupted = self._apply_vowel_reduction(token.text)
        elif error_type == "keyboard":
            corrupted = self._apply_keyboard_typo(token.text)
        # ...

        return ErrorResult(
            error_type=f"spelling_{error_type}",  # для маппинга
            category=self.category,
            start_idx=idx,
            original=token.text,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{token.text}",
        )
```

---

# Фонетические ошибки: Редукция гласных

```python
# Безударные гласные редуцируются

VOWEL_REDUCTION = {
    "о": "а",  # молоко → малако (безударная о → а)
    "е": "и",  # весна → висна
    "я": "и",  # пятак → питак
}

def _apply_vowel_reduction(self, word: str) -> str | None:
    # 1. Находим ударение
    stress_pos = self.stress_dict.get(word.lower())
    if stress_pos is None:
        return None

    # 2. Заменяем ТОЛЬКО безударные гласные
    result = list(word)
    vowel_idx = 0

    for i, char in enumerate(word):
        if char.lower() in "аеёиоуыэюя":
            if vowel_idx != stress_pos:  # безударная
                if char.lower() in VOWEL_REDUCTION:
                    result[i] = VOWEL_REDUCTION[char.lower()]
            vowel_idx += 1

    return "".join(result)

# Примеры:
# молоко́ (ударение на 3) → малако (о→а в позициях 1,2)
# ко́шка (ударение на 1) → кошка (без изменений)
```

---

# Pipeline: Генерация

```python
# src/synterr/core/pipeline.py

class ErrorPipeline:
    def generate(self, text: str) -> GeneratedSentence:
        # 1. Морфологический анализ (stanza)
        tokens = self.analyzer.analyze(text)
        # [AnalyzedToken(text="Мама", pos="NOUN", Case="Nom"), ...]

        # 2. Выбор обработчиков по весам
        sentence = [t.text for t in tokens]
        errors = []

        for _ in range(self.config.max_errors_per_sentence):
            handler = self._sample_error_type()  # по весам

            # 3. Находим применимые позиции
            applicable = [i for i in range(len(tokens))
                          if handler.can_apply(tokens, i)]

            if applicable:
                idx = random.choice(applicable)
                result = handler.apply(tokens, sentence, idx, modified)
                if result:
                    errors.append(result)

        # 4. Форматирование в GECToR формат
        return GeneratedSentence(
            original_tokens=[t.text for t in tokens],
            corrupted_tokens=sentence,
            errors=errors,
            formatted=self._format_output(sentence, errors),
        )
```

---

# Выходной формат: GECToR

```
$STARTSEPL|||SEPR$KEEP:CORRECT МамаSEPL|||SEPR$KEEP:CORRECT мылаSEPL|||SEPR
$REPLACE_раму:MORPH рамеSEPL|||SEPR$KEEP:CORRECT .
```

**Структура токена:**
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   $REPLACE_раму  :  MORPH    раме                          │
│   ─────────────     ─────    ────                          │
│        │              │        │                            │
│   correction      detection  corrupted                      │
│      tag          category    token                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Detection categories:
  CORRECT  - нет ошибки
  SPELL    - орфография
  MORPH    - морфология
  OTHER    - лексика, структура
```

---

# CLI: Команды

```bash
# Список языков
$ synterr list-languages
ru: Russian

# Список схем
$ synterr list-schemas
  rlc: Russian Learner Corpus (35 tags)
  synterr (default): Synterr native (14 tags)

# Покрытие схемы
$ synterr coverage --lang ru --schema rlc
Coverage: 9/35 tags (25.7%)
Covered: AgrCase, AgrGender, AgrNum, AgrPers, Gov,
         Misspell, Num, Ortho, Tense
Uncovered: Lex, Prep, Conj, Asp, Refl, WO, ...

# Генерация с пресетом
$ synterr generate --lang ru --preset rulec \
    --schema rlc \
    -i corpus.txt -o train.edits

# Генерация с кастомными весами
$ synterr generate --lang ru \
    -w '{"spelling": 0.8, "noun_case": 0.2}' \
    -i corpus.txt -o train.edits
```

---

# Покрытие RLC: Текущее состояние

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RLC SCHEMA COVERAGE: 25.7%                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  COVERED (9 tags)                 UNCOVERED (26 tags)               │
│  ═══════════════                  ═══════════════════               │
│                                                                     │
│  ✓ Ortho      (spelling)         ✗ Lex       (paronym)  ← Артём    │
│  ✓ Misspell   (spelling)         ✗ Prep      (prepos.)  ← Артём    │
│  ✓ Gov        (noun_case)        ✗ Conj      (conjunc.) ← Артём    │
│  ✓ Num        (noun_number)      ✗ Syntax    (+Miss/Extra) ← Артём │
│  ✓ AgrCase    (adj_case)         ✗ Asp       (aspect)              │
│  ✓ AgrNum     (adj_number)       ✗ Refl      (reflexive)           │
│  ✓ AgrGender  (adj_gender)       ✗ WO        (word order)          │
│  ✓ AgrPers    (verb_p_n)         ✗ Passive   (passive)             │
│  ✓ Tense      (verb_tense)       ✗ ... (18 more)                   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  После задач Артёма: ~40% coverage (+5 handlers)                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

# Задачи Артёма (v0.2.0)

| Обработчик | RLC тег | Сложность | Ресурс |
|------------|---------|-----------|--------|
| `paronym` | Lex | Легко | paronyms.json ✅ |
| `preposition` | Prep | Легко | prepositions.json |
| `conjunction` | Conj | Легко | conjunctions.json |
| `word_omission` | Syntax+Miss | Средне | — |
| `word_insertion` | Syntax+Extra | Средне | fillers.json |

```python
# Пример: ParonymHandler
class ParonymHandler:
    name = "paronym"
    subtypes = ["paronym"]      # → Lex в RLC
    category = "OTHER"
    changes_length = False

    def can_apply(self, tokens, idx):
        lemma = tokens[idx].lemma.lower()
        return lemma in self.paronyms  # одеть/надеть, ...

    def apply(self, tokens, sentence, idx, modified):
        # Заменяем на пароним
        alternatives = self.paronyms[tokens[idx].lemma]
        sentence[idx] = random.choice(alternatives)
        # ...
```

---

# Roadmap: Версии

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  v0.1.0 (текущая)     v0.2.0 (Артём)      v0.3.0+                  │
│  ═══════════════      ══════════════      ═══════                   │
│                                                                     │
│  ✓ Схемы (RLC)        □ paronym           □ Agreement (depparse)   │
│  ✓ Subtypes           □ preposition       □ Government             │
│  ✓ Spelling fix       □ conjunction       □ Aspect                 │
│  ✓ 8 handlers         □ word_omission     □ Reflexives             │
│                       □ word_insertion                              │
│                                                                     │
│  Coverage: 25.7%      Coverage: ~40%      Coverage: >60%           │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  v1.0.0 — PyPI release                                             │
│  ═══════════════════════                                            │
│                                                                     │
│  □ Coverage >90% of learner corpus errors                          │
│  □ Benchmarked on RULEC-GEC test set                               │
│  □ Full documentation                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

# Использование в GECToR

```bash
# 1. Генерация синтетических данных
synterr generate --lang ru --preset rulec \
    -i ~/corpora/lenta.txt \
    -o train_lenta.edits \
    --max-sentences 100000

# 2. Обучение GECToR
cd fast-gector
python train.py \
    --train ../train_lenta.edits \
    --val data/RULEC-GEC.dev.edits \
    --model ai-forever/ruRoberta-large

# 3. Инференс
python predict.py \
    --model_path ckpts/best \
    --input test.txt \
    --output corrected.txt
```

**Гипотеза**: stanza + структурированные ошибки → лучше качество GEC

---

# Итоги

## Что сделано в v0.1.0

1. **Pluggable schemas** — RLC (35 тегов), synterr (14 тегов)
2. **Handler subtypes** — маппинг подтипов на теги схемы
3. **Stress-based spelling** — корректная редукция гласных
4. **Clear separation** — schemas ≠ configs ≠ handlers

## Метрики

- 8 обработчиков, 12 подтипов
- RLC coverage: 25.7% → 40% (после Артёма)
- ~3.6k LOC Python

## Следующие шаги

- Артём: 5 новых обработчиков (v0.2.0)
- Анна: Agreement/Government (v0.3.0)
- Бенчмарк на RULEC-GEC

---

# Вопросы?

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   Repository:  https://github.com/mechanicpanic/synterr             │
│                                                                     │
│   Docs:        CONTRIBUTING.ru.md                                   │
│                docs/ARTEM_TASKS.md                                  │
│                VERSIONING.md                                        │
│                                                                     │
│   CLI:         synterr --help                                       │
│                synterr list-schemas                                 │
│                synterr coverage --lang ru --schema rlc              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
