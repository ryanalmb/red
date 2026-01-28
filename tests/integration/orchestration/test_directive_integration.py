"""Integration tests for orchestration/directive.py - Mission Directive Interpreter.

Story 8.7: Natural Language Mission Directive.

These tests verify the DirectiveInterpreter works correctly with real
(mocked) LLM responses and actual event bus integration patterns.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.orchestration.directive import (
    DirectiveInterpreter,
    DirectiveResult,
    DirectiveType,
    MissionDirective,
    ParsedDirective,
)
from cyberred.llm.ensemble import (
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    ModelResponse,
)
from cyberred.core.events import EventBus
from cyberred.core.exceptions import ScopeViolationError


class TestDirectiveIntegrationFlows:
    """Integration tests for directive interpretation flows."""

    @pytest.fixture
    def mock_ensemble(self) -> MagicMock:
        """Create a mock DirectorEnsemble."""
        ensemble = MagicMock(spec=DirectorEnsemble)
        return ensemble

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock EventBus with realistic behavior."""
        event_bus = MagicMock(spec=EventBus)
        event_bus.audit = AsyncMock(return_value="msg-001")
        event_bus.publish = AsyncMock(return_value=3)  # 3 subscribers
        return event_bus

    @pytest.fixture
    def mock_scope_validator(self) -> MagicMock:
        """Create a mock ScopeValidator."""
        from cyberred.tools.scope import ScopeValidator
        validator = MagicMock(spec=ScopeValidator)
        validator.validate = MagicMock(return_value=True)
        return validator

    @pytest.mark.asyncio
    async def test_full_focus_directive_flow(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test complete flow for focus directive: interpret -> audit -> publish."""
        # Setup realistic LLM response
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web application vulnerabilities", "SQL injection", "XSS"],
                "exclusions": ["network infrastructure"],
                "priorities": ["critical vulnerabilities first"],
                "pivot_reason": None,
                "confidence": 0.92,
            }),
            latency_ms=1200,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web application vulnerabilities, especially SQL injection and XSS. Skip network infrastructure.",
            engagement_id="eng-integration-001",
            operator_id="operator-1",
        )
        
        result = await interpreter.interpret(directive)
        
        # Verify successful interpretation
        assert result.success is True
        assert result.parsed is not None
        assert result.parsed.directive_type == DirectiveType.FOCUS
        assert "web application vulnerabilities" in result.parsed.focus_areas
        assert result.parsed.confidence == 0.92
        
        # Verify audit was logged with correct structure
        mock_event_bus.audit.assert_called_once()
        audit_event = mock_event_bus.audit.call_args[0][0]
        assert audit_event["type"] == "mission_directive"
        assert audit_event["engagement_id"] == "eng-integration-001"
        assert audit_event["operator_id"] == "operator-1"
        assert audit_event["success"] is True
        assert audit_event["parsed"]["directive_type"] == "focus"
        
        # Verify strategy was published
        mock_event_bus.publish.assert_called_once()
        channel, payload = mock_event_bus.publish.call_args[0]
        assert channel == "strategies:eng-integration-001"
        assert "objectives" in payload
        assert "actions" in payload

    @pytest.mark.asyncio
    async def test_exclude_directive_with_strategy_update(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test exclude directive creates correct strategy update."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "exclude",
                "focus_areas": [],
                "exclusions": ["DNS servers", "mail servers", "production database"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.88,
            }),
            latency_ms=900,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Skip DNS servers, mail servers, and production database",
            engagement_id="eng-integration-002",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.EXCLUDE
        assert len(result.parsed.exclusions) == 3
        
        # Verify strategy has avoid_list populated
        assert result.strategy_update is not None
        assert "DNS servers" in result.strategy_update.avoid_list

    @pytest.mark.asyncio
    async def test_pivot_directive_with_reason(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test pivot directive includes reason in strategy."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "pivot",
                "focus_areas": ["internal network", "Active Directory"],
                "exclusions": ["web applications"],
                "priorities": ["lateral movement", "privilege escalation"],
                "pivot_reason": "External perimeter fully compromised, initial foothold established",
                "confidence": 0.95,
            }),
            latency_ms=1100,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Pivot to internal network and AD, we have initial access",
            engagement_id="eng-integration-003",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.PIVOT
        assert result.parsed.pivot_reason is not None
        assert "compromised" in result.parsed.pivot_reason.lower()
        
        # Strategy rationale should include pivot reason
        assert "pivot" in result.strategy_update.rationale.lower() or "Pivot" in result.strategy_update.rationale

    @pytest.mark.asyncio
    async def test_scope_violation_prevents_strategy_publication(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
        mock_scope_validator: MagicMock,
    ) -> None:
        """Test that scope violations block strategy publication."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["10.0.0.0/8"],  # Out of scope network
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=800,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        # Configure scope validator to reject the target
        mock_scope_validator.validate = MagicMock(
            side_effect=ScopeViolationError(
                target="10.0.0.0/8",
                command="",
                scope_rule="ip_out_of_scope",
                message="IP 10.0.0.0/8 not in allowed networks",
            )
        )
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
            scope_validator=mock_scope_validator,
        )
        
        directive = MissionDirective(
            raw_text="Focus on 10.0.0.0/8 network",
            engagement_id="eng-integration-004",
        )
        
        result = await interpreter.interpret(directive)
        
        # Should fail with scope violation
        assert result.success is False
        assert result.scope_violation is True
        assert "scope" in result.error_message.lower()
        
        # Audit should still be logged (for compliance)
        mock_event_bus.audit.assert_called_once()
        audit_event = mock_event_bus.audit.call_args[0][0]
        assert audit_event["success"] is False
        assert audit_event["scope_violation"] is True
        
        # Strategy should NOT be published
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_abort_directive_creates_immediate_stop_actions(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test abort directive creates immediate stop actions."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "abort",
                "focus_areas": [],
                "exclusions": ["brute force attacks", "DoS testing"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.98,
            }),
            latency_ms=600,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="ABORT all brute force attacks and DoS testing immediately!",
            engagement_id="eng-integration-005",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.ABORT
        
        # Strategy should have abort objectives
        assert any("Abort" in obj for obj in result.strategy_update.objectives)
        assert any("stop" in action.lower() for action in result.strategy_update.actions)

    @pytest.mark.asyncio
    async def test_multiple_directives_in_sequence(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test multiple directives processed in sequence."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        # First directive: Focus
        mock_ensemble.query_model = AsyncMock(return_value=ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web apps"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=500,
            success=True,
        ))
        
        result1 = await interpreter.interpret(MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-seq-001",
        ))
        assert result1.success is True
        
        # Second directive: Exclude
        mock_ensemble.query_model = AsyncMock(return_value=ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "exclude",
                "focus_areas": [],
                "exclusions": ["login pages"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.85,
            }),
            latency_ms=500,
            success=True,
        ))
        
        result2 = await interpreter.interpret(MissionDirective(
            raw_text="Skip login pages",
            engagement_id="eng-seq-001",
        ))
        assert result2.success is True
        
        # Both should have been audited and published
        assert mock_event_bus.audit.call_count == 2
        assert mock_event_bus.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_strategy_metadata_includes_directive_info(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that published strategy includes directive metadata."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["API endpoints"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.87,
            }),
            latency_ms=700,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on API endpoints",
            engagement_id="eng-metadata-001",
            operator_id="senior-operator",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        
        # Check metadata includes directive info
        assert "directive" in result.strategy_update.metadata
        assert result.strategy_update.metadata["directive"]["raw_text"] == "Focus on API endpoints"
        assert result.strategy_update.metadata["directive"]["operator_id"] == "senior-operator"
