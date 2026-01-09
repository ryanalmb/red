"""Integration tests for RAG embeddings."""
import pytest
import time
from cyberred.rag.embeddings import RAGEmbeddings

@pytest.mark.integration
def test_embedding_latency_under_100ms() -> None:
    """Gate check: embedding latency must be <100ms on CPU."""
    embeddings = RAGEmbeddings()
    test_query = "lateral movement techniques for Windows Server 2022"
    
    # Warm up (model loading)
    _ = embeddings.encode(test_query)
    
    # Benchmark
    start = time.perf_counter()
    iterations = 10
    for _ in range(iterations):
        _ = embeddings.encode(test_query)
        
    elapsed_ms = ((time.perf_counter() - start) / iterations) * 1000
    
    # Gate: 100ms
    # Note: On CI/CD this might vary, but we want a target.
    # We can relax it or log it. The requirement says <100ms.
    assert elapsed_ms < 100, f"Latency {elapsed_ms:.1f}ms exceeds 100ms gate"

@pytest.mark.integration
async def test_embeddings_integration_with_store(tmp_path) -> None:
    """Embeddings work with RAGStore search."""
    from cyberred.rag.store import RAGStore
    from cyberred.rag.models import RAGChunk, ContentType
    
    # Setup
    store_path = tmp_path / "rag_store"
    store = RAGStore(str(store_path))
    embeddings = RAGEmbeddings()
    
    # Generate embedding
    text = "PowerShell execution policy bypass"
    vector = embeddings.encode(text)
    
    # Store chunk
    chunk = RAGChunk(
        id="test:1",
        text=text,
        source="test",
        technique_ids=["T1059.001"],
        content_type=ContentType.METHODOLOGY,
        metadata={},
        embedding=vector
    )
    await store.add([chunk])
    
    # Search
    results = await store.search(vector, top_k=1)
    
    assert len(results) == 1
    assert results[0].id == "test:1"
    # Score should be close to 1.0 (exact match)
    assert results[0].score > 0.99
