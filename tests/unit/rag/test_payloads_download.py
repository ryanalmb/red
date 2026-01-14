"""Extra unit tests to cover Payloads download/git paths."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_payloads_uses_cache_when_present(tmp_path: Path) -> None:
    from cyberred.rag.sources import payloads

    cache = tmp_path / "cache"
    repo_dir = cache / "payloadsallthethings"
    repo_dir.mkdir(parents=True)

    out = await payloads._download_payloads(cache, force_refresh=False)
    assert out == repo_dir


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_payloads_force_refresh_removes_existing(tmp_path: Path) -> None:
    from cyberred.rag.sources import payloads

    cache = tmp_path / "cache"
    repo_dir = cache / "payloadsallthethings"
    repo_dir.mkdir(parents=True)

    with patch("cyberred.rag.sources.payloads.shutil.rmtree") as rm, patch(
        "cyberred.rag.sources.payloads._git_sparse_checkout"
    ) as git:
        out = await payloads._download_payloads(cache, force_refresh=True)
        assert out == repo_dir
        rm.assert_called_once()
        git.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_payloads_git_error_raises_runtimeerror(tmp_path: Path) -> None:
    from cyberred.rag.sources import payloads

    cache = tmp_path / "cache"

    err = subprocess.CalledProcessError(1, ["git"], stderr=b"nope")
    with patch("cyberred.rag.sources.payloads._git_sparse_checkout", side_effect=err):
        with pytest.raises(RuntimeError):
            await payloads._download_payloads(cache, force_refresh=True)


@pytest.mark.unit
def test_git_sparse_checkout_invokes_git_commands(tmp_path: Path) -> None:
    from cyberred.rag.sources import payloads

    repo_dir = tmp_path / "repo"

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return None

    with patch("cyberred.rag.sources.payloads.subprocess.run", side_effect=_fake_run):
        payloads._git_sparse_checkout(repo_dir)

    assert calls[0][0][0:2] == ["git", "clone"]
    assert calls[1][0][0:3] == ["git", "sparse-checkout", "set"]
