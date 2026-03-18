from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Awaitable, Callable

import httpx
from fastapi import FastAPI


@dataclass(frozen=True)
class CaseObservation:
    value: str
    origin_fetches: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    iterations: int
    warmup: int
    total_seconds: float
    average_seconds: float
    origin_fetches: int
    cache_hits: int
    cache_misses: int
    sample_value: str | None


@dataclass(frozen=True)
class BenchmarkComparison:
    without_cache: BenchmarkResult
    with_redis_cache: BenchmarkResult
    cache_is_faster: bool
    speedup: float
    improvement_percent: float


def create_dummy_origin_app(origin_latency_ms: float) -> FastAPI:
    if origin_latency_ms < 0:
        raise ValueError("origin_latency_ms must be zero or greater")

    app = FastAPI(title="Mini Redis Benchmark Origin")

    @app.get("/source/{key}")
    async def read_source(key: str) -> dict[str, str]:
        await asyncio.sleep(origin_latency_ms / 1000)
        return {"value": _origin_value_for_key(key)}

    return app


async def measure_case(
    name: str,
    action: Callable[[], Awaitable[CaseObservation]],
    *,
    iterations: int = 20,
    warmup: int = 1,
) -> BenchmarkResult:
    if iterations <= 0:
        raise ValueError("iterations must be greater than zero")
    if warmup < 0:
        raise ValueError("warmup must be zero or greater")

    for _ in range(warmup):
        await action()

    origin_fetches = 0
    cache_hits = 0
    cache_misses = 0
    sample_value: str | None = None

    started_at = perf_counter()
    for _ in range(iterations):
        observation = await action()
        origin_fetches += observation.origin_fetches
        cache_hits += observation.cache_hits
        cache_misses += observation.cache_misses
        sample_value = observation.value
    finished_at = perf_counter()

    total_seconds = finished_at - started_at
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        warmup=warmup,
        total_seconds=total_seconds,
        average_seconds=total_seconds / iterations,
        origin_fetches=origin_fetches,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        sample_value=sample_value,
    )


async def run_without_cache_case(
    *,
    key: str,
    iterations: int = 20,
    warmup: int = 1,
    origin_latency_ms: float = 20.0,
) -> BenchmarkResult:
    async with _origin_client(origin_latency_ms) as origin_client:

        async def action() -> CaseObservation:
            value = await _fetch_origin(origin_client, key)
            return CaseObservation(value=value, origin_fetches=1)

        return await measure_case(
            "without_cache",
            action,
            iterations=iterations,
            warmup=warmup,
        )


async def run_with_redis_cache_case(
    *,
    key: str,
    iterations: int = 20,
    warmup: int = 1,
    origin_latency_ms: float = 20.0,
) -> BenchmarkResult:
    async with _origin_client(origin_latency_ms) as origin_client:
        async with _redis_client() as redis_client:
            await _reset_key(redis_client, key)

            async def action() -> CaseObservation:
                cached_value = await _read_cached_value(redis_client, key)
                if cached_value is not None:
                    return CaseObservation(value=cached_value, cache_hits=1)

                origin_value = await _fetch_origin(origin_client, key)
                await _write_cached_value(redis_client, key, origin_value)
                return CaseObservation(
                    value=origin_value,
                    origin_fetches=1,
                    cache_misses=1,
                )

            return await measure_case(
                "with_redis_cache",
                action,
                iterations=iterations,
                warmup=warmup,
            )


async def run_cache_vs_origin_benchmark(
    *,
    key: str,
    iterations: int = 20,
    warmup: int = 1,
    origin_latency_ms: float = 20.0,
) -> BenchmarkComparison:
    without_cache = await run_without_cache_case(
        key=key,
        iterations=iterations,
        warmup=warmup,
        origin_latency_ms=origin_latency_ms,
    )
    with_redis_cache = await run_with_redis_cache_case(
        key=key,
        iterations=iterations,
        warmup=warmup,
        origin_latency_ms=origin_latency_ms,
    )

    if without_cache.sample_value != with_redis_cache.sample_value:
        raise RuntimeError("Benchmark cases returned different logical payloads")

    cache_is_faster = with_redis_cache.total_seconds < without_cache.total_seconds
    if with_redis_cache.total_seconds == 0:
        speedup = float("inf")
    else:
        speedup = without_cache.total_seconds / with_redis_cache.total_seconds

    if without_cache.total_seconds == 0:
        improvement_percent = 0.0
    else:
        improvement_percent = (
            (without_cache.total_seconds - with_redis_cache.total_seconds)
            / without_cache.total_seconds
        ) * 100

    return BenchmarkComparison(
        without_cache=without_cache,
        with_redis_cache=with_redis_cache,
        cache_is_faster=cache_is_faster,
        speedup=speedup,
        improvement_percent=improvement_percent,
    )


def format_summary_table(comparison: BenchmarkComparison) -> str:
    without_cache = comparison.without_cache
    with_redis_cache = comparison.with_redis_cache

    lines = [
        "case                total (s)   avg (ms)   origin   hits  misses",
        "----------------------------------------------------------------",
        _format_result_line(without_cache),
        _format_result_line(with_redis_cache),
        "",
        f"sample value: {without_cache.sample_value}",
        f"cache faster: {'yes' if comparison.cache_is_faster else 'no'}",
        f"speedup: {comparison.speedup:.2f}x",
        f"improvement: {comparison.improvement_percent:.2f}%",
    ]
    return "\n".join(lines)


def _format_result_line(result: BenchmarkResult) -> str:
    return (
        f"{result.name:<18}"
        f"{result.total_seconds:>10.6f}"
        f"{result.average_seconds * 1000:>11.3f}"
        f"{result.origin_fetches:>9}"
        f"{result.cache_hits:>7}"
        f"{result.cache_misses:>8}"
    )


def _origin_value_for_key(key: str) -> str:
    return f"origin-value:{key}"


def _origin_client(origin_latency_ms: float) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(
        app=create_dummy_origin_app(origin_latency_ms),
        raise_app_exceptions=False,
    )
    return httpx.AsyncClient(transport=transport, base_url="http://origin")


def _redis_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(
        app=_create_mini_redis_app(),
        raise_app_exceptions=False,
    )
    return httpx.AsyncClient(transport=transport, base_url="http://mini-redis")


async def _fetch_origin(origin_client: httpx.AsyncClient, key: str) -> str:
    response = await origin_client.get(f"/source/{key}")
    _expect_status(response, 200, "Origin GET")
    payload = response.json()
    value = payload.get("value")
    if not isinstance(value, str):
        raise RuntimeError(f"Origin GET returned unexpected payload: {payload!r}")
    return value


async def _read_cached_value(redis_client: httpx.AsyncClient, key: str) -> str | None:
    response = await redis_client.get(f"/v1/keys/{key}")
    _expect_status(response, 200, "Mini Redis GET")
    payload = response.json()

    if payload == {"found": False, "value": None}:
        return None

    if payload.get("found") is True and isinstance(payload.get("value"), str):
        return payload["value"]

    raise RuntimeError(f"Mini Redis GET returned unexpected payload: {payload!r}")


async def _write_cached_value(
    redis_client: httpx.AsyncClient, key: str, value: str
) -> None:
    response = await redis_client.put(f"/v1/keys/{key}", json={"value": value})
    _expect_status(response, 200, "Mini Redis PUT")
    payload = response.json()
    if payload != {"result": "OK"}:
        raise RuntimeError(f"Mini Redis PUT returned unexpected payload: {payload!r}")


async def _reset_key(redis_client: httpx.AsyncClient, key: str) -> None:
    response = await redis_client.delete(f"/v1/keys/{key}")
    _expect_status(response, 200, "Mini Redis DEL")
    payload = response.json()
    if payload not in ({"result": 0}, {"result": 1}):
        raise RuntimeError(f"Mini Redis DEL returned unexpected payload: {payload!r}")


def _expect_status(response: httpx.Response, expected_status: int, label: str) -> None:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"{label} returned HTTP {response.status_code}: {response.text}"
        )


def _create_mini_redis_app() -> FastAPI:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app.main import create_app

    return create_app()
