"""TDD Test for non-blocking time provider behavior."""
import time
from unittest.mock import MagicMock, patch
import pytest
from cyberred.core.time import TrustedTime

class TestNonBlockingNTP:
    """Verify that TrustedTime does not block main thread during sync."""

    def test_init_does_not_block(self):
        """Test that initialization returns immediately even if NTP is slow."""
        with patch("ntplib.NTPClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            
            # Simulate a slow NTP response (0.5s)
            def slow_request(*args, **kwargs):
                time.sleep(0.5)
                mock_response = MagicMock()
                mock_response.offset = 0.0
                return mock_response
            
            mock_client.request.side_effect = slow_request
            
            start = time.perf_counter()
            # This should spawn a background thread and return immediately
            provider = TrustedTime(ntp_server="pool.ntp.org")
            duration = time.perf_counter() - start
            
            # Should be significantly faster than the 0.5s sleep
            assert duration < 0.1, f"Initialization blocked for {duration:.4f}s"

    def test_now_does_not_block_on_resync(self):
        """Test that calling now() does not block even if sync is needed."""
        with patch("ntplib.NTPClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            
            # Simulate a slow NTP response
            def slow_request(*args, **kwargs):
                time.sleep(0.5)
                mock_response = MagicMock()
                mock_response.offset = 0.1
                return mock_response
            
            mock_client.request.side_effect = slow_request
            
            # Create provider and force it to need a sync
            provider = TrustedTime()
            # Initialize internal state to simulate expired TTL
            provider._last_sync = 0.0  # Way in the past
            provider._sync_ttl = 1.0
            
            start = time.perf_counter()
            # This triggers _ensure_synced. In blocking impl, this waits 0.5s.
            # In non-blocking, it should trigger thread and return cached/local result immediately.
            _ = provider.now()
            duration = time.perf_counter() - start
            
            assert duration < 0.1, f"now() blocked for {duration:.4f}s"
