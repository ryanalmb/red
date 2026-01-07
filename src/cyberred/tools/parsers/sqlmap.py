import re
from typing import List
import structlog
from cyberred.core.models import Finding
from cyberred.tools.parsers.common import create_finding

log = structlog.get_logger()

# Severity mapping for SQL injection types
# Rationale:
# - Union/Stacked: Allow arbitrary data retrieval or command execution (Critical)
# - Error/Boolean/Time: Allow data retrieval but often slower or partial (High)
SQLI_SEVERITY_MAP = {
    "union query": "critical",
    "stacked queries": "critical", 
    "error-based": "high",
    "boolean-based blind": "high",
    "time-based blind": "high"
}



def _get_severity(inj_type: str) -> str:
    """Get severity from injection type string."""
    for key, sev in SQLI_SEVERITY_MAP.items():
        if key in inj_type.lower():
            return sev
    return "medium" # Default

def sqlmap_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """
    Parse sqlmap output to extract SQL injection findings.
    
    Args:
        stdout: Standard output from sqlmap
        stderr: Standard error from sqlmap
        exit_code: Exit code from sqlmap process
        agent_id: ID of the agent executing the tool
        target: Target IP or URL
        
    Returns:
        List of Finding objects (type="sqli", "sqli_db", "sqli_table", "sqli_column")
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
        
    # 1. Injection Points
    # Split by separator to handle multiple parameters, if present. 
    # The structure usually has "---" blocks for parameters.
    param_blocks = re.split(r'---\s*\n', stdout)
    
    for block in param_blocks:
        # Regex: Parameter: id (GET)
        param_match = re.search(r'Parameter: (\w+) \((\w+)\)', block)
        if param_match:
            p_name, p_type = param_match.groups()
            
            # Find all injection types in this block
            # Regex: Type: boolean-based blind
            for inj_type in re.findall(r'Type: ([^\n]+)', block):
                 sev = _get_severity(inj_type)
                 findings.append(create_finding(
                    type_val="sqli",
                    severity=sev,
                    target=target,
                    evidence=f"Parameter: {p_name} ({p_type}) | Type: {inj_type.strip()}",
                    agent_id=agent_id,
                    tool="sqlmap"
                 ))
                 
    # 2. Database Info
    # Regex: back-end DBMS: MySQL >= 5.0
    if dbms := re.search(r'back-end DBMS:\s*(.+)', stdout):
        findings.append(create_finding(
            type_val="sqli",
            severity="info",
            target=target,
            evidence=f"DBMS: {dbms.group(1).strip()}",
            agent_id=agent_id,
            tool="sqlmap"
        ))

    # 3. Enumeration (DBs, Tables, Columns)
    
    # Databases
    # Regex: available databases [3]:\n[*] ...
    if dbs_block := re.search(r'available databases \[\d+\]:\n((?:\[\*\] .+\n)+)', stdout):
        for db in re.findall(r'\[\*\] (\S+)', dbs_block.group(1)):
            findings.append(create_finding("sqli_db", "info", target, f"Database: {db}", agent_id, "sqlmap"))

    # Tables
    # Regex: Database: testdb\n[2 tables]\n[*] users...
    # Allow optional [N tables] line
    db_table_blocks = re.findall(r'Database: (\S+)\n(?:\[\d+ tables\]\n)?((?:\[\*\] .+\n)+)', stdout)
    for db_name, table_block in db_table_blocks:
        for table in re.findall(r'\[\*\] (\S+)', table_block):
            findings.append(create_finding("sqli_table", "info", target, f"Table: {db_name}.{table}", agent_id, "sqlmap"))

    # Columns
    # Regex: Table: testdb.users\n[3 columns]\n... table content ...
    # Allow optional [N columns] line
    table_col_blocks = re.findall(r'Table: (\S+)\n(?:\[\d+ columns\]\n)?[+|\-\s]+Column[+|\-\s]+Type[+|\-\s]+\n((?:\| .+\n)+)', stdout)
    for table_name, col_block in table_col_blocks:
        for line in col_block.strip().split('\n'):
            # | id       | int(11)     |
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 2:
                col_name, col_type = parts[0], parts[1]
                findings.append(create_finding("sqli_column", "info", target, f"Column: {col_name} ({col_type})", agent_id, "sqlmap"))

    log.info("sqlmap_parsed", target=target, findings_count=len(findings))
    return findings
