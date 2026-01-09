import pytest
from cyberred.rag import RAGStore, RAGChunk, ContentType

@pytest.mark.integration
class TestRAGStoreIntegration:
    """Integration tests for RAGStore persistence and scale."""

    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_integration")

    @pytest.mark.asyncio
    async def test_full_add_search_cycle(self, store_path):
        """Full add -> search cycle works."""
        store = RAGStore(store_path=store_path)
        
        chunk = RAGChunk(
            id="mitre:T1059",
            text="PowerShell is a powerful scripting language...",
            source="mitre_attack",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={"url": "https://attack.mitre.org"},
            embedding=[0.1] * 768
        )
        
        # Add
        await store.add([chunk])
        
        # Search exact match
        results = await store.search([0.1] * 768, top_k=1)
        assert len(results) == 1
        assert results[0].id == "mitre:T1059"
        assert results[0].text.startswith("PowerShell")

    @pytest.mark.asyncio
    async def test_store_persists_across_restarts(self, store_path):
        """Store persists across restarts."""
        # First instance
        store1 = RAGStore(store_path=store_path)
        chunk = RAGChunk("1", "persist", "src", [], ContentType.PAYLOAD, {}, [0.5]*768)
        await store1.add([chunk])
        
        # Second instance same path
        store2 = RAGStore(store_path=store_path)
        results = await store2.search([0.5]*768)
        
        assert len(results) == 1
        assert results[0].id == "1"

    @pytest.mark.asyncio
    async def test_scale_1000_vectors(self, store_path):
        """Store handles ~1000 vectors efficiently."""
        store = RAGStore(store_path=store_path)
        
        # Create 1000 chunks
        chunks = [
            RAGChunk(
                id=f"id_{i}",
                text=f"content {i}",
                source="scale_test",
                technique_ids=[],
                content_type=ContentType.PAYLOAD,
                metadata={},
                embedding=[float(i % 100) / 100.0] * 768  # Dummy vectors
            )
            for i in range(1000)
        ]
        
        # Add in one batch
        count = await store.add(chunks)
        assert count == 1000
        
        # Verify stats
        stats = await store.get_stats()
        assert stats.total_vectors == 1000
        
        # Search
        results = await store.search([0.5] * 768, top_k=10)
        assert len(results) == 10
