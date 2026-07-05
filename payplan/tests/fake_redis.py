"""In-memory Redis fake for unit tests. Mimics the subset of redis-py used by nomba_auth.

Supports:
- get(key) -> bytes|None
- set(key, value, ex=..., nx=...) -> True/False (False only when nx=True and key exists)
- delete(*keys) -> count of keys removed
- ttl(key) -> remaining seconds
- exists(key) -> bool
"""
import time


class FakeRedis:
    def __init__(self):
        self._store = {}

    def _now(self):
        return time.time()

    def _expired(self, entry):
        expires_at, _ = entry
        return expires_at is not None and self._now() >= expires_at

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._expired(entry):
            self._store.pop(key, None)
            return None
        return entry[1]

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self._store and not self._expired(self._store[key]):
            return False
        expires_at = self._now() + ex if ex is not None else None
        self._store[key] = (expires_at, value)
        return True

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self._store:
                self._store.pop(k, None)
                count += 1
        return count

    def ttl(self, key):
        entry = self._store.get(key)
        if entry is None:
            return -2
        if self._expired(entry):
            return -2
        expires_at, _ = entry
        if expires_at is None:
            return -1
        return int(expires_at - self._now())

    def exists(self, key):
        return 1 if self.get(key) is not None else 0
