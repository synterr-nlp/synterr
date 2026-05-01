#!/usr/bin/env python3
"""Verify v4 data files against committed SHA256 checksums.

Usage:
    uv run python scripts/verify_v4.py
    uv run python scripts/verify_v4.py --checksums data/v4_checksums.txt
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def parse_checksums(path: Path) -> list[tuple[str, Path]]:
    """Parse a sha256sum-style file. Returns list of (expected_hash, file_path)."""
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        entries.append((parts[0], Path(parts[1])))
    return entries


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description="Verify v4 data file checksums.")
    p.add_argument("--checksums", default="data/v4_checksums.txt", type=Path)
    p.add_argument("--root", default=".", type=Path,
                   help="Repository root (paths in checksum file are relative to it)")
    args = p.parse_args()

    if not args.checksums.exists():
        print(f"checksum file not found: {args.checksums}", file=sys.stderr)
        return 2

    entries = parse_checksums(args.checksums)
    if not entries:
        print(f"no entries in {args.checksums}", file=sys.stderr)
        return 2

    failures = 0
    missing = 0
    for expected, rel_path in entries:
        path = args.root / rel_path
        if not path.exists():
            print(f"MISSING  {rel_path}")
            missing += 1
            continue
        actual = sha256_file(path)
        if actual == expected:
            print(f"OK       {rel_path}")
        else:
            print(f"MISMATCH {rel_path}")
            print(f"         expected {expected}")
            print(f"         actual   {actual}")
            failures += 1

    total = len(entries)
    ok = total - failures - missing
    print(f"\n{ok}/{total} OK, {failures} mismatch, {missing} missing")
    return 0 if (failures == 0 and missing == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
