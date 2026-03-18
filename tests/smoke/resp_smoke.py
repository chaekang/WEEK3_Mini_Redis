from __future__ import annotations

import argparse
import socket
import sys
import threading
import time


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the RESP subset TCP smoke checks."
    )
    parser.add_argument("--host", default="127.0.0.1", help="RESP server host.")
    parser.add_argument("--port", type=int, default=6380, help="RESP server port.")
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        _expect_response(connection, _command("PING"), b"+PONG\r\n", "PING")
        _expect_response(
            connection, _command("SET", "demo", "hello"), b"+OK\r\n", "SET"
        )
        _expect_response(
            connection, _command("GET", "demo"), b"$5\r\nhello\r\n", "GET hit"
        )
        _expect_response(connection, _command("TTL", "demo"), b":-1\r\n", "TTL")
        _expect_response(
            connection, _command("EXPIRE", "demo", "1"), b":1\r\n", "EXPIRE"
        )
        _expect_response(connection, _command("PERSIST", "demo"), b":1\r\n", "PERSIST")
        _expect_response(connection, _command("TTL", "demo"), b":-1\r\n", "TTL clear")
        _expect_response(
            connection, _command("EXPIRE", "demo", "1"), b":1\r\n", "EXPIRE again"
        )

        time.sleep(1.1)

        _expect_response(
            connection, _command("GET", "demo"), b"$-1\r\n", "GET expired miss"
        )
        _expect_response(connection, _command("TTL", "demo"), b":-2\r\n", "TTL miss")
        _expect_response(connection, _command("DEL", "demo"), b":0\r\n", "DEL miss")
        _expect_response(
            connection,
            _command("PERSIST", "demo"),
            b":0\r\n",
            "PERSIST expired miss",
        )

    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        _expect_response(
            connection, _command("SET", "delete-me", "bye"), b"+OK\r\n", "SET delete"
        )
        _expect_response(connection, _command("DEL", "delete-me"), b":1\r\n", "DEL hit")
        _expect_response(
            connection, _command("GET", "delete-me"), b"$-1\r\n", "GET deleted miss"
        )

    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        _expect_response(
            connection,
            _command("SET", "invalidate-me", "now"),
            b"+OK\r\n",
            "SET invalidate",
        )
        _expect_response(
            connection,
            _command("EXPIRE", "invalidate-me", "0"),
            b":1\r\n",
            "EXPIRE immediate delete",
        )
        _expect_response(
            connection, _command("GET", "invalidate-me"), b"$-1\r\n", "GET invalidated"
        )
        _expect_response(
            connection, _command("TTL", "invalidate-me"), b":-2\r\n", "TTL invalidated"
        )

    _run_parallel_client_smoke(args.host, args.port)

    with socket.create_connection((args.host, args.port), timeout=5) as connection:
        connection.sendall(b"PING\r\n")
        response = _read_response(connection)
        if not response.startswith(b"-protocol error:"):
            raise AssertionError(
                f"Malformed frame: expected protocol error, got {response!r}"
            )
        print(f"Malformed frame: ok -> {response!r}")

    print("RESP smoke checks completed.")
    return 0


def _command(*parts: str) -> bytes:
    encoded = [f"*{len(parts)}\r\n".encode("ascii")]
    for part in parts:
        payload = part.encode("utf-8")
        encoded.append(b"$" + str(len(payload)).encode("ascii") + b"\r\n")
        encoded.append(payload + b"\r\n")
    return b"".join(encoded)


def _expect_response(
    connection: socket.socket, payload: bytes, expected: bytes, label: str
) -> None:
    connection.sendall(payload)
    response = _read_response(connection)
    if response != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {response!r}")
    print(f"{label}: ok -> {response!r}")


def _run_parallel_client_smoke(host: str, port: int) -> None:
    barrier = threading.Barrier(4)
    results: list[tuple[str, bytes, bytes]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def client_task(index: int) -> None:
        key = f"parallel:{index}"
        value = f"value-{index}"

        try:
            with socket.create_connection((host, port), timeout=5) as connection:
                barrier.wait(timeout=5)
                set_response = _send_and_read(connection, _command("SET", key, value))
                get_response = _send_and_read(connection, _command("GET", key))
            with lock:
                results.append((key, set_response, get_response))
        except BaseException as error:
            with lock:
                errors.append(error)

    threads = [
        threading.Thread(target=client_task, args=(index,), daemon=True)
        for index in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    if errors:
        raise AssertionError(f"Parallel client smoke failed: {errors!r}")
    if len(results) != 4:
        raise AssertionError(
            f"Parallel client smoke expected 4 results, got {len(results)}"
        )

    for key, set_response, get_response in sorted(results):
        expected_get = _bulk_string(f"value-{key.split(':', maxsplit=1)[1]}")
        if set_response != b"+OK\r\n":
            raise AssertionError(
                f"Parallel client {key}: expected SET +OK, got {set_response!r}"
            )
        if get_response != expected_get:
            raise AssertionError(
                f"Parallel client {key}: expected GET {expected_get!r}, got {get_response!r}"
            )
        print(f"Parallel client {key}: ok -> {get_response!r}")


def _read_response(connection: socket.socket) -> bytes:
    prefix = _read_exact(connection, 1)
    if prefix in {b"+", b"-", b":"}:
        return prefix + _readline(connection)
    if prefix == b"$":
        length_line = _readline(connection)
        length = int(length_line[:-2])
        if length < 0:
            return prefix + length_line
        return prefix + length_line + _read_exact(connection, length + 2)
    raise AssertionError(f"unexpected RESP response prefix: {prefix!r}")


def _send_and_read(connection: socket.socket, payload: bytes) -> bytes:
    connection.sendall(payload)
    return _read_response(connection)


def _readline(connection: socket.socket) -> bytes:
    buffer = bytearray()
    while not buffer.endswith(b"\r\n"):
        chunk = connection.recv(1)
        if chunk == b"":
            raise AssertionError("connection closed before CRLF")
        buffer.extend(chunk)
    return bytes(buffer)


def _read_exact(connection: socket.socket, size: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < size:
        chunk = connection.recv(size - len(buffer))
        if chunk == b"":
            raise AssertionError("connection closed before full payload")
        buffer.extend(chunk)
    return bytes(buffer)


def _bulk_string(value: str) -> bytes:
    payload = value.encode("utf-8")
    return b"$" + str(len(payload)).encode("ascii") + b"\r\n" + payload + b"\r\n"


if __name__ == "__main__":
    sys.exit(main())
