"""Shared command and API error definitions."""

from __future__ import annotations


class CommandError(Exception):
    """Base error shared across command dispatch and later protocol mapping."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownCommandError(CommandError):
    """Raised when a command is not registered for dispatch."""

    def __init__(self, command: str) -> None:
        super().__init__(f"unknown command: {command.upper()}")


class WrongNumberOfArgumentsError(CommandError):
    """Raised when a command receives the wrong number of arguments."""

    def __init__(self, command: str) -> None:
        super().__init__(f"wrong number of arguments for {command.upper()}")


class InvalidIntegerError(CommandError):
    """Raised when a command requires an integer argument and parsing fails."""

    def __init__(self, command: str, value: str) -> None:
        super().__init__(f"invalid integer for {command.upper()}: {value}")


class WrongTypeError(CommandError):
    """Raised when a command is used against an unsupported value type."""

    def __init__(self, command: str) -> None:
        super().__init__(f"wrong type for {command.upper()}")


class InternalError(CommandError):
    """Raised when an unexpected internal failure occurs."""

    status_code = 500

    def __init__(self) -> None:
        super().__init__("internal error")
