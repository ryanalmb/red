"""
Pytest fixtures for emergence tests.

Story 7.14: Emergence Validation Gate Test
Provides shared fixtures for cyber range integration and emergence testing.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock

from cyberred.orchestration.emergence import (
    EmergenceComparisonFramework,
    EmergenceComparisonConfig,
    CausalChainValidator,
)


# Environment variable configuration
AGENT_COUNT = int(os.environ.get("EMERGENCE_TEST_AGENT_COUNT", "100"))
TEST_TIMEOUT = int(os.environ.get("EMERGENCE_TEST_TIMEOUT", "1800"))  # 30 min
DOCKER_COMPOSE_TIMEOUT = int(os.environ.get("DOCKER_COMPOSE_TIMEOUT", "120"))  # 2 min

# Cyber range paths
CYBER_RANGE_DIR = Path(__file__).parent.parent.parent / "cyber-range"


@pytest.fixture
def emergence_config() -> EmergenceComparisonConfig:
    """Configuration for emergence comparison.
    
    Returns:
        EmergenceComparisonConfig with agent count and timeout from environment.
    """
    return EmergenceComparisonConfig(
        agent_count=AGENT_COUNT,
        timeout_seconds=TEST_TIMEOUT,
    )


@pytest.fixture
def comparison_framework(emergence_config: EmergenceComparisonConfig) -> EmergenceComparisonFramework:
    """Configured emergence comparison framework.
    
    Args:
        emergence_config: Configuration for the framework.
        
    Returns:
        EmergenceComparisonFramework instance with mock event bus.
    """
    event_bus = Mock()
    return EmergenceComparisonFramework(emergence_config, event_bus)


@pytest.fixture
def causal_validator() -> CausalChainValidator:
    """Causal chain validator instance.
    
    Returns:
        CausalChainValidator for chain depth validation.
    """
    return CausalChainValidator()


def _wait_for_targets_ready(timeout: int = 60) -> bool:
    """Wait for all cyber range targets to be accessible.
    
    Args:
        timeout: Maximum time to wait in seconds.
        
    Returns:
        True if targets are ready, False otherwise.
    """
    # Implementation: poll target health endpoints
    # For now, this is a placeholder that returns True for mock mode
    return True


@pytest.fixture(scope="session")
def cyber_range_up():
    """Start cyber range docker-compose for emergence testing.
    
    Scope: session (shared across all emergence tests)
    
    This fixture manages the lifecycle of the cyber-range docker-compose
    environment. In mock mode (default), it yields immediately without
    starting containers.
    
    Yields:
        Path to cyber range directory.
    """
    compose_file = CYBER_RANGE_DIR / "docker-compose.yml"
    
    # Check if we should run in mock mode (no actual containers)
    mock_mode = os.environ.get("EMERGENCE_MOCK_MODE", "true").lower() == "true"
    
    if mock_mode:
        # Mock mode: skip docker-compose, use synthetic data
        yield CYBER_RANGE_DIR
        return
    
    # Real mode: start containers (requires docker-compose)
    import subprocess
    
    try:
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            check=True,
            timeout=DOCKER_COMPOSE_TIMEOUT,
            capture_output=True,
        )
        
        # Wait for targets to be ready
        _wait_for_targets_ready()
        
        yield CYBER_RANGE_DIR
        
    finally:
        # Teardown: stop containers
        subprocess.run(
            ["docker-compose", "-f", str(compose_file), "down"],
            check=True,
            capture_output=True,
        )


@pytest.fixture
def agent_pool(cyber_range_up, emergence_config: EmergenceComparisonConfig):
    """Spawn agents for emergence testing.
    
    Args:
        cyber_range_up: Ensures cyber range is running.
        emergence_config: Configuration with agent count.
        
    Returns:
        Dict with agent pool information.
    """
    return {
        "count": emergence_config.agent_count,
        "timeout": emergence_config.timeout_seconds,
        "cyber_range_dir": cyber_range_up,
    }
