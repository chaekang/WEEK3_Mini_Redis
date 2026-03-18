"""Application composition root.

This module wires the protocol layer to an injected command executor.
Store and dispatcher integration can be connected later without changing the
HTTP surface defined in this branch.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.protocol import CommandExecutor, create_http_router, install_exception_handlers
from app.protocol.schemas import CommandResult


def _default_command_executor(command: str, args: list[str]) -> CommandResult:
    """Placeholder command executor until dispatcher/store branches merge."""

    del args
    if command == "PING":
        return "PONG"
    raise RuntimeError("Command executor is not wired yet.")


def create_app(command_executor: CommandExecutor | None = None) -> FastAPI:
    """Create the FastAPI application for the Mini Redis HTTP protocol."""

    executor = command_executor or _default_command_executor

    app = FastAPI(title="Mini Redis")
    install_exception_handlers(app)
    app.include_router(create_http_router(executor))
    return app


app = create_app()
