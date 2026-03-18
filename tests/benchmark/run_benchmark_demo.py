from __future__ import annotations

import argparse
import asyncio
import sys

from benchmark_helper import format_summary_table, run_cache_vs_origin_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a slow dummy origin endpoint against the same request path "
            "with Mini Redis used as an HTTP cache."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Measured requests per case.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup requests per case before timing starts.",
    )
    parser.add_argument(
        "--origin-latency-ms",
        type=float,
        default=20.0,
        help="Artificial latency added by the dummy origin endpoint.",
    )
    parser.add_argument(
        "--key",
        default="benchmark:hot-key",
        help="Hot key used for both the origin and Mini Redis cache path.",
    )
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    comparison = await run_cache_vs_origin_benchmark(
        key=args.key,
        iterations=args.iterations,
        warmup=args.warmup,
        origin_latency_ms=args.origin_latency_ms,
    )

    print("Mini Redis cache-vs-origin benchmark")
    print(f"key: {args.key}")
    print(f"iterations: {args.iterations}")
    print(f"warmup: {args.warmup}")
    print(f"origin latency: {args.origin_latency_ms:.1f} ms")
    print()
    print(format_summary_table(comparison))
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(main_async(args))
    except ValueError as exc:
        print(f"Benchmark configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
