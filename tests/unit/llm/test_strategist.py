"""Unit tests for DeepSeek Strategist Role (Story 8.2).

Tests cover:
- StrategistResponse dataclass
- ATTCKRecommendation dataclass  
- SwarmState and FindingsSummary context objects
- query_strategist() method
- ATT&CK technique extraction
- Enhanced strategist system prompt
- Timeout configuration (100s per architecture)
"""

from __future__ import annotations

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    ATTCKRecommendation,
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    FindingsSummary,
    ModelResponse,
    StrategistResponse,
    SwarmState,
    extract_attck_techniques,
)
from cyberred.llm.provider import LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


class TestATTCKRecommendation:
    """Tests for ATTCKRecommendation dataclass."""
    
    def test_create_valid_technique(self) -> None:
        """Test creating ATTCKRecommendation with valid data."""
        rec = ATTCKRecommendation(
            technique_id="T1566.001",
            technique_name="Spearphishing Attachment",
            rationale="Target uses email gateway",
            phase="initial-access",
        )
        assert rec.technique_id == "T1566.001"
        assert rec.technique_name == "Spearphishing Attachment"
        assert rec.rationale == "Target uses email gateway"
        assert rec.phase == "initial-access"
    
    def test_create_main_technique(self) -> None:
        """Test creating main technique without sub-technique."""
        rec = ATTCKRecommendation(
            technique_id="T1078",
            technique_name="Valid Accounts",
            rationale="Credentials discovered",
            phase="persistence",
        )
        assert rec.technique_id == "T1078"
    
    def test_empty_technique_id_raises(self) -> None:
        """Test that empty technique_id raises ValueError."""
        with pytest.raises(ValueError, match="technique_id cannot be empty"):
            ATTCKRecommendation(
                technique_id="",
                technique_name="Test",
                rationale="Test",
                phase="test",
            )
    
    def test_invalid_technique_format_raises(self) -> None:
        """Test that invalid ATT&CK format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ATT&CK technique ID format"):
            ATTCKRecommendation(
                technique_id="INVALID",
                technique_name="Test",
                rationale="Test",
                phase="test",
            )
    
    def test_invalid_technique_short_number_raises(self) -> None:
        """Test that short technique number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ATT&CK technique ID format"):
            ATTCKRecommendation(
                technique_id="T123",  # Should be T#### (4 digits)
                technique_name="Test",
                rationale="Test",
                phase="test",
            )


class TestStrategistResponse:
    """Tests for StrategistResponse dataclass."""
    
    def test_create_valid_response(self) -> None:
        """Test creating StrategistResponse with valid data."""
        model_resp = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek-ai/deepseek-v3.2",
            content="Strategic analysis",
            latency_ms=1500,
            success=True,
        )
        
        response = StrategistResponse(
            raw_content="Full strategic response...",
            recommendations=["Focus on web application", "Enumerate services"],
            next_phases=["exploitation", "privilege-escalation"],
            priorities=[("192.168.1.10", 10), ("192.168.1.20", 7)],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    rationale="Web server exposed",
                    phase="initial-access",
                )
            ],
            confidence=0.85,
            model_response=model_resp,
        )
        
        assert len(response.recommendations) == 2
        assert len(response.next_phases) == 2
        assert len(response.priorities) == 2
        assert response.priorities[0][1] == 10  # First priority score
        assert len(response.attck_techniques) == 1
        assert response.confidence == 0.85
    
    def test_confidence_below_zero_raises(self) -> None:
        """Test that confidence < 0.0 raises ValueError."""
        model_resp = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="test",
            content="test",
            latency_ms=100,
            success=True,
        )
        
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            StrategistResponse(
                raw_content="test",
                recommendations=[],
                next_phases=[],
                priorities=[],
                attck_techniques=[],
                confidence=-0.1,
                model_response=model_resp,
            )
    
    def test_confidence_above_one_raises(self) -> None:
        """Test that confidence > 1.0 raises ValueError."""
        model_resp = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="test",
            content="test",
            latency_ms=100,
            success=True,
        )
        
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            StrategistResponse(
                raw_content="test",
                recommendations=[],
                next_phases=[],
                priorities=[],
                attck_techniques=[],
                confidence=1.5,
                model_response=model_resp,
            )
    
    def test_empty_response_valid(self) -> None:
        """Test that empty lists are valid for strategist response."""
        model_resp = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="test",
            content="test",
            latency_ms=100,
            success=True,
        )
        
        response = StrategistResponse(
            raw_content="No specific recommendations",
            recommendations=[],
            next_phases=[],
            priorities=[],
            attck_techniques=[],
            confidence=0.5,
            model_response=model_resp,
        )
        
        assert len(response.recommendations) == 0
        assert response.confidence == 0.5


class TestATTCKExtraction:
    """Tests for ATT&CK technique extraction from strategist responses."""
    
    def test_extract_single_technique(self) -> None:
        """Test extracting single ATT&CK technique from response."""
        response_text = """
        Strategic recommendation: Target the web application.
        
        ### ATT&CK Techniques
        - T1190 - Exploit Public-Facing Application: Web server exposed on port 80
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 1
        assert techniques[0].technique_id == "T1190"
        assert "Exploit Public-Facing Application" in techniques[0].technique_name
        assert "Web server exposed" in techniques[0].rationale
    
    def test_extract_sub_technique(self) -> None:
        """Test extracting sub-technique format T####.###."""
        response_text = """
        T1566.001 - Spearphishing Attachment: Email gateway identified
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 1
        assert techniques[0].technique_id == "T1566.001"
        assert "Spearphishing" in techniques[0].technique_name
    
    def test_extract_multiple_techniques(self) -> None:
        """Test extracting multiple techniques from response."""
        response_text = """
        ### ATT&CK Techniques
        - T1190 - Exploit Public-Facing Application: Web server exposed
        - T1078 - Valid Accounts: Credentials found in database
        - T1059.001 - PowerShell: Windows environment detected
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 3
        assert techniques[0].technique_id == "T1190"
        assert techniques[1].technique_id == "T1078"
        assert techniques[2].technique_id == "T1059.001"
    
    def test_extract_no_techniques(self) -> None:
        """Test extraction returns empty list when no techniques found."""
        response_text = """
        General strategic analysis without specific ATT&CK references.
        Focus on reconnaissance and enumeration.
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 0
    
    def test_extract_case_insensitive(self) -> None:
        """Test extraction handles lowercase technique IDs."""
        response_text = """
        Consider t1190 - Exploit Public-Facing Application: Target identified
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 1
        assert techniques[0].technique_id == "T1190"  # Normalized to uppercase


class TestQueryStrategist:
    """Tests for query_strategist() method."""
    
    @pytest.mark.asyncio
    async def test_query_strategist_success(self) -> None:
        """Test successful strategist query with structured response."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Analyze attack strategy",
        )
        
        swarm_state = SwarmState(
            active_agents=45,
            phase="exploitation",
            targets_scanned=12,
            findings_count=8,
        )
        
        findings_summary = FindingsSummary(
            critical_count=2,
            high_count=3,
            medium_count=3,
            top_findings=["SQL injection on /admin", "SSH weak password"],
        )
        
        mock_llm_response = LLMResponse(
            content="""
            ### Strategic Recommendations
            1. Prioritize SQL injection for initial access
            2. Enumerate database after successful exploitation
            
            ### Next Phases
            - exploitation: Focus on web application vulnerabilities
            - privilege-escalation: Target database credentials
            
            ### Target Priorities
            | Priority | Target | Rationale |
            |----------|--------|-----------|
            | 1 | 192.168.1.10 | Web server with SQLi |
            | 2 | 192.168.1.20 | Database server |
            
            ### ATT&CK Techniques
            - T1190 - Exploit Public-Facing Application: Web server exposed
            - T1078 - Valid Accounts: Database credentials likely accessible
            
            ### Confidence Assessment
            0.85: High confidence based on clear vulnerability patterns
            """,
            model="deepseek-ai/deepseek-v3.2",
            usage=TokenUsage(prompt_tokens=500, completion_tokens=300, total_tokens=800),
            latency_ms=2500,
        )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(return_value=mock_llm_response)
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_strategist(
                context=context,
                swarm_state=swarm_state,
                findings_summary=findings_summary,
                objective="Gain administrative access",
            )
        
        assert isinstance(response, StrategistResponse)
        assert response.model_response.success is True
        assert len(response.recommendations) > 0
        assert len(response.attck_techniques) >= 2
        assert response.confidence > 0.0
    
    @pytest.mark.asyncio
    async def test_query_strategist_timeout(self) -> None:
        """Test strategist query timeout handling (100s timeout per architecture)."""
        # Use short timeout for test
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorModel
        
        custom_models = DIRECTOR_MODELS.copy()
        custom_models[DirectorRole.STRATEGIST] = DirectorModel(
            model_id="deepseek-ai/deepseek-v3.2",
            role=DirectorRole.STRATEGIST,
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
                await ensemble.query_strategist(context)
    
    @pytest.mark.asyncio
    async def test_query_strategist_builds_enhanced_prompt(self) -> None:
        """Test that strategist query includes swarm state and findings."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Next steps?",
        )
        
        swarm_state = SwarmState(
            active_agents=30,
            phase="exploitation",
            targets_scanned=5,
            findings_count=12,
        )
        
        findings_summary = FindingsSummary(
            critical_count=3,
            high_count=5,
            medium_count=4,
            top_findings=["SQLi vulnerability", "Open admin panel"],
        )
        
        captured_request = None
        
        async def capture_request(request, *args, **kwargs):
            nonlocal captured_request
            captured_request = request
            return LLMResponse(
                content="Strategic response",
                model="test",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                latency_ms=500,
            )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = capture_request
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            await ensemble.query_strategist(
                context=context,
                swarm_state=swarm_state,
                findings_summary=findings_summary,
                objective="Achieve domain admin",
            )
        
        assert captured_request is not None
        prompt = captured_request.prompt
        
        # Verify swarm state included
        assert "30" in prompt  # active_agents
        assert "exploitation" in prompt
        
        # Verify findings summary included
        assert "3" in prompt or "critical" in prompt.lower()
        assert "SQLi" in prompt or "vulnerability" in prompt
        
        # Verify objective included
        assert "domain admin" in prompt.lower()


class TestStrategistSystemPrompt:
    """Tests for enhanced strategist system prompt."""
    
    def test_strategist_prompt_includes_attck(self) -> None:
        """Test that strategist system prompt mentions ATT&CK."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        strategist_prompt = DIRECTOR_MODELS[DirectorRole.STRATEGIST].system_prompt
        
        # Enhanced prompt should mention ATT&CK techniques
        assert "ATT&CK" in strategist_prompt or "attack" in strategist_prompt.lower()
    
    def test_strategist_prompt_includes_structured_output(self) -> None:
        """Test that system prompt specifies structured output format."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        strategist_prompt = DIRECTOR_MODELS[DirectorRole.STRATEGIST].system_prompt
        
        # Should specify output structure
        assert any(keyword in strategist_prompt.lower() for keyword in [
            "recommendations",
            "priorities",
            "phases",
            "format",
        ])
    
    def test_strategist_timeout_is_100s(self) -> None:
        """Test that strategist timeout is 100s per architecture."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        strategist_model = DIRECTOR_MODELS[DirectorRole.STRATEGIST]
        
        assert strategist_model.timeout == 100.0


class TestStrategistResponseParsing:
    """Tests for strategist response parsing methods."""
    
    def test_extract_section_list_recommendations(self) -> None:
        """Test extracting numbered recommendations from section."""
        ensemble = DirectorEnsemble()
        content = """
        ### Strategic Recommendations
        1. Focus on web application vulnerabilities first
        2. Enumerate database credentials after initial access
        3. Establish persistence through scheduled tasks
        
        ### Other Section
        - Other content
        """
        
        recommendations = ensemble._extract_section_list(content, "Strategic Recommendations")
        
        assert len(recommendations) == 3
        assert "web application" in recommendations[0].lower()
        assert "database credentials" in recommendations[1].lower()
        assert "persistence" in recommendations[2].lower()
    
    def test_extract_section_list_bulleted(self) -> None:
        """Test extracting bulleted items from section."""
        ensemble = DirectorEnsemble()
        content = """
        ### Next Phases
        - exploitation: Focus on discovered SQL injection
        - privilege-escalation: Target domain admin accounts
        """
        
        phases = ensemble._extract_section_list(content, "Next Phases")
        
        assert len(phases) == 2
        assert "exploitation" in phases[0].lower()
        assert "privilege-escalation" in phases[1].lower()
    
    def test_extract_section_list_empty(self) -> None:
        """Test extracting from non-existent section returns empty list."""
        ensemble = DirectorEnsemble()
        content = "No strategic recommendations section here"
        
        items = ensemble._extract_section_list(content, "Strategic Recommendations")
        
        assert len(items) == 0
    
    def test_extract_priorities_from_table(self) -> None:
        """Test extracting priorities from markdown table."""
        ensemble = DirectorEnsemble()
        content = """
        ### Target Priorities
        | Priority | Target | Rationale |
        |----------|--------|-----------|
        | 1 | 192.168.1.10 | Web server with SQLi |
        | 2 | 192.168.1.20 | Database server |
        | 3 | 192.168.1.30 | File server |
        """
        
        priorities = ensemble._extract_priorities(content)
        
        assert len(priorities) == 3
        assert priorities[0] == ("192.168.1.10", 1)
        assert priorities[1] == ("192.168.1.20", 2)
        assert priorities[2] == ("192.168.1.30", 3)
    
    def test_extract_priorities_empty(self) -> None:
        """Test extracting priorities with no table returns empty list."""
        ensemble = DirectorEnsemble()
        content = "No priority table here"
        
        priorities = ensemble._extract_priorities(content)
        
        assert len(priorities) == 0
    
    def test_extract_confidence_found(self) -> None:
        """Test extracting confidence score from response."""
        ensemble = DirectorEnsemble()
        content = """
        ### Confidence Assessment
        0.85: High confidence based on clear vulnerability patterns
        """
        
        confidence = ensemble._extract_confidence(content)
        
        assert confidence == 0.85
    
    def test_extract_confidence_not_found(self) -> None:
        """Test default confidence when not found."""
        ensemble = DirectorEnsemble()
        content = "No confidence assessment section"
        
        confidence = ensemble._extract_confidence(content)
        
        assert confidence == 0.5  # Default
    
    def test_extract_confidence_clamped_high(self) -> None:
        """Test confidence is clamped to 1.0 max."""
        ensemble = DirectorEnsemble()
        content_high = "### Confidence Assessment\n1.5: Too high"
        
        assert ensemble._extract_confidence(content_high) == 1.0
    
    def test_extract_confidence_clamped_low(self) -> None:
        """Test confidence clamped at 0.0 min (negative values use default)."""
        ensemble = DirectorEnsemble()
        # Negative values won't parse correctly, so they return default 0.5
        content_low = "### Confidence Assessment\n-0.2: Too low"
        
        # The regex won't match negative numbers, so default is returned
        assert ensemble._extract_confidence(content_low) == 0.5
    
    def test_extract_confidence_zero(self) -> None:
        """Test confidence of exactly 0.0."""
        ensemble = DirectorEnsemble()
        content = "### Confidence Assessment\n0.0: No confidence"
        
        assert ensemble._extract_confidence(content) == 0.0
    
    def test_extract_confidence_invalid_float(self) -> None:
        """Test confidence with invalid float value (multi-dot) returns default."""
        ensemble = DirectorEnsemble()
        # Content that matches the regex pattern [0-9.]+ but fails float() conversion
        content = "### Confidence Assessment\n1.2.3: Multiple dots - invalid float"
        
        # Should return default 0.5 since '1.2.3' can't be converted to float
        assert ensemble._extract_confidence(content) == 0.5
    
    def test_build_strategist_prompt_with_all_context(self) -> None:
        """Test building strategist prompt with full context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-test",
            phase="exploitation",
            prompt="What next?",
            constraints={"no_dos": True},
            previous_strategies=["Initial scan complete"],
        )
        
        swarm_state = SwarmState(
            active_agents=25,
            phase="exploitation",
            targets_scanned=10,
            findings_count=15,
        )
        
        findings_summary = FindingsSummary(
            critical_count=3,
            high_count=5,
            medium_count=7,
            top_findings=["SQLi on /admin", "Weak SSH"],
        )
        
        prompt = ensemble._build_strategist_prompt(
            context, swarm_state, findings_summary, "Gain admin access"
        )
        
        # Verify all components included
        assert "eng-test" in prompt
        assert "25" in prompt  # active_agents
        assert "10" in prompt  # targets_scanned
        assert "3" in prompt or "Critical" in prompt
        assert "SQLi" in prompt
        assert "admin access" in prompt.lower()
        assert "no_dos" in prompt.lower()
        assert "Initial scan" in prompt
    
    def test_build_strategist_prompt_minimal(self) -> None:
        """Test building strategist prompt with minimal context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-minimal",
            phase="recon",
            prompt="Start reconnaissance",
        )
        
        prompt = ensemble._build_strategist_prompt(context)
        
        assert "eng-minimal" in prompt
        assert "recon" in prompt
        assert "Start reconnaissance" in prompt


class TestATTCKExtractionEdgeCases:
    """Additional tests for ATT&CK extraction edge cases."""
    
    def test_extract_attck_with_newlines_in_rationale(self) -> None:
        """Test extraction handles rationale spanning multiple lines."""
        response_text = """
        T1190 - Exploit Public-Facing Application: This is applicable because
        the target has an exposed web server with known vulnerabilities
        """
        
        techniques = extract_attck_techniques(response_text)
        
        assert len(techniques) == 1
        assert "web server" in techniques[0].rationale.lower()
    
    def test_extract_attck_invalid_id_logged(self) -> None:
        """Test that invalid technique IDs are skipped gracefully and logged."""
        response_text = """
        T999 - Invalid Technique: This should be skipped because T999 is only 3 digits
        T1190 - Valid Technique: This should be extracted
        """
        
        techniques = extract_attck_techniques(response_text)
        
        # Only valid technique extracted (T999 is invalid - need 4 digits)
        assert len(techniques) == 1
        assert techniques[0].technique_id == "T1190"
    
    def test_extract_attck_three_digit_id_skipped(self) -> None:
        """Test that 3-digit technique IDs are skipped (invalid format)."""
        # T999 has only 3 digits - invalid ATT&CK format
        response_text = """
        T999 - Three Digit ID: Should be skipped
        """
        
        techniques = extract_attck_techniques(response_text)
        
        # T999 doesn't match T#### pattern, so it won't even be parsed
        assert len(techniques) == 0


class TestSwarmStateValidation:
    """Tests for SwarmState dataclass validation."""
    
    def test_swarm_state_valid(self) -> None:
        """Test creating SwarmState with valid data."""
        state = SwarmState(
            active_agents=10,
            phase="exploitation",
            targets_scanned=5,
            findings_count=15,
        )
        assert state.active_agents == 10
        assert state.phase == "exploitation"
    
    def test_swarm_state_negative_active_agents_raises(self) -> None:
        """Test that negative active_agents raises ValueError."""
        with pytest.raises(ValueError, match="active_agents cannot be negative"):
            SwarmState(
                active_agents=-1,
                phase="recon",
                targets_scanned=0,
                findings_count=0,
            )
    
    def test_swarm_state_negative_targets_raises(self) -> None:
        """Test that negative targets_scanned raises ValueError."""
        with pytest.raises(ValueError, match="targets_scanned cannot be negative"):
            SwarmState(
                active_agents=5,
                phase="recon",
                targets_scanned=-1,
                findings_count=0,
            )
    
    def test_swarm_state_negative_findings_raises(self) -> None:
        """Test that negative findings_count raises ValueError."""
        with pytest.raises(ValueError, match="findings_count cannot be negative"):
            SwarmState(
                active_agents=5,
                phase="recon",
                targets_scanned=0,
                findings_count=-1,
            )
    
    def test_swarm_state_empty_phase_raises(self) -> None:
        """Test that empty phase raises ValueError."""
        with pytest.raises(ValueError, match="phase cannot be empty"):
            SwarmState(
                active_agents=5,
                phase="",
                targets_scanned=0,
                findings_count=0,
            )


class TestFindingsSummaryValidation:
    """Tests for FindingsSummary dataclass validation."""
    
    def test_findings_summary_valid(self) -> None:
        """Test creating FindingsSummary with valid data."""
        summary = FindingsSummary(
            critical_count=2,
            high_count=5,
            medium_count=10,
            top_findings=["SQLi on /admin"],
        )
        assert summary.critical_count == 2
        assert len(summary.top_findings) == 1
    
    def test_findings_summary_negative_critical_raises(self) -> None:
        """Test that negative critical_count raises ValueError."""
        with pytest.raises(ValueError, match="critical_count cannot be negative"):
            FindingsSummary(
                critical_count=-1,
                high_count=0,
                medium_count=0,
                top_findings=[],
            )
    
    def test_findings_summary_negative_high_raises(self) -> None:
        """Test that negative high_count raises ValueError."""
        with pytest.raises(ValueError, match="high_count cannot be negative"):
            FindingsSummary(
                critical_count=0,
                high_count=-1,
                medium_count=0,
                top_findings=[],
            )
    
    def test_findings_summary_negative_medium_raises(self) -> None:
        """Test that negative medium_count raises ValueError."""
        with pytest.raises(ValueError, match="medium_count cannot be negative"):
            FindingsSummary(
                critical_count=0,
                high_count=0,
                medium_count=-1,
                top_findings=[],
            )
    
    def test_findings_summary_empty_top_findings_valid(self) -> None:
        """Test that empty top_findings is valid."""
        summary = FindingsSummary(
            critical_count=0,
            high_count=0,
            medium_count=0,
            top_findings=[],
        )
        assert len(summary.top_findings) == 0


class TestQueryStrategistErrorHandling:
    """Tests for query_strategist error handling paths."""
    
    @pytest.mark.asyncio
    async def test_query_strategist_provider_unavailable_error(self) -> None:
        """Test that non-timeout errors raise LLMProviderUnavailable."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test error handling",
        )
        
        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=LLMProviderUnavailable("Model not available")
        )
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            with pytest.raises(LLMProviderUnavailable, match="Strategist query failed"):
                await ensemble.query_strategist(context)
    
    @pytest.mark.asyncio
    async def test_query_strategist_generic_error_raises_provider_unavailable(self) -> None:
        """Test that generic errors in model response raise LLMProviderUnavailable."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test error handling",
        )
        
        # Simulate failed model response with non-timeout error
        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            with pytest.raises(LLMProviderUnavailable, match="Strategist query failed"):
                await ensemble.query_strategist(context)


class TestBuildStrategistPromptEdgeCases:
    """Tests for edge cases in _build_strategist_prompt."""
    
    def test_build_prompt_with_empty_top_findings(self) -> None:
        """Test building prompt with findings summary but empty top_findings."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-test",
            phase="exploitation",
            prompt="What next?",
        )
        
        findings_summary = FindingsSummary(
            critical_count=3,
            high_count=5,
            medium_count=7,
            top_findings=[],  # Empty list
        )
        
        prompt = ensemble._build_strategist_prompt(context, findings_summary=findings_summary)
        
        # Should include counts but not "Top Findings:" section
        assert "Critical: 3" in prompt
        assert "High: 5" in prompt
        # Should not have enumerated findings
        assert "1." not in prompt or "Top Findings" not in prompt


class TestExtractPrioritiesEdgeCases:
    """Tests for edge cases in _extract_priorities."""
    
    def test_extract_priorities_malformed_rows(self) -> None:
        """Test extracting priorities handles malformed table rows."""
        ensemble = DirectorEnsemble()
        content = """
        ### Target Priorities
        | Priority | Target | Rationale |
        |----------|--------|-----------|
        | not_a_number | 192.168.1.10 | Should be skipped |
        | 2 | 192.168.1.20 | Valid row |
        | | Empty priority | Should be skipped |
        """
        
        priorities = ensemble._extract_priorities(content)
        
        # Only valid row should be extracted
        assert len(priorities) == 1
        assert priorities[0] == ("192.168.1.20", 2)
    
    def test_extract_priorities_extra_columns(self) -> None:
        """Test extracting priorities with extra table columns."""
        ensemble = DirectorEnsemble()
        content = """
        ### Target Priorities
        | Priority | Target | Rationale | Extra |
        |----------|--------|-----------|-------|
        | 1 | 192.168.1.10 | Valid | Extra data |
        """
        
        priorities = ensemble._extract_priorities(content)
        
        # Should still extract first two columns correctly
        assert len(priorities) == 1
        assert priorities[0] == ("192.168.1.10", 1)


class TestExtractSectionListEdgeCases:
    """Tests for edge cases in _extract_section_list."""
    
    def test_extract_section_mixed_numbering_and_bullets(self) -> None:
        """Test extracting section with mixed numbered and bullet items."""
        ensemble = DirectorEnsemble()
        content = """
        ### Strategic Recommendations
        1. First numbered item
        2. Second numbered item
        - First bullet item
        - Second bullet item
        """
        
        items = ensemble._extract_section_list(content, "Strategic Recommendations")
        
        # Should extract both numbered and bulleted items
        assert len(items) >= 4


class TestATTCKRecommendationPhaseValidation:
    """Tests for ATTCKRecommendation phase validation (MEDIUM issue)."""
    
    def test_attck_recommendation_unknown_phase_valid(self) -> None:
        """Test that unknown phase is currently accepted (documenting behavior)."""
        # This test documents current behavior - phase accepts any string
        rec = ATTCKRecommendation(
            technique_id="T1190",
            technique_name="Test",
            rationale="Test",
            phase="unknown",  # Currently accepted
        )
        assert rec.phase == "unknown"
    
    def test_attck_recommendation_valid_phases(self) -> None:
        """Test ATTCKRecommendation with valid kill chain phases."""
        valid_phases = ["recon", "initial-access", "execution", "persistence", 
                        "privilege-escalation", "defense-evasion", "credential-access",
                        "discovery", "lateral-movement", "collection", "exfiltration",
                        "command-and-control", "impact"]
        
        for phase in valid_phases:
            rec = ATTCKRecommendation(
                technique_id="T1190",
                technique_name="Test",
                rationale="Test",
                phase=phase,
            )
            assert rec.phase == phase
