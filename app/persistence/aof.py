"""Isolated AOF-lite append helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


class AofParseError(ValueError):
    """Raised when an AOF entry cannot be parsed or validated."""


@dataclass(frozen=True)
class AofEntry:
    """A single AOF write operation."""

    command: str
    args: tuple[str | float, ...]

    def __post_init__(self) -> None:
        _validate_entry(self.command, self.args)

    def to_json_line(self) -> str:
        payload = {"command": self.command, "args": list(self.args)}
        return json.dumps(payload, separators=(",", ":"))

    @classmethod
    def from_json_line(cls, line: str) -> "AofEntry":
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AofParseError("invalid AOF JSON") from exc

        if not isinstance(payload, dict):
            raise AofParseError("AOF entry must be an object")

        command = payload.get("command")
        args = payload.get("args")

        if not isinstance(command, str):
            raise AofParseError("AOF command must be a string")
        if not isinstance(args, list):
            raise AofParseError("AOF args must be a list")

        return cls(command=command, args=tuple(args))


class AofWriter:
    """Append-only JSON Lines writer for isolated persistence tests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle: TextIO = self.path.open("a", encoding="utf-8", newline="\n")

    def append_set(self, key: str, value: str) -> None:
        self._append(AofEntry(command="SET", args=(key, value)))

    def append_delete(self, key: str) -> None:
        self._append(AofEntry(command="DEL", args=(key,)))

    def append_expireat(self, key: str, expires_at: float) -> None:
        self._append(AofEntry(command="EXPIREAT", args=(key, expires_at)))

    def append_persist(self, key: str) -> None:
        self._append(AofEntry(command="PERSIST", args=(key,)))

    def flush(self) -> None:
        self._handle.flush()

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> "AofWriter":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _append(self, entry: AofEntry) -> None:
        self._handle.write(entry.to_json_line())
        self._handle.write("\n")


def _validate_entry(command: str, args: tuple[str | float, ...]) -> None:
    if command == "SET":
        if len(args) != 2 or not all(isinstance(item, str) for item in args):
            raise AofParseError("SET requires string key and value")
        return

    if command in {"DEL", "PERSIST"}:
        if len(args) != 1 or not isinstance(args[0], str):
            raise AofParseError(f"{command} requires a string key")
        return

    if command == "EXPIREAT":
        if len(args) != 2 or not isinstance(args[0], str) or type(args[1]) is not float:
            raise AofParseError("EXPIREAT requires string key and float expires_at")
        return

    raise AofParseError(f"unsupported AOF command: {command}")
