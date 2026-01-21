"""Command-line interface for synterr."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from synterr.core.pipeline import ErrorPipeline, GenerationConfig
from synterr.core.registry import get_language, list_languages


@click.group()
@click.version_option()
def main() -> None:
    """Synterr - Reproducible error generation for GEC."""
    pass


@main.command("list-languages")
def cmd_list_languages() -> None:
    """List available languages."""
    languages = list_languages()

    if not languages:
        click.echo("No languages available.")
        click.echo("Install language support, e.g.: pip install synterr[russian]")
        return

    click.echo("Available languages:")
    for code, name in languages.items():
        click.echo(f"  {code}: {name}")


@main.command("list-errors")
@click.option("--lang", "-l", required=True, help="Language code (e.g., ru)")
def cmd_list_errors(lang: str) -> None:
    """List error types for a language."""
    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    handlers = language.get_error_handlers()
    distribution = language.get_error_distribution()

    click.echo(f"Error types for {language.name} ({lang}):")
    click.echo()

    # Group by category
    by_category: dict[str, list[tuple[str, float, bool]]] = {}
    for h in handlers:
        cat = h.category
        weight = distribution.get(h.name, 0)
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((h.name, weight, h.changes_length))

    for category in sorted(by_category.keys()):
        click.echo(f"  [{category}]")
        for name, weight, changes_len in sorted(by_category[category]):
            marker = " (length-changing)" if changes_len else ""
            click.echo(f"    {name}: weight={weight:.2f}{marker}")
        click.echo()


@main.command("analyze")
@click.option("--lang", "-l", required=True, help="Language code")
@click.option("--depparse/--no-depparse", default=False, help="Enable dependency parsing")
@click.argument("text")
def cmd_analyze(lang: str, depparse: bool, text: str) -> None:
    """Analyze a sentence (debug mode)."""
    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    analyzer = language.get_analyzer(use_depparse=depparse)
    tokens = analyzer.analyze(text)

    click.echo(f"Tokens ({len(tokens)}):")
    for t in tokens:
        feat_str = ", ".join(f"{k}={v}" for k, v in sorted(t.features.items()))
        dep_str = ""
        if depparse and t.dep_rel:
            dep_str = f" [{t.dep_rel}→{t.head_idx}]"
        click.echo(f"  {t.idx}: {t.text!r} ({t.pos}) lemma={t.lemma!r} {{{feat_str}}}{dep_str}")


@main.command("generate")
@click.option("--lang", "-l", required=True, help="Language code")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--errors", "-e", help="Comma-separated error types (default: all)")
@click.option("--seed", "-s", type=int, default=42, help="Random seed")
@click.option("--max-sentences", "-n", type=int, help="Maximum sentences to process")
@click.option(
    "--label-format",
    type=click.Choice(["original", "binary", "multiclass"]),
    default="multiclass",
    help="Output label format",
)
@click.option("--depparse/--no-depparse", default=False, help="Enable dependency parsing")
@click.option("--batch-size", type=int, default=100, help="Batch size for processing")
def cmd_generate(
    lang: str,
    input_path: str,
    output_path: str,
    errors: str | None,
    seed: int,
    max_sentences: int | None,
    label_format: str,
    depparse: bool,
    batch_size: int,
) -> None:
    """Generate synthetic errors from corpus."""
    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Parse enabled errors
    enabled_errors = None
    if errors:
        enabled_errors = set(e.strip() for e in errors.split(","))

    # Create config
    config = GenerationConfig(
        seed=seed,
        use_depparse=depparse,
        label_format=label_format,
        enabled_errors=enabled_errors,
    )

    # Create pipeline
    pipeline = ErrorPipeline(language, config)

    # Read input
    input_file = Path(input_path)
    sentences: list[str] = []

    click.echo(f"Reading from {input_file}...")
    with input_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(line)
                if max_sentences and len(sentences) >= max_sentences:
                    break

    click.echo(f"Processing {len(sentences)} sentences...")

    # Generate errors
    output_file = Path(output_path)
    written = 0
    errors_count = 0

    with (
        output_file.open("w", encoding="utf-8") as out,
        click.progressbar(
            pipeline.generate_batch(sentences, batch_size=batch_size),
            length=len(sentences),
            label="Generating",
        ) as results,
    ):
        for result in results:
            if result.formatted:
                out.write(result.formatted + "\n")
                written += 1
                errors_count += len(result.errors)

    click.echo(f"Wrote {written} sentences with {errors_count} total errors to {output_file}")


if __name__ == "__main__":
    main()
