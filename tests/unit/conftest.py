"""Shared unit test configuration.

Wraps StigmergicAgent._setup_subscriptions to ensure mock event buses
have async-compatible psubscribe/subscribe before the real method runs.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _ensure_mock_event_bus_async_methods(monkeypatch):
    """Ensure MagicMock event buses support psubscribe/subscribe as AsyncMock.

    Phase 1 of the stigmergic fix changed subscribe('findings:*') to
    psubscribe('findings:*'). Many test fixtures only set publish=AsyncMock()
    on their MagicMock event bus. This wraps _setup_subscriptions to patch
    the mock just-in-time before the real method executes.
    """
    from cyberred.agents.base import StigmergicAgent

    try:
        original = StigmergicAgent._setup_subscriptions
    except AttributeError:
        # Some tests monkeypatch/mock the swarms dependency which can cause
        # StigmergicAgent to be a spec'd Mock rather than the real class.
        # In that case there's nothing to wrap.
        return

    async def _patched_setup(self):
        bus = self.event_bus
        if isinstance(bus, MagicMock):
            if not isinstance(getattr(bus, "psubscribe", None), AsyncMock):
                bus.psubscribe = AsyncMock()
            if not isinstance(getattr(bus, "subscribe", None), AsyncMock):
                bus.subscribe = AsyncMock()
        return await original(self)

    monkeypatch.setattr(StigmergicAgent, "_setup_subscriptions", _patched_setup)
