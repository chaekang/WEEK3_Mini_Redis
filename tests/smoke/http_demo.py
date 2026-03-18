from __future__ import annotations

import argparse
import sys
import time
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the documented HTTP smoke flow against a Mini Redis server."
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="HTTP base URL for the running Mini Redis server, for example http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--key", default="smoke:demo", help="Key used during the smoke run."
    )
    parser.add_argument(
        "--value", default="hello", help="Value written during the smoke run."
    )
    parser.add_argument(
        "--expire-seconds",
        type=int,
        default=2,
        help="TTL seconds to use for the EXPIRE step.",
    )
    parser.add_argument(
        "--wait-padding",
        type=float,
        default=0.2,
        help="Extra wait time after TTL expiration, in seconds.",
    )
    return parser.parse_args()


def assert_json(response: Any, expected: dict[str, object], step: str) -> None:
    if response.status_code != 200:
        raise RuntimeError(
            f"{step} returned HTTP {response.status_code}: {response.text}"
        )
    payload = response.json()
    if payload != expected:
        raise RuntimeError(f"{step} returned unexpected payload: {payload}")


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    key_path = f"/v1/keys/{args.key}"

    try:
        import httpx
    except ModuleNotFoundError:
        print(
            "Smoke failed: httpx is not installed in the current Python environment.",
            file=sys.stderr,
        )
        return 1

    try:
        with httpx.Client(base_url=base_url, timeout=5.0) as client:
            print("1. PING")
            assert_json(client.get("/v1/ping"), {"result": "PONG"}, "PING")

            print("2. SET")
            assert_json(
                client.put(key_path, json={"value": args.value}),
                {"result": "OK"},
                "SET",
            )

            print("3. GET hit")
            assert_json(
                client.get(key_path),
                {"found": True, "value": args.value},
                "GET hit",
            )

            print("4. EXPIRE")
            assert_json(
                client.post(
                    f"{key_path}/expire", json={"seconds": args.expire_seconds}
                ),
                {"result": 1},
                "EXPIRE",
            )

            print("5. TTL")
            ttl_response = client.get(f"{key_path}/ttl")
            if ttl_response.status_code != 200:
                raise RuntimeError(
                    f"TTL returned HTTP {ttl_response.status_code}: {ttl_response.text}"
                )
            ttl_payload = ttl_response.json()
            ttl_result = ttl_payload.get("result")
            if (
                type(ttl_result) is not int
                or not 0 <= ttl_result <= args.expire_seconds
            ):
                raise RuntimeError(f"TTL returned unexpected payload: {ttl_payload}")

            time.sleep(args.expire_seconds + args.wait_padding)

            print("6. GET expired miss")
            assert_json(
                client.get(key_path),
                {"found": False, "value": None},
                "GET expired miss",
            )

    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Smoke failed: {exc}", file=sys.stderr)
        return 1

    print("Smoke completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
