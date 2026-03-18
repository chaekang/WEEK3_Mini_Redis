import random
import time

from app.core.hash_table import HashTable


def constant_hash(_: str) -> int:
    return 1


def test_hash_table_handles_collisions_with_linear_probing() -> None:
    table = HashTable[str](hash_fn=constant_hash)

    table["alpha"] = "one"
    table["beta"] = "two"
    table["gamma"] = "three"

    assert table["alpha"] == "one"
    assert table["beta"] == "two"
    assert table["gamma"] == "three"
    assert list(table) == ["alpha", "beta", "gamma"]


def test_hash_table_keeps_probe_chain_after_tombstone_delete() -> None:
    table = HashTable[str](hash_fn=constant_hash)

    table["alpha"] = "one"
    table["beta"] = "two"
    table["gamma"] = "three"

    assert table.pop("beta") == "two"
    assert "beta" not in table
    assert table["gamma"] == "three"


def test_hash_table_reuses_tombstone_slots() -> None:
    table = HashTable[str](hash_fn=constant_hash)

    table["alpha"] = "one"
    table["beta"] = "two"
    table["gamma"] = "three"
    del table["beta"]
    table["delta"] = "four"

    assert table["alpha"] == "one"
    assert table["gamma"] == "three"
    assert table["delta"] == "four"
    assert len(table) == 3


def test_hash_table_resizes_and_preserves_entries() -> None:
    table = HashTable[str]()

    for index in range(6):
        table["key-{0}".format(index)] = "value-{0}".format(index)

    assert table.capacity == 16
    for index in range(6):
        assert table["key-{0}".format(index)] == "value-{0}".format(index)


def test_hash_table_matches_dict_under_mixed_operations() -> None:
    rng = random.Random(42)
    table = HashTable[str]()
    model = {}
    keys = ["key-{0}".format(index) for index in range(256)]

    for step in range(20000):
        key = rng.choice(keys)
        operation = rng.randrange(4)

        if operation in (0, 1):
            value = "value-{0}".format(step)
            table[key] = value
            model[key] = value
        elif operation == 2:
            default = object()
            assert table.pop(key, default) is model.pop(key, default)
        else:
            assert table.get(key) == model.get(key)

        if step % 250 == 0:
            assert len(table) == len(model)
            sample_keys = rng.sample(keys, 8)
            for sample_key in sample_keys:
                assert table.get(sample_key) == model.get(sample_key)

    assert len(table) == len(model)
    assert dict(table.items()) == model


def test_hash_table_large_workload_stays_within_loose_time_budget() -> None:
    table = HashTable[str]()
    total_keys = 10000

    started_at = time.perf_counter()
    for index in range(total_keys):
        key = "key-{0}".format(index)
        table[key] = "value-{0}".format(index)

    for index in range(total_keys):
        key = "key-{0}".format(index)
        assert table[key] == "value-{0}".format(index)

    for index in range(total_keys // 2):
        key = "key-{0}".format(index)
        assert table.pop(key) == "value-{0}".format(index)

    elapsed = time.perf_counter() - started_at

    assert len(table) == total_keys // 2
    assert elapsed < 3.0
