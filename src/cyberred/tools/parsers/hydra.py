import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common

def hydra_parser(
    stdout: str,
    stderr: str = "",
    exit_code: int | str = 0,
    agent_id: str = "",
    target: str = "",
    error_type: str | None = None,
) -> List[Finding]:
    """
    Parses Hydra stdout and returns a list of Findings.
    """
    # Backward compatibility for legacy signature: (stdout, agent_id, target)
    if not agent_id and not target and isinstance(exit_code, str):
        agent_id = stderr
        target = exit_code
        stderr = ""
        exit_code = 0

    findings: List[Finding] = []
    
    # Pattern: [22][ssh] host: 192.168.1.1   login: admin   password: password123
    # Use [\w-]+ for service name to capture 'http-get' etc.
    pattern = re.compile(r'\[(\d+)\]\[([\w-]+)\]\s+host:\s+(\S+)\s+login:\s+(\S+)\s+password:\s+(\S+)')
    
    for match in pattern.finditer(stdout):
        port, service, host, username, password = match.groups()
        
        evidence = f"[{service}:{port}] {username}:{password}"
        
        findings.append(common.create_finding(
            type_val="credential",
            severity="critical",
            target=host,
            evidence=evidence,
            agent_id=agent_id,
            tool="hydra"
        ))
        
    return findings
