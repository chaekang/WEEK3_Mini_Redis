from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_benchmark_helper() -> ModuleType:
    helper_path = Path(__file__).with_name("benchmark_helper.py")
    spec = importlib.util.spec_from_file_location("benchmark_helper_for_tests", helper_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def benchmark_helper() -> ModuleType:
    return load_benchmark_helper()


def test_measure_case_tracks_timing_and_call_counts(
    benchmark_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_values = iter([10.0, 13.0])
    monkeypatch.setattr(benchmark_helper, "perf_counter", lambda: next(counter_values))

    calls: list[str] = []
    result = benchmark_helper.measure_case(
        "without_cache",
        lambda: calls.append("run"),
        iterations=3,
        warmup=2,
    )

    assert calls == ["run"] * 5
    assert result.iterations == 3
    assert result.warmup == 2
    assert result.total_seconds == pytest.approx(3.0)
    assert result.average_seconds == pytest.approx(1.0)


def test_compare_cases_reports_relative_improvement(
    benchmark_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counter_values = iter([0.0, 10.0, 20.0, 25.0])
    monkeypatch.setattr(benchmark_helper, "perf_counter", lambda: next(counter_values))

    comparison = benchmark_helper.compare_cases(
        lambda: None,
        lambda: None,
        iterations=1,
        warmup=0,
    )
    summary = benchmark_helper.format_summary_table(comparison)

    assert comparison.cache_is_faster is True
    assert comparison.speedup == pytest.approx(2.0)
    assert comparison.improvement_percent == pytest.approx(50.0)
    assert "without_cache" in summary
    assert "with_cache" in summary
    assert "50.00%" in summary
