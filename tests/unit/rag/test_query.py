import pytest
from unittest.mock import Mock, AsyncMock
from cyberred.rag.query import RAGQueryInterface
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.models import RAGSearchResult, ContentType
from cyberred.rag.exceptions import RAGQueryTimeout
import asyncio

@pytest.mark.unit
class TestRAGQueryInterface:
    """Tests for RAGQueryInterface class."""
    
    @pytest.fixture
    def store(self):
        return Mock(spec=RAGStore)
        
    @pytest.fixture
    def embeddings(self):
        return Mock(spec=RAGEmbeddings)
        
    @pytest.fixture
    def query_interface(self, store, embeddings):
        return RAGQueryInterface(store, embeddings)

    def test_initialization(self, store, embeddings):
        """RAGQueryInterface initializes with store and embeddings."""
        interface = RAGQueryInterface(store, embeddings)
        assert interface._store == store
        assert interface._embeddings == embeddings

    @pytest.mark.asyncio
    async def test_query_returns_results(self, query_interface, store, embeddings):
        """query() returns List[RAGSearchResult] and embeds text."""
        # Setup mocks
        embeddings.encode.return_value = [0.1, 0.2]
        expected_result = RAGSearchResult(
            id="1", text="text", source="src", technique_ids=[],
            content_type=ContentType.METHODOLOGY, metadata={}, score=0.9
        )
        # Configure async mock for search
        store.search = AsyncMock(return_value=[expected_result])
        
        # Execute
        results = await query_interface.query("test query")
        
        # Verify
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0] == expected_result
        
        # Verify interactions
        embeddings.encode.assert_called_once_with("test query")
        store.search.assert_called_once()
        _, kwargs = store.search.call_args
        assert kwargs["embedding"] == [0.1, 0.2]  # Embeddings passed to search

    @pytest.mark.asyncio
    async def test_query_filters(self, query_interface, store, embeddings):
        """query() passes filters to store."""
        embeddings.encode.return_value = [0.1]
        store.search = AsyncMock(return_value=[])
        
        # Test 1: Source filter
        await query_interface.query("test", filter_source="src1")
        _, kwargs = store.search.call_args
        assert kwargs["filter_source"] == "src1"
        assert kwargs["filter_content_type"] is None
        
        # Test 2: ContentType filter
        await query_interface.query("test", filter_content_type=ContentType.PAYLOAD)
        _, kwargs = store.search.call_args
        assert kwargs["filter_source"] is None
        assert kwargs["filter_content_type"] == "payload"  # Converted to string

    @pytest.mark.asyncio
    async def test_query_timeout(self, query_interface, store, embeddings):
        """query() raises RAGQueryTimeout if it exceeds timeout."""
        embeddings.encode.return_value = [0.1]
        
        # Mock search to be slow
        async def slow_search(*args, **kwargs):
            await asyncio.sleep(0.2)
            return []
            
        store.search = AsyncMock(side_effect=slow_search)
        
        # Expect timeout exception when timeout is shorter than operation
        with pytest.raises(RAGQueryTimeout, match="Query timed out"):
            await query_interface.query("test", timeout=0.1)

    def test_default_timeout_is_10_seconds(self):
        """Default timeout should be 10.0 seconds (AC 3)."""
        from cyberred.rag.query import RAGQueryInterface
        assert RAGQueryInterface.DEFAULT_TIMEOUT == 10.0

    def test_default_top_k_is_5(self):
        """Default top_k should be 5 (AC 1)."""
        from cyberred.rag.query import RAGQueryInterface
        assert RAGQueryInterface.DEFAULT_TOP_K == 5

    @pytest.mark.asyncio
    async def test_top_k_limits_results(self, query_interface, store, embeddings):
        """query(top_k=N) returns at most N results (AC 2)."""
        embeddings.encode.return_value = [0.1]
        
        # Create 10 mock results
        mock_results = [
            RAGSearchResult(
                id=str(i), text=f"text{i}", source="src", technique_ids=[],
                content_type=ContentType.METHODOLOGY, metadata={}, score=1.0 - i*0.1
            )
            for i in range(10)
        ]
        
        # Mock store to return limited results based on top_k
        async def mock_search(embedding, top_k, **kwargs):
            return mock_results[:top_k]
            
        store.search = AsyncMock(side_effect=mock_search)
        
        # Test top_k=3 limits to 3 results
        results = await query_interface.query("test", top_k=3)
        assert len(results) == 3
        
        # Test top_k=5 limits to 5 results
        results = await query_interface.query("test", top_k=5)
        assert len(results) == 5


