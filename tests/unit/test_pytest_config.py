"""
Sample unit test to verify pytest and pytest-asyncio configuration.

This test validates:
- pytest discovers tests in tests/unit/ directory
- pytest-asyncio handles async test functions automatically
- Test fixtures from conftest.py are accessible
"""

import asyncio

import pytest


class TestPytestConfiguration:
    """Test suite to verify basic pytest configuration."""

    def test_sync_test_runs(self):
        """Verify synchronous tests run correctly."""
        assert True

    @pytest.mark.asyncio
    async def test_async_test_runs(self):
        """Verify async tests run correctly with pytest-asyncio."""
        await asyncio.sleep(0.001)
        assert True

    @pytest.mark.unit
    def test_unit_marker_works(self):
        """Verify custom test markers are registered."""
        assert True


class TestFixturesAvailable:
    """Test suite to verify fixtures from conftest.py are available."""

    def test_sample_finding_fixture(self, sample_finding):
        """Verify sample_finding fixture is accessible."""
        assert sample_finding["type"] == "sqli"
        assert sample_finding["severity"] == "high"
        assert "signature" in sample_finding

    def test_sample_tool_result_fixture(self, sample_tool_result):
        """Verify sample_tool_result fixture is accessible."""
        assert sample_tool_result["success"] is True
        assert sample_tool_result["exit_code"] == 0

    def test_test_config_dir_fixture(self, test_config_dir):
        """Verify test_config_dir fixture creates temp directory."""
        assert test_config_dir.exists()
        assert test_config_dir.name == ".cyber-red"


@pytest.mark.asyncio
async def test_async_function_level():
    """Verify async function-level tests work without class."""
    result = await asyncio.gather(
        asyncio.sleep(0.001),
        asyncio.sleep(0.001),
    )
    assert len(result) == 2
