"""External Authorization Notification System.

Story 10.9: External Authorization Notification

Provides webhook/email notifications for pending authorization requests
when TUI is disconnected. Implements:
- ExternalNotificationConfig: Configuration dataclass
- NotificationPayload: Payload dataclass for webhook/email content
- ExternalNotifier: Manager for scheduling and sending notifications

Per UX Design lines 518: ExternalNotifier component for webhook/email
alerts when disconnected.

Usage:
    from cyberred.core.notifications import (
        ExternalNotificationConfig,
        ExternalNotifier,
    )
    
    config = ExternalNotificationConfig(
        webhook_url="https://hooks.example.com/cyberred",
        email="operator@example.com",
    )
    
    notifier = ExternalNotifier(
        config=config,
        daemon_state=daemon_state,
        audit_logger=audit_logger,
        signing_key=signing_key,
    )
    
    await notifier.schedule_notification(request_id, request)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import httpx

from cyberred.core.config import parse_duration
from cyberred.core.exceptions import ConfigurationError

if TYPE_CHECKING:
    from cyberred.tui.screens.authorization import AuthorizationRequest

logger = logging.getLogger(__name__)


# =============================================================================
# ExternalNotificationConfig Dataclass
# =============================================================================


@dataclass
class ExternalNotificationConfig:
    """Configuration for external authorization notifications.
    
    Per UX Design lines 518: ExternalNotifier component for 
    webhook/email alerts when disconnected.
    
    Attributes:
        webhook_url: Optional webhook URL for HTTP POST notifications.
        email: Optional email address for email notifications.
        smtp_host: SMTP server host (default: localhost).
        smtp_port: SMTP server port (default: 587).
        smtp_use_tls: Whether to use TLS for SMTP (default: True).
        smtp_username: Optional SMTP authentication username.
        smtp_password: Optional SMTP authentication password.
        notification_delay: Time to wait before sending notification (default: 5 min).
    
    Raises:
        ConfigurationError: If webhook_url or email format is invalid,
            or if notification_delay is outside valid range (1-60 minutes).
    """
    webhook_url: str | None = None
    email: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    notification_delay: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate notification_delay bounds (1-60 minutes)
        min_delay = timedelta(minutes=1)
        max_delay = timedelta(minutes=60)
        
        if not (min_delay <= self.notification_delay <= max_delay):
            raise ConfigurationError(
                config_path="notifications",
                key="notification_delay",
                message=(
                    f"notification_delay must be between 1 and 60 minutes, "
                    f"got {self.notification_delay}"
                ),
            )
        
        # Validate webhook URL format if provided
        if self.webhook_url:
            if not self.webhook_url.startswith(("http://", "https://")):
                raise ConfigurationError(
                    config_path="notifications",
                    key="webhook_url",
                    message=(
                        f"webhook_url must be a valid HTTP(S) URL, "
                        f"got {self.webhook_url}"
                    ),
                )
        
        # Validate email format if provided
        if self.email:
            if "@" not in self.email or "." not in self.email.split("@")[-1]:
                raise ConfigurationError(
                    config_path="notifications",
                    key="email",
                    message=(
                        f"email must be a valid email address, "
                        f"got {self.email}"
                    ),
                )
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalNotificationConfig":
        """Create from config.yaml notifications section.
        
        Args:
            data: Dictionary with notification configuration.
            
        Returns:
            ExternalNotificationConfig instance.
            
        Raises:
            ConfigurationError: If configuration is invalid.
        """
        delay_str = data.get("notification_delay", "5m")
        try:
            delay = parse_duration(delay_str)
        except ValueError as e:
            raise ConfigurationError(
                config_path="notifications",
                key="notification_delay",
                message=str(e),
            ) from e
        
        return cls(
            webhook_url=data.get("webhook_url"),
            email=data.get("email"),
            smtp_host=data.get("smtp_host", "localhost"),
            smtp_port=data.get("smtp_port", 587),
            smtp_use_tls=data.get("smtp_use_tls", True),
            smtp_username=data.get("smtp_username"),
            smtp_password=data.get("smtp_password"),
            notification_delay=delay,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary for persistence.
        
        Returns:
            Dictionary with configuration values.
        """
        return {
            "webhook_url": self.webhook_url,
            "email": self.email,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_use_tls": self.smtp_use_tls,
            "smtp_username": self.smtp_username,
            "smtp_password": self.smtp_password,
            "notification_delay": int(self.notification_delay.total_seconds()),
        }
    
    @property
    def is_configured(self) -> bool:
        """Check if any notification method is configured.
        
        Returns:
            True if webhook_url or email is configured.
        """
        return bool(self.webhook_url or self.email)


# =============================================================================
# NotificationPayload Dataclass
# =============================================================================


@dataclass
class NotificationPayload:
    """Payload for external authorization notifications.
    
    Contains all context required for webhook/email notifications
    per AC #1: engagement_id, request_type, target, urgency.
    
    Attributes:
        engagement_id: ID of the engagement.
        request_id: ID of the authorization request.
        request_type: Type of authorization (lateral_movement, scope_expansion, etc.).
        target: Target of the proposed action.
        urgency: Urgency level (low, medium, high, critical).
        pending_since: When the request was created.
        response_url: Signed URL to respond via API.
        context: Additional context (source_agent, action, risk_assessment).
    """
    engagement_id: str
    request_id: str
    request_type: str
    target: str
    urgency: str
    pending_since: datetime | None = None
    response_url: str | None = None
    context: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the payload.
        """
        result = {
            "engagement_id": self.engagement_id,
            "request_id": self.request_id,
            "request_type": self.request_type,
            "target": self.target,
            "urgency": self.urgency,
        }
        
        if self.pending_since:
            result["pending_since"] = self.pending_since.isoformat()
        
        if self.response_url:
            result["response_url"] = self.response_url
        
        if self.context:
            result["context"] = self.context
        
        return result


# =============================================================================
# Email Template
# =============================================================================


EMAIL_SUBJECT_TEMPLATE = "[CyberRed] Authorization Required - {urgency} Priority"

EMAIL_BODY_TEMPLATE = """
An authorization request requires your attention.

Engagement: {engagement_id}
Request ID: {request_id}
Request Type: {request_type}
Target: {target}
Urgency: {urgency}
Pending Since: {pending_since}

Context:
{context}

Respond via API:
{response_url}

---
This notification was sent because the TUI is disconnected.
"""


# =============================================================================
# ExternalNotifier Class
# =============================================================================


class ExternalNotifier:
    """Manages external notifications for authorization requests.
    
    Sends webhook/email alerts when authorization requests remain
    pending while TUI is disconnected.
    
    Attributes:
        _config: ExternalNotificationConfig with notification settings.
        _daemon_state: Daemon state for TUI presence detection.
        _audit: Audit logger for notification events.
        _signing_key: Key for HMAC signing of payloads/tokens.
        _pending: Dict mapping request_id to asyncio.Task.
        _engagement_id: Optional engagement ID for payload.
    """
    
    def __init__(
        self,
        config: ExternalNotificationConfig,
        daemon_state: Any,
        audit_logger: Any,
        signing_key: bytes,
        engagement_id: str = "",
    ) -> None:
        """Initialize ExternalNotifier.
        
        Args:
            config: ExternalNotificationConfig with notification settings.
            daemon_state: Daemon state for TUI presence detection.
            audit_logger: Audit logger for notification events.
            signing_key: Key for HMAC signing of payloads/tokens.
            engagement_id: Optional engagement ID for payload.
        """
        self._config = config
        self._daemon_state = daemon_state
        self._audit = audit_logger
        self._signing_key = signing_key
        self._engagement_id = engagement_id
        self._pending: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._http_client = httpx.AsyncClient(timeout=10.0)
    
    async def schedule_notification(
        self,
        request_id: str,
        request: "AuthorizationRequest",
    ) -> None:
        """Schedule external notification after delay.
        
        Only schedules if TUI is detached. If TUI is attached,
        no notification is scheduled (AC #5).
        
        Args:
            request_id: ID of the authorization request.
            request: AuthorizationRequest instance.
        """
        async with self._lock:
            if request_id in self._pending:
                return  # Already scheduled
            
            # Only schedule if TUI is detached (AC #5)
            if self._daemon_state.is_tui_attached:
                return
            
            task = asyncio.create_task(
                self._delayed_notification(request_id, request)
            )
            self._pending[request_id] = task
            
            logger.info(
                "Scheduled external notification for %s (delay: %s)",
                request_id,
                self._config.notification_delay,
            )
    
    async def cancel_notification(self, request_id: str) -> None:
        """Cancel pending notification (request resolved or TUI attached).
        
        Safe to call even if no notification is pending.
        
        Args:
            request_id: ID of the authorization request.
        """
        async with self._lock:
            task = self._pending.pop(request_id, None)
            
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                logger.info(
                    "Cancelled external notification for %s",
                    request_id,
                )
    
    async def cancel_all_notifications(self) -> None:
        """Cancel all pending notifications.
        
        Used when engagement is stopped or TUI is reattached.
        """
        async with self._lock:
            tasks_to_cancel = list(self._pending.items())
            self._pending.clear()
        
        for request_id, task in tasks_to_cancel:
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            logger.debug("Cancelled notification for %s", request_id)
        
        logger.info("Cancelled all external notifications")
    
    async def on_tui_attached(self) -> None:
        """Handle TUI attachment event.
        
        Cancels all pending notifications when TUI is attached (AC #5).
        """
        await self.cancel_all_notifications()
    
    def get_pending_notifications(self) -> list[str]:
        """Get list of request IDs with pending notifications.
        
        Returns:
            List of request IDs awaiting notification.
        """
        return list(self._pending.keys())
    
    async def _delayed_notification(
        self,
        request_id: str,
        request: "AuthorizationRequest",
    ) -> None:
        """Wait for delay, then send notification.
        
        Args:
            request_id: ID of the authorization request.
            request: AuthorizationRequest instance.
        """
        try:
            await asyncio.sleep(self._config.notification_delay.total_seconds())
            
            # Check if TUI reconnected during delay
            if self._daemon_state.is_tui_attached:
                return
            
            payload = self._build_notification_payload(request)
            
            # Send webhook if configured
            if self._config.webhook_url:
                await self._send_webhook_with_retry(payload)
            
            # Send email if configured
            if self._config.email:
                await self._send_email_with_retry(payload)
            
        except asyncio.CancelledError:
            logger.debug("Notification cancelled for %s", request_id)
            raise
        finally:
            # Clean up
            async with self._lock:
                self._pending.pop(request_id, None)
    
    def _build_notification_payload(
        self,
        request: "AuthorizationRequest",
    ) -> dict[str, Any]:
        """Build notification payload from authorization request.
        
        Args:
            request: AuthorizationRequest instance.
            
        Returns:
            Dictionary payload for webhook/email.
        """
        # Parse timestamp
        pending_since = datetime.fromisoformat(request.timestamp)
        if pending_since.tzinfo is None:
            pending_since = pending_since.replace(tzinfo=timezone.utc)
        
        # Generate response token
        response_token = self._generate_response_token(request.id)
        response_url = f"https://cyberred.local/api/v1/auth/respond/{response_token}"
        
        # Build context from request
        context = {
            "source_agent": request.agent_id,
            "action": request.proposed_action,
        }
        if request.decision_context:
            context["decision_context"] = request.decision_context
        
        return {
            "engagement_id": self._engagement_id,
            "request_id": request.id,
            "request_type": request.request_type,
            "target": request.target,
            "urgency": request.risk_level,  # Map risk_level to urgency
            "pending_since": pending_since.isoformat(),
            "response_url": response_url,
            "context": context,
        }
    
    def _generate_response_token(self, request_id: str) -> str:
        """Generate signed token for API response endpoint.
        
        Args:
            request_id: ID of the authorization request.
            
        Returns:
            Signed token string.
        """
        # Include expiry time (1 hour from now)
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        token_data = f"{request_id}:{self._engagement_id}:{expiry.timestamp()}"
        
        signature = hmac.new(
            self._signing_key,
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{token_data}:{signature}"
    
    def _sign_payload(self, payload: dict[str, Any]) -> str:
        """Create HMAC-SHA256 signature for webhook verification.
        
        Args:
            payload: Payload dictionary to sign.
            
        Returns:
            Signature string prefixed with 'sha256='.
        """
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            self._signing_key,
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    async def _send_webhook(self, payload: dict[str, Any]) -> bool:
        """Send webhook notification.
        
        Args:
            payload: Notification payload.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self._config.webhook_url:
            return False
        
        try:
            signature = self._sign_payload(payload)
            headers = {
                "Content-Type": "application/json",
                "X-Cyberred-Signature": signature,
            }
            
            response = await self._http_client.post(
                self._config.webhook_url,
                json=payload,
                headers=headers,
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    "Webhook sent successfully for %s",
                    payload.get("request_id"),
                )
                return True
            else:
                logger.warning(
                    "Webhook returned status %d for %s",
                    response.status_code,
                    payload.get("request_id"),
                )
                return False
                
        except Exception as e:
            logger.error(
                "Webhook delivery failed for %s: %s",
                payload.get("request_id"),
                str(e),
            )
            return False
    
    async def _send_email(self, payload: dict[str, Any]) -> bool:
        """Send email notification.
        
        Args:
            payload: Notification payload.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self._config.email:
            return False
        
        try:
            # Build email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = EMAIL_SUBJECT_TEMPLATE.format(
                urgency=payload.get("urgency", "unknown").upper()
            )
            msg["From"] = self._config.smtp_username or "cyberred@localhost"
            msg["To"] = self._config.email
            
            # Format context
            context_str = ""
            if payload.get("context"):
                for key, value in payload["context"].items():
                    context_str += f"  {key}: {value}\n"
            
            body = EMAIL_BODY_TEMPLATE.format(
                engagement_id=payload.get("engagement_id", "unknown"),
                request_id=payload.get("request_id", "unknown"),
                request_type=payload.get("request_type", "unknown"),
                target=payload.get("target", "unknown"),
                urgency=payload.get("urgency", "unknown"),
                pending_since=payload.get("pending_since", "unknown"),
                context=context_str or "  No additional context",
                response_url=payload.get("response_url", "N/A"),
            )
            
            msg.attach(MIMEText(body, "plain"))
            
            # Send via SMTP
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                if self._config.smtp_use_tls:
                    server.starttls()
                if self._config.smtp_username and self._config.smtp_password:
                    server.login(self._config.smtp_username, self._config.smtp_password)
                server.send_message(msg)
            
            logger.info(
                "Email sent successfully for %s",
                payload.get("request_id"),
            )
            return True
            
        except Exception as e:
            logger.error(
                "Email delivery failed for %s: %s",
                payload.get("request_id"),
                str(e),
            )
            return False
    
    async def _send_with_retry(
        self,
        send_func: Callable[[dict[str, Any]], Coroutine[Any, Any, bool]],
        payload: dict[str, Any],
        notification_type: str,
    ) -> bool:
        """Send notification with exponential backoff retry.
        
        Args:
            send_func: Async function to send notification.
            payload: Notification payload.
            notification_type: Type for logging ("webhook" or "email").
            
        Returns:
            True if successful, False after all retries exhausted.
        """
        max_attempts = 3
        base_delay = 1.0  # seconds
        
        for attempt in range(max_attempts):
            try:
                result = await send_func(payload)
                if result:
                    try:
                        await self._audit.log_notification_sent(
                            notification_type=notification_type,
                            request_id=payload.get("request_id", "unknown"),
                            attempt=attempt + 1,
                        )
                    except Exception:
                        pass  # Audit logging should not block
                    return True
                raise Exception("Send returned False")
            except Exception as e:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                
                try:
                    await self._audit.log_notification_retry(
                        notification_type=notification_type,
                        request_id=payload.get("request_id", "unknown"),
                        attempt=attempt + 1,
                        error=str(e),
                        next_retry_delay=delay if attempt < max_attempts - 1 else None,
                    )
                except Exception:
                    pass  # Audit logging should not block
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        try:
            await self._audit.log_notification_failed(
                notification_type=notification_type,
                request_id=payload.get("request_id", "unknown"),
                total_attempts=max_attempts,
            )
        except Exception:
            pass  # Audit logging should not block
        
        logger.warning(
            "%s notification failed after %d attempts for %s",
            notification_type,
            max_attempts,
            payload.get("request_id"),
        )
        return False
    
    async def _send_webhook_with_retry(self, payload: dict[str, Any]) -> bool:
        """Send webhook with retry logic.
        
        Args:
            payload: Notification payload.
            
        Returns:
            True if successful, False otherwise.
        """
        return await self._send_with_retry(self._send_webhook, payload, "webhook")
    
    async def _send_email_with_retry(self, payload: dict[str, Any]) -> bool:
        """Send email with retry logic.
        
        Args:
            payload: Notification payload.
            
        Returns:
            True if successful, False otherwise.
        """
        return await self._send_with_retry(self._send_email, payload, "email")
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        await self._http_client.aclose()
