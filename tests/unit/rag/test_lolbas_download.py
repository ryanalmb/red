"""Additional tests to cover lolbas.py download + ingest branches."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.unit
def test_git_sparse_checkout_with_sparse_paths_runs_sparse_checkout(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _git_sparse_checkout

    repo_dir = tmp_path / "repo"

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return None

    with patch("cyberred.rag.sources.lolbas.subprocess.run", side_effect=_fake_run):
        _git_sparse_checkout("https://example.com/repo", repo_dir, ["a", "b"])

    assert calls[0][0][0:2] == ["git", "clone"]
    assert calls[1][0][0:3] == ["git", "sparse-checkout", "set"]
    assert calls[1][1].get("cwd") == repo_dir


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_lolbas_force_refresh_removes_existing(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"
    repo_dir = cache / "lolbas"
    repo_dir.mkdir(parents=True)

    with patch("cyberred.rag.sources.lolbas.shutil.rmtree") as rm, patch(
        "cyberred.rag.sources.lolbas._git_sparse_checkout"
    ) as git:
        out = await lolbas._download_lolbas(cache, force_refresh=True)
        assert out == repo_dir
        rm.assert_called_once()
        git.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_gtfobins_force_refresh_removes_existing(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"
    repo_dir = cache / "gtfobins"
    repo_dir.mkdir(parents=True)

    with patch("cyberred.rag.sources.lolbas.shutil.rmtree") as rm, patch(
        "cyberred.rag.sources.lolbas._git_sparse_checkout"
    ) as git:
        out = await lolbas._download_gtfobins(cache, force_refresh=True)
        assert out == repo_dir
        rm.assert_called_once()
        git.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_gtfobins_git_error_raises(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"
    err = subprocess.CalledProcessError(1, ["git"], stderr=b"no")

    with patch("cyberred.rag.sources.lolbas._git_sparse_checkout", side_effect=err):
        with pytest.raises(RuntimeError):
            await lolbas._download_gtfobins(cache, force_refresh=True)


@pytest.mark.unit
def test_gtfobins_techniques_dedup_across_functions() -> None:
    from cyberred.rag.sources.lolbas import _gtfobins_techniques_from_functions

    functions = {"shell": [], "reverse-shell": []}
    out = _gtfobins_techniques_from_functions(functions)
    assert out == ["T1059.004", "T1571"]


@pytest.mark.unit
def test_parse_gtfobins_frontmatter_non_dict_returns_none() -> None:
    from cyberred.rag.sources.lolbas import _parse_gtfobins_frontmatter

    md = """---
- a
- b
---
body
"""
    fm, body = _parse_gtfobins_frontmatter(md)
    assert fm is None
    assert body == md


@pytest.mark.unit
def test_parse_lolbas_yaml_commands_contains_non_dict_skips() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    yml = """
Name: X
Description: D
Commands:
  - justastring
  - Command: x
"""
    doc = _parse_lolbas_yaml(yml, Path("yml/OSBinaries/X.yml"))
    assert doc is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ingest_no_args_creates_defaults_and_uses_cheatsheet(tmp_path: Path) -> None:
    """`lolbas.ingest()` can be called with no args and uses CHEATSHEET content type."""

    lol_repo = tmp_path / "lolbas"
    gtf_repo = tmp_path / "gtfobins"
    lol_repo.mkdir()
    gtf_repo.mkdir()

    with (
        patch("cyberred.rag.sources.lolbas.RAGStore") as MockStore,
        patch("cyberred.rag.sources.lolbas.RAGEmbeddings") as MockEmbeddings,
        patch("cyberred.rag.sources.lolbas.RAGIngestPipeline") as MockPipeline,
        patch("cyberred.rag.sources.lolbas._download_lolbas", return_value=lol_repo),
        patch("cyberred.rag.sources.lolbas._download_gtfobins", return_value=gtf_repo),
        patch("cyberred.rag.sources.lolbas.asyncio.to_thread", new_callable=AsyncMock) as to_thread,
    ):
        # first to_thread: collect lolbas docs, second: gtfobins docs
        to_thread.side_effect = [[{"text": "a", "metadata": {"id": "1"}}], [{"text": "b", "metadata": {"id": "2"}}]]

        from cyberred.rag.ingest import IngestionStats

        mock_pipeline = MockPipeline.return_value
        mock_pipeline.process = AsyncMock(
            return_value=IngestionStats(
                source="lolbas",
                last_updated=AsyncMock(),
                chunk_count=2,
                document_count=2,
                file_hashes={},
                failed_docs=[],
            )
        )

        from cyberred.rag.sources import lolbas
        from cyberred.rag.models import ContentType

        stats = await lolbas.ingest()
        assert stats.source == "lolbas"

        _, kwargs = mock_pipeline.process.call_args
        assert kwargs["source"] == "lolbas"
        assert kwargs["content_type"] == ContentType.CHEATSHEET

        MockStore.assert_called_once()
        MockEmbeddings.assert_called_once()
