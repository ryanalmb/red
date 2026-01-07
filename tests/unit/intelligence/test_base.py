"""Unit tests for intelligence base interface.

Tests IntelPriority constants, IntelResult dataclass, and IntelligenceSource ABC.
"""

from __future__ import annotations

import json

import pytest


class TestIntelPriority:
    """Tests for IntelPriority constants (AC: 5)."""

    @pytest.mark.unit
    def test_intel_priority_constants_exist(self) -> None:
        """IntelPriority class has all required priority constants."""
        from cyberred.intelligence import IntelPriority

        # Verify all constants exist
        assert hasattr(IntelPriority, "CISA_KEV")
        assert hasattr(IntelPriority, "NVD_CRITICAL")
        assert hasattr(IntelPriority, "NVD_HIGH")
        assert hasattr(IntelPriority, "METASPLOIT")
        assert hasattr(IntelPriority, "NUCLEI")
        assert hasattr(IntelPriority, "EXPLOITDB")
        assert hasattr(IntelPriority, "NVD_MEDIUM")

    @pytest.mark.unit
    def test_intel_priority_values_correct_order(self) -> None:
        """Priority values are in correct order (lower = higher priority)."""
        from cyberred.intelligence import IntelPriority

        # Per architecture: CISA KEV > Critical CVE > High CVE > MSF > Nuclei > ExploitDB
        assert IntelPriority.CISA_KEV == 1
        assert IntelPriority.NVD_CRITICAL == 2
        assert IntelPriority.NVD_HIGH == 3
        assert IntelPriority.METASPLOIT == 4
        assert IntelPriority.NUCLEI == 5
        assert IntelPriority.EXPLOITDB == 6
        assert IntelPriority.NVD_MEDIUM == 7

    @pytest.mark.unit
    def test_intel_priority_ordering_ascending(self) -> None:
        """When sorted ascending, CISA_KEV comes first (highest priority)."""
        from cyberred.intelligence import IntelPriority

        priorities = [
            IntelPriority.EXPLOITDB,
            IntelPriority.CISA_KEV,
            IntelPriority.NVD_HIGH,
            IntelPriority.METASPLOIT,
            IntelPriority.NVD_CRITICAL,
            IntelPriority.NUCLEI,
        ]
        sorted_priorities = sorted(priorities)
        
        assert sorted_priorities == [
            IntelPriority.CISA_KEV,      # 1
            IntelPriority.NVD_CRITICAL,  # 2
            IntelPriority.NVD_HIGH,      # 3
            IntelPriority.METASPLOIT,    # 4
            IntelPriority.NUCLEI,        # 5
            IntelPriority.EXPLOITDB,     # 6
        ]


class TestIntelResult:
    """Tests for IntelResult dataclass (AC: 4, 5)."""

    @pytest.mark.unit
    def test_intel_result_instantiation_all_fields(self) -> None:
        """IntelResult can be instantiated with all required fields."""
        from cyberred.intelligence import IntelResult, IntelPriority

        result = IntelResult(
            source="cisa_kev",
            cve_id="CVE-2021-44228",
            severity="critical",
            exploit_available=True,
            exploit_path="/path/to/exploit",
            confidence=0.95,
            priority=IntelPriority.CISA_KEV,
            metadata={"published": "2021-12-10"},
        )

        assert result.source == "cisa_kev"
        assert result.cve_id == "CVE-2021-44228"
        assert result.severity == "critical"
        assert result.exploit_available is True
        assert result.exploit_path == "/path/to/exploit"
        assert result.confidence == 0.95
        assert result.priority == 1
        assert result.metadata == {"published": "2021-12-10"}

    @pytest.mark.unit
    def test_intel_result_optional_cve_id(self) -> None:
        """IntelResult cve_id can be None for non-CVE exploits."""
        from cyberred.intelligence import IntelResult, IntelPriority

        result = IntelResult(
            source="metasploit",
            cve_id=None,
            severity="high",
            exploit_available=True,
            exploit_path="exploit/linux/local/sudo_baron",
            confidence=0.85,
            priority=IntelPriority.METASPLOIT,
        )

        assert result.cve_id is None

    @pytest.mark.unit
    def test_intel_result_default_metadata(self) -> None:
        """IntelResult metadata defaults to empty dict."""
        from cyberred.intelligence import IntelResult, IntelPriority

        result = IntelResult(
            source="nvd",
            cve_id="CVE-2023-1234",
            severity="medium",
            exploit_available=False,
            exploit_path=None,
            confidence=1.0,
            priority=IntelPriority.NVD_MEDIUM,
        )

        assert result.metadata == {}

    @pytest.mark.unit
    def test_intel_result_to_json(self) -> None:
        """IntelResult.to_json() produces valid JSON string."""
        from cyberred.intelligence import IntelResult, IntelPriority

        result = IntelResult(
            source="nuclei",
            cve_id="CVE-2022-5555",
            severity="high",
            exploit_available=True,
            exploit_path="cves/2022/CVE-2022-5555.yaml",
            confidence=0.90,
            priority=IntelPriority.NUCLEI,
        )

        json_str = result.to_json()
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["source"] == "nuclei"
        assert parsed["cve_id"] == "CVE-2022-5555"
        assert parsed["severity"] == "high"
        assert parsed["exploit_available"] is True
        assert parsed["confidence"] == 0.90
        assert parsed["priority"] == 5

    @pytest.mark.unit
    def test_intel_result_from_json_string(self) -> None:
        """IntelResult.from_json() reconstructs from JSON string."""
        from cyberred.intelligence import IntelResult, IntelPriority

        json_str = json.dumps({
            "source": "exploitdb",
            "cve_id": "CVE-2020-1234",
            "severity": "critical",
            "exploit_available": True,
            "exploit_path": "45678",
            "confidence": 0.75,
            "priority": 6,
            "metadata": {"edb_id": "45678"},
        })

        result = IntelResult.from_json(json_str)

        assert result.source == "exploitdb"
        assert result.cve_id == "CVE-2020-1234"
        assert result.priority == IntelPriority.EXPLOITDB
        assert result.metadata == {"edb_id": "45678"}

    @pytest.mark.unit
    def test_intel_result_from_json_dict(self) -> None:
        """IntelResult.from_json() reconstructs from dict."""
        from cyberred.intelligence import IntelResult

        data = {
            "source": "nvd",
            "cve_id": "CVE-2021-0001",
            "severity": "low",
            "exploit_available": False,
            "exploit_path": None,
            "confidence": 1.0,
            "priority": 3,
            "metadata": {},
        }

        result = IntelResult.from_json(data)

        assert result.source == "nvd"
        assert result.severity == "low"

    @pytest.mark.unit
    def test_intel_result_validation_invalid_severity(self) -> None:
        """IntelResult raises ValueError for invalid severity."""
        from cyberred.intelligence import IntelResult, IntelPriority

        with pytest.raises(ValueError, match="(?i)severity"):
            IntelResult(
                source="test",
                cve_id=None,
                severity="extreme",  # Invalid
                exploit_available=False,
                exploit_path=None,
                confidence=1.0,
                priority=IntelPriority.EXPLOITDB,
            )

    @pytest.mark.unit
    def test_intel_result_validation_confidence_too_high(self) -> None:
        """IntelResult raises ValueError for confidence > 1.0."""
        from cyberred.intelligence import IntelResult, IntelPriority

        with pytest.raises(ValueError, match="(?i)confidence"):
            IntelResult(
                source="test",
                cve_id=None,
                severity="high",
                exploit_available=False,
                exploit_path=None,
                confidence=1.5,  # Invalid
                priority=IntelPriority.EXPLOITDB,
            )

    @pytest.mark.unit
    def test_intel_result_validation_confidence_negative(self) -> None:
        """IntelResult raises ValueError for confidence < 0.0."""
        from cyberred.intelligence import IntelResult, IntelPriority

        with pytest.raises(ValueError, match="(?i)confidence"):
            IntelResult(
                source="test",
                cve_id=None,
                severity="medium",
                exploit_available=False,
                exploit_path=None,
                confidence=-0.1,  # Invalid
                priority=IntelPriority.EXPLOITDB,
            )

    @pytest.mark.unit
    def test_intel_result_validation_invalid_priority(self) -> None:
        """IntelResult raises ValueError for invalid priority value."""
        from cyberred.intelligence import IntelResult

        with pytest.raises(ValueError, match="(?i)priority"):
            IntelResult(
                source="test",
                cve_id=None,
                severity="info",
                exploit_available=False,
                exploit_path=None,
                confidence=1.0,
                priority=999,  # Invalid
            )

    @pytest.mark.unit
    def test_intel_result_sorting_by_priority(self) -> None:
        """IntelResult objects can be sorted by priority (AC: 5)."""
        from cyberred.intelligence import IntelResult, IntelPriority

        results = [
            IntelResult(
                source="exploitdb",
                cve_id=None,
                severity="high",
                exploit_available=True,
                exploit_path="12345",
                confidence=0.8,
                priority=IntelPriority.EXPLOITDB,
            ),
            IntelResult(
                source="cisa_kev",
                cve_id="CVE-2021-44228",
                severity="critical",
                exploit_available=True,
                exploit_path=None,
                confidence=1.0,
                priority=IntelPriority.CISA_KEV,
            ),
            IntelResult(
                source="metasploit",
                cve_id="CVE-2021-44228",
                severity="critical",
                exploit_available=True,
                exploit_path="exploit/multi/http/log4shell",
                confidence=0.95,
                priority=IntelPriority.METASPLOIT,
            ),
        ]

        sorted_results = sorted(results, key=lambda r: r.priority)

        assert sorted_results[0].source == "cisa_kev"
        assert sorted_results[1].source == "metasploit"
        assert sorted_results[2].source == "exploitdb"


class TestIntelligenceSource:
    """Tests for IntelligenceSource ABC (AC: 1, 2, 3)."""

    @pytest.mark.unit
    def test_intelligence_source_is_abstract(self) -> None:
        """IntelligenceSource cannot be instantiated directly."""
        from cyberred.intelligence import IntelligenceSource

        with pytest.raises(TypeError, match="abstract"):
            IntelligenceSource(name="test")  # type: ignore[abstract]

    @pytest.mark.unit
    def test_subclass_without_query_raises_typeerror(self) -> None:
        """Subclass without query() implementation raises TypeError."""
        from cyberred.intelligence import IntelligenceSource, IntelResult

        class IncompleteSource(IntelligenceSource):
            async def health_check(self) -> bool:
                return True
            # Missing query() method

        with pytest.raises(TypeError, match="query"):
            IncompleteSource(name="incomplete")

    @pytest.mark.unit
    def test_subclass_without_health_check_raises_typeerror(self) -> None:
        """Subclass without health_check() implementation raises TypeError."""
        from cyberred.intelligence import IntelligenceSource, IntelResult
        from typing import List

        class IncompleteSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []
            # Missing health_check() method

        with pytest.raises(TypeError, match="health_check"):
            IncompleteSource(name="incomplete")

    @pytest.mark.unit
    def test_concrete_subclass_works(self) -> None:
        """Concrete subclass implementing both methods can be instantiated."""
        from cyberred.intelligence import IntelligenceSource, IntelResult
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []

            async def health_check(self) -> bool:
                return True

        source = MockSource(name="mock")
        
        assert source.name == "mock"

    @pytest.mark.unit
    def test_intelligence_source_default_timeout(self) -> None:
        """IntelligenceSource has default timeout of 5.0 seconds (FR74)."""
        from cyberred.intelligence import IntelligenceSource, IntelResult
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []

            async def health_check(self) -> bool:
                return True

        source = MockSource(name="mock")
        
        assert source.timeout == 5.0

    @pytest.mark.unit
    def test_intelligence_source_custom_timeout(self) -> None:
        """IntelligenceSource timeout can be customized."""
        from cyberred.intelligence import IntelligenceSource, IntelResult
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []

            async def health_check(self) -> bool:
                return True

        source = MockSource(name="mock", timeout=10.0)
        
        assert source.timeout == 10.0

    @pytest.mark.unit
    def test_intelligence_source_priority_property(self) -> None:
        """IntelligenceSource exposes priority property (AC: 3)."""
        from cyberred.intelligence import IntelligenceSource, IntelResult, IntelPriority
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []

            async def health_check(self) -> bool:
                return True

        # Default priority
        source_default = MockSource(name="mock")
        assert source_default.priority == IntelPriority.EXPLOITDB

        # Custom priority
        source_custom = MockSource(name="cisa", priority=IntelPriority.CISA_KEV)
        assert source_custom.priority == IntelPriority.CISA_KEV

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_intelligence_source_query_returns_list(self) -> None:
        """Concrete source query() returns List[IntelResult]."""
        from cyberred.intelligence import IntelligenceSource, IntelResult, IntelPriority
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return [
                    IntelResult(
                        source="mock",
                        cve_id="CVE-2021-1234",
                        severity="high",
                        exploit_available=False,
                        exploit_path=None,
                        confidence=0.9,
                        priority=self.priority,
                    )
                ]

            async def health_check(self) -> bool:
                return True

        source = MockSource(name="mock")
        results = await source.query("Apache", "2.4.49")

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], IntelResult)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_intelligence_source_health_check_returns_bool(self) -> None:
        """Concrete source health_check() returns bool."""
        from cyberred.intelligence import IntelligenceSource, IntelResult
        from typing import List

        class MockSource(IntelligenceSource):
            async def query(self, service: str, version: str) -> List[IntelResult]:
                return []

            async def health_check(self) -> bool:
                return True

        source = MockSource(name="mock")
        result = await source.health_check()

        assert isinstance(result, bool)
        assert result is True


class TestModuleExports:
    """Tests for module-level exports (AC: 6)."""

    @pytest.mark.unit
    def test_module_exports_intelligence_source(self) -> None:
        """IntelligenceSource is exported from cyberred.intelligence."""
        from cyberred.intelligence import IntelligenceSource
        
        assert IntelligenceSource is not None

    @pytest.mark.unit
    def test_module_exports_intel_result(self) -> None:
        """IntelResult is exported from cyberred.intelligence."""
        from cyberred.intelligence import IntelResult
        
        assert IntelResult is not None

    @pytest.mark.unit
    def test_module_exports_intel_priority(self) -> None:
        """IntelPriority is exported from cyberred.intelligence."""
        from cyberred.intelligence import IntelPriority
        
        assert IntelPriority is not None
