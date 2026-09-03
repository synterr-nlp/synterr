# Error types (Russian)

**49 handlers, 110 subtypes** across four detection categories (`SPELL`,
`MORPH`, `PUNCT`, `OTHER`). The full subtype lists and Rozental §
mappings are in
[`CLAUDE.md`](https://github.com/synterr-nlp/synterr/blob/master/CLAUDE.md);
`uv run synterr list-errors -l ru` is the live, authoritative listing.
LoRuGEC rule coverage is verified sentence-by-sentence in
[`docs/research/LORUGEC_COVERAGE.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/research/LORUGEC_COVERAGE.md)
(37/48 FULL, 11/48 PARTIAL, 0/48 NONE).

A 5-handler French proof-of-concept exists on the same architecture
(`src/synterr/languages/french/`, stanza `fr_sequoia` backend) — see
[Extending synterr](extending.md#6-add-a-new-language).

## Spelling — `SPELL`

| Handler | What it does | Example |
|---------|--------------|---------|
| `spelling` | Phonetic confusions, keyboard typos, alternating/unchecked roots (§2–3) | *молоко* → *малако* |
| `function_spelling` | не/ни attachment, conjunction split/merge, -таки, negative-pronoun не/ни | *чтобы* → *что бы* |
| `orthographic_spelling` | пре/при, ы/и after prefixes, suffixes, participles, vowels after ц/sibilants (incl. root §5 п.3, -ем/-им endings) | *преинтересный* → *приинтересный* |
| `compound_spelling` | Hyphen / solid / separate writing of compounds, numeral-dash, пол- | *по-моему* → *по моему* |
| `adverb_spelling` | Adverb writing variants (4 directional subtypes) | *по-русски* → *по русски* |

## Morphological — `MORPH`

| Handler | What it does | Example |
|---------|--------------|---------|
| `noun_case` | Wrong case on a governed/subject/other noun (dep-arc gated: obl/nmod/iobj/obj, nsubj, appos/conj/…) | *на столе* → *на стол* |
| `noun_case_prep` | Second locative -у vs standard -е (§ second locative) | *в лесу* → *в лесе* |
| `noun_case_gen_partitive` | Partitive genitive -а/-у (§150) | *история народа* → *народу* |
| `noun_case_instr_pl` | Instrumental plural -ями/-ьми (§155) | *дверями* → *дверьми* |
| `noun_number` | Singular ↔ plural | *книга* → *книги* |
| `noun_number_gen_pl` | Nonstandard genitive plural (§154) | *носков* → *носок* |
| `neg_genitive` | Acc↔Gen under negation, dep-arc (§201) | *не читал книгу* ↔ *книги* |
| `adj_case`, `adj_number`, `adj_gender` | Adjective/participle agreement via `amod` arc | *новая книга* → *новый книга* |
| `adj_form` | Short↔full adjective form | *готовы* → *готовые* |
| `adj_possessive_form` | Possessive-adjective oblique variants (§162) | *маминого* → *мамина* |
| `adj_short_en_enen` | Short-form -ен/-енен (§160) | *свойствен* → *свойственен* |
| `adj_double_comparative` | Insert pleonastic «более» before a synthetic comparative (length-changing) | *лучше* → *более лучше* |
| `verb_person_number` | Verb conjugation against `nsubj` | *они читает* → *они читают* |
| `verb_tense` | Past / present / future swap (finite forms only) | *читал* → *читает* |
| `verb_iterative_suffix` | о/а iterative suffix (§172.2) | *обусловливать* → *обуславливать* |
| `numeral_declension` | Numeral declension, incl. полтора | *полтора часа* → *полутора часа* |
| `pronoun_svoy` | свой → personal possessive (§167) | *нашёл свою книгу* → *мою книгу* |
| `pronoun_sebya` | себя → personal pronoun (§168) | *купил себе* → *купил ему* |
| `pronoun_n_form` | н-augment after prepositions (§169–170) | *у него* → *у его* |
| `agr_sv_collective`, `agr_sv_counting`, `agr_sv_approximate`, `agr_sv_compound`, `agr_sv_coordinated` | Subject–verb agreement flips, dep-arc (§183–190) | collective/numeral/compound subjects |
| `agr_mn_apposition`, `agr_mn_compound_term`, `agr_mn_numeral_adj` | Modifier–noun agreement: toponyms, hyphen compounds, два/три/четыре + adjective (§193–197) | — |

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
| `word_omission` | Drop a function word (preposition or conjunction) |
| `word_insertion` | Insert a filler word (discourse marker, particle) |

## Punctuation — `PUNCT`

| Handler | What it does |
|---------|--------------|
| `comma_delete` | Delete a comma at clause boundaries (10 dep-tree-classified subtypes: subordinate, compound, parenthetical, isolation, homogeneous, interjection, response, repeated, asyndetic, vocative) |
| `comma_pair_delete` | Delete both commas of an isolated phrase (5 subtypes: participle, relative, gerund, parenthetical, apposition) |
| `comma_insert` | Add a spurious comma (12 subtypes, incl. bidirectional: homogeneous_conj §86, subj_pred, pseudo_parenthetical §99, after_odnako §99, compound_conj_split §108, x_ne_x §90) |
| `dash_delete` | Delete a required dash (5 subtypes: subj_pred, asyndetic, apposition, ellipsis §80, other) |
| `dash_to_comma` | Substitute dash → comma at sentence-final appositions (§93, non-length-changing) |

## Schema mapping cheat sheet

```bash
# See current mappings
uv run synterr coverage --lang ru --schema rlc
uv run synterr coverage --lang ru --schema rozental
uv run synterr coverage --lang ru --schema errant
```
