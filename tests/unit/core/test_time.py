"""Unit tests for TrustedTime NTP synchronization module.

Tests follow TDD cycle for the new threaded implementation.
Mock threading.Thread to avoid real threads in unit tests, except where specifically testing concurrency.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from cyberred.core.time import TrustedTime

# Patch threading.Thread globally for this module to prevent side effects
@pytest.fixture(autouse=True)
def mock_thread():
    with patch("cyberred.core.time.threading.Thread") as mock:
        yield mock

class TestTrustedTimeInit:
    """Tests for initialization and thread startup."""

    def test_init_starts_daemon_thread(self, mock_thread):
        """Verify __init__ starts a daemon thread for sync loop."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            
            # Check thread creation
            mock_thread.assert_called_once()
            _, kwargs = mock_thread.call_args
            assert kwargs["target"] == time_provider._run_sync_loop
            assert kwargs["daemon"] is True
            assert kwargs["name"] == "NTP-Sync-Thread"
            
            # Check thread start
            mock_thread.return_value.start.assert_called_once()

    def test_stop_sets_event(self, mock_thread):
        """Verify stop() sets the stop event."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            time_provider.stop()
            assert time_provider._stop_event.is_set()


class TestTrustedTimeNow:
    """Tests for TrustedTime.now() method."""

    def test_now_uses_cached_offset(self):
        """Verify now() uses the internal _offset."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            # Manually set offset
            time_provider._offset = 3600.0  # 1 hour ahead
            
            result = time_provider.now()
            
            # Should be roughly 1 hour ahead of UTC now
            from datetime import datetime, timezone, timedelta
            now_utc = datetime.now(timezone.utc)
            parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
            
            diff = parsed - now_utc
            assert timedelta(minutes=59) < diff < timedelta(minutes=61)

    def test_now_returns_iso8601_format(self) -> None:
        """Verify timestamp format is ISO 8601 with UTC timezone."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            result = time_provider.now()
            assert "+" in result or "Z" in result
            from datetime import datetime
            parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None


class TestTrustedTimeSyncLogic:
    """Tests for the _sync method logic (drift detection, etc)."""

    def test_sync_updates_offset_on_success(self, caplog):
        """Verify _sync updates offset and logs debug."""
        with patch("cyberred.core.time.ntplib.NTPClient") as mock_client:
            mock_response = Mock()
            mock_response.offset = 0.5
            mock_client.return_value.request.return_value = mock_response

            with caplog.at_level(logging.DEBUG):
                time_provider = TrustedTime()
                time_provider._sync()
                
            assert time_provider._offset == 0.5
            assert time_provider.is_synced is True
            assert "NTP sync successful" in caplog.text

    def test_sync_logs_warning_on_drift(self, caplog):
        """Verify warning logged on medium drift."""
        with patch("cyberred.core.time.ntplib.NTPClient") as mock_client:
            mock_response = Mock()
            mock_response.offset = 2.0  # > 1.0 (warn)
            mock_client.return_value.request.return_value = mock_response

            time_provider = TrustedTime()
            time_provider._sync()
            
            assert "Clock drift detected" in caplog.text
            assert "Severe" not in caplog.text

    def test_sync_logs_error_on_severe_drift(self, caplog):
        """Verify error logged on severe drift."""
        with patch("cyberred.core.time.ntplib.NTPClient") as mock_client:
            mock_response = Mock()
            mock_response.offset = 10.0  # > 5.0 (error)
            mock_client.return_value.request.return_value = mock_response

            with caplog.at_level(logging.ERROR):
                time_provider = TrustedTime()
                time_provider._sync()
            
            assert "Severe clock drift detected" in caplog.text

    def test_sync_handles_exception(self, caplog):
        """Verify exception handling during sync."""
        import ntplib
        with patch("cyberred.core.time.ntplib.NTPClient") as mock_client:
            mock_client.return_value.request.side_effect = ntplib.NTPException("fail")

            time_provider = TrustedTime()
            time_provider._is_synced = True # Setup previous state
            
            time_provider._sync()
            
            assert time_provider.is_synced is False
            assert "NTP sync failed" in caplog.text
            # Offset should remain (or become 0.0 depending on partial impl, currently we asserted valid in code)
            # In validation we saw we commented out resetting offset to 0.0.
            # So offset should persist.


class TestSyncLoop:
    """Tests for _run_sync_loop logic."""

    def test_loop_calls_sync_multiple_times(self):
        """Verify loop keeps calling sync until stopped."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            
            # Mock _sync and _stop_event.wait
            time_provider._sync = Mock()
            
            # wait checks: return False (timeout/continue) twice, then True (stop)
            # wait(timeout) returns True if flag is set, False if timeout.
            # We want: 
            # 1. wait() -> False (continues loop, calls sync)
            # 2. wait() -> True (exit loop)
            # Note: _run_sync_loop calls _sync() ONCE before entering loop
            
            time_provider._stop_event.wait = Mock(side_effect=[False, True])
            
            time_provider._run_sync_loop()
            
            # Should call _sync 3 times:
            # 1. Initial call
            # 2. After first wait (False)
            # 3. Stop (wait returns True, loop terminates) -> wait... logic: while not wait(): sync()
            # so:
            # start -> sync(1)
            # wait() -> False -> sync(2)
            # wait() -> True -> loop ends.
            assert time_provider._sync.call_count == 2


class TestTimestampSigning:
    """Tests for timestamp cryptographic signing (unchanged logic)."""

    def test_sign_verify_roundtrip(self):
        """Verify signing and verifying works."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            ts = "2026-01-01T12:00:00+00:00"
            key = b"secret"
            sig = time_provider.sign_timestamp(ts, key)
            assert time_provider.verify_timestamp_signature(ts, sig, key)
            assert not time_provider.verify_timestamp_signature(ts, sig, b"wrong")


class TestModuleFunctions:
    """Tests for module-level functions."""
    
    def test_get_drift(self):
        """Verify get_drift returns offset."""
        with patch("cyberred.core.time.ntplib.NTPClient"):
            time_provider = TrustedTime()
            time_provider._offset = 1.23
            assert time_provider.get_drift() == 1.23

    def test_module_sign_verify(self):
        """Verify module-level sign and verify functions."""
        from cyberred.core import time as time_mod
        time_mod._default_time_provider = None
        
        with patch("cyberred.core.time.ntplib.NTPClient"):
            ts = "2026-01-01T12:00:00+00:00"
            key = b"secret"
            sig = time_mod.sign_timestamp(ts, key)
            assert isinstance(sig, str)
            assert time_mod.verify_timestamp_signature(ts, sig, key)
    def test_module_now(self):
        # We need to ensure the default singleton is reset or mocked
        from cyberred.core import time as time_mod
        time_mod._default_time_provider = None
        
        with patch("cyberred.core.time.ntplib.NTPClient"):
            res = time_mod.now()
            assert isinstance(res, str)
