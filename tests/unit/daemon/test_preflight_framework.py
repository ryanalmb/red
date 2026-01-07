import pytest
from enum import StrEnum
from dataclasses import dataclass
from abc import ABC, abstractmethod

def test_preflight_framework_structure():
    """Test that preflight framework components exist and follow spec."""
    from cyberred.daemon.preflight import (
        CheckStatus,
        CheckPriority,
        CheckResult,
        PreFlightCheck
    )
    
    # Verify Enums
    assert isinstance(CheckStatus.PASS, StrEnum)
    assert CheckStatus.PASS == "PASS"
    assert CheckStatus.WARN == "WARN"
    assert CheckStatus.FAIL == "FAIL"
    
    assert isinstance(CheckPriority.P0, StrEnum)
    assert CheckPriority.P0 == "P0"
    assert CheckPriority.P1 == "P1"
    
    # Verify Dataclass
    result = CheckResult(
        name="TEST_CHECK",
        status=CheckStatus.PASS,
        message="All good",
        details={"foo": "bar"},
        priority=CheckPriority.P0
    )
    assert result.name == "TEST_CHECK"
    assert result.status == "PASS"
    assert result.priority == "P0"
    
    # Verify Abstract Base Class
    assert issubclass(PreFlightCheck, ABC)
    assert hasattr(PreFlightCheck, "execute")
    assert getattr(PreFlightCheck.execute, "__isabstractmethod__", False)

@pytest.mark.asyncio
async def test_preflight_check_base_coverage():
    """Call base class methods via super() to ensure 100% coverage of the ABC."""
    from cyberred.daemon.preflight import PreFlightCheck, CheckPriority, CheckResult, CheckStatus
    
    class ConcreteCheck(PreFlightCheck):
        @property
        def name(self) -> str:
            return super().name
            
        @property
        def priority(self) -> CheckPriority:
            return super().priority
            
        async def execute(self, config: dict) -> CheckResult:
            await super().execute(config)
            return CheckResult("TEST", CheckStatus.PASS, self.priority, "OK")

    check = ConcreteCheck()
    # These will return None (from pass) but will hit the lines in preflight.py
    assert check.name is None
    assert check.priority is None
    await check.execute({})
