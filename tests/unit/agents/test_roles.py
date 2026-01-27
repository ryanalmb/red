"""Unit tests for AgentRole enum.

TDD RED phase tests - these should FAIL until AgentRole is implemented.
"""

import pytest


@pytest.mark.unit
class TestAgentRole:
    """Test cases for AgentRole enum."""

    def test_agent_role_has_eight_values(self) -> None:
        """Verify exactly 8 roles exist."""
        from cyberred.agents import AgentRole
        
        roles = list(AgentRole)
        assert len(roles) == 8, f"Expected 8 roles, got {len(roles)}"

    @pytest.mark.parametrize(
        "role_name",
        ["RECON", "EXPLOIT", "POSTEX", "WEBAPP", "WIRELESS", "AD", "CREDENTIAL", "FORENSICS"],
    )
    def test_all_roles_exist(self, role_name: str) -> None:
        """Each required role must exist in the enum."""
        from cyberred.agents import AgentRole
        
        assert hasattr(AgentRole, role_name), f"AgentRole missing {role_name}"
        role = getattr(AgentRole, role_name)
        assert role is not None

    def test_agent_role_values_are_lowercase(self) -> None:
        """Each role.value must equal role.name.lower()."""
        from cyberred.agents import AgentRole
        
        for role in AgentRole:
            assert role.value == role.name.lower(), (
                f"{role.name}.value is '{role.value}', expected '{role.name.lower()}'"
            )

    def test_agent_role_importable_from_agents(self) -> None:
        """AgentRole must be importable from cyberred.agents."""
        from cyberred.agents import AgentRole
        
        # If we get here, import succeeded
        assert AgentRole is not None
        
    def test_agent_role_is_enum(self) -> None:
        """AgentRole must be an Enum type."""
        from enum import Enum
        from cyberred.agents import AgentRole
        
        assert issubclass(AgentRole, Enum)

    def test_agent_role_values_are_strings(self) -> None:
        """Each role value must be a string."""
        from cyberred.agents import AgentRole
        
        for role in AgentRole:
            assert isinstance(role.value, str), f"{role.name}.value is not a string"
