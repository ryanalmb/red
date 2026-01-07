# Story 0.5: GitHub Actions CI Pipeline

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **self-hosted GitHub Actions with Docker support**,
So that **CI can run real Kali containers for integration tests**.

## Acceptance Criteria

1. **Given** Stories 0.1-0.4 are complete
2. **When** I push code to the repository
3. **Then** GitHub Actions workflow triggers on `.github/workflows/ci.yml`
4. **And** workflow runs on self-hosted runner with Docker (`runs-on: self-hosted`)
5. **And** unit tests run first (fast feedback)
6. **And** integration tests run with testcontainers
7. **And** safety tests run (marked as required)
8. **And** coverage gates are enforced (100% unit, 100% integration)
9. **And** workflow fails if any test fails or coverage drops

## Tasks / Subtasks

- [x] Create GitHub Actions Workflow File <!-- id: 0 -->
  - [x] Create `.github/workflows/ci.yml`
  - [x] Define `on: [push, pull_request]` triggers
  - [x] Configure `jobs` for `test` and `lint`
- [x] Configure CI Environment <!-- id: 1 -->
  - [x] Use `runs-on: self-hosted` to enable Docker-in-Docker for Kali containers
  - [x] Configure `actions/checkout@v4`
  - [x] Configure `actions/setup-python@v5` with python-version: '3.11'
  - [x] Configure dependency caching (`cache: 'pip'`)
- [x] Implement Test Strategies <!-- id: 2 -->
  - [x] Define step to install dependencies (`pip install .[dev]`)
  - [x] Define step to run unit tests (`pytest tests/unit`)
  - [x] Define step to run integration tests (`pytest tests/integration`)
  - [x] Define step to run safety tests (`pytest tests/safety`)
  - [x] Define step to check coverage (`pytest --cov ...`)
- [x] Verify Self-Hosted Runner Compatibility <!-- id: 3 -->
  - [x] Ensure Docker socket is accessible to the runner

## Senior Developer Review (AI)

- **Review Outcome**: Approved (Issues Fixed)
- **Review Date**: 2025-12-31

### Review Follow-ups (AI)

- [x] [AI-Review][High] Inefficient Test Execution: Refactor to combine coverage artifacts instead of re-running tests <!-- file:.github/workflows/ci.yml -->
- [x] [AI-Review][Medium] Missing Timeouts: Add `timeout-minutes` to all jobs <!-- file:.github/workflows/ci.yml -->
- [x] [AI-Review][Medium] Undocumented Changes: Add `.gitignore` to File List <!-- file:.gitignore -->
- [x] [AI-Review][Low] Security Hardening: Add `permissions: contents: read` <!-- file:.github/workflows/ci.yml -->

## Dev Notes

- **Self-Hosted Runner**: You MUST use `runs-on: self-hosted` for any job that requires Docker (integration tests, E2E). `ubuntu-latest` will not work with the `testcontainers-python` configuration in this environment.
- **Python Version**: Use Python 3.11+ as per architecture.
- **Dependencies**: Install using `pip install .[dev]` or `pip install -r requirements.txt` if available.
- **Coverage**: Identify coverage failure as a build failure.

### Project Structure Notes

- Workflow file location: `.github/workflows/ci.yml`
- Maintain standard directory structure.

### References

- [Source: docs/3-solutioning/epics-stories.md#Story 0.5: GitHub Actions CI Pipeline]
- [Source: docs/3-solutioning/architecture.md#Deployment & Configuration]

## Dev Agent Record

### Agent Model Used

Antigravity (Google DeepMind)

### Debug Log References

- YAML validation passed: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- All 18 tests pass: `pytest tests/unit tests/integration -v`

### Completion Notes List

- Created `.github/workflows/ci.yml` with comprehensive CI pipeline
- Configured 5 jobs: lint, unit-tests, integration-tests, safety-tests, coverage-gate
- All jobs use `runs-on: self-hosted` for Docker support (AC4)
- Lint job runs first with Ruff (linter + formatter) and MyPy (type checker)
- Unit tests run after lint with coverage reporting (AC5)
- Integration tests include Docker verification step (AC6)
- Safety tests run in parallel with integration tests (AC7)
- Coverage gate job runs `--cov-fail-under=100` enforcement (AC8, AC9)
- Uses `actions/checkout@v4` and `actions/setup-python@v5` with pip caching
- Coverage reports uploaded as artifacts for visibility
- **Code Review Fixes**:
  - Implemented `coverage combine` pattern to eliminate redundant test runs
  - Added `timeout-minutes` to all jobs (5-20 mins)
  - Added `permissions: contents: read` for security
  - Updated File List to include `.gitignore`

### File List

- `.github/workflows/ci.yml` (NEW) - Comprehensive CI pipeline with self-hosted runner
- `.gitignore` (MODIFIED) - Updated coverage artifact exclusions

## Change Log

| Date | Change |
|------|--------|
| 2025-12-31 | Created ci.yml with self-hosted runner, lint job, test jobs (unit/integration/safety), and 100% coverage gate |
| 2025-12-31 | Refactored ci.yml for efficient coverage combining, added timeouts, and security permissions (Review) |
