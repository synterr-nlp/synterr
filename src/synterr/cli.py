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


@main.command("list-schemas")
def cmd_list_schemas() -> None:
    """List available linguistic schemas."""
    from synterr.schemas import get_default_schema, list_schemas, load_schema

    schemas = list_schemas()

    if not schemas:
        click.echo("No schemas available.")
        return

    default = get_default_schema()
    click.echo("Available linguistic schemas:")
    for name in sorted(schemas):
        try:
            schema = load_schema(name)
            marker = " (default)" if name == default else ""
            click.echo(f"  {name}{marker}: {schema.description} ({len(schema.tags)} tags)")
        except Exception:
            click.echo(f"  {name}: (error loading)")


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
    by_category: dict[str, list[tuple[str, float, bool, list[str]]]] = {}
    for h in handlers:
        cat = h.category
        weight = distribution.get(h.name, 0)
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((h.name, weight, h.changes_length, h.subtypes))

    for category in sorted(by_category.keys()):
        click.echo(f"  [{category}]")
        for name, weight, changes_len, subtypes in sorted(by_category[category]):
            marker = " (length-changing)" if changes_len else ""
            click.echo(f"    {name}: weight={weight:.3f}{marker}")
            if len(subtypes) > 1:
                for subtype in subtypes:
                    click.echo(f"      - {name}:{subtype}")
        click.echo()


@main.command("coverage")
@click.option("--lang", "-l", required=True, help="Language code (e.g., ru)")
@click.option("--schema", "-s", required=True, help="Schema name (e.g., synterr, rlc)")
def cmd_coverage(lang: str, schema: str) -> None:
    """Show schema coverage by available handlers.

    Reports which schema tags are covered by the language's error handlers.

    Examples:

      synterr coverage --lang ru --schema rlc
    """
    from synterr.schemas import load_schema

    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    try:
        sch = load_schema(schema)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Get all subtypes from handlers
    handlers = language.get_error_handlers()
    available_subtypes = set()
    for h in handlers:
        available_subtypes.update(h.subtypes)

    # Get coverage report
    report = sch.get_coverage_report(available_subtypes)

    click.echo(f"Schema: {sch.name} v{sch.version}")
    click.echo(f"Description: {sch.description}")
    click.echo()
    click.echo(
        f"Coverage: {report['covered_tags']}/{report['total_tags']} tags ({report['coverage_percent']}%)"
    )
    click.echo()

    if report["covered_tag_names"]:
        click.echo("Covered tags:")
        for tag in report["covered_tag_names"]:
            click.echo(f"  ✓ {tag}")
        click.echo()

    if report["uncovered_tag_names"]:
        click.echo("Uncovered tags (no handler mapping):")
        for tag in report["uncovered_tag_names"]:
            click.echo(f"  ✗ {tag}")
        click.echo()

    if report["unmapped_subtypes"]:
        click.echo("Handler subtypes not in schema:")
        for subtype in report["unmapped_subtypes"]:
            click.echo(f"  ? {subtype}")


@main.command("list-backends")
@click.option("--lang", "-l", default="ru", help="Language code (default: ru)")
def cmd_list_backends(lang: str) -> None:
    """List available NLP backends."""
    if lang == "ru":
        from synterr.languages.russian.backends import BACKENDS, DEFAULT_BACKEND, list_backends

        status = list_backends()
        click.echo(f"Available backends for {lang}:")
        for name in BACKENDS:
            is_default = " (default)" if name == DEFAULT_BACKEND else ""
            avail = status.get(name, "unknown")
            click.echo(f"  {name}{is_default}: {avail}")
    else:
        click.echo(f"No backend info for language '{lang}'.")


@main.command("analyze")
@click.option("--lang", "-l", required=True, help="Language code")
@click.option("--backend", "-b", help="NLP backend (stanza, natasha, spacy)")
@click.option("--depparse/--no-depparse", default=False, help="Enable dependency parsing")
@click.argument("text")
def cmd_analyze(lang: str, backend: str | None, depparse: bool, text: str) -> None:
    """Analyze a sentence (debug mode)."""
    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    analyzer = language.get_analyzer(use_depparse=depparse, backend=backend)
    tokens = analyzer.analyze(text)

    click.echo(f"Tokens ({len(tokens)}):")
    for t in tokens:
        feat_str = ", ".join(f"{k}={v}" for k, v in sorted(t.features.items()))
        dep_str = ""
        if depparse and t.dep_rel:
            dep_str = f" [{t.dep_rel}→{t.head_idx}]"
        click.echo(f"  {t.idx}: {t.text!r} ({t.pos}) lemma={t.lemma!r} {{{feat_str}}}{dep_str}")


@main.command("corrupt")
@click.option("--lang", "-l", required=True, help="Language code")
@click.option(
    "--error", "-e", required=True, help="Error specifier: handler, handler:subtype, or schema tag"
)
@click.option("--position", "-p", type=int, help="Token position (0-indexed, random if omitted)")
@click.option("--backend", "-b", help="NLP backend (stanza, natasha, spacy)")
@click.option("--schema", "-s", help="Schema for tag lookup (e.g., rlc)")
@click.option("--seed", type=int, default=42, help="Random seed")
@click.argument("text")
def cmd_corrupt(
    lang: str,
    error: str,
    position: int | None,
    backend: str | None,
    schema: str | None,
    seed: int,
    text: str,
) -> None:
    """Apply a specific error to a sentence.

    Tagged corruption: apply exactly one error of the specified type.

    Error specifier formats:

      \b
      spelling              - any spelling error (all subtypes)
      spelling:vowel_reduction - only vowel_reduction subtype
      Ortho --schema rlc    - all subtypes mapped to Ortho tag

    Examples:

      \b
      # Any spelling error
      synterr corrupt -l ru -e spelling "Молоко стоит на столе."

      \b
      # Only vowel reduction (phonetic)
      synterr corrupt -l ru -e spelling:vowel_reduction "Молоко стоит на столе."

      \b
      # Only typos (keyboard errors)
      synterr corrupt -l ru -e spelling:keyboard "Привет мир."

      \b
      # All Ortho-mapped subtypes (phonetic errors, no typos)
      synterr corrupt -l ru -e Ortho --schema rlc "Молоко стоит на столе."

      \b
      # Schema tag for case errors
      synterr corrupt -l ru -e Gov --schema rlc "Мама мыла раму."
    """
    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    try:
        language = get_language(lang)
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    config = GenerationConfig(seed=seed, backend=backend, schema=schema)
    pipeline = ErrorPipeline(language, config)

    result = pipeline.apply_error(text, error, position)

    if result is None:
        click.echo(f"Cannot apply error '{error}' to this sentence.", err=True)
        # Show available handlers and applicable positions
        click.echo("\nAvailable error types:", err=True)
        for h in pipeline.handlers:
            click.echo(f"  {h.name}: {h.subtypes}", err=True)
        sys.exit(1)

    click.echo(f"Original:  {' '.join(result.original_tokens)}")
    click.echo(f"Corrupted: {' '.join(result.corrupted_tokens)}")
    if result.errors:
        err = result.errors[0]
        click.echo(f"Error:     {err.error_type} @ position {err.start_idx}")
        click.echo(f"Fix tag:   {err.fix_tag}")


@main.command("generate")
@click.option("--lang", "-l", required=True, help="Language code")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True), required=True)
@click.option("--output", "-o", "output_path", type=click.Path(), required=True)
@click.option("--backend", "-b", help="NLP backend (stanza, natasha, spacy)")
@click.option("--preset", "-p", help="Use preset config (e.g., rulec, gera, balanced)")
@click.option(
    "--config", "-c", "config_path", type=click.Path(exists=True), help="Custom YAML config"
)
@click.option("--schema", help="Linguistic schema (synterr, rlc, or path to YAML)")
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
@click.option(
    "--output-format", "-f",
    type=click.Choice(["gector", "tsv", "jsonl", "chat", "sft"]),
    default="gector",
    help="Output format: gector (token tags), tsv (src\\ttgt), jsonl (rich JSON), chat (instruction-tuning), sft ({src,tgt} JSONL)",
)
@click.option("--system-prompt", default=None, help="System prompt for chat format (default: built-in GEC prompt)")
def cmd_generate(
    lang: str,
    input_path: str,
    output_path: str,
    backend: str | None,
    preset: str | None,
    config_path: str | None,
    schema: str | None,
    errors: str | None,
    weights: str | None,
    seed: int,
    max_sentences: int | None,
    label_format: str,
    error_prob: float | None,
    depparse: bool,
    batch_size: int,
    output_format: str,
    system_prompt: str | None,
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
            backend=backend,
            schema=schema,
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
            backend=backend,
            schema=schema,
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
            backend=backend,
            schema=schema,
        )

    if schema:
        click.echo(f"Using schema: {schema}")

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

    # Default system prompt for chat format
    if output_format == "chat" and system_prompt is None:
        system_prompt = "Исправь грамматические ошибки в тексте. Верни только исправленный текст."

    with (
        output_file.open("w", encoding="utf-8") as out,
        click.progressbar(
            pipeline.generate_batch(sentences, batch_size=batch_size),
            length=len(sentences),
            label="Generating",
        ) as results,
    ):
        for result in results:
            if not result.errors and output_format != "tsv":
                # Skip unchanged sentences for non-tsv formats
                continue

            if output_format == "gector":
                if result.formatted:
                    out.write(result.formatted + "\n")
            elif output_format == "tsv":
                out.write(result.to_tsv() + "\n")
            elif output_format == "jsonl":
                out.write(result.to_jsonl(seed=seed, backend=backend, schema=schema) + "\n")
            elif output_format == "chat":
                import json
                original = " ".join(result.original_tokens)
                corrupted = " ".join(result.corrupted_tokens)
                record = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": corrupted},
                        {"role": "assistant", "content": original},
                    ]
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            elif output_format == "sft":
                import json
                original = " ".join(result.original_tokens)
                corrupted = " ".join(result.corrupted_tokens)
                record = {"src": corrupted, "tgt": original}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")

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


@main.command("generate-sft")
@click.option("-l", "--lang", default="ru", help="Language code")
@click.option("-i", "--input", "input_file", required=True, type=click.Path(exists=True), help="Input sentences")
@click.option("-o", "--output", "output_file", required=True, type=click.Path(), help="Output JSONL")
@click.option("-n", "--total", type=int, default=50000, help="Target total examples")
@click.option("--seed", type=int, default=42, help="Random seed")
@click.option("--depparse/--no-depparse", default=True, help="Enable dep parsing")
@click.option("--max-input", type=int, default=60000, help="Max input sentences to read")
@click.option("--batch-size", type=int, default=128, help="Stanza analysis batch size")
def cmd_generate_sft(
    lang: str,
    input_file: str,
    output_file: str,
    total: int,
    seed: int,
    depparse: bool,
    max_input: int,
    batch_size: int,
) -> None:
    """Generate SFT training data — force-apply per LoRuGEC rule.

    Each example gets {"src": corrupted, "tgt": clean, "rule": rule_name}.
    Distribution follows the LoRuGEC benchmark (48 rules).
    Saves a .dist.json sidecar with per-rule counts.
    """
    import json
    import random
    import time

    from sacremoses import MosesDetokenizer

    from synterr.lorugec import LORUGEC_RULES, extract_subtype, get_lorugec_distribution

    moses = MosesDetokenizer(lang="ru")

    def detokenize(tokens: list[str]) -> str:
        return moses.detokenize(tokens)

    # Read LoRuGEC distribution
    rule_counts = get_lorugec_distribution()
    total_lorugec = sum(rule_counts.values())

    targets: dict[str, int] = {}
    for rule, count in rule_counts.items():
        targets[rule] = max(1, round(count / total_lorugec * total))

    from collections import defaultdict
    subtype_groups: dict[tuple, list[str]] = defaultdict(list)
    for rule, mapping in LORUGEC_RULES.items():
        handler_name, subtype = mapping[0], mapping[1]
        word_filter = mapping[2] if len(mapping) > 2 else None
        if rule in targets:
            subtype_groups[(handler_name, subtype, word_filter)].append(rule)

    subtype_targets: dict[tuple, int] = {}
    for key, rules in subtype_groups.items():
        subtype_targets[key] = sum(targets[r] for r in rules)

    click.echo(f"LoRuGEC rules: {len(LORUGEC_RULES)}, groups: {len(subtype_targets)}, target: {sum(subtype_targets.values())}")

    # Read input
    sentences = []
    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(line)
                if len(sentences) >= max_input:
                    break
    click.echo(f"Input: {len(sentences)} sentences")

    # Pipeline
    config = GenerationConfig(seed=seed, schema="rozental", use_depparse=depparse)
    pipeline = ErrorPipeline(lang, config)

    # Analyze
    click.echo(f"Analyzing (batch_size={batch_size})...")
    t0 = time.time()
    all_tokens = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i : i + batch_size]
        all_tokens.extend(pipeline.analyzer.analyze_batch(batch))
        done = min(i + batch_size, len(sentences))
        if done % 8000 == 0 or done == len(sentences):
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            click.echo(f"  {done}/{len(sentences)} ({rate:.0f} sent/s)")
    click.echo(f"Analysis: {time.time() - t0:.1f}s")

    # Generate
    rng = random.Random(seed)
    all_examples: list[dict] = []
    results_per_rule: dict[str, int] = {r: 0 for r in LORUGEC_RULES}

    for (handler_name, subtype, word_filter), target in subtype_targets.items():
        handler = pipeline._get_handler_by_name(handler_name)
        if handler is None:
            continue

        indices = list(range(len(sentences)))
        rng.shuffle(indices)

        count = 0
        for idx in indices:
            if count >= target:
                break
            tokens = all_tokens[idx]
            if not tokens:
                continue

            original = [t.text for t in tokens]
            applicable = [i for i in range(len(tokens)) if handler.can_apply(tokens, i)]
            if not applicable:
                continue

            positions = applicable.copy()
            rng.shuffle(positions)

            for pos in positions:
                sentence = original.copy()
                modified: set[int] = set()
                result = handler.apply(tokens, sentence, pos, modified, rng=rng)
                if result is None:
                    continue
                result_subtype = extract_subtype(result.error_type, handler_name)
                if isinstance(subtype, tuple):
                    if result_subtype not in subtype:
                        continue
                elif result_subtype != subtype:
                    continue
                if word_filter is not None:
                    orig_lower = result.original.lower() if result.original else ""
                    corr_lower = result.corrupted.lower() if result.corrupted else ""
                    if word_filter not in orig_lower and word_filter not in corr_lower:
                        continue

                src = detokenize(sentence)
                tgt = detokenize(original)
                if src == tgt:
                    continue

                group_rules = subtype_groups[(handler_name, subtype, word_filter)]
                assigned_rule = group_rules[count % len(group_rules)]
                all_examples.append({"src": src, "tgt": tgt, "rule": assigned_rule})
                results_per_rule[assigned_rule] += 1
                count += 1
                break

        label = f"{handler_name}/{subtype}"
        if word_filter:
            label += f"[{word_filter}]"
        click.echo(f"  {label}: {count}/{target}")

    # Write
    rng.shuffle(all_examples)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # Save distribution sidecar
    dist_path = output_path.with_suffix(".dist.json")
    dist = {
        "total": len(all_examples),
        "target": total,
        "seed": seed,
        "source": Path(input_file).name,
        "rules": {r: {"got": results_per_rule.get(r, 0), "want": targets.get(r, 0)}
                  for r in sorted(LORUGEC_RULES.keys())},
    }
    with dist_path.open("w", encoding="utf-8") as f:
        json.dump(dist, f, ensure_ascii=False, indent=2)

    click.echo(f"\nDone: {len(all_examples)} examples → {output_path}")
    click.echo(f"Distribution: {dist_path}")

    # Summary
    full = sum(1 for r in LORUGEC_RULES if results_per_rule.get(r, 0) >= targets.get(r, 0))
    click.echo(f"Rules at target: {full}/{len(LORUGEC_RULES)}")


if __name__ == "__main__":
    main()
