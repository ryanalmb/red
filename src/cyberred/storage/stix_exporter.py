"""STIX 2.1 Export for Cyber-Red (Story 13.7).

Provides STIX 2.1 format export for threat intelligence sharing with
STIX-compatible systems (MISP, OpenCTI, etc.).

STIX (Structured Threat Information Expression) is an OASIS standard
for representing threat intelligence.

Note: This module provides STIX export only. TAXII client integration
for pushing to TAXII servers is planned for a future story.

Usage:
    from cyberred.storage.stix_exporter import STIXExporter, validate_stix
    
    exporter = STIXExporter()
    stix_json = exporter.export(report_data)
    
    # Validate output
    validate_stix(stix_json)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import stix2

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from cyberred.storage.report_generator import ReportData

# Package version
__version__ = "2.0.0"

# Consistent tool UUID for Cyber-Red identity
_TOOL_UUID = "d4e5f6a7-b8c9-4d0e-a1b2-c3d4e5f6a7b8"

# Vulnerability types that map to STIX vulnerability objects
VULN_TYPES = frozenset({
    "sqli", "xss", "rce", "lfi", "rfi", "xxe", "ssrf", "idor", "csrf"
})

# Regex for ATT&CK technique IDs
ATTACK_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?")

# Regex for CVE extraction
CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+")


class STIXExporter:
    """Export engagement findings to STIX 2.1 format.
    
    STIX (Structured Threat Information Expression) is an OASIS standard
    that enables threat intelligence sharing with compatible platforms.
    
    Example:
        >>> from cyberred.storage.stix_exporter import STIXExporter
        >>> exporter = STIXExporter()
        >>> stix_json = exporter.export(report_data)
        >>> with open("findings.stix.json", "w") as f:
        ...     f.write(stix_json)
    """
    
    def __init__(self) -> None:
        """Initialize STIX exporter with Cyber-Red identity."""
        self._tool_uuid = _TOOL_UUID
        self._identity = self._create_identity()
        # Cache for attack patterns to avoid duplicates
        self._attack_pattern_cache: dict[str, stix2.AttackPattern] = {}
    
    def export(
        self,
        report_data: ReportData,
        as_dict: bool = False,
        as_bundle: bool = False,
    ) -> str | dict[str, Any] | stix2.Bundle:
        """Export report data to STIX 2.1 format.
        
        Args:
            report_data: ReportData containing findings to export.
            as_dict: If True, return dict instead of JSON string.
            as_bundle: If True, return stix2.Bundle object.
            
        Returns:
            STIX output as JSON string, dictionary, or Bundle object.
        """
        # Reset cache for each export
        self._attack_pattern_cache = {}
        
        # Build all STIX objects
        objects = self._build_objects(report_data)
        
        # Create bundle
        bundle = stix2.Bundle(objects=objects)
        
        if as_bundle:
            return bundle
        
        if as_dict:
            return json.loads(bundle.serialize())
        
        # Return pretty-printed JSON with Unicode preserved
        return bundle.serialize(pretty=True, ensure_ascii=False)
    
    def _build_objects(self, report_data: ReportData) -> list[Any]:
        """Build all STIX objects from report data.
        
        Args:
            report_data: ReportData containing findings.
            
        Returns:
            List of STIX objects.
        """
        objects: list[Any] = []
        object_refs: list[str] = []
        
        # Always include identity
        objects.append(self._identity)
        object_refs.append(self._identity.id)
        
        # Process each finding
        for finding in report_data.findings:
            finding_objects = self._process_finding(finding)
            for obj in finding_objects:
                objects.append(obj)
                object_refs.append(obj.id)
        
        # Create summary report
        report = self._create_report(object_refs, report_data)
        objects.append(report)
        
        return objects
    
    def _process_finding(self, finding: dict[str, Any]) -> list[Any]:
        """Process a single finding into STIX objects.
        
        Args:
            finding: Finding dictionary.
            
        Returns:
            List of STIX objects for this finding.
        """
        objects: list[Any] = []
        indicator = None
        
        # Map to indicator if high/critical severity
        indicator = self._map_finding_to_indicator(finding)
        if indicator is not None:
            objects.append(indicator)
        
        # Map to vulnerability if vuln type
        vulnerability = self._map_finding_to_vulnerability(finding)
        if vulnerability is not None:
            objects.append(vulnerability)
        
        # Map ATT&CK techniques
        attck_ids = finding.get("attck_ids") or []
        for technique_id in attck_ids:
            attack_pattern = self._get_or_create_attack_pattern(technique_id)
            if attack_pattern is None:
                continue
            
            # Add attack pattern if not already added
            if attack_pattern not in objects:
                objects.append(attack_pattern)
            
            # Create relationship from indicator to attack-pattern
            if indicator is not None:
                relationship = self._create_relationship(
                    indicator.id,
                    attack_pattern.id,
                    "indicates",
                )
                objects.append(relationship)
        
        return objects
    
    def _create_identity(self) -> stix2.Identity:
        """Create Cyber-Red tool identity object.
        
        Returns:
            STIX Identity object.
        """
        return stix2.Identity(
            id=f"identity--{self._tool_uuid}",
            name="cyber-red",
            identity_class="system",
            description="Cyber-Red Autonomous Penetration Testing Platform",
        )
    
    def _map_finding_to_indicator(
        self, finding: dict[str, Any]
    ) -> stix2.Indicator | None:
        """Map high/critical severity finding to STIX indicator.
        
        Args:
            finding: Finding dictionary.
            
        Returns:
            STIX Indicator or None if not applicable.
        """
        severity = (finding.get("severity") or "").lower()
        if severity not in ("critical", "high"):
            return None
        
        target = finding.get("target") or ""
        finding_type = finding.get("type") or "unknown"
        evidence = finding.get("evidence") or f"{finding_type} vulnerability found"
        
        # Get timestamp
        timestamp = self._normalize_timestamp(finding.get("timestamp"))
        
        # Create STIX pattern based on target
        pattern = self._create_pattern(target)
        
        # Map severity to indicator type
        indicator_type = "malicious-activity" if severity in ("critical", "high") else "anomalous-activity"
        
        return stix2.Indicator(
            name=f"{finding_type} vulnerability on {target}" if target else f"{finding_type} vulnerability",
            description=evidence,
            indicator_types=[indicator_type],
            pattern=pattern,
            pattern_type="stix",
            valid_from=timestamp,
            created_by_ref=self._identity.id,
        )
    
    def _map_finding_to_vulnerability(
        self, finding: dict[str, Any]
    ) -> stix2.Vulnerability | None:
        """Map vulnerability-type finding to STIX vulnerability.
        
        Args:
            finding: Finding dictionary.
            
        Returns:
            STIX Vulnerability or None if not applicable.
        """
        finding_type = (finding.get("type") or "").lower()
        if finding_type not in VULN_TYPES:
            return None
        
        evidence = finding.get("evidence") or ""
        
        # Build external references
        external_refs = []
        
        # Extract CVE if present in evidence
        cve_match = CVE_PATTERN.search(evidence)
        if cve_match:
            external_refs.append(
                stix2.ExternalReference(
                    source_name="cve",
                    external_id=cve_match.group(0),
                )
            )
        
        return stix2.Vulnerability(
            name=finding_type.upper(),
            description=evidence or f"{finding_type} vulnerability",
            external_references=external_refs if external_refs else None,
            created_by_ref=self._identity.id,
        )
    
    def _get_or_create_attack_pattern(
        self, technique_id: str
    ) -> stix2.AttackPattern | None:
        """Get or create STIX attack-pattern from ATT&CK technique ID.
        
        Args:
            technique_id: ATT&CK technique ID (e.g., T1190, T1059.001).
            
        Returns:
            STIX AttackPattern or None if invalid ID.
        """
        # Validate technique ID format
        if not ATTACK_PATTERN.match(technique_id):
            logger.warning("Invalid ATT&CK technique ID format: %s", technique_id)
            return None
        
        # Return cached if exists
        if technique_id in self._attack_pattern_cache:
            return self._attack_pattern_cache[technique_id]
        
        # Build URL - handle sub-techniques
        url_technique = technique_id.replace(".", "/")
        url = f"https://attack.mitre.org/techniques/{url_technique}"
        
        attack_pattern = stix2.AttackPattern(
            name=f"ATT&CK Technique {technique_id}",
            external_references=[
                stix2.ExternalReference(
                    source_name="mitre-attack",
                    external_id=technique_id,
                    url=url,
                )
            ],
            created_by_ref=self._identity.id,
        )
        
        self._attack_pattern_cache[technique_id] = attack_pattern
        return attack_pattern
    
    def _create_relationship(
        self,
        source_ref: str,
        target_ref: str,
        relationship_type: str,
    ) -> stix2.Relationship:
        """Create STIX relationship object.
        
        Args:
            source_ref: Source object ID.
            target_ref: Target object ID.
            relationship_type: Type of relationship (e.g., "indicates", "uses").
            
        Returns:
            STIX Relationship object.
        """
        return stix2.Relationship(
            source_ref=source_ref,
            target_ref=target_ref,
            relationship_type=relationship_type,
            created_by_ref=self._identity.id,
        )
    
    def _create_report(
        self,
        object_refs: list[str],
        report_data: ReportData,
    ) -> stix2.Report:
        """Create STIX report summarizing engagement.
        
        Args:
            object_refs: List of object IDs to reference.
            report_data: Original report data.
            
        Returns:
            STIX Report object.
        """
        published = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        return stix2.Report(
            name=f"Cyber-Red Engagement: {report_data.engagement_id}",
            published=published,
            object_refs=object_refs if object_refs else [self._identity.id],
            created_by_ref=self._identity.id,
            report_types=["threat-report"],
        )
    
    def _create_pattern(self, target: str) -> str:
        """Create STIX pattern from target.
        
        Args:
            target: Target string (URL, IP, or domain).
            
        Returns:
            STIX pattern string.
        """
        if not target:
            return "[domain-name:value = 'unknown']"
        
        # URL pattern
        if target.startswith(("http://", "https://")):
            # Escape single quotes in target
            escaped = target.replace("'", "\\'")
            return f"[url:value = '{escaped}']"
        
        # IP address pattern (with optional port) - validate octets are 0-255
        ip_match = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})", target)
        if ip_match:
            octets = [int(ip_match.group(i)) for i in range(1, 5)]
            if all(0 <= octet <= 255 for octet in octets):
                ip = ".".join(str(o) for o in octets)
                return f"[ipv4-addr:value = '{ip}']"
        
        # Domain pattern (default)
        escaped = target.replace("'", "\\'")
        return f"[domain-name:value = '{escaped}']"
    
    def _normalize_timestamp(self, timestamp: Any) -> str:
        """Normalize timestamp to ISO 8601 string.
        
        Args:
            timestamp: Timestamp (string, datetime, or None).
            
        Returns:
            ISO 8601 formatted timestamp string with UTC timezone.
        """
        if timestamp is None:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        if hasattr(timestamp, "isoformat"):
            # datetime object - ensure timezone-aware
            if hasattr(timestamp, "tzinfo") and timestamp.tzinfo is None:
                # Naive datetime - assume UTC
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return timestamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Assume string - validate and return
        if isinstance(timestamp, str):
            return timestamp
        
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def validate_stix(stix_output: str | dict[str, Any]) -> bool:
    """Validate STIX output by parsing with stix2 library.
    
    Args:
        stix_output: STIX JSON string or dict.
        
    Returns:
        True if valid.
        
    Raises:
        stix2.exceptions.InvalidValueError: If invalid STIX.
        json.JSONDecodeError: If invalid JSON.
    """
    if isinstance(stix_output, dict):
        stix_output = json.dumps(stix_output)
    
    # Parse with stix2 - this validates STIX compliance
    bundle = stix2.parse(stix_output)
    
    # Must be a Bundle
    if not isinstance(bundle, stix2.Bundle):
        raise ValueError("STIX output must be a Bundle")
    
    return True
