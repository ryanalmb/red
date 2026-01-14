import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cyberred.rag.sources import payloads
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings


def _create_payloads_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "payloadsallthethings"
    (repo / "SQL Injection").mkdir(parents=True)
    (repo / "XSS Injection").mkdir(parents=True)

    (repo / "SQL Injection" / "README.md").write_text(
        "# SQLi\nExample T1105 payload", encoding="utf-8"
    )
    (repo / "XSS Injection" / "xss.md").write_text(
        "# XSS\nExample T1059.004", encoding="utf-8"
    )
    return repo


@pytest.mark.integration
@pytest.mark.asyncio
async def test_payloads_ingest_flow(tmp_path, monkeypatch):
    repo_dir = _create_payloads_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    # Ensure stats file goes under tmp_path to avoid cross-test pollution
    monkeypatch.setattr(payloads, "DEFAULT_CACHE_DIR", tmp_path / "cache")

    with patch("cyberred.rag.sources.payloads._download_payloads", return_value=repo_dir):
        stats = await payloads.ingest(store=store, embeddings=embeddings, incremental=False)

    assert stats.source == "payloads"
    assert stats.document_count >= 1
    assert stats.chunk_count >= 1

    results = await store.search([0.1] * 768, top_k=50)
    assert len(results) >= 1
    assert all(r.source == "payloads" for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_payloads_incremental_skips_unchanged(tmp_path, monkeypatch):
    repo_dir = _create_payloads_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(payloads, "DEFAULT_CACHE_DIR", tmp_path / "cache")

    with patch("cyberred.rag.sources.payloads._download_payloads", return_value=repo_dir):
        stats1 = await payloads.ingest(store=store, embeddings=embeddings, incremental=False)
        initial = stats1.chunk_count

        stats2 = await payloads.ingest(store=store, embeddings=embeddings, incremental=True)

    # second run should not create duplicates
    results = await store.search([0.1] * 768, top_k=200)
    assert len(results) == initial
    assert stats2.chunk_count in (0, initial)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_payloads_force_refresh_pass_through(tmp_path, monkeypatch):
    repo_dir = _create_payloads_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(payloads, "DEFAULT_CACHE_DIR", tmp_path / "cache")

    with patch("cyberred.rag.sources.payloads._download_payloads", return_value=repo_dir) as mock_download:
        await payloads.ingest(store=store, embeddings=embeddings, force_refresh=False)
        await payloads.ingest(store=store, embeddings=embeddings, force_refresh=True)

    assert mock_download.call_count == 2
    assert mock_download.call_args[1].get("force_refresh") is True
