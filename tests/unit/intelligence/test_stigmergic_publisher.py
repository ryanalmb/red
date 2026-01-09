"""Unit tests for StigmergicIntelligencePublisher and StigmergicIntelligenceSubscriber.

Story 5.10: Intelligence Stigmergic Publication

Tests stigmergic intelligence sharing for swarm-wide deduplication:
- Publisher serialization and topic generation
- Subscriber message handling and TTL expiration
- Integration with EventBus pub/sub
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.intelligence.base import IntelPriority, IntelResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_event_bus():
    """Mock EventBus for unit testing."""
    bus = MagicMock()
    bus.publish = AsyncMock(return_value=3)  # 3 subscribers
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def sample_intel_results():
    """Sample IntelResult list for testing."""
    return [
        IntelResult(
            source="cisa_kev",
            cve_id="CVE-2021-41773",
            severity="critical",
            exploit_available=True,
            exploit_path="/path/to/exploit",
            confidence=1.0,
            priority=IntelPriority.CISA_KEV,
            metadata={"added_date": "2021-11-03"},
        ),
        IntelResult(
            source="nvd",
            cve_id="CVE-2021-42013",
            severity="high",
            exploit_available=False,
            exploit_path=None,
            confidence=0.9,
            priority=IntelPriority.NVD_HIGH,
            metadata={},
        ),
    ]


# =============================================================================
# StigmergicIntelligencePublisher Tests
# =============================================================================


@pytest.mark.unit
class TestStigmergicIntelligencePublisherInstantiation:
    """Test StigmergicIntelligencePublisher instantiation."""

    async def test_publisher_can_be_instantiated_with_event_bus(self, mock_event_bus):
        """Test publisher can be created with EventBus."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        assert publisher is not None
        assert publisher._event_bus is mock_event_bus

    async def test_publisher_has_ttl_constant(self, mock_event_bus):
        """Test publisher has TTL_SECONDS = 300 (5 min)."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        assert publisher.TTL_SECONDS == 300


@pytest.mark.unit
class TestStigmergicIntelligencePublisherTopicGeneration:
    """Test topic generation for stigmergic publisher."""

    async def test_make_topic_generates_correct_format(self, mock_event_bus):
        """Test _make_topic generates findings:{target_hash}:intel_enriched."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        topic = publisher._make_topic("Apache", "2.4.49")

        # Topic format: findings:{hash}:intel_enriched
        assert topic.startswith("findings:")
        assert topic.endswith(":intel_enriched")

    async def test_make_topic_target_hash_is_sha256_first_8_chars(self, mock_event_bus):
        """Test target_hash is SHA256 of service:version (first 8 hex chars)."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        topic = publisher._make_topic("Apache", "2.4.49")

        # Calculate expected hash
        target_key = "apache:2.4.49"  # lowercased
        expected_hash = hashlib.sha256(target_key.encode()).hexdigest()[:8]
        expected_topic = f"findings:{expected_hash}:intel_enriched"

        assert topic == expected_topic

    async def test_make_topic_normalizes_service_version(self, mock_event_bus):
        """Test topic generation normalizes to lowercase."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        topic1 = publisher._make_topic("Apache", "2.4.49")
        topic2 = publisher._make_topic("APACHE", "2.4.49")
        topic3 = publisher._make_topic("apache", "2.4.49")

        assert topic1 == topic2 == topic3


@pytest.mark.unit
class TestStigmergicIntelligencePublisherPublish:
    """Test publish method of StigmergicIntelligencePublisher."""

    async def test_publish_serializes_intel_results(
        self, mock_event_bus, sample_intel_results
    ):
        """Test publish() serializes IntelResult list and calls EventBus.publish."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        result = await publisher.publish("Apache", "2.4.49", sample_intel_results)

        # Should have called publish
        mock_event_bus.publish.assert_called_once()

        # Get the call args
        call_args = mock_event_bus.publish.call_args
        topic = call_args[0][0]
        message = call_args[0][1]

        # Verify topic format
        assert topic.startswith("findings:")
        assert topic.endswith(":intel_enriched")

        # Verify message is serializable dict
        assert isinstance(message, dict)
        assert "results" in message
        assert len(message["results"]) == 2

    async def test_publish_includes_timestamp(
        self, mock_event_bus, sample_intel_results
    ):
        """Test published message includes timestamp."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        await publisher.publish("Apache", "2.4.49", sample_intel_results)

        message = mock_event_bus.publish.call_args[0][1]

        assert "timestamp" in message
        # Should be ISO format with Z suffix
        assert message["timestamp"].endswith("Z")

    async def test_publish_includes_ttl_seconds(
        self, mock_event_bus, sample_intel_results
    ):
        """Test published message includes ttl_seconds = 300."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        await publisher.publish("Apache", "2.4.49", sample_intel_results)

        message = mock_event_bus.publish.call_args[0][1]

        assert "ttl_seconds" in message
        assert message["ttl_seconds"] == 300

    async def test_publish_includes_source_agent_id(
        self, mock_event_bus, sample_intel_results
    ):
        """Test published message includes source_agent_id."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        await publisher.publish(
            "Apache", "2.4.49", sample_intel_results, agent_id="recon-47"
        )

        message = mock_event_bus.publish.call_args[0][1]

        assert message["source_agent_id"] == "recon-47"

    async def test_publish_default_agent_id_is_system(
        self, mock_event_bus, sample_intel_results
    ):
        """Test default agent_id is 'system'."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        await publisher.publish("Apache", "2.4.49", sample_intel_results)

        message = mock_event_bus.publish.call_args[0][1]

        assert message["source_agent_id"] == "system"

    async def test_publish_includes_service_and_version(
        self, mock_event_bus, sample_intel_results
    ):
        """Test published message includes service and version."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        await publisher.publish("Apache", "2.4.49", sample_intel_results)

        message = mock_event_bus.publish.call_args[0][1]

        assert message["service"] == "Apache"
        assert message["version"] == "2.4.49"

    async def test_publish_returns_subscriber_count(
        self, mock_event_bus, sample_intel_results
    ):
        """Test publish returns number of subscribers."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        mock_event_bus.publish = AsyncMock(return_value=5)
        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        result = await publisher.publish("Apache", "2.4.49", sample_intel_results)

        assert result == 5

    async def test_publish_with_empty_results(self, mock_event_bus):
        """Test publish with empty results list."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        result = await publisher.publish("Apache", "2.4.49", [])

        message = mock_event_bus.publish.call_args[0][1]
        assert message["results"] == []


# =============================================================================
# StigmergicIntelligenceSubscriber Tests
# =============================================================================


@pytest.mark.unit
class TestStigmergicIntelligenceSubscriberInstantiation:
    """Test StigmergicIntelligenceSubscriber instantiation."""

    async def test_subscriber_can_be_instantiated(self, mock_event_bus):
        """Test subscriber can be created with EventBus."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        assert subscriber is not None
        assert subscriber._event_bus is mock_event_bus

    async def test_subscriber_has_internal_cache(self, mock_event_bus):
        """Test subscriber has internal cache dict."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        assert hasattr(subscriber, "_cache")
        assert isinstance(subscriber._cache, dict)


@pytest.mark.unit
class TestStigmergicIntelligenceSubscriberSubscribe:
    """Test subscribe method."""

    async def test_subscribe_registers_with_event_bus(self, mock_event_bus):
        """Test subscribe() registers callback with EventBus."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        await subscriber.subscribe()

        # Should subscribe to findings:*:intel_enriched pattern
        mock_event_bus.subscribe.assert_called_once()
        call_args = mock_event_bus.subscribe.call_args
        pattern = call_args[0][0]
        assert pattern == "findings:*:intel_enriched"

    async def test_subscribe_with_custom_callback(self, mock_event_bus):
        """Test subscribe with custom callback."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)
        custom_callback = AsyncMock()

        await subscriber.subscribe(callback=custom_callback)

        mock_event_bus.subscribe.assert_called_once()


@pytest.mark.unit
class TestStigmergicIntelligenceSubscriberGet:
    """Test get method for retrieving cached results."""

    async def test_get_returns_cached_results_if_not_expired(self, mock_event_bus):
        """Test get() returns cached results if not expired."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        # Manually add to cache
        sample_result = IntelResult(
            source="test",
            cve_id="CVE-2021-1234",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )
        subscriber._cache["apache:2.4.49"] = {
            "results": [sample_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }

        results = subscriber.get("apache", "2.4.49")

        assert results is not None
        assert len(results) == 1
        assert results[0].cve_id == "CVE-2021-1234"

    async def test_get_returns_none_if_not_found(self, mock_event_bus):
        """Test get() returns None if not in cache."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        results = subscriber.get("unknown", "1.0.0")

        assert results is None

    async def test_get_returns_none_if_expired(self, mock_event_bus):
        """Test get() returns None if entry is expired."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        # Add expired entry
        sample_result = IntelResult(
            source="test",
            cve_id="CVE-2021-1234",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )
        subscriber._cache["apache:2.4.49"] = {
            "results": [sample_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() - timedelta(minutes=1),  # Expired
        }

        results = subscriber.get("apache", "2.4.49")

        assert results is None

    async def test_get_removes_expired_entry_from_cache(self, mock_event_bus):
        """Test get() removes expired entry from cache."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        # Add expired entry
        sample_result = IntelResult(
            source="test",
            cve_id="CVE-2021-1234",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )
        subscriber._cache["apache:2.4.49"] = {
            "results": [sample_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() - timedelta(minutes=1),
        }

        # Get should return None and clean up
        subscriber.get("apache", "2.4.49")

        assert "apache:2.4.49" not in subscriber._cache


@pytest.mark.unit
class TestStigmergicIntelligenceSubscriberMessageHandling:
    """Test message handling in subscriber."""

    async def test_handler_deserializes_intel_results(self, mock_event_bus):
        """Test subscriber handler deserializes IntelResult from message."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        # Capture the handler registered with subscribe
        await subscriber.subscribe()
        handler = mock_event_bus.subscribe.call_args[0][1]

        # Create a test message
        message = json.dumps(
            {
                "service": "Apache",
                "version": "2.4.49",
                "results": [
                    {
                        "source": "cisa_kev",
                        "cve_id": "CVE-2021-41773",
                        "severity": "critical",
                        "exploit_available": True,
                        "exploit_path": "/path/to/exploit",
                        "confidence": 1.0,
                        "priority": 1,
                        "metadata": {},
                    }
                ],
                "timestamp": "2026-01-08T05:00:00Z",
                "ttl_seconds": 300,
                "source_agent_id": "recon-47",
            }
        )

        # Call the handler
        await handler("findings:abc12345:intel_enriched", message)

        # Check cache was updated
        assert "apache:2.4.49" in subscriber._cache
        cached = subscriber._cache["apache:2.4.49"]
        assert len(cached["results"]) == 1
        assert cached["results"][0].cve_id == "CVE-2021-41773"

    async def test_handler_respects_ttl(self, mock_event_bus):
        """Test handler sets expires_at based on ttl_seconds."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        await subscriber.subscribe()
        handler = mock_event_bus.subscribe.call_args[0][1]

        message = json.dumps(
            {
                "service": "Apache",
                "version": "2.4.49",
                "results": [],
                "timestamp": "2026-01-08T05:00:00Z",
                "ttl_seconds": 300,
                "source_agent_id": "system",
            }
        )

        before = datetime.utcnow()
        await handler("findings:abc12345:intel_enriched", message)
        after = datetime.utcnow()

        cached = subscriber._cache["apache:2.4.49"]
        # expires_at should be ~5 minutes (300 seconds) from now
        expected_min = before + timedelta(seconds=295)
        expected_max = after + timedelta(seconds=305)

        assert expected_min <= cached["expires_at"] <= expected_max

    async def test_handler_calls_custom_callback(self, mock_event_bus):
        """Test handler calls custom callback when provided."""
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)
        custom_callback = AsyncMock()

        await subscriber.subscribe(callback=custom_callback)
        handler = mock_event_bus.subscribe.call_args[0][1]

        message = json.dumps(
            {
                "service": "Apache",
                "version": "2.4.49",
                "results": [
                    {
                        "source": "nvd",
                        "cve_id": "CVE-2021-12345",
                        "severity": "high",
                        "exploit_available": False,
                        "exploit_path": None,
                        "confidence": 0.9,
                        "priority": 3,
                        "metadata": {},
                    }
                ],
                "timestamp": "2026-01-08T05:00:00Z",
                "ttl_seconds": 300,
                "source_agent_id": "system",
            }
        )

        await handler("findings:abc12345:intel_enriched", message)

        custom_callback.assert_called_once()
        call_args = custom_callback.call_args[0]
        assert call_args[0] == "Apache"
        assert call_args[1] == "2.4.49"
        assert len(call_args[2]) == 1


# =============================================================================
# Aggregator Integration Tests
# =============================================================================


@pytest.mark.unit
class TestCachedIntelligenceAggregatorStigmergicIntegration:
    """Test CachedIntelligenceAggregator stigmergic integration."""

    async def test_aggregator_accepts_stigmergic_subscriber(self, mock_event_bus):
        """Test aggregator accepts optional StigmergicIntelligenceSubscriber."""
        from unittest.mock import MagicMock
        from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        mock_redis = MagicMock()
        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_subscriber=subscriber,
        )

        assert aggregator._stigmergic_subscriber is subscriber

    async def test_aggregator_accepts_stigmergic_publisher(self, mock_event_bus):
        """Test aggregator accepts optional StigmergicIntelligencePublisher."""
        from unittest.mock import MagicMock
        from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher

        mock_redis = MagicMock()
        publisher = StigmergicIntelligencePublisher(mock_event_bus)

        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_publisher=publisher,
        )

        assert aggregator._stigmergic_publisher is publisher

    async def test_aggregator_checks_stigmergic_first(self, mock_event_bus, sample_intel_results):
        """Test aggregator checks stigmergic cache before Redis cache."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
        from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber

        mock_redis = MagicMock()
        subscriber = StigmergicIntelligenceSubscriber(mock_event_bus)

        # Pre-populate stigmergic cache
        from datetime import datetime, timedelta
        subscriber._cache["apache:2.4.49"] = {
            "results": sample_intel_results,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }

        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_subscriber=subscriber,
        )

        # Mock the cache to verify it's not called
        with patch.object(aggregator, 'cache') as mock_cache:
            mock_cache.get_with_metadata = AsyncMock()

            results = await aggregator.query("Apache", "2.4.49")

            # Should return stigmergic results without checking Redis cache
            assert results == sample_intel_results
            # Cache should not be accessed when stigmergic hit
            mock_cache.get_with_metadata.assert_not_called()

    async def test_aggregator_publishes_after_source_query(
        self, mock_event_bus, sample_intel_results
    ):
        """Test aggregator publishes to stigmergic after source query."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
        from cyberred.intelligence.stigmergic import StigmergicIntelligencePublisher
        from cyberred.intelligence.base import IntelligenceSource

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.set = AsyncMock(return_value=True)

        publisher = StigmergicIntelligencePublisher(mock_event_bus)
        publisher.publish = AsyncMock(return_value=3)

        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_publisher=publisher,
        )

        # Mock the cache
        with patch.object(aggregator, 'cache') as mock_cache:
            mock_cache.get_with_metadata = AsyncMock(return_value=(None, None))
            mock_cache.set = AsyncMock()

            # Add a mock source that returns results
            mock_source = MagicMock(spec=IntelligenceSource)
            mock_source.name = "test_source"
            mock_source.query = AsyncMock(return_value=sample_intel_results)
            aggregator._sources = [mock_source]

            results = await aggregator.query("Apache", "2.4.49")

            # Should have published to stigmergic
            publisher.publish.assert_called_once()
            call_args = publisher.publish.call_args
            assert call_args[0][0] == "Apache"
            assert call_args[0][1] == "2.4.49"
