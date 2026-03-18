from app.commands.errors import (
    InternalError,
    InvalidIntegerError,
    UnknownCommandError,
    WrongNumberOfArgumentsError,
    WrongTypeError,
)


def test_unknown_command_error_uses_documented_message_and_status() -> None:
    error = UnknownCommandError("getx")

    assert str(error) == "unknown command: GETX"
    assert error.status_code == 400


def test_wrong_number_of_arguments_error_uses_documented_message_and_status() -> None:
    error = WrongNumberOfArgumentsError("set")

    assert str(error) == "wrong number of arguments for SET"
    assert error.status_code == 400


def test_invalid_integer_error_uses_documented_message_and_status() -> None:
    error = InvalidIntegerError("expire", "abc")

    assert str(error) == "invalid integer for EXPIRE: abc"
    assert error.status_code == 400


def test_wrong_type_error_uses_documented_message_and_status() -> None:
    error = WrongTypeError("ttl")

    assert str(error) == "wrong type for TTL"
    assert error.status_code == 400


def test_internal_error_uses_documented_message_and_status() -> None:
    error = InternalError()

    assert str(error) == "internal error"
    assert error.status_code == 500
