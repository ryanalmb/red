"""Integration tests for Strategy Publication to Agents.

Story 8.10: Strategy Publication to Agents.

Tests end-to-end strategy flow: synthesis → publish → agent receive.
Uses real production code with minimal mocking.
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.llm.ensemble import (
    ATTCKRecommendation,
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


class TestEndToEndStrategyFlow:
    """Integration tests for end-to-end strategy publication flow (AC 6)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus that tracks published messages."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        bus._published_messages = []
        
        async def track_publish(channel, message):
            bus._published_messages.append((channel, message))
        
        bus.publish.side_effect = track_publish
        return bus

    @pytest.fixture
    def sample_synthesized_strategy(self):
        """Create sample SynthesizedStrategy from DirectorEnsemble."""
        return SynthesizedStrategy(
            objectives=["Enumerate network services", "Identify vulnerabilities"],
            actions=["Run nmap scan", "Execute nuclei templates"],
            rationale="Multi-model strategic analysis identified high-value targets",
            confidence=0.85,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST, DirectorRole.CREATIVE],
            avoid_list=["192.168.1.254", "10.0.0.1/24"],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1046",
                    technique_name="Network Service Discovery",
                    rationale="Initial reconnaissance phase",
                    phase="discovery",
                ),
                ATTCKRecommendation(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    rationale="Web application vulnerabilities detected",
                    phase="initial-access",
                ),
            ],
            degradation_level=DegradationLevel.FULL,
        )

    @pytest.mark.asyncio
    async def test_synthesis_to_publish_to_receive_flow(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test end-to-end: synthesis → publish → receive (AC 6.1)."""
        engagement_id = "eng-e2e-001"
        
        # Step 1: Publish strategy via StrategyPublisher
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        published = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id=engagement_id,
        )
        
        assert published is not None
        assert published.engagement_id == engagement_id
        
        # Step 2: Verify message was published to correct channel
        assert len(mock_event_bus._published_messages) == 1
        channel, message = mock_event_bus._published_messages[0]
        assert channel == f"strategies:{engagement_id}"
        
        # Step 3: Create agent and simulate receiving the message
        agent = StigmergicAgent(
            agent_name="recon-agent",
            agent_id="agent-e2e-001",
            engagement_id=engagement_id,
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
        )
        
        # Simulate agent receiving the published message
        await agent._handle_strategy_update(message)
        
        # Step 4: Verify agent processed the strategy
        assert agent._active_strategy is not None
        assert agent._active_strategy.objectives == ["Enumerate network services", "Identify vulnerabilities"]
        assert agent._active_strategy.avoid_targets == ["192.168.1.254", "10.0.0.1/24"]
        
        # Verify decision context was updated (AC 5)
        context = agent.get_decision_context()
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_multiple_agents_receive_same_strategy(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test multiple agents receiving same strategy (AC 6.2)."""
        engagement_id = "eng-multi-001"
        
        # Publish strategy
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        published = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id=engagement_id,
        )
        
        # Get published message
        channel, message = mock_event_bus._published_messages[0]
        
        # Create multiple agents
        agents = []
        for i, role in enumerate([AgentRole.RECON, AgentRole.EXPLOIT, AgentRole.POSTEX]):
            agent = StigmergicAgent(
                agent_name=f"agent-{role.value}",
                agent_id=f"agent-multi-{i}",
                engagement_id=engagement_id,
                event_bus=mock_event_bus,
                role=role,
            )
            agents.append(agent)
        
        # Simulate all agents receiving the strategy
        for agent in agents:
            await agent._handle_strategy_update(message)
        
        # Verify all agents received and processed the strategy
        for agent in agents:
            assert agent._active_strategy is not None
            assert agent._active_strategy.objectives == sample_synthesized_strategy.objectives
            assert len(agent.get_decision_context()) > 0

    @pytest.mark.asyncio
    async def test_strategy_update_propagation_timing(
        self, mock_event_bus, sample_synthesized_strategy
    ):
        """Test strategy update propagation timing (AC 6.3)."""
        engagement_id = "eng-timing-001"
        
        # Publish strategy and measure timing
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        
        start_time = time.monotonic()
        published = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id=engagement_id,
        )
        publish_time = time.monotonic() - start_time
        
        # Create agent
        agent = StigmergicAgent(
            agent_name="timing-agent",
            agent_id="agent-timing-001",
            engagement_id=engagement_id,
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
        )
        
        # Measure agent processing time
        channel, message = mock_event_bus._published_messages[0]
        
        start_time = time.monotonic()
        await agent._handle_strategy_update(message)
        receive_time = time.monotonic() - start_time
        
        # Verify both operations complete quickly (non-blocking)
        assert publish_time < 1.0, f"Publication took {publish_time}s, expected < 1s"
        assert receive_time < 1.0, f"Reception took {receive_time}s, expected < 1s"
        
        # Verify strategy was received
        assert agent._active_strategy is not None

    @pytest.mark.asyncio
    async def test_graceful_handling_of_redis_unavailability(self, sample_synthesized_strategy):
        """Test graceful handling of Redis unavailability (AC 6.4)."""
        # Create EventBus that simulates Redis failure
        failing_bus = MagicMock()
        failing_bus.publish = AsyncMock(side_effect=Exception("Redis connection refused"))
        
        publisher = StrategyPublisher(event_bus=failing_bus)
        
        # Should not raise, but return None
        result = await publisher.publish_strategy(
            synthesized=sample_synthesized_strategy,
            engagement_id="eng-fail-001",
        )
        
        assert result is None  # Graceful failure
        failing_bus.publish.assert_called_once()  # Attempted to publish


class TestStrategyMessageFormat:
    """Tests for strategy message format verification (AC 3, 4)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_published_strategy_includes_objectives(self, mock_event_bus):
        """Test published strategy includes objectives (AC 3)."""
        strategy = SynthesizedStrategy(
            objectives=["Objective A", "Objective B", "Objective C"],
            actions=["Action 1"],
            rationale="Test",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST],
            degradation_level=DegradationLevel.FULL,
        )
        
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        await publisher.publish_strategy(strategy, "eng-obj-001")
        
        message = mock_event_bus.publish.call_args[0][1]
        assert "objectives" in message
        assert message["objectives"] == ["Objective A", "Objective B", "Objective C"]

    @pytest.mark.asyncio
    async def test_published_strategy_includes_priorities(self, mock_event_bus):
        """Test published strategy includes priorities (AC 3)."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Priority 1", "Priority 2"],  # Actions become priorities
            rationale="Test",
            confidence=0.8,
            contributing_roles=[DirectorRole.ANALYST],
            degradation_level=DegradationLevel.FULL,
        )
        
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        await publisher.publish_strategy(strategy, "eng-pri-001")
        
        message = mock_event_bus.publish.call_args[0][1]
        assert "priorities" in message
        assert message["priorities"] == ["Priority 1", "Priority 2"]

    @pytest.mark.asyncio
    async def test_published_strategy_includes_recommended_techniques(self, mock_event_bus):
        """Test published strategy includes recommended techniques (AC 3)."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Action"],
            rationale="Test",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1046",
                    technique_name="Network Service Discovery",
                    rationale="Test rationale",
                    phase="discovery",
                )
            ],
            degradation_level=DegradationLevel.FULL,
        )
        
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        await publisher.publish_strategy(strategy, "eng-tech-001")
        
        message = mock_event_bus.publish.call_args[0][1]
        assert "recommended_techniques" in message
        assert len(message["recommended_techniques"]) == 1
        assert message["recommended_techniques"][0]["technique_id"] == "T1046"

    @pytest.mark.asyncio
    async def test_published_strategy_includes_avoid_list(self, mock_event_bus):
        """Test published strategy includes avoid list (AC 4)."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Action"],
            rationale="Test",
            confidence=0.8,
            contributing_roles=[DirectorRole.ANALYST],
            avoid_list=["target-to-skip", "failed-approach-1"],
            degradation_level=DegradationLevel.FULL,
        )
        
        publisher = StrategyPublisher(event_bus=mock_event_bus)
        await publisher.publish_strategy(strategy, "eng-avoid-001")
        
        message = mock_event_bus.publish.call_args[0][1]
        assert "avoid_list" in message
        assert message["avoid_list"] == ["target-to-skip", "failed-approach-1"]


class TestAgentStrategyIncorporation:
    """Tests for agent strategy incorporation into decision_context (AC 5)."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_agent_incorporates_strategy_in_decision_context(self, mock_event_bus):
        """Test agent incorporates strategy in decision_context (AC 5)."""
        agent = StigmergicAgent(
            agent_name="ctx-agent",
            agent_id="agent-ctx-001",
            engagement_id="eng-ctx-001",
            event_bus=mock_event_bus,
            role=AgentRole.WEBAPP,
        )
        
        # Simulate receiving PublishedStrategy
        strategy_message = {
            "id": "strat-ctx-001",
            "engagement_id": "eng-ctx-001",
            "objectives": ["Test objective"],
            "priorities": ["priority1"],
            "recommended_techniques": [{"technique_id": "T1190", "name": "Exploit App", "rationale": "test"}],
            "avoid_list": ["avoid-this"],
            "confidence": 0.9,
            "timestamp": time.time(),
            "contributing_roles": ["strategist", "analyst", "creative"],
            "rationale": "Strategy rationale",
        }
        
        await agent._handle_strategy_update(strategy_message)
        
        # Verify decision_context includes strategy ID
        context = agent.get_decision_context()
        assert "strat-ctx-001" in context
        
        # Verify strategy is accessible
        assert agent._active_strategy is not None
        assert agent._active_strategy.id == "strat-ctx-001"

    @pytest.mark.asyncio
    async def test_agent_extracts_technique_ids_from_recommendations(self, mock_event_bus):
        """Test agent extracts technique IDs from recommended_techniques."""
        agent = StigmergicAgent(
            agent_name="tech-agent",
            agent_id="agent-tech-001",
            engagement_id="eng-tech-001",
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
        )
        
        strategy_message = {
            "id": "strat-tech-001",
            "engagement_id": "eng-tech-001",
            "objectives": ["Exploit"],
            "priorities": [],
            "recommended_techniques": [
                {"technique_id": "T1110", "name": "Brute Force", "rationale": "weak creds"},
                {"technique_id": "T1078", "name": "Valid Accounts", "rationale": "reuse"},
            ],
            "avoid_list": [],
            "confidence": 0.75,
            "timestamp": time.time(),
            "contributing_roles": ["strategist"],
            "rationale": "Focus on credential attacks",
        }
        
        await agent._handle_strategy_update(strategy_message)
        
        # Verify techniques are extracted
        assert agent._active_strategy.recommended_techniques == ["T1110", "T1078"]
