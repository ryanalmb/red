import pytest
from cyberred.rag import RAGStore, RAGEmbeddings, RAGQueryInterface, RAGChunk, ContentType

@pytest.mark.integration
class TestRAGQueryIntegration:
    
    @pytest.fixture
    def embeddings(self):
        # NOTE: Loading model might take time, but ensures integration validity
        return RAGEmbeddings()
        
    @pytest.fixture
    def store_path(self, tmp_path):
        return str(tmp_path / "rag_integration_query")
        
    @pytest.mark.asyncio
    async def test_query_flow(self, store_path, embeddings):
        """End-to-end query flow with filters."""
        store = RAGStore(store_path)
        rag = RAGQueryInterface(store, embeddings)
        
        # Populate
        # Using real embeddings for realistic matching
        vector1 = embeddings.encode("python script for automation")
        vector2 = embeddings.encode("compiled binary executable payload")
        
        chunks = [
            RAGChunk(
                id="1", 
                text="This is a python script for automation.", 
                source="src1", 
                technique_ids=[], 
                content_type=ContentType.METHODOLOGY, 
                metadata={}, 
                embedding=vector1
            ),
            RAGChunk(
                id="2", 
                text="This is a compiled binary executable payload.", 
                source="src2", 
                technique_ids=[], 
                content_type=ContentType.PAYLOAD, 
                metadata={}, 
                embedding=vector2
            ),
        ]
        await store.add(chunks)
        
        # Query 1: Basic Search for "python"
        results = await rag.query("python automation")
        assert len(results) >= 1
        assert results[0].id == "1"
        assert results[0].content_type == ContentType.METHODOLOGY
        
        # Query 2: Source Filter (expect "2")
        results = await rag.query("binary", filter_source="src2")
        assert len(results) == 1
        assert results[0].id == "2"
        
        # Query 3: Content Type Filter (expect "1")
        results = await rag.query("script", filter_content_type=ContentType.METHODOLOGY)
        assert len(results) == 1
        assert results[0].id == "1"
        
        # Query 4: Combined Filter (expect empty if mismatch)
        results = await rag.query("script", filter_source="src2", filter_content_type=ContentType.METHODOLOGY)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_empty_store(self, tmp_path, embeddings):
        """Querying an empty store returns empty list."""
        store = RAGStore(str(tmp_path / "empty_store"))
        rag = RAGQueryInterface(store, embeddings)
        
        results = await rag.query("anything")
        assert results == []
