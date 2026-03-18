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

    def ttl(self, key: str) -> int:
        self.calls.append(("ttl", (key,)))
        return -1

    def persist(self, key: str) -> int:
        self.calls.append(("persist", (key,)))
        return 1

    def sweep_expired(self) -> int:
        self.calls.append(("sweep_expired", ()))
        return 0


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
