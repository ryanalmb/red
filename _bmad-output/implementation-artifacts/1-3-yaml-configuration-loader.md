# Story 1.3: YAML Configuration Loader

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **layered YAML configuration loading**,
So that **I can configure system, engagement, and runtime settings separately (FR46)**.

## Acceptance Criteria

1. **Given** `~/.cyber-red/config.yaml` exists
2. **When** I call `get_settings()`
3. **Then** system config is loaded from `~/.cyber-red/config.yaml`
4. **And** engagement config can override system config
5. **And** runtime config can override engagement config
6. **And** methods verify valid configuration via Pydantic validation
7. **And** `ConfigurationError` is raised for invalid YAML or schema violations
8. **And** missing optional keys use sensible defaults
9. **And** unit tests cover all config layers and validation

## Tasks / Subtasks

- [x] Create Configuration Module <!-- id: 0 -->
  - [x] Create `src/cyberred/core/config.py` (AC: #2)
  - [x] Define `SystemConfig` Pydantic model (`BaseModel`) with system settings:
    - [x] `redis` section (host, port, sentinel_hosts, master_name)
    - [x] `llm` section (providers, rate_limit, timeout)
    - [x] `storage` section (base_path, max_disk_percent)
    - [x] `security` section (pbkdf2_iterations, cert_validity_days)
    - [x] `logging` section (level, format, output)
    - [x] `metrics` section (enabled, port)
  - [x] Define `EngagementConfig` Pydantic model (`BaseModel`) with engagement settings:
    - [x] `name: str` - Engagement identifier
    - [x] `scope_path: str` - Path to scope definition file
    - [x] `objectives: List[str]` - Mission objectives
    - [x] `max_agents: int` - Agent ceiling for this engagement
    - [x] `auto_pause_hours: int` - Authorization timeout (default: 24)
  - [x] Define `RuntimeConfig` Pydantic model (`BaseModel`) for dynamic overrides:
    - [x] `scope_overrides: Optional[Dict]` - Runtime scope adjustments
    - [x] `rate_limit_override: Optional[int]` - Temporary rate limit changes
    - [x] `paused: bool` - Engagement pause state
  - [x] Define `Settings` class inheriting from `pydantic_settings.BaseSettings`
- [x] Implement Settings Management <!-- id: 1 -->
  - [x] Implement `Settings` class with layered loading logic (AC: #3, #4, #5)
    - [x] Load system defaults
    - [x] Load from `~/.cyber-red/config.yaml` (System)
    - [x] Load from `~/.cyber-red/engagements/{name}.yaml` (Engagement)
    - [x] Apply in-memory runtime overrides
  - [x] Implement `load_system_config(path: Path)` helper methods using `yaml.safe_load()`
  - [x] Implement `get_settings()` thread-safe singleton accessor (AC: #2)
    - [x] Ensure config is loaded once and cached
    - [x] Allow force-reload for testing
  - [x] Configure `Settings` to use `env_prefix="CYBERRED_"` for automatic env var loading
- [x] Implement Secrets and Env Loading <!-- id: 2 -->
  - [x] Use `python-dotenv` to load `.env` file before Settings initialization
  - [x] Map environment variables to Pydantic fields via `Field(alias=...)` or env naming:
    - [x] `CYBERRED_NIM_API_KEY` → `llm.nim_api_key`
    - [x] `CYBERRED_MSF_RPC_PASSWORD` → `intelligence.metasploit.password`
    - [x] `CYBERRED_NVD_API_KEY` → `intelligence.nvd_api_key`
    - [x] `CYBERRED_MASTER_PASSWORD` → `security.master_password`
  - [x] Validate required secrets are present via Pydantic validator
  - [x] Never log secret values (NFR18) - use `SecretStr` type for sensitive fields
- [x] Implement Default Values <!-- id: 3 -->
  - [x] Define defaults in Pydantic models (AC: #8):
    - [x] `redis.host`: "localhost"
    - [x] `redis.port`: 6379
    - [x] `llm.rate_limit`: 30 (RPM)
    - [x] `lmm.timeout`: 180 (seconds)
    - [x] `security.pbkdf2_iterations`: 100000
    - [x] `security.cert_validity_days`: 1
  - [x] Use Pydantic `Field(default=...)` or `default_factory`
- [x] Implement Validation Logic <!-- id: 4 -->
  - [x] Wrap Pydantic `ValidationError` in `ConfigurationError` (AC: #7)
    - [x] Provide user-friendly error messages from Pydantic errors
  - [x] Validate types and constraints via Pydantic types:
    - [x] `PositiveInt` for ports and limits
    - [x] `DirectoryPath`/`FilePath` for paths
    - [x] `AnyUrl` for URLs
- [x] Export and Integration <!-- id: 5 -->
  - [x] Update `src/cyberred/core/__init__.py` to export config components
  - [x] Export: `get_settings`, `Settings`, `SystemConfig`, `EngagementConfig`
- [x] Create Unit Tests <!-- id: 6 -->
  - [x] Create `tests/unit/core/test_config.py` (AC: #9)
  - [x] Test system config loading from valid YAML
  - [x] Test layered overrides (System < Engagement < Runtime)
  - [x] Test secrets loading from .env and env vars
  - [x] Test `ConfigurationError` wrapping of Pydantic validation errors
  - [x] Test sensible defaults
  - [x] Test singleton behavior of `get_settings()`
  - [x] Use `tmp_path` fixture for config files

## Dev Notes

### Architecture Context

This story implements the **layered configuration system** using **Pydantic** for robust validation, upgrading the architecture's "YAML + .env" pattern with a strongly-typed schema.

**Config Structure:**
```
~/.cyber-red/
├── config.yaml              # System configuration
├── .env                     # Secrets (gitignored)
└── engagements/
    └── ministry-2025.yaml   # Engagement-specific config
```

### Pydantic Implementation (Enhancement)

Instead of plain dataclasses, use `pydantic` and `pydantic-settings`:
- **Validation**: Free type checking, constraint validation, and path existence checks.
- **Env Vars**: Native support via `BaseSettings` and `env_prefix`.
- **Secrets**: Use `pydantic.SecretStr` for automatic redaction in `repr()`.

```python
from pydantic import BaseModel, Field, SecretStr, PositiveInt
from pydantic_settings import BaseSettings

class RedisConfig(BaseModel):
    host: str = "localhost"
    port: PositiveInt = 6379
    ...

class Settings(BaseSettings):
    redis: RedisConfig = Field(default_factory=RedisConfig)
    ...
```

### FR46 & NFR26 Requirements

- **Layered Config**: Handled by merging dictionaries loaded from YAML into the Pydantic models.
- **No Hardcoding**: All providers configured via files/env.
- **Runtime Overrides**: `Settings` instance can be modified in-memory (e.g., `settings.copy(update={...})`).

### Error Handling

Wrap Pydantic errors to maintain `core.exceptions` hierarchy:

```python
try:
    settings = Settings(...)
except ValidationError as e:
    raise ConfigurationError(f"Config validation failed: {e}") from e
```

### Dependencies (Pinned)

Add to `pyproject.toml` with explicit versions to prevent drift:
```toml
dependencies = [
    "pyyaml~=6.0",
    "python-dotenv~=1.0",
    "pydantic>=2.5.0,<3.0.0",
    "pydantic-settings>=2.1.0,<3.0.0"
]
```

### Naming Conventions

- Classes: PascalCase (`Settings`, `SystemConfig`)
- Functions: snake_case (`get_settings()`)
- Constants: UPPER_SNAKE_CASE

### Project Structure Notes

- Location: `src/cyberred/core/config.py`
- Test location: `tests/unit/core/test_config.py`
- Exports: `get_settings`, `Settings`

### Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

## Change Log

| Date | Change |
|------|--------|
| 2025-12-31 | Story created with comprehensive context from architecture.md and epics-stories.md |
| 2025-12-31 | **Optimization**: Switched to Pydantic for validation, added `pydantic-settings`, pinned dependencies, and unified `Settings` singleton pattern based on validation feedback. |
| 2025-12-31 | **Implementation**: Completed story. Added `pydantic` deps, implemented `config.py` with all models, validation, and layered logic. Added comprehensive unit tests with 100% coverage. |
| 2025-12-31 | **Code Review**: Automated adversarial review performed. Fixed 1 High (singleton arg handling), 1 Medium (runtime test gap), and 1 Low (alias) issue. Status -> done. |

## Senior Developer Review (AI)

**Reviewer:** Code Review Workflow
**Date:** 2025-12-31
**Outcome:** Approved (Auto-fixed)

**Findings & Fixes:**
1.  **High**: `get_settings()` ignored arguments when singleton was already initialized. Fixed by adding a warning and documenting `force_reload` requirement.
2.  **Medium**: Missing integration test for Runtime Overrides. Added `test_runtime_overrides_integration`.
3.  **Low**: `logging_config` vs `logging` aliasing. Added `logging` property alias to `Settings`.

**Coverage**: 100%
