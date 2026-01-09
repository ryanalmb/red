import pytest
import asyncio
from unittest.mock import Mock
from cyberred.intelligence.aggregator import IntelligenceAggregator
from cyberred.intelligence.base import IntelligenceSource, IntelResult

class MockAgent:
    """Mock agent that consumes intelligence."""
    
    def __init__(self, aggregator):
        self.aggregator = aggregator
        self.decisions = []
        self.errors = []

    async def run_cycle(self, service, version):
        try:
            # Query - expectation: NEVER raises exception
            results = await self.aggregator.query(service, version)
            
            # Decision making
            if not results:
                 self.decisions.append("proceed_with_caution")
            else:
                 self.decisions.append(f"exploit_{len(results)}_vulns")
                 
        except Exception as e:
            self.errors.append(e)
            raise # Re-raise to fail test if it happens

@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continuity_total_failure():
    """Simulate all sources failing, verify agent continues."""
    aggregator = IntelligenceAggregator(timeout=0.1)
    source = Mock(spec=IntelligenceSource)
    source.name = "fail_source"
    source.query.side_effect = Exception("Connection Refused")
    aggregator.add_source(source)
    
    agent = MockAgent(aggregator)
    
    await agent.run_cycle("svc", "1.0")
    
    assert len(agent.errors) == 0
    assert "proceed_with_caution" in agent.decisions

@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continuity_partial_failure():
    """Simulate partial failure, verify agent uses partial results."""
    aggregator = IntelligenceAggregator(timeout=0.1)
    
    # Failing source
    fail_source = Mock(spec=IntelligenceSource)
    fail_source.name = "fail"
    fail_source.query.side_effect = asyncio.TimeoutError()
    
    # Success source
    success_source = Mock(spec=IntelligenceSource)
    success_source.name = "success"
    
    async def success_query(*args):
        return [IntelResult(
            source="success",
            cve_id="CVE-2023-1000",
            severity="high",
            confidence=1.0,
            priority=1,
            exploit_available=True,
            exploit_path=None,
            metadata={}
        )]
    success_source.query = success_query
    
    aggregator.add_source(fail_source)
    aggregator.add_source(success_source)
    
    agent = MockAgent(aggregator)
    
    await agent.run_cycle("svc", "1.0")
    
    assert len(agent.errors) == 0
    assert "exploit_1_vulns" in agent.decisions

@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continuity_invalid_data():
    """Simulate invalid data from source, verify agent continues with valid sources."""
    aggregator = IntelligenceAggregator(timeout=0.1)
    
    # Source returning invalid data (not a list)
    invalid_source = Mock(spec=IntelligenceSource)
    invalid_source.name = "invalid"
    async def invalid_query(*args):
        return "not a list"  # Invalid return type
    invalid_source.query = invalid_query
    
    # Valid source
    valid_source = Mock(spec=IntelligenceSource)
    valid_source.name = "valid"
    async def valid_query(*args):
        return [IntelResult(
            source="valid",
            cve_id="CVE-2023-2000",
            severity="critical",
            confidence=0.95,
            priority=1,
            exploit_available=True,
            exploit_path=None,
            metadata={}
        )]
    valid_source.query = valid_query
    
    aggregator.add_source(invalid_source)
    aggregator.add_source(valid_source)
    
    agent = MockAgent(aggregator)
    
    await agent.run_cycle("svc", "1.0")
    
    assert len(agent.errors) == 0
    assert "exploit_1_vulns" in agent.decisions  # Agent continues with valid source
