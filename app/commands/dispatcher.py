"""Command dispatcher boundary between protocol and store layers."""

from __future__ import annotations

from collections.abc import Sequence

from app.commands.errors import (
    CommandError,
    InternalError,
    InvalidIntegerError,
    WrongNumberOfArgumentsError,
)
from app.commands.registry import CommandSpec, build_registry, resolve_command
from app.core.interfaces import StoreProtocol


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
    ) -> None:
        self.store = store
        self.registry = registry or DEFAULT_REGISTRY

    def dispatch(self, command_name: str, arguments: Sequence[str]) -> object:
        """Validate and dispatch a command using the shared command registry."""

        command_spec = resolve_command(command_name, self.registry)
        if len(arguments) != command_spec.arity:
            raise WrongNumberOfArgumentsError(command_spec.name)

        try:
            return command_spec.handler(self.store, arguments)
        except CommandError:
            raise
        except Exception as error:
            raise InternalError() from error
