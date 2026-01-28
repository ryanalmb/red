"""Unit tests for MiniMax M2 Creative Role (Story 8.4).

Tests cover:
- ThinkingContent dataclass
- CreativeAlternative dataclass
- EvasionTechnique dataclass
- NovelApproach dataclass
- CreativeResponse dataclass
- CurrentStrategy dataclass
- DefenseEncountered dataclass
- FailedAttempt dataclass
- query_creative() method
- Thinking tag extraction
- Creative alternatives extraction
- Evasion techniques extraction
- Novel approaches extraction
- Enhanced creative system prompt
- Timeout configuration (100s per architecture)
"""

from __future__ import annotations

from typing import List
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


class TestThinkingContent:
    """Tests for ThinkingContent dataclass."""
    
    def test_create_valid_thinking_content(self) -> None:
        """Test creating ThinkingContent with valid data."""
        from cyberred.llm.ensemble import ThinkingContent
        
        tc = ThinkingContent(
            content="Analyzing the current defenses...",
            position=50,
        )
        assert tc.content == "Analyzing the current defenses..."
        assert tc.position == 50
    
    def test_empty_content_raises(self) -> None:
        """Test that empty content raises ValueError."""
        from cyberred.llm.ensemble import ThinkingContent
        
        with pytest.raises(ValueError, match="content cannot be empty"):
            ThinkingContent(content="", position=0)
    
    def test_negative_position_raises(self) -> None:
        """Test that negative position raises ValueError."""
        from cyberred.llm.ensemble import ThinkingContent
        
        with pytest.raises(ValueError, match="position cannot be negative"):
            ThinkingContent(content="Test", position=-1)
    
    def test_position_zero_valid(self) -> None:
        """Test that position=0 is valid."""
        from cyberred.llm.ensemble import ThinkingContent
        
        tc = ThinkingContent(content="Start of response", position=0)
        assert tc.position == 0


class TestCreativeAlternative:
    """Tests for CreativeAlternative dataclass."""
    
    def test_create_valid_alternative(self) -> None:
        """Test creating CreativeAlternative with valid data."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        alt = CreativeAlternative(
            alternative_id="ALT-001",
            description="Use DNS tunneling for data exfiltration",
            rationale="Bypasses firewall egress filtering",
            novelty_score=0.85,
        )
        assert alt.alternative_id == "ALT-001"
        assert alt.description == "Use DNS tunneling for data exfiltration"
        assert alt.rationale == "Bypasses firewall egress filtering"
        assert alt.novelty_score == 0.85
    
    def test_empty_alternative_id_raises(self) -> None:
        """Test that empty alternative_id raises ValueError."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        with pytest.raises(ValueError, match="alternative_id cannot be empty"):
            CreativeAlternative(
                alternative_id="",
                description="Test",
                rationale="Test",
                novelty_score=0.5,
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            CreativeAlternative(
                alternative_id="ALT-001",
                description="",
                rationale="Test",
                novelty_score=0.5,
            )
    
    def test_empty_rationale_raises(self) -> None:
        """Test that empty rationale raises ValueError."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        with pytest.raises(ValueError, match="rationale cannot be empty"):
            CreativeAlternative(
                alternative_id="ALT-001",
                description="Test",
                rationale="",
                novelty_score=0.5,
            )
    
    def test_novelty_score_below_zero_raises(self) -> None:
        """Test that novelty_score < 0.0 raises ValueError."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        with pytest.raises(ValueError, match="novelty_score must be 0.0-1.0"):
            CreativeAlternative(
                alternative_id="ALT-001",
                description="Test",
                rationale="Test",
                novelty_score=-0.1,
            )
    
    def test_novelty_score_above_one_raises(self) -> None:
        """Test that novelty_score > 1.0 raises ValueError."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        with pytest.raises(ValueError, match="novelty_score must be 0.0-1.0"):
            CreativeAlternative(
                alternative_id="ALT-001",
                description="Test",
                rationale="Test",
                novelty_score=1.5,
            )
    
    def test_novelty_score_boundary_values(self) -> None:
        """Test boundary values for novelty_score."""
        from cyberred.llm.ensemble import CreativeAlternative
        
        # Test 0.0 is valid
        alt_zero = CreativeAlternative(
            alternative_id="ALT-001",
            description="Test",
            rationale="Test",
            novelty_score=0.0,
        )
        assert alt_zero.novelty_score == 0.0
        
        # Test 1.0 is valid
        alt_one = CreativeAlternative(
            alternative_id="ALT-002",
            description="Test",
            rationale="Test",
            novelty_score=1.0,
        )
        assert alt_one.novelty_score == 1.0


class TestEvasionTechnique:
    """Tests for EvasionTechnique dataclass."""
    
    def test_create_valid_evasion(self) -> None:
        """Test creating EvasionTechnique with valid data."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        eva = EvasionTechnique(
            technique_id="EVA-001",
            description="Fragment packets to evade IDS signature detection",
            target_defense="Network IDS",
            success_likelihood=0.75,
        )
        assert eva.technique_id == "EVA-001"
        assert eva.description == "Fragment packets to evade IDS signature detection"
        assert eva.target_defense == "Network IDS"
        assert eva.success_likelihood == 0.75
    
    def test_empty_technique_id_raises(self) -> None:
        """Test that empty technique_id raises ValueError."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        with pytest.raises(ValueError, match="technique_id cannot be empty"):
            EvasionTechnique(
                technique_id="",
                description="Test",
                target_defense="WAF",
                success_likelihood=0.5,
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            EvasionTechnique(
                technique_id="EVA-001",
                description="",
                target_defense="WAF",
                success_likelihood=0.5,
            )
    
    def test_empty_target_defense_raises(self) -> None:
        """Test that empty target_defense raises ValueError."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        with pytest.raises(ValueError, match="target_defense cannot be empty"):
            EvasionTechnique(
                technique_id="EVA-001",
                description="Test",
                target_defense="",
                success_likelihood=0.5,
            )
    
    def test_success_likelihood_below_zero_raises(self) -> None:
        """Test that success_likelihood < 0.0 raises ValueError."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        with pytest.raises(ValueError, match="success_likelihood must be 0.0-1.0"):
            EvasionTechnique(
                technique_id="EVA-001",
                description="Test",
                target_defense="WAF",
                success_likelihood=-0.1,
            )
    
    def test_success_likelihood_above_one_raises(self) -> None:
        """Test that success_likelihood > 1.0 raises ValueError."""
        from cyberred.llm.ensemble import EvasionTechnique
        
        with pytest.raises(ValueError, match="success_likelihood must be 0.0-1.0"):
            EvasionTechnique(
                technique_id="EVA-001",
                description="Test",
                target_defense="WAF",
                success_likelihood=1.5,
            )


class TestNovelApproach:
    """Tests for NovelApproach dataclass."""
    
    def test_create_valid_novel_approach(self) -> None:
        """Test creating NovelApproach with valid data."""
        from cyberred.llm.ensemble import NovelApproach
        
        nov = NovelApproach(
            approach_id="NOV-001",
            description="Leverage printer SNMP for lateral movement",
            innovation_type="vector",
            risk_level="MEDIUM",
            potential_impact="Access to internal network segments",
        )
        assert nov.approach_id == "NOV-001"
        assert nov.description == "Leverage printer SNMP for lateral movement"
        assert nov.innovation_type == "vector"
        assert nov.risk_level == "MEDIUM"
        assert nov.potential_impact == "Access to internal network segments"
    
    def test_empty_approach_id_raises(self) -> None:
        """Test that empty approach_id raises ValueError."""
        from cyberred.llm.ensemble import NovelApproach
        
        with pytest.raises(ValueError, match="approach_id cannot be empty"):
            NovelApproach(
                approach_id="",
                description="Test",
                innovation_type="technique",
                risk_level="HIGH",
                potential_impact="Test",
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import NovelApproach
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            NovelApproach(
                approach_id="NOV-001",
                description="",
                innovation_type="technique",
                risk_level="HIGH",
                potential_impact="Test",
            )
    
    def test_invalid_innovation_type_raises(self) -> None:
        """Test that invalid innovation_type raises ValueError."""
        from cyberred.llm.ensemble import NovelApproach
        
        with pytest.raises(ValueError, match="Invalid innovation_type"):
            NovelApproach(
                approach_id="NOV-001",
                description="Test",
                innovation_type="invalid",
                risk_level="HIGH",
                potential_impact="Test",
            )
    
    def test_all_valid_innovation_types(self) -> None:
        """Test all valid innovation types."""
        from cyberred.llm.ensemble import NovelApproach
        
        for inno_type in ["technique", "vector", "social", "physical", "hybrid"]:
            nov = NovelApproach(
                approach_id="NOV-001",
                description="Test",
                innovation_type=inno_type,
                risk_level="HIGH",
                potential_impact="Test",
            )
            assert nov.innovation_type == inno_type
    
    def test_invalid_risk_level_raises(self) -> None:
        """Test that invalid risk_level raises ValueError."""
        from cyberred.llm.ensemble import NovelApproach
        
        with pytest.raises(ValueError, match="Invalid risk_level"):
            NovelApproach(
                approach_id="NOV-001",
                description="Test",
                innovation_type="technique",
                risk_level="INVALID",
                potential_impact="Test",
            )
    
    def test_all_valid_risk_levels(self) -> None:
        """Test all valid risk levels."""
        from cyberred.llm.ensemble import NovelApproach
        
        for risk in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            nov = NovelApproach(
                approach_id="NOV-001",
                description="Test",
                innovation_type="technique",
                risk_level=risk,
                potential_impact="Test",
            )
            assert nov.risk_level == risk


class TestCurrentStrategy:
    """Tests for CurrentStrategy dataclass."""
    
    def test_create_valid_strategy(self) -> None:
        """Test creating CurrentStrategy with valid data."""
        from cyberred.llm.ensemble import CurrentStrategy
        
        strat = CurrentStrategy(
            strategy_id="STRAT-001",
            description="Network-first reconnaissance approach",
            phase="reconnaissance",
            objectives=["Map network topology", "Identify high-value targets"],
            techniques_in_use=["T1046", "T1018"],
        )
        assert strat.strategy_id == "STRAT-001"
        assert strat.description == "Network-first reconnaissance approach"
        assert strat.phase == "reconnaissance"
        assert len(strat.objectives) == 2
        assert len(strat.techniques_in_use) == 2
    
    def test_empty_strategy_id_raises(self) -> None:
        """Test that empty strategy_id raises ValueError."""
        from cyberred.llm.ensemble import CurrentStrategy
        
        with pytest.raises(ValueError, match="strategy_id cannot be empty"):
            CurrentStrategy(
                strategy_id="",
                description="Test",
                phase="recon",
                objectives=[],
                techniques_in_use=[],
            )
    
    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import CurrentStrategy
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            CurrentStrategy(
                strategy_id="STRAT-001",
                description="",
                phase="recon",
                objectives=[],
                techniques_in_use=[],
            )


class TestDefenseEncountered:
    """Tests for DefenseEncountered dataclass."""
    
    def test_create_valid_defense(self) -> None:
        """Test creating DefenseEncountered with valid data."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        defense = DefenseEncountered(
            defense_id="DEF-001",
            defense_type="WAF",
            target="web-server-01",
            description="Cloudflare WAF blocking SQL injection attempts",
            blocking_technique="T1190",
        )
        assert defense.defense_id == "DEF-001"
        assert defense.defense_type == "WAF"
        assert defense.target == "web-server-01"
        assert defense.description == "Cloudflare WAF blocking SQL injection attempts"
        assert defense.blocking_technique == "T1190"
    
    def test_empty_defense_id_raises(self) -> None:
        """Test that empty defense_id raises ValueError."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        with pytest.raises(ValueError, match="defense_id cannot be empty"):
            DefenseEncountered(
                defense_id="",
                defense_type="WAF",
                target="target",
                description="Test",
            )
    
    def test_empty_defense_type_raises(self) -> None:
        """Test that empty defense_type raises ValueError."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        with pytest.raises(ValueError, match="defense_type cannot be empty"):
            DefenseEncountered(
                defense_id="DEF-001",
                defense_type="",
                target="target",
                description="Test",
            )
    
    def test_optional_blocking_technique(self) -> None:
        """Test that blocking_technique is optional."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        defense = DefenseEncountered(
            defense_id="DEF-001",
            defense_type="IDS",
            target="network",
            description="Snort IDS detected",
        )
        assert defense.blocking_technique is None

    def test_empty_target_raises(self) -> None:
        """Test that empty target raises ValueError."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        with pytest.raises(ValueError, match="target cannot be empty"):
            DefenseEncountered(
                defense_id="DEF-001",
                defense_type="WAF",
                target="",
                description="Test",
            )

    def test_empty_description_raises(self) -> None:
        """Test that empty description raises ValueError."""
        from cyberred.llm.ensemble import DefenseEncountered
        
        with pytest.raises(ValueError, match="description cannot be empty"):
            DefenseEncountered(
                defense_id="DEF-001",
                defense_type="WAF",
                target="target",
                description="",
            )


class TestFailedAttempt:
    """Tests for FailedAttempt dataclass."""
    
    def test_create_valid_failed_attempt(self) -> None:
        """Test creating FailedAttempt with valid data."""
        from cyberred.llm.ensemble import FailedAttempt
        
        fa = FailedAttempt(
            attempt_id="FA-001",
            technique="SQL Injection",
            target="login.example.com",
            failure_reason="WAF blocked payload",
            timestamp="2026-01-28T07:00:00Z",
        )
        assert fa.attempt_id == "FA-001"
        assert fa.technique == "SQL Injection"
        assert fa.target == "login.example.com"
        assert fa.failure_reason == "WAF blocked payload"
        assert fa.timestamp == "2026-01-28T07:00:00Z"
    
    def test_empty_attempt_id_raises(self) -> None:
        """Test that empty attempt_id raises ValueError."""
        from cyberred.llm.ensemble import FailedAttempt
        
        with pytest.raises(ValueError, match="attempt_id cannot be empty"):
            FailedAttempt(
                attempt_id="",
                technique="SQLi",
                target="target",
                failure_reason="blocked",
                timestamp="2026-01-28",
            )
    
    def test_empty_technique_raises(self) -> None:
        """Test that empty technique raises ValueError."""
        from cyberred.llm.ensemble import FailedAttempt
        
        with pytest.raises(ValueError, match="technique cannot be empty"):
            FailedAttempt(
                attempt_id="FA-001",
                technique="",
                target="target",
                failure_reason="blocked",
                timestamp="2026-01-28",
            )
    
    def test_empty_failure_reason_raises(self) -> None:
        """Test that empty failure_reason raises ValueError."""
        from cyberred.llm.ensemble import FailedAttempt
        
        with pytest.raises(ValueError, match="failure_reason cannot be empty"):
            FailedAttempt(
                attempt_id="FA-001",
                technique="SQLi",
                target="target",
                failure_reason="",
                timestamp="2026-01-28",
            )

    def test_empty_target_raises(self) -> None:
        """Test that empty target raises ValueError."""
        from cyberred.llm.ensemble import FailedAttempt
        
        with pytest.raises(ValueError, match="target cannot be empty"):
            FailedAttempt(
                attempt_id="FA-001",
                technique="SQLi",
                target="",
                failure_reason="blocked",
                timestamp="2026-01-28",
            )

    def test_empty_timestamp_raises(self) -> None:
        """Test that empty timestamp raises ValueError."""
        from cyberred.llm.ensemble import FailedAttempt
        
        with pytest.raises(ValueError, match="timestamp cannot be empty"):
            FailedAttempt(
                attempt_id="FA-001",
                technique="SQLi",
                target="target",
                failure_reason="blocked",
                timestamp="",
            )


class TestExtractThinkingTags:
    """Tests for extract_thinking_tags function."""
    
    def test_extract_single_thinking_tag(self) -> None:
        """Test extracting a single thinking tag."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = "Hello <think>This is my reasoning</think> world"
        results = extract_thinking_tags(response)
        
        assert len(results) == 1
        assert results[0].content == "This is my reasoning"
        assert results[0].position == 6
    
    def test_extract_multiple_thinking_tags(self) -> None:
        """Test extracting multiple thinking tags."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = """<think>First thought</think>
Some text here
<think>Second thought</think>
More text
<think>Third thought</think>"""
        
        results = extract_thinking_tags(response)
        
        assert len(results) == 3
        assert results[0].content == "First thought"
        assert results[1].content == "Second thought"
        assert results[2].content == "Third thought"
    
    def test_extract_no_thinking_tags(self) -> None:
        """Test extracting when no thinking tags present."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = "No thinking tags here"
        results = extract_thinking_tags(response)
        
        assert len(results) == 0
    
    def test_extract_empty_thinking_tag_skipped(self) -> None:
        """Test that empty thinking tags are skipped."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = "<think></think><think>Valid content</think><think>   </think>"
        results = extract_thinking_tags(response)
        
        assert len(results) == 1
        assert results[0].content == "Valid content"
    
    def test_extract_multiline_thinking_content(self) -> None:
        """Test extracting multiline thinking content."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = """<think>
Line 1
Line 2
Line 3
</think>"""
        
        results = extract_thinking_tags(response)
        
        assert len(results) == 1
        assert "Line 1" in results[0].content
        assert "Line 2" in results[0].content
        assert "Line 3" in results[0].content
    
    def test_case_insensitive_tags(self) -> None:
        """Test that thinking tags are case-insensitive."""
        from cyberred.llm.ensemble import extract_thinking_tags
        
        response = "<THINK>Upper case</THINK><Think>Mixed case</Think>"
        results = extract_thinking_tags(response)
        
        assert len(results) == 2


class TestStripThinkingTags:
    """Tests for strip_thinking_tags function."""
    
    def test_strip_single_tag(self) -> None:
        """Test stripping a single thinking tag."""
        from cyberred.llm.ensemble import strip_thinking_tags
        
        response = "Hello <think>reasoning</think> world"
        result = strip_thinking_tags(response)
        
        assert result == "Hello  world"
    
    def test_strip_multiple_tags(self) -> None:
        """Test stripping multiple thinking tags."""
        from cyberred.llm.ensemble import strip_thinking_tags
        
        response = "<think>First</think>Text<think>Second</think>More"
        result = strip_thinking_tags(response)
        
        assert result == "TextMore"
    
    def test_strip_no_tags(self) -> None:
        """Test stripping when no tags present."""
        from cyberred.llm.ensemble import strip_thinking_tags
        
        response = "No tags here"
        result = strip_thinking_tags(response)
        
        assert result == "No tags here"
    
    def test_strip_preserves_surrounding_text(self) -> None:
        """Test that surrounding text is preserved."""
        from cyberred.llm.ensemble import strip_thinking_tags
        
        response = """### Creative Alternatives
<think>Analyzing options...</think>
| ALT-001 | Description |"""
        
        result = strip_thinking_tags(response)
        
        assert "### Creative Alternatives" in result
        assert "| ALT-001 | Description |" in result
        assert "<think>" not in result


class TestExtractCreativeAlternatives:
    """Tests for extract_creative_alternatives function."""
    
    def test_extract_from_table(self) -> None:
        """Test extracting creative alternatives from table format."""
        from cyberred.llm.ensemble import extract_creative_alternatives
        
        response = """### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | Use DNS tunneling | Bypasses firewall | 0.85 |
| ALT-002 | ICMP covert channel | Evades DPI | 0.9 |"""
        
        results = extract_creative_alternatives(response)
        
        assert len(results) == 2
        assert results[0].alternative_id == "ALT-001"
        assert results[0].description == "Use DNS tunneling"
        assert results[0].rationale == "Bypasses firewall"
        assert results[0].novelty_score == 0.85
    
    def test_extract_no_alternatives(self) -> None:
        """Test extracting when no alternatives present."""
        from cyberred.llm.ensemble import extract_creative_alternatives
        
        response = "No alternatives section here"
        results = extract_creative_alternatives(response)
        
        assert len(results) == 0
    
    def test_extract_with_malformed_rows_skipped(self) -> None:
        """Test that malformed rows are skipped."""
        from cyberred.llm.ensemble import extract_creative_alternatives
        
        response = """### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | Valid | Valid rationale | 0.7 |
| | Missing ID | | 0.5 |
| ALT-002 | Also valid | Another rationale | 0.8 |"""
        
        results = extract_creative_alternatives(response)
        
        assert len(results) == 2
        assert results[0].alternative_id == "ALT-001"
        assert results[1].alternative_id == "ALT-002"


class TestExtractEvasionTechniques:
    """Tests for extract_evasion_techniques function."""
    
    def test_extract_from_table(self) -> None:
        """Test extracting evasion techniques from table format."""
        from cyberred.llm.ensemble import extract_evasion_techniques
        
        response = """### Evasion Techniques
| Technique ID | Description | Target Defense | Success Likelihood |
|--------------|-------------|----------------|-------------------|
| EVA-001 | Fragment packets | IDS | 0.75 |
| EVA-002 | Use encoding | WAF | 0.8 |"""
        
        results = extract_evasion_techniques(response)
        
        assert len(results) == 2
        assert results[0].technique_id == "EVA-001"
        assert results[0].description == "Fragment packets"
        assert results[0].target_defense == "IDS"
        assert results[0].success_likelihood == 0.75
    
    def test_extract_no_techniques(self) -> None:
        """Test extracting when no techniques present."""
        from cyberred.llm.ensemble import extract_evasion_techniques
        
        response = "No evasion section here"
        results = extract_evasion_techniques(response)
        
        assert len(results) == 0


class TestExtractNovelApproaches:
    """Tests for extract_novel_approaches function."""
    
    def test_extract_from_table(self) -> None:
        """Test extracting novel approaches from table format."""
        from cyberred.llm.ensemble import extract_novel_approaches
        
        response = """### Novel Approaches
| Approach ID | Description | Innovation Type | Risk Level | Potential Impact |
|-------------|-------------|-----------------|------------|------------------|
| NOV-001 | Printer SNMP pivot | vector | MEDIUM | Network access |
| NOV-002 | Social engineering | social | HIGH | Credential theft |"""
        
        results = extract_novel_approaches(response)
        
        assert len(results) == 2
        assert results[0].approach_id == "NOV-001"
        assert results[0].description == "Printer SNMP pivot"
        assert results[0].innovation_type == "vector"
        assert results[0].risk_level == "MEDIUM"
        assert results[0].potential_impact == "Network access"
    
    def test_extract_no_approaches(self) -> None:
        """Test extracting when no approaches present."""
        from cyberred.llm.ensemble import extract_novel_approaches
        
        response = "No novel approaches section here"
        results = extract_novel_approaches(response)
        
        assert len(results) == 0


class TestCreativeResponse:
    """Tests for CreativeResponse dataclass."""
    
    def test_create_valid_response(self) -> None:
        """Test creating CreativeResponse with valid data."""
        from cyberred.llm.ensemble import (
            CreativeResponse,
            ThinkingContent,
            CreativeAlternative,
            EvasionTechnique,
            NovelApproach,
            ModelResponse,
            DirectorRole,
        )
        
        model_resp = ModelResponse(
            role=DirectorRole.CREATIVE,
            model_id="minimaxai/minimax-m2",
            content="test",
            latency_ms=100,
            success=True,
        )
        
        resp = CreativeResponse(
            raw_content="<think>reasoning</think>content",
            clean_content="content",
            thinking_content=[ThinkingContent(content="reasoning", position=0)],
            creative_alternatives=[
                CreativeAlternative(
                    alternative_id="ALT-001",
                    description="Test",
                    rationale="Reason",
                    novelty_score=0.5,
                )
            ],
            evasion_techniques=[
                EvasionTechnique(
                    technique_id="EVA-001",
                    description="Test",
                    target_defense="WAF",
                    success_likelihood=0.5,
                )
            ],
            novel_approaches=[
                NovelApproach(
                    approach_id="NOV-001",
                    description="Test",
                    innovation_type="technique",
                    risk_level="HIGH",
                    potential_impact="Impact",
                )
            ],
            model_response=model_resp,
        )
        
        assert resp.raw_content == "<think>reasoning</think>content"
        assert resp.clean_content == "content"
        assert len(resp.thinking_content) == 1
        assert len(resp.creative_alternatives) == 1
        assert len(resp.evasion_techniques) == 1
        assert len(resp.novel_approaches) == 1


class TestQueryCreative:
    """Tests for query_creative method."""
    
    @pytest.fixture
    def mock_gateway(self) -> MagicMock:
        """Create a mock gateway."""
        mock = MagicMock()
        mock.director_complete = AsyncMock()
        return mock
    
    @pytest.fixture
    def sample_creative_response(self) -> str:
        """Sample creative response with all sections."""
        return """<think>
Analyzing the current strategy and defenses encountered...
The WAF is blocking direct SQL injection attempts.
Need to think creatively about bypass techniques.
</think>

### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | Time-based blind SQLi | Bypasses WAF pattern matching | 0.75 |

<think>
Considering evasion techniques for the WAF...
</think>

### Evasion Techniques
| Technique ID | Description | Target Defense | Success Likelihood |
|--------------|-------------|----------------|-------------------|
| EVA-001 | Unicode encoding | WAF | 0.8 |

### Novel Approaches
| Approach ID | Description | Innovation Type | Risk Level | Potential Impact |
|-------------|-------------|-----------------|------------|------------------|
| NOV-001 | Target API instead of web UI | vector | MEDIUM | Direct DB access |"""
    
    @pytest.mark.asyncio
    async def test_query_creative_success(
        self, mock_gateway: MagicMock, sample_creative_response: str
    ) -> None:
        """Test successful creative query."""
        from cyberred.llm.ensemble import CurrentStrategy, DefenseEncountered, FailedAttempt
        
        mock_gateway.director_complete.return_value = LLMResponse(
            content=sample_creative_response,
            model="minimaxai/minimax-m2",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300),
            latency_ms=500,
        )
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            ensemble = DirectorEnsemble()
            context = DirectorContext(
                engagement_id="eng-001",
                phase="exploitation",
                prompt="Suggest creative alternatives for SQLi attack",
            )
            
            current_strategy = CurrentStrategy(
                strategy_id="STRAT-001",
                description="Direct SQLi attack",
                phase="exploitation",
                objectives=["Gain DB access"],
                techniques_in_use=["T1190"],
            )
            
            defenses = [
                DefenseEncountered(
                    defense_id="DEF-001",
                    defense_type="WAF",
                    target="web-server",
                    description="Cloudflare WAF detected",
                )
            ]
            
            failed = [
                FailedAttempt(
                    attempt_id="FA-001",
                    technique="SQLi",
                    target="login.php",
                    failure_reason="WAF blocked",
                    timestamp="2026-01-28",
                )
            ]
            
            result = await ensemble.query_creative(
                context,
                current_strategy=current_strategy,
                defenses_encountered=defenses,
                failed_attempts=failed,
            )
            
            assert result.raw_content == sample_creative_response
            assert len(result.thinking_content) >= 1
            assert len(result.creative_alternatives) >= 1
            assert len(result.evasion_techniques) >= 1
            assert len(result.novel_approaches) >= 1
    
    @pytest.mark.asyncio
    async def test_query_creative_timeout(self, mock_gateway: MagicMock) -> None:
        """Test creative query timeout raises LLMTimeoutError."""
        import asyncio
        
        mock_gateway.director_complete.side_effect = asyncio.TimeoutError()
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            ensemble = DirectorEnsemble()
            context = DirectorContext(
                engagement_id="eng-001",
                phase="exploitation",
                prompt="Test prompt",
            )
            
            with pytest.raises(LLMTimeoutError):
                await ensemble.query_creative(context)
    
    @pytest.mark.asyncio
    async def test_query_creative_unavailable(self, mock_gateway: MagicMock) -> None:
        """Test creative query with unavailable model raises LLMProviderUnavailable."""
        mock_gateway.director_complete.side_effect = LLMProviderUnavailable("Model unavailable")
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            ensemble = DirectorEnsemble()
            context = DirectorContext(
                engagement_id="eng-001",
                phase="exploitation",
                prompt="Test prompt",
            )
            
            with pytest.raises(LLMProviderUnavailable):
                await ensemble.query_creative(context)
    
    @pytest.mark.asyncio
    async def test_query_creative_without_optional_params(
        self, mock_gateway: MagicMock, sample_creative_response: str
    ) -> None:
        """Test query_creative works without optional parameters."""
        mock_gateway.director_complete.return_value = LLMResponse(
            content=sample_creative_response,
            model="minimaxai/minimax-m2",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300),
            latency_ms=500,
        )
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            ensemble = DirectorEnsemble()
            context = DirectorContext(
                engagement_id="eng-001",
                phase="exploitation",
                prompt="Suggest creative alternatives",
            )
            
            result = await ensemble.query_creative(context)
            
            assert result is not None
            assert result.model_response.success


class TestBuildCreativePrompt:
    """Tests for _build_creative_prompt method."""
    
    def test_build_prompt_with_all_context(self) -> None:
        """Test building prompt with all context provided."""
        from cyberred.llm.ensemble import CurrentStrategy, DefenseEncountered, FailedAttempt
        
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Suggest creative alternatives",
        )
        
        current_strategy = CurrentStrategy(
            strategy_id="STRAT-001",
            description="Direct SQLi attack",
            phase="exploitation",
            objectives=["Gain DB access"],
            techniques_in_use=["T1190"],
        )
        
        defenses = [
            DefenseEncountered(
                defense_id="DEF-001",
                defense_type="WAF",
                target="web-server",
                description="Cloudflare WAF detected",
            )
        ]
        
        failed = [
            FailedAttempt(
                attempt_id="FA-001",
                technique="SQLi",
                target="login.php",
                failure_reason="WAF blocked",
                timestamp="2026-01-28",
            )
        ]
        
        prompt = ensemble._build_creative_prompt(
            context, current_strategy, defenses, failed
        )
        
        assert "eng-001" in prompt
        assert "exploitation" in prompt
        assert "Current Strategy" in prompt
        assert "STRAT-001" in prompt
        assert "Defenses Encountered" in prompt
        assert "WAF" in prompt
        assert "Failed Attempts" in prompt
        assert "SQLi" in prompt
    
    def test_build_prompt_minimal(self) -> None:
        """Test building prompt with minimal context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Need creative ideas",
        )
        
        prompt = ensemble._build_creative_prompt(context, None, None, None)
        
        assert "eng-001" in prompt
        assert "recon" in prompt
        assert "Need creative ideas" in prompt


class TestCreativeSystemPrompt:
    """Tests for enhanced CREATIVE system prompt."""
    
    def test_creative_system_prompt_has_structured_format(self) -> None:
        """Test that CREATIVE system prompt includes structured output requirements."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorRole
        
        creative_model = DIRECTOR_MODELS[DirectorRole.CREATIVE]
        prompt = creative_model.system_prompt
        
        # Verify structured format instructions are present
        assert "<think>" in prompt or "think" in prompt.lower()
        assert "Creative Alternatives" in prompt
        assert "Evasion Techniques" in prompt
        assert "Novel Approaches" in prompt
    
    def test_creative_timeout_is_100s(self) -> None:
        """Test that CREATIVE model timeout is 100s per architecture."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorRole
        
        creative_model = DIRECTOR_MODELS[DirectorRole.CREATIVE]
        assert creative_model.timeout == 100.0
    
    def test_creative_model_id_is_minimax(self) -> None:
        """Test that CREATIVE model ID is correct."""
        from cyberred.llm.ensemble import DIRECTOR_MODELS, DirectorRole
        
        creative_model = DIRECTOR_MODELS[DirectorRole.CREATIVE]
        assert creative_model.model_id == "minimaxai/minimax-m2"
