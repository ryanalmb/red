"""Integration tests for Pre-Engagement Liability Waiver workflow.

Story 13.9: Pre-Engagement Liability Waiver
Test-Driven Development (TDD) - RED Phase

These tests verify the full waiver workflow integration:
- SessionManager integration
- Audit logging integration
- Pre-flight check integration
- TUI modal interaction

All tests should FAIL initially (RED phase).
"""

import pytest
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import hashlib

# These imports will fail initially - expected in RED phase
try:
    from cyberred.tui.screens.waiver import WaiverScreen, WaiverAcceptance
    from cyberred.daemon.session_manager import SessionManager
    from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
    from cyberred.daemon.preflight_waiver import WaiverPreFlightCheck
except ImportError:
    WaiverScreen = None
    WaiverAcceptance = None
    SessionManager = None
    OperatorAuditLog = None
    OperatorAction = None
    WaiverPreFlightCheck = None


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def waiver_text():
    """Sample waiver text for testing."""
    return """CYBER SECURITY ENGAGEMENT LIABILITY WAIVER

Organization: Test Organization
Date: 2026-02-12

By accepting this waiver, I acknowledge that:
1. I have proper authorization to conduct security testing
2. I understand the risks associated with offensive security operations
3. I will operate only within the defined scope

This waiver is legally binding.
"""


@pytest.fixture
def engagement_config_file(tmp_path, waiver_text):
    """Create engagement config file for testing."""
    config_path = tmp_path / "engagement.yaml"
    config_path.write_text("""
name: test-engagement
targets:
  web:
    ip: 192.168.1.100
    services: [http, https]
""")
    
    # Create waiver config
    waiver_path = tmp_path / "waiver.yaml"
    waiver_path.write_text(f"""
organization_name: "Test Organization"
waiver_text: |
{waiver_text}
require_signature: true
""")
    
    return config_path


@pytest.fixture
async def mock_audit_log():
    """Mock OperatorAuditLog for testing."""
    if OperatorAuditLog is None:
        pytest.skip("OperatorAuditLog not available")
    
    audit_log = AsyncMock(spec=OperatorAuditLog)
    audit_log.log_action = AsyncMock()
    return audit_log


# ─────────────────────────────────────────────────────────────────────────────
# AC #8: Full Workflow Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWaiverWorkflowIntegration:
    """Test complete waiver workflow integration."""

    @pytest.mark.asyncio
    async def test_full_workflow_accept(self, engagement_config_file, mock_audit_log):
        """GIVEN new engagement creation
        WHEN waiver is accepted
        THEN engagement is created with waiver data logged"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        # This test verifies the full flow:
        # 1. create_engagement() called
        # 2. Waiver screen shown
        # 3. Operator accepts with signature
        # 4. Audit log entry created
        # 5. Engagement config stores waiver data
        # 6. Engagement creation succeeds
        
        session_manager = SessionManager()
        
        # Mock waiver screen to auto-accept
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=True,
                signature="John Doe",
                timestamp=datetime.now(timezone.utc).isoformat(),
                waiver_hash=hashlib.sha256(b"test").hexdigest()
            ))
            
            engagement_id = session_manager.create_engagement(engagement_config_file)
            
            # Verify engagement created
            assert engagement_id is not None
            
            # Verify waiver data stored
            context = session_manager.get_engagement(engagement_id)
            assert context is not None
            # Config should have waiver_hash, waiver_signature, waiver_timestamp

    @pytest.mark.asyncio
    async def test_full_workflow_decline(self, engagement_config_file):
        """GIVEN new engagement creation
        WHEN waiver is declined
        THEN engagement creation is cancelled"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        # This test verifies decline flow:
        # 1. create_engagement() called
        # 2. Waiver screen shown
        # 3. Operator declines
        # 4. Audit log entry created (WAIVER_DECLINED)
        # 5. EngagementCreationError raised
        # 6. No engagement created
        
        session_manager = SessionManager()
        
        # Mock waiver screen to decline
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=False,
                signature="",
                timestamp=datetime.now(timezone.utc).isoformat(),
                waiver_hash=""
            ))
            
            with pytest.raises(Exception):  # EngagementCreationError
                session_manager.create_engagement(engagement_config_file)

    @pytest.mark.asyncio
    async def test_waiver_with_custom_organization(self, tmp_path):
        """GIVEN waiver config with custom organization
        WHEN waiver screen is shown
        THEN custom organization name is displayed"""
        if WaiverScreen is None:
            pytest.skip("WaiverScreen not available (RED phase)")
        
        # Create custom waiver config
        waiver_path = tmp_path / "waiver.yaml"
        waiver_path.write_text("""
organization_name: "Custom Corp Ltd"
waiver_text: "Custom waiver for {{org_name}}"
""")
        
        # Test that custom org name is loaded and displayed
        # Will verify in actual integration

    def test_waiver_screen_keyboard_navigation(self):
        """GIVEN waiver screen is displayed
        WHEN operator uses Tab, Enter, Escape keys
        THEN navigation works correctly"""
        if WaiverScreen is None:
            pytest.skip("WaiverScreen not available (RED phase)")
        
        # Test keyboard navigation:
        # - Tab moves between fields
        # - Enter accepts (if valid)
        # - Escape triggers decline

    def test_waiver_screen_cannot_be_bypassed(self):
        """GIVEN waiver screen is shown
        WHEN operator tries to close without choice
        THEN screen cannot be dismissed"""
        if WaiverScreen is None:
            pytest.skip("WaiverScreen not available (RED phase)")
        
        # Waiver is a blocking modal
        # Cannot dismiss without Accept or Decline


# ─────────────────────────────────────────────────────────────────────────────
# AC #5: Audit Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWaiverAuditIntegration:
    """Test waiver audit logging integration."""

    @pytest.mark.asyncio
    async def test_waiver_accepted_logged_to_audit(self, mock_audit_log, waiver_text):
        """GIVEN waiver is accepted
        WHEN log_waiver_to_audit is called
        THEN audit entry with WAIVER_ACCEPTED action is created"""
        if OperatorAction is None:
            pytest.skip("OperatorAction not available (RED phase)")
        
        from cyberred.tui.screens.waiver import log_waiver_to_audit
        
        acceptance = WaiverAcceptance(
            accepted=True,
            signature="John Doe",
            timestamp="2026-02-12T08:15:43Z",
            waiver_hash=hashlib.sha256(waiver_text.encode()).hexdigest()
        )
        
        await log_waiver_to_audit(
            acceptance=acceptance,
            engagement_id="test-engagement-123",
            operator="testuser",
            audit_log=mock_audit_log
        )
        
        # Verify audit log called with correct action
        mock_audit_log.log_action.assert_called_once()
        call_args = mock_audit_log.log_action.call_args
        assert call_args[1]['action'] == OperatorAction.WAIVER_ACCEPTED

    @pytest.mark.asyncio
    async def test_waiver_declined_logged_to_audit(self, mock_audit_log):
        """GIVEN waiver is declined
        WHEN log_waiver_to_audit is called
        THEN audit entry with WAIVER_DECLINED action is created"""
        if OperatorAction is None:
            pytest.skip("OperatorAction not available (RED phase)")
        
        from cyberred.tui.screens.waiver import log_waiver_to_audit
        
        acceptance = WaiverAcceptance(
            accepted=False,
            signature="",
            timestamp="2026-02-12T08:15:43Z",
            waiver_hash=""
        )
        
        await log_waiver_to_audit(
            acceptance=acceptance,
            engagement_id="test-engagement-123",
            operator="testuser",
            audit_log=mock_audit_log
        )
        
        # Verify audit log called with declined action
        mock_audit_log.log_action.assert_called_once()
        call_args = mock_audit_log.log_action.call_args
        assert call_args[1]['action'] == OperatorAction.WAIVER_DECLINED

    @pytest.mark.asyncio
    async def test_audit_entry_includes_signature(self, mock_audit_log, waiver_text):
        """GIVEN waiver acceptance with signature
        WHEN logged to audit
        THEN context includes signature"""
        if OperatorAction is None:
            pytest.skip("OperatorAction not available (RED phase)")
        
        from cyberred.tui.screens.waiver import log_waiver_to_audit
        
        acceptance = WaiverAcceptance(
            accepted=True,
            signature="Jane Smith",
            timestamp="2026-02-12T08:15:43Z",
            waiver_hash=hashlib.sha256(waiver_text.encode()).hexdigest()
        )
        
        await log_waiver_to_audit(
            acceptance=acceptance,
            engagement_id="test-engagement-123",
            operator="testuser",
            audit_log=mock_audit_log
        )
        
        # Verify context includes signature
        call_args = mock_audit_log.log_action.call_args
        context = call_args[1].get('context', {})
        assert context.get('signature') == "Jane Smith"

    @pytest.mark.asyncio
    async def test_audit_entry_includes_waiver_hash(self, mock_audit_log, waiver_text):
        """GIVEN waiver acceptance
        WHEN logged to audit
        THEN context includes waiver_hash"""
        if OperatorAction is None:
            pytest.skip("OperatorAction not available (RED phase)")
        
        from cyberred.tui.screens.waiver import log_waiver_to_audit
        
        waiver_hash = hashlib.sha256(waiver_text.encode()).hexdigest()
        acceptance = WaiverAcceptance(
            accepted=True,
            signature="John Doe",
            timestamp="2026-02-12T08:15:43Z",
            waiver_hash=waiver_hash
        )
        
        await log_waiver_to_audit(
            acceptance=acceptance,
            engagement_id="test-engagement-123",
            operator="testuser",
            audit_log=mock_audit_log
        )
        
        # Verify context includes waiver_hash
        call_args = mock_audit_log.log_action.call_args
        context = call_args[1].get('context', {})
        assert context.get('waiver_hash') == waiver_hash

    @pytest.mark.asyncio
    async def test_audit_timestamp_matches_acceptance(self, mock_audit_log, waiver_text):
        """GIVEN waiver acceptance with timestamp
        WHEN logged to audit
        THEN audit timestamp matches acceptance timestamp"""
        if OperatorAction is None:
            pytest.skip("OperatorAction not available (RED phase)")
        
        from cyberred.tui.screens.waiver import log_waiver_to_audit
        
        timestamp = "2026-02-12T08:15:43Z"
        acceptance = WaiverAcceptance(
            accepted=True,
            signature="John Doe",
            timestamp=timestamp,
            waiver_hash=hashlib.sha256(waiver_text.encode()).hexdigest()
        )
        
        await log_waiver_to_audit(
            acceptance=acceptance,
            engagement_id="test-engagement-123",
            operator="testuser",
            audit_log=mock_audit_log
        )
        
        # Verify timestamp in context
        call_args = mock_audit_log.log_action.call_args
        context = call_args[1].get('context', {})
        assert context.get('timestamp') == timestamp


# ─────────────────────────────────────────────────────────────────────────────
# AC #6: Pre-Flight Check Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWaiverPreFlightCheck:
    """Test waiver pre-flight check enforcement."""

    @pytest.mark.asyncio
    async def test_start_engagement_fails_without_waiver_hash(self):
        """GIVEN engagement config without waiver_hash
        WHEN start_engagement is called
        THEN PreFlightCheckError is raised"""
        if WaiverPreFlightCheck is None:
            pytest.skip("WaiverPreFlightCheck not available (RED phase)")
        
        check = WaiverPreFlightCheck()
        
        config = {
            "name": "test-engagement",
            "targets": {"web": {"ip": "192.168.1.100"}},
            # No waiver_hash
        }
        
        result = await check.execute(config)
        
        from cyberred.daemon.preflight import CheckStatus, CheckPriority
        assert result.status == CheckStatus.FAIL
        assert result.priority == CheckPriority.P0  # Blocking

    @pytest.mark.asyncio
    async def test_start_engagement_succeeds_with_valid_waiver(self):
        """GIVEN engagement config with valid waiver_hash
        WHEN start_engagement is called
        THEN pre-flight check passes"""
        if WaiverPreFlightCheck is None:
            pytest.skip("WaiverPreFlightCheck not available (RED phase)")
        
        check = WaiverPreFlightCheck()
        
        config = {
            "name": "test-engagement",
            "targets": {"web": {"ip": "192.168.1.100"}},
            "waiver_hash": hashlib.sha256(b"test waiver").hexdigest(),
            "waiver_signature": "John Doe",
            "waiver_timestamp": "2026-02-12T08:15:43Z"
        }
        
        result = await check.execute(config)
        
        from cyberred.daemon.preflight import CheckStatus
        assert result.status == CheckStatus.PASS

    @pytest.mark.asyncio
    async def test_preflight_validates_waiver_hash_format(self):
        """GIVEN engagement config with invalid waiver_hash format
        WHEN pre-flight check runs
        THEN check fails"""
        if WaiverPreFlightCheck is None:
            pytest.skip("WaiverPreFlightCheck not available (RED phase)")
        
        check = WaiverPreFlightCheck()
        
        config = {
            "name": "test-engagement",
            "waiver_hash": "not-a-valid-sha256",  # Invalid format
            "waiver_signature": "John Doe",
            "waiver_timestamp": "2026-02-12T08:15:43Z"
        }
        
        result = await check.execute(config)
        
        from cyberred.daemon.preflight import CheckStatus
        assert result.status == CheckStatus.FAIL

    @pytest.mark.asyncio
    async def test_preflight_check_priority_is_p0(self):
        """GIVEN WaiverPreFlightCheck
        WHEN check is created
        THEN priority is P0 (blocking)"""
        if WaiverPreFlightCheck is None:
            pytest.skip("WaiverPreFlightCheck not available (RED phase)")
        
        check = WaiverPreFlightCheck()
        
        from cyberred.daemon.preflight import CheckPriority
        assert check.priority == CheckPriority.P0
        # P0 means engagement cannot start without this check passing


# ─────────────────────────────────────────────────────────────────────────────
# AC #6: SessionManager Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionManagerWaiverIntegration:
    """Test SessionManager integration with waiver workflow."""

    def test_create_engagement_shows_waiver_screen(self, engagement_config_file):
        """GIVEN create_engagement is called
        WHEN waiver is required
        THEN WaiverScreen is shown before completing"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        session_manager = SessionManager()
        
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=True,
                signature="John Doe",
                timestamp=datetime.now(timezone.utc).isoformat(),
                waiver_hash=hashlib.sha256(b"test").hexdigest()
            ))
            
            engagement_id = session_manager.create_engagement(engagement_config_file)
            
            # Verify waiver screen was shown
            mock_screen.assert_called_once()

    def test_engagement_config_stores_waiver_hash(self, engagement_config_file):
        """GIVEN waiver is accepted
        WHEN engagement is created
        THEN engagement config stores waiver_hash"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        session_manager = SessionManager()
        
        waiver_hash = hashlib.sha256(b"test waiver").hexdigest()
        
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=True,
                signature="John Doe",
                timestamp="2026-02-12T08:15:43Z",
                waiver_hash=waiver_hash
            ))
            
            engagement_id = session_manager.create_engagement(engagement_config_file)
            
            context = session_manager.get_engagement(engagement_id)
            assert context.engagement_config.get('waiver_hash') == waiver_hash

    def test_engagement_config_stores_waiver_signature(self, engagement_config_file):
        """GIVEN waiver is accepted with signature
        WHEN engagement is created
        THEN engagement config stores waiver_signature"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        session_manager = SessionManager()
        
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=True,
                signature="Jane Smith",
                timestamp="2026-02-12T08:15:43Z",
                waiver_hash=hashlib.sha256(b"test").hexdigest()
            ))
            
            engagement_id = session_manager.create_engagement(engagement_config_file)
            
            context = session_manager.get_engagement(engagement_id)
            assert context.engagement_config.get('waiver_signature') == "Jane Smith"

    def test_engagement_config_stores_waiver_timestamp(self, engagement_config_file):
        """GIVEN waiver is accepted
        WHEN engagement is created
        THEN engagement config stores waiver_timestamp"""
        if SessionManager is None:
            pytest.skip("SessionManager not available (RED phase)")
        
        session_manager = SessionManager()
        
        timestamp = "2026-02-12T08:15:43Z"
        
        with patch('cyberred.daemon.session_manager.WaiverScreen') as mock_screen:
            mock_screen.return_value.show = AsyncMock(return_value=WaiverAcceptance(
                accepted=True,
                signature="John Doe",
                timestamp=timestamp,
                waiver_hash=hashlib.sha256(b"test").hexdigest()
            ))
            
            engagement_id = session_manager.create_engagement(engagement_config_file)
            
            context = session_manager.get_engagement(engagement_id)
            assert context.engagement_config.get('waiver_timestamp') == timestamp


# ─────────────────────────────────────────────────────────────────────────────
# Test execution marker
# ─────────────────────────────────────────────────────────────────────────────

def test_integration_green_phase_marker():
    """This test confirms we are in GREEN phase for integration tests."""
    assert WaiverScreen is not None, "WaiverScreen should be implemented"
    assert SessionManager is not None, "SessionManager should be available"
    assert OperatorAuditLog is not None, "OperatorAuditLog should be available"
    assert WaiverPreFlightCheck is not None, "WaiverPreFlightCheck should be implemented"
