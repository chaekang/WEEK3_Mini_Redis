from __future__ import annotations

import io
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import product
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
from app.main import create_app
from app.protocol.resp_app import create_resp_server
from app.protocol.resp_codec import encode_command_result, encode_error
from app.protocol.resp_parser import RespProtocolError, parse_command_frame
from app.protocol.resp_server import RespServer


def _command(*parts: str) -> bytes:
    encoded = [f"*{len(parts)}\r\n".encode("ascii")]
    for part in parts:
        payload = part.encode("utf-8")
        encoded.append(b"$" + str(len(payload)).encode("ascii") + b"\r\n")
        encoded.append(payload + b"\r\n")
    return b"".join(encoded)


def _connect(server_address: tuple[str, int]) -> socket.socket:
    return socket.create_connection(server_address, timeout=5)


def _round_trip(connection: socket.socket, payload: bytes) -> bytes:
    connection.sendall(payload)
    return _read_response(connection)


def _resp_round_trip_raw(server_address: tuple[str, int], payload: bytes) -> bytes:
    with _connect(server_address) as connection:
        return _round_trip(connection, payload)


def _read_response(connection: socket.socket) -> bytes:
    prefix = _read_exact(connection, 1)
    if prefix in {b"+", b"-", b":"}:
        return prefix + _readline(connection)
    if prefix == b"$":
        length_line = _readline(connection)
        length = int(length_line[:-2])
        if length < 0:
            return prefix + length_line
        return prefix + length_line + _read_exact(connection, length + 2)
    raise AssertionError(f"unexpected RESP response prefix: {prefix!r}")


def _readline(connection: socket.socket) -> bytes:
    buffer = bytearray()
    while not buffer.endswith(b"\r\n"):
        chunk = connection.recv(1)
        if chunk == b"":
            raise AssertionError("connection closed before CRLF")
        buffer.extend(chunk)
    return bytes(buffer)


def _read_exact(connection: socket.socket, size: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < size:
        chunk = connection.recv(size - len(buffer))
        if chunk == b"":
            raise AssertionError("connection closed before full payload")
        buffer.extend(chunk)
    return bytes(buffer)


PROTOCOLS = ("resp", "http")
TTL_VALUES = (-5, -1, 0, 1, 2, 5, 10)
INVALIDATION_ACTIONS = ("DEL", "EXPIRE_ZERO", "EXPIRE_NEGATIVE")
LIFECYCLE_KINDS = (
    "expire_then_ttl",
    "persist_after_expire",
    "delete_then_missing",
)
CONCURRENCY_MODES = ("resp", "http", "mixed")
CONCURRENCY_WORKER_COUNTS = (4, 8, 16)
CONCURRENCY_PROFILES = (
    "different_key_set_get",
    "same_key_set_get",
    "different_key_set_expire_get",
    "different_key_persist_ttl",
    "same_key_del_get",
)
LONG_TEXT = "x" * 256

VALID_PARSE_CASES = [
    pytest.param(_command("PING"), ["PING"], id="ping-uppercase"),
    pytest.param(_command("ping"), ["ping"], id="ping-lowercase"),
    pytest.param(_command("SET", "", ""), ["SET", "", ""], id="empty-key-and-value"),
    pytest.param(_command("GET", LONG_TEXT), ["GET", LONG_TEXT], id="long-key"),
    pytest.param(_command("DEL", "session:1"), ["DEL", "session:1"], id="colon-key"),
    pytest.param(
        _command("SET", "space key", "space value"),
        ["SET", "space key", "space value"],
        id="spaces",
    ),
    pytest.param(
        _command("EXPIRE", "alpha", "0"), ["EXPIRE", "alpha", "0"], id="expire-zero"
    ),
    pytest.param(
        _command("SET", "unicode", "값"), ["SET", "unicode", "값"], id="unicode-value"
    ),
]

INVALID_PARSE_CASES = [
    pytest.param(
        b"PING\r\n",
        "protocol error: expected array of bulk strings",
        id="inline-command",
    ),
    pytest.param(
        b"*0\r\n",
        "protocol error: expected array of bulk strings",
        id="zero-length-array",
    ),
    pytest.param(
        b"*x\r\n",
        "protocol error: invalid array length",
        id="invalid-array-length",
    ),
    pytest.param(
        b"*1\n$4\r\nPING\r\n",
        "protocol error: invalid array length",
        id="array-line-without-crlf",
    ),
    pytest.param(
        b"*2\r\n+OK\r\n$1\r\na\r\n",
        "protocol error: expected bulk string",
        id="non-bulk-element",
    ),
    pytest.param(
        b"*2\r\n*1\r\n$1\r\na\r\n$1\r\nb\r\n",
        "protocol error: expected bulk string",
        id="nested-array",
    ),
    pytest.param(
        b"*1\r\n$-1\r\n",
        "protocol error: null bulk strings are not supported",
        id="null-bulk-string",
    ),
    pytest.param(
        b"*1\r\n$x\r\n",
        "protocol error: invalid bulk string length",
        id="invalid-bulk-length",
    ),
    pytest.param(
        b"*1\r\n$4\r\nabc",
        "protocol error: incomplete bulk string",
        id="incomplete-bulk-string",
    ),
    pytest.param(
        b"*1\r\n$3\r\nabc\n",
        "protocol error: invalid bulk string terminator",
        id="invalid-bulk-terminator",
    ),
    pytest.param(
        b"*2\r\n$3\r\nGET\r\n",
        "protocol error: expected bulk string",
        id="truncated-array",
    ),
    pytest.param(
        b"*1\r\n$2\r\n\xff\xff\r\n",
        "protocol error: bulk strings must be valid UTF-8",
        id="invalid-utf8",
    ),
]

CODEC_CASES = [
    pytest.param("PING", "PONG", b"+PONG\r\n", id="ping"),
    pytest.param("SET", "OK", b"+OK\r\n", id="set"),
    pytest.param("GET", (True, "hello"), b"$5\r\nhello\r\n", id="get-hit"),
    pytest.param("GET", (True, ""), b"$0\r\n\r\n", id="get-empty-string"),
    pytest.param("GET", (False, None), b"$-1\r\n", id="get-miss"),
    pytest.param("DEL", 0, b":0\r\n", id="del-miss"),
    pytest.param("DEL", 1, b":1\r\n", id="del-hit"),
    pytest.param("EXPIRE", 0, b":0\r\n", id="expire-miss"),
    pytest.param("EXPIRE", 1, b":1\r\n", id="expire-hit"),
    pytest.param("TTL", -2, b":-2\r\n", id="ttl-missing"),
    pytest.param("TTL", -1, b":-1\r\n", id="ttl-no-expire"),
    pytest.param("TTL", 0, b":0\r\n", id="ttl-zero"),
    pytest.param("TTL", 9, b":9\r\n", id="ttl-positive"),
    pytest.param("PERSIST", 1, b":1\r\n", id="persist-hit"),
]

ERROR_CODEC_CASES = [
    pytest.param(
        "wrong number of arguments for GET",
        b"-wrong number of arguments for GET\r\n",
        id="wrong-arity",
    ),
    pytest.param(
        "invalid integer for EXPIRE: abc",
        b"-invalid integer for EXPIRE: abc\r\n",
        id="invalid-integer",
    ),
    pytest.param(
        "unknown command: NOPE",
        b"-unknown command: NOPE\r\n",
        id="unknown-command",
    ),
    pytest.param("internal error", b"-internal error\r\n", id="internal-error"),
]

WRONG_ARITY_CASES = [
    pytest.param(
        _command("PING", "extra"), "wrong number of arguments for PING", id="ping"
    ),
    pytest.param(_command("GET"), "wrong number of arguments for GET", id="get"),
    pytest.param(
        _command("SET", "alpha"), "wrong number of arguments for SET", id="set"
    ),
    pytest.param(_command("DEL"), "wrong number of arguments for DEL", id="del"),
    pytest.param(
        _command("EXPIRE", "alpha"), "wrong number of arguments for EXPIRE", id="expire"
    ),
    pytest.param(_command("TTL"), "wrong number of arguments for TTL", id="ttl"),
    pytest.param(
        _command("PERSIST"), "wrong number of arguments for PERSIST", id="persist"
    ),
]

INVALID_INTEGER_CASES = [
    pytest.param("abc", id="alpha"),
    pytest.param("1.5", id="float"),
    pytest.param("+", id="plus"),
    pytest.param("", id="empty"),
    pytest.param("0x10", id="hex"),
]

UNKNOWN_COMMAND_CASES = [
    pytest.param("NOPE", id="nope"),
    pytest.param("INCR", id="incr"),
    pytest.param("MGET", id="mget"),
    pytest.param("multi", id="lowercase-multi"),
]

ERROR_ISOLATION_CASES = [
    pytest.param("resp_protocol_shape", "http", id="resp-shape-then-http"),
    pytest.param("resp_protocol_shape", "resp", id="resp-shape-then-resp"),
    pytest.param("resp_unknown_command", "http", id="resp-unknown-then-http"),
    pytest.param("resp_unknown_command", "resp", id="resp-unknown-then-resp"),
    pytest.param("http_invalid_request", "http", id="http-invalid-then-http"),
    pytest.param("http_invalid_request", "resp", id="http-invalid-then-resp"),
]

CONCURRENCY_CASES = [
    pytest.param(mode, workers, profile, id=f"{mode}-{workers}-{profile}")
    for mode, workers, profile in product(
        CONCURRENCY_MODES,
        CONCURRENCY_WORKER_COUNTS,
        CONCURRENCY_PROFILES,
    )
]


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class ProtocolHarness:
    app: Any
    http_client: TestClient
    resp_address: tuple[str, int]
    clock: FakeClock


@dataclass
class ConcurrencyOutcome:
    errors: list[str]
    worker_results: list[tuple[int, str, str, list[object]]]
    final_get: tuple[bool, str | None]
    final_ttl: int


@contextmanager
def running_dual_protocol_stack() -> Iterator[ProtocolHarness]:
    clock = FakeClock()
    store = Store(clock=clock)
    dispatcher = Dispatcher(store)
    app = create_app(command_executor=dispatcher.dispatch)
    resp_server = RespServer(dispatcher.dispatch, port=0)

    with resp_server, TestClient(app) as http_client:
        yield ProtocolHarness(
            app=app,
            http_client=http_client,
            resp_address=resp_server.server_address,
            clock=clock,
        )


@pytest.mark.parametrize(("payload", "expected"), VALID_PARSE_CASES)
def test_resp_parser_accepts_supported_bulk_arrays(
    payload: bytes, expected: list[str]
) -> None:
    assert parse_command_frame(io.BytesIO(payload)) == expected


@pytest.mark.parametrize(("payload", "message"), INVALID_PARSE_CASES)
def test_resp_parser_rejects_unsupported_request_shapes(
    payload: bytes, message: str
) -> None:
    with pytest.raises(RespProtocolError, match=message):
        parse_command_frame(io.BytesIO(payload))


@pytest.mark.parametrize(("command", "result", "expected"), CODEC_CASES)
def test_resp_codec_serializes_documented_result_types(
    command: str, result: object, expected: bytes
) -> None:
    assert encode_command_result(command, result) == expected


@pytest.mark.parametrize(("message", "expected"), ERROR_CODEC_CASES)
def test_resp_error_codec_serializes_simple_errors(
    message: str, expected: bytes
) -> None:
    assert encode_error(message) == expected


@pytest.mark.parametrize(("payload", "expected_message"), WRONG_ARITY_CASES)
def test_resp_server_reports_wrong_arity_errors(
    payload: bytes, expected_message: str
) -> None:
    with running_dual_protocol_stack() as harness:
        response = _resp_round_trip_raw(harness.resp_address, payload)
        assert response == _error_response(expected_message)


@pytest.mark.parametrize("value", INVALID_INTEGER_CASES)
def test_resp_server_reports_invalid_integer_errors(value: str) -> None:
    with running_dual_protocol_stack() as harness:
        response = _resp_round_trip_raw(
            harness.resp_address,
            _command("EXPIRE", "session", value),
        )
        assert response == _error_response(f"invalid integer for EXPIRE: {value}")


@pytest.mark.parametrize("command_name", UNKNOWN_COMMAND_CASES)
def test_resp_server_reports_unknown_commands(command_name: str) -> None:
    with running_dual_protocol_stack() as harness:
        response = _resp_round_trip_raw(
            harness.resp_address,
            _command(command_name, "key"),
        )
        assert response == _error_response(
            f"unknown command: {command_name.strip().upper()}"
        )


def test_standalone_resp_app_builds_default_command_stack() -> None:
    with create_resp_server(port=0) as resp_server:
        assert _execute_resp_command(resp_server.server_address, "PING") == "PONG"
        assert (
            _execute_resp_command(resp_server.server_address, "SET", "standalone", "ok")
            == "OK"
        )
        assert _execute_resp_command(
            resp_server.server_address, "GET", "standalone"
        ) == (
            True,
            "ok",
        )


@pytest.mark.parametrize(
    "setup_protocol,read_protocol,ttl_seconds",
    list(product(PROTOCOLS, PROTOCOLS, TTL_VALUES)),
)
def test_expiration_matrix_get_and_ttl(
    setup_protocol: str, read_protocol: str, ttl_seconds: int
) -> None:
    key = f"expiry:get:{setup_protocol}:{read_protocol}:{ttl_seconds}"

    with running_dual_protocol_stack() as harness:
        assert (
            _execute_protocol_command(harness, setup_protocol, "SET", key, "value")
            == "OK"
        )
        assert (
            _execute_protocol_command(
                harness, setup_protocol, "EXPIRE", key, str(ttl_seconds)
            )
            == 1
        )

        if ttl_seconds <= 0:
            _assert_missing_state(harness, read_protocol, key)
            return

        assert _execute_protocol_command(harness, read_protocol, "GET", key) == (
            True,
            "value",
        )
        ttl_before_expire = _execute_protocol_command(
            harness, read_protocol, "TTL", key
        )
        assert isinstance(ttl_before_expire, int)
        assert 0 <= ttl_before_expire <= ttl_seconds

        harness.clock.advance(float(ttl_seconds))
        _assert_missing_state(harness, read_protocol, key)


@pytest.mark.parametrize(
    "setup_protocol,access_protocol,ttl_seconds",
    list(product(PROTOCOLS, PROTOCOLS, TTL_VALUES)),
)
def test_expiration_matrix_persist_delete_and_overwrite(
    setup_protocol: str, access_protocol: str, ttl_seconds: int
) -> None:
    key = f"expiry:persist:{setup_protocol}:{access_protocol}:{ttl_seconds}"

    with running_dual_protocol_stack() as harness:
        assert (
            _execute_protocol_command(harness, setup_protocol, "SET", key, "value")
            == "OK"
        )
        assert (
            _execute_protocol_command(
                harness, setup_protocol, "EXPIRE", key, str(ttl_seconds)
            )
            == 1
        )

        persist_result = _execute_protocol_command(
            harness, access_protocol, "PERSIST", key
        )
        delete_result = _execute_protocol_command(harness, access_protocol, "DEL", key)

        if ttl_seconds <= 0:
            assert persist_result == 0
            assert delete_result == 0
            _assert_missing_state(harness, access_protocol, key)
            return

        assert persist_result == 1
        assert delete_result == 1
        _assert_missing_state(harness, access_protocol, key)

        recreate_protocol = _other_protocol(access_protocol)
        assert (
            _execute_protocol_command(
                harness, recreate_protocol, "SET", key, "recreated"
            )
            == "OK"
        )
        assert _execute_protocol_command(harness, access_protocol, "TTL", key) == -1

        harness.clock.advance(float(abs(ttl_seconds) + 10))
        assert _execute_protocol_command(harness, recreate_protocol, "GET", key) == (
            True,
            "recreated",
        )


@pytest.mark.parametrize(
    "action,setup_protocol,invalidation_protocol,verify_protocol",
    list(product(INVALIDATION_ACTIONS, PROTOCOLS, PROTOCOLS, PROTOCOLS)),
)
def test_invalidation_matrix_immediate_removal_is_consistent(
    action: str,
    setup_protocol: str,
    invalidation_protocol: str,
    verify_protocol: str,
) -> None:
    key = (
        f"invalidation:remove:{action}:{setup_protocol}:"
        f"{invalidation_protocol}:{verify_protocol}"
    )

    with running_dual_protocol_stack() as harness:
        assert (
            _execute_protocol_command(harness, setup_protocol, "SET", key, "value")
            == "OK"
        )

        invalidation_result = _run_invalidation_action(
            harness,
            invalidation_protocol,
            action,
            key,
        )
        assert invalidation_result == 1

        _assert_missing_state(harness, verify_protocol, key)
        assert _execute_protocol_command(harness, verify_protocol, "PERSIST", key) == 0
        assert _execute_protocol_command(harness, verify_protocol, "DEL", key) == 0


@pytest.mark.parametrize(
    "action,setup_protocol,invalidation_protocol,recreate_protocol",
    list(product(INVALIDATION_ACTIONS, PROTOCOLS, PROTOCOLS, PROTOCOLS)),
)
def test_invalidation_matrix_recreate_clears_previous_state(
    action: str,
    setup_protocol: str,
    invalidation_protocol: str,
    recreate_protocol: str,
) -> None:
    key = (
        f"invalidation:recreate:{action}:{setup_protocol}:"
        f"{invalidation_protocol}:{recreate_protocol}"
    )

    with running_dual_protocol_stack() as harness:
        assert (
            _execute_protocol_command(harness, setup_protocol, "SET", key, "value")
            == "OK"
        )
        assert (
            _execute_protocol_command(harness, setup_protocol, "EXPIRE", key, "10") == 1
        )

        invalidation_result = _run_invalidation_action(
            harness,
            invalidation_protocol,
            action,
            key,
        )
        assert invalidation_result == 1

        assert (
            _execute_protocol_command(
                harness, recreate_protocol, "SET", key, "new-value"
            )
            == "OK"
        )
        assert _execute_protocol_command(harness, recreate_protocol, "TTL", key) == -1

        harness.clock.advance(20.0)
        assert _execute_protocol_command(
            harness, _other_protocol(recreate_protocol), "GET", key
        ) == (True, "new-value")


@pytest.mark.parametrize(
    "lifecycle_kind,start_protocol,middle_protocol,final_protocol",
    list(product(LIFECYCLE_KINDS, PROTOCOLS, PROTOCOLS, PROTOCOLS)),
)
def test_cross_protocol_lifecycle_sequences(
    lifecycle_kind: str,
    start_protocol: str,
    middle_protocol: str,
    final_protocol: str,
) -> None:
    key = (
        f"lifecycle:{lifecycle_kind}:{start_protocol}:"
        f"{middle_protocol}:{final_protocol}"
    )

    with running_dual_protocol_stack() as harness:
        assert _execute_protocol_command(harness, start_protocol, "PING") == "PONG"
        assert (
            _execute_protocol_command(harness, start_protocol, "SET", key, "value")
            == "OK"
        )
        assert _execute_protocol_command(harness, middle_protocol, "GET", key) == (
            True,
            "value",
        )

        if lifecycle_kind == "expire_then_ttl":
            assert (
                _execute_protocol_command(harness, final_protocol, "EXPIRE", key, "5")
                == 1
            )
            ttl_result = _execute_protocol_command(harness, middle_protocol, "TTL", key)
            assert isinstance(ttl_result, int)
            assert 0 <= ttl_result <= 5

            harness.clock.advance(5.0)
            _assert_missing_state(harness, start_protocol, key)
            return

        if lifecycle_kind == "persist_after_expire":
            assert (
                _execute_protocol_command(harness, final_protocol, "EXPIRE", key, "5")
                == 1
            )
            assert (
                _execute_protocol_command(harness, middle_protocol, "PERSIST", key) == 1
            )
            assert _execute_protocol_command(harness, start_protocol, "TTL", key) == -1

            harness.clock.advance(5.0)
            assert _execute_protocol_command(harness, final_protocol, "GET", key) == (
                True,
                "value",
            )
            return

        assert _execute_protocol_command(harness, final_protocol, "DEL", key) == 1
        _assert_missing_state(harness, middle_protocol, key)


@pytest.mark.parametrize(("error_origin", "followup_protocol"), ERROR_ISOLATION_CASES)
def test_cross_protocol_error_isolation(
    error_origin: str, followup_protocol: str
) -> None:
    with running_dual_protocol_stack() as harness:
        if error_origin == "resp_protocol_shape":
            response = _resp_round_trip_raw(harness.resp_address, b"PING\r\n")
            assert response == _error_response(
                "protocol error: expected array of bulk strings"
            )
        elif error_origin == "resp_unknown_command":
            response = _resp_round_trip_raw(
                harness.resp_address,
                _command("NOPE", "key"),
            )
            assert response == _error_response("unknown command: NOPE")
        else:
            response = harness.http_client.put(
                "/v1/keys/http-error",
                content='{"value":',
                headers={"content-type": "application/json"},
            )
            assert response.status_code == 400
            assert response.json() == {"error": "invalid request"}

        assert _execute_protocol_command(harness, followup_protocol, "PING") == "PONG"
        assert (
            _execute_protocol_command(harness, followup_protocol, "SET", "healthy", "1")
            == "OK"
        )
        assert _execute_protocol_command(
            harness, followup_protocol, "GET", "healthy"
        ) == (True, "1")


@pytest.mark.parametrize(
    ("protocol_mode", "worker_count", "profile"), CONCURRENCY_CASES
)
def test_concurrency_matrix_preserves_invariants(
    protocol_mode: str, worker_count: int, profile: str
) -> None:
    outcome = _run_concurrency_case(protocol_mode, worker_count, profile)
    _assert_concurrency_invariants(outcome, worker_count, profile)


def _run_invalidation_action(
    harness: ProtocolHarness,
    protocol: str,
    action: str,
    key: str,
) -> int:
    if action == "DEL":
        result = _execute_protocol_command(harness, protocol, "DEL", key)
        assert isinstance(result, int)
        return result
    if action == "EXPIRE_ZERO":
        result = _execute_protocol_command(harness, protocol, "EXPIRE", key, "0")
        assert isinstance(result, int)
        return result

    result = _execute_protocol_command(harness, protocol, "EXPIRE", key, "-5")
    assert isinstance(result, int)
    return result


def _assert_missing_state(harness: ProtocolHarness, protocol: str, key: str) -> None:
    assert _execute_protocol_command(harness, protocol, "GET", key) == (False, None)
    assert _execute_protocol_command(harness, protocol, "TTL", key) == -2


def _run_concurrency_case(
    protocol_mode: str, worker_count: int, profile: str
) -> ConcurrencyOutcome:
    key_prefix = f"concurrency:{protocol_mode}:{worker_count}:{profile}"

    with running_dual_protocol_stack() as harness:
        if profile == "same_key_del_get":
            assert (
                _execute_protocol_command(harness, "resp", "SET", key_prefix, "seed")
                == "OK"
            )

        barrier = threading.Barrier(worker_count)
        errors: list[str] = []
        worker_results: list[tuple[int, str, str, list[object]]] = []
        lock = threading.Lock()

        def worker(index: int) -> None:
            protocol = _protocol_for_worker(protocol_mode, index)
            key = (
                key_prefix
                if profile.startswith("same_key")
                else f"{key_prefix}:{index}"
            )

            try:
                barrier.wait(timeout=10)
                results = _run_worker_sequence(
                    harness,
                    protocol,
                    _sequence_for_profile(profile, key, index),
                )
                with lock:
                    worker_results.append((index, protocol, key, results))
            except BaseException as error:
                with lock:
                    errors.append(f"worker-{index}: {error!r}")

        threads = [
            threading.Thread(target=worker, args=(index,), daemon=True)
            for index in range(worker_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        for index, thread in enumerate(threads):
            if thread.is_alive():
                errors.append(f"worker-{index}: thread did not finish")

        final_get = _execute_protocol_command(harness, "resp", "GET", key_prefix)
        final_ttl = _execute_protocol_command(harness, "resp", "TTL", key_prefix)
        assert isinstance(final_get, tuple)
        assert isinstance(final_ttl, int)

        return ConcurrencyOutcome(
            errors=errors,
            worker_results=sorted(worker_results, key=lambda item: item[0]),
            final_get=final_get,
            final_ttl=final_ttl,
        )


def _assert_concurrency_invariants(
    outcome: ConcurrencyOutcome, worker_count: int, profile: str
) -> None:
    assert outcome.errors == []
    assert len(outcome.worker_results) == worker_count

    if profile == "different_key_set_get":
        for index, _protocol, _key, results in outcome.worker_results:
            assert results == ["OK", (True, f"value-{index}")]
        return

    if profile == "same_key_set_get":
        allowed_values = {f"value-{index}" for index in range(worker_count)}
        for _index, _protocol, _key, results in outcome.worker_results:
            assert results[0] == "OK"
            assert results[1][0] is True
            assert results[1][1] in allowed_values
        assert outcome.final_get[0] is True
        assert outcome.final_get[1] in allowed_values
        assert outcome.final_ttl == -1
        return

    if profile == "different_key_set_expire_get":
        for index, _protocol, _key, results in outcome.worker_results:
            assert results == ["OK", 1, (True, f"value-{index}")]
        return

    if profile == "different_key_persist_ttl":
        for _index, _protocol, _key, results in outcome.worker_results:
            assert results == ["OK", 1, 1, -1]
        return

    for _index, _protocol, _key, results in outcome.worker_results:
        assert results[0] in {0, 1}
        assert results[1] == (False, None)
    assert outcome.final_get == (False, None)
    assert outcome.final_ttl == -2


def _sequence_for_profile(
    profile: str, key: str, index: int
) -> list[tuple[str, tuple[str, ...]]]:
    value = f"value-{index}"

    if profile == "different_key_set_get":
        return [("SET", (key, value)), ("GET", (key,))]
    if profile == "same_key_set_get":
        return [("SET", (key, value)), ("GET", (key,))]
    if profile == "different_key_set_expire_get":
        return [("SET", (key, value)), ("EXPIRE", (key, "5")), ("GET", (key,))]
    if profile == "different_key_persist_ttl":
        return [
            ("SET", (key, value)),
            ("EXPIRE", (key, "5")),
            ("PERSIST", (key,)),
            ("TTL", (key,)),
        ]

    return [("DEL", (key,)), ("GET", (key,))]


def _run_worker_sequence(
    harness: ProtocolHarness,
    protocol: str,
    sequence: list[tuple[str, tuple[str, ...]]],
) -> list[object]:
    if protocol == "http":
        with TestClient(harness.app) as client:
            return [
                _execute_http_command_with_client(client, command, *arguments)
                for command, arguments in sequence
            ]

    with _connect(harness.resp_address) as connection:
        return [
            _execute_resp_command_with_connection(connection, command, *arguments)
            for command, arguments in sequence
        ]


def _protocol_for_worker(protocol_mode: str, index: int) -> str:
    if protocol_mode == "resp":
        return "resp"
    if protocol_mode == "http":
        return "http"
    return "resp" if index % 2 == 0 else "http"


def _other_protocol(protocol: str) -> str:
    return "http" if protocol == "resp" else "resp"


def _execute_protocol_command(
    harness: ProtocolHarness,
    protocol: str,
    command: str,
    *arguments: str,
) -> object:
    if protocol == "resp":
        return _execute_resp_command(harness.resp_address, command, *arguments)
    return _execute_http_command_with_client(harness.http_client, command, *arguments)


def _execute_http_command_with_client(
    client: TestClient, command: str, *arguments: str
) -> object:
    normalized = command.strip().upper()

    if normalized == "PING":
        response = client.get("/v1/ping")
        assert response.status_code == 200, response.text
        return response.json()["result"]

    if normalized == "GET":
        response = client.get(f"/v1/keys/{arguments[0]}")
        assert response.status_code == 200, response.text
        payload = response.json()
        return payload["found"], payload["value"]

    if normalized == "SET":
        response = client.put(
            f"/v1/keys/{arguments[0]}",
            json={"value": arguments[1]},
        )
        assert response.status_code == 200, response.text
        return response.json()["result"]

    if normalized == "DEL":
        response = client.delete(f"/v1/keys/{arguments[0]}")
        assert response.status_code == 200, response.text
        return response.json()["result"]

    if normalized == "EXPIRE":
        response = client.post(
            f"/v1/keys/{arguments[0]}/expire",
            json={"seconds": int(arguments[1])},
        )
        assert response.status_code == 200, response.text
        return response.json()["result"]

    if normalized == "TTL":
        response = client.get(f"/v1/keys/{arguments[0]}/ttl")
        assert response.status_code == 200, response.text
        return response.json()["result"]

    if normalized == "PERSIST":
        response = client.delete(f"/v1/keys/{arguments[0]}/expiration")
        assert response.status_code == 200, response.text
        return response.json()["result"]

    raise AssertionError(f"unsupported HTTP command in test helper: {normalized}")


def _execute_resp_command(
    server_address: tuple[str, int], command: str, *arguments: str
) -> object:
    with _connect(server_address) as connection:
        return _execute_resp_command_with_connection(connection, command, *arguments)


def _execute_resp_command_with_connection(
    connection: socket.socket, command: str, *arguments: str
) -> object:
    raw_response = _round_trip(connection, _command(command, *arguments))
    return _decode_resp_command_result(command, raw_response)


def _decode_resp_command_result(command: str, raw_response: bytes) -> object:
    normalized = command.strip().upper()

    if raw_response.startswith(b"-"):
        raise AssertionError(
            f"unexpected RESP error for {normalized}: {raw_response!r}"
        )

    if normalized in {"PING", "SET"}:
        assert raw_response.startswith(b"+")
        return raw_response[1:-2].decode("utf-8")

    if normalized == "GET":
        if raw_response == b"$-1\r\n":
            return False, None
        assert raw_response.startswith(b"$")
        length_line, payload = raw_response[1:].split(b"\r\n", maxsplit=1)
        expected_length = int(length_line)
        value = payload[:-2].decode("utf-8")
        assert len(value.encode("utf-8")) == expected_length
        return True, value

    assert raw_response.startswith(b":")
    return int(raw_response[1:-2])


def _error_response(message: str) -> bytes:
    return f"-{message}\r\n".encode("utf-8")
