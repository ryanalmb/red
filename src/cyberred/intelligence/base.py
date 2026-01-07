"""Intelligence Source Base Interface.

This module defines the foundational abstractions for the Vulnerability
Intelligence Layer. All intelligence sources (CISA KEV, NVD, ExploitDB,
Nuclei, Metasploit) must implement these interfaces.

Classes:
    IntelPriority: Priority ranking constants for intelligence results.
    IntelResult: Dataclass for vulnerability/exploit intelligence data.
    IntelligenceSource: Abstract base class for all intelligence sources.

Architecture Reference:
    From architecture.md: Integration Pattern:
    1. Agent discovers service → calls intelligence.query(service, version)
    2. Aggregator queries sources in parallel (5s timeout per source)
    3. Results prioritized: CISA KEV > Critical CVE > High CVE > MSF > Nuclei > ExploitDB
    4. Agent receives IntelligenceResult with prioritized exploit paths
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Union

from cyberred.core.models import VALID_SEVERITIES


class IntelPriority:
    """Priority ranking for intelligence results.

    Lower numbers = higher priority (sorted ascending).
    Per architecture: CISA KEV > Critical CVE > High CVE > MSF > Nuclei > ExploitDB

    Attributes:
        CISA_KEV: Priority 1 - CISA Known Exploited Vulnerabilities (highest)
        NVD_CRITICAL: Priority 2 - NVD Critical severity CVEs
        NVD_HIGH: Priority 3 - NVD High severity CVEs
        METASPLOIT: Priority 4 - Metasploit modules available
        NUCLEI: Priority 5 - Nuclei templates available
        EXPLOITDB: Priority 6 - ExploitDB entries available
        NVD_MEDIUM: Priority 7 - NVD Medium severity CVEs (lowest)
    """

    CISA_KEV = 1
    NVD_CRITICAL = 2
    NVD_HIGH = 3
    METASPLOIT = 4
    NUCLEI = 5
    EXPLOITDB = 6
    NVD_MEDIUM = 7

    # Set of all valid priority values for validation.
    # Design decision: Priority 0 is reserved for future "emergency" sources.
    # Current implementation uses 1-7 range per architecture specification.
    _VALID_PRIORITIES = frozenset({1, 2, 3, 4, 5, 6, 7})


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
        metadata: Additional source-specific data (CVSS scores, references, etc.)

    Example:
        >>> result = IntelResult(
        ...     source="cisa_kev",
        ...     cve_id="CVE-2021-44228",
        ...     severity="critical",
        ...     exploit_available=True,
        ...     exploit_path=None,
        ...     confidence=1.0,
        ...     priority=IntelPriority.CISA_KEV,
        ... )
    """

    source: str
    cve_id: Optional[str]
    severity: str
    exploit_available: bool
    exploit_path: Optional[str]
    confidence: float
    priority: int
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Severity validation - reuse from core.models
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
            )

        # Confidence validation - must be 0.0-1.0
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid confidence '{self.confidence}'. Must be between 0.0 and 1.0."
            )

        # Priority validation - must be valid IntelPriority value
        if self.priority not in IntelPriority._VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority '{self.priority}'. "
                f"Must be one of: {sorted(IntelPriority._VALID_PRIORITIES)}"
            )

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string representation of the IntelResult.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> IntelResult:
        """Deserialize from JSON string or dict.

        Args:
            data: JSON string or dictionary with IntelResult fields.

        Returns:
            IntelResult instance reconstructed from JSON data.
        """
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


class IntelligenceSource(ABC):
    """Abstract base class for intelligence sources.

    All intelligence sources (CISA KEV, NVD, ExploitDB, Nuclei, Metasploit)
    must implement this interface for uniform querying by the aggregator.

    Subclasses MUST implement:
        - query(service, version): Query for vulnerabilities affecting service/version
        - health_check(): Check if source is available and responding

    Attributes:
        name: Human-readable source name
        timeout: Query timeout in seconds (default 5s per FR74)
        priority: Default priority for results from this source

Note:
        Subclasses MUST call super().__init__() to initialize base properties.

    Example:
        >>> class CisaKevSource(IntelligenceSource):
        ...     def __init__(self):
        ...         super().__init__(name="cisa_kev", priority=IntelPriority.CISA_KEV)
        ...
        ...     async def query(self, service: str, version: str) -> List[IntelResult]:
        ...         # Implementation here
        ...         return []
        ...
        ...     async def health_check(self) -> bool:
        ...         return True
        ...
        >>> source = CisaKevSource()
    """

    def __init__(
        self,
        name: str,
        timeout: float = 5.0,
        priority: int = IntelPriority.EXPLOITDB,
    ) -> None:
        """Initialize the intelligence source.

        Args:
            name: Human-readable source name.
            timeout: Query timeout in seconds (default 5.0 per FR74).
            priority: Default priority for results from this source.
        """
        self._name = name
        self._timeout = timeout
        self._priority = priority

    @property
    def name(self) -> str:
        """Get the source name."""
        return self._name

    @property
    def timeout(self) -> float:
        """Get the query timeout in seconds."""
        return self._timeout

    @property
    def priority(self) -> int:
        """Get the default priority for results from this source."""
        return self._priority

    @abstractmethod
    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query this source for vulnerabilities affecting service/version.

        Args:
            service: Service name (e.g., "Apache", "OpenSSH", "vsftpd")
            version: Version string (e.g., "2.4.49", "8.2p1")

        Returns:
            List of IntelResult objects, sorted by priority (lowest first).
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this source is available and responding.

        Returns:
            True if source is healthy, False otherwise.
        """
        ...
