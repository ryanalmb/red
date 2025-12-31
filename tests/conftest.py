"""
Cyber-Red v2.0 Test Configuration

Shared pytest fixtures and configuration for all test types.
"""

import json
import time
import yaml
import asyncio
from pathlib import Path
from typing import Any, Generator

import pytest
import structlog


# Configure pytest collection
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (require external services)")
    config.addinivalue_line("markers", "safety: Safety-critical tests (scope, kill switch, auth)")
    config.addinivalue_line("markers", "emergence: Emergence validation tests (stigmergic metrics)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full engagement flows)")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests (resilience)")
    config.addinivalue_line("markers", "load: Load and stress tests (scale validation)")


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.
    
    Required for pytest-asyncio to properly handle async fixtures and tests.
    Uses session scope to share the loop across all tests for efficiency.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# Basic test environment fixtures
@pytest.fixture
def test_config_dir(tmp_path):
    """Provide a temporary configuration directory for tests."""
    config_dir = tmp_path / ".cyber-red"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_finding():
    """Provide a sample Finding object for tests."""
    return {
        "id": "test-finding-001",
        "type": "sqli",
        "severity": "high",
        "target": "192.168.1.100",
        "evidence": "Parameter 'id' is vulnerable to SQL injection",
        "agent_id": "test-agent-001",
        "timestamp": "2025-01-01T00:00:00Z",
        "tool": "sqlmap",
        "topic": "findings:test:sqli",
        "signature": "test-signature",
    }


@pytest.fixture
def sample_tool_result():
    """Provide a sample ToolResult object for tests."""
    return {
        "success": True,
        "stdout": "Scan completed successfully",
        "stderr": "",
        "exit_code": 0,
        "duration_ms": 1500,
    }


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture_data(fixtures_dir):
    """
    Factory fixture to load data from a fixture file.
    
    Args:
        filename: Relative path to file within tests/fixtures/
        
    Returns:
        Parsed data (dict/list) from JSON or YAML file
    """
    def _load(filename: str) -> Any:
        file_path = fixtures_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {file_path}")
        
        if filename.endswith(".json"):
            with open(file_path, "r") as f:
                return json.load(f)
        elif filename.endswith((".yaml", ".yml")):
            with open(file_path, "r") as f:
                return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported fixture format: {filename}")
    return _load


@pytest.fixture
def sample_engagement_data(load_fixture_data):
    """Load sample engagement data from fixture file."""
    return load_fixture_data("engagements/sample_engagement.json")


@pytest.fixture
def sample_sqli_data(load_fixture_data):
    """Load sample SQLi finding data from fixture file."""
    return load_fixture_data("findings/sample_sqli.json")


@pytest.fixture
def sample_scope_data(load_fixture_data):
    """Load sample scope data from fixture file."""
    return load_fixture_data("scope/allowlist.yaml")


# Kali container fixture for integration tests
log = structlog.get_logger()


@pytest.fixture(scope="function")
def kali_container() -> Generator["DockerContainer", None, None]:
    """
    Provide a real Kali Linux container for integration tests.
    
    This fixture:
    - Automatically pulls and starts the Kali container
    - Logs startup time for performance tracking
    - Ensures proper cleanup even on test failure
    - Uses kalilinux/kali-rolling as the container image
    - Enforces network isolation (network_mode="none")
    
    Usage:
        @pytest.mark.integration
        def test_with_kali(kali_container):
            result = kali_container.exec("nmap --version")
            assert "Nmap" in result.output
    
    Note: Requires Docker to be available on the test machine.
    """
    from testcontainers.core.container import DockerContainer
    
    # Use kali-rolling as the primary image (kali-linux-docker is deprecated)
    image = "kalilinux/kali-rolling"
    
    container = DockerContainer(image)
    # Keep container running with a tail command
    container.with_command("tail -f /dev/null")
    # Enforce network isolation per architecture hardening requirements
    # 'none' disables all networking, forcing interaction via exec only (API)
    container.with_kwargs(network_mode="none")
    
    start_time = time.time()
    container.start()
    startup_ms = int((time.time() - start_time) * 1000)
    
    log.info(
        "kali_container_started",
        container_startup_ms=startup_ms,
        image=image,
        container_id=container.get_wrapped_container().id[:12],
    )
    
    try:
        yield container
    finally:
        # Ensure cleanup even on test failure
        try:
            container.stop()
            log.info(
                "kali_container_stopped",
                container_id=container.get_wrapped_container().id[:12],
            )
        except Exception as e:
            log.warning(
                "kali_container_cleanup_error",
                error=str(e),
            )
