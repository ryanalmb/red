"""Integration tests for Story 7.13: Stigmergic Topic Sharding.

Tests sharding under realistic conditions with actual async operations
and concurrent publishing from multiple agents.

NFR1: Agent coordination latency <1s stigmergic propagation
NFR8: Scale to 10K concurrent agents without Redis overload
"""

import asyncio
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.core.sharding import (
    AGGREGATOR_BATCH_MS,
    DEFAULT_SHARD_COUNT,
    AggregatedBatch,
    ShardAggregator,
    ShardedEventBus,
    ShardedTopic,
)


# =============================================================================
# Integration Tests for Sharding Under Load (AC: 6.1-6.5)
# =============================================================================


@pytest.mark.integration
class TestShardingIntegration:
    """Integration tests for sharding under realistic conditions."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus with realistic behavior."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value=1)
        bus.subscribe = AsyncMock(return_value=MagicMock())
        return bus

    @pytest.mark.asyncio
    async def test_concurrent_publishing_from_multiple_agents(self, mock_event_bus):
        """Test 100 agents publishing to sharded topics concurrently (AC: 6.1)."""
        from unittest.mock import patch

        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = 16

        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            # Create 100 "agents" (simulated as sharded bus instances)
            buses = [ShardedEventBus(mock_event_bus, shard_count=16) for _ in range(100)]

            # Each agent publishes a finding
            async def agent_publish(agent_idx: int, bus: ShardedEventBus):
                target_hash = hashlib.sha256(f"target_{agent_idx}".encode()).hexdigest()
                await bus.publish_finding(
                    target_hash,
                    "sqli",
                    {"id": f"finding_{agent_idx}", "agent": agent_idx},
                )

            # Publish concurrently
            start_time = time.perf_counter()
            await asyncio.gather(*[
                agent_publish(i, buses[i]) for i in range(100)
            ])
            elapsed = time.perf_counter() - start_time

            # All 100 publishes should complete
            assert mock_event_bus.publish.call_count == 100

            # Should complete quickly (NFR1: <1s latency)
            assert elapsed < 1.0, f"Concurrent publishing took {elapsed:.2f}s, expected <1s"

    @pytest.mark.asyncio
    async def test_aggregator_batches_and_deduplicates_under_load(self, mock_event_bus):
        """Test aggregator correctly batches and deduplicates under load (AC: 6.2)."""
        from unittest.mock import patch

        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = 16

        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng-load-test",
                shard_count=16,
                batch_window_ms=50,  # Short window for test
            )

            # Simulate 200 findings with 50% duplicates
            findings = []
            for i in range(100):
                # Each finding appears twice (duplicate)
                findings.append({"id": f"finding_{i}", "data": {"target": f"192.168.1.{i}"}})
                findings.append({"id": f"finding_{i}", "data": {"target": f"192.168.1.{i}"}})

            # Process all findings
            for idx, finding in enumerate(findings):
                shard = idx % 16
                await aggregator._handle_finding(f"findings:shard:{shard}:sqli", finding)

            # Verify metrics
            metrics = aggregator.get_metrics()
            assert metrics["total_received"] == 200
            assert metrics["total_deduplicated"] == 100  # 50% were duplicates
            assert metrics["dedup_rate"] == 0.5

            # Flush and verify aggregated output
            await aggregator._flush_batch()
            
            # Should have published aggregated findings
            mock_event_bus.publish.assert_called()
            call_args = mock_event_bus.publish.call_args
            payload = call_args[0][1]
            assert payload["count"] == 100  # Only unique findings

    @pytest.mark.asyncio
    async def test_shard_distribution_is_uniform(self, mock_event_bus):
        """Test shard distribution is approximately uniform (AC: 6.3)."""
        from unittest.mock import patch

        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = 16

        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng-dist-test",
                shard_count=16,
                batch_window_ms=1000,
            )

            # Simulate 1600 findings (100 per shard expected for uniform distribution)
            for i in range(1600):
                target_hash = hashlib.sha256(f"target_{i}".encode()).hexdigest()
                shard = ShardedTopic("findings", 16).get_shard(target_hash)
                await aggregator._handle_finding(
                    f"findings:shard:{shard}:scan",
                    {"id": f"finding_{i}"},
                )

            distribution = aggregator.get_shard_distribution()

            # Check all shards received messages
            assert len(distribution) == 16

            # Check distribution is reasonably uniform (within 50% of expected)
            expected_per_shard = 1600 / 16  # 100
            for shard, count in distribution.items():
                assert 50 < count < 150, f"Shard {shard} has {count}, expected ~100"

    @pytest.mark.asyncio
    async def test_backward_compatibility_with_non_sharded_channels(self, mock_event_bus):
        """Test backward compatibility with non-sharded channels (AC: 6.5)."""
        from unittest.mock import patch

        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = 16

        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            bus = ShardedEventBus(mock_event_bus, shard_count=16)

            # Non-sharded publish should work
            await bus.publish("control:kill", {"reason": "test"})
            mock_event_bus.publish.assert_called_with("control:kill", {"reason": "test"})

            # Non-sharded subscribe should work
            callback = AsyncMock()
            await bus.subscribe("strategies:eng123", callback)
            mock_event_bus.subscribe.assert_called_with("strategies:eng123", callback)

    @pytest.mark.asyncio
    async def test_full_pipeline_publish_aggregate_consume(self, mock_event_bus):
        """Test full sharding pipeline: publish -> aggregate -> consume."""
        from unittest.mock import patch

        mock_settings = MagicMock()
        mock_settings.redis = MagicMock()
        mock_settings.redis.shard_count = 8

        with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
            # Setup aggregator
            aggregator = ShardAggregator(
                mock_event_bus,
                engagement_id="eng-pipeline",
                shard_count=8,
                batch_window_ms=50,
            )

            # Start aggregator
            await aggregator.start()

            # Simulate multiple agents publishing findings
            sharded_bus = ShardedEventBus(mock_event_bus, shard_count=8)
            
            for i in range(50):
                target_hash = f"target_{i}"
                await sharded_bus.publish_finding(
                    target_hash,
                    "recon",
                    {"id": f"f_{i}", "port": 80 + i},
                )

            # Also simulate findings arriving at aggregator
            for i in range(50):
                shard = i % 8
                await aggregator._handle_finding(
                    f"findings:shard:{shard}:recon",
                    {"id": f"agg_{i}", "data": {"port": i}},
                )

            # Wait for flush
            await asyncio.sleep(0.1)

            # Stop aggregator (triggers final flush)
            await aggregator.stop()

            # Verify aggregated channel was published to
            publish_calls = [
                call for call in mock_event_bus.publish.call_args_list
                if call[0][0] == "findings:aggregated:eng-pipeline"
            ]
            assert len(publish_calls) > 0, "Aggregated findings should be published"

    @pytest.mark.asyncio
    async def test_sharding_with_different_shard_counts(self, mock_event_bus):
        """Test sharding works correctly with different shard counts."""
        from unittest.mock import patch

        for shard_count in [4, 8, 16, 32]:
            mock_settings = MagicMock()
            mock_settings.redis = MagicMock()
            mock_settings.redis.shard_count = shard_count

            mock_event_bus.reset_mock()

            with patch("cyberred.core.sharding.get_settings", return_value=mock_settings):
                bus = ShardedEventBus(mock_event_bus, shard_count=shard_count)
                
                # Publish to each shard
                for i in range(shard_count * 2):
                    target_hash = f"target_{i}"
                    await bus.publish_finding(target_hash, "scan", {"idx": i})

                # Verify all publishes went through
                assert mock_event_bus.publish.call_count == shard_count * 2

                # Verify channels are sharded
                channels = [call[0][0] for call in mock_event_bus.publish.call_args_list]
                for channel in channels:
                    assert channel.startswith("findings:shard:")
                    parts = channel.split(":")
                    shard_num = int(parts[2])
                    assert 0 <= shard_num < shard_count


@pytest.mark.integration
class TestShardedTopicConsistency:
    """Tests for consistent hashing behavior."""

    def test_same_target_always_same_shard(self):
        """Test consistent hashing - same target always maps to same shard."""
        topic = ShardedTopic("findings", shard_count=16)
        
        target = "192.168.1.100"
        expected_shard = topic.get_shard(target)
        
        # Verify 1000 times
        for _ in range(1000):
            assert topic.get_shard(target) == expected_shard

    def test_shard_stability_across_instances(self):
        """Test shard assignment is stable across different ShardedTopic instances."""
        topic1 = ShardedTopic("findings", shard_count=16)
        topic2 = ShardedTopic("findings", shard_count=16)
        
        targets = [f"target_{i}" for i in range(100)]
        
        for target in targets:
            assert topic1.get_shard(target) == topic2.get_shard(target)

    def test_channel_format_consistency(self):
        """Test channel format is consistent."""
        topic = ShardedTopic("findings", shard_count=16)
        
        for i in range(100):
            target = f"target_{i}"
            channel = topic.get_channel(target, "sqli")
            
            # Verify format
            parts = channel.split(":")
            assert len(parts) == 4
            assert parts[0] == "findings"
            assert parts[1] == "shard"
            assert parts[2].isdigit()
            assert parts[3] == "sqli"
