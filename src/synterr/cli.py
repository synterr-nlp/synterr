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


@main.command("list-presets")
@click.option("--lang", "-l", required=True, help="Language code (e.g., ru)")
def cmd_list_presets(lang: str) -> None:
    """List available presets for a language."""
    from synterr.configs import get_default_preset, list_presets, load_preset

    presets = list_presets(lang)
    default = get_default_preset(lang)

    if not presets:
        click.echo(f"No presets available for language '{lang}'.")
        return

    click.echo(f"Available presets for {lang}:")
    for name in sorted(presets):
        try:
            data = load_preset(lang, name)
            desc = data.get("description", "")
            marker = " (default)" if name == default else ""
            click.echo(f"  {name}{marker}: {desc}")
        except Exception:
            click.echo(f"  {name}: (error loading)")


@main.command("list-errors")
@click.option("--lang", "-l", required=True, help="Language code (e.g., ru)")
@click.option("--preset", "-p", help="Show weights from preset (default: language default)")
def cmd_list_errors(lang: str, preset: str | None) -> None:
    """List error types for a language."""
    from synterr.configs import load_preset

    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    handlers = language.get_error_handlers()

    # Get distribution from preset or language default
    if preset:
        try:
            data = load_preset(lang, preset)
            distribution = data.get("weights", {})
            source = f"preset '{preset}'"
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:
        distribution = language.get_error_distribution()
        source = "language default (use --preset to see others)"

    click.echo(f"Error types for {language.name} ({lang}):")
    click.echo(f"Weights from: {source}")
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
            click.echo(f"    {name}: weight={weight:.3f}{marker}")
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
@click.option("--preset", "-p", help="Use preset config (e.g., rulec, gera, balanced)")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="Custom YAML config")
@click.option("--errors", "-e", help="Comma-separated error types (default: all)")
@click.option("--weights", "-w", help="JSON weights dict, e.g., '{\"spelling\": 0.5}'")
@click.option("--seed", "-s", type=int, default=42, help="Random seed")
@click.option("--max-sentences", "-n", type=int, help="Maximum sentences to process")
@click.option(
    "--label-format",
    type=click.Choice(["original", "binary", "multiclass"]),
    default="multiclass",
    help="Output label format",
)
@click.option("--error-prob", type=float, help="Probability of introducing errors (0-1)")
@click.option("--depparse/--no-depparse", default=False, help="Enable dependency parsing")
@click.option("--batch-size", type=int, default=100, help="Batch size for processing")
def cmd_generate(
    lang: str,
    input_path: str,
    output_path: str,
    preset: str | None,
    config_path: str | None,
    errors: str | None,
    weights: str | None,
    seed: int,
    max_sentences: int | None,
    label_format: str,
    error_prob: float | None,
    depparse: bool,
    batch_size: int,
) -> None:
    """Generate synthetic errors from corpus.

    Configuration priority: --config > --preset > --weights > language default

    Examples:

      # Use RULEC-GEC distribution preset
      synterr generate --lang ru --preset rulec -i corpus.txt -o out.edits

      # Use custom config file
      synterr generate --lang ru --config my_weights.yaml -i corpus.txt -o out.edits

      # Fine-grained: specific errors with custom weights
      synterr generate --lang ru -e spelling,noun_case -w '{"spelling": 0.7}' -i in.txt -o out.edits
    """
    import json

    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Parse enabled errors
    enabled_errors = None
    if errors:
        enabled_errors = set(e.strip() for e in errors.split(","))

    # Parse custom weights
    error_weights = None
    if weights:
        try:
            error_weights = json.loads(weights)
        except json.JSONDecodeError as e:
            click.echo(f"Error parsing --weights JSON: {e}", err=True)
            sys.exit(1)

    # Build config from various sources
    if config_path:
        # Load from custom config file
        config = GenerationConfig.from_file(
            config_path,
            seed=seed,
            use_depparse=depparse,
            label_format=label_format,
            enabled_errors=enabled_errors,
        )
        click.echo(f"Using config: {config_path}")
    elif preset:
        # Load from preset
        config = GenerationConfig.from_preset(
            lang,
            preset,
            seed=seed,
            use_depparse=depparse,
            label_format=label_format,
            enabled_errors=enabled_errors,
        )
        click.echo(f"Using preset: {preset}")
    else:
        # Default config
        config = GenerationConfig(
            seed=seed,
            use_depparse=depparse,
            label_format=label_format,
            enabled_errors=enabled_errors,
            error_weights=error_weights,
        )

    # Override error_weights if provided via --weights (takes precedence)
    if error_weights and config.error_weights != error_weights:
        config.error_weights = error_weights

    # Override error_probability if provided
    if error_prob is not None:
        config.error_probability = error_prob

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


@main.command("analyze-distribution")
@click.argument("m2_files", nargs=-1, type=click.Path(exists=True), required=True)
@click.option("--output", "-o", type=click.Path(), help="Output JSON file for weights")
def cmd_analyze_distribution(m2_files: tuple[str, ...], output: str | None) -> None:
    """Analyze M2 files to extract error distribution.

    Accepts one or more M2 format files (e.g., RULEC-GEC.dev.m2, GERA.train.m2).
    Outputs error type frequencies and suggested synterr weights.
    """
    from synterr.analysis.distribution import (
        aggregate_distributions,
        analyze_m2_file,
        print_distribution_report,
    )

    stats_list = []
    for path in m2_files:
        click.echo(f"Analyzing {path}...")
        stats = analyze_m2_file(path)
        stats_list.append(stats)
        click.echo(f"  {stats.total_sentences:,} sentences, {stats.total_errors:,} errors")

    # Aggregate if multiple files
    if len(stats_list) > 1:
        combined = aggregate_distributions(stats_list)
        combined.source = f"combined ({len(stats_list)} files)"
    else:
        combined = stats_list[0]

    # Print report
    print_distribution_report(combined)

    # Output JSON if requested
    if output:
        import json

        weights = combined.get_synterr_weights()
        output_path = Path(output)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "source": combined.source,
                    "total_sentences": combined.total_sentences,
                    "total_errors": combined.total_errors,
                    "synterr_weights": weights,
                    "full_distribution": combined.get_distribution(normalize=True),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        click.echo(f"\nWeights saved to {output_path}")


if __name__ == "__main__":
    main()
