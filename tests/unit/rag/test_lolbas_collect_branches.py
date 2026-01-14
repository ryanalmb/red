"""Tests for collection branch edges (doc None without exceptions)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_collect_lolbas_documents_skips_none_docs(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _collect_lolbas_documents

    repo = tmp_path / "repo"
    d = repo / "yml" / "OSBinaries"
    d.mkdir(parents=True)

    # Empty YAML -> parser returns None, should be skipped.
    (d / "empty.yml").write_text("  \n", encoding="utf-8")

    docs = _collect_lolbas_documents(repo)
    assert docs == []


@pytest.mark.unit
def test_collect_gtfobins_documents_skips_none_docs(tmp_path: Path) -> None:
    from cyberred.rag.sources.lolbas import _collect_gtfobins_documents

    repo = tmp_path / "repo"
    d = repo / "_gtfobins"
    d.mkdir(parents=True)

    # Empty markdown -> parser returns None, should be skipped.
    (d / "empty.md").write_text("   ", encoding="utf-8")

    docs = _collect_gtfobins_documents(repo)
    assert docs == []
