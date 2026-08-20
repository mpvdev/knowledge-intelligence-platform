"""Bounded, thread-safe LRU cache shared by the embedding and chunk caches."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock


class LruCache[T]:
    def __init__(self, maximum_entries: int) -> None:
        if maximum_entries < 1:
            raise ValueError("An LRU cache needs room for at least one entry.")
        self.maximum_entries = maximum_entries
        self._entries: OrderedDict[str, T] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> T | None:
        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
            return value

    def put(self, key: str, value: T) -> None:
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self.maximum_entries:
                self._entries.popitem(last=False)
