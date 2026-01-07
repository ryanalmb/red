# Emergence Tests (`tests/emergence/`)

## Purpose

Emergence tests validate **stigmergic coordination behavior** between agents. These are **hard-gate tests** that verify the system exhibits emergent behavior beyond what isolated agents would achieve.

## Test Categories

| Test File | Purpose | Related Requirements |
|-----------|---------|---------------------|
| `test_emergence_score.py` | Emergence score >20% validation | NFR35 |
| `test_causal_chains.py` | 3+ hop causal chain validation | NFR36 |
| `test_decision_context.py` | 100% decision_context population | NFR37 |

## Running Emergence Tests

```bash
# Run all emergence tests
pytest -m emergence

# Run emergence tests with verbose output
pytest -m emergence -v

# Run emergence tests with coverage
pytest -m emergence --cov=cyberred
```

## Marker

All emergence tests are marked with `@pytest.mark.emergence`:

```python
import pytest

@pytest.mark.emergence
def test_emergence_score_exceeds_20_percent():
    """Verify emergence score exceeds 20% hard gate."""
    pass
```

## Emergence Test Protocol

Per architecture (lines 1030-1037):

### 1. Isolated Run (Baseline)
- 100 agents, no stigmergic pub/sub enabled
- Record all findings and attack paths
- Establishes baseline for comparison

### 2. Stigmergic Run (Test)
- 100 agents, full pub/sub enabled
- Record findings, attack paths, and **decision_context**
- Demonstrates emergent coordination

### 3. Emergence Calculation
```python
novel_chains = stigmergic_paths - isolated_paths
emergence_score = len(novel_chains) / len(total_stigmergic_paths)
# HARD GATE: emergence_score > 0.20
```

## Hard Gate Requirements

| Gate | Threshold | Story |
|------|-----------|-------|
| **Emergence Score** | >20% | 7.10, 7.14 |
| **Causal Chain Depth** | 3+ hops | 7.11 |
| **Decision Context** | 100% population | 7.8, 15.7 |

## Cyber Range Integration

Emergence tests use the cyber-range environment for reproducible validation:

```bash
# Start cyber-range targets
docker-compose -f cyber-range/docker-compose.yml up -d

# Reference files
cyber-range/expected-findings.json      # Known vulnerabilities
cyber-range/emergence-baseline.json     # Baseline for comparison
```

## Decision Context (AgentAction)

Per architecture line 633:
```python
@dataclass
class AgentAction:
    decision_context: List[str]  # IDs of stigmergic signals that influenced this action
```

This is **CRITICAL for emergence validation** - it proves agents are responding to shared information, not acting in isolation.

## Implementation Status

These are **placeholder tests** that will be implemented in:
- Story 7.8: Decision Context Tracking
- Story 7.9: Isolated vs Stigmergic Comparison
- Story 7.10: Emergence Score Calculation
- Story 7.11: Causal Chain Depth Validation
- Story 7.14: Emergence Validation Gate Test
- Story 15.5-15.7: End-to-End Emergence Validation
