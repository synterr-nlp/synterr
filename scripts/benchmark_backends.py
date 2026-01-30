#!/usr/bin/env python3
"""Benchmark synterr backends on morphological analysis."""

import time
from statistics import mean, stdev

# Sample sentences (mix of lengths)
SENTENCES = [
    "Мама мыла раму.",
    "Президент выступил с обращением к народу.",
    "В этом году лето было очень жарким и сухим.",
    "Студенты сдали экзамены и уехали на каникулы домой.",
    "Она купила новую книгу в магазине на углу.",
    "Дети играли во дворе до позднего вечера.",
    "Мы решили поехать на море в следующем месяце.",
    "Профессор объяснил студентам сложную тему.",
    "Кошка спала на диване весь день.",
    "Он написал письмо и отправил его по почте.",
]


def benchmark_backend(backend_name: str, n_iterations: int = 3, n_sentences: int = 100):
    """Benchmark a single backend."""
    from synterr.languages.russian.backends import get_backend

    print(f"\n{'=' * 50}")
    print(f"Backend: {backend_name}")
    print(f"{'=' * 50}")

    # Initialize
    print("Initializing...", end=" ", flush=True)
    start = time.perf_counter()
    if backend_name == "spacy":
        # Use small model for benchmark
        from synterr.languages.russian.backends.spacy_backend import SpacyBackend

        analyzer = SpacyBackend(model="ru_core_news_sm")
    else:
        analyzer = get_backend(backend_name)
    init_time = time.perf_counter() - start
    print(f"{init_time:.2f}s")

    # Warm up
    print("Warming up...", end=" ", flush=True)
    for s in SENTENCES[:3]:
        analyzer.analyze(s)
    print("done")

    # Benchmark single analysis
    print(f"\nSingle sentence analysis ({n_iterations} iterations):")
    times = []
    for i in range(n_iterations):
        start = time.perf_counter()
        for _ in range(n_sentences):
            for s in SENTENCES:
                analyzer.analyze(s)
        elapsed = time.perf_counter() - start
        total = n_sentences * len(SENTENCES)
        rate = total / elapsed
        times.append(rate)
        print(f"  Run {i + 1}: {rate:.1f} sent/s ({total} sentences in {elapsed:.2f}s)")

    avg = mean(times)
    std = stdev(times) if len(times) > 1 else 0
    print(f"  Average: {avg:.1f} ± {std:.1f} sent/s")

    # Benchmark batch analysis (if available)
    if hasattr(analyzer, "analyze_batch"):
        print(f"\nBatch analysis ({n_iterations} iterations):")
        all_sentences = SENTENCES * n_sentences
        times = []
        for i in range(n_iterations):
            start = time.perf_counter()
            analyzer.analyze_batch(all_sentences)
            elapsed = time.perf_counter() - start
            rate = len(all_sentences) / elapsed
            times.append(rate)
            print(
                f"  Run {i + 1}: {rate:.1f} sent/s ({len(all_sentences)} sentences in {elapsed:.2f}s)"
            )

        avg = mean(times)
        std = stdev(times) if len(times) > 1 else 0
        print(f"  Average: {avg:.1f} ± {std:.1f} sent/s")

    return avg


def main():
    print("synterr Backend Benchmark")
    print("=" * 50)
    print(f"Test corpus: {len(SENTENCES)} unique sentences")
    print("Hardware: M4 Pro")

    results = {}

    # Test each backend
    for backend in ["stanza", "natasha", "spacy"]:
        try:
            results[backend] = benchmark_backend(backend)
        except Exception as e:
            print(f"\n{backend}: FAILED - {e}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for backend, rate in results.items():
        print(f"  {backend}: ~{int(rate)} sent/s")


if __name__ == "__main__":
    main()
