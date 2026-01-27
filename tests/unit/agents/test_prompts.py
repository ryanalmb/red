"""Unit tests for PromptLibrary class.

TDD RED phase tests - these should FAIL until PromptLibrary is implemented.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.mark.unit
class TestPromptLibrary:
    """Test cases for PromptLibrary class."""

    def test_prompt_library_importable_from_agents(self) -> None:
        """PromptLibrary must be importable from cyberred.agents."""
        from cyberred.agents import PromptLibrary
        
        assert PromptLibrary is not None

    def test_get_returns_non_empty_string(self) -> None:
        """PromptLibrary.get() must return a non-empty string."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        result = PromptLibrary.get(role=AgentRole.RECON)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_loads_role_file(self, tmp_path: Path) -> None:
        """File content is loaded correctly for a role."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        # Create test prompt file
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        test_content = "# Recon Specialist\n\nTest prompt content."
        (prompts_dir / "recon.md").write_text(test_content)
        
        # Patch PROMPT_DIR to use temp directory
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()  # Clear any cached content
            result = PromptLibrary.get(role=AgentRole.RECON)
            
        assert result == test_content

    def test_specialty_takes_precedence(self, tmp_path: Path) -> None:
        """Specialty prompt takes precedence over base role prompt."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        base_content = "Base recon prompt"
        specialty_content = "Network specialty recon prompt"
        (prompts_dir / "recon.md").write_text(base_content)
        (prompts_dir / "recon_network.md").write_text(specialty_content)
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            result = PromptLibrary.get(role=AgentRole.RECON, specialty="network")
            
        assert result == specialty_content

    def test_falls_back_to_role(self, tmp_path: Path) -> None:
        """Missing specialty falls back to base role file."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        base_content = "Base exploit prompt for fallback test"
        (prompts_dir / "exploit.md").write_text(base_content)
        # Note: exploit_web.md does NOT exist
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            result = PromptLibrary.get(role=AgentRole.EXPLOIT, specialty="web")
            
        assert result == base_content

    def test_default_when_no_file(self, tmp_path: Path) -> None:
        """Returns functional default when no file exists."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        # No forensics.md file exists
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            result = PromptLibrary.get(role=AgentRole.FORENSICS)
        
        # Verify default contains required elements
        assert "penetration tester" in result.lower() or "penetration testing" in result.lower()
        assert "FORENSICS" in result or "forensics" in result.lower()
        assert "1,556+" in result or "1556" in result

    def test_caches_loaded_prompts(self, tmp_path: Path) -> None:
        """Cached version is returned without additional file I/O."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "recon.md").write_text("Original content")
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            
            # First call loads from file
            result1 = PromptLibrary.get(role=AgentRole.RECON)
            
            # Modify file
            (prompts_dir / "recon.md").write_text("Modified content")
            
            # Second call should return cached content
            result2 = PromptLibrary.get(role=AgentRole.RECON)
            
        assert result1 == result2 == "Original content"

    def test_clear_cache_enables_reload(self, tmp_path: Path) -> None:
        """After clear_cache(), file changes are picked up."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "recon.md").write_text("Original content")
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            
            # First load
            result1 = PromptLibrary.get(role=AgentRole.RECON)
            assert result1 == "Original content"
            
            # Modify file and clear cache
            (prompts_dir / "recon.md").write_text("Modified content")
            PromptLibrary.clear_cache()
            
            # Now should get new content
            result2 = PromptLibrary.get(role=AgentRole.RECON)
            
        assert result2 == "Modified content"

    def test_cache_key_format(self) -> None:
        """Cache keys differ for role vs role+specialty."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        key1 = PromptLibrary._cache_key(AgentRole.RECON, None)
        key2 = PromptLibrary._cache_key(AgentRole.RECON, "network")
        key3 = PromptLibrary._cache_key(AgentRole.EXPLOIT, None)
        
        assert key1 != key2, "Role-only key should differ from role+specialty"
        assert key1 != key3, "Different roles should have different keys"
        assert key2 != key3, "Different role+specialty combos should differ"

    def test_get_has_optional_specialty_parameter(self) -> None:
        """PromptLibrary.get() specialty parameter is optional."""
        from cyberred.agents import AgentRole, PromptLibrary
        from inspect import signature
        
        sig = signature(PromptLibrary.get)
        specialty_param = sig.parameters.get("specialty")
        
        assert specialty_param is not None
        assert specialty_param.default is None or specialty_param.default == ""

    def test_empty_string_specialty_treated_as_none(self, tmp_path: Path) -> None:
        """Empty string specialty is normalized to None."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        base_content = "Base recon prompt"
        (prompts_dir / "recon.md").write_text(base_content)
        # Create recon_.md to prove empty string doesn't try to load it
        (prompts_dir / "recon_.md").write_text("Should not load this")
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            result = PromptLibrary.get(role=AgentRole.RECON, specialty="")
            
        assert result == base_content

    def test_whitespace_specialty_treated_as_none(self, tmp_path: Path) -> None:
        """Whitespace-only specialty is normalized to None."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        base_content = "Base exploit prompt"
        (prompts_dir / "exploit.md").write_text(base_content)
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            result = PromptLibrary.get(role=AgentRole.EXPLOIT, specialty="   ")
            
        assert result == base_content

    def test_long_specialty_truncated(self, tmp_path: Path) -> None:
        """Specialty longer than MAX_SPECIALTY_LENGTH is truncated."""
        from cyberred.agents import AgentRole, PromptLibrary
        from cyberred.agents.prompts import MAX_SPECIALTY_LENGTH
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        base_content = "Base recon prompt for truncation test"
        (prompts_dir / "recon.md").write_text(base_content)
        
        # Very long specialty should not cause OSError
        long_specialty = "a" * 1000
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            # Should not raise, should fall back to base prompt
            result = PromptLibrary.get(role=AgentRole.RECON, specialty=long_specialty)
            
        assert result == base_content

    def test_long_specialty_logs_warning(self, tmp_path: Path) -> None:
        """Truncating long specialty logs a warning."""
        from cyberred.agents import AgentRole, PromptLibrary
        from cyberred.agents.prompts import MAX_SPECIALTY_LENGTH
        import structlog
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "recon.md").write_text("Base content")
        
        long_specialty = "x" * (MAX_SPECIALTY_LENGTH + 10)
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            with patch('cyberred.agents.prompts.logger') as mock_logger:
                PromptLibrary.get(role=AgentRole.RECON, specialty=long_specialty)
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert call_args[0][0] == "specialty_truncated"

    def test_specialty_fallback_logs_debug(self, tmp_path: Path) -> None:
        """When specialty file missing, debug log indicates fallback."""
        from cyberred.agents import AgentRole, PromptLibrary
        
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "exploit.md").write_text("Base exploit")
        # No exploit_custom.md exists
        
        with patch.object(PromptLibrary, 'PROMPT_DIR', prompts_dir):
            PromptLibrary.clear_cache()
            with patch('cyberred.agents.prompts.logger') as mock_logger:
                PromptLibrary.get(role=AgentRole.EXPLOIT, specialty="custom")
                # Check that fallback debug was logged
                debug_calls = [call for call in mock_logger.debug.call_args_list]
                fallback_logged = any(
                    "specialty_prompt_not_found_fallback" in str(call) 
                    for call in debug_calls
                )
                assert fallback_logged, "Fallback debug log not found"

    def test_thread_safety_lock_exists(self) -> None:
        """PromptLibrary has a threading lock for thread safety."""
        from cyberred.agents import PromptLibrary
        from threading import Lock
        
        assert hasattr(PromptLibrary, '_lock')
        assert isinstance(PromptLibrary._lock, type(Lock()))

    def test_max_specialty_length_constant_exported(self) -> None:
        """MAX_SPECIALTY_LENGTH constant is accessible."""
        from cyberred.agents.prompts import MAX_SPECIALTY_LENGTH
        
        assert isinstance(MAX_SPECIALTY_LENGTH, int)
        assert MAX_SPECIALTY_LENGTH > 0
        assert MAX_SPECIALTY_LENGTH <= 255  # Reasonable filesystem limit
