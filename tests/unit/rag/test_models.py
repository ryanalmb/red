import pytest
from dataclasses import asdict
from datetime import datetime
from cyberred.rag.models import RAGChunk, RAGSearchResult, ContentType, Tactic


@pytest.mark.unit
class TestTacticEnum:
    """Tests for Tactic enum (Story 6-13)."""

    def test_tactic_count(self) -> None:
        """All 14 ATT&CK Enterprise tactics are defined."""
        assert len(Tactic) == 14

    def test_tactic_values_lowercase_hyphenated(self) -> None:
        """Tactic values use lowercase with hyphens (ATT&CK STIX format)."""
        for tactic in Tactic:
            assert tactic.value == tactic.value.lower()
            assert "_" not in tactic.value  # Uses hyphens not underscores

    def test_expected_tactics(self) -> None:
        """All expected tactics are present."""
        expected = {
            "reconnaissance", "resource-development", "initial-access",
            "execution", "persistence", "privilege-escalation",
            "defense-evasion", "credential-access", "discovery",
            "lateral-movement", "collection", "command-and-control",
            "exfiltration", "impact"
        }
        actual = {t.value for t in Tactic}
        assert actual == expected

    def test_tactic_string_enum(self) -> None:
        """Tactic is a string enum (can be used directly as string)."""
        assert Tactic.LATERAL_MOVEMENT == "lateral-movement"
        assert Tactic.LATERAL_MOVEMENT.value == "lateral-movement"
        assert f"tactic:{Tactic.EXECUTION.value}" == "tactic:execution"


@pytest.mark.unit
class TestRAGChunkTactics:
    """Tests for RAGChunk tactics field (Story 6-13)."""

    def test_chunk_with_tactics(self) -> None:
        """RAGChunk accepts tactics field."""
        chunk = RAGChunk(
            id="test:1",
            text="test content",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["execution", "persistence"]
        )
        assert chunk.tactics == ["execution", "persistence"]

    def test_chunk_default_empty_tactics(self) -> None:
        """RAGChunk defaults to empty tactics list."""
        chunk = RAGChunk(
            id="test:1",
            text="test content",
            source="test",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={}
        )
        assert chunk.tactics == []

    def test_to_dict_includes_tactics(self) -> None:
        """RAGChunk.to_dict() includes tactics field."""
        chunk = RAGChunk(
            id="test:1",
            text="test",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            tactics=["lateral-movement"]
        )
        data = chunk.to_dict()
        assert data["tactics"] == ["lateral-movement"]

    def test_from_dict_with_tactics(self) -> None:
        """RAGChunk.from_dict() handles tactics field."""
        data = {
            "id": "test:1",
            "text": "test",
            "source": "test",
            "technique_ids": ["T1059"],
            "content_type": "methodology",
            "metadata": "{}",
            "tactics": ["execution"],
            "embedding": None
        }
        chunk = RAGChunk.from_dict(data)
        assert chunk.tactics == ["execution"]

    def test_from_dict_missing_tactics_defaults_empty(self) -> None:
        """RAGChunk.from_dict() defaults tactics to empty list if missing."""
        data = {
            "id": "test:1",
            "text": "test",
            "source": "test",
            "technique_ids": ["T1059"],
            "content_type": "methodology",
            "metadata": "{}",
            "embedding": None
            # tactics field missing
        }
        chunk = RAGChunk.from_dict(data)
        assert chunk.tactics == []

    def test_from_dict_null_tactics_defaults_empty(self) -> None:
        """RAGChunk.from_dict() handles null tactics."""
        data = {
            "id": "test:1",
            "text": "test",
            "source": "test",
            "technique_ids": ["T1059"],
            "content_type": "methodology",
            "metadata": "{}",
            "tactics": None,
            "embedding": None
        }
        chunk = RAGChunk.from_dict(data)
        assert chunk.tactics == []


@pytest.mark.unit
class TestRAGSearchResultTactics:
    """Tests for RAGSearchResult tactics and last_updated fields (Story 6-13)."""

    def test_result_with_tactics(self) -> None:
        """RAGSearchResult accepts tactics field."""
        result = RAGSearchResult(
            id="1",
            text="test",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95,
            tactics=["execution", "persistence"]
        )
        assert result.tactics == ["execution", "persistence"]

    def test_result_with_last_updated(self) -> None:
        """RAGSearchResult accepts last_updated field."""
        ts = datetime(2025, 1, 10, 12, 0, 0)
        result = RAGSearchResult(
            id="1",
            text="test",
            source="test",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95,
            last_updated=ts
        )
        assert result.last_updated == ts

    def test_result_default_empty_tactics(self) -> None:
        """RAGSearchResult defaults to empty tactics list."""
        result = RAGSearchResult(
            id="1",
            text="test",
            source="test",
            technique_ids=[],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95
        )
        assert result.tactics == []
        assert result.last_updated is None

    def test_to_dict_includes_tactics_and_last_updated(self) -> None:
        """RAGSearchResult.to_dict() includes new fields."""
        ts = datetime(2025, 1, 10, 12, 0, 0)
        result = RAGSearchResult(
            id="1",
            text="test",
            source="test",
            technique_ids=["T1059"],
            content_type=ContentType.METHODOLOGY,
            metadata={},
            score=0.95,
            tactics=["lateral-movement"],
            last_updated=ts
        )
        data = result.to_dict()
        assert data["tactics"] == ["lateral-movement"]
        assert data["last_updated"] == "2025-01-10T12:00:00"

    def test_from_dict_with_tactics_and_last_updated(self) -> None:
        """RAGSearchResult.from_dict() handles new fields."""
        data = {
            "id": "1",
            "text": "test",
            "source": "test",
            "technique_ids": ["T1059"],
            "content_type": "methodology",
            "metadata": {},
            "score": 0.95,
            "tactics": ["execution"],
            "last_updated": "2025-01-10T12:00:00"
        }
        result = RAGSearchResult.from_dict(data)
        assert result.tactics == ["execution"]
        assert result.last_updated == datetime(2025, 1, 10, 12, 0, 0)

    def test_from_dict_missing_new_fields(self) -> None:
        """RAGSearchResult.from_dict() handles missing new fields."""
        data = {
            "id": "1",
            "text": "test",
            "source": "test",
            "technique_ids": [],
            "content_type": "methodology",
            "metadata": {},
            "score": 0.95
        }
        result = RAGSearchResult.from_dict(data)
        assert result.tactics == []
        assert result.last_updated is None

    def test_from_dict_null_tactics_defaults_empty(self) -> None:
        """RAGSearchResult.from_dict() handles null/None tactics."""
        data = {
            "id": "1",
            "text": "test",
            "source": "test",
            "technique_ids": [],
            "content_type": "methodology",
            "metadata": {},
            "score": 0.95,
            "tactics": None,  # Explicitly null
            "last_updated": None
        }
        result = RAGSearchResult.from_dict(data)
        assert result.tactics == []
        assert result.last_updated is None


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
