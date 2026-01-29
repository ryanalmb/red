"""Integration tests for External Notification System.

Story 10.9: External Authorization Notification (AC: #7)

Tests the full notification flow with minimal mocking:
- Webhook delivery with mock HTTP server
- Email delivery with mock SMTP
- TUI presence detection
- Retry behavior
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.core.notifications import (
    ExternalNotificationConfig,
    ExternalNotifier,
    NotificationPayload,
)
from cyberred.tui.screens.authorization import AuthorizationRequest


# =============================================================================
# Integration Test Fixtures
# =============================================================================


@pytest.fixture
def notification_config() -> ExternalNotificationConfig:
    """Create notification config for integration tests."""
    return ExternalNotificationConfig(
        webhook_url="https://hooks.example.com/cyberred",
        email="operator@example.com",
        smtp_host="localhost",
        smtp_port=1025,  # Common test SMTP port
        smtp_use_tls=False,  # Disabled for testing
        notification_delay=timedelta(minutes=1),
    )


@pytest.fixture
def daemon_state() -> MagicMock:
    """Create mock daemon state."""
    state = MagicMock()
    state.is_tui_attached = False
    return state


@pytest.fixture
def audit_logger() -> AsyncMock:
    """Create mock audit logger."""
    logger = AsyncMock()
    logger.log_notification_sent = AsyncMock()
    logger.log_notification_retry = AsyncMock()
    logger.log_notification_failed = AsyncMock()
    return logger


@pytest.fixture
def sample_request() -> AuthorizationRequest:
    """Create sample authorization request."""
    return AuthorizationRequest(
        id="req-integration-test-1",
        request_type="lateral_movement",
        agent_id="exploit-agent-3",
        target="192.168.1.100",
        proposed_action="ssh_pivot",
        risk_level="high",
        related_findings=[{"cve": "CVE-2024-1234", "severity": "high"}],
        decision_context=["Discovered new subnet", "SSH port open"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# Integration Tests (AC: #7)
# =============================================================================


class TestNotificationFlowIntegration:
    """Integration tests for full notification flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_webhook_flow(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test end-to-end: request → schedule → webhook sent."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        # Mock the HTTP client to capture the webhook call
        webhook_payloads: list[dict[str, Any]] = []

        async def capture_webhook(url: str, **kwargs: Any) -> MagicMock:
            webhook_payloads.append(kwargs.get("json", {}))
            response = MagicMock()
            response.status_code = 200
            return response

        with patch.object(notifier._http_client, "post", side_effect=capture_webhook):
            # Build and send notification directly (bypassing delay)
            payload = notifier._build_notification_payload(sample_request)
            result = await notifier._send_webhook(payload)

            assert result is True
            assert len(webhook_payloads) == 1

            # Verify payload contents
            sent_payload = webhook_payloads[0]
            assert sent_payload["engagement_id"] == "eng-integration-1"
            assert sent_payload["request_id"] == "req-integration-test-1"
            assert sent_payload["request_type"] == "lateral_movement"
            assert sent_payload["target"] == "192.168.1.100"
            assert sent_payload["urgency"] == "high"
            assert "response_url" in sent_payload
            assert "pending_since" in sent_payload

        await notifier.close()

    @pytest.mark.asyncio
    async def test_end_to_end_email_flow(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test end-to-end: request → schedule → email sent."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        # Track email sending
        email_sent = False
        email_content: dict[str, Any] = {}

        def mock_smtp_send(*args: Any, **kwargs: Any) -> None:
            nonlocal email_sent, email_content
            email_sent = True

        with patch("cyberred.core.notifications.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp.send_message = mock_smtp_send
            mock_smtp_class.return_value = mock_smtp

            payload = notifier._build_notification_payload(sample_request)
            result = await notifier._send_email(payload)

            assert result is True
            assert email_sent is True

        await notifier.close()

    @pytest.mark.asyncio
    async def test_tui_attach_detach_notification_behavior(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test TUI attach/detach triggers correct notification behavior."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        # TUI detached - notification should be scheduled
        daemon_state.is_tui_attached = False
        await notifier.schedule_notification(sample_request.id, sample_request)
        assert sample_request.id in notifier.get_pending_notifications()

        # Simulate TUI reattach - should cancel notification
        daemon_state.is_tui_attached = True
        await notifier.on_tui_attached()
        assert sample_request.id not in notifier.get_pending_notifications()

        await notifier.close()

    @pytest.mark.asyncio
    async def test_response_cancels_pending_notification(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test response cancels pending notification."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        # Schedule notification
        daemon_state.is_tui_attached = False
        await notifier.schedule_notification(sample_request.id, sample_request)
        assert sample_request.id in notifier.get_pending_notifications()

        # Simulate operator response - cancel notification
        await notifier.cancel_notification(sample_request.id)
        assert sample_request.id not in notifier.get_pending_notifications()

        await notifier.close()

    @pytest.mark.asyncio
    async def test_retry_exhaustion_does_not_break_engagement(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test retry exhaustion doesn't break engagement."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        # Mock webhook to always fail
        async def failing_webhook(url: str, **kwargs: Any) -> None:
            raise Exception("Simulated network failure")

        with patch.object(notifier._http_client, "post", side_effect=failing_webhook):
            with patch("asyncio.sleep", AsyncMock()):
                payload = notifier._build_notification_payload(sample_request)
                result = await notifier._send_webhook_with_retry(payload)

                # Should return False but not raise
                assert result is False

                # Audit logger should have logged the failure
                audit_logger.log_notification_failed.assert_called_once()

        await notifier.close()


class TestNotificationPayloadIntegration:
    """Integration tests for notification payload building."""

    def test_payload_from_authorization_request(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
        sample_request: AuthorizationRequest,
    ) -> None:
        """Test payload is correctly built from authorization request."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"integration-test-key",
            engagement_id="eng-integration-1",
        )

        payload = notifier._build_notification_payload(sample_request)

        # Verify all required fields
        assert payload["engagement_id"] == "eng-integration-1"
        assert payload["request_id"] == sample_request.id
        assert payload["request_type"] == sample_request.request_type
        assert payload["target"] == sample_request.target
        assert payload["urgency"] == sample_request.risk_level

        # Verify context
        assert payload["context"]["source_agent"] == sample_request.agent_id
        assert payload["context"]["action"] == sample_request.proposed_action
        assert "decision_context" in payload["context"]

        # Verify response URL is signed
        assert "response_url" in payload
        assert "api/v1/auth/respond/" in payload["response_url"]

    def test_notification_payload_dataclass(self) -> None:
        """Test NotificationPayload dataclass serialization."""
        payload = NotificationPayload(
            engagement_id="eng-1",
            request_id="req-1",
            request_type="scope_expansion",
            target="10.0.0.0/8",
            urgency="critical",
            pending_since=datetime(2026, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
            response_url="https://cyberred.local/api/v1/auth/respond/token",
            context={"reason": "New network discovered"},
        )

        data = payload.to_dict()

        assert data["engagement_id"] == "eng-1"
        assert data["request_id"] == "req-1"
        assert data["request_type"] == "scope_expansion"
        assert data["target"] == "10.0.0.0/8"
        assert data["urgency"] == "critical"
        assert data["pending_since"] == "2026-01-15T14:00:00+00:00"
        assert data["response_url"] == "https://cyberred.local/api/v1/auth/respond/token"
        assert data["context"] == {"reason": "New network discovered"}


class TestWebhookSecurityIntegration:
    """Integration tests for webhook security features."""

    def test_hmac_signature_verification(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
    ) -> None:
        """Test HMAC signature can be verified by receiver."""
        import hashlib
        import hmac
        import json

        signing_key = b"shared-secret-key"

        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=signing_key,
            engagement_id="eng-1",
        )

        payload = {
            "engagement_id": "eng-1",
            "request_id": "req-1",
            "request_type": "lateral_movement",
            "target": "192.168.1.100",
            "urgency": "high",
        }

        # Generate signature using notifier
        signature = notifier._sign_payload(payload)

        # Verify signature format
        assert signature.startswith("sha256=")

        # Simulate receiver verification
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        expected_signature = hmac.new(
            signing_key,
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        assert signature == f"sha256={expected_signature}"

    def test_response_token_contains_required_data(
        self,
        notification_config: ExternalNotificationConfig,
        daemon_state: MagicMock,
        audit_logger: AsyncMock,
    ) -> None:
        """Test response token contains engagement_id, request_id, and expiry."""
        notifier = ExternalNotifier(
            config=notification_config,
            daemon_state=daemon_state,
            audit_logger=audit_logger,
            signing_key=b"test-key",
            engagement_id="eng-test-123",
        )

        token = notifier._generate_response_token("req-456")

        # Token format: {request_id}:{engagement_id}:{expiry_timestamp}:{signature}
        parts = token.split(":")
        assert len(parts) == 4
        assert parts[0] == "req-456"
        assert parts[1] == "eng-test-123"
        # parts[2] is expiry timestamp
        float(parts[2])  # Should be valid float
        # parts[3] is HMAC signature
        assert len(parts[3]) == 64  # SHA256 hex digest length
