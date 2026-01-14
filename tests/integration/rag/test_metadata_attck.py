"""Integration tests for RAG Result Metadata & ATT&CK Mapping (Story 6-13).

Tests end-to-end tactic filtering and metadata with real LanceDB.
Only embeddings are mocked.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from cyberred.rag import RAGStore, RAGQueryInterface, RAGChunk, ContentType
from cyberred.rag.models import Tactic, RAGSearchResult


@pytest.fixture
def mock_embeddings():
    """Mock embeddings that return deterministic vectors based on text content."""
    mock = Mock()
    
    def encode_fn(text: str) -> list:
        """Return different vectors based on text keywords for realistic matching."""
        # Use simple hash-based approach for deterministic but varied vectors
        base = [0.1] * 768
        if "lateral" in text.lower() or "psexec" in text.lower():
            base[0] = 0.9
            base[1] = 0.8
        elif "powershell" in text.lower() or "execution" in text.lower():
            base[0] = 0.2
            base[1] = 0.9
        elif "credential" in text.lower() or "mimikatz" in text.lower():
            base[0] = 0.5
            base[1] = 0.5
        return base
    
    mock.encode = encode_fn
    return mock


@pytest.mark.integration
class TestTacticFiltering:
    """Integration tests for tactic-based filtering."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_tactic_test")

    @pytest.mark.asyncio
    async def test_store_and_retrieve_with_tactics(self, store_path, mock_embeddings):
        """Chunks with tactics can be stored and retrieved."""
        store = RAGStore(store_path=store_path)
        
        chunk = RAGChunk(
            id="mitre:T1021.002",
            text="PsExec can be used for lateral movement via SMB.",
            source="mitre_attack",
            technique_ids=["T1021.002"],
            content_type=ContentType.METHODOLOGY,
            metadata={"url": "https://attack.mitre.org/techniques/T1021/002/"},
            tactics=["lateral-movement"],
            embedding=mock_embeddings.encode("psexec lateral movement")
        )
        
        await store.add([chunk])
        
        # Search and verify tactics are returned
        results = await store.search(
            mock_embeddings.encode("psexec lateral movement"),
            top_k=1
        )
        
        assert len(results) == 1
        assert results[0].id == "mitre:T1021.002"
        assert results[0].tactics == ["lateral-movement"]

    @pytest.mark.asyncio
    async def test_filter_by_single_tactic(self, store_path, mock_embeddings):
        """Results can be filtered by a single tactic."""
        store = RAGStore(store_path=store_path)
        
        chunks = [
            RAGChunk(
                id="lateral:1",
                text="PsExec for lateral movement",
                source="test",
                technique_ids=["T1021"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["lateral-movement"],
                embedding=mock_embeddings.encode("psexec lateral")
            ),
            RAGChunk(
                id="execution:1",
                text="PowerShell execution technique",
                source="test",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=mock_embeddings.encode("powershell execution")
            ),
            RAGChunk(
                id="credential:1",
                text="Mimikatz credential dumping",
                source="test",
                technique_ids=["T1003"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["credential-access"],
                embedding=mock_embeddings.encode("mimikatz credential")
            ),
        ]
        
        await store.add(chunks)
        
        # Filter by lateral-movement
        results = await store.search(
            mock_embeddings.encode("technique"),
            top_k=10,
            filter_tactic="lateral-movement"
        )
        
        assert len(results) == 1
        assert results[0].id == "lateral:1"
        assert "lateral-movement" in results[0].tactics

    @pytest.mark.asyncio
    async def test_filter_tactic_combined_with_source(self, store_path, mock_embeddings):
        """Tactic filter can be combined with source filter."""
        store = RAGStore(store_path=store_path)
        
        chunks = [
            RAGChunk(
                id="mitre:lateral",
                text="Lateral movement via SMB",
                source="mitre_attack",
                technique_ids=["T1021"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["lateral-movement"],
                embedding=mock_embeddings.encode("lateral smb")
            ),
            RAGChunk(
                id="hacktricks:lateral",
                text="Lateral movement via WinRM",
                source="hacktricks",
                technique_ids=["T1021"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["lateral-movement"],
                embedding=mock_embeddings.encode("lateral winrm")
            ),
        ]
        
        await store.add(chunks)
        
        # Filter by both tactic and source
        results = await store.search(
            mock_embeddings.encode("lateral"),
            top_k=10,
            filter_source="mitre_attack",
            filter_tactic="lateral-movement"
        )
        
        assert len(results) == 1
        assert results[0].id == "mitre:lateral"
        assert results[0].source == "mitre_attack"

    @pytest.mark.asyncio
    async def test_multiple_tactics_per_chunk(self, store_path, mock_embeddings):
        """Chunks with multiple tactics can be filtered by any of them."""
        store = RAGStore(store_path=store_path)
        
        # T1078 (Valid Accounts) maps to multiple tactics
        chunk = RAGChunk(
            id="multi:T1078",
            text="Using valid accounts for initial access and persistence",
            source="mitre_attack",
            technique_ids=["T1078"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["defense-evasion", "initial-access", "persistence", "privilege-escalation"],
            embedding=mock_embeddings.encode("valid accounts")
        )
        
        await store.add([chunk])
        
        # Should match when filtering by any of its tactics
        for tactic in ["defense-evasion", "initial-access", "persistence", "privilege-escalation"]:
            results = await store.search(
                mock_embeddings.encode("accounts"),
                top_k=1,
                filter_tactic=tactic
            )
            assert len(results) == 1, f"Should match tactic: {tactic}"
            assert results[0].id == "multi:T1078"


@pytest.mark.integration
class TestQueryInterfaceTacticFilter:
    """Integration tests for RAGQueryInterface tactic filtering."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_query_tactic_test")

    @pytest.mark.asyncio
    async def test_query_with_tactic_filter(self, store_path, mock_embeddings):
        """RAGQueryInterface.query() supports filter_tactic parameter."""
        store = RAGStore(store_path=store_path)
        rag = RAGQueryInterface(store, mock_embeddings)
        
        chunks = [
            RAGChunk(
                id="exec:1",
                text="PowerShell command execution",
                source="test",
                technique_ids=["T1059.001"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=mock_embeddings.encode("powershell execution")
            ),
            RAGChunk(
                id="persist:1",
                text="Registry run key persistence",
                source="test",
                technique_ids=["T1547.001"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["persistence", "privilege-escalation"],
                embedding=mock_embeddings.encode("registry persistence")
            ),
        ]
        
        await store.add(chunks)
        
        # Query with tactic filter
        results = await rag.query("technique", filter_tactic="execution")
        
        assert len(results) == 1
        assert results[0].id == "exec:1"
        assert "execution" in results[0].tactics

    @pytest.mark.asyncio
    async def test_query_invalid_tactic_raises_error(self, store_path, mock_embeddings):
        """RAGQueryInterface.query() raises ValueError for invalid tactic."""
        store = RAGStore(store_path=store_path)
        rag = RAGQueryInterface(store, mock_embeddings)
        
        with pytest.raises(ValueError, match="Invalid tactic"):
            await rag.query("test", filter_tactic="invalid-tactic")

    @pytest.mark.asyncio
    async def test_query_all_valid_tactics(self, store_path, mock_embeddings):
        """All valid Tactic enum values are accepted as filter."""
        store = RAGStore(store_path=store_path)
        rag = RAGQueryInterface(store, mock_embeddings)
        
        # Test all 14 tactics are valid filters (even if no results)
        for tactic in Tactic:
            results = await rag.query("test", filter_tactic=tactic.value)
            assert isinstance(results, list)  # No error, returns list


@pytest.mark.integration
class TestMetadataCompleteness:
    """Integration tests for metadata completeness in search results."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_metadata_test")

    @pytest.mark.asyncio
    async def test_search_result_contains_all_metadata(self, store_path, mock_embeddings):
        """Search results include source, technique_ids, tactics, and score."""
        store = RAGStore(store_path=store_path)
        
        chunk = RAGChunk(
            id="meta:test",
            text="Test content for metadata verification",
            source="test_source",
            technique_ids=["T1059", "T1059.001"],
            content_type=ContentType.METHODOLOGY,
            metadata={"author": "test", "version": "1.0"},
            tactics=["execution", "persistence"],
            embedding=mock_embeddings.encode("test metadata")
        )
        
        await store.add([chunk])
        
        results = await store.search(
            mock_embeddings.encode("test metadata"),
            top_k=1
        )
        
        assert len(results) == 1
        result = results[0]
        
        # Verify all metadata fields
        assert result.id == "meta:test"
        assert result.source == "test_source"
        assert result.technique_ids == ["T1059", "T1059.001"]
        assert result.tactics == ["execution", "persistence"]
        assert result.content_type == ContentType.METHODOLOGY
        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0
        assert result.metadata["author"] == "test"
        assert result.metadata["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_last_updated_from_metadata(self, store_path, mock_embeddings):
        """last_updated is extracted from metadata if present."""
        store = RAGStore(store_path=store_path)
        
        chunk = RAGChunk(
            id="dated:test",
            text="Content with last_updated timestamp",
            source="test_source",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={"last_updated": "2025-01-10T12:00:00"},
            tactics=[],
            embedding=mock_embeddings.encode("dated content")
        )
        
        await store.add([chunk])
        
        results = await store.search(
            mock_embeddings.encode("dated content"),
            top_k=1
        )
        
        assert len(results) == 1
        assert results[0].last_updated == datetime(2025, 1, 10, 12, 0, 0)


@pytest.mark.integration
class TestSchemaMigration:
    """Integration tests for schema migration (backward compatibility)."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_migration_test")

    @pytest.mark.asyncio
    async def test_chunks_without_tactics_default_to_empty(self, store_path, mock_embeddings):
        """Chunks created without tactics field default to empty list."""
        store = RAGStore(store_path=store_path)
        
        # Create chunk without tactics (simulating old data)
        chunk = RAGChunk(
            id="old:chunk",
            text="Old chunk without tactics",
            source="legacy",
            technique_ids=["T1234"],
            content_type=ContentType.PAYLOAD,
            metadata={},
            embedding=mock_embeddings.encode("old chunk")
        )
        # Note: tactics defaults to [] in RAGChunk
        
        await store.add([chunk])
        
        results = await store.search(
            mock_embeddings.encode("old chunk"),
            top_k=1
        )
        
        assert len(results) == 1
        assert results[0].tactics == []  # Defaults to empty list

    @pytest.mark.asyncio
    async def test_mixed_chunks_with_and_without_tactics(self, store_path, mock_embeddings):
        """Store handles mix of chunks with and without tactics."""
        store = RAGStore(store_path=store_path)
        
        chunks = [
            RAGChunk(
                id="with:tactics",
                text="Chunk with tactics",
                source="new",
                technique_ids=["T1059"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["execution"],
                embedding=mock_embeddings.encode("with tactics")
            ),
            RAGChunk(
                id="without:tactics",
                text="Chunk without tactics",
                source="old",
                technique_ids=["T1234"],
                content_type=ContentType.PAYLOAD,
                metadata={},
                # tactics defaults to []
                embedding=mock_embeddings.encode("without tactics")
            ),
        ]
        
        await store.add(chunks)
        
        # Both should be searchable
        results = await store.search(
            mock_embeddings.encode("chunk"),
            top_k=10
        )
        
        assert len(results) == 2
        
        # Find each result
        with_tactics = next(r for r in results if r.id == "with:tactics")
        without_tactics = next(r for r in results if r.id == "without:tactics")
        
        assert with_tactics.tactics == ["execution"]
        assert without_tactics.tactics == []


@pytest.mark.integration
class TestTacticFilteringEdgeCases:
    """Edge case tests for tactic filtering."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_edge_cases")

    @pytest.mark.asyncio
    async def test_filter_tactic_no_matches(self, store_path, mock_embeddings):
        """Filtering by tactic with no matches returns empty list."""
        store = RAGStore(store_path=store_path)
        
        chunk = RAGChunk(
            id="exec:only",
            text="Only has execution tactic",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution"],
            embedding=mock_embeddings.encode("execution only")
        )
        
        await store.add([chunk])
        
        # Filter by a tactic that doesn't exist in data
        results = await store.search(
            mock_embeddings.encode("execution"),
            top_k=10,
            filter_tactic="lateral-movement"
        )
        
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_filter_empty_tactics_list(self, store_path, mock_embeddings):
        """Filtering works correctly when chunk has empty tactics list."""
        store = RAGStore(store_path=store_path)
        
        chunks = [
            RAGChunk(
                id="has:tactics",
                text="Has lateral movement tactic",
                source="test",
                technique_ids=["T1021"],
                content_type=ContentType.METHODOLOGY,
                metadata={},
                tactics=["lateral-movement"],
                embedding=mock_embeddings.encode("lateral")
            ),
            RAGChunk(
                id="no:tactics",
                text="Has no tactics",
                source="test",
                technique_ids=[],
                content_type=ContentType.PAYLOAD,
                metadata={},
                tactics=[],
                embedding=mock_embeddings.encode("no tactics")
            ),
        ]
        
        await store.add(chunks)
        
        # Filter should exclude chunk with empty tactics
        results = await store.search(
            mock_embeddings.encode("test"),
            top_k=10,
            filter_tactic="lateral-movement"
        )
        
        assert len(results) == 1
        assert results[0].id == "has:tactics"
