"""Unit tests for Story 7.13: Stigmergic Topic Sharding.

Tests for ShardedTopic, ShardedEventBus, and ShardAggregator classes.
These tests verify sharding behavior to prevent "stigmergic storm" (NFR1, NFR8).
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.core.sharding import (
    DEFAULT_SHARD_COUNT,
    AggregatedBatch,
    ShardAggregator,
    ShardedEventBus,
    ShardedTopic,
)


# =============================================================================
# ShardedTopic Tests (Task 1)
# =============================================================================


class TestShardedTopic:
    """Tests for ShardedTopic class."""

    def test_init_default_shard_count(self):
        """Test ShardedTopic initializes with default shard count."""
        topic = ShardedTopic("findings")
        assert topic.base_topic == "findings"
        assert topic.shard_count == DEFAULT_SHARD_COUNT
        assert topic.shard_count == 16

    def test_init_custom_shard_count(self):
        """Test ShardedTopic with custom shard count."""
        for count in [4, 8, 16, 32]:
            topic = ShardedTopic("findings", shard_count=count)
            assert topic.shard_count == count

    def test_get_shard_returns_consistent_values(self):
        """Test get_shard returns same value for same input (AC: 5.1)."""
        topic = ShardedTopic("findings", shard_count=16)
        target_hash = "abc123def456"
        
        # Call multiple times
        results = [topic.get_shard(target_hash) for _ in range(100)]
        
        # All results should be identical
        assert len(set(results)) == 1
        assert all(r == results[0] for r in results)

    def test_get_shard_returns_valid_range(self):
        """Test get_shard returns value in valid range [0, shard_count)."""
        for shard_count in [4, 8, 16, 32]:
            topic = ShardedTopic("findings", shard_count=shard_count)
            
            # Test with various hashes
            test_hashes = [
                "abc123",
                "def456",
                "xyz789",
                "a" * 64,
                "f" * 64,
                "0" * 64,
            ]
            
            for target_hash in test_hashes:
                shard = topic.get_shard(target_hash)
                assert 0 <= shard < shard_count, f"Shard {shard} out of range for count {shard_count}"

    def test_get_shard_distribution_is_reasonable(self):
        """Test shard distribution is approximately uniform."""
        topic = ShardedTopic("findings", shard_count=16)
        
        # Generate 1000 random hashes and check distribution
        shard_counts = {i: 0 for i in range(16)}
        
        for i in range(1000):
            target_hash = hashlib.sha256(f"target_{i}".encode()).hexdigest()
            shard = topic.get_shard(target_hash)
            shard_counts[shard] += 1
        
        # Each shard should have roughly 1000/16 = 62.5 entries
        # Allow ±50% variance for statistical reasonability
        for shard, count in shard_counts.items():
            assert 20 < count < 120, f"Shard {shard} has {count} entries, distribution is skewed"

    def test_get_channel_format_correct(self):
        """Test get_channel produces correct sharded channel format (AC: 5.2)."""
        topic = ShardedTopic("findings", shard_count=16)
        target_hash = "abc123"
        finding_type = "sqli"
        
        channel = topic.get_channel(target_hash, finding_type)
        
        # Format should be: findings:shard:{N}:{type}
        assert channel.startswith("findings:shard:")
        parts = channel.split(":")
        assert len(parts) == 4
        assert parts[0] == "findings"
        assert parts[1] == "shard"
        assert parts[2].isdigit()
        assert int(parts[2]) < 16
        assert parts[3] == "sqli"

    def test_get_channel_uses_correct_shard(self):
        """Test get_channel uses shard from get_shard."""
        topic = ShardedTopic("findings", shard_count=16)
        target_hash = "abc123"
        finding_type = "xss"
        
        expected_shard = topic.get_shard(target_hash)
        channel = topic.get_channel(target_hash, finding_type)
        
        # Extract shard from channel
        shard_in_channel = int(channel.split(":")[2])
        assert shard_in_channel == expected_shard

    def test_get_all_shard_patterns_default(self):
        """Test get_all_shard_patterns returns all shards with wildcard type."""
        topic = ShardedTopic("findings", shard_count=16)
        
        patterns = topic.get_all_shard_patterns()
        
        assert len(patterns) == 16
        for i, pattern in enumerate(patterns):
            assert pattern == f"findings:shard:{i}:*"

    def test_get_all_shard_patterns_with_type(self):
        """Test get_all_shard_patterns with specific finding type."""
        topic = ShardedTopic("findings", shard_count=8)
        
        patterns = topic.get_all_shard_patterns(finding_type="sqli")
        
        assert len(patterns) == 8
        for i, pattern in enumerate(patterns):
            assert pattern == f"findings:shard:{i}:sqli"

    def test_different_targets_can_have_same_shard(self):
        """Test that different targets can hash to same shard (collision is OK)."""
        topic = ShardedTopic("findings", shard_count=4)  # Low count = more collisions
        
        # Find two targets with same shard
        shards_seen = {}
        for i in range(1000):
            target_hash = f"target_{i}"
            shard = topic.get_shard(target_hash)
            if shard in shards_seen:
                # Found collision - this is expected behavior
                assert shards_seen[shard] != target_hash
                return
            shards_seen[shard] = target_hash
        
        # Should have found a collision with 1000 targets in 4 shards
        pytest.fail("Should have found shard collision")

    def test_shard_count_validation_zero(self):
        """Test that shard_count=0 raises ValueError."""
        with pytest.raises(ValueError, match="shard_count must be > 0"):
            ShardedTopic("findings", shard_count=0)

    def test_shard_count_validation_negative(self):
        """Test that negative shard_count raises ValueError."""
        with pytest.raises(ValueError, match="shard_count must be > 0"):
            ShardedTopic("findings", shard_count=-1)


# =============================================================================
# ShardedEventBus Tests (Task 2)
# =============================================================================


class TestShardedEventBus:
    """Tests for ShardedEventBus wrapper class."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value=1)
        bus.subscribe = AsyncMock(return_value=MagicMock())
        return bus

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.redis = MagicMock()
        settings.redis.shard_count = 16
        return settings

    def test_init_with_default_shard_count(self, mock_event_bus, mock_settings):
        """Test ShardedEventBus initializes with default shard count."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus)
            assert bus.shard_count == 16

    def test_init_with_custom_shard_count(self, mock_event_bus, mock_settings):
        """Test ShardedEventBus with custom shard count."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=32)
            assert bus.shard_count == 32

    @pytest.mark.asyncio
    async def test_publish_finding_routes_to_correct_shard(self, mock_event_bus, mock_settings):
        """Test publish_finding routes to sharded channel (AC: 5.3)."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            target_hash = "abc123"
            finding_type = "sqli"
            message = {"id": "f1", "data": "test"}
            
            await bus.publish_finding(target_hash, finding_type, message)
            
            # Verify publish was called
            mock_event_bus.publish.assert_called_once()
            call_args = mock_event_bus.publish.call_args
            
            # Channel should be sharded format
            channel = call_args[0][0]
            assert channel.startswith("findings:shard:")
            assert channel.endswith(":sqli")
            
            # Message should be passed through
            assert call_args[0][1] == message

    @pytest.mark.asyncio
    async def test_publish_finding_consistent_routing(self, mock_event_bus, mock_settings):
        """Test same target always routes to same shard."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            target_hash = "consistent_target"
            
            # Publish multiple times
            for i in range(5):
                await bus.publish_finding(target_hash, f"type_{i}", {"data": i})
            
            # All calls should use same shard number
            channels = [call[0][0] for call in mock_event_bus.publish.call_args_list]
            shard_numbers = [int(ch.split(":")[2]) for ch in channels]
            
            assert len(set(shard_numbers)) == 1, "Same target should always route to same shard"

    @pytest.mark.asyncio
    async def test_subscribe_findings_all_shards(self, mock_event_bus, mock_settings):
        """Test subscribe_findings subscribes to all shards (AC: 5.4)."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            callback = AsyncMock()
            await bus.subscribe_findings(callback)
            
            # Should subscribe to all 16 shards
            assert mock_event_bus.subscribe.call_count == 16
            
            # Verify all shard patterns
            subscribed_patterns = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
            for i in range(16):
                assert f"findings:shard:{i}:*" in subscribed_patterns

    @pytest.mark.asyncio
    async def test_subscribe_findings_with_shard_subset(self, mock_event_bus, mock_settings):
        """Test subscribe_findings with specific shard subset."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            callback = AsyncMock()
            await bus.subscribe_findings(callback, shard_subset=[0, 1, 2, 3])
            
            # Should only subscribe to 4 shards
            assert mock_event_bus.subscribe.call_count == 4
            
            subscribed_patterns = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
            for i in [0, 1, 2, 3]:
                assert f"findings:shard:{i}:*" in subscribed_patterns

    @pytest.mark.asyncio
    async def test_subscribe_findings_with_finding_type_filter(self, mock_event_bus, mock_settings):
        """Test subscribe_findings with specific finding type."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=8)
            
            callback = AsyncMock()
            await bus.subscribe_findings(callback, finding_type="sqli")
            
            # All patterns should filter by type
            subscribed_patterns = [call[0][0] for call in mock_event_bus.subscribe.call_args_list]
            for pattern in subscribed_patterns:
                assert pattern.endswith(":sqli")

    @pytest.mark.asyncio
    async def test_passthrough_publish_non_sharded(self, mock_event_bus, mock_settings):
        """Test publish() passthrough for non-sharded channels."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            await bus.publish("control:kill", {"reason": "test"})
            
            mock_event_bus.publish.assert_called_once_with("control:kill", {"reason": "test"})

    @pytest.mark.asyncio
    async def test_passthrough_subscribe_non_sharded(self, mock_event_bus, mock_settings):
        """Test subscribe() passthrough for non-sharded channels."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)
            
            callback = AsyncMock()
            await bus.subscribe("control:kill", callback)
            
            mock_event_bus.subscribe.assert_called_once_with("control:kill", callback)


# =============================================================================
# AggregatedBatch Tests (Task 3 - helper class)
# =============================================================================


class TestAggregatedBatch:
    """Tests for AggregatedBatch dataclass."""

    def test_init_empty(self):
        """Test AggregatedBatch initializes empty."""
        batch = AggregatedBatch()
        assert batch.findings == []
        assert batch.seen_ids == set()
        assert batch.start_time is not None

    def test_add_finding_success(self):
        """Test adding finding to batch."""
        batch = AggregatedBatch()
        finding = {"id": "f1", "target": "192.168.1.1", "type": "sqli"}
        
        result = batch.add(finding)
        
        assert result is True
        assert len(batch.findings) == 1
        assert "f1" in batch.seen_ids

    def test_add_duplicate_finding_rejected(self):
        """Test duplicate findings are rejected (AC: 5.5 deduplication)."""
        batch = AggregatedBatch()
        finding1 = {"id": "f1", "target": "192.168.1.1", "type": "sqli"}
        finding2 = {"id": "f1", "target": "192.168.1.1", "type": "sqli"}  # Same ID
        
        result1 = batch.add(finding1)
        result2 = batch.add(finding2)
        
        assert result1 is True
        assert result2 is False
        assert len(batch.findings) == 1

    def test_add_finding_with_nested_id(self):
        """Test finding with ID in data field."""
        batch = AggregatedBatch()
        finding = {"data": {"id": "nested_id"}, "target": "192.168.1.1"}
        
        result = batch.add(finding)
        
        assert result is True
        assert "nested_id" in batch.seen_ids

    def test_add_finding_fallback_dedupe_key(self):
        """Test fallback dedupe key when no ID present uses content hash."""
        batch = AggregatedBatch()
        finding1 = {"target": "192.168.1.1", "type": "sqli", "agent_id": "agent1"}
        finding2 = {"target": "192.168.1.1", "type": "sqli", "agent_id": "agent1"}  # Identical content
        finding3 = {"target": "192.168.1.2", "type": "sqli", "agent_id": "agent1"}  # Different target
        
        result1 = batch.add(finding1)
        result2 = batch.add(finding2)  # Same content = same hash = duplicate
        result3 = batch.add(finding3)
        
        assert result1 is True
        assert result2 is False  # Duplicate (identical content)
        assert result3 is True  # Different target = different content hash

    def test_add_finding_different_payload_not_deduplicated(self):
        """Test that findings with same target/type but different payloads are NOT deduplicated."""
        batch = AggregatedBatch()
        # Two findings with same target/type/agent but different severity - should BOTH be added
        finding1 = {"target": "192.168.1.1", "type": "sqli", "agent_id": "agent1", "severity": "high"}
        finding2 = {"target": "192.168.1.1", "type": "sqli", "agent_id": "agent1", "severity": "critical"}
        
        result1 = batch.add(finding1)
        result2 = batch.add(finding2)
        
        assert result1 is True
        assert result2 is True  # Different content = different hash = NOT a duplicate
        assert len(batch.findings) == 2


# =============================================================================
# ShardAggregator Tests (Task 3)
# =============================================================================


class TestShardAggregator:
    """Tests for ShardAggregator class."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value=1)
        bus.subscribe = AsyncMock(return_value=MagicMock())
        return bus

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.redis = MagicMock()
        settings.redis.shard_count = 16
        return settings

    def test_init(self, mock_event_bus, mock_settings):
        """Test ShardAggregator initialization."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
                batch_window_ms=100,
            )
            
            assert aggregator._engagement_id == "eng123"
            assert aggregator._batch_window_ms == 100

    @pytest.mark.asyncio
    async def test_start_subscribes_to_all_shards(self, mock_event_bus, mock_settings):
        """Test start() subscribes to all shard channels."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=8,
            )
            
            await aggregator.start()
            
            # Should have subscribed via ShardedEventBus
            # The ShardedEventBus subscribes to all shards
            assert mock_event_bus.subscribe.call_count == 8
            
            await aggregator.stop()

    @pytest.mark.asyncio
    async def test_handle_finding_batches_messages(self, mock_event_bus, mock_settings):
        """Test findings are batched (AC: 5.5 batching)."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
                batch_window_ms=1000,  # Long window for test
            )
            
            # Simulate handling findings
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            await aggregator._handle_finding("findings:shard:1:xss", {"id": "f2"})
            
            # Batch should contain 2 findings
            assert len(aggregator._current_batch.findings) == 2

    @pytest.mark.asyncio
    async def test_handle_finding_deduplicates(self, mock_event_bus, mock_settings):
        """Test duplicate findings are deduplicated."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            # Same finding twice
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            await aggregator._handle_finding("findings:shard:1:sqli", {"id": "f1"})  # Duplicate
            
            # Only 1 finding in batch
            assert len(aggregator._current_batch.findings) == 1
            assert aggregator._total_deduplicated == 1

    @pytest.mark.asyncio
    async def test_flush_batch_publishes_aggregated(self, mock_event_bus, mock_settings):
        """Test flush publishes to aggregated channel."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            # Add findings
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            await aggregator._handle_finding("findings:shard:1:xss", {"id": "f2"})
            
            # Flush
            await aggregator._flush_batch()
            
            # Should publish to aggregated channel
            mock_event_bus.publish.assert_called_once()
            call_args = mock_event_bus.publish.call_args
            
            channel = call_args[0][0]
            assert channel == "findings:aggregated:eng123"
            
            payload = call_args[0][1]
            assert "findings" in payload
            assert payload["count"] == 2

    @pytest.mark.asyncio
    async def test_flush_batch_empty_does_nothing(self, mock_event_bus, mock_settings):
        """Test flush with empty batch does not publish."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            await aggregator._flush_batch()
            
            mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_shard_distribution_metrics(self, mock_event_bus, mock_settings):
        """Test shard distribution tracking (AC: 3.6)."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            # Findings from different shards
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            await aggregator._handle_finding("findings:shard:0:xss", {"id": "f2"})
            await aggregator._handle_finding("findings:shard:5:sqli", {"id": "f3"})
            
            distribution = aggregator.get_shard_distribution()
            
            assert distribution[0] == 2  # Two findings on shard 0
            assert distribution[5] == 1  # One finding on shard 5

    @pytest.mark.asyncio
    async def test_get_metrics(self, mock_event_bus, mock_settings):
        """Test aggregator metrics."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})  # Duplicate
            await aggregator._handle_finding("findings:shard:1:xss", {"id": "f2"})
            
            metrics = aggregator.get_metrics()
            
            assert metrics["total_received"] == 3
            assert metrics["total_deduplicated"] == 1
            assert metrics["dedup_rate"] == 1 / 3

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self, mock_event_bus, mock_settings):
        """Test stop() flushes remaining batch."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
                batch_window_ms=10000,  # Long window
            )
            
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            
            # Stop should flush
            aggregator._running = True
            await aggregator.stop()
            
            mock_event_bus.publish.assert_called_once()


# =============================================================================
# Configuration-driven shard count tests (AC: 5.6)
# =============================================================================


class TestShardingConfiguration:
    """Tests for configuration-driven shard counts."""

    @pytest.mark.parametrize("shard_count", [4, 8, 16, 32])
    def test_sharded_topic_respects_config(self, shard_count):
        """Test ShardedTopic respects configured shard count."""
        topic = ShardedTopic("findings", shard_count=shard_count)
        
        assert topic.shard_count == shard_count
        patterns = topic.get_all_shard_patterns()
        assert len(patterns) == shard_count

    @pytest.mark.parametrize("shard_count", [4, 8, 16, 32])
    def test_sharded_event_bus_respects_config(self, shard_count):
        """Test ShardedEventBus respects configured shard count."""
        mock_bus = MagicMock()
        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = shard_count
        
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_bus, shard_count=shard_count)
            assert bus.shard_count == shard_count

    def test_sharded_event_bus_fallback_on_settings_error(self):
        """Test ShardedEventBus falls back to default when get_settings fails."""
        mock_bus = MagicMock()
        
        with patch("cyberred.core.sharding.get_settings", side_effect=Exception("Config error")):
            bus = ShardedEventBus(mock_bus)
            assert bus.shard_count == DEFAULT_SHARD_COUNT


# =============================================================================
# Edge case tests for full coverage
# =============================================================================


class TestShardingEdgeCases:
    """Edge case tests for full coverage."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value=1)
        bus.subscribe = AsyncMock(return_value=MagicMock())
        return bus

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.redis = MagicMock()
        settings.redis.shard_count = 16
        return settings

    @pytest.mark.asyncio
    async def test_handle_finding_invalid_channel_format(self, mock_event_bus, mock_settings):
        """Test aggregator handles invalid channel format gracefully."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            # Channel with non-numeric shard (should trigger ValueError path)
            await aggregator._handle_finding("findings:shard:invalid:sqli", {"id": "f1"})
            
            # Should still process the finding
            assert aggregator._total_received == 1
            assert len(aggregator._current_batch.findings) == 1
            # Shard counts should be empty since parsing failed
            assert aggregator.get_shard_distribution() == {}

    @pytest.mark.asyncio
    async def test_handle_finding_non_shard_channel(self, mock_event_bus, mock_settings):
        """Test aggregator handles non-shard channel format."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
            )
            
            # Channel without "shard" prefix
            await aggregator._handle_finding("findings:abc123:sqli", {"id": "f1"})
            
            # Should still process the finding
            assert aggregator._total_received == 1
            assert len(aggregator._current_batch.findings) == 1

    @pytest.mark.asyncio
    async def test_flush_loop_executes_periodically(self, mock_event_bus, mock_settings):
        """Test _flush_loop runs and flushes batches periodically."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
                batch_window_ms=50,  # Short window for test
            )
            
            # Start the aggregator
            aggregator._running = True
            
            # Add a finding
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            
            # Start flush loop in background
            flush_task = asyncio.create_task(aggregator._flush_loop())
            
            # Wait for at least one flush cycle
            await asyncio.sleep(0.1)
            
            # Stop the loop
            aggregator._running = False
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            
            # Verify flush was called (publish should have been called)
            assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_aggregator_start_and_stop_lifecycle(self, mock_event_bus, mock_settings):
        """Test full start/stop lifecycle of aggregator."""
        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng123",
                shard_count=16,
                batch_window_ms=50,
            )
            
            # Start
            await aggregator.start()
            assert aggregator._running is True
            assert aggregator._flush_task is not None
            
            # Add finding
            await aggregator._handle_finding("findings:shard:0:sqli", {"id": "f1"})
            
            # Stop (should flush remaining)
            await aggregator.stop()
            assert aggregator._running is False
            
            # Verify final flush happened
            mock_event_bus.publish.assert_called()
