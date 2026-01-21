# Руководство для разработчиков synterr

Это руководство описывает архитектуру проекта и процесс разработки. Если у тебя есть вопросы — спрашивай!

## Содержание

1. [Установка и настройка](#установка-и-настройка)
2. [Архитектура проекта](#архитектура-проекта)
3. [Основные концепции](#основные-концепции)
4. [Как добавить новый тип ошибки](#как-добавить-новый-тип-ошибки)
5. [Тестирование](#тестирование)
6. [Стиль кода](#стиль-кода)
7. [Git workflow](#git-workflow)

---

## Установка и настройка

### Требования
- Python 3.11+
- uv (менеджер пакетов)

### Установка для разработки

```bash
# Клонируем репозиторий
git clone https://github.com/mechanicpanic/synterr.git
cd synterr

# Устанавливаем все зависимости (включая dev и russian)
uv sync --all-extras

# Проверяем, что всё работает
uv run pytest -v
uv run ruff check src tests
```

### Полезные команды

```bash
# Запуск тестов
uv run pytest -v

# Проверка стиля кода (линтер)
uv run ruff check src tests

# Автоматическое исправление ошибок линтера
uv run ruff check --fix src tests

# Форматирование кода
uv run ruff format src tests

# Запуск CLI
uv run synterr --help
uv run synterr list-languages
uv run synterr list-errors --lang ru
```

---

## Архитектура проекта

```
synterr/
├── src/synterr/
│   ├── __init__.py           # Экспорты пакета
│   ├── cli.py                # Командная строка (Click)
│   ├── core/                 # Ядро (не зависит от языка)
│   │   ├── protocol.py       # Протоколы и dataclass'ы
│   │   ├── registry.py       # Реестр языков
│   │   └── pipeline.py       # Пайплайн генерации ошибок
│   ├── configs/              # YAML конфигурации
│   │   └── russian/          # Пресеты для русского
│   ├── analysis/             # Анализ бенчмарков
│   └── languages/            # Поддержка языков
│       └── russian/          # Русский язык
│           ├── analyzer.py   # Морфологический анализ (stanza)
│           ├── inflector.py  # Словоизменение (pymorphy3)
│           ├── resources.py  # Словари, списки слов
│           └── errors/       # Обработчики ошибок
│               ├── spelling.py      # Орфографические
│               └── morphological.py # Морфологические
├── tests/                    # Тесты
├── data/                     # Ресурсы (JSON, etc.)
└── configs/                  # Пользовательские конфиги
```

---

## Основные концепции

### 1. Протоколы (Protocol)

Протоколы — это интерфейсы в Python. Они определяют, какие методы и атрибуты должен иметь класс.

**Файл:** `src/synterr/core/protocol.py`

```python
# AnalyzedToken — токен после морфологического анализа
@dataclass
class AnalyzedToken:
    text: str           # Оригинальный текст: "книгу"
    lemma: str          # Лемма: "книга"
    pos: str            # Часть речи (Universal POS): "NOUN"
    features: dict      # Морф. признаки: {"Case": "Acc", "Number": "Sing"}
    idx: int            # Индекс в предложении
    extra: dict         # Дополнительно (pymorphy parse, etc.)

# ErrorResult — результат применения ошибки
@dataclass
class ErrorResult:
    error_type: str     # Тип ошибки: "noun_case"
    category: str       # Категория: "MORPH", "SPELL", "OTHER"
    start_idx: int      # Начало (индекс токена)
    end_idx: int        # Конец
    original: str       # Оригинал: "книгу"
    corrupted: str      # С ошибкой: "книга"
    fix_tag: str        # Тег исправления: "$TRANSFORM_CASE_Acc"

# ErrorHandler — протокол обработчика ошибок
class ErrorHandler(Protocol):
    name: str              # Имя: "noun_case"
    category: str          # Категория: "MORPH"
    changes_length: bool   # Меняет ли длину предложения?

    def can_apply(self, tokens, idx) -> bool:
        """Можно ли применить ошибку к токену idx?"""
        ...

    def apply(self, tokens, sentence, idx, modified) -> ErrorResult | None:
        """Применить ошибку. Вернуть ErrorResult или None."""
        ...
```

### 2. Пайплайн генерации

**Файл:** `src/synterr/core/pipeline.py`

```python
from synterr.core.pipeline import ErrorPipeline, GenerationConfig

# Создаём конфигурацию
config = GenerationConfig(
    error_probability=0.7,      # Вероятность ошибки в предложении
    max_errors_per_sentence=3,  # Макс. ошибок на предложение
    error_weights={             # Веса типов ошибок
        "spelling": 0.5,
        "noun_case": 0.3,
        "verb_tense": 0.2,
    },
)

# Создаём пайплайн
pipeline = ErrorPipeline("ru", config)

# Генерируем ошибку
result = pipeline.generate("Мама мыла раму.")
print(result.corrupted_tokens)  # ['Мама', 'мыла', 'раме', '.']
print(result.errors)            # [ErrorResult(error_type='noun_case', ...)]
```

### 3. Реестр языков

Языки регистрируются через entry points в `pyproject.toml`:

```toml
[project.entry-points."synterr.languages"]
russian = "synterr.languages.russian:RussianLanguage"
```

Это позволяет автоматически находить языковые модули при импорте.

---

## Как добавить новый тип ошибки

### Шаг 1: Создай класс обработчика

**Файл:** `src/synterr/languages/russian/errors/my_error.py`

```python
from synterr.core.protocol import AnalyzedToken, ErrorResult

class MyErrorHandler:
    """Описание моего типа ошибки."""

    # Обязательные атрибуты
    name = "my_error"        # Уникальное имя
    category = "OTHER"       # SPELL, MORPH, PUNCT, или OTHER
    changes_length = False   # True если добавляет/удаляет токены

    def can_apply(self, tokens: list[AnalyzedToken], idx: int) -> bool:
        """Проверяем, можно ли применить ошибку к токену idx."""
        token = tokens[idx]

        # Пример: только для существительных
        if token.pos != "NOUN":
            return False

        # Другие проверки...
        return True

    def apply(
        self,
        tokens: list[AnalyzedToken],
        sentence: list[str],
        idx: int,
        modified: set[int],
    ) -> ErrorResult | None:
        """Применяем ошибку."""
        token = tokens[idx]
        original = sentence[idx]

        # Генерируем испорченное слово
        corrupted = self._corrupt_word(token)

        if corrupted is None or corrupted == original:
            return None  # Не удалось применить

        # Изменяем предложение
        sentence[idx] = corrupted
        modified.add(idx)

        return ErrorResult(
            error_type=self.name,
            category=self.category,
            start_idx=idx,
            end_idx=idx + 1,
            original=original,
            corrupted=corrupted,
            fix_tag=f"$REPLACE_{original}",
        )

    def _corrupt_word(self, token: AnalyzedToken) -> str | None:
        """Логика порчи слова."""
        # Твой код здесь
        pass
```

### Шаг 2: Зарегистрируй обработчик

**Файл:** `src/synterr/languages/russian/errors/__init__.py`

```python
def get_all_handlers() -> list[ErrorHandler]:
    from .spelling import SpellingErrorHandler
    from .morphological import NounCaseErrorHandler, ...
    from .my_error import MyErrorHandler  # <-- Добавь импорт

    return [
        SpellingErrorHandler(),
        NounCaseErrorHandler(),
        # ...
        MyErrorHandler(),  # <-- Добавь в список
    ]
```

### Шаг 3: Добавь вес в конфигурацию

**Файл:** `src/synterr/configs/russian/rulec.yaml`

```yaml
weights:
  spelling: 0.475
  noun_case: 0.280
  my_error: 0.05  # <-- Добавь вес
```

### Шаг 4: Напиши тесты

**Файл:** `tests/test_languages/test_russian/test_my_error.py`

```python
from synterr.core.protocol import AnalyzedToken, ErrorHandler
from synterr.languages.russian.errors.my_error import MyErrorHandler


class TestMyErrorHandler:
    def test_implements_protocol(self):
        handler = MyErrorHandler()
        assert isinstance(handler, ErrorHandler)
        assert handler.name == "my_error"
        assert handler.category == "OTHER"

    def test_can_apply(self):
        handler = MyErrorHandler()
        tokens = [
            AnalyzedToken(text="книга", lemma="книга", pos="NOUN", features={}, idx=0),
            AnalyzedToken(text="читать", lemma="читать", pos="VERB", features={}, idx=1),
        ]
        assert handler.can_apply(tokens, 0) is True   # NOUN — да
        assert handler.can_apply(tokens, 1) is False  # VERB — нет
```

---

## Тестирование

### Запуск всех тестов

```bash
uv run pytest -v
```

### Запуск конкретного теста

```bash
# Один файл
uv run pytest tests/test_core/test_protocol.py -v

# Один класс
uv run pytest tests/test_core/test_protocol.py::TestAnalyzedToken -v

# Один тест
uv run pytest tests/test_core/test_protocol.py::TestAnalyzedToken::test_create_token -v
```

### Запуск с coverage

```bash
uv run pytest --cov=src/synterr --cov-report=html
# Открой htmlcov/index.html в браузере
```

---

## Стиль кода

Мы используем **ruff** для линтинга и форматирования.

### Перед коммитом ОБЯЗАТЕЛЬНО:

```bash
# Проверка линтера
uv run ruff check src tests

# Автоисправление
uv run ruff check --fix src tests

# Форматирование
uv run ruff format src tests
```

### Основные правила

1. **Типизация** — используй type hints везде:
   ```python
   def process(text: str, count: int = 10) -> list[str]:
       ...
   ```

2. **Docstrings** — для публичных функций и классов:
   ```python
   def analyze(text: str) -> list[AnalyzedToken]:
       """Анализирует текст и возвращает токены.

       Args:
           text: Входной текст

       Returns:
           Список проанализированных токенов
       """
   ```

3. **Именование**:
   - Классы: `CamelCase` — `NounCaseErrorHandler`
   - Функции/переменные: `snake_case` — `can_apply`, `error_type`
   - Константы: `UPPER_CASE` — `CATEGORY_MORPH`

---

## Git workflow

### Перед началом работы

```bash
# Обновись с main
git checkout master
git pull origin master

# Создай ветку для своей задачи
git checkout -b feature/my-feature
```

### Коммиты

```bash
# Добавь файлы
git add src/synterr/languages/russian/errors/my_error.py
git add tests/test_languages/test_russian/test_my_error.py

# Проверь что добавляешь
git status
git diff --staged

# Коммит с понятным сообщением
git commit -m "Add my_error handler for X type errors"
```

### Хорошие сообщения коммитов

```
✅ Add noun_case error handler
✅ Fix vowel reduction for unstressed syllables
✅ Update RULEC weights based on corpus analysis

❌ fix
❌ changes
❌ asdf
```

### Pull Request

```bash
# Отправь ветку
git push -u origin feature/my-feature

# Создай PR через GitHub или:
gh pr create --title "Add my_error handler" --body "Description here"
```

---

## Полезные ссылки

- **Universal POS tags**: https://universaldependencies.org/u/pos/
- **Universal Features**: https://universaldependencies.org/u/feat/
- **pymorphy3**: https://pymorphy2.readthedocs.io/ (документация для pymorphy2, но API похож)
- **stanza**: https://stanfordnlp.github.io/stanza/

---

## Вопросы?

Если что-то непонятно — спрашивай! Лучше спросить, чем сделать неправильно и потом переделывать.
