import pytest
import lancedb
from pathlib import Path
from unittest.mock import MagicMock, patch
from cyberred.rag.store import RAGStore
from cyberred.rag.models import RAGChunk, ContentType

@pytest.mark.unit
class TestRAGStore:
    """Tests for RAGStore Core."""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        return str(tmp_path / "rag_store")

    def test_initialization_creates_directory(self, temp_store_path):
        """RAGStore(path) creates store directory if missing."""
        _ = RAGStore(store_path=temp_store_path)
        assert Path(temp_store_path).exists()
        assert Path(temp_store_path).is_dir()

    def test_initialization_creates_table(self, temp_store_path):
        """RAGStore creates table with correct schema."""
        store = RAGStore(store_path=temp_store_path)
        
        # Verify lancedb connection created
        assert "chunks" in store._db.table_names()
        
        # Verify schema implicitly by checking if we can open it
        table = store._db.open_table("chunks")
        assert table is not None
        # Could verify schema fields if strictly required, but ensuring it exists is 2A goal

    @pytest.mark.asyncio
    async def test_health_check_valid(self, temp_store_path):
        """health_check() returns True for valid store."""
        store = RAGStore(store_path=temp_store_path)
        assert await store.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_corrupted(self, temp_store_path):
        """health_check() returns False for corrupted/inaccessible store."""
        store = RAGStore(store_path=temp_store_path)
        
        # Mock the db.open_table to raise exception
        with patch.object(store._db, 'open_table', side_effect=Exception("Corrupt")):
            assert await store.health_check() is False

    @pytest.mark.asyncio
    async def test_add_new_chunks(self, temp_store_path):
        """add([chunks]) inserts new chunks."""
        store = RAGStore(store_path=temp_store_path)
        chunk = RAGChunk(
            id="1", text="test", source="s", technique_ids=[],
            content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768
        )
        count = await store.add([chunk])
        assert count == 1
        
        # Verify persistence
        table = store._db.open_table("chunks")
        assert len(table) == 1
        
    @pytest.mark.asyncio
    async def test_add_updates_existing(self, temp_store_path):
        """add([chunks]) updates existing chunks (upsert due to merge_insert behavior or explicit logic)."""
        store = RAGStore(store_path=temp_store_path)
        chunk1 = RAGChunk(
            id="1", text="old", source="s", technique_ids=[],
            content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768
        )
        await store.add([chunk1])
        
        chunk2 = RAGChunk(
            id="1", text="new", source="s", technique_ids=[],
            content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.2]*768
        )
        count = await store.add([chunk2])
        assert count == 1
        
        table = store._db.open_table("chunks")
        assert len(table) == 1
        data = table.to_arrow().to_pylist()
        assert data[0]["text"] == "new"

    @pytest.mark.asyncio
    async def test_add_empty_list(self, temp_store_path):
        """add([]) handles empty list gracefully."""
        store = RAGStore(store_path=temp_store_path)
        count = await store.add([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_add_validates_embeddings(self, temp_store_path):
        """add() validates chunks have embeddings."""
        store = RAGStore(store_path=temp_store_path)
        chunk = RAGChunk(
            id="1", text="test", source="s", technique_ids=[],
            content_type=ContentType.PAYLOAD, metadata={}, embedding=None
        )
        with pytest.raises(ValueError, match="missing embedding"):
            await store.add([chunk])
            
    @pytest.mark.asyncio
    async def test_search_basic(self, temp_store_path):
        """search() returns top_k results."""
        # Use small dim for precise vector testing
        store = RAGStore(store_path=temp_store_path, embedding_dim=3)
        
        # Add orthogonal chunks
        chunks = [
            RAGChunk("1", "chunk one", "s", [], ContentType.PAYLOAD, {}, [1.0, 0.0, 0.0]),
            RAGChunk("2", "chunk two", "s", [], ContentType.PAYLOAD, {}, [0.0, 1.0, 0.0]),
            RAGChunk("3", "chunk three", "s", [], ContentType.PAYLOAD, {}, [0.0, 0.0, 1.0])
        ]
        await store.add(chunks)
        
        # Search for vector similar to chunk 2
        query = [0.0, 1.0, 0.0]
        results = await store.search(query, top_k=2)
        
        assert len(results) == 2
        assert results[0].id == "2"
        assert results[0].score > 0.99  # Should be 1.0
        
    @pytest.mark.asyncio
    async def test_search_fields(self, temp_store_path):
        """search results include score and all fields."""
        store = RAGStore(store_path=temp_store_path)
        c = RAGChunk("1", "text", "src", ["T1"], ContentType.PAYLOAD, {"k":"v"}, [0.1]*768)
        await store.add([c])
        
        results = await store.search([0.1]*768, top_k=1)
        res = results[0]
        assert res.id == "1"
        assert res.text == "text"
        assert res.source == "src"
        assert res.technique_ids == ["T1"]
        assert res.content_type == "payload"
        assert res.metadata == {"k":"v"}
        assert isinstance(res.score, float)

    @pytest.mark.asyncio
    async def test_search_empty(self, temp_store_path):
        """search() on empty store returns empty list."""
        store = RAGStore(store_path=temp_store_path)
        results = await store.search([0.1]*768)
        assert results == []

    @pytest.mark.asyncio
    async def test_get_stats(self, temp_store_path):
        """get_stats() returns store statistics."""
        from cyberred.rag.models import RAGStoreStats
        
        store = RAGStore(store_path=temp_store_path)
        chunks = [
            RAGChunk("1", "t", "src1", [], ContentType.PAYLOAD, {}, [0.1]*768),
            RAGChunk("2", "t", "src2", [], ContentType.PAYLOAD, {}, [0.1]*768),
            RAGChunk("3", "t", "src1", [], ContentType.PAYLOAD, {}, [0.1]*768)
        ]
        await store.add(chunks)
        
        stats = await store.get_stats()
        assert isinstance(stats, RAGStoreStats)
        assert stats.total_vectors == 3
        assert "src1" in stats.sources
        assert "src2" in stats.sources
        assert len(stats.sources) == 2
        assert stats.storage_size_bytes > 0

    @pytest.mark.asyncio
    async def test_search_with_filter_source(self, temp_store_path):
        """search() filters by source."""
        store = RAGStore(store_path=temp_store_path)
        chunks = [
            RAGChunk("1", "chunk one", "source_a", [], ContentType.PAYLOAD, {}, [0.1]*768),
            RAGChunk("2", "chunk two", "source_b", [], ContentType.PAYLOAD, {}, [0.1]*768),
        ]
        await store.add(chunks)
        
        results = await store.search([0.1]*768, top_k=5, filter_source="source_a")
        assert len(results) == 1
        assert results[0].source == "source_a"

    @pytest.mark.asyncio
    async def test_search_with_filter_content_type(self, temp_store_path):
        """search() filters by content_type."""
        store = RAGStore(store_path=temp_store_path)
        chunks = [
            RAGChunk("1", "chunk one", "src", [], ContentType.PAYLOAD, {}, [0.1]*768),
            RAGChunk("2", "chunk two", "src", [], ContentType.METHODOLOGY, {}, [0.1]*768),
        ]
        await store.add(chunks)
        
        results = await store.search([0.1]*768, top_k=5, filter_content_type="methodology")
        assert len(results) == 1
        assert results[0].content_type == "methodology"

    @pytest.mark.asyncio
    async def test_search_with_both_filters(self, temp_store_path):
        """search() filters by both source and content_type."""
        store = RAGStore(store_path=temp_store_path)
        chunks = [
            RAGChunk("1", "a", "src_a", [], ContentType.PAYLOAD, {}, [0.1]*768),
            RAGChunk("2", "b", "src_a", [], ContentType.METHODOLOGY, {}, [0.1]*768),
            RAGChunk("3", "c", "src_b", [], ContentType.PAYLOAD, {}, [0.1]*768),
        ]
        await store.add(chunks)
        
        results = await store.search([0.1]*768, top_k=5, filter_source="src_a", filter_content_type="payload")
        assert len(results) == 1
        assert results[0].id == "1"

    @pytest.mark.asyncio
    async def test_search_table_not_exists(self, temp_store_path):
        """search() returns empty list when table doesn't exist in db."""
        store = RAGStore(store_path=temp_store_path)
        # Drop the table to simulate non-existent state
        store._db.drop_table(store.TABLE_NAME)
        
        results = await store.search([0.1]*768)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_exception_handling(self, temp_store_path):
        """search() returns empty list on exception."""
        store = RAGStore(store_path=temp_store_path)
        chunks = [RAGChunk("1", "t", "s", [], ContentType.PAYLOAD, {}, [0.1]*768)]
        await store.add(chunks)
        
        # Mock to raise exception during search
        with patch.object(store._db, 'open_table', side_effect=Exception("Search error")):
            results = await store.search([0.1]*768)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_json_decode_error(self, temp_store_path):
        """search() handles malformed JSON metadata gracefully."""
        store = RAGStore(store_path=temp_store_path)
        
        # Insert data with invalid JSON metadata directly
        table = store._db.open_table(store.TABLE_NAME)
        table.add([{
            "id": "bad",
            "text": "test",
            "source": "src",
            "technique_ids": [],
            "content_type": "payload",
            "metadata": "not valid json {{{",  # Invalid JSON
            "embedding": [0.1]*768
        }])
        
        results = await store.search([0.1]*768, top_k=1)
        assert len(results) == 1
        assert results[0].metadata == {}  # Should default to empty dict

    @pytest.mark.asyncio
    async def test_search_results_sorted_by_score_descending(self, temp_store_path):
        """search() returns results sorted by score in descending order."""
        store = RAGStore(store_path=temp_store_path, embedding_dim=3)
        
        chunks = [
            RAGChunk("far", "far chunk", "s", [], ContentType.PAYLOAD, {}, [0.0, 0.0, 1.0]),
            RAGChunk("mid", "mid chunk", "s", [], ContentType.PAYLOAD, {}, [0.5, 0.5, 0.0]),
            RAGChunk("close", "close chunk", "s", [], ContentType.PAYLOAD, {}, [1.0, 0.0, 0.0]),
        ]
        await store.add(chunks)
        
        # Query for vector most similar to [1.0, 0.0, 0.0]
        results = await store.search([1.0, 0.0, 0.0], top_k=3)
        
        # Verify descending score order
        assert len(results) == 3
        for i in range(len(results) - 1):
            assert results[i].score >= results[i+1].score, "Results not in descending score order"

    @pytest.mark.asyncio
    async def test_get_stats_table_not_exists(self, temp_store_path):
        """get_stats() returns empty stats when table doesn't exist."""
        store = RAGStore(store_path=temp_store_path)
        # Drop the table
        store._db.drop_table(store.TABLE_NAME)
        
        stats = await store.get_stats()
        assert stats.total_vectors == 0
        assert stats.sources == []

    @pytest.mark.asyncio
    async def test_get_stats_exception_handling(self, temp_store_path):
        """get_stats() handles exceptions gracefully in source query."""
        store = RAGStore(store_path=temp_store_path)
        chunks = [RAGChunk("1", "t", "src", [], ContentType.PAYLOAD, {}, [0.1]*768)]
        await store.add(chunks)
        
        # We need to mock the table's search method to raise an exception
        # The try block does: table.search().select(["source"]).to_arrow()
        original_open_table = store._db.open_table
        
        def mock_open_table(name):
            real_table = original_open_table(name)
            # Create a mock that raises on search()
            class MockTable:
                def __len__(self):
                    return len(real_table)
                def search(self):
                    raise Exception("Query failed")
            return MockTable()
        
        with patch.object(store._db, 'open_table', side_effect=mock_open_table):
            stats = await store.get_stats()
            # Should still return stats but with empty sources due to exception
            assert stats.sources == []
            assert stats.source_counts == {}

    @pytest.mark.asyncio
    async def test_module_exports(self) -> None:
        """Module exports symbols correctly."""
        # Note: Importing locally to avoid top-level import errors during dev
        import cyberred.rag
        
        assert hasattr(cyberred.rag, "RAGStore")
        assert hasattr(cyberred.rag, "RAGChunk")
        assert hasattr(cyberred.rag, "RAGSearchResult")
        assert hasattr(cyberred.rag, "RAGStoreStats")
        assert hasattr(cyberred.rag, "ContentType")
