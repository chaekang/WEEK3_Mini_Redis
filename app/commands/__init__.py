"""Command dispatch package."""

from app.commands.dispatcher import DEFAULT_REGISTRY, Dispatcher
from app.commands.errors import (
    CommandError,
    InternalError,
    InvalidIntegerError,
    UnknownCommandError,
    WrongNumberOfArgumentsError,
    WrongTypeError,
)
from app.commands.registry import CommandSpec, resolve_command

__all__ = [
    "CommandError",
    "CommandSpec",
    "DEFAULT_REGISTRY",
    "Dispatcher",
    "InternalError",
    "InvalidIntegerError",
    "UnknownCommandError",
    "WrongNumberOfArgumentsError",
    "WrongTypeError",
    "resolve_command",
]
