"""Isolated AOF-lite replay helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .aof import AofEntry, AofParseError


def replay_aof(path: str | Path, apply_entry: Callable[[AofEntry], None]) -> int:
    """Replay JSON Lines AOF entries through a callback."""

    aof_path = Path(path)
    if not aof_path.exists():
        return 0

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

            apply_entry(entry)
            applied += 1

    return applied
