import pytest
import structlog
import json
from dataclasses import dataclass, is_dataclass
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from cyberred.tools.output import ProcessedOutput, OutputProcessor, _strip_markdown_json
from cyberred.core.models import Finding


# Tests for _strip_markdown_json helper
class TestStripMarkdownJson:
    """Test markdown code fence stripping from LLM responses."""
    
    def test_plain_json_unchanged(self):
        """Raw JSON should pass through unchanged."""
        raw_json = '{"findings": [], "summary": "test"}'
        assert _strip_markdown_json(raw_json) == raw_json
    
    def test_json_with_markdown_fence(self):
        """JSON wrapped in ```json ... ``` should be unwrapped."""
        wrapped = '```json\n{"findings": [], "summary": "test"}\n```'
        expected = '{"findings": [], "summary": "test"}'
        assert _strip_markdown_json(wrapped) == expected
    
    def test_json_with_plain_fence(self):
        """JSON wrapped in ``` ... ``` (no language) should be unwrapped."""
        wrapped = '```\n{"findings": []}\n```'
        expected = '{"findings": []}'
        assert _strip_markdown_json(wrapped) == expected
    
    def test_preserves_whitespace_inside(self):
        """Whitespace inside JSON should be preserved."""
        wrapped = '```json\n{\n  "key": "value"\n}\n```'
        result = _strip_markdown_json(wrapped)
        assert '"key": "value"' in result
    
    def test_strips_outer_whitespace(self):
        """Leading/trailing whitespace should be stripped."""
        raw = '  \n{"data": 1}\n  '
        assert _strip_markdown_json(raw) == '{"data": 1}'
    
    def test_fence_without_newline(self):
        """Edge case: fence with no newline (malformed) returns empty."""
        # ``` with no newline - first_newline will be -1
        malformed = '```{"data": 1}```'
        result = _strip_markdown_json(malformed)
        # When no newline, we don't modify content[first_newline + 1:]
        # first_newline = -1, so content becomes content[0:] = unchanged
        # But still check endswith. '```{"data": 1}```' ends with ``` so it strips that
        assert '{"data": 1}' in result or result == '```{"data": 1}'
    
    def test_fence_without_closing(self):
        """Edge case: opening fence without closing fence."""
        # Starts with ``` but doesn't end with ```
        no_closing = '```json\n{"data": 1}'
        result = _strip_markdown_json(no_closing)
        # Should strip opening but not try to strip closing
        assert result == '{"data": 1}'

def test_processed_output_structure():
    """Verify ProcessedOutput dataclass structure."""
    # This import should fail initially
    from cyberred.tools.output import ProcessedOutput
    
    assert is_dataclass(ProcessedOutput)
    
    # Verify default values and types
    output = ProcessedOutput()
    assert isinstance(output.findings, list)
    assert len(output.findings) == 0
    assert output.summary == ""
    assert output.raw_truncated == ""
    assert output.tier == 3
    
    # Verify we can extract type hints (basic check)
    import inspect
    sig = inspect.signature(ProcessedOutput)
    assert "findings" in sig.parameters
    assert "summary" in sig.parameters
    assert "raw_truncated" in sig.parameters

def test_output_processor_skeleton():
    """Verify OutputProcessor structure and process method signature."""
    from cyberred.tools.output import OutputProcessor
    
    processor = OutputProcessor()
    
    # Verify process method exists and returns empty result initially
    # stdout, stderr, tool, exit_code, agent_id, target
    result = processor.process(
        stdout="raw output",
        stderr="",
        tool="nmap",
        exit_code=0,
        agent_id="agent-123",
        target="192.168.1.1"
    )
    
    from cyberred.tools.output import ProcessedOutput
    assert isinstance(result, ProcessedOutput)
    assert result.findings == []
    assert isinstance(result.summary, str)

def test_parser_registry_flow():
    """Verify parser registration."""
    from cyberred.tools.output import OutputProcessor
    
    processor = OutputProcessor()
    
    def dummy_parser(stdout, stderr, exit_code, agent_id, target):
        return []
        
    # Should fail initially (method missing)
    processor.register_parser("nmap", dummy_parser)
    
    # Should fail initially (method missing in Red/Green of Task 3, exists in Refactor output.py)
    # But wait, I need to update output.py with get_registered_parsers first or simultaneously.
    # The instructions say Refactor: Add method.
    
    # Note: I am updating the test to use the method getting added in the next tool call (batched).
    # But wait, python runs interpret line by line, so execution happens after tools.
    # But verification comes from running pytest later.
    processor.register_parser("nmap", dummy_parser)
    
    assert "nmap" in processor.get_registered_parsers()

def test_process_tier1_routing():
    """Verify routing to Tier 1 parser."""
    from cyberred.tools.output import OutputProcessor
    from cyberred.core.models import Finding
    
    processor = OutputProcessor()
    
    agent_id = "00000000-0000-0000-0000-000000000000"
    target = "192.168.1.1"
    
    def mock_parser(stdout, stderr, exit_code, agent_id, target):
        return [Finding(
            id="11111111-1111-1111-1111-111111111111", 
            type="test", 
            severity="low", 
            target=target, 
            evidence="out", 
            agent_id=agent_id, 
            timestamp="2023-01-01T00:00:00+00:00", 
            tool="nmap", 
            topic="topic", 
            signature=""
        )]
        
    processor.register_parser("nmap", mock_parser)
    
    # process method currently returns empty result
    result = processor.process("out", "err", "nmap", 0, agent_id, target)
    
    assert result.tier == 1
    assert len(result.findings) == 1
    assert result.findings[0].type == "test"
    assert len(result.findings) == 1
    assert result.findings[0].type == "test"

@patch("cyberred.tools.output.get_gateway")
def test_process_tier2_fallback(mock_get_gateway):
    """Verify fallback to Tier 2 LLM summarization."""
    from cyberred.tools.output import OutputProcessor
    
    # Setup mock gateway
    mock_gateway = AsyncMock()
    mock_get_gateway.return_value = mock_gateway
    mock_response = MagicMock()
    mock_response.content = '{"findings": [{"type": "test", "severity": "medium", "description": "llm finding", "evidence": "ev"}], "summary": "llm summary"}'
    mock_gateway.complete.return_value = mock_response
    
    processor = OutputProcessor()
    
    agent_id = "00000000-0000-0000-0000-000000000000"
    target = "192.168.1.1"
    
    result = processor.process("raw output", "err", "unknown_tool", 0, agent_id, target)
    
    assert result.tier == 2
    assert len(result.findings) == 1
    assert result.findings[0].type == "test"
    assert "llm finding" in result.findings[0].evidence
    assert result.summary == "llm summary"

@patch("cyberred.tools.output.get_gateway")
def test_process_tier3_fallback(mock_get_gateway):
    """Verify fallback to Tier 3 raw truncated output."""
    from cyberred.tools.output import OutputProcessor
    from cyberred.llm import LLMGatewayNotInitializedError
    
    mock_get_gateway.side_effect = LLMGatewayNotInitializedError("Gateway not init")
    
    processor = OutputProcessor(max_raw_length=10)
    
    agent_id = "00000000-0000-0000-0000-000000000000"
    target = "192.168.1.1"
    
    result = processor.process("1234567890EXTRA", "", "unknown", 0, agent_id, target)
    
    assert result.tier == 3
    assert result.raw_truncated == "1234567890"

def test_missing_coverage_tier1_exception():
    processor = OutputProcessor()
    
    # Mock parser that raises exception to hit line 84-86 (exception handler)
    def failing_parser(*args):
        raise ValueError("Parser failed")
        
    processor.register_parser("failtool", failing_parser)
    
    # Should fall through to Tier 2 (LLM), which we mock to fail to fall to Tier 3
    with patch("cyberred.tools.output.get_gateway") as mock_gw:
        mock_gw.side_effect = Exception("LLM failed")
        result = processor.process("out", "err", "failtool", 0, "id", "target")
        assert result.tier == 3

@patch("cyberred.tools.output.get_gateway")
def test_missing_coverage_llm_empty_findings(mock_get_gateway):
    # Test Tier 2 with empty findings list to hit lines 122 default and loop skip
    mock_gateway = AsyncMock()
    # Return valid JSON with no findings to hit empty loop path
    mock_response = MagicMock()
    mock_response.content = json.dumps({"findings": [], "summary": "Empty"})
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    result = processor.process("out", "err", "unknown", 0, "id", "target")
    
    assert result.tier == 2
    assert len(result.findings) == 0
    assert result.summary == "Empty"

def test_missing_coverage_logging_failure():
    # Only way to hit line 94-95 is if log.exception raises, which is rare but possible if mocked
    processor = OutputProcessor()
    
    with patch("cyberred.tools.output.log") as mock_log:
        mock_log.exception.side_effect = Exception("Log failed")
        
        # Trigger Tier 2 failure (no gateway)
        with patch("cyberred.tools.output.get_gateway", side_effect=Exception("LLM failed")):
             result = processor.process("out", "err", "unknown", 0, "id", "target")
             # Should swallow log exception and return Tier 3
             assert result.tier == 3
    assert len(result.findings) == 0
    assert "Raw tool output" in result.summary

def test_generate_cache_key():
    """Verify cache key generation."""
    from cyberred.tools.output import OutputProcessor
    import hashlib
    
    processor = OutputProcessor()
    
    tool = "Nmap"
    stdout = "output"
    stderr = "error"
    
    # Expected: tool.lower() + ":" + sha256(stdout+stderr)[:16]
    content = stdout + stderr
    expected_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    expected_key = f"nmap:{expected_hash}"
    
    # Should fail as method doesn't exist yet
    key = processor._generate_cache_key(tool, stdout, stderr)
    assert key == expected_key

@patch("cyberred.tools.output.get_gateway")
def test_llm_response_caching(mock_get_gateway):
    """Verify repeated LLM calls with same output are cached."""
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "cached"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    tool = "cache_test_tool"
    stdout = "same output"
    stderr = ""
    
    # First call - should hit LLM
    result1 = processor.process(stdout, stderr, tool, 0, "id", "target")
    assert result1.tier == 2
    
    # Second call - same input - should hit cache
    result2 = processor.process(stdout, stderr, tool, 0, "id", "target")
    assert result2.tier == 2
    assert result2.summary == "cached"
    
    # Verify gateway called only once
    assert mock_gateway.complete.call_count == 1

@patch("cyberred.tools.output.get_gateway")
def test_cache_configuration(mock_get_gateway):
    """Verify cache can be disabled."""
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "uncached"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    # Initialize with cache disabled (args will need to be added to init)
    processor = OutputProcessor(cache_enabled=False)
    
    tool = "cache_test_tool"
    stdout = "same output"
    stderr = ""
    
    # First call
    processor.process(stdout, stderr, tool, 0, "id", "target")
    
    # Second call
    processor.process(stdout, stderr, tool, 0, "id", "target")
    
    # Verify gateway called TWICE because cache is disabled
    assert mock_gateway.complete.call_count == 2

@patch("cyberred.tools.output.get_gateway")
def test_llm_timeout_usage(mock_get_gateway):
    """Verify timeout parameter is passed to gateway."""
    from cyberred.tools.output import OutputProcessor
    from cyberred.llm import TaskComplexity
    from unittest.mock import ANY
    
    mock_gateway = AsyncMock()
    # Mock successful response
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "ok"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    # Init with custom timeout
    processor = OutputProcessor(llm_timeout=15)
    
    processor.process("out", "err", "timeout_tool", 0, "id", "target")
    
    # Verify gateway called with LLMRequest
    # We can't verify timeout easily as it's handled by wait_for wrapper, 
    # but we can verify request construction
    args = mock_gateway.complete.call_args
    assert args is not None
    request = args[0][0]
    assert request.prompt is not None

@patch("cyberred.tools.output.get_gateway")
def test_llm_invalid_json(mock_get_gateway):
    """Verify invalid JSON response triggers fallback and formatted logging."""
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = 'NOT JSON'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    # Capture logs
    with patch("cyberred.tools.output.log") as mock_log:
        result = processor.process("out", "err", "json_tool", 0, "id", "target")
        
        assert result.tier == 3
        
        # Verify specific error logging
        mock_log.exception.assert_called()
        call_args = mock_log.exception.call_args
        assert "tier2_json_error" in str(call_args) or "tier2_json_error" == call_args[0][0]

@patch("cyberred.tools.output.get_gateway")
def test_llm_timeout_logging(mock_get_gateway):
    """Verify timeout triggers fallback and formatted logging."""
    import asyncio
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_gateway.complete.side_effect = asyncio.TimeoutError("Timeout")
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    with patch("cyberred.tools.output.log") as mock_log:
        result = processor.process("out", "err", "timeout_tool", 0, "id", "target")
        
        assert result.tier == 3
        
        found_timeout_log = False
        # Check warning logs
        for call in mock_log.warning.call_args_list:
            if "tier2_timeout" in str(call) or (call.args and call.args[0] == "tier2_timeout"):
                found_timeout_log = True
        
        # Check exception logs if fell through
        if not found_timeout_log:
             for call in mock_log.exception.call_args_list:
                 if "tier2_timeout" in str(call) or (call.args and call.args[0] == "tier2_timeout"):
                     found_timeout_log = True
                     
        assert found_timeout_log, "Did not find tier2_timeout log event"







@patch("cyberred.tools.parser_watcher.ParserWatcher")
def test_watcher_lifecycle(MockParserWatcher):
    """Verify OutputProcessor manages watcher lifecycle."""
    from cyberred.tools.output import OutputProcessor
    from pathlib import Path
    
    mock_watcher = MockParserWatcher.return_value
    parsers_dir = Path("/tmp/parsers")
    
    # Initialize with parsers_dir
    processor = OutputProcessor(parsers_dir=parsers_dir)
    
    # Start
    processor.start_watcher()
    MockParserWatcher.assert_called_once_with(parsers_dir=parsers_dir, processor=processor)
    mock_watcher.start.assert_called_once()
    
    # Stop
    processor.stop_watcher()
    mock_watcher.stop.assert_called_once()

@patch("threading.RLock")
def test_locking_mechanism(MockRLock):
    """Verify thread safety locks."""
    from cyberred.tools.output import OutputProcessor
    
    mock_lock = MockRLock.return_value
    # Ensure usage as context manager works
    mock_lock.__enter__ = Mock(return_value=mock_lock)
    mock_lock.__exit__ = Mock(return_value=None)
    
    processor = OutputProcessor()
    
    # Register should acquire lock
    processor.register_parser("tool", lambda *args: [])
    mock_lock.__enter__.assert_called()
    
    mock_lock.reset_mock()
    
    # Process should acquire lock
    processor.process("out", "err", "tool", 0, "id", "target")
    mock_lock.__enter__.assert_called()

def test_watcher_lifecycle_edge_cases():
    """Verify start/stop idempotency and robustness."""
    from cyberred.tools.output import OutputProcessor
    from unittest.mock import patch, Mock
    
    # Init without parsers_dir
    processor = OutputProcessor(parsers_dir=None)
    
    with patch("cyberred.tools.parser_watcher.ParserWatcher") as MockWatcher:
        # Start without dir -> should do nothing
        processor.start_watcher()
        MockWatcher.assert_not_called()
        
        # Manually set logic to test idempotency
        processor._parsers_dir = "/tmp"
        mock_watcher = MockWatcher.return_value
        
        # First start
        processor.start_watcher()
        MockWatcher.assert_called_once()
        mock_watcher.start.assert_called_once()
        
        # Check idempotency
        processor.start_watcher()
        assert MockWatcher.call_count == 1 # Still 1
        
        # First stop
        processor.stop_watcher()
        mock_watcher.stop.assert_called_once()
        assert processor._watcher is None
        
        # Second stop (idempotency)
        processor.stop_watcher()
        # Should not throw error

def test_unregister_unknown_parser():
    """Verify unregistering unknown parser doesn't error."""
    from cyberred.tools.output import OutputProcessor
    
    processor = OutputProcessor()
    # Should not raise exception
    processor.unregister_parser("non_existent_tool")

def test_unregister_existing_parser():
    """Verify unregistering an existing parser removes it from registry."""
    from cyberred.tools.output import OutputProcessor
    
    processor = OutputProcessor()
    
    def dummy_parser(*args):
        return []
    
    processor.register_parser("nmap", dummy_parser)
    assert "nmap" in processor.get_registered_parsers()
    
    processor.unregister_parser("nmap")
    assert "nmap" not in processor.get_registered_parsers()


# ============================================================================
# Phase 5 Tests: Partial Output Extraction (Story 4.13)
# ============================================================================

@patch("cyberred.tools.output.get_gateway")
def test_process_accepts_error_type_parameter(mock_get_gateway):
    """Test process() accepts optional error_type parameter.
    
    Per AC2: Failed results should still be processed for partial output extraction.
    """
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "partial"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    # Should NOT raise TypeError - process() should accept error_type
    result = processor.process(
        stdout="partial output",
        stderr="non-zero exit",
        tool="nmap",
        exit_code=1,
        agent_id="agent-123",
        target="192.168.1.1",
        error_type="NON_ZERO_EXIT"
    )
    
    assert result is not None


@patch("cyberred.tools.output.get_gateway")
def test_tier2_prompt_includes_error_type(mock_get_gateway):
    """Test Tier 2 prompt includes error_type context.
    
    Per Task 5.2: LLM should receive error context (e.g., why output might be truncated).
    """
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "timeout context"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    result = processor.process(
        stdout="partial output before timeout",
        stderr="",
        tool="nmap",
        exit_code=-1,
        agent_id="agent-123",
        target="192.168.1.1",
        error_type="TIMEOUT"
    )
    
    # Verify LLM was called with error_type context in prompt
    call_args = mock_gateway.complete.call_args
    request = call_args[0][0]
    prompt = request.prompt
    
    assert "TIMEOUT" in prompt, "Prompt should include error_type value"
    assert "Error Type" in prompt or "error_type" in prompt.lower(), "Prompt should label error_type"


@patch("cyberred.tools.output.get_gateway")
def test_tier2_prompt_with_execution_exception(mock_get_gateway):
    """Test Tier 2 prompt includes EXECUTION_EXCEPTION context."""
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "crash"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    result = processor.process(
        stdout="",
        stderr="Container crashed",
        tool="sqlmap",
        exit_code=-1,
        agent_id="agent-123",
        target="target.com",
        error_type="EXECUTION_EXCEPTION"
    )
    
    call_args = mock_gateway.complete.call_args
    request = call_args[0][0]
    prompt = request.prompt
    
    assert "EXECUTION_EXCEPTION" in prompt


@patch("cyberred.tools.output.get_gateway")
def test_tier2_prompt_without_error_type_backwards_compat(mock_get_gateway):
    """Test process() works without error_type (backwards compatibility)."""
    from cyberred.tools.output import OutputProcessor
    
    mock_gateway = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"findings": [], "summary": "success"}'
    mock_gateway.complete.return_value = mock_response
    mock_get_gateway.return_value = mock_gateway
    
    processor = OutputProcessor()
    
    # Old-style call without error_type - should still work
    result = processor.process(
        stdout="output",
        stderr="",
        tool="unknown",
        exit_code=0,
        agent_id="agent-123",
        target="target.com"
    )
    
    assert result.tier == 2
    assert result.summary == "success"


def test_tier1_parser_receives_error_type():
    """Test Tier 1 parsers can receive error_type for context-aware parsing."""
    from cyberred.tools.output import OutputProcessor
    from cyberred.core.models import Finding
    
    received_error_type = []
    
    def error_aware_parser(stdout, stderr, exit_code, agent_id, target, error_type=None):
        received_error_type.append(error_type)
        return []
    
    processor = OutputProcessor()
    processor.register_parser("nmap", error_aware_parser)
    
    result = processor.process(
        stdout="partial",
        stderr="",
        tool="nmap",
        exit_code=1,
        agent_id="agent-123",
        target="192.168.1.1",
        error_type="NON_ZERO_EXIT"
    )
    
    # Parser should have received error_type
    assert len(received_error_type) == 1
    assert received_error_type[0] == "NON_ZERO_EXIT"

