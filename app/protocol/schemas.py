"""Request and response schemas for the HTTP + JSON contract."""

from __future__ import annotations

from typing import Optional, Protocol, Tuple, Union

from typing_extensions import TypeAlias

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

CommandResult: TypeAlias = Union[str, int, Tuple[bool, Optional[str]]]


class CommandExecutor(Protocol):
    """Callable command boundary used by the protocol layer."""

    def __call__(self, command: str, args: list[str]) -> CommandResult:
        """Execute a command and return its semantic result."""
        ...


class SetValueRequest(BaseModel):
    """Body for PUT /v1/keys/{key}."""

    model_config = ConfigDict(extra="forbid")

    value: StrictStr


class ExpireRequest(BaseModel):
    """Body for POST /v1/keys/{key}/expire."""

    model_config = ConfigDict(extra="forbid")

    seconds: StrictInt


class StringResultResponse(BaseModel):
    """JSON envelope for string command results."""

    result: str


class IntegerResultResponse(BaseModel):
    """JSON envelope for integer command results."""

    result: int


class GetValueResponse(BaseModel):
    """JSON envelope for GET responses."""

    found: bool
    value: Optional[str]


class ErrorResponse(BaseModel):
    """JSON envelope for API errors."""

    error: str
