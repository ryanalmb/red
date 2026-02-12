"""Unit tests for enhanced timestamp signing (Story 13.10).

Tests for sign_event_timestamp() and verify_event_timestamp() methods
that bind timestamps to specific events for legal defensibility.
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from cyberred.core.time import TrustedTime


class TestSignEventTimestamp:
    """Tests for TrustedTime.sign_event_timestamp() method."""
    
    def test_sign_event_timestamp_returns_dict_with_required_fields(self):
        """Test that sign_event_timestamp returns dict with timestamp, event_hash, signature."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result = time_provider.sign_event_timestamp(event_hash, key)
        
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "event_hash" in result
        assert "signature" in result
    
    def test_sign_event_timestamp_includes_event_hash_in_result(self):
        """Test that event_hash is included in returned dict."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result = time_provider.sign_event_timestamp(event_hash, key)
        
        assert result["event_hash"] == event_hash
    
    def test_sign_event_timestamp_creates_valid_signature(self):
        """Test that signature is HMAC-SHA256 of timestamp + event_hash."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result = time_provider.sign_event_timestamp(event_hash, key)
        
        # Manually verify the signature
        message = result["timestamp"] + result["event_hash"]
        expected_sig = hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
        expected_b64 = base64.b64encode(expected_sig).decode("utf-8")
        
        assert result["signature"] == expected_b64
    
    def test_sign_event_timestamp_different_events_produce_different_signatures(self):
        """Test that different event hashes produce different signatures."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash1 = hashlib.sha256(b"event1").hexdigest()
        event_hash2 = hashlib.sha256(b"event2").hexdigest()
        
        result1 = time_provider.sign_event_timestamp(event_hash1, key)
        result2 = time_provider.sign_event_timestamp(event_hash2, key)
        
        assert result1["signature"] != result2["signature"]
    
    def test_sign_event_timestamp_different_keys_produce_different_signatures(self):
        """Test that different keys produce different signatures."""
        time_provider = TrustedTime()
        key1 = b"0" * 32
        key2 = b"1" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result1 = time_provider.sign_event_timestamp(event_hash, key1)
        result2 = time_provider.sign_event_timestamp(event_hash, key2)
        
        assert result1["signature"] != result2["signature"]
    
    def test_sign_event_timestamp_uses_utc_timezone(self):
        """Test that timestamp includes UTC timezone indicator."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result = time_provider.sign_event_timestamp(event_hash, key)
        
        # ISO 8601 format should include timezone
        assert "+00:00" in result["timestamp"] or result["timestamp"].endswith("Z")


class TestVerifyEventTimestamp:
    """Tests for TrustedTime.verify_event_timestamp() method."""
    
    def test_verify_event_timestamp_validates_correct_signature(self):
        """Test that valid signature is verified successfully."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key)
        is_valid = time_provider.verify_event_timestamp(signed_data, key)
        
        assert is_valid is True
    
    def test_verify_event_timestamp_rejects_invalid_signature(self):
        """Test that invalid signature is rejected."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key)
        # Tamper with signature
        signed_data["signature"] = base64.b64encode(b"invalid_signature").decode("utf-8")
        
        is_valid = time_provider.verify_event_timestamp(signed_data, key)
        
        assert is_valid is False
    
    def test_verify_event_timestamp_rejects_wrong_key(self):
        """Test that signature created with different key is rejected."""
        time_provider = TrustedTime()
        key1 = b"0" * 32
        key2 = b"1" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key1)
        is_valid = time_provider.verify_event_timestamp(signed_data, key2)
        
        assert is_valid is False
    
    def test_verify_event_timestamp_rejects_modified_timestamp(self):
        """Test that modifying timestamp invalidates signature."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key)
        # Tamper with timestamp
        signed_data["timestamp"] = "2020-01-01T00:00:00+00:00"
        
        is_valid = time_provider.verify_event_timestamp(signed_data, key)
        
        assert is_valid is False
    
    def test_verify_event_timestamp_rejects_modified_event_hash(self):
        """Test that modifying event_hash invalidates signature."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key)
        # Tamper with event_hash
        signed_data["event_hash"] = hashlib.sha256(b"tampered").hexdigest()
        
        is_valid = time_provider.verify_event_timestamp(signed_data, key)
        
        assert is_valid is False
    
    def test_verify_event_timestamp_uses_constant_time_comparison(self):
        """Test that verification uses hmac.compare_digest for timing attack prevention."""
        time_provider = TrustedTime()
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = time_provider.sign_event_timestamp(event_hash, key)
        
        # Patch hmac.compare_digest to verify it's being called
        with patch("hmac.compare_digest", wraps=hmac.compare_digest) as mock_compare:
            time_provider.verify_event_timestamp(signed_data, key)
            mock_compare.assert_called_once()


class TestModuleLevelEventSigningFunctions:
    """Tests for module-level convenience functions."""
    
    def test_sign_event_timestamp_module_function_works(self):
        """Test that module-level sign_event_timestamp() function works."""
        from cyberred.core.time import sign_event_timestamp
        
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        result = sign_event_timestamp(event_hash, key)
        
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "event_hash" in result
        assert "signature" in result
    
    def test_verify_event_timestamp_module_function_works(self):
        """Test that module-level verify_event_timestamp() function works."""
        from cyberred.core.time import sign_event_timestamp, verify_event_timestamp
        
        key = b"0" * 32
        event_hash = hashlib.sha256(b"test_event").hexdigest()
        
        signed_data = sign_event_timestamp(event_hash, key)
        is_valid = verify_event_timestamp(signed_data, key)
        
        assert is_valid is True
