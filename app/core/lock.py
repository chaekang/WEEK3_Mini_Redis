"""Store-level coarse lock helpers."""

import threading
from types import TracebackType
from typing import Optional, Protocol


class StoreLock(Protocol):
    """Minimal lock contract used by the store."""

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool: ...

    def release(self) -> None: ...

    def __enter__(self) -> bool: ...

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None: ...


def create_store_lock() -> StoreLock:
    """Create the single coarse lock shared by store operations."""

    return threading.Lock()
