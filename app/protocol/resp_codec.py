"""RESP response serialization helpers."""

from __future__ import annotations

from app.commands.registry import normalize_command_name
from app.protocol.schemas import CommandResult


def encode_command_result(command_name: str, result: CommandResult) -> bytes:
    """Serialize a shared semantic result to the documented RESP wire format."""

    normalized_command = normalize_command_name(command_name)

    if normalized_command == "GET":
        return _encode_get_result(result)
    if normalized_command in {"PING", "SET"}:
        if not isinstance(result, str):
            raise TypeError("Expected a string result.")
        return encode_simple_string(result)
    if normalized_command in {"DEL", "EXPIRE", "TTL", "PERSIST"}:
        if isinstance(result, bool) or not isinstance(result, int):
            raise TypeError("Expected an integer result.")
        return encode_integer(result)

    raise TypeError(f"Unsupported RESP command result: {normalized_command}")


def encode_simple_string(value: str) -> bytes:
    return f"+{value}\r\n".encode("utf-8")


def encode_bulk_string(value: str) -> bytes:
    payload = value.encode("utf-8")
    return b"$" + str(len(payload)).encode("ascii") + b"\r\n" + payload + b"\r\n"


def encode_null_bulk_string() -> bytes:
    return b"$-1\r\n"


def encode_integer(value: int) -> bytes:
    return f":{value}\r\n".encode("ascii")


def encode_error(message: str) -> bytes:
    return f"-{message}\r\n".encode("utf-8")


def _encode_get_result(result: CommandResult) -> bytes:
    if not isinstance(result, tuple) or len(result) != 2:
        raise TypeError("Expected a GET tuple result.")

    found, value = result
    if not isinstance(found, bool):
        raise TypeError("Expected GET tuple found flag to be a boolean.")
    if value is not None and not isinstance(value, str):
        raise TypeError("Expected GET tuple value to be a string or None.")

    if not found:
        return encode_null_bulk_string()
    if value is None:
        raise TypeError("Expected a GET hit to include a string value.")
    return encode_bulk_string(value)
