from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
from app.main import create_app


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def build_stack_app() -> tuple[Any, FakeClock]:
    clock = FakeClock()
    store = Store(clock=clock)
    dispatcher = Dispatcher(store)
    return create_app(command_executor=dispatcher.dispatch), clock


async def request(
    app: Any,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.anyio
async def test_full_stack_supports_the_documented_command_lifecycle() -> None:
    app, clock = build_stack_app()

    ping_response = await request(app, "GET", "/v1/ping")
    missing_response = await request(app, "GET", "/v1/keys/session")
    set_response = await request(app, "PUT", "/v1/keys/session", json={"value": "v1"})
    get_response = await request(app, "GET", "/v1/keys/session")
    ttl_without_expire = await request(app, "GET", "/v1/keys/session/ttl")
    expire_response = await request(
        app,
        "POST",
        "/v1/keys/session/expire",
        json={"seconds": 5},
    )
    ttl_after_expire = await request(app, "GET", "/v1/keys/session/ttl")

    clock.advance(2.4)
    ttl_after_time_passes = await request(app, "GET", "/v1/keys/session/ttl")

    persist_response = await request(app, "DELETE", "/v1/keys/session/expiration")
    ttl_after_persist = await request(app, "GET", "/v1/keys/session/ttl")
    delete_response = await request(app, "DELETE", "/v1/keys/session")
    missing_after_delete = await request(app, "GET", "/v1/keys/session")

    assert ping_response.json() == {"result": "PONG"}
    assert missing_response.json() == {"found": False, "value": None}
    assert set_response.json() == {"result": "OK"}
    assert get_response.json() == {"found": True, "value": "v1"}
    assert ttl_without_expire.json() == {"result": -1}
    assert expire_response.json() == {"result": 1}
    assert ttl_after_expire.json() == {"result": 5}
    assert ttl_after_time_passes.json() == {"result": 2}
    assert persist_response.json() == {"result": 1}
    assert ttl_after_persist.json() == {"result": -1}
    assert delete_response.json() == {"result": 1}
    assert missing_after_delete.json() == {"found": False, "value": None}


@pytest.mark.anyio
async def test_set_overwrite_clears_existing_ttl_across_the_http_stack() -> None:
    app, _clock = build_stack_app()

    first_set = await request(app, "PUT", "/v1/keys/profile", json={"value": "draft"})
    expire_response = await request(
        app,
        "POST",
        "/v1/keys/profile/expire",
        json={"seconds": 30},
    )
    overwrite_response = await request(
        app,
        "PUT",
        "/v1/keys/profile",
        json={"value": "published"},
    )
    ttl_response = await request(app, "GET", "/v1/keys/profile/ttl")
    get_response = await request(app, "GET", "/v1/keys/profile")

    assert first_set.json() == {"result": "OK"}
    assert expire_response.json() == {"result": 1}
    assert overwrite_response.json() == {"result": "OK"}
    assert ttl_response.json() == {"result": -1}
    assert get_response.json() == {"found": True, "value": "published"}


@pytest.mark.anyio
async def test_expired_and_non_positive_expire_paths_behave_like_missing_keys() -> None:
    app, clock = build_stack_app()

    await request(app, "PUT", "/v1/keys/temp", json={"value": "value"})
    immediate_expire = await request(
        app,
        "POST",
        "/v1/keys/temp/expire",
        json={"seconds": 0},
    )
    get_after_immediate_expire = await request(app, "GET", "/v1/keys/temp")
    ttl_after_immediate_expire = await request(app, "GET", "/v1/keys/temp/ttl")

    await request(app, "PUT", "/v1/keys/temp", json={"value": "value"})
    await request(app, "POST", "/v1/keys/temp/expire", json={"seconds": 1})
    clock.advance(1)

    get_after_lazy_expire = await request(app, "GET", "/v1/keys/temp")
    ttl_after_lazy_expire = await request(app, "GET", "/v1/keys/temp/ttl")
    persist_after_lazy_expire = await request(app, "DELETE", "/v1/keys/temp/expiration")
    delete_after_lazy_expire = await request(app, "DELETE", "/v1/keys/temp")

    assert immediate_expire.json() == {"result": 1}
    assert get_after_immediate_expire.json() == {"found": False, "value": None}
    assert ttl_after_immediate_expire.json() == {"result": -2}
    assert get_after_lazy_expire.json() == {"found": False, "value": None}
    assert ttl_after_lazy_expire.json() == {"result": -2}
    assert persist_after_lazy_expire.json() == {"result": 0}
    assert delete_after_lazy_expire.json() == {"result": 0}
