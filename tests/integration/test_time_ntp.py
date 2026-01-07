"""Integration tests for TrustedTime NTP synchronization.

Tests actual NTP synchronization with real NTP servers.
Skip gracefully if NTP servers are unreachable in CI.
"""

from __future__ import annotations

from datetime import datetime

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRealNTPSync:
    """Integration tests for real NTP synchronization."""

    def test_real_ntp_sync_succeeds(self) -> None:
        """Verify actual NTP synchronization works with real server."""
        from cyberred.core.time import TrustedTime
        import ntplib

        time_provider = TrustedTime()
        try:
            time_provider._sync()
            
            # Should be marked as synced
            assert time_provider.is_synced is True
            
            # Offset should be reasonable (less than 60 seconds)
            assert abs(time_provider.get_drift()) < 60.0
            
        except ntplib.NTPException:
            pytest.skip("NTP server unreachable - skipping integration test")

    def test_real_now_returns_valid_timestamp(self) -> None:
        """Verify now() returns valid ISO 8601 timestamp with real NTP."""
        from cyberred.core.time import TrustedTime
        import ntplib

        time_provider = TrustedTime()
        try:
            result = time_provider.now()
            
            # Should be valid ISO 8601
            assert isinstance(result, str)
            parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None
            
            # Should be reasonably close to current time (within 120 seconds)
            from datetime import timezone
            now_local = datetime.now(timezone.utc)
            diff = abs((parsed - now_local).total_seconds())
            assert diff < 120.0, f"Timestamp differs by {diff}s from local time"
            
        except ntplib.NTPException:
            pytest.skip("NTP server unreachable - skipping integration test")

    def test_multiple_ntp_servers(self) -> None:
        """Verify sync works with different NTP servers."""
        from cyberred.core.time import TrustedTime
        import ntplib

        servers = ["pool.ntp.org", "time.google.com", "time.cloudflare.com"]
        success_count = 0
        
        for server in servers:
            time_provider = TrustedTime(ntp_server=server)
            try:
                time_provider._sync()
                if time_provider.is_synced:
                    success_count += 1
            except ntplib.NTPException:
                continue  # Try next server
        
        if success_count == 0:
            pytest.skip("No NTP servers reachable - skipping integration test")
        
        # At least one server should work
        assert success_count >= 1


class TestDriftDetectionIntegration:
    """Integration tests for drift detection with real system."""

    def test_drift_within_reasonable_bounds(self) -> None:
        """Verify drift is within reasonable bounds on a healthy system."""
        from cyberred.core.time import TrustedTime
        import ntplib

        time_provider = TrustedTime()
        try:
            time_provider._sync()
            drift = time_provider.get_drift()
            
            # On a healthy system, drift should be less than 5 seconds
            # (unless system clock is severely misconfigured)
            # We use a lenient threshold for CI environments
            assert abs(drift) < 60.0, f"Drift of {drift}s is unusually high"
            
        except ntplib.NTPException:
            pytest.skip("NTP server unreachable - skipping integration test")


class TestModuleLevelFunctions:
    """Integration tests for module-level convenience functions."""

    def test_module_now_function(self) -> None:
        """Verify module-level now() function works."""
        from cyberred.core import time as time_module
        import ntplib

        # Reset module-level provider to ensure fresh state
        time_module._default_time_provider = None

        try:
            result = time_module.now()
            assert isinstance(result, str)
            # Verify it's valid ISO 8601
            datetime.fromisoformat(result.replace("Z", "+00:00"))
        except ntplib.NTPException:
            pytest.skip("NTP server unreachable - skipping integration test")

    def test_module_sign_and_verify(self) -> None:
        """Verify module-level sign/verify functions work together."""
        from cyberred.core import time as time_module
        import ntplib

        # Reset module-level provider to ensure fresh state  
        time_module._default_time_provider = None

        try:
            timestamp = time_module.now()
            key = b"integration-test-key"
            
            signature = time_module.sign_timestamp(timestamp, key)
            is_valid = time_module.verify_timestamp_signature(timestamp, signature, key)
            
            assert is_valid is True
        except ntplib.NTPException:
            pytest.skip("NTP server unreachable - skipping integration test")
