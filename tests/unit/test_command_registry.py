from app.commands.dispatcher import DEFAULT_REGISTRY
from app.commands.registry import resolve_command


def test_registry_contains_expected_mvp_commands() -> None:
    assert set(DEFAULT_REGISTRY) == {
        "PING",
        "GET",
        "SET",
        "DEL",
        "EXPIRE",
        "TTL",
        "PERSIST",
    }


def test_registry_resolves_commands_case_insensitively() -> None:
    assert resolve_command("ping", DEFAULT_REGISTRY) is resolve_command(
        "PING", DEFAULT_REGISTRY
    )


def test_registry_exposes_expected_command_arities() -> None:
    assert DEFAULT_REGISTRY["PING"].arity == 0
    assert DEFAULT_REGISTRY["GET"].arity == 1
    assert DEFAULT_REGISTRY["SET"].arity == 2
    assert DEFAULT_REGISTRY["DEL"].arity == 1
    assert DEFAULT_REGISTRY["EXPIRE"].arity == 2
    assert DEFAULT_REGISTRY["TTL"].arity == 1
    assert DEFAULT_REGISTRY["PERSIST"].arity == 1
