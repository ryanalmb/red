"""CrackMapExec output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def crackmapexec_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse crackmapexec output and return a list of Findings.
    
    Supports SMB, WinRM, LDAP protocols.
    
    Args:
        stdout: Raw crackmapexec output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for credentials, shares, and vulnerabilities
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Successful credential authentication [+]
        # Pattern: SMB 192.168.1.1 445 DC [+] domain\user:password (Pwn3d!)
        cred_match = re.search(r'(\w+)\s+(\S+)\s+\d+\s+\S+\s+\[\+\]\s+(\S+)\\(\S+):(\S+)', line)
        if cred_match:
            protocol, host, domain, username, password = cred_match.groups()
            is_admin = "(Pwn3d!)" in line or "Pwn3d" in line
            
            evidence = f"[{protocol}] {domain}\\{username}:{password}"
            if is_admin:
                evidence += " (Admin)"
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=host,
                evidence=evidence,
                agent_id=agent_id,
                tool="crackmapexec"
            ))
            continue
        
        # Share enumeration
        # Pattern: SMB 192.168.1.1 445 DC [*] Enumerated shares
        # or: SHARE$ READ,WRITE
        share_match = re.search(r'(\S+)\s+(READ|WRITE|READ,WRITE)', line)
        if share_match and ('SHARE' in line.upper() or '$' in line):
            share_name, permissions = share_match.groups()
            
            findings.append(common.create_finding(
                type_val="share",
                severity="info",
                target=target,
                evidence=f"Share: {share_name} [{permissions}]",
                agent_id=agent_id,
                tool="crackmapexec"
            ))
            continue
        
        # Vulnerability checks (LAPS, GPP, etc.)
        # Pattern: [+] LAPS password retrieved
        vuln_patterns = [
            (r'\[\+\].*LAPS', "LAPS password retrieved"),
            (r'\[\+\].*GPP', "GPP password found"),
            (r'\[\+\].*MS17-010', "MS17-010 vulnerable"),
            (r'\[\+\].*ZeroLogon', "ZeroLogon vulnerable"),
        ]
        
        for pattern, vuln_name in vuln_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(common.create_finding(
                    type_val="vuln",
                    severity="critical",
                    target=target,
                    evidence=f"Vulnerability: {vuln_name}",
                    agent_id=agent_id,
                    tool="crackmapexec"
                ))
                break
    
    return findings
