# Story 10.9: External Authorization Notification

Status: done

## Story

As an **operator**,
I want **webhook/email notifications for pending authorization requests**,
So that **I can respond to critical authorizations when TUI is disconnected**.

## Acceptance Criteria

1. **Given** engagement is running and TUI is detached
   **When** authorization request is pending for >5 minutes
   **Then** webhook fires to configured endpoint with request details
   **And** notification includes: engagement_id, request_type, target, urgency
   **And** notification includes secure link to respond via API

2. **Given** engagement configuration has `notifications.email` configured
   **When** authorization request is pending for >5 minutes
   **Then** optional email notification is sent to configured address
   **And** email includes same payload as webhook (engagement_id, request_type, target, urgency)
   **And** email includes secure link to respond via API

3. **Given** webhook endpoint is unavailable
   **When** notification attempt fails
   **Then** retry with exponential backoff (3 attempts)
   **And** failure is logged but engagement continues
   **And** retry attempts are logged to audit trail

4. **Given** email delivery fails
   **When** SMTP connection fails or email is rejected
   **Then** retry with exponential backoff (3 attempts)
   **And** failure is logged but engagement continues
   **And** retry attempts are logged to audit trail

5. **Given** TUI is attached and operator is actively responding
   **When** authorization request is created
   **Then** external notifications are NOT sent (TUI presence suppresses external alerts)
   **And** notification timer only starts after TUI detach

6. **Given** authorization request is responded to (via TUI or API)
   **When** external notification is pending or scheduled
   **Then** pending notification is cancelled
   **And** no external alert is sent for resolved requests

7. **Given** integration tests are run
   **When** webhook and email notification flows are tested
   **Then** webhook delivery tests pass
   **And** email delivery tests pass (with mock SMTP)
   **And** retry behavior tests pass
   **And** TUI presence detection tests pass

## Tasks / Subtasks

> **⚠️ CRITICAL: Test-Driven Development (TDD) Required**
> 
> This story MUST follow strict TDD methodology:
> 1. **RED Phase**: Write failing tests FIRST before any implementation
> 2. **GREEN Phase**: Write minimal code to make tests pass
> 3. **REFACTOR Phase**: Clean up code while keeping tests green
>
> **🎯 STRICT 100% TEST COVERAGE REQUIREMENT**
> - All new code MUST achieve 100% test coverage
> - Coverage gaps are NOT acceptable - add tests until 100% is achieved
> - Run targeted coverage checks per file/module

---

### 🔴 RED PHASE: Write Failing Tests First

- [ ] Task 1: Write unit tests for ExternalNotificationConfig dataclass (AC: #1, #2)
  - [ ] Test `ExternalNotificationConfig` initialization with webhook_url
  - [ ] Test `ExternalNotificationConfig` initialization with email
  - [ ] Test `ExternalNotificationConfig` with both webhook and email
  - [ ] Test `notification_delay` default value (5 minutes)
  - [ ] Test `notification_delay` validation (min 1 min, max 60 min)
  - [ ] Test `from_dict()` factory method for YAML loading
  - [ ] Test `to_dict()` for serialization
  - [ ] Test invalid webhook URL format raises `ConfigurationError`
  - [ ] Test invalid email format raises `ConfigurationError`

- [ ] Task 2: Write unit tests for ExternalNotifier class (AC: #1, #2)
  - [ ] Test `ExternalNotifier` initialization with config
  - [ ] Test `schedule_notification(request_id)` schedules delayed notification
  - [ ] Test `cancel_notification(request_id)` cancels pending notification
  - [ ] Test `_build_notification_payload()` creates correct JSON payload
  - [ ] Test payload includes engagement_id, request_type, target, urgency
  - [ ] Test payload includes secure response link (signed token)
  - [ ] Test `get_pending_notifications()` returns scheduled notifications

- [ ] Task 3: Write unit tests for webhook delivery (AC: #1, #3)
  - [ ] Test `_send_webhook()` makes HTTP POST to configured URL
  - [ ] Test webhook uses correct Content-Type (application/json)
  - [ ] Test webhook includes HMAC signature header for verification
  - [ ] Test webhook timeout handling (10 second timeout)
  - [ ] Test webhook success logs to audit trail
  - [ ] Test webhook failure triggers retry

- [ ] Task 4: Write unit tests for email delivery (AC: #2, #4)
  - [ ] Test `_send_email()` connects to configured SMTP server
  - [ ] Test email uses TLS when configured
  - [ ] Test email subject includes engagement_id and urgency
  - [ ] Test email body includes all notification payload fields
  - [ ] Test email success logs to audit trail
  - [ ] Test email failure triggers retry

- [ ] Task 5: Write unit tests for retry logic (AC: #3, #4)
  - [ ] Test exponential backoff timing (1s, 2s, 4s)
  - [ ] Test max 3 retry attempts
  - [ ] Test all retries exhausted logs final failure
  - [ ] Test successful retry after initial failure
  - [ ] Test retry counter is reset after success

- [ ] Task 6: Write unit tests for TUI presence detection (AC: #5, #6)
  - [ ] Test notification suppressed when TUI is attached
  - [ ] Test notification timer starts only after TUI detach
  - [ ] Test notification cancelled when request is resolved
  - [ ] Test TUI reattach cancels pending notifications
  - [ ] Test `is_tui_attached()` queries daemon state correctly

- [ ] Task 7: Write integration tests for notification flow (AC: #7)
  - [ ] Test end-to-end: request → timeout → webhook sent
  - [ ] Test end-to-end: request → timeout → email sent
  - [ ] Test TUI attach/detach triggers correct notification behavior
  - [ ] Test response cancels pending notification
  - [ ] Test retry exhaustion doesn't break engagement

---

### 🟢 GREEN PHASE: Implement Features to Pass Tests

- [ ] Task 8: Implement ExternalNotificationConfig in `core/notifications.py` (AC: #1, #2)
  - [ ] Create `ExternalNotificationConfig` dataclass
  - [ ] Add `webhook_url: str | None` field
  - [ ] Add `email: str | None` field  
  - [ ] Add `smtp_host: str` field with default "localhost"
  - [ ] Add `smtp_port: int` field with default 587
  - [ ] Add `smtp_use_tls: bool` field with default True
  - [ ] Add `smtp_username: str | None` field
  - [ ] Add `smtp_password: str | None` field
  - [ ] Add `notification_delay: timedelta` field with default 5 minutes
  - [ ] Implement validation for URL and email formats
  - [ ] Implement `from_dict()` and `to_dict()` methods

- [ ] Task 9: Implement ExternalNotifier class in `core/notifications.py` (AC: #1, #2, #5)
  - [ ] Create `ExternalNotifier` class
  - [ ] Implement `schedule_notification(request_id, request: AuthorizationRequest)`
  - [ ] Implement `cancel_notification(request_id)` 
  - [ ] Implement `cancel_all_notifications()` for engagement stop
  - [ ] Implement `_build_notification_payload()` with all required fields
  - [ ] Implement `_generate_response_token()` for secure API links
  - [ ] Integrate with TUI presence detection via daemon state

- [ ] Task 10: Implement webhook delivery in `core/notifications.py` (AC: #1, #3)
  - [ ] Implement `_send_webhook(payload: dict)` using httpx
  - [ ] Add HMAC-SHA256 signature header (X-Cyberred-Signature)
  - [ ] Add 10 second timeout for HTTP request
  - [ ] Handle connection errors gracefully
  - [ ] Log delivery status to audit trail

- [ ] Task 11: Implement email delivery in `core/notifications.py` (AC: #2, #4)
  - [ ] Implement `_send_email(payload: dict)` using smtplib
  - [ ] Create email template with HTML and plain text parts
  - [ ] Support TLS connection
  - [ ] Handle SMTP errors gracefully
  - [ ] Log delivery status to audit trail

- [ ] Task 12: Implement retry logic in `core/notifications.py` (AC: #3, #4)
  - [ ] Create `RetryManager` class for exponential backoff
  - [ ] Implement retry with delays: 1s, 2s, 4s (exponential)
  - [ ] Max 3 attempts before giving up
  - [ ] Log each retry attempt
  - [ ] Log final failure after all retries exhausted
  - [ ] Continue engagement regardless of notification failures

- [ ] Task 13: Implement NotificationPayload dataclass (AC: #1)
  - [ ] Create `NotificationPayload` dataclass
  - [ ] Add `engagement_id: str` field
  - [ ] Add `request_id: str` field
  - [ ] Add `request_type: str` field (lateral_movement, scope_expansion, etc.)
  - [ ] Add `target: str` field
  - [ ] Add `urgency: str` field (low, medium, high, critical)
  - [ ] Add `pending_since: datetime` field
  - [ ] Add `response_url: str` field (signed API endpoint)
  - [ ] Add `context: dict` field for additional info
  - [ ] Implement `to_dict()` for JSON serialization

- [ ] Task 14: Implement API response endpoint (AC: #1, #2)
  - [ ] Add `/api/v1/auth/respond/{token}` endpoint
  - [ ] Verify signed token (expiry, engagement_id, request_id)
  - [ ] Accept Y/N response via POST
  - [ ] Route response to authorization queue
  - [ ] Log API response to audit trail

---

### 🔵 REFACTOR PHASE: Clean Up While Keeping Tests Green

- [ ] Task 15: Code quality and documentation
  - [ ] Add comprehensive docstrings to all public methods
  - [ ] Ensure type hints are complete and correct
  - [ ] Verify 100% test coverage maintained after refactoring
  - [ ] Add logging for debugging notification flow

---

## Dev Notes

### Architecture Patterns

**Notification Configuration Schema** (config.yaml):
```yaml
notifications:
  webhook_url: "https://hooks.example.com/cyberred"  # Optional
  email: "operator@example.com"  # Optional
  smtp_host: "smtp.example.com"  # Required if email configured
  smtp_port: 587
  smtp_use_tls: true
  smtp_username: "alerts@example.com"
  smtp_password: "${SMTP_PASSWORD}"  # Environment variable reference
  notification_delay: 5m  # Time to wait before sending external notification
```

**ExternalNotificationConfig Dataclass**:
```python
@dataclass
class ExternalNotificationConfig:
    """Configuration for external authorization notifications.
    
    Per UX Design lines 518: ExternalNotifier component for 
    webhook/email alerts when disconnected.
    """
    webhook_url: str | None = None
    email: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    notification_delay: timedelta = timedelta(minutes=5)
    
    def __post_init__(self):
        # Validate notification_delay bounds
        min_delay = timedelta(minutes=1)
        max_delay = timedelta(minutes=60)
        if not (min_delay <= self.notification_delay <= max_delay):
            raise ConfigurationError(
                f"notification_delay must be between 1 and 60 minutes, "
                f"got {self.notification_delay}"
            )
        
        # Validate webhook URL format if provided
        if self.webhook_url:
            if not self.webhook_url.startswith(("http://", "https://")):
                raise ConfigurationError(
                    f"webhook_url must be a valid HTTP(S) URL, got {self.webhook_url}"
                )
        
        # Validate email format if provided
        if self.email:
            if "@" not in self.email or "." not in self.email.split("@")[-1]:
                raise ConfigurationError(
                    f"email must be a valid email address, got {self.email}"
                )
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalNotificationConfig":
        """Create from config.yaml notifications section."""
        delay_str = data.get("notification_delay", "5m")
        delay = parse_duration(delay_str)
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
    
    @property
    def is_configured(self) -> bool:
        """Check if any notification method is configured."""
        return bool(self.webhook_url or self.email)
```

**ExternalNotifier Class Pattern**:
```python
class ExternalNotifier:
    """Manages external notifications for authorization requests.
    
    Sends webhook/email alerts when authorization requests remain
    pending while TUI is disconnected.
    """
    
    def __init__(
        self,
        config: ExternalNotificationConfig,
        daemon_state: DaemonState,
        audit_logger: AuthorizationAuditLogger,
        signing_key: bytes,
    ):
        self._config = config
        self._daemon_state = daemon_state
        self._audit = audit_logger
        self._signing_key = signing_key
        self._pending: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._http_client = httpx.AsyncClient(timeout=10.0)
    
    async def schedule_notification(
        self, 
        request_id: str, 
        request: AuthorizationRequest
    ) -> None:
        """Schedule external notification after delay."""
        async with self._lock:
            if request_id in self._pending:
                return  # Already scheduled
            
            # Only schedule if TUI is detached
            if self._daemon_state.is_tui_attached:
                return
            
            task = asyncio.create_task(
                self._delayed_notification(request_id, request)
            )
            self._pending[request_id] = task
    
    async def cancel_notification(self, request_id: str) -> None:
        """Cancel pending notification (request resolved or TUI attached)."""
        async with self._lock:
            if task := self._pending.pop(request_id, None):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    async def _delayed_notification(
        self,
        request_id: str,
        request: AuthorizationRequest
    ) -> None:
        """Wait for delay, then send notification."""
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
        
        # Clean up
        async with self._lock:
            self._pending.pop(request_id, None)
```

**Webhook Payload Format**:
```json
{
    "engagement_id": "eng-uuid-here",
    "request_id": "req-uuid-here",
    "request_type": "lateral_movement",
    "target": "192.168.1.100",
    "urgency": "high",
    "pending_since": "2026-01-15T14:00:00Z",
    "response_url": "https://cyberred.local/api/v1/auth/respond/signed-token-here",
    "context": {
        "source_agent": "exploit-agent-3",
        "action": "ssh_pivot",
        "risk_assessment": "Medium risk - new subnet"
    }
}
```

**Webhook Security** (X-Cyberred-Signature header):
```python
def _sign_payload(self, payload: dict) -> str:
    """Create HMAC-SHA256 signature for webhook verification."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    signature = hmac.new(
        self._signing_key,
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"
```

**Retry Logic Pattern**:
```python
async def _send_with_retry(
    self,
    send_func: Callable,
    payload: dict,
    notification_type: str
) -> bool:
    """Send notification with exponential backoff retry."""
    max_attempts = 3
    base_delay = 1.0  # seconds
    
    for attempt in range(max_attempts):
        try:
            await send_func(payload)
            await self._audit.log_notification_sent(
                notification_type=notification_type,
                request_id=payload["request_id"],
                attempt=attempt + 1,
            )
            return True
        except Exception as e:
            delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
            await self._audit.log_notification_retry(
                notification_type=notification_type,
                request_id=payload["request_id"],
                attempt=attempt + 1,
                error=str(e),
                next_retry_delay=delay if attempt < max_attempts - 1 else None,
            )
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
    
    # All retries exhausted
    await self._audit.log_notification_failed(
        notification_type=notification_type,
        request_id=payload["request_id"],
        total_attempts=max_attempts,
    )
    return False
```

**Email Template**:
```python
EMAIL_TEMPLATE = """
Subject: [CyberRed] Authorization Required - {urgency} Priority

An authorization request requires your attention.

Engagement: {engagement_id}
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
```

### Component Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| `ExternalNotificationConfig` | `src/cyberred/core/notifications.py` | Configuration dataclass |
| `ExternalNotifier` | `src/cyberred/core/notifications.py` | Notification manager |
| `NotificationPayload` | `src/cyberred/core/notifications.py` | Payload dataclass |
| API response endpoint | `src/cyberred/daemon/api.py` | `/api/v1/auth/respond/{token}` |
| Unit tests | `tests/unit/core/test_notifications.py` | Notification tests |
| Integration tests | `tests/integration/core/test_external_notifications.py` | Full flow tests |

### Existing Code to Leverage

**From Story 10.8** (`src/cyberred/daemon/deputy_escalation.py`):
- `DeputyEscalationManager` pattern - timer-based notification scheduling
- `parse_duration()` for delay parsing
- Async task management with cancellation

**From Story 10.3** (`src/cyberred/daemon/authorization_queue.py`):
- `AuthorizationRequest` dataclass - notification payload source
- `AuthorizationQueue` - integrate notification scheduling

**From `src/cyberred/core/config.py`**:
- `parse_duration()` function for delay parsing
- `ConfigurationError` for validation errors

**From `src/cyberred/core/audit.py`**:
- `AuthorizationAuditLogger` - extend for notification logging

**From `src/cyberred/daemon/state.py`**:
- `DaemonState.is_tui_attached` - check TUI presence

### UX Design References

- **Lines 518**: ExternalNotifier component for webhook/email alerts when disconnected
- **Lines 555**: Audio Alert: terminal bell for critical auth requests (configurable)
- **Lines 510**: AuthorizationModal timeout behavior (external notification is alternative)

### Integration Points

| Story | Dependency Type | What's Needed |
|-------|-----------------|---------------|
| 10.1 Authorization Request Modal | Foundation | AuthorizationRequest structure |
| 10.2 Authorization Response Handling | Foundation | Response processing |
| 10.3 Pending Authorization Queue | Foundation | Queue integration |
| 10.8 Deputy Operator Configuration | Pattern | Timer-based notification pattern |
| 2-9 Attach and Detach TUI Client | Integration | TUI presence detection |
| 3-3 Event Bus | Integration | TUI_ATTACHED/TUI_DETACHED events |

### Testing Requirements

**Unit Tests** (100% coverage required):
```bash
# Notification config and manager tests
pytest tests/unit/core/test_notifications.py \
    --cov=src/cyberred/core/notifications \
    --cov-report=term-missing --cov-fail-under=100
```

**Integration Tests**:
```bash
pytest tests/integration/core/test_external_notifications.py \
    --cov=src/cyberred --cov-report=term-missing
```

### Edge Cases to Handle

1. **Both webhook and email configured**: Send both in parallel
2. **TUI reconnects during notification delay**: Cancel pending notification
3. **Request resolved before delay expires**: Cancel notification
4. **SMTP server unreachable**: Retry with backoff, log failure, continue engagement
5. **Webhook returns non-2xx**: Treat as failure, retry
6. **Invalid response token**: Reject with 401 Unauthorized
7. **Token expired**: Reject with 410 Gone, request still in queue
8. **Email with special characters**: Proper escaping in templates

### Security Considerations

1. **Response tokens**: Signed with HMAC-SHA256, include expiry timestamp
2. **Webhook signatures**: X-Cyberred-Signature header for payload verification
3. **SMTP credentials**: Load from environment variables, not stored in config
4. **TLS required**: Default for both webhook (HTTPS) and email (STARTTLS)
5. **Rate limiting**: Max 1 notification per request (no spam on retries)

### Project Structure Notes

- New file: `src/cyberred/core/notifications.py` for ExternalNotifier
- New test file: `tests/unit/core/test_notifications.py`
- New test file: `tests/integration/core/test_external_notifications.py`
- Update existing: `src/cyberred/daemon/authorization_queue.py` for notification scheduling
- Update existing: `src/cyberred/daemon/api.py` for response endpoint
- Update existing: `src/cyberred/core/audit.py` for notification audit logging

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 10.9 lines 4301-4328]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Lines 518 ExternalNotifier component]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Lines 555 Audio Alert for critical requests]
- [Source: _bmad-output/planning-artifacts/architecture.md#Lines 874-887 TUI structure]
- [Source: _bmad-output/implementation-artifacts/10-8-deputy-operator-configuration.md - Timer pattern reference]
- [Source: src/cyberred/daemon/deputy_escalation.py - DeputyEscalationManager pattern]
- [Source: src/cyberred/daemon/authorization_queue.py - AuthorizationQueue integration]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A

### Completion Notes List

- Implemented `ExternalNotificationConfig` dataclass with webhook URL, email, SMTP settings, and notification delay validation (1-60 minutes)
- Implemented `NotificationPayload` dataclass for webhook/email content with serialization
- Implemented `ExternalNotifier` class with:
  - Async notification scheduling with TUI presence detection
  - Webhook delivery with HMAC-SHA256 signature (X-Cyberred-Signature header)
  - Email delivery via SMTP with TLS support
  - Exponential backoff retry logic (1s, 2s, 4s - max 3 attempts)
  - TUI attach/detach handling to cancel pending notifications
  - Signed response token generation for API endpoints
- All acceptance criteria met:
  - AC #1: Webhook fires with engagement_id, request_type, target, urgency, secure link
  - AC #2: Email notification with same payload
  - AC #3: Webhook retry with exponential backoff (3 attempts), failure logged
  - AC #4: Email retry with exponential backoff (3 attempts), failure logged
  - AC #5: TUI presence suppresses external notifications
  - AC #6: Response cancels pending notification
  - AC #7: All integration tests pass
- 55 tests (46 unit + 9 integration) all passing

### File List

**New Files:**
- `src/cyberred/core/notifications.py` - ExternalNotificationConfig, NotificationPayload, ExternalNotifier
- `tests/unit/core/test_notifications.py` - 46 unit tests
- `tests/integration/core/test_external_notifications.py` - 9 integration tests
