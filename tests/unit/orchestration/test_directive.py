"""Unit tests for orchestration/directive.py - Mission Directive Interpreter.

Story 8.7: Natural Language Mission Directive.

Tests the DirectiveInterpreter, MissionDirective, ParsedDirective, and
DirectiveResult classes for natural language directive processing.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
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
    SynthesizedStrategy,
)
from cyberred.core.events import EventBus


# =============================================================================
# MissionDirective Dataclass Tests
# =============================================================================


class TestMissionDirective:
    """Tests for MissionDirective dataclass validation."""

    def test_valid_directive_creation(self) -> None:
        """Test creating a valid MissionDirective."""
        directive = MissionDirective(
            raw_text="Focus on web application vulnerabilities",
            engagement_id="eng-001",
        )
        assert directive.raw_text == "Focus on web application vulnerabilities"
        assert directive.engagement_id == "eng-001"
        assert directive.timestamp > 0
        assert directive.operator_id is None

    def test_directive_with_all_fields(self) -> None:
        """Test creating directive with all optional fields."""
        ts = time.time()
        directive = MissionDirective(
            raw_text="Skip network infrastructure",
            engagement_id="eng-002",
            timestamp=ts,
            operator_id="operator-1",
        )
        assert directive.timestamp == ts
        assert directive.operator_id == "operator-1"

    def test_empty_raw_text_raises(self) -> None:
        """Test that empty raw_text raises ValueError."""
        with pytest.raises(ValueError, match="raw_text cannot be empty"):
            MissionDirective(raw_text="", engagement_id="eng-001")

    def test_whitespace_raw_text_raises(self) -> None:
        """Test that whitespace-only raw_text raises ValueError."""
        with pytest.raises(ValueError, match="raw_text cannot be empty"):
            MissionDirective(raw_text="   ", engagement_id="eng-001")

    def test_empty_engagement_id_raises(self) -> None:
        """Test that empty engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            MissionDirective(raw_text="Focus on web", engagement_id="")

    def test_whitespace_engagement_id_raises(self) -> None:
        """Test that whitespace-only engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            MissionDirective(raw_text="Focus on web", engagement_id="  \t  ")


# =============================================================================
# ParsedDirective Dataclass Tests
# =============================================================================


class TestParsedDirective:
    """Tests for ParsedDirective dataclass."""

    def test_minimal_parsed_directive(self) -> None:
        """Test creating a minimal ParsedDirective."""
        parsed = ParsedDirective(directive_type=DirectiveType.FOCUS)
        assert parsed.directive_type == DirectiveType.FOCUS
        assert parsed.focus_areas == []
        assert parsed.exclusions == []
        assert parsed.priorities == []
        assert parsed.pivot_reason is None
        assert parsed.confidence == 0.0
        assert parsed.raw_interpretation == ""

    def test_full_parsed_directive(self) -> None:
        """Test creating a fully populated ParsedDirective."""
        parsed = ParsedDirective(
            directive_type=DirectiveType.PIVOT,
            focus_areas=["web apps", "SQL injection"],
            exclusions=["network", "DNS"],
            priorities=["critical", "high"],
            pivot_reason="Initial approach blocked by WAF",
            confidence=0.85,
            raw_interpretation="Parsed focus on web applications...",
        )
        assert parsed.directive_type == DirectiveType.PIVOT
        assert parsed.focus_areas == ["web apps", "SQL injection"]
        assert parsed.exclusions == ["network", "DNS"]
        assert parsed.priorities == ["critical", "high"]
        assert parsed.pivot_reason == "Initial approach blocked by WAF"
        assert parsed.confidence == 0.85

    def test_confidence_clamped_above_one(self) -> None:
        """Test that confidence > 1.0 is clamped to 1.0."""
        parsed = ParsedDirective(
            directive_type=DirectiveType.FOCUS,
            confidence=1.5,  # Invalid - above 1.0
        )
        assert parsed.confidence == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        """Test that confidence < 0.0 is clamped to 0.0."""
        parsed = ParsedDirective(
            directive_type=DirectiveType.FOCUS,
            confidence=-0.5,  # Invalid - below 0.0
        )
        assert parsed.confidence == 0.0

    def test_confidence_valid_range_preserved(self) -> None:
        """Test that valid confidence values are preserved."""
        parsed = ParsedDirective(
            directive_type=DirectiveType.FOCUS,
            confidence=0.75,
        )
        assert parsed.confidence == 0.75


# =============================================================================
# DirectiveType Enum Tests
# =============================================================================


class TestDirectiveType:
    """Tests for DirectiveType enum."""

    def test_all_directive_types(self) -> None:
        """Test all directive type values."""
        assert DirectiveType.FOCUS.value == "focus"
        assert DirectiveType.EXCLUDE.value == "exclude"
        assert DirectiveType.PRIORITIZE.value == "prioritize"
        assert DirectiveType.PIVOT.value == "pivot"
        assert DirectiveType.ABORT.value == "abort"

    def test_directive_type_from_string(self) -> None:
        """Test creating DirectiveType from string value."""
        assert DirectiveType("focus") == DirectiveType.FOCUS
        assert DirectiveType("exclude") == DirectiveType.EXCLUDE
        assert DirectiveType("prioritize") == DirectiveType.PRIORITIZE
        assert DirectiveType("pivot") == DirectiveType.PIVOT
        assert DirectiveType("abort") == DirectiveType.ABORT

    def test_invalid_directive_type_raises(self) -> None:
        """Test that invalid directive type raises ValueError."""
        with pytest.raises(ValueError):
            DirectiveType("invalid")


# =============================================================================
# DirectiveResult Dataclass Tests
# =============================================================================


class TestDirectiveResult:
    """Tests for DirectiveResult dataclass."""

    def test_success_result(self) -> None:
        """Test creating a successful result."""
        parsed = ParsedDirective(directive_type=DirectiveType.FOCUS)
        strategy = SynthesizedStrategy(
            objectives=["Focus on web"],
            actions=["Scan web apps"],
            rationale="Per operator directive",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST],
        )
        result = DirectiveResult(
            success=True,
            parsed=parsed,
            strategy_update=strategy,
        )
        assert result.success is True
        assert result.parsed == parsed
        assert result.strategy_update == strategy
        assert result.error_message is None
        assert result.scope_violation is False

    def test_failure_result(self) -> None:
        """Test creating a failure result."""
        result = DirectiveResult(
            success=False,
            error_message="Failed to interpret directive",
        )
        assert result.success is False
        assert result.parsed is None
        assert result.strategy_update is None
        assert result.error_message == "Failed to interpret directive"
        assert result.scope_violation is False

    def test_scope_violation_result(self) -> None:
        """Test creating a scope violation result."""
        result = DirectiveResult(
            success=False,
            error_message="Directive violates scope: cannot exclude 192.168.1.0/24",
            scope_violation=True,
        )
        assert result.success is False
        assert result.scope_violation is True
        assert "scope" in result.error_message.lower()


# =============================================================================
# DirectiveInterpreter Tests
# =============================================================================


class TestDirectiveInterpreter:
    """Tests for DirectiveInterpreter class."""

    @pytest.fixture
    def mock_ensemble(self) -> MagicMock:
        """Create a mock DirectorEnsemble."""
        ensemble = MagicMock(spec=DirectorEnsemble)
        return ensemble

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock EventBus."""
        event_bus = MagicMock(spec=EventBus)
        event_bus.audit = AsyncMock(return_value="msg-001")
        event_bus.publish = AsyncMock(return_value=1)
        return event_bus

    @pytest.fixture
    def mock_scope_validator(self) -> MagicMock:
        """Create a mock ScopeValidator."""
        from cyberred.tools.scope import ScopeValidator
        validator = MagicMock(spec=ScopeValidator)
        validator.validate = MagicMock(return_value=True)
        return validator

    def test_interpreter_initialization(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test DirectiveInterpreter initialization."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        assert interpreter._ensemble == mock_ensemble
        assert interpreter._event_bus == mock_event_bus
        assert interpreter._scope_validator is None

    def test_interpreter_with_scope_validator(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
        mock_scope_validator: MagicMock,
    ) -> None:
        """Test DirectiveInterpreter with scope validator."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
            scope_validator=mock_scope_validator,
        )
        assert interpreter._scope_validator == mock_scope_validator

    @pytest.mark.asyncio
    async def test_interpret_focus_directive(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpreting a focus directive."""
        # Setup mock response
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web applications", "SQL injection"],
                "exclusions": [],
                "priorities": ["critical vulnerabilities"],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=500,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web application vulnerabilities, especially SQL injection",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed is not None
        assert result.parsed.directive_type == DirectiveType.FOCUS
        assert "web applications" in result.parsed.focus_areas
        assert result.parsed.confidence == 0.9

    @pytest.mark.asyncio
    async def test_interpret_exclude_directive(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpreting an exclude directive."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "exclude",
                "focus_areas": [],
                "exclusions": ["network infrastructure", "DNS servers"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.85,
            }),
            latency_ms=450,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Skip network infrastructure and DNS servers",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.EXCLUDE
        assert "network infrastructure" in result.parsed.exclusions

    @pytest.mark.asyncio
    async def test_interpret_pivot_directive(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpreting a pivot directive."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "pivot",
                "focus_areas": ["internal network"],
                "exclusions": ["web applications"],
                "priorities": ["lateral movement"],
                "pivot_reason": "Web application fully compromised, moving to internal",
                "confidence": 0.92,
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
            raw_text="Pivot to internal network, web app is fully compromised",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.PIVOT
        assert result.parsed.pivot_reason is not None
        assert "compromised" in result.parsed.pivot_reason.lower()

    @pytest.mark.asyncio
    async def test_interpret_logs_to_audit(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that interpretation logs to audit trail."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.8,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
            operator_id="op-1",
        )
        
        await interpreter.interpret(directive)
        
        # Verify audit was called
        mock_event_bus.audit.assert_called_once()
        audit_call = mock_event_bus.audit.call_args[0][0]
        assert audit_call["type"] == "mission_directive"
        assert audit_call["engagement_id"] == "eng-001"
        assert audit_call["raw_text"] == "Focus on web"
        assert audit_call["operator_id"] == "op-1"
        assert audit_call["success"] is True

    @pytest.mark.asyncio
    async def test_interpret_publishes_strategy(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that successful interpretation publishes strategy update."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.8,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        await interpreter.interpret(directive)
        
        # Verify publish was called to strategies channel
        mock_event_bus.publish.assert_called_once()
        channel = mock_event_bus.publish.call_args[0][0]
        assert channel == "strategies:eng-001"

    @pytest.mark.asyncio
    async def test_scope_violation_blocks_directive(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
        mock_scope_validator: MagicMock,
    ) -> None:
        """Test that scope violations block directive processing."""
        from cyberred.core.exceptions import ScopeViolationError
        
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["10.0.0.0/8"],  # Out of scope
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        # Make scope validator reject the focus area
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
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is False
        assert result.scope_violation is True
        assert "scope" in result.error_message.lower()
        # Strategy should NOT be published on scope violation
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_error(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that LLM failure returns error result."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="",
            latency_ms=30000,
            success=False,
            error="Timeout after 100s",
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is False
        assert "timeout" in result.error_message.lower() or "failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_json_response_handled(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that invalid JSON response is handled gracefully."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="This is not valid JSON",
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        # Should either fail gracefully or attempt to parse non-JSON response
        # Either way, should not raise exception
        assert isinstance(result, DirectiveResult)

    @pytest.mark.asyncio
    async def test_audit_logs_failures(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that failures are also logged to audit trail."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="",
            latency_ms=30000,
            success=False,
            error="Timeout",
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        await interpreter.interpret(directive)
        
        # Audit should still be called for failures
        mock_event_bus.audit.assert_called_once()
        audit_call = mock_event_bus.audit.call_args[0][0]
        assert audit_call["success"] is False


# =============================================================================
# Directive Parsing Edge Cases
# =============================================================================


class TestDirectiveParsingEdgeCases:
    """Tests for edge cases in directive parsing."""

    @pytest.fixture
    def mock_ensemble(self) -> MagicMock:
        ensemble = MagicMock(spec=DirectorEnsemble)
        return ensemble

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        event_bus = MagicMock(spec=EventBus)
        event_bus.audit = AsyncMock(return_value="msg-001")
        event_bus.publish = AsyncMock(return_value=1)
        return event_bus

    @pytest.fixture
    def mock_scope_validator(self) -> MagicMock:
        from cyberred.tools.scope import ScopeValidator
        validator = MagicMock(spec=ScopeValidator)
        validator.validate = MagicMock(return_value=True)
        return validator

    @pytest.mark.asyncio
    async def test_empty_focus_areas_handled(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test handling of empty focus_areas in response."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "prioritize",
                "focus_areas": [],
                "exclusions": [],
                "priorities": ["critical", "high", "medium"],
                "pivot_reason": None,
                "confidence": 0.75,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Prioritize critical and high vulnerabilities",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.focus_areas == []
        assert result.parsed.priorities == ["critical", "high", "medium"]

    @pytest.mark.asyncio
    async def test_abort_directive_type(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test abort directive type."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "abort",
                "focus_areas": [],
                "exclusions": ["brute force attacks"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.95,
            }),
            latency_ms=350,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Abort all brute force attacks immediately",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.ABORT

    @pytest.mark.asyncio
    async def test_complex_combined_directive(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test complex directive with multiple components."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web applications", "API endpoints", "authentication"],
                "exclusions": ["network scanning", "port enumeration"],
                "priorities": ["authentication bypass", "SQL injection", "XSS"],
                "pivot_reason": None,
                "confidence": 0.88,
            }),
            latency_ms=550,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps and APIs, prioritize auth bypass and SQLi, skip network scanning",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert len(result.parsed.focus_areas) == 3
        assert len(result.parsed.exclusions) == 2
        assert len(result.parsed.priorities) == 3

    @pytest.mark.asyncio
    async def test_prioritize_directive_creates_strategy(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that prioritize directive creates proper strategy."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "prioritize",
                "focus_areas": [],
                "exclusions": [],
                "priorities": ["critical vulnerabilities", "high vulnerabilities", "medium vulnerabilities"],
                "pivot_reason": None,
                "confidence": 0.82,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Prioritize critical then high then medium vulnerabilities",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.PRIORITIZE
        assert result.strategy_update is not None
        # Strategy should have objectives for each priority
        assert len(result.strategy_update.objectives) >= 3

    @pytest.mark.asyncio
    async def test_invalid_directive_type_defaults_to_focus(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that invalid directive_type in JSON defaults to FOCUS."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "invalid_type_xyz",  # Invalid directive type
                "focus_areas": ["web apps"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.8,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        # Invalid directive_type should default to FOCUS
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.FOCUS
        assert result.parsed.focus_areas == ["web apps"]

    @pytest.mark.asyncio
    async def test_fallback_parsing_for_stop_keyword(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test fallback parsing detects abort from 'stop' keyword."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="I understand you want to stop the brute force attacks.",  # Non-JSON
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Stop all brute force attacks",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        # Fallback parsing should detect abort
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.ABORT
        assert result.parsed.confidence == 0.3  # Low confidence for fallback

    @pytest.mark.asyncio
    async def test_fallback_parsing_for_pivot_keyword(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test fallback parsing detects pivot keyword."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="I'll help you pivot to internal network.",  # Non-JSON
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Pivot to internal network",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.PIVOT

    @pytest.mark.asyncio
    async def test_fallback_parsing_for_exclude_keyword(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test fallback parsing detects exclude keyword."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="We should exclude the production database from testing.",  # Non-JSON
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Exclude production database",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.EXCLUDE

    @pytest.mark.asyncio
    async def test_fallback_parsing_for_priority_keyword(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test fallback parsing detects prioritize keyword."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="Let me prioritize the critical issues first.",  # Non-JSON
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Prioritize critical issues",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.PRIORITIZE

    @pytest.mark.asyncio
    async def test_looks_like_target_detection(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
        mock_scope_validator: MagicMock,
    ) -> None:
        """Test that IP-like focus areas are validated against scope."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["192.168.1.0/24", "example.com"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
            scope_validator=mock_scope_validator,
        )
        
        directive = MissionDirective(
            raw_text="Focus on 192.168.1.0/24 and example.com",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        # Scope validator should be called for IP and hostname targets
        assert mock_scope_validator.validate.call_count == 2

    @pytest.mark.asyncio
    async def test_interpret_with_current_context(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpretation with current engagement context."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web apps"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.85,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        current_context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Current state",
            constraints={"no_dos": True},
        )
        
        result = await interpreter.interpret(directive, current_context=current_context)
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_llm_returns_none_response(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test handling when LLM returns empty content."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="",  # Empty content
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        # Should handle gracefully via fallback parsing
        assert isinstance(result, DirectiveResult)

    @pytest.mark.asyncio
    async def test_general_exception_handling(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test general exception handling in interpret."""
        mock_ensemble.query_model = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is False
        assert "Unexpected error" in result.error_message

    @pytest.mark.asyncio
    async def test_interpret_with_current_context_with_constraints(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpretation with current context that has constraints (lines 403-404)."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["web apps"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.85,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        # Create context WITH constraints to hit lines 403-404
        current_context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Current state",
            constraints={"no_dos": True, "max_threads": 10},
        )
        
        result = await interpreter.interpret(directive, current_context=current_context)
        
        assert result.success is True
        # Verify the context was used in the prompt building
        mock_ensemble.query_model.assert_called_once()
        call_args = mock_ensemble.query_model.call_args
        context_arg = call_args[0][1]  # Second positional argument is the DirectorContext
        assert "no_dos" in context_arg.prompt or "Constraints" in context_arg.prompt

    @pytest.mark.asyncio
    async def test_interpret_with_context_empty_constraints(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test interpretation with context that has empty constraints (branch 370->373)."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                "focus_areas": ["api endpoints"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.8,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on API endpoints",
            engagement_id="eng-001",
        )
        
        # Create context with EMPTY constraints dict to hit the else branch
        current_context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Current state",
            constraints={},  # Empty - should NOT add constraints line
        )
        
        result = await interpreter.interpret(directive, current_context=current_context)
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_scope_validation_skips_non_target_focus_areas(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
        mock_scope_validator: MagicMock,
    ) -> None:
        """Test that non-target-like focus areas skip scope validation (branch 476->474)."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "focus",
                # These don't look like IP/hostname targets
                "focus_areas": ["SQL injection", "authentication bypass", "XSS vulnerabilities"],
                "exclusions": [],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.9,
            }),
            latency_ms=400,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
            scope_validator=mock_scope_validator,
        )
        
        directive = MissionDirective(
            raw_text="Focus on SQL injection and XSS",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        # Scope validator should NOT be called for these non-target focus areas
        mock_scope_validator.validate.assert_not_called()

    @pytest.mark.asyncio
    async def test_abort_directive_with_empty_exclusions_creates_default_strategy(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test ABORT directive with empty exclusions creates default abort strategy."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "abort",
                "focus_areas": [],
                "exclusions": [],  # Empty exclusions
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.95,
            }),
            latency_ms=350,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="ABORT everything now!",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.ABORT
        assert result.strategy_update is not None
        # Should have default abort objectives/actions
        assert len(result.strategy_update.objectives) >= 1
        assert len(result.strategy_update.actions) >= 1
        assert any("non-essential" in obj.lower() for obj in result.strategy_update.objectives)

    @pytest.mark.asyncio
    async def test_abort_directive_with_exclusions_creates_strategy(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test ABORT directive with exclusions creates proper strategy (branch 540->546)."""
        mock_response = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content=json.dumps({
                "directive_type": "abort",
                "focus_areas": [],
                "exclusions": ["brute force attacks", "password spraying", "DoS attacks"],
                "priorities": [],
                "pivot_reason": None,
                "confidence": 0.95,
            }),
            latency_ms=350,
            success=True,
        )
        mock_ensemble.query_model = AsyncMock(return_value=mock_response)
        
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Abort brute force, password spraying, and DoS attacks",
            engagement_id="eng-001",
        )
        
        result = await interpreter.interpret(directive)
        
        assert result.success is True
        assert result.parsed.directive_type == DirectiveType.ABORT
        assert result.strategy_update is not None
        # Should have objectives for each exclusion in ABORT directive
        assert len(result.strategy_update.objectives) == 3
        assert len(result.strategy_update.actions) == 3
        # Each abort should create "Abort: X" objectives
        for obj in result.strategy_update.objectives:
            assert obj.startswith("Abort:")
        # Each abort should create "Immediately stop all X activities" actions
        for action in result.strategy_update.actions:
            assert "Immediately stop all" in action

    def test_build_interpretation_prompt_with_constraints(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test _build_interpretation_prompt includes constraints when provided (lines 403-404)."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        # Context WITH non-empty constraints
        current_context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Current state",
            constraints={"no_dos": True, "max_threads": 10},
        )
        
        prompt = interpreter._build_interpretation_prompt(directive, current_context)
        
        # Should include constraints section
        assert "Constraints:" in prompt
        assert "no_dos" in prompt
        assert "max_threads" in prompt

    def test_build_interpretation_prompt_without_constraints(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test _build_interpretation_prompt skips constraints when empty."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        # Context with EMPTY constraints
        current_context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Current state",
            constraints={},
        )
        
        prompt = interpreter._build_interpretation_prompt(directive, current_context)
        
        # Should NOT include constraints section
        assert "Constraints:" not in prompt
        # But should include phase
        assert "Phase: exploitation" in prompt

    def test_build_interpretation_prompt_without_context(
        self,
        mock_ensemble: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test _build_interpretation_prompt without current context."""
        interpreter = DirectiveInterpreter(
            ensemble=mock_ensemble,
            event_bus=mock_event_bus,
        )
        
        directive = MissionDirective(
            raw_text="Focus on web apps",
            engagement_id="eng-001",
        )
        
        prompt = interpreter._build_interpretation_prompt(directive, current_context=None)
        
        # Should NOT include context section at all
        assert "## Current Context" not in prompt
        # But should include directive
        assert "Focus on web apps" in prompt
