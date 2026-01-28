"""Unit tests for StrategyPublisher and PublishedStrategy.

Story 8.10: Strategy Publication to Agents.

Tests strategy publication from DirectorEnsemble to agents via Redis pub/sub.
"""

import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    ATTCKRecommendation,
    CreativeAlternative,
    DirectorRole,
    SynthesizedStrategy,
    DegradationLevel,
)
from cyberred.orchestration.strategy_publisher import (
    PublishedStrategy,
    StrategyPublisher,
)
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole




class TestPublishedStrategy:
    """Tests for PublishedStrategy dataclass."""

    def test_published_strategy_creation(self):
        """Test PublishedStrategy can be created with all required fields."""
        strategy = PublishedStrategy(
            engagement_id="eng-001",
            objectives=["Enumerate services", "Find vulnerabilities"],
            priorities=["192.168.1.1", "192.168.1.2"],
            recommended_techniques=[
                {"technique_id": "T1046", "name": "Network Service Discovery", "rationale": "Initial recon"}
            ],
            avoid_list=["192.168.1.100"],
            confidence=0.85,
            timestamp=time.time(),
            contributing_roles=["strategist", "analyst"],
            rationale="Based on multi-model synthesis",
        )

        assert strategy.engagement_id == "eng-001"
        assert len(strategy.objectives) == 2
        assert strategy.confidence == 0.85
        assert len(strategy.contributing_roles) == 2

    def test_published_strategy_to_json(self):
        """Test PublishedStrategy serializes to JSON correctly."""
        

        ts = time.time()
        strategy = PublishedStrategy(
            engagement_id="eng-002",
            objectives=["Test objective"],
            priorities=["target1"],
            recommended_techniques=[],
            avoid_list=["bad-target"],
            confidence=0.9,
            timestamp=ts,
            contributing_roles=["strategist"],
            rationale="Test rationale",
        )

        json_data = strategy.to_json()
        assert isinstance(json_data, dict)
        assert json_data["engagement_id"] == "eng-002"
        assert json_data["objectives"] == ["Test objective"]
        assert json_data["avoid_list"] == ["bad-target"]
        assert json_data["confidence"] == 0.9
        assert json_data["timestamp"] == ts

    def test_published_strategy_from_synthesized(self):
        """Test PublishedStrategy can be created from SynthesizedStrategy."""
        
        

        synthesized = SynthesizedStrategy(
            objectives=["Exploit SSH", "Pivot internally"],
            actions=["Run hydra", "Try credentials"],
            rationale="Strategic approach based on findings",
            confidence=0.75,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
            avoid_list=["10.0.0.1"],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1110",
                    technique_name="Brute Force",
                    rationale="Weak passwords likely",
                    phase="credential-access",
                )
            ],
            degradation_level=DegradationLevel.FULL,
        )

        published = PublishedStrategy.from_synthesized(
            synthesized=synthesized,
            engagement_id="eng-003",
        )

        assert published.engagement_id == "eng-003"
        assert published.objectives == ["Exploit SSH", "Pivot internally"]
        assert published.avoid_list == ["10.0.0.1"]
        assert published.confidence == 0.75
        assert "strategist" in published.contributing_roles
        assert "analyst" in published.contributing_roles
        assert len(published.recommended_techniques) == 1
        assert published.recommended_techniques[0]["technique_id"] == "T1110"

    def test_published_strategy_confidence_validation(self):
        """Test PublishedStrategy validates confidence bounds."""

        with pytest.raises(ValueError, match="confidence must be between"):
            PublishedStrategy(
                engagement_id="eng-err",
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=1.5,  # Invalid
                timestamp=time.time(),
                contributing_roles=[],
                rationale="",
            )

        with pytest.raises(ValueError, match="confidence must be between"):
            PublishedStrategy(
                engagement_id="eng-err",
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=-0.1,  # Invalid
                timestamp=time.time(),
                contributing_roles=[],
                rationale="",
            )

    def test_published_strategy_confidence_boundary_values(self):
        """Test PublishedStrategy accepts confidence at boundary values 0.0 and 1.0."""
        ts = time.time()
        
        # Test confidence = 0.0 (minimum valid)
        strategy_min = PublishedStrategy(
            engagement_id="eng-bound",
            objectives=[],
            priorities=[],
            recommended_techniques=[],
            avoid_list=[],
            confidence=0.0,
            timestamp=ts,
            contributing_roles=[],
            rationale="",
        )
        assert strategy_min.confidence == 0.0
        
        # Test confidence = 1.0 (maximum valid)
        strategy_max = PublishedStrategy(
            engagement_id="eng-bound",
            objectives=[],
            priorities=[],
            recommended_techniques=[],
            avoid_list=[],
            confidence=1.0,
            timestamp=ts,
            contributing_roles=[],
            rationale="",
        )
        assert strategy_max.confidence == 1.0

    def test_published_strategy_engagement_id_validation(self):
        """Test PublishedStrategy validates engagement_id is non-empty string."""
        ts = time.time()
        
        # Empty engagement_id
        with pytest.raises(ValueError, match="engagement_id must be a non-empty string"):
            PublishedStrategy(
                engagement_id="",
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=0.5,
                timestamp=ts,
                contributing_roles=[],
                rationale="",
            )
        
        # None engagement_id
        with pytest.raises(ValueError, match="engagement_id must be a non-empty string"):
            PublishedStrategy(
                engagement_id=None,  # type: ignore
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=0.5,
                timestamp=ts,
                contributing_roles=[],
                rationale="",
            )

    def test_published_strategy_timestamp_validation(self):
        """Test PublishedStrategy validates timestamp is non-negative."""
        with pytest.raises(ValueError, match="timestamp must be non-negative"):
            PublishedStrategy(
                engagement_id="eng-ts",
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=0.5,
                timestamp=-1000.0,  # Negative - invalid
                contributing_roles=[],
                rationale="",
            )
        
        # Zero timestamp should be valid
        strategy = PublishedStrategy(
            engagement_id="eng-ts",
            objectives=[],
            priorities=[],
            recommended_techniques=[],
            avoid_list=[],
            confidence=0.5,
            timestamp=0.0,  # Zero is valid
            contributing_roles=[],
            rationale="",
        )
        assert strategy.timestamp == 0.0

    def test_published_strategy_none_list_fields_validation(self):
        """Test PublishedStrategy validates list fields are not None."""
        ts = time.time()
        
        with pytest.raises(ValueError, match="objectives cannot be None"):
            PublishedStrategy(
                engagement_id="eng-none",
                objectives=None,  # type: ignore
                priorities=[],
                recommended_techniques=[],
                avoid_list=[],
                confidence=0.5,
                timestamp=ts,
                contributing_roles=[],
                rationale="",
            )
        
        with pytest.raises(ValueError, match="priorities cannot be None"):
            PublishedStrategy(
                engagement_id="eng-none",
                objectives=[],
                priorities=None,  # type: ignore
                recommended_techniques=[],
                avoid_list=[],
                confidence=0.5,
                timestamp=ts,
                contributing_roles=[],
                rationale="",
            )
        
        with pytest.raises(ValueError, match="avoid_list cannot be None"):
            PublishedStrategy(
                engagement_id="eng-none",
                objectives=[],
                priorities=[],
                recommended_techniques=[],
                avoid_list=None,  # type: ignore
                confidence=0.5,
                timestamp=ts,
                contributing_roles=[],
                rationale="",
            )

    def test_published_strategy_from_json(self):
        """Test PublishedStrategy.from_json creates instance from dict."""
        ts = time.time()
        data = {
            "engagement_id": "eng-json",
            "objectives": ["obj1", "obj2"],
            "priorities": ["pri1"],
            "recommended_techniques": [{"technique_id": "T1046", "name": "Test", "rationale": "test"}],
            "avoid_list": ["avoid1"],
            "confidence": 0.85,
            "timestamp": ts,
            "contributing_roles": ["strategist"],
            "rationale": "Test rationale",
        }
        
        strategy = PublishedStrategy.from_json(data)
        
        assert strategy.engagement_id == "eng-json"
        assert strategy.objectives == ["obj1", "obj2"]
        assert strategy.priorities == ["pri1"]
        assert strategy.confidence == 0.85
        assert strategy.timestamp == ts
        assert strategy.rationale == "Test rationale"

    def test_published_strategy_from_json_missing_field(self):
        """Test PublishedStrategy.from_json raises KeyError for missing fields."""
        data = {
            "engagement_id": "eng-missing",
            # Missing other required fields
        }
        
        with pytest.raises(KeyError):
            PublishedStrategy.from_json(data)

    def test_published_strategy_roundtrip_json(self):
        """Test PublishedStrategy to_json and from_json roundtrip."""
        ts = time.time()
        original = PublishedStrategy(
            engagement_id="eng-roundtrip",
            objectives=["objective1"],
            priorities=["priority1"],
            recommended_techniques=[{"technique_id": "T1046", "name": "Test", "rationale": "r"}],
            avoid_list=["avoid1"],
            confidence=0.75,
            timestamp=ts,
            contributing_roles=["analyst"],
            rationale="Roundtrip test",
        )
        
        json_data = original.to_json()
        restored = PublishedStrategy.from_json(json_data)
        
        assert restored == original


class TestStrategyPublisher:
    """Tests for StrategyPublisher class."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.fixture
    def sample_synthesized_strategy(self):
        """Create sample SynthesizedStrategy for testing."""
        from cyberred.llm.ensemble import ATTCKRecommendation

        return SynthesizedStrategy(
            objectives=["Enumerate network", "Find open ports"],
            actions=["nmap scan", "service detection"],
            rationale="Initial reconnaissance phase",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST, DirectorRole.CREATIVE],
            avoid_list=["192.168.1.254"],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1046",
                    technique_name="Network Service Discovery",
                    rationale="Standard recon",
                    phase="discovery",
                )
            ],
            degradation_level=DegradationLevel.FULL,
        )

    def test_strategy_publisher_initialization(self, mock_event_bus):
        """Test StrategyPublisher initializes correctly."""
        

        publisher = StrategyPublisher(event_bus=mock_event_bus)
        assert publisher._event_bus is mock_event_bus

    def test_strategy_publisher_custom_confidence_threshold(self, mock_event_bus):
        """Test StrategyPublisher accepts custom confidence threshold."""
        

        publisher = StrategyPublisher(
            event_bus=mock_event_bus,
            confidence_threshold=0.9,
        )
        assert publisher._confidence_threshold == 0.9

    @pytest.mark.asyncio
    async def test_publish_strategy_success(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test successful strategy publication."""
        

        publisher = StrategyPublisher(event_bus=mock_event_bus)

        result = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id="eng-pub-001",
        )

        assert result is not None
        assert result.engagement_id == "eng-pub-001"

        # Verify EventBus.publish was called with correct channel
        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        assert call_args[0][0] == "strategies:eng-pub-001"

        # Verify message structure
        message = call_args[0][1]
        assert message["engagement_id"] == "eng-pub-001"
        assert message["objectives"] == ["Enumerate network", "Find open ports"]

    @pytest.mark.asyncio
    async def test_publish_strategy_below_threshold(self, mock_event_bus):
        """Test strategy not published when below confidence threshold."""
        

        low_confidence_strategy = SynthesizedStrategy(
            objectives=["Low confidence action"],
            actions=["action"],
            rationale="Low confidence",
            confidence=0.3,  # Below default threshold
            contributing_roles=[DirectorRole.STRATEGIST],
            degradation_level=DegradationLevel.DEGRADED_SINGLE,
        )

        publisher = StrategyPublisher(
            event_bus=mock_event_bus,
            confidence_threshold=0.5,
        )

        result = await publisher.publish_strategy(
            synthesized=low_confidence_strategy,
            engagement_id="eng-low",
        )

        assert result is None
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_strategy_handles_error_gracefully(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test StrategyPublisher handles publication errors gracefully."""
        

        mock_event_bus.publish = AsyncMock(side_effect=Exception("Redis error"))

        publisher = StrategyPublisher(event_bus=mock_event_bus)

        # Should not raise, but return None and log error
        result = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id="eng-err",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_publish_strategy_includes_all_fields(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test published strategy includes all required fields per AC 3,4."""
        

        publisher = StrategyPublisher(event_bus=mock_event_bus)

        await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id="eng-fields",
        )

        message = mock_event_bus.publish.call_args[0][1]

        # AC 3: objectives, priorities, recommended techniques
        assert "objectives" in message
        assert "priorities" in message
        assert "recommended_techniques" in message

        # AC 4: avoid list
        assert "avoid_list" in message
        assert message["avoid_list"] == ["192.168.1.254"]

        # Other required fields
        assert "confidence" in message
        assert "timestamp" in message
        assert "contributing_roles" in message
        assert "rationale" in message

    @pytest.mark.asyncio
    async def test_publish_strategy_logging(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test StrategyPublisher logs publication events."""
        

        publisher = StrategyPublisher(event_bus=mock_event_bus)

        with patch.object(publisher, "_log") as mock_log:
            await publisher.publish_strategy(
                synthesized=sample_synthesized_strategy,
                engagement_id="eng-log",
            )

            # Verify logging was called
            mock_log.info.assert_called()


class TestAgentStrategySubscription:
    """Tests for agent strategy subscription and decision_context update."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus for agent."""
        bus = MagicMock()
        bus.subscribe = AsyncMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_agent_receives_published_strategy_updates_decision_context(self, mock_event_bus):
        """Test agent updates decision_context when receiving PublishedStrategy (AC 5)."""
        
        

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id="agent-001",
            engagement_id="eng-ctx",
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
        )

        # Simulate PublishedStrategy message (Story 8.10 format)
        strategy_data = {
            "id": "pub-strategy-001",
            "engagement_id": "eng-ctx",
            "objectives": ["Objective 1"],
            "priorities": ["target1"],
            "recommended_techniques": [{"technique_id": "T1046", "name": "Network Discovery", "rationale": "test"}],
            "avoid_list": ["avoid1"],
            "confidence": 0.8,
            "timestamp": time.time(),
            "contributing_roles": ["strategist", "analyst"],
            "rationale": "Test rationale for strategy",
        }

        # Call handler directly
        await agent._handle_strategy_update(strategy_data)

        # Verify strategy was stored
        assert agent._active_strategy is not None
        assert agent._active_strategy.id == "pub-strategy-001"
        
        # Verify decision context was updated
        context = agent.get_decision_context()
        assert "pub-strategy-001" in context

    @pytest.mark.asyncio
    async def test_agent_subscribes_to_strategy_channel(self, mock_event_bus):
        """Test agent subscribes to strategies:{engagement_id} channel."""
        
        

        agent = StigmergicAgent(
            agent_name="test-sub",
            agent_id="agent-sub",
            engagement_id="eng-sub",
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
        )

        await agent._setup_subscriptions()

        # Verify subscription to strategy channel
        subscribe_calls = mock_event_bus.subscribe.call_args_list
        channels = [call[0][0] for call in subscribe_calls]
        assert "strategies:eng-sub" in channels

    @pytest.mark.asyncio
    async def test_agent_strategy_callback_on_published_strategy(self, mock_event_bus):
        """Test agent strategy callback is triggered on PublishedStrategy message receive."""
        
        

        agent = StigmergicAgent(
            agent_name="test-cb",
            agent_id="agent-cb",
            engagement_id="eng-cb",
            event_bus=mock_event_bus,
            role=AgentRole.POSTEX,
        )

        # Create valid PublishedStrategy message (Story 8.10 format)
        strategy_json = json.dumps({
            "id": "pub-strat-cb-001",
            "engagement_id": "eng-cb",
            "objectives": ["Test objective"],
            "priorities": ["action1"],
            "recommended_techniques": [{"technique_id": "T1078", "name": "Valid Accounts", "rationale": "test"}],
            "avoid_list": ["avoid-target"],
            "confidence": 0.7,
            "timestamp": time.time(),
            "contributing_roles": ["strategist"],
            "rationale": "Strategy rationale",
        })

        # Simulate message handling
        await agent._handle_message("strategies:eng-cb", strategy_json)

        # Verify strategy was processed
        assert agent._active_strategy is not None
        assert agent._active_strategy.id == "pub-strat-cb-001"
        assert agent._active_strategy.objectives == ["Test objective"]
        assert agent._active_strategy.avoid_targets == ["avoid-target"]
