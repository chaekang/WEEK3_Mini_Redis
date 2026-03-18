"""Store API and key/value storage implementation."""

import time
from typing import Callable, Optional, Tuple

from app.core.expiration import (
    calculate_expires_at,
    find_expired_keys,
    is_expired,
    ttl_seconds,
)

from app.core.hash_table import HashTable
from app.core.lock import StoreLock, create_store_lock


class Store:
    """In-memory key/value store with TTL metadata and coarse locking."""

    def __init__(self, clock: Optional[Callable[[], float]] = None) -> None:
        self.data_map: HashTable[str] = HashTable()
        self.expire_map: HashTable[float] = HashTable()
        self.lock: StoreLock = create_store_lock()
        self._clock = clock if clock is not None else time.time

    def get(self, key: str) -> Tuple[bool, Optional[str]]:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            if key not in self.data_map:
                return False, None
            return True, self.data_map[key]

    def set(self, key: str, value: str) -> str:
        with self.lock:
            self.data_map[key] = value
            self.expire_map.pop(key, None)
            return "OK"

    def delete(self, key: str) -> int:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            return int(self._delete_key_unlocked(key))

    def expire(self, key: str, seconds: int) -> int:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            if key not in self.data_map:
                return 0
            if seconds <= 0:
                self._delete_key_unlocked(key)
                return 1
            self.expire_map[key] = calculate_expires_at(now, seconds)
            return 1

    def expireat(self, key: str, expires_at: float) -> int:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            if key not in self.data_map:
                return 0
            if is_expired(expires_at, now):
                self._delete_key_unlocked(key)
                return 1
            self.expire_map[key] = expires_at
            return 1

    def ttl(self, key: str) -> int:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            if key not in self.data_map:
                return -2
            expires_at = self.expire_map.get(key)
            if expires_at is None:
                return -1
            return ttl_seconds(expires_at, now)

    def persist(self, key: str) -> int:
        with self.lock:
            now = self._clock()
            self._purge_expired_key_unlocked(key, now)
            if key not in self.data_map:
                return 0
            if key not in self.expire_map:
                return 0
            self.expire_map.pop(key, None)
            return 1

    def sweep_expired(self) -> int:
        with self.lock:
            now = self._clock()
            expired_keys = find_expired_keys(self.expire_map, now)
            for key in expired_keys:
                self._delete_key_unlocked(key)
            return len(expired_keys)

    def _purge_expired_key_unlocked(self, key: str, now: float) -> bool:
        expires_at = self.expire_map.get(key)
        if expires_at is None:
            return False
        if not is_expired(expires_at, now):
            return False
        self._delete_key_unlocked(key)
        return True

    def _delete_key_unlocked(self, key: str) -> bool:
        existed = key in self.data_map
        self.data_map.pop(key, None)
        self.expire_map.pop(key, None)
        return existed
