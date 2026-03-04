# Punctuation Heuristics

Dependency-tree-based comma and dash classification for synthetic error generation.

Source: `src/synterr/languages/russian/errors/punctuation.py`
Evaluated on: 10k Lenta.ru sentences via stanza with depparse.

## Core Idea

Stanza's dependency parser assigns every token a `head_idx` (syntactic parent) and `dep_rel` (relation label). Punctuation tokens get these too — a comma's head reveals **why** it's there:

```
"Студент, читающий книгу, ушёл"

  0 Студент    nsubj → ушёл(5)
  1 ,          punct → читающий(2)     ← comma points to the construction it delimits
  2 читающий   acl   → Студент(0)
  3 книгу      obj   → читающий(2)
  4 ,          punct → читающий(2)     ← BOTH commas share the same head
  5 ушёл       root
```

## Single Comma Classification (`_classify_comma`)

Priority order: parenthetical > isolation > compound/homogeneous > subordinate > fallback.

### 1. Parenthetical (`comma_parenthetical`)

**Signal:** `comma.head.dep_rel ∈ {parataxis, discourse}`

Stanza marks parenthetical insertions as `parataxis`:
- Вводные слова: конечно, вероятно, к сожалению
- Speech attribution: "сказал он", "по словам...", "как сообщает..."
- Inserted clauses: "ко всеобщему удивлению"

```
"По данным ФСБ, погибли четверо"
  данным ──parataxis──→ погибли
  ,      ──punct──→ данным             ← head is parataxis → parenthetical
```

**Fallback:** Adjacent lemma in `PARENTHETICAL_WORDS` set (~28 words).

**Impact:** 251 → 4,597 examples after switching from word list to dep_rel.

### 2. Isolation (`comma_isolation`)

**Signal:** `comma.head.dep_rel ∈ {acl, acl:relcl, advcl}`

Covers all обособленные обороты:
- `acl`: причастный оборот ("колонна, **отступавшая** по шоссе, обстреливалась")
- `acl:relcl`: relative clause ("дом, **который** построил Джек, стоял")
- `advcl`: деепричастный оборот ("**приехав** домой, он лёг")

Both opening and closing commas point to the same head → both classified correctly.

**Fallback (3 layers):**
1. Adjacent token has `dep_rel ∈ {acl, acl:relcl, advcl}`
2. Adjacent token has `VerbForm=Part` or `VerbForm=Conv`
3. **Subtree BFS**: scan left up to 15 tokens for an `acl`/`advcl` node, compute its subtree span via BFS (excluding PUNCT), check if comma sits at `subtree_max + 1`:

```
"колонна, отступавшая по шоссе от Перемышля к Саноку, обстреливалась"
  subtree(отступавшая) = {отступавшая, по, шоссе, от, Перемышля, к, Саноку}
  subtree_max = idx(Саноку) = comma_idx - 1                → isolation ✓
```

### 3. Compound (`comma_compound`)

**Signal:** `comma.head.dep_rel = conj` AND:
- Head is `VERB`/`AUX`
- Head's own head is also `VERB`/`AUX`
- Head has an `nsubj`/`nsubj:pass` dependent (its own subject)

The subject check distinguishes compound sentences from homogeneous members:

```
"Солнце светило, и птицы пели"               → compound (both have subjects)
"яблоки, и груши"                             → homogeneous (no subjects)
```

```
  светило ──root
  ,       ──punct──→ пели
  пели    ──conj──→ светило     ← conj between two VERB nodes
  птицы   ──nsubj──→ пели       ← пели has its own subject → compound
```

**Fallback:** Next token is CCONJ with `dep_rel=cc`. Follow `cc.head` — if it's a finite verb with `nsubj`, it's compound.

### 4. Homogeneous (`comma_homogeneous`)

**Signal:** `comma.head.dep_rel = conj` but compound criteria not met (head isn't finite verb, or no subject).

```
"Мама, папа и бабушка пришли"
  ,     ──punct──→ папа
  папа  ──conj──→ Мама          ← conj, but NOUN not VERB → homogeneous
```

**Fallback:** Left and right tokens share the same `head_idx`, or one is `conj` of the other.

**Last-resort fallback:** If nothing else matches → homogeneous. This catch-all bucket went from 54% to 26% after the dep-tree rewrite.

### 5. Subordinate (`comma_subordinate`)

**Signal:** `comma.head.dep_rel ∈ {ccomp, advcl, csubj, csubj:pass}`

Note: `advcl` appears in both isolation (priority 2) and subordinate. Since isolation runs first, `advcl` commas are caught as isolation. Only `ccomp` typically reaches this check.

```
"Он знал, что она придёт"
  ,       ──punct──→ придёт
  придёт  ──ccomp──→ знал        ← ccomp → subordinate
```

**Fallback:** Next token has `dep_rel=mark` or `pos=SCONJ`.

## Comma Pair Detection (`_find_comma_partner`)

Detects paired commas of обособленные обороты and deletes both.

**Algorithm:**
1. Get comma's head token
2. Check `head.dep_rel` against `PAIR_DEPRELS` map
3. Find all other commas with the same `head_idx`
4. Only trigger on the first (leftmost) comma → avoid double processing
5. Delete second comma first (higher index), then first → correct index handling

**Pair types:**

| `dep_rel` | Subtype | Construction | 10k Lenta count |
|-----------|---------|-------------|----------------:|
| `acl` | pair_participle | причастный оборот | 648 |
| `acl:relcl` | pair_relative | придаточное определительное | 15 |
| `advcl` + `VerbForm=Conv` | pair_gerund | деепричастный оборот | 14 |
| `parataxis` | pair_parenthetical | вводное слово/выражение | 76 |
| `appos` | pair_apposition | приложение | 2 |

**Critical filter:** `advcl` without `VerbForm=Conv` is excluded. A full subordinate clause ("когда стемнело") also has paired commas, but those are clause boundaries, not обособление.

## Dash Classification (`_classify_dash`)

POS-based (no dep tree needed):

- **dash_subj_pred:** left is NOUN/PRON/PROPN, right is NOUN/ADJ/NUM/VERB/PROPN ("Москва — столица")
- **dash_other:** everything else ("пришёл — увидел")

## Distribution (10k Lenta sentences, 19,600 single + 755 pair examples)

### Single comma deletions
| Subtype | Count | % |
|---------|------:|---:|
| comma_isolation | 6,935 | 35.4 |
| comma_homogeneous | 5,042 | 25.7 |
| comma_parenthetical | 4,597 | 23.5 |
| comma_subordinate | 2,341 | 11.9 |
| comma_compound | 667 | 3.4 |

### Pair deletions
| Subtype | Count |
|---------|------:|
| pair_participle | 648 |
| pair_parenthetical | 76 |
| pair_relative | 15 |
| pair_gerund | 14 |
| pair_apposition | 2 |

### Dashes
| Subtype | Count |
|---------|------:|
| dash_subj_pred | 10 |
| dash_other | 8 |

## Known Limitations

1. **`advcl` ambiguity**: "когда"-clauses are `advcl`, same as gerund phrases. Single commas before "когда" get classified as `comma_isolation` rather than `comma_subordinate` because isolation takes priority.

2. **Homogeneous still at 26%**: some are genuinely homogeneous, but includes misclassified clarifying members ("а именно...") and stanza parsing errors.

3. **Appositions rare in news**: only 2 on 10k Lenta sentences. Need different corpora (literary text, Wikipedia) to validate.

4. **Stanza parsing errors cascade**: incorrect dep_rel assignments lead to misclassification. No mitigation beyond fallback heuristics.

5. **No comma insertion yet**: current handlers only delete existing commas. Insertion (generating "missing comma" positions) can reuse the same heuristics in reverse — future work.
