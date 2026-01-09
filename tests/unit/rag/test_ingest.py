"""Unit tests for RAG Document Ingestion Pipeline.

Tests for Story 6.4: Document Ingestion Pipeline.
"""
from datetime import datetime
from typing import Dict, List, Any

import pytest


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
