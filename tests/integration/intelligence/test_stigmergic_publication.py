"""Integration tests for Story 5.10: Stigmergic Intelligence Publication.

Tests stigmergic intelligence sharing with REAL Redis - no mocks.
Uses testcontainers for Redis to verify:
- End-to-end pub/sub messaging
- Multiple subscribers receive same message
- TTL expiration (5 min) is honored
- Query order: stigmergic → cache → sources
- Swarm scenario: Agent A publishes, Agent B receives

AC: 6 - Integration tests verify pub/sub, TTL, and swarm intelligence sharing.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta

import pytest

from cyberred.core.config import RedisConfig
from cyberred.core.events import EventBus
from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
from cyberred.intelligence.base import IntelligenceSource, IntelPriority, IntelResult
from cyberred.intelligence.stigmergic import (
    StigmergicIntelligencePublisher,
    StigmergicIntelligenceSubscriber,
)
from cyberred.storage.redis_client import RedisClient


@pytest.fixture(scope="function")
def redis_container():
    """Provide a real Redis container for integration tests."""
    from testcontainers.redis import RedisContainer

    container = RedisContainer("redis:7-alpine")
    container.start()

    yield container

    container.stop()


@pytest.fixture
def redis_config(redis_container):
    """Create RedisConfig from testcontainer."""
    host = redis_container.get_container_host_ip()
    port = int(redis_container.get_exposed_port(6379))

    return RedisConfig(
        host=host,
        port=port,
        sentinel_hosts=[],
        master_name="mymaster",
    )


@pytest.fixture
async def redis_client(redis_config):
    """Create RedisClient connected to test Redis."""
    client = RedisClient(redis_config, engagement_id="stigmergic-test")
    await client.connect()

    yield client

    await client.close()


@pytest.fixture
async def event_bus(redis_client):
    """Create EventBus with RedisClient connected to test Redis."""
    bus = EventBus(redis_client)
    yield bus


def make_sample_results():
    """Create sample IntelResult for testing."""
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


class MockIntelSource(IntelligenceSource):
    """Mock intelligence source for integration testing."""

    def __init__(self, name: str, results=None):
        super().__init__(name)
        self._results = results or []
        self.call_count = 0

    async def query(self, service: str, version: str):
        self.call_count += 1
        return self._results

    async def health_check(self):
        return True


@pytest.mark.integration
class TestStigmergicPubSubIntegration:
    """Integration tests for stigmergic pub/sub with real Redis."""

    @pytest.mark.asyncio
    async def test_publisher_subscriber_round_trip(self, event_bus):
        """Test end-to-end pub/sub with real Redis (AC: 6)."""
        # Create publisher and subscriber
        publisher = StigmergicIntelligencePublisher(event_bus)
        subscriber = StigmergicIntelligenceSubscriber(event_bus)

        # Track received messages
        received_future = asyncio.get_event_loop().create_future()

        async def on_message(service: str, version: str, results):
            if not received_future.done():
                received_future.set_result((service, version, results))

        # Subscribe
        await subscriber.subscribe(callback=on_message)

        # Give subscription time to register
        await asyncio.sleep(0.2)

        # Publish
        sample_results = make_sample_results()
        subscriber_count = await publisher.publish("Apache", "2.4.49", sample_results)

        # Wait for callback
        try:
            recv_service, recv_version, recv_results = await asyncio.wait_for(
                received_future, timeout=2.0
            )

            assert recv_service == "Apache"
            assert recv_version == "2.4.49"
            assert len(recv_results) == 2
            assert recv_results[0].cve_id == "CVE-2021-41773"
            assert recv_results[1].cve_id == "CVE-2021-42013"

        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for stigmergic message")

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_same_message(self, event_bus):
        """Test multiple subscribers receive same message (AC: 6)."""
        publisher = StigmergicIntelligencePublisher(event_bus)

        # Create 3 independent subscribers
        subscriber1 = StigmergicIntelligenceSubscriber(event_bus)
        subscriber2 = StigmergicIntelligenceSubscriber(event_bus)
        subscriber3 = StigmergicIntelligenceSubscriber(event_bus)

        received = {1: None, 2: None, 3: None}
        events = {1: asyncio.Event(), 2: asyncio.Event(), 3: asyncio.Event()}

        async def make_callback(idx):
            async def callback(service, version, results):
                received[idx] = (service, version, len(results))
                events[idx].set()
            return callback

        await subscriber1.subscribe(callback=await make_callback(1))
        await subscriber2.subscribe(callback=await make_callback(2))
        await subscriber3.subscribe(callback=await make_callback(3))

        # Wait for subscriptions
        await asyncio.sleep(0.3)

        # Publish
        sample_results = make_sample_results()
        await publisher.publish("Nginx", "1.19.0", sample_results)

        # Wait for all subscribers
        try:
            await asyncio.wait_for(
                asyncio.gather(events[1].wait(), events[2].wait(), events[3].wait()),
                timeout=3.0
            )

            # All should have received the message
            assert received[1] == ("Nginx", "1.19.0", 2)
            assert received[2] == ("Nginx", "1.19.0", 2)
            assert received[3] == ("Nginx", "1.19.0", 2)

        except asyncio.TimeoutError:
            pytest.fail(f"Not all subscribers received message: {received}")

    @pytest.mark.asyncio
    async def test_subscriber_local_cache_ttl_expiration(self, event_bus):
        """Test subscriber cache respects TTL (5 min) - uses short TTL for test (AC: 6)."""
        subscriber = StigmergicIntelligenceSubscriber(event_bus)

        # Manually populate cache with expired entry
        sample_result = IntelResult(
            source="test",
            cve_id="CVE-2021-1234",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )

        # Add entry that expired 1 minute ago
        subscriber._cache["apache:2.4.49"] = {
            "results": [sample_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() - timedelta(minutes=1),  # Expired!
        }

        # Get should return None for expired entry
        results = subscriber.get("apache", "2.4.49")
        assert results is None

        # Cache entry should be removed
        assert "apache:2.4.49" not in subscriber._cache

    @pytest.mark.asyncio
    async def test_subscriber_cache_hit_for_valid_entry(self, event_bus):
        """Test subscriber cache returns results if not expired."""
        subscriber = StigmergicIntelligenceSubscriber(event_bus)

        sample_result = IntelResult(
            source="test",
            cve_id="CVE-2021-1234",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )

        # Add valid entry (expires in 5 minutes)
        subscriber._cache["apache:2.4.49"] = {
            "results": [sample_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }

        results = subscriber.get("apache", "2.4.49")
        assert results is not None
        assert len(results) == 1
        assert results[0].cve_id == "CVE-2021-1234"


@pytest.mark.integration
class TestStigmergicAggregatorIntegration:
    """Integration tests for CachedIntelligenceAggregator with stigmergic layer."""

    @pytest.mark.asyncio
    async def test_query_order_stigmergic_before_cache(self, redis_client, event_bus):
        """Test query order: stigmergic → cache → sources (AC: 3, 5)."""
        # Setup
        subscriber = StigmergicIntelligenceSubscriber(event_bus)
        publisher = StigmergicIntelligencePublisher(event_bus)

        aggregator = CachedIntelligenceAggregator(
            redis_client,
            stigmergic_subscriber=subscriber,
            stigmergic_publisher=publisher,
        )

        # Add a source that should NOT be called if stigmergic hits
        mock_source = MockIntelSource("test_src", [])
        aggregator.add_source(mock_source)

        # Pre-populate stigmergic cache
        stigmergic_result = IntelResult(
            source="stigmergic",
            cve_id="CVE-STIGMERGIC",
            severity="critical",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.CISA_KEV,
        )
        subscriber._cache["apache:2.4.49"] = {
            "results": [stigmergic_result],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
        }

        # Query - should hit stigmergic, NOT call source
        results = await aggregator.query("Apache", "2.4.49")

        assert len(results) == 1
        assert results[0].source == "stigmergic"
        assert results[0].cve_id == "CVE-STIGMERGIC"
        assert mock_source.call_count == 0  # Source NOT called

    @pytest.mark.asyncio
    async def test_aggregator_publishes_after_source_query(
        self, redis_client, event_bus
    ):
        """Test aggregator publishes to stigmergic after source query (AC: 1, 5)."""
        # Setup subscriber to verify publish
        subscriber = StigmergicIntelligenceSubscriber(event_bus)
        publisher = StigmergicIntelligencePublisher(event_bus)

        received_future = asyncio.get_event_loop().create_future()

        async def on_publish(service, version, results):
            if not received_future.done():
                received_future.set_result((service, version, results))

        await subscriber.subscribe(callback=on_publish)
        await asyncio.sleep(0.2)

        # Create aggregator with publisher (but NO subscriber so it queries sources)
        aggregator = CachedIntelligenceAggregator(
            redis_client,
            stigmergic_subscriber=None,  # No subscriber = will query sources
            stigmergic_publisher=publisher,
        )

        # Add source with results
        source_result = IntelResult(
            source="mock_src",
            cve_id="CVE-2024-0001",
            severity="high",
            exploit_available=True,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_HIGH,
        )
        mock_source = MockIntelSource("mock_src", [source_result])
        aggregator.add_source(mock_source)

        # Query - should call source and publish to stigmergic
        results = await aggregator.query("Apache", "2.4.49")

        assert len(results) == 1
        assert mock_source.call_count == 1

        # Verify stigmergic received the published results
        try:
            recv_service, recv_version, recv_results = await asyncio.wait_for(
                received_future, timeout=2.0
            )
            assert recv_service == "Apache"
            assert recv_version == "2.4.49"
            assert len(recv_results) == 1
            assert recv_results[0].cve_id == "CVE-2024-0001"

        except asyncio.TimeoutError:
            pytest.fail("Stigmergic publish was not received")

    @pytest.mark.asyncio
    async def test_swarm_scenario_agent_sharing(self, redis_client, event_bus):
        """Test swarm scenario: Agent A publishes, Agent B receives via stigmergic (AC: 6)."""
        # Agent A setup
        agent_a_publisher = StigmergicIntelligencePublisher(event_bus)

        # Agent B setup
        agent_b_subscriber = StigmergicIntelligenceSubscriber(event_bus)

        received_future = asyncio.get_event_loop().create_future()

        async def on_receive(service, version, results):
            if not received_future.done():
                received_future.set_result((service, version, results))

        await agent_b_subscriber.subscribe(callback=on_receive)
        await asyncio.sleep(0.2)

        # Agent A publishes intelligence results
        agent_a_results = [
            IntelResult(
                source="agent_a_scan",
                cve_id="CVE-SWARM-TEST",
                severity="critical",
                exploit_available=True,
                exploit_path="/msf/module/path",
                confidence=1.0,
                priority=IntelPriority.CISA_KEV,
                metadata={"discovered_by": "agent_a"},
            )
        ]
        await agent_a_publisher.publish(
            "OpenSSH", "8.2p1", agent_a_results, agent_id="agent-a-recon-01"
        )

        # Agent B should receive it
        try:
            recv_service, recv_version, recv_results = await asyncio.wait_for(
                received_future, timeout=2.0
            )

            assert recv_service == "OpenSSH"
            assert recv_version == "8.2p1"
            assert len(recv_results) == 1
            assert recv_results[0].cve_id == "CVE-SWARM-TEST"
            assert recv_results[0].metadata.get("discovered_by") == "agent_a"

            # Agent B can now use this from stigmergic cache
            cached = agent_b_subscriber.get("openssh", "8.2p1")
            assert cached is not None
            assert len(cached) == 1
            assert cached[0].cve_id == "CVE-SWARM-TEST"

        except asyncio.TimeoutError:
            pytest.fail("Agent B did not receive Agent A's intelligence")

    @pytest.mark.asyncio
    async def test_stigmergic_latency_under_threshold(self, event_bus):
        """Verify stigmergic pub/sub latency < 1s (NFR1 requirement)."""
        publisher = StigmergicIntelligencePublisher(event_bus)
        subscriber = StigmergicIntelligenceSubscriber(event_bus)

        received_future = asyncio.get_event_loop().create_future()
        publish_time = None

        async def on_receive(service, version, results):
            if not received_future.done():
                received_future.set_result(time.perf_counter())

        await subscriber.subscribe(callback=on_receive)
        await asyncio.sleep(0.2)

        # Publish and measure latency
        publish_time = time.perf_counter()
        await publisher.publish("Apache", "2.4.49", make_sample_results())

        try:
            receive_time = await asyncio.wait_for(received_future, timeout=2.0)
            latency_ms = (receive_time - publish_time) * 1000

            # NFR1: Stigmergic propagation should be < 1000ms
            assert latency_ms < 1000, f"Latency {latency_ms}ms exceeds threshold"

        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for stigmergic message")
