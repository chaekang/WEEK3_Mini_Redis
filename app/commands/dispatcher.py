"""Command dispatcher boundary between protocol and store layers."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from app.commands.errors import (
    CommandError,
    InternalError,
    InvalidIntegerError,
    WrongNumberOfArgumentsError,
)
from app.commands.registry import CommandSpec, build_registry, resolve_command
from app.core.expiration import calculate_expires_at
from app.core.interfaces import StoreProtocol
from app.persistence import AofEntry, AofWriter


def _ping_handler(_: StoreProtocol, __: Sequence[str]) -> str:
    return "PONG"


def _get_handler(
    store: StoreProtocol, arguments: Sequence[str]
) -> tuple[bool, str | None]:
    return store.get(arguments[0])


def _set_handler(store: StoreProtocol, arguments: Sequence[str]) -> str:
    return store.set(arguments[0], arguments[1])


def _delete_handler(store: StoreProtocol, arguments: Sequence[str]) -> int:
    return store.delete(arguments[0])


def _parse_int_argument(command_name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise InvalidIntegerError(command_name, value) from error


def _expire_handler(store: StoreProtocol, arguments: Sequence[str]) -> int:
    return store.expire(
        arguments[0],
        _parse_int_argument("EXPIRE", arguments[1]),
    )


def _ttl_handler(store: StoreProtocol, arguments: Sequence[str]) -> int:
    return store.ttl(arguments[0])


def _persist_handler(store: StoreProtocol, arguments: Sequence[str]) -> int:
    return store.persist(arguments[0])


DEFAULT_REGISTRY = build_registry(
    CommandSpec(name="PING", arity=0, handler=_ping_handler),
    CommandSpec(name="GET", arity=1, handler=_get_handler),
    CommandSpec(name="SET", arity=2, handler=_set_handler),
    CommandSpec(name="DEL", arity=1, handler=_delete_handler),
    CommandSpec(name="EXPIRE", arity=2, handler=_expire_handler),
    CommandSpec(name="TTL", arity=1, handler=_ttl_handler),
    CommandSpec(name="PERSIST", arity=1, handler=_persist_handler),
)


class Dispatcher:
    """Protocol-agnostic command dispatcher for the command layer."""

    def __init__(
        self,
        store: StoreProtocol,
        registry: dict[str, CommandSpec] | None = None,
        aof_writer: AofWriter | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.store = store
        self.registry = registry or DEFAULT_REGISTRY
        self.aof_writer = aof_writer
        self._clock = clock if clock is not None else time.time
        self._suppress_aof = False

    def dispatch(self, command_name: str, arguments: Sequence[str]) -> object:
        """Validate and dispatch a command using the shared command registry."""

        command_spec = resolve_command(command_name, self.registry)
        if len(arguments) != command_spec.arity:
            raise WrongNumberOfArgumentsError(command_spec.name)

        try:
            result = command_spec.handler(self.store, arguments)
            self._append_command(command_spec.name, arguments, result)
            return result
        except CommandError:
            raise
        except Exception as error:
            raise InternalError() from error

    def apply_aof_entry(self, entry: AofEntry, now: float | None = None) -> None:
        """Apply a replayed AOF entry without generating new AOF lines. EXPIREAT with expires_at <= now is skipped."""

        if now is None:
            now = self._clock()

        if entry.command == "SET":
            key, value = entry.args
            assert isinstance(key, str) and isinstance(value, str)
            self.store.set(key, value)
            return

        if entry.command == "DEL":
            (key,) = entry.args
            assert isinstance(key, str)
            self.store.delete(key)
            return

        if entry.command == "PERSIST":
            (key,) = entry.args
            assert isinstance(key, str)
            self.store.persist(key)
            return

        if entry.command == "EXPIREAT":
            key, expires_at = entry.args
            assert isinstance(key, str) and type(expires_at) is float
            if expires_at <= now:
                return
            self.store.expireat(key, expires_at)
            return

        raise ValueError(f"unsupported replay command: {entry.command}")

    def _append_command(
        self, command_name: str, arguments: Sequence[str], result: object
    ) -> None:
        if self.aof_writer is None or self._suppress_aof:
            return

        if command_name == "SET":
            self.aof_writer.append_set(arguments[0], arguments[1])
        elif command_name == "DEL":
            if result != 1:
                return
            self.aof_writer.append_delete(arguments[0])
        elif command_name == "PERSIST":
            if result != 1:
                return
            self.aof_writer.append_persist(arguments[0])
        elif command_name == "EXPIRE":
            if result != 1:
                return
            expires_at = calculate_expires_at(
                self._clock(),
                _parse_int_argument("EXPIRE", arguments[1]),
            )
            self.aof_writer.append_expireat(arguments[0], expires_at)
        else:
            return

        self.aof_writer.flush()
