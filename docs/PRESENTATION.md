# synterr v0.1.2
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

| Корпус | Предложений | Ошибок | Источник |
|--------|-------------|--------|----------|
| RULEC-GEC | 12,480 | 11,847 | L2/heritage learners |
| GERA | 6,681 | 5,988 | Russian school texts |

**Решение**: синтетическая генерация ошибок из чистого текста

---

# Подходы к синтетической генерации

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   C4_200M (Google)                    synterr                           │
│   ════════════════                    ═══════                           │
│                                                                         │
│   Neural seq2seq                      Rule-based handlers               │
│   ┌─────────────────┐                 ┌─────────────────┐              │
│   │ Clean + Tag ──▶ │                 │ Clean ──▶ Stanza│              │
│   │   [Transformer] │                 │    ──▶ Handler  │              │
│   │      ──▶ Error  │                 │    ──▶ Error    │              │
│   └─────────────────┘                 └─────────────────┘              │
│                                                                         │
│   ✓ Learns from data                  ✓ Interpretable                  │
│   ✓ 200M pairs                        ✓ Controllable                   │
│   ✗ Black-box                         ✓ Linguistically grounded        │
│   ✗ Fixed after training              ✓ Schema-aware (RLC tags)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# synterr: Архитектура верхнего уровня

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              synterr v0.1.2                             │
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
```

---

# Структура пакета

```
src/synterr/
├── core/
│   ├── protocol.py      # AnalyzedToken, ErrorResult, ErrorHandler Protocol
│   ├── pipeline.py      # ErrorPipeline, GenerationConfig, GeneratedSentence
│   └── registry.py      # Language discovery via entry_points
├── schemas/
│   ├── loader.py        # Schema, SchemaTag, SchemaModifier, SubtypeMapping
│   └── data/
│       ├── synterr.yaml # 14 tags (backward compat)
│       └── rlc.yaml     # 35 primary + 3 modifiers
├── configs/
│   └── russian/
│       ├── rulec.yaml   # RULEC-GEC distribution
│       ├── gera.yaml    # GERA distribution
│       └── balanced.yaml
└── languages/
    └── russian/
        ├── analyzer.py   # RussianAnalyzer (backend dispatcher)
        ├── inflector.py  # pymorphy3 wrapper + capitalization
        ├── resources.py  # Stress dict, paronyms, etc.
        ├── backends/
        │   ├── stanza_backend.py   # Default, SynTagRus-trained
        │   ├── natasha_backend.py  # Fast, lightweight
        │   └── spacy_backend.py    # spacy-ru
        └── errors/
            ├── spelling.py         # 8 subtypes
            └── morphological.py    # 7 handlers
```

---

# Core: AnalyzedToken

```python
# src/synterr/core/protocol.py

@dataclass
class AnalyzedToken:
    """Token after morphological analysis."""

    text: str                    # Original form: "книгу"
    lemma: str                   # Lemma: "книга"
    pos: str                     # Universal POS: "NOUN"
    features: dict[str, str]     # {"Case": "Acc", "Number": "Sing", "Gender": "Fem"}
    idx: int                     # Position in sentence
    head_idx: int | None = None  # Dependency head (if depparse enabled)
    dep_rel: str | None = None   # Dependency relation: "obj", "nsubj", etc.
    extra: dict = field(default_factory=dict)  # pymorphy3 parse object

    def get_feature(self, name: str, default: str | None = None) -> str | None:
        return self.features.get(name, default)

    def has_feature(self, name: str) -> bool:
        return name in self.features

# Features follow Universal Dependencies:
# Case: Nom, Gen, Dat, Acc, Ins, Loc
# Number: Sing, Plur
# Gender: Masc, Fem, Neut
# Person: 1, 2, 3
# Tense: Past, Pres, Fut
```

---

# Core: ErrorResult

```python
# src/synterr/core/protocol.py

@dataclass
class ErrorResult:
    """Result of applying an error to a sentence."""

    error_type: str      # "noun_case", "spelling_vowel_reduction"
    category: str        # "MORPH", "SPELL", "OTHER"
    start_idx: int       # Token start index
    end_idx: int         # Token end index (exclusive)
    original: str        # Original token: "раму"
    corrupted: str       # Corrupted token: "раме"
    fix_tag: str         # GECToR tag: "$TRANSFORM_CASE_Acc"

# Fix tag types:
#   $KEEP                    - no change needed
#   $DELETE                  - remove this token
#   $REPLACE_<word>          - replace with <word>
#   $TRANSFORM_CASE_<case>   - inflect to <case>
#   $TRANSFORM_NUMBER_<num>  - inflect to <num>
#   $APPEND_<word>           - append <word> after this token
#   $MERGE_<word>            - merge with next token
```

---

# Core: ErrorHandler Protocol

```python
# src/synterr/core/protocol.py

class ErrorHandler(Protocol):
    """Protocol for error handlers (structural subtyping)."""

    name: str                    # Handler name: "noun_case"
    subtypes: list[str]          # Error subtypes for schema mapping
    category: str                # Detection category: "MORPH"
    changes_length: bool         # True if handler adds/removes tokens

    def can_apply(
        self,
        tokens: Sequence[AnalyzedToken],
        idx: int
    ) -> bool:
        """Check if error can be applied at position idx.

        Must be pure (no side effects) and fast.
        Called for every token in every sentence.
        """
        ...

    def apply(
        self,
        tokens: Sequence[AnalyzedToken],
        sentence: list[str],       # Mutable! Modified in-place
        idx: int,
        modified: set[int],        # Already-modified indices
    ) -> ErrorResult | None:
        """Apply error and return result, or None if failed."""
        ...
```

---

# Backend: Морфологический анализ

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ANALYSIS PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  "Мама мыла раму"                                                      │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  STANZA (Neural, SynTagRus-trained)                             │   │
│  │  ════════════════════════════════════                           │   │
│  │  - Tokenization (razdel)                                        │   │
│  │  - POS tagging (UPOS)                                           │   │
│  │  - Morphological features (Case, Number, Gender, Tense, etc.)   │   │
│  │  - Lemmatization                                                │   │
│  │  - Dependency parsing (optional, ~40% slower)                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  PYMORPHY3 (Rule-based, Zaliznyak dictionary)                   │   │
│  │  ════════════════════════════════════════════                   │   │
│  │  - Parse object attached to token.extra["pymorphy_parse"]       │   │
│  │  - Used for INFLECTION only (not analysis)                      │   │
│  │  - 400k+ paradigms from OpenCorpora                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         │                                                               │
│         ▼                                                               │
│  [AnalyzedToken(text="раму", pos="NOUN", Case="Acc", ...), ...]        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# Backend: Выбор

```python
# src/synterr/languages/russian/backends/__init__.py

BACKENDS = {
    "stanza": StanzaBackend,    # Default
    "natasha": NatashaBackend,  # Fast
    "spacy": SpacyBackend,      # Alternative
}

DEFAULT_BACKEND = "stanza"

# Performance comparison (sentences/sec on M4 Pro):
#
# ┌──────────┬──────────┬──────────┬──────────┬──────────────────────────┐
# │ Backend  │ Single   │ Batch    │ Accuracy │ Notes                    │
# ├──────────┼──────────┼──────────┼──────────┼──────────────────────────┤
# │ stanza   │ ~75/s    │ ~500/s   │ Best     │ SynTagRus-trained neural │
# │ natasha  │ ~1700/s  │ ~1700/s  │ Good     │ Navec embeddings, light  │
# │ spacy    │ ~530/s   │ ~760/s   │ Good     │ spacy-ru, good depparse  │
# └──────────┴──────────┴──────────┴──────────┴──────────────────────────┘

# CLI selection:
# synterr generate --lang ru --backend natasha -i ... -o ...
```

---

# Inflector: pymorphy3 + сохранение регистра

```python
# src/synterr/languages/russian/inflector.py

def match_capitalization(original: str, new: str) -> str:
    """Match capitalization pattern of original to new word.

    "Мама" + "мамы" → "Мамы"
    "МАМА" + "мамы" → "МАМЫ"
    "мама" + "мамы" → "мамы"
    """
    if not original or not new:
        return new
    if original.isupper():
        return new.upper()
    elif original[0].isupper():
        return new[0].upper() + new[1:] if len(new) > 1 else new.upper()
    return new


def inflect_word(
    parse: Any,              # pymorphy3 parse object
    grammemes: set[str],     # {"accs"}, {"plur"}, etc.
    original: str | None = None
) -> str | None:
    """Inflect word, preserving original capitalization."""
    if parse is None:
        return None
    result = parse.inflect(grammemes)
    if result is None:
        return None
    word = result.word
    if original:
        word = match_capitalization(original, word)
    return word

# pymorphy3 grammemes (subset):
# Cases: nomn, gent, datv, accs, ablt, loct
# Numbers: sing, plur
# Genders: masc, femn, neut
```

---

# Morphological Handler: NounCaseErrorHandler

```python
# src/synterr/languages/russian/errors/morphological.py

class NounCaseErrorHandler:
    name = "noun_case"
    subtypes = ["noun_case"]   # Maps to RLC "Gov"
    category = "MORPH"
    changes_length = False

    APPLICABLE_POS = {"NOUN", "PROPN"}

    def can_apply(self, tokens: Sequence[AnalyzedToken], idx: int) -> bool:
        token = tokens[idx]
        return (
            token.pos in self.APPLICABLE_POS
            and token.has_feature("Case")
            and "pymorphy_parse" in token.extra
        )

    def apply(self, tokens, sentence, idx, modified) -> ErrorResult | None:
        token = tokens[idx]
        word = sentence[idx]
        parse = token.extra.get("pymorphy_parse")

        # Get current case, pick different one
        current_case = UD_TO_PYMORPHY_CASE.get(token.get_feature("Case"))
        other_cases = [c for c in CASES if c != current_case]
        target_case = random.choice(other_cases)

        # Inflect with capitalization preservation
        new_word = inflect_word(parse, {target_case}, word)

        if new_word and new_word != word:
            sentence[idx] = new_word
            modified.add(idx)
            original_case = token.get_feature("Case", "Nom")
            return ErrorResult(
                error_type="noun_case",
                category=self.category,
                start_idx=idx,
                end_idx=idx + 1,
                original=word,
                corrupted=new_word,
                fix_tag=f"$TRANSFORM_CASE_{original_case}",
            )
        return None
```

---

# Spelling Handler: Vowel Reduction

```python
# src/synterr/languages/russian/errors/spelling.py

# Phonetic rules: unstressed vowels reduce
VOWEL_REDUCTION = {
    "о": "а",   # молоко́ → малако (unstressed о → а)
    "е": "и",   # весна́ → висна
    "я": "и",   # пята́к → питак
}
VOWELS = set("аеёиоуыэюя")

class SpellingErrorHandler:
    def __init__(self):
        # Stress dictionary: word → stressed vowel index (0-based)
        # Built from frequency list + Wiktionary
        self.stress_dict = load_stress_dict()  # ~50k words

    def _apply_vowel_reduction(self, word: str) -> str | None:
        word_lower = word.lower()
        stress_pos = self.stress_dict.get(word_lower, -1)
        if stress_pos < 0:
            return None  # Unknown stress → skip

        vowel_count = sum(1 for c in word_lower if c in VOWELS)
        if vowel_count < 2:
            return None  # Monosyllabic → no reduction

        result = list(word)
        vowel_idx = 0
        changed = False

        for i, char in enumerate(word):
            if char.lower() in VOWELS:
                # Only replace UNSTRESSED vowels
                if vowel_idx != stress_pos and char.lower() in VOWEL_REDUCTION:
                    result[i] = VOWEL_REDUCTION[char.lower()]
                    changed = True
                vowel_idx += 1

        return "".join(result) if changed else None

# Examples:
# молоко́  (stress=2) → малако  (positions 0,1 reduced)
# ко́шка   (stress=0) → кошка   (no change, о is stressed)
# карова́  (stress=2) → already wrong, skip
```

---

# Spelling Handler: Subtypes

```python
class SpellingErrorHandler:
    name = "spelling"
    subtypes = [
        "vowel_reduction",    # молоко → малако
        "devoicing",          # гриб → грип (final devoicing)
        "prefix_voicing",     # расписать → разписать (из-/ис-, раз-/рас-)
        "tsa_confusion",      # цирк → цырк (ци/цы confusion)
        "cluster",            # солнце → сонце (silent consonant)
        "double_consonant",   # касса → каса
        "soft_sign",          # мышь → мыш
        "keyboard",           # привет → прмвет (adjacent keys)
    ]
    category = "SPELL"
    changes_length = False

    # Weights configurable via preset YAML (subtype_weights section)
    DEFAULT_WEIGHTS = {
        "vowel_reduction": 30,
        "tsa_confusion": 25,
        "prefix_voicing": 15,
        "devoicing": 10,
        "cluster": 10,
        "double_consonant": 5,
        "keyboard": 3,
        "soft_sign": 2,
    }

    def set_subtype_weights(self, weights: dict[str, int]) -> None:
        """Override default weights from config."""
        self._weights = weights
```

---

# Schema: Dataclasses

```python
# src/synterr/schemas/loader.py

@dataclass
class SchemaTag:
    name: str                      # "Ortho", "Gov", "AgrCase"
    description: str = ""
    detection_category: str = "OTHER"  # SPELL, MORPH, OTHER

@dataclass
class SchemaModifier:
    name: str                      # "Miss", "Extra", "Transfer"
    description: str = ""
    aliases: list[str] = field(default_factory=list)  # Del→Miss

@dataclass
class SubtypeMapping:
    primary: str                   # Primary tag: "Ortho"
    modifier: str | None = None    # Optional: "Miss"
    secondary: list[str] = field(default_factory=list)

    def get_full_tag(self) -> str:
        if self.modifier:
            return f"{self.primary}+{self.modifier}"
        return self.primary

@dataclass
class Schema:
    name: str
    version: str
    description: str
    detection_categories: dict[str, str]
    primary_tags: dict[str, SchemaTag]
    modifiers: dict[str, SchemaModifier]
    mappings: dict[str, SubtypeMapping]   # subtype → mapping

    def get_detection_category(self, subtype: str) -> str:
        """Get detection category for handler subtype."""
        tag_name = self.mappings.get(subtype, SubtypeMapping("")).primary
        if tag_name in self.primary_tags:
            return self.primary_tags[tag_name].detection_category
        return "OTHER"
```

---

# Schema: RLC YAML

```yaml
# src/synterr/schemas/data/rlc.yaml

name: rlc
version: "1.0"
description: "Russian Learner Corpus error taxonomy (35 primary + 3 modifiers)"

detection_categories:
  SPELL: "Orthographic/spelling errors"
  MORPH: "Morphological errors"
  OTHER: "Lexical, syntactic, structural errors"

primary_tags:
  # SPELLING (5)
  Graph:     { description: "Mixing alphabets (Cyrillic/Latin)", detection_category: SPELL }
  Hyphen:    { description: "Hyphenated spelling errors", detection_category: SPELL }
  Space:     { description: "Extra or missing spaces", detection_category: SPELL }
  Ortho:     { description: "Standard orthography violation", detection_category: SPELL }
  Misspell:  { description: "Complex spelling errors", detection_category: SPELL }

  # MORPHOLOGY - Government/Agreement (6)
  Gov:       { description: "Syntactic government (case selection)", detection_category: MORPH }
  AgrNum:    { description: "Number agreement", detection_category: MORPH }
  AgrCase:   { description: "Case agreement", detection_category: MORPH }
  AgrGender: { description: "Gender agreement", detection_category: MORPH }
  AgrPers:   { description: "Person agreement", detection_category: MORPH }
  # ... 29 more tags

modifiers:
  Miss:     { description: "Missing element", aliases: [Del] }
  Extra:    { description: "Extra element", aliases: [Ins] }
  Transfer: { description: "L1 transfer error" }
```

---

# Schema: Mapping subtypes → tags

```yaml
# src/synterr/schemas/data/rlc.yaml

mappings:
  # SpellingErrorHandler.subtypes → RLC tags
  vowel_reduction:
    primary: Ortho
  devoicing:
    primary: Ortho
  tsa_confusion:
    primary: Ortho
  keyboard:
    primary: Misspell

  # Morphological handlers → RLC tags
  noun_case:
    primary: Gov           # Government (case selection)
  noun_number:
    primary: Num           # Number as nominal category
  adj_case:
    primary: AgrCase       # Case agreement
  adj_number:
    primary: AgrNum        # Number agreement
  adj_gender:
    primary: AgrGender     # Gender agreement
  verb_person_number:
    primary: AgrPers       # Person agreement
  verb_tense:
    primary: Tense

  # Future handlers (Artem)
  word_omission:
    primary: Syntax
    modifier: Miss         # → Syntax+Miss
  word_insertion:
    primary: Syntax
    modifier: Extra        # → Syntax+Extra
```

---

# Pipeline: GenerationConfig

```python
# src/synterr/core/pipeline.py

@dataclass
class GenerationConfig:
    seed: int = 42                           # Reproducibility
    max_errors_per_sentence: int = 3
    error_probability: float = 0.7           # P(any error in sentence)
    use_depparse: bool = False               # Enable dependency parsing
    label_format: str = "multiclass"         # "original" | "binary" | "multiclass"
    enabled_errors: set[str] | None = None   # Filter handlers by name
    error_weights: dict[str, float] | None = None  # Override weights
    backend: str | None = None               # "stanza" | "natasha" | "spacy"
    schema: str | None = None                # "rlc" | "synterr" | path

    @classmethod
    def from_preset(cls, language: str, preset: str, **overrides):
        """Load from preset: 'rulec', 'gera', 'balanced'"""
        from synterr.configs import load_preset
        config_data = load_preset(language, preset)
        return cls._from_dict(config_data, **overrides)

    @classmethod
    def from_file(cls, path: str, **overrides):
        """Load from custom YAML file."""
        from synterr.configs import load_config
        config_data = load_config(path)
        return cls._from_dict(config_data, **overrides)
```

---

# Pipeline: Error Generation Flow

```python
# src/synterr/core/pipeline.py

class ErrorPipeline:
    def generate(self, text: str) -> GeneratedSentence:
        # 1. Morphological analysis
        tokens = self.analyzer.analyze(text)
        if not tokens:
            return GeneratedSentence([], [], [], "")

        original = [t.text for t in tokens]
        sentence = original.copy()   # Mutable copy
        modified: set[int] = set()   # Track modified positions
        errors: list[ErrorResult] = []

        # 2. Probabilistic skip
        if self._rng.random() > self.config.error_probability:
            return GeneratedSentence(original, sentence, [], self._format_output(sentence, []))

        # 3. Apply errors
        num_errors = self._rng.randint(1, self.config.max_errors_per_sentence)

        for _ in range(num_errors):
            if len(modified) >= len(tokens):
                break

            handler = self._sample_error_type()  # Weighted sampling
            if handler is None or handler.changes_length:
                continue

            applicable = [i for i in range(len(tokens))
                          if i not in modified and handler.can_apply(tokens, i)]
            if not applicable:
                continue

            idx = self._rng.choice(applicable)
            result = handler.apply(tokens, sentence, idx, modified)
            if result:
                errors.append(result)
                modified.add(idx)

        return GeneratedSentence(original, sentence, errors, self._format_output(sentence, errors))
```

---

# Pipeline: Weighted Sampling

```python
# src/synterr/core/pipeline.py

class ErrorPipeline:
    @property
    def distribution(self) -> dict[str, float]:
        """Get error weights. Priority: config > language default"""
        if self._distribution is None:
            if self.config.error_weights is not None:
                dist = self.config.error_weights.copy()
            else:
                dist = self.language.get_error_distribution()

            if self.config.enabled_errors is not None:
                dist = {k: v for k, v in dist.items()
                        if k in self.config.enabled_errors}
            self._distribution = dist
        return self._distribution

    def _sample_error_type(self) -> ErrorHandler | None:
        handler_map = {h.name: h for h in self.handlers}
        available = [name for name in self.distribution if name in handler_map]

        if not available:
            return None

        weights = [self.distribution[name] for name in available]
        chosen = self._rng.choices(available, weights=weights, k=1)[0]
        return handler_map[chosen]

# Example distribution (rulec.yaml):
# weights:
#   spelling: 0.475        # 47.5% of errors are spelling
#   noun_case: 0.280       # 28.0% are noun case
#   noun_number: 0.053
#   adj_case: 0.071
#   ...
```

---

# Pipeline: Tagged Corruption API (NEW)

```python
# src/synterr/core/pipeline.py

class ErrorPipeline:
    def apply_error(
        self,
        text: str,
        error_type: str,           # Handler name or schema tag
        position: int | None = None,
    ) -> GeneratedSentence | None:
        """Apply specific error type to sentence.

        Unlike generate(), applies exactly ONE error of specified type.
        Supports both handler names and schema tags.

        Args:
            text: Input sentence
            error_type: "noun_case" or "Gov" (with --schema rlc)
            position: Token index (random if None)

        Returns:
            GeneratedSentence or None if error cannot be applied
        """
        handler = self.get_handler(error_type)
        if handler is None:
            return None

        tokens = self.analyzer.analyze(text)
        applicable = self._find_applicable_indices(handler, tokens, set())

        if not applicable:
            return None

        idx = position if position in applicable else self._rng.choice(applicable)
        # ... apply and return

    def get_handler(self, error_type: str) -> ErrorHandler | None:
        """Resolve handler by name or schema tag."""
        # Direct match
        for h in self.handlers:
            if h.name == error_type:
                return h
        # Schema tag lookup
        if self.schema:
            for subtype, mapping in self.schema.mappings.items():
                if mapping.primary == error_type:
                    for h in self.handlers:
                        if subtype in h.subtypes:
                            return h
        return None
```

---

# CLI: corrupt command

```bash
# Apply specific error type to a sentence

$ synterr corrupt --lang ru --error spelling "Молоко стоит на столе."
Original:  Молоко стоит на столе .
Corrupted: Малако стоит на столе .
Error:     spelling_vowel_reduction @ position 0
Fix tag:   $REPLACE_Молоко

$ synterr corrupt --lang ru --error noun_case "Мама мыла раму."
Original:  Мама мыла раму .
Corrupted: Маме мыла раму .
Error:     noun_case @ position 0
Fix tag:   $TRANSFORM_CASE_Nom

# With schema tag (RLC)
$ synterr corrupt --lang ru --error Gov --schema rlc "Мама мыла раму."
Original:  Мама мыла раму .
Corrupted: Маме мыла раму .
Error:     noun_case @ position 0

# With specific position
$ synterr corrupt --lang ru --error noun_case --position 2 "Мама мыла раму."
Original:  Мама мыла раму .
Corrupted: Мама мыла раме .
Error:     noun_case @ position 2
Fix tag:   $TRANSFORM_CASE_Acc
```

---

# Output Format: GECToR

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GECToR .edits FORMAT                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  $START SEPL|||SEPR $KEEP:CORRECT Мама SEPL|||SEPR $KEEP:CORRECT мыла  │
│  SEPL|||SEPR $REPLACE_раму:MORPH раме SEPL|||SEPR $KEEP:CORRECT .      │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Token structure:                                                │  │
│  │                                                                  │  │
│  │  $REPLACE_раму : MORPH   раме                                   │  │
│  │  ───────────────  ─────  ────                                   │  │
│  │       │            │       │                                     │  │
│  │  correction    detection  corrupted                              │  │
│  │     tag        category    token                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Detection categories:                                                  │
│    CORRECT  - no error                                                  │
│    SPELL    - orthographic (→ from schema if loaded)                   │
│    MORPH    - morphological (→ from schema if loaded)                  │
│    OTHER    - lexical, structural                                       │
│                                                                         │
│  Correction tag types:                                                  │
│    $KEEP                  - no change                                   │
│    $DELETE                - remove token                                │
│    $REPLACE_<word>        - replace with <word>                         │
│    $TRANSFORM_CASE_<case> - inflect to case                            │
│    $TRANSFORM_NUMBER_<n>  - inflect to number                          │
│    $APPEND_<word>         - insert <word> after                         │
│    $MERGE_<word>          - merge with following                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# Output Formats (NEW in v0.1.2)

```python
# src/synterr/core/pipeline.py

result = pipeline.generate("Мама мыла раму.")

# GECToR format (default) — for training
result.formatted
# "$STARTSEPL|||SEPR$KEEP:CORRECT МамаSEPL|||SEPR..."

# TSV — parallel text for seq2seq models
result.to_tsv()
# "Мама мыла раму\tМама мыла раме"

# JSONL — rich format with metadata
result.to_jsonl(id="001", seed=42, schema="rlc")
# {"original": "Мама мыла раму", "corrupted": "Мама мыла раме",
#  "errors": [{"type": "noun_case", "category": "MORPH", ...}], ...}

# Diff — human-readable with highlighting
result.to_diff()
# "Мама мыла [-раму-]{+раме+}"

result.to_diff(use_color=True)
# ANSI-colored: red deletions, green insertions
```

**Diff Viewer** (`tools/diff_viewer.html`):
- Drag-drop JSONL loading
- Token-level error highlighting
- Filter by category/type
- Keyboard navigation (↑/↓)

---

# Language Discovery: Entry Points

```python
# src/synterr/core/registry.py

def _load_entry_points() -> None:
    """Load language modules from entry points (lazy, once)."""
    global _LOADED_ENTRY_POINTS
    if _LOADED_ENTRY_POINTS:
        return

    eps = entry_points(group="synterr.languages")

    for ep in eps:
        try:
            language_cls = ep.load()
            language = language_cls() if isinstance(language_cls, type) else language_cls
            register_language(language)
        except Exception as e:
            warnings.warn(f"Failed to load language module '{ep.name}': {e}")

    _LOADED_ENTRY_POINTS = True

# pyproject.toml:
# [project.entry-points."synterr.languages"]
# russian = "synterr.languages.russian:RussianLanguage"

# Future:
# english = "synterr.languages.english:EnglishLanguage"
# german = "synterr.languages.german:GermanLanguage"
```

---

# Config Presets

```yaml
# src/synterr/configs/russian/rulec.yaml

name: rulec
description: "RULEC-GEC corpus distribution (L2/heritage learners)"
source: "RULEC-GEC (Rozovskaya & Roth, 2019)"

error_probability: 0.7
max_errors_per_sentence: 3

# Weights normalized to implemented handlers
weights:
  spelling: 0.475         # 21.8% in corpus → 47.5% of implemented
  noun_case: 0.280        # 12.8%
  noun_number: 0.053      # 2.4%
  adj_case: 0.071         # 3.3%
  adj_number: 0.019       # 0.9%
  adj_gender: 0.027       # 1.2%
  verb_person_number: 0.052  # 2.4%
  verb_tense: 0.023       # 1.0%

# Unimplemented (for reference):
# insert: 14.6%         - Missing function words
# lexical: 12.2%        - Word choice errors
# delete: 8.2%          - Extra words
# preposition: 3.1%     - Preposition errors
# verb_aspect: 1.8%     - Aspect confusion
```

---

# CLI: All Commands

```bash
# Discovery
synterr list-languages          # Available languages
synterr list-schemas            # Available schemas
synterr list-presets --lang ru  # Presets for language
synterr list-errors --lang ru   # Error types with weights
synterr list-backends --lang ru # NLP backends

# Analysis
synterr analyze --lang ru "Мама мыла раму."
# Tokens (4):
#   0: 'Мама' (NOUN) lemma='мама' {Case=Nom, Gender=Fem, Number=Sing}
#   1: 'мыла' (VERB) lemma='мыть' {Aspect=Imp, Mood=Ind, Number=Sing, ...}
#   2: 'раму' (NOUN) lemma='рама' {Case=Acc, Gender=Fem, Number=Sing}
#   3: '.' (PUNCT) lemma='.'

# Schema coverage
synterr coverage --lang ru --schema rlc
# Coverage: 9/35 tags (25.7%)
# Covered: AgrCase, AgrGender, ...
# Uncovered: Lex, Prep, Conj, ...

# Single-sentence corruption
synterr corrupt --lang ru --error noun_case "Мама мыла раму."

# Batch generation
synterr generate --lang ru --preset rulec -i corpus.txt -o train.edits
synterr generate --lang ru --schema rlc -i corpus.txt -o train.edits
```

---

# RLC Coverage: Current State

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RLC SCHEMA COVERAGE: 25.7%                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  COVERED (9/35 tags)              UNCOVERED (26 tags)                   │
│  ══════════════════               ═══════════════════                   │
│                                                                         │
│  Tag        Handler               Tag        Planned                    │
│  ─────────  ────────────          ─────────  ────────────               │
│  Ortho      spelling              Lex        paronym (Artem)            │
│  Misspell   spelling              Prep       preposition (Artem)        │
│  Gov        noun_case             Conj       conjunction (Artem)        │
│  Num        noun_number           Syntax     word_* (Artem)             │
│  AgrCase    adj_case              Asp        aspect (v0.5.0)            │
│  AgrNum     adj_number            Refl       reflexive                  │
│  AgrGender  adj_gender            WO         word_order                 │
│  AgrPers    verb_person_number    Passive    passive                    │
│  Tense      verb_tense            Impers     impersonal                 │
│                                   Mode       conditional                │
│                                   Gerund     gerundive                  │
│                                   Brev       short adjective            │
│                                   Com        comparative                │
│                                   Aux        auxiliary/copula           │
│                                   ... (12 more)                         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  v0.2.0 (Artem): +5 handlers → ~40% coverage                           │
│  v0.3.0+:        Agreement/Government/Aspect → >60%                    │
│  v1.0.0:         >90% of learner corpus errors                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# Artem's Tasks (v0.2.0)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Handler          │ RLC Tag      │ Difficulty │ Resource               │
├───────────────────┼──────────────┼────────────┼────────────────────────┤
│  paronym          │ Lex          │ Easy       │ paronyms.json ✅       │
│  preposition      │ Prep         │ Easy       │ Create prepositions.json│
│  conjunction      │ Conj         │ Easy       │ Create conjunctions.json│
│  word_omission    │ Syntax+Miss  │ Medium     │ —                      │
│  word_insertion   │ Syntax+Extra │ Medium     │ Create fillers.json    │
└───────────────────┴──────────────┴────────────┴────────────────────────┘
```

```python
# Key difference for structural handlers:
class WordOmissionHandler:
    name = "word_omission"
    subtypes = ["word_omission"]
    category = "OTHER"
    changes_length = True    # ← CRITICAL: modifies sentence length

    def apply(self, tokens, sentence, idx, modified):
        deleted = sentence[idx]
        del sentence[idx]    # Mutates list length!

        return ErrorResult(
            start_idx=idx - 1,            # Tag on PREVIOUS token
            fix_tag=f"$APPEND_{deleted}", # Fix = append deleted word
            ...
        )
```

---

# Integration: GECToR Training

```bash
# 1. Generate synthetic data (100k sentences, ~2 min)
synterr generate --lang ru --preset rulec \
    --schema rlc \
    -i ~/corpora/lenta.txt \
    -o train_synthetic.edits \
    --max-sentences 100000 \
    --seed 42

# 2. Check output
head -1 train_synthetic.edits
# $STARTSEPL|||SEPR$KEEP:CORRECT ПрезидентSEPL|||SEPR...

wc -l train_synthetic.edits
# 100000 train_synthetic.edits

# 3. Train GECToR
cd fast-gector
python train.py \
    --train ../train_synthetic.edits \
    --val data/RULEC-GEC.dev.edits \
    --model ai-forever/ruRoberta-large \
    --epochs 10

# 4. Evaluate
python predict.py \
    --model_path ckpts/best \
    --input data/RULEC-GEC.test.txt \
    --output predictions.txt

# Calculate F0.5 with errant/m2scorer
```

---

# Performance Considerations

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE NOTES (M4 Pro benchmarks)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Backend speeds (sentences/sec):                                        │
│  ─────────────────────────────────────────────                         │
│  │ Backend  │ Single   │ Batch    │ Accuracy │                         │
│  ├──────────┼──────────┼──────────┼──────────┤                         │
│  │ stanza   │ ~75/s    │ ~500/s   │ Best     │ ← 7x faster in batch!   │
│  │ natasha  │ ~1700/s  │ ~1700/s  │ Good     │ ← Fastest               │
│  │ spacy    │ ~530/s   │ ~760/s   │ Good     │                         │
│                                                                         │
│  Memory:                                                                │
│  ─────────────────────────────────────────────                         │
│  - stanza: ~500MB (neural models)                                      │
│  - pymorphy3: ~100MB (dictionary)                                      │
│  - stress_dict: ~5MB (50k words)                                       │
│                                                                         │
│  Throughput (100k sentences, batch mode):                               │
│  ─────────────────────────────────────────────                         │
│  - stanza:  ~3.5 min                                                   │
│  - natasha: ~1 min                                                     │
│  - spacy:   ~2 min                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# Summary

## v0.1.2 Features

1. **Pluggable schemas** — RLC (35+3), synterr (14)
2. **Handler subtypes** — fine-grained error types (13 total)
3. **Tagged corruption API** — `apply_error(text, tag)`
4. **Stress-based spelling** — correct vowel reduction
5. **Capitalization preservation** — `Мама → Маме` not `мамы`
6. **Multiple backends** — stanza/natasha/spacy
7. **Output formats** — GECToR, TSV, JSONL, diff (NEW)
8. **Configurable subtype weights** — via preset YAML (NEW)
9. **Diff viewer** — `tools/diff_viewer.html` (NEW)

## Metrics

```
Handlers:     8 (13 subtypes)
Schemas:      2 (synterr, rlc)
RLC coverage: 25.7% → 40% (after Artem)
LOC:          ~4k Python
```

## Next Steps

- **v0.2.0**: Artem's 5 handlers (Lex, Prep, Conj, Syntax+Miss/Extra)
- **v0.3.0**: Agreement with depparse (amod, nsubj relations)
- **v1.0.0**: PyPI release, >90% coverage

---

# Questions?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   Repository:   https://github.com/mechanicpanic/synterr                │
│                                                                         │
│   Key files:                                                            │
│     src/synterr/core/protocol.py       # AnalyzedToken, ErrorHandler   │
│     src/synterr/core/pipeline.py       # ErrorPipeline, apply_error    │
│     src/synterr/schemas/loader.py      # Schema, SubtypeMapping        │
│     src/synterr/languages/russian/     # Handlers, backends            │
│                                                                         │
│   Docs:                                                                 │
│     docs/CONTRIBUTING.ru.md            # Developer guide               │
│     docs/ARTEM_TASKS.md                # v0.2.0 tasks                  │
│     docs/VERSIONING.md                 # Roadmap                       │
│     tools/diff_viewer.html             # Error inspection UI           │
│                                                                         │
│   Try it:                                                               │
│     uv run synterr corrupt -l ru -e spelling "Молоко на столе"         │
│     uv run synterr coverage --lang ru --schema rlc                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
