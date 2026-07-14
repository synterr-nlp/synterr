"""Build the schema viewer — a self-contained static HTML (table + tree).

Public build (committable; schema yaml only, no copyrighted text):

    uv run --with pyyaml python scripts/build_schema_viewer.py

Private build (adds full Rozental § text from the local book scrape;
output goes OUTSIDE the repo and must never be committed or pushed):

    uv run --with pyyaml python scripts/build_schema_viewer.py \
        --book-csv ../gector/data/rozental_book/master.csv \
        --private-out ../gector/schema_viewer_private.html
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "src" / "synterr" / "schemas" / "data" / "rozental.yaml"
PUBLIC_OUT = ROOT / "docs" / "schema_viewer.html"

PARA_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\s*[–-]\s*(\d+))?")


def para_numbers(paras_str: str) -> list[int]:
    """§ numbers referenced by a paras string ('§171, §173–175' → [171,173,174,175])."""
    nums: set[int] = set()
    for m in PARA_RE.finditer(paras_str or ""):
        a = int(m.group(1))
        b = int(m.group(3)) if m.group(3) else a
        nums.update(range(a, min(b, a + 40) + 1))
    return sorted(nums)


def load_schema() -> dict:
    doc = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    l0 = doc["detection_categories"]
    l1 = [
        {"tag": t, "l0": v.get("detection_category", ""), "descr": v.get("description", ""),
         "paras": v.get("rozental_paras", ""), "chapters": v.get("rozental_chapters", "")}
        for t, v in doc["primary_tags"].items()
    ]
    l2 = [
        {"tag": t, "parent": v.get("parent", ""), "descr": v.get("description", ""),
         "paras": v.get("paras", ""), "appl": v.get("l2_applicability", ""),
         "note": v.get("l2_note", "")}
        for t, v in doc["fine_grained_tags"].items()
    ]
    return {
        "name": doc.get("name", ""), "version": doc.get("version", ""),
        "description": doc.get("description", ""), "built": date.today().isoformat(),
        "l0": l0, "l1": l1, "l2": l2,
    }


def load_book(book_csv: Path) -> dict:
    """para → {title, subs: [text, ...]} from the master scrape (COPYRIGHTED)."""
    csv.field_size_limit(10**7)
    book: dict[str, dict] = {}
    with open(book_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            para = (r.get("para") or "").strip()
            if not para.isdigit():
                continue
            entry = book.setdefault(para, {"title": r.get("para_title", ""), "subs": []})
            text = (r.get("rule_text") or "").strip()
            if not text:
                continue
            if not (r.get("subpara") or "").strip():
                # Paragraph-level row: for §§ without subparas this holds the
                # whole text (65/213 §§). Drop a leading "§ N. Title" header
                # line; skip the row if nothing else remains.
                lines = text.split("\n")
                if lines[0].strip().startswith(f"§ {para}"):
                    text = "\n".join(lines[1:]).strip()
                if not text:
                    continue
            entry["subs"].append(text)
    return book


TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --bg:#fff; --fg:#1a1a1a; --muted:#666; --line:#ddd; --accent:#8b1e3f;
        --chip:#f0e6ea; --card:#fafafa; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16161a; --fg:#e8e8e8; --muted:#999; --line:#333;
          --accent:#e58aa5; --chip:#3a2a30; --card:#1f1f24; } }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.5 -apple-system,'Segoe UI',sans-serif;
       background:var(--bg); color:var(--fg); padding:1.5rem; }
h1 { font-size:1.3rem; margin:0 0 .2rem; }
.sub { color:var(--muted); font-size:.85rem; margin-bottom:1rem; }
.tabs button { font:inherit; padding:.4rem 1rem; border:1px solid var(--line);
  background:var(--card); color:var(--fg); cursor:pointer; }
.tabs button.on { background:var(--accent); color:#fff; border-color:var(--accent); }
#filter { font:inherit; padding:.4rem .6rem; border:1px solid var(--line);
  background:var(--bg); color:var(--fg); width:min(28rem,100%); margin:.8rem 0; }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:.85rem; }
th,td { text-align:left; padding:.35rem .55rem; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { position:sticky; top:0; background:var(--bg); cursor:default; }
code { font-family:ui-monospace,'SF Mono',monospace; font-size:.9em; }
.para-chip { display:inline-block; background:var(--chip); border-radius:.6em;
  padding:0 .45em; margin:0 .15em .15em 0; white-space:nowrap; }
.hasbook .para-chip { cursor:pointer; text-decoration:underline dotted; }
details { margin:.15rem 0 .15rem .9rem; }
summary { cursor:pointer; }
summary code { color:var(--accent); }
.muted { color:var(--muted); }
.l2row { margin-left:1.6rem; padding:.1rem 0; }
#paraPanel { position:fixed; right:0; top:0; bottom:0; width:min(34rem,92vw);
  background:var(--card); border-left:1px solid var(--line); padding:1rem;
  overflow-y:auto; display:none; box-shadow:-4px 0 18px rgba(0,0,0,.25); }
#paraPanel.show { display:block; }
#paraPanel h2 { font-size:1rem; margin-top:0; padding-right:2rem; }
#paraPanel .close { position:absolute; top:.6rem; right:.8rem; cursor:pointer;
  font-size:1.2rem; background:none; border:none; color:var(--fg); }
#paraPanel .subrule { border-left:3px solid var(--accent); padding-left:.7rem;
  margin:.7rem 0; white-space:pre-wrap; font-size:.85rem; }
.private-banner { background:var(--accent); color:#fff; padding:.3rem .8rem;
  border-radius:.4rem; display:inline-block; font-size:.8rem; margin-bottom:.8rem; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="sub" id="subtitle"></div>
<div id="banner"></div>
<div class="tabs">
  <button id="btnTable" class="on">Table</button>
  <button id="btnTree">Tree</button>
</div>
<input id="filter" type="search" placeholder="filter: tag / § / description…">
<div id="viewTable" class="wrap"></div>
<div id="viewTree" style="display:none"></div>
<aside id="paraPanel"><button class="close" onclick="hidePanel()">×</button><div id="paraBody"></div></aside>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const hasBook = !!D.book;
document.body.classList.toggle('hasbook', hasBook);
document.getElementById('subtitle').textContent =
  `${D.description} · v${D.version} · built ${D.built}` +
  ` · ${Object.keys(D.l0).length} L0 / ${D.l1.length} L1 / ${D.l2.length} L2`;
if (hasBook) document.getElementById('banner').innerHTML =
  '<span class="private-banner">PRIVATE BUILD — contains copyrighted book text; do not publish</span>';

const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;');
const paraNums = s => { const out=new Set();
  for (const m of String(s||'').matchAll(/(\\d+)(?:\\.(\\d+))?(?:\\s*[–-]\\s*(\\d+))?/g)) {
    const a=+m[1], b=m[3]?+m[3]:a; for(let n=a;n<=Math.min(b,a+40);n++) out.add(n); }
  return [...out]; };
const chips = s => paraNums(s).length
  ? paraNums(s).map(n=>`<span class="para-chip" data-para="${n}">§${n}</span>`).join('')
    + (String(s).match(/\\.(\\d)/)||String(s).includes('frame') ? ` <span class="muted">(${esc(s)})</span>` : '')
  : `<span class="muted">§-less</span>`;

function showPanel(n) {
  if (!hasBook) return;
  const e = D.book[String(n)];
  const body = document.getElementById('paraBody');
  body.innerHTML = e
    ? `<h2>§${n}. ${esc(e.title)}</h2>` + (e.subs.length
        ? e.subs.map(t=>`<div class="subrule">${esc(t)}</div>`).join('')
        : `<p class="muted">текст §${n} отсутствует в master-скрейпе (известная лакуна: §33)</p>`)
    : `<h2>§${n}</h2><p class="muted">не найден в скрейпе (известная лакуна оглавления: §49)</p>`;
  document.getElementById('paraPanel').classList.add('show');
}
function hidePanel(){ document.getElementById('paraPanel').classList.remove('show'); }
document.addEventListener('click', ev => {
  const c = ev.target.closest('.para-chip'); if (c) showPanel(c.dataset.para); });

// ---- table view ----
const l1ByTag = Object.fromEntries(D.l1.map(r=>[r.tag,r]));
const rows = D.l2.map(r => ({...r, l0: (l1ByTag[r.parent]||{}).l0 || ''}));
function renderTable(q) {
  q = (q||'').toLowerCase();
  const match = r => !q || [r.tag,r.parent,r.l0,r.paras,r.descr,r.note].join(' ').toLowerCase().includes(q);
  document.getElementById('viewTable').innerHTML = `<table><thead><tr>
    <th>L2 tag</th><th>L1</th><th>L0</th><th>§§</th><th>Description</th><th>L2 appl.</th><th>Note</th>
    </tr></thead><tbody>` + rows.filter(match).map(r=>`<tr>
    <td><code>${esc(r.tag)}</code></td><td><code>${esc(r.parent)}</code></td>
    <td>${esc(r.l0)}</td><td>${chips(r.paras)}</td><td>${esc(r.descr)}</td>
    <td>${esc(r.appl)}</td><td class="muted">${esc(r.note)}</td></tr>`).join('') + '</tbody></table>';
}

// ---- tree view ----
function renderTree(q) {
  q = (q||'').toLowerCase();
  const hit = s => !q || s.toLowerCase().includes(q);
  let html = '';
  for (const [l0, l0descr] of Object.entries(D.l0)) {
    const l1s = D.l1.filter(r => r.l0 === l0);
    if (!l1s.length && !hit(l0)) continue;
    let l1html = '';
    for (const p of l1s) {
      const kids = D.l2.filter(r => r.parent === p.tag);
      const kidHtml = kids
        .filter(r => hit([r.tag,r.paras,r.descr].join(' ')) || hit(p.tag))
        .map(r => `<div class="l2row"><code>${esc(r.tag)}</code> ${chips(r.paras)} ${esc(r.descr)}
          ${r.note?`<span class="muted">— ${esc(r.note)}</span>`:''}</div>`).join('');
      if (!kidHtml && !hit(p.tag+' '+p.descr)) continue;
      l1html += `<details open><summary><code>${esc(p.tag)}</code> ${chips(p.paras)}
        ${esc(p.descr)} <span class="muted">(${kids.length} L2)</span></summary>${kidHtml}</details>`;
    }
    if (!l1html) continue;
    html += `<details open><summary><strong>${esc(l0)}</strong>
      <span class="muted">${esc(l0descr)}</span></summary>${l1html}</details>`;
  }
  document.getElementById('viewTree').innerHTML = html || '<p class="muted">nothing matches</p>';
}

// ---- wiring ----
const $f = document.getElementById('filter');
let view = 'table';
function paint(){ view==='table' ? renderTable($f.value) : renderTree($f.value); }
$f.addEventListener('input', paint);
for (const [btn, v] of [['btnTable','table'],['btnTree','tree']])
  document.getElementById(btn).addEventListener('click', () => {
    view = v;
    document.getElementById('btnTable').classList.toggle('on', v==='table');
    document.getElementById('btnTree').classList.toggle('on', v==='tree');
    document.getElementById('viewTable').style.display = v==='table' ? '' : 'none';
    document.getElementById('viewTree').style.display = v==='tree' ? '' : 'none';
    paint();
  });
renderTable(''); renderTree('');
</script>
</body>
</html>
"""


def build(out: Path, data: dict, title: str) -> None:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(
        TEMPLATE.replace("__TITLE__", title).replace("__DATA__", payload),
        encoding="utf-8",
    )
    print(f"→ {out}  ({out.stat().st_size/1024:.0f} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-csv", type=Path, help="rozental_book master.csv (private build)")
    ap.add_argument("--private-out", type=Path, help="output path for the private build")
    args = ap.parse_args()

    data = load_schema()
    build(PUBLIC_OUT, data, f"Rozental Error Schema v{data['version']}")

    if args.book_csv and args.private_out:
        private = dict(data)
        private["book"] = load_book(args.book_csv)
        out = args.private_out.resolve()
        assert ROOT not in out.parents and out.parent != ROOT, (
            "private build must be written OUTSIDE the synterr repo"
        )
        build(out, private, f"Rozental Schema v{data['version']} — PRIVATE (с текстом книги)")
    elif args.book_csv or args.private_out:
        ap.error("--book-csv and --private-out must be given together")


if __name__ == "__main__":
    main()
