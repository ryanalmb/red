"""Impacket psexec output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def psexec_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse impacket-psexec output and return a list of Findings.
    
    Detects successful shell access.
    
    Args:
        stdout: Raw psexec output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for shell access
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    # Success indicators
    success_patterns = [
        r'\[\*\]\s*Process.*?created',
        r'\[\*\]\s*Opening\s+SVCManager',
        r'\[\*\]\s*Creating\s+service',
        r'\[\*\]\s*Starting\s+service',
        r'Microsoft Windows.*?Copyright',
        r'C:\\Windows\\system32>',
        r'NT AUTHORITY\\SYSTEM',
    ]
    
    shell_success = False
    username = ""
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Extract username from connection info
        user_match = re.search(r'Requesting shares on (\S+)\s*\.\.\.\s*using (\S+)', line)
        if user_match:
            username = user_match.group(2)
            continue
        
        # Check for success indicators
        for pattern in success_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                shell_success = True
                break
    
    if shell_success:
        evidence = f"Shell access obtained on {target}"
        if username:
            evidence += f" as {username}"
        
        findings.append(common.create_finding(
            type_val="shell_access",
            severity="critical",
            target=target,
            evidence=evidence,
            agent_id=agent_id,
            tool="psexec"
        ))
    
    # Check for explicit failure
    if not shell_success:
        failure_patterns = [
            r'STATUS_LOGON_FAILURE',
            r'STATUS_ACCESS_DENIED',
            r'ERROR.*?failed',
        ]
        
        for line in stdout.split('\n'):
            for pattern in failure_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # No finding for failures, but we could log if needed
                    pass
    
    return findings
