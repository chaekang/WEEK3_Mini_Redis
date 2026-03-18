"""HTTP handler entrypoints for the FastAPI protocol layer."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.protocol.schemas import (
    CommandExecutor,
    CommandResult,
    ErrorResponse,
    ExpireRequest,
    GetValueResponse,
    IntegerResultResponse,
    SetValueRequest,
    StringResultResponse,
)

SUPPORTED_COMMANDS = {"PING", "GET", "SET", "DEL", "EXPIRE", "TTL", "PERSIST"}


class CommandExecutionError(Exception):
    """Raised when downstream command execution should surface as a 400 error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def create_http_router(command_executor: CommandExecutor) -> APIRouter:
    """Build the HTTP router bound to a specific command executor."""

    router = APIRouter()

    @router.get("/v1/ping", response_model=StringResultResponse, name="PING")
    def ping() -> StringResultResponse:
        return _serialize_string_result(_execute_command(command_executor, "PING", []))

    @router.get("/v1/keys/{key}", response_model=GetValueResponse, name="GET")
    def get_value(key: str) -> GetValueResponse:
        return _serialize_get_result(_execute_command(command_executor, "GET", [key]))

    @router.put("/v1/keys/{key}", response_model=StringResultResponse, name="SET")
    def set_value(key: str, request_body: SetValueRequest) -> StringResultResponse:
        return _serialize_string_result(
            _execute_command(command_executor, "SET", [key, request_body.value])
        )

    @router.delete("/v1/keys/{key}", response_model=IntegerResultResponse, name="DEL")
    def delete_value(key: str) -> IntegerResultResponse:
        return _serialize_integer_result(
            _execute_command(command_executor, "DEL", [key])
        )

    @router.post(
        "/v1/keys/{key}/expire",
        response_model=IntegerResultResponse,
        name="EXPIRE",
    )
    def expire_value(key: str, request_body: ExpireRequest) -> IntegerResultResponse:
        return _serialize_integer_result(
            _execute_command(
                command_executor, "EXPIRE", [key, str(request_body.seconds)]
            )
        )

    @router.get("/v1/keys/{key}/ttl", response_model=IntegerResultResponse, name="TTL")
    def ttl_value(key: str) -> IntegerResultResponse:
        return _serialize_integer_result(
            _execute_command(command_executor, "TTL", [key])
        )

    @router.delete(
        "/v1/keys/{key}/expiration",
        response_model=IntegerResultResponse,
        name="PERSIST",
    )
    def persist_value(key: str) -> IntegerResultResponse:
        return _serialize_integer_result(
            _execute_command(command_executor, "PERSIST", [key])
        )

    return router


def install_exception_handlers(app: FastAPI) -> None:
    """Normalize framework and command errors to the documented JSON format."""

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        message = _validation_error_message(request, exc)
        return _error_response(status_code=400, message=message)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "internal error"
        return _error_response(status_code=exc.status_code, message=detail)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        return _error_response(status_code=500, message="internal error")


def _execute_command(
    command_executor: CommandExecutor, command: str, args: list[str]
) -> CommandResult:
    try:
        return command_executor(command, args)
    except CommandExecutionError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


def _serialize_string_result(result: CommandResult) -> StringResultResponse:
    if not isinstance(result, str):
        raise TypeError("Expected a string command result.")
    return StringResultResponse(result=result)


def _serialize_integer_result(result: CommandResult) -> IntegerResultResponse:
    if isinstance(result, bool) or not isinstance(result, int):
        raise TypeError("Expected an integer command result.")
    return IntegerResultResponse(result=result)


def _serialize_get_result(result: CommandResult) -> GetValueResponse:
    if not isinstance(result, tuple) or len(result) != 2:
        raise TypeError("Expected a GET tuple result.")

    found, value = result
    if not isinstance(found, bool):
        raise TypeError("Expected GET tuple found flag to be a boolean.")
    if value is not None and not isinstance(value, str):
        raise TypeError("Expected GET tuple value to be a string or None.")

    return GetValueResponse(found=found, value=value)


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(ErrorResponse(error=message)),
    )


def _validation_error_message(request: Request, exc: RequestValidationError) -> str:
    command = _command_name_from_request(request)

    for error in exc.errors():
        error_type = str(error.get("type", ""))
        if _is_json_invalid(error_type):
            return "invalid request"
        if command is None:
            return "invalid request"
        if _is_wrong_arity_error(error_type):
            return f"wrong number of arguments for {command}"
        if _is_wrong_type_error(error_type):
            return f"wrong type for {command}"

    return "invalid request"


def _command_name_from_request(request: Request) -> str | None:
    route = request.scope.get("route")
    if route is None:
        return None

    route_name = getattr(route, "name", None)
    if isinstance(route_name, str) and route_name in SUPPORTED_COMMANDS:
        return route_name
    return None


def _is_json_invalid(error_type: str) -> bool:
    return error_type in {"json_invalid", "value_error.jsondecode"}


def _is_wrong_arity_error(error_type: str) -> bool:
    return error_type in {"missing", "extra_forbidden", "value_error.missing"}


def _is_wrong_type_error(error_type: str) -> bool:
    if error_type in {
        "string_type",
        "int_type",
        "float_type",
        "bool_type",
        "list_type",
        "dict_type",
        "int_parsing",
        "string_sub_type",
    }:
        return True
    return error_type.startswith("type_error.") or error_type.startswith(
        "value_error.strict"
    )
