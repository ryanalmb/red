import pytest
from dataclasses import asdict
from cyberred.rag.models import RAGChunk, ContentType

@pytest.mark.unit
class TestRAGChunk:
    """Tests for RAGChunk dataclass."""

    def test_instantiation(self) -> None:
        """RAGChunk can be instantiated with required fields."""
        chunk = RAGChunk(
            id="mitre:T1059:0",
            text="PowerShell usage...",
            source="mitre_attack",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={"version": "1.0"},
            embedding=[0.1] * 768
        )
        
        assert chunk.id == "mitre:T1059:0"
        assert chunk.text == "PowerShell usage..."
        assert chunk.source == "mitre_attack"
        assert chunk.technique_ids == ["T1059"]
        assert chunk.content_type == ContentType.METHODOLOGY
        assert chunk.metadata == {"version": "1.0"}
        assert len(chunk.embedding) == 768

    def test_instantiation_without_embedding(self) -> None:
        """RAGChunk optional embedding field."""
        chunk = RAGChunk(
            id="test:1",
            text="Processing...",
            source="test",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={}
        )
        assert chunk.embedding is None

    def test_to_dict(self) -> None:
        """RAGChunk.to_dict() produces valid dict for LanceDB."""
        chunk = RAGChunk(
            id="test:1",
            text="foo",
            source="test",
            technique_ids=["T1234"],
            content_type=ContentType.CHEATSHEET,
            metadata={"k": "v"},
            embedding=[0.5] * 768
        )
        
        data = chunk.to_dict()
        assert data["id"] == "test:1"
        assert data["text"] == "foo"
        assert data["technique_ids"] == ["T1234"]
        assert data["content_type"] == "cheatsheet"  # Enum value
        assert data["metadata"] == '{"k": "v"}'  # JSON stringified for LanceDB? 
        # Wait, requirements didn't specify JSON stringified metadata for to_dict, 
        # but 2A Task 2.1 schema says "metadata: string (JSON serialized)". 
        # So to_dict should probably verify that? 
        # Let's assume to_dict handles the serialization or returns a dict that LanceDB needs.
        # However, typically LanceDB can handle dicts if schema is defined properly?
        # But schema in 2A says `metadata: string`. So yes, stringified.
        
    def test_from_dict(self) -> None:
        """RAGChunk.from_dict() reconstructs object."""
        data = {
            "id": "test:2",
            "text": "bar",
            "source": "test",
            "technique_ids": ["T5678"],
            "content_type": "payload",
            "metadata": '{"key": "value"}',
            "embedding": [0.9] * 768
        }
        
        chunk = RAGChunk.from_dict(data)
        assert chunk.id == "test:2"
        assert chunk.content_type == ContentType.PAYLOAD
        assert chunk.metadata == {"key": "value"}
        assert chunk.embedding[0] == 0.9

    def test_post_init_validation(self) -> None:
        """RAGChunk validates input in __post_init__."""
        # Test empty text
        with pytest.raises(ValueError, match="Text cannot be empty"):
            RAGChunk(
                id="id",
                text="",
                source="source",
                technique_ids=[],
                content_type=ContentType.METHODOLOGY,
                metadata={}
            )

    def test_post_init_empty_id_validation(self) -> None:
        """RAGChunk validates empty ID in __post_init__."""
        with pytest.raises(ValueError, match="ID cannot be empty"):
            RAGChunk(
                id="",
                text="some text",
                source="source",
                technique_ids=[],
                content_type=ContentType.METHODOLOGY,
                metadata={}
            )

    def test_from_dict_with_dict_metadata(self) -> None:
        """RAGChunk.from_dict handles metadata that's already a dict."""
        data = {
            "id": "test:3",
            "text": "baz",
            "source": "test",
            "technique_ids": [],
            "content_type": "methodology",
            "metadata": {"already": "dict"},  # Not a string
            "embedding": None
        }
        
        chunk = RAGChunk.from_dict(data)
        assert chunk.metadata == {"already": "dict"}

    def test_search_result(self) -> None:
        """RAGSearchResult contains all required fields."""
        # Note: Importing RAGSearchResult locally to allow test execution fail if missing
        from cyberred.rag.models import RAGSearchResult
        
        result = RAGSearchResult(
            id="1",
            text="foo",
            source="src",
            technique_ids=[],
            content_type="payload",
            metadata={},
            score=0.95
        )
        assert result.score == 0.95
        assert result.id == "1"

    def test_search_result_to_dict(self) -> None:
        """RAGSearchResult.to_dict() returns correct dict."""
        from cyberred.rag.models import RAGSearchResult
        
        result = RAGSearchResult(
            id="test-id",
            text="test text",
            source="test_source",
            technique_ids=["T1234"],
            content_type="methodology",
            metadata={"key": "value"},
            score=0.85
        )
        
        d = result.to_dict()
        assert d["id"] == "test-id"
        assert d["text"] == "test text"
        assert d["source"] == "test_source"
        assert d["technique_ids"] == ["T1234"]
        assert d["content_type"] == "methodology"
        assert d["metadata"] == {"key": "value"}
        assert d["score"] == 0.85
