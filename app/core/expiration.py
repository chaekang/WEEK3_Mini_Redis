"""Expiration and periodic sweep helpers."""

from typing import Mapping


def calculate_expires_at(now: float, seconds: int) -> float:
    """Convert a relative TTL into an absolute Unix timestamp."""

    return now + float(seconds)


def is_expired(expires_at: float, now: float) -> bool:
    """Return whether the expiration timestamp is no longer valid."""

    return expires_at <= now


def ttl_seconds(expires_at: float, now: float) -> int:
    """Return the remaining TTL as a non-negative integer number of seconds."""

    return max(0, int(expires_at - now))


def find_expired_keys(expire_map: Mapping[str, float], now: float) -> list[str]:
    """Collect keys that should be removed during a sweep."""

    return [
        key for key, expires_at in expire_map.items() if is_expired(expires_at, now)
    ]
