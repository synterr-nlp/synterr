# V5 handoff — remaining build work (written 2026-07-16 by the gector-side session)

You are a fresh session in synterr. This file is your work order. Read
`docs/V5_PLAN.md` first (esp. the direction-mismatch appendix) — it is the
contract; this file is the execution detail. House rules: `AGENTS.md`
(gate = `uv run ruff check src tests` + full pytest green; precision-first —
skip rather than emit a doubtful corruption; orient in the NKS synterr realm
if available).

**Do NOT run the final v5 generation (W5)** — dataset size is decided at the
team call (Mon/Tue Jul 20–21). Everything below is handler + pool work that
must land before it.

## Task 1 — NP-level «пары» insert subtype (the last piece of W1)

Target LORuGEC rule: «Знаки препинания в предложениях с однородными членами:
пары». Test direction: 20/20 items need comma DELETION ⇒ the generator must
corrupt by INSERTING a comma (model then learns to remove it). This was v4's
worst suppression (10% → 0%).

**Read before coding — do not theorize** (both sources are local, uncommitted
for copyright):

```bash
# §87 full text (subpara-level; note the попарное соединение clause and the
# §114 цельные-выражения exceptions — cross-ref only, don't claim the §):
python3 - <<'EOF'
import csv
csv.field_size_limit(10**7)
for r in csv.DictReader(open('../gector/data/rozental_book/master.csv')):
    if r['para'] == '87':
        print(r['subpara'], '|', r['rule_text'][:400], '\n')
EOF
# All 20 LORuGEC items for the rule (see what the wrong commas actually
# look like — that's your corruption target):
python3 - <<'EOF'
import json
for line in open('../rozental/data/lorugec.jsonl'):
    ex = json.loads(line)
    if ex['rule'].endswith('пары'):
        print(ex['split'], '|', ex['src'], '=>', ex['tgt'])
EOF
```

Mechanics: `comma_clause_junction` (punctuation.py) requires a clausal head,
so noun-phrase conjuncts never trigger — that's exactly the gap. The new
subtype detects NP/AdjP conjuncts joined by repeating or paired conjunctions
via depparse (`conj` relations) and inserts the comma the norm forbids.
Mirror the gate style of the six Jul-2 insert subtypes (commit `1544f0b`) —
each has a tight lexical/structural gate and an explicit accepted-risk note.
Wire the subtype into the handler-mapping section of
`src/synterr/schemas/data/rozental.yaml` (tag family `pu_comma`) and into the
lorugec preset so the rule key gets a `[delete]`-direction twin. Schema yaml
is v1.1 — add mapping entries only, do not touch tag definitions or paras.

Verify: unit tests in the style of the existing comma-subtype tests + run
`scripts/generate_review.py` so the new subtype gets a human-QA review bundle
(night-wave precedent, commit `d35feac`). Full suite green (1371+).

## Task 2 — asyndetic dash, insert side (W2)

`dash_asyndetic` (delete direction) exists. Add the insert side: a spurious
dash into an asyndetic clause junction where the norm wants comma/colon.
Read §116–118 from the same master.csv first (esp. §118: when the dash IS
correct — those contexts must be excluded, precision-first), and check which
LORuGEC dash rules test which direction before choosing gates (same jsonl
recipe as above, filter 'Тире').

## Task 3 — two starving host pools (rest of W3)

`data/pools/` + `scripts/mine_class_pools.py` are the pattern (seed 42,
cap 2000, sources per `pools.meta.json`). Missing:

1. **numeral_declension hosts** — sentences with cardinal numerals in oblique
   cases (the rule has 8 training examples total; `numeral_poltora.txt`
   exists but plain declension doesn't). Mine Taiga×3 + RuBLiMP pool.
2. **comma_in_set_phrase boost** — current pool is 28KB (thinnest). Widen the
   set-phrase lexicon the miner matches on before re-mining.

Update `pools.meta.json` seen/sampled counts; keep it seeded.

## Task 4 — the «47K duplicates» investigation (before touching pool build)

Task #50 claims a 47K-duplicate limitation in the v4 pool, but
`build_v4_sources.py` already dedupes via `set()`. Find where the figure came
from (candidates: dups WITHIN mine_scarce_sents output across sources;
near-dups surviving exact-match dedup; or a stale claim). Measure the actual
duplication of `data/mixed_sources_v4.txt` (exact + normalized). Fix only
what the measurement shows; write the finding into this file's log below.

## Order & discipline

Tasks are independent; 1 is highest-value. Small gate-green commits, one
concern each. Log progress by appending dated entries under «Log» below —
the gector-side session and Anna read this file to sync the plan after.

## Log

*(executing session appends here: date · task · what landed · commit)*
