"""Integration tests for Strategy Synthesis Engine (Story 8.5).

Tests verify synthesis quality with realistic model response patterns.
NO MOCKS - tests use real synthesis logic with realistic inputs.
"""

from __future__ import annotations

import pytest

from cyberred.llm.ensemble import (
    DirectorRole,
    DirectorContext,
    ModelResponse,
    DirectorQueryResult,
    SynthesisInput,
    SynthesizedStrategy,
    DirectorEnsemble,
    StrategySynthesizer,
    ConflictResolution,
    CONFLICT_PRIORITY,
)


class TestSynthesisIntegrationWithRealisticResponses:
    """Integration tests with realistic model response patterns."""

    @pytest.fixture
    def realistic_strategist_content(self) -> str:
        """Realistic strategist response content."""
        return """
### Strategic Recommendations
1. Focus on web application testing - the exposed Apache server shows potential for SQL injection
2. Prioritize credential harvesting - weak authentication detected on multiple services
3. Establish persistence through SSH - discovered weak SSH configuration

### Next Phases
- Exploitation Phase: Target web application vulnerabilities first (timing: immediate)
- Lateral Movement: Use harvested credentials to move through network (timing: after initial access)
- Post-exploitation: Establish persistence mechanisms (timing: after lateral movement)

### Target Priorities
| Priority | Target | Rationale |
|----------|--------|-----------|
| 1 | web-server-01 | Exposed Apache with potential SQLi |
| 2 | db-server-01 | Database backend, high value target |
| 3 | jump-host | Pivot point for lateral movement |

### ATT&CK Techniques
- T1190 - Exploit Public-Facing Application: Web server has known vulnerabilities
- T1078 - Valid Accounts: Weak credentials detected
- T1021.004 - Remote Services: SSH: Weak SSH configuration

### Confidence Assessment
0.85: High confidence based on comprehensive reconnaissance findings
"""

    @pytest.fixture
    def realistic_analyst_content(self) -> str:
        """Realistic analyst response content."""
        return """
### Attack Surface Analysis
The target environment presents a significant attack surface with multiple entry points.
Key observations:
- Web server (Apache 2.4.29) with outdated modules
- SSH service with password authentication enabled
- Database port exposed to internal network
- No WAF detected on web applications

### Risk Assessment
**Overall Risk Level:** HIGH
**Risk Factors:**
- Outdated software versions
- Weak authentication mechanisms
- Missing security controls (WAF, IDS)
- Exposed administrative interfaces
**Mitigations Needed:**
- Implement WAF for web applications
- Disable password-based SSH authentication
- Restrict database access to application servers only
- Avoid direct attacks on monitored services
**Confidence:** 0.9

### Security Gaps
| Gap ID | Description | Severity | Affected Assets |
|--------|-------------|----------|-----------------|
| GAP-001 | Missing WAF protection | HIGH | web-server-01 |
| GAP-002 | Weak SSH configuration | CRITICAL | all-servers |
| GAP-003 | Exposed database ports | MEDIUM | db-server-01 |

### Overlooked Opportunities
| Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
|----------------|-------------|------------------|-------------------|------------|
| OPP-001 | API endpoints not enumerated | HIGH | Run API fuzzing | 0.85 |
| OPP-002 | DNS zone transfer possible | MEDIUM | Attempt zone transfer | 0.7 |
"""

    @pytest.fixture
    def realistic_creative_content(self) -> str:
        """Realistic creative response content."""
        return """
<think>
The standard SQL injection approach may trigger WAF rules. Let me consider alternative 
encoding methods and timing-based attacks that are less likely to be detected.

Additionally, the SSH weak configuration suggests a brute-force approach might work,
but this would be noisy. Instead, we could leverage credential stuffing with known
password patterns.
</think>

### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | Use time-based blind SQLi instead of error-based | Avoids triggering IDS signatures | 0.75 |
| ALT-002 | Leverage DNS exfiltration for data extraction | Bypasses firewall restrictions | 0.85 |
| ALT-003 | Use living-off-the-land binaries for persistence | Evades AV detection | 0.9 |

<think>
The network segmentation appears weak. We could potentially use ICMP tunneling
to bypass firewall rules that only inspect TCP/UDP traffic.
</think>

### Evasion Techniques
| Technique ID | Description | Target Defense | Success Likelihood |
|--------------|-------------|----------------|-------------------|
| EVA-001 | Time-delay between requests | Rate limiting | 0.8 |
| EVA-002 | User-Agent rotation | WAF fingerprinting | 0.7 |
| EVA-003 | ICMP tunneling | Firewall bypass | 0.65 |

### Novel Approaches
| Approach ID | Description | Innovation Type | Risk Level | Potential Impact |
|-------------|-------------|-----------------|------------|------------------|
| NOV-001 | Polyglot payload injection | technique | MEDIUM | HIGH |
| NOV-002 | Protocol smuggling via HTTP/2 | vector | LOW | MEDIUM |
"""

    def test_synthesis_with_all_realistic_responses(
        self,
        realistic_strategist_content: str,
        realistic_analyst_content: str,
        realistic_creative_content: str,
    ) -> None:
        """Test synthesis with all three realistic model responses."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-integration-001",
            phase="exploitation",
            prompt="Provide strategic guidance for penetration test",
        )
        
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="deepseek-ai/deepseek-v3.2",
                content=realistic_strategist_content,
                latency_ms=1500,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="moonshotai/kimi-k2-instruct",
                content=realistic_analyst_content,
                latency_ms=2000,
                success=True,
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="minimaxai/minimax-m2",
                content=realistic_creative_content,
                latency_ms=1800,
                success=True,
            ),
        }
        
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=2000,
            successful_count=3,
            failed_count=0,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        # Perform synthesis
        strategy = ensemble.synthesize(synthesis_input)
        
        # Verify synthesis quality metrics
        assert strategy.confidence > 0.5, "Confidence should be good with all models"
        assert len(strategy.contributing_roles) == 3, "All roles should contribute"
        assert len(strategy.objectives) > 0, "Should extract objectives"
        assert len(strategy.actions) > 0, "Should extract actions"
        assert len(strategy.attck_techniques) > 0, "Should preserve ATT&CK techniques"
        assert len(strategy.risk_warnings) > 0, "Should extract risk warnings"
        assert strategy.rationale, "Should have rationale"
        
        # Verify structured output
        json_data = strategy.to_json()
        assert "objectives" in json_data
        assert "actions" in json_data
        assert "attck_techniques" in json_data
        assert json_data["confidence"] > 0

    def test_synthesis_graceful_degradation_one_model(
        self,
        realistic_strategist_content: str,
    ) -> None:
        """Test synthesis degrades gracefully with only one model."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-degradation-001",
            phase="recon",
            prompt="Test degradation",
        )
        
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="deepseek-ai/deepseek-v3.2",
                content=realistic_strategist_content,
                latency_ms=1500,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="moonshotai/kimi-k2-instruct",
                content="",
                latency_ms=100000,
                success=False,
                error="Timeout after 100s",
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="minimaxai/minimax-m2",
                content="",
                latency_ms=100000,
                success=False,
                error="Provider unavailable",
            ),
        }
        
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=100000,
            successful_count=1,
            failed_count=2,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # Should still produce valid strategy with lower confidence
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 1
        assert DirectorRole.STRATEGIST in strategy.contributing_roles
        assert strategy.confidence < 0.5, "Single model should have lower confidence"
        # Should still extract what's available from strategist
        assert len(strategy.objectives) > 0 or len(strategy.actions) > 0

    def test_synthesis_all_models_failed(self) -> None:
        """Test synthesis handles all models failing."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-all-failed-001",
            phase="recon",
            prompt="Test all failed",
        )
        
        responses = {
            role: ModelResponse(
                role=role,
                model_id=f"model-{role.value}",
                content="",
                latency_ms=100000,
                success=False,
                error="Model unavailable",
            )
            for role in DirectorRole
        }
        
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=100000,
            successful_count=0,
            failed_count=3,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # Should return error strategy
        assert isinstance(strategy, SynthesizedStrategy)
        assert len(strategy.contributing_roles) == 0
        assert strategy.confidence == 0.0
        assert "No model responses" in strategy.rationale or len(strategy.objectives) == 0


class TestSynthesizerStandalone:
    """Direct tests for StrategySynthesizer without DirectorEnsemble."""

    def test_synthesizer_directly_with_parsed_responses(self) -> None:
        """Test StrategySynthesizer with pre-parsed response objects."""
        from cyberred.llm.ensemble import (
            StrategistResponse,
            AnalystResponse,
            CreativeResponse,
            ATTCKRecommendation,
            SecurityGap,
            OverlookedOpportunity,
            RiskAssessment,
            CreativeAlternative,
            ThinkingContent,
        )
        
        synthesizer = StrategySynthesizer()
        
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Test web app", "Test API endpoints"],
            next_phases=["Move to exploitation"],
            priorities=[("target-1", 1), ("target-2", 2)],
            attck_techniques=[
                ATTCKRecommendation(
                    technique_id="T1190",
                    technique_name="Exploit Public-Facing Application",
                    rationale="Web app is vulnerable",
                    phase="exploit",
                )
            ],
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
            attack_surface_analysis="Large attack surface",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=["IDS detected aggressive scans"],
                mitigations_needed=["Use stealth approach", "Avoid noisy tools"],
                confidence=0.85,
            ),
            gaps=[
                SecurityGap(
                    gap_id="GAP-001",
                    description="Missing input validation",
                    severity="CRITICAL",
                    affected_assets=["web-app"],
                )
            ],
            overlooked_opportunities=[
                OverlookedOpportunity(
                    opportunity_id="OPP-001",
                    description="Admin panel exposed",
                    potential_impact="HIGH",
                    recommended_action="Test admin panel",
                    confidence=0.9,
                )
            ],
            model_response=ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        creative = CreativeResponse(
            raw_content="<think>test thinking</think>",
            clean_content="test thinking",
            thinking_content=[ThinkingContent(content="test thinking", position=0)],
            creative_alternatives=[
                CreativeAlternative(
                    alternative_id="ALT-001",
                    description="Try DNS tunneling",
                    rationale="Bypass firewall",
                    novelty_score=0.8,
                )
            ],
            evasion_techniques=[],
            novel_approaches=[],
            model_response=ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        strategy = synthesizer.synthesize(
            strategist=strategist,
            analyst=analyst,
            creative=creative,
        )
        
        # Comprehensive checks
        assert len(strategy.contributing_roles) == 3
        assert len(strategy.objectives) > 0
        assert len(strategy.attck_techniques) == 1
        assert strategy.attck_techniques[0].technique_id == "T1190"
        assert len(strategy.risk_warnings) > 0
        assert len(strategy.creative_alternatives) == 1


class TestConflictResolutionIntegration:
    """Integration tests for conflict detection and resolution."""

    def test_conflict_detection_with_opposing_recommendations(self) -> None:
        """Test that conflicts are detected when models disagree."""
        from cyberred.llm.ensemble import (
            StrategistResponse,
            AnalystResponse,
            RiskAssessment,
        )
        
        synthesizer = StrategySynthesizer()
        
        # Strategist recommends aggressive approach
        strategist = StrategistResponse(
            raw_content="test",
            recommendations=["Use aggressive scanning", "Rapid exploitation"],
            next_phases=[],
            priorities=[],
            attck_techniques=[],
            confidence=0.7,
            model_response=ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="test",
                content="test",
                latency_ms=100,
                success=True,
            ),
        )
        
        # Analyst warns about detection
        analyst = AnalystResponse(
            raw_content="test",
            attack_surface_analysis="",
            risk_assessment=RiskAssessment(
                overall_risk_level="HIGH",
                risk_factors=["IDS will detect aggressive scans", "Monitoring active"],
                mitigations_needed=["Use stealth"],
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
            strategist=strategist,
            analyst=analyst,
            creative=None,
        )
        
        # Should have resolved conflicts
        # The analyst's security concerns should win per priority rules
        assert len(strategy.conflicts_resolved) > 0 or len(strategy.risk_warnings) > 0
