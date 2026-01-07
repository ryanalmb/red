import pytest
from unittest.mock import patch, MagicMock
from typing import List
import inspect
import json

from cyberred.tools.parsers.nuclei import nuclei_parser
from cyberred.core.models import Finding

@pytest.mark.unit
def test_nuclei_parser_signature():
    """Verify nuclei_parser exists and matches ParserFn signature."""
    assert callable(nuclei_parser)
    sig = inspect.signature(nuclei_parser)
    params = list(sig.parameters.keys())
    assert params == ['stdout', 'stderr', 'exit_code', 'agent_id', 'target']
    assert sig.return_annotation == List[Finding] or sig.return_annotation == list[Finding]

@pytest.mark.unit
def test_nuclei_parser_empty_input():
    results = nuclei_parser("", "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert results == []

@pytest.mark.unit
def test_nuclei_parser_invalid_json():
    # Should not raise exception
    results = nuclei_parser("{invalid", "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert results == []

@pytest.mark.unit
def test_nuclei_parser_json_lines():
    # Verify it iterates lines
    with patch('json.loads') as mock_loads:
        mock_loads.return_value = {"template-id": "t", "info": {"severity": "info"}}
        stdout = '{"a": 1}\n{"b": 2}'
        nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
        assert mock_loads.call_count == 2

@pytest.mark.unit
def test_nuclei_parser_extracts_template_id_severity():
    import uuid
    stdout = json.dumps({
        "template-id": "test-template",
        "info": {"severity": "High"},
        "matched-at": "http://example.com"
    })
    
    agent_id = str(uuid.uuid4())
    results = nuclei_parser(stdout, "", 0, agent_id, "target.com")
    assert len(results) == 1
    f = results[0]
    assert f.severity == "high" 
    assert "test-template" in f.evidence

@pytest.mark.unit
def test_nuclei_parser_extracts_cve():
    # Case 1: classification.cve-id
    stdout1 = json.dumps({
        "template-id": "cve-test",
        "info": {
            "severity": "critical", 
            "classification": {"cve-id": "CVE-2021-1234"}
        },
        "matched-at": "url"
    })
    # Case 2: metadata.cve-id
    stdout2 = json.dumps({
        "template-id": "cve-test-2",
        "info": {
            "severity": "critical", 
            "metadata": {"cve-id": "CVE-2021-5678"}
        },
        "matched-at": "url"
    })
    
    stdout = stdout1 + "\n" + stdout2
    
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 2
    assert "CVE: CVE-2021-1234" in results[0].evidence
    assert "CVE: CVE-2021-5678" in results[1].evidence

@pytest.mark.unit
def test_nuclei_parser_extracts_url_evidence():
    stdout = json.dumps({
        "template-id": "t",
        "info": {"severity": "info"},
        "matched-at": "http://target.com/vuln",
        "extracted-results": ["data1", "data2"]
    })
    
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 1
    evidence = results[0].evidence
    assert "URL: http://target.com/vuln" in evidence
    assert "Extracted: data1, data2" in evidence

@pytest.mark.unit
def test_nuclei_parser_finding_type():
    stdout = json.dumps({
        "template-id": "1", "info": {"severity": "info", "tags": ["misc"], "classification": {"cve-id": "CVE-1"}}, "matched-at": "u"
    }) + "\n" + json.dumps({
        "template-id": "2", "info": {"severity": "info", "tags": ["exposure"]}, "matched-at": "u"
    }) + "\n" + json.dumps({
        "template-id": "3", "info": {"severity": "info", "tags": ["misconfig"]}, "matched-at": "u"
    }) + "\n" + json.dumps({
        "template-id": "4", "info": {"severity": "info", "tags": ["other"]}, "matched-at": "u"
    })
    
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 4
    assert results[0].type == "cve"
    assert results[1].type == "exposure"
    assert results[2].type == "misconfiguration"
    assert results[3].type == "vulnerability"

@pytest.mark.unit
def test_nuclei_parser_extracts_cvss():
    stdout = json.dumps({
        "template-id": "t", "info": {"severity": "info", "classification": {"cve-id": "cve", "cvss-score": 9.8}}, "matched-at": "u"
    })
    
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 1
    assert "CVSS: 9.8" in results[0].evidence

@pytest.mark.unit
def test_nuclei_parser_plain_text():
    stdout = "[2025-01-01 12:00:00] [template-test] [http] [high] http://example.com/vuln [extracted]"
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 1
    f = results[0]
    assert "Template: template-test" in f.evidence
    assert "URL: http://example.com/vuln" in f.evidence

@pytest.mark.unit
def test_nuclei_parser_exported():
    try:
        from cyberred.tools.parsers import nuclei_parser
    except ImportError:
        pytest.fail("nuclei_parser not exported from cyberred.tools.parsers")

@pytest.mark.unit
def test_nuclei_parser_unknown_severity():
    stdout = json.dumps({"template-id": "t", "info": {"severity": "unknown"}, "matched-at": "u"})
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 1
    assert results[0].severity == "info"

@pytest.mark.unit
def test_plain_text_mixed():
    stdout = """[2021] [t] [http] [info] u
    Invalid Line
    [2021] [t2] [http] [info] u2
    """
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 2

@pytest.mark.unit
def test_nuclei_parser_coverage_gaps():
    # 1. Empty lines in JSON (Line 55)
    # 2. Invalid JSON line but valid overall format (Line 60-62)
    # Input must pass _is_json_format (first line starts/ends with {})
    stdout = '{"template-id": "t1", "info": {"severity": "info"}, "matched-at": "u1"}\n\nBROKEN JSON\n{"template-id": "t2", "info": {"severity": "info"}, "matched-at": "u2"}'
    
    with patch('structlog.get_logger') as mock_log:
        results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
        
        assert len(results) == 2
        assert results[0].evidence == "Template: t1 | URL: u1"
        assert results[1].evidence == "Template: t2 | URL: u2"


@pytest.mark.unit
def test_nuclei_parser_plain_cve_classification():
    """Verify that only actual CVE IDs in template-id result in 'cve' type."""
    stdout = (
        "[2021] [CVE-2021-44228] [http] [critical] url\n"
        "[2021] [apache-cve-check] [http] [high] url\n"
    )
    results = nuclei_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000000", "target")
    assert len(results) == 2
    assert results[0].type == "cve"
    assert results[1].type == "vulnerability"

