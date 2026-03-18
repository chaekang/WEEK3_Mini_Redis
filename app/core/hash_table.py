"""Open-addressing hash table for store internals."""

from typing import (
    Callable,
    Generic,
    Iterator,
    MutableMapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
    overload,
)

_FNV_OFFSET_BASIS_64 = 14695981039346656037
_FNV_PRIME_64 = 1099511628211
_HASH_MASK_64 = 0xFFFFFFFFFFFFFFFF
_MAX_LOAD_FACTOR = 0.7
_MIN_CAPACITY = 8

V = TypeVar("V")
DefaultT = TypeVar("DefaultT")

_EMPTY = object()
_TOMBSTONE = object()
_MISSING = object()


def fnv1a_64(key: str) -> int:
    """Hash a string key with FNV-1a 64-bit over UTF-8 bytes."""

    hash_value = _FNV_OFFSET_BASIS_64
    for byte in key.encode("utf-8"):
        hash_value ^= byte
        hash_value = (hash_value * _FNV_PRIME_64) & _HASH_MASK_64
    return hash_value


class _Entry(Generic[V]):
    __slots__ = ("key", "value")

    def __init__(self, key: str, value: V) -> None:
        self.key = key
        self.value = value


class HashTable(MutableMapping[str, V], Generic[V]):
    """Mutable mapping backed by open addressing and linear probing."""

    def __init__(self, hash_fn: Optional[Callable[[str], int]] = None) -> None:
        self._hash_fn = hash_fn if hash_fn is not None else fnv1a_64
        self._capacity = _MIN_CAPACITY
        self._slots = [_EMPTY] * self._capacity
        self._size = 0
        self._tombstones = 0

    @property
    def capacity(self) -> int:
        """Return the current slot capacity."""

        return self._capacity

    def __len__(self) -> int:
        return self._size

    def __iter__(self) -> Iterator[str]:
        for slot in self._slots:
            if isinstance(slot, _Entry):
                yield slot.key

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._find_existing_index(key) is not None

    def __getitem__(self, key: str) -> V:
        index = self._find_existing_index(key)
        if index is None:
            raise KeyError(key)
        entry = cast(_Entry[V], self._slots[index])
        return entry.value

    def __setitem__(self, key: str, value: V) -> None:
        index, found = self._find_slot(key)
        if found:
            entry = cast(_Entry[V], self._slots[index])
            entry.value = value
            return

        target_slot = self._slots[index]
        projected_used_slots = (
            self._used_slots if target_slot is _TOMBSTONE else self._used_slots + 1
        )
        if projected_used_slots / self._capacity > _MAX_LOAD_FACTOR:
            self._resize(self._capacity * 2)
            index, found = self._find_slot(key)
            if found:
                entry = cast(_Entry[V], self._slots[index])
                entry.value = value
                return
            target_slot = self._slots[index]

        self._slots[index] = _Entry(key, value)
        self._size += 1
        if target_slot is _TOMBSTONE:
            self._tombstones -= 1

    def __delitem__(self, key: str) -> None:
        index = self._find_existing_index(key)
        if index is None:
            raise KeyError(key)
        self._delete_at(index)

    @overload
    def get(self, key: str) -> Optional[V]: ...

    @overload
    def get(self, key: str, default: DefaultT) -> Union[V, DefaultT]: ...

    def get(self, key: str, default: object = None) -> object:
        index = self._find_existing_index(key)
        if index is None:
            return default
        entry = cast(_Entry[V], self._slots[index])
        return entry.value

    @overload
    def pop(self, key: str) -> V: ...

    @overload
    def pop(self, key: str, default: DefaultT) -> Union[V, DefaultT]: ...

    def pop(self, key: str, default: object = _MISSING) -> object:
        index = self._find_existing_index(key)
        if index is None:
            if default is _MISSING:
                raise KeyError(key)
            return default
        entry = cast(_Entry[V], self._slots[index])
        self._delete_at(index)
        return entry.value

    @property
    def _used_slots(self) -> int:
        return self._size + self._tombstones

    def _delete_at(self, index: int) -> None:
        self._slots[index] = _TOMBSTONE
        self._size -= 1
        self._tombstones += 1

    def _find_existing_index(self, key: str) -> Optional[int]:
        start = self._hash_fn(key) % self._capacity
        for offset in range(self._capacity):
            index = (start + offset) % self._capacity
            slot = self._slots[index]
            if slot is _EMPTY:
                return None
            if slot is _TOMBSTONE:
                continue
            entry = cast(_Entry[V], slot)
            if entry.key == key:
                return index
        return None

    def _find_slot(self, key: str) -> Tuple[int, bool]:
        first_tombstone = None
        start = self._hash_fn(key) % self._capacity

        for offset in range(self._capacity):
            index = (start + offset) % self._capacity
            slot = self._slots[index]
            if slot is _EMPTY:
                if first_tombstone is not None:
                    return first_tombstone, False
                return index, False
            if slot is _TOMBSTONE:
                if first_tombstone is None:
                    first_tombstone = index
                continue
            entry = cast(_Entry[V], slot)
            if entry.key == key:
                return index, True

        if first_tombstone is not None:
            return first_tombstone, False
        raise RuntimeError("hash table is full")

    def _resize(self, new_capacity: int) -> None:
        old_slots = self._slots
        self._capacity = max(_MIN_CAPACITY, new_capacity)
        self._slots = [_EMPTY] * self._capacity
        self._size = 0
        self._tombstones = 0

        for slot in old_slots:
            if isinstance(slot, _Entry):
                self[slot.key] = slot.value
