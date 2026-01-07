import pytest
from unittest.mock import Mock, AsyncMock
from cyberred.daemon.preflight import (
    CheckStatus,
    CheckPriority,
    CheckResult,
    PreFlightCheck,
)
from cyberred.core.exceptions import PreFlightCheckError, PreFlightWarningError

class MockPassCheck(PreFlightCheck):
    @property
    def name(self): return "PASS_CHECK"
    @property
    def priority(self): return CheckPriority.P0
    async def execute(self, config):
        return CheckResult(self.name, CheckStatus.PASS, self.priority, "OK")

class MockFailP0Check(PreFlightCheck):
    @property
    def name(self): return "FAIL_P0"
    @property
    def priority(self): return CheckPriority.P0
    async def execute(self, config):
        return CheckResult(self.name, CheckStatus.FAIL, self.priority, "Failed")

class MockFailP1Check(PreFlightCheck):
    @property
    def name(self): return "FAIL_P1"
    @property
    def priority(self): return CheckPriority.P1
    async def execute(self, config):
        return CheckResult(self.name, CheckStatus.WARN, self.priority, "Warning")

@pytest.mark.asyncio
async def test_runner_execution_and_sorting():
    from cyberred.daemon.preflight import PreFlightRunner
    
    # Use DI constructor to inject mock checks
    runner = PreFlightRunner(checks=[MockFailP1Check(), MockPassCheck()])
    
    # Execute
    results = await runner.run_all({})
    
    # Verify sorting (P0 first) - Output order 
    # Architecture says run in sequence P0..P1
    # Check that results contain both and are sorted by priority
    assert len(results) == 2
    assert results[0].priority == "P0"  # P0 checks run first
    assert results[1].priority == "P1"

@pytest.mark.asyncio
async def test_validate_success():
    from cyberred.daemon.preflight import PreFlightRunner
    runner = PreFlightRunner()
    results = [
        CheckResult("C1", CheckStatus.PASS, CheckPriority.P0, "OK")
    ]
    # Should not raise
    runner.validate_results(results)

@pytest.mark.asyncio
async def test_validate_p0_fail():
    from cyberred.daemon.preflight import PreFlightRunner
    runner = PreFlightRunner()
    results = [
        CheckResult("C1", CheckStatus.FAIL, CheckPriority.P0, "Failed")
    ]
    with pytest.raises(PreFlightCheckError):
        runner.validate_results(results)

@pytest.mark.asyncio
async def test_validate_p1_warn():
    from cyberred.daemon.preflight import PreFlightRunner
    runner = PreFlightRunner()
    results = [
        CheckResult("C1", CheckStatus.WARN, CheckPriority.P1, "Warn")
    ]
    # Without ignore_warnings=True (default), should raise Warning
    with pytest.raises(PreFlightWarningError):
        runner.validate_results(results, ignore_warnings=False)

@pytest.mark.asyncio
async def test_validate_p1_ignore():
    from cyberred.daemon.preflight import PreFlightRunner
    runner = PreFlightRunner()
    results = [
        CheckResult("C1", CheckStatus.WARN, CheckPriority.P1, "Warn")
    ]
    # With ignore_warnings=True, should not raise
    runner.validate_results(results, ignore_warnings=True)
