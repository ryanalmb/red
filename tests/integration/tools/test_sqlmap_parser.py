import pytest
from pathlib import Path
from cyberred.tools.parsers import sqlmap_parser

@pytest.mark.integration
def test_sqlmap_basic_fixture():
    """Test parsing of basic sqlmap output fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/sqlmap_basic.txt")
    content = fixture_path.read_text()
    findings = sqlmap_parser(content, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    
    assert len(findings) >= 2 # 1 SQLi + 1 DBMS info
    
    sqli = [f for f in findings if f.type == "sqli"]
    assert len(sqli) >= 2 # One finding plus DBMS info which is type=sqli severity=info in implementation?
    # Inspect types/severities
    vulns = [f for f in sqli if f.severity == "high"]
    assert len(vulns) == 1
    assert "Type: boolean-based blind" in vulns[0].evidence

@pytest.mark.integration
def test_sqlmap_multi_fixture():
    """Test parsing of multiple findings fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/sqlmap_multi.txt")
    content = fixture_path.read_text()
    findings = sqlmap_parser(content, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    
    # 3 SQLi types + 1 DBMS info
    vulns = [f for f in findings if f.type == "sqli" and f.severity in ("critical", "high")]
    assert len(vulns) == 3
    
    types = [f.evidence for f in vulns]
    assert any("Type: boolean-based blind" in e for e in types)
    assert any("Type: error-based" in e for e in types)
    assert any("Type: UNION query" in e for e in types)

@pytest.mark.integration
def test_sqlmap_enum_fixture():
    """Test parsing of enumeration fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/sqlmap_enum.txt")
    content = fixture_path.read_text()
    findings = sqlmap_parser(content, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    
    # DBs: information_schema, testdb
    dbs = [f for f in findings if f.type == "sqli_db"]
    assert len(dbs) == 2
    
    # Tables: products, users
    tables = [f for f in findings if f.type == "sqli_table"]
    assert len(tables) == 2
    
    # Columns: id, username, password
    cols = [f for f in findings if f.type == "sqli_column"]
    assert len(cols) == 3

@pytest.mark.integration
def test_sqlmap_nosqli_fixture():
    """Test parsing of output with no findings."""
    fixture_path = Path("tests/fixtures/tool_outputs/sqlmap_nosqli.txt")
    content = fixture_path.read_text()
    findings = sqlmap_parser(content, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert findings == []
