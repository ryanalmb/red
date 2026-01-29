"""Unit tests for External Notification System.

Story 10.9: External Authorization Notification

RED Phase: These tests should FAIL until the implementation is complete.
Tests cover:
- ExternalNotificationConfig dataclass
- NotificationPayload dataclass  
- ExternalNotifier class
- Webhook delivery
- Email delivery
- Retry logic
- TUI presence detection
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# ExternalNotificationConfig Tests (AC: #1, #2)
# =============================================================================


class TestExternalNotificationConfig:
    """Tests for ExternalNotificationConfig dataclass."""

    def test_init_with_webhook_url(self) -> None:
        """Test initialization with webhook URL only."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(webhook_url="https://hooks.example.com/cyberred")

        assert config.webhook_url == "https://hooks.example.com/cyberred"
        assert config.email is None

    def test_init_with_email(self) -> None:
        """Test initialization with email only."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(email="operator@example.com")

        assert config.email == "operator@example.com"
        assert config.webhook_url is None

    def test_init_with_both_webhook_and_email(self) -> None:
        """Test initialization with both webhook and email."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            email="operator@example.com",
        )

        assert config.webhook_url == "https://hooks.example.com/cyberred"
        assert config.email == "operator@example.com"

    def test_default_notification_delay(self) -> None:
        """Test that default notification delay is 5 minutes."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(webhook_url="https://example.com/hook")

        assert config.notification_delay == timedelta(minutes=5)

    def test_notification_delay_minimum_validation(self) -> None:
        """Test that notification delay below 1 minute raises ConfigurationError."""
        from cyberred.core.exceptions import ConfigurationError
        from cyberred.core.notifications import ExternalNotificationConfig

        with pytest.raises(ConfigurationError) as exc_info:
            ExternalNotificationConfig(
                webhook_url="https://example.com/hook",
                notification_delay=timedelta(seconds=30),  # Below 1 min minimum
            )

        assert "notification_delay" in str(exc_info.value)

    def test_notification_delay_maximum_validation(self) -> None:
        """Test that notification delay above 60 minutes raises ConfigurationError."""
        from cyberred.core.exceptions import ConfigurationError
        from cyberred.core.notifications import ExternalNotificationConfig

        with pytest.raises(ConfigurationError) as exc_info:
            ExternalNotificationConfig(
                webhook_url="https://example.com/hook",
                notification_delay=timedelta(minutes=61),  # Above 60 min maximum
            )

        assert "notification_delay" in str(exc_info.value)

    def test_notification_delay_at_minimum_boundary(self) -> None:
        """Test that exactly 1 minute delay is valid."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            webhook_url="https://example.com/hook",
            notification_delay=timedelta(minutes=1),
        )

        assert config.notification_delay == timedelta(minutes=1)

    def test_notification_delay_at_maximum_boundary(self) -> None:
        """Test that exactly 60 minutes delay is valid."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            webhook_url="https://example.com/hook",
            notification_delay=timedelta(minutes=60),
        )

        assert config.notification_delay == timedelta(minutes=60)

    def test_invalid_webhook_url_format_raises(self) -> None:
        """Test that invalid webhook URL format raises ConfigurationError."""
        from cyberred.core.exceptions import ConfigurationError
        from cyberred.core.notifications import ExternalNotificationConfig

        with pytest.raises(ConfigurationError) as exc_info:
            ExternalNotificationConfig(webhook_url="not-a-valid-url")

        assert "webhook_url" in str(exc_info.value)

    def test_invalid_email_format_raises(self) -> None:
        """Test that invalid email format raises ConfigurationError."""
        from cyberred.core.exceptions import ConfigurationError
        from cyberred.core.notifications import ExternalNotificationConfig

        with pytest.raises(ConfigurationError) as exc_info:
            ExternalNotificationConfig(email="not-a-valid-email")

        assert "email" in str(exc_info.value)

    def test_default_smtp_settings(self) -> None:
        """Test default SMTP settings."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(email="operator@example.com")

        assert config.smtp_host == "localhost"
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True
        assert config.smtp_username is None
        assert config.smtp_password is None

    def test_custom_smtp_settings(self) -> None:
        """Test custom SMTP settings."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            email="operator@example.com",
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_use_tls=True,
            smtp_username="alerts@example.com",
            smtp_password="secret123",
        )

        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.smtp_username == "alerts@example.com"
        assert config.smtp_password == "secret123"

    def test_is_configured_with_webhook(self) -> None:
        """Test is_configured returns True when webhook is set."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(webhook_url="https://example.com/hook")

        assert config.is_configured is True

    def test_is_configured_with_email(self) -> None:
        """Test is_configured returns True when email is set."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(email="operator@example.com")

        assert config.is_configured is True

    def test_is_configured_with_neither(self) -> None:
        """Test is_configured returns False when nothing is configured."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig()

        assert config.is_configured is False


class TestExternalNotificationConfigFromDict:
    """Tests for ExternalNotificationConfig.from_dict() factory method."""

    def test_from_dict_basic(self) -> None:
        """Test creating config from dictionary."""
        from cyberred.core.notifications import ExternalNotificationConfig

        data = {
            "webhook_url": "https://hooks.example.com/cyberred",
        }

        config = ExternalNotificationConfig.from_dict(data)

        assert config.webhook_url == "https://hooks.example.com/cyberred"
        assert config.notification_delay == timedelta(minutes=5)

    def test_from_dict_invalid_duration_raises(self) -> None:
        """Test that invalid duration format raises ConfigurationError."""
        from cyberred.core.exceptions import ConfigurationError
        from cyberred.core.notifications import ExternalNotificationConfig

        data = {
            "webhook_url": "https://hooks.example.com/cyberred",
            "notification_delay": "invalid_duration",
        }

        with pytest.raises(ConfigurationError) as exc_info:
            ExternalNotificationConfig.from_dict(data)

        # Check key is set correctly in exception
        assert exc_info.value.key == "notification_delay"

    def test_from_dict_with_notification_delay_string(self) -> None:
        """Test parsing notification delay from string (e.g., '10m')."""
        from cyberred.core.notifications import ExternalNotificationConfig

        data = {
            "webhook_url": "https://example.com/hook",
            "notification_delay": "10m",
        }

        config = ExternalNotificationConfig.from_dict(data)

        assert config.notification_delay == timedelta(minutes=10)

    def test_from_dict_full_config(self) -> None:
        """Test parsing full configuration."""
        from cyberred.core.notifications import ExternalNotificationConfig

        data = {
            "webhook_url": "https://hooks.example.com/cyberred",
            "email": "operator@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_use_tls": True,
            "smtp_username": "alerts@example.com",
            "smtp_password": "secret123",
            "notification_delay": "15m",
        }

        config = ExternalNotificationConfig.from_dict(data)

        assert config.webhook_url == "https://hooks.example.com/cyberred"
        assert config.email == "operator@example.com"
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_port == 465
        assert config.smtp_use_tls is True
        assert config.smtp_username == "alerts@example.com"
        assert config.smtp_password == "secret123"
        assert config.notification_delay == timedelta(minutes=15)


class TestExternalNotificationConfigToDict:
    """Tests for ExternalNotificationConfig.to_dict() serialization."""

    def test_to_dict_basic(self) -> None:
        """Test serializing config to dictionary."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            webhook_url="https://example.com/hook",
            notification_delay=timedelta(minutes=10),
        )

        data = config.to_dict()

        assert data["webhook_url"] == "https://example.com/hook"
        assert "notification_delay" in data

    def test_to_dict_roundtrip(self) -> None:
        """Test that to_dict() output can be used with from_dict()."""
        from cyberred.core.notifications import ExternalNotificationConfig

        original = ExternalNotificationConfig(
            webhook_url="https://example.com/hook",
            email="operator@example.com",
            notification_delay=timedelta(minutes=15),
        )

        data = original.to_dict()
        restored = ExternalNotificationConfig.from_dict(data)

        assert restored.webhook_url == original.webhook_url
        assert restored.email == original.email
        assert restored.notification_delay == original.notification_delay


# =============================================================================
# NotificationPayload Tests (AC: #1)
# =============================================================================


class TestNotificationPayload:
    """Tests for NotificationPayload dataclass."""

    def test_init_with_required_fields(self) -> None:
        """Test initialization with required fields."""
        from cyberred.core.notifications import NotificationPayload

        payload = NotificationPayload(
            engagement_id="eng-uuid-123",
            request_id="req-uuid-456",
            request_type="lateral_movement",
            target="192.168.1.100",
            urgency="high",
        )

        assert payload.engagement_id == "eng-uuid-123"
        assert payload.request_id == "req-uuid-456"
        assert payload.request_type == "lateral_movement"
        assert payload.target == "192.168.1.100"
        assert payload.urgency == "high"

    def test_init_with_all_fields(self) -> None:
        """Test initialization with all fields including optional."""
        from cyberred.core.notifications import NotificationPayload

        pending_since = datetime.now(timezone.utc)
        context = {"source_agent": "exploit-agent-3", "action": "ssh_pivot"}

        payload = NotificationPayload(
            engagement_id="eng-uuid-123",
            request_id="req-uuid-456",
            request_type="lateral_movement",
            target="192.168.1.100",
            urgency="high",
            pending_since=pending_since,
            response_url="https://cyberred.local/api/v1/auth/respond/token",
            context=context,
        )

        assert payload.pending_since == pending_since
        assert payload.response_url == "https://cyberred.local/api/v1/auth/respond/token"
        assert payload.context == context

    def test_to_dict(self) -> None:
        """Test to_dict() serialization."""
        from cyberred.core.notifications import NotificationPayload

        pending_since = datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        payload = NotificationPayload(
            engagement_id="eng-uuid-123",
            request_id="req-uuid-456",
            request_type="lateral_movement",
            target="192.168.1.100",
            urgency="high",
            pending_since=pending_since,
            response_url="https://cyberred.local/api/v1/auth/respond/token",
            context={"action": "ssh_pivot"},
        )

        data = payload.to_dict()

        assert data["engagement_id"] == "eng-uuid-123"
        assert data["request_id"] == "req-uuid-456"
        assert data["request_type"] == "lateral_movement"
        assert data["target"] == "192.168.1.100"
        assert data["urgency"] == "high"
        assert "pending_since" in data
        assert data["response_url"] == "https://cyberred.local/api/v1/auth/respond/token"
        assert data["context"] == {"action": "ssh_pivot"}

    def test_to_dict_without_optional_fields(self) -> None:
        """Test to_dict() with only required fields."""
        from cyberred.core.notifications import NotificationPayload

        payload = NotificationPayload(
            engagement_id="eng-uuid-123",
            request_id="req-uuid-456",
            request_type="lateral_movement",
            target="192.168.1.100",
            urgency="high",
        )

        data = payload.to_dict()

        assert data["engagement_id"] == "eng-uuid-123"
        assert data["request_id"] == "req-uuid-456"
        assert "pending_since" not in data
        assert "response_url" not in data
        assert "context" not in data


# =============================================================================
# ExternalNotifier Tests (AC: #1, #2, #5)
# =============================================================================


class TestExternalNotifier:
    """Tests for ExternalNotifier class."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            email="operator@example.com",
            notification_delay=timedelta(minutes=1),  # Minimum valid delay
        )

    @pytest.fixture
    def mock_daemon_state(self) -> MagicMock:
        """Create mock daemon state."""
        state = MagicMock()
        state.is_tui_attached = False
        return state

    @pytest.fixture
    def mock_audit_logger(self) -> AsyncMock:
        """Create mock audit logger."""
        logger = AsyncMock()
        logger.log_notification_sent = AsyncMock()
        logger.log_notification_retry = AsyncMock()
        logger.log_notification_failed = AsyncMock()
        return logger

    def test_init_with_config(self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock) -> None:
        """Test ExternalNotifier initialization with config."""
        from cyberred.core.notifications import ExternalNotifier

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        assert notifier._config == mock_config
        assert notifier._daemon_state == mock_daemon_state

    @pytest.mark.asyncio
    async def test_schedule_notification(self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock) -> None:
        """Test schedule_notification schedules delayed notification."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state.is_tui_attached = False

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await notifier.schedule_notification("req-123", request)

        # Should have a pending notification
        pending = notifier.get_pending_notifications()
        assert "req-123" in pending

        # Cleanup
        await notifier.cancel_notification("req-123")

    @pytest.mark.asyncio
    async def test_cancel_notification(self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock) -> None:
        """Test cancel_notification cancels pending notification."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state.is_tui_attached = False

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await notifier.schedule_notification("req-123", request)
        await notifier.cancel_notification("req-123")

        # Should not have pending notification
        pending = notifier.get_pending_notifications()
        assert "req-123" not in pending

    @pytest.mark.asyncio
    async def test_notification_suppressed_when_tui_attached(
        self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock
    ) -> None:
        """Test notification suppressed when TUI is attached (AC: #5)."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state.is_tui_attached = True  # TUI is attached

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await notifier.schedule_notification("req-123", request)

        # Should NOT have a pending notification because TUI is attached
        pending = notifier.get_pending_notifications()
        assert "req-123" not in pending

    def test_build_notification_payload(self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock) -> None:
        """Test _build_notification_payload creates correct payload."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-uuid-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=["Discovered new subnet"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        payload = notifier._build_notification_payload(request)

        assert payload["engagement_id"] == "eng-uuid-123"
        assert payload["request_id"] == "req-123"
        assert payload["request_type"] == "lateral_movement"
        assert payload["target"] == "192.168.1.100"
        assert payload["urgency"] == "high"  # Mapped from risk_level
        assert "response_url" in payload
        assert "pending_since" in payload

    def test_get_pending_notifications(self, mock_config: Any, mock_daemon_state: MagicMock, mock_audit_logger: AsyncMock) -> None:
        """Test get_pending_notifications returns scheduled notifications."""
        from cyberred.core.notifications import ExternalNotifier

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        # Initially empty
        pending = notifier.get_pending_notifications()
        assert len(pending) == 0


# =============================================================================
# Webhook Delivery Tests (AC: #1, #3)
# =============================================================================


class TestWebhookDelivery:
    """Tests for webhook delivery functionality."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=5),
        )

    @pytest.mark.asyncio
    async def test_send_webhook_makes_http_post(self, mock_config: Any) -> None:
        """Test _send_webhook makes HTTP POST to configured URL."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {
            "engagement_id": "eng-123",
            "request_id": "req-456",
            "request_type": "lateral_movement",
            "target": "192.168.1.100",
            "urgency": "high",
        }

        with patch.object(notifier, "_http_client") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await notifier._send_webhook(payload)

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://hooks.example.com/cyberred"
            assert result is True

    @pytest.mark.asyncio
    async def test_webhook_uses_correct_content_type(self, mock_config: Any) -> None:
        """Test webhook uses correct Content-Type header."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        with patch.object(notifier, "_http_client") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            await notifier._send_webhook(payload)

            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs.get("headers", {}).get("Content-Type") == "application/json"

    @pytest.mark.asyncio
    async def test_webhook_includes_hmac_signature(self, mock_config: Any) -> None:
        """Test webhook includes HMAC signature header for verification."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()
        signing_key = b"test-signing-key"

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=signing_key,
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        with patch.object(notifier, "_http_client") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            await notifier._send_webhook(payload)

            call_kwargs = mock_client.post.call_args[1]
            headers = call_kwargs.get("headers", {})
            assert "X-Cyberred-Signature" in headers
            assert headers["X-Cyberred-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_webhook_failure_returns_false(self, mock_config: Any) -> None:
        """Test webhook failure returns False."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        with patch.object(notifier, "_http_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("Connection failed"))

            result = await notifier._send_webhook(payload)

            assert result is False


# =============================================================================
# Email Delivery Tests (AC: #2, #4)
# =============================================================================


class TestEmailDelivery:
    """Tests for email delivery functionality."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig with email."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            email="operator@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_use_tls=True,
            smtp_username="alerts@example.com",
            smtp_password="secret123",
            notification_delay=timedelta(minutes=5),
        )

    @pytest.mark.asyncio
    async def test_send_email_success(self, mock_config: Any) -> None:
        """Test _send_email sends email successfully."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {
            "engagement_id": "eng-123",
            "request_id": "req-456",
            "request_type": "lateral_movement",
            "target": "192.168.1.100",
            "urgency": "high",
            "pending_since": "2026-01-15T14:00:00Z",
            "response_url": "https://cyberred.local/api/v1/auth/respond/token",
        }

        with patch("cyberred.core.notifications.smtplib") as mock_smtplib:
            mock_smtp = MagicMock()
            mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

            result = await notifier._send_email(payload)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_email_failure_returns_false(self, mock_config: Any) -> None:
        """Test _send_email returns False on failure."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        with patch("cyberred.core.notifications.smtplib") as mock_smtplib:
            mock_smtplib.SMTP.side_effect = Exception("SMTP connection failed")

            result = await notifier._send_email(payload)

            assert result is False


# =============================================================================
# Retry Logic Tests (AC: #3, #4)
# =============================================================================


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=5),
        )

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, mock_config: Any) -> None:
        """Test exponential backoff timing (1s, 2s, 4s)."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        call_count = 0
        delays: list[float] = []

        async def failing_send(payload: dict) -> bool:
            nonlocal call_count
            call_count += 1
            raise Exception("Simulated failure")

        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            # Don't actually sleep in tests

        with patch("asyncio.sleep", mock_sleep):
            result = await notifier._send_with_retry(
                failing_send, {"request_id": "req-123"}, "webhook"
            )

        assert result is False
        # Should have delays of 1s, 2s (3 attempts total, 2 retries with delays)
        assert len(delays) == 2
        assert delays[0] == 1.0
        assert delays[1] == 2.0

    @pytest.mark.asyncio
    async def test_max_3_retry_attempts(self, mock_config: Any) -> None:
        """Test max 3 retry attempts."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        call_count = 0

        async def failing_send(payload: dict) -> bool:
            nonlocal call_count
            call_count += 1
            raise Exception("Simulated failure")

        with patch("asyncio.sleep", AsyncMock()):
            await notifier._send_with_retry(
                failing_send, {"request_id": "req-123"}, "webhook"
            )

        assert call_count == 3  # Max 3 attempts

    @pytest.mark.asyncio
    async def test_successful_retry_after_initial_failure(self, mock_config: Any) -> None:
        """Test successful retry after initial failure."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        call_count = 0

        async def eventually_succeeds(payload: dict) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("First attempt fails")
            return True

        with patch("asyncio.sleep", AsyncMock()):
            result = await notifier._send_with_retry(
                eventually_succeeds, {"request_id": "req-123"}, "webhook"
            )

        assert result is True
        assert call_count == 2  # First failure, second success

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_logs_failure(self, mock_config: Any) -> None:
        """Test all retries exhausted logs final failure."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        async def always_fails(payload: dict) -> bool:
            raise Exception("Always fails")

        with patch("asyncio.sleep", AsyncMock()):
            await notifier._send_with_retry(
                always_fails, {"request_id": "req-123"}, "webhook"
            )

        # Should have logged final failure
        mock_audit_logger.log_notification_failed.assert_called_once()


# =============================================================================
# TUI Presence Detection Tests (AC: #5, #6)
# =============================================================================


class TestTUIPresenceDetection:
    """Tests for TUI presence detection behavior."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=1),  # Minimum valid delay
        )

    @pytest.mark.asyncio
    async def test_tui_reattach_cancels_pending_notifications(self, mock_config: Any) -> None:
        """Test TUI reattach cancels pending notifications."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await notifier.schedule_notification("req-123", request)

        # Simulate TUI reattach - should cancel pending notifications
        await notifier.on_tui_attached()

        pending = notifier.get_pending_notifications()
        assert "req-123" not in pending

    @pytest.mark.asyncio
    async def test_notification_cancelled_when_request_resolved(self, mock_config: Any) -> None:
        """Test notification cancelled when request is resolved (AC: #6)."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        await notifier.schedule_notification("req-123", request)

        # Simulate request resolved
        await notifier.cancel_notification("req-123")

        pending = notifier.get_pending_notifications()
        assert "req-123" not in pending

    @pytest.mark.asyncio
    async def test_cancel_all_notifications(self, mock_config: Any) -> None:
        """Test cancel_all_notifications cancels all pending."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        for i in range(3):
            request = AuthorizationRequest(
                id=f"req-{i}",
                request_type="lateral_movement",
                agent_id="agent-1",
                target="192.168.1.100",
                proposed_action="ssh_pivot",
                risk_level="high",
                related_findings=[],
                decision_context=[],
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            await notifier.schedule_notification(f"req-{i}", request)

        # Should have 3 pending notifications
        assert len(notifier.get_pending_notifications()) == 3

        await notifier.cancel_all_notifications()

        pending = notifier.get_pending_notifications()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_notifier_close(self, mock_config: Any) -> None:
        """Test ExternalNotifier close() method."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        # Close should not raise
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_email_with_retry_success(self, mock_config: Any) -> None:
        """Test _send_email_with_retry method."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        # Config with email
        email_config = ExternalNotificationConfig(
            email="operator@example.com",
            notification_delay=timedelta(minutes=5),
        )

        notifier = ExternalNotifier(
            config=email_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456", "urgency": "high"}

        with patch("cyberred.core.notifications.smtplib") as mock_smtplib:
            mock_smtp = MagicMock()
            mock_smtplib.SMTP.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtplib.SMTP.return_value.__exit__ = MagicMock(return_value=False)

            result = await notifier._send_email_with_retry(payload)
            assert result is True

        await notifier.close()


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestMissingCoveragePaths:
    """Tests for previously uncovered code paths."""

    @pytest.fixture
    def mock_config(self) -> Any:
        """Create mock ExternalNotificationConfig."""
        from cyberred.core.notifications import ExternalNotificationConfig

        return ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            email="operator@example.com",
            notification_delay=timedelta(minutes=1),
        )

    @pytest.mark.asyncio
    async def test_send_webhook_no_url_configured(self, mock_config: Any) -> None:
        """Test _send_webhook returns False when no URL configured."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig

        # Config with no webhook URL
        no_webhook_config = ExternalNotificationConfig(
            email="operator@example.com",
            notification_delay=timedelta(minutes=5),
        )

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=no_webhook_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        result = await notifier._send_webhook(payload)
        assert result is False

        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_email_no_email_configured(self, mock_config: Any) -> None:
        """Test _send_email returns False when no email configured."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig

        # Config with no email
        no_email_config = ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=5),
        )

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=no_email_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        result = await notifier._send_email(payload)
        assert result is False

        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_webhook_non_2xx_status_code(self, mock_config: Any) -> None:
        """Test _send_webhook returns False for non-2xx status codes."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        payload = {"engagement_id": "eng-123", "request_id": "req-456"}

        with patch.object(notifier, "_http_client") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 500  # Server error
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await notifier._send_webhook(payload)

            assert result is False

        await notifier.close()

    @pytest.mark.asyncio
    async def test_delayed_notification_tui_reconnected_during_delay(self, mock_config: Any) -> None:
        """Test notification not sent if TUI reconnected during delay."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig
        from cyberred.tui.screens.authorization import AuthorizationRequest

        # Short delay config for testing
        short_config = ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=1),
        )

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=short_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        webhook_called = False

        async def mock_send_webhook(payload: dict) -> bool:
            nonlocal webhook_called
            webhook_called = True
            return True

        # Patch sleep to be instant and simulate TUI reconnection
        async def mock_sleep(delay: float) -> None:
            # Simulate TUI reconnecting during delay
            mock_daemon_state.is_tui_attached = True

        with patch.object(notifier, "_send_webhook", mock_send_webhook):
            with patch("asyncio.sleep", mock_sleep):
                await notifier._delayed_notification("req-123", request)

        # Webhook should NOT have been called because TUI reconnected
        assert webhook_called is False

        await notifier.close()

    @pytest.mark.asyncio
    async def test_delayed_notification_sends_both_webhook_and_email(self, mock_config: Any) -> None:
        """Test _delayed_notification sends both webhook and email when configured."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        webhook_called = False
        email_called = False

        async def mock_send_webhook_with_retry(payload: dict) -> bool:
            nonlocal webhook_called
            webhook_called = True
            return True

        async def mock_send_email_with_retry(payload: dict) -> bool:
            nonlocal email_called
            email_called = True
            return True

        with patch.object(notifier, "_send_webhook_with_retry", mock_send_webhook_with_retry):
            with patch.object(notifier, "_send_email_with_retry", mock_send_email_with_retry):
                with patch("asyncio.sleep", AsyncMock()):
                    await notifier._delayed_notification("req-123", request)

        assert webhook_called is True
        assert email_called is True

        await notifier.close()

    @pytest.mark.asyncio
    async def test_audit_logging_exception_in_send_with_retry_success(self, mock_config: Any) -> None:
        """Test audit logging exception doesn't block success path."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()
        # Make audit logger raise exception
        mock_audit_logger.log_notification_sent.side_effect = Exception("Audit failed")

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        async def always_succeeds(payload: dict) -> bool:
            return True

        result = await notifier._send_with_retry(
            always_succeeds, {"request_id": "req-123"}, "webhook"
        )

        # Should still return True even though audit logging failed
        assert result is True

        await notifier.close()

    @pytest.mark.asyncio
    async def test_audit_logging_exception_in_send_with_retry_retry_path(self, mock_config: Any) -> None:
        """Test audit logging exception doesn't block retry path."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()
        # Make retry audit logger raise exception
        mock_audit_logger.log_notification_retry.side_effect = Exception("Audit failed")

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        call_count = 0

        async def fails_then_succeeds(payload: dict) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("First attempt fails")
            return True

        with patch("asyncio.sleep", AsyncMock()):
            result = await notifier._send_with_retry(
                fails_then_succeeds, {"request_id": "req-123"}, "webhook"
            )

        # Should still succeed despite audit logging errors
        assert result is True
        assert call_count == 2

        await notifier.close()

    @pytest.mark.asyncio
    async def test_audit_logging_exception_in_send_with_retry_failure_path(self, mock_config: Any) -> None:
        """Test audit logging exception doesn't block failure logging path."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()
        # Make failure audit logger raise exception
        mock_audit_logger.log_notification_failed.side_effect = Exception("Audit failed")

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        async def always_fails(payload: dict) -> bool:
            raise Exception("Always fails")

        with patch("asyncio.sleep", AsyncMock()):
            result = await notifier._send_with_retry(
                always_fails, {"request_id": "req-123"}, "webhook"
            )

        # Should return False but not raise despite audit logging errors
        assert result is False

        await notifier.close()

    @pytest.mark.asyncio
    async def test_delayed_notification_cancelled_error_propagation(self, mock_config: Any) -> None:
        """Test CancelledError is properly propagated from _delayed_notification."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        async def mock_sleep_cancel(delay: float) -> None:
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", mock_sleep_cancel):
            with pytest.raises(asyncio.CancelledError):
                await notifier._delayed_notification("req-123", request)

        await notifier.close()

    def test_to_dict_notification_delay_serialization(self) -> None:
        """Test to_dict serializes notification_delay correctly."""
        from cyberred.core.notifications import ExternalNotificationConfig

        config = ExternalNotificationConfig(
            webhook_url="https://example.com/hook",
            notification_delay=timedelta(minutes=10),
        )

        data = config.to_dict()

        # Should serialize as integer seconds
        assert data["notification_delay"] == 600  # 10 minutes in seconds

    @pytest.mark.asyncio
    async def test_schedule_notification_already_scheduled(self, mock_config: Any) -> None:
        """Test schedule_notification returns early if already scheduled."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Schedule first time
        await notifier.schedule_notification("req-123", request)
        assert "req-123" in notifier.get_pending_notifications()

        # Schedule again - should return early without creating duplicate
        await notifier.schedule_notification("req-123", request)
        
        # Should still have exactly one pending notification
        pending = notifier.get_pending_notifications()
        assert pending.count("req-123") == 1

        await notifier.cancel_all_notifications()
        await notifier.close()

    @pytest.mark.asyncio
    async def test_build_notification_payload_naive_timestamp(self, mock_config: Any) -> None:
        """Test _build_notification_payload handles naive datetime timestamps."""
        from cyberred.core.notifications import ExternalNotifier
        from cyberred.tui.screens.authorization import AuthorizationRequest

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        # Create request with naive datetime (no timezone)
        naive_timestamp = datetime(2026, 1, 15, 14, 0, 0).isoformat()
        
        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=naive_timestamp,
        )

        payload = notifier._build_notification_payload(request)

        # Should have added UTC timezone
        assert "pending_since" in payload
        assert "+00:00" in payload["pending_since"] or "Z" in payload["pending_since"]

        await notifier.close()

    @pytest.mark.asyncio
    async def test_cancel_notification_not_pending(self, mock_config: Any) -> None:
        """Test cancel_notification when notification is not pending (task is None)."""
        from cyberred.core.notifications import ExternalNotifier

        mock_daemon_state = MagicMock()
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=mock_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
        )

        # Cancel a notification that was never scheduled - should not raise
        await notifier.cancel_notification("non-existent-request")

        # Should have no pending notifications
        assert len(notifier.get_pending_notifications()) == 0

        await notifier.close()

    @pytest.mark.asyncio
    async def test_delayed_notification_webhook_only(self) -> None:
        """Test _delayed_notification with only webhook configured (no email)."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig
        from cyberred.tui.screens.authorization import AuthorizationRequest

        # Config with only webhook, no email
        webhook_only_config = ExternalNotificationConfig(
            webhook_url="https://hooks.example.com/cyberred",
            notification_delay=timedelta(minutes=1),
        )

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=webhook_only_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        webhook_called = False

        async def mock_send_webhook_with_retry(payload: dict) -> bool:
            nonlocal webhook_called
            webhook_called = True
            return True

        with patch.object(notifier, "_send_webhook_with_retry", mock_send_webhook_with_retry):
            with patch("asyncio.sleep", AsyncMock()):
                await notifier._delayed_notification("req-123", request)

        assert webhook_called is True

        await notifier.close()

    @pytest.mark.asyncio
    async def test_delayed_notification_email_only(self) -> None:
        """Test _delayed_notification with only email configured (no webhook)."""
        from cyberred.core.notifications import ExternalNotifier, ExternalNotificationConfig
        from cyberred.tui.screens.authorization import AuthorizationRequest

        # Config with only email, no webhook
        email_only_config = ExternalNotificationConfig(
            email="operator@example.com",
            notification_delay=timedelta(minutes=1),
        )

        mock_daemon_state = MagicMock()
        mock_daemon_state.is_tui_attached = False
        mock_audit_logger = AsyncMock()

        notifier = ExternalNotifier(
            config=email_only_config,
            daemon_state=mock_daemon_state,
            audit_logger=mock_audit_logger,
            signing_key=b"test-signing-key",
            engagement_id="eng-123",
        )

        request = AuthorizationRequest(
            id="req-123",
            request_type="lateral_movement",
            agent_id="agent-1",
            target="192.168.1.100",
            proposed_action="ssh_pivot",
            risk_level="high",
            related_findings=[],
            decision_context=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        email_called = False

        async def mock_send_email_with_retry(payload: dict) -> bool:
            nonlocal email_called
            email_called = True
            return True

        with patch.object(notifier, "_send_email_with_retry", mock_send_email_with_retry):
            with patch("asyncio.sleep", AsyncMock()):
                await notifier._delayed_notification("req-123", request)

        assert email_called is True

        await notifier.close()
