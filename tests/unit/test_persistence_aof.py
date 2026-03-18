from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.persistence import AofEntry, AofParseError, AofWriter, replay_aof


@contextmanager
def workspace_tmpdir() -> Iterator[Path]:
    with TemporaryDirectory(dir=Path.cwd()) as raw_dir:
        yield Path(raw_dir)


def test_append_order_is_preserved_during_replay() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "appendonly.aof"

        with AofWriter(aof_path) as writer:
            writer.append_set("user:1", "hello world")
            writer.append_expire("user:1", 15)
            writer.append_persist("user:1")
            writer.append_delete("user:1")

        replayed: list[AofEntry] = []
        applied = replay_aof(aof_path, replayed.append)

        assert applied == 4
        assert replayed == [
            AofEntry(command="SET", args=("user:1", "hello world")),
            AofEntry(command="EXPIRE", args=("user:1", 15)),
            AofEntry(command="PERSIST", args=("user:1",)),
            AofEntry(command="DEL", args=("user:1",)),
        ]


def test_replay_callback_can_recover_latest_state() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "appendonly.aof"

        with AofWriter(aof_path) as writer:
            writer.append_set("session:1", "warm")
            writer.append_expire("session:1", 30)
            writer.append_set("session:2", "cold")
            writer.append_persist("session:1")
            writer.append_delete("session:2")

        state: dict[str, str] = {}
        expire_map: dict[str, int] = {}

        def apply_entry(entry: AofEntry) -> None:
            if entry.command == "SET":
                key, value = entry.args
                assert isinstance(key, str)
                assert isinstance(value, str)
                state[key] = value
                expire_map.pop(key, None)
                return

            if entry.command == "DEL":
                key = entry.args[0]
                assert isinstance(key, str)
                state.pop(key, None)
                expire_map.pop(key, None)
                return

            if entry.command == "EXPIRE":
                key, seconds = entry.args
                assert isinstance(key, str)
                assert type(seconds) is int
                if key in state:
                    expire_map[key] = seconds
                return

            if entry.command == "PERSIST":
                key = entry.args[0]
                assert isinstance(key, str)
                if key in state:
                    expire_map.pop(key, None)
                return

            raise AssertionError(f"unexpected command: {entry.command}")

        applied = replay_aof(aof_path, apply_entry)

        assert applied == 5
        assert state == {"session:1": "warm"}
        assert expire_map == {}


def test_replay_returns_zero_for_empty_log() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "appendonly.aof"
        aof_path.write_text("", encoding="utf-8")

        replayed: list[AofEntry] = []
        applied = replay_aof(aof_path, replayed.append)

        assert applied == 0
        assert replayed == []


def test_replay_returns_zero_when_log_file_is_missing() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "missing.aof"

        replayed: list[AofEntry] = []
        applied = replay_aof(aof_path, replayed.append)

        assert applied == 0
        assert replayed == []


def test_replay_raises_parse_error_for_malformed_line() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "appendonly.aof"
        aof_path.write_text(
            '{"command":"SET","args":["a","1"]}\nnot-json\n', encoding="utf-8"
        )

        with pytest.raises(AofParseError, match="line 2"):
            replay_aof(aof_path, lambda entry: None)


def test_expire_seconds_stays_an_integer_in_json_lines() -> None:
    with workspace_tmpdir() as tmp_path:
        aof_path = tmp_path / "appendonly.aof"

        with AofWriter(aof_path) as writer:
            writer.append_expire("cart:1", 42)

        payload = json.loads(aof_path.read_text(encoding="utf-8").strip())
        replayed: list[AofEntry] = []
        replay_aof(aof_path, replayed.append)

        assert payload == {"command": "EXPIRE", "args": ["cart:1", 42]}
        assert replayed[0] == AofEntry(command="EXPIRE", args=("cart:1", 42))
        assert type(replayed[0].args[1]) is int
