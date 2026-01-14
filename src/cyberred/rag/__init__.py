"""RAG Escalation Layer Module.

Implements local vector storage using LanceDB and ATT&CK-BERT embeddings (FR80).
"""
from cyberred.rag.store import RAGStore
from cyberred.rag.models import RAGChunk, RAGSearchResult, RAGStoreStats, ContentType, Tactic
from cyberred.rag.embeddings import RAGEmbeddings
from cyberred.rag.query import RAGQueryInterface
from cyberred.rag.scheduler import RAGScheduler
from cyberred.rag.exceptions import RAGQueryTimeout
from cyberred.rag.director_client import DirectorRAGClient, StrategyPivotResult, RAGQueryContext
from cyberred.rag.ingest import (
    RAGIngestPipeline,
    DocumentChunker,
    MarkdownCodeBlockSplitter,
    IngestionProgress,
    IngestionStats,
)

__all__ = [
    "RAGStore",
    "RAGChunk",
    "RAGSearchResult",
    "RAGStoreStats",
    "ContentType",
    "Tactic",  # Story 6.13: ATT&CK tactics enum
    "RAGEmbeddings",
    "RAGQueryInterface",
    "RAGScheduler",
    "RAGQueryTimeout",
    # Story 6.9: Director Ensemble RAG Integration
    "DirectorRAGClient",
    "StrategyPivotResult",
    "RAGQueryContext",
    # Story 6.4: Document Ingestion Pipeline
    "RAGIngestPipeline",
    "DocumentChunker",
    "MarkdownCodeBlockSplitter",
    "IngestionProgress",
    "IngestionStats",
]
