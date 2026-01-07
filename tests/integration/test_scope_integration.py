"""Integration tests for Scope Validator.

Verifies the integration of ScopeValidator within the tool execution workflow,
simulating the interactions defined in the architecture.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import yaml
import tempfile

from cyberred.tools.scope import ScopeValidator, ScopeConfig
from cyberred.core.exceptions import ScopeViolationError

class MockToolExecutor:
    """Simulated Tool Executor (e.g. KaliExecutor) to verify integration."""
    
    def __init__(self, scope_validator: ScopeValidator):
        self.scope_validator = scope_validator
        self.execution_log = []

    def execute(self, command: str) -> str:
        """Execute a tool command, enforcing scope validation first."""
        # 1. Verification of AC #3: validate() called BEFORE execution
        self.scope_validator.validate(command=command)
        
        # 2. Simulate execution
        self.execution_log.append(command)
        return f"Executed: {command}"

class TestScopeIntegration:
    """Integration tests for Scope Validator workflow."""

    def test_end_to_end_workflow_with_yaml_config(self):
        """Verify full workflow: Load Config -> Init Validator -> Validate Commands."""
        # 1. Create a temporary YAML config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            yaml.dump({
                "scope": {
                    "allowed_targets": ["192.168.1.0/24", "example.com"],
                    "allowed_ports": [80, 443],
                    "allowed_protocols": ["tcp"],
                    "allow_private": True
                }
            }, tmp)
            config_path = tmp.name

        try:
            # 2. Load validator from file
            validator = ScopeValidator.from_file(config_path)
            
            # 3. Create simulated executor
            executor = MockToolExecutor(validator)
            
            # 4. Verify in-scope command succeeds
            result = executor.execute("nmap -p 80 192.168.1.100")
            assert "Executed" in result
            assert "nmap -p 80 192.168.1.100" in executor.execution_log
            
            # 5. Verify out-of-scope command is blocked
            with pytest.raises(ScopeViolationError) as exc:
                executor.execute("nmap 10.0.0.1")
            
            assert "not in allowed networks" in str(exc.value)
            # Ensure NOT executed
            assert "nmap 10.0.0.1" not in executor.execution_log

        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_executor_enforces_hard_gate(self):
        """Verify that the executor cannot bypass the hard gate."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True
        })
        executor = MockToolExecutor(validator)
        
        # Verify injection attempt is blocked before execution
        with pytest.raises(ScopeViolationError):
            executor.execute("nmap 192.168.1.1; rm -rf /")
            
        # Verify valid command passes
        executor.execute("nmap 192.168.1.5")
        assert len(executor.execution_log) == 1

    def test_audit_logging_integration(self):
        """Verify that validation events are correctly logged to the audit system."""
        validator = ScopeValidator.from_config({
             "allowed_targets": ["192.168.1.0/24"],
             "allow_private": True
        })
        
        with patch("cyberred.tools.scope.log") as mock_log:
            validator.validate(target="192.168.1.1")
            
            # Verify structured logging call
            mock_log.info.assert_called()
            call_kwargs = mock_log.info.call_args[1]
            assert call_kwargs["target"] == "192.168.1.1"
            assert call_kwargs["decision"] == "ALLOW"
            
            # Verify DENY logging
            with pytest.raises(ScopeViolationError):
                validator.validate(target="10.0.0.1")
                
            args, kwargs = mock_log.info.call_args
            assert kwargs["decision"] == "DENY"
            assert kwargs["reason"] == "IP not in allowed networks"

