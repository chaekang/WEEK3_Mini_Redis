from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence import AofParseError, AofWriter
from app.protocol.http_handlers import CommandExecutionError
from app.protocol.schemas import CommandResult


class FakeExecutor:
    def __init__(self, responses: dict[tuple[str, tuple[str, ...]], Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def __call__(self, command: str, args: list[str]) -> CommandResult:
        key = (command, tuple(args))
        self.calls.append(key)
        response = self._responses[key]
        if isinstance(response, Exception):
            raise response
        return response


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
async def test_ping_serializes_pong() -> None:
    fake_executor = FakeExecutor({("PING", ()): "PONG"})

    response = await request(create_app(fake_executor), "GET", "/v1/ping")

    assert response.status_code == 200
    assert response.json() == {"result": "PONG"}
    assert fake_executor.calls == [("PING", ())]


@pytest.mark.anyio
async def test_get_hit_serializes_found_value() -> None:
    fake_executor = FakeExecutor({("GET", ("alpha",)): (True, "hello")})

    response = await request(create_app(fake_executor), "GET", "/v1/keys/alpha")

    assert response.status_code == 200
    assert response.json() == {"found": True, "value": "hello"}
    assert fake_executor.calls == [("GET", ("alpha",))]


@pytest.mark.anyio
async def test_get_miss_serializes_missing_value() -> None:
    fake_executor = FakeExecutor({("GET", ("missing",)): (False, None)})

    response = await request(create_app(fake_executor), "GET", "/v1/keys/missing")

    assert response.status_code == 200
    assert response.json() == {"found": False, "value": None}
    assert fake_executor.calls == [("GET", ("missing",))]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "json_body", "command", "args", "result", "expected_body"),
    [
        (
            "PUT",
            "/v1/keys/alpha",
            {"value": "hello"},
            "SET",
            ("alpha", "hello"),
            "OK",
            {"result": "OK"},
        ),
        ("DELETE", "/v1/keys/alpha", None, "DEL", ("alpha",), 1, {"result": 1}),
        (
            "POST",
            "/v1/keys/alpha/expire",
            {"seconds": 10},
            "EXPIRE",
            ("alpha", "10"),
            1,
            {"result": 1},
        ),
        ("GET", "/v1/keys/alpha/ttl", None, "TTL", ("alpha",), -1, {"result": -1}),
        (
            "DELETE",
            "/v1/keys/alpha/expiration",
            None,
            "PERSIST",
            ("alpha",),
            1,
            {"result": 1},
        ),
    ],
)
async def test_protocol_routes_serialize_command_results(
    method: str,
    path: str,
    json_body: dict[str, Any] | None,
    command: str,
    args: tuple[str, ...],
    result: Any,
    expected_body: dict[str, Any],
) -> None:
    fake_executor = FakeExecutor({(command, args): result})

    response = await request(create_app(fake_executor), method, path, json=json_body)

    assert response.status_code == 200
    assert response.json() == expected_body
    assert fake_executor.calls == [(command, args)]


@pytest.mark.anyio
async def test_command_execution_errors_map_to_bad_request() -> None:
    fake_executor = FakeExecutor(
        {("GET", ("broken",)): CommandExecutionError("unknown command: BROKEN")}
    )

    response = await request(create_app(fake_executor), "GET", "/v1/keys/broken")

    assert response.status_code == 400
    assert response.json() == {"error": "unknown command: BROKEN"}


@pytest.mark.anyio
async def test_unexpected_executor_errors_map_to_internal_error() -> None:
    fake_executor = FakeExecutor({("GET", ("broken",)): RuntimeError("boom")})

    response = await request(create_app(fake_executor), "GET", "/v1/keys/broken")

    assert response.status_code == 500
    assert response.json() == {"error": "internal error"}


@pytest.mark.anyio
async def test_missing_body_field_maps_to_wrong_number_of_arguments() -> None:
    fake_executor = FakeExecutor({})

    response = await request(
        create_app(fake_executor), "PUT", "/v1/keys/alpha", json={}
    )

    assert response.status_code == 400
    assert response.json() == {"error": "wrong number of arguments for SET"}
    assert fake_executor.calls == []


@pytest.mark.anyio
async def test_wrong_json_type_maps_to_wrong_type() -> None:
    fake_executor = FakeExecutor({})

    response = await request(
        create_app(fake_executor),
        "POST",
        "/v1/keys/alpha/expire",
        json={"seconds": "10"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": "wrong type for EXPIRE"}
    assert fake_executor.calls == []


@pytest.mark.anyio
async def test_malformed_json_maps_to_invalid_request() -> None:
    fake_executor = FakeExecutor({})

    response = await request(
        create_app(fake_executor),
        "PUT",
        "/v1/keys/alpha",
        content='{"value":',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": "invalid request"}
    assert fake_executor.calls == []


def test_default_app_starts_with_missing_aof_file(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    with TestClient(create_app()) as client:
        ping_response = client.get("/v1/ping")
        get_response = client.get("/v1/keys/alpha")

    assert ping_response.status_code == 200
    assert ping_response.json() == {"result": "PONG"}
    assert get_response.status_code == 200
    assert get_response.json() == {"found": False, "value": None}


def test_default_app_recovers_state_from_aof_without_growing_log(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    aof_path = tmp_path / "appendonly.aof"

    with AofWriter(aof_path) as writer:
        writer.append_set("alpha", "1")
        writer.append_expireat("alpha", 4102444800.0)
        writer.append_persist("alpha")

    original_lines = aof_path.read_text(encoding="utf-8").splitlines()

    with TestClient(create_app()) as client:
        response = client.get("/v1/keys/alpha")

    replayed_lines = aof_path.read_text(encoding="utf-8").splitlines()

    assert response.status_code == 200
    assert response.json() == {"found": True, "value": "1"}
    assert replayed_lines == original_lines


def test_default_app_does_not_revive_expired_replay_entries(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    aof_path = tmp_path / "appendonly.aof"

    with AofWriter(aof_path) as writer:
        writer.append_set("stale", "value")
        writer.append_expireat("stale", 1.0)

    with TestClient(create_app()) as client:
        response = client.get("/v1/keys/stale")

    assert response.status_code == 200
    assert response.json() == {"found": False, "value": None}


def test_default_app_fails_startup_for_malformed_aof(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    aof_path = tmp_path / "appendonly.aof"
    aof_path.write_text('{"command":"SET","args":["a","1"]}\nnot-json\n', encoding="utf-8")

    with pytest.raises(AofParseError, match="line 2"):
        with TestClient(create_app()):
            pass


def test_default_app_wires_the_real_command_stack() -> None:
    """Use TestClient so app lifespan runs and command_executor is set."""
    with TestClient(create_app()) as client:
        ping_response = client.get("/v1/ping")
        set_response = client.put("/v1/keys/alpha", json={"value": "1"})
        get_response = client.get("/v1/keys/alpha")

    assert ping_response.status_code == 200
    assert ping_response.json() == {"result": "PONG"}
    assert set_response.status_code == 200
    assert set_response.json() == {"result": "OK"}
    assert get_response.status_code == 200
    assert get_response.json() == {"found": True, "value": "1"}
