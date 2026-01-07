"""Impacket secretsdump output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def secretsdump_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse impacket-secretsdump output and return a list of Findings.
    
    Extracts NTLM hashes, Kerberos keys, and cleartext passwords.
    
    Args:
        stdout: Raw secretsdump output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target that was scanned
        
    Returns:
        List of Finding objects for dumped credentials
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    current_section = ""
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Detect section headers
        if '[*]' in line:
            if 'SAM' in line:
                current_section = "SAM"
            elif 'LSA' in line:
                current_section = "LSA"
            elif 'NTDS' in line:
                current_section = "NTDS"
            elif 'Kerberos' in line:
                current_section = "Kerberos"
            continue
        
        # SAM/NTDS hash format: username:rid:lmhash:nthash:::
        sam_match = re.match(r'^([^:]+):(\d+):([a-f0-9]{32}):([a-f0-9]{32}):::', line, re.IGNORECASE)
        if sam_match:
            username, rid, lm_hash, nt_hash = sam_match.groups()
            
            # Skip empty hashes
            if nt_hash == 'aad3b435b51404eeaad3b435b51404ee' or nt_hash == '31d6cfe0d16ae931b73c59d7e0c089c0':
                continue
            
            hash_type = f"{current_section}" if current_section else "NTLM"
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=f"[{hash_type}] {username}:{nt_hash}",
                agent_id=agent_id,
                tool="secretsdump"
            ))
            continue
        
        # Cleartext password (from LSA secrets or DPAPI)
        cleartext_match = re.search(r'Cleartext:\s*(\S+)', line, re.IGNORECASE)
        if cleartext_match:
            password = cleartext_match.group(1)
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=f"[Cleartext] Password: {password}",
                agent_id=agent_id,
                tool="secretsdump"
            ))
            continue
        
        # Kerberos keys
        krb_match = re.match(r'^([^:]+):aes\d+[^:]*:([a-f0-9]+)', line, re.IGNORECASE)
        if krb_match:
            username, key = krb_match.groups()
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="high",
                target=target,
                evidence=f"[Kerberos] {username} AES key",
                agent_id=agent_id,
                tool="secretsdump"
            ))
    
    return findings
