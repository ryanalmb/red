"""Unit tests for Kimi K2 Analyst Role (Story 8.3).

Tests cover:
- AnalystResponse dataclass
- SecurityGap dataclass
- OverlookedOpportunity dataclass
- RiskAssessment dataclass
- FindingDetail dataclass
- TargetEnvironment dataclass
- AttackPath dataclass
- query_analyst() method
- Gap and opportunity extraction
- Risk assessment extraction
- Enhanced analyst system prompt
- Timeout configuration (100s per architecture)
"""

from __future__ import annotations

from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    ModelResponse,
)
from cyberred.llm.provider import LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


class TestSecurityGap:
    """Tests for SecurityGap dataclass."""
    
    def test_create_valid_gap(self) -> None:
        """Test creating SecurityGap with valid data."""
        from cyberred.llm.ensemble import SecurityGap
        
        gap = SecurityGap(
            gap_id="GAP-001",
            description="Missing input validation on login form",
            severity="HIGH",
            affected_assets=["web-server-01", "api-gateway"],
        )
        assert gap.gap_id == "GAP-001"
        assert gap.description == "Missing input validation on login form"
        assert gap.severity == "HIGH"
        assert len(gap.affected_assets) == 2
    
    def test_empty_gap_id_raises(self) -> None:
        """Test that empty gap_id raises ValueError."""
        from cyberred.llm.ensemble import SecurityGap
        
        with pytest.raises(ValueError, match="gap_id cannot be empty"):
            SecurityGap(
                gap_id="",
                description="Test",
                severity="HIGH",
                affected_assets=[],
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import SecurityGap
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            SecurityGap(
                gap_id="GAP-001",
                description="",
                severity="HIGH",
                affected_assets=[],
            )
    
    def test_invalid_severity_raises(self) -> None:
        """Test that invalid severity raises ValueError."""
        from cyberred.llm.ensemble import SecurityGap
        
        with pytest.raises(ValueError, match="Invalid severity"):
            SecurityGap(
                gap_id="GAP-001",
                description="Test",
                severity="INVALID",
                affected_assets=[],
            )
    
    def test_all_valid_severities(self) -> None:
        """Test all valid severity levels."""
        from cyberred.llm.ensemble import SecurityGap
        
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            gap = SecurityGap(
                gap_id="GAP-001",
                description="Test",
                severity=severity,
                affected_assets=[],
            )
            assert gap.severity == severity


class TestOverlookedOpportunity:
    """Tests for OverlookedOpportunity dataclass."""
    
    def test_create_valid_opportunity(self) -> None:
        """Test creating OverlookedOpportunity with valid data."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        opp = OverlookedOpportunity(
            opportunity_id="OPP-001",
            description="Exposed admin panel without rate limiting",
            potential_impact="Full administrative access",
            recommended_action="Attempt credential stuffing",
            confidence=0.85,
        )
        assert opp.opportunity_id == "OPP-001"
        assert opp.description == "Exposed admin panel without rate limiting"
        assert opp.potential_impact == "Full administrative access"
        assert opp.recommended_action == "Attempt credential stuffing"
        assert opp.confidence == 0.85
    
    def test_empty_opportunity_id_raises(self) -> None:
        """Test that empty opportunity_id raises ValueError."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        with pytest.raises(ValueError, match="opportunity_id cannot be empty"):
            OverlookedOpportunity(
                opportunity_id="",
                description="Test",
                potential_impact="Test",
                recommended_action="Test",
                confidence=0.5,
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            OverlookedOpportunity(
                opportunity_id="OPP-001",
                description="",
                potential_impact="Test",
                recommended_action="Test",
                confidence=0.5,
            )
    
    def test_confidence_below_zero_raises(self) -> None:
        """Test that confidence < 0.0 raises ValueError."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            OverlookedOpportunity(
                opportunity_id="OPP-001",
                description="Test",
                potential_impact="Test",
                recommended_action="Test",
                confidence=-0.1,
            )
    
    def test_confidence_above_one_raises(self) -> None:
        """Test that confidence > 1.0 raises ValueError."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            OverlookedOpportunity(
                opportunity_id="OPP-001",
                description="Test",
                potential_impact="Test",
                recommended_action="Test",
                confidence=1.5,
            )
    
    def test_confidence_boundary_values(self) -> None:
        """Test boundary values for confidence."""
        from cyberred.llm.ensemble import OverlookedOpportunity
        
        # Test 0.0 is valid
        opp_zero = OverlookedOpportunity(
            opportunity_id="OPP-001",
            description="Test",
            potential_impact="Test",
            recommended_action="Test",
            confidence=0.0,
        )
        assert opp_zero.confidence == 0.0
        
        # Test 1.0 is valid
        opp_one = OverlookedOpportunity(
            opportunity_id="OPP-002",
            description="Test",
            potential_impact="Test",
            recommended_action="Test",
            confidence=1.0,
        )
        assert opp_one.confidence == 1.0


class TestRiskAssessment:
    """Tests for RiskAssessment dataclass."""
    
    def test_create_valid_risk_assessment(self) -> None:
        """Test creating RiskAssessment with valid data."""
        from cyberred.llm.ensemble import RiskAssessment
        
        assessment = RiskAssessment(
            overall_risk_level="HIGH",
            risk_factors=["Exposed services", "Weak authentication"],
            mitigations_needed=["Implement MFA", "Enable firewall"],
            confidence=0.9,
        )
        assert assessment.overall_risk_level == "HIGH"
        assert len(assessment.risk_factors) == 2
        assert len(assessment.mitigations_needed) == 2
        assert assessment.confidence == 0.9
    
    def test_invalid_risk_level_raises(self) -> None:
        """Test that invalid risk level raises ValueError."""
        from cyberred.llm.ensemble import RiskAssessment
        
        with pytest.raises(ValueError, match="Invalid risk level"):
            RiskAssessment(
                overall_risk_level="INVALID",
                risk_factors=[],
                mitigations_needed=[],
                confidence=0.5,
            )
    
    def test_all_valid_risk_levels(self) -> None:
        """Test all valid risk levels."""
        from cyberred.llm.ensemble import RiskAssessment
        
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            assessment = RiskAssessment(
                overall_risk_level=level,
                risk_factors=[],
                mitigations_needed=[],
                confidence=0.5,
            )
            assert assessment.overall_risk_level == level
    
    def test_confidence_below_zero_raises(self) -> None:
        """Test that confidence < 0.0 raises ValueError."""
        from cyberred.llm.ensemble import RiskAssessment
        
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=[],
                mitigations_needed=[],
                confidence=-0.1,
            )
    
    def test_confidence_above_one_raises(self) -> None:
        """Test that confidence > 1.0 raises ValueError."""
        from cyberred.llm.ensemble import RiskAssessment
        
        with pytest.raises(ValueError, match="confidence must be 0.0-1.0"):
            RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=[],
                mitigations_needed=[],
                confidence=1.5,
            )


class TestFindingDetail:
    """Tests for FindingDetail dataclass."""
    
    def test_create_valid_finding_detail(self) -> None:
        """Test creating FindingDetail with valid data."""
        from cyberred.llm.ensemble import FindingDetail
        
        finding = FindingDetail(
            finding_id="FIND-001",
            finding_type="vulnerability",
            target="192.168.1.10",
            service="http",
            severity="HIGH",
            description="SQL Injection in login form",
            evidence="Error: MySQL syntax",
        )
        assert finding.finding_id == "FIND-001"
        assert finding.finding_type == "vulnerability"
        assert finding.target == "192.168.1.10"
        assert finding.service == "http"
        assert finding.severity == "HIGH"
        assert finding.description == "SQL Injection in login form"
        assert finding.evidence == "Error: MySQL syntax"
    
    def test_finding_without_evidence(self) -> None:
        """Test creating FindingDetail without evidence."""
        from cyberred.llm.ensemble import FindingDetail
        
        finding = FindingDetail(
            finding_id="FIND-002",
            finding_type="exposure",
            target="192.168.1.20",
            service="ssh",
            severity="MEDIUM",
            description="SSH service exposed",
        )
        assert finding.evidence is None
    
    def test_empty_finding_id_raises(self) -> None:
        """Test that empty finding_id raises ValueError."""
        from cyberred.llm.ensemble import FindingDetail
        
        with pytest.raises(ValueError, match="finding_id cannot be empty"):
            FindingDetail(
                finding_id="",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="HIGH",
                description="Test",
            )
    
    def test_invalid_severity_raises(self) -> None:
        """Test that invalid severity raises ValueError."""
        from cyberred.llm.ensemble import FindingDetail
        
        with pytest.raises(ValueError, match="Invalid severity"):
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="INVALID",
                description="Test",
            )


class TestTargetEnvironment:
    """Tests for TargetEnvironment dataclass."""
    
    def test_create_valid_target_environment(self) -> None:
        """Test creating TargetEnvironment with valid data."""
        from cyberred.llm.ensemble import TargetEnvironment
        
        env = TargetEnvironment(
            environment_type="corporate",
            discovered_hosts=25,
            discovered_services=78,
            os_distribution={"Windows": 15, "Linux": 10},
            network_segments=["192.168.1.0/24", "10.0.0.0/8"],
        )
        assert env.environment_type == "corporate"
        assert env.discovered_hosts == 25
        assert env.discovered_services == 78
        assert env.os_distribution["Windows"] == 15
        assert len(env.network_segments) == 2
    
    def test_negative_discovered_hosts_raises(self) -> None:
        """Test that negative discovered_hosts raises ValueError."""
        from cyberred.llm.ensemble import TargetEnvironment
        
        with pytest.raises(ValueError, match="discovered_hosts cannot be negative"):
            TargetEnvironment(
                environment_type="corporate",
                discovered_hosts=-1,
                discovered_services=10,
                os_distribution={},
                network_segments=[],
            )
    
    def test_negative_discovered_services_raises(self) -> None:
        """Test that negative discovered_services raises ValueError."""
        from cyberred.llm.ensemble import TargetEnvironment
        
        with pytest.raises(ValueError, match="discovered_services cannot be negative"):
            TargetEnvironment(
                environment_type="corporate",
                discovered_hosts=10,
                discovered_services=-1,
                os_distribution={},
                network_segments=[],
            )


class TestAttackPath:
    """Tests for AttackPath dataclass."""
    
    def test_create_valid_attack_path(self) -> None:
        """Test creating AttackPath with valid data."""
        from cyberred.llm.ensemble import AttackPath
        
        path = AttackPath(
            path_id="PATH-001",
            entry_point="Web server SQL injection",
            steps=["Exploit SQLi", "Extract credentials", "Pivot to DB server"],
            target_asset="Domain Controller",
            success_probability=0.75,
        )
        assert path.path_id == "PATH-001"
        assert path.entry_point == "Web server SQL injection"
        assert len(path.steps) == 3
        assert path.target_asset == "Domain Controller"
        assert path.success_probability == 0.75
    
    def test_empty_path_id_raises(self) -> None:
        """Test that empty path_id raises ValueError."""
        from cyberred.llm.ensemble import AttackPath
        
        with pytest.raises(ValueError, match="path_id cannot be empty"):
            AttackPath(
                path_id="",
                entry_point="Test",
                steps=[],
                target_asset="Test",
                success_probability=0.5,
            )
    
    def test_probability_below_zero_raises(self) -> None:
        """Test that success_probability < 0.0 raises ValueError."""
        from cyberred.llm.ensemble import AttackPath
        
        with pytest.raises(ValueError, match="success_probability must be 0.0-1.0"):
            AttackPath(
                path_id="PATH-001",
                entry_point="Test",
                steps=[],
                target_asset="Test",
                success_probability=-0.1,
            )
    
    def test_probability_above_one_raises(self) -> None:
        """Test that success_probability > 1.0 raises ValueError."""
        from cyberred.llm.ensemble import AttackPath
        
        with pytest.raises(ValueError, match="success_probability must be 0.0-1.0"):
            AttackPath(
                path_id="PATH-001",
                entry_point="Test",
                steps=[],
                target_asset="Test",
                success_probability=1.5,
            )


class TestAnalystResponse:
    """Tests for AnalystResponse dataclass."""
    
    def test_create_valid_analyst_response(self) -> None:
        """Test creating AnalystResponse with valid data."""
        from cyberred.llm.ensemble import (
            AnalystResponse,
            SecurityGap,
            OverlookedOpportunity,
            RiskAssessment,
        )
        
        model_resp = ModelResponse(
            role=DirectorRole.ANALYST,
            model_id="moonshotai/kimi-k2-instruct",
            content="Analyst response content",
            latency_ms=2000,
            success=True,
        )
        
        response = AnalystResponse(
            raw_content="Full analyst response...",
            attack_surface_analysis="Comprehensive analysis of exposed services",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=["Exposed admin panel"],
                mitigations_needed=["Implement authentication"],
                confidence=0.85,
            ),
            gaps=[
                SecurityGap(
                    gap_id="GAP-001",
                    description="No rate limiting",
                    severity="MEDIUM",
                    affected_assets=["api-server"],
                )
            ],
            overlooked_opportunities=[
                OverlookedOpportunity(
                    opportunity_id="OPP-001",
                    description="Default credentials possible",
                    potential_impact="Full access",
                    recommended_action="Try default creds",
                    confidence=0.7,
                )
            ],
            model_response=model_resp,
        )
        
        assert response.raw_content == "Full analyst response..."
        assert "Comprehensive analysis" in response.attack_surface_analysis
        assert response.risk_assessment.overall_risk_level == "HIGH"
        assert len(response.gaps) == 1
        assert len(response.overlooked_opportunities) == 1
    
    def test_analyst_response_empty_lists_valid(self) -> None:
        """Test that empty gaps and opportunities lists are valid."""
        from cyberred.llm.ensemble import AnalystResponse, RiskAssessment
        
        model_resp = ModelResponse(
            role=DirectorRole.ANALYST,
            model_id="test",
            content="test",
            latency_ms=100,
            success=True,
        )
        
        response = AnalystResponse(
            raw_content="Minimal response",
            attack_surface_analysis="No significant attack surface",
            risk_assessment=RiskAssessment(
                overall_risk_level="LOW",
                risk_factors=[],
                mitigations_needed=[],
                confidence=0.5,
            ),
            gaps=[],
            overlooked_opportunities=[],
            model_response=model_resp,
        )
        
        assert len(response.gaps) == 0
        assert len(response.overlooked_opportunities) == 0


class TestGapExtraction:
    """Tests for extract_gaps function."""
    
    def test_extract_single_gap(self) -> None:
        """Test extracting single security gap from response."""
        from cyberred.llm.ensemble import extract_gaps
        
        response_text = """
        ### Security Gaps
        | Gap ID | Description | Severity | Affected Assets |
        |--------|-------------|----------|-----------------|
        | GAP-001 | Missing rate limiting on API | HIGH | api-server, web-app |
        """
        
        gaps = extract_gaps(response_text)
        
        assert len(gaps) == 1
        assert gaps[0].gap_id == "GAP-001"
        assert "rate limiting" in gaps[0].description.lower()
        assert gaps[0].severity == "HIGH"
        assert len(gaps[0].affected_assets) >= 1
    
    def test_extract_multiple_gaps(self) -> None:
        """Test extracting multiple gaps from response."""
        from cyberred.llm.ensemble import extract_gaps
        
        response_text = """
        ### Security Gaps
        | Gap ID | Description | Severity | Affected Assets |
        |--------|-------------|----------|-----------------|
        | GAP-001 | Missing input validation | CRITICAL | web-server |
        | GAP-002 | Weak password policy | HIGH | auth-service |
        | GAP-003 | Outdated SSL certificates | MEDIUM | all-services |
        """
        
        gaps = extract_gaps(response_text)
        
        assert len(gaps) == 3
        assert gaps[0].gap_id == "GAP-001"
        assert gaps[0].severity == "CRITICAL"
        assert gaps[1].gap_id == "GAP-002"
        assert gaps[2].gap_id == "GAP-003"
    
    def test_extract_no_gaps(self) -> None:
        """Test extraction returns empty list when no gaps found."""
        from cyberred.llm.ensemble import extract_gaps
        
        response_text = """
        General analysis without security gaps table.
        Focus on reconnaissance results.
        """
        
        gaps = extract_gaps(response_text)
        
        assert len(gaps) == 0
    
    def test_extract_gaps_invalid_severity_skipped(self) -> None:
        """Test that gaps with invalid severity are skipped."""
        from cyberred.llm.ensemble import extract_gaps
        
        response_text = """
        ### Security Gaps
        | Gap ID | Description | Severity | Affected Assets |
        |--------|-------------|----------|-----------------|
        | GAP-001 | Valid gap | HIGH | server |
        | GAP-002 | Invalid severity | UNKNOWN | server |
        """
        
        gaps = extract_gaps(response_text)
        
        # Only valid gap should be extracted
        assert len(gaps) == 1
        assert gaps[0].gap_id == "GAP-001"


class TestOpportunityExtraction:
    """Tests for extract_opportunities function."""
    
    def test_extract_single_opportunity(self) -> None:
        """Test extracting single overlooked opportunity from response."""
        from cyberred.llm.ensemble import extract_opportunities
        
        response_text = """
        ### Overlooked Opportunities
        | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
        |----------------|-------------|------------------|-------------------|------------|
        | OPP-001 | Exposed admin panel | Full admin access | Try default credentials | 0.8 |
        """
        
        opportunities = extract_opportunities(response_text)
        
        assert len(opportunities) == 1
        assert opportunities[0].opportunity_id == "OPP-001"
        assert "admin panel" in opportunities[0].description.lower()
        assert opportunities[0].confidence == 0.8
    
    def test_extract_multiple_opportunities(self) -> None:
        """Test extracting multiple opportunities from response."""
        from cyberred.llm.ensemble import extract_opportunities
        
        response_text = """
        ### Overlooked Opportunities
        | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
        |----------------|-------------|------------------|-------------------|------------|
        | OPP-001 | Unprotected backup files | Data exfiltration | Download backups | 0.9 |
        | OPP-002 | Debug endpoint exposed | Code execution | Test for RCE | 0.7 |
        | OPP-003 | API without auth | Unauthorized access | Enumerate API | 0.85 |
        """
        
        opportunities = extract_opportunities(response_text)
        
        assert len(opportunities) == 3
        assert opportunities[0].opportunity_id == "OPP-001"
        assert opportunities[1].opportunity_id == "OPP-002"
        assert opportunities[2].confidence == 0.85
    
    def test_extract_no_opportunities(self) -> None:
        """Test extraction returns empty list when no opportunities found."""
        from cyberred.llm.ensemble import extract_opportunities
        
        response_text = """
        General analysis without opportunities table.
        """
        
        opportunities = extract_opportunities(response_text)
        
        assert len(opportunities) == 0
    
    def test_extract_opportunities_invalid_confidence_skipped(self) -> None:
        """Test that opportunities with invalid confidence are skipped."""
        from cyberred.llm.ensemble import extract_opportunities
        
        response_text = """
        ### Overlooked Opportunities
        | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
        |----------------|-------------|------------------|-------------------|------------|
        | OPP-001 | Valid | Impact | Action | 0.8 |
        | OPP-002 | Invalid confidence | Impact | Action | not_a_number |
        """
        
        opportunities = extract_opportunities(response_text)
        
        assert len(opportunities) == 1
        assert opportunities[0].opportunity_id == "OPP-001"


class TestRiskAssessmentExtraction:
    """Tests for extract_risk_assessment function."""
    
    def test_extract_complete_risk_assessment(self) -> None:
        """Test extracting complete risk assessment from response."""
        from cyberred.llm.ensemble import extract_risk_assessment
        
        response_text = """
        ### Risk Assessment
        **Overall Risk Level:** HIGH
        **Risk Factors:**
        - Exposed critical services
        - Weak authentication
        **Mitigations Needed:**
        - Implement firewall rules
        - Enable MFA
        **Confidence:** 0.85
        """
        
        assessment = extract_risk_assessment(response_text)
        
        assert assessment.overall_risk_level == "HIGH"
        assert len(assessment.risk_factors) >= 2
        assert len(assessment.mitigations_needed) >= 2
        assert assessment.confidence == 0.85
    
    def test_extract_risk_assessment_critical(self) -> None:
        """Test extracting CRITICAL risk assessment."""
        from cyberred.llm.ensemble import extract_risk_assessment
        
        response_text = """
        ### Risk Assessment
        **Overall Risk Level:** CRITICAL
        **Risk Factors:**
        - Remote code execution vulnerability
        **Mitigations Needed:**
        - Patch immediately
        **Confidence:** 0.95
        """
        
        assessment = extract_risk_assessment(response_text)
        
        assert assessment.overall_risk_level == "CRITICAL"
        assert assessment.confidence == 0.95
    
    def test_extract_risk_assessment_not_found_returns_default(self) -> None:
        """Test default risk assessment when not found."""
        from cyberred.llm.ensemble import extract_risk_assessment
        
        response_text = """
        General analysis without risk assessment section.
        """
        
        assessment = extract_risk_assessment(response_text)
        
        # Default values when not found
        assert assessment.overall_risk_level == "MEDIUM"
        assert assessment.confidence == 0.5
    
    def test_extract_risk_assessment_all_levels(self) -> None:
        """Test extracting all valid risk levels."""
        from cyberred.llm.ensemble import extract_risk_assessment
        
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            response_text = f"""
            ### Risk Assessment
            **Overall Risk Level:** {level}
            **Risk Factors:**
            - Test factor
            **Mitigations Needed:**
            - Test mitigation
            **Confidence:** 0.5
            """
            
            assessment = extract_risk_assessment(response_text)
            assert assessment.overall_risk_level == level


class TestQueryAnalyst:
    """Tests for query_analyst() method."""
    
    @pytest.mark.asyncio
    async def test_query_analyst_success(self) -> None:
        """Test successful analyst query with structured response."""
        from cyberred.llm.ensemble import (
            FindingDetail,
            TargetEnvironment,
            AttackPath,
        )
        
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Analyze attack surface",
        )
        
        findings_details = [
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="HIGH",
                description="SQL Injection",
            )
        ]
        
        target_environment = TargetEnvironment(
            environment_type="corporate",
            discovered_hosts=10,
            discovered_services=25,
            os_distribution={"Windows": 5, "Linux": 5},
            network_segments=["192.168.1.0/24"],
        )
        
        discovered_paths = [
            AttackPath(
                path_id="PATH-001",
                entry_point="Web SQLi",
                steps=["Exploit SQLi", "Dump DB"],
                target_asset="Database",
                success_probability=0.8,
            )
        ]
        
        mock_llm_response = LLMResponse(
            content="""
            ### Attack Surface Analysis
            The target environment exposes multiple attack vectors through the web application.
            
            ### Risk Assessment
            **Overall Risk Level:** HIGH
            **Risk Factors:**
            - SQL Injection vulnerability in login form
            - Exposed database port
            **Mitigations Needed:**
            - Input validation
            - Network segmentation
            **Confidence:** 0.85
            
            ### Security Gaps
            | Gap ID | Description | Severity | Affected Assets |
            |--------|-------------|----------|-----------------|
            | GAP-001 | No WAF in place | HIGH | web-server |
            
            ### Overlooked Opportunities
            | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
            |----------------|-------------|------------------|-------------------|------------|
            | OPP-001 | Backup files exposed | Data leak | Download backups | 0.9 |
            """,
            model="moonshotai/kimi-k2-instruct",
            usage=TokenUsage(prompt_tokens=600, completion_tokens=400, total_tokens=1000),
            latency_ms=3000,
        )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(return_value=mock_llm_response)
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_analyst(
                context=context,
                findings_details=findings_details,
                target_environment=target_environment,
                discovered_paths=discovered_paths,
            )
        
        from cyberred.llm.ensemble import AnalystResponse
        assert isinstance(response, AnalystResponse)
        assert response.model_response.success is True
        assert "attack vectors" in response.attack_surface_analysis.lower()
        assert response.risk_assessment.overall_risk_level == "HIGH"
        assert len(response.gaps) >= 1
        assert len(response.overlooked_opportunities) >= 1
    
    @pytest.mark.asyncio
    async def test_query_analyst_timeout(self) -> None:
        """Test analyst query timeout handling (100s timeout per architecture)."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorModel
        
        custom_models = DIRECTOR_MODELS.copy()
        custom_models[DirectorRole.ANALYST] = DirectorModel(
            model_id="moonshotai/kimi-k2-instruct",
            role=DirectorRole.ANALYST,
            timeout=0.001,  # 1ms for test
            system_prompt="test",
        )
        
        ensemble = DirectorEnsemble(models=custom_models)
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test timeout",
        )
        
        async def slow_complete(*args, **kwargs):
            import asyncio
            await asyncio.sleep(1)
            return LLMResponse(
                content="Too slow",
                model="test",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                latency_ms=1000,
            )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = slow_complete
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            with pytest.raises(LLMTimeoutError):
                await ensemble.query_analyst(context)
    
    @pytest.mark.asyncio
    async def test_query_analyst_builds_enhanced_prompt(self) -> None:
        """Test that analyst query includes findings, environment, and paths."""
        from cyberred.llm.ensemble import (
            FindingDetail,
            TargetEnvironment,
            AttackPath,
        )
        
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Analyze gaps",
        )
        
        findings_details = [
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="CRITICAL",
                description="Remote Code Execution",
            )
        ]
        
        target_environment = TargetEnvironment(
            environment_type="cloud",
            discovered_hosts=50,
            discovered_services=120,
            os_distribution={"Linux": 50},
            network_segments=["10.0.0.0/8"],
        )
        
        discovered_paths = [
            AttackPath(
                path_id="PATH-001",
                entry_point="RCE on web app",
                steps=["Exploit RCE", "Establish shell"],
                target_asset="Application server",
                success_probability=0.9,
            )
        ]
        
        captured_request = None
        
        async def capture_request(request, *args, **kwargs):
            nonlocal captured_request
            captured_request = request
            return LLMResponse(
                content="### Attack Surface Analysis\nAnalysis here.",
                model="test",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                latency_ms=500,
            )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = capture_request
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            await ensemble.query_analyst(
                context=context,
                findings_details=findings_details,
                target_environment=target_environment,
                discovered_paths=discovered_paths,
            )
        
        assert captured_request is not None
        prompt = captured_request.prompt
        
        # Verify findings included
        assert "FIND-001" in prompt or "Remote Code Execution" in prompt
        assert "CRITICAL" in prompt
        
        # Verify environment included
        assert "cloud" in prompt.lower() or "50" in prompt
        
        # Verify paths included
        assert "PATH-001" in prompt or "RCE on web app" in prompt
    
    @pytest.mark.asyncio
    async def test_query_analyst_provider_unavailable(self) -> None:
        """Test analyst query error handling for provider unavailable."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test error",
        )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=LLMProviderUnavailable("Model not available")
        )
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            with pytest.raises(LLMProviderUnavailable, match="Analyst query failed"):
                await ensemble.query_analyst(context)


class TestAnalystSystemPrompt:
    """Tests for enhanced analyst system prompt."""
    
    def test_analyst_prompt_includes_structured_output(self) -> None:
        """Test that analyst system prompt specifies structured output format."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_prompt = DIRECTOR_MODELS[DirectorRole.ANALYST].system_prompt
        
        # Should specify structured output sections
        assert any(keyword in analyst_prompt.lower() for keyword in [
            "attack surface",
            "risk",
            "gap",
            "opportunit",
            "format",
        ])
    
    def test_analyst_timeout_is_100s(self) -> None:
        """Test that analyst timeout is 100s per architecture."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_model = DIRECTOR_MODELS[DirectorRole.ANALYST]
        
        assert analyst_model.timeout == 100.0
    
    def test_analyst_model_id_is_kimi_k2(self) -> None:
        """Test that analyst model is Kimi K2."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_model = DIRECTOR_MODELS[DirectorRole.ANALYST]
        
        # Model ID should be Kimi K2 variant
        assert "kimi" in analyst_model.model_id.lower()


class TestBuildAnalystPrompt:
    """Tests for _build_analyst_prompt method."""
    
    def test_build_analyst_prompt_with_all_context(self) -> None:
        """Test building analyst prompt with full context."""
        from cyberred.llm.ensemble import (
            FindingDetail,
            TargetEnvironment,
            AttackPath,
        )
        
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-test",
            phase="exploitation",
            prompt="Identify gaps",
            constraints={"no_destructive": True},
        )
        
        findings_details = [
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="HIGH",
                description="SQL Injection vulnerability",
            )
        ]
        
        target_environment = TargetEnvironment(
            environment_type="hybrid",
            discovered_hosts=30,
            discovered_services=85,
            os_distribution={"Windows": 20, "Linux": 10},
            network_segments=["192.168.0.0/16"],
        )
        
        discovered_paths = [
            AttackPath(
                path_id="PATH-001",
                entry_point="SQLi exploit",
                steps=["Exploit SQLi", "Pivot"],
                target_asset="Domain controller",
                success_probability=0.7,
            )
        ]
        
        prompt = ensemble._build_analyst_prompt(
            context, findings_details, target_environment, discovered_paths
        )
        
        # Verify all components included
        assert "eng-test" in prompt
        assert "exploitation" in prompt
        
        # Verify findings
        assert "FIND-001" in prompt
        assert "SQL Injection" in prompt
        assert "HIGH" in prompt
        
        # Verify environment
        assert "hybrid" in prompt.lower()
        assert "30" in prompt  # discovered_hosts
        
        # Verify paths
        assert "PATH-001" in prompt
        assert "SQLi exploit" in prompt
        
        # Verify constraints
        assert "no_destructive" in prompt.lower()
    
    def test_build_analyst_prompt_minimal(self) -> None:
        """Test building analyst prompt with minimal context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-minimal",
            phase="recon",
            prompt="Basic analysis",
        )
        
        prompt = ensemble._build_analyst_prompt(context)
        
        assert "eng-minimal" in prompt
        assert "recon" in prompt
        assert "Basic analysis" in prompt
    
    def test_build_analyst_prompt_with_finding_evidence(self) -> None:
        """Test building analyst prompt with finding that has evidence."""
        from cyberred.llm.ensemble import FindingDetail
        
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-test",
            phase="exploitation",
            prompt="Analyze",
        )
        
        findings_details = [
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="192.168.1.10",
                service="http",
                severity="HIGH",
                description="SQL Injection",
                evidence="Error message: You have an error in your SQL syntax near 'SELECT * FROM users WHERE id = 1 OR 1=1'",
            )
        ]
        
        prompt = ensemble._build_analyst_prompt(context, findings_details=findings_details)
        
        assert "Evidence:" in prompt
        assert "SQL syntax" in prompt


class TestExtractAttackSurfaceAnalysis:
    """Tests for _extract_attack_surface_analysis method."""
    
    def test_extract_attack_surface_found(self) -> None:
        """Test extracting attack surface analysis when present."""
        ensemble = DirectorEnsemble()
        content = """
        ### Attack Surface Analysis
        The target exposes multiple attack vectors including web services.
        
        ### Risk Assessment
        **Overall Risk Level:** HIGH
        """
        
        result = ensemble._extract_attack_surface_analysis(content)
        
        assert "multiple attack vectors" in result.lower()
    
    def test_extract_attack_surface_not_found(self) -> None:
        """Test extracting attack surface analysis when not present."""
        ensemble = DirectorEnsemble()
        content = """
        General response without attack surface section.
        """
        
        result = ensemble._extract_attack_surface_analysis(content)
        
        assert result == ""


class TestGapExtractionEdgeCases:
    """Additional edge case tests for gap extraction."""
    
    def test_extract_gaps_with_value_error(self) -> None:
        """Test gap extraction handles ValueError from dataclass validation."""
        from cyberred.llm.ensemble import extract_gaps
        
        # Gap with empty description after strip (edge case)
        response_text = """
        ### Security Gaps
        | Gap ID | Description | Severity | Affected Assets |
        |--------|-------------|----------|-----------------|
        | GAP-001 |    | HIGH | server |
        """
        
        gaps = extract_gaps(response_text)
        
        # Should be skipped due to empty description
        assert len(gaps) == 0


class TestOpportunityExtractionEdgeCases:
    """Additional edge case tests for opportunity extraction."""
    
    def test_extract_opportunities_with_value_error(self) -> None:
        """Test opportunity extraction handles ValueError from dataclass validation."""
        from cyberred.llm.ensemble import extract_opportunities
        
        # Opportunity with confidence out of range
        response_text = """
        ### Overlooked Opportunities
        | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
        |----------------|-------------|------------------|-------------------|------------|
        | OPP-001 | Valid | Impact | Action | 1.5 |
        """
        
        opportunities = extract_opportunities(response_text)
        
        # Should be skipped due to invalid confidence
        assert len(opportunities) == 0


class TestRiskAssessmentExtractionEdgeCases:
    """Additional edge case tests for risk assessment extraction."""
    
    def test_extract_risk_assessment_invalid_confidence(self) -> None:
        """Test risk assessment extraction handles invalid confidence gracefully."""
        from cyberred.llm.ensemble import extract_risk_assessment
        
        response_text = """
        ### Risk Assessment
        **Overall Risk Level:** HIGH
        **Risk Factors:**
        - Test factor
        **Mitigations Needed:**
        - Test mitigation
        **Confidence:** not_a_float
        """
        
        assessment = extract_risk_assessment(response_text)
        
        # Should use default confidence
        assert assessment.overall_risk_level == "HIGH"
        assert assessment.confidence == 0.5  # Default when parse fails


class TestCaseInsensitiveExtraction:
    """Tests for case-insensitive gap and opportunity extraction (code review fix)."""
    
    def test_extract_gaps_lowercase(self) -> None:
        """Test extracting gaps with lowercase gap-xxx IDs."""
        from cyberred.llm.ensemble import extract_gaps
        
        response_text = """
        ### Security Gaps
        | Gap ID | Description | Severity | Affected Assets |
        |--------|-------------|----------|-----------------|
        | gap-001 | Missing rate limiting on API | HIGH | api-server, web-app |
        """
        
        gaps = extract_gaps(response_text)
        
        assert len(gaps) == 1
        assert gaps[0].gap_id == "GAP-001"  # Should be normalized to uppercase
        assert gaps[0].severity == "HIGH"
    
    def test_extract_opportunities_lowercase(self) -> None:
        """Test extracting opportunities with lowercase opp-xxx IDs."""
        from cyberred.llm.ensemble import extract_opportunities
        
        response_text = """
        ### Overlooked Opportunities
        | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
        |----------------|-------------|------------------|-------------------|------------|
        | opp-001 | Exposed admin panel | Full admin access | Try default credentials | 0.8 |
        """
        
        opportunities = extract_opportunities(response_text)
        
        assert len(opportunities) == 1
        assert opportunities[0].opportunity_id == "OPP-001"  # Should be normalized to uppercase
        assert opportunities[0].confidence == 0.8


class TestModuleExports:
    """Tests for module-level exports (code review fix)."""
    
    def test_story_83_exports_from_llm_module(self) -> None:
        """Test that Story 8.3 classes are exported from cyberred.llm."""
        from cyberred.llm import (
            SecurityGap,
            OverlookedOpportunity,
            RiskAssessment,
            FindingDetail,
            TargetEnvironment,
            AttackPath,
            AnalystResponse,
            extract_gaps,
            extract_opportunities,
            extract_risk_assessment,
        )
        
        # Just verify imports work
        assert SecurityGap is not None
        assert OverlookedOpportunity is not None
        assert RiskAssessment is not None
        assert FindingDetail is not None
        assert TargetEnvironment is not None
        assert AttackPath is not None
        assert AnalystResponse is not None
        assert extract_gaps is not None
        assert extract_opportunities is not None
        assert extract_risk_assessment is not None


class TestModelIdConfiguration:
    """Tests for correct model ID configuration (code review fix)."""
    
    def test_analyst_model_id_matches_architecture(self) -> None:
        """Test that analyst model ID matches architecture spec: moonshotai/kimi-k2-instruct."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorRole
        
        analyst_model = DIRECTOR_MODELS[DirectorRole.ANALYST]
        
        # Per architecture and story: moonshotai/kimi-k2-instruct (corrected from moonshot-ai/kimi-k2)
        assert analyst_model.model_id == "moonshotai/kimi-k2-instruct", (
            f"Model ID should be 'moonshotai/kimi-k2-instruct' per architecture, got '{analyst_model.model_id}'"
        )
