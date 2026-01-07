"""Mimikatz output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def mimikatz_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse mimikatz output and return a list of Findings.
    
    Extracts plaintext passwords, NTLM hashes, and Kerberos tickets.
    
    Args:
        stdout: Raw mimikatz output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for credentials
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    current_user = ""
    current_domain = ""
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Track current user context
        user_match = re.search(r'\*\s+Username\s*:\s*(\S+)', line, re.IGNORECASE)
        if user_match:
            current_user = user_match.group(1)
            continue
        
        domain_match = re.search(r'\*\s+Domain\s*:\s*(\S+)', line, re.IGNORECASE)
        if domain_match:
            current_domain = domain_match.group(1)
            continue
        
        # Plaintext password
        password_match = re.search(r'\*\s+Password\s*:\s*(\S+)', line, re.IGNORECASE)
        if password_match:
            password = password_match.group(1)
            
            # Skip null or empty passwords
            if password.lower() in ['(null)', 'null', '']:
                continue
            
            evidence = f"Plaintext: {current_domain}\\{current_user}:{password}"
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="mimikatz"
            ))
            continue
        
        # NTLM hash
        ntlm_match = re.search(r'\*\s+NTLM\s*:\s*([a-f0-9]{32})', line, re.IGNORECASE)
        if ntlm_match:
            ntlm_hash = ntlm_match.group(1)
            
            # Skip empty hashes
            if ntlm_hash == '31d6cfe0d16ae931b73c59d7e0c089c0':
                continue
            
            evidence = f"NTLM: {current_domain}\\{current_user}:{ntlm_hash}"
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=evidence,
                agent_id=agent_id,
                tool="mimikatz"
            ))
            continue
        
        # Kerberos ticket
        krb_match = re.search(r'Kerberos.*?:\s*(\S+)', line, re.IGNORECASE)
        if krb_match and ('ticket' in line.lower() or 'kirbi' in line.lower()):
            ticket_info = krb_match.group(1)
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="high",
                target=target,
                evidence=f"Kerberos ticket: {current_user} - {ticket_info}",
                agent_id=agent_id,
                tool="mimikatz"
            ))
    
    return findings
