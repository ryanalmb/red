"""Metasploit output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def metasploit_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse Metasploit (msfconsole) output and return a list of Findings.
    
    Extracts session information and exploit success messages.
    
    Args:
        stdout: Raw Metasploit output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for sessions and vulnerabilities
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Session opened
        # Pattern: [*] Meterpreter session 1 opened (192.168.1.1:4444 -> 192.168.1.2:49152)
        # or: [*] Command shell session 2 opened
        session_match = re.search(
            r'\[\*\]\s+(Meterpreter|Command\s+shell)\s+session\s+(\d+)\s+opened',
            line, re.IGNORECASE
        )
        if session_match:
            session_type, session_id = session_match.groups()
            
            findings.append(common.create_finding(
                type_val="session",
                severity="critical",
                target=target,
                evidence=f"{session_type} session {session_id} opened",
                agent_id=agent_id,
                tool="metasploit"
            ))
            continue
        
        # Exploit success messages
        # Pattern: [+] 192.168.1.1:445 - exploit/windows/smb/ms17_010_eternalblue - WIN
        exploit_match = re.search(
            r'\[\+\]\s+(\S+).*?(exploit/\S+).*?(WIN|SUCCESS|VULNERABLE)',
            line, re.IGNORECASE
        )
        if exploit_match:
            host, exploit_module, status = exploit_match.groups()
            
            findings.append(common.create_finding(
                type_val="vuln",
                severity="critical",
                target=host if ':' not in host else host.split(':')[0],
                evidence=f"Exploit success: {exploit_module}",
                agent_id=agent_id,
                tool="metasploit"
            ))
            continue
        
        # Generic vulnerability check
        # Pattern: [+] 192.168.1.1:445 - Host is VULNERABLE
        vuln_match = re.search(
            r'\[\+\]\s+(\S+).*?(?:is\s+)?VULNERABLE',
            line, re.IGNORECASE
        )
        if vuln_match:
            host = vuln_match.group(1)
            
            findings.append(common.create_finding(
                type_val="vuln",
                severity="high",
                target=host if ':' not in host else host.split(':')[0],
                evidence=f"Vulnerability confirmed: {line}",
                agent_id=agent_id,
                tool="metasploit"
            ))
    
    return findings
