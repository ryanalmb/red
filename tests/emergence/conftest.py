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


# Story 7.25: 8-role diversity fixtures
from dataclasses import dataclass
from cyberred.agents.roles import AgentRole
from cyberred.orchestration.emergence.models import AttackPath, PathStep, RunResult, ComparisonResult
from cyberred.orchestration.emergence import NFR35_EMERGENCE_THRESHOLD


@dataclass
class MockContextResult:
    """Mock result for decision context validation in failure scenarios.
    
    Used when testing gate failure reports without full validation pipeline.
    """
    passed: bool = False
    percentage: float = 0.0


@dataclass
class EmergenceGateReport:
    """Comprehensive report from emergence gate validation.
    
    Attributes:
        nfr35_passed: Whether emergence score > 0.20.
        nfr35_score: The actual emergence score.
        nfr36_passed: Whether at least one 3+ hop chain exists.
        nfr36_max_depth: Maximum chain depth observed.
        nfr37_passed: Whether 100% decision_context populated.
        nfr37_rate: Decision context population rate.
        all_passed: Whether all gates passed.
        report_text: Human-readable report.
        role_contributions: Per-role contribution counts (Story 7.25, AC: 6).
    """
    nfr35_passed: bool
    nfr35_score: float
    nfr36_passed: bool
    nfr36_max_depth: int
    nfr37_passed: bool
    nfr37_rate: float
    all_passed: bool
    report_text: str
    role_contributions: dict[str, int] | None = None  # Story 7.25: per-role metrics

    @classmethod
    def from_results(
        cls,
        comparison: ComparisonResult,
        chain_result,
        context_result,
        novel_paths: list[AttackPath] | None = None,
    ) -> "EmergenceGateReport":
        """Create report from validation results.
        
        Args:
            comparison: ComparisonResult from emergence comparison.
            chain_result: ChainDepthResult from causal validation.
            context_result: ValidationResult from decision_context check.
            novel_paths: Optional list of novel paths for role contribution calc.
                         If None, uses comparison.novel_paths.
        """
        nfr35_passed = comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD
        nfr36_passed = chain_result.passed
        nfr37_passed = context_result.passed and context_result.percentage == 100.0
        
        all_passed = nfr35_passed and nfr36_passed and nfr37_passed
        
        # Calculate role contributions from novel paths (Story 7.25, AC: 6)
        paths_to_analyze = novel_paths if novel_paths is not None else comparison.novel_paths
        role_contributions: dict[str, int] = {}
        
        for path in paths_to_analyze:
            for step in path.steps:
                # Extract role from technique (e.g., "recon_technique" -> "recon")
                technique = step.technique.replace("_technique", "")
                role_contributions[technique] = role_contributions.get(technique, 0) + 1
        
        # Build role breakdown for report
        role_breakdown = ", ".join(
            f"{role}:{count}" for role, count in sorted(role_contributions.items())
        ) if role_contributions else "none"
        
        report_text = (
            f"\n{'='*60}\n"
            f"EMERGENCE HARD GATE REPORT\n"
            f"{'='*60}\n"
            f"NFR35 (>20% emergence): {'PASS' if nfr35_passed else 'FAIL'} "
            f"({comparison.emergence_score:.2%})\n"
            f"NFR36 (3+ hop chains):  {'PASS' if nfr36_passed else 'FAIL'} "
            f"(max depth: {chain_result.max_observed_depth})\n"
            f"NFR37 (100% context):   {'PASS' if nfr37_passed else 'FAIL'} "
            f"({context_result.percentage:.1f}%)\n"
            f"Role Contributions:     {role_breakdown}\n"
            f"{'='*60}\n"
            f"OVERALL: {'PASS - SHIP APPROVED' if all_passed else 'FAIL - NO SHIP'}\n"
            f"{'='*60}"
        )
        
        return cls(
            nfr35_passed=nfr35_passed,
            nfr35_score=comparison.emergence_score,
            nfr36_passed=nfr36_passed,
            nfr36_max_depth=chain_result.max_observed_depth,
            nfr37_passed=nfr37_passed,
            nfr37_rate=context_result.percentage,
            all_passed=all_passed,
            report_text=report_text,
            role_contributions=role_contributions,
        )


def create_path_for_role(
    role: AgentRole,
    target: str = "192.168.1.1",
    finding_prefix: str = "",
    action_prefix: str = "",
    decision_context: list[str] | None = None,
) -> AttackPath:
    """Create an AttackPath with a step for the given role.
    
    Args:
        role: AgentRole to create path for.
        target: Target IP/host for the step.
        finding_prefix: Optional prefix for finding_id.
        action_prefix: Optional prefix for action_id.
        decision_context: Optional decision context for the step.
        
    Returns:
        AttackPath with a single step for the role.
    """
    prefix = finding_prefix or role.value
    act_prefix = action_prefix or role.value
    
    step = PathStep(
        target=target,
        technique=f"{role.value}_technique",
        finding_id=f"finding_{prefix}_001",
        action_id=f"action_{act_prefix}_001",
        decision_context=decision_context or [],
    )
    return AttackPath(steps=[step])


def create_multi_step_path(
    roles: list[AgentRole],
    base_target: str = "192.168.1.1",
) -> AttackPath:
    """Create an AttackPath with steps from multiple roles (causal chain).
    
    Each step after the first references the previous step's finding
    in its decision_context, creating a proper causal chain.
    
    Args:
        roles: List of AgentRole for each step in the chain.
        base_target: Base target IP/host.
        
    Returns:
        AttackPath with steps from all specified roles.
    """
    steps: list[PathStep] = []
    
    for i, role in enumerate(roles):
        decision_context: list[str] = []
        if i > 0:
            # Reference previous step's finding
            prev_role = roles[i - 1]
            decision_context = [f"finding_{prev_role.value}_{i:03d}"]
        
        step = PathStep(
            target=base_target,
            technique=f"{role.value}_technique",
            finding_id=f"finding_{role.value}_{i+1:03d}",
            action_id=f"action_{role.value}_{i+1:03d}",
            decision_context=decision_context,
        )
        steps.append(step)
    
    return AttackPath(steps=steps)


@pytest.fixture
def all_agent_roles() -> list[AgentRole]:
    """Return all 8 agent roles."""
    return list(AgentRole)


@pytest.fixture
def three_role_list() -> list[AgentRole]:
    """Return the original 3 roles (RECON, EXPLOIT, POSTEX)."""
    return [AgentRole.RECON, AgentRole.EXPLOIT, AgentRole.POSTEX]


@pytest.fixture
def eight_role_stigmergic_result(all_agent_roles: list[AgentRole]) -> RunResult:
    """Create a stigmergic RunResult with paths from all 8 agent types.
    
    This fixture provides a full-diversity swarm result for emergence testing.
    Each role contributes at least one attack path.
    """
    paths: list[AttackPath] = []
    
    # Create one path per role
    for i, role in enumerate(all_agent_roles):
        path = create_path_for_role(
            role,
            target=f"192.168.1.{i + 1}",
            decision_context=[f"signal_{role.value}"],
        )
        paths.append(path)
    
    # Add a multi-role causal chain (4 hops - meets NFR36)
    cross_role_chain = create_multi_step_path([
        AgentRole.RECON,
        AgentRole.EXPLOIT,
        AgentRole.POSTEX,
        AgentRole.AD,
    ])
    paths.append(cross_role_chain)
    
    return RunResult(
        run_id="stigmergic-8-role-001",
        mode="stigmergic",
        agent_count=AGENT_COUNT,
        findings=[{"id": f"finding_{role.value}_001"} for role in all_agent_roles],
        attack_paths=paths,
        actions=[
            {
                "id": f"action_{role.value}_001",
                "agent_id": f"agent_{role.value}",
                "action_type": f"{role.value}_technique",
                "target": f"192.168.1.{i + 1}",
                "timestamp": "2026-01-28T00:00:00Z",
                "decision_context": [f"signal_{role.value}"],
            }
            for i, role in enumerate(all_agent_roles)
        ],
        duration_ms=120000,
    )


@pytest.fixture
def three_role_stigmergic_result(three_role_list: list[AgentRole]) -> RunResult:
    """Create a stigmergic RunResult with paths from only 3 roles (baseline).
    
    This fixture provides a limited-diversity swarm result for comparison.
    Only RECON, EXPLOIT, POSTEX roles are represented.
    """
    paths: list[AttackPath] = []
    
    # Create one path per role
    for i, role in enumerate(three_role_list):
        path = create_path_for_role(
            role,
            target=f"192.168.1.{i + 1}",
            decision_context=[f"signal_{role.value}"],
        )
        paths.append(path)
    
    # Add a 3-role causal chain
    cross_role_chain = create_multi_step_path(three_role_list)
    paths.append(cross_role_chain)
    
    return RunResult(
        run_id="stigmergic-3-role-001",
        mode="stigmergic",
        agent_count=AGENT_COUNT,
        findings=[{"id": f"finding_{role.value}_001"} for role in three_role_list],
        attack_paths=paths,
        actions=[
            {
                "id": f"action_{role.value}_001",
                "agent_id": f"agent_{role.value}",
                "action_type": f"{role.value}_technique",
                "target": f"192.168.1.{i + 1}",
                "timestamp": "2026-01-28T00:00:00Z",
                "decision_context": [f"signal_{role.value}"],
            }
            for i, role in enumerate(three_role_list)
        ],
        duration_ms=60000,
    )


@pytest.fixture
def isolated_baseline_result() -> RunResult:
    """Create an isolated RunResult with minimal baseline paths."""
    # Only 2 baseline paths (will be shared with stigmergic runs)
    paths = [
        create_path_for_role(AgentRole.RECON, target="192.168.1.1", finding_prefix="iso_recon"),
        create_path_for_role(AgentRole.EXPLOIT, target="192.168.1.2", finding_prefix="iso_exploit"),
    ]
    
    return RunResult(
        run_id="isolated-baseline-001",
        mode="isolated",
        agent_count=AGENT_COUNT,
        findings=[{"id": "finding_iso_recon_001"}, {"id": "finding_iso_exploit_001"}],
        attack_paths=paths,
        actions=[],
        duration_ms=60000,
    )
