from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_benchmark_helper() -> ModuleType:
    helper_path = Path(__file__).with_name("benchmark_helper.py")
    spec = importlib.util.spec_from_file_location(
        "benchmark_helper_for_tests", helper_path
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def benchmark_helper() -> ModuleType:
    return load_benchmark_helper()


@pytest.mark.anyio
async def test_measure_case_tracks_timing_call_counts_and_measured_totals(
    benchmark_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_values = iter([10.0, 13.0])
    monkeypatch.setattr(benchmark_helper, "perf_counter", lambda: next(counter_values))

    calls: list[str] = []

    async def action() -> object:
        calls.append("run")
        return benchmark_helper.CaseObservation(
            value="origin-value:alpha",
            origin_fetches=1,
            cache_hits=2,
            cache_misses=3,
        )

    result = await benchmark_helper.measure_case(
        "demo_case",
        action,
        iterations=3,
        warmup=2,
    )

    assert calls == ["run"] * 5
    assert result.iterations == 3
    assert result.warmup == 2
    assert result.total_seconds == pytest.approx(3.0)
    assert result.average_seconds == pytest.approx(1.0)
    assert result.origin_fetches == 3
    assert result.cache_hits == 6
    assert result.cache_misses == 9
    assert result.sample_value == "origin-value:alpha"


@pytest.mark.anyio
async def test_without_cache_calls_origin_for_each_measured_iteration(
    benchmark_helper: ModuleType,
) -> None:
    result = await benchmark_helper.run_without_cache_case(
        key="alpha",
        iterations=4,
        warmup=0,
        origin_latency_ms=0.0,
    )

    assert result.name == "without_cache"
    assert result.origin_fetches == 4
    assert result.cache_hits == 0
    assert result.cache_misses == 0
    assert result.sample_value == "origin-value:alpha"


@pytest.mark.anyio
async def test_with_redis_cache_misses_once_then_hits_for_same_hot_key(
    benchmark_helper: ModuleType,
) -> None:
    result = await benchmark_helper.run_with_redis_cache_case(
        key="alpha",
        iterations=4,
        warmup=0,
        origin_latency_ms=0.0,
    )

    assert result.name == "with_redis_cache"
    assert result.origin_fetches == 1
    assert result.cache_hits == 3
    assert result.cache_misses == 1
    assert result.sample_value == "origin-value:alpha"


@pytest.mark.anyio
async def test_with_redis_cache_warmup_primes_cache_before_measured_runs(
    benchmark_helper: ModuleType,
) -> None:
    result = await benchmark_helper.run_with_redis_cache_case(
        key="alpha",
        iterations=3,
        warmup=1,
        origin_latency_ms=0.0,
    )

    assert result.origin_fetches == 0
    assert result.cache_hits == 3
    assert result.cache_misses == 0
    assert result.sample_value == "origin-value:alpha"


@pytest.mark.anyio
async def test_cache_vs_origin_benchmark_reports_speedup_and_matching_payload(
    benchmark_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_values = iter([0.0, 10.0, 20.0, 25.0])
    monkeypatch.setattr(benchmark_helper, "perf_counter", lambda: next(counter_values))

    comparison = await benchmark_helper.run_cache_vs_origin_benchmark(
        key="alpha",
        iterations=1,
        warmup=0,
        origin_latency_ms=0.0,
    )
    summary = benchmark_helper.format_summary_table(comparison)

    assert comparison.without_cache.sample_value == "origin-value:alpha"
    assert comparison.with_redis_cache.sample_value == "origin-value:alpha"
    assert comparison.cache_is_faster is True
    assert comparison.speedup == pytest.approx(2.0)
    assert comparison.improvement_percent == pytest.approx(50.0)
    assert "without_cache" in summary
    assert "with_redis_cache" in summary
    assert "cache faster: yes" in summary
    assert "speedup: 2.00x" in summary
    assert "sample value: origin-value:alpha" in summary


@pytest.mark.anyio
async def test_redis_cache_case_uses_fresh_state_for_each_run(
    benchmark_helper: ModuleType,
) -> None:
    first = await benchmark_helper.run_with_redis_cache_case(
        key="fresh-state",
        iterations=1,
        warmup=0,
        origin_latency_ms=0.0,
    )
    second = await benchmark_helper.run_with_redis_cache_case(
        key="fresh-state",
        iterations=1,
        warmup=0,
        origin_latency_ms=0.0,
    )

    assert first.origin_fetches == 1
    assert first.cache_misses == 1
    assert first.cache_hits == 0
    assert second.origin_fetches == 1
    assert second.cache_misses == 1
    assert second.cache_hits == 0
