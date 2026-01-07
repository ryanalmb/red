"""CISA Known Exploited Vulnerabilities (KEV) Source Integration.

This module implements the CisaKevSource intelligence source that queries
the CISA KEV catalog for actively exploited vulnerabilities.

Classes:
    KevEntry: Dataclass representing a single KEV catalog entry.
    KevCatalog: Local cache manager for the CISA KEV catalog.
    CisaKevSource: Intelligence source implementing the IntelligenceSource interface.

Architecture Reference:
    From architecture.md: CISA KEV has priority 1 (highest) because all KEV
    entries represent actively exploited vulnerabilities requiring immediate
    attention.

Example:
    >>> from cyberred.intelligence.sources import CisaKevSource
    >>> source = CisaKevSource()
    >>> results = await source.query("Apache", "2.4.49")
    >>> for r in results:
    ...     print(f"{r.cve_id}: {r.metadata['vulnerability_name']}")
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import structlog

from cyberred.core.config import get_settings
from cyberred.intelligence.base import IntelligenceSource, IntelPriority, IntelResult


log = structlog.get_logger()


# =============================================================================
# KEV Data Models
# =============================================================================


@dataclass
class KevEntry:
    """Represents a single CISA KEV catalog entry.

    Attributes:
        cve_id: CVE identifier (e.g., "CVE-2021-44228")
        vendor_project: Vendor or project name (e.g., "Apache")
        product: Product name (e.g., "Log4j")
        vulnerability_name: Human-readable vulnerability name
        date_added: Date added to KEV catalog (YYYY-MM-DD)
        short_description: Brief description of the vulnerability
        required_action: Action required to remediate
        due_date: Remediation due date (YYYY-MM-DD)
        notes: Additional notes (often empty)
    """

    cve_id: str
    vendor_project: str
    product: str
    vulnerability_name: str
    date_added: str
    short_description: str
    required_action: str
    due_date: str
    notes: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> KevEntry:
        """Create a KevEntry from raw CISA KEV JSON.

        The CISA JSON uses camelCase field names that we normalize
        to snake_case for Pythonic access.

        Args:
            data: Raw JSON entry from CISA KEV feed.

        Returns:
            KevEntry instance with normalized field names.
        """
        return cls(
            cve_id=data["cveID"],
            vendor_project=data["vendorProject"],
            product=data["product"],
            vulnerability_name=data["vulnerabilityName"],
            date_added=data["dateAdded"],
            short_description=data["shortDescription"],
            required_action=data["requiredAction"],
            due_date=data["dueDate"],
            notes=data.get("notes", ""),
        )


# =============================================================================
# KEV Catalog Cache
# =============================================================================


class KevCatalog:
    """Local cache manager for CISA KEV catalog.

    Downloads and caches the CISA KEV JSON feed locally for fast querying.
    Cache is refreshed daily per story requirements (Story 5.2 AC4).

    Attributes:
        FEED_URL: Official CISA KEV JSON feed URL.
        CACHE_TTL: Cache time-to-live (24 hours).
    """

    FEED_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    CACHE_TTL = timedelta(hours=24)

    @property
    def CACHE_FILE(self) -> Path:
        """Get the cache file path under configured storage base.

        Uses get_settings().storage.base_path which defaults to ~/.cyber-red.

        Returns:
            Path to the kev_catalog.json cache file.
        """
        base = Path(get_settings().storage.base_path).expanduser()
        return base / "kev_catalog.json"

    def is_cache_valid(self) -> bool:
        """Check if the cache exists and is within TTL.

        Returns:
            True if cache file exists and is less than 24 hours old.
        """
        cache_file = self.CACHE_FILE
        if not cache_file.exists():
            return False

        # Check file modification time
        file_mtime = cache_file.stat().st_mtime
        age_seconds = time.time() - file_mtime
        max_age_seconds = self.CACHE_TTL.total_seconds()

        return age_seconds < max_age_seconds

    def load_cached(self) -> Optional[List[KevEntry]]:
        """Load entries from cache if valid.

        Returns:
            List of KevEntry objects if cache is valid, None otherwise.
        """
        if not self.is_cache_valid():
            return None

        try:
            cache_data = json.loads(self.CACHE_FILE.read_text())
            vulnerabilities = cache_data.get("vulnerabilities", [])
            return [KevEntry.from_json(v) for v in vulnerabilities]
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("kev_cache_load_failed", error=str(e))
            return None

    async def fetch(self) -> List[KevEntry]:
        """Fetch the KEV catalog from CISA and cache it locally.

        Downloads the complete KEV catalog JSON, parses all entries,
        and saves to local cache file.

        Returns:
            List of KevEntry objects from the fresh download.

        Raises:
            aiohttp.ClientError: If network request fails.
        """
        log.info("kev_catalog_fetch_start", url=self.FEED_URL)

        async with aiohttp.ClientSession() as session:
            async with session.get(self.FEED_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                data = await response.json()

        vulnerabilities = data.get("vulnerabilities", [])
        entries = [KevEntry.from_json(v) for v in vulnerabilities]

        # Save to cache
        cache_file = self.CACHE_FILE
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data))

        log.info(
            "kev_catalog_fetch_complete",
            entry_count=len(entries),
            catalog_version=data.get("catalogVersion"),
        )

        return entries

    async def ensure_cached(self) -> List[KevEntry]:
        """Ensure catalog is cached and return entries.

        Uses cached entries if valid, otherwise fetches fresh data.

        Returns:
            List of KevEntry objects.
        """
        cached = self.load_cached()
        if cached is not None:
            log.debug("kev_catalog_using_cache", entry_count=len(cached))
            return cached

        return await self.fetch()


# =============================================================================
# CisaKevSource Implementation
# =============================================================================


class CisaKevSource(IntelligenceSource):
    """CISA Known Exploited Vulnerabilities intelligence source.

    Highest priority intelligence source (priority=1). Queries locally
    cached KEV catalog to identify actively exploited vulnerabilities.

    All results from this source have:
    - severity="critical" (KEV entries are by definition critical)
    - exploit_available=True (KEV = known exploited)
    - priority=IntelPriority.CISA_KEV (1, highest)

    Example:
        >>> source = CisaKevSource()
        >>> results = await source.query("Apache", "2.4.49")
        >>> for r in results:
        ...     print(f"{r.cve_id}: priority={r.priority}")
    """

    def __init__(self, catalog: Optional[KevCatalog] = None) -> None:
        """Initialize the CISA KEV source.

        Args:
            catalog: Optional KevCatalog instance for dependency injection.
                If not provided, a new KevCatalog is created.
        """
        super().__init__(
            name="cisa_kev",
            timeout=5.0,  # Per FR74
            priority=IntelPriority.CISA_KEV,
        )
        self._catalog = catalog or KevCatalog()

    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query KEV catalog for vulnerabilities affecting service/version.

        Performs case-insensitive matching on vendor/product fields.

        Args:
            service: Service name to search for (e.g., "Apache", "OpenSSH")
            version: Version string (currently used for logging, matching
                is primarily on vendor/product)

        Returns:
            List of IntelResult objects sorted by date_added (newest first).
            Returns empty list on any error (per ERR3).
        """
        log.info("cisa_kev_query_start", service=service, version=version)

        try:
            entries = await self._catalog.ensure_cached()
            results = []

            for entry in entries:
                matches, confidence = self._matches_service(entry, service, version)
                if matches:
                    results.append(self._to_intel_result(entry, confidence))

            # Sort by date_added (newest first)
            results.sort(key=lambda r: r.metadata.get("date_added", ""), reverse=True)

            log.info("cisa_kev_query_complete", result_count=len(results))
            return results

        except Exception as e:
            log.warning("cisa_kev_query_failed", error=str(e))
            return []  # Return empty per ERR3

    async def health_check(self) -> bool:
        """Check if CISA KEV source is healthy.

        Healthy if:
        - Valid cache exists (preferred), OR
        - CISA feed URL is reachable

        Returns:
            True if source is healthy, False otherwise.
        """
        # If valid cache exists, we're healthy
        if self._catalog.is_cache_valid():
            return True

        # Otherwise, check if CISA feed is reachable
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    KevCatalog.FEED_URL,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except aiohttp.ClientError:
            return False

    def _matches_service(
        self, entry: KevEntry, service: str, version: str
    ) -> Tuple[bool, float]:
        """Check if KEV entry matches the service/version query.

        Performs case-insensitive substring matching on vendor_project
        and product fields.

        Args:
            entry: KEV entry to check.
            service: Service name to match.
            version: Version string (used for confidence scoring).

        Returns:
            Tuple of (matches: bool, confidence: float 0.0-1.0)
        """
        service_lower = service.lower().strip()
        vendor_lower = entry.vendor_project.lower()
        product_lower = entry.product.lower()

        # Check if service matches vendor or product
        vendor_match = service_lower in vendor_lower
        product_match = service_lower in product_lower

        if not (vendor_match or product_match):
            return False, 0.0

        # Calculate confidence based on match quality
        # Exact matches get higher confidence
        confidence = 0.7  # Base confidence for substring match

        if service_lower == vendor_lower or service_lower == product_lower:
            confidence = 1.0  # Exact match
        elif vendor_match and product_match:
            confidence = 0.9  # Matches both

        return True, confidence

    def _to_intel_result(self, entry: KevEntry, confidence: float) -> IntelResult:
        """Convert a KevEntry to an IntelResult.

        All KEV entries are converted with:
        - severity="critical" (by definition)
        - exploit_available=True (known exploited)
        - priority=IntelPriority.CISA_KEV

        Args:
            entry: KEV entry to convert.
            confidence: Match confidence from query (0.0-1.0).

        Returns:
            IntelResult with KEV-specific metadata.
        """
        return IntelResult(
            source="cisa_kev",
            cve_id=entry.cve_id,
            severity="critical",  # All KEV entries are critical by definition
            exploit_available=True,  # KEV = known exploited = exploit exists
            exploit_path=None,  # KEV doesn't provide exploit paths directly
            confidence=confidence,
            priority=IntelPriority.CISA_KEV,
            metadata={
                "vulnerability_name": entry.vulnerability_name,
                "vendor_project": entry.vendor_project,
                "product": entry.product,
                "date_added": entry.date_added,
                "due_date": entry.due_date,
                "required_action": entry.required_action,
                "short_description": entry.short_description,
                "notes": entry.notes,
            },
        )
