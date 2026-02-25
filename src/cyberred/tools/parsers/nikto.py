import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common

def nikto_parser(
    stdout: str,
    stderr: str = "",
    exit_code: int | str = 0,
    agent_id: str = "",
    target: str = "",
    error_type: str | None = None,
) -> List[Finding]:
    """
    Parses Nikto stdout and returns a list of Findings.
    """
    # Backward compatibility for legacy signature: (stdout, agent_id, target)
    if not agent_id and not target and isinstance(exit_code, str):
        agent_id = stderr
        target = exit_code
        stderr = ""
        exit_code = 0

    findings: List[Finding] = []
    
    # Pattern: Optional[+ ](Ref): (Path): (Desc)
    # Handles lines starting with + or not
    pattern = re.compile(r'(?:\+\s+)?((?:OSVDB|CVE)-\S+):\s+([^:]+):\s+(.+)')
    
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
            
        match = pattern.search(line)
        if match:
            ref, path, desc = match.groups()
            
            # Determine severity
            severity = "high" if "CVE" in ref else "medium"
            
            findings.append(common.create_finding(
                type_val="web_vuln",
                severity=severity,
                target=target,
                evidence=f"[{ref}] {path}: {desc}",
                agent_id=agent_id,
                tool="nikto"
            ))
            
    return findings
