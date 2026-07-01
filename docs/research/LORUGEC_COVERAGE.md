# LoRuGEC Rule Coverage by Handler

Generated: 2026-05-01 | **fully re-verified live: 2026-06-13** | synterr post-audit HEAD | 28 handlers, 75 subtypes
Source: `data/lorugec_rule_map.json` / `data/lorugec_join.json` (48 LoRuGEC rules, 960 examples, val=348 / test=612, no train)

> **This is a verified-works map.** Unlike the 2026-05 revision (a handler-*claim*
> map), every row below was checked by live `pipeline.apply_error` invocations
> against the current code: at least one crafted sentence per rule, plus the
> rule's canonical LoRuGEC example where usable, rerun several times to cover
> randomized subtype/position choices. Verdicts:
>
> - **FULL** — the handler was observed generating precisely this rule's error,
>   including on the rule's canonical error shape.
> - **PARTIAL** — the handler fires and produces a genuine error under the
>   rule, but misses the canonical benchmark shape, covers only one error
>   direction, or is gated to a narrower sub-case. Per-row notes say which.
> - **NONE** — no handler produces this rule's error class. (There are none.)

## Summary

| Status | Rules | May-2026 (verified col.) |
|--------|------:|------:|
| **FULL** | 37 | ~33 |
| **PARTIAL** | 11 | 15 |
| **NONE** | 0 | 0 |

Headline movement since May: the three «как» rows (Known-broken #1) are fixed
and verified; four punctuation PARTIALs closed (вводные, определения ×2, СПП
общая часть, однородные придаточные, стык союзов); five former claim-level
FULLs were demoted on live verification (пре/при, гласные после ц, гласные
после шипящих, -таки, наречия). Details in the changelog at the bottom.

## Per-rule mapping

### spell_affixes (2 FULL, 3 PARTIAL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Правописание разделительных "ъ" и "ь" | `spelling:soft_sign` | FULL | подъехал→подьехал, вьюга→вюга. Caveat: same subtype also emits non-разделительный soft-sign errors (ночь→ноч, §71-class). |
| Правописание приставок пре- и при- | `orthographic_spelling:pre_pri` | PARTIAL | Fires only when the *surface form* is a morpheme-dict entry (прибыть→пребыть, пригородный→прегородный). Inflected surfaces refuse — the guard looks up the surface in the lemma-keyed unified dict (`_swap_pre_pri` ignores the `lemma` argument `_apply_subtype` already has). The canonical LoRuGEC example «пребывает» is refused. |
| Гласные "ы" и "и" после приставок | `orthographic_spelling:y_i_after_prefix` | FULL | разыскать→разискать, безынтересным→безинтересным. |
| Гласные после "ц" | `orthographic_spelling:vowel_after_ts` | PARTIAL | Fires on suffix/ending positions (птицы→птици). Root-internal positions are skipped by design (morpheme-position gate, 2026-03) — the canonical LoRuGEC error герцога→герцега is a root position and refuses. |
| Гласные после шипящих | `orthographic_spelling:vowel_after_sibilant` | PARTIAL | Fires on suffix/ending positions (врачом→врачём, девчонка→девчёнка). Canonical жюри→жури is root-internal → refused by the same gate. |

### spell_noun (3/3 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified |
|---|---|---|---|
| -еньк, -оньк в существительных | `orthographic_spelling:suffix_enk_onk` | FULL | душенька→душонька, Лизонька→Лизенька |
| -иц, -ец в существительных среднего рода | `orthographic_spelling:suffix_its_ets` | FULL | письмецо→письмицо, маслице→маслеце |
| -ек, -ик | `orthographic_spelling:suffix_ek_ik` | FULL | овражек→овражик, ключик→ключек |

### spell_verb / participle (2/2 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified |
|---|---|---|---|
| "н" и "нн" в суффиксах прилагательных | `orthographic_spelling:nn_suffix` | FULL | государственной→государственой, песчаной→песчанной (both directions) |
| Гласные в суффиксах причастий | `orthographic_spelling:participle_suffix` | FULL | борющийся→борящийся, тающий→таящий |

### spell_adj (1 FULL, 1 PARTIAL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| -инск, -енск | `orthographic_spelling:suffix_insk_ensk` | FULL | сестринский→сестренский (canonical word), екатерининский→екатериненский |
| Сложные прилагательные | `compound_spelling:compound_adj` | PARTIAL | Merged→hyphen direction works, including inflected forms (железнодорожному→железно-дорожному, древнерусский→древне-русский). Hyphen→merged direction is dead in practice — stanza tokenizes hyphenated compounds into fragments, so list entries like научно-исследовательский never match. Both lexicons are small closed lists (37 + 15 stems); canonical «раннецветущие» is not in them. |

### spell_compounds (2/2 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified |
|---|---|---|---|
| Дефис в письменных эквивалентах сложных слов | `compound_spelling:num_dash` | FULL | 25-процентный→25процентный, 2-е→2е |
| Числительное пол- | `compound_spelling:pol_spelling` | FULL | полвека→пол-века (canonical exact), пол-лимона→поллимона |

### spell_adverb (0 FULL, 1 PARTIAL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Слитное/раздельное/дефисное написание наречий | `adverb_spelling:*` (4 directional subtypes) | PARTIAL | All three families fire live: наконец→на конец (solid→sep), по-новому→по новому (hyphen→sep), во время грозы→вовремя грозы (sep→solid). But coverage is bounded by the closed §53–58 lists; the canonical LoRuGEC item «за полночь→заполночь» is not in the list (never was) and refuses. |

### spell_function (9 FULL, 1 PARTIAL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| "не" с причастиями | `function_spelling:ne_attachment / ne_detachment` | FULL | не найденное→ненайденное (canonical shape with dependent words), незаконченный→не законченный |
| "не" с глаголами | `function_spelling:ne_attachment` | FULL | не знает→незнает |
| "не" с прилагательными | `function_spelling:ne_attachment / ne_detachment` | FULL | не простая, а…→непростая, а…; неправильный→не правильный |
| "не" с существительными | `function_spelling:ne_attachment / ne_detachment` | FULL | не правду, а ложь→неправду, а ложь (canonical contrast shape); неудача→не удача. Exact canonical noun «несмелость» refuses (word-known guard), same construction fires with dictionary nouns. |
| Правописание "чтобы" | `function_spelling:conjunction_split / merge` | FULL | чтобы→что бы, что бы→чтобы |
| Правописание "также" | `function_spelling:conjunction_split / merge` | FULL | а также→а так же, так же, как→также, как |
| Правописание "зато" | `function_spelling:conjunction_split / merge` | FULL | зато→за то, за то, что→зато, что |
| Правописание "оттого" | `function_spelling:conjunction_split / merge` | FULL | оттого, что→от того, что; от того, как→оттого, как |
| Правописание "причем"/"притом" | `function_spelling:conjunction_split / merge` | FULL | причем→при чем, при чем→причем |
| Частица -таки | `function_spelling:taki_hyphen` | PARTIAL | Only the hyphen-removal direction is implemented (всё-таки→всё таки). The canonical direction — standalone «таки» after a noun gaining a hyphen (снегу таки→снегу-таки) — is explicitly skipped in `_apply_taki` ("skip standalone таки for now"). опять-таки / довольно-таки also refuse (tokenizer splits them). |

### punct_dash (3/3 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Тире между подлежащим и сказуемым | `dash_delete:dash_subj_pred` (+ fall-through `dash_other`) | FULL | Москва — столица→Москва столица (subj_pred). The very common «X — это Y» canonical (дом — это…) **is** generated, but classifies as `dash_other`: the §79 gate (2026-06-10) excludes PRON «это» from the subj_pred right-side check, so it falls through. Coverage intact (lorugec preset weights dash_other), schema subtype label wrong for это-sentences. |
| Тире при приложении | `dash_delete:dash_apposition` + `dash_to_comma` | FULL | Final apposition: дерево — осину → deleted (dash_apposition) and → дерево , осину (dash_to_comma, now correctly restricted to §93 п.8 б sentence-final appositions). The canonical paired apposition «мы — весёлая детвора —» is generated too (second dash deleted, exactly the benchmark src) but classifies as `dash_subj_pred` — another label-only caveat. |
| Тире в бессоюзных предложениях | `dash_delete:dash_asyndetic` | FULL | За двумя зайцами погонишься — ни одного…→dash deleted (canonical exact); Лес рубят — щепки летят ✓. (May's "1 of §118's 8 sub-rules" demotion no longer holds for the delete direction: any asyndetic dash present in source is deletable regardless of semantic sub-relation.) |

### punct_comma (6 FULL, 5 PARTIAL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Запятая перед "как": 1 (обстоятельственные/фикс.) | `comma_insert:comma_before_kak` | FULL | «рекомендуется как минимум…»→comma inserted before как (canonical exact). **Known-broken #1 fixed** (`546204a`, appositive-«как» disambiguation by head POS instead of dep_rel alone). |
| Запятая перед "как": 2 (в качестве) | `comma_insert:comma_before_kak` | FULL | «работал в этой организации как экономист»→…, как экономист (canonical exact); also работал как зверь ✓. |
| Запятая перед "как": 3 (предикатив) | `comma_insert:comma_before_kak` | FULL | «рассматривались как символы»→…, как символы (canonical exact); Дети как цветы жизни ✓. |
| Запятая в фразеологических выражениях | `comma_insert:comma_in_set_phrase` | PARTIAL | Fires exactly per the rule's definition (repeated и/или/ни): и день и ночь→и день, и ночь; ни свет ни заря→ни свет, ни заря. But the canonical benchmark example «о том, о сём» is a repeated-*preposition* phrase with no conjunction anchor — outside `_FROZEN_PHRASES` — and refuses. |
| Запятая в цельных по смыслу сочетаниях | `comma_insert:comma_in_indivisible` | PARTIAL | Fires on the right phrases but always inserts *inside* after the first word («как , ни в чем не бывало», «не , то чтобы») — the canonical error puts commas *around* the phrase («, как ни в чем не бывало ,»). Wrong insertion point → produced errors don't match the benchmark shape and look unnatural. |
| Однородные члены: пары | `comma_delete:comma_homogeneous` | PARTIAL | Delete direction fires (о любви и ненависти, о жизни и смерти → comma between pair groups deleted). Canonical direction is the opposite — *extra* commas splicing pair unions («, и Лена , и Света») — no insert path exists for non-clausal pairs. |
| Пунктуация при вводных словах | `comma_pair_delete:pair_parenthetical` (+ `comma_delete:comma_parenthetical`) | FULL | Он, конечно, придёт→Он конечно придёт; «Стало быть, по-вашему, …» (canonical) fires. Canonical direction *is* deletion — May's "INSERT missing" demotion was off-target. |
| Пунктуация при повторяющихся союзах | `comma_delete:comma_homogeneous` | PARTIAL | Deletes the required comma before a repeated «и» (и петь, и танцевать→и петь и танцевать) — a genuine violation. Canonical direction (extra comma before the *first* «и»: «это , и самостоятельное блюдо») is not generatable. |
| Обособление деепричастий после союзов | `comma_pair_delete:pair_gerund` | PARTIAL | Pair-deletion fires incl. on the canonical sentence (…, а выбирая между казино и банком(,)…). But the rule's specific point — the comma between союз and деепричастие — has canonical direction *insertion* («, а , выбирая»), which no handler produces. |
| Обособление определений к личному местоимению | `comma_pair_delete:pair_participle` | FULL | Canonical fires: У меня(,) воспитанной в цыганском таборе…(,) — isolation commas deleted; Он, уставший…, ✓. (Handler deletes the pair; benchmark src drops one — same violation class.) |
| Обособление определений, оторванных от слова | `comma_pair_delete:pair_participle` | FULL | Canonical fires: На стене(,) открытые всем ветрам(,) висят часы. |

### punct_compound / punct_complex (3/3 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Запятая между частями СПП с общей частью | `comma_insert:comma_clause_junction` | FULL | Canonical error reproduced exactly: «Вчера … шли бои(, )и одна ракета упала…» → comma inserted before «и» despite the common element. Closed since May (was "общая часть not modeled"). |
| Запятая между однородными придаточными | `comma_delete:comma_subordinate` + `comma_insert:comma_clause_junction` | FULL | Both directions live on the canonical sentence: delete a required comma between «как»-clauses, and insert the canonical extra comma before «и как ветшает усадьба». |
| Запятая на стыке двух союзов | `comma_insert:comma_between_conjunctions` | FULL | Canonical benchmark sentence reproduced exactly: «…завораживают, и(, )когда мы впервые увидели…, то…». Covers coordinating+subordinating junctions with a correlative («и когда … то»); subordinating+subordinating junctions («что если … то») are not matched — minor caveat within FULL. |

### lex_choice (2/2 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified |
|---|---|---|---|
| Лексическая сочетаемость | `collocation:collocation` | FULL | играет роль→имеет/несёт роль, одержал победу→завоевал/получил победу |
| Плеоназмы | `pleonasm:pleonasm` | FULL | автобиографию→свою автобиографию, вакансия→свободная вакансия |

### morph_numeral (2/2 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified |
|---|---|---|---|
| Склонение количественных числительных | `numeral_declension:numeral_declension` | FULL | о пятидесяти→о пятьдесят; canonical multi-word cardinal partially un-declines component-wise (Из двухсот шестидесяти пяти → Из двести шестидесяти пяти / Из двухсот шестьдесят пяти) |
| Склонение полтора/полторы/полтораста | `numeral_declension:numeral_poltora` | FULL | около полутора→около полтора, до полутора миллионов→до полтора миллионов (canonical exact) |

### gov_case + syntax_advanced (2/2 FULL)

| LoRuGEC rule | Handler.subtype | Verdict | Verified / note |
|---|---|---|---|
| Согласование причастий с определяемым словом | `adj_case` (via amod arc, `--depparse`) | FULL | Canonical fires: с гостями, присутствовавшими→присутствовавшие/присутствовавших; о книге, прочитанной→прочитанная |
| Нарушение норм управления | `noun_case` (obl/nmod/iobj/obj-gated) + `preposition` | FULL | гордимся страной→страна/стране (case-government), из Москвы→с Москвы (§199 preposition confusion). Note: the *lorugec preset* zero-weights `noun_case`, so in preset sampling this rule rides on `preposition` alone (the preset comment attributing управление to `adj_case` is a mislabel — adj_case is agreement). Canonical spurious-preposition insertion («коснуться до нас») is not a covered sub-pattern. |

## Remaining gaps (all PARTIAL, no NONE)

1. **пре/при** — surface-form lookup in the lemma-keyed morpheme dict blocks all
   inflected targets. Cheapest close: pass `lemma` (already available in
   `_apply_subtype`) into `_swap_pre_pri`'s `has_prefix` check.
2. **Гласные после ц / после шипящих** — root positions deliberately skipped
   since the 2026-03 morpheme-position gate; benchmark canonicals are root
   positions (герцога, жюри). Closing would need a stress-checked root
   whitelist, at precision risk.
3. **-таки** — separate→hyphen direction unimplemented; canonical is that
   direction.
4. **Сложные прилагательные** — hyphen→merged direction dead to tokenization;
   lexicons small.
5. **Наречия** — mechanism verified in all three directions; canonical item
   «за полночь» missing from the §53–58 lists (add it).
6. **Фразеологические выражения** — repeated-preposition variant («о том о
   сём») unrepresentable in the conjunction-keyed matcher.
7. **Цельные по смыслу** — insertion point is always phrase-internal after
   word 1; should be before the phrase (and/or paired around it).
8. **Однородные пары / повторяющиеся союзы / деепричастия после союзов** —
   three rules whose canonical direction is comma *insertion* at spots where
   only deletion handlers exist. A small `comma_insert` extension (insert
   before first repeated conjunction; between союз and деепричастие; splice
   pair unions) would close all three.

## Subtype-label caveats (coverage OK, tag wrong)

- «X — это Y» dash deletions emit `dash_other`, not `dash_subj_pred` — the
  2026-06-10 §79 gate excludes PRON «это» as a predicate head. Anything
  consuming subtype/schema tags (rozental L2 mapping) mislabels these.
- Paired-apposition dash deletions («мы — весёлая детвора —») emit
  `dash_subj_pred`, not `dash_apposition`.

## What changed since the 2026-05 assessment

**Closed (was broken/partial in May, verified FULL now):**

- Three «как» rows — Known-broken #1 fixed by `546204a` (head-POS
  disambiguation of stanza's blanket `mark` on «как»); all three canonical
  benchmark sentences verified live.
- Запятая на стыке двух союзов — `comma_between_conjunctions` reproduces the
  canonical «и, когда … то» error exactly.
- СПП с общей частью + однородные придаточные — `comma_clause_junction`
  covers the canonical insert direction.
- Вводные слова, определения к местоимению, определения оторванные — May's
  PARTIAL rationales don't hold against live runs on the canonicals.
- General-cardinal declension (Known-broken #2) — re-confirmed live.

**Demoted (May said FULL at claim level; live verification says PARTIAL):**

- пре/при (inflected surfaces refuse — behavior dates to 2026-03, first
  *detected* now), гласные после ц, гласные после шипящих (root gate, also
  2026-03), -таки (canonical direction never implemented), наречия (canonical
  item never in the lists), фразеологические выражения (canonical is a
  repeated-preposition phrase), цельные по смыслу (wrong insertion point).
  None of these are June regressions — the May FULLs were unverified claims.

**Actual June behavior changes worth knowing:**

- `85575bd` (§79/§82/§93 dash exceptions) — net precision win; side effect is
  the two subtype-label caveats above, and `dash_to_comma` is now correctly
  restricted to sentence-final appositions (mid-sentence dash→comma is a
  non-error per §93 п.1–2, so May's looser firing was generating non-errors).

## What this means for the paper

Verification, not implementation, was the right call: live probing moved 8
rows in both directions relative to the claim map. The remaining 11 PARTIALs
split into three cheap fixes (pre_pri lemma pass-through, «за полночь» list
entry, indivisible insertion point), three direction gaps closable by one
comma-insert extension, and five accepted precision trade-offs (root-position
spelling, -таки reverse direction, compound-adj tokenization). Per-row
verified sentences above make this doc re-checkable: rerun any row with
`uv run synterr corrupt -l ru -e <handler>:<subtype> --depparse "<sentence>"`.
