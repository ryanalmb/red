import pytest
from cyberred.rag.models import RAGSearchResult, ContentType

@pytest.mark.unit
class TestRAGSearchResultEnhancement:
    """Tests for RAGSearchResult enhancements (Story 6.3)."""

    def test_content_type_is_enum(self) -> None:
        """RAGSearchResult.content_type should be of type ContentType."""
        result = RAGSearchResult(
            id="1",
            text="text",
            source="source",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.9
        )
        assert isinstance(result.content_type, ContentType)
        assert result.content_type == ContentType.METHODOLOGY

    def test_to_dict_serializes_enum(self) -> None:
        """RAGSearchResult.to_dict() should serialize ContentType enum to string."""
        result = RAGSearchResult(
            id="1",
            text="text",
            source="source",
            technique_ids=[],
            content_type=ContentType.PAYLOAD,
            metadata={},
            score=0.9
        )
        data = result.to_dict()
        assert data["content_type"] == "payload"
        assert type(data["content_type"]) is str

    def test_from_dict_deserializes_enum(self) -> None:
        """RAGSearchResult.from_dict() should deserialize string to ContentType enum."""
        data = {
            "id": "1",
            "text": "text",
            "source": "source",
            "technique_ids": [],
            "content_type": "payload",
            "metadata": {},
            "score": 0.9
        }
        result = RAGSearchResult.from_dict(data)
        assert result.content_type == ContentType.PAYLOAD
        assert isinstance(result.content_type, ContentType)
