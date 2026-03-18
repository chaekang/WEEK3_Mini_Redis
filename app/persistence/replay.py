"""Isolated AOF-lite replay helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from app.core.interfaces import StoreProtocol

from .aof import AofEntry, AofParseError


def apply_aof_entry_to_store(
    store: StoreProtocol, entry: AofEntry, now: float
) -> None:
    """Apply a single AOF entry to the store. Store.expireat(..., past) deletes the key."""

    if entry.command == "SET":
        key, value = entry.args
        assert isinstance(key, str) and isinstance(value, str)
        store.set(key, value)
        return

    if entry.command == "DEL":
        (key,) = entry.args
        assert isinstance(key, str)
        store.delete(key)
        return

    if entry.command == "PERSIST":
        (key,) = entry.args
        assert isinstance(key, str)
        store.persist(key)
        return

    if entry.command == "EXPIREAT":
        key, expires_at = entry.args
        assert isinstance(key, str) and type(expires_at) is float
        store.expireat(key, expires_at)
        return

    raise ValueError(f"unsupported replay command: {entry.command}")


def replay_aof(
    path: str | Path,
    apply_entry: Callable[[AofEntry, float], None],
    *,
    now: float | None = None,
) -> int:
    """Replay JSON Lines AOF entries through a callback. Passes (entry, now) to apply_entry."""

    aof_path = Path(path)
    if not aof_path.exists():
        return 0

    if now is None:
        now = time.time()

    applied = 0
    with aof_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                entry = AofEntry.from_json_line(line)
            except AofParseError as exc:
                raise AofParseError(f"{exc} at line {line_number}") from exc

            apply_entry(entry, now)
            applied += 1

    return applied
