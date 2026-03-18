"""Standalone RESP application wiring without touching the HTTP main module."""

from __future__ import annotations

import argparse
from typing import cast

from app.commands.dispatcher import Dispatcher
from app.core.store import Store
from app.protocol.schemas import CommandExecutor
from app.protocol.resp_server import RespServer


def create_resp_executor() -> CommandExecutor:
    """Build the default RESP command pipeline."""

    store = Store()
    dispatcher = Dispatcher(store)
    return cast(CommandExecutor, dispatcher.dispatch)


def create_resp_server(host: str = "127.0.0.1", port: int = 6380) -> RespServer:
    """Create a standalone RESP server with the default dispatcher pipeline."""

    return RespServer(create_resp_executor(), host=host, port=port)


def main() -> int:
    """Run the standalone RESP server until interrupted."""

    parser = argparse.ArgumentParser(description="Run the Mini Redis RESP server.")
    parser.add_argument("--host", default="127.0.0.1", help="RESP server host.")
    parser.add_argument("--port", type=int, default=6380, help="RESP server port.")
    args = parser.parse_args()

    server = create_resp_server(host=args.host, port=args.port)
    host, port = server.server_address
    print(f"RESP server listening on {host}:{port}")
    print("Press Ctrl+C to stop the RESP server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping RESP server...")
    finally:
        server.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
