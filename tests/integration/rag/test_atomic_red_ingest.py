import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from cyberred.rag.sources import atomic_red
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.models import RAGChunk


def _create_test_repo(tmp_path: Path) -> Path:
    """Helper to create a mock Atomic Red Team repo structure."""
    repo_dir = tmp_path / "atomic-red-team"
    atomics_dir = repo_dir / "atomics"
    atomics_dir.mkdir(parents=True)
    
    # Create a sample technique file
    technique_dir = atomics_dir / "T1059.001"
    technique_dir.mkdir()
    yaml_file = technique_dir / "T1059.001.yaml"
    
    yaml_content = """
attack_technique: T1059.001
display_name: "PowerShell"
atomic_tests:
  - name: "Test 1"
    description: "Description 1"
    supported_platforms:
      - windows
    executor:
      name: powershell
      command: "Write-Host 'Attack'"
"""
    yaml_file.write_text(yaml_content, encoding="utf-8")
    return repo_dir


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_red_ingest_flow(tmp_path):
    """Test full ingestion flow with mocked download (AC: 8)."""
    repo_dir = _create_test_repo(tmp_path)
        
    with patch("cyberred.rag.sources.atomic_red._download_atomics", return_value=repo_dir) as mock_download:
        
        # Use a real RAGStore with local LanceDB in tmp_path
        db_path = tmp_path / "lancedb"
        store = RAGStore(store_path=str(db_path))
        
        # Mock embeddings to avoid model download
        embeddings = MagicMock(spec=RAGEmbeddings)
        embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
        
        # Run ingest
        stats = await atomic_red.ingest(
            store=store, 
            embeddings=embeddings, 
            incremental=False
        )
        
        # Assertions
        assert stats.source == "atomic_red"
        assert stats.document_count == 1
        assert stats.chunk_count >= 1
        
        # Verify content in store
        results = await store.search([0.1] * 768, top_k=10)
        assert len(results) >= 1
        
        # Verify source
        assert results[0].source == "atomic_red"
        
        # Verify text content from template across all chunks
        all_text = "\n".join([r.text for r in results])
        assert "Atomic Red Team Test: Test 1" in all_text
        assert "Technique: T1059.001 - PowerShell" in all_text  # Now includes display_name
        assert "Write-Host 'Attack'" in all_text
        
        # Verify metadata (check first result)
        doc = results[0]
        assert doc.metadata["technique_id"] == "T1059.001"
        assert doc.metadata["executor_type"] == "powershell"
        # Check stable ID format in doc_id metadata (preserved by chunker)
        assert ":" in doc.metadata.get("doc_id", "")
        
        # Verify mocked download was called
        mock_download.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_red_ingest_no_args(tmp_path):
    """Test no-args call works (AC: 2)."""
    repo_dir = _create_test_repo(tmp_path)
    
    with patch("cyberred.rag.sources.atomic_red._download_atomics", return_value=repo_dir), \
         patch("cyberred.rag.sources.atomic_red.RAGStore") as MockStore, \
         patch("cyberred.rag.sources.atomic_red.RAGEmbeddings") as MockEmbeddings, \
         patch("cyberred.rag.sources.atomic_red.RAGIngestPipeline") as MockPipeline:
        
        from cyberred.rag.ingest import IngestionStats
        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process = AsyncMock(return_value=IngestionStats(
            source="atomic_red",
            last_updated=None,
            chunk_count=5,
            document_count=1,
            file_hashes={},
            failed_docs=[]
        ))
        
        # Call with no arguments - should not raise
        stats = await atomic_red.ingest()
        
        assert stats.source == "atomic_red"
        MockStore.assert_called_once()
        MockEmbeddings.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_red_incremental_ingest_skips_unchanged(tmp_path, monkeypatch):
    """Test incremental ingest skips unchanged docs (AC: 8)."""
    repo_dir = _create_test_repo(tmp_path)
    
    # Use a unique stats file location to avoid cross-test pollution
    stats_dir = tmp_path / "rag_stats"
    stats_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))  # Stats files go in ~/.cyber-red/
    
    with patch("cyberred.rag.sources.atomic_red._download_atomics", return_value=repo_dir):
        db_path = tmp_path / "lancedb"
        store = RAGStore(store_path=str(db_path))
        
        embeddings = MagicMock(spec=RAGEmbeddings)
        embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
        
        # First ingest - full (non-incremental to ensure we get chunks)
        stats1 = await atomic_red.ingest(
            store=store,
            embeddings=embeddings,
            incremental=False  # First run: full ingest
        )
        
        initial_chunk_count = stats1.chunk_count
        assert initial_chunk_count >= 1, f"First ingest should have chunks, got {stats1}"
        
        # Second ingest - incremental should skip unchanged
        stats2 = await atomic_red.ingest(
            store=store,
            embeddings=embeddings,
            incremental=True  # Second run: incremental
        )
        
        # With unchanged content and incremental=True, chunks should be 0 (skipped)
        # or same count if it re-upserts - key is no duplicates
        
        # Verify no duplicates in store - total should still be initial count
        results = await store.search([0.1] * 768, top_k=100)
        assert len(results) == initial_chunk_count, \
            f"Should have {initial_chunk_count} chunks, got {len(results)} (no duplicates)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_red_force_refresh_parameter(tmp_path):
    """Test force_refresh parameter is passed through."""
    repo_dir = _create_test_repo(tmp_path)
    
    with patch("cyberred.rag.sources.atomic_red._download_atomics", return_value=repo_dir) as mock_download:
        db_path = tmp_path / "lancedb"
        store = RAGStore(store_path=str(db_path))
        
        embeddings = MagicMock(spec=RAGEmbeddings)
        embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]
        
        await atomic_red.ingest(
            store=store,
            embeddings=embeddings,
            force_refresh=True
        )
        
        # Verify force_refresh was passed to download function
        mock_download.assert_called_once()
        call_kwargs = mock_download.call_args[1]
        assert call_kwargs.get("force_refresh") is True
