"""Integration tests for OutputProcessor with mock LLM.

Story 4.5 Task 13: Verify Tier 2/Tier 3 behavior with mock LLM provider.
"""
import pytest
import json
from unittest.mock import patch, AsyncMock
from cyberred.tools.output import OutputProcessor, ProcessedOutput
from cyberred.tools.parsers.nmap_stub import nmap_stub_parser

# Valid UUID constants for testing (Finding model requires UUID format)
TEST_AGENT_ID_1 = "00000000-0000-0000-0000-000000000001"
TEST_AGENT_ID_2 = "00000000-0000-0000-0000-000000000002"
TEST_AGENT_ID_3 = "00000000-0000-0000-0000-000000000003"
TEST_AGENT_ID_4 = "00000000-0000-0000-0000-000000000004"
TEST_AGENT_ID_5 = "00000000-0000-0000-0000-000000000005"


@pytest.mark.integration
class TestOutputProcessorIntegration:
    """Integration tests for OutputProcessor tier routing."""
    
    def test_tier1_nmap_stub_parser(self):
        """Test Tier 1 routing with nmap stub parser."""
        processor = OutputProcessor()
        processor.register_parser("nmap", nmap_stub_parser)
        
        result = processor.process(
            stdout="Nmap scan report for 192.168.1.1\nPORT   STATE SERVICE\n22/tcp open  ssh",
            stderr="",
            tool="nmap",
            exit_code=0,
            agent_id=TEST_AGENT_ID_1,
            target="192.168.1.1"
        )
        
        assert result.tier == 1
        assert len(result.findings) == 1
        assert result.findings[0].tool == "nmap"
        assert result.findings[0].target == "192.168.1.1"
        assert "Parsed 1 findings" in result.summary
    
    @patch("cyberred.tools.output.get_gateway")
    def test_tier2_llm_summarization(self, mock_get_gateway):
        """Test Tier 2 fallback to LLM summarization."""
        # Setup mock LLM gateway
        mock_gateway = AsyncMock()
        mock_gateway.complete.return_value = json.dumps({
            "findings": [
                {
                    "type": "open_port",
                    "severity": "medium",
                    "description": "SSH port open",
                    "evidence": "22/tcp open ssh"
                }
            ],
            "summary": "Found open SSH port on target"
        })
        mock_get_gateway.return_value = mock_gateway
        
        processor = OutputProcessor()
        # No parser registered - should fall back to LLM
        
        result = processor.process(
            stdout="PORT   STATE SERVICE\n22/tcp open  ssh",
            stderr="",
            tool="custom_scanner",
            exit_code=0,
            agent_id=TEST_AGENT_ID_2,
            target="192.168.1.100"
        )
        
        assert result.tier == 2
        assert len(result.findings) == 1
        assert result.findings[0].type == "open_port"
        assert result.summary == "Found open SSH port on target"
        
        # Verify gateway was called
        mock_gateway.complete.assert_called_once()
    
    @patch("cyberred.tools.output.get_gateway")
    def test_tier3_fallback_when_llm_fails(self, mock_get_gateway):
        """Test Tier 3 fallback when LLM is unavailable."""
        from cyberred.llm import LLMGatewayNotInitializedError
        
        mock_get_gateway.side_effect = LLMGatewayNotInitializedError("Gateway not initialized")
        
        processor = OutputProcessor(max_raw_length=50)
        
        result = processor.process(
            stdout="This is raw tool output that will be truncated...",
            stderr="",
            tool="unknown_tool",
            exit_code=0,
            agent_id=TEST_AGENT_ID_3,
            target="192.168.1.200"
        )
        
        assert result.tier == 3
        assert len(result.findings) == 0
        assert len(result.raw_truncated) <= 50
        assert "Raw tool output" in result.summary
    
    @patch("cyberred.tools.output.get_gateway")
    def test_tier3_fallback_on_llm_timeout(self, mock_get_gateway):
        """Test Tier 3 fallback when LLM times out."""
        import asyncio
        
        mock_gateway = AsyncMock()
        mock_gateway.complete.side_effect = asyncio.TimeoutError("LLM timeout")
        mock_get_gateway.return_value = mock_gateway
        
        processor = OutputProcessor()
        
        result = processor.process(
            stdout="Tool output",
            stderr="",
            tool="slow_scanner",
            exit_code=0,
            agent_id=TEST_AGENT_ID_4,
            target="192.168.1.250"
        )
        
        assert result.tier == 3
        assert len(result.findings) == 0
    
    @patch("cyberred.tools.output.get_gateway")
    def test_tier3_fallback_on_invalid_json(self, mock_get_gateway):
        """Test Tier 3 fallback when LLM returns invalid JSON."""
        mock_gateway = AsyncMock()
        mock_gateway.complete.return_value = "This is not valid JSON"
        mock_get_gateway.return_value = mock_gateway
        
        processor = OutputProcessor()
        
        result = processor.process(
            stdout="Tool output",
            stderr="",
            tool="json_breaker",
            exit_code=0,
            agent_id=TEST_AGENT_ID_5,
            target="192.168.1.251"
        )
        
        assert result.tier == 3
        assert len(result.findings) == 0
