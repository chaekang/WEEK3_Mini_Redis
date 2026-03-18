"""Application composition root."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
from app.persistence import AofWriter, replay_aof
from app.protocol import CommandExecutor, create_http_router, install_exception_handlers
from app.protocol.schemas import CommandResult

DEFAULT_AOF_PATH = Path("appendonly.aof")


def _delegating_command_executor(app: FastAPI) -> CommandExecutor:
    def execute(command: str, args: list[str]) -> CommandResult:
        executor = getattr(app.state, "command_executor", None)
        if executor is None:
            raise RuntimeError("Command executor is not wired yet.")
        return executor(command, args)

    return execute


@asynccontextmanager
async def _runtime_lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = Store()
    writer = AofWriter(DEFAULT_AOF_PATH)
    dispatcher = Dispatcher(store, aof_writer=writer)

    app.state.command_executor = dispatcher.dispatch

    try:
        replay_aof(
            DEFAULT_AOF_PATH,
            lambda entry, now: dispatcher.apply_aof_entry(entry, now),
        )
        yield
    finally:
        writer.flush()
        writer.close()


def create_app(command_executor: CommandExecutor | None = None) -> FastAPI:
    """Create the FastAPI application for the Mini Redis HTTP protocol."""

    app = FastAPI(
        title="Mini Redis",
        lifespan=None if command_executor is not None else _runtime_lifespan,
    )
    if command_executor is not None:
        app.state.command_executor = command_executor
    install_exception_handlers(app)
    app.include_router(create_http_router(_delegating_command_executor(app)))
    return app


app = create_app()
