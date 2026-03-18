"""Application composition root."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
from app.protocol import CommandExecutor, create_http_router, install_exception_handlers


def _create_default_command_executor() -> CommandExecutor:
    """Build the default command pipeline for the integrated application."""

    store = Store()
    dispatcher = Dispatcher(store)
    return cast(CommandExecutor, dispatcher.dispatch)


def create_app(command_executor: CommandExecutor | None = None) -> FastAPI:
    """Create the FastAPI application for the Mini Redis HTTP protocol."""

    executor = (
        command_executor
        if command_executor is not None
        else _create_default_command_executor()
    )

    app = FastAPI(title="Mini Redis")
    install_exception_handlers(app)
    app.include_router(create_http_router(executor))
    return app


app = create_app()
