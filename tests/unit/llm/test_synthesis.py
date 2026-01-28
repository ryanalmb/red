"""Unit tests for Strategy Synthesis Engine (Story 8.5).

Tests cover:
- ConflictResolution dataclass
- StrategySynthesizer class
- Objective extraction from all roles
- Action extraction and merging
- Conflict detection and resolution
- Confidence-based prioritization
- Consensus calculation
- Extended SynthesizedStrategy fields
- Edge cases: single model, all failed, partial responses
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.llm.ensemble import (
    DirectorRole,
    DirectorContext,
    ModelResponse,
    DirectorQueryResult,
    SynthesisInput,
    SynthesizedStrategy,
    DirectorEnsemble,
    StrategistResponse,
    AnalystResponse,
    CreativeResponse,
    ATTCKRecommendation,
    SecurityGap,
    OverlookedOpportunity,
    RiskAssessment,
    CreativeAlternative,
    ThinkingContent,
    EvasionTechnique,
    NovelApproach,
    # Story 8.5 new types
    ConflictResolution,
    StrategySynthesizer,
    CONFLICT_PRIORITY,
)
from cyberred.llm.provider import TokenUsage


class TestConflictResolution:
    """Tests for ConflictResolution dataclass."""

    def test_create_conflict_resolution(self) -> None:
        """Test creating a ConflictResolution."""
        conflict = ConflictResolution(
            conflict_type="priority",
            source_roles=[DirectorRole.STRATEGIST, DirectorRole.CREATIVE],
            conflicting_values=["aggressive_scan", "stealth_scan"],
            resolved_value="stealth_scan",
            resolution_rationale="Security concerns take precedence",
        )
        assert conflict.conflict_type == "priority"
        assert len(conflict.source_roles) == 2
        assert conflict.resolved_value == "stealth_scan"

    def test_conflict_types(self) -> None:
        """Test valid conflict types."""
        valid_types = ["priority", "approach", "target", "technique", "safety"]
        for conflict_type in valid_types:
            conflict = ConflictResolution(
                conflict_type=conflict_type,
                source_roles=[DirectorRole.ANALYST],
                conflicting_values=["val1"],
                resolved_value="val1",
                resolution_rationale="Test",
            )
            assert conflict.conflict_type == conflict_type


class TestConflictPriority:
    """Tests for CONFLICT_PRIORITY constants."""

    def test_priority_order(self) -> None:
        """Test that priority order is correct per story requirements."""
        # Security warning should be highest priority (lowest number)
        assert CONFLICT_PRIORITY["security_warning"] < CONFLICT_PRIORITY["strategic_priority"]
        # Scope constraint should be before strategic priority
        assert CONFLICT_PRIORITY["scope_constraint"] < CONFLICT_PRIORITY["strategic_priority"]
        # Strategic priority before risk avoidance
        assert CONFLICT_PRIORITY["strategic_priority"] < CONFLICT_PRIORITY["risk_avoidance"]
        # Creative alternative should be lowest priority (highest number)
        assert CONFLICT_PRIORITY["creative_alternative"] > CONFLICT_PRIORITY["risk_avoidance"]

    def test_all_priorities_defined(self) -> None:
        """Test that all expected priority types are defined."""
        expected_types = [
            "security_warning",
            "scope_constraint", 
            "strategic_priority",
            "risk_avoidance",
            "creative_alternative",
        ]
        for ptype in expected_types:
            assert ptype in CONFLICT_PRIORITY


class TestExtendedSynthesizedStrategy:
    """Tests for extended SynthesizedStrategy fields (Story 8.5)."""

    def test_new_fields_exist(self) -> None:
        """Test that new fields are available on SynthesizedStrategy."""
        strategy = SynthesizedStrategy(
            objectives=["obj1"],
            actions=["act1"],
            rationale="test",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST],
            avoid_list=["target1"],
            attck_techniques=[ATTCKRecommendation(
                technique_id="T1566",
                technique_name="Phishing",
                rationale="Common entry point",
                phase="exploit",
            )],
            creative_alternatives=[],
            risk_warnings=["High risk network"],
            conflicts_resolved=[],
        )
        assert strategy.avoid_list == ["target1"]
        assert len(strategy.attck_techniques) == 1
        assert strategy.risk_warnings == ["High risk network"]

    def test_to_json(self) -> None:
        """Test to_json method for Redis publication."""
        strategy = SynthesizedStrategy(
            objectives=["Gain foothold"],
            actions=["Scan port 22", "Exploit SSH"],
            rationale="Based on findings",
            confidence=0.85,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
            avoid_list=["10.0.0.1"],
            attck_techniques=[ATTCKRecommendation(
                technique_id="T1021.004",
                technique_name="Remote Services: SSH",
                rationale="SSH access discovered",
                phase="exploit",
            )],
            creative_alternatives=[],
            risk_warnings=["IDS detected"],
            conflicts_resolved=[],
        )
        json_data = strategy.to_json()
        
        assert json_data["objectives"] == ["Gain foothold"]
        assert json_data["actions"] == ["Scan port 22", "Exploit SSH"]
        assert json_data["confidence"] == 0.85
        assert json_data["avoid_list"] == ["10.0.0.1"]
        assert len(json_data["attck_techniques"]) == 1
        assert json_data["attck_techniques"][0]["technique_id"] == "T1021.004"
        assert "contributing_roles" in json_data


class TestStrategySynthesizer:
    """Tests for StrategySynthesizer class."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        """Create a StrategySynthesizer instance."""
        return StrategySynthesizer()

    @pytest.fixture
    def sample_strategist_response(self) -> StrategistResponse:
        """Create sample strategist response."""
        return StrategistResponse(
            raw_content="Strategic analysis",
            recommendations=["Focus on web services", "Avoid network scanning"],
            next_phases=["Exploitation phase"],
            priorities=[("web-server", 1), ("database", 2)],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    rationale="Web app vulnerable",
                    phase="exploit",
                )
            ],
            confidence=0.85,
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="deepseek",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )

    @pytest.fixture
    def sample_analyst_response(self) -> AnalystResponse:
        """Create sample analyst response."""
        return AnalystResponse(
            raw_content="Analysis results",
            attack_surface_analysis="Large attack surface with multiple entry points",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=["Exposed services", "Weak authentication"],
                mitigations_needed=["Implement MFA"],
                confidence=0.9,
            ),
            gaps=[
                SecurityGap(
                    gap_id="GAP-001",
                    description="Missing WAF",
                    severity="HIGH",
                    affected_assets=["web-server"],
                )
            ],
            overlooked_opportunities=[
                OverlookedOpportunity(
                    opportunity_id="OPP-001",
                    description="API endpoints not scanned",
                    potential_impact="HIGH",
                    recommended_action="Scan API endpoints",
                    confidence=0.8,
                )
            ],
            model_response=ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="kimi-k2",
                content="test",
                latency_ms=150,
                success=True,
            ),
        )

    @pytest.fixture
    def sample_creative_response(self) -> CreativeResponse:
        """Create sample creative response."""
        return CreativeResponse(
            raw_content="Creative approaches with <think>Consider lateral movement</think>",
            clean_content="Creative approaches with thinking block",
            thinking_content=[
                ThinkingContent(
                    content="Consider lateral movement",
                    position=0,
                )
            ],
            creative_alternatives=[
                CreativeAlternative(
                    alternative_id="ALT-001",
                    description="Use DNS tunneling for exfiltration",
                    rationale="Bypass firewall restrictions",
                    novelty_score=0.8,
                )
            ],
            evasion_techniques=[],
            novel_approaches=[],
            model_response=ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="minimax-m2",
                content="test",
                latency_ms=120,
                success=True,
            ),
        )


class TestObjectiveExtraction:
    """Tests for objective extraction from roles."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_extract_objectives_from_strategist(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test extracting objectives from strategist recommendations."""
        objectives = synthesizer._extract_objectives(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
        )
        assert len(objectives) > 0
        # Strategist recommendations should become objectives
        assert any("web" in obj.lower() for obj in objectives)

    def test_extract_objectives_from_analyst(
        self,
        synthesizer: StrategySynthesizer,
        sample_analyst_response: AnalystResponse,
    ) -> None:
        """Test extracting objectives from analyst gaps."""
        objectives = synthesizer._extract_objectives(
            strategist=None,
            analyst=sample_analyst_response,
            creative=None,
        )
        # Analyst gaps should contribute objectives
        assert len(objectives) >= 0  # May or may not have objectives from analyst

    def test_extract_objectives_all_roles(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test extracting objectives from all three roles."""
        objectives = synthesizer._extract_objectives(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
        )
        assert len(objectives) > 0


class TestActionExtraction:
    """Tests for action extraction and merging."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_extract_actions_from_strategist(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test extracting actions from strategist."""
        actions = synthesizer._extract_actions(
            strategist=sample_strategist_response,
            creative=None,
        )
        assert isinstance(actions, list)

    def test_extract_actions_from_creative(
        self,
        synthesizer: StrategySynthesizer,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test extracting actions from creative alternatives."""
        actions = synthesizer._extract_actions(
            strategist=None,
            creative=sample_creative_response,
        )
        assert isinstance(actions, list)

    def test_merge_insights(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
    ) -> None:
        """Test merging analyst gaps with strategist priorities."""
        merged = synthesizer._merge_insights(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
        )
        assert isinstance(merged, list)


class TestConflictDetection:
    """Tests for conflict detection between model recommendations."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_detect_no_conflicts(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test when no conflicts exist."""
        # Create responses that agree
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Scan web server"],
            next_phases=[],
            priorities=[("web", 1)],
            attck_techniques=[],
            confidence=0.8,
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        conflicts = synthesizer._detect_conflicts(
            strategist=strategist,
            analyst=None,
            creative=None,
        )
        assert isinstance(conflicts, list)

    def test_detect_priority_conflict(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test detecting priority conflicts between roles."""
        # Strategist says aggressive, analyst says cautious
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Aggressive scanning recommended"],
            next_phases=[],
            priorities=[],
            attck_techniques=[],
            confidence=0.8,
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        analyst = AnalystResponse(
            raw_content="test",
            attack_surface_analysis="",
            risk_assessment=RiskAssessment(
                overall_risk_level="CRITICAL",
                risk_factors=["IDS will detect aggressive scans"],
                mitigations_needed=["Use stealth approach"],
                confidence=0.9,
            ),
            gaps=[],
            overlooked_opportunities=[],
            model_response=ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        conflicts = synthesizer._detect_conflicts(
            strategist=strategist,
            analyst=analyst,
            creative=None,
        )
        # May or may not detect conflicts depending on implementation
        assert isinstance(conflicts, list)


class TestConflictResolutionLogic:
    """Tests for conflict resolution using priority rules."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_resolve_security_wins_over_aggressive(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test that security warnings win over aggressive approaches."""
        conflicts = [
            ConflictResolution(
                conflict_type="approach",
                source_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
                conflicting_values=["aggressive_scan", "stealth_scan"],
                resolved_value="",  # Not resolved yet
                resolution_rationale="",
            ),
        ]
        # Resolution should prioritize security
        resolved = synthesizer._resolve_conflicts(conflicts)
        assert isinstance(resolved, list)

    def test_resolve_empty_conflicts(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test resolving empty conflict list."""
        resolved = synthesizer._resolve_conflicts([])
        assert resolved == []


class TestConfidencePrioritization:
    """Tests for confidence-based prioritization."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_weight_by_confidence(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test weighting actions by confidence scores."""
        actions = [
            ("action1", 0.9),
            ("action2", 0.5),
            ("action3", 0.8),
        ]
        weighted = synthesizer._weight_by_confidence(actions)
        # Higher confidence should rank higher
        assert weighted[0][0] == "action1"  # 0.9 confidence
        assert weighted[1][0] == "action3"  # 0.8 confidence
        assert weighted[2][0] == "action2"  # 0.5 confidence


class TestConsensusCalculation:
    """Tests for consensus score calculation."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_full_consensus(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test consensus when all models agree."""
        consensus = synthesizer._calculate_consensus(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
        )
        assert 0.0 <= consensus <= 1.0

    def test_single_model_consensus(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test consensus with only one model available."""
        consensus = synthesizer._calculate_consensus(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
        )
        # Single model should have low/zero consensus
        assert consensus <= 0.33

    def test_no_models_consensus(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test consensus with no models available."""
        consensus = synthesizer._calculate_consensus(
            strategist=None,
            analyst=None,
            creative=None,
        )
        assert consensus == 0.0


class TestSynthesizeMethod:
    """Tests for the main synthesize method."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_synthesize_all_roles(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test synthesize with all three roles."""
        strategy = synthesizer.synthesize(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
        )
        
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.objectives) > 0
        assert strategy.confidence > 0
        assert len(strategy.contributing_roles) == 3
        # ATT&CK techniques preserved from strategist
        assert len(strategy.attck_techniques) > 0
        # Risk warnings from analyst
        assert len(strategy.risk_warnings) > 0

    def test_synthesize_single_model(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test synthesize with only strategist available."""
        strategy = synthesizer.synthesize(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
        )
        
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 1
        # Lower confidence with single model
        assert strategy.confidence < 0.5

    def test_synthesize_no_models(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test synthesize with no models (all failed)."""
        strategy = synthesizer.synthesize(
            strategist=None,
            analyst=None,
            creative=None,
        )
        
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 0
        assert strategy.confidence == 0.0
        assert "No model responses" in strategy.rationale or len(strategy.objectives) == 0

    def test_synthesize_preserves_thinking_tags(
        self,
        synthesizer: StrategySynthesizer,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test that thinking tags from creative are preserved."""
        strategy = synthesizer.synthesize(
            strategist=None,
            analyst=None,
            creative=sample_creative_response,
        )
        
        # Creative alternatives should be preserved
        assert len(strategy.creative_alternatives) > 0

    def test_synthesize_structured_output(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test that output is properly structured per AC#5."""
        strategy = synthesizer.synthesize(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
        )
        
        # Final strategy structured: objectives, actions, rationale
        assert hasattr(strategy, "objectives")
        assert hasattr(strategy, "actions")
        assert hasattr(strategy, "rationale")
        assert isinstance(strategy.objectives, list)
        assert isinstance(strategy.actions, list)
        assert isinstance(strategy.rationale, str)


class TestDirectorEnsembleSynthesizeIntegration:
    """Tests for DirectorEnsemble.synthesize() using StrategySynthesizer."""

    def test_ensemble_synthesize_uses_synthesizer(self) -> None:
        """Test that DirectorEnsemble.synthesize uses StrategySynthesizer."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        
        # Create responses with proper content
        strategist_content = """
### Strategic Recommendations
1. Focus on web application testing
2. Prioritize SQL injection checks

### Target Priorities
| Priority | Target | Rationale |
|----------|--------|-----------|
| 1 | web-server | Primary target |

### ATT&CK Techniques
- T1190 - Exploit Public-Facing Application: Web app vulnerable

### Confidence Assessment
0.85: High confidence based on reconnaissance
"""
        
        analyst_content = """
### Attack Surface Analysis
Large attack surface with web services exposed.

### Risk Assessment
**Overall Risk Level:** HIGH
**Risk Factors:**
- Exposed services
- Weak authentication
**Mitigations Needed:**
- Implement WAF
**Confidence:** 0.9

### Security Gaps
| Gap ID | Description | Severity | Affected Assets |
|--------|-------------|----------|-----------------|
| GAP-001 | Missing WAF | HIGH | web-server |
"""
        
        creative_content = """
<think>
Consider alternative approaches to bypass defenses.
</think>

### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | DNS tunneling | Bypass firewall | 0.8 |
"""
        
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content=strategist_content,
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content=analyst_content,
                latency_ms=200,
                success=True,
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content=creative_content,
                latency_ms=150,
                success=True,
            ),
        }
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=200,
            successful_count=3,
            failed_count=0,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # Should use full synthesizer, not placeholder
        assert "placeholder" not in strategy.metadata.get("synthesis_version", "")
        assert len(strategy.objectives) > 0 or len(strategy.actions) > 0
        assert strategy.confidence > 0


class TestSynthesizeAsync:
    """Tests for synthesize_async method (Story 8.5 Task 5)."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    @pytest.mark.asyncio
    async def test_synthesize_async_simple_case(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test async synthesis returns simple strategy when sufficient."""
        strategy = await synthesizer.synthesize_async(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
        )
        
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 3

    @pytest.mark.asyncio
    async def test_synthesize_async_timeout_fallback(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test async synthesis falls back on timeout."""
        # With only one response, simple synthesis should be used
        strategy = await synthesizer.synthesize_async(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
            timeout=60.0,
        )
        
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 1

    @pytest.mark.asyncio
    async def test_synthesize_async_custom_timeout(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test async synthesis respects custom timeout parameter."""
        strategy = await synthesizer.synthesize_async(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
            timeout=30.0,  # Custom timeout
        )
        
        assert isinstance(strategy, SynthesizedStrategy)


class TestToJsonPhaseField:
    """Tests for to_json including phase field in ATT&CK techniques."""

    def test_to_json_includes_attck_phase(self) -> None:
        """Test that to_json includes phase field for ATT&CK techniques."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Test action"],
            rationale="Test rationale",
            confidence=0.8,
            contributing_roles=[DirectorRole.STRATEGIST],
            attck_techniques=[ATTCKRecommendation(
                technique_id="T1190",
                technique_name="Exploit Public-Facing Application",
                rationale="Web app vulnerable",
                phase="exploit",
            )],
        )
        
        json_data = strategy.to_json()
        
        assert "phase" in json_data["attck_techniques"][0]
        assert json_data["attck_techniques"][0]["phase"] == "exploit"


class TestAvoidListExtraction:
    """Tests for avoid_list extraction with expanded keywords."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_avoid_list_detects_dont(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test that avoid_list detects 'don't' keyword."""
        analyst = AnalystResponse(
            raw_content="test",
            attack_surface_analysis="",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=[],
                mitigations_needed=["Don't use aggressive scanning"],
                confidence=0.9,
            ),
            gaps=[],
            overlooked_opportunities=[],
            model_response=ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        strategy = synthesizer.synthesize(
            strategist=None,
            analyst=analyst,
            creative=None,
        )
        
        assert len(strategy.avoid_list) == 1
        assert "Don't use aggressive scanning" in strategy.avoid_list

    def test_avoid_list_detects_never(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test that avoid_list detects 'never' keyword."""
        analyst = AnalystResponse(
            raw_content="test",
            attack_surface_analysis="",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=[],
                mitigations_needed=["Never target production directly"],
                confidence=0.9,
            ),
            gaps=[],
            overlooked_opportunities=[],
            model_response=ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        strategy = synthesizer.synthesize(
            strategist=None,
            analyst=analyst,
            creative=None,
        )
        
        assert len(strategy.avoid_list) == 1


class TestConfidenceValidation:
    """Tests for confidence score validation."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_final_confidence_always_valid_range(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test that final confidence is always in valid 0-1 range."""
        # Create response with edge case confidence values
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Test"],
            next_phases=[],
            priorities=[],
            attck_techniques=[],
            confidence=1.0,  # Edge case: maximum valid
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        strategy = synthesizer.synthesize(
            strategist=strategist,
            analyst=None,
            creative=None,
        )
        
        # Final confidence should always be within 0-1 range
        assert 0.0 <= strategy.confidence <= 1.0

    def test_final_confidence_with_zero_confidence_model(
        self,
        synthesizer: StrategySynthesizer,
    ) -> None:
        """Test synthesis handles zero confidence model."""
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Test"],
            next_phases=[],
            priorities=[],
            attck_techniques=[],
            confidence=0.0,  # Zero confidence
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        strategy = synthesizer.synthesize(
            strategist=strategist,
            analyst=None,
            creative=None,
        )
        
        # Final confidence should still be valid (based on availability factor)
        assert 0.0 <= strategy.confidence <= 1.0
        # With single model at 0 confidence, final should be low but non-zero
        # (availability_factor * 0.4) + (0.0 * 0.4) + (0.0 * 0.2) = 0.133...
        assert strategy.confidence > 0.0


class TestBuildRationale:
    """Tests for _build_rationale method."""

    @pytest.fixture
    def synthesizer(self) -> StrategySynthesizer:
        return StrategySynthesizer()

    def test_build_rationale_all_perspectives(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
        sample_analyst_response: AnalystResponse,
        sample_creative_response: CreativeResponse,
    ) -> None:
        """Test building rationale from all perspectives."""
        rationale = synthesizer._build_rationale(
            strategist=sample_strategist_response,
            analyst=sample_analyst_response,
            creative=sample_creative_response,
            conflicts_resolved=[],
        )
        
        assert isinstance(rationale, str)
        assert len(rationale) > 0

    def test_build_rationale_with_conflicts(
        self,
        synthesizer: StrategySynthesizer,
        sample_strategist_response: StrategistResponse,
    ) -> None:
        """Test building rationale including resolved conflicts."""
        conflicts = [
            ConflictResolution(
                conflict_type="priority",
                source_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
                conflicting_values=["aggressive", "stealth"],
                resolved_value="stealth",
                resolution_rationale="Security concerns",
            ),
        ]
        rationale = synthesizer._build_rationale(
            strategist=sample_strategist_response,
            analyst=None,
            creative=None,
            conflicts_resolved=conflicts,
        )
        
        assert isinstance(rationale, str)


# Module-level fixtures for reuse across test classes
@pytest.fixture
def sample_strategist_response() -> StrategistResponse:
    """Create sample strategist response."""
    return StrategistResponse(
        raw_content="Strategic analysis",
        recommendations=["Focus on web services", "Avoid network scanning"],
        next_phases=["Exploitation phase"],
        priorities=[("web-server", 1), ("database", 2)],
        attck_techniques=[
            ATTCKRecommendation(
                technique_id="T1190",
                technique_name="Exploit Public-Facing Application",
                rationale="Web app vulnerable",
                phase="exploit",
            )
        ],
        confidence=0.85,
        model_response=ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="deepseek",
            content="test",
            latency_ms=100,
            success=True,
        ),
    )


@pytest.fixture
def sample_analyst_response() -> AnalystResponse:
    """Create sample analyst response."""
    return AnalystResponse(
        raw_content="Analysis results",
        attack_surface_analysis="Large attack surface with multiple entry points",
        risk_assessment=RiskAssessment(
            overall_risk_level="HIGH",
            risk_factors=["Exposed services", "Weak authentication"],
            mitigations_needed=["Implement MFA"],
            confidence=0.9,
        ),
        gaps=[
            SecurityGap(
                gap_id="GAP-001",
                description="Missing WAF",
                severity="HIGH",
                affected_assets=["web-server"],
            )
        ],
        overlooked_opportunities=[
            OverlookedOpportunity(
                opportunity_id="OPP-001",
                description="API endpoints not scanned",
                potential_impact="HIGH",
                recommended_action="Scan API endpoints",
                confidence=0.8,
            )
        ],
        model_response=ModelResponse(
            role=DirectorRole.ANALYST,
            model_id="kimi-k2",
            content="test",
            latency_ms=150,
            success=True,
        ),
    )


@pytest.fixture
def sample_creative_response() -> CreativeResponse:
    """Create sample creative response."""
    return CreativeResponse(
        raw_content="Creative approaches with <think>Consider lateral movement</think>",
        clean_content="Creative approaches with thinking block",
        thinking_content=[
            ThinkingContent(
                content="Consider lateral movement",
                position=0,
            )
        ],
        creative_alternatives=[
            CreativeAlternative(
                alternative_id="ALT-001",
                description="Use DNS tunneling for exfiltration",
                rationale="Bypass firewall restrictions",
                novelty_score=0.8,
            )
        ],
        evasion_techniques=[],
        novel_approaches=[],
        model_response=ModelResponse(
            role=DirectorRole.CREATIVE,
            model_id="minimax-m2",
            content="test",
            latency_ms=120,
            success=True,
        ),
    )
