from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the protocol branch smoke checks."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the running Mini Redis server.",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=5.0) as client:
        ping_response = client.get("/v1/ping")
        _expect_json(ping_response, 200, {"result": "PONG"}, "PING")

        malformed_response = client.put("/v1/keys/demo", json={})
        _expect_json(
            malformed_response,
            400,
            {"error": "wrong number of arguments for SET"},
            "Malformed request",
        )

        set_response = client.put("/v1/keys/demo", json={"value": "hello"})
        _expect_json(set_response, 200, {"result": "OK"}, "SET")

        get_response = client.get("/v1/keys/demo")
        _expect_json(get_response, 200, {"found": True, "value": "hello"}, "GET hit")

        expire_response = client.post("/v1/keys/demo/expire", json={"seconds": 1})
        _expect_json(expire_response, 200, {"result": 1}, "EXPIRE")

        ttl_response = client.get("/v1/keys/demo/ttl")
        _expect_status(ttl_response, 200, "TTL")
        ttl_payload = ttl_response.json()
        if not isinstance(ttl_payload, dict) or not isinstance(
            ttl_payload.get("result"), int
        ):
            raise AssertionError(f"TTL: expected integer result, got {ttl_payload!r}")
        print(f"TTL: ok -> {ttl_payload}")

        time.sleep(1.1)

        expired_get_response = client.get("/v1/keys/demo")
        _expect_json(
            expired_get_response,
            200,
            {"found": False, "value": None},
            "GET expired miss",
        )

    print("Protocol smoke checks completed.")
    return 0


def _expect_json(
    response: httpx.Response,
    expected_status: int,
    expected_body: dict[str, Any],
    label: str,
) -> None:
    _expect_status(response, expected_status, label)
    payload = response.json()
    if payload != expected_body:
        raise AssertionError(
            f"{label}: expected body {expected_body!r}, got {payload!r}"
        )
    print(f"{label}: ok -> {payload}")


def _expect_status(response: httpx.Response, expected_status: int, label: str) -> None:
    if response.status_code != expected_status:
        raise AssertionError(
            f"{label}: expected status {expected_status}, got {response.status_code} with body {response.text!r}"
        )


if __name__ == "__main__":
    sys.exit(main())
