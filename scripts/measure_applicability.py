#!/usr/bin/env python3
"""Thin wrapper — the implementation lives in synterr.discovery.

Equivalent CLI: uv run synterr survey -l ru -i <file> [-n N] [-o report.json]
"""

import sys

from synterr.cli import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "survey", *sys.argv[1:]]
    main()
