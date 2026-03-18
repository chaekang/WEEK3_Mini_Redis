from __future__ import annotations

from typing import Any

import pytest

from app.commands.dispatcher import Dispatcher
from app.commands.errors import (
    InternalError,
    InvalidIntegerError,
    UnknownCommandError,
    WrongNumberOfArgumentsError,
)
from app.persistence import AofEntry


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.raise_error = False

    def get(self, key: str) -> tuple[bool, str | None]:
        self.calls.append(("get", (key,)))
        return True, "value"

    def set(self, key: str, value: str) -> str:
        self.calls.append(("set", (key, value)))
        return "OK"

    def delete(self, key: str) -> int:
        self.calls.append(("delete", (key,)))
        return 1

    def expire(self, key: str, seconds: int) -> int:
        self.calls.append(("expire", (key, seconds)))
        if self.raise_error:
            raise RuntimeError("boom")
        return 1

    def expireat(self, key: str, expires_at: float) -> int:
        self.calls.append(("expireat", (key, expires_at)))
        return 1

    def ttl(self, key: str) -> int:
        self.calls.append(("ttl", (key,)))
        return -1

    def persist(self, key: str) -> int:
        self.calls.append(("persist", (key,)))
        return 1

    def sweep_expired(self) -> int:
        self.calls.append(("sweep_expired", ()))
        return 0


class FakeAofWriter:
    def __init__(self) -> None:
        self.entries: list[AofEntry] = []
        self.flush_calls = 0

    def append_set(self, key: str, value: str) -> None:
        self.entries.append(AofEntry(command="SET", args=(key, value)))

    def append_delete(self, key: str) -> None:
        self.entries.append(AofEntry(command="DEL", args=(key,)))

    def append_expireat(self, key: str, expires_at: float) -> None:
        self.entries.append(AofEntry(command="EXPIREAT", args=(key, expires_at)))

    def append_persist(self, key: str) -> None:
        self.entries.append(AofEntry(command="PERSIST", args=(key,)))

    def flush(self) -> None:
        self.flush_calls += 1


def test_dispatcher_dispatches_ping_without_store_usage() -> None:
    store = FakeStore()
    dispatcher = Dispatcher(store)

    result = dispatcher.dispatch("PING", [])

    assert result == "PONG"
    assert store.calls == []


def test_dispatcher_dispatches_store_backed_command() -> None:
    store = FakeStore()
    dispatcher = Dispatcher(store)

    result = dispatcher.dispatch("set", ["user:1", "hello"])

    assert result == "OK"
    assert store.calls == [("set", ("user:1", "hello"))]


def test_dispatcher_raises_for_unknown_command() -> None:
    dispatcher = Dispatcher(FakeStore())

    with pytest.raises(UnknownCommandError, match="unknown command: NOPE"):
        dispatcher.dispatch("nope", [])


def test_dispatcher_raises_for_wrong_arity() -> None:
    dispatcher = Dispatcher(FakeStore())

    with pytest.raises(
        WrongNumberOfArgumentsError,
        match="wrong number of arguments for GET",
    ):
        dispatcher.dispatch("GET", [])


def test_dispatcher_maps_invalid_integer_errors() -> None:
    dispatcher = Dispatcher(FakeStore())

    with pytest.raises(
        InvalidIntegerError,
        match="invalid integer for EXPIRE: tomorrow",
    ):
        dispatcher.dispatch("EXPIRE", ["session", "tomorrow"])


def test_dispatcher_maps_unexpected_store_errors_to_internal_error() -> None:
    store = FakeStore()
    store.raise_error = True
    dispatcher = Dispatcher(store)

    with pytest.raises(InternalError, match="internal error"):
        dispatcher.dispatch("EXPIRE", ["session", "10"])


def test_dispatcher_appends_set_to_aof_after_success() -> None:
    store = FakeStore()
    writer = FakeAofWriter()
    dispatcher = Dispatcher(store, aof_writer=writer)

    result = dispatcher.dispatch("SET", ["user:1", "hello"])

    assert result == "OK"
    assert writer.entries == [AofEntry(command="SET", args=("user:1", "hello"))]
    assert writer.flush_calls == 1


def test_dispatcher_appends_expire_as_expireat_timestamp() -> None:
    store = FakeStore()
    writer = FakeAofWriter()
    dispatcher = Dispatcher(store, aof_writer=writer, clock=lambda: 100.0)

    result = dispatcher.dispatch("EXPIRE", ["session", "15"])

    assert result == 1
    assert writer.entries == [AofEntry(command="EXPIREAT", args=("session", 115.0))]
    assert writer.flush_calls == 1


def test_dispatcher_does_not_append_read_only_commands() -> None:
    store = FakeStore()
    writer = FakeAofWriter()
    dispatcher = Dispatcher(store, aof_writer=writer)

    assert dispatcher.dispatch("PING", []) == "PONG"
    assert dispatcher.dispatch("GET", ["user:1"]) == (True, "value")
    assert dispatcher.dispatch("TTL", ["user:1"]) == -1
    assert writer.entries == []
    assert writer.flush_calls == 0


def test_dispatcher_does_not_append_when_command_fails() -> None:
    store = FakeStore()
    store.raise_error = True
    writer = FakeAofWriter()
    dispatcher = Dispatcher(store, aof_writer=writer)

    with pytest.raises(InternalError, match="internal error"):
        dispatcher.dispatch("EXPIRE", ["session", "10"])

    assert writer.entries == []
    assert writer.flush_calls == 0


def test_apply_aof_entry_replays_without_appending_again() -> None:
    store = FakeStore()
    writer = FakeAofWriter()
    dispatcher = Dispatcher(store, aof_writer=writer)

    dispatcher.apply_aof_entry(AofEntry(command="SET", args=("a", "1")))
    dispatcher.apply_aof_entry(AofEntry(command="EXPIREAT", args=("a", 150.0)))
    dispatcher.apply_aof_entry(AofEntry(command="PERSIST", args=("a",)))
    dispatcher.apply_aof_entry(AofEntry(command="DEL", args=("a",)))

    assert store.calls == [
        ("set", ("a", "1")),
        ("expireat", ("a", 150.0)),
        ("persist", ("a",)),
        ("delete", ("a",)),
    ]
    assert writer.entries == []
    assert writer.flush_calls == 0
