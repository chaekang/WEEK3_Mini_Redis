from __future__ import annotations

import argparse
import time
from collections.abc import Callable

from benchmark_helper import compare_cases, format_summary_table


def build_without_cache(source_latency_ms: float) -> Callable[[], str]:
    def fetch_without_cache() -> str:
        time.sleep(source_latency_ms / 1000)
        return "fresh-value"

    return fetch_without_cache


def build_with_cache(source_latency_ms: float) -> Callable[[], str]:
    cache: dict[str, str] = {}

    def fetch_with_cache() -> str:
        if "item" not in cache:
            time.sleep(source_latency_ms / 1000)
            cache["item"] = "cached-value"
        return cache["item"]

    return fetch_with_cache


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the branch-local benchmark harness with a simulated cache path."
    )
    parser.add_argument("--iterations", type=int, default=20, help="Measured runs per case.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs before measuring.")
    parser.add_argument(
        "--source-latency-ms",
        type=float,
        default=20.0,
        help="Simulated upstream latency in milliseconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comparison = compare_cases(
        build_without_cache(args.source_latency_ms),
        build_with_cache(args.source_latency_ms),
        iterations=args.iterations,
        warmup=args.warmup,
    )
    print("Simulated cache benchmark")
    print(format_summary_table(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
