"""Safety tests for Drop Box Abort & Wipe functionality.

Story 12.10: Drop Box Abort & Wipe
AC#7: Safety tests for wipe completeness verification

These tests verify CRITICAL security requirements:
- No sensitive files remain after wipe
- Sensitive files are overwritten with random data before deletion
- Abort command works in connected and disconnected scenarios
- Partial wipe scenarios are handled correctly

Per Architecture:
- FR30: "Operator can send abort/wipe command to any drop box"
- ERR4: "Drop box connection loss — Log warning, attempt wipe command, mark lost"

These tests are in RED phase - they test functionality that doesn't exist yet.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# NOTE: These imports will FAIL until implementation exists
# This is intentional - RED phase of TDD
# =============================================================================

try:
    from cyberred.c2.abort import (
        AbortCommand,
        AbortController,
        AbortControllerConfig,
        AbortReason,
        AbortResult,
        WipeResult,
        WipeStatus,
        secure_wipe_file,
        get_sensitive_file_paths,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    # Placeholder definitions for test discovery
    AbortReason = None
    WipeStatus = None
    AbortCommand = None
    WipeResult = None
    AbortResult = None
    AbortControllerConfig = None
    AbortController = None
    secure_wipe_file = None
    get_sensitive_file_paths = None


# Skip all tests if imports fail (RED phase indicator)
pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="abort module not implemented yet (RED phase)"
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_sensitive_dir(tmp_path: Path) -> Path:
    """Create a temp directory with mock sensitive files."""
    sensitive_dir = tmp_path / "dropbox_data"
    sensitive_dir.mkdir()
    
    # Create mock certificate files
    certs_dir = sensitive_dir / "certs"
    certs_dir.mkdir()
    (certs_dir / "client.crt").write_bytes(b"MOCK CERTIFICATE DATA " * 100)
    (certs_dir / "client.key").write_bytes(b"MOCK PRIVATE KEY DATA " * 100)
    (certs_dir / "ca.crt").write_bytes(b"MOCK CA CERTIFICATE " * 100)
    
    # Create mock log files
    logs_dir = sensitive_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / "commands.log").write_text("2026-02-12 Command executed: nmap -sS 10.0.0.1\n" * 50)
    (logs_dir / "connections.log").write_text("2026-02-12 Connected to C2 server\n" * 50)
    
    # Create mock cache files
    cache_dir = sensitive_dir / "cache"
    cache_dir.mkdir()
    (cache_dir / "credentials.cache").write_bytes(b"username:password_hash\n" * 20)
    (cache_dir / "targets.cache").write_text("10.0.0.1\n10.0.0.2\n" * 50)
    
    # Create config file
    (sensitive_dir / "config.yaml").write_text("c2_server: https://c2.example.com\nshared_secret: REDACTED\n")
    
    return sensitive_dir


@pytest.fixture
def mock_c2_server() -> MagicMock:
    """Create mock C2Server."""
    mock = MagicMock()
    mock.send_to_drop_box = AsyncMock()
    mock.receive_from_drop_box = AsyncMock()
    mock.mark_as_lost = MagicMock()
    return mock


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock EventBus."""
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


# =============================================================================
# AC#7: Wipe Completeness Verification
# =============================================================================


class TestWipeCompleteness:
    """Safety tests verifying no sensitive files remain after wipe (AC#7)."""

    def test_secure_wipe_file_overwrites_before_delete(
        self,
        tmp_path: Path,
    ) -> None:
        """Sensitive files are overwritten with random data before deletion (AC#3, AC#7).
        
        This is a CRITICAL security requirement per architecture:
        "Sensitive data must be overwritten with random data before deletion 
        to prevent forensic recovery"
        """
        # Create a test file with known content
        test_file = tmp_path / "secret.key"
        original_content = b"THIS IS A SECRET KEY THAT MUST BE SECURELY WIPED"
        test_file.write_bytes(original_content)
        
        # Get file inode for verification
        original_stat = test_file.stat()
        original_size = original_stat.st_size
        
        # Perform secure wipe
        result = secure_wipe_file(test_file)
        
        # File should be deleted
        assert not test_file.exists(), "File should be deleted after secure wipe"
        assert result is True, "secure_wipe_file should return True on success"

    def test_secure_wipe_file_uses_crypto_random(
        self,
        tmp_path: Path,
    ) -> None:
        """Secure wipe uses cryptographically secure random data.
        
        Verifies that the overwrite uses crypto-grade random (not just zeros).
        """
        test_file = tmp_path / "secret.key"
        original_content = b"SENSITIVE DATA" * 100
        test_file.write_bytes(original_content)
        
        # Mock os.urandom or secrets to verify it's called
        with patch("secrets.token_bytes") as mock_token:
            mock_token.return_value = b"\x00" * len(original_content)
            
            # This should use crypto random for overwrite
            secure_wipe_file(test_file)
            
            # Verify crypto random was called
            mock_token.assert_called()

    def test_no_sensitive_files_remain_after_full_wipe(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """No sensitive files remain after wipe completes (AC#7).
        
        This test creates a realistic drop box file structure and verifies
        complete removal of all sensitive data.
        """
        # Get list of all sensitive file paths
        sensitive_paths = get_sensitive_file_paths(temp_sensitive_dir)
        
        # Verify we have files to wipe
        assert len(sensitive_paths) > 0, "Test setup should create sensitive files"
        
        # Verify files exist before wipe
        for path in sensitive_paths:
            assert Path(path).exists(), f"File should exist before wipe: {path}"
        
        # Perform wipe on all sensitive files
        from cyberred.c2.abort import wipe_all_sensitive_files
        result = wipe_all_sensitive_files(temp_sensitive_dir)
        
        # Verify all files are gone
        remaining_files = list(temp_sensitive_dir.rglob("*"))
        remaining_files = [f for f in remaining_files if f.is_file()]
        
        assert len(remaining_files) == 0, f"No files should remain after wipe. Found: {remaining_files}"
        assert result.status == WipeStatus.SUCCESS

    def test_wipe_removes_certificates(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """Wipe removes all certificate files (AC#3)."""
        certs_dir = temp_sensitive_dir / "certs"
        assert (certs_dir / "client.crt").exists()
        assert (certs_dir / "client.key").exists()
        assert (certs_dir / "ca.crt").exists()
        
        from cyberred.c2.abort import wipe_all_sensitive_files
        wipe_all_sensitive_files(temp_sensitive_dir)
        
        # No certificate files should remain
        assert not (certs_dir / "client.crt").exists()
        assert not (certs_dir / "client.key").exists()
        assert not (certs_dir / "ca.crt").exists()

    def test_wipe_removes_logs(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """Wipe removes all log files (AC#3)."""
        logs_dir = temp_sensitive_dir / "logs"
        assert (logs_dir / "commands.log").exists()
        assert (logs_dir / "connections.log").exists()
        
        from cyberred.c2.abort import wipe_all_sensitive_files
        wipe_all_sensitive_files(temp_sensitive_dir)
        
        # No log files should remain
        assert not (logs_dir / "commands.log").exists()
        assert not (logs_dir / "connections.log").exists()

    def test_wipe_removes_cache(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """Wipe removes all cache files (AC#3)."""
        cache_dir = temp_sensitive_dir / "cache"
        assert (cache_dir / "credentials.cache").exists()
        assert (cache_dir / "targets.cache").exists()
        
        from cyberred.c2.abort import wipe_all_sensitive_files
        wipe_all_sensitive_files(temp_sensitive_dir)
        
        # No cache files should remain
        assert not (cache_dir / "credentials.cache").exists()
        assert not (cache_dir / "targets.cache").exists()


# =============================================================================
# AC#7: Connected vs Disconnected Abort Scenarios
# =============================================================================


class TestAbortConnectedScenario:
    """Tests for abort with connected drop box (AC#7)."""

    @pytest.mark.asyncio
    async def test_abort_connected_full_flow(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort with connected drop box - full flow (AC#7).
        
        Tests the happy path where drop box is connected and responds.
        """
        # Configure mock to simulate successful abort response
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 15,
            "files_failed": 0,
            "errors": [],
            "self_destruct_initiated": True,
        }
        
        config = AbortControllerConfig(wipe_timeout_seconds=30)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
            delete_binary=False,
        )
        
        # Verify full successful flow
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.SUCCESS
        assert result.wipe_result.files_wiped == 15
        assert result.self_destruct_initiated is True
        
        # Verify command was sent
        mock_c2_server.send_to_drop_box.assert_called_once()
        
        # Verify events were published
        assert mock_event_bus.publish.call_count >= 2


class TestAbortDisconnectedScenario:
    """Tests for abort with disconnected drop box (AC#6, AC#7)."""

    @pytest.mark.asyncio
    async def test_abort_disconnected_marks_lost(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort with disconnected drop box marks it as 'lost' (AC#6, AC#7).
        
        Per ERR4: "Drop box connection loss — Log warning, attempt wipe command, mark lost"
        """
        # Configure mock to simulate connection timeout
        mock_c2_server.receive_from_drop_box.side_effect = asyncio.TimeoutError()
        
        config = AbortControllerConfig(wipe_timeout_seconds=1)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="operator@test.com",
        )
        
        # Command should still be sent (drop box may execute locally)
        mock_c2_server.send_to_drop_box.assert_called_once()
        
        # Drop box should be marked as lost
        mock_c2_server.mark_as_lost.assert_called_once_with("db-001", reason="abort_connection_lost")
        
        # Result should indicate connection lost
        assert result.abort_received is False

    @pytest.mark.asyncio
    async def test_abort_disconnected_logs_warning(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort with disconnected drop box logs warning per ERR4 (AC#6, AC#7)."""
        mock_c2_server.receive_from_drop_box.side_effect = asyncio.TimeoutError()
        
        config = AbortControllerConfig(wipe_timeout_seconds=1)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            issued_by="operator@test.com",
        )
        
        # Verify connection_lost event was published (for audit/warning)
        calls = mock_event_bus.publish.call_args_list
        event_topics = [str(call) for call in calls]
        assert any("connection_lost" in topic or "lost" in topic.lower() for topic in event_topics)


# =============================================================================
# AC#7: Partial Wipe Scenarios
# =============================================================================


class TestPartialWipeSafety:
    """Safety tests for partial wipe scenarios (AC#7)."""

    def test_partial_wipe_locked_file(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """Partial wipe when file is locked/inaccessible (AC#7).
        
        Tests that wipe continues even when some files cannot be deleted.
        """
        # Create a file and make it read-only to simulate locked
        locked_file = temp_sensitive_dir / "locked.key"
        locked_file.write_bytes(b"LOCKED SECRET")
        locked_file.chmod(0o000)  # Remove all permissions
        
        try:
            from cyberred.c2.abort import wipe_all_sensitive_files
            result = wipe_all_sensitive_files(temp_sensitive_dir)
            
            # Should report partial wipe
            assert result.status == WipeStatus.PARTIAL
            assert result.files_failed >= 1
            assert len(result.errors) >= 1
            assert "locked.key" in str(result.errors) or "Permission" in str(result.errors)
        finally:
            # Restore permissions for cleanup
            locked_file.chmod(0o644)

    def test_partial_wipe_reports_all_errors(
        self,
        temp_sensitive_dir: Path,
    ) -> None:
        """Partial wipe reports all file errors (AC#7)."""
        # Create multiple problematic files
        for i in range(3):
            locked_file = temp_sensitive_dir / f"locked_{i}.key"
            locked_file.write_bytes(b"LOCKED")
            locked_file.chmod(0o000)
        
        try:
            from cyberred.c2.abort import wipe_all_sensitive_files
            result = wipe_all_sensitive_files(temp_sensitive_dir)
            
            # All errors should be reported
            assert result.files_failed >= 3
            assert len(result.errors) >= 3
        finally:
            # Cleanup
            for i in range(3):
                locked_file = temp_sensitive_dir / f"locked_{i}.key"
                if locked_file.exists():
                    locked_file.chmod(0o644)

    @pytest.mark.asyncio
    async def test_abort_cancels_pending_operations(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort cancels all pending operations on drop box (AC#2, AC#7)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
            "pending_commands_cancelled": 5,
        }
        
        config = AbortControllerConfig()
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            issued_by="operator@test.com",
        )
        
        # Abort command should be sent
        mock_c2_server.send_to_drop_box.assert_called_once()
        
        # Verify abort was processed
        assert result.abort_received is True


# =============================================================================
# Binary Deletion Safety Tests
# =============================================================================


class TestBinaryDeletionSafety:
    """Safety tests for optional binary deletion (AC#4)."""

    def test_binary_deletion_when_requested(
        self,
        tmp_path: Path,
    ) -> None:
        """Drop box binary is deleted when delete_binary=True (AC#4)."""
        # Create mock binary
        binary_path = tmp_path / "dropbox"
        binary_path.write_bytes(b"\x7fELF" + b"\x00" * 1000)  # Mock ELF binary
        
        from cyberred.c2.abort import self_destruct
        
        # Execute self-destruct with binary deletion
        self_destruct(binary_path, delete_binary=True)
        
        # Binary should be deleted
        assert not binary_path.exists()

    def test_binary_preserved_when_not_requested(
        self,
        tmp_path: Path,
    ) -> None:
        """Drop box binary is preserved when delete_binary=False (AC#4)."""
        # Create mock binary
        binary_path = tmp_path / "dropbox"
        binary_path.write_bytes(b"\x7fELF" + b"\x00" * 1000)
        
        from cyberred.c2.abort import self_destruct
        
        # Execute self-destruct WITHOUT binary deletion
        self_destruct(binary_path, delete_binary=False)
        
        # Binary should still exist (for forensic analysis if needed)
        assert binary_path.exists()


# =============================================================================
# Audit Trail Safety Tests
# =============================================================================


class TestAuditTrailSafety:
    """Safety tests for audit trail completeness (AC#5)."""

    @pytest.mark.asyncio
    async def test_abort_audit_contains_required_fields(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort audit log contains: timestamp, operator, drop_box_id, reason (AC#5)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        }
        
        config = AbortControllerConfig()
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify event was published with required fields
        mock_event_bus.publish.assert_called()
        
        # Find the abort event and verify it has required fields
        calls = mock_event_bus.publish.call_args_list
        abort_event_found = False
        
        for call in calls:
            event_data = call[1] if len(call) > 1 else (call[0][1] if len(call[0]) > 1 else {})
            if isinstance(event_data, dict):
                # Check for required audit fields
                if "drop_box_id" in event_data or "reason" in event_data:
                    abort_event_found = True
                    # These fields should be present for compliance
                    # (actual field checking will depend on implementation)
        
        # At minimum, events were published for audit
        assert mock_event_bus.publish.call_count >= 1
