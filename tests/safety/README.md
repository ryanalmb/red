# Safety Tests (`tests/safety/`)

## Purpose

Safety tests are **hard-gate tests that MUST NEVER FAIL**. They validate critical safety invariants that protect against dangerous or unauthorized system behavior.

## Test Categories

| Test File | Purpose | Related Requirements |
|-----------|---------|---------------------|
| `test_scope_blocks.py` | Scope validator blocks out-of-scope targets | FR20-FR21, ERR6 |
| `test_killswitch.py` | Kill switch halts operations in <1s | NFR2, FR17-FR18 |
| `test_auth_required.py` | Lateral movement requires authorization | FR13-FR16, FR63-FR64 |

## Running Safety Tests

```bash
# Run all safety tests
pytest -m safety

# Run safety tests with verbose output
pytest -m safety -v

# Run safety tests and stop on first failure
pytest -m safety -x
```

## Marker

All safety tests are marked with `@pytest.mark.safety`:

```python
import pytest

@pytest.mark.safety
def test_scope_blocks_unauthorized_target():
    """Safety-critical: Verify unauthorized targets are blocked."""
    pass
```

## CI Integration

Safety tests are configured to **always run** in CI pipelines. They are gate tests that block deployment if any fail.

```yaml
# .github/workflows/ci.yml
- name: Run Safety Tests
  run: pytest -m safety --tb=short
```

## Hard Gate Requirements

These tests enforce the following hard gates:

1. **Scope Validation (Story 1.8)**
   - All tool executions must pass scope validation BEFORE execution
   - Out-of-scope attempts raise `ScopeViolationError`
   - Validation is fail-closed (deny on error)

2. **Kill Switch Timing (Story 1.9/1.10)**
   - Kill switch must complete in <1s under 10K agent load
   - Three-path execution: Redis pub/sub, SIGTERM cascade, Docker API
   - Must work even if Redis is offline

3. **Authorization Enforcement (Epic 10)**
   - Lateral movement requires human authorization
   - Pending authorizations are queued with timeout
   - Auto-pause after 24h pending (FR64)

## Implementation Status

These are **placeholder tests** that will be implemented in subsequent stories:
- Story 1.8: Scope Validator (Hard-Gate)
- Story 1.9/1.10: Kill Switch Core (Tri-Path)
- Epic 10: War Room TUI - Authorization & Control
