import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common

def hydra_parser(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """
    Parses Hydra stdout and returns a list of Findings.
    """
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
