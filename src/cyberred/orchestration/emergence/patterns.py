"""Emergent pattern detection for stigmergic coordination.

Story 7.15: Emergent Attack Strategy Triggering.

This module provides pattern detection logic for identifying emergent
attack opportunities from collective agent findings. Patterns emerge
when multiple agents discover related information that, when correlated,
reveals attack paths no individual agent could find.

Pattern Types:
    SERVICE_CORRELATION: Same service/version across multiple targets
    CREDENTIAL_PIVOT: Credential found with accessible service
    FAILED_EXPLOIT_ESCALATION: Multiple exploit failures trigger RAG
    ENUMERATION_COMPLETE: Recon coverage triggers phase transition
    CROSS_AGENT_DISCOVERY: Findings from different roles correlate
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from cyberred.core.models import Finding

log = structlog.get_logger().bind(component="emergent_patterns")


class PatternType(Enum):
    """Types of emergent patterns that can be detected."""
    
    SERVICE_CORRELATION = "service_correlation"
    CREDENTIAL_PIVOT = "credential_pivot"
    FAILED_EXPLOIT_ESCALATION = "failed_exploit_escalation"
    ENUMERATION_COMPLETE = "enumeration_complete"
    CROSS_AGENT_DISCOVERY = "cross_agent_discovery"


@dataclass
class EmergentPattern:
    """Detected emergent pattern from collective findings.
    
    Attributes:
        id: Unique identifier for this pattern instance.
        pattern_type: Type of pattern detected.
        confidence: Confidence score (0.0 to 1.0).
        contributing_findings: IDs of findings that contributed to this pattern.
        recommended_actions: Suggested actions based on the pattern.
        timestamp: When the pattern was detected (ISO 8601).
    """
    
    id: str
    pattern_type: PatternType
    confidence: float
    contributing_findings: list[str]
    recommended_actions: list[str]
    timestamp: str
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = asdict(self)
        data["pattern_type"] = self.pattern_type.value
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, data: str | dict) -> EmergentPattern:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data)  # Make mutable copy
        data["pattern_type"] = PatternType(data["pattern_type"])
        return cls(**data)


class EmergentPatternDetector:
    """Detects emergent patterns from collective agent findings.
    
    Analyzes findings to identify tactical opportunities that emerge
    from correlating information across multiple agents.
    
    Attributes:
        _service_correlation_threshold: Min findings for service correlation.
        _failed_exploit_threshold: Min failures for escalation.
        _confidence_minimum: Minimum confidence to return pattern.
    """
    
    # Service keywords for CREDENTIAL_PIVOT detection
    PIVOT_SERVICES = frozenset({"smb", "ssh", "rdp", "winrm", "ftp", "telnet", "vnc"})
    
    def __init__(
        self,
        service_correlation_threshold: int = 2,
        failed_exploit_threshold: int = 3,
        confidence_minimum: float = 0.6,
    ) -> None:
        """Initialize the detector.
        
        Args:
            service_correlation_threshold: Minimum findings with same service
                version to trigger SERVICE_CORRELATION pattern.
            failed_exploit_threshold: Minimum exploit failures on same target
                to trigger FAILED_EXPLOIT_ESCALATION pattern.
            confidence_minimum: Minimum confidence score to include pattern
                in results.
        """
        self._service_correlation_threshold = service_correlation_threshold
        self._failed_exploit_threshold = failed_exploit_threshold
        self._confidence_minimum = confidence_minimum
        self._log = log
    
    def detect(self, findings: list[Finding]) -> list[EmergentPattern]:
        """Detect emergent patterns from a list of findings.
        
        Args:
            findings: List of Finding objects to analyze.
            
        Returns:
            List of detected EmergentPattern instances above confidence minimum.
        """
        if not findings:
            return []
        
        # Deduplicate findings by ID
        seen_ids: set[str] = set()
        unique_findings: list[Finding] = []
        for f in findings:
            if f.id not in seen_ids:
                seen_ids.add(f.id)
                unique_findings.append(f)
        
        patterns: list[EmergentPattern] = []
        
        # Detect each pattern type
        patterns.extend(self._detect_service_correlation(unique_findings))
        patterns.extend(self._detect_credential_pivot(unique_findings))
        patterns.extend(self._detect_failed_exploit_escalation(unique_findings))
        patterns.extend(self._detect_cross_agent_discovery(unique_findings))
        
        # Filter by confidence minimum
        filtered = [p for p in patterns if p.confidence >= self._confidence_minimum]
        
        self._log.info(
            "patterns_detected",
            total_findings=len(unique_findings),
            patterns_found=len(filtered),
        )
        
        return filtered
    
    def _detect_service_correlation(self, findings: list[Finding]) -> list[EmergentPattern]:
        """Detect SERVICE_CORRELATION pattern.
        
        Triggered when multiple agents report the same service/version
        across different targets.
        """
        patterns: list[EmergentPattern] = []
        
        # Group findings by evidence signature (service + version)
        service_groups: dict[str, list[Finding]] = defaultdict(list)
        
        for f in findings:
            if f.type in ("service", "open_port"):
                # Extract service signature from evidence
                sig = self._extract_service_signature(f.evidence)
                if sig:
                    service_groups[sig].append(f)
        
        # Check each group for correlation
        for sig, group in service_groups.items():
            if len(group) >= self._service_correlation_threshold:
                # Unique targets
                targets = {f.target for f in group}
                if len(targets) >= 2:  # Must be different targets
                    # Calculate confidence: base 0.7 + 0.1 per additional match
                    confidence = min(0.7 + 0.1 * (len(group) - 2), 1.0)
                    
                    patterns.append(EmergentPattern(
                        id=str(uuid.uuid4()),
                        pattern_type=PatternType.SERVICE_CORRELATION,
                        confidence=confidence,
                        contributing_findings=[f.id for f in group],
                        recommended_actions=[
                            f"prioritize_exploit_{sig.replace(' ', '_').lower()}",
                            "correlate_vulnerability_intel",
                        ],
                        timestamp=datetime.now(UTC).isoformat(),
                    ))
        
        return patterns
    
    def _detect_credential_pivot(self, findings: list[Finding]) -> list[EmergentPattern]:
        """Detect CREDENTIAL_PIVOT pattern.
        
        Triggered when a credential is found alongside an accessible
        service that could use those credentials (SMB, SSH, RDP, etc.).
        """
        patterns: list[EmergentPattern] = []
        
        # Find credential findings
        credentials = [f for f in findings if f.type == "credential"]
        
        # Find service findings for pivot-capable services
        pivot_services: list[Finding] = []
        for f in findings:
            if f.type in ("service", "open_port"):
                evidence_lower = f.evidence.lower()
                if any(svc in evidence_lower for svc in self.PIVOT_SERVICES):
                    pivot_services.append(f)
        
        # Check for credential + service combinations
        if credentials and pivot_services:
            for cred in credentials:
                for svc in pivot_services:
                    # Calculate confidence based on service accessibility
                    confidence = 0.8 if cred.target != svc.target else 0.75
                    
                    patterns.append(EmergentPattern(
                        id=str(uuid.uuid4()),
                        pattern_type=PatternType.CREDENTIAL_PIVOT,
                        confidence=confidence,
                        contributing_findings=[cred.id, svc.id],
                        recommended_actions=[
                            "authenticate_with_credential",
                            "attempt_lateral_movement",
                        ],
                        timestamp=datetime.now(UTC).isoformat(),
                    ))
        
        return patterns
    
    def _detect_failed_exploit_escalation(self, findings: list[Finding]) -> list[EmergentPattern]:
        """Detect FAILED_EXPLOIT_ESCALATION pattern.
        
        Triggered when multiple exploit attempts fail on the same target,
        indicating need for RAG escalation per Story 6.10.
        """
        patterns: list[EmergentPattern] = []
        
        # Group failed exploits by target
        failed_by_target: dict[str, list[Finding]] = defaultdict(list)
        
        for f in findings:
            if f.type in ("exploit_failed", "exploit_failure"):
                failed_by_target[f.target].append(f)
        
        # Check for threshold breaches
        for target, failures in failed_by_target.items():
            if len(failures) >= self._failed_exploit_threshold:
                patterns.append(EmergentPattern(
                    id=str(uuid.uuid4()),
                    pattern_type=PatternType.FAILED_EXPLOIT_ESCALATION,
                    confidence=0.9,  # High confidence for explicit failures
                    contributing_findings=[f.id for f in failures],
                    recommended_actions=[
                        "trigger_rag_escalation",
                        "query_alternative_techniques",
                    ],
                    timestamp=datetime.now(UTC).isoformat(),
                ))
        
        return patterns
    
    def _detect_cross_agent_discovery(self, findings: list[Finding]) -> list[EmergentPattern]:
        """Detect CROSS_AGENT_DISCOVERY pattern.
        
        Triggered when findings from different agent types correlate
        on the same target (e.g., service enumeration + vulnerability scan).
        """
        patterns: list[EmergentPattern] = []
        
        # Group findings by target
        by_target: dict[str, list[Finding]] = defaultdict(list)
        for f in findings:
            by_target[f.target].append(f)
        
        # Check each target for cross-agent correlation
        for target, target_findings in by_target.items():
            # Get unique agent IDs
            agent_ids = {f.agent_id for f in target_findings}
            
            if len(agent_ids) >= 2:
                # Get unique finding types
                finding_types = {f.type for f in target_findings}
                
                # Check for meaningful correlation (not just multiple port scans)
                high_value_types = {"vulnerability", "credential", "exploit_success"}
                recon_types = {"service", "open_port", "technology"}
                
                has_high_value = bool(finding_types & high_value_types)
                has_recon = bool(finding_types & recon_types)
                
                if has_high_value and has_recon:
                    confidence = 0.75 + 0.05 * min(len(agent_ids), 5)
                    
                    patterns.append(EmergentPattern(
                        id=str(uuid.uuid4()),
                        pattern_type=PatternType.CROSS_AGENT_DISCOVERY,
                        confidence=min(confidence, 1.0),
                        contributing_findings=[f.id for f in target_findings],
                        recommended_actions=[
                            "spawn_specialized_agent",
                            "correlate_findings_deep",
                        ],
                        timestamp=datetime.now(UTC).isoformat(),
                    ))
        
        return patterns
    
    def _extract_service_signature(self, evidence: str) -> str | None:
        """Extract a normalized service signature from evidence.
        
        Args:
            evidence: Raw evidence string from finding.
            
        Returns:
            Normalized service signature or None if not extractable.
        """
        if not evidence:
            return None
        
        # Common patterns: "SSH OpenSSH 8.2p1", "Apache 2.4.49", etc.
        # Normalize: lowercase, remove minor version details
        evidence_lower = evidence.lower()
        
        # Extract key service identifiers
        keywords = ["ssh", "apache", "nginx", "mysql", "postgres", "smb", "ftp", "http"]
        
        for kw in keywords:
            if kw in evidence_lower:
                # Extract version if present (major.minor)
                import re
                version_match = re.search(r"(\d+\.\d+)", evidence)
                if version_match:
                    return f"{kw} {version_match.group(1)}"
                return kw
        
        return None
