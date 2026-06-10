#!/usr/bin/env python3
"""Thin wrapper — the implementation lives in synterr.discovery.

Equivalent CLI: uv run synterr mine-pools -s <src> [-s <src> ...] -o data/pools
"""

import sys

from synterr.cli import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "mine-pools", *sys.argv[1:]]
    main()
