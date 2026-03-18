"""Store-level coarse lock helpers."""

from _thread import LockType
import threading


def create_store_lock() -> LockType:
    """Create the single coarse lock shared by store operations."""

    return threading.Lock()
