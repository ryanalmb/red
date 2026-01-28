# Story 8.9: Finding Aggregation for Director Input

<!-- CRITICAL: Development Standards for Epic 8 and Beyond -->
<!-- ====================================================== -->
<!-- 1. STRICT TDD: Write tests BEFORE implementation code   -->
<!-- 2. 100% CODE COVERAGE: All new code must have tests     -->
<!-- 3. NO UNTESTED CODE: Every branch, every edge case      -->
<!-- 4. VERIFY INTEGRATION: Test against real APIs when keys -->
<!--    are available, not just mocks                        -->
<!-- ====================================================== -->

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Director Ensemble**,
I want **aggregated findings as input for strategy synthesis**,
So that **Director sees the complete picture, not individual events**.

## Acceptance Criteria

1. **Given** Epic 7 (agents publishing findings) is complete
   - **When** re-plan trigger fires
   - **Then** aggregator collects findings since last Director cycle

2. **Given** findings are collected from multiple agents
   - **When** aggregation is performed
   - **Then** findings are deduplicated by target + type
   - **And** duplicate findings are merged (preserving earliest timestamp)

3. **Given** findings span multiple categories
   - **When** aggregation is performed
   - **Then** findings are grouped by category (recon, exploit, postex)
   - **And** each category maintains its own findings list

4. **Given** aggregation completes
   - **When** summary is generated
   - **Then** aggregator produces summary statistics:
     - Total finding count
     - Count per severity (critical, high, medium, low, info)
     - Count per category (recon, exploit, postex)
   - **And** statistics include timestamps (window start, window end)

5. **Given** large number of findings in cycle
   - **When** findings exceed max_findings_per_cycle (default 100)
   - **Then** findings are prioritized by severity (critical > high > medium > low > info)
   - **And** within same severity, prioritize by recency (newest first)
   - **And** excess findings are dropped with warning logged

6. **Given** aggregated findings are ready
   - **When** summary is formatted for Director prompt
   - **Then** output is structured for LLM consumption
   - **And** summary includes actionable context per category
   - **And** format is consistent with Director Ensemble input expectations

7. **Given** aggregator is tested
   - **When** unit tests run
   - **Then** all aggregation logic is verified:
     - Deduplication by target + type
     - Grouping by category
     - Summary statistics calculation
     - Priority ordering
     - Max findings limit enforcement

## Tasks / Subtasks

- [x] Task 1: Create `orchestration/aggregator.py` module (AC: 1-6)
  - [x] 1.1: Define `FindingCategory` enum (RECON, EXPLOIT, POSTEX, OTHER)
  - [x] 1.2: Define `FindingSeverity` enum with ordering (CRITICAL, HIGH, MEDIUM, LOW, INFO)
  - [x] 1.3: Define `AggregatedFinding` dataclass with target, type, severity, category, timestamp, metadata
  - [x] 1.4: Define `AggregationSummary` dataclass with statistics and formatted output
  - [x] 1.5: Define `AggregatorConfig` dataclass with max_findings_per_cycle, dedup_enabled flags

- [x] Task 2: Implement FindingAggregator class core (AC: 1-2)
  - [x] 2.1: Implement `__init__()` with config and window tracking
  - [x] 2.2: Implement `add_finding()` method for incremental collection
  - [x] 2.3: Implement `_deduplicate()` method using target + type as key
  - [x] 2.4: Track window start/end timestamps for cycle boundaries
  - [x] 2.5: Implement `reset_window()` for new cycle initialization

- [x] Task 3: Implement category grouping (AC: 3)
  - [x] 3.1: Implement `_categorize_finding()` to assign category based on finding type
  - [x] 3.2: Map finding types to categories:
    - RECON: port_scan, service_detection, subdomain, web_tech, dns_record
    - EXPLOIT: vulnerability, cve, sqli, xss, rce, lfi, ssrf
    - POSTEX: credential, shell, pivot, persistence, exfil
    - OTHER: anything not matching above
  - [x] 3.3: Implement `get_by_category()` to retrieve findings per category
  - [x] 3.4: Store findings in category-indexed structure

- [x] Task 4: Implement summary statistics (AC: 4)
  - [x] 4.1: Implement `get_summary()` method returning AggregationSummary
  - [x] 4.2: Calculate counts per severity (critical, high, medium, low, info)
  - [x] 4.3: Calculate counts per category (recon, exploit, postex, other)
  - [x] 4.4: Include window timestamps (start, end, duration)
  - [x] 4.5: Include total finding count (pre and post dedup)

- [x] Task 5: Implement priority ordering and limiting (AC: 5)
  - [x] 5.1: Implement `_prioritize()` method with severity-first ordering
  - [x] 5.2: Define severity ordering: CRITICAL=0, HIGH=1, MEDIUM=2, LOW=3, INFO=4
  - [x] 5.3: Secondary sort by timestamp (newest first within same severity)
  - [x] 5.4: Implement `_enforce_limit()` to cap at max_findings_per_cycle
  - [x] 5.5: Log warning when findings are dropped due to limit
  - [x] 5.6: Track dropped_count in summary

- [x] Task 6: Implement Director prompt formatting (AC: 6)
  - [x] 6.1: Implement `format_for_director()` method returning structured string
  - [x] 6.2: Format includes summary statistics section
  - [x] 6.3: Format includes per-category findings with key details
  - [x] 6.4: Format includes actionable context (e.g., "3 critical vulnerabilities found on target X")
  - [x] 6.5: Keep format concise to fit within LLM context limits

- [x] Task 7: Integrate with EventBus for finding collection (AC: 1)
  - [x] 7.1: Subscribe to `findings:{engagement_id}:*` pattern
  - [x] 7.2: Parse finding events into AggregatedFinding instances
  - [x] 7.3: Handle malformed finding events gracefully (log + skip)
  - [x] 7.4: Implement `start()` and `stop()` lifecycle methods

- [x] Task 8: Integrate with ReplanTriggerManager (AC: 1)
  - [x] 8.1: Implement `get_findings_since()` for windowed retrieval
  - [x] 8.2: Accept optional timestamp to filter findings
  - [x] 8.3: Return aggregated, deduplicated, prioritized findings
  - [x] 8.4: Clear window after retrieval (prepare for next cycle)

- [x] Task 9: Write unit tests (AC: 1-7)
  - [x] 9.1: Test `FindingCategory` enum completeness
  - [x] 9.2: Test `FindingSeverity` enum ordering
  - [x] 9.3: Test `AggregatedFinding` dataclass creation and comparison
  - [x] 9.4: Test `AggregationSummary` dataclass statistics
  - [x] 9.5: Test deduplication by target + type
  - [x] 9.6: Test category assignment for all finding types
  - [x] 9.7: Test summary statistics calculation
  - [x] 9.8: Test priority ordering (severity then recency)
  - [x] 9.9: Test max_findings limit enforcement
  - [x] 9.10: Test Director prompt formatting output

- [x] Task 10: Write integration tests (AC: 1-7)
  - [x] 10.1: Test end-to-end finding collection via EventBus
  - [x] 10.2: Test aggregation with real finding events
  - [x] 10.3: Test integration with ReplanTriggerManager callback
  - [x] 10.4: Test window reset across Director cycles
  - [x] 10.5: Test concurrent finding addition
  - [x] 10.6: Test graceful handling of malformed events

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Per Architecture Document (`_bmad-output/planning-artifacts/architecture.md`):**

1. **Feedback Loop & Re-Planning** (lines 316-340):
   - **Cycle:** Agents execute → Publish findings → Aggregator batches → Director re-plans → Strategy published → Agents adapt
   - Aggregator sits between agents and Director in the feedback loop
   - Must batch findings efficiently to prevent Director context overflow

2. **Stigmergic Publication Pattern** (line 271):
   - Findings published to `findings:{target_hash}:{type}` topics
   - Aggregator subscribes to `findings:*` for comprehensive collection

3. **Director Ensemble Integration** (Story 8.1, 8.5):
   - Use `DirectorEnsemble` from `cyberred/llm/ensemble.py` for synthesis
   - Aggregated findings become input for `query_all()` context
   - 180s aggregate timeout for ensemble

4. **File Location** (architecture line 807):
   - Module location: `src/cyberred/orchestration/aggregator.py`

5. **Performance Requirements**:
   - Max 100 findings per cycle (configurable) - prevents context overflow
   - Must handle 10K agents publishing findings concurrently
   - O(1) deduplication using hash-based lookup

### Source Tree Components to Touch

```
src/cyberred/orchestration/
├── __init__.py              # Add FindingAggregator exports
├── aggregator.py            # NEW: Finding aggregation module
└── replan_triggers.py       # Integration point (uses aggregator)

src/cyberred/core/
└── events.py                # EventBus subscription for findings

tests/unit/orchestration/
└── test_aggregator.py       # NEW: Unit tests

tests/integration/orchestration/
└── test_aggregator_integration.py  # NEW: Integration tests
```

### Key Implementation Details

#### FindingCategory Enum

```python
from enum import Enum

class FindingCategory(Enum):
    """Categories for grouping findings."""
    RECON = "recon"           # Discovery/enumeration findings
    EXPLOIT = "exploit"       # Vulnerability/exploitation findings
    POSTEX = "postex"         # Post-exploitation findings
    OTHER = "other"           # Uncategorized findings
```

#### FindingSeverity Enum

```python
class FindingSeverity(Enum):
    """Severity levels with priority ordering."""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4      # Lowest priority
    
    def __lt__(self, other: "FindingSeverity") -> bool:
        """Enable severity comparison for sorting."""
        return self.value < other.value
```

#### AggregatedFinding Dataclass

```python
@dataclass
class AggregatedFinding:
    """A finding aggregated from agent publications.
    
    Attributes:
        target: Target identifier (IP, hostname, URL).
        finding_type: Type of finding (e.g., "sqli", "port_scan").
        severity: Severity level.
        category: Category for grouping.
        timestamp: When finding was discovered.
        agent_id: Agent that discovered the finding.
        metadata: Additional context (cve_id, technique, etc).
    """
    target: str
    finding_type: str
    severity: FindingSeverity
    category: FindingCategory
    timestamp: float
    agent_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def dedup_key(self) -> str:
        """Key for deduplication (target + type)."""
        return f"{self.target}:{self.finding_type}"
```

#### AggregationSummary Dataclass

```python
@dataclass
class AggregationSummary:
    """Summary of aggregated findings for Director input.
    
    Attributes:
        total_count: Total findings after deduplication.
        raw_count: Total findings before deduplication.
        dropped_count: Findings dropped due to limit.
        by_severity: Count per severity level.
        by_category: Count per category.
        window_start: Start of aggregation window.
        window_end: End of aggregation window.
        findings: Prioritized list of findings.
    """
    total_count: int
    raw_count: int
    dropped_count: int
    by_severity: Dict[FindingSeverity, int]
    by_category: Dict[FindingCategory, int]
    window_start: float
    window_end: float
    findings: List[AggregatedFinding]
```

#### AggregatorConfig Dataclass

```python
@dataclass
class AggregatorConfig:
    """Configuration for FindingAggregator.
    
    Attributes:
        max_findings_per_cycle: Maximum findings to include (default 100).
        dedup_enabled: Whether to deduplicate findings (default True).
        include_info_severity: Whether to include INFO severity (default False).
    """
    max_findings_per_cycle: int = 100
    dedup_enabled: bool = True
    include_info_severity: bool = False
```

#### FindingAggregator Class Structure

```python
class FindingAggregator:
    """Aggregates findings from agents for Director input.
    
    Collects findings published by agents, deduplicates, categorizes,
    and prioritizes them for Director Ensemble consumption.
    
    Example:
        aggregator = FindingAggregator(
            event_bus=event_bus,
            config=config,
        )
        await aggregator.start(engagement_id)
        # ... agents publish findings ...
        summary = aggregator.get_summary()
        director_prompt = aggregator.format_for_director()
        aggregator.reset_window()
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        config: Optional[AggregatorConfig] = None,
    ) -> None:
        """Initialize FindingAggregator.
        
        Args:
            event_bus: EventBus for subscribing to findings (optional for testing).
            config: Optional aggregator configuration.
        """
        self._event_bus = event_bus
        self._config = config or AggregatorConfig()
        self._findings: Dict[str, AggregatedFinding] = {}  # dedup_key -> finding
        self._window_start: float = 0.0
        self._window_end: float = 0.0
        self._engagement_id: Optional[str] = None
        self._running = False
        self._log = structlog.get_logger().bind(component="aggregator")
    
    async def start(self, engagement_id: str) -> None:
        """Start collecting findings for engagement."""
        pass
    
    async def stop(self) -> None:
        """Stop collecting and cleanup subscriptions."""
        pass
    
    def add_finding(self, finding: AggregatedFinding) -> bool:
        """Add a finding to the aggregation.
        
        Returns:
            True if finding was added, False if deduplicated.
        """
        pass
    
    def get_summary(self) -> AggregationSummary:
        """Get aggregation summary with statistics."""
        pass
    
    def format_for_director(self) -> str:
        """Format aggregated findings for Director prompt."""
        pass
    
    def reset_window(self) -> None:
        """Reset aggregation window for new cycle."""
        pass
    
    def get_findings_since(self, timestamp: Optional[float] = None) -> AggregationSummary:
        """Get findings since timestamp (for ReplanTriggerManager)."""
        pass
    
    def _categorize(self, finding_type: str) -> FindingCategory:
        """Categorize finding based on type."""
        pass
    
    def _prioritize(self, findings: List[AggregatedFinding]) -> List[AggregatedFinding]:
        """Sort findings by severity then recency."""
        pass
    
    async def _handle_finding_event(self, event: Dict[str, Any]) -> None:
        """Handle finding event from EventBus."""
        pass
```

#### Finding Type to Category Mapping

```python
FINDING_TYPE_CATEGORIES: Dict[str, FindingCategory] = {
    # RECON findings
    "port_scan": FindingCategory.RECON,
    "service_detection": FindingCategory.RECON,
    "subdomain": FindingCategory.RECON,
    "web_tech": FindingCategory.RECON,
    "dns_record": FindingCategory.RECON,
    "banner_grab": FindingCategory.RECON,
    "ssl_cert": FindingCategory.RECON,
    "waf_detect": FindingCategory.RECON,
    
    # EXPLOIT findings
    "vulnerability": FindingCategory.EXPLOIT,
    "cve": FindingCategory.EXPLOIT,
    "sqli": FindingCategory.EXPLOIT,
    "xss": FindingCategory.EXPLOIT,
    "rce": FindingCategory.EXPLOIT,
    "lfi": FindingCategory.EXPLOIT,
    "ssrf": FindingCategory.EXPLOIT,
    "auth_bypass": FindingCategory.EXPLOIT,
    "idor": FindingCategory.EXPLOIT,
    
    # POSTEX findings
    "credential": FindingCategory.POSTEX,
    "shell": FindingCategory.POSTEX,
    "pivot": FindingCategory.POSTEX,
    "persistence": FindingCategory.POSTEX,
    "exfil": FindingCategory.POSTEX,
    "privesc": FindingCategory.POSTEX,
    "lateral_move": FindingCategory.POSTEX,
}
```

#### Director Prompt Format Example

```python
def format_for_director(self) -> str:
    """Format aggregated findings for Director prompt.
    
    Example output:
    ```
    ## Findings Summary (Last 5 min)
    
    **Statistics:**
    - Total: 23 findings (47 raw, 24 deduplicated)
    - Critical: 2, High: 5, Medium: 10, Low: 6
    - Recon: 8, Exploit: 12, Post-Ex: 3
    
    **Critical Findings:**
    1. [EXPLOIT] CVE-2024-1234 on 10.0.0.5:8080 (SQLi)
    2. [EXPLOIT] CVE-2024-5678 on 10.0.0.10:443 (RCE)
    
    **High Findings:**
    1. [EXPLOIT] XSS on 10.0.0.5:8080/search
    2. [RECON] Admin panel exposed on 10.0.0.10:443/admin
    ...
    
    **Actionable Context:**
    - 2 critical vulnerabilities on 10.0.0.5 suggest immediate exploitation focus
    - Post-exploitation opportunities available via shell on 10.0.0.10
    ```
    """
    pass
```

### Testing Requirements

1. **Unit Tests** (`tests/unit/orchestration/test_aggregator.py`):
   - Test enum completeness and ordering
   - Test dataclass creation and comparison
   - Test deduplication logic (same key → merge)
   - Test category assignment for all finding types
   - Test summary statistics accuracy
   - Test priority ordering (severity first, then recency)
   - Test max_findings limit and dropped count
   - Test Director prompt formatting

2. **Integration Tests** (`tests/integration/orchestration/test_aggregator_integration.py`):
   - Test EventBus subscription and finding collection
   - Test concurrent finding addition (thread safety)
   - Test integration with ReplanTriggerManager
   - Test window reset across cycles
   - Test malformed event handling
   - Test end-to-end Director input flow

### Previous Story Intelligence

From **Story 8.8** (Re-Plan Triggers):
- `ReplanTriggerManager` uses aggregator via `get_findings_window()` method
- Aggregator provides findings batch when trigger fires
- Window tracking: `last_trigger_time` marks cycle boundary
- Task 8 in 8.8 specifically references integration with `orchestration/aggregator.py`

From **Story 8.1** (Director Ensemble Base Architecture):
- `DirectorEnsemble` class expects structured input for synthesis
- Use aggregated findings as context for `query_all()`
- 180s aggregate timeout for ensemble

From **Story 8.5** (Strategy Synthesis Engine):
- `SynthesizedStrategy` output format
- Synthesis considers findings for strategic recommendations

From **Story 3.3** (Event Bus):
- `EventBus.subscribe()` for pattern-based subscription
- `findings:{engagement_id}:*` pattern for comprehensive collection

From **Story 7.1-7.25** (Agents):
- Agents publish findings to `findings:{target_hash}:{type}` topics
- Finding format includes: target, type, severity, cve_id, technique, details

### Dependencies

- **Story 8.1-8.5:** Director Ensemble and Strategy Synthesis (COMPLETE)
- **Story 8.8:** Re-Plan Triggers (COMPLETE - consumes this aggregator)
- **Story 3.3-3.4:** Event Bus (COMPLETE)
- **Story 7.x:** Agent finding publication (COMPLETE)

### Project Structure Notes

- **Alignment:** Module `orchestration/aggregator.py` follows existing `orchestration/` structure
- **Naming:** `FindingAggregator` follows existing `*Aggregator` naming patterns in intelligence module
- **Imports:** Use existing `EventBus` from `cyberred.core.events`
- **Export:** Add exports to `orchestration/__init__.py`
- **Conflict:** Note that `intelligence/aggregator.py` exists for vulnerability intelligence - this is a different aggregator for findings

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Feedback-Loop-Re-Planning] - Aggregator role in feedback loop
- [Source: _bmad-output/planning-artifacts/architecture.md#Stigmergic-Publication-Pattern] - Finding topic patterns
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-8.9] - Story requirements
- [Source: _bmad-output/implementation-artifacts/8-8-re-plan-triggers.md] - ReplanTriggerManager integration
- [Source: _bmad-output/implementation-artifacts/8-1-director-ensemble-base-architecture.md] - Ensemble input expectations
- [Source: src/cyberred/orchestration/replan_triggers.py] - Trigger manager using aggregator
- [Source: src/cyberred/core/events.py] - EventBus subscription patterns
- [Source: src/cyberred/intelligence/aggregator.py] - Existing aggregator pattern (different domain)

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A

### Completion Notes List

- Implemented FindingAggregator module with full TDD approach
- All 86 tests pass (74 unit + 12 integration)
- 100% code coverage on orchestration/aggregator.py
- Exports added to orchestration/__init__.py
- Deduplication by target+type preserves earliest timestamp
- Priority ordering: severity first (CRITICAL=0), then recency (newest first)
- Director prompt formatting includes statistics, critical/high findings, actionable context
- EventBus integration with pattern subscription and graceful error handling

### File List

- src/cyberred/orchestration/aggregator.py (NEW)
- src/cyberred/orchestration/__init__.py (MODIFIED - added exports)
- tests/unit/orchestration/test_aggregator.py (NEW)
- tests/integration/orchestration/test_aggregator_integration.py (NEW)

## Senior Developer Review (AI)

**Reviewer:** Rovo Dev  
**Date:** 2026-01-28  
**Outcome:** ✅ APPROVED (after fixes)

### Issues Found and Fixed

| # | Severity | Issue | Resolution |
|---|----------|-------|------------|
| 1 | **HIGH** | `include_info_severity` config flag defined but never used in code | Implemented filtering in `add_finding()` method; changed default to `True` for backward compatibility |
| 2 | **HIGH** | `format_for_director()` showed incorrect "deduplicated" count when findings were dropped (raw - total conflated dedup + dropped) | Fixed calculation: now shows accurate `dedup_count = raw - unique_before_drop` and separately shows dropped count |
| 3 | **MEDIUM** | `format_for_director()` didn't show dropped findings count to Director | Added conditional display: "X dropped due to limit" when dropped_count > 0 |
| 4 | **MEDIUM** | Actionable Context section was empty when no CRITICAL findings or POSTEX | Enhanced logic: now shows HIGH severity findings, then EXPLOIT count, then RECON count, or general findings count as fallback |
| 5 | **LOW** | Missing tests for actionable context formatting variations | Added `TestActionableContext` test class with 4 test cases |
| 6 | **LOW** | Missing tests for `include_info_severity` config behavior | Added `TestIncludeInfoSeverityConfig` test class with 3 test cases |

### Tests Added

- `TestIncludeInfoSeverityConfig` (3 tests) - Tests INFO severity filtering behavior
- `TestActionableContext` (4 tests) - Tests actionable context with various severity/category combinations
- `TestDedupDropStatistics` (3 tests) - Tests correct dedup/drop count display in Director prompt

### Verification

- All 96 tests pass (84 unit + 12 integration)
- 100% code coverage on `src/cyberred/orchestration/aggregator.py`
- All Acceptance Criteria verified implemented
