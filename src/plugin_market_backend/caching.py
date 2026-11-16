"""为市场聚合接口提供轻量级进程内缓存。

任务 10 使用基于 ``cachetools.TTLCache`` 的通用异步加载工具，
以及按 ``home``、``announcements_active`` 等逻辑命名空间
组织的轻量级缓存失效总线。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from typing import Any

from cachetools import TTLCache


CacheKey = Hashable | tuple[Hashable, ...]
AsyncLoader = Callable[[], Awaitable[Any]]

_caches_by_ttl: dict[int, TTLCache] = {}
_locks: dict[tuple[int, CacheKey], asyncio.Lock] = {}
_registry_lock = asyncio.Lock()


def _cache_for_ttl(ttl: int) -> TTLCache:
    cache = _caches_by_ttl.get(ttl)
    if cache is None:
        cache = TTLCache(maxsize=512, ttl=ttl)
        _caches_by_ttl[ttl] = cache
    return cache


async def aget_or_set(key: CacheKey, ttl: int, loader: AsyncLoader) -> Any:
    """返回 ``key`` 对应的缓存值，未命中时通过 ``loader`` 加载。"""
    cache = _cache_for_ttl(int(ttl))
    if key in cache:
        return cache[key]

    lock_key = (int(ttl), key)
    async with _registry_lock:
        lock = _locks.setdefault(lock_key, asyncio.Lock())

    async with lock:
        if key in cache:
            return cache[key]
        value = await loader()
        cache[key] = value
        return value


def _matches_namespace(key: CacheKey, namespace: str) -> bool:
    if isinstance(key, tuple) and key:
        return str(key[0]) == namespace
    return str(key) == namespace or str(key).startswith(f"{namespace}:")


class CacheBus:
    """按命名空间同步清除缓存键的辅助工具。"""

    def invalidate(self, namespace: str) -> None:
        for cache in _caches_by_ttl.values():
            doomed = [key for key in cache.keys() if _matches_namespace(key, namespace)]
            for key in doomed:
                cache.pop(key, None)


cache_bus = CacheBus()