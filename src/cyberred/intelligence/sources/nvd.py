"""NVD (National Vulnerability Database) Source Integration.

This module implements the NvdSource intelligence source that queries
the NIST NVD API for CVE data using the nvdlib library.

Classes:
    NvdCveEntry: Dataclass representing a normalized NVD CVE entry.
    NvdSource: Intelligence source implementing the IntelligenceSource interface.

Functions:
    get_nvd_priority: Map CVSS score to IntelPriority constant.

Architecture Reference:
    From architecture.md: NVD sources are prioritized by CVSS severity:
    - Critical (9.0+) → NVD_CRITICAL (priority 2)
    - High (7.0-8.9) → NVD_HIGH (priority 3)
    - Medium/Low → NVD_MEDIUM (priority 7)

Example:
    >>> from cyberred.intelligence.sources import NvdSource
    >>> source = NvdSource()
    >>> results = await source.query("OpenSSH", "8.2")
    >>> for r in results:
    ...     print(f"{r.cve_id}: CVSS {r.metadata.get('cvss_v3_score')}")
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

import nvdlib
import structlog

from cyberred.intelligence.base import IntelligenceSource, IntelPriority, IntelResult


log = structlog.get_logger()


# =============================================================================
# NVD Entry Dataclass
# =============================================================================


@dataclass
class NvdCveEntry:
    """Normalized NVD CVE entry.

    Maps nvdlib CVE object fields to flat structure for IntelResult conversion.

    Attributes:
        cve_id: CVE identifier (e.g., "CVE-2021-44228")
        cvss_v3_score: CVSS v3.x base score (0.0-10.0), None if not available
        cvss_v3_vector: CVSS v3.x vector string
        cvss_v2_score: CVSS v2.0 base score (0.0-10.0), fallback
        description: CVE description text
        references: List of reference URLs
        published_date: CVE publication date
        last_modified_date: Last modification date
        cpe_matches: List of CPE strings this CVE affects
    """

    cve_id: str
    cvss_v3_score: Optional[float]
    cvss_v3_vector: Optional[str]
    cvss_v2_score: Optional[float]
    description: str
    references: List[str]
    published_date: str
    last_modified_date: str
    cpe_matches: List[str] = field(default_factory=list)

    @classmethod
    def from_nvdlib(cls, cve: Any) -> NvdCveEntry:
        """Create NvdCveEntry from nvdlib CVE object.

        Handles the nvdlib CVE object structure and extracts all
        relevant fields, handling missing/None values gracefully.

        Args:
            cve: nvdlib CVE object from searchCVE().

        Returns:
            NvdCveEntry instance with normalized fields.
        """
        # Extract description - nvdlib provides descriptions as list
        description = ""
        if hasattr(cve, "descriptions") and cve.descriptions:
            for desc in cve.descriptions:
                if hasattr(desc, "value"):
                    description = desc.value
                    break

        # Extract references - nvdlib provides reference objects
        references = []
        if hasattr(cve, "references") and cve.references:
            for ref in cve.references:
                if hasattr(ref, "url"):
                    references.append(ref.url)

        # Extract CPE matches if available
        cpe_matches = []
        if hasattr(cve, "cpe") and cve.cpe:
            for cpe in cve.cpe:
                if hasattr(cpe, "criteria"):
                    cpe_matches.append(cpe.criteria)

        return cls(
            cve_id=cve.id,
            cvss_v3_score=getattr(cve, "v31score", None),
            cvss_v3_vector=getattr(cve, "v31vector", None),
            cvss_v2_score=getattr(cve, "v2score", None),
            description=description,
            references=references,
            published_date=getattr(cve, "published", ""),
            last_modified_date=getattr(cve, "lastModified", ""),
            cpe_matches=cpe_matches,
        )


# =============================================================================
# Priority Mapping Function
# =============================================================================


def get_nvd_priority(cvss_score: Optional[float]) -> int:
    """Map CVSS score to IntelPriority.

    Uses CVSS v3.x severity thresholds to determine priority.

    Args:
        cvss_score: CVSS score (0.0-10.0) or None

    Returns:
        IntelPriority constant based on severity thresholds:
        - 9.0+ → NVD_CRITICAL (2)
        - 7.0-8.9 → NVD_HIGH (3)
        - <7.0 or None → NVD_MEDIUM (7)

    Note:
        The architecture specifies NVD_MEDIUM=7 per base.py definition.
        Low severity CVEs (0.1-3.9) map to NVD_MEDIUM per story AC3.
    """
    if cvss_score is None:
        return IntelPriority.NVD_MEDIUM
    if cvss_score >= 9.0:
        return IntelPriority.NVD_CRITICAL
    if cvss_score >= 7.0:
        return IntelPriority.NVD_HIGH
    return IntelPriority.NVD_MEDIUM


# =============================================================================
# NvdSource Implementation
# =============================================================================


class NvdSource(IntelligenceSource):
    """NVD intelligence source using nvdlib.

    Queries the National Vulnerability Database API for CVE data.
    Uses keyword search for service/version correlation.

    Attributes:
        _api_key: Optional NVD API key for higher rate limits.

    Configuration:
        - API key from environment: NVD_API_KEY
        - Rate limit with key: 50 req/30s
        - Rate limit without key: 5 req/30s

    Example:
        >>> source = NvdSource()
        >>> results = await source.query("Apache", "2.4.49")
        >>> for r in results:
        ...     print(f"{r.cve_id}: priority={r.priority}")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        """Initialize the NVD source.

        Args:
            api_key: Optional NVD API key for higher rate limits.
                If not provided, uses NVD_API_KEY environment variable.
            timeout: Query timeout in seconds (default 5.0 per FR74).
        """
        super().__init__(
            name="nvd",
            timeout=timeout,
            priority=IntelPriority.NVD_CRITICAL,
        )
        self._api_key = api_key or os.environ.get("NVD_API_KEY")

        if self._api_key:
            log.debug("nvd_source_init", api_key_present=True)
        else:
            log.debug("nvd_source_init", api_key_present=False)

    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query NVD for CVEs affecting service/version.

        Uses nvdlib.searchCVE with keyword matching.

        Args:
            service: Service name (e.g., "OpenSSH", "Apache")
            version: Version string (e.g., "8.2", "2.4.49")

        Returns:
            List of IntelResult sorted by severity (critical first).
            Empty list on any error.
        """
        log.info("nvd_query_start", service=service, version=version)

        try:
            # nvdlib is synchronous - run in executor for async compatibility
            loop = asyncio.get_event_loop()
            cves = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: nvdlib.searchCVE(
                        keywordSearch=f"{service} {version}",
                        key=self._api_key,
                    ),
                ),
                timeout=self._timeout,
            )
            return self._convert_results(cves, service, version)
        except asyncio.TimeoutError:
            log.warning("nvd_query_timeout", service=service, version=version)
            return []
        except Exception as e:
            log.warning("nvd_query_failed", error=str(e), service=service)
            return []

    async def health_check(self) -> bool:
        """Check if NVD API is reachable.

        Performs a minimal query to verify API accessibility.

        Returns:
            True if NVD API responds, False otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: nvdlib.searchCVE(
                        cveId="CVE-2021-44228",  # Known CVE for testing
                        key=self._api_key,
                    ),
                ),
                timeout=10.0,  # NVD API can be slow, use longer timeout
            )
            return True
        except Exception:
            return False

    def _convert_results(
        self,
        cves: List[Any],
        service: str,
        version: str,
    ) -> List[IntelResult]:
        """Convert nvdlib CVE objects to IntelResults.

        Args:
            cves: List of nvdlib CVE objects.
            service: Original service query (for confidence calculation).
            version: Original version query.

        Returns:
            List of IntelResult sorted by priority (critical first).
        """
        results = []
        for cve in cves:
            entry = NvdCveEntry.from_nvdlib(cve)
            result = self._to_intel_result(entry, confidence=0.8)  # Base confidence
            results.append(result)

        # Sort by priority (lower = higher priority)
        results.sort(key=lambda r: r.priority)

        log.info("nvd_query_complete", result_count=len(results))
        return results

    def _to_intel_result(self, entry: NvdCveEntry, confidence: float) -> IntelResult:
        """Convert NVD CVE entry to IntelResult.

        Args:
            entry: Normalized NVD CVE entry.
            confidence: Match confidence from query (0.0-1.0).

        Returns:
            IntelResult with NVD-specific metadata.
        """
        cvss_score = entry.cvss_v3_score or entry.cvss_v2_score
        priority = get_nvd_priority(cvss_score)
        severity = self._score_to_severity(cvss_score)

        return IntelResult(
            source="nvd",
            cve_id=entry.cve_id,
            severity=severity,
            exploit_available=False,  # NVD doesn't track exploit availability directly
            exploit_path=None,
            confidence=confidence,
            priority=priority,
            metadata={
                "cvss_v3_score": entry.cvss_v3_score,
                "cvss_v3_vector": entry.cvss_v3_vector,
                "cvss_v2_score": entry.cvss_v2_score,
                "description": entry.description,
                "references": entry.references,
                "published_date": entry.published_date,
                "last_modified_date": entry.last_modified_date,
            },
        )

    def _score_to_severity(self, cvss_score: Optional[float]) -> str:
        """Convert CVSS score to severity string.

        Uses CVSS v3 severity thresholds.

        Args:
            cvss_score: CVSS score (0.0-10.0) or None.

        Returns:
            Severity string: "critical", "high", "medium", "low", or "info".
        """
        if cvss_score is None:
            return "info"
        if cvss_score >= 9.0:
            return "critical"
        if cvss_score >= 7.0:
            return "high"
        if cvss_score >= 4.0:
            return "medium"
        return "low"
