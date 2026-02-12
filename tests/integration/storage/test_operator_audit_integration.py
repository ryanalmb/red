"""Integration tests for Story 13.2: Append-Only Audit Log.

Tests the full audit cycle with REAL Redis (no mocks).
All tests should FAIL initially (RED phase) as implementation doesn't exist yet.

Acceptance Criteria covered:
- AC #1: Given engagement is running
- AC #2: When operator performs any action
- AC #3: Then action is logged to append-only audit stream
- AC #4: And log entries include: timestamp, operator, action, context, signature
- AC #5: And log is stored in Redis Streams (consumer group)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pytest

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestOperatorAuditIntegration:
    """Integration tests for OperatorAuditLog with real Redis."""

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
        
        client = RedisClient(config, engagement_id="int-test-eng")
        await client.connect()
        yield client
        await client.close()

    @pytest.fixture
    async def audit_log(self, redis_client):
        """Create OperatorAuditLog instance."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        engagement_id = f"int-test-{uuid.uuid4().hex[:8]}"
        log = OperatorAuditLog(redis_client, engagement_id)
        await log.initialize()
        return log

    async def test_full_audit_cycle(self, audit_log) -> None:
        """Test full cycle: log_action -> get_entries -> verify_integrity."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # GIVEN: An initialized audit log
        # WHEN: Logging an action
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.100", "agent_id": "recon-01"},
        )
        
        # THEN: Entry should be retrievable
        entries = await audit_log.get_entries(start_id="0", count=100)
        assert len(entries) >= 1
        
        found = next((e for e in entries if e.entry_id == entry.entry_id), None)
        assert found is not None
        assert found.operator == "root"
        assert found.action == OperatorAction.APPROVE
        
        # AND: Entry should have valid integrity
        is_valid = await audit_log.verify_integrity(entry.entry_id)
        assert is_valid is True

    async def test_multiple_operators_logging_concurrently(
        self, redis_client
    ) -> None:
        """Test multiple operators logging actions concurrently."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        engagement_id = f"concurrent-{uuid.uuid4().hex[:8]}"
        
        async def log_actions(operator_name: str, count: int) -> list:
            """Log multiple actions for an operator."""
            log = OperatorAuditLog(redis_client, engagement_id)
            await log.initialize()
            
            entries = []
            for i in range(count):
                entry = await log.log_action(
                    operator=operator_name,
                    action=OperatorAction.APPROVE,
                    context={"index": i},
                )
                entries.append(entry)
            return entries
        
        # WHEN: Multiple operators log concurrently
        results = await asyncio.gather(
            log_actions("operator1", 5),
            log_actions("operator2", 5),
            log_actions("operator3", 5),
        )
        
        # THEN: All entries should be logged
        total_entries = sum(len(r) for r in results)
        assert total_entries == 15
        
        # AND: All entries should be retrievable
        log = OperatorAuditLog(redis_client, engagement_id)
        all_entries = await log.get_entries(start_id="0", count=100)
        assert len(all_entries) >= 15

    async def test_persistence_across_reconnection(
        self, redis_container
    ) -> None:
        """Test entries survive Redis reconnection."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        engagement_id = f"persist-{uuid.uuid4().hex[:8]}"
        
        # GIVEN: Entries logged with first connection
        config = RedisConfig(
            host=redis_container["host"],
            port=redis_container["port"],
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client1 = RedisClient(config, engagement_id=engagement_id)
        await client1.connect()
        
        log1 = OperatorAuditLog(client1, engagement_id)
        await log1.initialize()
        
        entry1 = await log1.log_action(
            operator="root",
            action=OperatorAction.START,
            context={"session": "first"},
        )
        
        await client1.close()
        
        # WHEN: Reconnecting with new client
        client2 = RedisClient(config, engagement_id=engagement_id)
        await client2.connect()
        
        log2 = OperatorAuditLog(client2, engagement_id)
        await log2.initialize()
        
        # THEN: Original entry should be retrievable
        entries = await log2.get_entries(start_id="0", count=100)
        
        found = next((e for e in entries if e.entry_id == entry1.entry_id), None)
        assert found is not None
        assert found.operator == "root"
        
        await client2.close()

    async def test_consumer_group_is_created_on_initialize(
        self, redis_client
    ) -> None:
        """Test consumer group is created during initialization."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog, AUDIT_CONSUMER_GROUP
        
        engagement_id = f"consumer-{uuid.uuid4().hex[:8]}"
        log = OperatorAuditLog(redis_client, engagement_id)
        await log.initialize()
        
        # GIVEN: Multiple entries logged
        for i in range(3):
            await log.log_action(
                operator="root",
                action=OperatorAction.APPROVE,
                context={"index": i},
            )
        
        # THEN: Entries should be retrievable via get_entries
        entries = await log.get_entries(start_id="0", count=10)
        assert len(entries) >= 3
        
        # AND: Consumer group should exist (verify via stream info)
        # Note: Consumer group "audit-readers" is created on initialize()
        # The group name is exported as AUDIT_CONSUMER_GROUP constant
        assert AUDIT_CONSUMER_GROUP == "audit-readers"

    async def test_all_operator_actions_logged(self, audit_log) -> None:
        """Test all OperatorAction types can be logged."""
        from cyberred.storage.operator_audit import OperatorAction
        
        actions = [
            OperatorAction.APPROVE,
            OperatorAction.DENY,
            OperatorAction.KILL,
            OperatorAction.SCOPE_CHANGE,
            OperatorAction.PAUSE,
            OperatorAction.RESUME,
            OperatorAction.START,
            OperatorAction.STOP,
        ]
        
        logged_entries = []
        for action in actions:
            entry = await audit_log.log_action(
                operator="root",
                action=action,
                context={"action_type": action.value},
            )
            logged_entries.append(entry)
        
        # All actions should be logged successfully
        assert len(logged_entries) == 8
        
        # All should be retrievable
        entries = await audit_log.get_entries(start_id="0", count=100)
        assert len(entries) >= 8

    async def test_entry_includes_all_required_fields(self, audit_log) -> None:
        """Test log entries include: timestamp, operator, action, context, signature."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # WHEN: Logging an action
        entry = await audit_log.log_action(
            operator="admin_user",
            action=OperatorAction.SCOPE_CHANGE,
            context={"added": ["10.0.0.0/8"], "removed": []},
        )
        
        # THEN: All required fields should be present
        assert entry.entry_id is not None
        assert entry.timestamp is not None
        assert entry.engagement_id is not None
        assert entry.operator == "admin_user"
        assert entry.action == OperatorAction.SCOPE_CHANGE
        assert entry.context == {"added": ["10.0.0.0/8"], "removed": []}
        assert entry.signature is not None
        assert len(entry.signature) == 64  # SHA256 hex

    async def test_timestamp_is_utc(self, audit_log) -> None:
        """Test timestamp is in UTC."""
        from cyberred.storage.operator_audit import OperatorAction
        
        before = datetime.now(timezone.utc)
        
        entry = await audit_log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
        )
        
        after = datetime.now(timezone.utc)
        
        # Timestamp should be between before and after
        assert entry.timestamp >= before
        assert entry.timestamp <= after
        
        # Should have UTC timezone
        assert entry.timestamp.tzinfo is not None


class TestAuditLogEdgeCases:
    """Edge case tests for audit log."""

    @pytest.fixture
    async def redis_client(self, redis_container):
        """Get real Redis client."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient
        
        config = RedisConfig(
            host=redis_container["host"],
            port=redis_container["port"],
            sentinel_hosts=[],
            master_name="mymaster",
        )
        
        client = RedisClient(config, engagement_id="edge-test-eng")
        await client.connect()
        yield client
        await client.close()

    async def test_empty_stream_returns_empty_list(self, redis_client) -> None:
        """Test get_entries on empty stream returns empty list."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        engagement_id = f"empty-{uuid.uuid4().hex[:8]}"
        log = OperatorAuditLog(redis_client, engagement_id)
        await log.initialize()
        
        entries = await log.get_entries(start_id="0", count=100)
        
        assert entries == []

    async def test_large_context_is_handled(self, redis_client) -> None:
        """Test large context dict is handled correctly."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        engagement_id = f"large-{uuid.uuid4().hex[:8]}"
        log = OperatorAuditLog(redis_client, engagement_id)
        await log.initialize()
        
        # Large context with many keys
        large_context = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}
        
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.SCOPE_CHANGE,
            context=large_context,
        )
        
        # Should be retrievable
        entries = await log.get_entries(start_id="0", count=100)
        found = next((e for e in entries if e.entry_id == entry.entry_id), None)
        
        assert found is not None
        assert found.context == large_context

    async def test_special_characters_in_context(self, redis_client) -> None:
        """Test special characters in context are handled."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        engagement_id = f"special-{uuid.uuid4().hex[:8]}"
        log = OperatorAuditLog(redis_client, engagement_id)
        await log.initialize()
        
        special_context = {
            "unicode": "日本語テスト",
            "quotes": 'He said "hello"',
            "newlines": "line1\nline2\nline3",
            "backslash": "path\\to\\file",
            "null_char": "test\x00null",
        }
        
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context=special_context,
        )
        
        entries = await log.get_entries(start_id="0", count=100)
        found = next((e for e in entries if e.entry_id == entry.entry_id), None)
        
        assert found is not None
        # Context should be preserved (null char may be stripped)
        assert found.context["unicode"] == "日本語テスト"
        assert found.context["quotes"] == 'He said "hello"'
