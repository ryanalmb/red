from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
import json
from datetime import datetime


class ContentType(str, Enum):
    """Content type classification for RAG chunks."""
    METHODOLOGY = "methodology"
    PAYLOAD = "payload"
    CHEATSHEET = "cheatsheet"


class Tactic(str, Enum):
    """MITRE ATT&CK Enterprise tactics (kill chain phases).
    
    The 14 ATT&CK Enterprise tactics in kill chain order.
    Values use lowercase with hyphens to match ATT&CK STIX format.
    """
    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource-development"
    INITIAL_ACCESS = "initial-access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege-escalation"
    DEFENSE_EVASION = "defense-evasion"
    CREDENTIAL_ACCESS = "credential-access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral-movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command-and-control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"

@dataclass
class RAGChunk:
    """A chunk of content for RAG storage and retrieval.
    
    Attributes:
        id: Unique identifier for the chunk.
        text: The text content of the chunk.
        source: Source name (e.g., "mitre_attack", "hacktricks").
        technique_ids: List of ATT&CK technique IDs (T#### or T####.###).
        tactics: List of ATT&CK tactics/kill chain phases (e.g., "lateral-movement").
        content_type: Type of content (METHODOLOGY, PAYLOAD, CHEATSHEET).
        metadata: Additional metadata as key-value pairs.
        embedding: Optional embedding vector (768 dimensions for ATT&CK-BERT).
    """
    id: str
    text: str
    source: str
    technique_ids: List[str]
    content_type: ContentType
    metadata: Dict[str, Any]
    tactics: List[str] = field(default_factory=list)
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
        
        # Handle backward compatibility: tactics defaults to empty list if missing
        tactics = data.get("tactics", [])
        if tactics is None:
            tactics = []
            
        return cls(
            id=data["id"],
            text=data["text"],
            source=data["source"],
            technique_ids=data["technique_ids"],
            content_type=ContentType(data["content_type"]),
            metadata=metadata,
            tactics=tactics,
            embedding=data.get("embedding")
        )

@dataclass
class RAGSearchResult:
    """Result from semantic search.
    
    Implements FR83: Returns methodology with metadata (source, date, technique IDs).
    Implements FR84: Includes ATT&CK tactics for kill chain phase correlation.
    
    Attributes:
        id: Unique identifier for the result.
        text: The text content.
        source: Source name (e.g., "mitre_attack").
        technique_ids: List of ATT&CK technique IDs.
        tactics: List of ATT&CK tactics/kill chain phases.
        content_type: Type of content.
        metadata: Additional metadata.
        score: Relevance score (0.0 to 1.0, higher is more relevant).
        last_updated: Timestamp when the source was last updated.
    """
    id: str
    text: str
    source: str
    technique_ids: List[str]
    content_type: ContentType
    metadata: Dict[str, Any]
    score: float
    tactics: List[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if hasattr(self.content_type, 'value'):
            data['content_type'] = self.content_type.value
        # Convert datetime to ISO string for serialization
        if self.last_updated:
            data['last_updated'] = self.last_updated.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGSearchResult":
        # Handle backward compatibility: tactics defaults to empty list
        tactics = data.get("tactics", [])
        if tactics is None:
            tactics = []
        
        # Parse last_updated from ISO string or datetime
        last_updated = data.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        
        return cls(
            id=data["id"],
            text=data["text"],
            source=data["source"],
            technique_ids=data["technique_ids"],
            content_type=ContentType(data["content_type"]),
            metadata=data.get("metadata", {}),
            score=data["score"],
            tactics=tactics,
            last_updated=last_updated
        )

@dataclass
class RAGStoreStats:
    total_vectors: int
    storage_size_bytes: int
    sources: List[str]
    last_updated: Optional[datetime]
    source_counts: Dict[str, int] = field(default_factory=dict)
