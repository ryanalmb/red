import pytest
import inspect
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import base
from cyberred.tools.parsers import sqlmap

@pytest.mark.unit
def test_sqlmap_parser_signature():
    """Task 1: Verify sqlmap_parser exists and matches ParserFn signature."""
    try:
        from cyberred.tools.parsers import sqlmap
    except ImportError:
        pytest.fail("Could not import cyberred.tools.parsers.sqlmap")

    assert hasattr(sqlmap, "sqlmap_parser"), "sqlmap_parser function missing"
    
    # Check signature
    sig = inspect.signature(sqlmap.sqlmap_parser)
    params = list(sig.parameters.keys())
    expected_params = ["stdout", "stderr", "exit_code", "agent_id", "target"]
    assert params == expected_params, f"Expected params {expected_params}, got {params}"
    
    # Check return type hint
    assert sig.return_annotation == List[Finding], "Return type must be List[Finding]"

@pytest.mark.unit
def test_empty_output():
    """Task 2: Parser returns empty list for empty/None output."""
    findings = sqlmap.sqlmap_parser("", "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert findings == []
    
    findings = sqlmap.sqlmap_parser(None, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert findings == []

@pytest.mark.unit
def test_invalid_output():
    """Task 2: Parser returns empty list for non-sqlmap output."""
    stdout = "Pinging 127.0.0.1 with 32 bytes of data..."
    findings = sqlmap.sqlmap_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert findings == []

@pytest.mark.unit
def test_extract_vulnerabilities():
    """Task 3 & 4: Extract parameters and injection types."""
    stdout = """
---
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1' AND 5851=5851 AND 'mDWN'='mDWN

    Type: error-based
    Title: MySQL >= 5.5 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (BIGINT UNSIGNED)
    Payload: id=1' AND (SELECT 2*(IF((SELECT * FROM (SELECT CONCAT(0x7162767a71,(SELECT (ELT(2836=2836,1))),0x716a717871,0x78))s), 8446744073709551610, 8446744073709551610))) AND 'cKkH'='cKkH
---
"""
    findings = sqlmap.sqlmap_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert len(findings) == 2
    
    # Task 3: Parameter extraction
    assert "Parameter: id (GET)" in findings[0].evidence
    
    # Task 4: Injection type extraction
    assert findings[0].type == "sqli"
    assert "Type: boolean-based blind" in findings[0].evidence
    assert findings[0].severity == "high" # Based on map
    
    assert findings[1].type == "sqli"
    assert "Type: error-based" in findings[1].evidence
    assert findings[1].severity == "high"

@pytest.mark.unit
def test_extract_dbms():
    """Task 5 & 6: Extract DBMS type and version."""
    stdout = """
[INFO] the back-end DBMS is MySQL
web application technology: PHP 7.4.3, Apache 2.4.41
back-end DBMS: MySQL >= 5.5
    """
    findings = sqlmap.sqlmap_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    
    # Should find the DBMS info
    dbms_finding = next((f for f in findings if "DBMS:" in f.evidence), None)
    assert dbms_finding is not None
    assert dbms_finding.type == "sqli"
    assert dbms_finding.severity == "info"
    assert "MySQL >= 5.5" in dbms_finding.evidence

    # Test PostgreSQL
    stdout_pg = """
    [INFO] the back-end DBMS is PostgreSQL
    back-end DBMS: PostgreSQL 10
    """
    findings_pg = sqlmap.sqlmap_parser(stdout_pg, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    f_pg = findings_pg[0]
    assert "PostgreSQL 10" in f_pg.evidence

    # Test Oracle
    stdout_ora = """
    [INFO] the back-end DBMS is Oracle
    back-end DBMS: Oracle 11g
    """
    findings_ora = sqlmap.sqlmap_parser(stdout_ora, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    f_ora = findings_ora[0]
    assert "Oracle 11g" in f_ora.evidence

@pytest.mark.unit
def test_extract_enumeration():
    """Task 7, 8, 9: Extract databases, tables, columns."""
    stdout = """
available databases [3]:
[*] information_schema
[*] mysql
[*] testdb

Database: testdb
[*] users
[*] products

Table: testdb.users
+----------+-------------+
| Column   | Type        |
+----------+-------------+
| id       | int(11)     |
| username | varchar(50) |
| password | varchar(50) |
+----------+-------------+
    """
    findings = sqlmap.sqlmap_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    
    # Task 7: Databases
    dbs = [f for f in findings if f.type == "sqli_db"]
    assert len(dbs) == 3
    assert any("Database: testdb" in f.evidence for f in dbs)
    
    # Task 8: Tables (Wait, need to implement table extraction in parser)
    # The current parser plan includes this.
    # But wait, looking at my implementation plan, I need to map these to Finding types?
    # Story says: Create Finding for each enumerated table with type="sqli_table"
    # Create Finding for enumerated column with type="sqli_column"
    
    # So I expect separate findings for each table and column row? 
    # Or grouped? Story says "Create Finding for enumerated tables" (plural) or "for each" (singular)?
    # Task 8 desc: "Create Finding for enumerated tables with type='sqli_table'"
    # Task 9 desc: "Create Finding for enumerated columns with type='sqli_column'"
    
    # Let's assume one finding per table and one per column for granularity, 
    # OR maybe grouped by table?
    # "Create Finding for enumerated columns" - possibly "Table: testdb.users columns" finding?
    
    # Given the volume, individual findings for 1000s of columns would be spammy.
    # But for a TDD task, I'll follow the pattern:
    # "Parse table list... Create Finding for enumerated tables"
    # I'll implement it as one finding per detected table/column for now as per "Tier 1" usually extracting findings.
    
    # Actually, looking at the provided output example:
    # available databases [3]: [*] information_schema ...
    # This block is parsed as one finding or multiple?
    # Task 7: "Create Finding for each enumerated database with type='sqli_db'" -> Multiple findings.
    
    # So:
    # Check tables
    tables = [f for f in findings if f.type == "sqli_table"]
    assert len(tables) == 2 # users, products
    assert any("Table: testdb.users" in f.evidence for f in tables)

    # Check columns
    cols = [f for f in findings if f.type == "sqli_column"]
    assert len(cols) == 3 # id, username, password
    assert any("Column: id (int(11))" in f.evidence for f in cols)

@pytest.mark.unit
def test_registration():
    """Task 12 & 13: Export and registration."""
    # Test export from package
    try:
        from cyberred.tools.parsers import sqlmap_parser
    except ImportError:
        pytest.fail("sqlmap_parser not exported from cyberred.tools.parsers")
    
    # Test registration with OutputProcessor
    from cyberred.tools.output import OutputProcessor
    processor = OutputProcessor()
    processor.register_parser("sqlmap", sqlmap_parser)
    assert "sqlmap" in processor.get_registered_parsers()

@pytest.mark.unit
def test_corner_cases():
    """Task 16: Cover edge cases for 100% coverage."""
    # 1. Unknown injection type (severity default)
    stdout = """
---
Parameter: id (GET)
    Type: unknown-injection-type
---
    """
    findings = sqlmap.sqlmap_parser(stdout, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    assert findings[0].severity == "medium"
    
    # 2. Malformed column line (len(parts) < 2)
    stdout_cols = """
Table: testdb.malformed
+----------+-------------+
| Column   | Type        |
+----------+-------------+
| bad_line |
| ok_col   | int         |
+----------+-------------+
    """
    findings = sqlmap.sqlmap_parser(stdout_cols, "", 0, "00000000-0000-0000-0000-000000000001", "127.0.0.1")
    cols = [f for f in findings if f.type == "sqli_column"]
    assert len(cols) == 1
    assert "ok_col" in cols[0].evidence
