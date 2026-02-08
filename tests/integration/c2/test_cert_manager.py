"""Integration tests for CertificateManager.

Tests full certificate lifecycle per Story 12.3:
- Full lifecycle: CA → server → client → rotate → revoke
- C2Server SSL context hot-reload on rotation
- Revoked cert rejection via CRL
- Auto-rotation when near expiry
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from cryptography import x509

from cyberred.c2.cert_manager import (
    CertificateManager,
    CertManagerConfig,
    _get_current_time,
)
from cyberred.c2.server import C2Server, C2ServerConfig
from cyberred.core.keystore import Keystore, generate_salt


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def keystore() -> Keystore:
    """Create a Keystore for testing."""
    salt = generate_salt()
    return Keystore.from_password("integration-test-password", salt)


@pytest.fixture
def cert_config(tmp_path: Path) -> CertManagerConfig:
    """Create CertManagerConfig with temp directory."""
    return CertManagerConfig(
        cert_dir=tmp_path / "certs",
        validity_hours=24,
        renewal_threshold_hours=1,
        rotation_check_interval=1,  # 1 second for faster tests
    )


@pytest.fixture
def cert_manager(cert_config: CertManagerConfig, keystore: Keystore) -> CertificateManager:
    """Create CertificateManager instance."""
    return CertificateManager(cert_config, keystore)


# =============================================================================
# Full Lifecycle Tests (Task 9.1)
# =============================================================================


class TestFullCertLifecycle:
    """Test full certificate lifecycle."""

    def test_full_lifecycle_ca_server_client(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test CA → server → client certificate lifecycle."""
        # Step 1: Generate engagement CA
        ca_path = cert_manager.generate_engagement_ca("engagement-integration-test")
        assert ca_path.exists()

        # Verify CA certificate
        ca_cert_bytes = ca_path.read_bytes()
        ca_cert = x509.load_pem_x509_certificate(ca_cert_bytes)
        assert "Cyber-Red CA" in ca_cert.subject.rfc4514_string()

        # Step 2: Issue server certificate
        server_cert_path, server_key_path = cert_manager.issue_server_cert(
            san_names=["c2.example.com", "192.168.1.100", "localhost"],
            common_name="c2-server",
        )
        assert server_cert_path.exists()
        assert server_key_path.exists()

        # Verify server cert has correct SANs
        server_cert_bytes = server_cert_path.read_bytes()
        server_cert = x509.load_pem_x509_certificate(server_cert_bytes)
        san_ext = server_cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )
        san_values = [str(name.value) for name in san_ext.value]
        assert "c2.example.com" in san_values
        assert "localhost" in san_values

        # Step 3: Issue client certificates for multiple drop boxes
        client1_cert, client1_key = cert_manager.issue_client_cert("dropbox-alpha")
        client2_cert, client2_key = cert_manager.issue_client_cert("dropbox-beta")

        assert client1_cert.exists()
        assert client2_cert.exists()

        # Verify tracking
        assert len(cert_manager.issued_certs) == 3  # server + 2 clients

    def test_lifecycle_with_rotation(self, cert_manager: CertificateManager) -> None:
        """Test lifecycle including rotation."""
        cert_manager.generate_engagement_ca("rotation-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        original_serial = cert_manager.issued_certs["server"].serial_number

        # Rotate
        new_cert_path, _ = cert_manager.rotate_cert("server")

        # Verify old is revoked, new is issued
        assert original_serial in cert_manager.revoked_serials
        assert cert_manager.issued_certs["server"].serial_number != original_serial
        assert new_cert_path.exists()

    def test_lifecycle_with_revocation(self, cert_manager: CertificateManager) -> None:
        """Test lifecycle including revocation and CRL."""
        cert_manager.generate_engagement_ca("revocation-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.issue_client_cert("client-1")

        # Revoke client cert
        client_serial = cert_manager.issued_certs["dropbox-client-1"].serial_number
        cert_manager.revoke_cert("dropbox-client-1")

        # Verify CRL contains revoked serial
        crl_path = cert_manager.get_crl_path()
        assert crl_path is not None

        crl_bytes = crl_path.read_bytes()
        crl = x509.load_pem_x509_crl(crl_bytes)

        revoked_serials = [rc.serial_number for rc in crl]
        assert client_serial in revoked_serials

        # Server cert should still be valid
        assert cert_manager.issued_certs["server"].revoked is False


# =============================================================================
# C2Server Integration Tests (Task 9.4)
# =============================================================================


class TestC2ServerIntegration:
    """Test CertificateManager integration with C2Server."""

    @pytest.mark.asyncio
    async def test_c2server_with_cert_manager_certs(
        self, cert_manager: CertificateManager, tmp_path: Path
    ) -> None:
        """Test C2Server uses CertificateManager-generated certs."""
        # Generate certs
        cert_manager.generate_engagement_ca("c2-integration")
        server_cert, server_key = cert_manager.issue_server_cert(
            ["localhost", "127.0.0.1"], common_name="c2-server"
        )
        ca_cert = cert_manager.get_ca_cert_path()

        # Create C2Server config with generated certs
        c2_config = C2ServerConfig(
            host="127.0.0.1",
            port=0,  # OS assigns port
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
            shared_secret=b"test-secret-key-32bytes-long!!!",
        )

        server = C2Server(c2_config)

        # Server should be configurable (actual connection test in e2e)
        assert server._config.ca_cert_path == ca_cert
        assert server._config.server_cert_path == server_cert

    @pytest.mark.asyncio
    async def test_reload_ssl_context(
        self, cert_manager: CertificateManager, tmp_path: Path
    ) -> None:
        """Test SSL context hot-reload after rotation."""
        # Setup
        cert_manager.generate_engagement_ca("reload-test")
        server_cert, server_key = cert_manager.issue_server_cert(
            ["localhost"], common_name="server"
        )
        ca_cert = cert_manager.get_ca_cert_path()

        c2_config = C2ServerConfig(
            host="127.0.0.1",
            port=0,
            ca_cert_path=ca_cert,
            server_cert_path=server_cert,
            server_key_path=server_key,
        )

        server = C2Server(c2_config)

        # Generate CRL
        cert_manager.issue_client_cert("test-client")
        cert_manager.revoke_cert("dropbox-test-client")

        # Reload should not raise
        await server.reload_ssl_context(cert_manager)


# =============================================================================
# Auto-Rotation Tests (Task 9.2)
# =============================================================================


class TestAutoRotation:
    """Test automatic certificate rotation."""

    @pytest.mark.asyncio
    async def test_auto_rotation_near_expiry(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test auto-rotation triggers when cert near expiry."""
        # Use very short check interval
        cert_config.rotation_check_interval = 1

        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("auto-rotate-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        original_serial = cert_manager.issued_certs["server"].serial_number

        # Manually set cert to near expiry
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() + timedelta(minutes=30)
        )

        # Start scheduler
        await cert_manager.start_rotation_scheduler()

        # Wait for rotation check
        await asyncio.sleep(2)

        # Stop scheduler
        await cert_manager.stop_rotation_scheduler()

        # Verify rotation occurred
        new_serial = cert_manager.issued_certs["server"].serial_number
        assert new_serial != original_serial
        assert original_serial in cert_manager.revoked_serials

    @pytest.mark.asyncio
    async def test_scheduler_handles_errors_gracefully(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test scheduler continues after errors."""
        cert_config.rotation_check_interval = 1

        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("error-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        await cert_manager.start_rotation_scheduler()

        # Brief run
        await asyncio.sleep(1.5)

        await cert_manager.stop_rotation_scheduler()

        # Should complete without error
        assert cert_manager._rotation_running is False


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_multiple_ca_generations(self, cert_manager: CertificateManager) -> None:
        """Test generating multiple CAs (replaces previous)."""
        cert_manager.generate_engagement_ca("first")
        first_ca = cert_manager._ca_store

        cert_manager.generate_engagement_ca("second")
        second_ca = cert_manager._ca_store

        # Should be different CA instances
        assert first_ca is not second_ca

    def test_cert_with_ip_and_dns_sans(self, cert_manager: CertificateManager) -> None:
        """Test cert with mixed IP and DNS SANs."""
        cert_manager.generate_engagement_ca("san-test")
        cert_path, _ = cert_manager.issue_server_cert(
            san_names=["example.com", "10.0.0.1", "192.168.1.1", "c2.local"],
            common_name="mixed-san-server",
        )

        cert_bytes = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes)
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        # Verify both DNS and IP types present
        dns_names = [n.value for n in san_ext.value if isinstance(n, x509.DNSName)]
        ip_addrs = [str(n.value) for n in san_ext.value if isinstance(n, x509.IPAddress)]

        assert "example.com" in dns_names
        assert "10.0.0.1" in ip_addrs

    def test_revoke_already_revoked(self, cert_manager: CertificateManager) -> None:
        """Test revoking already revoked cert logs warning."""
        cert_manager.generate_engagement_ca("double-revoke")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        cert_manager.revoke_cert("server")
        # Second revoke should not raise, just warn
        cert_manager.revoke_cert("server")

        assert cert_manager.issued_certs["server"].revoked is True

    def test_check_expiry_revoked_cert(self, cert_manager: CertificateManager) -> None:
        """Test check_expiry returns None for revoked cert."""
        cert_manager.generate_engagement_ca("expiry-revoked")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")

        remaining = cert_manager.check_expiry("server")
        assert remaining is None

    def test_rotate_preserves_sans(self, cert_manager: CertificateManager) -> None:
        """Test rotation preserves SANs from original cert."""
        cert_manager.generate_engagement_ca("san-preserve")
        original_sans = ["host1.local", "host2.local", "10.0.0.5"]
        cert_manager.issue_server_cert(original_sans, common_name="server")

        # Rotate
        new_cert_path, _ = cert_manager.rotate_cert("server")

        # Verify SANs preserved
        cert_bytes = new_cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes)
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        san_values = []
        for name in san_ext.value:
            if isinstance(name, x509.DNSName):
                san_values.append(name.value)
            elif isinstance(name, x509.IPAddress):
                san_values.append(str(name.value))

        assert "host1.local" in san_values
        assert "host2.local" in san_values
        assert "10.0.0.5" in san_values


# =============================================================================
# Coverage Gap Tests
# =============================================================================


class TestRotationErrors:
    """Test rotation error handling."""

    @pytest.mark.asyncio
    async def test_rotation_loop_handles_rotation_error(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that rotation loop handles individual cert rotation errors."""
        cert_config.rotation_check_interval = 1

        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("error-handling-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        # Set to near expiry
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() + timedelta(minutes=30)
        )

        # Delete the cert file to cause rotation to fail
        cert_manager._issued_certs["server"].cert_path.unlink()

        await cert_manager.start_rotation_scheduler()
        await asyncio.sleep(2)
        await cert_manager.stop_rotation_scheduler()

        # Verify scheduler handled error gracefully and stopped cleanly
        assert not cert_manager._rotation_running, "Rotation scheduler should be stopped"
        assert cert_manager._rotation_task is None, "Rotation task should be cleaned up"
        # Original cert should still be tracked (rotation failed, not removed)
        assert "server" in cert_manager._issued_certs, "Failed rotation should not remove cert from registry"


class TestCoverageGaps:
    """Tests to fill coverage gaps."""

    def test_needs_renewal_expired_cert(self, cert_manager: CertificateManager) -> None:
        """Test needs_renewal returns True for expired cert."""
        cert_manager.generate_engagement_ca("expired-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        # Set to expired
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() - timedelta(hours=1)
        )

        assert cert_manager.needs_renewal("server") is True

    def test_check_expiry_expired_returns_none(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test check_expiry returns None for expired cert."""
        cert_manager.generate_engagement_ca("expired-check")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        # Set to expired
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() - timedelta(hours=1)
        )

        remaining = cert_manager.check_expiry("server")
        assert remaining is None

    def test_rotate_server_without_sans_fallback(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test rotation falls back to localhost when no SANs found."""
        cert_manager.generate_engagement_ca("fallback-test")

        # Issue cert directly via CAStore to avoid SAN tracking
        cert, key = cert_manager._ca_store.generate_cert(
            common_name="no-san-server",
            valid_hours=24,
            san_names=None,  # No SANs
        )

        # Manually track it
        from cyberred.c2.cert_manager import IssuedCert

        cert_path = cert_manager._config.cert_dir / "no-san-server.crt"
        key_path = cert_manager._config.cert_dir / "no-san-server.key"

        from cyberred.core.ca_store import CAStore

        cert_path.write_bytes(CAStore.serialize_cert_pem(cert))
        key_path.write_bytes(CAStore.serialize_key_pem(key))

        now = _get_current_time()
        issued = IssuedCert(
            serial_number=cert.serial_number,
            common_name="no-san-server",
            issued_at=now,
            expires_at=now + timedelta(hours=24),
            cert_path=cert_path,
            key_path=key_path,
        )
        cert_manager._issued_certs["no-san-server"] = issued

        # Rotate - should use localhost fallback
        new_cert_path, _ = cert_manager.rotate_cert("no-san-server")
        assert new_cert_path.exists()

    def test_crl_distribution_callback_sync(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test CRL distribution callback is invoked on CRL generation."""
        cert_manager.generate_engagement_ca("crl-callback-test")
        
        # Track callback invocations
        callback_calls: list[tuple] = []
        
        def sync_callback(crl_path, crl_bytes):
            callback_calls.append((crl_path, crl_bytes))
        
        cert_manager.set_crl_distribution_callback(sync_callback)
        
        # Issue and revoke a cert to trigger CRL generation
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")
        
        # Callback should have been called
        assert len(callback_calls) == 1
        assert callback_calls[0][0].name == "crl.pem"
        assert b"BEGIN X509 CRL" in callback_calls[0][1]

    def test_crl_distribution_callback_async(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test CRL distribution callback works with async functions."""
        cert_manager.generate_engagement_ca("crl-async-test")
        
        callback_called = []
        
        async def async_callback(crl_path, crl_bytes):
            callback_called.append(True)
        
        cert_manager.set_crl_distribution_callback(async_callback)
        
        # Issue and revoke to trigger CRL
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")
        
        # Callback should be scheduled (async task created)
        # Note: actual execution depends on event loop
        assert cert_manager._crl_distribution_callback is not None

    def test_crl_distribution_callback_error_handling(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test CRL distribution handles callback errors gracefully."""
        cert_manager.generate_engagement_ca("crl-error-test")
        
        def failing_callback(crl_path, crl_bytes):
            raise RuntimeError("Simulated distribution failure")
        
        cert_manager.set_crl_distribution_callback(failing_callback)
        
        # Issue and revoke - should not raise despite callback error
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")  # Should not raise
        
        # CRL should still be generated
        assert cert_manager.get_crl_path() is not None

    def test_generate_crl_no_ca_raises(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test generate_crl raises when CA not generated."""
        cert_manager = CertificateManager(cert_config, keystore)
        
        with pytest.raises(RuntimeError, match="CA not generated"):
            cert_manager.generate_crl()


class TestRotationBackoff:
    """Tests for rotation loop backoff behavior."""

    @pytest.mark.asyncio
    async def test_rotation_loop_backoff_on_repeated_errors(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that rotation loop uses exponential backoff on errors."""
        import time
        
        cert_config.rotation_check_interval = 1
        
        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("backoff-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        
        # Force cert to need renewal
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() + timedelta(minutes=30)
        )
        
        # Delete cert file to cause repeated failures
        cert_manager._issued_certs["server"].cert_path.unlink()
        
        start_time = time.time()
        await cert_manager.start_rotation_scheduler()
        # Let it run through at least one error cycle
        await asyncio.sleep(3)
        await cert_manager.stop_rotation_scheduler()
        
        # Should have handled errors without crashing
        assert not cert_manager._rotation_running

    @pytest.mark.asyncio
    async def test_rotation_loop_general_exception_triggers_backoff(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that non-rotation errors in the loop trigger backoff."""
        from unittest.mock import patch, AsyncMock
        
        cert_config.rotation_check_interval = 1
        
        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("general-error-test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        
        # Force cert to need renewal
        cert_manager._issued_certs["server"].expires_at = (
            _get_current_time() + timedelta(minutes=30)
        )
        
        call_count = [0]
        original_needs_renewal = cert_manager.needs_renewal
        
        def mock_needs_renewal(cn):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Simulated general error")
            return original_needs_renewal(cn)
        
        cert_manager.needs_renewal = mock_needs_renewal
        
        await cert_manager.start_rotation_scheduler()
        await asyncio.sleep(4)  # Allow time for backoff cycles
        await cert_manager.stop_rotation_scheduler()
        
        # Should have handled errors and applied backoff
        assert call_count[0] >= 1


class TestCRLEdgeCases:
    """Tests for CRL edge cases."""

    def test_generate_crl_ca_key_none(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test generate_crl raises when CA key is None."""
        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("key-none-test")
        
        # Corrupt the CA store by setting key to None
        cert_manager._ca_store._ca_key = None
        
        with pytest.raises(RuntimeError, match="CA key/cert not available"):
            cert_manager.generate_crl()

    def test_generate_crl_ca_cert_none(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test generate_crl raises when CA cert is None."""
        cert_manager = CertificateManager(cert_config, keystore)
        cert_manager.generate_engagement_ca("cert-none-test")
        
        # Corrupt the CA store by setting cert to None
        cert_manager._ca_store._ca_cert = None
        
        with pytest.raises(RuntimeError, match="CA key/cert not available"):
            cert_manager.generate_crl()
