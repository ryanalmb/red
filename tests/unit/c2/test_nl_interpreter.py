"""Unit tests for NL Interpreter.

Story 12.8: Natural Language Drop Box Setup - Task 9.1

Tests NL parsing with mocked LLM responses.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.c2.nl_interpreter import (
    DeploymentPlan,
    DropBoxDeploymentInterpreter,
    InterpretationError,
    SUPPORTED_PLATFORMS,
    MAX_NL_INPUT_LENGTH,
)


class TestDeploymentPlan:
    """Tests for DeploymentPlan dataclass."""
    
    def test_valid_plan_android(self):
        """Test valid Android deployment plan."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="my-phone",
        )
        assert plan.is_valid()
        assert plan.validate() == []
    
    def test_valid_plan_windows(self):
        """Test valid Windows deployment plan."""
        plan = DeploymentPlan(
            platform="windows",
            ip_address="10.0.0.50",
        )
        assert plan.is_valid()
    
    def test_valid_plan_linux_hostname(self):
        """Test valid Linux plan with hostname instead of IP."""
        plan = DeploymentPlan(
            platform="linux",
            ip_address="server.local",
        )
        assert plan.is_valid()
    
    def test_invalid_platform(self):
        """Test invalid platform."""
        plan = DeploymentPlan(
            platform="unsupported",
            ip_address="192.168.1.100",
        )
        errors = plan.validate()
        assert len(errors) == 1
        assert "Unsupported platform" in errors[0]
    
    def test_empty_platform(self):
        """Test empty platform."""
        plan = DeploymentPlan(
            platform="",
            ip_address="192.168.1.100",
        )
        errors = plan.validate()
        assert "Platform is required" in errors[0]
    
    def test_empty_ip_address(self):
        """Test empty IP address."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="",
        )
        errors = plan.validate()
        assert "IP address or hostname is required" in errors[0]
    
    def test_invalid_ip_address(self):
        """Test invalid IP address format."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="not!valid@host",
        )
        errors = plan.validate()
        assert "Invalid IP address or hostname" in errors[0]
    
    def test_platform_normalization(self):
        """Test platform is normalized to lowercase."""
        plan = DeploymentPlan(
            platform="ANDROID",
            ip_address="192.168.1.100",
        )
        assert plan.platform == "android"
        assert plan.is_valid()
    
    def test_needs_clarification_low_confidence(self):
        """Test needs_clarification with low confidence."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            confidence=0.3,
        )
        assert plan.needs_clarification()
    
    def test_needs_clarification_with_question(self):
        """Test needs_clarification with clarification_needed set."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            confidence=0.9,
            clarification_needed="What is the hostname?",
        )
        assert plan.needs_clarification()
    
    def test_no_clarification_needed(self):
        """Test no clarification needed for confident plan."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            confidence=0.95,
        )
        assert not plan.needs_clarification()
    
    def test_generate_drop_box_id_with_hostname(self):
        """Test drop box ID generation with hostname."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="office-phone",
        )
        drop_box_id = plan.generate_drop_box_id()
        assert "office-phone" in drop_box_id
        assert "android" in drop_box_id
    
    def test_generate_drop_box_id_without_hostname(self):
        """Test drop box ID generation without hostname."""
        plan = DeploymentPlan(
            platform="linux",
            ip_address="192.168.1.100",
        )
        drop_box_id = plan.generate_drop_box_id()
        assert "linux" in drop_box_id
        assert "192-168-1-100" in drop_box_id
    
    def test_generate_drop_box_id_sanitization(self):
        """Test drop box ID sanitization of special characters."""
        plan = DeploymentPlan(
            platform="windows",
            ip_address="192.168.1.100",
            hostname="my server!@#$%",
        )
        drop_box_id = plan.generate_drop_box_id()
        assert "!" not in drop_box_id
        assert "@" not in drop_box_id


class TestDropBoxDeploymentInterpreter:
    """Tests for DropBoxDeploymentInterpreter."""
    
    @pytest.fixture
    def interpreter(self):
        """Create interpreter instance."""
        return DropBoxDeploymentInterpreter()
    
    @pytest.fixture
    def mock_gateway(self):
        """Create mock LLM gateway."""
        gateway = MagicMock()
        gateway.agent_complete = AsyncMock()
        return gateway
    
    @pytest.mark.asyncio
    async def test_interpret_valid_android(self, interpreter, mock_gateway):
        """Test interpreting valid Android deployment request."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "android",
            "ip_address": "192.168.1.100",
            "hostname": "android-phone",
            "confidence": 0.95,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Deploy on Android at 192.168.1.100")
        
        assert plan.platform == "android"
        assert plan.ip_address == "192.168.1.100"
        assert plan.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_interpret_valid_windows(self, interpreter, mock_gateway):
        """Test interpreting valid Windows deployment request."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "windows",
            "ip_address": "10.0.0.50",
            "hostname": "office-server",
            "confidence": 0.9,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Set up Windows drop box on 10.0.0.50")
        
        assert plan.platform == "windows"
        assert plan.ip_address == "10.0.0.50"
    
    @pytest.mark.asyncio
    async def test_interpret_ambiguous_input(self, interpreter, mock_gateway):
        """Test interpreting ambiguous input requiring clarification."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "",
            "ip_address": "",
            "confidence": 0.2,
            "clarification_needed": "Please specify the platform and IP address",
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Deploy on my phone")
        
        assert plan.needs_clarification()
        assert plan.confidence < 0.5
    
    @pytest.mark.asyncio
    async def test_interpret_empty_input(self, interpreter):
        """Test interpreting empty input raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await interpreter.interpret("")
    
    @pytest.mark.asyncio
    async def test_interpret_whitespace_input(self, interpreter):
        """Test interpreting whitespace-only input raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await interpreter.interpret("   ")
    
    @pytest.mark.asyncio
    async def test_interpret_input_too_long(self, interpreter):
        """Test interpreting input that exceeds max length."""
        long_input = "x" * (MAX_NL_INPUT_LENGTH + 1)
        with pytest.raises(ValueError, match="too long"):
            await interpreter.interpret(long_input)
    
    @pytest.mark.asyncio
    async def test_interpret_llm_error(self, interpreter, mock_gateway):
        """Test handling LLM error response."""
        mock_response = MagicMock()
        mock_response.content = ""
        mock_response.finish_reason = "error:transient:LLMTimeoutError"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            with pytest.raises(InterpretationError, match="temporarily unavailable"):
                await interpreter.interpret("Deploy on Android at 192.168.1.100")
    
    @pytest.mark.asyncio
    async def test_interpret_json_with_markdown(self, interpreter, mock_gateway):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_response = MagicMock()
        mock_response.content = """```json
{
    "platform": "linux",
    "ip_address": "server.local",
    "hostname": "linux-server",
    "confidence": 0.85
}
```"""
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Linux dropbox at server.local")
        
        assert plan.platform == "linux"
        assert plan.ip_address == "server.local"
    
    @pytest.mark.asyncio
    async def test_interpret_missing_platform_adds_clarification(self, interpreter, mock_gateway):
        """Test that missing platform triggers clarification request."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "",
            "ip_address": "192.168.1.100",
            "confidence": 0.7,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Deploy at 192.168.1.100")
        
        assert plan.clarification_needed is not None
        assert "platform" in plan.clarification_needed.lower()


class TestSupportedPlatforms:
    """Tests for supported platforms constant."""
    
    def test_all_platforms_present(self):
        """Test all expected platforms are supported."""
        expected = {"android", "windows", "linux", "macos", "ios"}
        assert SUPPORTED_PLATFORMS == expected
    
    def test_platforms_are_lowercase(self):
        """Test all platforms are lowercase."""
        for platform in SUPPORTED_PLATFORMS:
            assert platform == platform.lower()


class TestInterpretationError:
    """Tests for InterpretationError exception."""
    
    def test_error_with_message(self):
        """Test error with just message."""
        error = InterpretationError("Test error")
        assert str(error) == "Test error"
        assert error.suggestion is None
    
    def test_error_with_suggestion(self):
        """Test error with message and suggestion."""
        error = InterpretationError("Test error", suggestion="Try this instead")
        assert str(error) == "Test error"
        assert error.suggestion == "Try this instead"


class TestDropBoxDeploymentInterpreterEdgeCases:
    """Additional edge case tests for interpreter."""
    
    @pytest.fixture
    def interpreter(self):
        """Create interpreter instance."""
        return DropBoxDeploymentInterpreter()
    
    @pytest.fixture
    def mock_gateway(self):
        """Create mock LLM gateway."""
        gateway = MagicMock()
        gateway.agent_complete = AsyncMock()
        return gateway
    
    @pytest.mark.asyncio
    async def test_interpret_strips_whitespace(self, interpreter, mock_gateway):
        """Test input whitespace is stripped."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "linux",
            "ip_address": "10.0.0.1",
            "confidence": 0.9,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("   Deploy on Linux at 10.0.0.1   ")
        
        assert plan.platform == "linux"
    
    @pytest.mark.asyncio
    async def test_parse_response_extracts_json_from_text(self, interpreter, mock_gateway):
        """Test JSON extraction from mixed text response."""
        mock_response = MagicMock()
        mock_response.content = 'Here is the parsed result: {"platform": "windows", "ip_address": "10.0.0.5", "confidence": 0.85}'
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Windows at 10.0.0.5")
        
        assert plan.platform == "windows"
        assert plan.ip_address == "10.0.0.5"
    
    @pytest.mark.asyncio
    async def test_interpret_missing_ip_adds_clarification(self, interpreter, mock_gateway):
        """Test that missing IP triggers clarification."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "platform": "linux",
            "ip_address": "",
            "confidence": 0.7,
        })
        mock_response.finish_reason = "stop"
        mock_gateway.agent_complete.return_value = mock_response
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            plan = await interpreter.interpret("Linux dropbox")
        
        assert plan.clarification_needed is not None
        assert "ip" in plan.clarification_needed.lower() or "address" in plan.clarification_needed.lower()
    
    @pytest.mark.asyncio
    async def test_gateway_exception_raises_interpretation_error(self, interpreter, mock_gateway):
        """Test that gateway exceptions are wrapped in InterpretationError."""
        mock_gateway.agent_complete.side_effect = Exception("Connection failed")
        
        with patch.object(interpreter, '_get_gateway', return_value=mock_gateway):
            with pytest.raises(InterpretationError) as exc_info:
                await interpreter.interpret("Deploy on Android at 192.168.1.1")
        
        assert "Connection failed" in str(exc_info.value)


class TestDeploymentPlanEdgeCases:
    """Additional edge case tests for DeploymentPlan."""
    
    def test_ipv6_address_valid(self):
        """Test IPv6 address is valid."""
        plan = DeploymentPlan(
            platform="linux",
            ip_address="::1",
        )
        assert plan.is_valid()
    
    def test_ipv6_full_address_valid(self):
        """Test full IPv6 address is valid."""
        plan = DeploymentPlan(
            platform="linux",
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        )
        assert plan.is_valid()
    
    def test_hostname_with_subdomain_valid(self):
        """Test hostname with subdomain is valid."""
        plan = DeploymentPlan(
            platform="windows",
            ip_address="server.internal.company.local",
        )
        assert plan.is_valid()
    
    def test_generate_drop_box_id_empty_hostname(self):
        """Test ID generation with empty hostname uses IP."""
        plan = DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="",
        )
        drop_box_id = plan.generate_drop_box_id()
        assert "android" in drop_box_id
        assert "192-168-1-100" in drop_box_id
    
    def test_multiple_validation_errors(self):
        """Test plan with multiple validation errors."""
        plan = DeploymentPlan(
            platform="invalid",
            ip_address="not!valid",
        )
        errors = plan.validate()
        assert len(errors) == 2  # Both platform and IP invalid
