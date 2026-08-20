"""The shared bounded LRU used by embeddings and the vector store."""

from __future__ import annotations

import pytest

from app.cache import LruCache


def test_evicts_least_recently_used() -> None:
    cache: LruCache[int] = LruCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")  # "a" is now the most recently used
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_missing_key_returns_none() -> None:
    cache: LruCache[int] = LruCache(1)
    assert cache.get("absent") is None


def test_overwrite_does_not_grow_the_cache() -> None:
    cache: LruCache[int] = LruCache(1)
    cache.put("a", 1)
    cache.put("a", 2)
    assert cache.get("a") == 2


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="at least one entry"):
        LruCache(0)
