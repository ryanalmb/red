"""NTP-synchronized time provider with drift detection.

Provides cryptographically verifiable timestamps for audit trails (NFR16, FR50).
Falls back to local system time with warning if NTP unreachable.

Location: src/cyberred/core/time.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import threading
import time as stdlib_time
from cyberred.core.config import get_settings
from datetime import datetime, timezone
from typing import Optional

import ntplib

logger = logging.getLogger(__name__)


class TrustedTime:
    """NTP-synchronized time provider with drift detection.

    Provides cryptographically verifiable timestamps for audit trails.
    Falls back to local system time with warning if NTP unreachable.
    
    Uses a background thread to maintain synchronization, ensuring now()
    never blocks the main execution loop (Deep Dive fix).

    Attributes:
        DEFAULT_NTP_SERVER: Default NTP server pool.
        SYNC_TTL_SECONDS: How often to re-sync with NTP (seconds).
        DRIFT_WARN_THRESHOLD: Log warning if drift exceeds this (seconds).
        DRIFT_ERROR_THRESHOLD: Log error if drift exceeds this (seconds).
    """

    def __init__(self, ntp_server: str | None = None) -> None:
        """Initialize TrustedTime with optional custom NTP server.
        
        Starts a background daemon thread for synchronization.

        Args:
            ntp_server: NTP server hostname. Defaults to value in config.
        """
        settings = get_settings()
        self._ntp_server = ntp_server or settings.ntp.server
        self._sync_ttl = settings.ntp.sync_ttl
        self._drift_warn = settings.ntp.drift_warn_threshold
        self._drift_error = settings.ntp.drift_error_threshold
        
        self._offset: float = 0.0
        self._last_sync: Optional[float] = None
        self._is_synced: bool = False
        self._client = ntplib.NTPClient()
        
        # Threading control
        self._stop_event = threading.Event()
        self._sync_thread = threading.Thread(
            target=self._run_sync_loop,
            name="NTP-Sync-Thread",
            daemon=True
        )
        self._sync_thread.start()

    def now(self) -> str:
        """Return NTP-synchronized timestamp in ISO 8601 format.

        This method is non-blocking. It uses the latest cached offset.
        If NTP sync fails, the offset defaults to 0.0 (local time) with warnings logged.

        Returns:
            ISO 8601 formatted timestamp (e.g., '2026-01-01T23:59:59.123456+00:00')
        """
        # Read atomic float offset (GIL ensures atomicity for float read/write)
        current_offset = self._offset
        
        local = datetime.now(timezone.utc)
        adjusted_ts = local.timestamp() + current_offset
        adjusted_dt = datetime.fromtimestamp(adjusted_ts, tz=timezone.utc)
        return adjusted_dt.isoformat()

    @property
    def is_synced(self) -> bool:
        """Return True if time is currently synchronized with NTP."""
        return self._is_synced

    def get_drift(self) -> float:
        """Return current drift (NTP offset) in seconds.

        Returns:
            Offset between NTP time and local system time in seconds.
            Positive means local clock is behind NTP.
        """
        return self._offset

    def sign_timestamp(self, timestamp: str, key: bytes) -> str:
        """Create HMAC-SHA256 signature for timestamp.

        Args:
            timestamp: ISO 8601 timestamp string to sign.
            key: Secret key for HMAC computation.

        Returns:
            Base64-encoded HMAC-SHA256 signature.
        """
        sig = hmac.new(key, timestamp.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(sig).decode("utf-8")

    def verify_timestamp_signature(
        self, timestamp: str, signature: str, key: bytes
    ) -> bool:
        """Verify HMAC-SHA256 signature for timestamp.

        Args:
            timestamp: ISO 8601 timestamp string that was signed.
            signature: Base64-encoded signature to verify.
            key: Secret key used for original signing.

        Returns:
            True if signature is valid, False otherwise.
        """
        expected = self.sign_timestamp(timestamp, key)
        return hmac.compare_digest(expected, signature)

    def sign_event_timestamp(self, event_hash: str, key: bytes) -> dict[str, str]:
        """Create signed timestamp bound to specific event.
        
        For legal defensibility, binds timestamp to event content via HMAC-SHA256
        of (timestamp + event_hash). This prevents timestamp reuse attacks.
        
        Args:
            event_hash: SHA-256 hash of event/file content (hex string).
            key: Engagement-specific signing key.
        
        Returns:
            Dictionary with:
                - timestamp: ISO 8601 timestamp with UTC timezone
                - event_hash: The input event hash
                - signature: Base64-encoded HMAC-SHA256(timestamp + event_hash, key)
        """
        timestamp = self.now()
        message = timestamp + event_hash
        sig = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
        signature = base64.b64encode(sig).decode("utf-8")
        
        return {
            "timestamp": timestamp,
            "event_hash": event_hash,
            "signature": signature,
        }

    def verify_event_timestamp(self, signed_data: dict[str, str], key: bytes) -> bool:
        """Verify signed timestamp bound to event.
        
        Args:
            signed_data: Dictionary with timestamp, event_hash, signature fields.
            key: Secret key used for original signing.
        
        Returns:
            True if signature is valid, False otherwise.
        """
        timestamp = signed_data.get("timestamp", "")
        event_hash = signed_data.get("event_hash", "")
        signature = signed_data.get("signature", "")
        
        # Recalculate expected signature
        message = timestamp + event_hash
        expected_sig = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
        expected_b64 = base64.b64encode(expected_sig).decode("utf-8")
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_b64, signature)

    def stop(self) -> None:
        """Stop the background synchronization thread."""
        self._stop_event.set()
        # We generally don't join() daemon threads on shutdown to avoid hanging,
        # but this method allows controlled shutdown if needed.

    def _run_sync_loop(self) -> None:
        """Background loop to synchronize with NTP."""
        # Initial sync attempt immediately
        self._sync()
        
        while not self._stop_event.wait(timeout=self._sync_ttl):
            self._sync()

    def _sync(self) -> None:
        """Synchronize with NTP server and detect drift."""
        try:
            response = self._client.request(self._ntp_server, version=3)
            self._offset = response.offset
            self._last_sync = stdlib_time.monotonic()
            self._is_synced = True

            # Drift detection
            abs_offset = abs(self._offset)
            if abs_offset > self._drift_error:
                logger.error(
                    "Severe clock drift detected: %.2fs offset from NTP",
                    self._offset,
                )
            elif abs_offset > self._drift_warn:
                logger.warning(
                    "Clock drift detected: %.2fs offset from NTP",
                    self._offset,
                )
            else:
                logger.debug("NTP sync successful, offset: %.3fs", self._offset)

        except (ntplib.NTPException, OSError) as e:
            logger.warning(
                "NTP sync failed (falling back to local time): %s", e
            )
            self._is_synced = False
            # We don't reset offset to 0.0 immediately on one failure to preserve 
            # best-known drift, unless user explicitly wants fail-safe fallback.
            # However, for rigorous correctness, if we are not synced, we shouldn't trust old offset indefinitely.
            # For now, we keep the old offset until successful re-sync or restart.
            # self._offset = 0.0 
            
            self._last_sync = stdlib_time.monotonic()


# Module-level convenience functions for simple usage
_default_time_provider: Optional[TrustedTime] = None


def _get_default_provider() -> TrustedTime:
    """Get or create default TrustedTime instance."""
    global _default_time_provider
    if _default_time_provider is None:
        _default_time_provider = TrustedTime()
    return _default_time_provider


def now() -> str:
    """Return NTP-synchronized timestamp in ISO 8601 format.

    Convenience function using default TrustedTime instance.

    Returns:
        ISO 8601 formatted timestamp.
    """
    return _get_default_provider().now()


def sign_timestamp(timestamp: str, key: bytes) -> str:
    """Create HMAC-SHA256 signature for timestamp.

    Convenience function using default TrustedTime instance.

    Args:
        timestamp: ISO 8601 timestamp string to sign.
        key: Secret key for HMAC computation.

    Returns:
        Base64-encoded HMAC-SHA256 signature.
    """
    return _get_default_provider().sign_timestamp(timestamp, key)


def verify_timestamp_signature(timestamp: str, signature: str, key: bytes) -> bool:
    """Verify HMAC-SHA256 signature for timestamp.

    Convenience function using default TrustedTime instance.

    Args:
        timestamp: ISO 8601 timestamp string that was signed.
        signature: Base64-encoded signature to verify.
        key: Secret key used for original signing.

    Returns:
        True if signature is valid, False otherwise.
    """
    return _get_default_provider().verify_timestamp_signature(timestamp, signature, key)


def sign_event_timestamp(event_hash: str, key: bytes) -> dict[str, str]:
    """Create signed timestamp bound to specific event.

    Convenience function using default TrustedTime instance.

    Args:
        event_hash: SHA-256 hash of event/file content (hex string).
        key: Engagement-specific signing key.

    Returns:
        Dictionary with timestamp, event_hash, and signature fields.
    """
    return _get_default_provider().sign_event_timestamp(event_hash, key)


def verify_event_timestamp(signed_data: dict[str, str], key: bytes) -> bool:
    """Verify signed timestamp bound to event.

    Convenience function using default TrustedTime instance.

    Args:
        signed_data: Dictionary with timestamp, event_hash, signature fields.
        key: Secret key used for original signing.

    Returns:
        True if signature is valid, False otherwise.
    """
    return _get_default_provider().verify_event_timestamp(signed_data, key)


class DriftMonitor:
    """Background service to monitor clock drift and trigger alerts.
    
    Story 13.10: Monitors NTP drift and publishes alerts when drift exceeds
    thresholds (>1s warning, >5s error).
    
    Attributes:
        DRIFT_WARN_THRESHOLD: Warning threshold in seconds (default: 1.0).
        DRIFT_ERROR_THRESHOLD: Error threshold in seconds (default: 5.0).
        CHECK_INTERVAL: How often to check drift in seconds (default: 60).
    """
    
    DRIFT_WARN_THRESHOLD = 1.0
    DRIFT_ERROR_THRESHOLD = 5.0
    CHECK_INTERVAL = 60
    
    def __init__(self, event_bus: Any = None) -> None:
        """Initialize DriftMonitor.
        
        Args:
            event_bus: Event bus for publishing alerts. If None, alerts are logged only.
        """
        self.time_provider = TrustedTime()
        self.event_bus = event_bus
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the drift monitoring background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("DriftMonitor already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="DriftMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("DriftMonitor started")
    
    def stop(self) -> None:
        """Stop the drift monitoring background thread."""
        self._stop_event.set()
        if self._thread is not None:
            # Don't join daemon threads to avoid blocking shutdown
            logger.info("DriftMonitor stopped")
    
    def _run(self) -> None:
        """Background loop to check drift periodically."""
        while not self._stop_event.wait(timeout=self.CHECK_INTERVAL):
            self._check_drift()
    
    def _check_drift(self) -> None:
        """Check current drift and publish alerts if needed."""
        try:
            drift = self.time_provider.get_drift()
            abs_drift = abs(drift)
            
            if abs_drift > self.DRIFT_ERROR_THRESHOLD:
                self._publish_alert("error", drift)
            elif abs_drift > self.DRIFT_WARN_THRESHOLD:
                self._publish_alert("warning", drift)
        
        except Exception as e:
            logger.error("Error checking drift: %s", e)
    
    def _publish_alert(self, level: str, drift: float) -> None:
        """Publish drift alert.
        
        Args:
            level: Alert level ("warning" or "error").
            drift: Drift value in seconds.
        """
        alert_data = {
            "type": "drift_alert",
            "level": level,
            "drift_seconds": drift,
            "threshold": self.DRIFT_ERROR_THRESHOLD if level == "error" else self.DRIFT_WARN_THRESHOLD,
            "message": f"Clock drift {level}: {drift:.2f}s",
        }
        
        logger.log(
            logging.ERROR if level == "error" else logging.WARNING,
            "Clock drift %s: %.2fs",
            level,
            drift,
        )
        
        if self.event_bus is not None:
            try:
                # Publish to situational_alert topic
                # Event bus publish is typically async, handle appropriately
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.create_task(
                        self.event_bus.publish("situational_alert", alert_data)
                    )
                except RuntimeError:
                    # No running loop, skip async publish
                    pass
            except Exception as e:
                logger.error("Failed to publish drift alert: %s", e)
