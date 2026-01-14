"""Unit tests for PayloadsAllTheThings source integration.

Story 6.8: PayloadsAllTheThings & LOLBAS/GTFOBins Integration

Tests are focused on parsing/categorization/metadata extraction without network access.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.unit
class TestPayloadsCategoryMapping:
    def test_extract_category_from_path_sql_injection(self) -> None:
        from cyberred.rag.sources.payloads import _extract_category_from_rel_path

        rel = Path("SQL Injection/README.md")
        assert _extract_category_from_rel_path(rel) == "sqli"

    def test_extract_category_from_path_unknown_falls_back_to_general(self) -> None:
        from cyberred.rag.sources.payloads import _extract_category_from_rel_path

        rel = Path("Some Unknown Category/file.md")
        assert _extract_category_from_rel_path(rel) == "general"


@pytest.mark.unit
class TestPayloadsTechniqueExtraction:
    def test_extracts_unique_valid_technique_ids(self) -> None:
        from cyberred.rag.sources.payloads import _extract_technique_ids

        text = "T1059.004 and T1059.004 again plus T1105 and invalid T12 and T99999"
        ids = _extract_technique_ids(text)
        assert ids == ["T1059.004", "T1105"]


@pytest.mark.unit
class TestPayloadsMarkdownParsing:
    def test_parse_markdown_file_creates_document(self) -> None:
        from cyberred.rag.sources.payloads import _parse_markdown_file

        content = "# SQLi\n\nTechnique: T1190\nPayload: ' OR 1=1 --"
        rel_path = Path("SQL Injection/Basic/README.md")
        doc = _parse_markdown_file(content, rel_path)

        assert doc is not None
        assert "text" in doc and "metadata" in doc
        assert doc["metadata"]["category"] == "sqli"
        assert doc["metadata"]["path"] == str(rel_path)
        # Should include technique IDs if present
        assert doc["metadata"].get("technique_ids") == ["T1190"]

    def test_empty_markdown_file_returns_none(self) -> None:
        from cyberred.rag.sources.payloads import _parse_markdown_file

        assert _parse_markdown_file("   \n", Path("SQL Injection/empty.md")) is None


@pytest.mark.unit
class TestPayloadsMoreCoverage:
    def test_validate_technique_id_false_on_empty(self) -> None:
        from cyberred.rag.sources.payloads import validate_technique_id

        assert validate_technique_id("") is False

    def test_extract_category_from_rel_path_empty_parts(self) -> None:
        from cyberred.rag.sources.payloads import _extract_category_from_rel_path

        assert _extract_category_from_rel_path(Path()) == "general"


    def test_parse_markdown_file_without_technique_ids_has_no_key(self) -> None:
        from cyberred.rag.sources.payloads import _parse_markdown_file

        doc = _parse_markdown_file("no techniques here", Path("SQL Injection/a.md"))
        assert doc is not None
        assert "technique_ids" not in doc["metadata"]

    def test_parse_all_markdown_files_handles_stat_oserror_and_read_error(self, tmp_path: Path, monkeypatch) -> None:
        from cyberred.rag.sources.payloads import _parse_all_markdown_files

        repo = tmp_path / "repo"
        repo.mkdir()
        good = repo / "SQL Injection"
        good.mkdir()
        f1 = good / "one.md"
        f1.write_text("T1105", encoding="utf-8")

        # Force stat() to raise OSError for this file, but do not break pytest/pathlib internals.
        orig_stat = Path.stat

        def _patched_stat(self: Path, *args, **kwargs):
            if self == f1:
                raise OSError("boom")
            return orig_stat(self, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", _patched_stat)

        # Create a path that will raise on read_text
        f2 = good / "two.md"
        f2.write_text("will error", encoding="utf-8")

        orig_read_text = Path.read_text

        def _patched_read_text(self: Path, *args, **kwargs):
            if self == f2:
                raise RuntimeError("boom")
            return orig_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _patched_read_text)

        # Put the erroring file first so the exception path continues to the next file.
        # Add a third file that results in doc=None (empty markdown) without raising.
        f3 = good / "three.md"
        f3.write_text("   \n", encoding="utf-8")

        docs = _parse_all_markdown_files([f2, f3, f1], repo)
        assert len(docs) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_public_api_no_args(tmp_path: Path) -> None:
    """`payloads.ingest()` can be called with no args and uses PAYLOAD content type."""

    # Create a fake repo directory layout with one markdown file
    repo_dir = tmp_path / "payloads"
    (repo_dir / "SQL Injection").mkdir(parents=True)
    (repo_dir / "SQL Injection" / "README.md").write_text(
        "# SQL Injection\nT1190", encoding="utf-8"
    )

    with patch("cyberred.rag.sources.payloads.RAGStore") as MockStore, \
        patch("cyberred.rag.sources.payloads.RAGEmbeddings") as MockEmbeddings, \
        patch("cyberred.rag.sources.payloads.RAGIngestPipeline") as MockPipeline, \
        patch("cyberred.rag.sources.payloads._download_payloads", return_value=repo_dir):

        from cyberred.rag.ingest import IngestionStats

        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process = AsyncMock(
            return_value=IngestionStats(
                source="payloads",
                last_updated=AsyncMock(),
                chunk_count=1,
                document_count=1,
                file_hashes={},
                failed_docs=[],
            )
        )

        from cyberred.rag.sources import payloads

        stats = await payloads.ingest()
        assert stats.source == "payloads"

        # Ensure we asked pipeline to ingest using ContentType.PAYLOAD
        from cyberred.rag.models import ContentType

        _, kwargs = mock_pipeline.process.call_args
        assert kwargs["source"] == "payloads"
        assert kwargs["content_type"] == ContentType.PAYLOAD
