"""Unit tests for PreFlightProtocol.

Story 12.9: Pre-Flight Protocol
Tests follow RED-GREEN-REFACTOR TDD cycle.
Coverage target: 100% for preflight.py
"""

from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.c2.preflight import (
    PreFlightConfig,
    PreFlightProtocol,
    PreFlightResult,
    PreFlightStatus,
    PreFlightStep,
    PreFlightStepResult,
    StepStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_config() -> PreFlightConfig:
    """Default pre-flight config (10s timeout)."""
    return PreFlightConfig()


@pytest.fixture
def fast_config() -> PreFlightConfig:
    """Fast config for testing (1s timeout)."""
    return PreFlightConfig(step_timeout_seconds=1)


@pytest.fixture
def mock_c2_server() -> MagicMock:
    """Create mock C2Server with async send/receive methods."""
    mock = MagicMock()
    mock.send_to_drop_box = AsyncMock()
    mock.receive_from_drop_box = AsyncMock()
    return mock


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock EventBus."""
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def protocol(
    default_config: PreFlightConfig,
    mock_c2_server: MagicMock,
    mock_event_bus: MagicMock,
) -> PreFlightProtocol:
    """Create PreFlightProtocol with mocked dependencies."""
    return PreFlightProtocol(
        config=default_config,
        c2_server=mock_c2_server,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def protocol_no_eventbus(
    default_config: PreFlightConfig,
    mock_c2_server: MagicMock,
) -> PreFlightProtocol:
    """Create PreFlightProtocol without EventBus."""
    return PreFlightProtocol(
        config=default_config,
        c2_server=mock_c2_server,
    )


@pytest.fixture
def protocol_no_c2() -> PreFlightProtocol:
    """Create PreFlightProtocol without C2Server."""
    return PreFlightProtocol()


# =============================================================================
# Task 1: Enum Tests (Subtasks 1.1, 1.4)
# =============================================================================


class TestPreFlightStepEnum:
    """Tests for PreFlightStep enum."""

    def test_step_values(self) -> None:
        """PreFlightStep has correct values."""
        assert PreFlightStep.PING.value == "ping"
        assert PreFlightStep.EXEC_TEST.value == "exec_test"
        assert PreFlightStep.STREAM_TEST.value == "stream_test"
        assert PreFlightStep.NET_ENUM.value == "net_enum"
        assert PreFlightStep.READY.value == "ready"

    def test_step_members(self) -> None:
        """PreFlightStep has all 5 expected members."""
        members = list(PreFlightStep)
        assert len(members) == 5
        assert PreFlightStep.PING in members
        assert PreFlightStep.EXEC_TEST in members
        assert PreFlightStep.STREAM_TEST in members
        assert PreFlightStep.NET_ENUM in members
        assert PreFlightStep.READY in members


class TestPreFlightStatusEnum:
    """Tests for PreFlightStatus enum."""

    def test_status_values(self) -> None:
        """PreFlightStatus has correct values."""
        assert PreFlightStatus.READY.value == "ready"
        assert PreFlightStatus.NOT_READY.value == "not_ready"
        assert PreFlightStatus.IN_PROGRESS.value == "in_progress"
        assert PreFlightStatus.NOT_STARTED.value == "not_started"

    def test_status_members(self) -> None:
        """PreFlightStatus has all 4 expected members."""
        members = list(PreFlightStatus)
        assert len(members) == 4


class TestStepStatusEnum:
    """Tests for StepStatus enum."""

    def test_step_status_values(self) -> None:
        """StepStatus has correct values."""
        assert StepStatus.PASS.value == "pass"
        assert StepStatus.FAIL.value == "fail"
        assert StepStatus.TIMEOUT.value == "timeout"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_step_status_members(self) -> None:
        """StepStatus has all 4 expected members."""
        members = list(StepStatus)
        assert len(members) == 4


# =============================================================================
# Task 1: Dataclass Tests (Subtasks 1.2, 1.3)
# =============================================================================


class TestPreFlightStepResult:
    """Tests for PreFlightStepResult dataclass."""

    def test_step_result_defaults(self) -> None:
        """PreFlightStepResult has correct defaults."""
        result = PreFlightStepResult(
            step=PreFlightStep.PING,
            status=StepStatus.PASS,
        )
        assert result.step == PreFlightStep.PING
        assert result.status == StepStatus.PASS
        assert result.duration_ms == 0
        assert result.details == ""
        assert result.error is None

    def test_step_result_custom_values(self) -> None:
        """PreFlightStepResult accepts custom values."""
        result = PreFlightStepResult(
            step=PreFlightStep.EXEC_TEST,
            status=StepStatus.FAIL,
            duration_ms=150,
            details="Command failed",
            error="Connection refused",
        )
        assert result.step == PreFlightStep.EXEC_TEST
        assert result.status == StepStatus.FAIL
        assert result.duration_ms == 150
        assert result.details == "Command failed"
        assert result.error == "Connection refused"

    def test_step_result_timeout(self) -> None:
        """PreFlightStepResult correctly represents timeout."""
        result = PreFlightStepResult(
            step=PreFlightStep.STREAM_TEST,
            status=StepStatus.TIMEOUT,
            duration_ms=10000,
            details="Step timed out after 10s",
            error="Timeout",
        )
        assert result.status == StepStatus.TIMEOUT
        assert result.error == "Timeout"

    def test_step_result_skipped(self) -> None:
        """PreFlightStepResult correctly represents skipped step."""
        result = PreFlightStepResult(
            step=PreFlightStep.NET_ENUM,
            status=StepStatus.SKIPPED,
            details="Skipped due to previous step failure",
        )
        assert result.status == StepStatus.SKIPPED
        assert result.duration_ms == 0


class TestPreFlightResult:
    """Tests for PreFlightResult dataclass."""

    def test_result_defaults(self) -> None:
        """PreFlightResult has correct defaults."""
        result = PreFlightResult(overall_status=PreFlightStatus.NOT_STARTED)
        assert result.overall_status == PreFlightStatus.NOT_STARTED
        assert result.step_results == []
        assert result.total_duration_ms == 0
        assert result.drop_box_id == ""
        assert result.timestamp == ""

    def test_result_ready(self) -> None:
        """PreFlightResult correctly represents READY status."""
        step_results = [
            PreFlightStepResult(step=PreFlightStep.PING, status=StepStatus.PASS, duration_ms=45),
            PreFlightStepResult(step=PreFlightStep.EXEC_TEST, status=StepStatus.PASS, duration_ms=100),
            PreFlightStepResult(step=PreFlightStep.STREAM_TEST, status=StepStatus.PASS, duration_ms=200),
            PreFlightStepResult(step=PreFlightStep.NET_ENUM, status=StepStatus.PASS, duration_ms=300),
        ]
        result = PreFlightResult(
            overall_status=PreFlightStatus.READY,
            step_results=step_results,
            total_duration_ms=645,
            drop_box_id="db-001",
            timestamp="2026-02-10T23:00:00+00:00",
        )
        assert result.overall_status == PreFlightStatus.READY
        assert len(result.step_results) == 4
        assert result.total_duration_ms == 645
        assert result.drop_box_id == "db-001"

    def test_result_not_ready(self) -> None:
        """PreFlightResult correctly represents NOT_READY status."""
        result = PreFlightResult(
            overall_status=PreFlightStatus.NOT_READY,
            step_results=[
                PreFlightStepResult(step=PreFlightStep.PING, status=StepStatus.FAIL, error="No response"),
            ],
            drop_box_id="db-002",
        )
        assert result.overall_status == PreFlightStatus.NOT_READY


class TestPreFlightConfig:
    """Tests for PreFlightConfig dataclass."""

    def test_config_defaults(self) -> None:
        """PreFlightConfig has correct default (10s timeout)."""
        config = PreFlightConfig()
        assert config.step_timeout_seconds == 10

    def test_config_custom(self) -> None:
        """PreFlightConfig accepts custom timeout."""
        config = PreFlightConfig(step_timeout_seconds=5)
        assert config.step_timeout_seconds == 5


# =============================================================================
# Task 2: PreFlightProtocol Initialization Tests (Subtask 2.2)
# =============================================================================


class TestPreFlightProtocolInit:
    """Tests for PreFlightProtocol initialization."""

    def test_init_with_default_config(self) -> None:
        """Protocol initializes with default configuration."""
        protocol = PreFlightProtocol()
        assert protocol.config.step_timeout_seconds == 10
        assert protocol._c2_server is None
        assert protocol._event_bus is None

    def test_init_with_custom_config(self) -> None:
        """Protocol initializes with custom configuration."""
        config = PreFlightConfig(step_timeout_seconds=5)
        protocol = PreFlightProtocol(config=config)
        assert protocol.config.step_timeout_seconds == 5

    def test_init_with_dependencies(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Protocol initializes with injected dependencies."""
        protocol = PreFlightProtocol(
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        assert protocol._c2_server is mock_c2_server
        assert protocol._event_bus is mock_event_bus

    def test_step_sequence_order(self) -> None:
        """STEP_SEQUENCE is in correct deterministic order."""
        expected = [
            PreFlightStep.PING,
            PreFlightStep.EXEC_TEST,
            PreFlightStep.STREAM_TEST,
            PreFlightStep.NET_ENUM,
        ]
        assert expected == PreFlightProtocol.STEP_SEQUENCE

    def test_step_sequence_excludes_ready(self) -> None:
        """READY is not in the executable step sequence."""
        assert PreFlightStep.READY not in PreFlightProtocol.STEP_SEQUENCE


# =============================================================================
# Task 2: Individual Step Executor Tests (Subtasks 2.4-2.7, 2.10)
# =============================================================================


class TestPingStep:
    """Tests for _execute_ping step executor."""

    @pytest.mark.asyncio
    async def test_ping_success(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """PING step passes with valid response."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True}
        result = await protocol._execute_ping("db-001")

        assert result.step == PreFlightStep.PING
        assert result.status == StepStatus.PASS
        assert result.duration_ms >= 0
        assert "RTT:" in result.details
        assert result.error is None
        mock_c2_server.send_to_drop_box.assert_awaited_once_with("db-001", "preflight_ping", {})

    @pytest.mark.asyncio
    async def test_ping_failure_no_response(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """PING step fails when no response received."""
        mock_c2_server.receive_from_drop_box.return_value = None
        result = await protocol._execute_ping("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "No response"

    @pytest.mark.asyncio
    async def test_ping_failure_unsuccessful_response(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """PING step fails when response indicates failure."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": False, "error": "Connection refused"}
        result = await protocol._execute_ping("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_ping_failure_exception(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """PING step fails on exception."""
        mock_c2_server.send_to_drop_box.side_effect = RuntimeError("WebSocket closed")
        result = await protocol._execute_ping("db-001")

        assert result.status == StepStatus.FAIL
        assert "WebSocket closed" in result.error

    @pytest.mark.asyncio
    async def test_ping_failure_no_c2_server(self, protocol_no_c2: PreFlightProtocol) -> None:
        """PING step fails when no C2 server configured."""
        result = await protocol_no_c2._execute_ping("db-001")

        assert result.status == StepStatus.FAIL
        assert "No C2 server configured" in result.error


class TestExecTestStep:
    """Tests for _execute_exec_test step executor."""

    @pytest.mark.asyncio
    async def test_exec_test_success(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step passes with valid output."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "success": True,
            "output": "preflight_test",
        }
        result = await protocol._execute_exec_test("db-001")

        assert result.step == PreFlightStep.EXEC_TEST
        assert result.status == StepStatus.PASS
        assert "preflight_test" in result.details
        mock_c2_server.send_to_drop_box.assert_awaited_once_with(
            "db-001", "preflight_exec", {"command": "echo preflight_test"},
        )

    @pytest.mark.asyncio
    async def test_exec_test_failure_empty_output(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step fails when output is empty."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True, "output": ""}
        result = await protocol._execute_exec_test("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Empty output"

    @pytest.mark.asyncio
    async def test_exec_test_failure_no_response(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step fails when no response received."""
        mock_c2_server.receive_from_drop_box.return_value = None
        result = await protocol._execute_exec_test("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "No response"

    @pytest.mark.asyncio
    async def test_exec_test_failure_unsuccessful(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step fails when response is unsuccessful."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": False, "error": "Permission denied"}
        result = await protocol._execute_exec_test("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Permission denied"

    @pytest.mark.asyncio
    async def test_exec_test_failure_exception(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step fails on exception."""
        mock_c2_server.send_to_drop_box.side_effect = RuntimeError("Send failed")
        result = await protocol._execute_exec_test("db-001")

        assert result.status == StepStatus.FAIL
        assert "Send failed" in result.error

    @pytest.mark.asyncio
    async def test_exec_test_failure_no_c2_server(self, protocol_no_c2: PreFlightProtocol) -> None:
        """EXEC_TEST step fails when no C2 server configured."""
        result = await protocol_no_c2._execute_exec_test("db-001")

        assert result.status == StepStatus.FAIL
        assert "No C2 server configured" in result.error


class TestStreamTestStep:
    """Tests for _execute_stream_test step executor."""

    @pytest.mark.asyncio
    async def test_stream_test_success(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step passes with matching hash."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.return_value = {
            "success": True,
            "hash": expected_hash,
        }
        result = await protocol._execute_stream_test("db-001")

        assert result.step == PreFlightStep.STREAM_TEST
        assert result.status == StepStatus.PASS
        assert "hash match" in result.details

    @pytest.mark.asyncio
    async def test_stream_test_failure_hash_mismatch(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step fails with hash mismatch."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "success": True,
            "hash": "wrong_hash_value",
        }
        result = await protocol._execute_stream_test("db-001")

        assert result.status == StepStatus.FAIL
        assert "hash mismatch" in result.details
        assert "wrong_hash_value" in result.error

    @pytest.mark.asyncio
    async def test_stream_test_failure_no_response(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step fails when no response received."""
        mock_c2_server.receive_from_drop_box.return_value = None
        result = await protocol._execute_stream_test("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "No response"

    @pytest.mark.asyncio
    async def test_stream_test_failure_unsuccessful(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step fails when response is unsuccessful."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": False, "error": "Stream interrupted"}
        result = await protocol._execute_stream_test("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Stream interrupted"

    @pytest.mark.asyncio
    async def test_stream_test_failure_exception(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step fails on exception."""
        mock_c2_server.send_to_drop_box.side_effect = ConnectionError("Lost connection")
        result = await protocol._execute_stream_test("db-001")

        assert result.status == StepStatus.FAIL
        assert "Lost connection" in result.error

    @pytest.mark.asyncio
    async def test_stream_test_failure_no_c2_server(self, protocol_no_c2: PreFlightProtocol) -> None:
        """STREAM_TEST step fails when no C2 server configured."""
        result = await protocol_no_c2._execute_stream_test("db-001")

        assert result.status == StepStatus.FAIL
        assert "No C2 server configured" in result.error

    @pytest.mark.asyncio
    async def test_stream_test_sends_correct_payload(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST sends payload with hash for integrity verification."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()
        mock_c2_server.receive_from_drop_box.return_value = {"success": True, "hash": expected_hash}

        await protocol._execute_stream_test("db-001")

        mock_c2_server.send_to_drop_box.assert_awaited_once_with(
            "db-001",
            "preflight_stream",
            {"payload": test_payload, "expected_hash": expected_hash},
        )


class TestNetEnumStep:
    """Tests for _execute_net_enum step executor."""

    @pytest.mark.asyncio
    async def test_net_enum_success(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step passes with discovered interfaces."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "success": True,
            "interfaces": [
                {"name": "eth0", "ip": "192.168.1.100"},
                {"name": "wlan0", "ip": "10.0.0.50"},
            ],
        }
        result = await protocol._execute_net_enum("db-001")

        assert result.step == PreFlightStep.NET_ENUM
        assert result.status == StepStatus.PASS
        assert "2 interface(s)" in result.details

    @pytest.mark.asyncio
    async def test_net_enum_failure_empty_interfaces(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step fails with empty interface list."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "success": True,
            "interfaces": [],
        }
        result = await protocol._execute_net_enum("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Empty interface list"

    @pytest.mark.asyncio
    async def test_net_enum_failure_no_response(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step fails when no response received."""
        mock_c2_server.receive_from_drop_box.return_value = None
        result = await protocol._execute_net_enum("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "No response"

    @pytest.mark.asyncio
    async def test_net_enum_failure_unsuccessful(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step fails when response is unsuccessful."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": False, "error": "Access denied"}
        result = await protocol._execute_net_enum("db-001")

        assert result.status == StepStatus.FAIL
        assert result.error == "Access denied"

    @pytest.mark.asyncio
    async def test_net_enum_failure_exception(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step fails on exception."""
        mock_c2_server.send_to_drop_box.side_effect = RuntimeError("Timeout")
        result = await protocol._execute_net_enum("db-001")

        assert result.status == StepStatus.FAIL
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_net_enum_failure_no_c2_server(self, protocol_no_c2: PreFlightProtocol) -> None:
        """NET_ENUM step fails when no C2 server configured."""
        result = await protocol_no_c2._execute_net_enum("db-001")

        assert result.status == StepStatus.FAIL
        assert "No C2 server configured" in result.error


# =============================================================================
# Task 2: Timeout Tests (Subtask 2.8)
# =============================================================================


class TestTimeoutHandling:
    """Tests for per-step timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self) -> None:
        """Step that exceeds timeout returns TIMEOUT status."""
        config = PreFlightConfig(step_timeout_seconds=1)
        protocol = PreFlightProtocol(config=config)

        # Mock the step executor itself to simulate a slow step
        async def slow_executor(drop_box_id: str) -> PreFlightStepResult:
            await asyncio.sleep(10)
            return PreFlightStepResult(step=PreFlightStep.PING, status=StepStatus.PASS)

        result = await protocol._execute_with_timeout(
            slow_executor, "db-001", PreFlightStep.PING,
        )

        assert result.status == StepStatus.TIMEOUT
        assert result.step == PreFlightStep.PING
        assert "timed out" in result.details
        assert result.error == "Timeout"

    @pytest.mark.asyncio
    async def test_timeout_duration_recorded(self) -> None:
        """Timeout step records approximate duration."""
        config = PreFlightConfig(step_timeout_seconds=1)
        protocol = PreFlightProtocol(config=config)

        async def slow_executor(drop_box_id: str) -> PreFlightStepResult:
            await asyncio.sleep(10)
            return PreFlightStepResult(step=PreFlightStep.PING, status=StepStatus.PASS)

        result = await protocol._execute_with_timeout(
            slow_executor, "db-001", PreFlightStep.PING,
        )

        # Duration should be approximately the timeout value (1000ms ±500ms)
        assert result.duration_ms >= 500
        assert result.duration_ms <= 3000

    @pytest.mark.asyncio
    async def test_no_timeout_for_fast_step(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """Step that completes quickly does not timeout."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True}

        result = await protocol._execute_with_timeout(
            protocol._execute_ping, "db-001", PreFlightStep.PING,
        )

        assert result.status == StepStatus.PASS


# =============================================================================
# Task 2: Orchestrator Tests (Subtask 2.3, 2.9, 2.11)
# =============================================================================


class TestRunPreflight:
    """Tests for run_preflight orchestrator."""

    @pytest.mark.asyncio
    async def test_full_pass_all_steps(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """Full pre-flight passes when all steps succeed (AC #6)."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        # Configure mock responses for each step
        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},  # PING
            {"success": True, "output": "preflight_test"},  # EXEC_TEST
            {"success": True, "hash": expected_hash},  # STREAM_TEST
            {"success": True, "interfaces": [{"name": "eth0", "ip": "192.168.1.1"}]},  # NET_ENUM
        ]

        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.READY
        assert result.drop_box_id == "db-001"
        assert result.timestamp != ""
        assert result.total_duration_ms >= 0
        assert len(result.step_results) == 4
        assert all(r.status == StepStatus.PASS for r in result.step_results)

    @pytest.mark.asyncio
    async def test_step_order_is_deterministic(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """Steps execute in PING→EXEC_TEST→STREAM_TEST→NET_ENUM order (AC #1)."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},
            {"success": True, "output": "preflight_test"},
            {"success": True, "hash": expected_hash},
            {"success": True, "interfaces": [{"name": "eth0", "ip": "10.0.0.1"}]},
        ]

        result = await protocol.run_preflight("db-001")

        step_order = [r.step for r in result.step_results]
        assert step_order == [
            PreFlightStep.PING,
            PreFlightStep.EXEC_TEST,
            PreFlightStep.STREAM_TEST,
            PreFlightStep.NET_ENUM,
        ]

    @pytest.mark.asyncio
    async def test_fail_fast_on_ping_failure(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """When PING fails, remaining steps are SKIPPED (AC #7)."""
        mock_c2_server.receive_from_drop_box.return_value = None

        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.NOT_READY
        assert result.step_results[0].step == PreFlightStep.PING
        assert result.step_results[0].status == StepStatus.FAIL
        # Remaining steps should be SKIPPED
        assert result.step_results[1].status == StepStatus.SKIPPED
        assert result.step_results[2].status == StepStatus.SKIPPED
        assert result.step_results[3].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_fail_fast_on_exec_test_failure(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """When EXEC_TEST fails after PING passes, remaining steps are SKIPPED."""
        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},  # PING passes
            {"success": False, "error": "Command rejected"},  # EXEC_TEST fails
        ]

        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.NOT_READY
        assert result.step_results[0].status == StepStatus.PASS
        assert result.step_results[1].status == StepStatus.FAIL
        assert result.step_results[2].status == StepStatus.SKIPPED
        assert result.step_results[3].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_fail_fast_on_stream_test_failure(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """When STREAM_TEST fails, NET_ENUM is SKIPPED."""
        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},  # PING passes
            {"success": True, "output": "ok"},  # EXEC_TEST passes
            None,  # STREAM_TEST fails (no response)
        ]

        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.NOT_READY
        assert result.step_results[0].status == StepStatus.PASS
        assert result.step_results[1].status == StepStatus.PASS
        assert result.step_results[2].status == StepStatus.FAIL
        assert result.step_results[3].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_fail_on_net_enum_failure(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """When NET_ENUM fails (last step), result is NOT_READY."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},  # PING
            {"success": True, "output": "ok"},  # EXEC_TEST
            {"success": True, "hash": expected_hash},  # STREAM_TEST
            {"success": False, "error": "Access denied"},  # NET_ENUM fails
        ]

        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.NOT_READY
        assert result.step_results[0].status == StepStatus.PASS
        assert result.step_results[1].status == StepStatus.PASS
        assert result.step_results[2].status == StepStatus.PASS
        assert result.step_results[3].status == StepStatus.FAIL

    @pytest.mark.asyncio
    async def test_timeout_causes_not_ready(self, mock_event_bus: MagicMock) -> None:
        """Timeout on any step causes NOT_READY status."""
        config = PreFlightConfig(step_timeout_seconds=1)
        protocol = PreFlightProtocol(config=config, event_bus=mock_event_bus)

        # Patch the PING executor to be slow so _execute_with_timeout triggers TimeoutError
        async def slow_ping(drop_box_id: str) -> PreFlightStepResult:
            await asyncio.sleep(10)
            return PreFlightStepResult(step=PreFlightStep.PING, status=StepStatus.PASS)

        protocol._execute_ping = slow_ping  # type: ignore[assignment]
        result = await protocol.run_preflight("db-001")

        assert result.overall_status == PreFlightStatus.NOT_READY
        assert result.step_results[0].status == StepStatus.TIMEOUT
        # Remaining skipped after timeout
        assert result.step_results[1].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_run_preflight_records_total_duration(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """run_preflight records total duration of the sequence."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},
            {"success": True, "output": "ok"},
            {"success": True, "hash": expected_hash},
            {"success": True, "interfaces": [{"name": "lo"}]},
        ]

        result = await protocol.run_preflight("db-001")

        assert result.total_duration_ms >= 0


# =============================================================================
# Task 4: EventBus Integration Tests (Subtasks 4.1-4.4)
# =============================================================================


class TestEventBusIntegration:
    """Tests for EventBus event publishing."""

    @pytest.mark.asyncio
    async def test_started_event_published(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """c2.preflight.started event is published (Task 4.1)."""
        mock_c2_server.receive_from_drop_box.return_value = None  # PING fails, that's ok

        await protocol.run_preflight("db-001")

        # Find the started event call
        started_calls = [
            call for call in mock_event_bus.publish.call_args_list
            if call[0][0] == "c2:preflight:started"
        ]
        assert len(started_calls) == 1
        assert started_calls[0][0][1]["drop_box_id"] == "db-001"

    @pytest.mark.asyncio
    async def test_step_completed_events_published(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """c2.preflight.step_completed event published after each step (Task 4.2)."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},
            {"success": True, "output": "ok"},
            {"success": True, "hash": expected_hash},
            {"success": True, "interfaces": [{"name": "eth0"}]},
        ]

        await protocol.run_preflight("db-001")

        step_completed_calls = [
            call for call in mock_event_bus.publish.call_args_list
            if call[0][0] == "c2:preflight:step_completed"
        ]
        assert len(step_completed_calls) == 4

    @pytest.mark.asyncio
    async def test_completed_event_published(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """c2.preflight.completed event is published with result (Task 4.3)."""
        mock_c2_server.receive_from_drop_box.return_value = None

        await protocol.run_preflight("db-001")

        completed_calls = [
            call for call in mock_event_bus.publish.call_args_list
            if call[0][0] == "c2:preflight:completed"
        ]
        assert len(completed_calls) == 1
        assert completed_calls[0][0][1]["overall_status"] == "not_ready"

    @pytest.mark.asyncio
    async def test_completed_event_ready_status(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """c2.preflight.completed event has 'ready' status on full pass."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

        mock_c2_server.receive_from_drop_box.side_effect = [
            {"success": True},
            {"success": True, "output": "ok"},
            {"success": True, "hash": expected_hash},
            {"success": True, "interfaces": [{"name": "eth0"}]},
        ]

        await protocol.run_preflight("db-001")

        completed_calls = [
            call for call in mock_event_bus.publish.call_args_list
            if call[0][0] == "c2:preflight:completed"
        ]
        assert completed_calls[0][0][1]["overall_status"] == "ready"

    @pytest.mark.asyncio
    async def test_no_events_without_eventbus(self, protocol_no_eventbus: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """No events published when EventBus is not configured."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True}
        # Should not raise even without EventBus
        await protocol_no_eventbus.run_preflight("db-001")

    @pytest.mark.asyncio
    async def test_event_publish_failure_does_not_break_preflight(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """EventBus publish failure does not break pre-flight execution."""
        mock_event_bus.publish.side_effect = RuntimeError("EventBus down")
        mock_c2_server.receive_from_drop_box.return_value = None

        # Should not raise
        result = await protocol.run_preflight("db-001")
        assert result.overall_status == PreFlightStatus.NOT_READY

    @pytest.mark.asyncio
    async def test_step_completed_event_on_skipped_steps(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock, mock_event_bus: MagicMock) -> None:
        """Skipped steps do NOT publish step_completed events (only executed steps do)."""
        mock_c2_server.receive_from_drop_box.return_value = None  # PING fails

        await protocol.run_preflight("db-001")

        step_completed_calls = [
            call for call in mock_event_bus.publish.call_args_list
            if call[0][0] == "c2:preflight:step_completed"
        ]
        # Only PING step completes (with FAIL), other 3 are SKIPPED (no event)
        assert len(step_completed_calls) == 1
        assert step_completed_calls[0][0][1]["step"] == "ping"


# =============================================================================
# Task 3: C2 Message Integration Tests (Subtasks 3.1-3.4)
# =============================================================================


class TestC2MessageIntegration:
    """Tests for C2 command/response message construction."""

    @pytest.mark.asyncio
    async def test_ping_sends_preflight_ping_command(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """PING step sends 'preflight_ping' command."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True}
        await protocol._execute_ping("db-001")

        mock_c2_server.send_to_drop_box.assert_awaited_once_with("db-001", "preflight_ping", {})

    @pytest.mark.asyncio
    async def test_exec_sends_preflight_exec_command(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """EXEC_TEST step sends 'preflight_exec' command with echo."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True, "output": "ok"}
        await protocol._execute_exec_test("db-001")

        mock_c2_server.send_to_drop_box.assert_awaited_once_with(
            "db-001", "preflight_exec", {"command": "echo preflight_test"},
        )

    @pytest.mark.asyncio
    async def test_stream_sends_preflight_stream_command(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """STREAM_TEST step sends 'preflight_stream' command with payload and hash."""
        test_payload = "preflight_stream_integrity_test_data"
        expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()
        mock_c2_server.receive_from_drop_box.return_value = {"success": True, "hash": expected_hash}

        await protocol._execute_stream_test("db-001")

        mock_c2_server.send_to_drop_box.assert_awaited_once_with(
            "db-001", "preflight_stream",
            {"payload": test_payload, "expected_hash": expected_hash},
        )

    @pytest.mark.asyncio
    async def test_net_enum_sends_preflight_net_enum_command(self, protocol: PreFlightProtocol, mock_c2_server: MagicMock) -> None:
        """NET_ENUM step sends 'preflight_net_enum' command."""
        mock_c2_server.receive_from_drop_box.return_value = {"success": True, "interfaces": [{"name": "eth0"}]}
        await protocol._execute_net_enum("db-001")

        mock_c2_server.send_to_drop_box.assert_awaited_once_with("db-001", "preflight_net_enum", {})

    @pytest.mark.asyncio
    async def test_send_command_raises_without_c2(self, protocol_no_c2: PreFlightProtocol) -> None:
        """_send_command raises RuntimeError without C2 server."""
        with pytest.raises(RuntimeError, match="No C2 server configured"):
            await protocol_no_c2._send_command("db-001", "test", {})

    @pytest.mark.asyncio
    async def test_receive_response_raises_without_c2(self, protocol_no_c2: PreFlightProtocol) -> None:
        """_receive_response raises RuntimeError without C2 server."""
        with pytest.raises(RuntimeError, match="No C2 server configured"):
            await protocol_no_c2._receive_response("db-001", "test")
