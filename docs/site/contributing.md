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
uv run pytest
```

Feature branches off `master`, PR back. CI must pass:

- `uv run pytest`
- `uv run ruff check src tests`
- `uv run ruff format --check src tests`
- `uv run mypy`

## Where to look

- **Architecture**: [`CLAUDE.md`](https://github.com/synterr-nlp/synterr/blob/master/CLAUDE.md)
- **Adding a handler**: see Russian guide for fully-worked examples
- **Roadmap**: [`docs/ROADMAP.md`](https://github.com/synterr-nlp/synterr/blob/master/docs/ROADMAP.md)
- **Open issues**: [GitHub Issues](https://github.com/synterr-nlp/synterr/issues)
