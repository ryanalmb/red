from typing import List, Optional
import asyncio
import structlog
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.models import RAGSearchResult, ContentType
from cyberred.rag.exceptions import RAGQueryTimeout

log = structlog.get_logger()

class RAGQueryInterface:
    DEFAULT_TOP_K = 5
    DEFAULT_TIMEOUT = 10.0
    
    def __init__(
        self, 
        store: RAGStore, 
        embeddings: RAGEmbeddings
    ) -> None:
        self._store = store
        self._embeddings = embeddings

    async def query(
        self,
        text: str,
        top_k: int = DEFAULT_TOP_K,
        timeout: float = DEFAULT_TIMEOUT,
        filter_source: Optional[str] = None,
        filter_content_type: Optional[ContentType] = None,
    ) -> List[RAGSearchResult]:
        """Semantic search for methodology retrieval.
        
        Args:
            text: Query text (embedded via ATT&CK-BERT)
            top_k: Maximum results to return (default: 5)
            timeout: Query timeout in seconds (default: 10.0)
            filter_source: Optional filter by source name
            filter_content_type: Optional filter by ContentType enum
            
        Returns:
            List of RAGSearchResult sorted by score descending
            
        Raises:
            RAGQueryTimeout: If query exceeds timeout
        """
        log.info("rag_query_start", query=text[:50], top_k=top_k)
        
        embedding = self._embeddings.encode(text)
        filter_type_str = filter_content_type.value if filter_content_type else None
        
        try:
            results = await asyncio.wait_for(
                self._store.search(
                    embedding=embedding,
                    top_k=top_k,
                    filter_source=filter_source,
                    filter_content_type=filter_type_str
                ),
                timeout=timeout
            )
            log.info("rag_query_complete", result_count=len(results))
            return results
        except asyncio.TimeoutError:
            log.warning("rag_query_timeout", query=text[:50], timeout=timeout)
            raise RAGQueryTimeout(f"Query timed out after {timeout}s")
