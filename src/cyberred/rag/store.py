import lancedb
import pyarrow as pa
import structlog
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime
from cyberred.rag.models import RAGChunk, RAGSearchResult, RAGStoreStats

log = structlog.get_logger()

class RAGStore:
    EMBEDDING_DIM = 768
    TABLE_NAME = "chunks"
    
    def __init__(self, store_path: Optional[str] = None, embedding_dim: int = 768) -> None:
        """Initialize the RAG store.
        
        Args:
            store_path: Path to the LanceDB store directory.
            embedding_dim: Dimension of embeddings (default: 768).
        """
        self.embedding_dim = embedding_dim
        self._store_path = Path(store_path or "~/.cyber-red/rag/lancedb").expanduser()
        self._store_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._store_path))
        self._ensure_table()
        
    def _ensure_table(self) -> None:
        """Ensure the chunks table exists with correct schema."""
        if self.TABLE_NAME in self._db.table_names():
            return
            
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("source", pa.string()),
            pa.field("technique_ids", pa.list_(pa.string())),
            pa.field("content_type", pa.string()),
            pa.field("metadata", pa.string()), # JSON serialized
            pa.field("embedding", pa.list_(pa.float32(), self.embedding_dim))
        ])
        
        self._db.create_table(self.TABLE_NAME, schema=schema)

    async def health_check(self) -> bool:
        """Verify store is accessible and valid.
        
        Returns:
            True if store is operational, False otherwise.
        """
        try:
            # Verify table exists and is queryable
            table = self._db.open_table(self.TABLE_NAME)
            # Force table access to ensure connectivity
            _ = len(table)
            return True
        except Exception as e:
            log.warning("rag_store_health_check_failed", error=str(e))
            return False

    async def add(self, chunks: List[RAGChunk]) -> int:
        """Add or update chunks in the store.
        
        Args:
            chunks: List of RAGChunk objects with embeddings set
            
        Returns:
            Number of chunks added/updated
            
        Raises:
            ValueError: If a chunk is missing expected embedding
        """
        if not chunks:
            return 0
            
        # Validate all chunks have embeddings
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk {chunk.id} missing embedding")
                
        if len(chunks) > 100:
            log.info("rag_store_upsert_start", count=len(chunks))

        table = self._db.open_table(self.TABLE_NAME)
        data = [chunk.to_dict() for chunk in chunks]
        
        table.merge_insert("id") \
             .when_matched_update_all() \
             .when_not_matched_insert_all() \
             .execute(data)
             
        return len(chunks)

    async def search(
        self, 
        embedding: List[float], 
        top_k: int = 5,
        filter_source: Optional[str] = None,
        filter_content_type: Optional[str] = None,
    ) -> List[RAGSearchResult]:
        """Search for similar chunks.
        
        Args:
            embedding: Query embedding vector
            top_k: Number of results to return
            filter_source: Optional source filter
            filter_content_type: Optional content type filter
            
        Returns:
            List of RAGSearchResult sorted by relevance (highest first)
        """
        # If table doesn't exist or is empty, return empty list
        if self.TABLE_NAME not in self._db.table_names():
            return []
        
        try:     
            table = self._db.open_table(self.TABLE_NAME)
            if len(table) == 0:
                return []
                
            # We use cosine distance for similarity search (1 - cosine_sim)
            query = table.search(embedding, query_type="vector").metric("cosine")
            
            where_clauses = []
            if filter_source:
                where_clauses.append(f"source = '{filter_source}'")
            if filter_content_type:
                where_clauses.append(f"content_type = '{filter_content_type}'")
                
            if where_clauses:
                query = query.where(" AND ".join(where_clauses))
                
            query = query.limit(top_k)
            
            results = query.to_arrow().to_pylist()
            
            output = []
            for r in results:
                # Metadata is stored as JSON string, need to parse back
                meta = r.get("metadata", "{}")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                
                # _distance is returned by default for vector search
                # For cosine metric, distance = 1 - similarity.
                dist = r.get("_distance", 1.0)
                score = 1.0 - dist
                 
                output.append(RAGSearchResult(
                    id=r["id"],
                    text=r["text"],
                    source=r["source"],
                    technique_ids=r["technique_ids"],
                    content_type=r["content_type"],
                    metadata=meta,
                    score=score
                ))
                
            return output
            
        except Exception as e:
            log.error("rag_store_search_error", error=str(e))
            return []

    async def get_stats(self) -> RAGStoreStats:
        """Get store statistics for TUI display."""
        if self.TABLE_NAME not in self._db.table_names():
            return RAGStoreStats(0, 0, [], datetime.now())
            
        table = self._db.open_table(self.TABLE_NAME)
        total_vectors = len(table)
        
        # Calculate size roughly or check dir size?
        # Using directory size is more accurate for "storage_size_bytes"
        size_bytes = sum(f.stat().st_size for f in self._store_path.glob('**/*') if f.is_file())
        
        # Get unique sources
        # LanceDB doesn't have a distinct query easily accessible via python API without loading?
        # we can use duckdb integration if available, or just pyarrow
        # For small corpus (70k), a full scan of just source column is okay-ish.
        # But `table.to_pandas()` requires pandas. `table.to_arrow()` works.
        
        try:
            # Efficiently query only the source column
            t = table.search().select(["source"]).to_arrow()
            sources_list = t["source"].to_pylist()
            unique_sources = sorted(list(set(sources_list)))
            
            source_counts = {}
            for s in sources_list:
                source_counts[s] = source_counts.get(s, 0) + 1
                
        except Exception:
            unique_sources = []
            source_counts = {}
            
        return RAGStoreStats(
            total_vectors=total_vectors,
            storage_size_bytes=size_bytes,
            sources=unique_sources,
            last_updated=datetime.now(),
            source_counts=source_counts
        )
