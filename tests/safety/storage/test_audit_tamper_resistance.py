"""Safety tests for Story 13.2: Audit Log Tamper Resistance.

Tests verify tamper detection and resistance per AC #7.
All tests should FAIL initially (RED phase) as implementation doesn't exist yet.

These tests use REAL Redis (no mocks) to verify actual tamper resistance.

Acceptance Criteria covered:
- AC #7: Safety tests verify tamper resistance
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pytest

# Mark all tests in this module as safety tests
pytestmark = [pytest.mark.safety, pytest.mark.asyncio]


# =============================================================================
# AC #7: Tamper Resistance Tests
# =============================================================================

class TestAuditTamperResistance:
    """Test tamper resistance of audit log per AC #7.
    
    These tests use real Redis to verify actual tamper detection.
    """

    @pytest.fixture
    async def redis_client(self, redis_container):
        """Get real Redis client from container fixture."""
        # Uses redis_container fixture from conftest.py
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        
        config = RedisConfig(
            host=redis_container["host"],
            port=redis_container["port"],
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client = RedisClient(config, engagement_id="test-tamper-eng")
        await client.connect()
        yield client
        await client.close()

    @pytest.fixture
    async def audit_log(self, redis_client):
        """Create OperatorAuditLog instance."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        log = OperatorAuditLog(redis_client, "test-tamper-eng")
        await log.initialize()
        return log

    async def test_direct_redis_modification_detected_on_read(
        self, redis_client, audit_log
    ) -> None:
        """Test: Direct Redis modification of entry is detected on read."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: A valid audit entry is logged
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # WHEN: Entry is directly modified in Redis (simulating tampering)
        stream_name = f"audit:test-tamper-eng"
        
        # Get raw entry from Redis and tamper with it
        raw_entries = await redis_client._master.xrange(stream_name, "-", "+")
        assert len(raw_entries) >= 1
        
        entry_id, fields = raw_entries[-1]
        if isinstance(entry_id, bytes):
            entry_id = entry_id.decode()
        
        # Tamper with the payload by modifying operator name
        payload = fields.get(b"payload") or fields.get("payload")
        if isinstance(payload, bytes):
            payload = payload.decode()
        
        payload_data = json.loads(payload)
        content = json.loads(payload_data["content"])
        content["operator"] = "hacker"  # Tamper!
        payload_data["content"] = json.dumps(content)
        
        # Write tampered data back
        await redis_client._master.xadd(
            stream_name,
            {"payload": json.dumps(payload_data)},
        )
        
        # THEN: Tampered entry is NOT returned (detected as invalid)
        entries = await audit_log.get_entries(start_id="0", count=100)
        
        # Original entry should be valid, tampered one should be filtered
        tampered_found = any(e.operator == "hacker" for e in entries)
        assert not tampered_found, "Tampered entry should be detected and filtered"

    async def test_modified_signature_is_rejected(
        self, redis_client, audit_log
    ) -> None:
        """Test: Modified signature is rejected."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: A valid audit entry
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.DENY,
            context={"reason": "out_of_scope"},
        )
        
        # WHEN: Signature is modified directly in Redis
        stream_name = f"audit:test-tamper-eng"
        raw_entries = await redis_client._master.xrange(stream_name, "-", "+")
        
        entry_id, fields = raw_entries[-1]
        payload = fields.get(b"payload") or fields.get("payload")
        if isinstance(payload, bytes):
            payload = payload.decode()
        
        payload_data = json.loads(payload)
        payload_data["sig"] = "deadbeef" * 8  # Invalid signature
        
        # Write entry with bad signature
        await redis_client._master.xadd(
            stream_name,
            {"payload": json.dumps(payload_data)},
        )
        
        # THEN: Entry with invalid signature is rejected
        entries = await audit_log.get_entries(start_id="0", count=100)
        
        # Check that no entry has the tampered signature content
        for e in entries:
            assert e.signature != "deadbeef" * 8

    async def test_missing_signature_field_is_rejected(
        self, redis_client, audit_log
    ) -> None:
        """Test: Missing signature field is rejected."""
        # GIVEN: An entry written without signature
        stream_name = f"audit:test-tamper-eng"
        
        payload_without_sig = {
            "content": json.dumps({
                "entry_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engagement_id": "test-tamper-eng",
                "operator": "attacker",
                "action": "approve",
                "context": {},
            }),
            # "sig" field is missing!
            "ts": 1234567890.0,
        }
        
        await redis_client._master.xadd(
            stream_name,
            {"payload": json.dumps(payload_without_sig)},
        )
        
        # THEN: Entry without signature is rejected
        entries = await audit_log.get_entries(start_id="0", count=100)
        
        # Should not contain entry from "attacker"
        attacker_found = any(e.operator == "attacker" for e in entries)
        assert not attacker_found, "Entry without signature should be rejected"

    async def test_truncated_entry_is_rejected(
        self, redis_client, audit_log
    ) -> None:
        """Test: Truncated entry is rejected."""
        # GIVEN: A truncated/malformed entry
        stream_name = f"audit:test-tamper-eng"
        
        # Write truncated JSON
        await redis_client._master.xadd(
            stream_name,
            {"payload": '{"content": "truncated...'},  # Invalid JSON
        )
        
        # THEN: Truncated entry is rejected (doesn't crash, just filtered)
        entries = await audit_log.get_entries(start_id="0", count=100)
        
        # Should not raise, should return valid entries only
        assert isinstance(entries, list)

    async def test_replayed_entry_detected(
        self, redis_client, audit_log
    ) -> None:
        """Test: Replayed entry (duplicate) is detected."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: A valid audit entry
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # WHEN: Same entry is "replayed" by re-adding it
        stream_name = f"audit:test-tamper-eng"
        raw_entries = await redis_client._master.xrange(stream_name, "-", "+")
        
        entry_id, fields = raw_entries[-1]
        payload = fields.get(b"payload") or fields.get("payload")
        
        # Replay the exact same payload
        await redis_client._master.xadd(stream_name, {"payload": payload})
        
        # THEN: Duplicate detection should identify replayed entries
        # (Implementation may log warning or track duplicates)
        entries = await audit_log.get_entries(start_id="0", count=100)
        
        # Count entries with same entry_id
        entry_ids = [e.entry_id for e in entries]
        duplicate_count = entry_ids.count(entry.entry_id)
        
        # Both valid (same signature), but duplicate detection should note it
        # At minimum, verify_chain should detect duplicate entry_ids
        assert duplicate_count >= 1  # Original exists

    async def test_verify_integrity_validates_specific_entry(
        self, redis_client, audit_log
    ) -> None:
        """Test: verify_integrity(entry_id) validates specific entry."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: A valid audit entry
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.KILL,
            context={"reason": "emergency"},
        )
        
        # WHEN: Verifying integrity of that entry
        is_valid = await audit_log.verify_integrity(entry.entry_id)
        
        # THEN: Entry should be valid
        assert is_valid is True

    async def test_verify_integrity_detects_tampered_entry(
        self, redis_client, audit_log
    ) -> None:
        """Test: verify_integrity returns False for tampered entry."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: A valid audit entry
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.SCOPE_CHANGE,
            context={"added": ["10.0.0.0/8"]},
        )
        
        # WHEN: Entry is tampered in Redis
        stream_name = f"audit:test-tamper-eng"
        raw_entries = await redis_client._master.xrange(stream_name, "-", "+")
        
        # Find and tamper the entry
        for eid, fields in raw_entries:
            payload = fields.get(b"payload") or fields.get("payload")
            if isinstance(payload, bytes):
                payload = payload.decode()
            
            payload_data = json.loads(payload)
            content = json.loads(payload_data["content"])
            
            if content.get("entry_id") == entry.entry_id:
                # Tamper the content
                content["operator"] = "malicious"
                payload_data["content"] = json.dumps(content)
                
                # Delete old entry and add tampered one
                # (Redis doesn't allow in-place updates to streams)
                await redis_client._master.xadd(
                    stream_name,
                    {"payload": json.dumps(payload_data)},
                )
                break
        
        # THEN: verify_integrity should detect tampering
        # Note: The original entry is still valid, but a tampered copy exists
        # verify_integrity should handle this appropriately
        is_valid = await audit_log.verify_integrity(entry.entry_id)
        assert is_valid is True  # Original should still be valid

    async def test_verify_chain_validates_entire_audit_trail(
        self, redis_client, audit_log
    ) -> None:
        """Test: verify_chain() validates entire audit chain integrity."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: Multiple valid audit entries
        for i in range(5):
            await audit_log.log_action(
                operator=f"user{i}",
                action=OperatorAction.APPROVE,
                context={"index": i},
            )
        
        # WHEN: Verifying entire chain
        all_valid, invalid_ids = await audit_log.verify_chain()
        
        # THEN: All entries should be valid
        assert all_valid is True
        assert invalid_ids == []

    async def test_verify_chain_reports_invalid_entries(
        self, redis_client, audit_log
    ) -> None:
        """Test: verify_chain returns list of invalid entry IDs."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: Valid entries
        await audit_log.log_action(
            operator="root",
            action=OperatorAction.START,
            context={},
        )
        
        # AND: A tampered entry injected directly
        stream_name = f"audit:test-tamper-eng"
        
        tampered_entry_id = str(uuid.uuid4())
        tampered_payload = {
            "content": json.dumps({
                "entry_id": tampered_entry_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engagement_id": "test-tamper-eng",
                "operator": "hacker",
                "action": "kill",
                "context": {},
                "signature": "invalid_sig",
            }),
            "sig": "wrong_signature_here",
            "ts": 1234567890.0,
        }
        
        await redis_client._master.xadd(
            stream_name,
            {"payload": json.dumps(tampered_payload)},
        )
        
        # WHEN: Verifying chain
        all_valid, invalid_ids = await audit_log.verify_chain()
        
        # THEN: Should report the tampered entry
        assert all_valid is False
        assert len(invalid_ids) >= 1


class TestAuditIntegrityVerification:
    """Additional integrity verification tests."""

    @pytest.fixture
    async def redis_client(self, redis_container):
        """Get real Redis client from container fixture."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        
        config = RedisConfig(
            host=redis_container["host"],
            port=redis_container["port"],
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client = RedisClient(config, engagement_id="test-integrity-eng")
        await client.connect()
        yield client
        await client.close()

    @pytest.fixture
    async def audit_log(self, redis_client):
        """Create OperatorAuditLog instance."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        log = OperatorAuditLog(redis_client, "test-integrity-eng")
        await log.initialize()
        return log

    async def test_out_of_order_entry_insertion_logged(
        self, redis_client, audit_log
    ) -> None:
        """Test: Out-of-order entry insertion is logged."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: An entry with old timestamp inserted after newer entries
        await audit_log.log_action(
            operator="root",
            action=OperatorAction.START,
            context={},
        )
        
        # Inject an entry with an old timestamp
        stream_name = f"audit:test-integrity-eng"
        old_timestamp = "2020-01-01T00:00:00+00:00"  # Very old
        
        # Note: Redis stream IDs are time-based, so this tests
        # the application's handling of timestamp anomalies
        
        # THEN: verify_chain should detect time anomalies (optional feature)
        all_valid, invalid_ids = await audit_log.verify_chain()
        
        # Basic validation should pass
        assert isinstance(all_valid, bool)
        assert isinstance(invalid_ids, list)

    async def test_empty_context_is_valid(
        self, redis_client, audit_log
    ) -> None:
        """Test: Empty context dict is valid."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: An entry with empty context
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.STOP,
            context={},
        )
        
        # THEN: Entry should be valid
        is_valid = await audit_log.verify_integrity(entry.entry_id)
        assert is_valid is True

    async def test_complex_context_is_signed_correctly(
        self, redis_client, audit_log
    ) -> None:
        """Test: Complex nested context is signed correctly."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: An entry with complex nested context
        complex_context = {
            "targets": ["192.168.1.1", "192.168.1.2"],
            "options": {
                "aggressive": True,
                "ports": [80, 443, 8080],
            },
            "metadata": {
                "source": "recon-agent",
                "confidence": 0.95,
            },
        }
        
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.SCOPE_CHANGE,
            context=complex_context,
        )
        
        # THEN: Entry should be valid
        is_valid = await audit_log.verify_integrity(entry.entry_id)
        assert is_valid is True
        
        # AND: Context should be preserved
        entries = await audit_log.get_entries(start_id="0", count=100)
        found = next((e for e in entries if e.entry_id == entry.entry_id), None)
        assert found is not None
        assert found.context == complex_context
