"""Unit tests for engagement statistics aggregation.

Story 13.12: Engagement Summary Statistics
Tests verify AC#5: Unit tests verify statistic accuracy
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import asdict

from cyberred.storage.statistics import (
    EngagementStatistics,
    EngagementStatisticsAggregator,
)
from cyberred.daemon.state_machine import EngagementState
from cyberred.core.exceptions import EngagementNotFoundError


class TestEngagementStatisticsDataclass:
    """Test EngagementStatistics dataclass serialization and validation.
    
    AC#1: Summary includes duration, agent count, finding count by severity
    AC#2: Summary includes coverage %, tools executed, LLM calls
    AC#3: Summary includes emergence score (if calculated)
    """

    def test_complete_statistics_creation(self):
        """Test creating EngagementStatistics with all fields.
        
        GIVEN: Complete engagement statistics data
        WHEN: Creating EngagementStatistics instance
        THEN: All fields are properly initialized
        """
        # GIVEN: Complete statistics data
        stats = EngagementStatistics(
            engagement_id="eng-test-123",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-01T01:30:00Z",
            duration_seconds=5400,  # 1.5 hours
            total_agents_spawned=100,
            active_agents=25,
            idle_agents=70,
            error_agents=5,
            max_concurrent_agents=50,
            findings_critical=3,
            findings_high=8,
            findings_medium=15,
            findings_low=25,
            total_findings=51,
            coverage_percent=85.5,
            tools_executed=200,
            successful_tools=185,
            failed_tools=15,
            llm_calls=750,
            llm_tokens_input=75000,
            llm_tokens_output=37500,
            emergence_score=0.28,
            emergence_threshold_met=True,
            engagement_state="completed",
            operator="alice",
        )

        # THEN: All fields are accessible
        assert stats.engagement_id == "eng-test-123"
        assert stats.duration_seconds == 5400
        assert stats.total_agents_spawned == 100
        assert stats.findings_critical == 3
        assert stats.total_findings == 51
        assert stats.coverage_percent == 85.5
        assert stats.tools_executed == 200
        assert stats.llm_calls == 750
        assert stats.emergence_score == 0.28
        assert stats.emergence_threshold_met is True
        assert stats.engagement_state == "completed"

    def test_statistics_without_emergence(self):
        """Test creating statistics when emergence score not available.
        
        GIVEN: Statistics data without emergence score
        WHEN: Creating EngagementStatistics instance
        THEN: Emergence fields are None/False
        """
        # GIVEN: No emergence data
        stats = EngagementStatistics(
            engagement_id="eng-test-456",
            start_time="2026-01-01T00:00:00Z",
            end_time=None,  # Still running
            duration_seconds=3600,
            total_agents_spawned=50,
            active_agents=50,
            idle_agents=0,
            error_agents=0,
            max_concurrent_agents=50,
            findings_critical=0,
            findings_high=2,
            findings_medium=5,
            findings_low=10,
            total_findings=17,
            coverage_percent=45.0,
            tools_executed=100,
            successful_tools=98,
            failed_tools=2,
            llm_calls=300,
            llm_tokens_input=30000,
            llm_tokens_output=15000,
            emergence_score=None,  # Not calculated yet
            emergence_threshold_met=False,
            engagement_state="running",
            operator="bob",
        )

        # THEN: Emergence fields are None/False
        assert stats.emergence_score is None
        assert stats.emergence_threshold_met is False
        assert stats.end_time is None  # Still running
        assert stats.engagement_state == "running"

    def test_to_dict_serialization(self):
        """Test EngagementStatistics.to_dict() serialization.
        
        GIVEN: EngagementStatistics instance
        WHEN: Calling to_dict()
        THEN: Returns properly structured dictionary
        """
        # GIVEN: Statistics instance
        stats = EngagementStatistics(
            engagement_id="eng-serialize",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-01T02:00:00Z",
            duration_seconds=7200,
            total_agents_spawned=75,
            active_agents=0,
            idle_agents=0,
            error_agents=0,
            max_concurrent_agents=40,
            findings_critical=5,
            findings_high=10,
            findings_medium=20,
            findings_low=30,
            total_findings=65,
            coverage_percent=92.3,
            tools_executed=150,
            successful_tools=145,
            failed_tools=5,
            llm_calls=500,
            llm_tokens_input=50000,
            llm_tokens_output=25000,
            emergence_score=0.35,
            emergence_threshold_met=True,
            engagement_state="completed",
            operator="charlie",
        )

        # WHEN: Converting to dict
        data = stats.to_dict()

        # THEN: Structure is correct
        assert data["engagement_id"] == "eng-serialize"
        assert data["duration_seconds"] == 7200
        assert data["findings"]["critical"] == 5
        assert data["findings"]["high"] == 10
        assert data["findings"]["total"] == 65
        assert data["tools"]["executed"] == 150
        assert data["tools"]["successful"] == 145
        assert data["llm"]["calls"] == 500
        assert data["llm"]["tokens_input"] == 50000
        assert data["emergence"]["score"] == 0.35
        assert data["emergence"]["threshold_met"] is True
        assert data["engagement_state"] == "completed"

    def test_to_dict_without_emergence(self):
        """Test to_dict() when emergence is None.
        
        GIVEN: Statistics without emergence score
        WHEN: Calling to_dict()
        THEN: Emergence field is None
        """
        # GIVEN: No emergence
        stats = EngagementStatistics(
            engagement_id="eng-no-emerge",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-01T01:00:00Z",
            duration_seconds=3600,
            total_agents_spawned=25,
            active_agents=0,
            idle_agents=0,
            error_agents=0,
            max_concurrent_agents=25,
            findings_critical=1,
            findings_high=2,
            findings_medium=3,
            findings_low=4,
            total_findings=10,
            coverage_percent=50.0,
            tools_executed=50,
            successful_tools=48,
            failed_tools=2,
            llm_calls=100,
            llm_tokens_input=10000,
            llm_tokens_output=5000,
            emergence_score=None,
            emergence_threshold_met=False,
            engagement_state="completed",
            operator="dana",
        )

        # WHEN: Converting to dict
        data = stats.to_dict()

        # THEN: Emergence is None
        assert data["emergence"] is None

    def test_from_dict_deserialization(self):
        """Test EngagementStatistics.from_dict() deserialization.
        
        GIVEN: Statistics dictionary
        WHEN: Calling from_dict()
        THEN: Returns properly initialized EngagementStatistics
        """
        # GIVEN: Dictionary data
        data = {
            "engagement_id": "eng-deserialize",
            "start_time": "2026-01-01T00:00:00Z",
            "end_time": "2026-01-01T03:00:00Z",
            "duration_seconds": 10800,
            "total_agents_spawned": 120,
            "active_agents": 0,
            "idle_agents": 0,
            "error_agents": 0,
            "max_concurrent_agents": 60,
            "findings": {
                "critical": 7,
                "high": 14,
                "medium": 28,
                "low": 35,
                "total": 84,
            },
            "coverage_percent": 95.7,
            "tools": {
                "executed": 250,
                "successful": 240,
                "failed": 10,
            },
            "llm": {
                "calls": 1000,
                "tokens_input": 100000,
                "tokens_output": 50000,
            },
            "emergence": {
                "score": 0.42,
                "threshold_met": True,
            },
            "engagement_state": "completed",
            "operator": "eve",
        }

        # WHEN: Deserializing
        stats = EngagementStatistics.from_dict(data)

        # THEN: All fields are correct
        assert stats.engagement_id == "eng-deserialize"
        assert stats.duration_seconds == 10800
        assert stats.findings_critical == 7
        assert stats.findings_high == 14
        assert stats.total_findings == 84
        assert stats.tools_executed == 250
        assert stats.successful_tools == 240
        assert stats.llm_calls == 1000
        assert stats.llm_tokens_input == 100000
        assert stats.emergence_score == 0.42
        assert stats.emergence_threshold_met is True
        assert stats.operator == "eve"

    def test_roundtrip_serialization(self):
        """Test to_dict() → from_dict() roundtrip.
        
        GIVEN: EngagementStatistics instance
        WHEN: Converting to_dict() then from_dict()
        THEN: Restored instance matches original
        """
        # GIVEN: Original statistics
        original = EngagementStatistics(
            engagement_id="eng-roundtrip",
            start_time="2026-01-01T00:00:00Z",
            end_time="2026-01-01T01:00:00Z",
            duration_seconds=3600,
            total_agents_spawned=50,
            active_agents=10,
            idle_agents=35,
            error_agents=5,
            max_concurrent_agents=30,
            findings_critical=2,
            findings_high=4,
            findings_medium=8,
            findings_low=16,
            total_findings=30,
            coverage_percent=75.0,
            tools_executed=100,
            successful_tools=95,
            failed_tools=5,
            llm_calls=400,
            llm_tokens_input=40000,
            llm_tokens_output=20000,
            emergence_score=0.25,
            emergence_threshold_met=True,
            engagement_state="completed",
            operator="frank",
        )

        # WHEN: Roundtrip
        data = original.to_dict()
        restored = EngagementStatistics.from_dict(data)

        # THEN: All fields match
        assert restored.engagement_id == original.engagement_id
        assert restored.duration_seconds == original.duration_seconds
        assert restored.total_agents_spawned == original.total_agents_spawned
        assert restored.findings_critical == original.findings_critical
        assert restored.total_findings == original.total_findings
        assert restored.coverage_percent == original.coverage_percent
        assert restored.tools_executed == original.tools_executed
        assert restored.llm_calls == original.llm_calls
        assert restored.emergence_score == original.emergence_score
        assert restored.operator == original.operator


class TestEngagementStatisticsAggregator:
    """Test EngagementStatisticsAggregator metric collection.
    
    AC#1: Summary includes duration, agent count, finding count by severity
    AC#2: Summary includes coverage %, tools executed, LLM calls
    AC#3: Summary includes emergence score (if calculated)
    AC#5: Unit tests verify statistic accuracy
    """

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for aggregator."""
        session_manager = Mock()
        checkpoint_manager = Mock()
        llm_gateway = Mock()
        event_bus = Mock()
        
        return {
            "session_manager": session_manager,
            "checkpoint_manager": checkpoint_manager,
            "llm_gateway": llm_gateway,
            "event_bus": event_bus,
        }

    @pytest.fixture
    def aggregator(self, mock_dependencies):
        """Create EngagementStatisticsAggregator with mocks."""
        return EngagementStatisticsAggregator(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_aggregator_collects_all_metrics(self, aggregator, mock_dependencies):
        """Test aggregator collects metrics from all sources.
        
        GIVEN: Engagement with complete metric data
        WHEN: Calling get_statistics()
        THEN: All metrics are collected and aggregated
        """
        # GIVEN: Mock engagement context
        engagement_id = "eng-aggregate"
        start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
        
        context = Mock()
        context.id = engagement_id
        context.state = EngagementState.COMPLETED
        context.created_at = start_time
        context.completed_at = end_time
        context.engagement_config = {"engagement": {"operator": "test-operator"}}
        
        mock_dependencies["session_manager"].get_engagement_or_raise.return_value = context
        
        # Mock metric sources
        aggregator._get_finding_stats = AsyncMock(return_value={
            "findings_critical": 3,
            "findings_high": 7,
            "findings_medium": 12,
            "findings_low": 20,
            "total_findings": 42,
        })
        
        aggregator._get_agent_stats = AsyncMock(return_value={
            "total_agents_spawned": 80,
            "active_agents": 0,
            "idle_agents": 0,
            "error_agents": 0,
            "max_concurrent_agents": 45,
        })
        
        aggregator._get_tool_stats = AsyncMock(return_value={
            "coverage_percent": 88.5,
            "tools_executed": 175,
            "successful_tools": 170,
            "failed_tools": 5,
        })
        
        aggregator._get_llm_stats = AsyncMock(return_value={
            "llm_calls": 600,
            "llm_tokens_input": 60000,
            "llm_tokens_output": 30000,
        })
        
        aggregator._get_emergence_stats = AsyncMock(return_value={
            "emergence_score": 0.32,
            "emergence_threshold_met": True,
        })

        # WHEN: Collecting statistics
        stats = await aggregator.get_statistics(engagement_id)

        # THEN: All metrics are present
        assert stats.engagement_id == engagement_id
        assert stats.duration_seconds == 7200  # 2 hours
        assert stats.total_agents_spawned == 80
        assert stats.findings_critical == 3
        assert stats.total_findings == 42
        assert stats.coverage_percent == 88.5
        assert stats.tools_executed == 175
        assert stats.llm_calls == 600
        assert stats.emergence_score == 0.32
        assert stats.operator == "test-operator"

    @pytest.mark.asyncio
    async def test_aggregator_handles_running_engagement(self, aggregator, mock_dependencies):
        """Test aggregator calculates duration for running engagement.
        
        GIVEN: Engagement in RUNNING state
        WHEN: Calling get_statistics()
        THEN: Duration calculated from start to now, end_time is None
        """
        # GIVEN: Running engagement
        engagement_id = "eng-running"
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        context = Mock()
        context.id = engagement_id
        context.state = EngagementState.RUNNING
        context.created_at = start_time
        context.completed_at = None
        context.engagement_config = {"engagement": {"operator": "live-operator"}}
        
        mock_dependencies["session_manager"].get_engagement_or_raise.return_value = context
        
        # Mock minimal metrics
        aggregator._get_finding_stats = AsyncMock(return_value={
            "findings_critical": 0, "findings_high": 0,
            "findings_medium": 0, "findings_low": 0, "total_findings": 0,
        })
        aggregator._get_agent_stats = AsyncMock(return_value={
            "total_agents_spawned": 10, "active_agents": 10,
            "idle_agents": 0, "error_agents": 0, "max_concurrent_agents": 10,
        })
        aggregator._get_tool_stats = AsyncMock(return_value={
            "coverage_percent": 15.0, "tools_executed": 20,
            "successful_tools": 20, "failed_tools": 0,
        })
        aggregator._get_llm_stats = AsyncMock(return_value={
            "llm_calls": 50, "llm_tokens_input": 5000, "llm_tokens_output": 2500,
        })
        aggregator._get_emergence_stats = AsyncMock(return_value={
            "emergence_score": None, "emergence_threshold_met": False,
        })

        # WHEN: Collecting statistics
        stats = await aggregator.get_statistics(engagement_id)

        # THEN: Duration is calculated, end_time is None
        assert stats.end_time is None
        assert stats.duration_seconds >= 3600  # At least 1 hour
        assert stats.engagement_state == str(EngagementState.RUNNING)

    @pytest.mark.asyncio
    async def test_aggregator_handles_missing_engagement(self, aggregator, mock_dependencies):
        """Test aggregator raises error for missing engagement.
        
        GIVEN: Engagement does not exist
        WHEN: Calling get_statistics()
        THEN: Raises EngagementNotFoundError
        """
        # GIVEN: Missing engagement
        mock_dependencies["session_manager"].get_engagement_or_raise.side_effect = (
            EngagementNotFoundError("eng-missing")
        )

        # WHEN/THEN: Raises error
        with pytest.raises(EngagementNotFoundError):
            await aggregator.get_statistics("eng-missing")

    @pytest.mark.asyncio
    async def test_aggregator_handles_no_emergence_data(self, aggregator, mock_dependencies):
        """Test aggregator handles engagement without emergence calculation.
        
        GIVEN: Engagement without emergence score
        WHEN: Calling get_statistics()
        THEN: Emergence fields are None/False
        """
        # GIVEN: Engagement without emergence
        engagement_id = "eng-no-emerge"
        context = Mock()
        context.id = engagement_id
        context.state = EngagementState.COMPLETED
        context.created_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        context.completed_at = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        context.engagement_config = {"engagement": {"operator": "test"}}
        
        mock_dependencies["session_manager"].get_engagement_or_raise.return_value = context
        
        # Mock metrics with no emergence
        aggregator._get_finding_stats = AsyncMock(return_value={
            "findings_critical": 1, "findings_high": 2,
            "findings_medium": 3, "findings_low": 4, "total_findings": 10,
        })
        aggregator._get_agent_stats = AsyncMock(return_value={
            "total_agents_spawned": 20, "active_agents": 0,
            "idle_agents": 0, "error_agents": 0, "max_concurrent_agents": 15,
        })
        aggregator._get_tool_stats = AsyncMock(return_value={
            "coverage_percent": 60.0, "tools_executed": 50,
            "successful_tools": 48, "failed_tools": 2,
        })
        aggregator._get_llm_stats = AsyncMock(return_value={
            "llm_calls": 100, "llm_tokens_input": 10000, "llm_tokens_output": 5000,
        })
        aggregator._get_emergence_stats = AsyncMock(return_value={
            "emergence_score": None,
            "emergence_threshold_met": False,
        })

        # WHEN: Collecting statistics
        stats = await aggregator.get_statistics(engagement_id)

        # THEN: Emergence is None/False
        assert stats.emergence_score is None
        assert stats.emergence_threshold_met is False
