# Contributing

The full contributor guide lives at
[`CONTRIBUTING.md`](https://github.com/synterr-nlp/synterr/blob/master/CONTRIBUTING.md)
in the repo. The Russian-language version with worked examples
of adding a handler is at
[`docs/CONTRIBUTING.ru.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/CONTRIBUTING.ru.md).

## At a glance

```bash
git clone https://github.com/synterr-nlp/synterr
cd synterr
uv sync --all-extras
make check
```

Feature branches off `master`, PR back. The gate is one call:
`make check` runs ruff check, ruff format `--check`, mypy, and the fast
(non-`slow`) tests. CI runs the same Makefile targets plus
`make test-slow` (real-stanza tests); `make check-full` adds those and
the strict docs build locally.

## Where to look

- **Architecture**: [Architecture](architecture.md)
- **Adding a handler**: see Russian guide for fully-worked examples
- **Open issues**: [GitHub Issues](https://github.com/synterr-nlp/synterr/issues)
