"""Unit tests for Deployment Instructions.

Story 12.8: Natural Language Drop Box Setup - Task 9.1

Tests platform-specific instruction generation.
"""

import pytest
from pathlib import Path

from cyberred.c2.deployment_instructions import (
    get_instructions,
    is_mobile_platform,
    SUPPORTED_PLATFORMS,
)


class TestGetInstructions:
    """Tests for get_instructions function."""
    
    @pytest.fixture
    def cert_paths(self, tmp_path):
        """Create temporary certificate paths."""
        cert_path = tmp_path / "dropbox.crt"
        key_path = tmp_path / "dropbox.key"
        ca_path = tmp_path / "ca.crt"
        
        # Create dummy files
        cert_path.write_text("CERT")
        key_path.write_text("KEY")
        ca_path.write_text("CA")
        
        return cert_path, key_path, ca_path
    
    def test_android_instructions(self, cert_paths):
        """Test Android instruction generation."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        instructions = get_instructions("android", cert_path, key_path, ca_path, c2_url)
        
        assert "Android" in instructions
        assert "adb push" in instructions
        assert str(cert_path) in instructions
        assert c2_url in instructions
        assert "qr" in instructions.lower()
    
    def test_windows_instructions(self, cert_paths):
        """Test Windows instruction generation."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        instructions = get_instructions("windows", cert_path, key_path, ca_path, c2_url)
        
        assert "Windows" in instructions
        assert "PowerShell" in instructions or "powershell" in instructions.lower()
        assert str(cert_path) in instructions
        assert c2_url in instructions
        assert "Firewall" in instructions or "firewall" in instructions.lower()
    
    def test_linux_instructions(self, cert_paths):
        """Test Linux instruction generation."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        instructions = get_instructions("linux", cert_path, key_path, ca_path, c2_url)
        
        assert "Linux" in instructions
        assert "curl" in instructions
        assert "chmod" in instructions
        assert str(cert_path) in instructions
        assert c2_url in instructions
        assert "systemd" in instructions.lower()
    
    def test_macos_instructions(self, cert_paths):
        """Test macOS instruction generation."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        instructions = get_instructions("macos", cert_path, key_path, ca_path, c2_url)
        
        assert "macOS" in instructions
        assert "xattr" in instructions or "quarantine" in instructions.lower()
        assert str(cert_path) in instructions
        assert c2_url in instructions
        assert "launchd" in instructions.lower()
    
    def test_ios_instructions(self, cert_paths):
        """Test iOS instruction generation."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        instructions = get_instructions("ios", cert_path, key_path, ca_path, c2_url)
        
        assert "iOS" in instructions
        assert "QR" in instructions or "qr" in instructions.lower()
        assert c2_url in instructions
    
    def test_invalid_platform(self, cert_paths):
        """Test invalid platform raises ValueError."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        with pytest.raises(ValueError, match="Unsupported platform"):
            get_instructions("invalid", cert_path, key_path, ca_path, c2_url)
    
    def test_platform_case_insensitive(self, cert_paths):
        """Test platform names are case insensitive."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        
        # Should not raise
        instructions = get_instructions("ANDROID", cert_path, key_path, ca_path, c2_url)
        assert "Android" in instructions
        
        instructions = get_instructions("Linux", cert_path, key_path, ca_path, c2_url)
        assert "Linux" in instructions
    
    def test_drop_box_id_in_instructions(self, cert_paths):
        """Test drop_box_id is used in instructions where applicable."""
        cert_path, key_path, ca_path = cert_paths
        c2_url = "wss://c2.example.com:8444"
        drop_box_id = "test-dropbox-123"
        
        instructions = get_instructions(
            "linux", cert_path, key_path, ca_path, c2_url, drop_box_id
        )
        
        # The drop_box_id should be used in systemd service name
        assert drop_box_id in instructions


class TestIsMobilePlatform:
    """Tests for is_mobile_platform function."""
    
    def test_android_is_mobile(self):
        """Test Android is identified as mobile."""
        assert is_mobile_platform("android") is True
    
    def test_ios_is_mobile(self):
        """Test iOS is identified as mobile."""
        assert is_mobile_platform("ios") is True
    
    def test_windows_not_mobile(self):
        """Test Windows is not mobile."""
        assert is_mobile_platform("windows") is False
    
    def test_linux_not_mobile(self):
        """Test Linux is not mobile."""
        assert is_mobile_platform("linux") is False
    
    def test_macos_not_mobile(self):
        """Test macOS is not mobile."""
        assert is_mobile_platform("macos") is False
    
    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert is_mobile_platform("ANDROID") is True
        assert is_mobile_platform("IOS") is True
        assert is_mobile_platform("Android") is True


class TestSupportedPlatforms:
    """Tests for SUPPORTED_PLATFORMS constant."""
    
    def test_all_platforms_have_instructions(self, tmp_path):
        """Test all supported platforms can generate instructions."""
        cert_path = tmp_path / "cert.crt"
        key_path = tmp_path / "cert.key"
        ca_path = tmp_path / "ca.crt"
        cert_path.write_text("CERT")
        key_path.write_text("KEY")
        ca_path.write_text("CA")
        
        c2_url = "wss://c2.example.com:8444"
        
        for platform in SUPPORTED_PLATFORMS:
            instructions = get_instructions(platform, cert_path, key_path, ca_path, c2_url)
            assert len(instructions) > 100  # Reasonable minimum length
