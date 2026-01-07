# Story 5.1: Intelligence Source Base Interface

**Status**: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **FIRST STORY IN EPIC 5:** This story establishes the foundational abstractions for the Vulnerability Intelligence Layer. All subsequent intelligence source implementations (5.2-5.6) depend on this interface.

## Story

As a **developer**,
I want **a base interface for all intelligence sources**,
So that **sources can be queried uniformly and new sources added easily**.

## Acceptance Criteria

1. **Given** I need to implement a new intelligence source
   **When** I extend `IntelligenceSource` base class
   **Then** I must implement `query(service: str, version: str) -> List[IntelResult]`
   **And** I must implement `health_check() -> bool`

2. **Given** an `IntelligenceSource` subclass
   **When** I access its `timeout` property
   **Then** it returns the configured timeout (default 5s per FR74)

3. **Given** an `IntelligenceSource` subclass
   **When** I access its `priority` property
   **Then** it returns an integer for result ranking

4. **Given** I create an `IntelResult` dataclass
   **When** I specify the required fields
   **Then** it includes: source, cve_id, severity, exploit_available, exploit_path, confidence

5. **Given** I have `IntelResult` objects from multiple sources
   **When** I sort them by `priority`
   **Then** CISA_KEV=1 < NVD_CRITICAL=2 < NVD_HIGH=3 < MSF=4 < NUCLEI=5 < EXPLOITDB=6

6. **Given** unit tests for the interface
   **When** tests run
   **Then** they verify interface contract and dataclass behavior

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Create intelligence module structure
  - [x] Create `src/cyberred/intelligence/__init__.py`
  - [x] Create `tests/unit/intelligence/__init__.py`
  - [x] Create `tests/integration/intelligence/__init__.py`

---

### Phase 1: Priority Constants [RED → GREEN → REFACTOR]

#### 1A: Define Priority Ranking Constants (AC: 5)

- [x] Task 1.1: Create priority constants
  - [x] **[RED]** Create `tests/unit/intelligence/test_base.py`
  - [x] **[RED]** Write failing test: `IntelPriority` constants exist with correct values
  - [x] **[GREEN]** Create `src/cyberred/intelligence/base.py`
  - [x] **[GREEN]** Define `IntelPriority` class with constants:
    ```python
    class IntelPriority:
        """Priority ranking for intelligence results.
        
        Lower numbers = higher priority (sorted ascending).
        Per architecture: CISA KEV > Critical CVE > High CVE > MSF > Nuclei > ExploitDB
        """
        CISA_KEV = 1
        NVD_CRITICAL = 2
        NVD_HIGH = 3
        METASPLOIT = 4
        NUCLEI = 5
        EXPLOITDB = 6
        NVD_MEDIUM = 7  # Lower priority than ExploitDB
    ```
  - [x] **[REFACTOR]** Add docstrings explaining priority ordering

---

### Phase 2: IntelResult Dataclass [RED → GREEN → REFACTOR]

#### 2A: Define IntelResult Dataclass (AC: 4, 5)

- [x] Task 2.1: Create IntelResult dataclass
  - [x] **[RED]** Write failing test: `IntelResult` accepts all required fields
  - [x] **[RED]** Write failing test: `IntelResult.to_json()` produces valid JSON
  - [x] **[RED]** Write failing test: `IntelResult.from_json()` reconstructs object
  - [x] **[GREEN]** Implement `IntelResult` dataclass:
    ```python
    @dataclass
    class IntelResult:
        """Intelligence query result.
        
        Represents a single vulnerability/exploit finding from an intelligence source.
        
        Attributes:
            source: Name of the intelligence source (e.g., "cisa_kev", "nvd", "metasploit")
            cve_id: CVE identifier (e.g., "CVE-2021-44228"), optional for non-CVE exploits
            severity: Severity level ("critical", "high", "medium", "low", "info")
            exploit_available: Whether a known exploit exists
            exploit_path: Path/reference to exploit (MSF module path, EDB ID, etc.)
            confidence: Query match confidence (0.0-1.0)
            priority: Result priority for sorting (from IntelPriority)
            metadata: Additional source-specific data (CVss scores, references, etc.)
        """
        source: str
        cve_id: Optional[str]
        severity: str
        exploit_available: bool
        exploit_path: Optional[str]
        confidence: float
        priority: int
        metadata: dict = field(default_factory=dict)
    ```
  - [x] **[GREEN]** Implement `to_json()` method
  - [x] **[GREEN]** Implement `from_json()` classmethod
  - [x] **[REFACTOR]** Add validation in `__post_init__`:
    - Severity must be in `VALID_SEVERITIES` (import from `cyberred.core.models`)
    - Confidence must be 0.0-1.0
    - Priority must be valid `IntelPriority` value
  - [x] **[REFACTOR]** Write tests for validation errors (invalid severity, confidence out-of-range)

---

### Phase 3: IntelligenceSource ABC [RED → GREEN → REFACTOR]

#### 3A: Define Abstract Base Class (AC: 1, 2, 3)

- [x] Task 3.1: Create IntelligenceSource ABC
  - [x] **[RED]** Write failing test: `IntelligenceSource` is abstract (cannot instantiate)
  - [x] **[RED]** Write failing test: subclass without `query()` raises TypeError
  - [x] **[RED]** Write failing test: subclass without `health_check()` raises TypeError
  - [x] **[GREEN]** Implement `IntelligenceSource` ABC:
    ```python
    from abc import ABC, abstractmethod
    
    class IntelligenceSource(ABC):
        """Abstract base class for intelligence sources.
        
        All intelligence sources (CISA KEV, NVD, ExploitDB, Nuclei, Metasploit)
        must implement this interface for uniform querying by the aggregator.
        
        Attributes:
            name: Human-readable source name
            timeout: Query timeout in seconds (default 5s per FR74)
            priority: Default priority for results from this source
        """
        
        def __init__(
            self,
            name: str,
            timeout: float = 5.0,
            priority: int = IntelPriority.EXPLOITDB,
        ) -> None:
            self._name = name
            self._timeout = timeout
            self._priority = priority
        
        @property
        def name(self) -> str:
            return self._name
        
        @property
        def timeout(self) -> float:
            return self._timeout
        
        @property
        def priority(self) -> int:
            return self._priority
        
        @abstractmethod
        async def query(self, service: str, version: str) -> List[IntelResult]:
            """Query this source for vulnerabilities affecting service/version.
            
            Args:
                service: Service name (e.g., "Apache", "OpenSSH", "vsftpd")
                version: Version string (e.g., "2.4.49", "8.2p1")
            
            Returns:
                List of IntelResult objects, sorted by priority (lowest first)
            """
            ...
        
        @abstractmethod
        async def health_check(self) -> bool:
            """Check if this source is available and responding.
            
            Returns:
                True if source is healthy, False otherwise
            """
            ...
    ```
  - [x] **[REFACTOR]** Add type hints and complete docstrings

#### 3B: Test Concrete Implementation Pattern (AC: 1)

- [x] Task 3.2: Create test fixture for subclass verification
  - [x] **[RED]** Write failing test: concrete subclass implementing both methods works
  - [x] **[GREEN]** Create `MockIntelligenceSource` in tests for verification
  - [x] **[GREEN]** Verify `query()` returns `List[IntelResult]`
  - [x] **[GREEN]** Verify `health_check()` returns `bool`
  - [x] **[REFACTOR]** Document expected implementation pattern in docstrings

---

### Phase 4: Module Exports [RED → GREEN → REFACTOR]

#### 4A: Configure Module Exports (AC: 6)

- [x] Task 4.1: Setup module __init__.py
  - [x] **[RED]** Write test: `from cyberred.intelligence import IntelligenceSource, IntelResult, IntelPriority` works
  - [x] **[GREEN]** Update `src/cyberred/intelligence/__init__.py` with exports
  - [x] **[REFACTOR]** Add module docstring

---

### Phase 5: Coverage & Documentation [BLUE]

- [x] Task 5.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/intelligence/test_base.py --cov=src/cyberred/intelligence --cov-report=term-missing`
  - [x] Ensure all branches covered (97% - abstract method stubs excluded)

- [x] Task 5.2: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 5.3: Final verification
  - [x] Verify all ACs met
  - [x] Run full test suite: `pytest tests/ -v --tb=short` (308 tests passed)
  - [x] Update story status to `review`

## Dev Notes

### Architecture Reference

From [architecture.md](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L838-L847):

```
├── intelligence/                 # Vulnerability Intelligence Layer
│   ├── __init__.py
│   ├── aggregator.py             # Unified query interface across sources
│   ├── cache.py                  # Redis-backed caching (offline-capable)
│   └── sources/
│       ├── cisa_kev.py           # CISA KEV JSON feed (priority)
│       ├── nvd.py                # NVD API via nvdlib
│       ├── exploitdb.py          # SearchSploit wrapper
│       ├── nuclei.py             # Nuclei template index
│       └── metasploit.py         # MSF module search (RPC)
```

### Intelligence Layer Design (from Architecture)

From [architecture.md#L235-L271](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L235-L271):

**Integration Pattern:**
1. Agent discovers service → calls `intelligence.query(service, version)`
2. Aggregator queries sources in parallel (5s timeout per source)
3. Results prioritized: CISA KEV > Critical CVE > High CVE > MSF module > Nuclei template > ExploitDB
4. Agent receives `IntelligenceResult` with prioritized exploit paths

**Stigmergic Publication:** Results are shared swarm-wide via `findings:{target_hash}:intel_enriched`

### Dataclass Pattern to Follow

Follow the existing pattern from [core/models.py](file:///root/red/src/cyberred/core/models.py):

```python
@dataclass
class IntelResult:
    """..."""
    # Required fields first
    source: str
    ...
    # Optional fields with defaults last
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Validation logic here
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: Union[str, dict]) -> "IntelResult":
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)
```

### Test Pattern to Follow

From [tests/unit/core/test_models.py](file:///root/red/tests/unit/core/test_models.py):

```python
class TestIntelResult:
    """Tests for IntelResult dataclass."""
    
    def test_intel_result_instantiation_all_fields(self) -> None:
        """IntelResult can be instantiated with all fields."""
        ...
    
    def test_intel_result_to_json(self) -> None:
        """IntelResult.to_json() produces valid JSON."""
        ...
```

### Key Learnings from Previous Stories

From [4-13-tool-execution-error-handling.md](file:///root/red/_bmad-output/implementation-artifacts/4-13-tool-execution-error-handling.md#L288-L297):

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit`
5. **Follow existing naming** — Match existing module patterns in `src/cyberred/`
6. **Async methods** — Intelligence queries should be async for parallel execution

### Dependencies

No new dependencies required. Story uses:
- `dataclasses` (stdlib)
- `abc` (stdlib)  
- `typing` (stdlib)
- `json` (stdlib)

**Code Reuse (CRITICAL):**
- Import `VALID_SEVERITIES` from `cyberred.core.models` — do NOT recreate

### Logging Guidance

Subclass implementations should use `structlog` for query logging:
```python
import structlog
log = structlog.get_logger()

async def query(self, service: str, version: str) -> List[IntelResult]:
    log.info("intelligence_query_start", source=self.name, service=service, version=version)
    # ... implementation
    log.info("intelligence_query_complete", source=self.name, result_count=len(results))
```

### Forward Reference

**Story 5.7 (Intelligence Aggregator)** will consume `IntelligenceSource` subclasses and call `query()` in parallel with `asyncio.gather()`. Design the ABC with parallel execution in mind.

### Project Structure Notes

**New Files to Create:**
```
src/cyberred/intelligence/
├── __init__.py          # Module exports
└── base.py              # IntelligenceSource ABC, IntelResult, IntelPriority

tests/unit/intelligence/
├── __init__.py
└── test_base.py         # Unit tests for base interface

tests/integration/intelligence/
└── __init__.py          # Prep for future integration tests
```

### References

- **Epic 5 Overview:** [epics-stories.md#L2056-L2098](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2056-L2098)
- **Story 5.1 Requirements:** [epics-stories.md#L2101-L2122](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2101-L2122)
- **Architecture - Intelligence Layer:** [architecture.md#L235-L273](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L235-L273)
- **Architecture - Project Structure:** [architecture.md#L838-L847](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L838-L847)
- **Existing Models Pattern:** [core/models.py](file:///root/red/src/cyberred/core/models.py)
- **Existing Tests Pattern:** [tests/unit/core/test_models.py](file:///root/red/tests/unit/core/test_models.py)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4 (Antigravity)

### Debug Log References

- Test run: 26 unit tests passed for intelligence module
- Coverage: 97.01% on `base.py` (lines 210, 219 are abstract method stubs)
- Full regression: 308 tests passed

### Completion Notes List

1. ✅ Created intelligence module directory structure with all `__init__.py` files
2. ✅ Implemented `IntelPriority` constants with correct priority ordering (CISA_KEV=1 through NVD_MEDIUM=7)
3. ✅ Implemented `IntelResult` dataclass with all 8 fields plus validation in `__post_init__`
4. ✅ Validation reuses `VALID_SEVERITIES` from `cyberred.core.models` - no duplication
5. ✅ Implemented `IntelligenceSource` ABC with `query()` and `health_check()` abstract methods
6. ✅ Default timeout 5.0s per FR74, configurable via constructor
7. ✅ Module exports configured in `__init__.py` with module docstring
8. ✅ Comprehensive test suite with 26 tests covering all ACs
9. ✅ All methods are async-ready for parallel execution in Story 5.7

### Change Log

- 2026-01-07: Story implemented - all phases complete, ready for review
- 2026-01-07: Code review complete - all issues fixed, status → done

### Senior Developer Review (AI)

**Reviewer:** Antigravity (Claude Sonnet 4)
**Date:** 2026-01-07
**Outcome:** ✅ APPROVED

**Findings Fixed:**
- M1: Staged all intelligence module files to git
- M2: Added design decision comment for priority 1-7 range in `_VALID_PRIORITIES`
- M3: Documented pytest marker pattern (informational)
- L1: Removed unused `List` import from `test_base.py`
- L2: Enhanced `IntelligenceSource` docstring with `super().__init__()` requirement

**Verification:**
- All 26 tests pass
- Coverage: 97.01% on `base.py` (abstract stubs excluded)
- All 6 ACs validated as implemented

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/intelligence/__init__.py` |
| [NEW] | `src/cyberred/intelligence/base.py` |
| [NEW] | `tests/unit/intelligence/__init__.py` |
| [NEW] | `tests/unit/intelligence/test_base.py` |
| [NEW] | `tests/integration/intelligence/__init__.py` |
