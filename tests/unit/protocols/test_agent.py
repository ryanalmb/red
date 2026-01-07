"""Unit tests for AgentProtocol.

Tests verify:
1. Compliant classes pass isinstance() checks
2. Non-compliant classes fail isinstance() checks
3. Method signatures match expected types
4. shutdown() method presence and signature

Note: typing.Protocol with @runtime_checkable only checks method
existence, not full signature compliance at runtime. Full signature
checks are performed by mypy at static analysis time.
"""

from __future__ import annotations

from typing import List

import pytest

from cyberred.core.models import AgentAction
from cyberred.protocols import AgentProtocol


class CompliantAgent:
    """A minimal compliant implementation for testing.
    
    Implements all required AgentProtocol methods with correct signatures.
    """
    
    def __init__(self) -> None:
        self._id = "a47bc10b-58cc-4372-a567-0e02b2c3d480"
        self._status = "idle"
        self._context: List[str] = []
    
    async def execute(self, task: str) -> AgentAction:
        """Execute a task and return the resulting action."""
        return AgentAction(
            id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
            agent_id=self._id,
            action_type="test",
            target="127.0.0.1",
            timestamp="2026-01-01T00:00:00Z",
            decision_context=self._context,
        )
    
    async def reason(self, context: List[str]) -> str:
        """Generate reasoning based on context."""
        return f"Reasoning about {len(context)} signals"
    
    def get_id(self) -> str:
        """Return agent identifier."""
        return self._id
    
    def get_status(self) -> str:
        """Return current status."""
        return self._status
    
    def get_decision_context(self) -> List[str]:
        """Return stigmergic influences."""
        return self._context
    
    async def shutdown(self) -> None:
        """Cleanup resources."""
        self._status = "shutdown"


class PartialAgent:
    """An agent missing some required methods."""
    
    def get_id(self) -> str:
        return "partial-agent"
    
    # Missing: execute, reason, get_status, get_decision_context, shutdown


class NonCompliantClass:
    """A class with no agent methods at all."""
    
    def do_something(self) -> str:
        return "something"


# -----------------------------------------------------------------------------
# Protocol Compliance Tests
# -----------------------------------------------------------------------------

def test_compliant_agent_passes_isinstance() -> None:
    """Verify that a fully compliant agent passes isinstance check."""
    agent = CompliantAgent()
    assert isinstance(agent, AgentProtocol)


def test_non_compliant_class_fails_isinstance() -> None:
    """Verify that a non-compliant class fails isinstance check."""
    obj = NonCompliantClass()
    assert not isinstance(obj, AgentProtocol)


def test_partial_agent_fails_isinstance() -> None:
    """Verify that a partially compliant class fails isinstance check."""
    agent = PartialAgent()
    assert not isinstance(agent, AgentProtocol)


# -----------------------------------------------------------------------------
# Method Signature Tests
# -----------------------------------------------------------------------------

def test_execute_method_exists() -> None:
    """Verify execute method exists with correct callable type."""
    agent = CompliantAgent()
    assert hasattr(agent, "execute")
    assert callable(agent.execute)


def test_reason_method_exists() -> None:
    """Verify reason method exists with correct callable type."""
    agent = CompliantAgent()
    assert hasattr(agent, "reason")
    assert callable(agent.reason)


def test_get_id_method_exists() -> None:
    """Verify get_id method exists and returns string."""
    agent = CompliantAgent()
    assert hasattr(agent, "get_id")
    result = agent.get_id()
    assert isinstance(result, str)


def test_get_status_method_exists() -> None:
    """Verify get_status method exists and returns string."""
    agent = CompliantAgent()
    assert hasattr(agent, "get_status")
    result = agent.get_status()
    assert isinstance(result, str)


def test_get_decision_context_method_exists() -> None:
    """Verify get_decision_context method exists and returns list."""
    agent = CompliantAgent()
    assert hasattr(agent, "get_decision_context")
    result = agent.get_decision_context()
    assert isinstance(result, list)


def test_shutdown_method_exists() -> None:
    """Verify shutdown method exists with correct callable type."""
    agent = CompliantAgent()
    assert hasattr(agent, "shutdown")
    assert callable(agent.shutdown)


# -----------------------------------------------------------------------------
# Async Method Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_returns_agent_action() -> None:
    """Verify execute returns an AgentAction instance."""
    agent = CompliantAgent()
    result = await agent.execute("test task")
    assert isinstance(result, AgentAction)


@pytest.mark.asyncio
async def test_reason_returns_string() -> None:
    """Verify reason returns a string."""
    agent = CompliantAgent()
    result = await agent.reason(["signal-1", "signal-2"])
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_shutdown_completes_successfully() -> None:
    """Verify shutdown can be awaited and updates status."""
    agent = CompliantAgent()
    assert agent.get_status() == "idle"
    await agent.shutdown()
    assert agent.get_status() == "shutdown"
