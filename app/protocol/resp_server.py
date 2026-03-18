"""RESP subset TCP server implementation."""

from __future__ import annotations

import socketserver
import threading
from collections.abc import Callable
from typing import cast

from app.commands.errors import CommandError
from app.protocol.resp_codec import encode_command_result, encode_error
from app.protocol.resp_parser import RespProtocolError, parse_command_frame
from app.protocol.schemas import CommandExecutor


class _RespRequestHandler(socketserver.StreamRequestHandler):
    """Socket handler that parses RESP commands and writes RESP responses."""

    server: "_RespSocketServer"

    def handle(self) -> None:
        while True:
            try:
                frame = parse_command_frame(self.rfile)
            except RespProtocolError as error:
                self.wfile.write(encode_error(str(error)))
                self.wfile.flush()
                return

            if frame is None:
                return

            command_name, *arguments = frame
            try:
                result = self.server.command_executor(command_name, arguments)
                payload = encode_command_result(command_name, result)
            except CommandError as error:
                payload = encode_error(error.message)
            except Exception:
                payload = encode_error("internal error")

            self.wfile.write(payload)
            self.wfile.flush()


class _RespSocketServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server carrying the shared command executor."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        command_executor: CommandExecutor,
    ) -> None:
        self.command_executor = command_executor
        super().__init__(server_address, _RespRequestHandler)


class RespServer:
    """Small lifecycle wrapper around the threaded RESP TCP server."""

    def __init__(
        self,
        command_executor: CommandExecutor,
        host: str = "127.0.0.1",
        port: int = 6380,
    ) -> None:
        self._server = _RespSocketServer((host, port), command_executor)
        self._thread: threading.Thread | None = None

    @property
    def server_address(self) -> tuple[str, int]:
        return cast(tuple[str, int], self._server.server_address)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(
            target=cast(Callable[[], None], self._server.serve_forever),
            name="mini-redis-resp",
            daemon=True,
        )
        self._thread.start()

    def serve_forever(self) -> None:
        """Run the RESP server in the current thread until shutdown."""

        self._server.serve_forever()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "RespServer":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
