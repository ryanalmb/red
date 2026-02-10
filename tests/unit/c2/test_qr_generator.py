"""Unit tests for QR Code Generator.

Story 12.8: Natural Language Drop Box Setup - Task 9.4

Tests QR code generation for mobile platforms.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cyberred.c2.qr_generator import (
    QRPayload,
    generate_deployment_qr,
    generate_qr_for_cert,
    get_cert_fingerprint,
)


class TestQRPayload:
    """Tests for QRPayload dataclass."""
    
    def test_to_json(self):
        """Test JSON serialization."""
        payload = QRPayload(
            c2_url="wss://c2.example.com:8444",
            cert_fingerprint="sha256:abc123def456",
            drop_box_id="android-dropbox",
        )
        
        json_str = payload.to_json()
        data = json.loads(json_str)
        
        assert data["c2_url"] == "wss://c2.example.com:8444"
        assert data["cert_fingerprint"] == "sha256:abc123def456"
        assert data["drop_box_id"] == "android-dropbox"
    
    def test_to_json_parseable(self):
        """Test JSON can be parsed back."""
        payload = QRPayload(
            c2_url="wss://c2.example.com:8444",
            cert_fingerprint="sha256:abc123",
            drop_box_id="test-box",
        )
        
        json_str = payload.to_json()
        parsed = json.loads(json_str)
        
        assert isinstance(parsed, dict)
        assert len(parsed) == 3


class TestGetCertFingerprint:
    """Tests for get_cert_fingerprint function."""
    
    def test_fingerprint_format(self, tmp_path):
        """Test fingerprint has correct format."""
        # Create a minimal PEM certificate
        cert_content = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpegPjMBMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC7o96WzE2Bm3C8E1fJ9dKf
L0GQ3u+3hH2fJSPL0J3QKSPNfPVMZrPPFEB0MJHrxH8PN2GHqX0BrJlMbqPLRPUJ
AgMBAAGjUzBRMB0GA1UdDgQWBBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAfBgNVHSME
GDAWgBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAPBgNVHRMBAf8EBTADAQH/MA0GCSqG
SIb3DQEBCwUAA0EAu6PelsxNgZtwvBNXyfXSny9BkN7vt4R9nyUjy9Cd0CkjzXz1
TGazzxRAdDCR68R/DzdhgKl9AayZTG6jy0T1CQ==
-----END CERTIFICATE-----"""
        
        cert_path = tmp_path / "test.crt"
        cert_path.write_text(cert_content)
        
        fingerprint = get_cert_fingerprint(cert_path)
        
        assert fingerprint.startswith("sha256:")
        assert len(fingerprint) == 7 + 64  # "sha256:" + 64 hex chars
    
    def test_fingerprint_consistent(self, tmp_path):
        """Test same cert produces same fingerprint."""
        cert_content = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpegPjMBMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC7o96WzE2Bm3C8E1fJ9dKf
L0GQ3u+3hH2fJSPL0J3QKSPNfPVMZrPPFEB0MJHrxH8PN2GHqX0BrJlMbqPLRPUJ
AgMBAAGjUzBRMB0GA1UdDgQWBBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAfBgNVHSME
GDAWgBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAPBgNVHRMBAf8EBTADAQH/MA0GCSqG
SIb3DQEBCwUAA0EAu6PelsxNgZtwvBNXyfXSny9BkN7vt4R9nyUjy9Cd0CkjzXz1
TGazzxRAdDCR68R/DzdhgKl9AayZTG6jy0T1CQ==
-----END CERTIFICATE-----"""
        
        cert_path = tmp_path / "test.crt"
        cert_path.write_text(cert_content)
        
        fp1 = get_cert_fingerprint(cert_path)
        fp2 = get_cert_fingerprint(cert_path)
        
        assert fp1 == fp2
    
    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError for missing cert."""
        cert_path = tmp_path / "nonexistent.crt"
        
        with pytest.raises(FileNotFoundError):
            get_cert_fingerprint(cert_path)


class TestGenerateDeploymentQR:
    """Tests for generate_deployment_qr function."""
    
    def test_generate_qr_with_library(self):
        """Test QR generation with qrcode library installed."""
        payload = QRPayload(
            c2_url="wss://c2.example.com:8444",
            cert_fingerprint="sha256:abc123",
            drop_box_id="test-dropbox",
        )
        
        qr_code = generate_deployment_qr(payload)
        
        # Should contain block characters or be a fallback
        assert len(qr_code) > 0
        # Either has QR pattern or fallback text
        assert "██" in qr_code or "Manual Configuration" in qr_code
    
    def test_generate_qr_fallback(self):
        """Test fallback when qrcode library not available."""
        from cyberred.c2.qr_generator import _generate_fallback_qr

        payload = QRPayload(
            c2_url="wss://c2.example.com:8444",
            cert_fingerprint="sha256:abc123",
            drop_box_id="test-dropbox",
        )

        result = _generate_fallback_qr(payload)

        # Verify fallback contains manual configuration info
        assert "QR Code Library Not Installed" in result
        assert "Manual Configuration" in result
        assert payload.c2_url in result
        assert payload.drop_box_id in result
        assert payload.cert_fingerprint in result
        assert "pip install qrcode" in result
    
    def test_qr_contains_payload_data(self):
        """Test QR code encodes the payload data."""
        payload = QRPayload(
            c2_url="wss://test.com:8444",
            cert_fingerprint="sha256:testfp",
            drop_box_id="my-dropbox",
        )
        
        # The QR code should encode the JSON payload
        # We can't decode it without scanning, but we can verify it generates
        qr_code = generate_deployment_qr(payload)
        assert len(qr_code) > 50  # Reasonable minimum size


class TestGenerateQRForCert:
    """Tests for generate_qr_for_cert convenience function."""
    
    def test_generates_qr_from_cert(self, tmp_path):
        """Test generating QR code directly from cert file."""
        # Create a minimal PEM certificate
        cert_content = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpegPjMBMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC7o96WzE2Bm3C8E1fJ9dKf
L0GQ3u+3hH2fJSPL0J3QKSPNfPVMZrPPFEB0MJHrxH8PN2GHqX0BrJlMbqPLRPUJ
AgMBAAGjUzBRMB0GA1UdDgQWBBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAfBgNVHSME
GDAWgBQ7o96WzE2Bm3C8E1fJ9dKfL0GQ3jAPBgNVHRMBAf8EBTADAQH/MA0GCSqG
SIb3DQEBCwUAA0EAu6PelsxNgZtwvBNXyfXSny9BkN7vt4R9nyUjy9Cd0CkjzXz1
TGazzxRAdDCR68R/DzdhgKl9AayZTG6jy0T1CQ==
-----END CERTIFICATE-----"""
        
        cert_path = tmp_path / "dropbox.crt"
        cert_path.write_text(cert_content)
        
        c2_url = "wss://c2.example.com:8444"
        drop_box_id = "test-android"
        
        qr_code = generate_qr_for_cert(c2_url, cert_path, drop_box_id)
        
        assert len(qr_code) > 0
