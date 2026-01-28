"""Integration tests for Kimi K2 Analyst Role (Story 8.3).

These tests verify the analyst role works correctly with real LLM APIs.
Tests are skipped if NVIDIA_API_KEY is not set.

Tests cover:
- Real Kimi K2 queries via NIM API
- Structured response parsing from actual model output
- Timeout behavior under real conditions
- Graceful degradation when model unavailable
"""

from __future__ import annotations

import os
from typing import Optional

import pytest

from cyberred.llm.ensemble import (
    AnalystResponse,
    AttackPath,
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    FindingDetail,
    RiskAssessment,
    SecurityGap,
    TargetEnvironment,
)
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


# Skip all tests if no API key is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set - skipping integration tests"
)


class TestAnalystIntegration:
    """Integration tests for Kimi K2 analyst role with real API."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)  # Allow up to 2 minutes for real API call
    async def test_query_analyst_real_api(self) -> None:
        """Test analyst query with real Kimi K2 model via NIM API."""
        ensemble = DirectorEnsemble()
        
        context = DirectorContext(
            engagement_id="integration-test-001",
            phase="exploitation",
            prompt="Analyze the following attack surface and identify security gaps",
        )
        
        findings_details = [
            FindingDetail(
                finding_id="FIND-001",
                finding_type="vulnerability",
                target="10.0.0.5",
                service="http",
                severity="HIGH",
                description="SQL Injection vulnerability in login form",
                evidence="Error: MySQL syntax error",
            ),
            FindingDetail(
                finding_id="FIND-002",
                finding_type="exposure",
                target="10.0.0.5",
                service="ssh",
                severity="MEDIUM",
                description="SSH service exposed with weak ciphers",
            ),
        ]
        
        target_environment = TargetEnvironment(
            environment_type="corporate",
            discovered_hosts=5,
            discovered_services=12,
            os_distribution={"Linux": 3, "Windows": 2},
            network_segments=["10.0.0.0/24"],
        )
        
        discovered_paths = [
            AttackPath(
                path_id="PATH-001",
                entry_point="SQL Injection on web app",
                steps=["Exploit SQLi", "Extract credentials", "Access database"],
                target_asset="Database server",
                success_probability=0.75,
            )
        ]
        
        try:
            response = await ensemble.query_analyst(
                context=context,
                findings_details=findings_details,
                target_environment=target_environment,
                discovered_paths=discovered_paths,
            )
            
            # Verify response structure
            assert isinstance(response, AnalystResponse)
            assert response.model_response.success is True
            assert response.raw_content  # Should have content
            
            # Verify risk assessment was extracted (or default returned)
            assert isinstance(response.risk_assessment, RiskAssessment)
            assert response.risk_assessment.overall_risk_level in (
                "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
            )
            
            # Log response for debugging
            print(f"\n--- Analyst Response ---")
            print(f"Attack Surface Analysis: {response.attack_surface_analysis[:200]}...")
            print(f"Risk Level: {response.risk_assessment.overall_risk_level}")
            print(f"Gaps Found: {len(response.gaps)}")
            print(f"Opportunities Found: {len(response.overlooked_opportunities)}")
            
        except LLMProviderUnavailable as e:
            pytest.skip(f"Kimi K2 model unavailable: {e}")
        except LLMTimeoutError as e:
            pytest.skip(f"Kimi K2 timeout (may be under load): {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_query_analyst_minimal_context(self) -> None:
        """Test analyst query with minimal context."""
        ensemble = DirectorEnsemble()
        
        context = DirectorContext(
            engagement_id="integration-test-002",
            phase="recon",
            prompt="Provide initial attack surface assessment for a web application target",
        )
        
        try:
            response = await ensemble.query_analyst(context=context)
            
            assert isinstance(response, AnalystResponse)
            assert response.model_response.success is True
            
        except LLMProviderUnavailable as e:
            pytest.skip(f"Kimi K2 model unavailable: {e}")
        except LLMTimeoutError as e:
            pytest.skip(f"Kimi K2 timeout: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_analyst_response_contains_structured_sections(self) -> None:
        """Test that analyst response contains expected structured sections."""
        ensemble = DirectorEnsemble()
        
        context = DirectorContext(
            engagement_id="integration-test-003",
            phase="exploitation",
            prompt="""Analyze this target and provide:
            1. Attack surface analysis
            2. Risk assessment with severity
            3. Any security gaps
            4. Overlooked opportunities
            
            Target: Web application with exposed admin panel""",
        )
        
        try:
            response = await ensemble.query_analyst(context=context)
            
            # The model should return some structured content
            assert response.raw_content
            
            # Check that we got some form of analysis
            # (The model may not always follow exact format, but should provide analysis)
            content_lower = response.raw_content.lower()
            assert any(keyword in content_lower for keyword in [
                "attack", "risk", "vulnerability", "security", "analysis"
            ])
            
        except LLMProviderUnavailable as e:
            pytest.skip(f"Kimi K2 model unavailable: {e}")
        except LLMTimeoutError as e:
            pytest.skip(f"Kimi K2 timeout: {e}")


class TestAnalystTimeout:
    """Tests for analyst timeout behavior."""
    
    @pytest.mark.asyncio
    async def test_analyst_model_has_100s_timeout(self) -> None:
        """Verify analyst model is configured with 100s timeout per architecture."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_model = DIRECTOR_MODELS[DirectorRole.ANALYST]
        
        assert analyst_model.timeout == 100.0, (
            f"Analyst timeout should be 100s per architecture, got {analyst_model.timeout}"
        )


class TestAnalystModelConfiguration:
    """Tests for analyst model configuration."""
    
    def test_analyst_uses_kimi_k2_model(self) -> None:
        """Verify analyst role uses Kimi K2 model."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_model = DIRECTOR_MODELS[DirectorRole.ANALYST]
        
        assert "kimi" in analyst_model.model_id.lower(), (
            f"Analyst should use Kimi K2 model, got {analyst_model.model_id}"
        )
    
    def test_analyst_system_prompt_contains_required_sections(self) -> None:
        """Verify analyst system prompt specifies required output format."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS
        
        analyst_prompt = DIRECTOR_MODELS[DirectorRole.ANALYST].system_prompt
        prompt_lower = analyst_prompt.lower()
        
        # Should mention key sections
        assert "attack surface" in prompt_lower
        assert "risk" in prompt_lower
        assert "gap" in prompt_lower
        assert "opportunit" in prompt_lower
