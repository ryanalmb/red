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
            RAGChunk(id="1", text="chunk one", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[1.0, 0.0, 0.0]),
            RAGChunk(id="2", text="chunk two", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.0, 1.0, 0.0]),
            RAGChunk(id="3", text="chunk three", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.0, 0.0, 1.0])
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
        c = RAGChunk(id="1", text="text", source="src", technique_ids=["T1"], content_type=ContentType.PAYLOAD, metadata={"k":"v"}, embedding=[0.1]*768)
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
            RAGChunk(id="1", text="t", source="src1", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="2", text="t", source="src2", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="3", text="t", source="src1", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768)
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
            RAGChunk(id="1", text="chunk one", source="source_a", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="2", text="chunk two", source="source_b", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
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
            RAGChunk(id="1", text="chunk one", source="src", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="2", text="chunk two", source="src", technique_ids=[], content_type=ContentType.METHODOLOGY, metadata={}, embedding=[0.1]*768),
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
            RAGChunk(id="1", text="a", source="src_a", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="2", text="b", source="src_a", technique_ids=[], content_type=ContentType.METHODOLOGY, metadata={}, embedding=[0.1]*768),
            RAGChunk(id="3", text="c", source="src_b", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768),
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
        chunks = [RAGChunk(id="1", text="t", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768)]
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
            RAGChunk(id="far", text="far chunk", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.0, 0.0, 1.0]),
            RAGChunk(id="mid", text="mid chunk", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.5, 0.5, 0.0]),
            RAGChunk(id="close", text="close chunk", source="s", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[1.0, 0.0, 0.0]),
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
        chunks = [RAGChunk(id="1", text="t", source="src", technique_ids=[], content_type=ContentType.PAYLOAD, metadata={}, embedding=[0.1]*768)]
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
        assert hasattr(cyberred.rag, "Tactic")  # Story 6-13


@pytest.mark.unit
class TestRAGStoreTactics:
    """Tests for tactics storage and retrieval in RAGStore (Story 6-13)."""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        return str(tmp_path / "rag_tactics_test")

    @pytest.mark.asyncio
    async def test_add_chunk_with_tactics(self, temp_store_path):
        """RAGStore.add() stores chunks with tactics field."""
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="test:tactics",
            text="Test chunk with tactics",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution", "persistence"],
            embedding=[0.1] * 768
        )
        
        count = await store.add([chunk])
        assert count == 1

    @pytest.mark.asyncio
    async def test_search_returns_tactics(self, temp_store_path):
        """RAGStore.search() returns tactics in results."""
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="test:tactics",
            text="Lateral movement technique",
            source="mitre",
            technique_ids=["T1021"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["lateral-movement"],
            embedding=[0.1] * 768
        )
        
        await store.add([chunk])
        results = await store.search([0.1] * 768, top_k=1)
        
        assert len(results) == 1
        assert results[0].tactics == ["lateral-movement"]

    @pytest.mark.asyncio
    async def test_search_filter_tactic_matches(self, temp_store_path):
        """RAGStore.search() with filter_tactic returns matching results."""
        store = RAGStore(store_path=temp_store_path)
        
        chunks = [
            RAGChunk(
                id="exec:1",
                text="Execution technique",
                source="test",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=[0.1] * 768
            ),
            RAGChunk(
                id="lateral:1",
                text="Lateral movement technique",
                source="test",
                technique_ids=["T1021"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["lateral-movement"],
                embedding=[0.1] * 768
            ),
        ]
        
        await store.add(chunks)
        
        # Filter by execution
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="execution")
        assert len(results) == 1
        assert results[0].id == "exec:1"
        
        # Filter by lateral-movement
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="lateral-movement")
        assert len(results) == 1
        assert results[0].id == "lateral:1"

    @pytest.mark.asyncio
    async def test_search_filter_tactic_no_match(self, temp_store_path):
        """RAGStore.search() with filter_tactic returns empty if no match."""
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="exec:1",
            text="Execution technique",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution"],
            embedding=[0.1] * 768
        )
        
        await store.add([chunk])
        
        # Filter by tactic that doesn't exist
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="exfiltration")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_multiple_tactics_per_chunk(self, temp_store_path):
        """Chunk with multiple tactics is matched by any of them."""
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="multi:1",
            text="Multi-tactic technique",
            source="test",
            technique_ids=["T1078"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["initial-access", "persistence", "privilege-escalation"],
            embedding=[0.1] * 768
        )
        
        await store.add([chunk])
        
        # Should match on any tactic
        for tactic in ["initial-access", "persistence", "privilege-escalation"]:
            results = await store.search([0.1] * 768, top_k=1, filter_tactic=tactic)
            assert len(results) == 1
            assert results[0].id == "multi:1"

    @pytest.mark.asyncio
    async def test_search_empty_tactics_default(self, temp_store_path):
        """Chunks without tactics default to empty list."""
        store = RAGStore(store_path=temp_store_path)
        
        # Chunk without tactics (defaults to [])
        chunk = RAGChunk(
            id="no:tactics",
            text="Chunk without tactics",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={},
            embedding=[0.1] * 768
        )
        
        await store.add([chunk])
        results = await store.search([0.1] * 768, top_k=1)
        
        assert len(results) == 1
        assert results[0].tactics == []

    @pytest.mark.asyncio
    async def test_search_filter_tactic_combined_with_source(self, temp_store_path):
        """filter_tactic works combined with filter_source."""
        store = RAGStore(store_path=temp_store_path)
        
        chunks = [
            RAGChunk(
                id="mitre:exec",
                text="MITRE execution",
                source="mitre_attack",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=[0.1] * 768
            ),
            RAGChunk(
                id="hacktricks:exec",
                text="HackTricks execution",
                source="hacktricks",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=[0.1] * 768
            ),
        ]
        
        await store.add(chunks)
        
        # Filter by both source and tactic
        results = await store.search(
            [0.1] * 768, 
            top_k=10, 
            filter_source="mitre_attack",
            filter_tactic="execution"
        )
        
        assert len(results) == 1
        assert results[0].id == "mitre:exec"
        assert results[0].source == "mitre_attack"

    @pytest.mark.asyncio
    async def test_tactics_preserved_on_update(self, temp_store_path):
        """Tactics are preserved when chunk is updated (upsert)."""
        store = RAGStore(store_path=temp_store_path)
        
        # Add initial chunk
        chunk = RAGChunk(
            id="update:1",
            text="Original text",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution"],
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        # Update with new tactics
        updated_chunk = RAGChunk(
            id="update:1",
            text="Updated text",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution", "persistence"],  # Added persistence
            embedding=[0.2] * 768
        )
        await store.add([updated_chunk])
        
        # Verify updated
        results = await store.search([0.2] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].tactics == ["execution", "persistence"]


@pytest.mark.unit
class TestRAGStoreProperties:
    """Tests for RAGStore properties and initialization (Story 6-13 coverage)."""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        return str(tmp_path / "rag_props_test")

    def test_db_path_property(self, temp_store_path):
        """db_path property returns the store path."""
        from pathlib import Path
        store = RAGStore(store_path=temp_store_path)
        
        assert store.db_path == Path(temp_store_path)
        assert store.db_path.exists()

    def test_store_creates_directory(self, tmp_path):
        """Store creates directory if it doesn't exist."""
        nested_path = tmp_path / "nested" / "deep" / "store"
        store = RAGStore(store_path=str(nested_path))
        
        assert nested_path.exists()
        assert store.db_path == nested_path

    @pytest.mark.asyncio
    async def test_health_check_valid_store(self, temp_store_path):
        """health_check returns True for valid store."""
        store = RAGStore(store_path=temp_store_path)
        
        # Add a chunk to ensure table exists
        chunk = RAGChunk(
            id="health:1",
            text="test",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={},
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        result = await store.health_check()
        assert result is True


@pytest.mark.unit
class TestRAGStoreSchemaMigration:
    """Tests for RAGStore schema migration (Story 6-13 coverage)."""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        return str(tmp_path / "rag_migration_test")

    @pytest.mark.asyncio
    async def test_migration_adds_tactics_column(self, temp_store_path):
        """Schema migration adds tactics column to existing tables."""
        import lancedb
        import pyarrow as pa
        from pathlib import Path
        
        # Create a legacy table WITHOUT tactics column
        Path(temp_store_path).mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(temp_store_path)
        
        legacy_schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("source", pa.string()),
            pa.field("technique_ids", pa.list_(pa.string())),
            # NO tactics column - legacy schema
            pa.field("content_type", pa.string()),
            pa.field("metadata", pa.string()),
            pa.field("embedding", pa.list_(pa.float32(), 768))
        ])
        
        # Create legacy table with data
        db.create_table("chunks", schema=legacy_schema)
        table = db.open_table("chunks")
        table.add([{
            "id": "legacy:1",
            "text": "legacy chunk",
            "source": "old_source",
            "technique_ids": ["T1059"],
            "content_type": "payload",
            "metadata": "{}",
            "embedding": [0.1] * 768
        }])
        
        # Close connection
        del table
        del db
        
        # Now open with RAGStore - should trigger migration
        store = RAGStore(store_path=temp_store_path)
        
        # Verify we can search and get results with tactics field
        results = await store.search([0.1] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].id == "legacy:1"
        assert results[0].tactics == []  # Migrated data has empty tactics

    @pytest.mark.asyncio
    async def test_migration_preserves_existing_data(self, temp_store_path):
        """Schema migration preserves all existing data."""
        import lancedb
        import pyarrow as pa
        from pathlib import Path
        
        # Create a legacy table WITHOUT tactics column
        Path(temp_store_path).mkdir(parents=True, exist_ok=True)
        db = lancedb.connect(temp_store_path)
        
        legacy_schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("source", pa.string()),
            pa.field("technique_ids", pa.list_(pa.string())),
            pa.field("content_type", pa.string()),
            pa.field("metadata", pa.string()),
            pa.field("embedding", pa.list_(pa.float32(), 768))
        ])
        
        db.create_table("chunks", schema=legacy_schema)
        table = db.open_table("chunks")
        
        # Add multiple legacy rows
        for i in range(5):
            table.add([{
                "id": f"legacy:{i}",
                "text": f"legacy chunk {i}",
                "source": "old_source",
                "technique_ids": ["T1059"],
                "content_type": "methodology",
                "metadata": '{"key": "value"}',
                "embedding": [0.1 + i * 0.01] * 768
            }])
        
        del table
        del db
        
        # Open with RAGStore - triggers migration
        store = RAGStore(store_path=temp_store_path)
        
        # Verify all data preserved
        stats = await store.get_stats()
        assert stats.total_vectors == 5

    @pytest.mark.asyncio
    async def test_no_migration_needed_for_new_store(self, temp_store_path):
        """New store doesn't need migration."""
        store = RAGStore(store_path=temp_store_path)
        
        # Add chunk with tactics
        chunk = RAGChunk(
            id="new:1",
            text="new chunk",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution"],
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        # Verify tactics are preserved
        results = await store.search([0.1] * 768, top_k=1)
        assert results[0].tactics == ["execution"]


@pytest.mark.unit
class TestRAGStoreEdgeCases:
    """Tests for edge cases and coverage gaps in RAGStore (Story 6-13)."""

    @pytest.fixture
    def temp_store_path(self, tmp_path):
        return str(tmp_path / "rag_edge_test")

    @pytest.mark.asyncio
    async def test_add_large_batch_logs_info(self, temp_store_path):
        """Adding >100 chunks logs info message."""
        store = RAGStore(store_path=temp_store_path)
        
        # Create 101 chunks to trigger the log message
        chunks = [
            RAGChunk(
                id=f"batch:{i}",
                text=f"chunk {i}",
                source="test",
                technique_ids=[],
                content_type=ContentType.PAYLOAD,
                metadata={},
                embedding=[0.1 + i * 0.001] * 768
            )
            for i in range(101)
        ]
        
        count = await store.add(chunks)
        assert count == 101

    @pytest.mark.asyncio
    async def test_search_filter_tactic_excludes_non_matching(self, temp_store_path):
        """Search with filter_tactic excludes chunks without that tactic."""
        store = RAGStore(store_path=temp_store_path)
        
        chunks = [
            RAGChunk(
                id="exec:1",
                text="execution chunk",
                source="test",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=[0.1] * 768
            ),
            RAGChunk(
                id="recon:1",
                text="recon chunk",
                source="test",
                technique_ids=["T1595"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["reconnaissance"],
                embedding=[0.1] * 768
            ),
        ]
        await store.add(chunks)
        
        # Filter for execution - should exclude recon
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="execution")
        assert len(results) == 1
        assert results[0].id == "exec:1"
        
        # Filter for recon - should exclude execution
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="reconnaissance")
        assert len(results) == 1
        assert results[0].id == "recon:1"

    @pytest.mark.asyncio
    async def test_search_metadata_last_updated_parsing(self, temp_store_path):
        """Search correctly parses last_updated from metadata."""
        from datetime import datetime
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="dated:1",
            text="chunk with date",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={"last_updated": "2025-01-10T12:00:00"},
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        results = await store.search([0.1] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].last_updated == datetime(2025, 1, 10, 12, 0, 0)

    @pytest.mark.asyncio
    async def test_search_metadata_invalid_last_updated(self, temp_store_path):
        """Search handles invalid last_updated gracefully."""
        store = RAGStore(store_path=temp_store_path)
        
        chunk = RAGChunk(
            id="invalid:1",
            text="chunk with invalid date",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={"last_updated": "not-a-date"},
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        results = await store.search([0.1] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].last_updated is None  # Invalid date returns None

    @pytest.mark.asyncio
    async def test_search_metadata_json_decode_error(self, temp_store_path):
        """Search handles malformed JSON metadata gracefully."""
        import lancedb
        from pathlib import Path
        
        # Manually insert a row with invalid JSON metadata
        Path(temp_store_path).mkdir(parents=True, exist_ok=True)
        store = RAGStore(store_path=temp_store_path)
        
        # Add a valid chunk first to create the table
        chunk = RAGChunk(
            id="valid:1",
            text="valid chunk",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={},
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        # Directly insert a row with malformed metadata
        db = lancedb.connect(temp_store_path)
        table = db.open_table("chunks")
        table.add([{
            "id": "malformed:1",
            "text": "malformed metadata chunk",
            "source": "test",
            "technique_ids": [],
            "tactics": [],
            "content_type": "payload",
            "metadata": "not-valid-json{{{",  # Invalid JSON
            "embedding": [0.2] * 768
        }])
        
        # Search should still work - malformed metadata becomes {}
        results = await store.search([0.2] * 768, top_k=2)
        assert len(results) >= 1
        
        # Find the malformed chunk in results
        malformed_result = next((r for r in results if r.id == "malformed:1"), None)
        assert malformed_result is not None
        assert malformed_result.metadata == {}  # Fallback to empty dict

    @pytest.mark.asyncio
    async def test_search_empty_tactics_in_stored_data(self, temp_store_path):
        """Search handles empty tactics stored in LanceDB."""
        store = RAGStore(store_path=temp_store_path)
        
        # Chunk with empty tactics
        chunk = RAGChunk(
            id="empty_tactics:1",
            text="empty tactics chunk",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={},
            tactics=[],  # Empty list
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        results = await store.search([0.1] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].tactics == []  # Empty list preserved

    @pytest.mark.asyncio
    async def test_search_filter_tactic_no_match_returns_empty(self, temp_store_path):
        """Search with filter_tactic returns empty when no chunks match."""
        store = RAGStore(store_path=temp_store_path)
        
        # Only add execution tactic chunks
        chunk = RAGChunk(
            id="exec:1",
            text="execution only",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution"],
            embedding=[0.1] * 768
        )
        await store.add([chunk])
        
        # Filter for a tactic that doesn't exist
        results = await store.search([0.1] * 768, top_k=10, filter_tactic="exfiltration")
        assert len(results) == 0
