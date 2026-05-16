"""Small unit tests for the in-process cache helpers (task 10 groundwork)."""

from __future__ import annotations

from plugin_market_backend.caching import aget_or_set, cache_bus


async def test_aget_or_set_hits_cache_until_invalidated() -> None:
    calls = 0

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return f"value-{calls}"

    first = await aget_or_set(("home", "viewer-a"), 60, loader)
    second = await aget_or_set(("home", "viewer-a"), 60, loader)
    cache_bus.invalidate("home")
    third = await aget_or_set(("home", "viewer-a"), 60, loader)

    assert first == "value-1"
    assert second == "value-1"
    assert third == "value-2"