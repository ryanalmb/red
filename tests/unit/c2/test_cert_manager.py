"""Unit tests for CertificateManager.

Tests certificate lifecycle management per Story 12.3:
- Config defaults (24h validity, 1h threshold)
- CA generation and disk persistence
- Server/client cert issuance with correct validity and SANs
- Expiry checking and renewal threshold logic
- Rotation (revokes old, issues new)
- CRL generation with revoked serials
- Scheduler lifecycle (start/stop)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from cryptography import x509

from cyberred.c2.cert_manager import (
    CertificateManager,
    CertManagerConfig,
    IssuedCert,
    _get_current_time,
)
from cyberred.core.keystore import Keystore, generate_salt


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def keystore() -> Keystore:
    """Create a Keystore for testing."""
    salt = generate_salt()
    return Keystore.from_password("test-password", salt)


@pytest.fixture
def cert_config(tmp_path: Path) -> CertManagerConfig:
    """Create CertManagerConfig with temp directory."""
    return CertManagerConfig(
        cert_dir=tmp_path / "certs",
        validity_hours=24,
        renewal_threshold_hours=1,
        rotation_check_interval=300,
    )


@pytest.fixture
def cert_manager(cert_config: CertManagerConfig, keystore: Keystore) -> CertificateManager:
    """Create CertificateManager instance."""
    return CertificateManager(cert_config, keystore)


# =============================================================================
# Config Tests (Task 1)
# =============================================================================


class TestCertManagerConfig:
    """Test CertManagerConfig dataclass."""

    def test_config_defaults(self, tmp_path: Path) -> None:
        """Test default config values per architecture."""
        config = CertManagerConfig(cert_dir=tmp_path)
        assert config.validity_hours == 24  # Per architecture
        assert config.renewal_threshold_hours == 1  # Per PRD
        assert config.rotation_check_interval == 300  # 5 minutes

    def test_config_custom_values(self, tmp_path: Path) -> None:
        """Test custom config values."""
        config = CertManagerConfig(
            cert_dir=tmp_path,
            validity_hours=48,
            renewal_threshold_hours=2,
            rotation_check_interval=60,
        )
        assert config.validity_hours == 48
        assert config.renewal_threshold_hours == 2
        assert config.rotation_check_interval == 60


class TestCertificateManagerInit:
    """Test CertificateManager initialization."""

    def test_init_creates_cert_dir(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that init creates cert directory."""
        assert not cert_config.cert_dir.exists()
        CertificateManager(cert_config, keystore)
        assert cert_config.cert_dir.exists()

    def test_init_stores_config(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that config is stored correctly."""
        manager = CertificateManager(cert_config, keystore)
        assert manager._config == cert_config
        assert manager._keystore == keystore

    def test_init_empty_registries(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test that registries start empty."""
        manager = CertificateManager(cert_config, keystore)
        assert manager._issued_certs == {}
        assert manager._revoked_serials == set()
        assert manager._ca_store is None


# =============================================================================
# CA Generation Tests (Task 2)
# =============================================================================


class TestEngagementCAGeneration:
    """Test engagement CA generation."""

    def test_generate_ca_success(self, cert_manager: CertificateManager) -> None:
        """Test successful CA generation."""
        ca_path = cert_manager.generate_engagement_ca("test-engagement-123")
        assert ca_path.exists()
        assert ca_path.name == "ca.crt"

    def test_generate_ca_creates_key_file(self, cert_manager: CertificateManager) -> None:
        """Test that CA key is saved encrypted."""
        cert_manager.generate_engagement_ca("test-engagement")
        key_path = cert_manager._config.cert_dir / "ca.key.enc"
        assert key_path.exists()

    def test_generate_ca_empty_id_raises(self, cert_manager: CertificateManager) -> None:
        """Test that empty engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            cert_manager.generate_engagement_ca("")

    def test_generate_ca_whitespace_id_raises(self, cert_manager: CertificateManager) -> None:
        """Test that whitespace-only engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            cert_manager.generate_engagement_ca("   ")

    def test_generate_ca_sets_ca_store(self, cert_manager: CertificateManager) -> None:
        """Test that CA store is set after generation."""
        assert cert_manager._ca_store is None
        cert_manager.generate_engagement_ca("test")
        assert cert_manager._ca_store is not None


# =============================================================================
# Server Certificate Tests (Task 3)
# =============================================================================


class TestServerCertIssuance:
    """Test server certificate issuance."""

    def test_issue_server_cert_success(self, cert_manager: CertificateManager) -> None:
        """Test successful server cert issuance."""
        cert_manager.generate_engagement_ca("test")
        cert_path, key_path = cert_manager.issue_server_cert(
            san_names=["c2.local", "127.0.0.1"],
            common_name="c2-server",
        )
        assert cert_path.exists()
        assert key_path.exists()

    def test_issue_server_cert_no_ca_raises(self, cert_manager: CertificateManager) -> None:
        """Test that issuing without CA raises RuntimeError."""
        with pytest.raises(RuntimeError, match="CA not generated"):
            cert_manager.issue_server_cert(["localhost"])

    def test_issue_server_cert_empty_cn_raises(self, cert_manager: CertificateManager) -> None:
        """Test that empty common_name raises ValueError."""
        cert_manager.generate_engagement_ca("test")
        with pytest.raises(ValueError, match="common_name cannot be empty"):
            cert_manager.issue_server_cert(["localhost"], common_name="")

    def test_issue_server_cert_empty_san_raises(self, cert_manager: CertificateManager) -> None:
        """Test that empty san_names raises ValueError."""
        cert_manager.generate_engagement_ca("test")
        with pytest.raises(ValueError, match="san_names cannot be empty"):
            cert_manager.issue_server_cert([])

    def test_issue_server_cert_tracks_issued(self, cert_manager: CertificateManager) -> None:
        """Test that issued cert is tracked in registry."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="c2-server")
        assert "c2-server" in cert_manager._issued_certs
        issued = cert_manager._issued_certs["c2-server"]
        assert isinstance(issued, IssuedCert)
        assert issued.common_name == "c2-server"

    def test_issue_server_cert_24h_validity(self, cert_manager: CertificateManager) -> None:
        """Test that server cert has 24h validity per architecture."""
        cert_manager.generate_engagement_ca("test")
        cert_path, _ = cert_manager.issue_server_cert(["localhost"])

        # Load and check cert
        cert_bytes = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes)

        validity = cert.not_valid_after_utc - cert.not_valid_before_utc
        assert validity == timedelta(hours=24)


# =============================================================================
# Client Certificate Tests (Task 4)
# =============================================================================


class TestClientCertIssuance:
    """Test client certificate issuance."""

    def test_issue_client_cert_success(self, cert_manager: CertificateManager) -> None:
        """Test successful client cert issuance."""
        cert_manager.generate_engagement_ca("test")
        cert_path, key_path = cert_manager.issue_client_cert("dropbox-001")
        assert cert_path.exists()
        assert key_path.exists()
        assert "dropbox-dropbox-001" in str(cert_path)

    def test_issue_client_cert_no_ca_raises(self, cert_manager: CertificateManager) -> None:
        """Test that issuing without CA raises RuntimeError."""
        with pytest.raises(RuntimeError, match="CA not generated"):
            cert_manager.issue_client_cert("dropbox-001")

    def test_issue_client_cert_empty_id_raises(self, cert_manager: CertificateManager) -> None:
        """Test that empty drop_box_id raises ValueError."""
        cert_manager.generate_engagement_ca("test")
        with pytest.raises(ValueError, match="drop_box_id cannot be empty"):
            cert_manager.issue_client_cert("")

    def test_issue_client_cert_tracks_issued(self, cert_manager: CertificateManager) -> None:
        """Test that issued client cert is tracked."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_client_cert("db-123")
        assert "dropbox-db-123" in cert_manager._issued_certs


# =============================================================================
# Expiry Checking Tests (Task 5)
# =============================================================================


class TestExpiryChecking:
    """Test certificate expiry checking."""

    def test_check_expiry_returns_remaining(self, cert_manager: CertificateManager) -> None:
        """Test check_expiry returns time remaining."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        remaining = cert_manager.check_expiry("server")
        assert remaining is not None
        # Should be close to 24 hours (minus a few seconds for execution)
        assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)

    def test_check_expiry_not_found_raises(self, cert_manager: CertificateManager) -> None:
        """Test check_expiry raises KeyError for unknown cert."""
        with pytest.raises(KeyError, match="Certificate not found"):
            cert_manager.check_expiry("nonexistent")

    def test_needs_renewal_false_when_fresh(self, cert_manager: CertificateManager) -> None:
        """Test needs_renewal returns False for fresh cert."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        assert cert_manager.needs_renewal("server") is False

    def test_needs_renewal_true_when_near_expiry(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test needs_renewal returns True when within threshold."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        # Manually set expires_at to within threshold
        issued = cert_manager._issued_certs["server"]
        issued.expires_at = _get_current_time() + timedelta(minutes=30)

        assert cert_manager.needs_renewal("server") is True

    def test_needs_renewal_not_found_raises(self, cert_manager: CertificateManager) -> None:
        """Test needs_renewal raises KeyError for unknown cert."""
        with pytest.raises(KeyError, match="Certificate not found"):
            cert_manager.needs_renewal("nonexistent")


# =============================================================================
# Rotation Tests (Task 6)
# =============================================================================


class TestCertRotation:
    """Test certificate rotation."""

    def test_rotate_cert_revokes_old(self, cert_manager: CertificateManager) -> None:
        """Test that rotation revokes the old cert."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        old_serial = cert_manager._issued_certs["server"].serial_number

        cert_manager.rotate_cert("server")

        assert old_serial in cert_manager._revoked_serials

    def test_rotate_cert_issues_new(self, cert_manager: CertificateManager) -> None:
        """Test that rotation issues a new cert."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        old_serial = cert_manager._issued_certs["server"].serial_number

        new_cert_path, _ = cert_manager.rotate_cert("server")

        new_serial = cert_manager._issued_certs["server"].serial_number
        assert new_serial != old_serial
        assert new_cert_path.exists()

    def test_rotate_cert_not_found_raises(self, cert_manager: CertificateManager) -> None:
        """Test rotate_cert raises KeyError for unknown cert."""
        cert_manager.generate_engagement_ca("test")
        with pytest.raises(KeyError, match="Certificate not found"):
            cert_manager.rotate_cert("nonexistent")

    def test_rotate_client_cert(self, cert_manager: CertificateManager) -> None:
        """Test rotating a client cert."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_client_cert("box-001")

        old_serial = cert_manager._issued_certs["dropbox-box-001"].serial_number

        cert_manager.rotate_cert("dropbox-box-001")

        new_serial = cert_manager._issued_certs["dropbox-box-001"].serial_number
        assert new_serial != old_serial
        assert old_serial in cert_manager._revoked_serials


# =============================================================================
# CRL Tests (Task 7)
# =============================================================================


class TestCRL:
    """Test Certificate Revocation List functionality."""

    def test_revoke_cert_adds_to_revoked(self, cert_manager: CertificateManager) -> None:
        """Test that revoke_cert adds serial to revoked set."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        serial = cert_manager._issued_certs["server"].serial_number

        cert_manager.revoke_cert("server")

        assert serial in cert_manager._revoked_serials
        assert cert_manager._issued_certs["server"].revoked is True

    def test_revoke_cert_not_found_raises(self, cert_manager: CertificateManager) -> None:
        """Test revoke_cert raises KeyError for unknown cert."""
        with pytest.raises(KeyError, match="Certificate not found"):
            cert_manager.revoke_cert("nonexistent")

    def test_generate_crl_creates_file(self, cert_manager: CertificateManager) -> None:
        """Test generate_crl creates CRL file."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")

        crl_path = cert_manager.generate_crl()

        assert crl_path.exists()
        assert crl_path.name == "crl.pem"

    def test_generate_crl_contains_revoked(self, cert_manager: CertificateManager) -> None:
        """Test that CRL contains revoked serial."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        serial = cert_manager._issued_certs["server"].serial_number
        cert_manager.revoke_cert("server")

        crl_path = cert_manager.generate_crl()

        # Parse and verify CRL
        crl_bytes = crl_path.read_bytes()
        crl = x509.load_pem_x509_crl(crl_bytes)

        revoked_serials = [rc.serial_number for rc in crl]
        assert serial in revoked_serials

    def test_generate_crl_no_ca_raises(self, cert_manager: CertificateManager) -> None:
        """Test generate_crl raises RuntimeError without CA."""
        with pytest.raises(RuntimeError, match="CA not generated"):
            cert_manager.generate_crl()


# =============================================================================
# Scheduler Tests (Task 6)
# =============================================================================


class TestRotationScheduler:
    """Test rotation scheduler lifecycle."""

    @pytest.mark.asyncio
    async def test_start_scheduler(self, cert_manager: CertificateManager) -> None:
        """Test starting rotation scheduler."""
        cert_manager.generate_engagement_ca("test")

        await cert_manager.start_rotation_scheduler()
        assert cert_manager._rotation_running is True
        assert cert_manager._rotation_task is not None

        await cert_manager.stop_rotation_scheduler()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, cert_manager: CertificateManager) -> None:
        """Test stopping rotation scheduler."""
        cert_manager.generate_engagement_ca("test")

        await cert_manager.start_rotation_scheduler()
        await cert_manager.stop_rotation_scheduler()

        assert cert_manager._rotation_running is False
        assert cert_manager._rotation_task is None

    @pytest.mark.asyncio
    async def test_double_start_warns(self, cert_manager: CertificateManager) -> None:
        """Test that double start logs warning."""
        cert_manager.generate_engagement_ca("test")

        await cert_manager.start_rotation_scheduler()
        await cert_manager.start_rotation_scheduler()  # Should warn, not error

        await cert_manager.stop_rotation_scheduler()


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling edge cases."""

    def test_init_invalid_cert_dir_type(self, keystore: Keystore) -> None:
        """Test that non-Path cert_dir raises ValueError."""
        with pytest.raises(ValueError, match="cert_dir must be a Path instance"):
            # Pass string instead of Path
            config = CertManagerConfig(cert_dir="/tmp/certs")  # type: ignore
            CertificateManager(config, keystore)

    def test_rotate_cert_no_ca_raises(
        self, cert_config: CertManagerConfig, keystore: Keystore
    ) -> None:
        """Test rotate_cert raises RuntimeError without CA."""
        manager = CertificateManager(cert_config, keystore)
        # Manually add a cert without generating CA
        manager._issued_certs["test"] = IssuedCert(
            serial_number=12345,
            common_name="test",
            issued_at=_get_current_time(),
            expires_at=_get_current_time() + timedelta(hours=24),
            cert_path=cert_config.cert_dir / "test.crt",
            key_path=cert_config.cert_dir / "test.key",
        )
        with pytest.raises(RuntimeError, match="CA not generated"):
            manager.rotate_cert("test")


class TestHelperMethods:
    """Test helper methods."""

    def test_get_ca_cert_path_none_before_ca(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test get_ca_cert_path returns None before CA generated."""
        assert cert_manager.get_ca_cert_path() is None

    def test_get_ca_cert_path_after_ca(self, cert_manager: CertificateManager) -> None:
        """Test get_ca_cert_path returns path after CA generated."""
        cert_manager.generate_engagement_ca("test")
        ca_path = cert_manager.get_ca_cert_path()
        assert ca_path is not None
        assert ca_path.exists()

    def test_get_crl_path_none_before_crl(
        self, cert_manager: CertificateManager
    ) -> None:
        """Test get_crl_path returns None before CRL generated."""
        assert cert_manager.get_crl_path() is None

    def test_get_crl_path_after_crl(self, cert_manager: CertificateManager) -> None:
        """Test get_crl_path returns path after CRL generated."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"])
        cert_manager.revoke_cert("c2-server")

        crl_path = cert_manager.get_crl_path()
        assert crl_path is not None
        assert crl_path.exists()

    def test_issued_certs_property(self, cert_manager: CertificateManager) -> None:
        """Test issued_certs returns copy of registry."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")

        issued = cert_manager.issued_certs
        assert "server" in issued
        # Verify it's a copy
        issued["server"] = None  # type: ignore
        assert cert_manager._issued_certs["server"] is not None

    def test_revoked_serials_property(self, cert_manager: CertificateManager) -> None:
        """Test revoked_serials returns copy of set."""
        cert_manager.generate_engagement_ca("test")
        cert_manager.issue_server_cert(["localhost"], common_name="server")
        cert_manager.revoke_cert("server")

        revoked = cert_manager.revoked_serials
        assert len(revoked) == 1
        # Verify it's a copy
        revoked.clear()
        assert len(cert_manager._revoked_serials) == 1
