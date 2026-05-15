#!/usr/bin/env python3
"""Query a CoNLL-U cache with semgrex patterns; emit matches as JSONL.

Pipeline:
  parse_corpus.py  →  cache.conllu  →  mine_semgrex.py  →  matches.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml
from stanza.server.semgrex import Semgrex
from stanza.utils.conll import CoNLL


def load_patterns(path: Path, names: list[str] | None) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        all_patterns = yaml.safe_load(f)
    if not isinstance(all_patterns, dict):
        raise SystemExit(f"{path} must be a mapping of name → pattern")
    if names:
        missing = [n for n in names if n not in all_patterns]
        if missing:
            raise SystemExit(f"unknown patterns: {missing}")
        all_patterns = {n: all_patterns[n] for n in names}
    return {k: v.strip() for k, v in all_patterns.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--cache", type=Path, required=True,
                    help="CoNLL-U file from parse_corpus.py")
    ap.add_argument("-p", "--patterns", type=Path,
                    default=Path(__file__).with_name("semgrex_patterns.yaml"))
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--only", nargs="+", default=None,
                    help="restrict to a subset of pattern names")
    ap.add_argument("--limit-per-pattern", type=int, default=None,
                    help="stop a pattern once it has this many matches")
    args = ap.parse_args()

    patterns = load_patterns(args.patterns, args.only)
    pat_names = list(patterns.keys())
    pat_exprs = [patterns[n] for n in pat_names]

    print(f"loading cache: {args.cache}", file=sys.stderr)
    doc = CoNLL.conll2doc(str(args.cache))
    n_sents = len(doc.sentences)
    print(f"  {n_sents} sentence(s) loaded", file=sys.stderr)

    print(f"running {len(pat_names)} pattern(s) via CoreNLP/semgrex…",
          file=sys.stderr)
    with Semgrex() as sem:
        response = sem.process(doc, *pat_exprs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    limits_hit: set[str] = set()

    with args.output.open("w", encoding="utf-8") as out:
        # response.result: one entry per sentence
        #   .result: one entry per pattern (in the order we passed them)
        #     .match: list of Match objects with .node[] bindings
        for sent_idx, sent_result in enumerate(response.result):
            sentence = doc.sentences[sent_idx]
            for pat_name, graph_result in zip(pat_names, sent_result.result):
                if pat_name in limits_hit:
                    continue
                for match in graph_result.match:
                    bindings = {
                        node.name: node.matchIndex
                        for node in match.node
                    }
                    record = {
                        "text": sentence.text,
                        "pattern": pat_name,
                        "match": bindings,
                        "tokens": [w.text for w in sentence.words],
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    counts[pat_name] += 1
                    if (args.limit_per_pattern
                            and counts[pat_name] >= args.limit_per_pattern):
                        limits_hit.add(pat_name)
                        break

    print("matches per pattern:", file=sys.stderr)
    for name in pat_names:
        flag = " (capped)" if name in limits_hit else ""
        print(f"  {name:<30s} {counts[name]:>6d}{flag}", file=sys.stderr)
    print(f"→ {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
