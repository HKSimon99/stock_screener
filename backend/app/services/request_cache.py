from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    expires_at: float
    value: T


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, _Entry[T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T) -> T:
        with self._lock:
            self._entries[key] = _Entry(expires_at=monotonic() + self._ttl_seconds, value=value)
        return value

