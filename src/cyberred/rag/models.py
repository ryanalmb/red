from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
import json

class ContentType(str, Enum):
    METHODOLOGY = "methodology"
    PAYLOAD = "payload"
    CHEATSHEET = "cheatsheet"

from datetime import datetime

@dataclass
class RAGChunk:
    id: str
    text: str
    source: str
    technique_ids: List[str]
    content_type: ContentType
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Text cannot be empty")
        if not self.id:
            raise ValueError("ID cannot be empty")
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LanceDB storage."""
        data = asdict(self)
        # Convert Enum to string
        data['content_type'] = self.content_type.value
        # Serialize metadata to JSON string for LanceDB schema compliance
        data['metadata'] = json.dumps(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGChunk":
        """Create from LanceDB dictionary."""
        # Handle stringified metadata
        metadata = data.get("metadata", "{}")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
            
        return cls(
            id=data["id"],
            text=data["text"],
            source=data["source"],
            technique_ids=data["technique_ids"],
            content_type=ContentType(data["content_type"]),
            metadata=metadata,
            embedding=data.get("embedding")
        )

@dataclass
class RAGSearchResult:
    """Result from semantic search.
    
    Implements FR83: Returns methodology with metadata (source, date, technique IDs).
    """
    id: str
    text: str
    source: str
    technique_ids: List[str]
    content_type: ContentType
    metadata: Dict[str, Any]
    score: float

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if hasattr(self.content_type, 'value'):
            data['content_type'] = self.content_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGSearchResult":
        return cls(
            id=data["id"],
            text=data["text"],
            source=data["source"],
            technique_ids=data["technique_ids"],
            content_type=ContentType(data["content_type"]),
            metadata=data.get("metadata", {}),
            score=data["score"]
        )

@dataclass
class RAGStoreStats:
    total_vectors: int
    storage_size_bytes: int
    sources: List[str]
    last_updated: Optional[datetime]
    source_counts: Dict[str, int] = field(default_factory=dict)
