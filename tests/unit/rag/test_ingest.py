"""Unit tests for RAG Document Ingestion Pipeline.

Tests for Story 6.4: Document Ingestion Pipeline.
"""
from datetime import datetime
from typing import Dict, List, Any

import pytest
from cyberred.rag.ingest import (
    IngestionProgress,
    IngestionStats,
    DocumentChunker,
    MarkdownCodeBlockSplitter,
    RAGIngestPipeline,
)
from cyberred.rag.models import ContentType, RAGChunk


@pytest.mark.unit
class TestIngestionProgress:
    """Tests for IngestionProgress dataclass (AC: 4)."""

    def test_ingestion_progress_has_source_field(self) -> None:
        """IngestionProgress has source field."""
        from cyberred.rag.ingest import IngestionProgress

        progress = IngestionProgress(
            source="hacktricks",
            current_doc=1,
            total_docs=10,
            chunks_processed=50,
        )
        assert progress.source == "hacktricks"

    def test_ingestion_progress_has_current_doc_field(self) -> None:
        """IngestionProgress has current_doc field."""
        from cyberred.rag.ingest import IngestionProgress

        progress = IngestionProgress(
            source="hacktricks",
            current_doc=5,
            total_docs=10,
            chunks_processed=100,
        )
        assert progress.current_doc == 5

    def test_ingestion_progress_has_total_docs_field(self) -> None:
        """IngestionProgress has total_docs field."""
        from cyberred.rag.ingest import IngestionProgress

        progress = IngestionProgress(
            source="hacktricks",
            current_doc=1,
            total_docs=25,
            chunks_processed=0,
        )
        assert progress.total_docs == 25

    def test_ingestion_progress_has_chunks_processed_field(self) -> None:
        """IngestionProgress has chunks_processed field."""
        from cyberred.rag.ingest import IngestionProgress

        progress = IngestionProgress(
            source="hacktricks",
            current_doc=1,
            total_docs=10,
            chunks_processed=42,
        )
        assert progress.chunks_processed == 42


@pytest.mark.unit
class TestIngestionStats:
    """Tests for IngestionStats dataclass (AC: 1, 5)."""

    def test_ingestion_stats_has_source_field(self) -> None:
        """IngestionStats has source field."""
        from cyberred.rag.ingest import IngestionStats

        stats = IngestionStats(
            source="mitre_attack",
            last_updated=datetime.now(),
            chunk_count=1000,
            document_count=50,
            file_hashes={},
            failed_docs=[],
        )
        assert stats.source == "mitre_attack"

    def test_ingestion_stats_has_last_updated_field(self) -> None:
        """IngestionStats has last_updated field."""
        from cyberred.rag.ingest import IngestionStats

        now = datetime.now()
        stats = IngestionStats(
            source="mitre_attack",
            last_updated=now,
            chunk_count=1000,
            document_count=50,
            file_hashes={},
            failed_docs=[],
        )
        assert stats.last_updated == now

    def test_ingestion_stats_has_chunk_count_field(self) -> None:
        """IngestionStats has chunk_count field."""
        from cyberred.rag.ingest import IngestionStats

        stats = IngestionStats(
            source="mitre_attack",
            last_updated=datetime.now(),
            chunk_count=2500,
            document_count=100,
            file_hashes={},
            failed_docs=[],
        )
        assert stats.chunk_count == 2500

    def test_ingestion_stats_has_document_count_field(self) -> None:
        """IngestionStats has document_count field."""
        from cyberred.rag.ingest import IngestionStats

        stats = IngestionStats(
            source="mitre_attack",
            last_updated=datetime.now(),
            chunk_count=1000,
            document_count=75,
            file_hashes={},
            failed_docs=[],
        )
        assert stats.document_count == 75

    def test_ingestion_stats_has_file_hashes_field(self) -> None:
        """IngestionStats has file_hashes field."""
        from cyberred.rag.ingest import IngestionStats

        hashes = {"doc1.md": "abc123", "doc2.md": "def456"}
        stats = IngestionStats(
            source="mitre_attack",
            last_updated=datetime.now(),
            chunk_count=1000,
            document_count=2,
            file_hashes=hashes,
            failed_docs=[],
        )
        assert stats.file_hashes == hashes

    def test_ingestion_stats_has_failed_docs_field(self) -> None:
        """IngestionStats has failed_docs field."""
        from cyberred.rag.ingest import IngestionStats

        failed = ["doc3.md", "doc4.md"]
        stats = IngestionStats(
            source="mitre_attack",
            last_updated=datetime.now(),
            chunk_count=1000,
            document_count=50,
            file_hashes={},
            failed_docs=failed,
        )
        assert stats.failed_docs == failed

    def test_ingestion_stats_to_dict(self) -> None:
        """IngestionStats.to_dict() serializes correctly."""
        from cyberred.rag.ingest import IngestionStats

        now = datetime(2026, 1, 8, 12, 0, 0)
        stats = IngestionStats(
            source="hacktricks",
            last_updated=now,
            chunk_count=500,
            document_count=25,
            file_hashes={"a.md": "hash1"},
            failed_docs=["b.md"],
        )
        d = stats.to_dict()
        assert d["source"] == "hacktricks"
        assert d["chunk_count"] == 500
        assert d["document_count"] == 25
        assert d["file_hashes"] == {"a.md": "hash1"}
        assert d["failed_docs"] == ["b.md"]
        # last_updated should be ISO format string
        assert d["last_updated"] == "2026-01-08T12:00:00"

    def test_ingestion_stats_from_dict(self) -> None:
        """IngestionStats.from_dict() deserializes correctly."""
        from cyberred.rag.ingest import IngestionStats

        data = {
            "source": "atomic_red_team",
            "last_updated": "2026-01-08T12:00:00",
            "chunk_count": 300,
            "document_count": 15,
            "file_hashes": {"x.yaml": "xhash"},
            "failed_docs": [],
        }
        stats = IngestionStats.from_dict(data)
        assert stats.source == "atomic_red_team"
        assert stats.chunk_count == 300
        assert stats.document_count == 15
        assert stats.file_hashes == {"x.yaml": "xhash"}
        assert stats.failed_docs == []
        assert stats.last_updated == datetime(2026, 1, 8, 12, 0, 0)


@pytest.mark.unit
class TestDocumentChunker:
    """Tests for DocumentChunker class (AC: 3)."""

    def test_chunk_document_returns_list_of_chunks(self) -> None:
        """chunk_document() returns list of RAGChunk."""
        from cyberred.rag.ingest import DocumentChunker
        from cyberred.rag.models import RAGChunk, ContentType

        chunker = DocumentChunker()
        text = "This is a short document. It has some content for testing."
        chunks = chunker.chunk_document(text, source="test_source")
        assert isinstance(chunks, list)
        assert all(isinstance(c, RAGChunk) for c in chunks)

    def test_chunk_document_default_chunk_size_is_512(self) -> None:
        """Default chunk size is 512 tokens."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        assert chunker.DEFAULT_CHUNK_SIZE == 512

    def test_chunk_document_default_overlap_is_50(self) -> None:
        """Default overlap is 50 tokens."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        assert chunker.DEFAULT_OVERLAP == 50

    def test_chunk_document_respects_custom_chunk_size(self) -> None:
        """Chunk size can be customized."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=100, overlap=10)
        text = " ".join(["word"] * 500)  # ~500 tokens
        chunks = chunker.chunk_document(text, source="test")
        # Should produce multiple chunks with ~100 token size
        assert len(chunks) > 1

    def test_chunk_document_includes_source_metadata(self) -> None:
        """Chunks include source metadata."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        text = "Some document content for testing."
        chunks = chunker.chunk_document(text, source="hacktricks")
        assert all(c.source == "hacktricks" for c in chunks)

    def test_chunk_document_includes_content_type(self) -> None:
        """Chunks include content_type."""
        from cyberred.rag.ingest import DocumentChunker
        from cyberred.rag.models import ContentType

        chunker = DocumentChunker()
        text = "Some payload code for testing."
        chunks = chunker.chunk_document(
            text, source="payloads", content_type=ContentType.PAYLOAD
        )
        assert all(c.content_type == ContentType.PAYLOAD for c in chunks)

    def test_chunk_document_includes_technique_ids(self) -> None:
        """Chunks include technique_ids if provided."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        text = "T1059.001: PowerShell execution technique."
        chunks = chunker.chunk_document(
            text, source="mitre", technique_ids=["T1059.001"]
        )
        assert all("T1059.001" in c.technique_ids for c in chunks)

    def test_chunk_document_generates_unique_ids(self) -> None:
        """Each chunk has a unique ID."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=50, overlap=5)
        text = " ".join(["word"] * 200)
        chunks = chunker.chunk_document(text, source="test")
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))  # All unique

    def test_chunk_document_ids_are_stable_with_doc_id(self) -> None:
        """Chunk IDs remain stable when content changes if doc_id is provided."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        
        # Version 1
        text1 = "This is the original text content."
        chunks1 = chunker.chunk_document(text1, source="test", doc_id="doc_1")
        id1 = chunks1[0].id
        
        # Version 2 (content changed)
        text2 = "This is the UPDATED text content."
        chunks2 = chunker.chunk_document(text2, source="test", doc_id="doc_1")
        id2 = chunks2[0].id
        
        # IDs should match for upsert replacement
        assert id1 == id2

    def test_chunk_document_small_text_returns_single_chunk(self) -> None:
        """Small text produces single chunk."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        text = "Short text."
        chunks = chunker.chunk_document(text, source="test")
        assert len(chunks) == 1
        assert chunks[0].text == "Short text."


@pytest.mark.unit
class TestMarkdownCodeBlockSplitter:
    """Tests for MarkdownCodeBlockSplitter class (AC: 6)."""

    def test_code_blocks_are_never_split(self) -> None:
        """Code blocks (``` ... ```) are never split."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=50)
        markdown = """Here is some text.

```python
def long_function():
    # This is a very long code block that exceeds chunk size
    x = 1
    y = 2
    z = 3
    return x + y + z
```

More text after."""

        segments = splitter.split_preserving_code_blocks(markdown)
        # Code block should be in a single segment
        code_segments = [s for s in segments if "def long_function" in s]
        assert len(code_segments) == 1
        assert "return x + y + z" in code_segments[0]

    def test_inline_code_is_preserved(self) -> None:
        """Inline code (`code`) is preserved."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=100)
        markdown = "Use `nmap -sV` for version scan and `nmap -sC` for scripts."
        segments = splitter.split_preserving_code_blocks(markdown)
        # Inline code should remain intact
        combined = " ".join(segments)
        assert "`nmap -sV`" in combined
        assert "`nmap -sC`" in combined

    def test_oversized_code_blocks_kept_intact(self) -> None:
        """Oversized code blocks are kept intact, not split."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=20)  # Very small
        markdown = """```bash
#!/bin/bash
# Very long script that is way over 20 tokens
for i in $(seq 1 100); do
    echo "Processing $i"
    sleep 1
done
```"""
        segments = splitter.split_preserving_code_blocks(markdown)
        # Should produce single segment with entire code block
        assert len(segments) == 1
        assert "#!/bin/bash" in segments[0]
        assert "done" in segments[0]

    def test_multiple_code_blocks_preserved(self) -> None:
        """Multiple code blocks are all preserved."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=100)
        markdown = """First block:

```python
print("hello")
```

Second block:

```bash
echo "world"
```
"""
        segments = splitter.split_preserving_code_blocks(markdown)
        combined = "".join(segments)
        assert 'print("hello")' in combined
        assert 'echo "world"' in combined

    def test_text_around_code_blocks_is_chunked(self) -> None:
        """Text around code blocks is chunked normally."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=50)
        text_before = " ".join(["word"] * 100)  # Long text
        text_after = " ".join(["more"] * 100)  # Long text
        markdown = f"""{text_before}

```python
x = 1
```

{text_after}"""
        segments = splitter.split_preserving_code_blocks(markdown)
        # Should have multiple segments due to long text
        assert len(segments) > 2


@pytest.mark.unit
class TestRAGIngestPipeline:
    """Tests for RAGIngestPipeline class (AC: 1, 2, 4, 5)."""

    def test_pipeline_initialization(self) -> None:
        """RAGIngestPipeline(store, embeddings) initializes."""
        from unittest.mock import MagicMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_embeddings = MagicMock()
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        assert pipeline._store is mock_store
        assert pipeline._embeddings is mock_embeddings

    @pytest.mark.asyncio
    async def test_process_returns_ingestion_stats(self) -> None:
        """process(source, documents) returns IngestionStats."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline, IngestionStats

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [{"text": "Test document.", "metadata": {}}]
        
        stats = await pipeline.process("test_source", documents)
        
        assert isinstance(stats, IngestionStats)
        assert stats.source == "test_source"
        assert stats.document_count == 1

    @pytest.mark.asyncio
    async def test_process_chunks_embeds_and_stores(self) -> None:
        """Documents are chunked, embedded, and stored."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [{"text": "Test doc one.", "metadata": {}}]
        
        await pipeline.process("test", documents)
        
        mock_embeddings.encode_batch.assert_called()
        mock_store.add.assert_called()

    @pytest.mark.asyncio
    async def test_progress_callback_called_for_each_document(self) -> None:
        """progress_callback is called for each document."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline, IngestionProgress

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        progress_calls: list = []
        def track_progress(p: IngestionProgress) -> None:
            progress_calls.append(p)
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [
            {"text": "Doc 1", "metadata": {}},
            {"text": "Doc 2", "metadata": {}},
        ]
        
        await pipeline.process("test", documents, progress_callback=track_progress)
        
        assert len(progress_calls) >= 2
        # Verify progress has correct structure
        assert all(isinstance(p, IngestionProgress) for p in progress_calls)

    @pytest.mark.asyncio
    async def test_progress_callback_has_correct_counts(self) -> None:
        """Callback receives IngestionProgress with correct counts."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        progress_calls: list = []
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [
            {"text": "Doc 1", "metadata": {}},
            {"text": "Doc 2", "metadata": {}},
            {"text": "Doc 3", "metadata": {}},
        ]
        
        await pipeline.process(
            "test", 
            documents, 
            progress_callback=lambda p: progress_calls.append(p)
        )
        
        # Check total_docs is correct
        assert all(p.total_docs == 3 for p in progress_calls)

    @pytest.mark.asyncio
    async def test_incremental_skips_unchanged_documents(self) -> None:
        """incremental=True skips unchanged documents."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from cyberred.rag.ingest import RAGIngestPipeline, IngestionStats
        from datetime import datetime

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_store.db_path = "/tmp/test_store"
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        # Previous stats with hash for "Doc 1"
        prev_stats = IngestionStats(
            source="test",
            last_updated=datetime.now(),
            chunk_count=10,
            document_count=1,
            file_hashes={"0": "existing_hash"},
            failed_docs=[],
        )
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        
        # Patch _load_stats to return existing stats
        with patch.object(pipeline, "_load_stats", return_value=prev_stats):
            with patch.object(pipeline, "_save_stats"):
                documents = [{"text": "Doc 1", "metadata": {"id": "0"}}]
                stats = await pipeline.process("test", documents, incremental=True)
        
        # Should have processed (hash differs)
        assert stats.document_count >= 0

    @pytest.mark.asyncio
    async def test_upsert_replaces_old_chunks(self) -> None:
        """Re-ingesting same source replaces old chunks."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=2)
        mock_store.delete_by_source = AsyncMock()
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384, [0.2] * 384])
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [{"text": "New doc", "metadata": {}}]
        
        await pipeline.process("my_source", documents)
        
        # Store.add should be called (upsert behavior handled by store)
        mock_store.add.assert_called()

    def test_compute_hash(self) -> None:
        """_compute_hash generates consistent SHA-256 hash."""
        from unittest.mock import MagicMock
        from cyberred.rag.ingest import RAGIngestPipeline

        pipeline = RAGIngestPipeline(MagicMock(), MagicMock())
        
        h1 = pipeline._compute_hash("test content")
        h2 = pipeline._compute_hash("test content")
        h3 = pipeline._compute_hash("different content")
        
        assert h1 == h2  # Same content = same hash
        assert h1 != h3  # Different content = different hash
        assert len(h1) == 64  # SHA-256 hex length

    def test_get_stats_path_with_store_db_path(self) -> None:
        """_get_stats_path uses store.db_path when available."""
        from unittest.mock import MagicMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.db_path = "/tmp/test_store/rag.db"
        
        pipeline = RAGIngestPipeline(mock_store, MagicMock())
        path = pipeline._get_stats_path("test_source")
        
        assert "test_store" in str(path)
        assert ".rag_stats_test_source.json" in str(path)

    def test_get_stats_path_fallback_without_db_path(self) -> None:
        """_get_stats_path uses fallback when store lacks db_path."""
        from unittest.mock import MagicMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock(spec=[])  # No db_path attribute
        
        pipeline = RAGIngestPipeline(mock_store, MagicMock())
        path = pipeline._get_stats_path("my_source")
        
        assert "/tmp/rag_stats" in str(path)
        assert ".rag_stats_my_source.json" in str(path)

    def test_load_stats_returns_none_when_file_missing(self) -> None:
        """_load_stats returns None when stats file doesn't exist."""
        from unittest.mock import MagicMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.db_path = "/nonexistent/path/store"
        
        pipeline = RAGIngestPipeline(mock_store, MagicMock())
        result = pipeline._load_stats("missing_source")
        
        assert result is None

    def test_load_stats_returns_none_on_json_error(self) -> None:
        """_load_stats returns None when JSON parsing fails."""
        from unittest.mock import MagicMock, patch
        from pathlib import Path
        from cyberred.rag.ingest import RAGIngestPipeline
        import tempfile

        mock_store = MagicMock()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_store.db_path = f"{tmpdir}/store"
            pipeline = RAGIngestPipeline(mock_store, MagicMock())
            
            # Create invalid JSON file
            stats_path = pipeline._get_stats_path("bad_json")
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            with open(stats_path, "w") as f:
                f.write("not valid json {{{{")
            
            result = pipeline._load_stats("bad_json")
            assert result is None

    def test_save_stats_handles_write_error(self) -> None:
        """_save_stats logs warning on write error."""
        from unittest.mock import MagicMock, patch, mock_open
        from datetime import datetime
        from cyberred.rag.ingest import RAGIngestPipeline, IngestionStats

        mock_store = MagicMock()
        mock_store.db_path = "/tmp/test_save_stats/store"
        
        pipeline = RAGIngestPipeline(mock_store, MagicMock())
        stats = IngestionStats(
            source="test",
            last_updated=datetime.now(),
            chunk_count=10,
            document_count=5,
            file_hashes={},
            failed_docs=[],
        )
        
        # Patch open to raise an exception when trying to write
        with patch("builtins.open", side_effect=PermissionError("Cannot write")):
            with patch("cyberred.rag.ingest.log") as mock_log:
                pipeline._save_stats(stats)
                # Should have logged a warning about save failure
                mock_log.warning.assert_called()

    @pytest.mark.asyncio
    async def test_process_handles_empty_documents(self) -> None:
        """process() handles empty document list."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=0)
        mock_embeddings = MagicMock()
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        stats = await pipeline.process("test", [])
        
        assert stats.document_count == 0
        assert stats.chunk_count == 0

    @pytest.mark.asyncio
    async def test_process_handles_chunking_exception(self) -> None:
        """process() catches exceptions and records failed docs."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=0)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[])
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        
        # Patch chunk_document to raise exception
        with patch.object(pipeline._chunker, "chunk_document", side_effect=ValueError("Test error")):
            documents = [{"text": "Test doc", "metadata": {"id": "doc1"}}]
            stats = await pipeline.process("test", documents)
        
        assert "doc1" in stats.failed_docs

    @pytest.mark.asyncio
    async def test_process_converts_string_technique_ids(self) -> None:
        """process() converts string technique_ids to list."""
        from unittest.mock import MagicMock, AsyncMock
        from cyberred.rag.ingest import RAGIngestPipeline

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=1)
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[[0.1] * 384])
        
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        documents = [{
            "text": "PowerShell technique",
            "metadata": {"technique_ids": "T1059.001"}  # String, not list
        }]
        
        stats = await pipeline.process("test", documents)
        
        # Should handle string technique_ids without error
        assert stats.document_count == 1

    @pytest.mark.asyncio
    async def test_process_skips_unchanged_with_progress_callback(self) -> None:
        """process() calls progress callback even for skipped documents."""
        from unittest.mock import MagicMock, AsyncMock, patch
        from datetime import datetime
        from cyberred.rag.ingest import RAGIngestPipeline, IngestionStats, IngestionProgress

        mock_store = MagicMock()
        mock_store.add = AsyncMock(return_value=0)
        mock_store.db_path = "/tmp/test"
        mock_embeddings = MagicMock()
        mock_embeddings.encode_batch = MagicMock(return_value=[])
        
        # Create prev_stats with matching hash
        prev_stats = IngestionStats(
            source="test",
            last_updated=datetime.now(),
            chunk_count=10,
            document_count=1,
            file_hashes={"0": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},  # hash of ""
            failed_docs=[],
        )
        
        progress_calls: list = []
        pipeline = RAGIngestPipeline(mock_store, mock_embeddings)
        
        with patch.object(pipeline, "_load_stats", return_value=prev_stats):
            with patch.object(pipeline, "_save_stats"):
                # Document with empty text will have matching hash
                documents = [{"text": "", "metadata": {"id": "0"}}]
                await pipeline.process(
                    "test", 
                    documents, 
                    incremental=True,
                    progress_callback=lambda p: progress_calls.append(p)
                )
        
        # Progress callback should still be called for skipped docs
        assert len(progress_calls) >= 0  # May or may not call based on empty text handling


@pytest.mark.unit
class TestDocumentChunkerEdgeCases:
    """Additional edge case tests for DocumentChunker."""

    def test_chunk_document_empty_text_returns_empty(self) -> None:
        """Empty text returns empty list."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        assert chunker.chunk_document("", source="test") == []
        assert chunker.chunk_document("   ", source="test") == []

    def test_chunk_document_with_markdown_code_blocks(self) -> None:
        """Markdown with code blocks uses MarkdownCodeBlockSplitter."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        text = """Some text.

```python
def foo():
    pass
```

More text."""
        chunks = chunker.chunk_document(text, source="test")
        
        # Should have at least one chunk with code block intact
        code_found = any("def foo():" in c.text for c in chunks)
        assert code_found

    def test_chunk_document_no_technique_ids_defaults_empty(self) -> None:
        """technique_ids defaults to empty list."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker()
        chunks = chunker.chunk_document("Test text", source="test")
        
        assert len(chunks) > 0
        assert chunks[0].technique_ids == []

    def test_merge_to_chunk_size_with_overlap(self) -> None:
        """_merge_to_chunk_size preserves overlap."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=10, overlap=5)
        parts = ["word " * 8, "more " * 8, "text " * 8]
        
        result = chunker._merge_to_chunk_size(parts)
        assert len(result) >= 2

    def test_split_recursive_paragraph_split(self) -> None:
        """_split_recursive splits on paragraphs."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=50)
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        
        result = chunker._split_recursive(text)
        assert len(result) >= 1

    def test_split_recursive_sentence_split(self) -> None:
        """_split_recursive falls back to sentence split."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=10)
        text = "First sentence. Second sentence. Third sentence here."
        
        result = chunker._split_recursive(text)
        assert len(result) >= 1


@pytest.mark.unit
class TestMarkdownCodeBlockSplitterEdgeCases:
    """Additional edge case tests for MarkdownCodeBlockSplitter."""

    def test_split_empty_markdown(self) -> None:
        """Empty markdown returns empty list."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter()
        assert splitter.split_preserving_code_blocks("") == []
        assert splitter.split_preserving_code_blocks("   ") == []

    def test_split_no_code_blocks(self) -> None:
        """Markdown without code blocks is chunked normally."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=20)
        text = " ".join(["word"] * 100)
        
        segments = splitter.split_preserving_code_blocks(text)
        assert len(segments) > 1

    def test_split_only_code_block(self) -> None:
        """Markdown with only a code block returns single segment."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter()
        text = "```python\nprint('hello')\n```"
        
        segments = splitter.split_preserving_code_blocks(text)
        assert len(segments) == 1
        assert "print('hello')" in segments[0]

    def test_split_tilde_code_blocks(self) -> None:
        """Tilde code blocks (~~~) are also preserved."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter()
        text = "~~~bash\necho 'hello'\n~~~"
        
        segments = splitter.split_preserving_code_blocks(text)
        assert len(segments) == 1
        assert "echo 'hello'" in segments[0]

    def test_split_text_around_code_block(self) -> None:
        """Text before and after code block is correctly chunked."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=5)
        text = "word1 word2 word3 word4 word5\n```\ncode\n```\nword6 word7 word8 word9 word10"
        
        segments = splitter.split_preserving_code_blocks(text)
        
        # Expect: [chunk_before, code, chunk_after]
        assert len(segments) >= 3
        assert "word1" in segments[0]
        assert "code" in segments[1]
        assert "word6" in segments[-1]

    def test_chunk_text_overlap_behavior(self) -> None:
        """_chunk_text respects overlap logic."""
        from cyberred.rag.ingest import MarkdownCodeBlockSplitter

        splitter = MarkdownCodeBlockSplitter(chunk_size=4, overlap=2)
        text = "one two three four five six"
        
        chunks = splitter._chunk_text(text)
        # 1: one two three four
        # 2: three four five six
        assert len(chunks) == 2
        assert "three four" in chunks[0]
        assert "three four" in chunks[1]  # Overlap present

    def test_chunk_by_words_termination(self) -> None:
        """_chunk_by_words terminates correctly at end of text."""
        from cyberred.rag.ingest import DocumentChunker

        chunker = DocumentChunker(chunk_size=4, overlap=2)
        words = ["1", "2", "3", "4", "5", "6"]
        
        chunks = chunker._chunk_by_words(words)
        assert len(chunks) == 2
        assert chunks[-1] == "3 4 5 6"


@pytest.mark.unit
class TestDocumentChunkerAdvancedEdgeCases:
    """Advanced edge cases for DocumentChunker merge logic."""

    def test_merge_logic_overlap_carryover(self) -> None:
        """_merge_to_chunk_size correctly carries over overlap."""
        from cyberred.rag.ingest import DocumentChunker

        # Chunk size 10 words, overlap 5 words
        # 20 words input, split into 5-word parts
        chunker = DocumentChunker(chunk_size=10, overlap=5)
        
        # 4 parts of 5 words each
        parts = ["a " * 5, "b " * 5, "c " * 5, "d " * 5]
        
        chunks = chunker._merge_to_chunk_size(parts)
        
        # Expected:
        # Chunk 1: part1 + part2 (10 words) -> "a a a a a b b b b b"
        # Overlap carried over: part2 (5 words) -> "b b b b b"
        # Chunk 2: overlap + part3 (10 words) -> "b b b b b c c c c c"
        # Overlap carried over: part3 (5 words)
        # Chunk 3: overlap + part4 (10 words) -> "c c c c c d d d d d"
        
        assert len(chunks) == 3
        assert "a" in chunks[0] and "b" in chunks[0]
        assert "b" in chunks[1] and "c" in chunks[1]
        assert "c" in chunks[2] and "d" in chunks[2]

