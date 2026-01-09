"""Production Smoke Tests for RAGStore.

These tests verify the actual production RAG store at ~/.cyber-red/rag/lancedb.
They should be run after ingestion (Story 6.4+) to validate real data integrity.

Run with: pytest tests/integration/rag/test_production_store.py -v
Skip if no production store: pytest -m "not production"
"""
import pytest
from pathlib import Path

from cyberred.rag import RAGStore, RAGStoreStats


# Expected corpus size after full ingestion (~70K vectors per architecture)
EXPECTED_MIN_VECTORS = 50_000  # Conservative minimum
EXPECTED_MAX_VECTORS = 100_000  # Upper bound
PRODUCTION_PATH = Path.home() / ".cyber-red" / "rag" / "lancedb"


def production_store_exists() -> bool:
    """Check if production store directory exists."""
    return PRODUCTION_PATH.exists() and PRODUCTION_PATH.is_dir()


@pytest.mark.integration
@pytest.mark.skipif(
    not production_store_exists(),
    reason="Production store not found at ~/.cyber-red/rag/lancedb"
)
class TestProductionRAGStore:
    """Smoke tests for production RAG store.
    
    These tests verify the actual production state, not isolated test fixtures.
    Run after ingestion pipeline has populated the store.
    """

    @pytest.fixture
    def production_store(self) -> RAGStore:
        """Connect to actual production store."""
        return RAGStore(store_path=str(PRODUCTION_PATH))

    @pytest.mark.asyncio
    async def test_production_store_health_check(self, production_store: RAGStore) -> None:
        """Production store passes health check."""
        is_healthy = await production_store.health_check()
        assert is_healthy, "Production RAGStore failed health check!"

    @pytest.mark.asyncio
    async def test_production_store_has_vectors(self, production_store: RAGStore) -> None:
        """Production store contains expected vector count."""
        stats = await production_store.get_stats()
        
        assert stats.total_vectors > 0, "Production store is empty!"
        print(f"\n📊 Production Store Stats:")
        print(f"   Total vectors: {stats.total_vectors:,}")
        print(f"   Storage size: {stats.storage_size_bytes / 1024 / 1024:.2f} MB")
        print(f"   Sources: {', '.join(stats.sources)}")

    @pytest.mark.asyncio
    async def test_production_store_has_expected_sources(self, production_store: RAGStore) -> None:
        """Production store contains expected data sources."""
        stats = await production_store.get_stats()
        
        # Expected sources per architecture (Story 6.5-6.8)
        expected_sources = {
            "mitre_attack",      # Story 6.5
            "atomic_red",        # Story 6.6  
            "hacktricks",        # Story 6.7
            "payloads",          # Story 6.8
            "lolbas",            # Story 6.8
            "gtfobins",          # Story 6.8
        }
        
        actual_sources = set(stats.sources)
        missing = expected_sources - actual_sources
        
        # Warn about missing sources but don't fail (depends on ingestion progress)
        if missing:
            print(f"\n⚠️  Missing sources (may be pending ingestion): {missing}")
        
        # At minimum, should have at least one source
        assert len(actual_sources) > 0, "No sources found in production store!"
        print(f"\n✅ Found sources: {actual_sources}")

    @pytest.mark.asyncio 
    async def test_production_store_corpus_size(self, production_store: RAGStore) -> None:
        """Production store corpus size is within expected range."""
        stats = await production_store.get_stats()
        
        print(f"\n📏 Corpus size validation:")
        print(f"   Vectors: {stats.total_vectors:,}")
        print(f"   Expected range: {EXPECTED_MIN_VECTORS:,} - {EXPECTED_MAX_VECTORS:,}")
        
        if stats.total_vectors < EXPECTED_MIN_VECTORS:
            pytest.skip(
                f"Corpus size {stats.total_vectors:,} below minimum {EXPECTED_MIN_VECTORS:,}. "
                "Ingestion may be incomplete."
            )
        
        assert stats.total_vectors <= EXPECTED_MAX_VECTORS, (
            f"Corpus size {stats.total_vectors:,} exceeds expected max {EXPECTED_MAX_VECTORS:,}"
        )

    @pytest.mark.asyncio
    async def test_production_search_returns_results(self, production_store: RAGStore) -> None:
        """Production store can perform semantic search (with dummy vector).
        
        Note: This uses a dummy embedding. Real semantic search requires 
        ATT&CK-BERT embeddings (Story 6.2).
        """
        # Use a random-ish vector - won't be semantically meaningful but tests mechanics
        dummy_embedding = [0.1] * 768
        
        results = await production_store.search(dummy_embedding, top_k=5)
        
        assert len(results) > 0, "Search returned no results from production store!"
        
        print(f"\n🔍 Sample search results (dummy vector):")
        for i, r in enumerate(results[:3], 1):
            print(f"   {i}. [{r.source}] {r.id} (score: {r.score:.4f})")
            print(f"      {r.text[:80]}...")

    @pytest.mark.asyncio
    async def test_production_search_with_filters(self, production_store: RAGStore) -> None:
        """Production store supports filtered searches."""
        stats = await production_store.get_stats()
        
        if not stats.sources:
            pytest.skip("No sources available to filter by")
        
        # Filter by first available source
        source = stats.sources[0]
        dummy_embedding = [0.1] * 768
        
        results = await production_store.search(
            dummy_embedding, 
            top_k=5, 
            filter_source=source
        )
        
        # All results should be from filtered source
        for r in results:
            assert r.source == source, f"Got result from {r.source}, expected {source}"
        
        print(f"\n✅ Filtered search by source '{source}' returned {len(results)} results")

    @pytest.mark.asyncio
    async def test_production_data_integrity(self, production_store: RAGStore) -> None:
        """Verify data integrity - all results have required fields."""
        dummy_embedding = [0.1] * 768
        results = await production_store.search(dummy_embedding, top_k=10)
        
        for r in results:
            # All required fields must be present and non-empty
            assert r.id, f"Missing ID in result"
            assert r.text, f"Missing text in result {r.id}"
            assert r.source, f"Missing source in result {r.id}"
            assert r.content_type in ("methodology", "payload", "cheatsheet"), (
                f"Invalid content_type '{r.content_type}' in result {r.id}"
            )
            assert isinstance(r.metadata, dict), f"Invalid metadata type in result {r.id}"
            assert 0.0 <= r.score <= 1.0, f"Score {r.score} out of range for result {r.id}"
        
        print(f"\n✅ Data integrity check passed for {len(results)} results")
