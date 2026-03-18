"""Command registry definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.commands.errors import UnknownCommandError
from app.core.interfaces import StoreProtocol

CommandHandler = Callable[[StoreProtocol, Sequence[str]], object]


@dataclass(frozen=True)
class CommandSpec:
    """Immutable command definition used by the dispatcher."""

    name: str
    arity: int
    handler: CommandHandler


def normalize_command_name(command_name: str) -> str:
    """Normalize command names to the canonical uppercase form."""

    return command_name.strip().upper()


def build_registry(*command_specs: CommandSpec) -> dict[str, CommandSpec]:
    """Create a registry keyed by normalized command name."""

    return {
        normalize_command_name(command_spec.name): command_spec
        for command_spec in command_specs
    }


def resolve_command(command_name: str, registry: dict[str, CommandSpec]) -> CommandSpec:
    """Resolve a command definition or raise the documented shared error."""

    normalized_name = normalize_command_name(command_name)
    command_spec = registry.get(normalized_name)
    if command_spec is None:
        raise UnknownCommandError(normalized_name)
    return command_spec
