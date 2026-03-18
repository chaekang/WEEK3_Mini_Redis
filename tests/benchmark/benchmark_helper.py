from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    iterations: int
    warmup: int
    total_seconds: float
    average_seconds: float


@dataclass(frozen=True)
class BenchmarkComparison:
    without_cache: BenchmarkResult
    with_cache: BenchmarkResult
    cache_is_faster: bool
    speedup: float
    improvement_percent: float


def measure_case(
    name: str,
    action: Callable[[], T],
    *,
    iterations: int = 20,
    warmup: int = 1,
) -> BenchmarkResult:
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero")
    if warmup < 0:
        raise ValueError("warmup must be zero or greater")

    for _ in range(warmup):
        action()

    started_at = perf_counter()
    for _ in range(iterations):
        action()
    finished_at = perf_counter()

    total_seconds = finished_at - started_at
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        warmup=warmup,
        total_seconds=total_seconds,
        average_seconds=total_seconds / iterations,
    )


def compare_cases(
    without_cache: Callable[[], T],
    with_cache: Callable[[], T],
    *,
    iterations: int = 20,
    warmup: int = 1,
) -> BenchmarkComparison:
    without_cache_result = measure_case(
        "without_cache",
        without_cache,
        iterations=iterations,
        warmup=warmup,
    )
    with_cache_result = measure_case(
        "with_cache",
        with_cache,
        iterations=iterations,
        warmup=warmup,
    )

    cache_is_faster = (
        with_cache_result.total_seconds < without_cache_result.total_seconds
    )

    if with_cache_result.total_seconds == 0:
        speedup = float("inf")
    else:
        speedup = without_cache_result.total_seconds / with_cache_result.total_seconds

    if without_cache_result.total_seconds == 0:
        improvement_percent = 0.0
    else:
        improvement_percent = (
            (without_cache_result.total_seconds - with_cache_result.total_seconds)
            / without_cache_result.total_seconds
        ) * 100

    return BenchmarkComparison(
        without_cache=without_cache_result,
        with_cache=with_cache_result,
        cache_is_faster=cache_is_faster,
        speedup=speedup,
        improvement_percent=improvement_percent,
    )


def format_summary_table(comparison: BenchmarkComparison) -> str:
    without_cache = comparison.without_cache
    with_cache = comparison.with_cache

    lines = [
        "case            total (s)   avg (ms)",
        "------------------------------------",
        (
            f"{without_cache.name:<15}"
            f"{without_cache.total_seconds:>10.6f}"
            f"{without_cache.average_seconds * 1000:>11.3f}"
        ),
        (
            f"{with_cache.name:<15}"
            f"{with_cache.total_seconds:>10.6f}"
            f"{with_cache.average_seconds * 1000:>11.3f}"
        ),
        "",
        f"cache faster: {'yes' if comparison.cache_is_faster else 'no'}",
        f"speedup: {comparison.speedup:.2f}x",
        f"improvement: {comparison.improvement_percent:.2f}%",
    ]
    return "\n".join(lines)
