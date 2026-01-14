"""Targeted tests to hit remaining branch edges in lolbas._parse_lolbas_yaml."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_lolbas_commands_section_skipped_when_empty_list() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    yml = """
Name: Z
Description: D
Commands: []
"""
    doc = _parse_lolbas_yaml(yml, Path("yml/OSBinaries/Z.yml"))
    assert doc is not None
    assert "## Commands" not in doc["text"]


@pytest.mark.unit
def test_lolbas_command_desc_present_without_command_hits_cmd_false_desc_true() -> None:
    from cyberred.rag.sources.lolbas import _parse_lolbas_yaml

    yml = """
Name: W
Description: D
Commands:
  - Description: only-desc
"""
    doc = _parse_lolbas_yaml(yml, Path("yml/OSBinaries/W.yml"))
    assert doc is not None
    # Should include the description bullet but no backticked command.
    assert "only-desc" in doc["text"]
    assert "`" not in doc["text"]  # no command formatting
