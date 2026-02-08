"""Certificate Manager for automated certificate lifecycle management.

Per FR24 and Architecture: Automated certificate generation and rotation for mTLS C2 channels.
- 24-hour certificate validity
- Auto-renewal 1 hour before expiry
- CRL (Certificate Revocation List) distribution

Usage:
    from cyberred.c2 import CertificateManager, CertManagerConfig

    config = CertManagerConfig(cert_dir=Path("/certs"))
    cert_manager = CertificateManager(config, keystore)
    cert_manager.generate_engagement_ca("engagement-123")
    cert_path, key_path = cert_manager.issue_server_cert(["c2.local"])
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import structlog
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from cyberred.core.keystore import Keystore
from cyberred.core.ca_store import CAStore

log = structlog.get_logger()


def _get_current_time() -> datetime:
    """Get current UTC time. Extracted for testing purposes.
    
    Returns:
        Current UTC datetime with timezone info.
    """
    return datetime.now(timezone.utc)


@dataclass
class CertManagerConfig:
    """Configuration for CertificateManager.

    Attributes:
        cert_dir: Directory for storing certificates and keys.
        validity_hours: Certificate validity in hours (default: 24 per architecture).
        renewal_threshold_hours: Auto-renew when this many hours remain (default: 1).
        rotation_check_interval: Seconds between rotation checks (default: 300 = 5 min).
    """

    cert_dir: Path
    validity_hours: int = 24
    renewal_threshold_hours: int = 1
    rotation_check_interval: int = 300


@dataclass
class IssuedCert:
    """Tracking record for an issued certificate.

    Attributes:
        serial_number: Certificate serial number.
        common_name: Certificate CN (unique identifier).
        issued_at: Timestamp when cert was issued.
        expires_at: Timestamp when cert expires.
        cert_path: Path to certificate PEM file.
        key_path: Path to private key PEM file.
        revoked: Whether the certificate has been revoked.
        revoked_at: Timestamp when cert was revoked (if applicable).
    """

    serial_number: int
    common_name: str
    issued_at: datetime
    expires_at: datetime
    cert_path: Path
    key_path: Path
    revoked: bool = False
    revoked_at: Optional[datetime] = None


class CertificateManager:
    """Automated certificate lifecycle management for mTLS C2.

    Manages CA generation, certificate issuance, rotation, and revocation
    for the mTLS C2 channel per FR24 security requirements.

    Attributes:
        _config: CertManagerConfig instance.
        _keystore: Keystore for CA key encryption.
        _ca_store: CAStore instance (created on CA generation).
        _issued_certs: Registry of issued certificates by common name.
        _revoked_serials: Set of revoked certificate serial numbers.
        _rotation_task: Async task for automatic rotation.
    """

    def __init__(self, config: CertManagerConfig, keystore: Keystore) -> None:
        """Initialize CertificateManager.

        Args:
            config: CertManagerConfig with cert_dir and timing parameters.
            keystore: Keystore instance for CA key encryption.

        Raises:
            ValueError: If config.cert_dir is not a valid path.
        """
        if not isinstance(config.cert_dir, Path):
            raise ValueError("cert_dir must be a Path instance")

        self._config = config
        self._keystore = keystore
        self._ca_store: Optional[CAStore] = None
        self._issued_certs: dict[str, IssuedCert] = {}
        self._revoked_serials: set[int] = set()
        self._rotation_task: Optional[asyncio.Task] = None
        self._rotation_running = False
        self._crl_distribution_callback: Optional[callable] = None

        # Ensure cert directory exists
        self._config.cert_dir.mkdir(parents=True, exist_ok=True)

        log.info(
            "cert_manager_initialized",
            cert_dir=str(config.cert_dir),
            validity_hours=config.validity_hours,
            renewal_threshold_hours=config.renewal_threshold_hours,
        )

    def set_crl_distribution_callback(self, callback: callable) -> None:
        """Set callback for CRL distribution to clients.
        
        The callback will be invoked whenever the CRL is updated (on revocation
        or rotation). It receives the CRL path and CRL bytes.
        
        Args:
            callback: Async or sync callable(crl_path: Path, crl_bytes: bytes) -> None
        """
        self._crl_distribution_callback = callback
        log.info("crl_distribution_callback_registered")

    def generate_engagement_ca(self, engagement_id: str) -> Path:
        """Generate a new CA for this engagement.

        Args:
            engagement_id: Unique engagement identifier.

        Returns:
            Path to the CA certificate file.

        Raises:
            ValueError: If engagement_id is empty.
            RuntimeError: If CA generation fails.
        """
        if not engagement_id or not engagement_id.strip():
            raise ValueError("engagement_id cannot be empty")

        ca_name = f"Cyber-Red CA - {engagement_id}"
        self._ca_store = CAStore(self._keystore)
        self._ca_store.generate_ca(ca_name)

        # Save CA to disk
        ca_key_path = self._config.cert_dir / "ca.key.enc"
        ca_cert_path = self._config.cert_dir / "ca.crt"
        self._ca_store.save(ca_key_path, ca_cert_path)

        log.info(
            "engagement_ca_generated",
            engagement_id=engagement_id,
            ca_cert_path=str(ca_cert_path),
        )

        return ca_cert_path

    def issue_server_cert(
        self, san_names: list[str], common_name: str = "c2-server"
    ) -> tuple[Path, Path]:
        """Issue a server certificate with SANs.

        Args:
            san_names: Subject Alternative Names (DNS names or IP addresses).
            common_name: Certificate CN (default: "c2-server").

        Returns:
            Tuple of (cert_path, key_path).

        Raises:
            RuntimeError: If CA has not been generated.
            ValueError: If common_name is empty or san_names is empty.
        """
        if self._ca_store is None:
            raise RuntimeError("CA not generated. Call generate_engagement_ca() first.")
        if not common_name or not common_name.strip():
            raise ValueError("common_name cannot be empty")
        if not san_names:
            raise ValueError("san_names cannot be empty")

        cert, key = self._ca_store.generate_cert(
            common_name=common_name,
            valid_hours=self._config.validity_hours,
            san_names=san_names,
        )

        # Save to disk
        cert_path = self._config.cert_dir / f"{common_name}.crt"
        key_path = self._config.cert_dir / f"{common_name}.key"

        cert_path.write_bytes(CAStore.serialize_cert_pem(cert))
        key_path.write_bytes(CAStore.serialize_key_pem(key))
        
        # Restrict private key permissions (owner read/write only)
        os.chmod(key_path, 0o600)

        # Track issued cert
        now = _get_current_time()
        issued = IssuedCert(
            serial_number=cert.serial_number,
            common_name=common_name,
            issued_at=now,
            expires_at=now + timedelta(hours=self._config.validity_hours),
            cert_path=cert_path,
            key_path=key_path,
        )
        self._issued_certs[common_name] = issued

        log.info(
            "server_cert_issued",
            common_name=common_name,
            san_names=san_names,
            expires_at=issued.expires_at.isoformat(),
        )

        return cert_path, key_path

    def issue_client_cert(self, drop_box_id: str) -> tuple[Path, Path]:
        """Issue a client certificate for a drop box.

        Args:
            drop_box_id: Unique drop box identifier (used as CN).

        Returns:
            Tuple of (cert_path, key_path).

        Raises:
            RuntimeError: If CA has not been generated.
            ValueError: If drop_box_id is empty.
        """
        if self._ca_store is None:
            raise RuntimeError("CA not generated. Call generate_engagement_ca() first.")
        if not drop_box_id or not drop_box_id.strip():
            raise ValueError("drop_box_id cannot be empty")

        common_name = f"dropbox-{drop_box_id}"
        cert, key = self._ca_store.generate_cert(
            common_name=common_name,
            valid_hours=self._config.validity_hours,
        )

        # Save to disk
        cert_path = self._config.cert_dir / f"{common_name}.crt"
        key_path = self._config.cert_dir / f"{common_name}.key"

        cert_path.write_bytes(CAStore.serialize_cert_pem(cert))
        key_path.write_bytes(CAStore.serialize_key_pem(key))
        
        # Restrict private key permissions (owner read/write only)
        os.chmod(key_path, 0o600)

        # Track issued cert
        now = _get_current_time()
        issued = IssuedCert(
            serial_number=cert.serial_number,
            common_name=common_name,
            issued_at=now,
            expires_at=now + timedelta(hours=self._config.validity_hours),
            cert_path=cert_path,
            key_path=key_path,
        )
        self._issued_certs[common_name] = issued

        log.info(
            "client_cert_issued",
            drop_box_id=drop_box_id,
            common_name=common_name,
            expires_at=issued.expires_at.isoformat(),
        )

        return cert_path, key_path

    def check_expiry(self, common_name: str) -> Optional[timedelta]:
        """Check time remaining until certificate expires.

        Args:
            common_name: Certificate CN to check.

        Returns:
            Timedelta until expiry, or None if cert not found or expired.

        Raises:
            KeyError: If certificate not found.
        """
        if common_name not in self._issued_certs:
            raise KeyError(f"Certificate not found: {common_name}")

        issued = self._issued_certs[common_name]
        if issued.revoked:
            return None

        now = _get_current_time()
        remaining = issued.expires_at - now

        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def needs_renewal(self, common_name: str) -> bool:
        """Check if certificate needs renewal (within threshold).

        Args:
            common_name: Certificate CN to check.

        Returns:
            True if cert needs renewal (within renewal_threshold_hours of expiry).

        Raises:
            KeyError: If certificate not found.
        """
        remaining = self.check_expiry(common_name)
        if remaining is None:
            return True  # Expired or revoked, needs renewal

        threshold = timedelta(hours=self._config.renewal_threshold_hours)
        return remaining <= threshold

    def rotate_cert(self, common_name: str) -> tuple[Path, Path]:
        """Rotate a certificate: revoke old, issue new.

        Args:
            common_name: Certificate CN to rotate.

        Returns:
            Tuple of (new_cert_path, new_key_path).

        Raises:
            KeyError: If certificate not found.
            RuntimeError: If CA has not been generated.
        """
        if self._ca_store is None:
            raise RuntimeError("CA not generated. Call generate_engagement_ca() first.")
        if common_name not in self._issued_certs:
            raise KeyError(f"Certificate not found: {common_name}")

        old_issued = self._issued_certs[common_name]

        # Revoke the old cert
        self.revoke_cert(common_name)

        # Issue new cert (determine if server or client by CN pattern)
        if common_name.startswith("dropbox-"):
            # Client cert - extract drop_box_id
            drop_box_id = common_name.replace("dropbox-", "")
            return self.issue_client_cert(drop_box_id)
        else:
            # Server cert - need to get SANs from old cert
            # Read old cert to extract SANs
            old_cert_bytes = old_issued.cert_path.read_bytes()
            old_cert = x509.load_pem_x509_certificate(old_cert_bytes)

            san_names: list[str] = []
            try:
                san_ext = old_cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName
                )
                for name in san_ext.value:
                    if isinstance(name, x509.DNSName):
                        san_names.append(name.value)
                    elif isinstance(name, x509.IPAddress):
                        san_names.append(str(name.value))
            except x509.ExtensionNotFound:
                pass

            if not san_names:
                san_names = ["localhost"]  # Fallback

            return self.issue_server_cert(san_names, common_name)

    def revoke_cert(self, common_name: str) -> None:
        """Revoke a certificate.

        Args:
            common_name: Certificate CN to revoke.

        Raises:
            KeyError: If certificate not found.
        """
        if common_name not in self._issued_certs:
            raise KeyError(f"Certificate not found: {common_name}")

        issued = self._issued_certs[common_name]
        if issued.revoked:
            log.warning("cert_already_revoked", common_name=common_name)
            return

        issued.revoked = True
        issued.revoked_at = _get_current_time()
        self._revoked_serials.add(issued.serial_number)

        log.info(
            "cert_revoked",
            common_name=common_name,
            serial_number=issued.serial_number,
        )

        # Regenerate CRL
        self.generate_crl()

    def generate_crl(self) -> Path:
        """Generate Certificate Revocation List.

        Returns:
            Path to the CRL file.

        Raises:
            RuntimeError: If CA has not been generated.
        """
        if self._ca_store is None:
            raise RuntimeError("CA not generated. Call generate_engagement_ca() first.")

        # Get CA key and cert for signing CRL
        # Access private attributes (CAStore doesn't expose these directly)
        ca_key = self._ca_store._ca_key
        ca_cert = self._ca_store._ca_cert

        if ca_key is None or ca_cert is None:
            raise RuntimeError("CA key/cert not available")

        now = _get_current_time()
        crl_builder = x509.CertificateRevocationListBuilder()
        crl_builder = crl_builder.issuer_name(ca_cert.subject)
        crl_builder = crl_builder.last_update(now)
        crl_builder = crl_builder.next_update(now + timedelta(hours=24))

        # Add revoked certificates
        for cn, issued in self._issued_certs.items():
            if issued.revoked and issued.revoked_at:
                revoked_cert = (
                    x509.RevokedCertificateBuilder()
                    .serial_number(issued.serial_number)
                    .revocation_date(issued.revoked_at)
                    .build()
                )
                crl_builder = crl_builder.add_revoked_certificate(revoked_cert)

        # Sign CRL
        crl = crl_builder.sign(ca_key, hashes.SHA256())

        # Save to disk
        crl_path = self._config.cert_dir / "crl.pem"
        crl_bytes = crl.public_bytes(serialization.Encoding.PEM)
        crl_path.write_bytes(crl_bytes)

        log.info(
            "crl_generated",
            crl_path=str(crl_path),
            revoked_count=len(self._revoked_serials),
        )

        # Distribute CRL to clients via callback (AC #6)
        if self._crl_distribution_callback is not None:
            try:
                result = self._crl_distribution_callback(crl_path, crl_bytes)
                # Handle async callbacks
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
                log.info("crl_distribution_triggered", crl_path=str(crl_path))
            except Exception as e:
                log.error("crl_distribution_failed", error=str(e))

        return crl_path

    async def start_rotation_scheduler(self) -> None:
        """Start automatic certificate rotation scheduler.

        Checks all issued certs periodically and rotates those near expiry.
        """
        if self._rotation_running:
            log.warning("rotation_scheduler_already_running")
            return

        self._rotation_running = True
        self._rotation_task = asyncio.create_task(self._rotation_loop())

        log.info(
            "rotation_scheduler_started",
            check_interval=self._config.rotation_check_interval,
        )

    async def stop_rotation_scheduler(self) -> None:
        """Stop the rotation scheduler gracefully."""
        if not self._rotation_running:
            return

        self._rotation_running = False

        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
            self._rotation_task = None

        log.info("rotation_scheduler_stopped")

    async def _rotation_loop(self) -> None:
        """Internal rotation loop - checks and rotates certs as needed."""
        backoff = self._config.rotation_check_interval

        while self._rotation_running:
            try:
                await asyncio.sleep(self._config.rotation_check_interval)

                # Check all non-revoked certs
                for cn in list(self._issued_certs.keys()):
                    issued = self._issued_certs[cn]
                    if issued.revoked:
                        continue

                    if self.needs_renewal(cn):
                        log.info("cert_auto_rotating", common_name=cn)
                        try:
                            self.rotate_cert(cn)
                        except Exception as e:
                            log.error(
                                "cert_rotation_failed",
                                common_name=cn,
                                error=str(e),
                            )

                # Reset backoff on success
                backoff = self._config.rotation_check_interval

            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("rotation_loop_error", error=str(e))
                backoff = min(backoff * 2, 60)  # Exponential backoff, max 60s
                await asyncio.sleep(backoff)

    def get_ca_cert_path(self) -> Optional[Path]:
        """Get path to CA certificate.

        Returns:
            Path to CA cert, or None if CA not generated.
        """
        if self._ca_store is None:
            return None
        ca_cert_path = self._config.cert_dir / "ca.crt"
        return ca_cert_path if ca_cert_path.exists() else None

    def get_crl_path(self) -> Optional[Path]:
        """Get path to CRL file.

        Returns:
            Path to CRL, or None if not generated.
        """
        crl_path = self._config.cert_dir / "crl.pem"
        return crl_path if crl_path.exists() else None

    @property
    def issued_certs(self) -> dict[str, IssuedCert]:
        """Get read-only view of issued certificates."""
        return dict(self._issued_certs)

    @property
    def revoked_serials(self) -> set[int]:
        """Get read-only view of revoked serial numbers."""
        return set(self._revoked_serials)
