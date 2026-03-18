import threading
from typing import List, Optional, Tuple

from app.core.hash_table import HashTable
from app.core.store import Store


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_set_get_and_delete_round_trip() -> None:
    store = Store()

    assert isinstance(store.data_map, HashTable)
    assert isinstance(store.expire_map, HashTable)
    assert store.set("alpha", "one") == "OK"
    assert store.get("alpha") == (True, "one")
    assert store.delete("alpha") == 1
    assert store.get("alpha") == (False, None)
    assert store.delete("alpha") == 0


def test_set_overwrite_clears_existing_ttl() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("session", "v1")
    assert store.expire("session", 30) == 1
    assert "session" in store.expire_map

    assert store.set("session", "v2") == "OK"
    assert store.get("session") == (True, "v2")
    assert store.ttl("session") == -1
    assert "session" not in store.expire_map


def test_store_uses_hash_table_for_both_internal_maps() -> None:
    store = Store()

    assert isinstance(store.data_map, HashTable)
    assert isinstance(store.expire_map, HashTable)


def test_expire_non_positive_seconds_deletes_immediately() -> None:
    store = Store()

    store.set("temp", "value")
    assert store.expire("temp", 0) == 1
    assert store.get("temp") == (False, None)
    assert store.delete("temp") == 0
    assert store.expire("missing", -5) == 0


def test_persist_removes_ttl_but_keeps_value() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("profile", "hello")
    assert store.expire("profile", 15) == 1

    assert store.persist("profile") == 1
    assert store.get("profile") == (True, "hello")
    assert store.ttl("profile") == -1
    assert store.persist("profile") == 0
    assert store.persist("missing") == 0


def test_store_operations_serialize_on_the_shared_coarse_lock() -> None:
    store = Store()
    store.set("counter", "1")

    started = threading.Event()
    completed = threading.Event()
    results: List[Tuple[bool, Optional[str]]] = []

    def worker() -> None:
        started.set()
        results.append(store.get("counter"))
        completed.set()

    with store.lock:
        thread = threading.Thread(target=worker)
        thread.start()

        assert started.wait(timeout=0.5)
        assert not completed.wait(timeout=0.05)

    assert completed.wait(timeout=0.5)
    thread.join(timeout=0.5)
    assert not thread.is_alive()
    assert results == [(True, "1")]
