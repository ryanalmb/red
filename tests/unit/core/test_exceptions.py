"""Unit tests for cyberred.core.exceptions module.

Tests the exception hierarchy:
- CyberRedError (base)
- ScopeViolationError
- KillSwitchTriggered
- ConfigurationError
- CheckpointIntegrityError
"""

import json
import pytest


class TestCyberRedError:
    """Tests for the base CyberRedError exception."""

    def test_inherits_from_exception(self):
        """CyberRedError should inherit from Exception."""
        from cyberred.core.exceptions import CyberRedError

        assert issubclass(CyberRedError, Exception)

    def test_can_be_raised_and_caught(self):
        """CyberRedError can be raised and caught."""
        from cyberred.core.exceptions import CyberRedError

        with pytest.raises(CyberRedError):
            raise CyberRedError("Test error")

    def test_has_meaningful_default_message(self):
        """CyberRedError has a meaningful message when raised without args."""
        from cyberred.core.exceptions import CyberRedError

        error = CyberRedError()
        assert str(error) != ""
        assert "cyberred" in str(error).lower() or "error" in str(error).lower()

    def test_accepts_custom_message(self):
        """CyberRedError accepts a custom message."""
        from cyberred.core.exceptions import CyberRedError

        error = CyberRedError("Custom message")
        assert "Custom message" in str(error)


class TestScopeViolationError:
    """Tests for ScopeViolationError exception."""

    def test_inherits_from_cyberred_error(self):
        """ScopeViolationError should inherit from CyberRedError."""
        from cyberred.core.exceptions import CyberRedError, ScopeViolationError

        assert issubclass(ScopeViolationError, CyberRedError)

    def test_can_be_caught_as_cyberred_error(self):
        """ScopeViolationError can be caught as CyberRedError."""
        from cyberred.core.exceptions import CyberRedError, ScopeViolationError

        with pytest.raises(CyberRedError):
            raise ScopeViolationError(
                target="192.168.1.100", command="nmap", scope_rule="test_rule"
            )

    def test_has_target_attribute(self):
        """ScopeViolationError has target attribute."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.100", command="nmap", scope_rule="test_default"
        )
        assert error.target == "192.168.1.100"

    def test_has_command_attribute(self):
        """ScopeViolationError has command attribute."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.100", command="nmap -p 22", scope_rule="test_default"
        )
        assert error.command == "nmap -p 22"


    def test_has_scope_rule_attribute(self):
        """ScopeViolationError has scope_rule attribute."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.100", command="nmap", scope_rule="cidr_block"
        )
        assert error.scope_rule == "cidr_block"

    def test_message_contains_context(self):
        """ScopeViolationError message should contain contextual information."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.100", command="nmap -p 22", scope_rule="cidr_block"
        )
        msg = str(error)
        assert "192.168.1.100" in msg
        assert "scope" in msg.lower()

    def test_has_meaningful_default_message(self):
        """ScopeViolationError has meaningful default when args provided."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="10.0.0.1", command="ping", scope_rule="allowlist"
        )
        assert len(str(error)) > 0
        assert "10.0.0.1" in str(error)

    def test_provides_context_dict(self):
        """ScopeViolationError provides context dictionary for logging."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.1", command="nmap", scope_rule="cidr"
        )
        assert error.context == {
            "target": "192.168.1.1",
            "command": "nmap",
            "scope_rule": "cidr",
        }


class TestKillSwitchTriggered:
    """Tests for KillSwitchTriggered exception."""

    def test_inherits_from_cyberred_error(self):
        """KillSwitchTriggered should inherit from CyberRedError."""
        from cyberred.core.exceptions import CyberRedError, KillSwitchTriggered

        assert issubclass(KillSwitchTriggered, CyberRedError)

    def test_can_be_caught_as_cyberred_error(self):
        """KillSwitchTriggered can be caught as CyberRedError."""
        from cyberred.core.exceptions import CyberRedError, KillSwitchTriggered

        with pytest.raises(CyberRedError):
            raise KillSwitchTriggered(
                engagement_id="eng-001", triggered_by="op", reason="stop"
            )

    def test_has_engagement_id_attribute(self):
        """KillSwitchTriggered has engagement_id attribute."""
        from cyberred.core.exceptions import KillSwitchTriggered

        error = KillSwitchTriggered(
            engagement_id="eng-001", triggered_by="op", reason="stop"
        )
        assert error.engagement_id == "eng-001"

    def test_has_triggered_by_attribute(self):
        """KillSwitchTriggered has triggered_by attribute."""
        from cyberred.core.exceptions import KillSwitchTriggered

        error = KillSwitchTriggered(
            engagement_id="eng-001", triggered_by="operator", reason="stop"
        )
        assert error.triggered_by == "operator"

    def test_has_reason_attribute(self):
        """KillSwitchTriggered has reason attribute."""
        from cyberred.core.exceptions import KillSwitchTriggered

        error = KillSwitchTriggered(
            engagement_id="eng-001", triggered_by="operator", reason="Emergency stop"
        )
        assert error.reason == "Emergency stop"

    def test_message_contains_context(self):
        """KillSwitchTriggered message should contain contextual information."""
        from cyberred.core.exceptions import KillSwitchTriggered

        error = KillSwitchTriggered(
            engagement_id="eng-001", triggered_by="operator", reason="Emergency"
        )
        msg = str(error)
        assert "eng-001" in msg or "kill" in msg.lower()

    def test_provides_context_dict(self):
        """KillSwitchTriggered provides context dictionary for logging."""
        from cyberred.core.exceptions import KillSwitchTriggered

        error = KillSwitchTriggered(
            engagement_id="eng-001", triggered_by="admin", reason="panic"
        )
        assert error.context == {
            "engagement_id": "eng-001",
            "triggered_by": "admin",
            "reason": "panic",
        }


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_inherits_from_cyberred_error(self):
        """ConfigurationError should inherit from CyberRedError."""
        from cyberred.core.exceptions import ConfigurationError, CyberRedError

        assert issubclass(ConfigurationError, CyberRedError)

    def test_can_be_caught_as_cyberred_error(self):
        """ConfigurationError can be caught as CyberRedError."""
        from cyberred.core.exceptions import ConfigurationError, CyberRedError

        with pytest.raises(CyberRedError):
            raise ConfigurationError(config_path="/etc/config.yaml")

    def test_has_config_path_attribute(self):
        """ConfigurationError has config_path attribute."""
        from cyberred.core.exceptions import ConfigurationError

        error = ConfigurationError(config_path="/etc/config.yaml")
        assert error.config_path == "/etc/config.yaml"

    def test_has_key_attribute(self):
        """ConfigurationError has key attribute."""
        from cyberred.core.exceptions import ConfigurationError

        error = ConfigurationError(config_path="/etc/config.yaml", key="redis.host")
        assert error.key == "redis.host"

    def test_has_expected_type_attribute(self):
        """ConfigurationError has expected_type attribute."""
        from cyberred.core.exceptions import ConfigurationError

        error = ConfigurationError(
            config_path="/etc/config.yaml", key="port", expected_type="int"
        )
        assert error.expected_type == "int"

    def test_message_contains_context(self):
        """ConfigurationError message should contain contextual information."""
        from cyberred.core.exceptions import ConfigurationError

        error = ConfigurationError(
            config_path="/etc/config.yaml", key="redis.host", expected_type="str"
        )
        msg = str(error)
        assert "/etc/config.yaml" in msg or "config" in msg.lower()

    def test_provides_context_dict(self):
        """ConfigurationError provides context dictionary for logging."""
        from cyberred.core.exceptions import ConfigurationError

        error = ConfigurationError(
            config_path="/tmp/cfg.yaml", key="port", expected_type="int"
        )
        # Note: None values are filtered out or present as None?
        # Let's enforce they are present for explicit context
        ctx = error.context
        assert ctx["config_path"] == "/tmp/cfg.yaml"
        assert ctx["key"] == "port"
        assert ctx["expected_type"] == "int"


class TestCheckpointIntegrityError:
    """Tests for CheckpointIntegrityError exception."""

    def test_inherits_from_cyberred_error(self):
        """CheckpointIntegrityError should inherit from CyberRedError."""
        from cyberred.core.exceptions import CheckpointIntegrityError, CyberRedError

        assert issubclass(CheckpointIntegrityError, CyberRedError)

    def test_can_be_caught_as_cyberred_error(self):
        """CheckpointIntegrityError can be caught as CyberRedError."""
        from cyberred.core.exceptions import CheckpointIntegrityError, CyberRedError

        with pytest.raises(CyberRedError):
            raise CheckpointIntegrityError(checkpoint_path="/data/checkpoint.db")

    def test_has_checkpoint_path_attribute(self):
        """CheckpointIntegrityError has checkpoint_path attribute."""
        from cyberred.core.exceptions import CheckpointIntegrityError

        error = CheckpointIntegrityError(checkpoint_path="/data/checkpoint.db")
        assert error.checkpoint_path == "/data/checkpoint.db"

    def test_has_verification_type_attribute(self):
        """CheckpointIntegrityError has verification_type attribute."""
        from cyberred.core.exceptions import CheckpointIntegrityError

        error = CheckpointIntegrityError(
            checkpoint_path="/data/checkpoint.db", verification_type="signature"
        )
        assert error.verification_type == "signature"

    def test_verification_type_scope(self):
        """CheckpointIntegrityError supports 'scope' verification type."""
        from cyberred.core.exceptions import CheckpointIntegrityError

        error = CheckpointIntegrityError(
            checkpoint_path="/data/checkpoint.db", verification_type="scope"
        )
        assert error.verification_type == "scope"

    def test_message_contains_context(self):
        """CheckpointIntegrityError message should contain contextual information."""
        from cyberred.core.exceptions import CheckpointIntegrityError

        error = CheckpointIntegrityError(
            checkpoint_path="/data/checkpoint.db", verification_type="signature"
        )
        msg = str(error)
        assert "/data/checkpoint.db" in msg or "checkpoint" in msg.lower()

    def test_provides_context_dict(self):
        """CheckpointIntegrityError provides context dictionary for logging."""
        from cyberred.core.exceptions import CheckpointIntegrityError

        error = CheckpointIntegrityError(
            checkpoint_path="/chk.db", verification_type="sig"
        )
        assert error.context == {"checkpoint_path": "/chk.db", "verification_type": "sig"}


class TestExceptionReprAndStr:
    """Tests for exception repr and str methods for debugging."""

    def test_cyberred_error_repr(self):
        """CyberRedError has useful repr for debugging."""
        from cyberred.core.exceptions import CyberRedError

        error = CyberRedError("Test message")
        repr_str = repr(error)
        assert "CyberRedError" in repr_str

    def test_scope_violation_error_repr(self):
        """ScopeViolationError has useful repr with attributes."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(target="192.168.1.1", command="nmap", scope_rule="cidr")
        repr_str = repr(error)
        assert "ScopeViolationError" in repr_str

    def test_exceptions_context_property(self):
        """Exceptions should expose a context property for structlog binding."""
        from cyberred.core.exceptions import ScopeViolationError

        error = ScopeViolationError(
            target="192.168.1.1", command="nmap", scope_rule="cidr"
        )
        # Verify the context property exists and is correct
        assert isinstance(error.context, dict)
        assert error.context["target"] == "192.168.1.1"

