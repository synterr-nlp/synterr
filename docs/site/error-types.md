# Error types (Russian)

Twenty-five handlers (69 subtypes) covering five categories. The full subtype lists
and Rozental § mappings are in
[`CLAUDE.md`](https://github.com/synterr-nlp/synterr/blob/master/CLAUDE.md);
LoRuGEC rule coverage is verified in
[`docs/research/LORUGEC_COVERAGE.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/research/LORUGEC_COVERAGE.md)
(36/48 FULL, 12/48 PARTIAL).

## Spelling — `SPELL`

| Handler | What it does | Example |
|---------|--------------|---------|
| `spelling` | Phonetic confusions, keyboard typos | *молоко* → *малако* |
| `function_spelling` | не/ни attachment, conjunction split/merge, -таки | *чтобы* → *что бы* |
| `orthographic_spelling` | пре/при, ы/и after prefixes, suffixes, participles | *преинтересный* → *приинтересный* |
| `compound_spelling` | Hyphen / solid / separate writing of compounds | *по-моему* → *по моему* |
| `adverb_spelling` | Adverb writing variants (4 directional subtypes) | *по-русски* → *по русски* |

## Morphological — `MORPH`

| Handler | What it does | Example |
|---------|--------------|---------|
| `noun_case` | Wrong case on governed noun (obl/nmod/iobj/obj) | *на столе* → *на стол* |
| `noun_number` | Singular ↔ plural | *книга* → *книги* |
| `adj_case`, `adj_number`, `adj_gender` | Adjective agreement errors via `amod` arc | *новая книга* → *новый книга* |
| `verb_person_number` | Verb conjugation against `nsubj` | *они читает* → *они читают* |
| `verb_tense` | Past / present / future swap | *читал* → *читает* |
| `numeral_declension` | Numeral declension errors | *полтора часа* → *полутора часа* |

## Lexical — `OTHER`

| Handler | What it does |
|---------|--------------|
| `paronym` | Confusable word pairs (*одеть* / *надеть*) |
| `preposition` | Wrong preposition |
| `conjunction` | Wrong conjunction |
| `pleonasm` | Tautological phrases (*главный приоритет*) |
| `collocation` | Lexical compatibility violations |

## Structural — `OTHER`

| Handler | What it does |
|---------|--------------|
| `word_omission` | Drop a token |
| `word_insertion` | Insert an extraneous token |

## Punctuation — `PUNCT`

| Handler | What it does |
|---------|--------------|
| `comma_delete` | Delete a comma at clause boundaries (5 dep-tree-classified subtypes) |
| `comma_pair_delete` | Delete both commas of an isolated phrase (5 subtypes) |
| `comma_insert` | Add a spurious comma (before *как*, in set phrases, between conjunctions) |
| `dash_delete` | Delete a required dash (subj/pred, asyndetic, other) |

## Schema mapping cheat sheet

```bash
# See current mappings
uv run synterr coverage --lang ru --schema rlc
uv run synterr coverage --lang ru --schema rozental
uv run synterr coverage --lang ru --schema errant
```
