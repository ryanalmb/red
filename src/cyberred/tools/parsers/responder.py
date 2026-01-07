"""Responder output parser for structured finding extraction."""
import re
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import common


def responder_parser(
    stdout: str,
    stderr: str,
    exit_code: int,
    agent_id: str,
    target: str
) -> List[Finding]:
    """
    Parse Responder output and return a list of Findings.
    
    Extracts captured credentials (NTLMv1, NTLMv2, HTTP, etc.).
    
    Args:
        stdout: Raw Responder log output
        stderr: Standard error output (unused)
        exit_code: Exit code from command (unused)
        agent_id: The agent ID that ran the scan
        target: The target network
        
    Returns:
        List of Finding objects for captured credentials
    """
    findings: List[Finding] = []
    
    if not stdout or not stdout.strip():
        return findings
    
    for line in stdout.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # NTLMv2 hash capture
        # Pattern: [SMB] NTLMv2 Hash : DOMAIN\user::DOMAIN:challenge:hash:hash
        # or: [SMB] NTLMv2-SSP Hash : user::DOMAIN:...
        ntlm_match = re.search(
            r'\[(\w+)\]\s+NTLMv[12](?:-SSP)?\s+(?:Hash|Client)\s*:\s*(\S+)',
            line, re.IGNORECASE
        )
        if ntlm_match:
            protocol, hash_data = ntlm_match.groups()
            
            # Extract username from hash
            username = hash_data.split('::')[0] if '::' in hash_data else hash_data.split(':')[0]
            
            # Try to extract client IP
            client_ip = target
            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
            if ip_match:
                client_ip = ip_match.group(1)
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="high",
                target=client_ip,
                evidence=f"[{protocol}] NTLMv2 Hash captured: {username}",
                agent_id=agent_id,
                tool="responder"
            ))
            continue
        
        # HTTP Basic Auth capture
        http_match = re.search(
            r'\[HTTP\].*?(\S+)\s*:\s*(\S+)',
            line, re.IGNORECASE
        )
        if http_match and 'Basic' in line:
            username, password = http_match.groups()
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=f"[HTTP] Basic Auth captured: {username}:{password}",
                agent_id=agent_id,
                tool="responder"
            ))
            continue
        
        # LDAP credential capture
        ldap_match = re.search(
            r'\[LDAP\].*?Cleartext.*?(\S+)\s*:\s*(\S+)',
            line, re.IGNORECASE
        )
        if ldap_match:
            username, password = ldap_match.groups()
            
            findings.append(common.create_finding(
                type_val="credential",
                severity="critical",
                target=target,
                evidence=f"[LDAP] Cleartext credential: {username}:{password}",
                agent_id=agent_id,
                tool="responder"
            ))
    
    return findings
