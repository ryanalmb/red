"""Integration tests for Authorization Screen (Story 10.1).

Tests the integration between:
- AuthorizationScreen and CyberRedApp
- Auth request push delivery via SessionManager
- Anomaly bubbling when auth requests arrive
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.streaming import StreamEvent, StreamEventType
from cyberred.tui.screens.authorization import (
    AuthorizationScreen,
    AuthorizationRequest,
    AuthorizationDecision,
)


# ─────────────────────────────────────────────────────────────────────────────
# SessionManager Push Auth Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionManagerAuthPush:
    """Tests for SessionManager.push_auth_request integration."""

    @pytest.fixture
    def session_manager(self) -> SessionManager:
        """Create a SessionManager for testing."""
        return SessionManager(max_engagements=5)

    @pytest.fixture
    def sample_auth_data(self) -> dict:
        """Sample authorization request data."""
        return {
            "id": "auth-test-001",
            "request_type": "lateral_move",
            "agent_id": "recon-001",
            "target": "192.168.1.100",
            "proposed_action": "SSH brute force",
            "risk_level": "HIGH",
            "related_findings": [
                {"finding_id": "f1", "title": "SSH open", "severity": "MEDIUM"}
            ],
            "swarm_snapshot": {
                "total_agents": 10,
                "by_status": {"idle": 5, "scanning": 3, "attacking": 2},
            },
        }

    def test_push_auth_request_no_subscribers(
        self, session_manager: SessionManager, sample_auth_data: dict
    ):
        """Test push_auth_request with no subscribers returns 0."""
        count = session_manager.push_auth_request("nonexistent", sample_auth_data)
        assert count == 0

    def test_push_auth_request_broadcasts_to_subscribers(
        self, session_manager: SessionManager, sample_auth_data: dict, tmp_path
    ):
        """Test push_auth_request broadcasts to all subscribers."""
        # Create a mock engagement config
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("name: test\n")
        
        # Create and start engagement
        engagement_id = session_manager.create_engagement(config_path)
        
        # Mock state machine to allow subscription
        context = session_manager.get_engagement(engagement_id)
        context.state_machine._current_state = context.state_machine._current_state.__class__.RUNNING
        
        # Subscribe two callbacks
        received_events = []
        
        def callback1(event):
            received_events.append(("cb1", event))
        
        def callback2(event):
            received_events.append(("cb2", event))
        
        session_manager.subscribe_to_engagement(engagement_id, callback1)
        session_manager.subscribe_to_engagement(engagement_id, callback2)
        
        # Push auth request
        count = session_manager.push_auth_request(engagement_id, sample_auth_data)
        
        assert count == 2
        assert len(received_events) == 2
        
        # Verify event structure
        for name, event in received_events:
            assert isinstance(event, StreamEvent)
            assert event.event_type == StreamEventType.AUTH_REQUEST
            assert event.data["id"] == "auth-test-001"
            assert event.data["target"] == "192.168.1.100"

    def test_push_auth_request_creates_correct_event_type(
        self, session_manager: SessionManager, sample_auth_data: dict, tmp_path
    ):
        """Test that push_auth_request creates AUTH_REQUEST event type."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("name: test\n")
        
        engagement_id = session_manager.create_engagement(config_path)
        context = session_manager.get_engagement(engagement_id)
        context.state_machine._current_state = context.state_machine._current_state.__class__.RUNNING
        
        captured_event = None
        
        def capture_callback(event):
            nonlocal captured_event
            captured_event = event
        
        session_manager.subscribe_to_engagement(engagement_id, capture_callback)
        session_manager.push_auth_request(engagement_id, sample_auth_data)
        
        assert captured_event is not None
        assert captured_event.event_type == StreamEventType.AUTH_REQUEST
        assert captured_event.timestamp is not None


# ─────────────────────────────────────────────────────────────────────────────
# App Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAppAuthIntegration:
    """Tests for CyberRedApp authorization handling integration."""

    @pytest.fixture
    def sample_auth_data(self) -> dict:
        """Sample authorization request data."""
        return {
            "id": "auth-int-001",
            "request_type": "lateral_move",
            "agent_id": "exploit-001",
            "target": "10.0.0.50",
            "proposed_action": "Lateral movement via SMB",
            "risk_level": "CRITICAL",
            "related_findings": [],
            "swarm_snapshot": {"total_agents": 25, "by_status": {"idle": 10}},
        }

    @pytest.mark.asyncio
    async def test_handle_auth_request_creates_authorization_request(
        self, sample_auth_data: dict
    ):
        """Test that handle_auth_request creates AuthorizationRequest from dict."""
        from cyberred.tui.app import CyberRedApp
        
        # Create app with mock bus
        mock_bus = MagicMock()
        app = CyberRedApp(event_bus=mock_bus)
        
        # Mock required widgets
        mock_log = MagicMock()
        mock_grid = MagicMock()
        mock_status_bar = MagicMock()
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            
            # Mock push_screen to capture the screen
            pushed_screen = None
            def capture_push(screen):
                nonlocal pushed_screen
                pushed_screen = screen
            
            app.push_screen = capture_push
            
            # Call handler
            await app.handle_auth_request(sample_auth_data)
            
            # Verify AuthorizationScreen was pushed
            assert pushed_screen is not None
            assert isinstance(pushed_screen, AuthorizationScreen)
            assert pushed_screen._request.id == "auth-int-001"
            assert pushed_screen._request.target == "10.0.0.50"

    @pytest.mark.asyncio
    async def test_handle_auth_request_updates_agent_status(
        self, sample_auth_data: dict
    ):
        """Test that handle_auth_request updates agent to AUTH_PENDING status."""
        from cyberred.tui.app import CyberRedApp
        
        mock_bus = MagicMock()
        app = CyberRedApp(event_bus=mock_bus)
        
        mock_log = MagicMock()
        mock_grid = MagicMock()
        mock_status_bar = MagicMock()
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            app.push_screen = MagicMock()
            
            await app.handle_auth_request(sample_auth_data)
            
            # Verify agent status was updated to auth_pending
            mock_grid.update_agent.assert_called_once_with("exploit-001", "auth_pending")

    @pytest.mark.asyncio
    async def test_handle_auth_request_increments_pending_count(
        self, sample_auth_data: dict
    ):
        """Test that handle_auth_request increments pending auth count."""
        from cyberred.tui.app import CyberRedApp
        
        mock_bus = MagicMock()
        app = CyberRedApp(event_bus=mock_bus)
        
        mock_log = MagicMock()
        mock_grid = MagicMock()
        mock_status_bar = MagicMock()
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            app.push_screen = MagicMock()
            
            # Initialize pending count
            app._pending_auth_count = 0
            
            await app.handle_auth_request(sample_auth_data)
            
            # Verify count was incremented
            assert app._pending_auth_count == 1
            
            # Verify status bar was updated
            mock_status_bar.update_pending_auth.assert_called_with(1)


# ─────────────────────────────────────────────────────────────────────────────
# Response Callback Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthResponseCallback:
    """Tests for authorization response callback integration."""

    @pytest.mark.asyncio
    async def test_callback_publishes_to_event_bus(self):
        """Test that response callback publishes to event bus."""
        from cyberred.tui.app import CyberRedApp
        
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()
        app = CyberRedApp(event_bus=mock_bus)
        
        mock_log = MagicMock()
        mock_grid = MagicMock()
        mock_status_bar = MagicMock()
        
        sample_data = {
            "id": "auth-cb-001",
            "agent_id": "agent-001",
            "target": "192.168.1.1",
            "proposed_action": "Test",
            "request_type": "lateral_move",
        }
        
        captured_callback = None
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            
            def capture_push(screen):
                nonlocal captured_callback
                captured_callback = screen._callback
            
            app.push_screen = capture_push
            app._pending_auth_count = 0
            
            await app.handle_auth_request(sample_data)
        
        # Call the captured callback with approved response
        assert captured_callback is not None
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            
            await captured_callback({
                "request_id": "auth-cb-001",
                "decision": "APPROVED",
                "approved": True,
                "skipped": False,
                "target": "192.168.1.1",
            })
        
        # Verify event bus was called
        mock_bus.publish.assert_called()
        call_args = mock_bus.publish.call_args
        assert call_args[0][0] == "hitl:auth_response"

    @pytest.mark.asyncio
    async def test_callback_resets_agent_status_after_response(self):
        """Test that response callback resets agent status to active."""
        from cyberred.tui.app import CyberRedApp
        
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()
        app = CyberRedApp(event_bus=mock_bus)
        
        mock_log = MagicMock()
        mock_grid = MagicMock()
        mock_status_bar = MagicMock()
        
        sample_data = {
            "id": "auth-reset-001",
            "agent_id": "agent-reset-001",
            "target": "192.168.1.1",
            "proposed_action": "Test",
            "request_type": "lateral_move",
        }
        
        captured_callback = None
        
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            
            def capture_push(screen):
                nonlocal captured_callback
                captured_callback = screen._callback
            
            app.push_screen = capture_push
            app._pending_auth_count = 1
            
            await app.handle_auth_request(sample_data)
        
        # Reset mock to track new calls
        mock_grid.reset_mock()
        
        # Call callback
        with patch.object(app, "query_one") as mock_query:
            def query_handler(selector, widget_type=None):
                if "kill-chain" in selector:
                    return mock_log
                elif "hive-grid" in selector:
                    return mock_grid
                elif "status-bar" in selector:
                    return mock_status_bar
                raise Exception(f"Unknown query: {selector}")
            
            mock_query.side_effect = query_handler
            
            await captured_callback({
                "approved": True,
                "skipped": False,
            })
        
        # Verify agent status was reset to active
        mock_grid.update_agent.assert_called_once_with("agent-reset-001", "active")


# ─────────────────────────────────────────────────────────────────────────────
# NFR5 Latency Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthDeliveryLatency:
    """Tests for auth request delivery latency (NFR5: <500ms)."""

    @pytest.mark.asyncio
    async def test_push_auth_request_is_synchronous(self):
        """Test that push_auth_request uses synchronous callbacks for low latency."""
        session_manager = SessionManager()
        
        # Verify broadcast_event (called by push_auth_request) is synchronous
        # by checking it doesn't return a coroutine
        result = session_manager.broadcast_event("nonexistent", MagicMock())
        
        # Should be an int (count), not a coroutine
        assert isinstance(result, int)
        assert not asyncio.iscoroutine(result)

    def test_authorization_request_creation_is_fast(self):
        """Test that AuthorizationRequest.from_dict is fast."""
        import time
        
        data = {
            "id": "perf-test",
            "agent_id": "agent-1",
            "target": "192.168.1.1",
            "proposed_action": "Test action",
            "request_type": "lateral_move",
            "risk_level": "HIGH",
            "related_findings": [{"title": f"Finding {i}"} for i in range(10)],
            "swarm_snapshot": {
                "total_agents": 100,
                "by_status": {"idle": 50, "scanning": 30, "attacking": 20},
            },
        }
        
        start = time.perf_counter()
        for _ in range(1000):
            AuthorizationRequest.from_dict(data)
        elapsed = time.perf_counter() - start
        
        # 1000 iterations should complete in <100ms
        assert elapsed < 0.1, f"Creation took {elapsed*1000:.2f}ms for 1000 iterations"
