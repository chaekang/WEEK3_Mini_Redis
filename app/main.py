"""Application composition root."""

from __future__ import annotations

<<<<<<< feature/persistence-tests-bench
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
=======
from typing import cast
>>>>>>> chore/dev

from fastapi import FastAPI

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
<<<<<<< feature/persistence-tests-bench
from app.persistence import AofWriter, replay_aof
=======
>>>>>>> chore/dev
from app.protocol import CommandExecutor, create_http_router, install_exception_handlers

DEFAULT_AOF_PATH = Path("appendonly.aof")


def _delegating_command_executor(app: FastAPI) -> CommandExecutor:
    def execute(command: str, args: list[str]) -> CommandResult:
        executor = getattr(app.state, "command_executor", None)
        if executor is None:
            raise RuntimeError("Command executor is not wired yet.")
        return executor(command, args)

<<<<<<< feature/persistence-tests-bench
    return execute


@asynccontextmanager
async def _runtime_lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = Store()
    writer = AofWriter(DEFAULT_AOF_PATH)
    dispatcher = Dispatcher(store, aof_writer=writer)

    app.state.command_executor = dispatcher.dispatch

    try:
        replay_aof(DEFAULT_AOF_PATH, dispatcher.apply_aof_entry)
        yield
    finally:
        writer.flush()
        writer.close()
=======
def _create_default_command_executor() -> CommandExecutor:
    """Build the default command pipeline for the integrated application."""

    store = Store()
    dispatcher = Dispatcher(store)
    return cast(CommandExecutor, dispatcher.dispatch)
>>>>>>> chore/dev


def create_app(command_executor: CommandExecutor | None = None) -> FastAPI:
    """Create the FastAPI application for the Mini Redis HTTP protocol."""

<<<<<<< feature/persistence-tests-bench
    app = FastAPI(
        title="Mini Redis",
        lifespan=None if command_executor is not None else _runtime_lifespan,
    )
    app.state.command_executor = command_executor
=======
    executor = (
        command_executor
        if command_executor is not None
        else _create_default_command_executor()
    )

    app = FastAPI(title="Mini Redis")
>>>>>>> chore/dev
    install_exception_handlers(app)
    app.include_router(create_http_router(_delegating_command_executor(app)))
    return app


app = create_app()
