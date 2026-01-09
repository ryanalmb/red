"""Document Ingestion Pipeline for RAG Layer.

Implements document chunking, embedding, and storage for the RAG escalation layer (FR77).
"""
import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

from cyberred.rag.models import ContentType, RAGChunk

log = structlog.get_logger()


@dataclass
class IngestionProgress:
    """Progress tracking for ingestion pipeline (FR77).
    
    Used for TUI display via callback during document processing.
    """
    source: str
    current_doc: int
    total_docs: int
    chunks_processed: int


@dataclass
class IngestionStats:
    """Ingestion statistics for a source (FR77).
    
    Tracks ingestion results and file hashes for incremental updates.
    """
    source: str
    last_updated: datetime
    chunk_count: int
    document_count: int
    file_hashes: Dict[str, str]
    failed_docs: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        data = asdict(self)
        data["last_updated"] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionStats":
        """Deserialize from dictionary."""
        return cls(
            source=data["source"],
            last_updated=datetime.fromisoformat(data["last_updated"]),
            chunk_count=data["chunk_count"],
            document_count=data["document_count"],
            file_hashes=data.get("file_hashes", {}),
            failed_docs=data.get("failed_docs", []),
        )


class MarkdownCodeBlockSplitter:
    """Splits markdown preserving code block integrity (AC: 6).
    
    Ensures code blocks (``` ... ```) are never split, even if oversized.
    """

    # Regex to match fenced code blocks (``` or ~~~)
    CODE_BLOCK_PATTERN = re.compile(
        r"(```[\s\S]*?```|~~~[\s\S]*?~~~)", 
        re.MULTILINE
    )

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split_preserving_code_blocks(self, markdown: str) -> List[str]:
        """Split markdown preserving code block integrity.
        
        Args:
            markdown: Markdown text to split
            
        Returns:
            List of text segments with code blocks intact
        """
        # Find all code blocks and their positions
        segments: List[str] = []
        last_end = 0
        
        for match in self.CODE_BLOCK_PATTERN.finditer(markdown):
            # Add text before this code block (chunked normally)
            text_before = markdown[last_end:match.start()]
            if text_before.strip():
                segments.extend(self._chunk_text(text_before))
            
            # Add the code block as a single segment (never split)
            code_block = match.group()
            segments.append(code_block)
            
            last_end = match.end()
        
        # Add any remaining text after the last code block
        remaining = markdown[last_end:]
        if remaining.strip():
            segments.extend(self._chunk_text(remaining))
        
        # If no segments, return original as single segment
        if not segments:
            return [markdown] if markdown.strip() else []
        
        return segments

    def _chunk_text(self, text: str) -> List[str]:
        """Chunk regular text using token-based splitting."""
        words = text.split()
        if len(words) <= self._chunk_size:
            return [text]
        
        chunks: List[str] = []
        current_start = 0
        
        while current_start < len(words):
            end = min(current_start + self._chunk_size, len(words))
            chunk = " ".join(words[current_start:end])
            chunks.append(chunk)
            
            # Move forward with overlap
            current_start = end - self._overlap if end < len(words) else end
        
        return chunks


class DocumentChunker:
    """Chunks documents for RAG ingestion (AC: 3).
    
    Uses recursive character text splitting with configurable chunk size and overlap.
    Preserves code blocks using MarkdownCodeBlockSplitter for markdown content.
    """

    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_OVERLAP = 50

    def __init__(
        self, 
        chunk_size: int = DEFAULT_CHUNK_SIZE, 
        overlap: int = DEFAULT_OVERLAP
    ) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._markdown_splitter = MarkdownCodeBlockSplitter(chunk_size, overlap)

    def chunk_document(
        self,
        text: str,
        source: str,
        content_type: ContentType = ContentType.METHODOLOGY,
        technique_ids: Optional[List[str]] = None,
    ) -> List[RAGChunk]:
        """Split document into chunks with metadata.
        
        Args:
            text: Document text to chunk
            source: Source identifier (e.g., "hacktricks", "mitre_attack")
            content_type: ContentType enum for these chunks
            technique_ids: Optional list of ATT&CK technique IDs
            
        Returns:
            List of RAGChunk objects ready for embedding
        """
        if not text or not text.strip():
            return []
        
        technique_ids = technique_ids or []
        
        # Check if markdown (has code blocks)
        if "```" in text or "~~~" in text:
            segments = self._markdown_splitter.split_preserving_code_blocks(text)
        else:
            segments = self._split_recursive(text)
        
        # Convert segments to RAGChunks
        chunks: List[RAGChunk] = []
        for i, segment in enumerate(segments):
            if not segment.strip():
                continue
                
            chunk_id = self._generate_chunk_id(source, segment, i)
            chunk = RAGChunk(
                id=chunk_id,
                text=segment,
                source=source,
                technique_ids=technique_ids.copy(),
                content_type=content_type,
                metadata={"chunk_index": i},
            )
            chunks.append(chunk)
        
        log.debug(
            "rag_document_chunked",
            source=source,
            chunks=len(chunks),
            content_type=content_type.value,
        )
        
        return chunks

    def _split_recursive(self, text: str) -> List[str]:
        """Recursively split text using paragraph, sentence, word boundaries."""
        # Try paragraph split first
        paragraphs = text.split("\n\n")
        if len(paragraphs) > 1:
            return self._merge_to_chunk_size(paragraphs)
        
        # Try sentence split
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) > 1:
            return self._merge_to_chunk_size(sentences)
        
        # Fall back to word split
        words = text.split()
        if len(words) <= self._chunk_size:
            return [text]
        
        return self._chunk_by_words(words)

    def _merge_to_chunk_size(self, parts: List[str]) -> List[str]:
        """Merge small parts into chunks respecting chunk_size."""
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_size = 0
        
        for part in parts:
            part_size = len(part.split())
            
            if current_size + part_size > self._chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Keep overlap
                overlap_parts = current_chunk[-(self._overlap // 20):] if self._overlap else []
                current_chunk = overlap_parts
                current_size = sum(len(p.split()) for p in current_chunk)
            
            current_chunk.append(part)
            current_size += part_size
        
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        return chunks

    def _chunk_by_words(self, words: List[str]) -> List[str]:
        """Chunk by word count with overlap."""
        chunks: List[str] = []
        current_start = 0
        
        while current_start < len(words):
            end = min(current_start + self._chunk_size, len(words))
            chunk = " ".join(words[current_start:end])
            chunks.append(chunk)
            current_start = end - self._overlap if end < len(words) else end
        
        return chunks

    def _generate_chunk_id(self, source: str, text: str, index: int) -> str:
        """Generate deterministic chunk ID for upsert behavior."""
        content = f"{source}:{text[:100]}:{index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class RawDocument:
    """Type hint for raw document input."""
    text: str
    metadata: Dict[str, Any]


class RAGIngestPipeline:
    """Document ingestion pipeline for RAG layer (FR77).
    
    Processes documents through chunking, embedding, and storage.
    Supports incremental ingestion and progress tracking.
    """

    def __init__(
        self,
        store: "RAGStore",  # type: ignore
        embeddings: "RAGEmbeddings",  # type: ignore
    ) -> None:
        """Initialize the ingestion pipeline.
        
        Args:
            store: RAGStore instance for vector storage
            embeddings: RAGEmbeddings instance for text encoding
        """
        self._store = store
        self._embeddings = embeddings
        self._chunker = DocumentChunker()

    async def process(
        self,
        source: str,
        documents: List[Dict[str, Any]],
        content_type: ContentType = ContentType.METHODOLOGY,
        incremental: bool = False,
        progress_callback: Optional[Callable[[IngestionProgress], None]] = None,
    ) -> IngestionStats:
        """Process documents through ingestion pipeline.
        
        Args:
            source: Source identifier (e.g., "hacktricks", "mitre_attack")
            documents: List of {text: str, metadata: dict} documents
            content_type: ContentType enum for these documents
            incremental: If True, skip unchanged files based on hash
            progress_callback: Optional callback for progress updates
            
        Returns:
            IngestionStats with processing results
        """
        log.info(
            "rag_ingest_start",
            source=source,
            doc_count=len(documents),
            incremental=incremental,
        )

        # Load previous stats if incremental
        prev_stats = self._load_stats(source) if incremental else None
        prev_hashes = prev_stats.file_hashes if prev_stats else {}

        all_chunks: List[RAGChunk] = []
        file_hashes: Dict[str, str] = {}
        failed_docs: List[str] = []
        total_docs = len(documents)
        processed_count = 0

        for i, doc in enumerate(documents):
            doc_id = doc.get("metadata", {}).get("id", str(i))
            text = doc.get("text", "")
            
            # Compute hash for incremental
            doc_hash = self._compute_hash(text)
            file_hashes[doc_id] = doc_hash

            # Skip if unchanged and incremental
            if incremental and prev_hashes.get(doc_id) == doc_hash:
                log.debug("rag_ingest_skip_unchanged", doc_id=doc_id)
                processed_count += 1
                if progress_callback:
                    progress_callback(IngestionProgress(
                        source=source,
                        current_doc=processed_count,
                        total_docs=total_docs,
                        chunks_processed=len(all_chunks),
                    ))
                continue

            try:
                # Extract technique IDs from metadata
                technique_ids = doc.get("metadata", {}).get("technique_ids", [])
                if isinstance(technique_ids, str):
                    technique_ids = [technique_ids]

                # Chunk the document
                chunks = self._chunker.chunk_document(
                    text=text,
                    source=source,
                    content_type=content_type,
                    technique_ids=technique_ids,
                )
                all_chunks.extend(chunks)
                processed_count += 1

            except Exception as e:
                log.error("rag_ingest_doc_failed", doc_id=doc_id, error=str(e))
                failed_docs.append(doc_id)

            # Progress callback
            if progress_callback:
                progress_callback(IngestionProgress(
                    source=source,
                    current_doc=processed_count,
                    total_docs=total_docs,
                    chunks_processed=len(all_chunks),
                ))

        # Embed all chunks in batch
        if all_chunks:
            texts = [c.text for c in all_chunks]
            embeddings = self._embeddings.encode_batch(texts)
            for chunk, embedding in zip(all_chunks, embeddings):
                chunk.embedding = embedding

            # Store chunks (upsert behavior handled by store)
            await self._store.add(all_chunks)

        # Create stats
        stats = IngestionStats(
            source=source,
            last_updated=datetime.now(),
            chunk_count=len(all_chunks),
            document_count=processed_count,
            file_hashes=file_hashes,
            failed_docs=failed_docs,
        )

        # Save stats for incremental support
        self._save_stats(stats)

        log.info(
            "rag_ingest_complete",
            source=source,
            chunks=len(all_chunks),
            documents=processed_count,
            failed=len(failed_docs),
        )

        return stats

    def _compute_hash(self, text: str) -> str:
        """Compute SHA-256 hash of document text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _load_stats(self, source: str) -> Optional[IngestionStats]:
        """Load previous ingestion stats for source."""
        import json
        from pathlib import Path

        stats_path = self._get_stats_path(source)
        if stats_path.exists():
            try:
                with open(stats_path, "r") as f:
                    data = json.load(f)
                return IngestionStats.from_dict(data)
            except Exception as e:
                log.warning("rag_stats_load_failed", source=source, error=str(e))
        return None

    def _save_stats(self, stats: IngestionStats) -> None:
        """Persist ingestion stats for incremental support."""
        import json
        from pathlib import Path

        stats_path = self._get_stats_path(stats.source)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(stats_path, "w") as f:
                json.dump(stats.to_dict(), f, indent=2)
        except Exception as e:
            log.warning("rag_stats_save_failed", source=stats.source, error=str(e))

    def _get_stats_path(self, source: str) -> "Path":
        """Get path for stats file."""
        from pathlib import Path
        
        # Store alongside the LanceDB database
        if hasattr(self._store, "db_path"):
            base = Path(self._store.db_path).parent
        else:
            base = Path("/tmp/rag_stats")
        
        return base / f".rag_stats_{source}.json"
