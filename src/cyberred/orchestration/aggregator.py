"""Finding Aggregation for Director Input.

Story 8.9: Finding Aggregation for Director Input.

This module provides the FindingAggregator class that collects, deduplicates,
categorizes, and prioritizes findings from agents for Director Ensemble
consumption.

Key Features:
- Deduplication by target + type (preserves earliest timestamp)
- Category grouping (RECON, EXPLOIT, POSTEX, OTHER)
- Priority ordering (severity first, then recency)
- Max findings limit with severity-based prioritization
- Director prompt formatting for LLM consumption
- EventBus integration for finding collection

Classes:
    FindingCategory: Categories for grouping findings
    FindingSeverity: Severity levels with priority ordering
    AggregatedFinding: A finding aggregated from agent publications
    AggregationSummary: Summary of aggregated findings
    AggregatorConfig: Configuration for FindingAggregator
    FindingAggregator: Aggregates findings from agents for Director input

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

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from cyberred.core.events import EventBus

log = structlog.get_logger()

__all__ = [
    "FindingCategory",
    "FindingSeverity",
    "AggregatedFinding",
    "AggregationSummary",
    "AggregatorConfig",
    "FindingAggregator",
    "FINDING_TYPE_CATEGORIES",
]


# =============================================================================
# Enums (Task 1.1, 1.2)
# =============================================================================


class FindingCategory(Enum):
    """Categories for grouping findings.
    
    Attributes:
        RECON: Discovery/enumeration findings
        EXPLOIT: Vulnerability/exploitation findings
        POSTEX: Post-exploitation findings
        OTHER: Uncategorized findings
    """
    RECON = "recon"
    EXPLOIT = "exploit"
    POSTEX = "postex"
    OTHER = "other"


class FindingSeverity(Enum):
    """Severity levels with priority ordering.
    
    Lower value = higher priority for sorting.
    
    Attributes:
        CRITICAL: Highest priority (value 0)
        HIGH: High priority (value 1)
        MEDIUM: Medium priority (value 2)
        LOW: Low priority (value 3)
        INFO: Lowest priority (value 4)
    """
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4
    
    def __lt__(self, other: "FindingSeverity") -> bool:
        """Enable severity comparison for sorting."""
        if not isinstance(other, FindingSeverity):
            return NotImplemented
        return self.value < other.value
    
    def __le__(self, other: "FindingSeverity") -> bool:
        """Enable <= comparison."""
        if not isinstance(other, FindingSeverity):
            return NotImplemented
        return self.value <= other.value
    
    def __gt__(self, other: "FindingSeverity") -> bool:
        """Enable > comparison."""
        if not isinstance(other, FindingSeverity):
            return NotImplemented
        return self.value > other.value
    
    def __ge__(self, other: "FindingSeverity") -> bool:
        """Enable >= comparison."""
        if not isinstance(other, FindingSeverity):
            return NotImplemented
        return self.value >= other.value


# =============================================================================
# Finding Type to Category Mapping (Task 3.2)
# =============================================================================


FINDING_TYPE_CATEGORIES: Dict[str, FindingCategory] = {
    # RECON findings
    "port_scan": FindingCategory.RECON,
    "service_detection": FindingCategory.RECON,
    "subdomain": FindingCategory.RECON,
    "web_tech": FindingCategory.RECON,
    "dns_record": FindingCategory.RECON,
    "banner_grab": FindingCategory.RECON,
    "ssl_cert": FindingCategory.RECON,
    "host_status": FindingCategory.RECON,
    "os_detection": FindingCategory.RECON,
    "open_port": FindingCategory.RECON,
    "nse_script": FindingCategory.RECON,
    "directory": FindingCategory.RECON,
    "file": FindingCategory.RECON,
    "recon": FindingCategory.RECON,
    "waf_detect": FindingCategory.RECON,
    "waf": FindingCategory.RECON,
    "web_tech": FindingCategory.RECON,
    
    # EXPLOIT findings
    "vulnerability": FindingCategory.EXPLOIT,
    "cve": FindingCategory.EXPLOIT,
    "sqli": FindingCategory.EXPLOIT,
    "sqli_db": FindingCategory.EXPLOIT,
    "sqli_table": FindingCategory.EXPLOIT,
    "sqli_column": FindingCategory.EXPLOIT,
    "xss": FindingCategory.EXPLOIT,
    "rce": FindingCategory.EXPLOIT,
    "lfi": FindingCategory.EXPLOIT,
    "ssrf": FindingCategory.EXPLOIT,
    "auth_bypass": FindingCategory.EXPLOIT,
    "idor": FindingCategory.EXPLOIT,
    "exploit": FindingCategory.EXPLOIT,
    "web_vuln": FindingCategory.EXPLOIT,
    
    # POSTEX findings
    "ad": FindingCategory.POSTEX,
    "domainadmin": FindingCategory.POSTEX,
    "forensics": FindingCategory.POSTEX,
    "postex": FindingCategory.POSTEX,
    "privesc_vector": FindingCategory.POSTEX,
    "wireless": FindingCategory.POSTEX,
    "credential": FindingCategory.POSTEX,
    "shell": FindingCategory.POSTEX,
    "pivot": FindingCategory.POSTEX,
    "persistence": FindingCategory.POSTEX,
    "exfil": FindingCategory.POSTEX,
    "privesc": FindingCategory.POSTEX,
    "lateral_move": FindingCategory.POSTEX,
}


# =============================================================================
# Data Classes (Tasks 1.3, 1.4, 1.5)
# =============================================================================


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
    outcome_status: str = "attempted"
    
    @property
    def dedup_key(self) -> str:
        """Key for deduplication (target + type + tool + evidence hash)."""
        tool = str(self.metadata.get("tool", "")).strip().lower()
        evidence = str(
            self.metadata.get("raw_evidence")
            or self.metadata.get("evidence")
            or ""
        ).strip()
        if not tool and not evidence:
            return f"{self.target}:{self.finding_type}"

        evidence_hash = hashlib.sha1(evidence.encode("utf-8")).hexdigest()[:12] if evidence else "na"
        if tool:
            return f"{self.target}:{self.finding_type}:{tool}:{evidence_hash}"
        return f"{self.target}:{self.finding_type}:{evidence_hash}"


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
    by_outcome: Dict[str, int] = field(default_factory=dict)


@dataclass
class AggregatorConfig:
    """Configuration for FindingAggregator.
    
    Attributes:
        max_findings_per_cycle: Maximum findings to include (default 100).
        dedup_enabled: Whether to deduplicate findings (default True).
        include_info_severity: Whether to include INFO severity (default True).
        rolling_memory_enabled: Keep carry-forward findings across cycles.
        rolling_window_seconds: Retention window for carry-forward findings.
        rolling_max_findings: Max carry-forward findings retained.
    """
    max_findings_per_cycle: int = 100
    dedup_enabled: bool = True
    include_info_severity: bool = True
    rolling_memory_enabled: bool = True
    rolling_window_seconds: int = 1800
    rolling_max_findings: int = 300


# =============================================================================
# FindingAggregator Class (Tasks 2-8)
# =============================================================================


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
        event_bus: Optional["EventBus"] = None,
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
        self._findings_list: List[AggregatedFinding] = []  # For non-dedup mode
        self._rolling_findings: Dict[str, AggregatedFinding] = {}  # carry-forward memory
        self._raw_count = 0
        self._outcome_totals: Dict[str, int] = defaultdict(int)
        self._window_start: float = time.time()
        self._window_end: float = time.time()
        self._engagement_id: Optional[str] = None
        self._running = False
        self._subscriptions: List[Any] = []
        self._log = log.bind(component="aggregator")

    # =========================================================================
    # Lifecycle Methods (Task 7)
    # =========================================================================

    async def start(self, engagement_id: str) -> None:
        """Start collecting findings for engagement.
        
        Args:
            engagement_id: The engagement to collect findings for.
        """
        self._engagement_id = engagement_id
        self._running = True
        self._window_start = time.time()
        self._window_end = time.time()
        
        self._log.info(
            "aggregator_started",
            engagement_id=engagement_id,
            max_findings=self._config.max_findings_per_cycle,
        )
        
        # Set up EventBus subscriptions if available
        if self._event_bus:
            await self._setup_subscriptions()

    async def stop(self) -> None:
        """Stop collecting and cleanup subscriptions."""
        self._running = False
        
        # Cleanup subscriptions (supports cancel()/unsubscribe() handles)
        for task in self._subscriptions:
            try:
                cancel_fn = getattr(task, "cancel", None)
                unsubscribe_fn = getattr(task, "unsubscribe", None)
                if callable(cancel_fn):
                    result = cancel_fn()
                    if asyncio.iscoroutine(result):
                        await result
                elif callable(unsubscribe_fn):
                    result = unsubscribe_fn()
                    if asyncio.iscoroutine(result):
                        await result
            except Exception as e:
                self._log.warning(
                    "subscription_cancel_error",
                    error=str(e),
                )
        self._subscriptions.clear()
        
        self._log.info(
            "aggregator_stopped",
            engagement_id=self._engagement_id,
            total_findings=len(self._findings),
        )

    # =========================================================================
    # Core Methods (Tasks 2-4)
    # =========================================================================

    def add_finding(self, finding: AggregatedFinding) -> bool:
        """Add a finding to the aggregation.
        
        Args:
            finding: The finding to add.
        
        Returns:
            True if finding was added, False if deduplicated or filtered.
        """
        self._raw_count += 1
        self._window_end = max(self._window_end, finding.timestamp)
        
        # Filter INFO severity if not included
        if not self._config.include_info_severity and finding.severity == FindingSeverity.INFO:
            return False
        
        if not self._config.dedup_enabled:
            # No dedup - just append
            self._findings_list.append(finding)
            self._remember_rolling(finding)
            return True
        
        dedup_key = finding.dedup_key
        
        if dedup_key in self._findings:
            # Duplicate - preserve earliest timestamp (AC 2)
            existing = self._findings[dedup_key]
            if finding.timestamp < existing.timestamp:
                self._findings[dedup_key] = AggregatedFinding(
                    target=existing.target,
                    finding_type=existing.finding_type,
                    severity=existing.severity,
                    category=existing.category,
                    timestamp=finding.timestamp,  # Earlier timestamp
                    agent_id=existing.agent_id,
                    metadata=existing.metadata,
                )
            self._remember_rolling(finding)
            return False
        
        # New finding
        self._findings[dedup_key] = finding
        self._remember_rolling(finding)
        return True

    def _remember_rolling(self, finding: AggregatedFinding) -> None:
        """Remember finding in rolling carry-forward memory."""
        if not self._config.rolling_memory_enabled:
            return

        dedup_key = finding.dedup_key
        existing = self._rolling_findings.get(dedup_key)
        if existing is None:
            self._rolling_findings[dedup_key] = finding
        else:
            replace = False
            if finding.severity < existing.severity:
                replace = True
            elif finding.severity == existing.severity and finding.timestamp >= existing.timestamp:
                replace = True
            if replace:
                self._rolling_findings[dedup_key] = finding
        self._prune_rolling_memory()

    def _prune_rolling_memory(self) -> None:
        """Prune carry-forward memory by time window and max count."""
        if not self._rolling_findings:
            return

        now_ts = time.time()
        cutoff = now_ts - max(60, int(self._config.rolling_window_seconds))
        stale_keys = [
            key
            for key, finding in self._rolling_findings.items()
            if finding.timestamp < cutoff
        ]
        for key in stale_keys:
            self._rolling_findings.pop(key, None)

        limit = max(10, int(self._config.rolling_max_findings))
        if len(self._rolling_findings) <= limit:
            return

        prioritized = sorted(
            self._rolling_findings.values(),
            key=lambda f: (f.severity.value, -f.timestamp),
        )
        self._rolling_findings = {finding.dedup_key: finding for finding in prioritized[:limit]}

    def _get_rolling_findings(self) -> List[AggregatedFinding]:
        """Get prioritized carry-forward findings."""
        self._prune_rolling_memory()
        return sorted(
            self._rolling_findings.values(),
            key=lambda f: (f.severity.value, -f.timestamp),
        )

    def get_by_category(self, category: FindingCategory) -> List[AggregatedFinding]:
        """Get findings filtered by category.
        
        Args:
            category: The category to filter by.
        
        Returns:
            List of findings matching the category.
        """
        findings = self._get_all_findings()
        return [f for f in findings if f.category == category]

    def get_summary(self) -> AggregationSummary:
        """Get aggregation summary with statistics.
        
        Returns:
            AggregationSummary with counts and prioritized findings.
        """
        findings = self._get_all_findings()
        
        # Prioritize by severity then recency
        prioritized = self._prioritize(findings)
        
        # Enforce limit
        dropped_count = 0
        if len(prioritized) > self._config.max_findings_per_cycle:
            dropped_count = len(prioritized) - self._config.max_findings_per_cycle
            prioritized = prioritized[:self._config.max_findings_per_cycle]
            self._log.warning(
                "findings_dropped_due_to_limit",
                dropped_count=dropped_count,
                max_findings=self._config.max_findings_per_cycle,
            )
        
        # Calculate counts
        by_severity: Dict[FindingSeverity, int] = defaultdict(int)
        by_category: Dict[FindingCategory, int] = defaultdict(int)
        by_outcome: Dict[str, int] = defaultdict(int)
        
        for finding in prioritized:
            by_severity[finding.severity] += 1
            by_category[finding.category] += 1
            by_outcome[(finding.outcome_status or "attempted").lower()] += 1
        
        return AggregationSummary(
            total_count=len(prioritized),
            raw_count=self._raw_count,
            dropped_count=dropped_count,
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            window_start=self._window_start,
            window_end=self._window_end,
            findings=prioritized,
            by_outcome=dict(by_outcome),
        )

    def format_for_director(self) -> str:
        """Format aggregated findings for Director prompt.
        
        Returns:
            Structured string for LLM consumption.
        """
        summary = self.get_summary()
        
        # Calculate accurate dedup count (raw - unique before dropping)
        unique_before_drop = summary.total_count + summary.dropped_count
        dedup_count = summary.raw_count - unique_before_drop
        
        lines = []
        lines.append("## Findings Summary")
        lines.append("")
        lines.append("**Statistics:**")
        stats_line = f"- Total: {summary.total_count} findings ({summary.raw_count} raw, {dedup_count} deduplicated)"
        if summary.dropped_count > 0:
            stats_line += f", {summary.dropped_count} dropped due to limit"
        lines.append(stats_line)
        
        # Severity breakdown
        severity_parts = []
        for sev in [FindingSeverity.CRITICAL, FindingSeverity.HIGH, FindingSeverity.MEDIUM, FindingSeverity.LOW, FindingSeverity.INFO]:
            count = summary.by_severity.get(sev, 0)
            if count > 0:
                severity_parts.append(f"{sev.name.title()}: {count}")
        if severity_parts:
            lines.append(f"- {', '.join(severity_parts)}")

        outcome_parts = []
        for outcome_key in ("validated", "attempted", "failed"):
            count = summary.by_outcome.get(outcome_key, 0)
            if count > 0:
                outcome_parts.append(f"{outcome_key.title()}: {count}")
        if outcome_parts:
            lines.append(f"- Outcomes: {', '.join(outcome_parts)}")
        
        # Category breakdown
        category_parts = []
        for cat in [FindingCategory.RECON, FindingCategory.EXPLOIT, FindingCategory.POSTEX, FindingCategory.OTHER]:
            count = summary.by_category.get(cat, 0)
            if count > 0:
                category_parts.append(f"{cat.name.title()}: {count}")
        if category_parts:
            lines.append(f"- {', '.join(category_parts)}")
        
        lines.append("")
        
        # Critical findings section
        critical_findings = [f for f in summary.findings if f.severity == FindingSeverity.CRITICAL]
        if critical_findings:
            lines.append("**Critical Findings:**")
            for i, finding in enumerate(critical_findings[:5], 1):
                cve = finding.metadata.get("cve_id", "")
                cve_str = f" ({cve})" if cve else ""
                lines.append(f"{i}. [{finding.category.name}] {finding.finding_type} on {finding.target}{cve_str}")
            lines.append("")
        
        # High findings section
        high_findings = [f for f in summary.findings if f.severity == FindingSeverity.HIGH]
        if high_findings:
            lines.append("**High Findings:**")
            for i, finding in enumerate(high_findings[:5], 1):
                lines.append(f"{i}. [{finding.category.name}] {finding.finding_type} on {finding.target}")
            lines.append("")
        
        # Actionable context
        if summary.total_count > 0:
            lines.append("**Actionable Context:**")
            
            # Group by target for context
            target_severities: Dict[str, List[FindingSeverity]] = defaultdict(list)
            for finding in summary.findings:
                target_severities[finding.target].append(finding.severity)
            
            has_context = False
            
            # Find targets with critical findings
            for target, severities in target_severities.items():
                crit_count = sum(1 for s in severities if s == FindingSeverity.CRITICAL)
                if crit_count > 0:
                    lines.append(f"- {crit_count} critical vulnerabilities on {target} suggest immediate focus")
                    has_context = True
                    break
            
            # Find targets with high severity findings (if no critical)
            if not has_context:
                for target, severities in target_severities.items():
                    high_count = sum(1 for s in severities if s == FindingSeverity.HIGH)
                    if high_count > 0:
                        lines.append(f"- {high_count} high severity findings on {target} warrant attention")
                        has_context = True
                        break
            
            # Check for post-ex opportunities
            postex_count = summary.by_category.get(FindingCategory.POSTEX, 0)
            if postex_count > 0:
                lines.append(f"- {postex_count} post-exploitation opportunities available")
                has_context = True
            
            # Provide general context if nothing specific
            if not has_context:
                exploit_count = summary.by_category.get(FindingCategory.EXPLOIT, 0)
                recon_count = summary.by_category.get(FindingCategory.RECON, 0)
                if exploit_count > 0:
                    lines.append(f"- {exploit_count} exploit findings require further investigation")
                elif recon_count > 0:
                    lines.append(f"- {recon_count} recon findings available for target enumeration")
                else:
                    lines.append(f"- {summary.total_count} findings collected for analysis")
        else:
            lines.append("**No findings in this cycle.**")

        current_keys = {f.dedup_key for f in summary.findings}
        carry_forward = [
            finding
            for finding in self._get_rolling_findings()
            if finding.dedup_key not in current_keys
        ]
        if carry_forward:
            lines.append("")
            lines.append("**Carry-Forward Context (recent unresolved/high-value):**")
            for i, finding in enumerate(carry_forward[:10], 1):
                lines.append(
                    f"{i}. [{finding.severity.name}] [{finding.category.name}] "
                    f"{finding.finding_type} on {finding.target}"
                )
        
        return "\n".join(lines)

    def get_outcome_totals(self) -> Dict[str, int]:
        """Return cumulative deduplicated outcome totals across engagement."""
        return dict(self._outcome_totals)

    def reset_window(self) -> None:
        """Reset aggregation window for new cycle."""
        self._findings.clear()
        self._findings_list.clear()
        self._raw_count = 0
        self._window_start = time.time()
        self._window_end = time.time()
        
        self._log.info("aggregator_window_reset")

    def get_findings_since(
        self,
        timestamp: Optional[float] = None,
    ) -> AggregationSummary:
        """Get findings since timestamp (for ReplanTriggerManager).
        
        Args:
            timestamp: Optional timestamp to filter findings. If None, returns all.
        
        Returns:
            AggregationSummary with filtered, deduplicated, prioritized findings.
        """
        findings = self._get_all_findings()
        
        # Filter by timestamp if provided
        if timestamp is not None:
            findings = [f for f in findings if f.timestamp > timestamp]
        
        # Prioritize
        prioritized = self._prioritize(findings)
        
        # Enforce limit
        dropped_count = 0
        if len(prioritized) > self._config.max_findings_per_cycle:
            dropped_count = len(prioritized) - self._config.max_findings_per_cycle
            prioritized = prioritized[:self._config.max_findings_per_cycle]
        
        # Calculate counts
        by_severity: Dict[FindingSeverity, int] = defaultdict(int)
        by_category: Dict[FindingCategory, int] = defaultdict(int)
        by_outcome: Dict[str, int] = defaultdict(int)
        
        for finding in prioritized:
            by_severity[finding.severity] += 1
            by_category[finding.category] += 1
            by_outcome[(finding.outcome_status or "attempted").lower()] += 1
        
        summary = AggregationSummary(
            total_count=len(prioritized),
            raw_count=self._raw_count,
            dropped_count=dropped_count,
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            window_start=self._window_start,
            window_end=self._window_end,
            findings=prioritized,
            by_outcome=dict(by_outcome),
        )

        return summary

    # =========================================================================
    # Internal Methods (Tasks 3, 5)
    # =========================================================================

    def _categorize(self, finding_type: str) -> FindingCategory:
        """Categorize finding based on type.
        
        Args:
            finding_type: The type of finding.
        
        Returns:
            FindingCategory for the type, or OTHER if unknown.
        """
        return FINDING_TYPE_CATEGORIES.get(finding_type, FindingCategory.OTHER)

    def _prioritize(self, findings: List[AggregatedFinding]) -> List[AggregatedFinding]:
        """Sort findings by severity then recency.
        
        Args:
            findings: List of findings to sort.
        
        Returns:
            Sorted list (severity ascending = critical first, timestamp descending = newest first).
        """
        return sorted(
            findings,
            key=lambda f: (f.severity.value, -f.timestamp),
        )

    def _get_all_findings(self) -> List[AggregatedFinding]:
        """Get all findings (handles dedup vs non-dedup mode).
        
        Returns:
            List of all findings.
        """
        if self._config.dedup_enabled:
            return list(self._findings.values())
        return list(self._findings_list)

    # =========================================================================
    # EventBus Integration (Task 7)
    # =========================================================================

    async def _setup_subscriptions(self) -> None:
        """Set up EventBus subscriptions for finding collection."""
        if not self._event_bus or not self._engagement_id:
            return

        # psubscribe for wildcard — agents publish to findings:{target_hash}:{type}
        pattern = "findings:*"

        try:
            task = await self._event_bus.psubscribe(
                pattern,
                self._handle_finding_event,
            )
            self._subscriptions.append(task)

            self._log.info(
                "subscribed_to_findings",
                pattern=pattern,
            )
        except Exception as e:
            self._log.warning(
                "subscription_setup_error",
                pattern=pattern,
                error=str(e),
            )

    async def _handle_finding_event(
        self,
        channel: str,
        message: Any,
    ) -> None:
        """Handle finding event from EventBus.

        Args:
            channel: The channel the finding was received on.
            message: Finding data (JSON string or dict from psubscribe).
        """
        if not self._running:
            return

        # Skip batch aggregation and intel-enriched messages (no individual target/type fields)
        if ":aggregated:" in channel or ":intel_enriched" in channel:
            return

        # Handle both string (JSON) and dict (pre-deserialized by EventBus)
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                self._log.warning(
                    "finding_parse_error",
                    channel=channel,
                    error=str(e),
                )
                return
        elif isinstance(message, dict):
            data = message
        else:
            return

        # Handle sharded bus wrapper format: {"agent_id":..., "data":{...}}
        if "data" in data and isinstance(data["data"], dict):
            inner = data["data"]
        else:
            inner = data

        # Extract finding data
        target = inner.get("target", "")
        finding_type = inner.get("type", inner.get("finding_type", ""))
        severity_str = inner.get("severity", "info").upper()
        outcome_status = str(inner.get("outcome_status", "attempted")).strip().lower() or "attempted"
        if outcome_status not in {"validated", "attempted", "failed"}:
            outcome_status = "attempted"
        agent_id = inner.get("agent_id", data.get("agent_id", "unknown"))
        raw_ts = inner.get("timestamp", None)
        if isinstance(raw_ts, str):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(raw_ts).timestamp()
            except (ValueError, TypeError):
                timestamp = time.time()
        elif isinstance(raw_ts, (int, float)):
            timestamp = float(raw_ts)
        else:
            timestamp = time.time()
        
        if not target or not finding_type:
            self._log.warning(
                "finding_missing_fields",
                channel=channel,
                has_target=bool(target),
                has_type=bool(finding_type),
            )
            return
        
        # Map severity string to enum
        try:
            severity = FindingSeverity[severity_str]
        except KeyError:
            severity = FindingSeverity.INFO
        
        # Categorize finding
        category = self._categorize(finding_type)
        
        # Create and add finding
        finding = AggregatedFinding(
            target=target,
            finding_type=finding_type,
            severity=severity,
            category=category,
            timestamp=timestamp,
            agent_id=agent_id,
            outcome_status=outcome_status,
            metadata={
                k: v for k, v in inner.items()
                if k not in {"target", "type", "finding_type", "severity", "agent_id", "timestamp"}
            },
        )
        
        added = self.add_finding(finding)
        if added:
            self._outcome_totals[outcome_status] += 1
        
        self._log.debug(
            "finding_processed",
            target=target,
            finding_type=finding_type,
            severity=severity_str,
            outcome_status=outcome_status,
            added=added,
        )
