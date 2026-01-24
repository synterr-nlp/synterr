# Задачи для Артёма (v0.2.0)

Эти задачи не требуют глубоких лингвистических знаний — следуй существующим паттернам в коде.

## Что нового в v0.1.0

Перед началом работы ознакомься с новой архитектурой:

### Схемы (schemas)

Теперь synterr поддерживает **лингвистические схемы** — стандартные таксономии ошибок:

```bash
# Посмотреть доступные схемы
uv run synterr list-schemas

# Посмотреть покрытие RLC схемы текущими обработчиками
uv run synterr coverage --lang ru --schema rlc
```

Схемы определяют **что называть** ошибкой (теги: Ortho, Gov, Lex...), а обработчики определяют **как её генерировать**.

### Подтипы обработчиков (subtypes)

Каждый обработчик теперь объявляет свои **подтипы**:

```python
class SpellingErrorHandler:
    name = "spelling"
    subtypes = ["vowel_reduction", "keyboard", "devoicing", ...]  # НОВОЕ!
```

Подтипы маппятся на теги схемы в YAML файлах (`schemas/data/rlc.yaml`).

---

## Обзор задач

Тебе нужно реализовать **5 обработчиков ошибок**:

| Обработчик | Сложность | Ресурс | RLC тег |
|------------|-----------|--------|---------|
| `paronym` | Легко | paronyms.json ✅ готов | Lex |
| `preposition` | Легко | Создать prepositions.json | Prep |
| `conjunction` | Легко | Создать conjunctions.json | Conj |
| `word_omission` | Средне | — | Syntax+Miss |
| `word_insertion` | Средне | Создать fillers.json | Syntax+Extra |

После реализации RLC coverage вырастет с 25.7% до ~40%.

---

## Задача 1: Обработчик паронимов (`paronym`)

**Файл**: `src/synterr/languages/russian/errors/lexical.py` (создать)

**Логика**:
1. Проверить, есть ли слово в словаре паронимов
2. Если да — заменить на пароним

**Ресурс уже есть**: `src/synterr/data/russian/paronyms.json`

```python
from synterr.languages.russian.resources import get_paronyms

class ParonymHandler:
    name = "paronym"
    subtypes = ["paronym"]  # НОВОЕ: для маппинга на RLC тег Lex
    category = "OTHER"
    changes_length = False

    def __init__(self):
        self.paronyms = get_paronyms()

    def can_apply(self, tokens, idx):
        word = tokens[idx].lemma.lower()
        return word in self.paronyms

    def apply(self, tokens, sentence, idx, modified):
        word = tokens[idx].text
        lemma = tokens[idx].lemma.lower()

        # Выбрать случайный пароним
        alternatives = self.paronyms[lemma]
        new_word = random.choice(alternatives)

        # Заменить в предложении
        sentence[idx] = new_word

        return ErrorResult(
            error_type="paronym",
            category="OTHER",
            start_idx=idx,
            end_idx=idx,
            original=word,
            corrupted=new_word,
            fix_tag=f"$REPLACE_{word}",
        )
```

---

## Задача 2: Обработчик предлогов (`preposition`)

**Файл**: `src/synterr/languages/russian/errors/lexical.py`

**Сначала создай ресурс** `src/synterr/data/russian/prepositions.json`:

```json
{
  "_meta": {
    "description": "Группы семантически близких предлогов",
    "source": "manual curation"
  },
  "spatial": ["в", "на", "у", "около", "возле", "рядом с"],
  "direction_to": ["в", "на", "к"],
  "direction_from": ["из", "с", "от"],
  "temporal": ["в", "на", "за", "через", "после", "до"],
  "causal": ["из-за", "благодаря", "вследствие", "ввиду"]
}
```

**Логика**:
1. Проверить, является ли токен предлогом (POS == "ADP")
2. Найти группу, к которой он принадлежит
3. Заменить на другой предлог из той же группы

---

## Задача 3: Обработчик союзов (`conjunction`)

**Файл**: `src/synterr/languages/russian/errors/lexical.py`

**Создай ресурс** `src/synterr/data/russian/conjunctions.json`:

```json
{
  "_meta": {
    "description": "Пары смешиваемых союзов"
  },
  "pairs": {
    "а": ["но", "и"],
    "но": ["а", "однако"],
    "и": ["а", "да"],
    "что": ["чтобы"],
    "чтобы": ["что"],
    "потому что": ["поэтому", "так как"],
    "если": ["когда", "раз"]
  }
}
```

**Логика**: аналогично предлогам, но POS == "CCONJ" или "SCONJ"

---

## Задача 4: Пропуск слова (`word_omission`)

**Файл**: `src/synterr/languages/russian/errors/structural.py` (создать)

**ВАЖНО**: `changes_length = True`

**Логика**:
1. Найти служебное слово (предлог, частицу, союз)
2. Удалить его из предложения
3. Тег исправления: `$APPEND_слово` на предыдущем токене

```python
OMITTABLE_POS = {"ADP", "PART", "CCONJ", "SCONJ"}

class WordOmissionHandler:
    name = "word_omission"
    subtypes = ["word_omission"]  # Маппится на Syntax+Miss в RLC
    category = "OTHER"
    changes_length = True  # ВАЖНО!

    def can_apply(self, tokens, idx):
        # Не удалять первое слово
        if idx == 0:
            return False
        return tokens[idx].pos in OMITTABLE_POS

    def apply(self, tokens, sentence, idx, modified):
        deleted_word = sentence[idx]

        # Удаляем слово
        del sentence[idx]

        # Тег на ПРЕДЫДУЩИЙ токен
        return ErrorResult(
            error_type="word_omission",
            category="OTHER",
            start_idx=idx - 1,  # предыдущий токен!
            end_idx=idx - 1,
            original=deleted_word,
            corrupted="",
            fix_tag=f"$APPEND_{deleted_word}",
        )
```

---

## Задача 5: Вставка слова (`word_insertion`)

**Файл**: `src/synterr/languages/russian/errors/structural.py`

**Создай ресурс** `src/synterr/data/russian/fillers.json`:

```json
{
  "_meta": {
    "description": "Слова-паразиты для вставки"
  },
  "fillers": ["вот", "ну", "так", "это", "значит", "типа", "как бы", "ведь"]
}
```

**Логика**:
1. Выбрать случайную позицию
2. Вставить слово-паразит
3. Тег исправления: `$DELETE` на вставленном токене

```python
class WordInsertionHandler:
    name = "word_insertion"
    subtypes = ["word_insertion"]  # Маппится на Syntax+Extra в RLC
    category = "OTHER"
    changes_length = True  # ВАЖНО!

    def can_apply(self, tokens, idx):
        # Можно вставить после любого токена, кроме последнего
        return idx < len(tokens) - 1

    def apply(self, tokens, sentence, idx, modified):
        filler = random.choice(FILLERS)

        # Вставляем ПОСЛЕ текущего токена
        sentence.insert(idx + 1, filler)

        return ErrorResult(
            error_type="word_insertion",
            category="OTHER",
            start_idx=idx + 1,  # позиция вставленного
            end_idx=idx + 1,
            original="",
            corrupted=filler,
            fix_tag="$DELETE",
        )
```

---

## Регистрация обработчиков

После создания добавь в `src/synterr/languages/russian/errors/__init__.py`:

```python
from synterr.languages.russian.errors.lexical import (
    ParonymHandler,
    PrepositionHandler,
    ConjunctionHandler,
)
from synterr.languages.russian.errors.structural import (
    WordOmissionHandler,
    WordInsertionHandler,
)

ALL_HANDLERS = [
    # ... существующие ...
    ParonymHandler(),
    PrepositionHandler(),
    ConjunctionHandler(),
    WordOmissionHandler(),
    WordInsertionHandler(),
]
```

---

## Тестирование

Для каждого обработчика создай тесты в `tests/test_languages/test_russian/test_lexical.py`:

```python
class TestParonymHandler:
    def test_implements_protocol(self):
        handler = ParonymHandler()
        assert hasattr(handler, "name")
        assert hasattr(handler, "category")
        assert hasattr(handler, "changes_length")
        assert hasattr(handler, "can_apply")
        assert hasattr(handler, "apply")

    def test_can_apply_finds_paronyms(self):
        # ...

    def test_apply_substitutes_correctly(self):
        # ...
```

---

## Команды для работы

```bash
# Установка зависимостей
uv sync --all-extras

# Запуск тестов
uv run pytest -v

# Проверка линтером
uv run ruff check src tests

# Тест CLI
uv run synterr list-errors --lang ru
```

---

## После реализации: обнови маппинги схемы

После добавления обработчиков, добавь их в RLC схему:

**Файл:** `src/synterr/schemas/data/rlc.yaml`

```yaml
mappings:
  # ... существующие ...

  # Твои новые обработчики:
  paronym:
    primary: Lex
  preposition:
    primary: Prep
  conjunction:
    primary: Conj
  word_omission:
    primary: Syntax
    modifier: Miss
  word_insertion:
    primary: Syntax
    modifier: Extra
```

Проверь, что покрытие выросло:

```bash
uv run synterr coverage --lang ru --schema rlc
# Должно показать ~40% вместо 25.7%
```

---

## Вопросы?

Если что-то непонятно:
1. Посмотри существующие обработчики в `errors/spelling.py` и `errors/morphological.py`
2. Прочитай `CONTRIBUTING.ru.md`
3. Посмотри как устроены схемы в `src/synterr/schemas/`
4. Спроси Анну
