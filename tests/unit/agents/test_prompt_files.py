"""Unit tests for prompt file existence and content.

TDD RED phase tests - these should FAIL until prompt files are created.
"""

import pytest
from pathlib import Path


# All 8 required prompt files
REQUIRED_PROMPTS = [
    "recon.md",
    "exploit.md",
    "postex.md",
    "webapp.md",
    "wireless.md",
    "ad.md",
    "credential.md",
    "forensics.md",
]


@pytest.mark.unit
class TestPromptFiles:
    """Test cases for prompt file existence and content."""

    @pytest.fixture
    def prompts_dir(self) -> Path:
        """Return the prompts directory path."""
        return Path(__file__).parents[3] / "src" / "cyberred" / "agents" / "prompts"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
    def test_required_prompt_file_exists(self, prompts_dir: Path, filename: str) -> None:
        """Each required prompt file must exist."""
        filepath = prompts_dir / filename
        assert filepath.exists(), f"Missing required prompt file: {filename}"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
    def test_prompt_file_not_empty(self, prompts_dir: Path, filename: str) -> None:
        """Content length must be > 100 chars."""
        filepath = prompts_dir / filename
        if not filepath.exists():
            pytest.skip(f"File {filename} does not exist yet")
            
        content = filepath.read_text()
        assert len(content) > 100, f"Prompt {filename} too short ({len(content)} chars)"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
    def test_prompt_has_objectives(self, prompts_dir: Path, filename: str) -> None:
        """Each prompt must contain 'objective' (case-insensitive)."""
        filepath = prompts_dir / filename
        if not filepath.exists():
            pytest.skip(f"File {filename} does not exist yet")
            
        content = filepath.read_text().lower()
        assert "objective" in content, f"Prompt {filename} missing 'objective' section"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
    def test_prompt_has_tool_guidance(self, prompts_dir: Path, filename: str) -> None:
        """Each prompt must contain 'tool' (case-insensitive)."""
        filepath = prompts_dir / filename
        if not filepath.exists():
            pytest.skip(f"File {filename} does not exist yet")
            
        content = filepath.read_text().lower()
        assert "tool" in content, f"Prompt {filename} missing tool guidance"

    @pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
    def test_prompt_has_coordination(self, prompts_dir: Path, filename: str) -> None:
        """Each prompt should contain coordination instructions."""
        filepath = prompts_dir / filename
        if not filepath.exists():
            pytest.skip(f"File {filename} does not exist yet")
            
        content = filepath.read_text().lower()
        assert "coordination" in content or "stigmergic" in content, (
            f"Prompt {filename} missing coordination section"
        )

    def test_prompts_directory_exists(self, prompts_dir: Path) -> None:
        """The prompts directory must exist."""
        assert prompts_dir.exists(), f"Prompts directory does not exist: {prompts_dir}"
        assert prompts_dir.is_dir(), f"Prompts path is not a directory: {prompts_dir}"
