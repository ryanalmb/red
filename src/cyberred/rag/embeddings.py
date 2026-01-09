"""RAG Embeddings Module.

Implements ATT&CK-BERT embeddings with fallback to all-mpnet-base-v2.
"""
from typing import Optional, List
import structlog
from sentence_transformers import SentenceTransformer

log = structlog.get_logger()

class RAGEmbeddings:
    """RAG Embeddings generator with fallback support."""
    
    PRIMARY_MODEL = "basel/ATTACK-BERT"
    FALLBACK_MODEL = "sentence-transformers/all-mpnet-base-v2"
    EMBEDDING_DIM = 768
    
    def __init__(self) -> None:
        """Initialize RAG embeddings (lazy loading)."""
        self._model: Optional[SentenceTransformer] = None
        self._model_name: Optional[str] = None
        
    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._model is not None

    @property
    def active_model(self) -> Optional[str]:
        """Return the name of the currently loaded model, or None if not loaded."""
        return self._model_name

    def _load_model(self) -> None:
        """Load embedding model with fallback support."""
        if self.is_loaded:
            return

        try:
            self._model = SentenceTransformer(self.PRIMARY_MODEL, device="cpu")
            self._model_name = self.PRIMARY_MODEL
        except Exception as e:
            log.warning("rag_embeddings_fallback_activated", 
                       primary_model=self.PRIMARY_MODEL, error=str(e))
            self._model = SentenceTransformer(self.FALLBACK_MODEL, device="cpu")
            self._model_name = self.FALLBACK_MODEL

    def encode(self, text: str) -> List[float]:
        """Encode text to embedding vector.
        
        Args:
            text: Text to encode (trimmed to 512 tokens internally)
            
        Returns:
            768-dimensional embedding vector as List[float]
        """
        if not self.is_loaded:
            self._load_model()
            
        # self._model is guaranteed strictly not None by _load_model or logic flow
        # explicit check for mypy
        if self._model is None:  # pragma: no cover
            raise RuntimeError("Failed to load embedding model")

        # Convert to list ensuring strict float type
        embedding = self._model.encode(text, convert_to_numpy=True).tolist()
        return embedding

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts efficiently.
        
        Args:
            texts: List of texts to encode
            
        Returns:
            List of 768-dimensional embedding vectors
        """
        if not texts:
            return []
            
        if not self.is_loaded:
            self._load_model()

        # self._model is guaranteed strictly not None
        if self._model is None:  # pragma: no cover
            raise RuntimeError("Failed to load embedding model")

        if len(texts) > 100:
            log.info("rag_embeddings_batch_start", count=len(texts))

        # Convert to list of lists
        embeddings = self._model.encode(texts, convert_to_numpy=True).tolist()
        return embeddings
