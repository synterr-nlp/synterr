#!/usr/bin/env python3
"""Parallel SFT data generation using multiprocessing.

Each worker gets its own stanza pipeline + error pipeline.
Embarrassingly parallel: split sentences → process independently → concat.

Usage:
    uv run python scripts/generate_parallel.py \
        --preset lorugec --depparse --seed 42 \
        -n 50000 -j 8 \
        -i lenta_50k.txt -o data/qwen_sft_50k.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path


def _worker(args: tuple) -> str:
    """Process a chunk of sentences. Returns path to temp output file."""
    chunk_id, sentences, preset, seed, depparse, output_format, tmp_dir = args

    # Each worker imports and creates its own pipeline
    from synterr.core.pipeline import ErrorPipeline, GenerationConfig

    config = GenerationConfig.from_preset(
        "ru",
        preset,
        seed=seed + chunk_id,  # Different seed per chunk for variety
        use_depparse=depparse,
        schema="rozental",
    )
    pipeline = ErrorPipeline("ru", config)

    out_path = os.path.join(tmp_dir, f"chunk_{chunk_id:04d}.jsonl")
    written = 0
    errors_count = 0

    with open(out_path, "w", encoding="utf-8") as f:
        for result in pipeline.generate_batch(sentences, batch_size=64):
            original = " ".join(result.original_tokens)
            corrupted = " ".join(result.corrupted_tokens)

            if output_format == "sft":
                record = {"src": corrupted, "tgt": original}
            elif output_format == "chat":
                record = {
                    "messages": [
                        {"role": "system", "content": "Исправь грамматические ошибки в тексте. Верни только исправленный текст."},
                        {"role": "user", "content": corrupted},
                        {"role": "assistant", "content": original},
                    ]
                }
            else:
                record = {"src": corrupted, "tgt": original}

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            errors_count += len(result.errors)

    return out_path, written, errors_count


def main():
    parser = argparse.ArgumentParser(description="Parallel SFT data generation")
    parser.add_argument("-i", "--input", required=True, help="Input sentences file")
    parser.add_argument("-o", "--output", required=True, help="Output JSONL file")
    parser.add_argument("-n", "--max-sentences", type=int, help="Max sentences")
    parser.add_argument("-j", "--workers", type=int, default=os.cpu_count(), help="Number of workers")
    parser.add_argument("--preset", default="lorugec", help="Preset name")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("--depparse", action="store_true", help="Enable dep parsing")
    parser.add_argument("--format", default="sft", choices=["sft", "chat"], help="Output format")
    args = parser.parse_args()

    # Read sentences
    sentences = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(line)
                if args.max_sentences and len(sentences) >= args.max_sentences:
                    break

    n_workers = min(args.workers, len(sentences))
    print(f"Processing {len(sentences)} sentences with {n_workers} workers...")

    # Split into chunks
    chunk_size = (len(sentences) + n_workers - 1) // n_workers
    chunks = []
    for i in range(n_workers):
        start = i * chunk_size
        end = min(start + chunk_size, len(sentences))
        if start < end:
            chunks.append(sentences[start:end])

    print(f"Split into {len(chunks)} chunks of ~{chunk_size} sentences each")

    # Prepare worker args
    tmp_dir = tempfile.mkdtemp(prefix="synterr_parallel_")
    worker_args = [
        (i, chunk, args.preset, args.seed, args.depparse, args.format, tmp_dir)
        for i, chunk in enumerate(chunks)
    ]

    t0 = time.time()

    # Run in parallel
    with Pool(n_workers) as pool:
        results = pool.map(_worker, worker_args)

    # Concatenate outputs
    total_written = 0
    total_errors = 0
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as out:
        for chunk_path, written, errors_count in results:
            total_written += written
            total_errors += errors_count
            with open(chunk_path, encoding="utf-8") as chunk_f:
                for line in chunk_f:
                    out.write(line)
            os.unlink(chunk_path)

    os.rmdir(tmp_dir)

    elapsed = time.time() - t0
    rate = total_written / elapsed if elapsed > 0 else 0
    print(f"Done: {total_written} sentences, {total_errors} errors in {elapsed:.1f}s ({rate:.0f} sent/s)")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
