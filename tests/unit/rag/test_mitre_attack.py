"""Unit tests for MITRE ATT&CK Source Integration.

Story 6.5: MITRE ATT&CK Source Integration (FR77)
Tests technique extraction, sub-technique linkage, mitigation linking, and ID filtering.
"""
import pytest
from typing import Any, Dict, List

from cyberred.rag.sources.mitre_attack import (
    TECHNIQUE_ID_PATTERN,
    _extract_technique,
    _extract_mitigation,
    _link_mitigations,
    _resolve_parent_technique_ids,
    _convert_to_documents,
)


class TestTechniqueIdPattern:
    """Test ATT&CK technique ID regex pattern (AC: 7)."""

    def test_matches_base_technique_id(self) -> None:
        """Test matching base technique IDs like T1059."""
        assert TECHNIQUE_ID_PATTERN.match("T1059")
        assert TECHNIQUE_ID_PATTERN.match("T1234")
        assert TECHNIQUE_ID_PATTERN.match("T0001")

    def test_matches_subtechnique_id(self) -> None:
        """Test matching sub-technique IDs like T1059.001."""
        assert TECHNIQUE_ID_PATTERN.match("T1059.001")
        assert TECHNIQUE_ID_PATTERN.match("T1234.999")
        assert TECHNIQUE_ID_PATTERN.match("T0001.123")

    def test_rejects_invalid_ids(self) -> None:
        """Test rejection of invalid technique IDs."""
        assert not TECHNIQUE_ID_PATTERN.match("T123")  # Too short
        assert not TECHNIQUE_ID_PATTERN.match("T12345")  # Too long
        assert not TECHNIQUE_ID_PATTERN.match("T1059.01")  # Subtechnique too short
        assert not TECHNIQUE_ID_PATTERN.match("T1059.1234")  # Subtechnique too long
        assert not TECHNIQUE_ID_PATTERN.match("M1059")  # Wrong prefix
        assert not TECHNIQUE_ID_PATTERN.match("1059")  # No prefix
        assert not TECHNIQUE_ID_PATTERN.match("")  # Empty


class TestExtractTechnique:
    """Test technique extraction from STIX attack-pattern objects (AC: 4)."""

    def test_extracts_basic_technique(self) -> None:
        """Test extracting a basic technique with all fields."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--1234",
            "name": "PowerShell",
            "description": "Adversaries may use PowerShell commands.",
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": "T1059",
                    "url": "https://attack.mitre.org/techniques/T1059",
                }
            ],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "execution"}
            ],
            "x_mitre_platforms": ["Windows"],
            "x_mitre_detection": "Monitor for process creation events.",
        }

        result = _extract_technique(obj)

        assert result is not None
        assert result["attack_id"] == "T1059"
        assert result["name"] == "PowerShell"
        assert result["description"] == "Adversaries may use PowerShell commands."
        assert result["tactics"] == ["execution"]
        assert result["platforms"] == ["Windows"]
        assert result["detection"] == "Monitor for process creation events."
        assert result["is_subtechnique"] is False
        assert result["parent_technique_id"] is None
        assert result["source_url"] == "https://attack.mitre.org/techniques/T1059"

    def test_extracts_subtechnique_with_parent_ref(self) -> None:
        """Test extracting sub-technique with x_mitre_parent_technique_ref (AC: 6)."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--5678",
            "name": "PowerShell Profile",
            "description": "Adversaries may modify PowerShell profiles.",
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": "T1546.013",
                }
            ],
            "kill_chain_phases": [],
            "x_mitre_platforms": ["Windows"],
            "x_mitre_is_subtechnique": True,
            "x_mitre_parent_technique_ref": "attack-pattern--1234",
        }

        result = _extract_technique(obj)

        assert result is not None
        assert result["attack_id"] == "T1546.013"
        assert result["is_subtechnique"] is True
        assert result["parent_technique_id"] == "attack-pattern--1234"

    def test_extracts_subtechnique_fallback_parent_derivation(self) -> None:
        """Test sub-technique parent ID derived from T####.### format (AC: 6)."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--9999",
            "name": "Python",
            "description": "Python scripting.",
            "external_references": [
                {
                    "source_name": "mitre-attack",
                    "external_id": "T1059.006",
                }
            ],
            "x_mitre_is_subtechnique": True,
            # No x_mitre_parent_technique_ref - should derive from ID
        }

        result = _extract_technique(obj)

        assert result is not None
        assert result["attack_id"] == "T1059.006"
        assert result["is_subtechnique"] is True
        assert result["parent_technique_id"] == "T1059"

    def test_extracts_multiple_tactics(self) -> None:
        """Test extracting technique with multiple tactics."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--multi",
            "name": "Multi-Tactic Technique",
            "description": "Spans multiple tactics.",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1001"}
            ],
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "defense-evasion"},
                {"kill_chain_name": "mitre-attack", "phase_name": "command-and-control"},
            ],
        }

        result = _extract_technique(obj)

        assert result is not None
        assert "defense-evasion" in result["tactics"]
        assert "command-and-control" in result["tactics"]

    def test_extracts_multiple_platforms(self) -> None:
        """Test extracting technique with multiple platforms."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--plat",
            "name": "Cross-Platform",
            "description": "Works on multiple platforms.",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1002"}
            ],
            "x_mitre_platforms": ["Windows", "Linux", "macOS"],
        }

        result = _extract_technique(obj)

        assert result is not None
        assert result["platforms"] == ["Windows", "Linux", "macOS"]

    def test_rejects_invalid_technique_id(self) -> None:
        """Test rejection of objects without valid ATT&CK IDs."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--bad",
            "name": "Bad ID",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "BADID"}
            ],
        }

        result = _extract_technique(obj)
        assert result is None

    def test_rejects_revoked_technique(self) -> None:
        """Test rejection of revoked techniques."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--revoked",
            "name": "Revoked Technique",
            "revoked": True,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1003"}
            ],
        }

        result = _extract_technique(obj)
        assert result is None

    def test_rejects_deprecated_technique(self) -> None:
        """Test rejection of deprecated techniques."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--deprecated",
            "name": "Deprecated Technique",
            "x_mitre_deprecated": True,
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1004"}
            ],
        }

        result = _extract_technique(obj)
        assert result is None

    def test_rejects_no_mitre_attack_reference(self) -> None:
        """Test rejection when no mitre-attack source_name reference."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--other",
            "name": "Other Source",
            "external_references": [
                {"source_name": "other-source", "external_id": "T1005"}
            ],
        }

        result = _extract_technique(obj)
        assert result is None

    def test_handles_missing_optional_fields(self) -> None:
        """Test extraction with minimal required fields."""
        obj = {
            "type": "attack-pattern",
            "id": "attack-pattern--minimal",
            "name": "Minimal",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1006"}
            ],
        }

        result = _extract_technique(obj)

        assert result is not None
        assert result["attack_id"] == "T1006"
        assert result["name"] == "Minimal"
        assert result["description"] == ""
        assert result["tactics"] == []
        assert result["platforms"] == []
        assert result["detection"] == ""


class TestExtractMitigation:
    """Test mitigation extraction from STIX course-of-action objects (AC: 5)."""

    def test_extracts_basic_mitigation(self) -> None:
        """Test extracting a basic mitigation."""
        obj = {
            "type": "course-of-action",
            "id": "course-of-action--1234",
            "name": "Application Developer Guidance",
            "description": "Guidance for developers to reduce attack surface.",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "M1013"}
            ],
        }

        result = _extract_mitigation(obj)

        assert result is not None
        assert result["stix_id"] == "course-of-action--1234"
        assert result["mitigation_id"] == "M1013"
        assert result["name"] == "Application Developer Guidance"
        assert result["description"] == "Guidance for developers to reduce attack surface."

    def test_rejects_revoked_mitigation(self) -> None:
        """Test rejection of revoked mitigations."""
        obj = {
            "type": "course-of-action",
            "id": "course-of-action--revoked",
            "name": "Revoked Mitigation",
            "revoked": True,
        }

        result = _extract_mitigation(obj)
        assert result is None

    def test_rejects_deprecated_mitigation(self) -> None:
        """Test rejection of deprecated mitigations."""
        obj = {
            "type": "course-of-action",
            "id": "course-of-action--deprecated",
            "name": "Deprecated Mitigation",
            "x_mitre_deprecated": True,
        }

        result = _extract_mitigation(obj)
        assert result is None


class TestLinkMitigations:
    """Test mitigation linking to techniques via relationships (AC: 5)."""

    def test_links_mitigations_to_techniques(self) -> None:
        """Test linking mitigations to techniques via relationship objects."""
        techniques = {
            "attack-pattern--1": {"attack_id": "T1001", "name": "Technique 1"},
            "attack-pattern--2": {"attack_id": "T1002", "name": "Technique 2"},
        }

        mitigations = {
            "course-of-action--a": {"name": "Mitigation A", "description": "Desc A"},
            "course-of-action--b": {"name": "Mitigation B", "description": "Desc B"},
        }

        relationships = [
            {
                "type": "relationship",
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--a",
                "target_ref": "attack-pattern--1",
            },
            {
                "type": "relationship",
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--b",
                "target_ref": "attack-pattern--1",
            },
            {
                "type": "relationship",
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--a",
                "target_ref": "attack-pattern--2",
            },
        ]

        result = _link_mitigations(techniques, mitigations, relationships)

        # Technique 1 should have 2 mitigations
        assert "attack-pattern--1" in result
        assert len(result["attack-pattern--1"]) == 2
        mit_names = [m["name"] for m in result["attack-pattern--1"]]
        assert "Mitigation A" in mit_names
        assert "Mitigation B" in mit_names

        # Technique 2 should have 1 mitigation
        assert "attack-pattern--2" in result
        assert len(result["attack-pattern--2"]) == 1
        assert result["attack-pattern--2"][0]["name"] == "Mitigation A"

    def test_ignores_unknown_refs(self) -> None:
        """Test that unknown technique/mitigation refs are ignored."""
        techniques = {"attack-pattern--1": {"attack_id": "T1001"}}
        mitigations = {"course-of-action--a": {"name": "Mit A"}}

        relationships = [
            {
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--unknown",  # Unknown mitigation
                "target_ref": "attack-pattern--1",
            },
            {
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--a",
                "target_ref": "attack-pattern--unknown",  # Unknown technique
            },
        ]

        result = _link_mitigations(techniques, mitigations, relationships)

        # No valid links should be created
        assert len(result) == 0


class TestResolveParentTechniqueIds:
    """Test parent technique ID resolution (AC: 6)."""

    def test_resolves_stix_refs_to_attack_ids(self) -> None:
        """Test resolving STIX refs to ATT&CK IDs for parent techniques."""
        techniques = {
            "attack-pattern--parent": {
                "attack_id": "T1546",
                "is_subtechnique": False,
                "parent_technique_id": None,
            },
            "attack-pattern--child": {
                "attack_id": "T1546.013",
                "is_subtechnique": True,
                "parent_technique_id": "attack-pattern--parent",  # STIX ref
            },
        }

        _resolve_parent_technique_ids(techniques)

        assert techniques["attack-pattern--child"]["parent_technique_id"] == "T1546"

    def test_preserves_already_resolved_ids(self) -> None:
        """Test that already-resolved ATT&CK IDs are preserved."""
        techniques = {
            "attack-pattern--child": {
                "attack_id": "T1059.006",
                "is_subtechnique": True,
                "parent_technique_id": "T1059",  # Already resolved
            },
        }

        _resolve_parent_technique_ids(techniques)

        # Should remain unchanged (not found in STIX mapping, so left as-is)
        assert techniques["attack-pattern--child"]["parent_technique_id"] == "T1059"


class TestConvertToDocuments:
    """Test conversion to RAG documents (AC: 7)."""

    def test_converts_technique_to_document(self) -> None:
        """Test converting a technique to a document with proper format."""
        techniques = {
            "attack-pattern--1": {
                "stix_id": "attack-pattern--1",
                "attack_id": "T1059",
                "name": "Command and Scripting Interpreter",
                "description": "Adversaries may use interpreters.",
                "tactics": ["execution"],
                "platforms": ["Windows", "Linux"],
                "detection": "Monitor process activity.",
                "is_subtechnique": False,
                "parent_technique_id": None,
                "source_url": "https://attack.mitre.org/techniques/T1059",
            }
        }

        mitigations: Dict[str, List[Dict[str, Any]]] = {
            "attack-pattern--1": [
                {"name": "Disable Scripts", "description": "Disable scripting."}
            ]
        }

        documents = _convert_to_documents(techniques, mitigations)

        assert len(documents) == 1
        doc = documents[0]

        # Check text content
        assert "Technique T1059: Command and Scripting Interpreter" in doc["text"]
        assert "Description:" in doc["text"]
        assert "Adversaries may use interpreters." in doc["text"]
        assert "Tactics: execution" in doc["text"]
        assert "Platforms: Windows, Linux" in doc["text"]
        assert "Detection:" in doc["text"]
        assert "Monitor process activity." in doc["text"]
        assert "Mitigations:" in doc["text"]
        assert "Disable Scripts" in doc["text"]

        # Check metadata
        assert doc["metadata"]["id"] == "T1059"
        assert doc["metadata"]["technique_ids"] == ["T1059"]
        assert doc["metadata"]["name"] == "Command and Scripting Interpreter"
        assert doc["metadata"]["tactics"] == ["execution"]
        assert doc["metadata"]["platforms"] == ["Windows", "Linux"]
        assert doc["metadata"]["is_subtechnique"] is False
        assert doc["metadata"]["source_url"] == "https://attack.mitre.org/techniques/T1059"

    def test_converts_subtechnique_with_parent(self) -> None:
        """Test converting a sub-technique with parent reference."""
        techniques = {
            "attack-pattern--parent": {
                "stix_id": "attack-pattern--parent",
                "attack_id": "T1059",
                "name": "Command and Scripting Interpreter",
                "description": "Parent technique.",
                "tactics": ["execution"],
                "platforms": ["Windows"],
                "detection": "",
                "is_subtechnique": False,
                "parent_technique_id": None,
                "source_url": None,
            },
            "attack-pattern--child": {
                "stix_id": "attack-pattern--child",
                "attack_id": "T1059.001",
                "name": "PowerShell",
                "description": "PowerShell sub-technique.",
                "tactics": ["execution"],
                "platforms": ["Windows"],
                "detection": "Monitor PowerShell.",
                "is_subtechnique": True,
                "parent_technique_id": "attack-pattern--parent",  # STIX ref to resolve
                "source_url": None,
            },
        }

        documents = _convert_to_documents(techniques, {})

        # Find the sub-technique document
        child_doc = next(d for d in documents if d["metadata"]["id"] == "T1059.001")

        assert "Parent Technique: T1059" in child_doc["text"]
        assert child_doc["metadata"]["is_subtechnique"] is True
        assert child_doc["metadata"]["parent_technique_id"] == "T1059"

    def test_handles_technique_without_mitigations(self) -> None:
        """Test converting technique with no mitigations."""
        techniques = {
            "attack-pattern--1": {
                "stix_id": "attack-pattern--1",
                "attack_id": "T1001",
                "name": "Data Obfuscation",
                "description": "Obfuscate data.",
                "tactics": ["command-and-control"],
                "platforms": [],
                "detection": "",
                "is_subtechnique": False,
                "parent_technique_id": None,
                "source_url": None,
            }
        }

        documents = _convert_to_documents(techniques, {})

        assert len(documents) == 1
        assert "Mitigations:" not in documents[0]["text"]

    def test_document_metadata_has_required_fields(self) -> None:
        """Test that document metadata contains all required fields."""
        techniques = {
            "attack-pattern--1": {
                "stix_id": "attack-pattern--1",
                "attack_id": "T1234",
                "name": "Test Technique",
                "description": "",
                "tactics": [],
                "platforms": [],
                "detection": "",
                "is_subtechnique": False,
                "parent_technique_id": None,
                "source_url": None,
            }
        }

        documents = _convert_to_documents(techniques, {})

        doc = documents[0]
        # Required metadata fields per story
        assert "id" in doc["metadata"]
        assert "technique_ids" in doc["metadata"]
        assert isinstance(doc["metadata"]["technique_ids"], list)
        assert len(doc["metadata"]["technique_ids"]) >= 1
        assert TECHNIQUE_ID_PATTERN.match(doc["metadata"]["technique_ids"][0])
