# SFT Data Coverage Report

Generated: 2026-03-12
Source: Russian Wikipedia (200k sentences, depparse enabled)
Output: `data/qwen_sft_50k.jsonl` (35,804 examples, 21.9 MB)
Target: 50,000 (1,042 per rule × 48 rules)
Script: `scripts/generate_sft.py` (force-apply per LoRuGEC rule)

## Per-subtype coverage (handler/subtype)

| Handler / Subtype | Got | Target | % |
|---|---:|---:|---:|
| adj_case/adj_case | 2084 | 2084 | 100% |
| adverb_spelling/adverb_solid_to_separate | 1042 | 1042 | 100% |
| collocation/collocation | 1042 | 1042 | 100% |
| comma_delete/comma_homogeneous | 2084 | 2084 | 100% |
| comma_delete/comma_subordinate | 2084 | 2084 | 100% |
| comma_insert/comma_before_kak | 2445 | 3126 | 78% |
| comma_insert/comma_between_conjunctions | 24 | 1042 | 2% |
| comma_insert/comma_in_indivisible | 113 | 1042 | 11% |
| comma_insert/comma_in_set_phrase | 3 | 1042 | 0% |
| comma_pair_delete/pair_gerund | 273 | 1042 | 26% |
| comma_pair_delete/pair_parenthetical | 732 | 1042 | 70% |
| comma_pair_delete/pair_participle | 2084 | 2084 | 100% |
| compound_spelling/compound_adj | 1003 | 1042 | 96% |
| compound_spelling/num_dash | 1042 | 1042 | 100% |
| compound_spelling/pol_spelling | 644 | 1042 | 62% |
| dash_delete/dash_asyndetic | 1042 | 1042 | 100% |
| dash_delete/dash_other | 1042 | 1042 | 100% |
| dash_delete/dash_subj_pred | 1042 | 1042 | 100% |
| function_spelling/conjunction_merge | 953 | 5210 | 18% |
| function_spelling/ne_attachment | 3126 | 3126 | 100% |
| function_spelling/ne_detachment | 1042 | 1042 | 100% |
| function_spelling/taki_hyphen | 43 | 1042 | 4% |
| numeral_declension/numeral_declension | 1 | 1042 | 0% |
| numeral_declension/numeral_poltora | 82 | 1042 | 8% |
| orthographic_spelling/nn_suffix | 1042 | 1042 | 100% |
| orthographic_spelling/participle_suffix | 1042 | 1042 | 100% |
| orthographic_spelling/pre_pri | 1042 | 1042 | 100% |
| orthographic_spelling/suffix_ek_ik | 1042 | 1042 | 100% |
| orthographic_spelling/suffix_enk_onk | 336 | 1042 | 32% |
| orthographic_spelling/suffix_insk_ensk | 83 | 1042 | 8% |
| orthographic_spelling/suffix_its_ets | 935 | 1042 | 90% |
| orthographic_spelling/vowel_after_sibilant | 1042 | 1042 | 100% |
| orthographic_spelling/vowel_after_ts | 1042 | 1042 | 100% |
| orthographic_spelling/y_i_after_prefix | 1042 | 1042 | 100% |
| pleonasm/pleonasm | 1042 | 1042 | 100% |
| spelling/soft_sign | 1042 | 1042 | 100% |

## Per-rule coverage (LoRuGEC 48 rules)

| Rule | Got | Target | % |
|---|---:|---:|---:|
| "н" и "нн" в суффиксах прилагательных | 1042 | 1042 | 100% |
| Гласные "ы" и "и" после приставок | 1042 | 1042 | 100% |
| Гласные после "ц" | 1042 | 1042 | 100% |
| Гласные после шипящих | 1042 | 1042 | 100% |
| Дефис в составе письменных эквивалентов сложных слов | 1042 | 1042 | 100% |
| Запятая внутри выражений фразеологического характера | 3 | 1042 | **0%** |
| Запятая между однородными придаточными | 1042 | 1042 | 100% |
| Запятая между частями СПП с общей частью | 1042 | 1042 | 100% |
| Запятая на стыке двух союзов | 24 | 1042 | **2%** |
| Запятая перед союзом "как": 1 | 815 | 1042 | 78% |
| Запятая перед союзом "как": 2 | 815 | 1042 | 78% |
| Запятая перед союзом "как": 3 | 815 | 1042 | 78% |
| Знаки препинания в предложениях с однородными членами: пары | 1042 | 1042 | 100% |
| Лексическая сочетаемость слов | 1042 | 1042 | 100% |
| Нарушение норм управления | 1042 | 1042 | 100% |
| Обособление деепричастий после союзов | 273 | 1042 | **26%** |
| Обособление согласованных определений, относящихся к личному местоимению | 1042 | 1042 | 100% |
| Обособление согласованных определений, оторванных от определяемого слова | 1042 | 1042 | 100% |
| Плеоназмы | 1042 | 1042 | 100% |
| Правописание "зато" | 190 | 1042 | **18%** |
| Правописание "не" с глаголами | 1042 | 1042 | 100% |
| Правописание "не" с прилагательными | 1042 | 1042 | 100% |
| Правописание "оттого" | 191 | 1042 | **18%** |
| Правописание "причем" и "притом" | 191 | 1042 | **18%** |
| Правописание "также" | 190 | 1042 | **18%** |
| Правописание "чтобы" | 191 | 1042 | **18%** |
| Правописание гласных в суффиксах причастий | 1042 | 1042 | 100% |
| Правописание приставок пре- и при- | 1042 | 1042 | 100% |
| Правописание разделительных "ъ" и "ь" | 1042 | 1042 | 100% |
| Правописание сложных прилагательных | 1003 | 1042 | 96% |
| Правописание суффиксов -еньк, -оньк в существительных | 336 | 1042 | **32%** |
| Правописание суффиксов -иц, -ец в существительных среднего рода | 935 | 1042 | 90% |
| Правописание суффиксов −ек, −ик | 1042 | 1042 | 100% |
| Правописание суффиксов −инск, −енск в прилагательных | 83 | 1042 | **8%** |
| Правописание частицы "не" с причастиями | 1042 | 1042 | 100% |
| Правописание частицы "не" с существительными | 1042 | 1042 | 100% |
| Правописание частицы -таки | 43 | 1042 | **4%** |
| Правописание числительного пол- | 644 | 1042 | 62% |
| Пунктуация в цельных по смыслу (неразложимых) сочетаниях | 113 | 1042 | **11%** |
| Пунктуация при вводных словах и конструкциях | 732 | 1042 | 70% |
| Пунктуация при повторяющихся союзах | 1042 | 1042 | 100% |
| Склонение количественных числительных | 1 | 1042 | **0%** |
| Склонение числительных "полтора", "полторы", "полтораста" | 82 | 1042 | **8%** |
| Слитное, раздельное и дефисное написание наречий | 1042 | 1042 | 100% |
| Согласование причастий с определяемым словом | 1042 | 1042 | 100% |
| Тире в бессоюзных предложениях | 1042 | 1042 | 100% |
| Тире между подлежащим и сказуемым | 1042 | 1042 | 100% |
| Тире при приложении | 1042 | 1042 | 100% |

## Summary

- **27/48 rules at 100%** target
- **6/48 rules at 62-96%** (near target, source text limitation)
- **15/48 rules below 50%** (rare forms in Wikipedia text)

### Shortfall categories

| Category | Rules | Root cause |
|---|---|---|
| Rare conjunctions | зато, оттого, также, чтобы, причём (~190 ea) | `conjunction_merge` subtype doesn't filter by specific word |
| Colloquial idioms | фразеологизмы (3) | Wikipedia lacks colloquial text |
| Rare morphology | -таки (43), -еньк (336), -инск (83), полтора (82) | Rare word forms in encyclopedic text |
| Narrow triggers | союзы на стыке (24), деепричастия после союзов (273) | Genuinely rare syntactic patterns |
| Missing handler | Склонение количественных числительных (1) | Handler only covers полтора, not all cardinal numerals |
