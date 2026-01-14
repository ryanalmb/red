"""Integration tests for MITRE ATT&CK Source Integration.

Story 6.5: MITRE ATT&CK Source Integration (FR77)
Tests end-to-end ingest with mocked network (AC: 8).
"""
import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
import respx
from httpx import Response

from cyberred.rag.sources import mitre_attack
from cyberred.rag.sources.mitre_attack import (
    ENTERPRISE_ATTACK_URL,
    SOURCE_NAME,
    TECHNIQUE_ID_PATTERN,
    ingest,
)
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings


def _create_mock_stix_bundle() -> Dict[str, Any]:
    """Create a minimal mock STIX bundle for testing."""
    return {
        "type": "bundle",
        "id": "bundle--test",
        "spec_version": "2.1",
        "objects": [
            # Parent technique
            {
                "type": "attack-pattern",
                "id": "attack-pattern--parent-1",
                "name": "Command and Scripting Interpreter",
                "description": "Adversaries may abuse command and script interpreters to execute commands.",
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
                "x_mitre_platforms": ["Windows", "Linux", "macOS"],
                "x_mitre_detection": "Monitor for process execution with arguments.",
                "x_mitre_is_subtechnique": False,
            },
            # Sub-technique
            {
                "type": "attack-pattern",
                "id": "attack-pattern--child-1",
                "name": "PowerShell",
                "description": "Adversaries may abuse PowerShell commands and scripts.",
                "external_references": [
                    {
                        "source_name": "mitre-attack",
                        "external_id": "T1059.001",
                        "url": "https://attack.mitre.org/techniques/T1059/001",
                    }
                ],
                "kill_chain_phases": [
                    {"kill_chain_name": "mitre-attack", "phase_name": "execution"}
                ],
                "x_mitre_platforms": ["Windows"],
                "x_mitre_detection": "Monitor for loading of PowerShell modules.",
                "x_mitre_is_subtechnique": True,
                "x_mitre_parent_technique_ref": "attack-pattern--parent-1",
            },
            # Another technique for variety
            {
                "type": "attack-pattern",
                "id": "attack-pattern--2",
                "name": "OS Credential Dumping",
                "description": "Adversaries may attempt to dump credentials.",
                "external_references": [
                    {
                        "source_name": "mitre-attack",
                        "external_id": "T1003",
                        "url": "https://attack.mitre.org/techniques/T1003",
                    }
                ],
                "kill_chain_phases": [
                    {"kill_chain_name": "mitre-attack", "phase_name": "credential-access"}
                ],
                "x_mitre_platforms": ["Windows", "Linux"],
                "x_mitre_detection": "Monitor for credential access patterns.",
                "x_mitre_is_subtechnique": False,
            },
            # Mitigation
            {
                "type": "course-of-action",
                "id": "course-of-action--1",
                "name": "Privileged Account Management",
                "description": "Manage the creation, modification, use of privileged accounts.",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "M1026"}
                ],
            },
            # Another mitigation
            {
                "type": "course-of-action",
                "id": "course-of-action--2",
                "name": "Execution Prevention",
                "description": "Block execution of code through policies.",
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "M1038"}
                ],
            },
            # Relationship: mitigation mitigates technique
            {
                "type": "relationship",
                "id": "relationship--1",
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--1",
                "target_ref": "attack-pattern--2",
            },
            {
                "type": "relationship",
                "id": "relationship--2",
                "relationship_type": "mitigates",
                "source_ref": "course-of-action--2",
                "target_ref": "attack-pattern--parent-1",
            },
            # Revoked technique (should be filtered out)
            {
                "type": "attack-pattern",
                "id": "attack-pattern--revoked",
                "name": "Revoked Technique",
                "description": "This should not appear.",
                "revoked": True,
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T9999"}
                ],
            },
        ],
    }


@pytest.fixture
def mock_stix_bundle() -> Dict[str, Any]:
    """Provide mock STIX bundle for tests."""
    return _create_mock_stix_bundle()


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Provide temporary store path for tests."""
    return tmp_path / "test_lancedb"


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Provide temporary cache directory for tests."""
    return tmp_path / "mitre_cache"


@pytest.mark.integration
class TestMitreAttackIngest:
    """Integration tests for MITRE ATT&CK ingestion (AC: 8)."""

    @respx.mock
    async def test_ingest_returns_correct_source(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that ingest returns stats with source='mitre_attack' (AC: 8)."""
        # Mock the HTTP request
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        # Create store and embeddings
        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        # Patch cache directory
        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            stats = await ingest(store=store, embeddings=embeddings, incremental=False)

            assert stats.source == SOURCE_NAME
            assert stats.source == "mitre_attack"
        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_ingest_stores_chunks_with_technique_ids(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that ingested chunks have valid technique_ids (AC: 8)."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            stats = await ingest(store=store, embeddings=embeddings, incremental=False)

            # Verify chunks were created
            assert stats.chunk_count > 0

            # Query the store to check chunks
            store_stats = await store.get_stats()
            assert store_stats.total_vectors > 0
            assert SOURCE_NAME in store_stats.sources

            # Search for a technique to verify technique_ids
            test_embedding = embeddings.encode("PowerShell execution")
            results = await store.search(test_embedding, top_k=10, filter_source=SOURCE_NAME)

            # At least one result should have a valid technique ID
            found_valid_technique_id = False
            for result in results:
                for tid in result.technique_ids:
                    if TECHNIQUE_ID_PATTERN.match(tid):
                        found_valid_technique_id = True
                        break

            assert found_valid_technique_id, "No valid ATT&CK technique IDs found in search results"

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_ingest_includes_detection_mitigation_content(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that ingested documents include detection/mitigation content (AC: 8)."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            await ingest(store=store, embeddings=embeddings, incremental=False)

            # Search for detection content
            detection_embedding = embeddings.encode("Monitor for process execution")
            detection_results = await store.search(
                detection_embedding, top_k=5, filter_source=SOURCE_NAME
            )

            # Should find content with detection info
            found_detection = any("Monitor" in r.text or "detection" in r.text.lower() 
                                  for r in detection_results)
            assert found_detection, "Detection content not found in ingested documents"

            # Search for mitigation content
            mitigation_embedding = embeddings.encode("Privileged Account Management")
            mitigation_results = await store.search(
                mitigation_embedding, top_k=5, filter_source=SOURCE_NAME
            )

            # Should find content with mitigation info
            found_mitigation = any("Privileged" in r.text or "mitigation" in r.text.lower()
                                   for r in mitigation_results)
            assert found_mitigation, "Mitigation content not found in ingested documents"

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_ingest_no_args_works(
        self, mock_stix_bundle: Dict[str, Any], temp_cache_dir: Path, tmp_path: Path
    ) -> None:
        """Test that ingest() with no args creates default store/embeddings (AC: 2)."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        # Patch both cache and default store path to use temp directories
        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        # We need to patch RAGStore's default path for this test
        import cyberred.rag.store as store_module
        original_store_init = store_module.RAGStore.__init__

        def patched_init(self: Any, store_path: str | None = None, embedding_dim: int = 768) -> None:
            if store_path is None:
                store_path = str(tmp_path / "default_lancedb")
            original_store_init(self, store_path, embedding_dim)

        store_module.RAGStore.__init__ = patched_init  # type: ignore[method-assign]

        try:
            # Call with no args - should work per AC: 2
            stats = await ingest()

            assert stats.source == "mitre_attack"
            assert stats.document_count > 0

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache
            store_module.RAGStore.__init__ = original_store_init  # type: ignore[method-assign]

    @respx.mock
    async def test_ingest_handles_subtechnique_parent_linkage(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that sub-techniques are linked to parent techniques (AC: 6)."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            await ingest(store=store, embeddings=embeddings, incremental=False)

            # Search for the sub-technique
            powershell_embedding = embeddings.encode("PowerShell T1059.001")
            results = await store.search(powershell_embedding, top_k=5, filter_source=SOURCE_NAME)

            # Find the PowerShell sub-technique
            powershell_result = None
            for r in results:
                if "T1059.001" in r.technique_ids:
                    powershell_result = r
                    break

            assert powershell_result is not None, "PowerShell sub-technique not found"
            # The text should mention parent technique
            assert "T1059" in powershell_result.text or "Parent" in powershell_result.text

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_ingest_filters_revoked_techniques(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that revoked techniques are not ingested."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            await ingest(store=store, embeddings=embeddings, incremental=False)

            # Search for the revoked technique
            revoked_embedding = embeddings.encode("T9999 Revoked Technique")
            results = await store.search(revoked_embedding, top_k=10, filter_source=SOURCE_NAME)

            # Should NOT find T9999
            for r in results:
                assert "T9999" not in r.technique_ids, "Revoked technique was incorrectly ingested"

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_incremental_ingest_skips_unchanged(
        self, mock_stix_bundle: Dict[str, Any], temp_store_path: Path, temp_cache_dir: Path
    ) -> None:
        """Test that incremental ingest skips unchanged documents."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        store = RAGStore(store_path=str(temp_store_path))
        embeddings = RAGEmbeddings()

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            # First ingest - use incremental=False to ensure fresh state
            stats1 = await ingest(store=store, embeddings=embeddings, incremental=False)
            assert stats1.chunk_count > 0
            first_chunk_count = stats1.chunk_count

            # Second ingest with same data using incremental=True should skip
            stats2 = await ingest(store=store, embeddings=embeddings, incremental=True)
            # When incremental and unchanged, chunk_count should be 0 (no new chunks)
            assert stats2.chunk_count == 0
            # Document count still reflects total docs processed (even if skipped)
            assert stats2.document_count == stats1.document_count

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache


@pytest.mark.integration
class TestMitreAttackDownload:
    """Integration tests for STIX bundle download and caching."""

    @respx.mock
    async def test_download_caches_bundle(
        self, mock_stix_bundle: Dict[str, Any], temp_cache_dir: Path
    ) -> None:
        """Test that bundle is cached after download."""
        respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            from cyberred.rag.sources.mitre_attack import _download_bundle

            # First download
            path = await _download_bundle()
            assert path.exists()
            assert path.name == "enterprise-attack.json"

            # Hash file should exist
            hash_path = temp_cache_dir / "enterprise-attack.json.sha256"
            assert hash_path.exists()

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache

    @respx.mock
    async def test_download_uses_cache_on_hit(
        self, mock_stix_bundle: Dict[str, Any], temp_cache_dir: Path
    ) -> None:
        """Test that cached bundle is reused without re-download."""
        route = respx.get(ENTERPRISE_ATTACK_URL).mock(
            return_value=Response(200, json=mock_stix_bundle)
        )

        original_cache = mitre_attack.DEFAULT_CACHE_DIR
        mitre_attack.DEFAULT_CACHE_DIR = temp_cache_dir

        try:
            from cyberred.rag.sources.mitre_attack import _download_bundle

            # First download
            await _download_bundle()
            assert route.call_count == 1

            # Second call should use cache
            await _download_bundle()
            assert route.call_count == 1  # Still 1 - no new request

        finally:
            mitre_attack.DEFAULT_CACHE_DIR = original_cache
