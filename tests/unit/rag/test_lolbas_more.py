"""Extra unit tests to reach 100% coverage for lolbas.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_validate_technique_id_false_on_empty() -> None:
    from cyberred.rag.sources.lolbas import validate_technique_id

    assert validate_technique_id("") is False


@pytest.mark.unit
def test_extract_technique_ids_dedup_and_validate() -> None:
    from cyberred.rag.sources.lolbas import _extract_technique_ids

    assert _extract_technique_ids("T1105 T1105 bad T12") == ["T1105"]


@pytest.mark.unit
def test_git_sparse_checkout_skips_sparse_when_no_paths(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _git_sparse_checkout

    repo_dir = tmp_path / "repo"

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return None

    with patch("cyberred.rag.sources.lolbas.subprocess.run", side_effect=_fake_run):
        _git_sparse_checkout("https://example.com/repo", repo_dir, [])

    assert len(calls) == 1
    assert calls[0][0][0:2] == ["git", "clone"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_lolbas_uses_cache(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"
    repo_dir = cache / "lolbas"
    repo_dir.mkdir(parents=True)

    out = await lolbas._download_lolbas(cache, force_refresh=False)
    assert out == repo_dir


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_gtfobins_uses_cache(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"
    repo_dir = cache / "gtfobins"
    repo_dir.mkdir(parents=True)

    out = await lolbas._download_gtfobins(cache, force_refresh=False)
    assert out == repo_dir


@pytest.mark.unit
@pytest.mark.asyncio
async def test_download_lolbas_git_error_raises(tmp_path: Path) -> None:
    from cyberred.rag.sources import lolbas

    cache = tmp_path / "cache"

    err = subprocess.CalledProcessError(1, ["git"], stderr=b"no")
    with patch("cyberred.rag.sources.lolbas._git_sparse_checkout", side_effect=err):
        with pytest.raises(RuntimeError):
            await lolbas._download_lolbas(cache, force_refresh=True)


@pytest.mark.unit
def test_parse_lolbas_yaml_empty_returns_none() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    assert _parse_lolbas_yaml("  ", Path("x.yml")) is None


@pytest.mark.unit
def test_parse_lolbas_yaml_non_dict_returns_none() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    assert _parse_lolbas_yaml("- a\n- b\n", Path("x.yml")) is None


@pytest.mark.unit
def test_parse_lolbas_yaml_fallback_technique_from_whole_file_when_no_mitreid() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    yml = """
Name: Thing
Description: Something
Commands:
  - Command: thing.exe
    Description: does stuff
""" + "\n# T1059.004"  # technique in whole text

    doc = _parse_lolbas_yaml(yml, Path("yml/OSBinaries/Thing.yml"))
    assert doc is not None
    assert doc["metadata"]["technique_ids"] == ["T1059.004"]


@pytest.mark.unit
def test_parse_gtfobins_frontmatter_variants() -> None:
    from cyberred.rag.sources.lolbas import _parse_gtfobins_frontmatter

    fm, body = _parse_gtfobins_frontmatter("no frontmatter")
    assert fm is None
    assert body == "no frontmatter"

    # starts with --- but doesn't match regex
    fm2, body2 = _parse_gtfobins_frontmatter("---\nno end")
    assert fm2 is None
    assert body2 == "---\nno end"


@pytest.mark.unit
def test_parse_gtfobins_frontmatter_yaml_error_returns_none() -> None:
    from cyberred.rag.sources.lolbas import _parse_gtfobins_frontmatter

    bad = """---
: bad: [
---
body
"""
    fm, body = _parse_gtfobins_frontmatter(bad)
    assert fm is None


@pytest.mark.unit
def test_gtfobins_techniques_from_functions_non_dict() -> None:
    from cyberred.rag.sources.lolbas import _gtfobins_techniques_from_functions

    assert _gtfobins_techniques_from_functions(["x"]) == []


@pytest.mark.unit
def test_parse_gtfobins_markdown_empty_returns_none() -> None:
    from cyberred.rag.sources.lolbas import _parse_gtfobins_markdown

    assert _parse_gtfobins_markdown("   ", Path("_gtfobins/x.md")) is None


@pytest.mark.unit
def test_collect_gtfobins_documents_missing_root_returns_empty(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _collect_gtfobins_documents

    repo = tmp_path / "repo"
    repo.mkdir()
    assert _collect_gtfobins_documents(repo) == []


@pytest.mark.unit
def test_collect_lolbas_documents_missing_dirs_returns_empty(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _collect_lolbas_documents

    repo = tmp_path / "repo"
    repo.mkdir()
    assert _collect_lolbas_documents(repo) == []


@pytest.mark.unit
def test_collect_lolbas_documents_handles_read_error(tmp_path: Path, monkeypatch) -> None:
    from cyberred.rag.sources.lolbas import _collect_lolbas_documents

    repo = tmp_path / "repo"
    d = repo / "yml" / "OSBinaries"
    d.mkdir(parents=True)
    f = d / "a.yml"
    f.write_text("Name: A", encoding="utf-8")

    orig_read_text = Path.read_text

    def _patched_read_text(self: Path, *args, **kwargs):
        if self == f:
            raise RuntimeError("boom")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _patched_read_text)

    assert _collect_lolbas_documents(repo) == []


@pytest.mark.unit
def test_collect_gtfobins_documents_handles_read_error(tmp_path: Path, monkeypatch) -> None:
    from cyberred.rag.sources.lolbas import _collect_gtfobins_documents

    repo = tmp_path / "repo"
    d = repo / "_gtfobins"
    d.mkdir(parents=True)
    f = d / "a.md"
    f.write_text("---\nfunctions: {}\n---\nbody", encoding="utf-8")

    orig_read_text = Path.read_text

    def _patched_read_text(self: Path, *args, **kwargs):
        if self == f:
            raise RuntimeError("boom")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _patched_read_text)

    assert _collect_gtfobins_documents(repo) == []
