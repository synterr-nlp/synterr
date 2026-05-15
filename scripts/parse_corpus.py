#!/usr/bin/env python3
"""Parse a sentence-per-line corpus to a CoNLL-U cache with stanza."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import stanza
from stanza.utils.conll import CoNLL


def iter_sentences(path: Path, max_sentences: int | None):
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield line
            n += 1
            if max_sentences and n >= max_sentences:
                return


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--max-sentences", type=int, default=None)
    ap.add_argument("--no-gpu", action="store_true")
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    nlp = stanza.Pipeline(
        args.lang,
        processors="tokenize,pos,lemma,depparse",
        tokenize_no_ssplit=True,
        use_gpu=not args.no_gpu,
    )

    n = 0
    start = time.time()
    batch: list[str] = []

    with args.output.open("w", encoding="utf-8") as out:
        def flush(batch: list[str]) -> None:
            nonlocal n
            if not batch:
                return
            docs = [nlp(s) for s in batch]
            for doc in docs:
                out.write("{:C}\n\n".format(doc))
            n += len(batch)
            elapsed = time.time() - start
            rate = n / max(elapsed, 1e-6)
            print(
                f"  parsed {n:>7d} sents  |  {rate:5.1f} sent/s  |  "
                f"{elapsed/60:.1f} min elapsed",
                file=sys.stderr,
                flush=True,
            )

        for sent in iter_sentences(args.input, args.max_sentences):
            batch.append(sent)
            if len(batch) >= args.batch_size:
                flush(batch)
                batch = []
        flush(batch)

    print(f"done: {n} sentences → {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
