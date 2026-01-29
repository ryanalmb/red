"""Unit tests for DeputyOperatorConfig.

Story 10.8: Deputy Operator Configuration
Tests AC: #1, #5

RED Phase: These tests should FAIL until DeputyOperatorConfig is implemented.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from cyberred.core.exceptions import ConfigurationError


class TestDeputyOperatorConfig:
    """Tests for DeputyOperatorConfig dataclass."""

    def test_init_with_valid_email(self) -> None:
        """Test initialization with valid deputy operator email."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        assert config.deputy_operator == "deputy@example.com"
        # Default timeout should be 30 minutes
        assert config.escalation_timeout == timedelta(minutes=30)

    def test_init_with_valid_identifier(self) -> None:
        """Test initialization with valid deputy operator identifier."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(deputy_operator="deputy-user-123")
        
        assert config.deputy_operator == "deputy-user-123"

    def test_default_escalation_timeout(self) -> None:
        """Test that default escalation timeout is 30 minutes."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        assert config.escalation_timeout == timedelta(minutes=30)

    def test_custom_escalation_timeout(self) -> None:
        """Test initialization with custom escalation timeout."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=45),
        )
        
        assert config.escalation_timeout == timedelta(minutes=45)

    def test_escalation_timeout_minimum_validation(self) -> None:
        """Test that escalation timeout below 5 minutes raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        with pytest.raises(ConfigurationError) as exc_info:
            DeputyOperatorConfig(
                deputy_operator="deputy@example.com",
                escalation_timeout=timedelta(minutes=4),  # Below 5 min minimum
            )
        
        assert "escalation_timeout" in str(exc_info.value)
        assert "5 minutes" in str(exc_info.value)

    def test_escalation_timeout_maximum_validation(self) -> None:
        """Test that escalation timeout above 24 hours raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        with pytest.raises(ConfigurationError) as exc_info:
            DeputyOperatorConfig(
                deputy_operator="deputy@example.com",
                escalation_timeout=timedelta(hours=25),  # Above 24 hour maximum
            )
        
        assert "escalation_timeout" in str(exc_info.value)
        assert "24 hours" in str(exc_info.value)

    def test_escalation_timeout_at_minimum_boundary(self) -> None:
        """Test that exactly 5 minutes timeout is valid."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=5),
        )
        
        assert config.escalation_timeout == timedelta(minutes=5)

    def test_escalation_timeout_at_maximum_boundary(self) -> None:
        """Test that exactly 24 hours timeout is valid."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(hours=24),
        )
        
        assert config.escalation_timeout == timedelta(hours=24)

    def test_empty_deputy_operator_raises(self) -> None:
        """Test that empty deputy_operator raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        with pytest.raises(ConfigurationError) as exc_info:
            DeputyOperatorConfig(deputy_operator="")
        
        assert "deputy_operator" in str(exc_info.value)
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_deputy_operator_raises(self) -> None:
        """Test that whitespace-only deputy_operator raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        with pytest.raises(ConfigurationError) as exc_info:
            DeputyOperatorConfig(deputy_operator="   ")
        
        assert "deputy_operator" in str(exc_info.value)
        assert "empty" in str(exc_info.value).lower()


class TestDeputyOperatorConfigFromDict:
    """Tests for DeputyOperatorConfig.from_dict() factory method."""

    def test_from_dict_basic(self) -> None:
        """Test creating config from dictionary."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "deputy_operator": "deputy@example.com",
        }
        
        config = DeputyOperatorConfig.from_dict(data)
        
        assert config.deputy_operator == "deputy@example.com"
        assert config.escalation_timeout == timedelta(minutes=30)

    def test_from_dict_with_timeout_string_minutes(self) -> None:
        """Test parsing timeout from string with minutes format (e.g., '30m')."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "deputy_operator": "deputy@example.com",
            "escalation_timeout": "45m",
        }
        
        config = DeputyOperatorConfig.from_dict(data)
        
        assert config.escalation_timeout == timedelta(minutes=45)

    def test_from_dict_with_timeout_string_hours(self) -> None:
        """Test parsing timeout from string with hours format (e.g., '2h')."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "deputy_operator": "deputy@example.com",
            "escalation_timeout": "2h",
        }
        
        config = DeputyOperatorConfig.from_dict(data)
        
        assert config.escalation_timeout == timedelta(hours=2)

    def test_from_dict_with_timeout_integer_seconds(self) -> None:
        """Test parsing timeout from integer (seconds)."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "deputy_operator": "deputy@example.com",
            "escalation_timeout": 3600,  # 1 hour in seconds
        }
        
        config = DeputyOperatorConfig.from_dict(data)
        
        assert config.escalation_timeout == timedelta(hours=1)

    def test_from_dict_missing_deputy_operator_raises(self) -> None:
        """Test that missing deputy_operator raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "escalation_timeout": "30m",
        }
        
        with pytest.raises((ConfigurationError, KeyError, TypeError)):
            DeputyOperatorConfig.from_dict(data)

    def test_from_dict_invalid_timeout_format_raises(self) -> None:
        """Test that invalid timeout format raises ConfigurationError."""
        from cyberred.core.config import DeputyOperatorConfig
        
        data = {
            "deputy_operator": "deputy@example.com",
            "escalation_timeout": "invalid",
        }
        
        with pytest.raises((ConfigurationError, ValueError)):
            DeputyOperatorConfig.from_dict(data)


class TestDeputyOperatorConfigToDict:
    """Tests for DeputyOperatorConfig.to_dict() serialization."""

    def test_to_dict_basic(self) -> None:
        """Test serializing config to dictionary."""
        from cyberred.core.config import DeputyOperatorConfig
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=45),
        )
        
        data = config.to_dict()
        
        assert data["deputy_operator"] == "deputy@example.com"
        assert "escalation_timeout" in data
        # Timeout should be serialized as seconds (int) or string
        assert data["escalation_timeout"] in [2700, "45m", "2700s", timedelta(minutes=45)]

    def test_to_dict_roundtrip(self) -> None:
        """Test that to_dict() output can be used with from_dict()."""
        from cyberred.core.config import DeputyOperatorConfig
        
        original = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(hours=1),
        )
        
        data = original.to_dict()
        restored = DeputyOperatorConfig.from_dict(data)
        
        assert restored.deputy_operator == original.deputy_operator
        assert restored.escalation_timeout == original.escalation_timeout


class TestParseDuration:
    """Tests for parse_duration helper function."""

    def test_parse_duration_minutes(self) -> None:
        """Test parsing duration with minutes format."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration("30m") == timedelta(minutes=30)
        assert parse_duration("5m") == timedelta(minutes=5)
        assert parse_duration("90m") == timedelta(minutes=90)

    def test_parse_duration_hours(self) -> None:
        """Test parsing duration with hours format."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration("1h") == timedelta(hours=1)
        assert parse_duration("24h") == timedelta(hours=24)
        assert parse_duration("2h") == timedelta(hours=2)

    def test_parse_duration_seconds(self) -> None:
        """Test parsing duration with seconds format."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration("300s") == timedelta(seconds=300)
        assert parse_duration("3600s") == timedelta(seconds=3600)

    def test_parse_duration_integer(self) -> None:
        """Test parsing duration from integer (seconds)."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration(300) == timedelta(seconds=300)
        assert parse_duration(3600) == timedelta(seconds=3600)

    def test_parse_duration_timedelta_passthrough(self) -> None:
        """Test that timedelta input is passed through unchanged."""
        from cyberred.core.config import parse_duration
        
        td = timedelta(minutes=45)
        assert parse_duration(td) == td

    def test_parse_duration_invalid_format(self) -> None:
        """Test that invalid format raises ValueError."""
        from cyberred.core.config import parse_duration
        
        with pytest.raises(ValueError):
            parse_duration("invalid")
        
        with pytest.raises(ValueError):
            parse_duration("30")  # No unit
        
        with pytest.raises(ValueError):
            parse_duration("m30")  # Wrong order

    def test_parse_duration_float_values(self) -> None:
        """Test parsing duration with float values (e.g., '1.5h')."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration("1.5h") == timedelta(hours=1.5)
        assert parse_duration("30.5m") == timedelta(minutes=30.5)
        assert parse_duration("90.25s") == timedelta(seconds=90.25)

    def test_parse_duration_float_integer(self) -> None:
        """Test parsing duration from float (seconds)."""
        from cyberred.core.config import parse_duration
        
        assert parse_duration(300.5) == timedelta(seconds=300.5)
        assert parse_duration(3600.75) == timedelta(seconds=3600.75)
