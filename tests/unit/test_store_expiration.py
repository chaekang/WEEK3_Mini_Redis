from app.core.expiration import (
    calculate_expires_at,
    find_expired_keys,
    is_expired,
    ttl_seconds,
)
from app.core.hash_table import HashTable
from app.core.store import Store


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_expiration_helpers_use_absolute_timestamps() -> None:
    expire_map = HashTable[float]()
    expire_map["a"] = 100.0
    expire_map["b"] = 110.0
    expire_map["c"] = 95.0

    assert calculate_expires_at(100.0, 10) == 110.0
    assert is_expired(100.0, 100.0)
    assert not is_expired(110.0, 100.0)
    assert ttl_seconds(110.0, 103.2) == 6
    assert sorted(find_expired_keys(expire_map, 100.0)) == ["a", "c"]


def test_expire_stores_absolute_time_and_ttl_counts_down() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("token", "abc")
    assert store.expire("token", 10) == 1
    assert store.expire_map["token"] == 110.0
    assert store.ttl("token") == 10

    clock.advance(3.2)
    assert store.ttl("token") == 6


def test_ttl_reports_missing_and_no_expiration_states() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    assert store.ttl("missing") == -2

    store.set("plain", "value")
    assert store.ttl("plain") == -1


def test_get_lazy_expiration_returns_miss_and_cleans_maps() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("lazy", "value")
    store.expire("lazy", 5)

    clock.advance(5)
    assert store.get("lazy") == (False, None)
    assert "lazy" not in store.data_map
    assert "lazy" not in store.expire_map


def test_ttl_lazy_expiration_returns_missing_after_expiry() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("soon", "gone")
    store.expire("soon", 1)

    clock.advance(1)
    assert store.ttl("soon") == -2
    assert "soon" not in store.data_map
    assert "soon" not in store.expire_map


def test_sweep_expired_removes_only_expired_keys() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("a", "one")
    store.set("b", "two")
    store.set("c", "three")

    store.expire("a", 5)
    store.expire("b", 10)

    clock.advance(6)
    assert store.sweep_expired() == 1
    assert store.get("a") == (False, None)
    assert store.get("b") == (True, "two")
    assert store.get("c") == (True, "three")


def test_expireat_restores_future_absolute_timestamp() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("future", "value")

    assert store.expireat("future", 110.0) == 1
    assert store.expire_map["future"] == 110.0
    assert store.ttl("future") == 10


def test_expireat_immediately_deletes_when_timestamp_is_past() -> None:
    clock = FakeClock()
    store = Store(clock=clock)

    store.set("past", "value")

    assert store.expireat("past", 99.0) == 1
    assert store.get("past") == (False, None)
    assert "past" not in store.expire_map
