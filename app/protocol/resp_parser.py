"""RESP request parsing helpers for the subset TCP protocol."""

from __future__ import annotations

from typing import Protocol


class RespProtocolError(Exception):
    """Raised when a RESP request does not match the supported subset."""


class RespReadableStream(Protocol):
    """Binary stream shape required by the RESP parser."""

    def read(self, size: int = -1, /) -> bytes | None: ...

    def readline(self, size: int = -1, /) -> bytes: ...


def parse_command_frame(stream: RespReadableStream) -> list[str] | None:
    """Parse one RESP command frame from a binary stream.

    Returns ``None`` when the peer closes the stream cleanly before sending
    another frame.
    """

    prefix = stream.read(1)
    if prefix == b"":
        return None
    if prefix != b"*":
        raise RespProtocolError("protocol error: expected array of bulk strings")

    array_length = _parse_length(stream, "protocol error: invalid array length")
    if array_length <= 0:
        raise RespProtocolError("protocol error: expected array of bulk strings")

    parts: list[str] = []
    for _ in range(array_length):
        marker = stream.read(1)
        if marker != b"$":
            raise RespProtocolError("protocol error: expected bulk string")

        bulk_length = _parse_length(
            stream, "protocol error: invalid bulk string length"
        )
        if bulk_length < 0:
            raise RespProtocolError(
                "protocol error: null bulk strings are not supported"
            )

        payload = _read_exact(stream, bulk_length)
        _expect_crlf(stream, "protocol error: invalid bulk string terminator")

        try:
            parts.append(payload.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise RespProtocolError(
                "protocol error: bulk strings must be valid UTF-8"
            ) from error

    return parts


def _parse_length(stream: RespReadableStream, error_message: str) -> int:
    line = _readline(stream, error_message)
    try:
        return int(line)
    except ValueError as error:
        raise RespProtocolError(error_message) from error


def _readline(stream: RespReadableStream, error_message: str) -> bytes:
    line = stream.readline()
    if line == b"" or not line.endswith(b"\r\n"):
        raise RespProtocolError(error_message)
    return line[:-2]


def _read_exact(stream: RespReadableStream, size: int) -> bytes:
    payload = stream.read(size)
    if payload is None or len(payload) != size:
        raise RespProtocolError("protocol error: incomplete bulk string")
    return payload


def _expect_crlf(stream: RespReadableStream, error_message: str) -> None:
    if stream.read(2) != b"\r\n":
        raise RespProtocolError(error_message)
