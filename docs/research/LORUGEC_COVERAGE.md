# LoRuGEC Rule Coverage by Handler

Generated: 2026-05-01 | counts refreshed 2026-05-27 | synterr v1.0.1 | 25 handlers, 69 subtypes
Source: `../gector/data/rozental_book/cross_reference.csv` (48 LoRuGEC rules)

> **This is a handler-*claim* map, NOT a verified-works map.** A row marked FULL
> means a handler subtype is *intended* to cover the rule — it does **not** mean
> the handler has been validated against LoRuGEC examples. A 2026-05-27 audit
> found several FULL rows that fire on the wrong target or return "Cannot apply"
> on the rule's canonical inputs (see the Honest-status column and the
> Known-broken section). Treat FULL as "mapped," PARTIAL as "mapped, specifics
> unverified," and read the per-rule notes before trusting any number.

## Summary

Two numbers, because they answer different questions:

| Status | Mapped (handler exists) | Verified (fires correctly on canonical inputs) |
|--------|------:|------:|
| **FULL** | 36 | ~33 |
| **PARTIAL** | 12 | 15 |
| **NONE** | 0 | 0 |

The "Mapped" column is the original handler-claim count. The "Verified" column is
the honest recount after spot-checking against real sentences — it still demotes
the three «как» comparison rows (Known-broken #1). The general-cardinal numeral
rule was demoted in the 2026-05-27 audit but is now implemented and restored
(Known-broken #2, resolved 2026-06-02). Total LoRuGEC rules: **48** (val=348,
test=612, no train).

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
| Тире при приложении | `dash_delete:dash_apposition` (delete) + `dash_to_comma:dash_to_comma_apposition` (substitute) | FULL — now apposition-specific via appos/parataxis arc (2026-05-27) |
| Тире в бессоюзных предложениях | `dash_delete:dash_asyndetic` | PARTIAL — only 1 of §118's 8 sub-rules |

### punct_comma (4 FULL, 7 PARTIAL)

| LoRuGEC rule | Handler.subtype | Status |
|---|---|---|
| Запятая в фразеологических выражениях | `comma_insert:comma_in_set_phrase` | FULL |
| Запятая перед "как": 1 | `comma_insert:comma_before_kak` | **BROKEN** — see Known-broken #1 |
| Запятая перед "как": 2 | `comma_insert:comma_before_kak` | **BROKEN** — see Known-broken #1 |
| Запятая перед "как": 3 | `comma_insert:comma_before_kak` | **BROKEN** — see Known-broken #1 |
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
| Склонение количественных числительных | `numeral_declension:numeral_declension` — oblique general cardinal reverts to its Nom/Acc citation form (о пятидесяти → о пятьдесят) |
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

## Known-broken (2026-05-27 audit)

These are FULL/mapped rows that fail on the rule's canonical inputs. Demoted in
the Verified column above.

1. **`comma_before_kak` — fails on comparative «как» (3 rows).** Returns "Cannot
   apply" on the canonical §93 comparison sentences ("работал как зверь", "бледна
   как смерть", "Дети как цветы жизни", …). Root cause: stanza tags comparative
   «как» with dep_rel `mark`/`advcl`/`cc`, all in `_KAK_CLAUSE_DEPRELS`
   (`comma_insert.py:38`), so the handler deliberately skips. The three
   "Запятая перед «как»" rows all ride on this one subtype. Fix needs a
   comparative-«как» detector that distinguishes §93 (no comma) from genuine
   subordinate «как» — likely lexical + head-POS, since stanza's dep_rel alone
   collides. Until then these are NONE-grade, not FULL.

2. ~~**`numeral_declension` general cardinals — not implemented.**~~
   **RESOLVED (2026-06-02).** `can_apply` now also matches oblique general
   cardinals: when a NUMR-parsed token is in Gen/Dat/Ins/Loc, the handler
   inflects it back to its Nom/Acc citation form (о пятидесяти → о пятьдесят,
   около трёхсот → около триста), reproducing the canonical "fails to decline"
   L2 error. `_general_cardinal_target` guards against non-numerals (e.g. "сто"
   parses as NOUN) and forms whose nominative equals the surface. полтора
   remains a separate working row.

## What this means for M1

**Original plan (stale):** close 9 missing rules.
**Revised plan:** verification, not implementation, is the bottleneck. The real
work is (a) a real-backend integration harness so FULL claims are auditable
rather than asserted, and (b) fixing the remaining Known-broken row (the three
«как» comparison rows; #2 is now resolved). Per-row "last verified" with the
test sentence would make this doc self-checking.
