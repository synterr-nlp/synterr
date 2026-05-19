# LoRuGEC Rule Coverage by Handler

Generated: 2026-05-01 (counts refreshed 2026-05-12) | synterr v1.0.0 | 24 handlers, 63 subtypes
Source: `../gector/data/rozental_book/cross_reference.csv` (48 LoRuGEC rules)

## Summary

| Status | Count | % |
|--------|------:|--:|
| **FULL** — direct handler subtype matches the rule | 36 | 75% |
| **PARTIAL** — handler exists but specifics need verification | 12 | 25% |
| **NONE** | 0 | 0% |

Total LoRuGEC rules: **48** (val=348, test=612, no train).

Note: this is a *handler claim* assessment. Generation quality (audit bugs, output validity) is a
separate question — tracked separately in the team's internal queue. The "PARTIAL" bucket reflects
rules where the handler's coverage of *this specific rule* needs spot-checking, not handler quality.

## Per-rule mapping

### spell_affixes (5/5 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Правописание разделительных "ъ" и "ь" | `spelling:soft_sign` |
| Правописание приставок пре- и при- | `orthographic_spelling:pre_pri` |
| Гласные "ы" и "и" после приставок | `orthographic_spelling:y_i_after_prefix` |
| Гласные после "ц" | `orthographic_spelling:vowel_after_ts` |
| Гласные после шипящих | `orthographic_spelling:vowel_after_sibilant` |

### spell_noun (3/3 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| -еньк, -оньк в существительных | `orthographic_spelling:suffix_enk_onk` |
| -иц, -ец в существительных среднего рода | `orthographic_spelling:suffix_its_ets` |
| -ек, -ик | `orthographic_spelling:suffix_ek_ik` |

### spell_verb / participle (2/2 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| "н" и "нн" в суффиксах прилагательных | `orthographic_spelling:nn_suffix` |
| Гласные в суффиксах причастий | `orthographic_spelling:participle_suffix` |

### spell_adj (1 FULL, 1 PARTIAL)

| LoRuGEC rule | Handler.subtype | Status |
|---|---|---|
| -инск, -енск | `orthographic_spelling:suffix_insk_ensk` | FULL |
| Сложные прилагательные | `compound_spelling:compound_adj` | PARTIAL — many form variants, needs spot-check |

### spell_compounds (2/2 FULL — recent)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Дефис в письменных эквивалентах сложных слов | `compound_spelling:num_dash` |
| Числительное пол- | `compound_spelling:pol_spelling` |

### spell_adverb (1/1 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Слитное/раздельное/дефисное написание наречий | `adverb_spelling:*` (4 directional subtypes) |

### spell_function (10/10 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| "не" с причастиями | `function_spelling:ne_attachment / ne_detachment` |
| "не" с глаголами | `function_spelling:ne_attachment` |
| "не" с прилагательными | `function_spelling:ne_attachment` |
| "не" с существительными | `function_spelling:ne_attachment` |
| Правописание "чтобы" | `function_spelling:conjunction_split / merge` |
| Правописание "также" | `function_spelling:conjunction_split / merge` |
| Правописание "зато" | `function_spelling:conjunction_split / merge` |
| Правописание "оттого" | `function_spelling:conjunction_split / merge` |
| Правописание "причем"/"притом" | `function_spelling:conjunction_split / merge` |
| Частица -таки | `function_spelling:taki_hyphen` |

### punct_dash (1 FULL, 2 PARTIAL)

| LoRuGEC rule | Handler.subtype | Status |
|---|---|---|
| Тире между подлежащим и сказуемым | `dash_delete:dash_subj_pred` | FULL |
| Тире при приложении | `dash_delete:dash_other` | PARTIAL — generic dash; rule wants apposition specifically |
| Тире в бессоюзных предложениях | `dash_delete:dash_asyndetic` | PARTIAL — new, no audit yet |

### punct_comma (4 FULL, 7 PARTIAL)

| LoRuGEC rule | Handler.subtype | Status |
|---|---|---|
| Запятая в фразеологических выражениях | `comma_insert:comma_in_set_phrase` | FULL |
| Запятая перед "как": 1 | `comma_insert:comma_before_kak` | FULL |
| Запятая перед "как": 2 | `comma_insert:comma_before_kak` | FULL |
| Запятая перед "как": 3 | `comma_insert:comma_before_kak` | FULL |
| Запятая в цельных по смыслу сочетаниях | `comma_insert:comma_in_indivisible` | FULL |
| Однородные члены: пары | `comma_delete:comma_homogeneous` | PARTIAL — "пары" condition is specific |
| Пунктуация при вводных словах | `comma_pair_delete:pair_parenthetical` | PARTIAL — only DELETE direction; rule includes INSERT |
| Пунктуация при повторяющихся союзах | `comma_insert:comma_between_conjunctions` | PARTIAL — INSERT only |
| Обособление деепричастий после союзов | `comma_pair_delete:pair_gerund` | PARTIAL — "после союзов" condition specific |
| Обособление определений к личному местоимению | `comma_pair_delete:pair_participle` | PARTIAL — pronoun-targeting condition |
| Обособление определений, оторванных от слова | `comma_pair_delete:pair_apposition` | PARTIAL — distance condition |

### punct_compound / punct_complex (3 PARTIAL)

| LoRuGEC rule | Handler.subtype | Status |
|---|---|---|
| Запятая между частями СПП с общей частью | `comma_delete:comma_compound` | PARTIAL — "общая часть" not modeled |
| Запятая между однородными придаточными | `comma_delete:comma_homogeneous` (clausal) | PARTIAL — clausal vs nominal not separated |
| Запятая на стыке двух союзов | none directly | PARTIAL — falls under `comma_subordinate` adjacency |

### lex_choice (2/2 FULL — recent)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Лексическая сочетаемость | `collocation:collocation` |
| Плеоназмы | `pleonasm:pleonasm` |

### morph_numeral (2/2 FULL — recent)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Склонение количественных числительных | `numeral_declension:numeral_declension` |
| Склонение полтора/полторы/полтораста | `numeral_declension:numeral_poltora` |

### gov_case + syntax_advanced (2/2 FULL)

| LoRuGEC rule | Handler.subtype |
|---|---|
| Согласование причастий с определяемым словом | `adj_case` (via amod arc) |
| Нарушение норм управления | `noun_case` (gated to obl/nmod/iobj/obj as of v1.0) |

## What changed since the last coverage estimate (2026-03-06)

The earlier "9 missing rules / 19% NONE" estimate is **stale**. Closed since:

- `4b16660` — "Close LoRuGEC coverage gaps: 9 new rules, 3 new handlers, nn_suffix subtype" — closed compounds (3), `nn_suffix`
- `5b2311d` — added `numeral_declension` handler — closed numerals (2)
- `5b2311d` — added `adverb_spelling` handler — closed adverb split (1)
- `semantics.py` — added `pleonasm` and `collocation` handlers — closed pleonasm (1) + lex_choice (1)
- `comma_insert.comma_in_indivisible` — closed цельных по смыслу
- `dash_delete.dash_asyndetic` — closed бессоюзные тире

What's left is not "missing rules" but **PARTIAL coverage of fine-grained punctuation conditions** —
the rule fires, but the handler doesn't model the specific syntactic/semantic precondition LoRuGEC tests.

## What this means for M1

**Original plan (stale):** close 9 missing rules.
**Revised plan:** the audit + verification work is more important than implementation. The PARTIAL
bucket needs spot-checking against LoRuGEC val examples, not new handlers.
