"""RAG Escalation Layer Module.

Implements local vector storage using LanceDB and ATT&CK-BERT embeddings (FR80).
"""
from cyberred.rag.store import RAGStore
from cyberred.rag.models import RAGChunk, RAGSearchResult, RAGStoreStats, ContentType
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.query import RAGQueryInterface
from cyberred.rag.exceptions import RAGQueryTimeout

__all__ = [
    "RAGStore",
    "RAGChunk",
    "RAGSearchResult",
    "RAGStoreStats",
    "ContentType",
    "RAGEmbeddings",
    "RAGQueryInterface",
    "RAGQueryTimeout",
]
